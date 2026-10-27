"""Protezione di tutto ciò che NON va tradotto.

Prima di mandare un testo all'AI, tag, a capo, variabili e chiavi di
traduzione vengono sostituiti da segnaposto <x0/>, <x1/>, ... Dopo la
traduzione si verifica che ogni segnaposto sia tornato esattamente una volta
e poi lo si rimette com'era. Se anche un solo segnaposto manca, la
traduzione viene scartata.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

_TOKEN_RE = re.compile(r"<\s*x\s*(\d+)\s*/\s*>")

_PROTECT_RE = re.compile(
    "|".join(
        [
            r"\r\n|\n|\r",                                  # a capo (conserva la forma originale)
            r"<[/!A-Za-z0-9][^<>]{0,300}>",                 # <Alias=Player>, <mag>, <font ...>, <br>, <img ...>
            r"\[pagebreak\]",                               # cambio pagina dei libri
            r"&(?:[A-Za-z]+|#\d+|#x[0-9A-Fa-f]+);",         # entità HTML
            r"%%|%[-+#0]*\d*(?:\.\d+)?[dfsixXuc]",          # printf
            r"\{[^{}\s]{1,40}\}",                           # {0}, {nome}
            r"\$[A-Za-z0-9_]+",                             # chiavi di traduzione $KEY
            r"\\[nrt]",                                     # \n \r \t scritti letteralmente
        ]
    ),
    re.IGNORECASE,
)

_KEY_ONLY_RE = re.compile(r"\$[A-Za-z0-9_]+")

# caratteri comuni fuori da cp1252 e un'alternativa sicura
_SUBST = {
    "‑": "-", "‐": "-", "−": "-", " ": " ", " ": " ",
    "→": "->", "←": "<-", "≈": "~", "×": "x",
}


class ProtectionError(ValueError):
    """La traduzione ha rovinato i segnaposto o il testo non è usabile."""


@dataclass
class Protected:
    lead: str = ""
    trail: str = ""
    masked: str = ""
    tokens: list[str] = field(default_factory=list)
    skip_reason: str | None = None


def protect(text: str) -> Protected:
    core = text.strip()
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    if not core:
        return Protected(skip_reason="vuota")
    if _KEY_ONLY_RE.fullmatch(core):
        return Protected(skip_reason="chiave di traduzione ($KEY)")

    tokens: list[str] = []

    def _sub(m: re.Match) -> str:
        tokens.append(m.group(0))
        return f"<x{len(tokens) - 1}/>"

    masked = _PROTECT_RE.sub(_sub, core)
    if not re.search(r"[^\W\d_]", _TOKEN_RE.sub("", masked)):
        return Protected(skip_reason="nessun testo da tradurre")
    return Protected(lead=lead, trail=trail, masked=masked, tokens=tokens)


def restore(p: Protected, translated: str) -> str:
    if not isinstance(translated, str) or not translated.strip():
        raise ProtectionError("traduzione vuota")
    found = Counter(int(n) for n in _TOKEN_RE.findall(translated))
    expected = Counter(range(len(p.tokens)))
    if found != expected:
        raise ProtectionError(
            f"segnaposto non conservati (attesi {len(p.tokens)}, trovati {sum(found.values())})"
        )
    body = _TOKEN_RE.sub(lambda m: p.tokens[int(m.group(1))], translated.strip())
    return p.lead + body + p.trail


def fit_encoding(text: str, enc: str) -> str:
    """Rende il testo scrivibile nella codifica del gioco o solleva ProtectionError."""
    try:
        text.encode(enc)
        return text
    except UnicodeEncodeError:
        pass
    fixed = unicodedata.normalize("NFC", "".join(_SUBST.get(c, c) for c in text))
    try:
        fixed.encode(enc)
        return fixed
    except UnicodeEncodeError as e:
        raise ProtectionError(f"caratteri non supportati da {enc}: {text[e.start:e.end]!r}")
