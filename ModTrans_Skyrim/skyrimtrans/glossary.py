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

_NAME_RE = re.compile(r"^(?P<stem>.+)_(?P<lang>[a-z]+)\.(?P<ext>strings|dlstrings|ilstrings)$", re.I)
MAX_WORDS, MAX_LEN, MIN_LEN = 6, 60, 3
ORDINARY_MIN = 8      # una parola scritta in minuscolo almeno così spesso nei testi del gioco è vocabolario comune


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


def collect_strings(data: Path, languages: set[str]) -> dict[tuple[str, str, str], bytes]:
    """{(plugin minuscolo, lingua, estensione): contenuto}. I file sciolti battono gli archivi."""
    found: dict[tuple[str, str, str], bytes] = {}
    for bsa_path in sorted(data.glob("*.bsa")):
        try:
            archive = bsa_mod.Bsa(bsa_path)
            for e in archive.entries:
                if not e.path.startswith("strings/"):
                    continue
                m = _NAME_RE.match(e.path.rsplit("/", 1)[-1])
                if m and m["lang"].lower() in languages:
                    found[(m["stem"].lower(), m["lang"].lower(), m["ext"].lower())] = archive.read(e)
        except (bsa_mod.BsaError, OSError):
            continue                                   # un archivio illeggibile non blocca gli altri
    for folder in data.iterdir():
        if folder.is_dir() and folder.name.lower() == "strings":
            for f in folder.iterdir():
                m = _NAME_RE.match(f.name)
                if f.is_file() and m and m["lang"].lower() in languages:
                    found[(m["stem"].lower(), m["lang"].lower(), m["ext"].lower())] = f.read_bytes()
    return found


def _decode_all(buf: bytes, enc: str, ext: str = ".strings") -> dict[int, str]:
    sf = StringsFile(buf, ext)
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


def _words(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", text.lower())


def _content(words: list[str]) -> list[str]:
    return [w for w in words if len(w) > 3]             # scarta articoli e preposizioni (of, the, di, del, d')


def is_literal(en: str, it: str, lexicon: dict[str, str]) -> bool:
    """True se la traduzione è solo la somma delle traduzioni delle singole parole (Iron Sword -> Spada di Ferro):
    il modello la ottiene da solo. Nel dubbio (parola sconosciuta) ritorna False: la voce resta."""
    words = _content(_words(en))
    if len(words) < 2:
        return False
    toks = _words(it)                                   # qui servono anche le parole corte (oro, re, sol)
    for w in words:
        tr = lexicon.get(w)
        if not tr:
            return False
        stem = tr[:max(3, len(tr) - 2)]                  # tollera genere e plurale (nero/nera, lupo/lupi)
        if not any(t.startswith(stem) for t in toks):
            return False
    return True


def build_glossary(data: Path, source: str, target: str, src_enc: str = "cp1252", tgt_enc: str = "cp1252",
                   ) -> tuple[dict[str, str], dict]:
    """Ritorna (glossario, info). info = plugin usati, plugin senza l'altra lingua, scartati per ambiguità."""
    source, target = source.lower(), target.lower()
    if source == target:
        raise GlossaryError("La lingua originale e quella di destinazione sono uguali")
    files = collect_strings(find_data_dir(data), {source, target})
    stems = sorted({k[0] for k in files})
    votes: dict[str, Counter] = {}
    used, missing = [], []
    lower_count: Counter = Counter()                    # quante volte ogni parola compare in minuscolo nel gioco
    for stem in stems:
        if (stem, source, "strings") not in files or (stem, target, "strings") not in files:
            missing.append(stem)
            continue
        try:
            a = _decode_all(files[(stem, source, "strings")], src_enc)
            b = _decode_all(files[(stem, target, "strings")], tgt_enc)
        except StringsError:
            missing.append(stem)
            continue
        for ext in ("strings", "dlstrings", "ilstrings"):
            buf = files.get((stem, source, ext))
            if buf:
                try:
                    texts = a if ext == "strings" else _decode_all(buf, src_enc, "." + ext)
                except StringsError:
                    continue
                for t in texts.values():
                    lower_count.update(re.findall(r"\b[a-z]{3,}\b", t))
        used.append(stem)
        for sid, en in a.items():
            it = b.get(sid)
            if it and it != en and looks_like_term(en) and looks_like_term(it[:1].upper() + it[1:]) and len(it) <= MAX_LEN + 20:
                votes.setdefault(en, Counter())[it] += 1
    chosen, ambiguous = {}, 0
    for en, c in votes.items():
        (best, n), total = c.most_common(1)[0], sum(c.values())
        if n * 2 > total:
            chosen[en] = best
        else:
            ambiguous += 1                              # stesso nome con traduzioni diverse: meglio non imporne una
    # Il glossario deve contenere solo ciò che il modello non sa già: tolgo le traduzioni ovvie.
    lexicon = {en.lower(): _words(it)[0] for en, it in chosen.items() if len(_words(en)) == 1 and len(_words(it)) == 1}
    glossary, common, literal = {}, 0, 0
    for en, it in chosen.items():
        if len(_words(en)) == 1 and len(_words(it)) == 1 and lower_count[en.lower()] >= ORDINARY_MIN:
            common += 1                                 # Gold -> Oro: parola comune, una sola parola per lato
        elif is_literal(en, it, lexicon):
            literal += 1                                # Iron Sword -> Spada di Ferro: somma delle parti
        else:
            glossary[en] = it
    info = {"used": used, "missing": missing, "ambiguous": ambiguous, "terms": len(glossary),
            "common": common, "literal": literal}
    if not used:
        raise GlossaryError(
            f"Non ho trovato file Strings in entrambe le lingue ({source} e {target}) in {data}. "
            f"Servono es. Skyrim_{source}.STRINGS e Skyrim_{target}.STRINGS (sciolti in Data/Strings o dentro i .bsa).")
    return dict(sorted(glossary.items())), info
