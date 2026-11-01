import io
import json
import sys
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_all import build_plugin  # noqa: E402
from test_gui import start_server, wait  # noqa: E402
from skyrimtrans import gui  # noqa: E402
from skyrimtrans.history import History  # noqa: E402


class FakeAI:
    """Server compatibile OpenAI. Le richieste di traduzione aspettano `gate` (per tenere una mod 'in corso')."""

    def __init__(self, gated=False):
        self.gate = threading.Event()
        if not gated:
            self.gate.set()
        self.requests = 0
        self.models: set[str] = set()                   # modelli visti nelle richieste di traduzione
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                user = body["messages"][1]["content"]
                try:
                    items = json.loads(user)
                    outer.gate.wait(10)
                    outer.requests += 1
                    outer.models.add(body["model"])
                    reply = json.dumps([{"id": i["id"], "text": "IT " + i["text"]} for i in items])
                except ValueError:
                    reply = "OK"                                   # il controllo iniziale della connessione
                out = json.dumps({"choices": [{"message": {"content": reply}}]}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}/v1"

    def close(self):
        self.gate.set()
        self.srv.shutdown(); self.srv.server_close()


def upload(c, name):
    return json.loads(c.call(f"/api/upload?name={name}", raw=build_plugin())[1])["upload_id"]


def settings(uid, ai, **kw):
    return dict({"upload_id": uid, "lang": "italian", "source": "english", "provider": "openai", "preset": "custom",
                 "model": "m", "base_url": ai.url, "api_key": "SEGRETA", "batch_items": 10}, **kw)


def queue(c):
    return json.loads(c.call("/api/queue")[1])


def until(fn, what="condizione"):
    for _ in range(100):
        r = fn()
        if r:
            return r
        time.sleep(0.05)
    raise AssertionError(f"timeout: {what}")


def test_mods_run_one_at_a_time_in_order_without_further_input(monkeypatch, tmp_path):
    ai = FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    ids = [json.loads(c.call("/api/start", settings(upload(c, f"M{n}.esp"), ai))[1])["job_id"] for n in range(3)]
    q = until(lambda: (lambda v: v if v["jobs"][0]["state"] == "running" else None)(queue(c)), "prima mod in corso")
    assert [j["state"] for j in q["jobs"]] == ["running", "queued", "queued"]        # una sola alla volta
    assert [j["id"] for j in q["jobs"]] == ids and [j["name"] for j in q["jobs"]] == ["M0.esp", "M1.esp", "M2.esp"]
    ai.gate.set()                                                                      # nessun altro intervento
    until(lambda: all(j["state"] == "done" for j in queue(c)["jobs"]), "tutte finite")
    assert all(wait(c, i)["state"] == "done" for i in ids)
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_cancelling_a_waiting_mod_removes_it_from_the_queue(monkeypatch, tmp_path):
    ai = FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    first = json.loads(c.call("/api/start", settings(upload(c, "A.esp"), ai))[1])["job_id"]
    second = json.loads(c.call("/api/start", settings(upload(c, "B.esp"), ai))[1])["job_id"]
    third = json.loads(c.call("/api/start", settings(upload(c, "C.esp"), ai))[1])["job_id"]
    until(lambda: queue(c)["jobs"][0]["state"] == "running", "prima in corso")
    c.call(f"/api/cancel/{second}", {})
    states = {j["id"]: j["state"] for j in queue(c)["jobs"]}
    assert states[second] == "cancelled" and states[third] == "queued"
    ai.gate.set()
    until(lambda: queue(c)["jobs"][2]["state"] == "done", "terza finita")
    assert queue(c)["jobs"][1]["state"] == "cancelled" and wait(c, first)["state"] == "done"
    assert app.jobs[second].log == [] and app.jobs[second].done == 0                    # la annullata non è mai partita
    assert ai.requests == 1                                                            # la terza riusa la memoria della prima
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_clear_queue_cancels_only_waiting_mods(monkeypatch, tmp_path):
    ai = FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    for n in range(3):
        c.call("/api/start", settings(upload(c, f"M{n}.esp"), ai))
    until(lambda: queue(c)["jobs"][0]["state"] == "running", "prima in corso")
    assert json.loads(c.call("/api/queue/clear", {})[1])["cancelled"] == 2
    ai.gate.set()
    until(lambda: queue(c)["jobs"][0]["state"] == "done", "prima finita")
    assert [j["state"] for j in queue(c)["jobs"]] == ["done", "cancelled", "cancelled"]
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_queue_pauses_when_the_service_is_down_and_retry_works(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    bad = dict(settings(upload(c, "A.esp"), ai), base_url="http://127.0.0.1:9/v1")
    a = json.loads(c.call("/api/start", bad)[1])["job_id"]
    b = json.loads(c.call("/api/start", settings(upload(c, "B.esp"), ai))[1])["job_id"]
    until(lambda: queue(c)["paused"], "coda in pausa")
    q = queue(c)
    assert q["pause_msg"] and [j["state"] for j in q["jobs"]] == ["error", "queued"]
    time.sleep(0.3)
    assert queue(c)["jobs"][1]["state"] == "queued"                    # la successiva NON parte da sola
    c.call("/api/queue/resume", {})
    assert wait(c, b)["state"] == "done" and queue(c)["paused"] is False
    # "Riprova" rimette in coda la stessa mod con le stesse impostazioni; una mod finita bene non si può riprovare
    assert c.call(f"/api/retry/{b}", {})[0] == 400
    app.jobs[a].own["base_url"] = ai.url                                # (l'utente ha riacceso il server)
    again = json.loads(c.call(f"/api/retry/{a}", {})[1])["job_id"]
    assert again != a and wait(c, again)["state"] == "done"
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_api_key_is_dropped_from_memory_when_done(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    job = json.loads(c.call("/api/start", settings(upload(c, "A.esp"), ai))[1])["job_id"]
    assert wait(c, job)["state"] == "done"
    until(lambda: "api_key" not in app.jobs[job].s, "chiave rimossa")
    ai.close(); httpd.shutdown(); httpd.server_close()


# ------------------------------------------------------------ cronologia
def test_history_download_while_another_mod_is_running(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    done = json.loads(c.call("/api/start", settings(upload(c, "First.esp"), ai))[1])["job_id"]
    assert wait(c, done)["state"] == "done"
    ai.gate.clear()                                                    # la seconda resta in corso
    # senza memoria: altrimenti riuserebbe le traduzioni della prima, finirebbe subito e non resterebbe "in corso"
    json.loads(c.call("/api/start", settings(upload(c, "Second.esp"), ai, use_memory=False))[1])
    until(lambda: queue(c)["jobs"][1]["state"] == "running", "seconda in corso")
    hist = json.loads(c.call("/api/history")[1])
    assert [e["name"] for e in hist["entries"]] == ["First.esp"] and hist["entries"][0]["available"]
    assert hist["entries"][0]["translated"] == 3 and hist["bytes"] > 0
    code, data = c.call(f"/api/history/{done}/download?t={app.token}", token=False)
    assert code == 200 and "First.esp" in zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert queue(c)["jobs"][1]["state"] == "running"                   # il download non ha fermato la traduzione
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_history_survives_restart_and_can_delete(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    job = json.loads(c.call("/api/start", settings(upload(c, "Keep.esp"), ai))[1])["job_id"]
    assert wait(c, job)["state"] == "done"
    until(lambda: json.loads(c.call("/api/history")[1])["entries"], "voce in cronologia")
    httpd.shutdown(); httpd.server_close(); app.close()
    httpd2, app2 = gui.create_server(0)                                # "riavvio" del programma
    threading.Thread(target=httpd2.serve_forever, daemon=True).start()
    c2 = type(c)(httpd2, app2)
    ent = json.loads(c2.call("/api/history")[1])["entries"]
    assert [e["id"] for e in ent] == [job] and ent[0]["available"]
    assert c2.call(f"/api/history/{job}/download?t={app2.token}", token=False)[0] == 200
    zpath = app2.history.zip_path(job)
    assert zpath.is_file()
    assert c2.call("/api/history/delete", {"id": job})[0] == 200
    assert not zpath.exists() and json.loads(c2.call("/api/history")[1])["entries"] == []
    assert c2.call("/api/history/delete", {"id": job})[0] == 404
    assert c2.call(f"/api/history/{job}/download?t={app2.token}", token=False)[0] == 404
    ai.close(); httpd2.shutdown(); httpd2.server_close(); app2.close()


def test_history_folder_entries_never_delete_the_users_folder(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    out = tmp_path / "Risultati"
    job = json.loads(c.call("/api/start", settings(upload(c, "InFolder.esp"), ai, out_where="folder",
                                                   out_dir=str(out), out_mode="folder"))[1])["job_id"]
    assert wait(c, job)["state"] == "done"
    ent = until(lambda: json.loads(c.call("/api/history")[1])["entries"], "voce")[0]
    assert ent["mode"] == "folder" and ent["available"] and Path(ent["saved_to"]).is_dir()
    assert c.call("/api/history/delete", {"id": job})[0] == 200
    assert Path(ent["saved_to"]).is_dir()                              # la cartella dell'utente resta
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_history_entry_reports_missing_files_and_rejects_bad_requests(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    job = json.loads(c.call("/api/start", settings(upload(c, "Gone.esp"), ai))[1])["job_id"]
    assert wait(c, job)["state"] == "done"
    until(lambda: json.loads(c.call("/api/history")[1])["entries"], "voce")
    app.history.zip_path(job).unlink()                                 # file sparito dal disco
    ent = json.loads(c.call("/api/history")[1])["entries"][0]
    assert ent["available"] is False
    assert c.call(f"/api/history/{job}/download?t={app.token}", token=False)[0] == 404
    assert c.call("/api/history")[0] == 200 and c.call("/api/history", token=False)[0] == 403
    assert c.call("/api/history/delete", {"id": "../../etc/passwd"})[0] == 404
    assert c.call("/api/history/clear", {})[0] == 200 and json.loads(c.call("/api/history")[1])["entries"] == []
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_dry_runs_and_failures_are_not_recorded(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    job = json.loads(c.call("/api/start", settings(upload(c, "Dry.esp"), ai, dry_run=True))[1])["job_id"]
    assert wait(c, job)["state"] == "done"
    assert json.loads(c.call("/api/history")[1])["entries"] == []
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_history_module_is_robust(tmp_path):
    h = History(tmp_path / "h")
    assert h.list() == []
    (tmp_path / "h").mkdir()
    (tmp_path / "h" / "index.json").write_text("{non json")                # indice rovinato: si riparte vuoti
    assert h.list() == []
    e = {"id": "a" * 32, "name": "X.esp", "lang": "italian", "mode": "zip", "warnings": ["w"] * 500, "failures": []}
    src = tmp_path / "src.zip"
    src.write_bytes(b"PK")
    h.add(e, src)
    assert not src.exists() and h.zip_path("a" * 32).read_bytes() == b"PK"
    assert len(h.list()[0]["warnings"]) == 100                                 # elenchi lunghi troncati
    assert h.zip_path("../x") is None
    h.add(dict(e, id="b" * 32, mode="folder", saved_to=str(tmp_path / "nonesiste")))
    assert [x["id"] for x in h.list()] == ["b" * 32, "a" * 32]                 # la più recente per prima
    assert h.get("b" * 32)["available"] is False
    assert h.clear() == 2 and h.list() == [] and not h.zip_path("a" * 32).exists()


def test_retry_after_partial_failure_reuses_memory(monkeypatch, tmp_path):
    """"Riprova le fallite": una mod finita con stringhe non tradotte si rimette in coda; le già fatte vengono dalla memoria."""
    ai = FakeAI()
    orig = ai.srv.RequestHandlerClass.do_POST
    state = {"n": 0}

    def flaky(self):
        state["n"] += 1
        if 2 <= state["n"] <= 4:                                      # la prima stringa fallisce anche dopo i nuovi tentativi
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"choices": [{"message": {"content": "[]"}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers()
            self.wfile.write(out)
            return
        orig(self)

    ai.srv.RequestHandlerClass.do_POST = flaky
    httpd, app, c = start_server(monkeypatch, tmp_path)
    s = dict(settings(upload(c, "Part.esp"), ai), batch_items=1)
    job = json.loads(c.call("/api/start", s)[1])["job_id"]
    st = wait(c, job)
    assert st["state"] == "done" and st["report"]["failures"]          # qualche stringa non tradotta
    again = json.loads(c.call(f"/api/retry/{job}", {})[1])["job_id"]
    st2 = wait(c, again)
    assert st2["state"] == "done" and not st2["report"]["failures"] and st2["report"]["from_memory"] > 0
    ai.close(); httpd.shutdown(); httpd.server_close()
