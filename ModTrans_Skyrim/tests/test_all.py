import json
import struct
import sys
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modtrans import plugin as pl, protect as pr  # noqa: E402
from modtrans.pipeline import run  # noqa: E402
from modtrans.translator import Translator  # noqa: E402


def sub(t, d):
    return t.encode() + struct.pack("<H", len(d)) + d


def rec(t, formid, subs, flags=0, compress=False):
    raw = b"".join(subs)
    if compress:
        flags |= pl.FLAG_COMPRESSED
        raw = struct.pack("<I", len(raw)) + zlib.compress(raw)
    return t.encode() + struct.pack("<IIIIHH", len(raw), flags, formid, 0, 44, 0) + raw


def grup(children, label=b"BOOK"):
    body = b"".join(children)
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label + struct.pack("<IHHI", 0, 0, 0, 0) + body


def build_plugin():
    tes4 = rec("TES4", 0, [sub("HEDR", struct.pack("<fII", 1.7, 2, 0x800)), sub("CNAM", b"Author\0")])
    book = rec("BOOK", 0x801, [
        sub("EDID", b"MyBook\0"),
        sub("FULL", b"Ancient Tome\0"),
        sub("DESC", b"Hello <Alias=Player>.\r\nYou have <mag> gold.[pagebreak]Page two.\0"),
        sub("DATA", b"\x01\x02\x03\x04Not text but looks like text\0"),
    ], compress=True)
    weap = rec("WEAP", 0x802, [sub("EDID", b"MySword\0"), sub("FULL", b"Iron Sword\0"),
                               sub("DATA", struct.pack("<IfH", 25, 9.0, 8))])
    return tes4 + grup([book, weap])


class FakeBackend:
    """Traduce 'in italiano' mettendo un prefisso; mantiene i segnaposto."""
    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, 0

    def __call__(self, system, user):
        self.calls += 1
        items = json.loads(user)
        out = []
        for it in items:
            t = it["text"]
            if self.mode == "drop":
                t = "Ciao senza segnaposto"
            else:
                t = "IT " + t
            out.append({"id": it["id"], "text": t})
        return "```json\n" + json.dumps(out) + "\n```"


def test_protect_roundtrip():
    p = pr.protect("Hi <Alias=Player>,\r\n100 %d {0} $KEY")
    assert len(p.tokens) == 5
    assert pr.restore(p, p.masked.replace("Hi", "Ciao")) == "Ciao <Alias=Player>,\r\n100 %d {0} $KEY"
    try:
        pr.restore(p, "Ciao")
        assert False
    except pr.ProtectionError:
        pass
    assert pr.protect("$MY_KEY").skip_reason


def test_plugin_identity_and_translate(tmp_path):
    data = build_plugin()
    assert pl.Plugin(data).to_bytes() == data
    mod = tmp_path / "mod"
    mod.mkdir()
    (mod / "My.esp").write_bytes(data)
    out = tmp_path / "out.zip"
    be = FakeBackend()
    rep = run(mod, out, Translator(be, "Italian"), "italian")
    assert rep.translated == 3 and not rep.failures, rep
    new = zipfile.ZipFile(out).read("My.esp")
    assert pl.verify_plugin(data, new, "cp1252") == []
    a, b = pl.Plugin(data), pl.Plugin(new)
    ra = {r.formid: dict(r.subs()) for r in a.records}
    rb = {r.formid: dict(r.subs()) for r in b.records}
    # campi non testuali identici byte per byte
    assert ra[0x801][b"DATA".decode()] == rb[0x801]["DATA"]
    assert ra[0x802]["DATA"] == rb[0x802]["DATA"]
    assert ra[0x801]["EDID"] == rb[0x801]["EDID"]
    assert rb[0x801]["FULL"] == b"IT Ancient Tome\0"
    desc = rb[0x801]["DESC"]
    assert b"<Alias=Player>" in desc and b"<mag>" in desc and b"\r\n" in desc and b"[pagebreak]" in desc
    # il record compresso e' ancora valido e il gruppo ha la dimensione giusta
    assert pl.Plugin(new).to_bytes() == new


def test_bad_translation_keeps_original(tmp_path):
    data = build_plugin()
    mod = tmp_path / "m"
    mod.mkdir()
    (mod / "My.esp").write_bytes(data)
    out = tmp_path / "o.zip"
    rep = run(mod, out, Translator(FakeBackend("drop"), "Italian", retries=1), "italian")
    new = zipfile.ZipFile(out).read("My.esp")
    ra = {r.formid: dict(r.subs()) for r in pl.Plugin(data).records}
    rb = {r.formid: dict(r.subs()) for r in pl.Plugin(new).records}
    # DESC aveva segnaposto: rifiutata, resta originale
    assert rb[0x801]["DESC"] == ra[0x801]["DESC"]
    assert rep.failures


def test_mcm_and_strings(tmp_path):
    from modtrans import mcm, strings_file as sf

    mod = tmp_path / "m"
    (mod / "Interface" / "Translations").mkdir(parents=True)
    txt = "$KEY_A\tEnable feature\r\n$KEY_B\tSpeed: {0}\r\n\r\n"
    (mod / "Interface/Translations/My_ENGLISH.txt").write_bytes(b"\xff\xfe" + txt.encode("utf-16-le"))
    ids = [(1, 0), (2, 6)]
    body = b"Sword\0" + b"Shield\0"
    (mod / "My_English.STRINGS").write_bytes(
        struct.pack("<II", 2, len(body)) + b"".join(struct.pack("<II", i, o) for i, o in ids) + body)
    out = tmp_path / "o.zip"
    rep = run(mod, out, Translator(FakeBackend(), "Italian"), "italian")
    z = zipfile.ZipFile(out)
    names = z.namelist()
    assert "Interface/Translations/My_ITALIAN.txt" in names and "My_ITALIAN.STRINGS" in names
    new = z.read("Interface/Translations/My_ITALIAN.txt")
    assert new.startswith(b"\xff\xfe")
    t = new[2:].decode("utf-16-le")
    assert t.startswith("$KEY_A\tIT Enable feature\r\n$KEY_B\tIT Speed: {0}\r\n\r\n")
    s = sf.StringsFile(z.read("My_ITALIAN.STRINGS"), ".strings")
    assert [i for i, _ in s.entries] == [1, 2]
    assert sorted(s.raw.values()) == [b"IT Shield\0", b"IT Sword\0"]


def test_cli(tmp_path):
    from modtrans.cli import main
    (tmp_path / "My.esp").write_bytes(build_plugin())
    out = tmp_path / "x.zip"
    assert main([str(tmp_path / "My.esp"), "-l", "italian", "-o", str(out)], backend=FakeBackend()) == 0
    assert zipfile.ZipFile(out).read("My.esp")


def test_openai_compatible_local_server(tmp_path):
    """Server HTTP finto che parla il protocollo OpenAI: prova il backend vero, non un mock."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from modtrans.cli import main

    seen = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen["path"], seen["auth"], seen["model"] = self.path, self.headers.get("Authorization"), body["model"]
            items = json.loads(body["messages"][1]["content"])
            reply = "<think>ragiono...</think>" + json.dumps(
                [{"id": i["id"], "text": "IT " + i["text"]} for i in items])
            out = json.dumps({"choices": [{"message": {"content": reply}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    (tmp_path / "My.esp").write_bytes(build_plugin())
    out = tmp_path / "o.zip"
    rc = main([str(tmp_path / "My.esp"), "-l", "italian", "-o", str(out), "--provider", "openai",
               "--model", "llama3", "--base-url", f"http://127.0.0.1:{srv.server_port}/v1"])
    srv.shutdown()
    assert rc == 0 and seen["path"] == "/v1/chat/completions" and seen["auth"] is None
    new = zipfile.ZipFile(out).read("My.esp")
    full = {r.formid: dict(r.subs()).get("FULL") for r in pl.Plugin(new).records}
    assert full[0x801] == b"IT Ancient Tome\0" and full[0x802] == b"IT Iron Sword\0"
    assert pl.verify_plugin(build_plugin(), new, "cp1252") == []
