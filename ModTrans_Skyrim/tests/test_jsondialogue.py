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
    rep = run(mod, out, Translator(FakeBackend(), "Italian"), "italian", json_mode="known")
    assert zipfile.ZipFile(out).read("Config/settings.json").decode() == other
    assert rep.translated == 0


def test_text_with_id_outside_lines_is_not_translated(tmp_path):
    other = '{"Entry": {"id": "z", "text": "Not a dialogue line"}}'
    mod = _mod(tmp_path, other, "a.json")
    out = tmp_path / "o.zip"
    run(mod, out, Translator(FakeBackend(), "Italian"), "italian", json_mode="known")
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
    rep = run(mod, out, Translator(FakeBackend(), "Italian"), "italian", json_mode="known")
    assert zipfile.ZipFile(out).read("c.json").decode() == other
    assert rep.translated == 0


# ------------------------------------------------------------ analisi dei campi con l'AI
QA = """{
  "pack": {"id": "q.pack", "name": "Quiz pack", "type": "dialogue"},
  "Quiz_A": {
    "event": "scene",
    "speakerRole": "villager",
    "questions": [{"id": "q1", "label": "Where were you last night?", "mood": "angry"}],
    "answers": [
      {"id": "a1", "text": "I was at the tavern all evening.", "tag": "honest_reply"},
      {"id": "a2", "text": "None of your business, friend.", "tag": "rude_reply"}
    ]
  },
  "Quiz_B": {
    "event": "scene",
    "speakerRole": "guard",
    "questions": [{"id": "q2", "label": "Who sent you here, traveler?", "mood": "calm"}]
  }
}
"""


class ClassifyingBackend(FakeBackend):
    """Traduce come FakeBackend; alla richiesta di classificare i campi risponde secondo una regola fissa."""
    def __init__(self, yes, mode="ok"):
        super().__init__(mode)
        self.yes, self.asked = set(yes), []

    def __call__(self, system, user):
        items = json.loads(user)
        if items and "path" in items[0]:
            self.calls += 1
            self.asked.append(items)
            return json.dumps([{"id": it["id"], "translate": it["path"] in self.yes, "why": "test"} for it in items])
        return super().__call__(system, user)


def _qa(tmp_path, backend, **kw):
    mod = _mod(tmp_path, QA, "Packs/Q/Dialogue/Quiz.json")
    out = tmp_path / "o.zip"
    rep = run(mod, out, Translator(backend, "Italian"), "italian", **kw)
    return rep, json.loads(zipfile.ZipFile(out).read("Packs/Q/Dialogue/Quiz.json").decode())


def test_ai_chooses_fields_and_codes_stay(tmp_path):
    be = ClassifyingBackend({"questions[].label", "answers[].text"})
    rep, d = _qa(tmp_path, be)
    assert d["Quiz_A"]["questions"][0]["label"] == "IT Where were you last night?"
    assert d["Quiz_B"]["questions"][0]["label"] == "IT Who sent you here, traveler?"
    assert d["Quiz_A"]["answers"][1]["text"] == "IT None of your business, friend."
    a = json.loads(QA)                       # codici, id, tag e umore: intatti
    for sec in ("Quiz_A", "Quiz_B"):
        assert d[sec]["speakerRole"] == a[sec]["speakerRole"] and d[sec]["event"] == a[sec]["event"]
    assert d["Quiz_A"]["questions"][0]["mood"] == "angry" and d["Quiz_A"]["answers"][0]["tag"] == "honest_reply"
    assert d["pack"] == a["pack"]
    assert rep.translated == 4 and not rep.failures
    assert len(be.asked) == 1                # una sola richiesta per tutti i file, non una per campo
    seen = {f["path"]: f for f in rep.json_fields}
    assert seen["questions[].label"]["translate"] and seen["questions[].label"]["by"] == "AI"
    assert "answers[].tag" not in seen                      # 'honest_reply' è un codice: scartato prima ancora di chiedere
    assert not seen["questions[].mood"]["translate"] and seen["questions[].mood"]["by"] == "AI"
    assert any(w.startswith("Info: campi JSON tradotti") for w in rep.warnings)


def test_ai_saying_no_means_untouched(tmp_path):
    rep, d = _qa(tmp_path, ClassifyingBackend(set()))
    a = json.loads(QA)
    assert d == a and rep.translated == 0


def test_without_ai_answer_falls_back_to_field_names(tmp_path):
    rep, d = _qa(tmp_path, FakeBackend())      # FakeBackend non sa classificare: risponde in modo inutilizzabile
    assert d["Quiz_A"]["questions"][0]["label"].startswith("IT ")      # nome tipico + frasi
    assert d["Quiz_A"]["answers"][0]["text"].startswith("IT ")
    assert d["Quiz_A"]["speakerRole"] == "villager" and d["Quiz_A"]["answers"][0]["tag"] == "honest_reply"
    assert any("ripiego" in w for w in rep.warnings)


def test_include_and_exclude_override_ai(tmp_path):
    be = ClassifyingBackend({"questions[].label", "answers[].text"})
    rep, d = _qa(tmp_path, be, json_include=["questions[].mood"], json_exclude=["answers[].*"])
    assert d["Quiz_A"]["questions"][0]["mood"] == "IT angry"
    assert d["Quiz_A"]["answers"][0]["text"] == "I was at the tavern all evening."
    assert all(not any(i["path"].startswith("answers") for i in batch) for batch in be.asked)


def test_known_mode_never_asks_ai(tmp_path):
    be = ClassifyingBackend({"questions[].label"})
    rep, d = _qa(tmp_path, be, json_mode="known")
    assert d == json.loads(QA) and not be.asked


def test_local_filter_drops_obvious_codes():
    for v in (">=0", "ddf.va.sex1.1", "Data/Meshes/x.nif", "snake_case_id", "camelCaseId", "0.5", "  "):
        assert not jsontext.value_ok(v), v
    for v in ("Where were you?", "Yes.", "Dragonborn", "free"):
        assert jsontext.value_ok(v), v
