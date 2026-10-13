import json

from .core.masking import token_ids
from .engines.base import extract_json


def preset_block(preset):
    return (f"GIOCO: {preset['game']}\nAMBIENTAZIONE: {preset['setting']}\nTONO: {preset['tone']}\n"
            "REGOLE DI STILE:\n- " + "\n- ".join(preset["style_rules"]) +
            "\nPERSONAGGI:\n" + "\n".join(f"- {k}: {v}" for k, v in preset.get("characters", {}).items()))


class Translator:
    def __init__(self, engine, preset, glossary, batch_size=15, source_lang="Auto", target_lang="Italian"):
        self.engine = engine
        self.preset = preset
        self.glossary = glossary
        self.bs = batch_size
        self.source_lang = source_lang
        self.target_lang = target_lang

    def system(self):
        lang_pair = f"da {self.source_lang} a {self.target_lang}" if self.source_lang != "Auto" else f"verso {self.target_lang}"
        return ("# ROLE: translator\n"
                f"Sei un traduttore professionista di videogiochi, specializzato in mod. Devi tradurre tassativamente {lang_pair}.\n\n"
                f"{preset_block(self.preset)}\n\n"
                "REGOLE TASSATIVE:\n"
                "- I segnaposto ⟦N⟧ sono codici di gioco: copiali IDENTICI, tutti, senza duplicarli né tradurli. "
                f"Puoi spostarli solo se la sintassi della lingua di destinazione ({self.target_lang}) lo richiede.\n"
                "- Non tradurre né modificare numeri.\n"
                "- Rispetta il glossario vincolante fornito per ogni elemento.\n"
                "- La chiave (key) dà contesto su chi parla/dove appare il testo: usala, ma non tradurla.\n"
                "- Rispondi SOLO con un oggetto JSON {\"id\": \"traduzione\"} con tutti gli id ricevuti. "
                f"Tutto il testo tradotto generato deve essere ESCLUSIVAMENTE in {self.target_lang}.")

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
                print(f"  ! batch fallito ({e}); le chiavi verranno marcate BLOCK")
                continue
            for n, u in enumerate(chunk, 1):
                if isinstance(res.get(str(n)), str):
                    out[u.key] = res[str(n)]
        return out