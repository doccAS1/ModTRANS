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


if __name__ == "__main__":
    test_mask_roundtrip(); test_repair_loop(); test_one_or_two_judges(); test_aggregate_missing_judges()
    test_rerun_does_not_retranslate_own_output(); test_languages_are_isolated(); test_tm_migration()
    print("tests ok")
