"""Cronologia delle mod tradotte: resta su disco tra un avvio e l'altro del programma.

- Risultato scaricabile dal browser: lo zip viene conservato in `<home>/history/<id>.zip`.
- Risultato salvato in una cartella scelta dall'utente: si ricorda solo il percorso; il programma
  non cancella mai quella cartella, nemmeno quando si toglie la voce dalla cronologia.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path

ID_RE = re.compile(r"[0-9a-f]{32}")
MAX_LIST = 100        # avvisi/errori conservati per voce


def history_dir() -> Path:
    return Path(os.environ.get("SKYRIMTRANS_HOME") or (Path.home() / ".skyrimtrans")) / "history"


class History:
    def __init__(self, directory: Path | None = None):
        self.dir = directory or history_dir()
        self._lock = threading.Lock()

    # -- indice
    @property
    def _index(self) -> Path:
        return self.dir / "index.json"

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self._index.read_text("utf-8"))
            return [e for e in data if isinstance(e, dict) and ID_RE.fullmatch(str(e.get("id", "")))]
        except (OSError, ValueError):
            return []

    def _save(self, entries: list[dict]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False)
            os.replace(tmp, self._index)          # scrittura atomica: un crash non lascia un indice a metà
        except OSError:
            Path(tmp).unlink(missing_ok=True)
            raise

    def zip_path(self, entry_id: str) -> Path | None:
        return self.dir / f"{entry_id}.zip" if ID_RE.fullmatch(entry_id) else None

    # -- lettura
    def list(self) -> list[dict]:
        """Voci dalla più recente, con `available` (il file o la cartella esistono ancora) e `size`."""
        with self._lock:
            entries = self._load()
        out = []
        for e in reversed(entries):
            e = dict(e)
            if e.get("mode") == "zip":
                p = self.zip_path(e["id"])
                e["available"] = bool(p and p.is_file())
                e["size"] = p.stat().st_size if e["available"] else 0
            else:
                e["available"] = bool(e.get("saved_to")) and Path(e["saved_to"]).exists()
                e["size"] = 0
            out.append(e)
        return out

    def get(self, entry_id: str) -> dict | None:
        return next((e for e in self.list() if e["id"] == entry_id), None)

    def total_bytes(self) -> int:
        return sum(e["size"] for e in self.list())

    # -- scrittura
    def add(self, entry: dict, zip_src: Path | None = None) -> Path | None:
        """Registra una voce. Con `zip_src` sposta lo zip nella cronologia e ne ritorna il nuovo percorso."""
        entry = dict(entry, finished=time.strftime("%Y-%m-%d %H:%M"))
        for k in ("warnings", "failures"):
            entry[k] = list(entry.get(k) or [])[:MAX_LIST]
        with self._lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            dest = None
            if zip_src is not None:
                dest = self.zip_path(entry["id"])
                try:
                    shutil.move(str(zip_src), str(dest))
                except OSError:
                    dest.unlink(missing_ok=True)
                    raise
            entries = [e for e in self._load() if e["id"] != entry["id"]]
            entries.append(entry)
            self._save(entries)
            return dest

    def delete(self, entry_id: str) -> bool:
        """Toglie la voce e, se è uno zip della cronologia, lo cancella. Le cartelle dell'utente non si toccano."""
        with self._lock:
            entries = self._load()
            keep = [e for e in entries if e["id"] != entry_id]
            if len(keep) == len(entries):
                return False
            p = self.zip_path(entry_id)
            if p:
                p.unlink(missing_ok=True)
            self._save(keep)
            return True

    def clear(self) -> int:
        with self._lock:
            entries = self._load()
            for e in entries:
                p = self.zip_path(e["id"])
                if p:
                    p.unlink(missing_ok=True)
            self._save([])
            return len(entries)
