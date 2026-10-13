"""Stardew Valley (SMAPI / Content Patcher): traduce i18n/default.json o inietta direttamente in content.json e manifest.json."""
import json, re
from pathlib import Path

from ..core.models import Unit
from .base import Adapter


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
        elif c == "," and re.match(r"\s*[}\]]", s[i + 1:i + 200]):
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


def walk_content(data, path=""):
    """Esplora content.json ed estrae solo le stringhe sicure usando una whitelist."""
    whitelist = {"displayname", "description", "text", "dialogue", "message", "logname"}
    if isinstance(data, dict):
        for k, v in data.items():
            new_path = f"{path}.{k}" if path else str(k)
            if isinstance(v, str) and v.strip():
                if k.lower() in whitelist or (path.lower().endswith("entries") and "/" not in v):
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
        self.LANG = target_code
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
            self.manifest_src.write_text(json.dumps(m_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if self.mode == "i18n":
            self.i18n_out.parent.mkdir(exist_ok=True)
            i18n_mapping = {k: v for k, v in mapping.items() if not k.startswith("manifest.")}
            self.i18n_out.write_text(json.dumps(i18n_mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif self.mode == "content":
            data = load_lenient(self.content_src)
            apply_mapping(data, mapping)
            self.content_src.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


ADAPTERS = {"stardew": StardewAdapter}