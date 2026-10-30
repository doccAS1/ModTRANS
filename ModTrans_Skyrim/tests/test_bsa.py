import struct
import sys
import zipfile
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_all import FakeBackend, build_plugin, grup, rec, sub  # noqa: E402
from skyrimtrans import bsa as B, plugin as pl  # noqa: E402
from skyrimtrans.pipeline import run  # noqa: E402
from skyrimtrans.translator import Translator  # noqa: E402


# --------------------------------------------------------------- LZ4 con vettori scritti a mano
def lz4_frame(blocks, raw=False, checksum=False):
    flg = 0x60 | (0x10 if checksum else 0)
    out = b"\x04\x22\x4d\x18" + bytes([flg, 0x40, 0x00])
    for b in blocks:
        out += struct.pack("<I", len(b) | (0x80000000 if raw else 0)) + b + (b"\0\0\0\0" if checksum else b"")
    return out + struct.pack("<I", 0)


def test_lz4_handwritten_vectors():
    assert B.lz4_frame_decompress(lz4_frame([bytes([0x35]) + b"abc" + b"\x03\x00"])) == b"abcabcabcabc"
    assert B.lz4_frame_decompress(lz4_frame([bytes([0x16]) + b"a" + b"\x01\x00"])) == b"a" * 11   # copia sovrapposta
    assert B.lz4_frame_decompress(lz4_frame([b"hello"], raw=True)) == b"hello"
    # lunghezze estese (>= 15 letterali e >= 19 di match)
    lit = bytes(range(65, 65 + 20))
    blk = bytes([0xF0 | 0x0F, 5]) + lit + b"\x14\x00" + bytes([240])
    assert B.lz4_frame_decompress(lz4_frame([blk], checksum=True)).startswith(lit)
    for bad in (b"nope", lz4_frame([b"x"])[:-6], lz4_frame([bytes([0x35]) + b"abc" + b"\x09\x00"])):
        with pytest.raises(B.BsaError):
            B.lz4_frame_decompress(bad)


def test_lz4_matches_reference_library():
    lz4 = pytest.importorskip("lz4.frame")
    text = "".join(f"Line {n}: the quick brown fox jumps over the lazy dog {n * 7}\r\n" for n in range(4000)).encode()
    for kw in ({}, {"block_size": lz4.BLOCKSIZE_MAX64KB, "block_linked": True},
               {"block_size": lz4.BLOCKSIZE_MAX64KB, "block_linked": False}, {"block_checksum": True, "content_checksum": True}):
        assert B.lz4_frame_decompress(lz4.compress(text, **kw)) == text


# --------------------------------------------------------------- creatore di BSA (solo per i test)
def build_bsa(files, version=104, compress=False, embed=False, comp_fn=None, flip=(), tamper_tfile=0):
    folders = {}
    for path, data in files.items():
        d, _, n = path.rpartition("\\")
        folders.setdefault(d, []).append((n, data))
    flags = 1 | 2 | (4 if compress else 0) | (0x100 if embed else 0)
    rec_size = 16 if version == 104 else 24
    tfile = sum(len(n) + 1 for fs in folders.values() for n, _ in fs)
    tfolder = sum(len(d) + 1 for d in folders)
    nfile = sum(len(fs) for fs in folders.values())
    blocks_start = 36 + len(folders) * rec_size
    block_sizes = [1 + len(d) + 1 + len(fs) * 16 for d, fs in folders.items()]
    names_start = blocks_start + sum(block_sizes)
    data_pos = names_start + tfile
    payloads, frec = [], {}
    for d, fs in folders.items():
        for n, data in fs:
            comp = compress and (d + "\\" + n) not in flip
            body = data
            if comp:
                body = struct.pack("<I", len(data)) + (zlib.compress(data) if version == 104 else comp_fn(data))
            if embed:
                full = (d + "\\" + n).encode()
                body = bytes([len(full)]) + full + body
            size_field = len(body) | (0x40000000 if (d + "\\" + n) in flip else 0)
            frec[(d, n)] = (size_field, data_pos)
            data_pos += len(body)
            payloads.append(body)
    out = struct.pack("<4sIIIIIIIHH", b"BSA\0", version, 36, flags, len(folders), nfile, tfolder, tfile + tamper_tfile, 0, 0)
    pos = blocks_start
    for (d, fs), bs in zip(folders.items(), block_sizes):
        offset = pos + tfile
        out += struct.pack("<QII", 0, len(fs), offset) if version == 104 else struct.pack("<QIIQ", 0, len(fs), 0, offset)
        pos += bs
    for d, fs in folders.items():
        out += bytes([len(d) + 1]) + d.encode() + b"\0"
        for n, _ in fs:
            out += struct.pack("<QII", 0, *frec[(d, n)])
    for d, fs in folders.items():
        for n, _ in fs:
            out += n.encode() + b"\0"
    return out + b"".join(payloads)


def raw_lz4(data):
    return lz4_frame([data], raw=True)


FILES = {"strings\\test_english.strings": b"S" * 40, "interface\\translations\\test_english.txt": "é\r\n".encode() * 50,
         "meshes\\a\\b.nif": bytes(range(256)) * 3}


@pytest.mark.parametrize("version,compress,embed", [(104, False, False), (104, True, False), (104, True, True),
                                                    (105, False, False), (105, True, False), (105, True, True)])
def test_roundtrip_all_flavours(tmp_path, version, compress, embed):
    p = tmp_path / "a.bsa"
    p.write_bytes(build_bsa(FILES, version, compress, embed, comp_fn=raw_lz4))
    a = B.Bsa(p)
    got = {e.path: a.read(e) for e in a.entries}
    assert got == {k.replace("\\", "/"): v for k, v in FILES.items()}


def test_lz4_real_library_and_flipped_compression_bit(tmp_path):
    lz4 = pytest.importorskip("lz4.frame")
    big = ("Some longer string for compression. " * 3000).encode()
    files = dict(FILES, **{"strings\\big_english.dlstrings": big})
    flip = {"meshes\\a\\b.nif"}                       # in un archivio compresso, questo file è salvato NON compresso
    p = tmp_path / "a.bsa"
    p.write_bytes(build_bsa(files, 105, True, comp_fn=lz4.compress, flip=flip))
    a = B.Bsa(p)
    assert {e.path: a.read(e) for e in a.entries} == {k.replace("\\", "/"): v for k, v in files.items()}
    assert {e.path: e.compressed for e in a.entries}["meshes/a/b.nif"] is False


def test_broken_archives_raise_clean_errors(tmp_path):
    good = build_bsa(FILES, 104, True)
    cases = {"magic": b"XXXX" + good[4:], "version": good[:4] + struct.pack("<I", 103) + good[8:],
             "troncato": good[:60], "coerenza": build_bsa(FILES, 104, True, tamper_tfile=3),
             "vuoto": b"", "xbox": good[:12] + struct.pack("<I", struct.unpack_from("<I", good, 12)[0] | 0x40) + good[16:]}
    for name, data in cases.items():
        p = tmp_path / f"{name}.bsa"
        p.write_bytes(data)
        with pytest.raises(B.BsaError):
            B.Bsa(p)
    # dati di un file fuori dall'archivio
    p = tmp_path / "t.bsa"
    p.write_bytes(good[:-10])
    a = B.Bsa(p)
    with pytest.raises(B.BsaError):
        for e in a.entries:
            a.read(e)


# --------------------------------------------------------------- pipeline: mod localizzata con Strings nel .bsa
def strings_file(prefixed, items):
    body, offs = b"", []
    for sid, t in items:
        offs.append((sid, len(body)))
        b = t.encode("cp1252") + b"\0"
        body += (struct.pack("<I", len(b)) + b) if prefixed else b
    return struct.pack("<II", len(items), len(body)) + b"".join(struct.pack("<II", i, o) for i, o in offs) + body


def localized_plugin():
    tes4 = rec("TES4", 0, [sub("HEDR", struct.pack("<fII", 1.7, 1, 0x800)), sub("CNAM", b"Me\0")], flags=0x80)
    weap = rec("WEAP", 0x801, [sub("EDID", b"W\0"), sub("FULL", struct.pack("<I", 1))])
    return tes4 + grup([weap], b"WEAP")


def make_mod(tmp_path, bsa_bytes, extra=None):
    mod = tmp_path / "mod"
    mod.mkdir()
    (mod / "My.esp").write_bytes(localized_plugin())
    if bsa_bytes is not None:
        (mod / "My.bsa").write_bytes(bsa_bytes)
    for rel, data in (extra or {}).items():
        (mod / rel).parent.mkdir(parents=True, exist_ok=True)
        (mod / rel).write_bytes(data)
    return mod


def test_pipeline_translates_strings_inside_bsa_as_loose_files(tmp_path):
    files = {"strings\\my_english.strings": strings_file(False, [(1, "Iron Sword")]),
             "strings\\my_english.dlstrings": strings_file(True, [(2, "A fine sword.\r\nSharp.")]),
             "strings\\my_english.ilstrings": strings_file(True, [(3, "Hello there.")]),
             "interface\\translations\\my_english.txt": b"\xff\xfe" + "$KEY\tEnable it\r\n".encode("utf-16-le"),
             "strings\\my_french.strings": strings_file(False, [(1, "Epee")]),     # altra lingua: ignorata
             "meshes\\w.nif": b"nif"}
    for version in (104, 105):
        bsa_bytes = build_bsa(files, version, compress=True, comp_fn=raw_lz4)
        mod = make_mod(tmp_path / f"v{version}", bsa_bytes) if (tmp_path / f"v{version}").mkdir() is None else None
        out = tmp_path / f"o{version}.zip"
        rep = run(mod, out, Translator(FakeBackend(), "Italian"), "italian")
        assert not rep.failures, rep.failures
        z = zipfile.ZipFile(out)
        assert sorted(z.namelist()) == sorted([
            "My.esp", "My.bsa", "Strings/my_ITALIAN.strings", "Strings/my_ITALIAN.dlstrings",
            "Strings/my_ITALIAN.ilstrings", "Interface/Translations/my_ITALIAN.txt"])
        assert z.read("My.bsa") == bsa_bytes and z.read("My.esp") == localized_plugin()   # originali intatti
        from skyrimtrans import strings_file as sf
        assert list(sf.StringsFile(z.read("Strings/my_ITALIAN.strings"), ".strings").raw.values()) == [b"IT Iron Sword\0"]
        assert list(sf.StringsFile(z.read("Strings/my_ITALIAN.dlstrings"), ".dlstrings").raw.values()) == [b"IT A fine sword.\r\nSharp.\0"]
        assert z.read("Interface/Translations/my_ITALIAN.txt")[2:].decode("utf-16-le") == "$KEY\tIT Enable it\r\n"
        assert any("My.bsa" in w and w.startswith("Info:") for w in rep.warnings)
        assert not any("nulla da tradurre" in w for w in rep.warnings)


def test_loose_file_wins_over_archive_and_corrupt_archive_is_reported(tmp_path):
    files = {"strings\\my_english.strings": strings_file(False, [(1, "From archive")])}
    mod = make_mod(tmp_path / "a", build_bsa(files, 104)) if (tmp_path / "a").mkdir() is None else None
    (mod / "Strings").mkdir()
    (mod / "Strings" / "My_English.STRINGS").write_bytes(strings_file(False, [(1, "Loose wins")]))
    rep = run(mod, tmp_path / "o.zip", Translator(FakeBackend(), "Italian"), "italian")
    from skyrimtrans import strings_file as sf
    z = zipfile.ZipFile(tmp_path / "o.zip")
    assert list(sf.StringsFile(z.read("Strings/My_ITALIAN.STRINGS"), ".strings").raw.values()) == [b"IT Loose wins\0"]

    mod2 = make_mod(tmp_path / "b", b"BSA\0" + b"\1" * 80) if (tmp_path / "b").mkdir() is None else None
    rep2 = run(mod2, tmp_path / "o2.zip", Translator(FakeBackend(), "Italian"), "italian")
    assert any("My.bsa" in w and "non leggibile" in w for w in rep2.warnings)
    assert any("nulla da tradurre" in w for w in rep2.warnings)         # e lo dice chiaramente
    assert zipfile.ZipFile(tmp_path / "o2.zip").read("My.bsa").startswith(b"BSA\0")
