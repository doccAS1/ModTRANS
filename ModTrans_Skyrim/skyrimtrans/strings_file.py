"""File .STRINGS / .DLSTRINGS / .ILSTRINGS delle mod localizzate.

Formato: [count u32][dataSize u32][count x (id u32, offset u32)][dati].
STRINGS = zstring; DLSTRINGS/ILSTRINGS = [len u32][zstring].
Gli id e l'ordine restano identici, cambia solo il contenuto delle stringhe.
"""
from __future__ import annotations

import struct

from .common import Unit, decode_zstring

LENGTH_PREFIXED = {".dlstrings", ".ilstrings"}


class StringsError(Exception):
    pass


class StringsFile:
    def __init__(self, buf: bytes, ext: str):
        self.prefixed = ext.lower() in LENGTH_PREFIXED
        if len(buf) < 8:
            raise StringsError("file troppo corto")
        count, dsize = struct.unpack_from("<II", buf, 0)
        dstart = 8 + count * 8
        if dstart + dsize > len(buf) or dstart > len(buf):
            raise StringsError("header incoerente")
        self.entries = [struct.unpack_from("<II", buf, 8 + i * 8) for i in range(count)]
        self.data = buf[dstart:dstart + dsize]
        self.raw: dict[int, bytes] = {}
        for _, off in self.entries:
            if off in self.raw:
                continue
            if self.prefixed:
                if off + 4 > len(self.data):
                    raise StringsError("offset fuori dai dati")
                ln = struct.unpack_from("<I", self.data, off)[0]
                chunk = self.data[off + 4:off + 4 + ln]
                if len(chunk) != ln:
                    raise StringsError("stringa troncata")
            else:
                end = self.data.find(b"\x00", off)
                if end < 0:
                    raise StringsError("stringa non terminata")
                chunk = self.data[off:end + 1]
            self.raw[off] = chunk
        if self.to_bytes(self.raw) != buf[:dstart + dsize] and not self._shared_layout_ok(buf):
            pass  # layout non canonico: si riscrive comunque in modo valido

    def _shared_layout_ok(self, buf):  # pragma: no cover
        return False

    def to_bytes(self, raw: dict[int, bytes]) -> bytes:
        out = bytearray()
        new_off: dict[int, int] = {}
        for _, off in self.entries:
            if off in new_off:
                continue
            new_off[off] = len(out)
            chunk = raw[off]
            out += (struct.pack("<I", len(chunk)) + chunk) if self.prefixed else chunk
        head = struct.pack("<II", len(self.entries), len(out))
        for sid, off in self.entries:
            head += struct.pack("<II", sid, new_off[off])
        return head + bytes(out)


def extract_units(sf: StringsFile, enc: str, file: str, kind_hint: str) -> tuple[list[Unit], list[str]]:
    units, warns = [], []
    kind = {"dlstrings": "description", "ilstrings": "dialogue"}.get(kind_hint, "name")
    for off, chunk in sf.raw.items():
        s = decode_zstring(chunk if chunk.endswith(b"\x00") else chunk + b"\x00", enc)
        if s is None:
            warns.append(f"{file}: stringa a offset {off} non valida, saltata")
            continue
        if s:
            units.append(Unit(file, off, kind, s))
    return units, warns


def apply_units(sf: StringsFile, changes: dict, enc: str) -> bytes:
    raw = dict(sf.raw)
    for off, text in changes.items():
        raw[off] = text.encode(enc) + b"\x00"
    return sf.to_bytes(raw)


def verify_strings(orig: bytes, new: bytes, ext: str, enc: str) -> list[str]:
    try:
        a, b = StringsFile(orig, ext), StringsFile(new, ext)
    except StringsError as e:
        return [f"file strings non valido: {e}"]
    if [i for i, _ in a.entries] != [i for i, _ in b.entries]:
        return ["elenco ID modificato"]
    sa = {sid: a.raw[o] for sid, o in a.entries}
    sb = {sid: b.raw[o] for sid, o in b.entries}
    bad = [f"ID {sid}: stringa non valida" for sid, v in sb.items()
           if v != sa[sid] and decode_zstring(v if v.endswith(b"\x00") else v + b"\x00", enc) is None]
    return bad
