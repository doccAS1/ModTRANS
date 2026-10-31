import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skyrimtrans import checks  # noqa: E402
from skyrimtrans.protect import protect, remask, restore  # noqa: E402
from skyrimtrans.translator import TranslationStore, Translator  # noqa: E402


class Script:
    """Backend finto: risponde in base al tipo di richiesta (traduzione, accorciamento, revisione)."""

    def __init__(self, translate=None, shorten=None, review=None):
        self.translate, self.shorten, self.review = translate or (lambda t: "IT " + t), shorten, review
        self.log = []

    def __call__(self, system, user):
        items = json.loads(user)
        if system.startswith("You shorten"):
            kind = "shorten"
            out = [{"id": i["id"], "text": self.shorten(i)} for i in items]
        elif system.startswith("You review"):
            kind = "review"
            out = [dict({"id": i["id"]}, **self.review(i)) for i in items]
        else:
            kind = "translate"
            out = [{"id": i["id"], "text": self.translate(i["text"])} for i in items]
        self.log.append(kind)
        return json.dumps(out)


# ------------------------------------------------------------ controlli locali
def test_numbers_are_compared_ignoring_thousand_separators_and_markers():
    assert checks.hard_check("description", "Deals 10 damage for 1,000 s", "Infligge 10 danni per 1.000 s") is None
    assert checks.hard_check("description", "Deals <x0/>10 damage", "Infligge <x0/>10 danni") is None
    assert "numeri" in checks.hard_check("description", "Deals 10 damage", "Infligge 100 danni")
    assert "numeri" in checks.hard_check("name", "Elixir 5", "Elisir")
    # nei dialoghi i numeri possono diventare parole: non si controllano
    assert checks.hard_check("dialogue_response", "I saw 3 dragons", "Ho visto tre draghi") is None


def test_assistant_artifacts_are_caught():
    assert checks.hard_check("name", "Iron Sword", "Here is the translation: Spada di ferro")
    assert checks.hard_check("name", "Iron Sword", "```Spada di ferro```")
    assert checks.hard_check("dialogue_prompt", "Tell me more", "«Dimmi di più»")
    assert checks.hard_check("dialogue_prompt", "Tell me more", "Dimmi di più") is None
    # se l'originale stesso è tra virgolette, tenerle è giusto
    assert checks.hard_check("dialogue_response", "\"Hello\"", "\"Ciao\"") is None


def test_length_and_untranslated_heuristics():
    assert checks.too_long("button", "Cancel", "Annullare l'operazione corrente")
    assert not checks.too_long("button", "Cancel", "Annulla")
    assert not checks.too_long("book_text", "Short", "Una frase molto molto più lunga dell'originale")
    assert checks.looks_untranslated("description", "Restores your health slowly", "Restores your health slowly")
    assert not checks.looks_untranslated("name", "Dragon Priest Mask", "Dragon Priest Mask")
    assert not checks.looks_untranslated("button", "OK", "OK")


def test_remask_numbers_markers_like_the_source():
    p = protect("Hello\nworld <Alias=Player> and\nmore")
    out = restore(p, "Ciao<x0/>mondo <x1/> e<x2/>altro")
    assert remask(p, out) == "Ciao<x0/>mondo <x1/> e<x2/>altro"
    assert remask(p, "Ciao mondo senza segnaposto") is None             # ne mancano
    assert remask(p, "  " + out + "  ") == "Ciao<x0/>mondo <x1/> e<x2/>altro"      # spazi ai bordi ignorati
    assert remask(p, out + " $EXTRA") is None                            # uno in più


# ------------------------------------------------------------ dentro il traduttore
def test_changed_numbers_are_retried_then_original_is_kept():
    be = Script(translate=lambda t: t.replace("10", "100").replace("Deals", "Infligge"))
    tr = Translator(be, "Italian", retries=1)
    out = tr.translate_all([("description:ALCH", "Deals 10 damage")])
    assert out == {} and "numeri" in tr.failed[("description:ALCH", "Deals 10 damage")]
    assert be.log.count("translate") == 2                                # primo tentativo + un ritento


def test_number_error_in_one_item_does_not_spoil_the_others():
    def tr_fn(t):
        return "Spada 99" if t == "Sword 5" else "IT " + t
    tr = Translator(Script(translate=tr_fn), "Italian", retries=0)
    out = tr.translate_all([("name:WEAP", "Sword 5"), ("name:WEAP", "Axe")])
    assert list(out.values()) == ["IT Axe"]


def test_long_ui_texts_are_shortened_and_the_short_version_is_remembered(tmp_path):
    long_out = "Annulla l'operazione corrente subito"
    be = Script(translate=lambda t: long_out, shorten=lambda i: "Annulla")
    st = TranslationStore(tmp_path / "m.jsonl")
    tr = Translator(be, "Italian", store=st)
    out = tr.translate_all([("button:MESG", "Cancel")])
    assert out == {("button:MESG", "Cancel"): "Annulla"} and tr.stats["shortened"] == 1
    assert be.log == ["translate", "shorten"]
    # la memoria su disco ha la versione corta (l'ultima riga vince)
    assert TranslationStore(tmp_path / "m.jsonl").load() == {("button:MESG", "Cancel"): "Annulla"}


def test_shorten_that_breaks_markers_or_is_not_shorter_is_ignored_with_a_warning():
    bad_outputs = iter(["Annulla l'operazione corrente subito", "Annulla <x0/>"])
    be = Script(translate=lambda t: "Annulla l'operazione corrente subito", shorten=lambda i: next(bad_outputs))
    tr = Translator(be, "Italian")
    out = tr.translate_all([("button:MESG", "Cancel"), ("button:MESG", "Close")])
    assert set(out.values()) == {"Annulla l'operazione corrente subito"} and tr.stats["shortened"] == 0
    assert sum("più lunga" in w for w in tr.warnings) == 2


def test_shorten_can_be_disabled():
    be = Script(translate=lambda t: "Annulla l'operazione corrente subito")
    tr = Translator(be, "Italian", shorten=False)
    tr.translate_all([("button:MESG", "Cancel")])
    assert be.log == ["translate"] and tr.stats["shortened"] == 0


def test_shorten_failure_is_not_fatal():
    class Boom(Script):
        def __call__(self, system, user):
            if system.startswith("You shorten"):
                return "non è json"
            return super().__call__(system, user)
    tr = Translator(Boom(translate=lambda t: "Annulla l'operazione corrente subito"), "Italian")
    out = tr.translate_all([("button:MESG", "Cancel")])
    assert out == {("button:MESG", "Cancel"): "Annulla l'operazione corrente subito"}
    assert any("rifinitura saltato" in w for w in tr.warnings)


def test_untranslated_multiword_text_is_warned_not_dropped():
    tr = Translator(Script(translate=lambda t: t), "Italian")
    out = tr.translate_all([("description:ALCH", "Restores your health slowly")])
    assert len(out) == 1 and any("inglese" in w for w in tr.warnings)


def test_review_applies_valid_fixes_and_rejects_bad_ones():
    def review(i):
        if i["original"] == "Bad one":
            return {"ok": False, "fix": "Corretta <x9/>"}                  # segnaposto inventato: scartata
        if i["original"] == "Wrong one":
            return {"ok": False, "fix": "Giusta"}
        return {"ok": True}
    be = Script(translate=lambda t: "Sbagliata", review=review)
    tr = Translator(be, "Italian", review=True)
    out = tr.translate_all([("description:ALCH", "Wrong one"), ("description:ALCH", "Bad one"), ("description:ALCH", "Fine one")])
    assert out[("description:ALCH", "Wrong one")] == "Giusta"
    assert out[("description:ALCH", "Bad one")] == "Sbagliata" and out[("description:ALCH", "Fine one")] == "Sbagliata"
    assert tr.stats["qa_checked"] == 3 and tr.stats["qa_fixed"] == 1
    assert any("scartata" in w for w in tr.warnings)


def test_review_sees_markers_and_is_off_by_default():
    seen = []
    def review(i):
        seen.append(i["translation"])
        return {"ok": True}
    be = Script(translate=lambda t: t.replace("Hello", "Ciao"), review=review)
    Translator(be, "Italian", review=True).translate_all([("description:ALCH", "Hello\nthere world")])
    assert seen == ["Ciao<x0/>there world"]
    be2 = Script()
    Translator(be2, "Italian").translate_all([("description:ALCH", "Some text here")])
    assert be2.log == ["translate"]


def test_items_from_memory_are_not_rechecked(tmp_path):
    st = TranslationStore(tmp_path / "m.jsonl")
    Translator(Script(), "Italian", store=st).translate_all([("description:ALCH", "Some text here")])
    be = Script()
    tr = Translator(be, "Italian", store=TranslationStore(tmp_path / "m.jsonl"), review=True)
    tr.translate_all([("description:ALCH", "Some text here")])
    assert be.log == [] and tr.stats["qa_checked"] == 0


def test_shorten_request_carries_the_limit():
    asked = []
    def shorten(i):
        asked.append(i["max_chars"])
        return "Annulla"
    Translator(Script(translate=lambda t: "Annulla l'operazione corrente subito", shorten=shorten), "Italian") \
        .translate_all([("button:MESG", "Cancel")])
    assert asked == [16] and checks.max_chars("Cancel") == 16 and checks.max_chars("x" * 100) == 150
