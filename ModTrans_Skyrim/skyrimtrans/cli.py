from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .pipeline import LANGS, check_writable_dir, clean_name, run
from .translator import (DEFAULT_MODEL, AbortRun, AnthropicBackend, OpenAICompatBackend, Translator,
                         store_for)


def main(argv=None, backend=None) -> int:
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
    ap.add_argument("--glossary", type=Path, help="JSON {termine: traduzione}")
    ap.add_argument("--fresh", action="store_true", help="ignora la memoria delle traduzioni (ritraduce tutto; i risultati la aggiornano)")
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
    store = None if a.no_memory else store_for(a.lang, profile, glossary)
    tr = Translator(backend, a.lang.capitalize(), glossary, batch_items=a.batch_items, store=store,
                    reuse_memory=not a.fresh)

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
