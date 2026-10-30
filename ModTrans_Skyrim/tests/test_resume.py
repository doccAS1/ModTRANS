import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skyrimtrans.translator import (AbortRun, BackendError, OpenAICompatBackend, TranslationStore,  # noqa: E402
                                    Translator, clear_memory, memory_info, store_for)


def ok_reply(user, prefix="IT "):
    return json.dumps([{"id": i["id"], "text": prefix + i["text"]} for i in json.loads(user)])


class Counting:
    def __init__(self):
        self.calls = 0

    def __call__(self, system, user):
        self.calls += 1
        return ok_reply(user)


ITEMS = [("name", f"Thing number {n}") for n in range(5)]


def test_memory_resumes_and_is_reused(tmp_path):
    st = TranslationStore(tmp_path / "m.jsonl")
    be = Counting()
    out = Translator(be, "Italian", store=st, batch_items=2).translate_all(ITEMS)
    assert len(out) == 5 and be.calls == 3
    # nuova esecuzione (come dopo un'interruzione): nessuna richiesta
    be2 = Counting()
    tr2 = Translator(be2, "Italian", store=TranslationStore(tmp_path / "m.jsonl"))
    assert tr2.translate_all(ITEMS) == out and be2.calls == 0 and tr2.stats["from_memory"] == 5
    # le parole della memoria alimentano anche la coerenza dei termini
    assert tr2.terms["Thing number 3"] == "IT Thing number 3"
    # "fresh": ignora la memoria ma la aggiorna
    be3 = Counting()
    Translator(be3, "Italian", store=TranslationStore(tmp_path / "m.jsonl"), reuse_memory=False).translate_all(ITEMS)
    assert be3.calls == 1
    # riga rovinata nel file: ignorata, il resto si legge
    with open(tmp_path / "m.jsonl", "a", encoding="utf-8") as f:
        f.write("{non json\n")
    assert len(TranslationStore(tmp_path / "m.jsonl").load()) == 5


def test_store_files_are_separated_by_language_model_and_glossary(tmp_path, monkeypatch):
    a = store_for("italian", "openai-x", None).path
    assert a != store_for("french", "openai-x", None).path
    assert a != store_for("italian", "openai-y", None).path
    assert a != store_for("italian", "openai-x", {"Dragonborn": "Sangue di Drago"}).path
    import os
    assert a.parent == Path(os.environ["SKYRIMTRANS_HOME"]) / "memory"   # mai nella home vera durante i test


def test_memory_info_and_clear(tmp_path):
    assert memory_info() == {"files": 0, "entries": 0, "bytes": 0}
    st = store_for("italian", "p")
    Translator(Counting(), "Italian", store=st).translate_all(ITEMS)
    info = memory_info()
    assert info["files"] == 1 and info["entries"] == 5 and info["bytes"] > 0
    assert clear_memory() == 1 and memory_info()["entries"] == 0


def test_rate_limit_waits_retry_after_then_succeeds():
    state = {"n": 0}
    waits, notes = [], []

    def be(system, user):
        state["n"] += 1
        if state["n"] <= 2:
            raise BackendError("HTTP 429", 429, retry_after=7)
        return ok_reply(user)

    tr = Translator(be, "Italian", sleep=waits.append)
    tr.on_wait = lambda s, why: notes.append((s, why))
    assert len(tr.translate_all(ITEMS)) == 5
    assert sum(waits) == pytest.approx(14) and notes == [(7, "errore del servizio AI: HTTP 429")] * 2
    assert tr.stats["retries"] == 2


def test_backoff_without_retry_after_grows_and_is_capped():
    waits = []

    def be(system, user):
        raise BackendError("HTTP 503", 503)

    tr = Translator(be, "Italian", net_retries=6, sleep=waits.append, max_failed_batches=99)
    tr.translate_all(ITEMS[:1])
    steps = [2, 4, 8, 16, 32, 60]
    assert abs(sum(waits) - sum(steps)) < 1e-6
    assert tr.failed  # alla fine l'originale resta e il motivo è registrato


def test_fatal_error_aborts_immediately():
    calls = Counting()

    def be(system, user):
        calls.calls += 1
        raise BackendError("HTTP 401: chiave non valida", 401)

    with pytest.raises(AbortRun, match="rifiutato"):
        Translator(be, "Italian", sleep=lambda s: None).translate_all(ITEMS)
    assert calls.calls == 1


def test_abort_after_consecutive_failed_batches_keeps_what_was_done(tmp_path):
    state = {"n": 0}

    def be(system, user):
        state["n"] += 1
        if state["n"] == 1:
            return ok_reply(user)
        raise BackendError("HTTP 503", 503)

    st = TranslationStore(tmp_path / "m.jsonl")
    tr = Translator(be, "Italian", store=st, batch_items=1, net_retries=1, max_failed_batches=3, sleep=lambda s: None)
    with pytest.raises(AbortRun, match="salvate in memoria"):
        tr.translate_all(ITEMS)
    assert state["n"] == 1 + 3 * 2                 # 1 riuscito + 3 lotti falliti da 2 tentativi
    assert len(TranslationStore(tmp_path / "m.jsonl").load()) == 1   # il lavoro riuscito è al sicuro
    # e rilanciando riparte da lì
    be2 = Counting()
    Translator(be2, "Italian", store=TranslationStore(tmp_path / "m.jsonl"), batch_items=1).translate_all(ITEMS)
    assert be2.calls == 4


def test_broken_placeholders_do_not_abort_the_run():
    """Un modello debole che perde i segnaposto è un limite del modello: non ferma tutto, restano gli originali."""
    def be(system, user):
        return json.dumps([{"id": i["id"], "text": "senza segnaposto"} for i in json.loads(user)])

    items = [("description", f"Line one\nLine two {n}") for n in range(6)]
    tr = Translator(be, "Italian", batch_items=1, retries=1, sleep=lambda s: None)
    assert tr.translate_all(items) == {}
    assert len(tr.failed) == 6 and all("segnaposto" in v for v in tr.failed.values())


def test_invalid_json_everywhere_aborts():
    tr = Translator(lambda s, u: "non è json", "Italian", batch_items=1, retries=1, max_failed_batches=3,
                    sleep=lambda s: None)
    with pytest.raises(AbortRun, match="risposte? non valid|non valida"):
        tr.translate_all(ITEMS)


def test_cancel_is_checked_during_waits():
    class Stop(Exception):
        pass

    beats = {"n": 0}

    def heartbeat():
        beats["n"] += 1
        if beats["n"] > 3:
            raise Stop()

    def be(system, user):
        raise BackendError("HTTP 429", 429, retry_after=60)

    slept = []
    tr = Translator(be, "Italian", sleep=slept.append)
    tr.heartbeat = heartbeat
    with pytest.raises(Stop):
        tr.translate_all(ITEMS)
    assert sum(slept) < 5   # non ha aspettato i 60 secondi interi


def test_openai_backend_reads_retry_after_header_and_status():
    hits = {"n": 0}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            hits["n"] += 1
            if hits["n"] == 1:
                self.send_response(429); self.send_header("Retry-After", "0"); self.send_header("Content-Length", "2")
                self.end_headers(); self.wfile.write(b"{}")
                return
            out = json.dumps({"choices": [{"message": {"content": "[]"}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    be = OpenAICompatBackend("m", f"http://127.0.0.1:{srv.server_port}/v1")
    with pytest.raises(BackendError) as ei:
        be("s", "u")
    assert ei.value.status == 429 and ei.value.retry_after == 0 and not ei.value.fatal
    assert be("s", "u") == "[]"
    srv.shutdown()
    srv.server_close()   # senza questo il socket resta in ascolto e la connessione aspetta all'infinito
    # server spento: errore di connessione, ritentabile
    with pytest.raises(BackendError) as ei:
        be("s", "u")
    assert ei.value.status is None and not ei.value.fatal
    assert BackendError("x", 401).fatal and BackendError("x", 404).fatal and not BackendError("x", 500).fatal
