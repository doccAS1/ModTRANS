"""Glossario ufficiale costruito dal gioco stesso.

Skyrim e i DLC tengono i testi in `Strings/<plugin>_<lingua>.STRINGS`, con lo stesso ID in ogni lingua.
Accoppiando i file inglese e italiano per ID si ottengono i nomi ufficiali (armi, luoghi, incantesimi...).
Si legge sia da file sciolti sia dai .bsa; tutto avviene sul PC dell'utente: nessun testo del gioco
viene distribuito con il programma.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from . import bsa as bsa_mod
from .common import decode_zstring
from .strings_file import StringsError, StringsFile

_NAME_RE = re.compile(r"^(?P<stem>.+)_(?P<lang>[a-z]+)\.strings$", re.I)
MAX_WORDS, MAX_LEN, MIN_LEN = 6, 60, 3


class GlossaryError(ValueError):
    pass


def find_data_dir(path: Path) -> Path:
    """Accetta la cartella Data oppure quella del gioco (che contiene Data)."""
    path = Path(path).expanduser()
    if not path.is_dir():
        raise GlossaryError(f"Cartella non trovata: {path}")
    for cand in (path, path / "Data", path / "data"):
        if (cand / "Strings").is_dir() or (cand / "strings").is_dir() or any(cand.glob("*.bsa")):
            return cand
    raise GlossaryError(f"In {path} non trovo né una cartella Strings né archivi .bsa: scegli la cartella Data di Skyrim")


def collect_strings(data: Path, languages: set[str]) -> dict[tuple[str, str], bytes]:
    """{(plugin minuscolo, lingua): contenuto del file .STRINGS}. I file sciolti battono gli archivi."""
    found: dict[tuple[str, str], bytes] = {}
    for bsa_path in sorted(data.glob("*.bsa")):
        try:
            archive = bsa_mod.Bsa(bsa_path)
            for e in archive.entries:
                if not e.path.startswith("strings/"):
                    continue
                m = _NAME_RE.match(e.path.rsplit("/", 1)[-1])
                if m and m["lang"].lower() in languages:
                    found[(m["stem"].lower(), m["lang"].lower())] = archive.read(e)
        except (bsa_mod.BsaError, OSError):
            continue                                   # un archivio illeggibile non blocca gli altri
    for folder in data.iterdir():
        if folder.is_dir() and folder.name.lower() == "strings":
            for f in folder.iterdir():
                m = _NAME_RE.match(f.name)
                if f.is_file() and m and m["lang"].lower() in languages:
                    found[(m["stem"].lower(), m["lang"].lower())] = f.read_bytes()
    return found


def _decode_all(buf: bytes, enc: str) -> dict[int, str]:
    sf = StringsFile(buf, ".strings")
    out = {}
    for sid, off in sf.entries:
        chunk = sf.raw.get(off, b"")
        s = decode_zstring(chunk if chunk.endswith(b"\x00") else chunk + b"\x00", enc)
        if s:
            out[sid] = s
    return out


def looks_like_term(en: str) -> bool:
    """Un nome di gioco (non una frase, non un testo con formattazione)."""
    if not (MIN_LEN <= len(en) <= MAX_LEN) or len(en.split()) > MAX_WORDS:
        return False
    if re.search(r"[<>%$\[\]{}\n\r\\]", en) or en != en.strip():
        return False
    if not en[0].isupper() or en.rstrip().endswith((".", "!", "?", ":", ",", ";")):
        return False
    return bool(re.search(r"[A-Za-z]{2}", en))


def build_glossary(data: Path, source: str, target: str, src_enc: str = "cp1252", tgt_enc: str = "cp1252",
                   ) -> tuple[dict[str, str], dict]:
    """Ritorna (glossario, info). info = plugin usati, plugin senza l'altra lingua, scartati per ambiguità."""
    source, target = source.lower(), target.lower()
    if source == target:
        raise GlossaryError("La lingua originale e quella di destinazione sono uguali")
    files = collect_strings(find_data_dir(data), {source, target})
    stems = sorted({s for s, _ in files})
    votes: dict[str, Counter] = {}
    used, missing = [], []
    for stem in stems:
        if (stem, source) not in files or (stem, target) not in files:
            missing.append(stem)
            continue
        try:
            a = _decode_all(files[(stem, source)], src_enc)
            b = _decode_all(files[(stem, target)], tgt_enc)
        except StringsError:
            missing.append(stem)
            continue
        used.append(stem)
        for sid, en in a.items():
            it = b.get(sid)
            if it and it != en and looks_like_term(en) and looks_like_term(it[:1].upper() + it[1:]) and len(it) <= MAX_LEN + 20:
                votes.setdefault(en, Counter())[it] += 1
    glossary, ambiguous = {}, 0
    for en, c in votes.items():
        (best, n), total = c.most_common(1)[0], sum(c.values())
        if n * 2 > total:
            glossary[en] = best
        else:
            ambiguous += 1                              # stesso nome con traduzioni diverse: meglio non imporne una
    info = {"used": used, "missing": missing, "ambiguous": ambiguous, "terms": len(glossary)}
    if not used:
        raise GlossaryError(
            f"Non ho trovato file Strings in entrambe le lingue ({source} e {target}) in {data}. "
            f"Servono es. Skyrim_{source}.STRINGS e Skyrim_{target}.STRINGS (sciolti in Data/Strings o dentro i .bsa).")
    return dict(sorted(glossary.items())), info
