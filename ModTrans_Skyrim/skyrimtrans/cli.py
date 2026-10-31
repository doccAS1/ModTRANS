from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .pipeline import LANGS, check_writable_dir, clean_name, run
from .translator import (DEFAULT_MODEL, AbortRun, AnthropicBackend, OpenAICompatBackend, Translator,
                         store_for)


def glossary_main(argv) -> int:
    from .glossary import GlossaryError, build_glossary
    ap = argparse.ArgumentParser(
        prog="skyrimtrans glossario",
        description="Costruisce un glossario ufficiale accoppiando i file Strings del gioco in due lingue.")
    ap.add_argument("data", type=Path, help="cartella Data di Skyrim (o quella del gioco)")
    ap.add_argument("-l", "--lang", required=True, choices=sorted(LANGS), help="lingua di destinazione (es. italian)")
    ap.add_argument("-s", "--source", default="english", choices=sorted(LANGS))
    ap.add_argument("-o", "--output", type=Path, help="file JSON (default: glossario_<lingua>.json nella cartella corrente)")
    a = ap.parse_args(argv)
    try:
        gl, info = build_glossary(a.data, a.source, a.lang, LANGS[a.source][1], LANGS[a.lang][1])
    except GlossaryError as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 2
    out = a.output or Path(f"glossario_{a.lang}.json")
    out.write_text(json.dumps(gl, ensure_ascii=False, indent=1), "utf-8")
    print(f"Glossario: {info['terms']} termini da {len(info['used'])} file ({', '.join(info['used'])}) -> {out}")
    if info["missing"]:
        print(f"  Senza l'altra lingua, saltati: {', '.join(info['missing'])}")
    if info["common"] or info["literal"]:
        print(f"  Tolte le traduzioni ovvie: {info['common']} parole comuni e {info['literal']} nomi composti letteralmente")
    if info["ambiguous"]:
        print(f"  Nomi con traduzioni diverse nel gioco, esclusi: {info['ambiguous']}")
    print("  Usalo con: skyrimtrans MiaMod.zip -l", a.lang, "--game-glossary", out)
    return 0


def main(argv=None, backend=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] in ("glossario", "glossary"):
        return glossary_main(argv[1:])
    ap = argparse.ArgumentParser(
        prog="skyrimtrans", description="Traduce le mod di Skyrim senza toccare la struttura.")
    ap.add_argument("mod", type=Path, help="cartella, .zip o .esp/.esm/.esl")
    ap.add_argument("-l", "--lang", required=True, choices=sorted(LANGS), help="lingua di destinazione")
    ap.add_argument("-s", "--source", default="english", choices=sorted(LANGS))
    ap.add_argument("-o", "--output", type=Path, help="percorso di output (default: <mod>_<lingua>.zip accanto alla mod)")
    ap.add_argument("--out-dir", type=Path, help="cartella dove salvare il risultato (la crea se manca)")
    ap.add_argument("--as-folder", action="store_true", help="salva una cartella pronta invece di uno zip")
    ap.add_argument("--overwrite", action="store_true", help="sovrascrive se esiste già (di default sceglie un nome libero)")
    ap.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic",
                    help="'openai' = qualsiasi API compatibile OpenAI (anche locale)")
    ap.add_argument("--model", help=f"default anthropic: {DEFAULT_MODEL}; per openai è obbligatorio")
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                    help="es. http://localhost:11434/v1 (Ollama), http://localhost:1234/v1 (LM Studio)")
    ap.add_argument("--api-key", default=None, help="altrimenti OPENAI_API_KEY / ANTHROPIC_API_KEY")
    ap.add_argument("--batch-items", type=int, default=40, help="stringhe per richiesta (con modelli piccoli: 5-10)")
    ap.add_argument("--glossary", type=Path, help="JSON {termine: traduzione}: i tuoi termini, sempre dati al modello e con la precedenza")
    ap.add_argument("--game-glossary", type=Path, help="glossario ufficiale creato con 'skyrimtrans glossario' (grande: al modello va solo ciò che serve a ogni lotto)")
    ap.add_argument("--game-data", type=Path, help="cartella Data di Skyrim: costruisce il glossario ufficiale al volo (come 'glossario')")
    ap.add_argument("--fresh", action="store_true", help="ignora la memoria delle traduzioni (ritraduce tutto; i risultati la aggiornano)")
    ap.add_argument("--review", action="store_true", help="dopo la traduzione, un secondo passaggio AI rilegge e corregge errori evidenti (più richieste)")
    ap.add_argument("--no-shorten", action="store_true", help="non accorciare i testi d'interfaccia molto più lunghi dell'originale")
    ap.add_argument("--no-memory", action="store_true", help="non legge né scrive la memoria delle traduzioni su disco")
    ap.add_argument("--brief", help="contesto sulla mod dato al modello (testo)")
    ap.add_argument("--brief-file", type=Path, help="come --brief, da file di testo")
    ap.add_argument("--nexus", help="ID o link Nexus Mods della mod, oppure 'auto' (ID dal nome del file)")
    ap.add_argument("--nexus-key", default=os.environ.get("NEXUS_API_KEY"), help="chiave API Nexus (o NEXUS_API_KEY)")
    ap.add_argument("--nexus-game", default="skyrimspecialedition", choices=["skyrimspecialedition", "skyrim"])
    ap.add_argument("--report", type=Path, help="scrive il report in JSON")
    a = ap.parse_args(argv)

    name = f"{clean_name(a.mod.name)}_{a.lang}" + ("" if a.as_folder else ".zip")
    if a.output:
        out = a.output
    elif a.out_dir:
        try:
            out = check_writable_dir(a.out_dir) / name
        except ValueError as e:
            ap.error(str(e))
    else:
        out = a.mod.with_name(name)
    glossary = json.loads(a.glossary.read_text("utf-8")) if a.glossary else None
    if backend is None:
        if a.provider == "openai":
            if not a.model:
                ap.error("--model è obbligatorio con --provider openai")
            backend = OpenAICompatBackend(
                a.model, a.base_url, a.api_key or os.environ.get("OPENAI_API_KEY"))
        else:
            try:
                backend = AnthropicBackend(a.model or DEFAULT_MODEL, a.api_key)
            except ImportError:
                ap.error("manca la libreria: pip install anthropic (oppure usa --provider openai)")
    profile = f"{a.provider}-{a.model or (DEFAULT_MODEL if a.provider == 'anthropic' else 'x')}"
    game_gl = None
    try:
        if a.game_glossary:
            game_gl = json.loads(a.game_glossary.read_text("utf-8"))
        elif a.game_data:
            from .glossary import build_glossary
            game_gl, ginfo = build_glossary(a.game_data, a.source, a.lang, LANGS[a.source][1], LANGS[a.lang][1])
            print(f"Glossario ufficiale: {ginfo['terms']} termini da {len(ginfo['used'])} file")
    except (ValueError, OSError) as e:
        print(f"Errore nel glossario ufficiale: {e}", file=sys.stderr)
        return 2
    store = None if a.no_memory else store_for(a.lang, profile, {**(game_gl or {}), **(glossary or {})} or None)
    tr = Translator(backend, a.lang.capitalize(), glossary, batch_items=a.batch_items, store=store,
                    reuse_memory=not a.fresh, shorten=not a.no_shorten, review=a.review, game_glossary=game_gl)

    def prog(d, t):
        print(f"\r  tradotte {d}/{t}", end="", file=sys.stderr, flush=True)

    if not a.mod.exists():
        ap.error(f"file non trovato: {a.mod}")
    try:
        if a.brief_file:
            tr.set_brief(a.brief_file.read_text("utf-8"))
        elif a.brief:
            tr.set_brief(a.brief)
        elif a.nexus:
            from . import context as ctx
            ref = ctx.detect_nexus_id(a.mod.name) if a.nexus == "auto" else ctx.parse_nexus_ref(a.nexus)
            if ref is None:
                ap.error("ID Nexus non riconosciuto")
            nx = ctx.fetch_nexus(ref, a.nexus_key or "", a.nexus_game)
            text, srcs, warn = ctx.build_brief(ctx.offline_for_path(a.mod), nx, backend)
            tr.set_brief(text)
            print(f"Contesto da: {', '.join(srcs)} (Nexus: {nx['name']})" + (f" - {warn}" if warn else ""))
            print(f"  {text[:300]}")
    except ValueError as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 2
    try:
        rep = run(a.mod, out, tr, a.lang, a.source, prog, a.as_folder, a.overwrite)
    except (ValueError, AbortRun) as e:
        print(f"\nErrore: {e}", file=sys.stderr)
        return 2
    print(file=sys.stderr)
    print(f"Fatto: {rep.output}")
    print(f"  stringhe tradotte: {rep.translated} (dalla memoria: {rep.from_memory}, richieste all'AI: {rep.requests})"
          f" | lasciate originali: {rep.kept_original}")
    if rep.shortened or rep.qa_checked:
        print(f"  qualità: accorciate {rep.shortened} | riviste {rep.qa_checked}, corrette {rep.qa_fixed}")
    if rep.failures:
        print("  Alcune stringhe non sono state tradotte: rilancia lo stesso comando per riprovare solo quelle.")
    print(f"  file modificati/creati: {len(rep.files)}")
    for w in rep.warnings[:20]:
        print(f"  ! {w}")
    for f in rep.failures[:20]:
        print(f"  x {f}")
    if a.report:
        a.report.write_text(json.dumps(rep.__dict__, ensure_ascii=False, indent=2), "utf-8")
    return 0
