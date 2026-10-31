"""Interfaccia web locale: `skyrimtrans-gui` (si apre nel browser, solo su 127.0.0.1)."""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import context as ctx
from .gui_page import PAGE
from .pipeline import LANGS, OutputError, check_writable_dir, clean_name, run
from .translator import (DEFAULT_MODEL, AbortRun, AnthropicBackend, OpenAICompatBackend, Translator,
                         clear_memory, memory_info, store_for)

SETTINGS_FILE = Path.home() / ".skyrimtrans.json"
SAVE_KEYS = ("lang", "source", "preset", "model", "base_url", "batch_items", "nexus_game",
             "out_where", "out_dir", "out_mode", "use_memory", "shorten", "review")  # mai la chiave API
ALLOWED_EXT = {".zip", ".7z", ".esp", ".esm", ".esl"}
LANG_LABELS = {"english": "Inglese", "french": "Francese", "german": "Tedesco", "italian": "Italiano",
               "spanish": "Spagnolo", "russian": "Russo", "polish": "Polacco", "czech": "Ceco"}


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, dry: bool, name: str, lang: str):
        self.id = uuid.uuid4().hex
        self.state, self.phase, self.dry = "running", "Avvio", dry
        self.done = self.total = 0
        self.log: list[str] = []
        self.report = self.error = self.out = self.saved_to = None
        self.name, self.lang = name, lang
        self.cancel = threading.Event()


class App:
    def __init__(self):
        self.token = secrets.token_urlsafe(16)
        self.work = Path(tempfile.mkdtemp(prefix="skyrimtrans_"))
        self.uploads: dict[str, tuple[Path, str]] = {}
        self.jobs: dict[str, Job] = {}
        self.outputs: set[str] = set()   # percorsi prodotti da noi: gli unici che "Apri cartella" può aprire

    def close(self):
        shutil.rmtree(self.work, ignore_errors=True)


def load_saved() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text("utf-8"))
    except Exception:
        return {}


def save_settings(s: dict) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps({k: s.get(k) for k in SAVE_KEYS}, ensure_ascii=False), "utf-8")
    except Exception:
        pass


def make_backend(s: dict):
    if s["provider"] == "anthropic":
        try:
            return AnthropicBackend(s.get("model") or DEFAULT_MODEL, s.get("api_key") or None)
        except ImportError:
            raise ValueError("Manca la libreria 'anthropic': esegui  pip install anthropic")
    if not s.get("model"):
        raise ValueError("Inserisci il nome del modello")
    return OpenAICompatBackend(s["model"], s.get("base_url") or "https://api.openai.com/v1",
                               s.get("api_key") or os.environ.get("OPENAI_API_KEY"))


def browse(path: str) -> dict:
    """Elenco delle sottocartelle di `path` sul PC dell'utente (serve al selettore di cartelle della pagina)."""
    p = Path(path).expanduser() if path else Path.home()
    try:
        p = p.resolve()
    except OSError:
        p = Path.home()
    if not p.is_dir():
        p = p.parent if p.parent.is_dir() else Path.home()
    try:
        dirs = sorted((d.name for d in p.iterdir() if d.is_dir() and not d.name.startswith(".")), key=str.lower)
    except OSError:
        dirs = []
    drives = ([f"{c}:\\" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{c}:\\")]
              if os.name == "nt" else [])
    quick = [str(q) for q in (Path.home(), Path.home() / "Downloads", Path.home() / "Documents",
                              Path.home() / "Desktop") if q.is_dir()]
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "dirs": dirs,
            "drives": drives, "quick": quick, "sep": os.sep}


def open_in_file_manager(path: str) -> None:
    d = Path(path)
    d = d if d.is_dir() else d.parent
    if os.name == "nt":
        os.startfile(str(d))  # noqa: S606 - cartella scelta dall'utente
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(d)])
    else:
        subprocess.Popen(["xdg-open", str(d)])


def build_context(app: App, b: dict) -> dict:
    """Contesto della mod: offline sempre; Nexus (API ufficiale) e riassunto AI se richiesti."""
    if b.get("upload_id") not in app.uploads:
        raise ValueError("Carica prima un file")
    src, _ = app.uploads[b["upload_id"]]
    try:
        offline = ctx.offline_for_path(src)
        nexus, nexus_name = None, None
        if (b.get("nexus_ref") or "").strip():
            mod_id = ctx.parse_nexus_ref(b["nexus_ref"])
            if mod_id is None:
                raise ctx.ContextError("Link o ID Nexus non riconosciuto (es. 168874 o .../mods/168874)")
            nexus = ctx.fetch_nexus(mod_id, (b.get("nexus_key") or os.environ.get("NEXUS_API_KEY") or "").strip(),
                                    b.get("nexus_game") or "skyrimspecialedition")
            nexus_name = nexus["name"]
        backend = None
        if nexus:  # il riassunto usa lo stesso servizio AI scelto per la traduzione
            try:
                backend = make_backend(b)
            except ValueError:
                backend = None
        text, sources, warning = ctx.build_brief(offline, nexus, backend)
        if nexus and backend is None:
            warning = "Nessun servizio AI configurato: mostro i dati grezzi di Nexus"
    except ctx.ContextError:
        raise  # messaggio già chiaro per l'utente
    return {"brief": text, "sources": sources or ["nessuna"], "nexus_name": nexus_name, "warning": warning}


def run_job(app: App, job: Job, s: dict) -> None:
    try:
        src, up_name = app.uploads[s["upload_id"]]
        out_dir = (s.get("out_dir") or "").strip() if s.get("out_where") == "folder" and not job.dry else ""
        as_folder = bool(out_dir) and s.get("out_mode") != "zip"
        if out_dir:  # il risultato va nella cartella scelta, con un nome libero (non si sovrascrive nulla)
            dest = check_writable_dir(Path(out_dir)) / (f"{clean_name(up_name)}_{s['lang']}" + ("" if as_folder else ".zip"))
        else:
            dest = app.work / f"{job.id}.zip"
        glossary = None
        if s.get("glossary"):
            try:
                glossary = json.loads(s["glossary"])
                assert isinstance(glossary, dict)
            except Exception:
                raise ValueError("Il glossario non è un JSON valido (serve un oggetto {\"termine\": \"traduzione\"})")
        if job.dry:
            backend = lambda _sys, u: json.dumps([{"id": i["id"], "text": i["text"]} for i in json.loads(u)])
        else:
            backend = make_backend(s)
            job.phase = "Verifico la connessione"
            job.log.append("Verifico la connessione al servizio AI...")
            try:
                backend("Reply with the single word OK.", "ping")  # fallisce subito se chiave/server sbagliati
            except Exception as e:  # noqa: BLE001
                hint = ("Controlla che il server sia acceso e l'indirizzo giusto."
                        if s["provider"] == "openai" else "Controlla la chiave API.")
                raise RuntimeError(f"Connessione al servizio AI non riuscita. {hint} Dettaglio: {e}") from None
        store = None if job.dry else store_for(s["lang"], f"{s['provider']}-{s.get('model') or DEFAULT_MODEL}", glossary)
        tr = Translator(backend, s["lang"].capitalize(), glossary,
                        batch_items=max(1, int(s.get("batch_items") or 40)),
                        store=store, reuse_memory=s.get("use_memory", True),
                        shorten=s.get("shorten", True), review=bool(s.get("review")))

        def heartbeat():
            if job.cancel.is_set():
                raise Cancelled()

        def on_wait(seconds, why):
            job.phase = f"Attendo il servizio AI ({int(seconds)} s)"
            job.log.append(f"{why}. Riprovo tra {int(seconds)} secondi...")

        tr.heartbeat, tr.on_wait = heartbeat, on_wait
        if (s.get("brief") or "").strip():
            tr.set_brief(s["brief"])  # contesto scritto/corretto dall'utente

        def prog(d, t):
            heartbeat()
            job.done, job.total = d, t
            job.phase = "Analisi e traduzione"

        job.phase = "Analisi e traduzione"
        job.log.append("Analisi del file e traduzione...")
        rep = run(src, dest, tr, s["lang"], s["source"], prog, as_folder=as_folder)
        job.report = {"translated": rep.translated, "kept_original": rep.kept_original,
                      "files": rep.files, "warnings": rep.warnings, "failures": rep.failures,
                      "from_memory": rep.from_memory, "requests": rep.requests,
                      "shortened": rep.shortened, "qa_checked": rep.qa_checked, "qa_fixed": rep.qa_fixed}
        if out_dir:
            job.saved_to = rep.output
            app.outputs.add(str(Path(rep.output).resolve()))
        job.log.append(f"Trovate {rep.translated} stringhe traducibili." if job.dry
                       else f"Fatto: {rep.translated} stringhe ({rep.from_memory} dalla memoria, {rep.requests} richieste all'AI), "
                            f"{len(rep.files)} file prodotti.")
        job.out = None if (job.dry or out_dir) else Path(rep.output)
        job.phase, job.state = "Completato", "done"
    except Cancelled:
        job.state, job.phase = "cancelled", "Annullato"
    except AbortRun as e:
        job.state, job.phase, job.error = "error", "Interrotto", str(e)
        job.log.append(f"Interrotto: {e}")
    except Exception as e:  # noqa: BLE001 - qualunque errore va mostrato all'utente
        job.state, job.phase, job.error = "error", "Errore", f"{e}"
        job.log.append(f"Errore: {e}")


def make_handler(app: App, port_holder: list):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        # ------------------------------------------------------------ util
        def _json(self, obj, code=200):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def _host_ok(self):
            host = (self.headers.get("Host") or "").lower()
            return host in {f"127.0.0.1:{port_holder[0]}", f"localhost:{port_holder[0]}"}

        def _auth(self, q):
            tok = self.headers.get("X-Token") or (q.get("t") or [""])[0]
            return secrets.compare_digest(tok, app.token)

        def _body_json(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        # ------------------------------------------------------------ GET
        def do_GET(self):
            u, q = urlparse(self.path), parse_qs(urlparse(self.path).query)
            if not self._host_ok():
                return self._json({"error": "host non consentito"}, 403)
            if u.path == "/":
                defaults = {"langs": [[k, LANG_LABELS[k]] for k in LANGS], "saved": load_saved(),
                            "default_model": DEFAULT_MODEL}
                page = PAGE.replace("__TOKEN__", app.token).replace(
                    "__DEFAULTS__", json.dumps(defaults, ensure_ascii=False).replace("</", "<\\/"))
                b = page.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b)
                return
            if not self._auth(q):
                return self._json({"error": "non autorizzato"}, 403)
            if u.path == "/api/memory":
                return self._json(memory_info())
            if u.path == "/api/browse":
                return self._json(browse((q.get("path") or [""])[0]))
            m = re.fullmatch(r"/api/status/([0-9a-f]{32})", u.path)
            if m and m.group(1) in app.jobs:
                j = app.jobs[m.group(1)]
                return self._json({"state": j.state, "phase": j.phase, "done": j.done, "total": j.total,
                                   "log": j.log[-200:], "report": j.report, "error": j.error, "dry": j.dry,
                                   "saved_to": j.saved_to})
            m = re.fullmatch(r"/api/download/([0-9a-f]{32})", u.path)
            if m and m.group(1) in app.jobs and app.jobs[m.group(1)].out:
                j = app.jobs[m.group(1)]
                size = j.out.stat().st_size
                fname = f"{Path(j.name).stem}_{j.lang}.zip"
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.end_headers()
                with open(j.out, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
                return
            self._json({"error": "non trovato"}, 404)

        # ------------------------------------------------------------ POST
        def do_POST(self):
            u, q = urlparse(self.path), parse_qs(urlparse(self.path).query)
            if not self._host_ok() or not self._auth(q):
                return self._json({"error": "non autorizzato"}, 403)
            try:
                if u.path == "/api/upload":
                    name = Path((q.get("name") or ["mod"])[0]).name
                    ext = Path(name).suffix.lower()
                    if ext not in ALLOWED_EXT:
                        return self._json({"error": "Formato non supportato: usa .zip, .7z, .esp, .esm, .esl"}, 400)
                    uid = uuid.uuid4().hex
                    d = app.work / uid
                    d.mkdir()
                    path = d / name  # nome originale: un plugin rinominato romperebbe la mod
                    left = int(self.headers.get("Content-Length") or 0)
                    with open(path, "wb") as f:
                        while left > 0:
                            chunk = self.rfile.read(min(1 << 20, left))
                            if not chunk:
                                break
                            f.write(chunk)
                            left -= len(chunk)
                    if left:
                        return self._json({"error": "Caricamento interrotto"}, 400)
                    app.uploads[uid] = (path, name)
                    return self._json({"upload_id": uid, "nexus_id": ctx.detect_nexus_id(name)})
                if u.path == "/api/context":
                    return self._json(build_context(app, self._body_json()))
                if u.path == "/api/start":
                    s = self._body_json()
                    if s.get("upload_id") not in app.uploads:
                        return self._json({"error": "Carica prima un file"}, 400)
                    if s.get("lang") not in LANGS or s.get("source") not in LANGS:
                        return self._json({"error": "Lingua non valida"}, 400)
                    if s["lang"] == s["source"]:
                        return self._json({"error": "La lingua di destinazione coincide con quella originale"}, 400)
                    if s.get("out_where") == "folder" and not s.get("dry_run"):
                        if not (s.get("out_dir") or "").strip():
                            return self._json({"error": "Scegli la cartella dove salvare"}, 400)
                        check_writable_dir(Path(s["out_dir"].strip()))   # ValueError con messaggio chiaro
                    job = Job(bool(s.get("dry_run")), app.uploads[s["upload_id"]][1], s["lang"])
                    app.jobs[job.id] = job
                    save_settings(s)
                    threading.Thread(target=run_job, args=(app, job, s), daemon=True).start()
                    return self._json({"job_id": job.id})
                if u.path == "/api/memory/clear":
                    return self._json({"cleared": clear_memory()})
                if u.path == "/api/mkdir":
                    b = self._body_json()
                    name = (b.get("name") or "").strip()
                    if not name or re.search(r'[\\/:*?"<>|]', name) or name in (".", ".."):
                        return self._json({"error": "Nome cartella non valido"}, 400)
                    new = Path(b.get("path") or "") / name
                    try:
                        new.mkdir(parents=False, exist_ok=True)
                    except OSError as e:
                        return self._json({"error": f"Non riesco a creare la cartella: {e.strerror or e}"}, 400)
                    return self._json(browse(str(new)))
                if u.path == "/api/open":
                    p = str(Path(self._body_json().get("path") or "").resolve())
                    if p not in app.outputs:
                        return self._json({"error": "Percorso non consentito"}, 403)
                    try:
                        open_in_file_manager(p)
                    except OSError as e:
                        return self._json({"error": f"Non riesco ad aprire la cartella: {e}"}, 400)
                    return self._json({"ok": True})
                m = re.fullmatch(r"/api/cancel/([0-9a-f]{32})", u.path)
                if m and m.group(1) in app.jobs:
                    app.jobs[m.group(1)].cancel.set()
                    return self._json({"ok": True})
            except (ctx.ContextError, OutputError) as e:
                return self._json({"error": str(e)}, 400)
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                return self._json({"error": f"Richiesta non valida: {e}"}, 400)
            self._json({"error": "non trovato"}, 404)

    return H


def create_server(port: int = 0):
    app = App()
    holder = [0]
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, holder))
    holder[0] = httpd.server_port
    return httpd, app


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="skyrimtrans-gui", description="Interfaccia grafica (nel browser) di skyrimtrans")
    ap.add_argument("--port", type=int, default=0, help="porta locale (default: libera a caso)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    httpd, app = create_server(a.port)
    url = f"http://127.0.0.1:{httpd.server_port}/"
    print(f"skyrimtrans è attivo su {url}\nPremi Ctrl+C per chiudere.")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
