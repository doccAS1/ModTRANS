"""Lettura (solo lettura) degli archivi .bsa di Skyrim: v104 (Legendary Edition, zlib) e v105 (Special Edition, LZ4).

Serve per le mod localizzate che tengono i file Strings/ dentro il proprio .bsa: li leggiamo da lì e scriviamo le
traduzioni come file sciolti (in Skyrim i file sciolti hanno la precedenza sull'archivio), senza mai modificare
né ricreare il .bsa originale.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


class BsaError(Exception):
    pass


# ---------------------------------------------------------------- LZ4 (Skyrim SE)
def _lz4_block(src: bytes, out: bytearray) -> None:
    """Decomprime un blocco LZ4 aggiungendolo a `out` (che fa anche da storia per i blocchi collegati)."""
    i, n = 0, len(src)
    try:
        while i < n:
            token = src[i]
            i += 1
            lit = token >> 4
            if lit == 15:
                while True:
                    b = src[i]
                    i += 1
                    lit += b
                    if b != 255:
                        break
            out += src[i:i + lit]
            i += lit
            if i >= n:
                break                                   # l'ultima sequenza ha solo letterali
            offset = src[i] | (src[i + 1] << 8)
            i += 2
            if offset == 0 or offset > len(out):
                raise BsaError("LZ4: offset non valido")
            ml = token & 15
            if ml == 15:
                while True:
                    b = src[i]
                    i += 1
                    ml += b
                    if b != 255:
                        break
            ml += 4
            start = len(out) - offset
            if offset >= ml:
                out += out[start:start + ml]
            else:                                       # copia sovrapposta: si ripete il pattern
                for k in range(ml):
                    out.append(out[start + k])
    except IndexError:
        raise BsaError("LZ4: dati troncati") from None


def lz4_frame_decompress(data: bytes) -> bytes:
    if data[:4] != b"\x04\x22\x4d\x18":
        raise BsaError("LZ4: intestazione non riconosciuta")
    flg = data[4]
    if flg >> 6 != 1:
        raise BsaError("LZ4: versione del formato non supportata")
    block_checksum, content_size, dict_id = (flg >> 4) & 1, (flg >> 3) & 1, flg & 1
    pos = 6 + (8 if content_size else 0) + (4 if dict_id else 0) + 1   # FLG, BD, [dimensione], [dizionario], HC
    out = bytearray()
    while True:
        if pos + 4 > len(data):
            raise BsaError("LZ4: frame troncato")
        bs = int.from_bytes(data[pos:pos + 4], "little")
        pos += 4
        if bs == 0:
            break
        raw, bs = bool(bs & 0x80000000), bs & 0x7FFFFFFF
        blk = data[pos:pos + bs]
        if len(blk) != bs:
            raise BsaError("LZ4: blocco troncato")
        pos += bs + (4 if block_checksum else 0)
        if raw:
            out += blk
        else:
            _lz4_block(blk, out)
    return bytes(out)


# ---------------------------------------------------------------- archivio
@dataclass
class BsaEntry:
    path: str          # minuscolo, con "/" (es. "strings/mod_english.strings")
    size: int
    offset: int
    compressed: bool


class Bsa:
    def __init__(self, path: Path):
        self.path = Path(path)
        with open(self.path, "rb") as f:
            hdr = f.read(36)
            if len(hdr) < 36 or hdr[:4] != b"BSA\0":
                raise BsaError("non è un archivio BSA di Skyrim")
            (_, self.version, off, flags, nfold, nfile, tfolder, tfile, _ff, _pad) = struct.unpack("<4sIIIIIIIHH", hdr)
            if self.version not in (104, 105):
                raise BsaError(f"versione BSA {self.version} non supportata (solo Skyrim: 104 e 105)")
            if flags & 0x40:
                raise BsaError("archivi Xbox 360 non supportati")
            if not (flags & 1 and flags & 2):
                raise BsaError("archivio senza nomi di cartelle/file")
            self.default_compressed, self.embed_names = bool(flags & 4), bool(flags & 0x100)
            rec = 16 if self.version == 104 else 24
            f.seek(off)
            folders = []
            for _ in range(nfold):
                b = f.read(rec)
                if len(b) != rec:
                    raise BsaError("tabella cartelle troncata")
                if self.version == 104:
                    _h, count, offset = struct.unpack("<QII", b)
                else:
                    _h, count, _p, offset = struct.unpack("<QIIQ", b)
                folders.append((count, offset))
            blocks = []
            for count, offset in folders:
                f.seek(offset - tfile)                       # l'offset conta anche il blocco dei nomi dei file
                n = f.read(1)
                if not n:
                    raise BsaError("blocco cartella fuori dal file")
                name = f.read(n[0]).rstrip(b"\0").decode("cp1252", "replace").replace("\\", "/").lower()
                recs = []
                for _ in range(count):
                    r = f.read(16)
                    if len(r) != 16:
                        raise BsaError("record file troncato")
                    recs.append(struct.unpack("<QII", r)[1:])
                blocks.append((name, recs))
            # controllo di coerenza: dopo l'ultimo blocco devono esserci i nomi dei file, nel punto che le
            # dimensioni dichiarate nell'intestazione prevedono. Se non torna, non fidarsi di nulla.
            expected = off + nfold * rec + tfolder + nfold + nfile * 16
            if f.tell() != expected:
                raise BsaError("struttura dell'archivio non coerente (formato non riconosciuto)")
            names = f.read(tfile).split(b"\0")[:nfile]
            if len(names) != nfile:
                raise BsaError("elenco nomi file troncato")
        self.entries: list[BsaEntry] = []
        i = 0
        for folder, recs in blocks:
            for size_field, offset in recs:
                fname = names[i].decode("cp1252", "replace").lower()
                i += 1
                comp = self.default_compressed ^ bool(size_field & 0x40000000)
                p = f"{folder}/{fname}" if folder else fname
                self.entries.append(BsaEntry(p, size_field & 0x3FFFFFFF, offset, comp))

    def read(self, e: BsaEntry) -> bytes:
        with open(self.path, "rb") as f:
            f.seek(e.offset)
            raw = f.read(e.size)
        if len(raw) != e.size:
            raise BsaError(f"{e.path}: dati fuori dal file")
        if self.embed_names:
            if not raw:
                raise BsaError(f"{e.path}: dati vuoti")
            raw = raw[1 + raw[0]:]
        if not e.compressed:
            return raw
        if len(raw) < 4:
            raise BsaError(f"{e.path}: dati compressi troncati")
        orig = struct.unpack_from("<I", raw, 0)[0]
        try:
            data = zlib.decompress(raw[4:]) if self.version == 104 else lz4_frame_decompress(raw[4:])
        except zlib.error as ex:
            raise BsaError(f"{e.path}: zlib: {ex}") from None
        if len(data) != orig:
            raise BsaError(f"{e.path}: dimensione decompressa incoerente")
        return data
