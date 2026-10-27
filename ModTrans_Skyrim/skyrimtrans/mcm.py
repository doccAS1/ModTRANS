"""File di traduzione dei menu MCM (Interface/Translations/<nome>_<LINGUA>.txt).

Righe '$CHIAVE<TAB>testo', UTF-16 LE con BOM. Chiavi, tab e righe vuote
restano identiche; si traduce solo il testo dopo il primo tab.
"""
from __future__ import annotations

import re

from .common import Unit

_NAME_RE = re.compile(r"^(?P<base>.+)_(?P<lang>[A-Za-z]+)\.txt$", re.IGNORECASE)


def split_name(filename: str):
    m = _NAME_RE.match(filename)
    return (m.group("base"), m.group("lang").upper()) if m else (None, None)


def decode(buf: bytes) -> tuple[str, str, bool]:
    """Ritorna (testo, codifica, ha_bom)."""
    if buf.startswith(b"\xff\xfe"):
        return buf[2:].decode("utf-16-le"), "utf-16-le", True
    if buf.startswith(b"\xfe\xff"):
        return buf[2:].decode("utf-16-be"), "utf-16-be", True
    if buf.startswith(b"\xef\xbb\xbf"):
        return buf[3:].decode("utf-8"), "utf-8", True
    try:
        return buf.decode("utf-8"), "utf-8", False
    except UnicodeDecodeError:
        return buf.decode("cp1252"), "cp1252", False


def encode(text: str, enc: str, bom: bool) -> bytes:
    body = text.encode(enc)
    if not bom:
        return body
    return {"utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff", "utf-8": b"\xef\xbb\xbf"}.get(enc, b"") + body


def split_lines(text: str) -> list[str]:
    return re.split(r"(\r\n|\n|\r)", text)  # i separatori restano nella lista


def extract_units(text: str, file: str) -> list[Unit]:
    units = []
    parts = split_lines(text)
    for i in range(0, len(parts), 2):
        line = parts[i]
        if "\t" not in line or not line.startswith("$"):
            continue
        _, value = line.split("\t", 1)
        if value.strip():
            units.append(Unit(file, i, "ui_label", value))
    return units


def apply_units(text: str, changes: dict) -> str:
    parts = split_lines(text)
    for i, new in changes.items():
        key, _ = parts[i].split("\t", 1)
        parts[i] = key + "\t" + new
    return "".join(parts)


def verify(orig: str, new: str) -> list[str]:
    a, b = split_lines(orig), split_lines(new)
    if len(a) != len(b):
        return ["numero di righe diverso"]
    problems = []
    for i in range(0, len(a), 2):
        if a[i] == b[i]:
            continue
        ka, kb = a[i].split("\t", 1)[0], b[i].split("\t", 1)[0]
        if ka != kb or "\t" not in b[i] or "\t" in b[i].split("\t", 1)[1]:
            problems.append(f"riga {i // 2 + 1}: struttura modificata")
    for i in range(1, len(a), 2):
        if a[i] != b[i]:
            problems.append("a capo modificati")
            break
    return problems
