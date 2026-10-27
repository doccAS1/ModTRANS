"""Manifest per-mod + backup/restore."""
import hashlib, json, re, shutil, time
from pathlib import Path

from .fsutil import atomic_write_text

TOOL_VERSION = "0.1.0"


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:12]


def safe_id(mod_id):
    safe = re.sub(r"[^\w.-]+", "_", mod_id)
    return safe if safe.strip(".") else "_"       # "." e ".." non devono diventare percorsi


class Originals:
    """Testi ORIGINALI delle stringhe che il tool riscrive sul posto (Description del manifest,
    content.json). Sono per mod e non dipendono dalla lingua di destinazione: così un run non parte
    mai da un testo già tradotto, nemmeno passando da una lingua all'altra (it -> fr -> it).

    Per ogni chiave: {"orig": testo originale, "written": [testi che abbiamo scritto noi]}.
    Se il testo sul disco è l'originale o uno dei nostri, la sorgente è l'originale; se è un testo
    diverso, l'autore ha aggiornato la mod e il nuovo testo diventa l'originale."""
    MAX_WRITTEN = 50

    def __init__(self, workdir, game, mod_id):
        self.mod_id = mod_id
        self.game_dir = Path(workdir) / "projects" / game
        self.safe = safe_id(mod_id)
        self.path = self.game_dir / self.safe / "originals.json"
        self.d, self._projects = {}, None
        if self.path.exists():
            try:
                self.d = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.d = {}            # registro rovinato: si riparte dai manifest dei progetti

    def _known_pairs(self, key):
        """(originale, traduzione) già nei manifest di tutte le lingue di questa mod: serve a
        riconoscere l'output di versioni del tool che non avevano ancora questo registro."""
        if self._projects is None:
            self._projects = []
            if self.game_dir.exists():
                for d in self.game_dir.iterdir():
                    if d.name != self.safe and not d.name.startswith(self.safe + "__"):
                        continue
                    try:
                        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    if m.get("mod_id") == self.mod_id:
                        self._projects.append(m.get("units", {}))
        return [(u["src"], u["dst"]) for units in self._projects
                if (u := units.get(key)) and u.get("src") and u.get("dst") and u["src"] != u["dst"]]

    def resolve(self, key, disk_text):
        e = self.d.get(key)
        if e and (disk_text == e["orig"] or disk_text in e["written"]):
            return e["orig"]
        pairs = self._known_pairs(key)
        for src, dst in pairs:
            if dst == disk_text:       # è una traduzione scritta da noi in un run precedente
                self.d[key] = {"orig": src, "written": sorted({x for _, x in pairs})[-self.MAX_WRITTEN:]}
                return src
        self.d[key] = {"orig": disk_text, "written": []}   # primo run, oppure testo aggiornato dall'autore
        return disk_text

    def record(self, key, dst):
        e = self.d.get(key)
        if e and dst != e["orig"] and dst not in e["written"]:
            e["written"] = (e["written"] + [dst])[-self.MAX_WRITTEN:]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.path, json.dumps(self.d, ensure_ascii=False, indent=2))


class Project:
    def __init__(self, workdir, game, mod_id, mod_version, existing_output_keys=(), lang="it"):
        safe = safe_id(mod_id)
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
        atomic_write_text(self.path, json.dumps(self.m, ensure_ascii=False, indent=2))

    def review_queue(self):
        return {k: v for k, v in self.m["units"].items()
                if v["decision"] in ("REVISION", "BLOCK", "PUBLISH_WITH_NOTE")}

    def save_review(self):
        q = self.review_queue()
        atomic_write_text(self.dir / "review.json", json.dumps(q, ensure_ascii=False, indent=2))
        return q

    # --- backup ---
    def backup(self, mod_dir, rel_paths):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        root, n = self.dir / "backups", 0
        b = root / stamp
        while b.exists():              # due scritture nello stesso secondo non devono sovrascriversi
            n += 1
            b = root / f"{stamp}-{n:03d}"
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

    def backups_left(self):
        root = self.dir / "backups"
        return sum(1 for _ in root.iterdir()) if root.exists() else 0

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
