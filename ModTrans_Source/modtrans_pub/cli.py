import argparse, json, sys, tomllib
from pathlib import Path

from . import pipeline


def main(argv=None):
    ap = argparse.ArgumentParser("modtrans", description="Automatic mod translator")
    ap.add_argument("command", choices=["translate", "restore", "review"])
    ap.add_argument("mod_dir")
    ap.add_argument("-c", "--config", default="config.toml")
    ap.add_argument("-l", "--lang", metavar="CODE",
                    help="target language code, e.g. it, fr, es, de, pt-BR (overrides target_lang_code in the config)")
    ap.add_argument("-s", "--source-lang", metavar="NAME",
                    help="source language name, e.g. English (default: Auto)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        cfg = tomllib.loads(Path(a.config).read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"Config file not found: {a.config} (copy config.example.toml to config.toml)")
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Invalid config file {a.config}: {e}")
    if a.lang:
        cfg["target_lang_code"] = a.lang
        cfg.pop("target_lang_name", None)      # il nome si ricava dal nuovo codice
    if a.source_lang:
        cfg["source_lang_name"] = a.source_lang
    if a.command == "translate":
        pipeline.run(a.mod_dir, cfg, a.dry_run)
    elif a.command == "restore":
        print("Restored." if pipeline.restore(a.mod_dir, cfg) else "No backup available.")
    else:
        print(json.dumps(pipeline.load_review(a.mod_dir, cfg), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
