"""Lettura/scrittura dei plugin Skyrim (.esp/.esm/.esl), LE e SE.

Il file viene letto come albero (GRUP e record). I record non toccati
restano byte per byte identici; di quelli modificati si ricalcolano solo le
dimensioni (sottorecord, record, gruppi) e, se erano compressi, si
ricomprimono.
"""
from __future__ import annotations

import struct
import zlib

from .common import Unit, decode_zstring
from .tables import TABLE, TABLE_RTYPES

HEADER_SIZE = 24
FLAG_LOCALIZED = 0x00000080
FLAG_COMPRESSED = 0x00040000


class PluginError(Exception):
    pass


# --------------------------------------------------------------- sottorecord
def parse_subrecords(raw: bytes) -> list[list]:
    subs: list[list] = []
    pos, n, big = 0, len(raw), None
    while pos < n:
        if pos + 6 > n:
            raise PluginError("sottorecord troncato")
        stype = raw[pos:pos + 4]
        size = struct.unpack_from("<H", raw, pos + 4)[0]
        pos += 6
        if stype == b"XXXX":
            if size != 4 or pos + 4 > n:
                raise PluginError("XXXX malformato")
            big = struct.unpack_from("<I", raw, pos)[0]
            pos += 4
            continue
        if big is not None:
            size, big = big, None
        if pos + size > n:
            raise PluginError("sottorecord oltre i limiti")
        subs.append([stype.decode("latin-1"), raw[pos:pos + size]])
        pos += size
    return subs


def build_subrecords(subs: list[list]) -> bytes:
    out = bytearray()
    for stype, data in subs:
        t = stype.encode("latin-1")
        if len(data) > 0xFFFF:
            out += b"XXXX" + struct.pack("<HI", 4, len(data)) + t + struct.pack("<H", 0)
        else:
            out += t + struct.pack("<H", len(data))
        out += data
    return bytes(out)


# ------------------------------------------------------------------- albero
class Record:
    __slots__ = ("header", "data", "_subs")

    def __init__(self, header: bytes, data: bytes):
        self.header = header
        self.data = data
        self._subs: list[list] | None = None

    @property
    def rtype(self) -> str:
        return self.header[:4].decode("latin-1")

    @property
    def flags(self) -> int:
        return struct.unpack_from("<I", self.header, 8)[0]

    @property
    def formid(self) -> int:
        return struct.unpack_from("<I", self.header, 12)[0]

    def raw(self) -> bytes:
        if not self.flags & FLAG_COMPRESSED:
            return self.data
        if len(self.data) < 4:
            raise PluginError("record compresso troncato")
        size = struct.unpack_from("<I", self.data, 0)[0]
        try:
            raw = zlib.decompress(self.data[4:])
        except zlib.error as e:
            raise PluginError(f"zlib: {e}")
        if len(raw) != size:
            raise PluginError("dimensione decompressa incoerente")
        return raw

    def subs(self) -> list[list]:
        if self._subs is None:
            self._subs = parse_subrecords(self.raw())
        return self._subs

    def commit(self) -> None:
        raw = build_subrecords(self.subs())
        if self.flags & FLAG_COMPRESSED:
            self.data = struct.pack("<I", len(raw)) + zlib.compress(raw, 9)
        else:
            self.data = raw

    def to_bytes(self) -> bytes:
        hdr = bytearray(self.header)
        struct.pack_into("<I", hdr, 4, len(self.data))
        return bytes(hdr) + self.data


class Group:
    __slots__ = ("header", "children")

    def __init__(self, header: bytes, children: list):
        self.header = header
        self.children = children

    def to_bytes(self) -> bytes:
        body = b"".join(c.to_bytes() for c in self.children)
        hdr = bytearray(self.header)
        struct.pack_into("<I", hdr, 4, HEADER_SIZE + len(body))
        return bytes(hdr) + body


def _parse(buf: bytes, pos: int, end: int) -> list:
    nodes: list = []
    while pos < end:
        if pos + HEADER_SIZE > end:
            raise PluginError("header troncato")
        hdr = buf[pos:pos + HEADER_SIZE]
        size = struct.unpack_from("<I", hdr, 4)[0]
        if hdr[:4] == b"GRUP":
            if size < HEADER_SIZE or pos + size > end:
                raise PluginError("gruppo oltre i limiti")
            nodes.append(Group(hdr, _parse(buf, pos + HEADER_SIZE, pos + size)))
            pos += size
        else:
            if pos + HEADER_SIZE + size > end:
                raise PluginError("record oltre i limiti")
            nodes.append(Record(hdr, buf[pos + HEADER_SIZE:pos + HEADER_SIZE + size]))
            pos += HEADER_SIZE + size
    return nodes


def _iter_records(nodes):
    for n in nodes:
        if isinstance(n, Group):
            yield from _iter_records(n.children)
        else:
            yield n


class Plugin:
    def __init__(self, buf: bytes):
        self.nodes = _parse(buf, 0, len(buf))
        self.records: list[Record] = list(_iter_records(self.nodes))
        if not self.records or self.records[0].rtype != "TES4":
            raise PluginError("non è un plugin Skyrim valido (manca TES4)")
        if self.to_bytes() != buf:
            raise PluginError("il file non si riscrive identico: struttura non supportata")

    @property
    def localized(self) -> bool:
        return bool(self.records[0].flags & FLAG_LOCALIZED)

    def to_bytes(self) -> bytes:
        return b"".join(n.to_bytes() for n in self.nodes)


# ------------------------------------------------------- estrazione/scrittura
def extract_units(plugin: Plugin, enc: str, file: str) -> tuple[list[Unit], list[str]]:
    units: list[Unit] = []
    warns: list[str] = []
    if plugin.localized:
        warns.append("plugin localizzato: i testi sono nei file Strings/, il plugin resta invariato")
        return units, warns
    for ri, rec in enumerate(plugin.records):
        rt = rec.rtype
        if rt not in TABLE_RTYPES:
            continue
        try:
            subs = rec.subs()
            if build_subrecords(subs) != rec.raw():
                raise PluginError("sottorecord non riproducibili")
        except PluginError as e:
            warns.append(f"{rt} {rec.formid:08X}: saltato ({e})")
            continue
        for si, (st, data) in enumerate(subs):
            kind = TABLE.get((rt, st))
            if not kind or not data:
                continue
            s = decode_zstring(data, enc)
            if s is None:
                warns.append(f"{rt}.{st} {rec.formid:08X}: non è una stringa valida, saltato")
                continue
            units.append(Unit(file, (ri, si), kind, s))
    return units, warns


def apply_units(plugin: Plugin, changes: dict, enc: str) -> list[str]:
    errors: list[str] = []
    by_rec: dict[int, list] = {}
    for (ri, si), text in changes.items():
        by_rec.setdefault(ri, []).append((si, text))
    for ri, items in by_rec.items():
        rec = plugin.records[ri]
        subs = rec.subs()
        touched = False
        for si, text in items:
            try:
                b = text.encode(enc)
            except UnicodeEncodeError:
                errors.append(f"{rec.rtype} {rec.formid:08X}: caratteri non codificabili")
                continue
            if b"\x00" in b:
                errors.append(f"{rec.rtype} {rec.formid:08X}: NUL nel testo")
                continue
            subs[si][1] = b + b"\x00"
            touched = True
        if touched:
            rec.commit()
    return errors


# ------------------------------------------------------------- verifica
def verify_plugin(orig: bytes, new: bytes, enc: str) -> list[str]:
    """Confronta originale e tradotto. Lista vuota = solo le stringhe ammesse sono cambiate."""
    problems: list[str] = []
    try:
        a, b = Plugin(orig), Plugin(new)
    except PluginError as e:
        return [f"il file tradotto non è valido: {e}"]

    def walk(na, nb):
        if len(na) != len(nb):
            problems.append("numero di nodi diverso")
            return
        for x, y in zip(na, nb):
            if type(x) is not type(y):
                problems.append("tipo di nodo diverso")
                continue
            if isinstance(x, Group):
                if x.header[:4] + x.header[8:] != y.header[:4] + y.header[8:]:
                    problems.append("header di gruppo modificato")
                walk(x.children, y.children)
                continue
            if x.header[:4] != y.header[:4] or x.header[8:] != y.header[8:]:
                problems.append(f"{x.rtype} {x.formid:08X}: header modificato")
                continue
            if x.data == y.data:
                continue
            sx, sy = x.subs(), y.subs()
            if len(sx) != len(sy):
                problems.append(f"{x.rtype} {x.formid:08X}: numero di sottorecord diverso")
                continue
            for (tx, dx), (ty, dy) in zip(sx, sy):
                if tx != ty:
                    problems.append(f"{x.rtype} {x.formid:08X}: ordine sottorecord cambiato")
                elif dx != dy:
                    if (x.rtype, tx) not in TABLE:
                        problems.append(f"{x.rtype}.{tx} {x.formid:08X}: campo non testuale modificato")
                    elif decode_zstring(dy, enc) is None:
                        problems.append(f"{x.rtype}.{tx} {x.formid:08X}: stringa non valida")

    try:
        walk(a.nodes, b.nodes)
    except PluginError as e:
        problems.append(str(e))
    return problems
