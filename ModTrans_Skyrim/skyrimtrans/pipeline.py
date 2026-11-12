"""Orchestrazione: scansiona la mod, estrae le stringhe, traduce, riscrive, verifica."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import bsa as bsa_mod, jsontext, mcm, plugin as pl, strings_file as sf
from .context import offline_facts, plugin_info
from .common import Unit
from .protect import ProtectionError, fit_encoding, protect, remask
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
    from_memory: int = 0   # stringhe riprese dalla memoria delle traduzioni (nessuna richiesta)
    requests: int = 0      # richieste fatte al servizio AI
    shortened: int = 0     # testi d'interfaccia accorciati perché troppo lunghi
    qa_checked: int = 0    # stringhe riviste dal secondo passaggio (--review)
    qa_fixed: int = 0      # stringhe corrette dalla revisione
    json_fields: list = field(default_factory=list)   # campi dei JSON: percorso, quanti, tradotto sì/no, chi ha deciso, esempi


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


def _wanted(rel: str, src_name: str) -> bool:
    """Un file sciolto che ci interessa: plugin, Strings nella lingua originale, menu MCM nella lingua originale."""
    p = Path(rel)
    ext = p.suffix.lower()
    if ext in PLUGIN_EXT:
        return True
    if ext in STRINGS_EXT:
        return bool(re.search(f"_{src_name}$", p.stem, re.I))
    if ext == ".json":
        return True                              # si guarda dentro: conta solo se ha battute ("lines" con "id" e "text")
    return ext == ".txt" and "interface/translations" in rel.lower() and mcm.split_name(p.name)[1] == src_name


def _from_archives(root: Path, loose: dict, src_name: str, rep) -> list:
    """File Strings e MCM che stanno dentro i .bsa della mod (a meno che esista già lo stesso file sciolto)."""
    found = []
    for p in sorted(root.rglob("*")):
        if not (p.is_file() and p.suffix.lower() == ".bsa"):
            continue
        try:
            archive = bsa_mod.Bsa(p)
            n = 0
            for e in archive.entries:
                if not (e.path.startswith(("strings/", "interface/translations/")) and _wanted(e.path, src_name)):
                    continue
                rel = e.path.replace("strings/", "Strings/", 1).replace("interface/translations/",
                                                                        "Interface/Translations/", 1)
                if rel.lower() in loose:
                    continue                       # il file sciolto ha la precedenza, come nel gioco
                found.append((rel, archive.read(e), p.name))
                n += 1
        except (bsa_mod.BsaError, OSError) as ex:
            rep.warnings.append(f"{p.name}: archivio non leggibile ({ex}): se contiene file Strings, non verranno tradotti")
    return found


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


_OUT_LOCK = threading.Lock()      # code in parallelo: due mod con lo stesso nome non devono scegliere lo stesso nome libero


def write_output(out: Path, dest: Path, as_folder: bool, overwrite: bool = False) -> Path:
    """Scrive il risultato come zip o come cartella. Di default non sovrascrive: sceglie un nome libero."""
    with _OUT_LOCK:
        return _write_output(out, dest, as_folder, overwrite)


def _write_output(out: Path, dest: Path, as_folder: bool, overwrite: bool = False) -> Path:
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


def _json_jobs(pending, translator, rep, mode, include, exclude):
    """Decide quali campi dei JSON tradurre: battute note (lines/text con id) sempre; il resto lo decide l'AI
    (mode 'auto') guardando i percorsi e qualche esempio, con ripiego su nomi di campo tipici se non risponde."""
    import fnmatch
    known_by_file, groups_by_file, merged = {}, {}, {}
    for rel, text, e, bom, found, data in pending:
        known = {p for p in found if jsontext.is_known_line(p, found) and found[p][2].strip()}
        known_by_file[rel] = known
        groups_by_file[rel] = jsontext.groups(found, {p for p in found if jsontext.is_known_line(p, found)})
        for pat, g in groups_by_file[rel].items():
            m = merged.setdefault(pat, {"count": 0, "samples": [], "files": []})
            m["count"] += g["count"]
            for s in g["samples"]:
                if s not in m["samples"] and len(m["samples"]) < 5:
                    m["samples"].append(s)
            if rel not in m["files"] and len(m["files"]) < 3:
                m["files"].append(rel)
    decision: dict[str, tuple[bool, str]] = {}
    for pat in merged:
        if any(fnmatch.fnmatch(pat, x) for x in exclude):
            decision[pat] = (False, "escluso da te")
        elif any(fnmatch.fnmatch(pat, x) for x in include):
            decision[pat] = (True, "scelto da te")
    todo = [p for p in merged if p not in decision]
    if todo and mode == "auto" and translator is not None:
        asked = translator.classify_fields([
            {"id": i, "path": pat, "occurrences": merged[pat]["count"], "files": merged[pat]["files"],
             "samples": merged[pat]["samples"]} for i, pat in enumerate(todo)])
        if not asked:
            rep.warnings.append("JSON: l'AI non ha classificato i campi: uso un ripiego sui nomi di campo tipici "
                                "(text, answer, question, label...). Controlla l'elenco dei campi tradotti.")
        for i, pat in enumerate(todo):
            if i in asked:
                decision[pat] = (asked[i], "AI")
            else:
                decision[pat] = (jsontext.looks_like_text(pat, merged[pat]["samples"]), "ripiego")
    for pat in todo:
        if pat not in decision:                      # senza AI (anteprima) o in modalità "known"
            decision[pat] = ((jsontext.looks_like_text(pat, merged[pat]["samples"]), "ripiego")
                             if mode == "auto" else (False, "non analizzato"))
    jobs, units = [], []
    for rel, text, e, bom, found, data in pending:
        paths = sorted(known_by_file[rel])
        for pat, g in groups_by_file[rel].items():
            if decision[pat][0]:
                paths += g["paths"]
        parsed = (found, sorted(set(paths), key=lambda p: found[p][0]))
        u = jsontext.extract_units(parsed, rel)
        if u:
            jobs.append(("json", rel, (text, e, bom, parsed), data))
            units += u
    nknown = sum(len(v) for v in known_by_file.values())
    if nknown:
        rep.json_fields.append({"path": "lines[].text (con id)", "count": nknown, "translate": True, "by": "schema noto",
                                "samples": []})
    for pat, m in merged.items():
        rep.json_fields.append({"path": pat, "count": m["count"], "translate": decision[pat][0], "by": decision[pat][1],
                                "samples": m["samples"][:3]})
    yes = [f"{f['path']} ({f['count']})" for f in rep.json_fields if f["translate"]]
    no = [f"{f['path']} ({f['count']})" for f in rep.json_fields if not f["translate"]]
    if yes or no:
        cut = lambda L: ", ".join(L[:12]) + (f" … (+{len(L) - 12})" if len(L) > 12 else "")
        if yes:
            rep.warnings.append("Info: campi JSON tradotti: " + cut(yes))
        if no:
            rep.warnings.append("Info: campi JSON lasciati com'erano (dati della mod): " + cut(no))
    return jobs, units


_TRIVIAL = ("vuota", "chiave di traduzione ($KEY)", "nessun testo da tradurre")


class Project:
    """Una mod aperta: stringhe estratte, traduzioni (dell'AI e scritte a mano) e riscrittura dei file.

    Serve sia a `run()` (apri → traduci → scrivi) sia all'editor della pagina, che mostra le righe prima, durante e
    dopo la traduzione, permette di correggerle a mano o di tradurne solo alcune, e riscrive il risultato."""

    def __init__(self, src: Path, target: str, source: str = "english", json_mode: str = "auto",
                 json_include=(), json_exclude=(), translator: Translator | None = None):
        self.target, self.source = target.lower(), source.lower()
        self.tgt_name, self.enc = LANGS[self.target]
        self.src_name, _ = LANGS[self.source]
        self.json_mode, self.json_include, self.json_exclude = json_mode, tuple(json_include), tuple(json_exclude)
        self.lock = threading.RLock()
        self.auto: dict[tuple, str] = {}        # traduzioni dell'AI, per (file, posizione)
        self.manual: dict[tuple, str] = {}      # traduzioni scritte a mano: hanno la precedenza
        self.why: dict[tuple, str] = {}         # perché una riga non è stata tradotta
        self.stats: dict = {}
        self.tr_warnings: list[str] = []
        self._skip: dict[tuple, bool] = {}
        self.live: dict | None = None           # cache del traduttore in corso (righe già tradotte, non ancora consolidate)
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name)
        try:
            self.root = prepare_input(src, self.work)
            self._collect()
        except BaseException:
            self.close()
            raise
        self.classify(translator)

    def close(self) -> None:
        self._tmp.cleanup()

    # ------------------------------------------------------------------ analisi
    def _collect(self) -> None:
        enc, src_name, rep = self.enc, self.src_name, Report()
        self.rep = rep
        sources, loose = [], {}  # (relpath, dati originali, archivio)
        for p in sorted(self.root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(self.root).as_posix()
                loose[rel.lower()] = rel
                sources.append((rel, p.read_bytes() if _wanted(rel, src_name) else None, None))
        sources += _from_archives(self.root, loose, src_name, rep)
        self._fixed_jobs, self._fixed_units, self._json_pending = [], [], []
        for rel, data, origin in sources:
            ext = Path(rel).suffix.lower()
            if data is None:
                continue
            try:
                if ext in PLUGIN_EXT:
                    obj = pl.Plugin(data)
                    u, w = pl.extract_units(obj, enc, rel)
                    self._fixed_jobs.append(("plugin", rel, obj, data))
                elif ext in STRINGS_EXT:
                    obj = sf.StringsFile(data, ext)
                    u, w = sf.extract_units(obj, enc, rel, ext[1:])
                    self._fixed_jobs.append(("strings", rel, obj, data))
                elif ext == ".json":
                    if len(data) > 30_000_000:
                        continue
                    text, e, bom = mcm.decode(data)
                    try:
                        found = jsontext.scan(text)
                    except (jsontext.JsonError, ValueError, IndexError) as ex:
                        if '"lines"' in text or '"text"' in text:
                            rep.warnings.append(f"{rel}: JSON non analizzabile, copiato senza modifiche ({ex})")
                        continue
                    self._json_pending.append((rel, text, e, bom, found, data))
                    continue
                else:
                    text, e, bom = mcm.decode(data)
                    u, w = mcm.extract_units(text, rel), []
                    self._fixed_jobs.append(("mcm", rel, (text, e, bom), data))
            except (pl.PluginError, sf.StringsError, UnicodeError, bsa_mod.BsaError) as e:
                rep.warnings.append(f"{rel}: non analizzabile, copiato senza modifiche ({e})")
                continue
            if origin:
                rep.warnings.append(f"Info: {rel} letto dall'archivio {origin}")
            rep.warnings += w
            self._fixed_units += u

    def ensure_brief(self, translator: Translator) -> None:
        if not translator.brief:  # contesto minimo sempre disponibile: autore, descrizione, dipendenze
            translator.set_brief(offline_facts(
                [plugin_info(obj, rel, self.enc) for k, rel, obj, _ in self._fixed_jobs if k == "plugin"]))

    def classify(self, translator: Translator | None) -> None:
        """Decide quali campi dei JSON sono testo (con l'AI se c'è un traduttore, altrimenti con il ripiego)."""
        self._jrep = Report()
        jj, ju = [], []
        if self._json_pending:
            if translator is not None:
                self.ensure_brief(translator)
            jj, ju = _json_jobs(self._json_pending, translator, self._jrep, self.json_mode,
                                self.json_include, self.json_exclude)
        self.jobs = self._fixed_jobs + jj
        self.units: list[Unit] = self._fixed_units + ju
        kinds = {k for k, *_ in self.jobs}
        localized = [rel for k, rel, obj, _ in self.jobs if k == "plugin" and obj.localized]
        self._localized_warning = []
        if localized and "strings" not in kinds:
            self._localized_warning.append(
                f"{', '.join(localized)}: plugin localizzato, ma non ho trovato file Strings in "
                f"{self.source.capitalize()} né sciolti né dentro i .bsa: per questo plugin non c'è nulla da tradurre")

    @staticmethod
    def key(u: Unit) -> tuple:
        return (u.file, repr(u.locator))

    # ------------------------------------------------------------------ traduzione
    def translate(self, translator: Translator, progress=None, only=None) -> None:
        """Traduce con l'AI le righe indicate (`only` = posizioni; None = tutte), tranne quelle scritte a mano."""
        self.ensure_brief(translator)
        self.live = translator.cache
        units = [u for i, u in enumerate(self.units)
                 if (only is None or i in only) and self.key(u) not in self.manual]
        fit, same = (lambda s: fit_encoding(s, self.enc)), (lambda s: s)
        results: dict = {}
        for sel, f in (([u for u in units if u.kind not in ("ui_label", "json_dialogue")], fit),
                       ([u for u in units if u.kind == "ui_label"], same),    # MCM e JSON sono unicode: nessun vincolo
                       ([u for u in units if u.kind == "json_dialogue"], same)):
            results.update(translator.translate_all([(u.kind, u.text) for u in sel], f, progress))
        with self.lock:
            for u in units:
                k = (u.kind, u.text)
                if k in results:
                    self.auto[self.key(u)] = results[k]
                    self.why.pop(self.key(u), None)
                else:
                    self.auto.pop(self.key(u), None)
                    self.why[self.key(u)] = translator.failed.get(k, "non tradotta")
            for k, v in translator.stats.items():
                self.stats[k] = self.stats.get(k, 0) + v if k in ("requests", "from_memory", "shortened", "qa_checked",
                                                                  "qa_fixed", "retries") else v
            self.tr_warnings = list(dict.fromkeys(self.tr_warnings + translator.warnings))
        self.live = None

    def effective(self, u: Unit) -> str | None:
        return self.manual.get(self.key(u)) or self.auto.get(self.key(u))

    def edit(self, i: int, text: str) -> str | None:
        """Traduzione scritta a mano per la riga `i`. Ritorna il motivo del rifiuto, oppure None se va bene.
        Testo vuoto = si torna alla traduzione dell'AI (o all'originale)."""
        u = self.units[i]
        with self.lock:
            if not text.strip():
                self.manual.pop(self.key(u), None)
                return None
            p = protect(u.text)
            if p.skip_reason:
                return f"Questa riga non si traduce ({p.skip_reason})."
            nl = "\r\n" if "\r\n" in u.text else ("\r" if "\r" in u.text and "\n" not in u.text else "\n")
            text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", nl)
            if remask(p, text) is None:
                return ("Tag, variabili o a capo diversi dall'originale: devono restare uguali "
                        "(per esempio <Alias=Player>, %s, [PLAYERNAME]).")
            if u.kind not in ("ui_label", "json_dialogue"):
                try:
                    fit_encoding(text, self.enc)
                except ProtectionError as e:
                    return str(e)
            self.manual[self.key(u)] = p.lead + text.strip() + p.trail
        return None

    def _row(self, u: Unit, live: dict):
        key = self.key(u)
        if key in self.manual:
            return self.manual[key], "edited", None
        if key in self.auto:
            return self.auto[key], "done", None
        if (u.kind, u.text) in live:
            return live[(u.kind, u.text)], "done", None
        why = self.why.get(key)
        if key not in self._skip:
            self._skip[key] = bool(protect(u.text).skip_reason)
        if why in _TRIVIAL or self._skip[key]:
            return None, "skip", why
        return None, ("failed" if why else "todo"), why

    @staticmethod
    def _match(u: Unit, tr, q: str, state: str, file: str, st: str) -> bool:
        if file and u.file != file or state and st != state:
            return False
        return not q or q in u.text.lower() or (tr is not None and q in tr.lower())

    def page(self, offset: int = 0, limit: int = 100, q: str = "", state: str = "", file: str = "") -> dict:
        """Una pagina di righe (originale + traduzione + stato) con filtri, i conteggi per stato e l'elenco dei file."""
        live, q = self.live or {}, q.strip().lower()
        counts: dict[str, int] = {}
        hits = []
        for i, u in enumerate(self.units):
            tr, st, why = self._row(u, live)
            counts[st] = counts.get(st, 0) + 1
            if self._match(u, tr, q, state, file, st):
                hits.append((i, u, tr, st, why))
        rows = [{"i": i, "file": u.file, "kind": u.kind, "orig": u.text, "tr": tr, "state": st, "why": why}
                for i, u, tr, st, why in hits[offset:offset + limit]]
        return {"total": len(self.units), "matched": len(hits), "counts": counts, "rows": rows,
                "files": sorted({u.file for u in self.units})}

    def select(self, q: str = "", state: str = "", file: str = "") -> list[int]:
        """Posizioni delle righe che corrispondono ai filtri (per tradurle in blocco)."""
        live, q = self.live or {}, q.strip().lower()
        out = []
        for i, u in enumerate(self.units):
            tr, st, _ = self._row(u, live)
            if st != "skip" and self._match(u, tr, q, state, file, st):
                out.append(i)
        return out

    # ------------------------------------------------------------------ scrittura
    def build(self, dest: Path, as_folder: bool = False, overwrite: bool = False) -> Report:
        """Riscrive i file con le traduzioni attuali (anche quelle a mano) e produce lo zip o la cartella."""
        with self.lock:
            return self._build(dest, as_folder, overwrite)

    def _build(self, dest: Path, as_folder: bool, overwrite: bool) -> Report:
        enc, src_name, tgt_name = self.enc, self.src_name, self.tgt_name
        rep = Report()
        rep.warnings = list(self.rep.warnings) + list(self._jrep.warnings) + list(self._localized_warning)
        rep.json_fields = list(self._jrep.json_fields)
        out = self.work / "out"
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(self.root, out)

        def lookup(u: Unit):
            t = self.effective(u)
            if t is None:
                why = self.why.get(self.key(u), "non tradotta")
                if why not in _TRIVIAL:
                    rep.kept_original += 1                 # le stringhe vuote/chiavi non sono "mancate": non c'era nulla da tradurre
                    rep.failures.append(f"{u.file} [{u.kind}] {u.text[:60]!r}: {why}")
            else:
                rep.translated += 1
            return t

        for kind, rel, obj, orig in self.jobs:
            units = [u for u in self.units if u.file == rel]
            changes = {u.locator: t for u in units if (t := lookup(u)) is not None}
            if not changes:
                continue
            if kind == "plugin":
                errs = pl.apply_units(obj, changes, enc)
                new = obj.to_bytes()
                bad = errs + pl.verify_plugin(orig, new, enc)
                if bad:
                    rep.failures += [f"{rel}: {b}" for b in bad]
                    rep.warnings.append(f"{rel}: verifica fallita, file lasciato ORIGINALE")
                    continue
                (out / rel).write_bytes(new)
            elif kind == "strings":
                new = sf.apply_units(obj, changes, enc)
                bad = sf.verify_strings(orig, new, Path(rel).suffix, enc)
                if bad:
                    rep.failures += [f"{rel}: {b}" for b in bad]
                    continue
                newrel = _target_name(rel, src_name, tgt_name)
                (out / newrel).parent.mkdir(parents=True, exist_ok=True)
                (out / newrel).write_bytes(new)
                rel = newrel
            elif kind == "json":
                text, e, bom, parsed = obj
                new_text = jsontext.apply_units(text, parsed, changes)
                bad = jsontext.verify(text, new_text, parsed)
                if bad:
                    rep.failures += [f"{rel}: {b}" for b in bad]
                    rep.warnings.append(f"{rel}: verifica fallita, file lasciato ORIGINALE")
                    continue
                (out / rel).write_bytes(mcm.encode(new_text, e, bom))
            else:
                text, e, bom = obj
                new_text = mcm.apply_units(text, changes)
                bad = mcm.verify(text, new_text)
                if bad:
                    rep.failures += [f"{rel}: {b}" for b in bad]
                    continue
                newrel = _target_name(rel, src_name, tgt_name)
                (out / newrel).parent.mkdir(parents=True, exist_ok=True)
                (out / newrel).write_bytes(mcm.encode(new_text, e, bom))
                rel = newrel
            rep.files.append(rel)

        s = self.stats
        rep.from_memory, rep.requests = s.get("from_memory", 0), s.get("requests", 0)
        rep.shortened, rep.qa_checked, rep.qa_fixed = (s.get(k, 0) for k in ("shortened", "qa_checked", "qa_fixed"))
        rep.warnings += [f"Controllo: {w}" for w in self.tr_warnings]
        rep.output = str(write_output(out, dest, as_folder, overwrite))
        shutil.rmtree(out, ignore_errors=True)
        return rep


def run(src: Path, dest: Path, translator: Translator, target: str,
        source: str = "english", progress=None, as_folder: bool = False, overwrite: bool = False,
        json_mode: str = "auto", json_include=(), json_exclude=()) -> Report:
    proj = Project(src, target, source, json_mode, json_include, json_exclude, translator=translator)
    try:
        proj.translate(translator, progress)
        return proj.build(dest, as_folder, overwrite)
    finally:
        proj.close()
