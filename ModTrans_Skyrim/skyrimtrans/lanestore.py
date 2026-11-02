"""Code salvate su disco (facoltativo): nome, impostazioni e **chiave API**, per ritrovarle al prossimo avvio.

La chiave è salvata in chiaro (cifrarla senza una password dell'utente darebbe solo un'illusione di sicurezza):
il file sta nella cartella personale, con permessi riservati al solo utente dove il sistema li supporta.
L'esistenza del file è il segno che l'utente ha scelto di ricordare le code; cancellarlo = dimenticare tutto.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def lanes_file() -> Path:
    return Path(os.environ.get("SKYRIMTRANS_HOME") or (Path.home() / ".skyrimtrans")) / "lanes.json"


def load() -> list[dict] | None:
    """Le code salvate [{name, s}], oppure None se l'utente non ha scelto di ricordarle (o il file è illeggibile)."""
    try:
        data = json.loads(lanes_file().read_text("utf-8"))
        lanes = data["lanes"]
        return [{"name": str(l["name"]), "s": dict(l["s"])} for l in lanes
                if isinstance(l, dict) and isinstance(l.get("s"), dict) and l.get("name")]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save(lanes: list[dict]) -> None:
    path = lanes_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")      # mkstemp crea il file già riservato al proprietario (0600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "lanes": lanes}, f, ensure_ascii=False)
        os.replace(tmp, path)                                       # scrittura atomica
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def delete() -> None:
    lanes_file().unlink(missing_ok=True)
