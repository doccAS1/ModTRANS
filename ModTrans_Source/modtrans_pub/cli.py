import argparse, json, sys, tomllib
from pathlib import Path

from . import pipeline


def main(argv=None):
    ap = argparse.ArgumentParser("modtrans", description="Traduttore automatico di mod")
    ap.add_argument("command", choices=["translate", "restore", "review"])
    ap.add_argument("mod_dir")
    ap.add_argument("-c", "--config", default="config.toml")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    cfg = tomllib.loads(Path(a.config).read_text(encoding="utf-8"))
    if a.command == "translate":
        pipeline.run(a.mod_dir, cfg, a.dry_run)
    elif a.command == "restore":
        print("Ripristinato." if pipeline.restore(a.mod_dir, cfg) else "Nessun backup disponibile.")
    else:
        print(json.dumps(pipeline.load_review(a.mod_dir, cfg), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
