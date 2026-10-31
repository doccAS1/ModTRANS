"""Controlli locali sulla qualità delle traduzioni (gratuiti, senza chiamare nessuna AI)."""
from __future__ import annotations

import re
from collections import Counter

# Testi dove i numeri sono dati (statistiche, quantità): se cambiano è quasi sempre un errore.
# Nei dialoghi e nei libri un "3" scritto "tre" è normale, quindi lì non si controlla.
NUM_STRICT = {"name", "description", "button", "ui_label", "message", "quest_objective", "loading_screen",
              "plugin_description"}
# Testi con poco spazio nell'interfaccia (nomi, pulsanti, voci di menu, scelte di dialogo).
UI_LIMITED = {"name", "button", "dialogue_prompt", "quest_objective", "ui_label"}

_TOK = re.compile(r"<\s*x\s*\d+\s*/\s*>")
_QUOTES_OPEN, _QUOTES_CLOSE = "\"“«„", "\"”»“"
PREAMBLES = ("here is", "here's", "here are", "translation:", "translated text", "sure,", "sure!", "certainly",
             "of course", "ecco la traduzione", "ecco il testo", "ecco la versione", "traduzione:", "```")


def numbers(masked: str) -> Counter:
    """Le sequenze di cifre (senza i segnaposto): '1,000' e '1.000' danno lo stesso risultato."""
    text = _TOK.sub(" ", masked)
    text = re.sub(r"(?<=\d)[.,\u00a0](?=\d{3}(?!\d))", "", text)       # 1.000 / 1,000 / 1 000 = 1000
    return Counter(re.findall(r"\d+", text))


def hard_check(base_kind: str, src_masked: str, out_masked: str) -> str | None:
    """Problemi che rendono inutilizzabile la traduzione: il motivo, oppure None se va bene."""
    s, o = src_masked.strip(), out_masked.strip()
    low = o.lower()
    if any(low.startswith(p) for p in PREAMBLES) and not s.lower().startswith(PREAMBLES):
        return "il modello ha aggiunto una premessa al testo"
    if len(o) >= 2 and o[0] in _QUOTES_OPEN and o[-1] in _QUOTES_CLOSE and not (s[:1] and s[0] in _QUOTES_OPEN):
        return "il modello ha messo il testo tra virgolette"
    if base_kind in NUM_STRICT:
        a, b = numbers(s), numbers(o)
        if a != b:
            return f"numeri cambiati ({', '.join(sorted(a - b)) or '-'} → {', '.join(sorted(b - a)) or '-'})"
    return None


def max_chars(src: str) -> int:
    return int(max(1.5 * len(src), len(src) + 10))


def too_long(base_kind: str, src: str, out: str) -> bool:
    return base_kind in UI_LIMITED and len(out) > max(1.6 * len(src), len(src) + 12)


def looks_untranslated(base_kind: str, src: str, out: str) -> bool:
    """Uguale all'originale e fatta di più parole: probabilmente il modello l'ha lasciata in inglese."""
    return base_kind != "name" and out.strip() == src.strip() and len(src.split()) >= 3
