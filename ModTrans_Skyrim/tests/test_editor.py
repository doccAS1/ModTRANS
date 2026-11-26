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
from test_queue import FakeAI, queue, settings, until, upload  # noqa: E402
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


# ------------------------------------------------------------------ scarica ora (zip parziale)
def download(c, key):
    """(codice, nome file, byte) del download parziale/finale di una mod aperta."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(f"{c.base}/api/proj/download?key={key}", headers={"X-Token": c.tok})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers.get("Content-Disposition", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, "", e.read()


def texts_in_bytes(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".esp"))
        obj = pl.Plugin(z.read(name))
    units, _ = pl.extract_units(obj, "cp1252", name)
    return {u.text for u in units}


def test_download_now_while_the_mod_is_still_running(monkeypatch, tmp_path):
    """Mod in corso (nessuna riga consolidata): lo zip si scarica lo stesso, con ciò che c'è già."""
    slow = FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    job = start(c, upload(c, "M.esp"), slow)
    key = job["job_id"]
    until(lambda: app.jobs[key].project is not None, "progetto aperto")
    code, cd, data = download(c, key)
    assert code == 200 and "_parziale.zip" in cd
    assert "Iron Sword" in texts_in_bytes(data)                                     # niente tradotto ancora: tutto originale
    # arriva una parte delle traduzioni (cache del traduttore in corso): finisce nello zip, il resto resta originale
    proj = app.jobs[key].project
    for u in proj.units:
        if u.text == "Iron Sword":
            proj.live = {(u.kind, u.text): "Spada di ferro"}
    code, cd, data = download(c, key)
    out = texts_in_bytes(data)
    assert code == 200 and "Spada di ferro" in out and "Ancient Tome" in out and "Iron Sword" not in out
    proj.live = None
    slow.gate.set()
    assert wait(c, key)["state"] == "done"
    stop(httpd, slow)


def test_download_now_includes_hand_edits_and_final_name_has_no_partial_suffix(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    uid = upload(c, "M.esp")
    key = opened(c, uid)                                                              # mod aperta, mai tradotta
    i = rows(c, key)["Iron Sword"]["i"]
    c.call("/api/proj/edit", {"key": key, "i": i, "text": "Spada di ferro"})
    code, cd, data = download(c, key)
    assert code == 200 and "_parziale" in cd
    out = texts_in_bytes(data)
    assert "Spada di ferro" in out and "Ancient Tome" in out                          # a mano + resto in originale
    job = start(c, uid, ai)
    assert wait(c, job["job_id"])["state"] == "done"
    code, cd, data = download(c, job["job_id"])
    assert code == 200 and "_parziale" not in cd and "M_italian.zip" in cd
    assert texts_in_bytes(data) >= {"Spada di ferro", "IT Ancient Tome"}
    assert download(c, "u:" + "0" * 32)[0] == 404
    # il download parziale non tocca ciò che è stato salvato e non lascia file temporanei in giro
    assert not list(app.work.glob("parziale-*.zip"))
    stop(httpd, ai)


def test_partial_build_ignores_live_when_not_partial(monkeypatch, tmp_path):
    httpd, app, c = start_server(monkeypatch, tmp_path)
    key = opened(c, upload(c, "M.esp"))
    proj = app.project_for(key)
    u = next(x for x in proj.units if x.text == "Iron Sword")
    proj.live = {(u.kind, u.text): "Spada"}
    proj.build(tmp_path / "a.zip", overwrite=True)                                    # build "vero": solo righe consolidate/a mano
    proj.build(tmp_path / "b.zip", overwrite=True, partial=True)
    assert "Iron Sword" in texts_in_bytes((tmp_path / "a.zip").read_bytes())
    assert "Spada" in texts_in_bytes((tmp_path / "b.zip").read_bytes())
    httpd.shutdown(); httpd.server_close()


def test_download_now_after_cancel_keeps_what_was_already_translated(monkeypatch, tmp_path):
    """Lavoro annullato a metà: lo zip c'è lo stesso, con le righe già tradotte e il resto in originale."""
    ai = FakeAI(hold_after=1)                                   # la prima richiesta passa, le altre aspettano
    httpd, app, c = start_server(monkeypatch, tmp_path)
    key = start(c, upload(c, "M.esp"), ai, batch_items=1)["job_id"]
    until(lambda: app.jobs[key].project is not None and app.jobs[key].project.live, "prima riga tradotta")
    assert json.loads(c.call(f"/api/status/{key}")[1])["has_project"] is True
    c.call(f"/api/cancel/{key}", {})
    ai.gate.set()
    until(lambda: app.jobs[key].state == "cancelled", "annullato")
    code, cd, data = download(c, key)
    assert code == 200 and "M_italian_parziale.zip" in cd
    out = texts_in_bytes(data)
    assert any(t.startswith("IT ") for t in out)                # qualcosa è stato tradotto...
    assert any(not t.startswith("IT ") for t in out)            # ...e il resto è com'era, non rotto né perso
    assert [j for j in queue(c)["jobs"] if j["id"] == key][0]["has_project"] is True
    stop(httpd, ai)


def test_download_now_says_why_when_there_is_nothing_to_download(monkeypatch, tmp_path):
    slow = FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    uid = upload(c, "M.esp")
    first = start(c, uid, slow)
    lane = first["lane_id"]
    second = start(c, upload(c, "N.esp"), slow, lane=lane)                          # stessa coda: aspetta il suo turno
    until(lambda: app.jobs[first["job_id"]].project is not None, "primo aperto")
    code, _, body = download(c, second["job_id"])
    assert code == 409 and "in coda" in json.loads(body)["error"]
    assert [j for j in queue(c)["jobs"] if j["id"] == second["job_id"]][0]["has_project"] is False
    slow.gate.set()
    assert wait(c, first["job_id"])["state"] == "done"
    app.jobs[first["job_id"]].project = None                                        # chiusa per fare posto alle altre
    code, _, body = download(c, first["job_id"])
    assert code == 404 and "memoria" in json.loads(body)["error"]
    stop(httpd, slow)
