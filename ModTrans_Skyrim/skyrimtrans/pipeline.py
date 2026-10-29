"""Orchestrazione: scansiona la mod, estrae le stringhe, traduce, riscrive, verifica."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import mcm, plugin as pl, strings_file as sf
from .context import offline_facts, plugin_info
from .common import Unit
from .protect import fit_encoding
from .translator import Translator

LANGS = {  # lingua -> (nome file Skyrim, codifica del gioco)
    "english": ("ENGLISH", "cp1252"), "french": ("FRENCH", "cp1252"),
    "german": ("GERMAN", "cp1252"), "italian": ("ITALIAN", "cp1252"),
    "spanish": ("SPANISH", "cp1252"), "russian": ("RUSSIAN", "cp1251"),
    "polish": ("POLISH", "cp1250"), "czech": ("CZECH", "cp1250"),
}
PLUGIN_EXT = {".esp", ".esm", ".esl"}
STRINGS_EXT = {".strings", ".dlstrings", ".ilstrings"}


@dataclass
class Report:
    translated: int = 0
    kept_original: int = 0
    files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    output: str = ""   # percorso finale del risultato (zip o cartella)


def safe_extract(zip_path: Path, dest: Path) -> None:
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for m in z.infolist():
            target = (dest / m.filename).resolve()
            if dest != target and dest not in target.parents:
                raise ValueError(f"percorso non sicuro nello zip: {m.filename}")
        z.extractall(dest)


def prepare_input(src: Path, work: Path) -> Path:
    root = work / "in"
    root.mkdir()
    if src.is_dir():
        shutil.copytree(src, root, dirs_exist_ok=True)
    elif src.suffix.lower() in {".zip"}:
        safe_extract(src, root)
    elif src.suffix.lower() == ".7z":
        try:
            import py7zr
        except ImportError:
            raise ValueError("per i .7z serve: pip install py7zr")
        with py7zr.SevenZipFile(src) as z:
            base = root.resolve()
            for n in z.getnames():
                t = (base / n).resolve()
                if t != base and base not in t.parents:
                    raise ValueError(f"percorso non sicuro nel 7z: {n}")
            z.extractall(root)
    elif src.suffix.lower() in PLUGIN_EXT:
        shutil.copy2(src, root / src.name)
    else:
        raise ValueError("formati supportati: cartella, .zip, .7z, .esp/.esm/.esl")
    return root


_NEXUS_TAIL = re.compile(r"-\d{3,7}-\d+(?:-\d+){0,3}-\d{9,11}$")


def clean_name(filename: str) -> str:
    """Nome leggibile dal file scaricato: toglie estensione, ID/versione/timestamp di Nexus e caratteri vietati."""
    stem = _NEXUS_TAIL.sub("", Path(filename).stem)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")
    return stem or "mod"


def unique_path(p: Path) -> Path:
    """Se `p` esiste già, aggiunge ' (2)', ' (3)'... prima dell'estensione: non si sovrascrive mai nulla."""
    if not p.exists():
        return p
    stem, suffix = (p.name, "") if p.is_dir() or not p.suffix else (p.stem, p.suffix)
    n = 2
    while True:
        cand = p.with_name(f"{stem} ({n}){suffix}")
        if not cand.exists():
            return cand
        n += 1


class OutputError(ValueError):
    """Problema con la cartella o il file di output (messaggio già chiaro per l'utente)."""


def check_writable_dir(d: Path) -> Path:
    """Crea la cartella se serve e verifica che si possa scrivere. ValueError con messaggio chiaro."""
    d = d.expanduser()
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / f".skyrimtrans_{os.getpid()}.tmp"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as e:
        raise OutputError(f"Non posso scrivere nella cartella {d}: {e.strerror or e}") from None
    return d


def write_output(out: Path, dest: Path, as_folder: bool, overwrite: bool = False) -> Path:
    """Scrive il risultato come zip o come cartella. Di default non sovrascrive: sceglie un nome libero."""
    if not overwrite:
        dest = unique_path(dest)
    elif dest.exists():
        shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if as_folder:
        shutil.copytree(out, dest)
    else:
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(out).as_posix())
    return dest


def _target_name(name: str, src_lang: str, tgt_lang: str) -> str:
    return re.sub(re.escape(src_lang), tgt_lang, name, flags=re.IGNORECASE)


def run(src: Path, dest: Path, translator: Translator, target: str,
        source: str = "english", progress=None, as_folder: bool = False, overwrite: bool = False) -> Report:
    tgt_name, enc = LANGS[target.lower()]
    src_name, _ = LANGS[source.lower()]
    rep = Report()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        root = prepare_input(src, work)
        out = work / "out"
        shutil.copytree(root, out)

        jobs = []  # (kind di file, relpath, dati)
        all_units: list[Unit] = []
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            ext = p.suffix.lower()
            try:
                if ext in PLUGIN_EXT:
                    obj = pl.Plugin(p.read_bytes())
                    u, w = pl.extract_units(obj, enc, rel)
                    jobs.append(("plugin", rel, obj))
                elif ext in STRINGS_EXT and re.search(f"_{src_name}$", p.stem, re.I):
                    obj = sf.StringsFile(p.read_bytes(), ext)
                    u, w = sf.extract_units(obj, enc, rel, ext[1:])
                    jobs.append(("strings", rel, obj))
                elif ext == ".txt" and "interface/translations" in rel.lower() and \
                        mcm.split_name(p.name)[1] == src_name:
                    text, e, bom = mcm.decode(p.read_bytes())
                    u, w = mcm.extract_units(text, rel), []
                    jobs.append(("mcm", rel, (text, e, bom)))
                else:
                    continue
            except (pl.PluginError, sf.StringsError, UnicodeError) as e:
                rep.warnings.append(f"{rel}: non analizzabile, copiato senza modifiche ({e})")
                continue
            rep.warnings += w
            all_units += u

        if not translator.brief:  # contesto minimo sempre disponibile: autore, descrizione, dipendenze
            translator.set_brief(offline_facts(
                [plugin_info(obj, rel, enc) for k, rel, obj in jobs if k == "plugin"]))

        fit = lambda s: fit_encoding(s, enc)
        mcm_fit = lambda s: s
        # MCM è unicode: nessun vincolo di codifica
        by_kind = {"mcm": [x for x in all_units if x.kind == "ui_label"]}
        main = [x for x in all_units if x.kind != "ui_label"]
        results = {}
        results.update(translator.translate_all([(u.kind, u.text) for u in main], fit, progress))
        results.update(translator.translate_all([(u.kind, u.text) for u in by_kind["mcm"]], mcm_fit, progress))

        def lookup(u: Unit):
            t = results.get((u.kind, u.text))
            if t is None:
                rep.kept_original += 1
                why = translator.failed.get((u.kind, u.text), "non tradotta")
                if why not in ("vuota", "chiave di traduzione ($KEY)", "nessun testo da tradurre"):
                    rep.failures.append(f"{u.file} [{u.kind}] {u.text[:60]!r}: {why}")
            else:
                rep.translated += 1
            return t

        for kind, rel, obj in jobs:
            units = [u for u in all_units if u.file == rel]
            changes = {u.locator: t for u in units if (t := lookup(u)) is not None}
            if not changes:
                continue
            orig_path = root / rel
            if kind == "plugin":
                errs = pl.apply_units(obj, changes, enc)
                new = obj.to_bytes()
                bad = errs + pl.verify_plugin(orig_path.read_bytes(), new, enc)
                if bad:
                    rep.failures += [f"{rel}: {b}" for b in bad]
                    rep.warnings.append(f"{rel}: verifica fallita, file lasciato ORIGINALE")
                    continue
                (out / rel).write_bytes(new)
            elif kind == "strings":
                new = sf.apply_units(obj, changes, enc)
                bad = sf.verify_strings(orig_path.read_bytes(), new, Path(rel).suffix, enc)
                if bad:
                    rep.failures += [f"{rel}: {b}" for b in bad]
                    continue
                newrel = _target_name(rel, src_name, tgt_name)
                (out / newrel).parent.mkdir(parents=True, exist_ok=True)
                (out / newrel).write_bytes(new)
                rel = newrel
            else:
                text, e, bom = obj
                new_text = mcm.apply_units(text, changes)
                bad = mcm.verify(text, new_text)
                if bad:
                    rep.failures += [f"{rel}: {b}" for b in bad]
                    continue
                newrel = _target_name(rel, src_name, tgt_name)
                (out / newrel).write_bytes(mcm.encode(new_text, e, bom))
                rel = newrel
            rep.files.append(rel)

        rep.output = str(write_output(out, dest, as_folder, overwrite))
    return rep
