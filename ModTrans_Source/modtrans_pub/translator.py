import json

from .core.masking import token_ids
from .engines.base import extract_json


def preset_block(preset):
    return (f"GAME: {preset['game']}\nSETTING: {preset['setting']}\nTONE: {preset['tone']}\n"
            "STYLE RULES:\n- " + "\n- ".join(preset["style_rules"]) +
            "\nCHARACTERS:\n" + "\n".join(f"- {k}: {v}" for k, v in preset.get("characters", {}).items()))


class Translator:
    def __init__(self, engine, preset, glossary, batch_size=15, source_lang="Auto", target_lang="Italian"):
        self.engine = engine
        self.preset = preset
        self.glossary = glossary
        self.bs = batch_size
        self.source_lang = source_lang
        self.target_lang = target_lang

    def system(self):
        lang_pair = f"from {self.source_lang} to {self.target_lang}" if self.source_lang != "Auto" else f"into {self.target_lang}"
        return ("# ROLE: translator\n"
                f"You are a professional video game translator specialised in mods. You must translate {lang_pair}.\n\n"
                f"{preset_block(self.preset)}\n\n"
                "STRICT RULES:\n"
                "- The ⟦N⟧ placeholders are game codes: copy ALL of them IDENTICALLY, without duplicating or translating them. "
                f"You may move them only if the grammar of the target language ({self.target_lang}) requires it.\n"
                "- Do not translate or change numbers.\n"
                "- Follow the binding glossary provided for each item.\n"
                "- The key gives context on who speaks / where the text appears: use it, but do not translate it.\n"
                "- Reply with a JSON object ONLY, {\"id\": \"translation\"}, with every id received. "
                f"All translated text must be EXCLUSIVELY in {self.target_lang}.")

    def translate(self, units):
        """units con .masked già valorizzato -> {key: testo_mascherato_tradotto}"""
        out = {}
        for i in range(0, len(units), self.bs):
            chunk = units[i:i + self.bs]
            items = {str(n): {"key": u.key, "text": u.masked,
                              "glossary": self.glossary.relevant(u.source)}
                     for n, u in enumerate(chunk, 1)}
            try:
                res = extract_json(self.engine.chat(self.system(), json.dumps({"items": items}, ensure_ascii=False)))
            except Exception as e:
                print(f"  ! batch failed ({e}); its keys will be marked BLOCK")
                continue
            for n, u in enumerate(chunk, 1):
                if isinstance(res.get(str(n)), str):
                    out[u.key] = res[str(n)]
        return out