import json
from pathlib import Path

from .adapters.stardew import ADAPTERS
from .core.glossary import Glossary
from .core.masking import mask, strip_tokens, unmask
from .core.memory import TranslationMemory
from .core.models import Decision
from .core.project import Project, sha
from .engines.base import make_engine
from .qa.aggregate import aggregate
from .qa.judges import JudgeA, JudgeB
from .qa.repair import RepairAgent
from .translator import Translator

PKG = Path(__file__).parent
GOOD = {"PUBLISH", "PUBLISH_WITH_NOTE"}
MAX_REPAIRS = 2

def pick_adapter(mod_dir, game, target_code="it"):
    cls = ADAPTERS[game]
    if not cls.detect(mod_dir):
        raise SystemExit(f"'{mod_dir}' non sembra una mod {game} (manca manifest.json)")
    return cls(mod_dir, target_code)


def _build_mapping(units, project, existing):
    """key -> testo tradotto da scrivere nella mod (le BLOCK restano in inglese)."""
    mapping = {}
    for u in units:
        if u.key in project.foreign and u.key in existing:
            mapping[u.key] = existing[u.key]
        elif (m := project.unit(u.key)) and m["decision"] != "BLOCK" and m["dst"]:
            mapping[u.key] = m["dst"]
    return mapping


def _recover_original_sources(units, project):
    """Se il testo trovato nella mod è quello che abbiamo scritto noi in un run precedente
    (Description del manifest, content.json riscritto sul posto), la sorgente è l'originale
    memorizzato: così un nuovo run non ritraduce la nostra stessa traduzione."""
    for u in units:
        prev = project.unit(u.key)
        if prev and prev["dst"] and prev["dst"] != prev["src"] and u.source == prev["dst"]:
            u.source = prev["src"]


def run(mod_dir, cfg, dry_run=False, log=print):
    game = cfg.get("game", "stardew")
    workdir = Path(cfg.get("workdir", "~/.modtrans")).expanduser()
    
    # 1. Recupera le lingue passate dalla GUI
    target_code = cfg.get("target_lang_code", "it")
    target_name = cfg.get("target_lang_name", "Italian")
    source_name = cfg.get("source_lang_name", "Auto")
    
    # 2. Inizializza l'adapter passandogli il codice lingua
    adapter = pick_adapter(mod_dir, game, target_code)
    
    # --- BLOCCO AI MOD EXCLUSION ---
    if not getattr(adapter, 'ai_allowed', True):
        log(f"\n✗ OPERATION BLOCKED: {adapter.mod_name}\nOops, this mod can't be translated! the author of the mod chose to not make it possible, and my tool has to respect this. (this is not a problem with the tool itself, which would be fully capable on doing so). You can ask the author to enable it and try again.")
        return None

    if not adapter.supported():
        log(f"✗ {adapter.mod_name}: nessun file traducibile trovato (mancano i18n/default.json e content.json).")
        return None
        
    preset = json.load(open(PKG / "presets" / f"{game}.json", encoding="utf-8"))
    
    # 3. INIEZIONE DINAMICA DELLE LINGUE NEI PROMPT
    lang_prompt = f"\n\nCRITICAL INSTRUCTION: You must translate the text from {source_name} to {target_name}. Output ONLY in {target_name}."
    if "translator" in preset: 
        preset["translator"] += lang_prompt
    if "judge_a" in preset: 
        preset["judge_a"] += f"\n\nCRITICAL INSTRUCTION: Evaluate if the text is accurately translated into {target_name}."
    if "judge_b" in preset: 
        preset["judge_b"] += f"\n\nCRITICAL INSTRUCTION: Evaluate if the {target_name} text sounds natural and fluent."
    if "repair" in preset: 
        preset["repair"] += f"\n\nCRITICAL INSTRUCTION: Fix the {target_name} translation based on the provided issues."
        
    glossary = Glossary.load(PKG / "presets" / f"{game}_glossary.json")
    gh = glossary.hash()
    tmk = f"{gh}.{target_code}"   # la translation memory è per lingua di destinazione
    
    existing = adapter.read_output()
    project = Project(workdir, game, adapter.mod_id, adapter.mod_version, existing.keys(), target_code)
    tm = TranslationMemory(workdir / "tm.sqlite")
    
    # Inizializza i motori. Se mancano nel TOML, diventano None
    t_eng = make_engine(cfg["translator"])
    ja_eng = make_engine(cfg["judge_a"]) if "judge_a" in cfg else None
    jb_eng = make_engine(cfg["judge_b"]) if "judge_b" in cfg else None
    
    translator = Translator(t_eng, preset, glossary, cfg.get("batch_size", 15), source_name, target_name)
    # Il Giudice A esiste sempre: senza motore LLM esegue solo i controlli deterministici
    # (segnaposto, numeri, glossario, lunghezza), come descritto nel README.
    judge_a = JudgeA(glossary, ja_eng, preset, target_name)
    judge_b = JudgeB(jb_eng, preset, target_name) if jb_eng else None
    repairer = RepairAgent(make_engine(cfg["repair"]) if "repair" in cfg else t_eng, preset, target_name)

    units = adapter.extract()
    _recover_original_sources(units, project)
    project.prune({u.key for u in units} | project.foreign)
    todo, reused = [], 0
    for u in units:
        if u.key in project.foreign:
            continue
        prev = project.unit(u.key)
        if prev and prev["src_hash"] == sha(u.source) and prev["glossary"] == gh and prev["decision"] != "BLOCK":
            reused += 1; continue
        u.masked, u.tokens = mask(u.source)
        if not any(c.isalpha() for c in strip_tokens(u.masked)):
            project.set_unit(u.key, u.source, u.source, "PUBLISH", gh, via="passthrough"); continue
        hit = tm.get(game, u.source, tmk)
        if hit:
            project.set_unit(u.key, u.source, hit, "PUBLISH", gh, via="tm"); reused += 1; continue
        todo.append(u)
    log(f"{adapter.mod_name} v{adapter.mod_version}: {len(units)} stringhe, "
        f"{reused} già a posto, {len(todo)} da tradurre")

    translated = translator.translate(todo) if todo else {}
    stats = {}
    for u in todo:
        tr = translated.get(u.key)
        if tr is None:
            project.set_unit(u.key, u.source, "", "BLOCK", gh, [{"type": "engine", "detail": "nessuna traduzione"}])
            stats["BLOCK"] = stats.get("BLOCK", 0) + 1; continue
        
        attempts, issues = 0, []
        while True:
            a = judge_a.evaluate(u, tr)
            # B si consulta solo se A non ha già respinto la stringa
            b = judge_b.evaluate(u, tr) if (judge_b and a.ok) else None
            decision = aggregate(a, b)
            issues = a.issues + (b.issues if b else [])

            if decision == Decision.REPAIR and attempts < MAX_REPAIRS:
                tr, attempts = repairer.repair(u, tr, issues), attempts + 1
                continue
            if decision == Decision.REPAIR:
                decision = Decision.BLOCK if a.hard else Decision.REVISION
            break

        final = unmask(tr, u.tokens)
        project.set_unit(u.key, u.source, final, decision.value, gh, issues, attempts)
        if decision.value in GOOD:
            tm.put(game, u.source, tmk, final)
        stats[decision.value] = stats.get(decision.value, 0) + 1

    mapping = _build_mapping(units, project, existing)
    review = project.save_review()
    if not dry_run:
        project.backup(mod_dir, adapter.output_files())
        adapter.write(mapping)
        project.save(glossary_hash=gh, translator=t_eng.name,
                     judges={"A": ja_eng.name if ja_eng else "deterministic", "B": jb_eng.name if jb_eng else "skipped"})
    log(f"Esito: {stats or 'nulla da fare'} | in revisione/nota: {len(review)} | "
        f"scritte {len(mapping)}/{len(units)} chiavi" + (" (dry-run)" if dry_run else ""))
    return {"stats": stats, "review": review, "written": len(mapping), "total": len(units)}

def restore(mod_dir, cfg):
    game = cfg.get("game", "stardew")
    target_code = cfg.get("target_lang_code", "it")
    adapter = pick_adapter(mod_dir, game, target_code)
    workdir = Path(cfg.get("workdir", "~/.modtrans")).expanduser()
    p = Project(workdir, game, adapter.mod_id, adapter.mod_version, (), target_code)
    return p.restore_latest(mod_dir)


def _open_project(mod_dir, cfg):
    game = cfg.get("game", "stardew")
    adapter = pick_adapter(mod_dir, game, cfg.get("target_lang_code", "it"))
    workdir = Path(cfg.get("workdir", "~/.modtrans")).expanduser()
    code = cfg.get("target_lang_code", "it")
    project = Project(workdir, game, adapter.mod_id, adapter.mod_version, adapter.read_output().keys(), code)
    return game, adapter, workdir, project


def load_review(mod_dir, cfg):
    """Stringhe in attesa di revisione umana: {key: {src, dst, decision, issues, ...}}."""
    *_, project = _open_project(mod_dir, cfg)
    return {k: v for k, v in project.m["units"].items()
            if v["decision"] in ("REVISION", "BLOCK", "PUBLISH_WITH_NOTE")}


def apply_review(mod_dir, cfg, edits):
    """Applica le decisioni umane {key: testo_finale} e riscrive i file della mod (con backup).

    Le stringhe approvate diventano PUBLISH (via='human') ed entrano nella translation memory.
    Ritorna il numero di stringhe aggiornate."""
    game, adapter, workdir, project = _open_project(mod_dir, cfg)
    gh = Glossary.load(PKG / "presets" / f"{game}_glossary.json").hash()
    tm = TranslationMemory(workdir / "tm.sqlite")
    tmk = f"{gh}.{cfg.get('target_lang_code', 'it')}"
    done = 0
    for key, text in edits.items():
        cur = project.unit(key)
        if not cur or not text.strip():
            continue
        project.set_unit(key, cur["src"], text, "PUBLISH", gh, via="human")
        tm.put(game, cur["src"], tmk, text)
        done += 1
    if done:
        units = adapter.extract()
        mapping = _build_mapping(units, project, adapter.read_output())
        project.save_review()
        project.backup(mod_dir, adapter.output_files())
        adapter.write(mapping)
        project.save()
    return done
