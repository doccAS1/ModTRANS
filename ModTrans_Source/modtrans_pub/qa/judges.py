import json, re

from ..core.masking import strip_tokens, token_ids
from ..core.models import Verdict
from ..engines.base import extract_json
from ..translator import preset_block

NUM = re.compile(r"\d+")


class JudgeA:
    """Accuracy: controlli deterministici (veto forte) + opzionale verifica LLM di fedeltà."""
    def __init__(self, glossary, engine=None, preset=None, target_lang="la lingua di destinazione"):
        self.glossary, self.engine, self.preset, self.target_lang = glossary, engine, preset, target_lang

    def deterministic(self, unit, tr):
        issues = []
        if not tr.strip():
            return [{"type": "empty", "detail": "traduzione vuota"}]
        if token_ids(unit.masked) != token_ids(tr):
            issues.append({"type": "placeholder",
                           "detail": f"segnaposto attesi {token_ids(unit.masked)}, trovati {token_ids(tr)}"})
        if sorted(NUM.findall(strip_tokens(unit.masked))) != sorted(NUM.findall(strip_tokens(tr))):
            issues.append({"type": "number", "detail": "numeri diversi dall'originale"})
        issues += self.glossary.check(unit.source, tr)
        if len(tr) > 2.3 * len(unit.masked) + 15:
            issues.append({"type": "length", "detail": "traduzione molto più lunga dell'originale"})
        return issues

    def evaluate(self, unit, tr):
        det = self.deterministic(unit, tr)
        if det:
            return Verdict("A", False, 0.0, det, hard=any(i["type"] in ("placeholder", "number", "empty") for i in det))
        if not self.engine:
            return Verdict("A", True, 1.0)
        system = (f"# ROLE: judge\nSei il Giudice A (ACCURATEZZA) per traduzioni di mod verso {self.target_lang}. Valuti SOLO fedeltà di significato: "
                  "omissioni, aggiunte, errori di senso, termini errati. Ignora lo stile. I ⟦N⟧ sono codici di gioco, già verificati.\n"
                  'Rispondi SOLO JSON: {"score":0-1,"ok":bool,"issues":[{"type":"meaning","detail":"...","suggestion":"..."}]}\n'
                  f"{preset_block(self.preset) if self.preset else ''}")
        r = extract_json(self.engine.chat(system, json.dumps({"key": unit.key, "source": unit.masked, "translation": tr},
                                                             ensure_ascii=False)))
        return Verdict("A", bool(r.get("ok", False)), float(r.get("score", 0)), r.get("issues", []))


class JudgeB:
    """Fluency: naturalezza, registro, coerenza col mondo di gioco (veto morbido)."""
    def __init__(self, engine, preset, target_lang="la lingua di destinazione"):
        self.engine, self.preset, self.target_lang = engine, preset, target_lang

    def evaluate(self, unit, tr):
        system = (f"# ROLE: judge\nSei il Giudice B (FLUENCY) per traduzioni di videogiochi verso {self.target_lang}. Valuti: naturalezza nella lingua di destinazione, "
                  "registro e tono adatti al gioco e a chi parla (deducilo dalla key), adattamento culturale, genere grammaticale, "
                  "lunghezza adatta a una UI. Non giudicare l'accuratezza tecnica. I ⟦N⟧ sono codici di gioco.\n"
                  'Rispondi SOLO JSON: {"score":0-1,"ok":bool,"issues":[{"type":"fluency|register|culture","detail":"...","suggestion":"..."}]}\n'
                  f"{preset_block(self.preset)}")
        r = extract_json(self.engine.chat(system, json.dumps({"key": unit.key, "source": unit.masked, "translation": tr},
                                                             ensure_ascii=False)))
        return Verdict("B", bool(r.get("ok", False)), float(r.get("score", 0)), r.get("issues", []))
