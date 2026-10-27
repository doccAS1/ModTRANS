import json, tempfile
from pathlib import Path
from modtrans import pipeline
from modtrans.core.masking import mask, unmask
from modtrans.core.models import Decision, Verdict
from modtrans.engines.base import MockEngine
from modtrans.qa.aggregate import aggregate


def test_mask_roundtrip():
    s = "Hey, @! 3 geodes#$b#Ok$h {{X}} %adj [388] ^him^her"
    m, t = mask(s)
    assert "@" not in m and "$h" not in m and "{{" not in m
    assert unmask(m, t) == s


class Saboteur(MockEngine):
    """Traduttore che perde un segnaposto; il repair lo ripara."""
    def chat(self, system, user):
        if "ROLE: translator" in system:
            items = json.loads(user)["items"]
            return json.dumps({i: v["text"].replace("⟦1⟧", "") for i, v in items.items()}, ensure_ascii=False)
        return super().chat(system, user)


def test_repair_loop(monkeypatch=None):
    import modtrans.pipeline as p
    orig = p.make_engine
    p.make_engine = lambda c: Saboteur()
    d = Path(tempfile.mkdtemp()); (d / "i18n").mkdir()
    (d / "manifest.json").write_text('{"UniqueID":"X.Y","Version":"1"}')
    (d / "i18n" / "default.json").write_text('{"a":"Hi @, take {{Item}} now"}')
    try:
        r = p.run(d, {"workdir": str(d / "w"), "translator": {"type": "mock"}}, log=lambda *_: None)
    finally:
        p.make_engine = orig
    out = json.load(open(d / "i18n" / "it.json"))
    assert "@" in out["a"] and "{{Item}}" in out["a"], out
    assert r["stats"].get("PUBLISH") == 1, r
    print("repair ok:", out)


def _mod(tmp):
    d = Path(tmp); (d / "i18n").mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text('{"UniqueID":"X.Y","Version":"1"}')
    (d / "i18n" / "default.json").write_text('{"a":"Hi @, take {{Item}} now"}')
    return d


def test_one_or_two_judges():
    """Regressione: con un solo giudice configurato la pipeline andava in AttributeError."""
    import modtrans.pipeline as p
    for name, extra in {"solo A": {"judge_a": {"type": "mock"}},
                        "solo B": {"judge_b": {"type": "mock"}},
                        "A e B": {"judge_a": {"type": "mock"}, "judge_b": {"type": "mock"}}}.items():
        d = _mod(tempfile.mkdtemp())
        cfg = {"workdir": str(d / "w"), "translator": {"type": "mock"}, **extra}
        r = p.run(d, cfg, log=lambda *_: None)
        assert r["stats"].get("PUBLISH") == 1, (name, r)
        out = json.load(open(d / "i18n" / "it.json"))
        assert "@" in out["a"] and "{{Item}}" in out["a"], (name, out)
    print("uno/due giudici ok")


def test_aggregate_missing_judges():
    ok = lambda s: Verdict("x", True, s)
    assert aggregate(None, None) == Decision.PUBLISH
    assert aggregate(ok(0.95), None) == Decision.PUBLISH
    assert aggregate(ok(0.7), None) == Decision.PUBLISH_WITH_NOTE
    assert aggregate(None, ok(0.95)) == Decision.PUBLISH
    assert aggregate(None, Verdict("B", False, 0.5)) == Decision.REVISION
    assert aggregate(Verdict("A", False, 0.0), None) == Decision.REPAIR
    print("aggregate ok")


def test_rerun_does_not_retranslate_own_output():
    """Il Description del manifest viene riscritto sul posto: il run successivo non deve ritradurlo."""
    import modtrans.pipeline as p
    d = _mod(tempfile.mkdtemp())
    (d / "manifest.json").write_text('{"UniqueID":"X.Y","Version":"1","Description":"A mod"}')
    cfg = {"workdir": str(d / "w"), "translator": {"type": "mock"}}
    p.run(d, cfg, log=lambda *_: None)
    assert json.load(open(d / "manifest.json"))["Description"] == "[IT] A mod"
    lines = []
    r = p.run(d, cfg, log=lines.append)
    assert "0 da tradurre" in lines[0], lines
    assert json.load(open(d / "manifest.json"))["Description"] == "[IT] A mod"
    assert r["stats"] == {}, r
    print("re-run ok")


class LangEcho(MockEngine):
    """Traduttore che marca l'output con la lingua richiesta nel prompt."""
    def chat(self, system, user):
        if "ROLE: translator" in system:
            tag = "FR" if "French" in system else "IT"
            items = json.loads(user)["items"]
            return json.dumps({i: f"[{tag}] " + v["text"] for i, v in items.items()}, ensure_ascii=False)
        return super().chat(system, user)


def test_languages_are_isolated():
    """Regressione: la TM e il manifest riusavano le traduzioni italiane per altre lingue."""
    import modtrans.pipeline as p
    orig = p.make_engine
    p.make_engine = lambda c: LangEcho()
    d = _mod(tempfile.mkdtemp())
    base = {"workdir": str(d / "w"), "translator": {"type": "mock"}}
    try:
        p.run(d, {**base, "target_lang_code": "it", "target_lang_name": "Italian"}, log=lambda *_: None)
        p.run(d, {**base, "target_lang_code": "fr", "target_lang_name": "French"}, log=lambda *_: None)
    finally:
        p.make_engine = orig
    it = json.load(open(d / "i18n" / "it.json"))["a"]
    fr = json.load(open(d / "i18n" / "fr.json"))["a"]
    assert it.startswith("[IT]") and fr.startswith("[FR]"), (it, fr)
    print("lingue separate ok")


def test_tm_migration():
    from modtrans.core.memory import TranslationMemory
    import sqlite3
    d = Path(tempfile.mkdtemp()); db = d / "tm.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE tm(game TEXT, src TEXT, gloss TEXT, dst TEXT, PRIMARY KEY(game, src, gloss))")
    c.execute("INSERT INTO tm VALUES('stardew','Hello','abcdef1234','Ciao')"); c.commit(); c.close()
    tm = TranslationMemory(db)
    assert tm.get("stardew", "Hello", "abcdef1234.it") == "Ciao"
    assert tm.get("stardew", "Hello", "abcdef1234.fr") is None
    print("migrazione TM ok")


# ---------------------------------------------------------------- sicurezza / robustezza
class Inject(MockEngine):
    """Traduttore ostile: aggiunge codici di gioco che nell'originale non ci sono."""
    def chat(self, system, user):
        if "ROLE: translator" in system:
            items = json.loads(user)["items"]
            return json.dumps({i: v["text"] + " {{EvilToken}} #$e# %spouse $h" for i, v in items.items()})
        return super().chat(system, user)


def test_injected_game_codes_never_reach_output():
    import modtrans.pipeline as p
    orig = p.make_engine
    p.make_engine = lambda c: Inject()
    d = _mod(tempfile.mkdtemp())
    (d / "i18n" / "default.json").write_text('{"a":"Welcome to the farm"}')
    try:
        p.run(d, {"workdir": str(d / "w"), "translator": {"type": "mock"}}, log=lambda *_: None)
    finally:
        p.make_engine = orig
    out = json.loads((d / "i18n" / "it.json").read_text()) if (d / "i18n" / "it.json").exists() else {}
    blob = json.dumps(out)
    assert "EvilToken" not in blob and "%spouse" not in blob and "#$e#" not in blob, out
    print("injection ok:", out)


def test_uniqueid_cannot_escape_project_dir():
    import modtrans.pipeline as p
    for uid in ["..", "."]:
        d = _mod(tempfile.mkdtemp())
        (d / "manifest.json").write_text('{"UniqueID":"%s","Version":"1"}' % uid)
        w = Path(tempfile.mkdtemp())
        p.run(d, {"workdir": str(w), "translator": {"type": "mock"}}, log=lambda *_: None)
        assert not (w / "projects" / "manifest.json").exists()
        assert not (w / "projects" / "stardew" / "manifest.json").exists()
        assert (w / "projects" / "stardew" / "_" / "manifest.json").exists()
    print("uniqueid ok")


def test_content_entries_skip_non_text():
    from modtrans.adapters.stardew import walk_content
    cj = {"Changes": [{"Action": "EditData", "Target": "Data/Foo",
                       "Entries": {"Flag": "true", "N": "42", "Item": "(O)388", "Id": "{{ModId}}_Foo",
                                   "Path": "Foo.Bar", "Name": "Golden Apple"},
                       "Text": "Hello there"}]}
    got = dict(walk_content(cj))
    assert set(got.values()) == {"Golden Apple", "Hello there"}, got
    print("entries ok")


def test_backups_in_same_second_do_not_overwrite():
    import modtrans.pipeline as p
    d = _mod(tempfile.mkdtemp())
    (d / "manifest.json").write_text('{"UniqueID":"X.Y","Version":"1","Description":"Original"}')
    cfg = {"workdir": str(d / "w"), "translator": {"type": "mock"}}
    p.run(d, cfg, log=lambda *_: None); p.run(d, cfg, log=lambda *_: None)
    assert p.restore(d, cfg) and p.restore(d, cfg)
    assert json.load(open(d / "manifest.json"))["Description"] == "Original"
    print("backup unici ok")


def test_language_code_cannot_traverse():
    import modtrans.pipeline as p
    from modtrans.core.fsutil import valid_lang
    d = _mod(tempfile.mkdtemp())
    for bad in ["../pwned", "it/../../x", "", "a", "it.json"]:
        try:
            p.run(d, {"workdir": str(d / "w"), "translator": {"type": "mock"}, "target_lang_code": bad},
                  log=lambda *_: None)
            raise AssertionError(f"accettato {bad!r}")
        except SystemExit:
            pass
    assert not (d / "pwned.json").exists()
    for good in ["it", "fr", "zh-CN", "pt_BR"]:
        assert valid_lang(good) == good
    print("lingua ok")


def test_review_cli_makes_no_ai_calls_and_dry_run_writes_nothing():
    import modtrans.pipeline as p, sqlite3, io, contextlib
    from modtrans import cli
    calls = []

    class Count(MockEngine):
        def chat(self, s, u):
            calls.append(1); return super().chat(s, u)
    orig = p.make_engine
    p.make_engine = lambda c: Count()
    d = _mod(tempfile.mkdtemp()); w = d / "w"
    cp = d / "c.toml"; cp.write_text(f'workdir = "{w.as_posix()}"\n[translator]\ntype = "mock"\n')
    try:
        p.run(d, {"workdir": str(w), "translator": {"type": "mock"}}, dry_run=True, log=lambda *_: None)
        rows = sqlite3.connect(w / "tm.sqlite").execute("select count(*) from tm").fetchone()[0]
        assert rows == 0 and not list(w.rglob("review.json")) and not (d / "i18n" / "it.json").exists()
        calls.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["review", str(d), "-c", str(cp)])
        assert calls == [], "review non deve chiamare l'LLM"
    finally:
        p.make_engine = orig
    print("review/dry-run ok")


def test_lenient_json_comments_before_closing_bracket():
    from modtrans.adapters.stardew import load_lenient
    cases = {'{"a":1, // nota\n}': {"a": 1}, '{"a":1,\n/* x */ }': {"a": 1},
             '{"a":[1,2,\n// c\n]}': {"a": [1, 2]}, '{"a":"x, // y",}': {"a": "x, // y"}}
    for txt, want in cases.items():
        f = Path(tempfile.mkdtemp()) / "m.json"; f.write_text(txt)
        assert load_lenient(f) == want, (txt, load_lenient(f))
    print("json lenient ok")


def test_safe_extract_zip():
    import zipfile
    from modtrans.core.fsutil import safe_extract_zip
    t = Path(tempfile.mkdtemp())

    def mk(name, entries):
        with zipfile.ZipFile(t / name, "w", zipfile.ZIP_DEFLATED) as z:
            for n, data in entries.items():
                z.writestr(n, data)
        return t / name
    safe_extract_zip(mk("ok.zip", {"Mod/manifest.json": "{}"}), t / "ok")
    assert (t / "ok" / "Mod" / "manifest.json").exists()
    for bad, label in [({"../evil.txt": "x"}, "zip-slip"), ({"/abs.txt": "x"}, "assoluto")]:
        try:
            safe_extract_zip(mk("bad.zip", bad), t / "bad"); raise AssertionError(label)
        except ValueError:
            pass
        assert not (t / "evil.txt").exists() and not (t / "bad").exists()
    bomb = mk("bomb.zip", {f"f{i}.bin": b"\0" * (1 << 20) for i in range(3)})   # ~3 MB espansi
    try:
        safe_extract_zip(bomb, t / "bomb", max_total=2 << 20); raise AssertionError("bomb")
    except ValueError:
        assert not (t / "bomb").exists()
    try:
        safe_extract_zip(bomb, t / "many", max_entries=2); raise AssertionError("entries")
    except ValueError:
        pass
    print("zip sicuro ok")


def test_mask_literal_placeholder_roundtrip():
    s = "keep \u27e61\u27e7 and {{X}} and %name"
    m, t = mask(s)
    assert unmask(m, t) == s, (m, t)
    print("token letterali ok")


def test_api_key_not_sent_over_plain_http():
    import os
    from modtrans.engines.base import OpenAICompatEngine
    os.environ["MT_TEST_KEY"] = "k"
    try:
        OpenAICompatEngine("m", base_url="http://example.com/v1", api_key_env="MT_TEST_KEY"); raise AssertionError("http")
    except ValueError:
        pass
    for ok in ["https://openrouter.ai/api/v1", "http://localhost:11434/v1", "http://127.0.0.1:1234/v1",
               "http://192.168.1.5:8000/v1"]:
        OpenAICompatEngine("m", base_url=ok, api_key_env="MT_TEST_KEY")
    print("chiave/https ok")


# ---------------------------------------------------------------- fix gravi (1.1, 1.2, 2.1)
class RecLang(MockEngine):
    """Traduttore che marca la lingua e registra i testi che riceve."""
    seen = []

    def chat(self, system, user):
        if "ROLE: translator" in system:
            tag = "FR" if "French" in system else "IT"
            items = json.loads(user)["items"]
            for v in items.values():
                RecLang.seen.append((tag, v["key"], v["text"]))
            return json.dumps({i: f"[{tag}] " + v["text"] for i, v in items.items()}, ensure_ascii=False)
        return super().chat(system, user)


def _lang_run(p, d, w, code, name):
    return p.run(d, {"workdir": str(w), "translator": {"type": "mock"},
                     "target_lang_code": code, "target_lang_name": name}, log=lambda *_: None)


def _with_engine(p, factory):
    orig = p.make_engine
    p.make_engine = factory
    return orig


def test_languages_never_stack_on_inplace_text():
    """1.1: it -> fr -> it non deve partire da testi già tradotti (Description e content.json)."""
    import modtrans.pipeline as p
    orig = _with_engine(p, lambda c: RecLang())
    try:
        d1 = _mod(tempfile.mkdtemp())
        (d1 / "manifest.json").write_text('{"UniqueID":"A.B","Version":"1","Description":"A test mod"}')
        d2 = Path(tempfile.mkdtemp()); (d2 / "manifest.json").write_text('{"UniqueID":"C.D","Version":"1"}')
        (d2 / "content.json").write_text('{"Changes":[{"Action":"EditData","Target":"X","Text":"Hello farmer"}]}')
        for d, read, orig_text in [(d1, lambda d: json.load(open(d / "manifest.json"))["Description"], "A test mod"),
                                   (d2, lambda d: json.load(open(d / "content.json"))["Changes"][0]["Text"], "Hello farmer")]:
            w = Path(tempfile.mkdtemp()); RecLang.seen.clear()
            _lang_run(p, d, w, "it", "Italian"); _lang_run(p, d, w, "fr", "French"); _lang_run(p, d, w, "it", "Italian")
            sources = [txt for _, k, txt in RecLang.seen if "Description" in k or "Text" in k]
            assert sources == [orig_text, orig_text], sources          # il run it finale è riusato, non ritradotto
            assert read(d) == f"[IT] {orig_text}", read(d)              # e sul disco c'è di nuovo l'italiano
            _lang_run(p, d, w, "fr", "French")
            assert read(d) == f"[FR] {orig_text}", read(d)
    finally:
        p.make_engine = orig
    print("lingue non si impilano ok")


def test_originals_migration_and_author_update():
    """1.1: dati di versioni senza registro (migrazione) e mod aggiornata dall'autore."""
    import modtrans.pipeline as p
    orig = _with_engine(p, lambda c: RecLang())
    try:
        d = _mod(tempfile.mkdtemp())
        (d / "manifest.json").write_text('{"UniqueID":"A.B","Version":"1","Description":"A test mod"}')
        w = Path(tempfile.mkdtemp())
        _lang_run(p, d, w, "it", "Italian")
        for f in w.rglob("originals.json"):
            f.unlink()                                                   # come una versione precedente del tool
        RecLang.seen.clear()
        _lang_run(p, d, w, "fr", "French")
        assert [t for _, k, t in RecLang.seen if "Description" in k] == ["A test mod"], RecLang.seen
        # l'autore pubblica una nuova versione: il testo sul disco non è né l'originale né una nostra traduzione
        (d / "manifest.json").write_text('{"UniqueID":"A.B","Version":"2","Description":"Brand new text"}')
        RecLang.seen.clear()
        _lang_run(p, d, w, "it", "Italian")
        assert [t for _, k, t in RecLang.seen if "Description" in k] == ["Brand new text"], RecLang.seen
        assert json.load(open(d / "manifest.json"))["Description"] == "[IT] Brand new text"
    finally:
        p.make_engine = orig
    print("migrazione/aggiornamento autore ok")


class FailJudge(MockEngine):
    """Giudice che fallisce (rete / JSON non valido) alle chiamate indicate."""
    def __init__(self, fail_on=None, exc=RuntimeError("HTTP 503 (simulato)")):
        self.n, self.fail_on, self.exc = 0, fail_on, exc

    def chat(self, system, user):
        if "ROLE: judge" in system:
            self.n += 1
            if self.fail_on is None or self.n in self.fail_on:
                raise self.exc
        return super().chat(system, user)


def _four_strings():
    d = _mod(tempfile.mkdtemp())
    (d / "i18n" / "default.json").write_text('{"a":"One","b":"Two","c":"Three","d":"Four"}')
    return d


def test_judge_and_repair_errors_do_not_crash_the_run():
    """1.2: un errore di rete / JSON malformato nei giudici o nel repair non deve interrompere il run."""
    import modtrans.pipeline as p
    # a) un solo errore: la stringa resta in inglese (BLOCK) e viene ritentata al run successivo
    d = _four_strings(); w = d / "w"; judge = FailJudge({2})
    orig = _with_engine(p, lambda c: judge if c.get("tag") == "j" else MockEngine())
    cfg = {"workdir": str(w), "translator": {"type": "mock"}, "judge_a": {"type": "mock", "tag": "j"}}
    try:
        r = p.run(d, cfg, log=lambda *_: None)
        assert r["stats"] == {"PUBLISH": 3, "BLOCK": 1}, r["stats"]
        assert len(json.load(open(d / "i18n" / "it.json"))) == 3
        assert any(m for m in w.rglob("manifest.json")), "il manifest deve essere salvato"
        blocked = [v for v in r["review"].values() if v["decision"] == "BLOCK"][0]
        assert blocked["issues"][-1]["type"] == "engine_error"
        p.make_engine = lambda c: MockEngine()                           # il motore torna disponibile
        r2 = p.run(d, cfg, log=lambda *_: None)
        assert r2["stats"] == {"PUBLISH": 1} and len(json.load(open(d / "i18n" / "it.json"))) == 4, r2
        # b) motore non raggiungibile: dopo 3 errori di fila si interrompe, senza crash, e salva
        d = _four_strings(); w = d / "w"; logs = []
        d2 = d / "i18n" / "default.json"; d2.write_text('{"a":"One","b":"Two","c":"Three","d":"Four","e":"Five"}')
        p.make_engine = lambda c: FailJudge(None) if c.get("tag") == "j" else MockEngine()
        cfg = {"workdir": str(w), "translator": {"type": "mock"}, "judge_a": {"type": "mock", "tag": "j"}}
        r = p.run(d, cfg, log=logs.append)
        assert r["stats"] == {"BLOCK": 5}, r["stats"]
        assert any("interrompo" in l for l in logs), logs
        assert any(m for m in w.rglob("manifest.json"))
        # c) il repair fallisce
        d = _mod(tempfile.mkdtemp()); (d / "i18n" / "default.json").write_text('{"a":"Hi @, take {{Item}} now"}')

        class FailRepair(Saboteur):
            def chat(self, system, user):
                if "ROLE: repair" in system:
                    raise ValueError("JSON non valido (simulato)")
                return super().chat(system, user)
        p.make_engine = lambda c: FailRepair()
        r = p.run(d, {"workdir": str(d / "w"), "translator": {"type": "mock"}}, log=lambda *_: None)
        assert r["stats"] == {"BLOCK": 1}, r["stats"]
        # d) errore imprevisto (non Exception): i risultati già ottenuti non vanno persi
        d = _four_strings(); w = d / "w"
        p.make_engine = lambda c: FailJudge({2}, KeyboardInterrupt()) if c.get("tag") == "j" else MockEngine()
        cfg = {"workdir": str(w), "translator": {"type": "mock"}, "judge_a": {"type": "mock", "tag": "j"}}
        try:
            p.run(d, cfg, log=lambda *_: None); raise AssertionError("doveva interrompersi")
        except KeyboardInterrupt:
            pass
        man = json.load(open(next(w.rglob("manifest.json"))))
        assert len(man["units"]) == 1, man["units"].keys()               # la prima stringa è salva
    finally:
        p.make_engine = orig
    print("errori giudici/repair ok")


def test_unreviewed_flag():
    class Doubt(MockEngine):
        def chat(self, system, user):
            if "ROLE: judge" in system:
                return json.dumps({"score": 0.2, "ok": False, "issues": []})
            return super().chat(system, user)
    def run(judge_b_engine):
        real = pipeline.make_engine
        pipeline.make_engine = lambda c: judge_b_engine if c.get("type") == "doubt" else real(c)
        try:
            with tempfile.TemporaryDirectory() as d:
                mod = Path(d) / "m"; (mod / "i18n").mkdir(parents=True)
                (mod / "manifest.json").write_text(json.dumps({"Name": "M", "UniqueID": "a.b", "Version": "1.0"}))
                (mod / "i18n" / "default.json").write_text(json.dumps({"k": "Hello farmer"}))
                cfg = {"workdir": str(Path(d) / "w"), "translator": {"type": "mock"},
                       "judge_a": {"type": "mock"}, "judge_b": {"type": "doubt"}}
                msgs = []
                r = pipeline.run(mod, cfg, log=msgs.append)
                written = json.loads((mod / "i18n" / "it.json").read_text(encoding="utf-8"))
                return r, msgs, written
        finally:
            pipeline.make_engine = real
    r, msgs, written = run(Doubt())
    assert r["unreviewed"] == ["k"] and "k" in written and any("ATTENZIONE" in m for m in msgs), (r, msgs)
    r, msgs, written = run(MockEngine())
    assert r["unreviewed"] == [] and not any("ATTENZIONE" in m for m in msgs)
    print("flag non verificate ok")


def test_medium_bugs():
    import socket, urllib.request
    from modtrans.engines import base
    from modtrans.engines.base import extract_json, OpenAICompatEngine
    from modtrans.core.glossary import Glossary
    # 3.2: JSON con note e graffe attorno
    assert extract_json('Note {x}\n```json\n{"a": {"b": 1}}\n```\nbye {y}') == {"a": {"b": 1}}
    assert extract_json('Ecco: {"a": 1} (vedi {docs})') == {"a": 1}
    try:
        extract_json("niente json {qui}"); assert False
    except ValueError:
        pass
    # 3.3: timeout configurabile, e un read timeout viene ritentato
    assert OpenAICompatEngine("m", timeout=7).timeout == 7 and OpenAICompatEngine("m").timeout == 120
    calls = []
    real, sleep = urllib.request.urlopen, base.time.sleep
    def flaky(req, timeout=None):
        calls.append(timeout)
        if len(calls) < 3:
            raise socket.timeout("timed out")
        import io; return io.BytesIO(b'{"ok": 1}')
    urllib.request.urlopen, base.time.sleep = flaky, lambda *_: None
    try:
        assert base._post("http://x", {}, {}, timeout=9) == {"ok": 1} and calls == [9, 9, 9]
    finally:
        urllib.request.urlopen, base.time.sleep = real, sleep
    # 3.4: termini con punteggiatura e CJK
    g = Glossary({"C++": "C++", "勇者": "Eroe"}, ["Pelican Town!"])
    assert g._has("C++", "I like C++ a lot") and g._has("勇者", "这是勇者的剑")
    assert g._has("Pelican Town!", "Hi Pelican Town! bye") and not g._has("cat", "concatenate")
    # 2.3: codici prima scoperti
    for src in ["Take [O 388] now", "Pick $1 or $A", "$q -1 null#Hello?", "$q 100/101 fb#Hi", "$r 5 10 evt#Nice"]:
        m, t = mask(src)
        assert unmask(m, t) == src
        assert "null" not in m and "[O" not in m and "$1" not in m and "$A" not in m and "fb" not in m and "evt" not in m, m
    print("bug medi ok")


def test_number_check_no_blocking_false_positives():
    """2.1: separatori delle migliaia, numeri scritti a lettere; i numeri CAMBIATI restano un errore grave."""
    from modtrans.core.glossary import Glossary
    from modtrans.core.masking import mask
    from modtrans.core.models import Unit
    from modtrans.qa.judges import JudgeA

    def check(src, tr):
        u = Unit("k", src); u.masked, u.tokens = mask(src)
        v = JudgeA(Glossary(), None).evaluate(u, tr)
        return [i["type"] for i in v.issues], v.hard
    assert check("You have 1,000g", "Hai 1.000g") == ([], False)
    assert check("You have 1,000g", "Hai 1000g") == ([], False)
    assert check("You have 1,000,000g", "Hai 1.000.000g") == ([], False)
    assert check("three apples", "3 mele") == ([], False)
    assert check("Day 2", "Giorno 2") == ([], False)
    assert check("the 1st of spring", "il primo di primavera") == (["number_missing"], False)
    assert check("3 apples", "tre mele") == (["number_missing"], False)
    assert check("You have 50 gold", "Hai oro") == (["number_missing"], False)
    assert check("Costs 100g", "Costa 10g") == (["number"], True)          # numero cambiato: grave
    assert check("Costs 100g", "Costa 100g e 7 monete") == (["number"], True)   # numero inventato: grave
    print("controllo numeri ok")


if __name__ == "__main__":
    test_mask_roundtrip(); test_repair_loop(); test_one_or_two_judges(); test_aggregate_missing_judges()
    test_rerun_does_not_retranslate_own_output(); test_languages_are_isolated(); test_tm_migration()
    test_injected_game_codes_never_reach_output(); test_uniqueid_cannot_escape_project_dir()
    test_content_entries_skip_non_text(); test_backups_in_same_second_do_not_overwrite()
    test_language_code_cannot_traverse(); test_review_cli_makes_no_ai_calls_and_dry_run_writes_nothing()
    test_lenient_json_comments_before_closing_bracket(); test_safe_extract_zip()
    test_mask_literal_placeholder_roundtrip(); test_api_key_not_sent_over_plain_http()
    test_languages_never_stack_on_inplace_text(); test_originals_migration_and_author_update()
    test_judge_and_repair_errors_do_not_crash_the_run(); test_number_check_no_blocking_false_positives()
    test_medium_bugs(); test_unreviewed_flag()
    print("tests ok")
