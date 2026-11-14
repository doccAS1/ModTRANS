import io
import json
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_gui import start_server, wait  # noqa: E402
from test_lanes import start, stop  # noqa: E402
from test_queue import FakeAI, settings, until, upload  # noqa: E402
from skyrimtrans import plugin as pl  # noqa: E402


def opened(c, uid, lang="italian", source="english"):
    r = c.call("/api/proj/open", {"upload_id": uid, "lang": lang, "source": source})
    assert r[0] == 200, r
    return json.loads(r[1])["key"]


def page(c, key, **kw):
    q = "&".join(f"{k}={quote(str(v))}" for k, v in kw.items())
    r = c.call(f"/api/proj/page?key={key}" + (("&" + q) if q else ""))
    return r[0], json.loads(r[1])


def rows(c, key, **kw):
    return {r["orig"]: r for r in page(c, key, **kw)[1]["rows"]}


def texts_in_zip(path):
    """Testi del plugin dentro lo zip prodotto: {originale: tradotto} non serve, basta l'insieme dei testi."""
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".esp"))
        obj = pl.Plugin(z.read(name))
    units, _ = pl.extract_units(obj, "cp1252", name)
    return {u.text for u in units}


def test_open_before_translation_shows_original_strings(monkeypatch, tmp_path):
    httpd, app, c = start_server(monkeypatch, tmp_path)
    key = opened(c, upload(c, "M.esp"))
    code, p = page(c, key)
    assert code == 200 and p["total"] == 3 and p["matched"] == 3
    assert {r["orig"] for r in p["rows"]} == {"Ancient Tome", "Iron Sword", "Hello <Alias=Player>.\r\nYou have <mag> gold.[pagebreak]Page two."}
    assert all(r["tr"] is None and r["state"] == "todo" for r in p["rows"]) and p["counts"] == {"todo": 3}
    assert [r["orig"] for r in page(c, key, q="sword")[1]["rows"]] == ["Iron Sword"]      # ricerca
    assert page(c, key, state="edited")[1]["matched"] == 0 and page(c, key, file="nessuno.esp")[1]["matched"] == 0
    assert page(c, key, offset=1, limit=1)[1]["rows"][0]["i"] == 1                          # paginazione
    httpd.shutdown(); httpd.server_close()


def test_hand_edit_before_translation_survives_the_job(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    uid = upload(c, "M.esp")
    key = opened(c, uid)
    i = rows(c, key)["Iron Sword"]["i"]
    assert c.call("/api/proj/edit", {"key": key, "i": i, "text": "Spada di ferro"})[0] == 200
    assert rows(c, key)["Iron Sword"]["state"] == "edited"
    job = start(c, uid, ai)
    st = wait(c, job["job_id"])
    assert st["state"] == "done"
    out = texts_in_zip(app.jobs[job["job_id"]].out)
    assert "Spada di ferro" in out and "IT Ancient Tome" in out and "IT Iron Sword" not in out   # a mano vince, il resto lo fa l'AI
    assert ai.requests >= 1 and "Iron Sword" not in ai.texts and "Ancient Tome" in ai.texts   # la riga a mano non si manda all'AI
    stop(httpd, ai)


def test_edit_validation_keeps_tags_and_rejects_bad_rows(monkeypatch, tmp_path):
    httpd, app, c = start_server(monkeypatch, tmp_path)
    key = opened(c, upload(c, "M.esp"))
    r = rows(c, key)
    book = next(v for k, v in r.items() if k.startswith("Hello"))
    bad = c.call("/api/proj/edit", {"key": key, "i": book["i"], "text": "Ciao.\nHai tanto oro.[pagebreak]Pagina due."})
    assert bad[0] == 400 and "Tag" in json.loads(bad[1])["error"]                      # mancano <Alias=Player> e <mag>
    good = c.call("/api/proj/edit", {"key": key, "i": book["i"],
                                     "text": "Ciao <Alias=Player>.\nHai <mag> monete.[pagebreak]Pagina due."})
    assert good[0] == 200                                                                  # il "\n" della pagina vale come a capo originale
    assert rows(c, key)[book["orig"]]["tr"] == "Ciao <Alias=Player>.\r\nHai <mag> monete.[pagebreak]Pagina due."
    assert c.call("/api/proj/edit", {"key": key, "i": 99, "text": "x"})[0] == 400
    assert c.call("/api/proj/edit", {"key": "u:" + "0" * 32, "i": 0, "text": "x"})[0] == 404
    c.call("/api/proj/edit", {"key": key, "i": book["i"], "text": "  "})                   # vuoto = torna com'era
    assert rows(c, key)[book["orig"]]["state"] == "todo"
    httpd.shutdown(); httpd.server_close()


def test_translate_a_single_row_with_the_api(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    key = opened(c, upload(c, "M.esp"))
    i = rows(c, key)["Iron Sword"]["i"]
    s = {k: v for k, v in settings("x", ai).items() if k != "upload_id"}
    assert c.call("/api/proj/translate", {"key": key, "rows": [i], "settings": s})[0] == 200
    until(lambda: json.loads(c.call(f"/api/proj/page?key={key}")[1])["task"]["state"] == "done", "traduzione riga")
    r = rows(c, key)
    assert r["Iron Sword"]["tr"] == "IT Iron Sword" and r["Iron Sword"]["state"] == "done"
    assert r["Ancient Tome"]["state"] == "todo"                                              # le altre non sono toccate
    assert ai.requests == 1
    # ritradurre una riga già fatta chiede una risposta nuova (niente memoria)
    c.call("/api/proj/translate", {"key": key, "rows": [i], "settings": s})
    until(lambda: ai.requests == 2, "seconda richiesta")
    assert c.call("/api/proj/translate", {"key": key, "rows": [], "settings": s})[0] == 400
    stop(httpd, ai)


def test_translate_all_filtered_rows_and_errors(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    key = opened(c, upload(c, "M.esp"))
    s = {k: v for k, v in settings("x", ai).items() if k != "upload_id"}
    assert c.call("/api/proj/translate", {"key": key, "filter": {"q": "o", "state": "todo"}, "settings": s})[0] == 200
    until(lambda: json.loads(c.call(f"/api/proj/page?key={key}")[1])["task"]["state"] == "done", "traduzione filtrate")
    assert page(c, key)[1]["counts"] == {"done": 3}                                          # "o" è in tutte e tre
    stop(httpd, ai)
    # servizio non raggiungibile: errore chiaro, righe invariate
    httpd, app, c = start_server(monkeypatch, tmp_path)
    key = opened(c, upload(c, "M.esp"))
    dead = {k: v for k, v in settings("x", FakeAI()).items() if k != "upload_id"}
    dead["base_url"] = "http://127.0.0.1:9/v1"
    c.call("/api/proj/translate", {"key": key, "rows": [0], "settings": dead})
    t = until(lambda: (lambda x: x if x["state"] in ("error", "done") else None)(page(c, key)[1]["task"]), "errore")
    assert t["state"] == "error" and t["error"] and page(c, key)[1]["counts"].get("done", 0) == 0
    httpd.shutdown(); httpd.server_close()


def test_after_translation_edit_and_save_rewrites_the_result(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    job = start(c, upload(c, "M.esp"), ai)
    assert wait(c, job["job_id"])["state"] == "done"
    key = job["job_id"]
    p = page(c, key)[1]
    assert p["can_save"] and p["counts"] == {"done": 3} and p["job_state"] == "done"
    i = rows(c, key)["Iron Sword"]["i"]
    assert c.call("/api/proj/edit", {"key": key, "i": i, "text": "Spada di ferro"})[0] == 200
    assert "IT Iron Sword" in texts_in_zip(app.jobs[key].out)                               # finché non si salva, il file è quello di prima
    r = c.call("/api/proj/save", {"key": key})
    assert r[0] == 200
    out = texts_in_zip(app.jobs[key].out)
    assert "Spada di ferro" in out and "IT Iron Sword" not in out and "IT Ancient Tome" in out
    h = next(e for e in app.history.list() if e["id"] == key)
    assert h["available"] and h["translated"] == 3
    # lo zip scaricabile dalla cronologia è quello corretto
    r = c.call(f"/api/history/{key}/download")
    assert r[0] == 200
    stop(httpd, ai)


def test_cannot_translate_rows_while_the_mod_is_running_and_old_projects_close(monkeypatch, tmp_path):
    slow = FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    job = start(c, upload(c, "M.esp"), slow)
    until(lambda: app.jobs[job["job_id"]].project is not None, "progetto aperto")
    s = {k: v for k, v in settings("x", slow).items() if k != "upload_id"}
    assert c.call("/api/proj/translate", {"key": job["job_id"], "rows": [0], "settings": s})[0] == 409
    assert page(c, job["job_id"])[1]["total"] == 3                                           # intanto le righe si vedono
    assert c.call("/api/proj/save", {"key": job["job_id"]})[0] == 400                        # non ancora tradotta
    slow.gate.set()
    assert wait(c, job["job_id"])["state"] == "done"
    stop(httpd, slow)


def test_only_the_last_projects_stay_open(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    first = start(c, upload(c, "A.esp"), ai)
    assert wait(c, first["job_id"])["state"] == "done"
    ids = [first["job_id"]]
    for n in range(4):
        j = start(c, upload(c, f"B{n}.esp"), ai, lane=first["lane_id"])
        assert wait(c, j["job_id"])["state"] == "done"
        ids.append(j["job_id"])
    until(lambda: sum(1 for i in ids if app.jobs[i].project) <= app.MAX_PROJECTS, "vecchie chiuse")
    assert page(c, ids[0])[0] == 404 and page(c, ids[-1])[0] == 200
    stop(httpd, ai)
