import difflib, json

from ..engines.base import extract_json
from ..translator import preset_block


class RepairAgent:
    """Propone una patch minima; se la modifica è troppo invasiva viene scartata."""
    MIN_SIMILARITY = 0.5

    def __init__(self, engine, preset):
        self.engine, self.preset = engine, preset

    def repair(self, unit, tr, issues):
        system = ("# ROLE: repair\nCorreggi la traduzione EN->IT risolvendo SOLO i problemi elencati, con la modifica più piccola possibile. "
                  "Conserva tutti i segnaposto ⟦N⟧ esattamente una volta ciascuno.\n"
                  f'Rispondi SOLO JSON: {{"text":"traduzione corretta"}}\n{preset_block(self.preset)}')
        r = extract_json(self.engine.chat(system, json.dumps(
            {"key": unit.key, "source": unit.masked, "translation": tr, "issues": issues}, ensure_ascii=False)))
        new = r.get("text", "")
        if difflib.SequenceMatcher(None, tr, new).ratio() < self.MIN_SIMILARITY and tr.strip():
            return tr  # patch troppo invasiva: scartata (conta come tentativo)
        return new
