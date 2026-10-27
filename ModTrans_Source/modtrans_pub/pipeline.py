import json
from pathlib import Path

from .adapters.stardew import ADAPTERS
from .core.fsutil import valid_lang
from .core.glossary import Glossary
from .core.masking import mask, strip_tokens, unmask
from .core.memory import TranslationMemory
from .core.models import Decision
from .core.project import Originals, Project, sha
from .engines.base import make_engine
from .qa.aggregate import aggregate
from .qa.judges import JudgeA, JudgeB
from .qa.repair import RepairAgent
from .translator import Translator

PKG = Path(__file__).parent
GOOD = {"PUBLISH", "PUBLISH_WITH_NOTE"}
MAX_REPAIRS = 2
MAX_ENGINE_FAILS = 3
ENGINE_RETRY_NOTE = "(not verified: it will be retried on the next run)"

def _lang(cfg):
    try:
        return valid_lang(cfg.get("target_lang_code", "it"))
    except ValueError as e:
        raise SystemExit(str(e))


def pick_adapter(mod_dir, game, target_code="it"):
    cls = ADAPTERS[game]
    if not cls.detect(mod_dir):
        raise SystemExit(f"'{mod_dir}' does not look like a {game} mod (manifest.json is missing)")
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


def _resolve_inplace_sources(adapter, units, originals):
    """Per i testi riscritti sul posto (Description, content.json) la sorgente è l'originale della mod,
    non il testo trovato sul disco, che può essere una nostra traduzione (anche di un'altra lingua)."""
    for u in units:
        if u.file in adapter.inplace_files:
            u.source = originals.resolve(u.key, u.source)


def _record_written(adapter, units, mapping, originals):
    for u in units:
        if u.file in adapter.inplace_files and u.key in mapping:
            originals.record(u.key, mapping[u.key])


def run(mod_dir, cfg, dry_run=False, log=print):
    game = cfg.get("game", "stardew")
    workdir = Path(cfg.get("workdir", "~/.modtrans")).expanduser()
    
    # 1. Recupera le lingue passate dalla GUI
    target_code = _lang(cfg)
    target_name = cfg.get("target_lang_name", "Italian")
    source_name = cfg.get("source_lang_name", "Auto")
    
    # 2. Inizializza l'adapter passandogli il codice lingua
    adapter = pick_adapter(mod_dir, game, target_code)
    
    # --- BLOCCO AI MOD EXCLUSION ---
    if not getattr(adapter, 'ai_allowed', True):
        log(f"\n✗ OPERATION BLOCKED: {adapter.mod_name}\nOops, this mod can't be translated! the author of the mod chose to not make it possible, and my tool has to respect this. (this is not a problem with the tool itself, which would be fully capable on doing so). You can ask the author to enable it and try again.")
        return None

    if not adapter.supported():
        log(f"✗ {adapter.mod_name}: no translatable files found (i18n/default.json and content.json are missing).")
        return None
        
    preset = json.load(open(PKG / "presets" / f"{game}.json", encoding="utf-8"))
    
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
    originals = Originals(workdir, game, adapter.mod_id)
    _resolve_inplace_sources(adapter, units, originals)
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
    log(f"{adapter.mod_name} v{adapter.mod_version}: {len(units)} strings, "
        f"{reused} already done, {len(todo)} to translate")

    translated = translator.translate(todo) if todo else {}
    stats = {}
    engine_fails, aborted = 0, False        # errori consecutivi dei motori di controllo (giudici / repair)
    try:
        for u in todo:
            if aborted:
                project.set_unit(u.key, u.source, "", "BLOCK", gh, [{"type": "engine_error", "detail": ENGINE_RETRY_NOTE}])
                stats["BLOCK"] = stats.get("BLOCK", 0) + 1; continue
            tr = translated.get(u.key)
            if tr is None:
                project.set_unit(u.key, u.source, "", "BLOCK", gh, [{"type": "engine", "detail": "no translation returned"}])
                stats["BLOCK"] = stats.get("BLOCK", 0) + 1; continue

            attempts, issues, engine_error = 0, [], None
            while True:
                try:
                    a = judge_a.evaluate(u, tr)
                    # B si consulta solo se A non ha già respinto la stringa
                    b = judge_b.evaluate(u, tr) if (judge_b and a.ok) else None
                except Exception as e:         # rete, timeout, JSON non valido del giudice
                    engine_error = f"judge: {e}"; break
                decision = aggregate(a, b)
                issues = a.issues + (b.issues if b else [])

                if decision == Decision.REPAIR and attempts < MAX_REPAIRS:
                    try:
                        tr, attempts = repairer.repair(u, tr, issues), attempts + 1
                    except Exception as e:
                        engine_error = f"repair: {e}"; break
                    continue
                if decision == Decision.REPAIR:
                    decision = Decision.BLOCK if a.hard else Decision.REVISION
                break

            if engine_error:
                # Non verificata: resta in inglese (BLOCK) e verrà ritentata al prossimo avvio.
                decision = Decision.BLOCK
                issues = issues + [{"type": "engine_error", "detail": f"{engine_error[:200]} {ENGINE_RETRY_NOTE}"}]
                engine_fails += 1
                if engine_fails >= MAX_ENGINE_FAILS:
                    aborted = True
                    log(f"! {MAX_ENGINE_FAILS} consecutive errors from the checking engine ({engine_error[:120]}): "
                        "stopping the checks. The remaining strings will be retried on the next run.")
            else:
                engine_fails = 0

            final = unmask(tr, u.tokens)
            project.set_unit(u.key, u.source, final, decision.value, gh, issues, attempts)
            if decision.value in GOOD and not dry_run:
                tm.put(game, u.source, tmk, final)
            stats[decision.value] = stats.get(decision.value, 0) + 1
    except BaseException:
        if not dry_run:                        # un errore imprevisto non deve far perdere i risultati già ottenuti
            try:
                project.save(); originals.save()
            except Exception:
                pass
        raise

    mapping = _build_mapping(units, project, existing)
    review = project.review_queue()
    if not dry_run:
        project.save_review()
        project.backup(mod_dir, adapter.output_files())
        adapter.write(mapping)
        _record_written(adapter, units, mapping, originals)
        originals.save()
        project.save(glossary_hash=gh, translator=t_eng.name,
                     judges={"A": ja_eng.name if ja_eng else "deterministic", "B": jb_eng.name if jb_eng else "skipped"})
    log(f"Result: {stats or 'nothing to do'} | in review/with note: {len(review)} | "
        f"written {len(mapping)}/{len(units)} keys" + (" (dry-run)" if dry_run else ""))
    # stringhe scritte nella mod ma ancora in attesa di approvazione umana
    unreviewed = sorted(k for k in mapping
                        if (m := project.unit(k)) and m["decision"] == "REVISION")
    if unreviewed:
        log(f"⚠ WARNING: {len(unreviewed)} string(s) were written to the mod but the reviewers were not "
            "sure about them, so the translation may not be perfect. Check them with Manual Review "
            "(or the `review` command).")
    return {"stats": stats, "review": review, "written": len(mapping), "total": len(units),
            "unreviewed": unreviewed}

def backups_left(mod_dir, cfg):
    game = cfg.get("game", "stardew")
    adapter = pick_adapter(mod_dir, game, cfg.get("target_lang_code", "it"))
    workdir = Path(cfg.get("workdir", "~/.modtrans")).expanduser()
    return Project(workdir, game, adapter.mod_id, adapter.mod_version).backups_left()


def restore(mod_dir, cfg):
    game = cfg.get("game", "stardew")
    target_code = _lang(cfg)
    adapter = pick_adapter(mod_dir, game, target_code)
    workdir = Path(cfg.get("workdir", "~/.modtrans")).expanduser()
    p = Project(workdir, game, adapter.mod_id, adapter.mod_version, (), target_code)
    return p.restore_latest(mod_dir)


def _open_project(mod_dir, cfg):
    game = cfg.get("game", "stardew")
    code = _lang(cfg)
    adapter = pick_adapter(mod_dir, game, code)
    workdir = Path(cfg.get("workdir", "~/.modtrans")).expanduser()
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
    tmk = f"{gh}.{_lang(cfg)}"
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
        originals = Originals(workdir, game, adapter.mod_id)
        _record_written(adapter, units, mapping, originals)
        originals.save()
        project.save()
    return done
