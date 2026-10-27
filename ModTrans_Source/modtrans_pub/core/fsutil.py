"""Utilità sicure per il file system: scritture atomiche, codici lingua, estrazione zip."""
import os, re, shutil, zipfile
from pathlib import Path

LANG_RX = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8}){0,2}$")


def valid_lang(code):
    """Il codice lingua finisce nel nome di un file (i18n/<code>.json): niente percorsi."""
    if not isinstance(code, str) or not LANG_RX.fullmatch(code):
        raise ValueError(f"invalid language code: {code!r}")
    return code


def atomic_write_text(path, text, encoding="utf-8"):
    """Scrive su un file temporaneo e lo sostituisce: un crash a metà non lascia file troncati."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)


def safe_extract_zip(zpath, dest, max_total=2 * 1024 ** 3, max_entries=20000):
    """Estrae uno zip rifiutando percorsi fuori da `dest` (zip-slip) e archivi
    che si espandono oltre i limiti (zip bomb). Il limite è sui byte realmente scritti,
    non su quelli dichiarati nell'header, che un archivio ostile può falsificare."""
    dest = Path(dest)
    created = not dest.exists()
    dest.mkdir(parents=True, exist_ok=True)
    root, total = dest.resolve(), 0
    try:
        with zipfile.ZipFile(zpath) as z:
            infos = z.infolist()
            if len(infos) > max_entries:
                raise ValueError(f"archive has too many entries ({len(infos)} > {max_entries})")
            for info in infos:
                target = (root / info.filename).resolve()
                if not target.is_relative_to(root):
                    raise ValueError(f"unsafe path in archive: {info.filename}")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(target, "wb") as out:
                    while chunk := src.read(1 << 20):
                        total += len(chunk)
                        if total > max_total:
                            raise ValueError("archive is too large once extracted (possible zip bomb)")
                        out.write(chunk)
    except BaseException:
        if created:
            shutil.rmtree(dest, ignore_errors=True)
        raise
    return dest
