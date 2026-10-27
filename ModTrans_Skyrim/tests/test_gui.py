import io
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_all import build_plugin  # noqa: E402
from modtrans import gui  # noqa: E402


class Client:
    def __init__(self, httpd, app):
        self.base, self.tok = f"http://127.0.0.1:{httpd.server_port}", app.token

    def call(self, path, data=None, method=None, raw=None, token=True):
        h = {"X-Token": self.tok} if token else {}
        body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        if data is not None:
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, body, h, method=method or ("POST" if body else "GET"))
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()


def start_server(monkeypatch, tmp_path):
    monkeypatch.setattr(gui, "SETTINGS_FILE", tmp_path / "settings.json")
    httpd, app = gui.create_server(0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, app, Client(httpd, app)


def wait(c, job):
    for _ in range(100):
        st = json.loads(c.call(f"/api/status/{job}")[1])
        if st["state"] != "running":
            return st
        time.sleep(0.1)
    raise AssertionError("timeout")


def test_security(monkeypatch, tmp_path):
    httpd, app, c = start_server(monkeypatch, tmp_path)
    assert c.call("/api/status/" + "0" * 32, token=False)[0] == 403
    assert c.call("/api/upload?name=a.esp", raw=b"x", token=False)[0] == 403
    code, _ = c.call("/api/upload?name=evil.exe", raw=b"x")
    assert code == 400
    # Host sbagliato (DNS rebinding)
    req = urllib.request.Request(c.base + "/", headers={"Host": "evil.com"})
    try:
        urllib.request.urlopen(req)
        assert False
    except urllib.error.HTTPError as e:
        assert e.code == 403
    httpd.shutdown()


def test_dry_run_and_errors(monkeypatch, tmp_path):
    httpd, app, c = start_server(monkeypatch, tmp_path)
    up = json.loads(c.call("/api/upload?name=My.esp", raw=build_plugin())[1])
    base = {"upload_id": up["upload_id"], "lang": "italian", "source": "english", "provider": "openai",
            "model": "x", "base_url": "http://127.0.0.1:9/v1", "batch_items": 10}
    # analisi senza AI
    job = json.loads(c.call("/api/start", dict(base, dry_run=True))[1])["job_id"]
    st = wait(c, job)
    assert st["state"] == "done" and st["report"]["translated"] == 3
    assert c.call(f"/api/download/{job}")[0] == 404  # nessun file in dry-run
    # server AI irraggiungibile: errore chiaro e immediato
    job = json.loads(c.call("/api/start", dict(base, dry_run=False))[1])["job_id"]
    st = wait(c, job)
    assert st["state"] == "error" and st["error"]
    # richieste non valide
    assert c.call("/api/start", dict(base, lang="english"))[0] == 400
    assert c.call("/api/start", dict(base, upload_id="nope"))[0] == 400
    # glossario rotto
    job = json.loads(c.call("/api/start", dict(base, glossary="{rotto", dry_run=True))[1])["job_id"]
    assert "glossario" in wait(c, job)["error"].lower()
    httpd.shutdown()


def test_full_flow_download(monkeypatch, tmp_path):
    """Flusso completo con un server compatibile OpenAI finto."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            user = body["messages"][1]["content"]
            try:
                reply = json.dumps([{"id": i["id"], "text": "IT " + i["text"]} for i in json.loads(user)])
            except Exception:
                reply = "OK"
            out = json.dumps({"choices": [{"message": {"content": reply}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    fake = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    up = json.loads(c.call("/api/upload?name=My.esp", raw=build_plugin())[1])
    s = {"upload_id": up["upload_id"], "lang": "italian", "source": "english", "provider": "openai",
         "preset": "ollama", "model": "m", "base_url": f"http://127.0.0.1:{fake.server_port}/v1",
         "api_key": "SEGRETA", "batch_items": 10}
    job = json.loads(c.call("/api/start", s)[1])["job_id"]
    st = wait(c, job)
    assert st["state"] == "done", st
    code, data = c.call(f"/api/download/{job}?t={app.token}", token=False)
    assert code == 200
    z = zipfile.ZipFile(io.BytesIO(data))
    assert "My.esp" in z.namelist()
    saved = json.loads((tmp_path / "settings.json").read_text())
    assert saved["model"] == "m" and "SEGRETA" not in json.dumps(saved)  # la chiave non finisce su disco
    httpd.shutdown(); fake.shutdown()
