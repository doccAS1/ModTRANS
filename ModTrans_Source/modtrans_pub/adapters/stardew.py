"""Stardew Valley (SMAPI / Content Patcher): traduce i18n/default.json o inietta direttamente in content.json e manifest.json."""
import json, re
from pathlib import Path

from ..core.fsutil import atomic_write_text, valid_lang
from ..core.models import Unit
from .base import Adapter


def _next_significant(s, j):
    """Indice del primo carattere che non è spazio né commento, a partire da j."""
    n = len(s)
    while j < n:
        if s[j].isspace():
            j += 1
        elif s.startswith("//", j):
            k = s.find("\n", j); j = n if k < 0 else k
        elif s.startswith("/*", j):
            k = s.find("*/", j + 2); j = n if k < 0 else k + 2
        else:
            break
    return j


def load_lenient(path):
    """SMAPI accetta JSON con commenti e virgole finali: li gestiamo senza toccare le stringhe."""
    s = Path(path).read_text(encoding="utf-8-sig")
    out, i, n, instr = [], 0, len(s), False
    while i < n:
        c = s[i]
        if instr:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i + 1]); i += 2; continue
            if c == '"':
                instr = False
            i += 1; continue
        if c == '"':
            instr = True
        elif s.startswith("//", i):
            j = s.find("\n", i); i = n if j < 0 else j; continue
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2); i = n if j < 0 else j + 2; continue
        elif c == ",":                  # virgola finale, anche se seguita da commenti prima della chiusura
            j = _next_significant(s, i + 1)
            if j < n and s[j] in "}]":
                i += 1; continue
        out.append(c); i += 1
    return json.loads("".join(out))


def flatten(d, prefix=""):
    """Appiattisce un dizionario standard i18n."""
    for k, v in d.items():
        if isinstance(v, dict):
            yield from flatten(v, f"{prefix}{k}.")
        else:
            yield f"{prefix}{k}", v


def _looks_like_text(v):
    """Esclude valori che sono dati e non testo (true, numeri, ID qualificati, token, percorsi):
    tradurli rompe la mod."""
    s = v.strip()
    if s.lower() in ("true", "false", "null"):
        return False
    if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
        return False
    if re.fullmatch(r"\(\w+\)\S+", s):          # (O)388
        return False
    if not re.search(r"\s", s) and re.search(r"[_:/(){}]|\w\.\w", s):   # ID, percorsi, {{Token}}_Foo
        return False
    return True


def walk_content(data, path=""):
    """Esplora content.json ed estrae solo le stringhe sicure usando una whitelist."""
    whitelist = {"displayname", "description", "text", "dialogue", "message", "logname"}
    if isinstance(data, dict):
        for k, v in data.items():
            new_path = f"{path}.{k}" if path else str(k)
            if isinstance(v, str) and v.strip():
                if k.lower() in whitelist or (path.lower().endswith("entries") and "/" not in v and _looks_like_text(v)):
                    yield new_path, v
            if isinstance(v, (dict, list)):
                yield from walk_content(v, new_path)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            yield from walk_content(v, f"{path}[{i}]")


def apply_mapping(data, mapping, path=""):
    """Inietta le traduzioni nel json originale seguendo il percorso mappato."""
    if isinstance(data, dict):
        for k, v in data.items():
            new_path = f"{path}.{k}" if path else str(k)
            if new_path in mapping:
                data[k] = mapping[new_path]
            elif isinstance(v, (dict, list)):
                apply_mapping(v, mapping, new_path)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            new_path = f"{path}[{i}]"
            if new_path in mapping:
                data[i] = mapping[new_path]
            elif isinstance(v, (dict, list)):
                apply_mapping(v, mapping, new_path)


class StardewAdapter(Adapter):
    game = "stardew"

    def __init__(self, mod_dir, target_code="it"):
        self.LANG = valid_lang(target_code)
        self.dir = Path(mod_dir)
        m = load_lenient(self.dir / "manifest.json")
        self.mod_id = m.get("UniqueID") or self.dir.name
        self.mod_version = str(m.get("Version", "?"))
        self.mod_name = m.get("Name", self.dir.name)
        
        # --- AI MOD EXCLUSION CHECK ---
        self.ai_allowed = True
        if m.get("DenyAI") is True:
            self.ai_allowed = False
        elif m.get("AllowAI") is False:
            self.ai_allowed = False
            
        self.i18n_src = self.dir / "i18n" / "default.json"
        self.i18n_out = self.dir / "i18n" / f"{self.LANG}.json"
        self.content_src = self.dir / "content.json"
        self.manifest_src = self.dir / "manifest.json"
        
        if self.i18n_src.exists():
            self.mode = "i18n"
        elif self.content_src.exists():
            self.mode = "content"
        else:
            self.mode = "none"

    @classmethod
    def detect(cls, mod_dir):
        return (Path(mod_dir) / "manifest.json").exists()

    def supported(self):
        return self.mode != "none"

    def extract(self):
        units = []
        manifest_data = load_lenient(self.manifest_src)
        if "Description" in manifest_data and isinstance(manifest_data["Description"], str) and manifest_data["Description"].strip():
            units.append(Unit("manifest.Description", manifest_data["Description"], "manifest.json"))
            
        if self.mode == "i18n":
            data = load_lenient(self.i18n_src)
            units.extend([Unit(k, v, "i18n/default.json") for k, v in flatten(data) if isinstance(v, str) and v.strip()])
        elif self.mode == "content":
            data = load_lenient(self.content_src)
            units.extend([Unit(k, v, "content.json") for k, v in walk_content(data) if isinstance(v, str) and v.strip()])
            
        return units

    def read_output(self):
        if self.mode == "i18n":
            return dict(flatten(load_lenient(self.i18n_out))) if self.i18n_out.exists() else {}
        return {} 

    def output_files(self):
        files = ["manifest.json"]
        if self.mode == "i18n":
            files.append(f"i18n/{self.LANG}.json")
        elif self.mode == "content":
            files.append("content.json")
        return files

    def write(self, mapping):
        if "manifest.Description" in mapping:
            m_data = load_lenient(self.manifest_src)
            m_data["Description"] = mapping["manifest.Description"]
            atomic_write_text(self.manifest_src, json.dumps(m_data, ensure_ascii=False, indent=2) + "\n")

        if self.mode == "i18n":
            self.i18n_out.parent.mkdir(exist_ok=True)
            i18n_mapping = {k: v for k, v in mapping.items() if not k.startswith("manifest.")}
            atomic_write_text(self.i18n_out, json.dumps(i18n_mapping, ensure_ascii=False, indent=2) + "\n")
        elif self.mode == "content":
            data = load_lenient(self.content_src)
            apply_mapping(data, mapping)
            atomic_write_text(self.content_src, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


ADAPTERS = {"stardew": StardewAdapter}