"""Pacchetti di dialoghi in JSON (es. TMSDynamicDialogue/Packs/.../Dialogue/*.json).

Si traduce SOLO il campo "text" degli oggetti dentro una lista "lines" che hanno anche un "id"
(le battute). Tutto il resto (id, event, actions, relationship, ...) è logica della mod e
resta com'è. Il file non viene riscritto da zero: si sostituiscono soltanto le stringhe
"text" nel testo originale, quindi spazi, rientri e ordine delle chiavi restano identici.
"""
from __future__ import annotations

import json

from .common import Unit


class JsonError(Exception):
    pass


_WS = " \t\r\n"


def _scan(text: str):
    """Ritorna {percorso: (inizio, fine, valore)} per ogni stringa-valore del JSON."""
    out: dict[tuple, tuple[int, int, str]] = {}
    n = len(text)
    pos = 0

    def ws():
        nonlocal pos
        while pos < n and text[pos] in _WS:
            pos += 1

    def string():
        nonlocal pos
        start = pos
        pos += 1
        while pos < n:
            c = text[pos]
            if c == "\\":
                pos += 2
                continue
            if c == '"':
                pos += 1
                return start, pos
            pos += 1
        raise JsonError("stringa non chiusa")

    def value(path):
        nonlocal pos
        ws()
        if pos >= n:
            raise JsonError("fine inattesa")
        c = text[pos]
        if c == '"':
            a, b = string()
            out[path] = (a, b, json.loads(text[a:b]))
        elif c == "{":
            pos += 1
            ws()
            if text[pos:pos + 1] == "}":
                pos += 1
                return
            while True:
                ws()
                if text[pos:pos + 1] != '"':
                    raise JsonError("chiave attesa")
                a, b = string()
                key = json.loads(text[a:b])
                ws()
                if text[pos:pos + 1] != ":":
                    raise JsonError("':' atteso")
                pos += 1
                value(path + (key,))
                ws()
                c2 = text[pos:pos + 1]
                pos += 1
                if c2 == "}":
                    return
                if c2 != ",":
                    raise JsonError("',' o '}' atteso")
        elif c == "[":
            pos += 1
            ws()
            if text[pos:pos + 1] == "]":
                pos += 1
                return
            i = 0
            while True:
                value(path + (i,))
                i += 1
                ws()
                c2 = text[pos:pos + 1]
                pos += 1
                if c2 == "]":
                    return
                if c2 != ",":
                    raise JsonError("',' o ']' atteso")
        else:
            a = pos
            while pos < n and text[pos] not in _WS + ",]}":
                pos += 1
            if a == pos:
                raise JsonError("valore atteso")

    value(())
    ws()
    if pos != n:
        raise JsonError("testo dopo la fine del JSON")
    return out


def _is_line_text(path: tuple, found: dict) -> bool:
    """È la battuta di un oggetto di "lines" (con "id")?"""
    return (len(path) >= 3 and path[-1] == "text" and isinstance(path[-2], int) and path[-3] == "lines"
            and (path[:-1] + ("id",)) in found)


def parse(text: str):
    """(stringhe, percorsi delle battute) oppure JsonError."""
    found = _scan(text)
    paths = [p for p in found if _is_line_text(p, found)]
    return found, paths


def extract_units(parsed, file: str) -> list[Unit]:
    found, paths = parsed
    return [Unit(file, p, "json_dialogue", found[p][2]) for p in paths if found[p][2].strip()]


def apply_units(text: str, parsed, changes: dict) -> str:
    found, _ = parsed
    spans = sorted(((found[p][0], found[p][1], new) for p, new in changes.items()), reverse=True)
    for a, b, new in spans:
        text = text[:a] + json.dumps(new, ensure_ascii=False) + text[b:]
    return text


def verify(orig: str, new: str, parsed) -> list[str]:
    """Stessa struttura e stessi valori, tranne le battute traducibili."""
    _, paths = parsed
    allowed = set(paths)
    try:
        a, b = json.loads(orig), json.loads(new)
    except ValueError as e:
        return [f"JSON non valido dopo la traduzione ({e})"]
    problems: list[str] = []

    def walk(x, y, path):
        if len(problems) >= 5:
            return
        if path in allowed:
            if not (isinstance(x, str) and isinstance(y, str)):
                problems.append(f"{'/'.join(map(str, path))}: tipo cambiato")
            return
        if type(x) is not type(y):
            problems.append(f"{'/'.join(map(str, path))}: tipo cambiato")
        elif isinstance(x, dict):
            if list(x) != list(y):
                problems.append(f"{'/'.join(map(str, path))}: chiavi cambiate")
                return
            for k in x:
                walk(x[k], y[k], path + (k,))
        elif isinstance(x, list):
            if len(x) != len(y):
                problems.append(f"{'/'.join(map(str, path))}: lunghezza cambiata")
                return
            for i, (p, q) in enumerate(zip(x, y)):
                walk(p, q, path + (i,))
        elif x != y:
            problems.append(f"{'/'.join(map(str, path))}: valore cambiato")

    walk(a, b, ())
    return problems
