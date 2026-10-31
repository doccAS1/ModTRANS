import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_all import build_plugin  # noqa: E402
from test_bsa import build_bsa  # noqa: E402
from test_gui import start_server, wait  # noqa: E402
from skyrimtrans import glossary as G  # noqa: E402
from skyrimtrans.cli import main  # noqa: E402
from skyrimtrans.translator import Translator  # noqa: E402


def build_strings(d: dict[int, str], enc="cp1252", prefixed=False) -> bytes:
    data, entries = b"", []
    for sid, text in d.items():
        entries.append((sid, len(data)))
        z = text.encode(enc) + b"\0"
        data += (struct.pack("<I", len(z)) + z) if prefixed else z
    return struct.pack("<II", len(entries), len(data)) + b"".join(struct.pack("<II", a, b) for a, b in entries) + data


EN = {1: "Iron Sword", 2: "Whiterun", 3: "Dragonborn", 4: "Deals 10 damage.", 5: "Wolf", 6: "Hold: Whiterun",
      7: "Steel Dagger", 8: "Red Mead", 9: "Gold", 10: "Hello <Alias=Player>", 11: "Guard", 12: "Guard Post"}
IT = {1: "Spada di Ferro", 2: "Whiterun", 3: "Sangue di Drago", 4: "Infligge 10 danni.", 5: "Lupo", 6: "Contea: Whiterun",
      7: "Pugnale d'Acciaio", 8: "Idromele Rosso", 9: "Oro", 10: "Ciao <Alias=Player>", 11: "Guardia", 12: "Posto di Guardia"}


def make_data(tmp_path, en=EN, it=IT):
    data = tmp_path / "Data"
    (data / "Strings").mkdir(parents=True)
    (data / "Strings" / "Skyrim_english.STRINGS").write_bytes(build_strings(en))
    (data / "Strings" / "Skyrim_italian.STRINGS").write_bytes(build_strings(it))
    return data


def test_builds_official_names_only(tmp_path):
    gl, info = G.build_glossary(make_data(tmp_path), "english", "italian")
    assert gl["Iron Sword"] == "Spada di Ferro" and gl["Dragonborn"] == "Sangue di Drago" and gl["Steel Dagger"] == "Pugnale d'Acciaio"
    assert gl["Red Mead"] == "Idromele Rosso" and gl["Gold"] == "Oro"
    assert "Whiterun" not in gl                      # uguale in entrambe le lingue: niente da imporre
    assert "Deals 10 damage." not in gl and "Hello <Alias=Player>" not in gl     # frasi e testi con tag fuori
    assert info["used"] == ["skyrim"] and info["terms"] == len(gl) and not info["missing"]


def test_reads_archives_and_loose_files_win(tmp_path):
    data = tmp_path / "Data"
    data.mkdir()
    (data / "Skyrim - Interface.bsa").write_bytes(build_bsa({
        "strings\\skyrim_english.strings": build_strings({1: "Iron Sword", 2: "Wolf"}),
        "strings\\skyrim_italian.strings": build_strings({1: "Spada di Ferro", 2: "Lupo"})}, compress=True))
    gl, _ = G.build_glossary(data, "english", "italian")
    assert gl == {"Iron Sword": "Spada di Ferro", "Wolf": "Lupo"}
    (data / "Strings").mkdir()
    (data / "Strings" / "Skyrim_italian.STRINGS").write_bytes(build_strings({1: "Spadone", 2: "Lupo"}))
    gl, _ = G.build_glossary(data, "english", "italian")
    assert gl["Iron Sword"] == "Spadone"             # il file sciolto vince sull'archivio, come nel gioco


def test_ambiguous_names_and_missing_language(tmp_path):
    data = make_data(tmp_path, {1: "Guard", 2: "Guard", 3: "Guard", 4: "Iron Sword"},
                     {1: "Guardia", 2: "Sentinella", 3: "Guardia", 4: "Spada di Ferro"})
    gl, info = G.build_glossary(data, "english", "italian")
    assert gl["Guard"] == "Guardia"                  # la traduzione più usata (2 su 3)
    d2 = make_data(tmp_path / "x", {1: "Guard", 2: "Guard"}, {1: "Guardia", 2: "Sentinella"})
    gl2, info2 = G.build_glossary(d2, "english", "italian")
    assert "Guard" not in gl2 and info2["ambiguous"] == 1
    # un DLC senza la lingua di destinazione viene saltato e segnalato
    (data / "Strings" / "Dawnguard_english.STRINGS").write_bytes(build_strings({1: "Crossbow"}))
    _, info3 = G.build_glossary(data, "english", "italian")
    assert info3["missing"] == ["dawnguard"] and info3["used"] == ["skyrim"]


def test_clear_errors(tmp_path):
    with pytest.raises(G.GlossaryError, match="non trovata"):
        G.build_glossary(tmp_path / "nope", "english", "italian")
    empty = tmp_path / "e"
    empty.mkdir()
    with pytest.raises(G.GlossaryError, match="Strings"):
        G.build_glossary(empty, "english", "italian")
    only_en = tmp_path / "o" / "Data" / "Strings"
    only_en.mkdir(parents=True)
    (only_en / "Skyrim_english.STRINGS").write_bytes(build_strings(EN))
    with pytest.raises(G.GlossaryError, match="entrambe le lingue"):
        G.build_glossary(tmp_path / "o", "english", "italian")          # accetta anche la cartella del gioco
    with pytest.raises(G.GlossaryError, match="uguali"):
        G.build_glossary(make_data(tmp_path / "y"), "italian", "italian")


def test_game_folder_is_accepted(tmp_path):
    root = tmp_path / "Skyrim Special Edition"
    make_data(root)
    gl, _ = G.build_glossary(root, "english", "italian")
    assert gl["Iron Sword"] == "Spada di Ferro"


# ------------------------------------------------------------ uso nel traduttore
class Spy:
    def __init__(self):
        self.systems = []

    def __call__(self, system, user):
        self.systems.append(system)
        return json.dumps([{"id": i["id"], "text": "IT " + i["text"]} for i in json.loads(user)])


def test_only_terms_present_in_the_batch_reach_the_model():
    big = {f"Term{n} Thing": f"Cosa{n}" for n in range(500)}
    big.update({"Iron Sword": "Spada di Ferro", "Dragonborn": "Sangue di Drago"})
    spy = Spy()
    tr = Translator(spy, "Italian", game_glossary=big, batch_items=1)
    tr.translate_all([("description:WEAP", "A fine Iron Sword made by the Dragonborn."), ("description:WEAP", "Nothing special here")])
    with_terms = [s for s in spy.systems if "Iron Sword => Spada di Ferro" in s]
    assert len(with_terms) == 1 and "Dragonborn => Sangue di Drago" in with_terms[0]
    assert "Term7 Thing" not in "".join(spy.systems)                     # i 500 termini non presenti restano fuori
    plain = [s for s in spy.systems if "Iron Sword" not in s][0]
    assert "game's own" not in plain                                     # nessuna intestazione se non c'è nulla


def test_matching_is_by_whole_words_and_user_glossary_wins():
    spy = Spy()
    game = {"Iron Sword": "Spada di Ferro", "Wolf": "Lupo"}
    Translator(spy, "Italian", glossary={"Iron Sword": "Lama d'Acciaio"}, game_glossary=game).translate_all(
        [("description:WEAP", "An Iron Sword and a Wolfhound")])
    s = spy.systems[0]
    assert "Iron Sword => Lama d'Acciaio" in s and "Spada di Ferro" not in s     # il glossario dell'utente ha la precedenza
    assert "Wolf =>" not in s                                                    # "Wolfhound" non è "Wolf"
    spy2 = Spy()
    Translator(spy2, "Italian", game_glossary={"Iron Sword": "Spada di Ferro"}).translate_all(
        [("description:WEAP", "The Iron Swordsman arrives")])
    assert "Spada di Ferro" not in spy2.systems[0]                               # parola intera, non prefisso


def test_game_terms_are_not_repeated_in_remembered_terms():
    spy = Spy()
    tr = Translator(spy, "Italian", game_glossary={"Iron Sword": "Spada di Ferro"}, batch_items=1)
    tr.translate_all([("name:WEAP", "Iron Sword"), ("description:WEAP", "A strong Iron Sword for you")])
    last = spy.systems[-1]
    assert last.count("Iron Sword =>") == 1


# ------------------------------------------------------------ CLI e GUI
def test_cli_glossary_command(tmp_path, capsys):
    data = make_data(tmp_path)
    out = tmp_path / "g.json"
    assert main(["glossario", str(data), "-l", "italian", "-o", str(out)]) == 0
    assert json.loads(out.read_text("utf-8"))["Iron Sword"] == "Spada di Ferro"
    assert "termini" in capsys.readouterr().out
    assert main(["glossario", str(tmp_path / "vuota"), "-l", "italian", "-o", str(out)]) == 2
    assert "non trovata" in capsys.readouterr().err


def test_cli_translation_uses_game_glossary(tmp_path):
    data = make_data(tmp_path)
    esp = tmp_path / "My.esp"
    esp.write_bytes(build_plugin())
    spy = Spy()
    assert main([str(esp), "-l", "italian", "--game-data", str(data), "--out-dir", str(tmp_path / "o"),
                 "--no-memory"], backend=spy) == 0
    assert any("Iron Sword => Spada di Ferro" in s for s in spy.systems)   # il nome ufficiale arriva al modello
    assert not any("Ancient Tome =>" in s for s in spy.systems)
    assert main([str(esp), "-l", "italian", "--game-data", str(tmp_path / "boh"), "--no-memory"], backend=spy) == 2


def test_gui_game_data_error_is_plain(monkeypatch, tmp_path):
    httpd, app, c = start_server(monkeypatch, tmp_path)
    up = json.loads(c.call("/api/upload?name=My.esp", raw=build_plugin())[1])
    s = {"upload_id": up["upload_id"], "lang": "italian", "source": "english", "provider": "openai", "preset": "x",
         "model": "m", "base_url": "http://127.0.0.1:9/v1", "dry_run": True, "game_data": str(tmp_path / "nope")}
    job = json.loads(c.call("/api/start", s)[1])["job_id"]
    st = wait(c, job)
    assert st["state"] == "error" and "non trovata" in st["error"] and "Cartella non trovata" in st["error"]
    httpd.shutdown(); httpd.server_close()


def test_lowercase_and_sentence_like_entries_are_excluded(tmp_path):
    data = make_data(tmp_path, {1: "arrow", 2: "Iron Sword", 3: "Welcome to Whiterun!", 4: "A very long name with way too many words in it"},
                     {1: "freccia", 2: "Spada di Ferro", 3: "Benvenuto a Whiterun!", 4: "Un nome molto lungo con troppe parole"})
    gl, _ = G.build_glossary(data, "english", "italian")
    assert gl == {"Iron Sword": "Spada di Ferro"}


def test_obvious_translations_are_left_out_but_special_ones_stay(tmp_path):
    en = {1: "Gold", 2: "Iron", 3: "Sword", 4: "Ingot", 5: "Iron Sword", 6: "Gold Ingot", 7: "Dragonborn",
          8: "Nirnroot", 9: "Iron Ingot", 10: "Hall of the Dead"}
    it = {1: "Oro", 2: "Ferro", 3: "Spada", 4: "Lingotto", 5: "Spada di Ferro", 6: "Lingotto d'Oro", 7: "Sangue di Drago",
          8: "Radicenirn", 9: "Lingotto di Ferro", 10: "Sala dei Morti"}
    data = make_data(tmp_path, en, it)
    # nei testi del gioco "gold" compare spesso in minuscolo: è una parola comune
    talk = {n: "I have some gold for you" for n in range(100, 112)}
    (data / "Strings" / "Skyrim_english.ILSTRINGS").write_bytes(build_strings(talk, prefixed=True))
    gl, info = G.build_glossary(data, "english", "italian")
    assert "Gold" not in gl                                           # parola comune, una parola per lato: ovvia
    assert gl["Iron"] == "Ferro"                                      # rara nei testi di questo mini-gioco: resta (soglia sul conteggio)
    assert gl["Dragonborn"] == "Sangue di Drago"                      # non letterale: resta
    assert gl["Nirnroot"] == "Radicenirn"                             # parola rara, una sola parola: resta
    assert "Iron Sword" not in gl and "Gold Ingot" not in gl and "Iron Ingot" not in gl    # somma delle parti: il modello lo sa
    assert gl["Hall of the Dead"] == "Sala dei Morti"                 # "Dead" non è nel lessico: nel dubbio resta
    assert info["common"] == 1 and info["literal"] == 3


def test_literal_check_unit():
    lex = {"iron": "ferro", "sword": "spada", "black": "nero", "horse": "cavallo"}
    assert G.is_literal("Iron Sword", "Spada di Ferro", lex)
    assert G.is_literal("Black Horse", "Cavallo Nera", lex)            # genere/plurale tollerati
    assert not G.is_literal("Iron Sword", "Lama d'Acciaio", lex)       # traduzione libera: resta
    assert not G.is_literal("Iron Dragon", "Drago di Ferro", lex)      # "Dragon" sconosciuta: nel dubbio resta
    assert not G.is_literal("Dragonborn", "Sangue di Drago", lex)      # una sola parola: mai letterale
