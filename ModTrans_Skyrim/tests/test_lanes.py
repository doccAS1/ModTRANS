import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_gui import start_server, wait  # noqa: E402
from test_queue import FakeAI, queue, settings, until, upload  # noqa: E402
from skyrimtrans.translator import TranslationStore  # noqa: E402


def start(c, uid, ai, lane="new", **kw):
    """Aggiunge una mod. lane='new' crea una coda con queste impostazioni; altrimenti usa quella indicata."""
    body = settings(uid, ai, **kw) if lane == "new" else {"upload_id": uid, **kw}
    body["lane_id"] = lane
    return json.loads(c.call("/api/start", body)[1])


def lanes(c):
    return {l["name"]: l for l in queue(c)["lanes"]}


def stop(httpd, *ais):
    for a in ais:
        a.close()
    httpd.shutdown(); httpd.server_close()


def test_two_lanes_run_in_parallel_each_with_its_own_api(monkeypatch, tmp_path):
    slow, fast = FakeAI(gated=True), FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    a = start(c, upload(c, "Slow.esp"), slow, model="modello-lento")
    b = start(c, upload(c, "Fast.esp"), fast, model="modello-veloce")
    assert a["lane_id"] != b["lane_id"]
    assert wait(c, b["job_id"])["state"] == "done"                     # la coda veloce finisce...
    st = json.loads(c.call(f"/api/status/{a['job_id']}")[1])
    assert st["state"] == "running"                                    # ...mentre l'altra è ancora in corso
    slow.gate.set()
    assert wait(c, a["job_id"])["state"] == "done"
    assert slow.models == {"modello-lento"} and fast.models == {"modello-veloce"}      # ognuna ha usato la sua API
    stop(httpd, slow, fast)


def test_inside_a_lane_mods_stay_sequential_while_other_lanes_run(monkeypatch, tmp_path):
    ai1, ai2 = FakeAI(gated=True), FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    a1 = start(c, upload(c, "A1.esp"), ai1)
    a2 = start(c, upload(c, "A2.esp"), ai1, lane=a1["lane_id"])
    b1 = start(c, upload(c, "B1.esp"), ai2)
    until(lambda: {j["id"]: j["state"] for j in queue(c)["jobs"]} ==
          {a1["job_id"]: "running", a2["job_id"]: "queued", b1["job_id"]: "running"}, "due in corso, una in attesa")
    ai1.gate.set(); ai2.gate.set()
    until(lambda: all(j["state"] == "done" for j in queue(c)["jobs"]), "tutte finite")
    assert [j["lane"] for j in queue(c)["jobs"]] == [a1["lane_id"], a1["lane_id"], b1["lane_id"]]
    stop(httpd, ai1, ai2)


def test_one_lane_pausing_does_not_stop_the_others(monkeypatch, tmp_path):
    ok = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    bad = start(c, upload(c, "Bad1.esp"), ok, base_url="http://127.0.0.1:9/v1")
    bad2 = start(c, upload(c, "Bad2.esp"), ok, lane=bad["lane_id"])
    good = start(c, upload(c, "Good.esp"), ok)
    assert wait(c, good["job_id"])["state"] == "done"
    until(lambda: lanes(c)["Coda 1"]["paused"], "prima coda in pausa")
    assert lanes(c)["Coda 2"]["paused"] is False and lanes(c)["Coda 1"]["pause_msg"]
    time.sleep(0.3)
    assert [j["state"] for j in queue(c)["jobs"] if j["lane"] == bad["lane_id"]] == ["error", "queued"]
    c.call("/api/queue/resume", {"lane_id": good["lane_id"]})            # riprendere un'altra coda non tocca quella in pausa
    assert lanes(c)["Coda 1"]["paused"] is True
    stop(httpd, ok)


def test_updating_a_lane_fixes_the_api_for_the_waiting_mods(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    first = start(c, upload(c, "A.esp"), ai, base_url="http://127.0.0.1:9/v1", model="vecchio")
    second = start(c, upload(c, "B.esp"), ai, lane=first["lane_id"])
    until(lambda: lanes(c)["Coda 1"]["paused"], "in pausa")
    fixed = settings(upload(c, "x.esp"), ai, model="nuovo")
    fixed.pop("upload_id")
    r = json.loads(c.call("/api/lane/update", {"lane_id": first["lane_id"], "settings": fixed})[1])
    assert "nuovo" in r["summary"] and "Italiano" in r["summary"]
    c.call("/api/queue/resume", {"lane_id": first["lane_id"]})
    assert wait(c, second["job_id"])["state"] == "done"
    assert ai.models == {"nuovo"}                                       # la mod in attesa ha usato le nuove impostazioni
    bad = dict(fixed, lang="english")                                   # stessa lingua dell'originale
    assert c.call("/api/lane/update", {"lane_id": first["lane_id"], "settings": bad})[0] == 400
    assert c.call("/api/lane/update", {"lane_id": "0" * 32, "settings": fixed})[0] == 404
    stop(httpd, ai)


def test_adding_to_an_existing_lane_uses_the_lane_settings_not_the_request(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    first = start(c, upload(c, "A.esp"), ai, model="della-coda")
    assert wait(c, first["job_id"])["state"] == "done"
    second = start(c, upload(c, "B.esp"), ai, lane=first["lane_id"], lang="french", model="altro", provider="anthropic")
    st = wait(c, second["job_id"])
    assert st["state"] == "done" and st["lang"] == "italian"           # la lingua e il modello restano quelli della coda
    assert ai.models == {"della-coda"}
    assert c.call("/api/start", {"upload_id": upload(c, "C.esp"), "lane_id": "0" * 32})[0] == 404
    stop(httpd, ai)


def test_clear_and_resume_can_target_a_single_lane(monkeypatch, tmp_path):
    g1, g2 = FakeAI(gated=True), FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    a = start(c, upload(c, "A1.esp"), g1)
    start(c, upload(c, "A2.esp"), g1, lane=a["lane_id"])
    b = start(c, upload(c, "B1.esp"), g2)
    b2 = start(c, upload(c, "B2.esp"), g2, lane=b["lane_id"])
    until(lambda: [j["state"] for j in queue(c)["jobs"]] == ["running", "queued", "running", "queued"], "stato iniziale")
    assert json.loads(c.call("/api/queue/clear", {"lane_id": a["lane_id"]})[1])["cancelled"] == 1
    states = {j["id"]: j["state"] for j in queue(c)["jobs"]}
    assert states[b2["job_id"]] == "queued" and list(states.values()).count("cancelled") == 1   # solo quella della coda A
    g1.gate.set(); g2.gate.set()
    until(lambda: queue(c)["jobs"][3]["state"] == "done", "B2 finita")
    stop(httpd, g1, g2)


def test_closing_lanes_and_the_limit(monkeypatch, tmp_path):
    ai = FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    a = start(c, upload(c, "A.esp"), ai)
    until(lambda: queue(c)["jobs"][0]["state"] == "running", "in corso")
    assert c.call("/api/lane/close", {"lane_id": a["lane_id"]})[0] == 400          # occupata
    ai.gate.set()
    wait(c, a["job_id"])
    until(lambda: not lanes(c)["Coda 1"]["busy"], "libera")
    assert c.call("/api/lane/close", {"lane_id": a["lane_id"]})[0] == 200
    assert queue(c)["lanes"] == [] and queue(c)["jobs"] == []                       # sparisce dalla coda; resta in cronologia
    assert len(json.loads(c.call("/api/history")[1])["entries"]) == 1
    assert c.call("/api/lane/close", {"lane_id": a["lane_id"]})[0] == 404
    uid = upload(c, "L.esp")
    for _ in range(6):
        assert c.call("/api/start", dict(settings(uid, ai, dry_run=True), lane_id="new"))[0] == 200
    code, body = c.call("/api/start", dict(settings(uid, ai, dry_run=True), lane_id="new"))
    assert code == 400 and "Al massimo 6 code" in json.loads(body)["error"]
    stop(httpd, ai)


def test_retry_goes_back_to_the_same_lane(monkeypatch, tmp_path):
    ai = FakeAI()
    httpd, app, c = start_server(monkeypatch, tmp_path)
    a = start(c, upload(c, "A.esp"), ai, base_url="http://127.0.0.1:9/v1")
    until(lambda: lanes(c)["Coda 1"]["paused"], "in pausa")
    again = json.loads(c.call(f"/api/retry/{a['job_id']}", {})[1])
    jobs = {j["id"]: j for j in queue(c)["jobs"]}
    assert jobs[again["job_id"]]["lane"] == a["lane_id"]
    stop(httpd, ai)


def test_two_lanes_saving_the_same_name_in_one_folder_do_not_collide(monkeypatch, tmp_path):
    ai = FakeAI(gated=True)
    httpd, app, c = start_server(monkeypatch, tmp_path)
    out = tmp_path / "Risultati"
    kw = dict(out_where="folder", out_dir=str(out), out_mode="zip")
    a = start(c, upload(c, "Same.esp"), ai, **kw)
    b = start(c, upload(c, "Same.esp"), ai, **kw)
    until(lambda: [j["state"] for j in queue(c)["jobs"]] == ["running", "running"], "entrambe in corso")
    ai.gate.set()
    sa, sb = wait(c, a["job_id"]), wait(c, b["job_id"])
    assert sa["state"] == sb["state"] == "done" and sa["saved_to"] != sb["saved_to"]
    assert sorted(p.name for p in out.iterdir()) == ["Same_italian (2).zip", "Same_italian.zip"]
    stop(httpd, ai)


def test_memory_file_shared_by_two_lanes_stays_valid(tmp_path):
    path = tmp_path / "m.jsonl"
    stores = [TranslationStore(path) for _ in range(4)]

    def work(st, n):
        for r in range(40):
            st.add(("name", f"T{n}-{r}-" + "x" * 3000), f"IT {n}-{r}")        # righe lunghe: quelle che si mescolerebbero
            st.flush()

    ts = [threading.Thread(target=work, args=(st, n)) for n, st in enumerate(stores)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(TranslationStore(path).load()) == 160                           # nessuna riga rovinata o persa


def test_output_and_memory_writes_are_serialized_between_lanes(tmp_path):
    """Deterministico: finché un'altra coda tiene il blocco, scrivere l'output o la memoria aspetta."""
    from skyrimtrans import pipeline as pp
    from skyrimtrans import translator as tr

    src = tmp_path / "out"
    src.mkdir()
    (src / "a.txt").write_text("a")
    st = TranslationStore(tmp_path / "m.jsonl")
    st.add(("name", "Iron Sword"), "Spada")
    for lock, action in ((pp._OUT_LOCK, lambda: pp.write_output(src, tmp_path / "r.zip", False)),
                         (tr._STORE_LOCK, st.flush)):
        done = threading.Event()
        with lock:
            t = threading.Thread(target=lambda a=action: (a(), done.set()))
            t.start()
            assert not done.wait(0.3)                                  # bloccata dall'altra coda
        assert done.wait(5)                                            # appena il blocco si libera, procede
        t.join()
    assert (tmp_path / "r.zip").exists() and TranslationStore(tmp_path / "m.jsonl").load() == {("name", "Iron Sword"): "Spada"}
