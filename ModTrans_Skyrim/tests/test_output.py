import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_all import FakeBackend, build_plugin  # noqa: E402
from test_gui import start_server, wait  # noqa: E402
from skyrimtrans import gui, pipeline as pp  # noqa: E402
from skyrimtrans.cli import main  # noqa: E402
from skyrimtrans.translator import Translator  # noqa: E402


def test_clean_name_and_unique_path(tmp_path):
    assert pp.clean_name("ABR_Primitive_Recipes-168874-1-0-1767583643.7z") == "ABR_Primitive_Recipes"
    assert pp.clean_name('we<ir>d:na"me?.zip') == "we_ir_d_na_me_"
    assert pp.clean_name("....zip") == "mod"
    f = tmp_path / "x.zip"
    assert pp.unique_path(f) == f
    f.write_bytes(b"1")
    assert pp.unique_path(f) == tmp_path / "x (2).zip"
    (tmp_path / "x (2).zip").write_bytes(b"1")
    assert pp.unique_path(f) == tmp_path / "x (3).zip"
    d = tmp_path / "mod_italian"
    d.mkdir()
    assert pp.unique_path(d) == tmp_path / "mod_italian (2)"


def test_write_output_folder_zip_and_overwrite(tmp_path):
    out = tmp_path / "out"
    (out / "sub").mkdir(parents=True)
    (out / "sub" / "a.txt").write_text("a")
    z = pp.write_output(out, tmp_path / "r.zip", False)
    assert zipfile.ZipFile(z).namelist() == ["sub/a.txt"]
    z2 = pp.write_output(out, tmp_path / "r.zip", False)              # niente sovrascrittura
    assert z2.name == "r (2).zip" and z.exists()
    f = pp.write_output(out, tmp_path / "res", True)
    assert (f / "sub" / "a.txt").read_text() == "a"
    f2 = pp.write_output(out, tmp_path / "res", True, overwrite=True)  # con overwrite sostituisce
    assert f2 == tmp_path / "res"


def test_check_writable_dir(tmp_path):
    d = pp.check_writable_dir(tmp_path / "a" / "b")
    assert d.is_dir()
    (tmp_path / "file").write_text("x")
    with pytest.raises(pp.OutputError, match="Non posso scrivere"):
        pp.check_writable_dir(tmp_path / "file" / "sub")


def test_cli_out_dir_and_folder(tmp_path, capsys):
    esp = tmp_path / "Mod-1234-1-0-1700000000.esp"
    esp.write_bytes(build_plugin())
    assert main([str(esp), "-l", "italian", "--out-dir", str(tmp_path / "risultati"), "--as-folder"],
                backend=FakeBackend()) == 0
    res = tmp_path / "risultati" / "Mod_italian"
    assert (res / esp.name).exists()
    # secondo giro: non sovrascrive
    assert main([str(esp), "-l", "italian", "--out-dir", str(tmp_path / "risultati"), "--as-folder"],
                backend=FakeBackend()) == 0
    assert (tmp_path / "risultati" / "Mod_italian (2)" / esp.name).exists()
    assert "Fatto:" in capsys.readouterr().out


def test_gui_browse_mkdir_and_open(monkeypatch, tmp_path):
    httpd, app, c = start_server(monkeypatch, tmp_path)
    (tmp_path / "uno").mkdir()
    (tmp_path / ".nascosta").mkdir()
    (tmp_path / "file.txt").write_text("x")
    b = json.loads(c.call(f"/api/browse?path={tmp_path}")[1])
    assert b["path"] == str(tmp_path.resolve()) and b["dirs"] == ["uno"]       # solo cartelle, niente nascoste
    assert b["parent"] == str(tmp_path.resolve().parent)
    assert json.loads(c.call("/api/browse?path=/non/esiste/proprio")[1])["path"]   # ripiega su una cartella valida
    n = json.loads(c.call("/api/mkdir", {"path": str(tmp_path), "name": "nuova"})[1])
    assert (tmp_path / "nuova").is_dir() and n["path"].endswith("nuova")
    for bad in ["", "..", "a/b", "a\\b", "x:y"]:
        assert c.call("/api/mkdir", {"path": str(tmp_path), "name": bad})[0] == 400
    assert c.call("/api/browse?path=/", token=False)[0] == 403                  # serve il token
    assert c.call("/api/open", {"path": str(tmp_path)})[0] == 403               # solo percorsi prodotti da noi
    httpd.shutdown()


def test_gui_saves_to_folder_and_dry_run_writes_nothing(monkeypatch, tmp_path):
    httpd, app, c = start_server(monkeypatch, tmp_path)
    opened = []
    monkeypatch.setattr(gui, "open_in_file_manager", lambda p: opened.append(p))
    up = json.loads(c.call("/api/upload?name=Abr-168874-1-0-1767583643.esp", raw=build_plugin())[1])
    target = tmp_path / "out"
    base = {"upload_id": up["upload_id"], "lang": "italian", "source": "english", "provider": "openai",
            "model": "x", "base_url": "http://127.0.0.1:9/v1", "batch_items": 10}

    # analisi: non scrive nulla nemmeno se è scelta una cartella
    job = json.loads(c.call("/api/start", dict(base, dry_run=True, out_where="folder", out_dir=str(target)))[1])["job_id"]
    assert wait(c, job)["state"] == "done"
    assert not target.exists()

    # errori chiari prima di partire
    code, body = c.call("/api/start", dict(base, out_where="folder", out_dir=""))
    assert code == 400 and "Scegli la cartella" in json.loads(body)["error"]
    (tmp_path / "f").write_text("x")
    code, body = c.call("/api/start", dict(base, out_where="folder", out_dir=str(tmp_path / "f" / "x")))
    assert code == 400 and json.loads(body)["error"].startswith("Non posso scrivere")

    # traduzione vera con server AI finto compatibile OpenAI
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class AI(BaseHTTPRequestHandler):
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

    ai = HTTPServer(("127.0.0.1", 0), AI)
    threading.Thread(target=ai.serve_forever, daemon=True).start()
    base["base_url"] = f"http://127.0.0.1:{ai.server_port}/v1"
    for mode, expect in (("folder", "Abr_italian"), ("zip", "Abr_italian.zip")):
        job = json.loads(c.call("/api/start", dict(base, out_where="folder", out_dir=str(target), out_mode=mode))[1])["job_id"]
        st = wait(c, job)
        assert st["state"] == "done", st
        assert Path(st["saved_to"]) == (target.resolve() / expect) or Path(st["saved_to"]).name == expect
        assert c.call(f"/api/download/{job}")[0] == 404          # niente download: è già salvato
        assert c.call("/api/open", {"path": st["saved_to"]})[0] == 200 and opened[-1] == str(Path(st["saved_to"]).resolve())
    assert (target / "Abr_italian" / "Abr-168874-1-0-1767583643.esp").exists()
    assert zipfile.ZipFile(target / "Abr_italian.zip").namelist() == ["Abr-168874-1-0-1767583643.esp"]
    # senza cartella: scarica come prima
    job = json.loads(c.call("/api/start", dict(base))[1])["job_id"]
    st = wait(c, job)
    assert st["saved_to"] is None and c.call(f"/api/download/{job}")[0] == 200
    httpd.shutdown(); ai.shutdown()
