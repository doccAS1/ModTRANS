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


if __name__ == "__main__":
    test_mask_roundtrip(); test_repair_loop(); test_one_or_two_judges(); test_aggregate_missing_judges()
    test_rerun_does_not_retranslate_own_output(); test_languages_are_isolated(); test_tm_migration()
    test_injected_game_codes_never_reach_output(); test_uniqueid_cannot_escape_project_dir()
    test_content_entries_skip_non_text(); test_backups_in_same_second_do_not_overwrite()
    test_language_code_cannot_traverse(); test_review_cli_makes_no_ai_calls_and_dry_run_writes_nothing()
    test_lenient_json_comments_before_closing_bracket(); test_safe_extract_zip()
    test_mask_literal_placeholder_roundtrip(); test_api_key_not_sent_over_plain_http()
    print("tests ok")
