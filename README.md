# ModTRANS: a universal mod translator

**One tool to translate mods for all the major games.**

You give it a mod you downloaded, pick the language you want, and ModTRANS finds *only* the
text that needs translating, translates it, checks the result, and hands you the mod back,
translated and ready to use. The mod's structure is never broken: game codes, placeholders,
file layout and everything that is not human-readable text stay exactly as the author made them.

> **Status:** early development. **Stardew Valley is supported today.** Every other game below is on
> the roadmap and is *not* usable yet.

---

## Why

Most mods are published in one language, and translators have to re-do the same boring and
risky work for every game: dig through game-specific files, avoid breaking tags and variables,
repack the mod, test it. ModTRANS aims to do that work once, in one place, for every game, with
a shared translation engine and a small, game-specific adapter for each title.

## Principles

- **Never break the mod.** Game codes (`@`, `$h`, `{{Token}}`, `%name`, `[388]`, markup...) are masked before
  translation and restored afterwards; the output is checked so that none is lost, duplicated or changed.
- **Translate only text.** Only strings that players read are touched. Everything else is left alone.
- **Reversible.** Every write is backed up first and can be rolled back with one command (or one button).
- **Quality checked, not just generated.** Two independent reviewers (accuracy and fluency) judge each
  string, rejected ones are automatically repaired, and doubtful ones go to a human review queue.
- **Respect the authors.** If a mod author opted out of AI translation, the tool refuses to process that mod.
- **Any language, any model.** Pick the source and target language you need, and run it with the AI provider you
  prefer: Claude, any OpenAI-compatible service (OpenAI, OpenRouter...), or a free local model (Ollama, LM Studio...).
- **Consistent terminology.** A per-game glossary and a translation memory keep names and terms identical
  across a whole mod and across mods.

## How it works

Every game goes through the same pipeline:

1. **Extract**: the game adapter reads the mod and returns the translatable strings.
2. **Mask**: game codes are replaced by safe placeholders.
3. **Reuse**: strings already translated and unchanged, or already in the translation memory, are skipped.
4. **Translate** in batches, guided by the game's tone, characters and glossary.
5. **Judge**: accuracy checks (free deterministic checks first, then an optional AI judge) and fluency checks.
6. **Repair**: rejected strings get up to two minimal fixes; what still fails is blocked or sent to human review.
7. **Write**: the previous state is backed up, then the translated files are written back into the mod.

Details, configuration and examples are in the
[user guide](ModTrans_Source/modtrans_pub/README.md).

## Current status

| | |
|---|---|
| **Supported game** | Stardew Valley (SMAPI / Content Patcher mods) |
| **Interface** | Desktop GUI (Tkinter) and command line |
| **Review workflow** | Manual review window, backup and restore |
| **AI providers** | Anthropic, OpenAI-compatible endpoints (cloud or local), mock engine for testing |
| **Languages** | Source: auto-detect or a chosen language. Target: Italian, French, Spanish, German, Chinese, Russian, Japanese, Portuguese (more can be added easily) |
| **Requirements** | Python 3.11+, no external packages |

## Roadmap

The goal is one translator for all of these. The order is not final, and the technical notes are
first assumptions that will be verified against real mods while each adapter is built.

| Game | Where the text is expected to live | Status |
|---|---|---|
| **Stardew Valley** | `i18n/*.json`, `content.json`, `manifest.json` | Supported |
| **Minecraft** | Language files (`lang/*.json`) in mods and resource packs | Planned |
| **Kingdom Come: Deliverance** | Localization XML packed in `.pak` files | Planned |
| **Cyberpunk 2077** | Localization data inside `.archive` files and REDmod | Planned |
| **Baldur's Gate 3** | `.pak` mods with localization (`.loca` / XML) | Planned |
| **Skyrim** | Plugins (`.esp/.esm/.esl`) and string tables (`.strings`, `.dlstrings`, `.ilstrings`) | Planned |
| **Fallout 3** | Plugins (`.esp/.esm`) | Planned |
| **Fallout: New Vegas** | Plugins (`.esp/.esm`) | Planned |
| **Fallout 4** | Plugins and string tables | Planned |
| **Starfield** | Plugins and string tables | Planned |
| **The Elder Scrolls IV: Oblivion (remake)** | Plugins and UE-based mod files | Planned |
| **Elden Ring** | Text files (FMG) inside message archives | Planned |
| **Red Dead Redemption 2** | Game text tables (format to be researched) | Planned |
| **Crimson Desert** | To be researched once the modding scene settles | Planned |
| **Dragon Age: Origins** | Talk tables (`.tlk`) and packaged mods | Planned |
| **Dragon Age II** | Talk tables (`.tlk`) and packaged mods | Planned |
| **Dragon Age: Inquisition** | Frostbite text resources | Planned |
| **The Sims 3** | `.package` files with string tables (STBL) | Planned |
| **The Sims 4** | `.package` files with string tables (STBL) | Planned |

Games that share a technology are expected to share most of the work: for example the Bethesda
titles (plugins + string tables), the BioWare titles (talk tables), and The Sims 3 / 4 (packages).

Cross-game features planned along the way:
- **Official-terminology glossaries** built automatically from each game's own localization files, so names and
  terms match the translation the base game already uses.
- **A shared review queue** and translation memory that work the same way for every game.
- **Per-game style presets** (tone, characters, rules) so a farming sim and a dark fantasy RPG don't sound alike.

## Adding a game

A game is one small *adapter* that knows how to do four things with that game's mod files:

```
detect(mod_dir)        # is this a mod for this game?
extract()              # -> the translatable strings
output_files()         # which files will be written (for backups)
write(mapping)         # put the translated strings back, structure untouched
```

Everything else (masking, translation, judging, repair, memory, backups, review, GUI) is shared.
See `ModTrans_Source/modtrans_pub/adapters/` for the Stardew Valley adapter.

## Download (Windows)

If you just want to use it, no Python needed: download `ModTrans-windows.zip` from the
[Releases](../../releases) page, unzip it, and run `ModTrans.exe`. Next to it you'll find `config.toml`
(edit it to choose your AI provider), and the app creates it for you if it's missing.

You still need an API key for the AI provider you choose (or a local model). With the default config, set
`OPENROUTER_API_KEY` as described in the [user guide](ModTrans_Source/modtrans_pub/README.md#setting-your-api-key-cloud-engines).

> **Antivirus warning:** executables built with PyInstaller are sometimes flagged by Windows
> Defender or other antivirus software as a false positive. The program is fully open source: you can read the
> code here and build the `.exe` yourself with `build_exe.bat`, or run it from source with `python start.py`.

The `.exe` also accepts the command line, for example `ModTrans.exe translate "<mod folder>" -c config.toml`.

## Getting started (from source)

Follow the [user guide](ModTrans_Source/modtrans_pub/README.md). In short: install Python 3.11+, copy
`config.example.toml` to `config.toml`, add the key of the AI provider you want to use (or point it to a local model),
then start the GUI with `python start.py`.

In this repository the package folder is called `modtrans_pub`; `start.py` works with either that name or
`modtrans`.

## Contributing

Bug reports, mod samples for the games above, and adapters are welcome. If you know the modding formats of
one of the planned games, your notes are the most valuable thing you can share.

Please respect mod authors: check their permissions before publishing a translation of their work, and
do not use ModTRANS on mods whose authors have asked not to be translated with AI.
