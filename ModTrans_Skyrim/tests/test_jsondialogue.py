import json
import zipfile

from test_all import FakeBackend, run
from skyrimtrans import jsontext
from skyrimtrans.translator import Translator

SAMPLE = """{
  "pack": {"id": "x.base.001", "name": "Base pack", "type": "dialogue", "schemaVersion": "3.1"},
  "DISABLED": false,
  "Greet_A": {
    "event": "scene",
    "actions": ["hug", "kiss"],
    "actorCount": 2,
    "relationship": [">=0", "<=4"],
    "lines": [
      {"id": "a.1", "speaker": "target", "mouthOccupied": "free", "text": "You look lovely today."},
      {
        "id": "a.2",
        "speaker": "actor",
        "text": "Hello, <Alias=Player>! \\"Welcome\\"\\nTake 100 coins."
      }
    ]
  },
  "Empty": {"lines": [{"id": "a.3", "text": ""}]},
  "tags": ["text", "lines"]
}
"""


def _mod(tmp_path, text=SAMPLE, name="Packs/P/Dialogue/Base.json"):
    mod = tmp_path / "m"
    f = mod / name
    f.parent.mkdir(parents=True)
    f.write_text(text, encoding="utf-8")
    return mod


def test_only_line_text_is_translated(tmp_path):
    mod = _mod(tmp_path)
    out = tmp_path / "o.zip"
    rep = run(mod, out, Translator(FakeBackend(), "Italian"), "italian")
    new = zipfile.ZipFile(out).read("Packs/P/Dialogue/Base.json").decode("utf-8")
    a, b = json.loads(SAMPLE), json.loads(new)
    assert b["Greet_A"]["lines"][0]["text"] == "IT You look lovely today."
    assert b["Greet_A"]["lines"][1]["text"] == 'IT Hello, <Alias=Player>! "Welcome"\nTake 100 coins.'
    # tutto il resto è identico, riga per riga
    b["Greet_A"]["lines"][0]["text"] = a["Greet_A"]["lines"][0]["text"]
    b["Greet_A"]["lines"][1]["text"] = a["Greet_A"]["lines"][1]["text"]
    assert a == b
    assert rep.translated == 2 and not rep.failures


def test_layout_is_preserved(tmp_path):
    """Spazi, rientri e a capo restano quelli del file originale: cambiano solo le stringhe 'text'."""
    mod = _mod(tmp_path)
    out = tmp_path / "o.zip"
    run(mod, out, Translator(FakeBackend(), "Italian"), "italian")
    new = zipfile.ZipFile(out).read("Packs/P/Dialogue/Base.json").decode("utf-8")
    import re
    strip = lambda s: re.sub(r'"text": "(?:[^"\\]|\\.)*"', '"text": X', s)
    assert strip(new) == strip(SAMPLE)


def test_other_json_files_untouched(tmp_path):
    other = '{"name": "Config", "text": "Do not touch me", "lines": ["x"], "items": [{"text": "no id"}]}'
    mod = _mod(tmp_path, other, "Config/settings.json")
    out = tmp_path / "o.zip"
    rep = run(mod, out, Translator(FakeBackend(), "Italian"), "italian")
    assert zipfile.ZipFile(out).read("Config/settings.json").decode() == other
    assert rep.translated == 0


def test_text_with_id_outside_lines_is_not_translated(tmp_path):
    other = '{"Entry": {"id": "z", "text": "Not a dialogue line"}}'
    mod = _mod(tmp_path, other, "a.json")
    out = tmp_path / "o.zip"
    run(mod, out, Translator(FakeBackend(), "Italian"), "italian")
    assert zipfile.ZipFile(out).read("a.json").decode() == other


def test_broken_json_is_copied_with_warning(tmp_path):
    broken = '{"lines": [ {"id": "a", "text": "Hi" '
    mod = _mod(tmp_path, broken, "b.json")
    out = tmp_path / "o.zip"
    rep = run(mod, out, Translator(FakeBackend(), "Italian"), "italian")
    assert zipfile.ZipFile(out).read("b.json").decode() == broken
    assert any("JSON non analizzabile" in w for w in rep.warnings)


def test_bom_and_unicode_kept(tmp_path):
    text = '{"G": {"lines": [{"id": "1", "text": "Café ☕"}]}}'
    mod = tmp_path / "m"
    (mod / "u.json").parent.mkdir(parents=True)
    (mod / "u.json").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    out = tmp_path / "o.zip"
    run(mod, out, Translator(FakeBackend(), "Italian"), "italian")
    raw = zipfile.ZipFile(out).read("u.json")
    assert raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw[3:].decode("utf-8"))["G"]["lines"][0]["text"] == "IT Café ☕"


def test_verify_catches_structure_change():
    parsed = jsontext.parse(SAMPLE)
    bad = SAMPLE.replace('"hug"', '"hugs"')
    assert jsontext.verify(SAMPLE, bad, parsed)
    bad2 = SAMPLE.replace('"a.1"', '"a.9"')
    assert jsontext.verify(SAMPLE, bad2, parsed)
    good = jsontext.apply_units(SAMPLE, parsed, {p: "X" for p in parsed[1]})
    assert jsontext.verify(SAMPLE, good, parsed) == []


def test_list_with_other_name_or_without_id_is_not_translated(tmp_path):
    other = ('{"A": {"items": [{"id": "1", "text": "Not in a lines list"}]},'
             ' "B": {"lines": [{"speaker": "x", "text": "No id here"}]}}')
    mod = _mod(tmp_path, other, "c.json")
    out = tmp_path / "o.zip"
    rep = run(mod, out, Translator(FakeBackend(), "Italian"), "italian")
    assert zipfile.ZipFile(out).read("c.json").decode() == other
    assert rep.translated == 0
