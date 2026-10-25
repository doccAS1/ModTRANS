"""Manifest per-mod + backup/restore."""
import hashlib, json, re, shutil, time
from pathlib import Path

TOOL_VERSION = "0.1.0"


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:12]


class Project:
    def __init__(self, workdir, game, mod_id, mod_version, existing_output_keys=(), lang="it"):
        safe = re.sub(r"[^\w.-]+", "_", mod_id)
        if lang != "it":            # "it" mantiene il percorso storico, così i backup vecchi restano validi
            safe = f"{safe}__{re.sub(r'[^\w-]+', '_', lang)}"
        self.dir = Path(workdir) / "projects" / game / safe
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "manifest.json"
        if self.path.exists():
            self.m = json.load(open(self.path, encoding="utf-8"))
        else:  # prima volta: ciò che esiste già nel file di output della lingua è dell'autore, non nostro
            self.m = {"game": game, "mod_id": mod_id, "foreign_keys": sorted(existing_output_keys),
                      "units": {}}
        self.m["mod_version"] = mod_version
        self.m["tool_version"] = TOOL_VERSION

    @property
    def foreign(self):
        return set(self.m["foreign_keys"])

    def unit(self, key):
        return self.m["units"].get(key)

    def set_unit(self, key, source, dst, decision, gloss, issues=(), attempts=0, via="llm"):
        self.m["units"][key] = {"src_hash": sha(source), "src": source, "dst": dst,
                                "decision": decision, "glossary": gloss, "issues": list(issues),
                                "attempts": attempts, "via": via,
                                "updated": time.strftime("%Y-%m-%d %H:%M:%S")}

    def prune(self, valid_keys):
        for k in [k for k in self.m["units"] if k not in valid_keys]:
            del self.m["units"][k]

    def save(self, **extra):
        self.m.update(extra)
        json.dump(self.m, open(self.path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def save_review(self):
        q = {k: v for k, v in self.m["units"].items()
             if v["decision"] in ("REVISION", "BLOCK", "PUBLISH_WITH_NOTE")}
        json.dump(q, open(self.dir / "review.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return q

    # --- backup ---
    def backup(self, mod_dir, rel_paths):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        b = self.dir / "backups" / stamp
        rec = {"existing": [], "created": []}
        for rel in rel_paths:
            src = Path(mod_dir) / rel
            if src.exists():
                (b / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, b / rel)
                rec["existing"].append(rel)
            else:
                rec["created"].append(rel)
        b.mkdir(parents=True, exist_ok=True)
        json.dump(rec, open(b / "backup.json", "w"))

    def restore_latest(self, mod_dir):
        root = self.dir / "backups"
        if not root.exists() or not any(root.iterdir()):
            return False
        b = sorted(root.iterdir())[-1]
        rec = json.load(open(b / "backup.json"))
        for rel in rec["existing"]:
            shutil.copy2(b / rel, Path(mod_dir) / rel)
        for rel in rec["created"]:
            (Path(mod_dir) / rel).unlink(missing_ok=True)
        shutil.rmtree(b)
        return True
