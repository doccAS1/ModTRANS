from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Unit:
    """Una stringa traducibile trovata in un file."""

    file: str          # percorso relativo del file
    locator: Any       # dove si trova dentro il file (serve per riscriverla)
    kind: str          # tipo di testo (name, dialogue, book_text, ...)
    text: str


def decode_zstring(data: bytes, enc: str) -> str | None:
    """Decodifica una zstring (terminata da un solo NUL). None se non è una stringa valida.

    Più severa del necessario di proposito: se un campo non sembra testo,
    non lo si tocca.
    """
    if not data.endswith(b"\x00"):
        return None
    body = data[:-1]
    if b"\x00" in body:
        return None
    try:
        s = body.decode(enc)
    except UnicodeDecodeError:
        return None
    if any(ord(c) < 32 and c not in "\t\r\n" for c in s):
        return None
    return s
