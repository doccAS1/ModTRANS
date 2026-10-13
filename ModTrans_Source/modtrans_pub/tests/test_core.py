import json, tempfile
from pathlib import Path
from modtrans import pipeline
from modtrans.core.masking import mask, unmask
from modtrans.engines.base import MockEngine


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


if __name__ == "__main__":
    test_mask_roundtrip(); test_repair_loop(); print("tests ok")
