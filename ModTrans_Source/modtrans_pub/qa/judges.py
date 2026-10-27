import json, re
from collections import Counter

from ..core.masking import mask, strip_tokens, token_ids
from ..core.models import Verdict
from ..engines.base import extract_json
from ..translator import preset_block

NUM = re.compile(r"\d+")
# separatore delle migliaia (1,000 / 1.000 / 1 000 con spazio non separabile) -> 1000
THOUSANDS = re.compile(r"(?<=\d)[,.\u00a0\u202f](?=\d{3}(?!\d))")
# numeri scritti a lettere nell'originale: la traduzione può legittimamente usare le cifre
SPELLED = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
           "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
           "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
           "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
           "thousand": 1000, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
           "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}
SPELLED_RX = re.compile(r"\b(" + "|".join(sorted(SPELLED, key=len, reverse=True)) + r")\b", re.I)


def numbers(text):
    return Counter(NUM.findall(THOUSANDS.sub("", strip_tokens(text))))


class JudgeA:
    """Accuracy: controlli deterministici (veto forte) + opzionale verifica LLM di fedeltà."""
    def __init__(self, glossary, engine=None, preset=None, target_lang="the target language"):
        self.glossary, self.engine, self.preset, self.target_lang = glossary, engine, preset, target_lang

    def deterministic(self, unit, tr):
        issues = []
        if not tr.strip():
            return [{"type": "empty", "detail": "empty translation"}]
        if token_ids(unit.masked) != token_ids(tr):
            issues.append({"type": "placeholder",
                           "detail": f"expected placeholders {token_ids(unit.masked)}, found {token_ids(tr)}"})
        src_n, tr_n = numbers(unit.masked), numbers(tr)
        spelled = Counter(str(SPELLED[w.lower()]) for w in SPELLED_RX.findall(strip_tokens(unit.masked)))
        invented = tr_n - src_n - spelled      # cifre nella traduzione che l'originale non spiega: numero cambiato
        missing = src_n - tr_n                 # cifre dell'originale assenti: spesso scritte a lettere (1st -> primo)
        if invented:
            issues.append({"type": "number",
                           "detail": f"numbers that are not in the original: {sorted(invented.elements())}"})
        elif missing:
            issues.append({"type": "number_missing",
                           "detail": f"numbers from the original missing in the translation: {sorted(missing.elements())}; "
                                     "keep the digits as in the original"})
        # Nella sorgente i codici di gioco sono stati mascherati: nella traduzione non devono
        # ricomparirne di "grezzi" (un testo ostile può spingere l'LLM a inserirne di nuovi).
        stray = mask(strip_tokens(tr))[1]
        if stray:
            issues.append({"type": "injected_code",
                           "detail": f"game codes that are not in the original: {stray[:5]}"})
        issues += self.glossary.check(unit.source, tr)
        if len(tr) > 2.3 * len(unit.masked) + 15:
            issues.append({"type": "length", "detail": "translation much longer than the original"})
        return issues

    def evaluate(self, unit, tr):
        det = self.deterministic(unit, tr)
        if det:
            return Verdict("A", False, 0.0, det, hard=any(i["type"] in ("placeholder", "number", "empty", "injected_code") for i in det))
        if not self.engine:
            return Verdict("A", True, 1.0)
        system = (f"# ROLE: judge\nYou are Judge A (ACCURACY) for mod translations into {self.target_lang}. Judge ONLY fidelity of meaning: "
                  "omissions, additions, mistranslations, wrong terms. Ignore style. The ⟦N⟧ are game codes, already verified.\n"
                  'Reply with JSON ONLY: {"score":0-1,"ok":bool,"issues":[{"type":"meaning","detail":"...","suggestion":"..."}]}\n'
                  f"{preset_block(self.preset) if self.preset else ''}")
        r = extract_json(self.engine.chat(system, json.dumps({"key": unit.key, "source": unit.masked, "translation": tr},
                                                             ensure_ascii=False)))
        return Verdict("A", bool(r.get("ok", False)), float(r.get("score", 0)), r.get("issues", []))


class JudgeB:
    """Fluency: naturalezza, registro, coerenza col mondo di gioco (veto morbido)."""
    def __init__(self, engine, preset, target_lang="the target language"):
        self.engine, self.preset, self.target_lang = engine, preset, target_lang

    def evaluate(self, unit, tr):
        system = (f"# ROLE: judge\nYou are Judge B (FLUENCY) for video game translations into {self.target_lang}. Judge: naturalness in the target language, "
                  "register and tone suited to the game and the speaker (infer it from the key), cultural adaptation, grammatical gender, "
                  "length suited to a UI. Do not judge technical accuracy. The ⟦N⟧ are game codes.\n"
                  'Reply with JSON ONLY: {"score":0-1,"ok":bool,"issues":[{"type":"fluency|register|culture","detail":"...","suggestion":"..."}]}\n'
                  f"{preset_block(self.preset)}")
        r = extract_json(self.engine.chat(system, json.dumps({"key": unit.key, "source": unit.masked, "translation": tr},
                                                             ensure_ascii=False)))
        return Verdict("B", bool(r.get("ok", False)), float(r.get("score", 0)), r.get("issues", []))
