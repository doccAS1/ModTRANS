import json
import os
import stat
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_gui import Client, start_server, wait  # noqa: E402
from test_lanes import start  # noqa: E402
from test_queue import FakeAI, queue, settings, upload  # noqa: E402
from skyrimtrans import gui, lanestore  # noqa: E402


def restart(monkeypatch, tmp_path, httpd, app):
    """Chiude e riapre il programma (stessa cartella utente)."""
    httpd.shutdown(); httpd.server_close(); app.close()
    monkeypatch.setattr(gui, "SETTINGS_FILE", tmp_path / "settings.json")
    httpd2, app2 = gui.create_server(0)
    threading.Thread(target=httpd2.serve_forever, daemon=True).start()
    return httpd2, app2, Client(httpd2, app2)


def test_nothing_is_saved_unless_the_user_asks(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    start(c, upload(c, "A.esp"), ai, api_key="SEGRETISSIMA")
    assert queue(c)["remember"] is False and not lanestore.lanes_file().exists()
    assert "SEGRETISSIMA" not in json.dumps(json.loads((tmp_path / "settings.json").read_text()))
    httpd2, app2, c2 = restart(monkeypatch, tmp_path, httpd, app)
    assert queue(c2)["lanes"] == []                                    # al riavvio non c'è niente
    ai.close(); httpd2.shutdown(); httpd2.server_close(); app2.close()


def test_saved_lanes_come_back_with_their_own_keys(monkeypatch, tmp_path):
    ai1, ai2 = FakeAI(), FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    assert c.call("/api/remember", {"on": True})[0] == 200
    a = start(c, upload(c, "A.esp"), ai1, api_key="CHIAVE-UNO", model="m1")
    b = start(c, upload(c, "B.esp"), ai2, api_key="CHIAVE-DUE", model="m2")
    wait(c, a["job_id"]); wait(c, b["job_id"])
    data = json.loads(lanestore.lanes_file().read_text("utf-8"))["lanes"]
    assert [l["name"] for l in data] == ["Coda 1", "Coda 2"] and [l["s"]["api_key"] for l in data] == ["CHIAVE-UNO", "CHIAVE-DUE"]
    if os.name == "posix":
        assert stat.S_IMODE(lanestore.lanes_file().stat().st_mode) == 0o600      # leggibile solo dal proprietario
    ai1.auth.clear(); ai2.auth.clear()
    httpd2, app2, c2 = restart(monkeypatch, tmp_path, httpd, app)
    q = queue(c2)
    assert q["remember"] is True and [(l["name"], l["has_key"]) for l in q["lanes"]] == [("Coda 1", True), ("Coda 2", True)]
    assert [l["summary"].split(" · ")[1].split(" ")[0] for l in q["lanes"]] == ["m1", "m2"]
    assert "CHIAVE" not in json.dumps(q)                                 # la chiave non torna mai al browser
    # aggiungo mod alle code ritrovate, senza reinserire nulla: ognuna usa la SUA chiave
    la, lb = q["lanes"][0]["id"], q["lanes"][1]["id"]
    ja = json.loads(c2.call("/api/start", {"upload_id": upload(c2, "C.esp"), "lane_id": la, "use_memory": False})[1])["job_id"]
    jb = json.loads(c2.call("/api/start", {"upload_id": upload(c2, "D.esp"), "lane_id": lb, "use_memory": False})[1])["job_id"]
    assert wait(c2, ja)["state"] == "done" and wait(c2, jb)["state"] == "done"
    assert ai1.auth == {"Bearer CHIAVE-UNO"} and ai2.auth == {"Bearer CHIAVE-DUE"}
    # una nuova coda dopo il riavvio continua la numerazione
    e = start(c2, upload(c2, "E.esp"), ai1, api_key="CHIAVE-TRE")
    assert [l["name"] for l in queue(c2)["lanes"]][-1] == "Coda 3"
    ai1.close(); ai2.close(); httpd2.shutdown(); httpd2.server_close(); app2.close()


def test_update_keeps_the_saved_key_when_the_field_is_empty_and_replaces_it_otherwise(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    c.call("/api/remember", {"on": True})
    a = start(c, upload(c, "A.esp"), ai, api_key="VECCHIA")
    form = settings(upload(c, "x.esp"), ai, model="altro"); form.pop("upload_id"); form["api_key"] = ""
    assert c.call("/api/lane/update", {"lane_id": a["lane_id"], "settings": form})[0] == 200
    saved = lambda: json.loads(lanestore.lanes_file().read_text("utf-8"))["lanes"][0]["s"]
    assert saved()["api_key"] == "VECCHIA" and saved()["model"] == "altro"       # campo vuoto: la chiave resta
    form["api_key"] = "NUOVA"
    c.call("/api/lane/update", {"lane_id": a["lane_id"], "settings": form})
    assert saved()["api_key"] == "NUOVA"
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_closing_a_lane_forgets_it_and_turning_off_deletes_everything(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    c.call("/api/remember", {"on": True})
    assert lanestore.lanes_file().exists()                               # il file c'è anche senza code: segna la scelta
    a = start(c, upload(c, "A.esp"), ai, api_key="K1")
    b = start(c, upload(c, "B.esp"), ai, api_key="K2")
    wait(c, a["job_id"]); wait(c, b["job_id"])
    c.call("/api/lane/close", {"lane_id": a["lane_id"]})
    assert [l["name"] for l in lanestore.load()] == ["Coda 2"]           # chiusa = dimenticata (con la sua chiave)
    c.call("/api/remember", {"on": False})
    assert not lanestore.lanes_file().exists() and queue(c)["remember"] is False
    assert len(queue(c)["lanes"]) == 1                                   # le code in uso restano finché il programma è aperto
    new = start(c, upload(c, "C.esp"), ai, api_key="K3")
    assert not lanestore.lanes_file().exists()                           # e non si salva più nulla
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_unreadable_lane_file_is_ignored(monkeypatch, tmp_path):
    lanestore.lanes_file().parent.mkdir(parents=True, exist_ok=True)
    lanestore.lanes_file().write_text("{non json")
    httpd, app, c = start_server(monkeypatch, tmp_path)
    q = queue(c)
    assert q["lanes"] == [] and q["remember"] is False                   # file rovinato: si riparte puliti, nessun errore
    httpd.shutdown(); httpd.server_close()
    lanestore.lanes_file().write_text(json.dumps({"lanes": [{"name": "Coda 4", "s": {"lang": "italian"}}, {"x": 1}, "no"]}))
    assert [l["name"] for l in lanestore.load()] == ["Coda 4"]           # voci rovinate scartate, le buone restano


def test_keys_never_appear_in_any_response(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    c.call("/api/remember", {"on": True})
    a = start(c, upload(c, "A.esp"), ai, api_key="TOP-SECRET-KEY")
    wait(c, a["job_id"])
    for path in ("/api/queue", f"/api/status/{a['job_id']}", "/api/history", "/api/memory"):
        assert b"TOP-SECRET-KEY" not in c.call(path)[1], path
    assert "TOP-SECRET-KEY" not in "".join(app.jobs[a["job_id"]].log)
    ai.close(); httpd.shutdown(); httpd.server_close()


def test_simple_mode_requests_do_not_leave_an_empty_saved_lane(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    c.call("/api/remember", {"on": True})
    job = json.loads(c.call("/api/start", settings(upload(c, "A.esp"), ai))[1])["job_id"]     # senza lane_id
    assert wait(c, job)["state"] == "done"
    assert lanestore.load() == []                                        # la coda predefinita non ha impostazioni proprie
    other = start(c, upload(c, "B.esp"), ai, api_key="K")                # una coda vera, creata dopo
    wait(c, other["job_id"])
    assert [l["name"] for l in lanestore.load()] == ["Coda 2"]           # nel file solo quella: la predefinita resta fuori
    ai.close(); httpd.shutdown(); httpd.server_close()
