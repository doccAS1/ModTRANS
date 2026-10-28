from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .pipeline import LANGS, run
from .translator import DEFAULT_MODEL, AnthropicBackend, OpenAICompatBackend, Translator


def main(argv=None, backend=None) -> int:
    ap = argparse.ArgumentParser(
        prog="skyrimtrans", description="Traduce le mod di Skyrim senza toccare la struttura.")
    ap.add_argument("mod", type=Path, help="cartella, .zip o .esp/.esm/.esl")
    ap.add_argument("-l", "--lang", required=True, choices=sorted(LANGS), help="lingua di destinazione")
    ap.add_argument("-s", "--source", default="english", choices=sorted(LANGS))
    ap.add_argument("-o", "--output", type=Path, help="zip di output (default: <mod>_<lingua>.zip)")
    ap.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic",
                    help="'openai' = qualsiasi API compatibile OpenAI (anche locale)")
    ap.add_argument("--model", help=f"default anthropic: {DEFAULT_MODEL}; per openai è obbligatorio")
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                    help="es. http://localhost:11434/v1 (Ollama), http://localhost:1234/v1 (LM Studio)")
    ap.add_argument("--api-key", default=None, help="altrimenti OPENAI_API_KEY / ANTHROPIC_API_KEY")
    ap.add_argument("--batch-items", type=int, default=40, help="stringhe per richiesta (con modelli piccoli: 5-10)")
    ap.add_argument("--glossary", type=Path, help="JSON {termine: traduzione}")
    ap.add_argument("--report", type=Path, help="scrive il report in JSON")
    a = ap.parse_args(argv)

    out = a.output or a.mod.with_name(f"{a.mod.stem}_{a.lang}.zip")
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
    tr = Translator(backend, a.lang.capitalize(), glossary, batch_items=a.batch_items)

    def prog(d, t):
        print(f"\r  tradotte {d}/{t}", end="", file=sys.stderr, flush=True)

    if not a.mod.exists():
        ap.error(f"file non trovato: {a.mod}")
    try:
        rep = run(a.mod, out, tr, a.lang, a.source, prog)
    except ValueError as e:
        print(f"\nErrore: {e}", file=sys.stderr)
        return 2
    print(file=sys.stderr)
    print(f"Fatto: {out}")
    print(f"  stringhe tradotte: {rep.translated} | lasciate originali: {rep.kept_original}")
    print(f"  file modificati/creati: {len(rep.files)}")
    for w in rep.warnings[:20]:
        print(f"  ! {w}")
    for f in rep.failures[:20]:
        print(f"  x {f}")
    if a.report:
        a.report.write_text(json.dumps(rep.__dict__, ensure_ascii=False, indent=2), "utf-8")
    return 0
