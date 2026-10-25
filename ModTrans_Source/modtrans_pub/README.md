# modtrans: automatic mod translator

Currently supports **Stardew Valley** (SMAPI / Content Patcher mods with an `i18n/default.json`).
It translates the mod, validates the result with two judges, repairs errors, and writes
`i18n/<lang>.json` into the mod folder.

**What gets modified in the mod folder:** `i18n/<lang>.json` is created/updated, and the
`Description` field of `manifest.json` is replaced with its translation. For mods without
`i18n/default.json`, `content.json` is rewritten in place (only whitelisted text fields; the
structure is preserved). Before every write the previous state is backed up, and
`restore` rolls it back. On re-runs, text that the tool itself wrote is recognized and not
translated again. `i18n/default.json` is never touched.

Requirements: Python 3.11+, no external packages.

## Quick start

    cp modtrans/config.example.toml config.toml     # then edit it (see below)
    python -m modtrans translate "C:/.../Stardew Valley/Mods/SomeMod" -c config.toml

Run these from the folder that **contains** the `modtrans/` folder.
In the GitHub repository that folder is called `modtrans_pub`: rename it to `modtrans` to use the `python -m modtrans` commands
(`start.py` and the GUI work with either name).

| Command | What it does |
|---|---|
| `python -m modtrans translate <mod> -c config.toml` | Translate (only new/changed strings on re-runs) |
| `python -m modtrans translate <mod> -c config.toml --dry-run` | Simulate: runs everything, writes nothing |
| `python -m modtrans review <mod> -c config.toml` | Show strings waiting for human review |
| `python -m modtrans restore <mod> -c config.toml` | Roll back to the previous backup |

Tests: `python -m modtrans.tests.test_core`

---

## Configuration guide

All settings live in one TOML file (`config.toml`). The file has **general settings** at the top
and one **section per role** (`[translator]`, `[judge_a]`, `[judge_b]`, `[repair]`).

TOML basics: `#` starts a comment; text values go in `"quotes"`, numbers don't; a line like
`[translator]` starts a section, and every key below it belongs to that section.
To switch configurations, comment out one block (add `#` at the start of each line) and uncomment another.
Don't leave two active sections with the same name.

### General settings

| Key | Meaning | Default |
|---|---|---|
| `game` | Which game adapter to use. Only `"stardew"` exists for now. | `"stardew"` |
| `workdir` | Folder where the tool stores its own data: per-mod manifest, backups, review queue, translation memory. Not inside your mods. On Windows use forward slashes (`"C:/Users/You/modtrans-data"`). | `"~/.modtrans"` |
| `batch_size` | How many strings go into a single LLM request. Larger = fewer calls/cheaper, but small models get confused with big batches. Cloud: 15–30. Small local models: 5–8. | `15` |

### The four roles

The tool uses an LLM for up to four different jobs. Each has its own section, so each can use a
different model or even a different provider (e.g. translate locally, judge in the cloud).

| Section | Job | If you omit it |
|---|---|---|
| `[translator]` | Does the translation. **Required.** | (error) |
| `[judge_a]` | **Accuracy**: checks the meaning is faithful (omissions, wrong terms). Runs *after* free built-in checks on placeholders, numbers and glossary, which always run. Strong veto: if A rejects, the string goes to repair. | Only the free built-in checks run (no LLM cost) |
| `[judge_b]` | **Fluency**: checks that it sounds natural, matches the character's tone, fits the game. Soft veto: can downgrade a result to "publish with note" or "human review", never triggers repair alone. | Skipped (the other checks still decide) |
| `[repair]` | Fixes strings Judge A rejected with a minimal patch (max 2 attempts, then the string is blocked or sent to human review). | Reuses the translator's engine |

Using a **different model for the judges than for the translator** is recommended: a model tends to
miss its own mistakes. Judges can be cheaper/smaller models because their job is easier than translating.

### Keys inside each role section

#### `type`: which kind of engine runs this role

| `type` | What it is | Needs |
|---|---|---|
| `"anthropic"` | Claude through the Anthropic cloud API. | API key + `model` |
| `"openai_compat"` | Any server that speaks the OpenAI chat format. This covers **local** servers (Ollama, LM Studio, llama.cpp server, vLLM) and cloud ones (OpenAI, OpenRouter). Which one you reach is decided by `base_url`. | `base_url` + `model` (+ API key only for cloud) |
| `"mock"` | A fake engine for testing. No network, no cost; it only prefixes text with `[IT]`, so don't use it for real translations. | nothing |

#### Other keys

| Key | Applies to | Meaning |
|---|---|---|
| `model` | anthropic, openai_compat | The exact model name on that provider/server. Must be valid or you'll get an HTTP error. For local servers it must match a model you've downloaded/loaded (e.g. `ollama list`). |
| `api_key_env` | anthropic, openai_compat (cloud) | The **name of an environment variable** that holds your key, e.g. `"ANTHROPIC_API_KEY"`. The key itself is never written in the config, so you can share the file safely. Not needed for local servers. |
| `base_url` | openai_compat | Server address ending in `/v1`. Ollama: `http://localhost:11434/v1`. LM Studio: `http://localhost:1234/v1`. OpenAI: `https://api.openai.com/v1`. |
| `max_tokens` | all real engines | Maximum length of each reply. Default 4096; raise it if replies get cut off with large batches. |
| `temperature` | openai_compat | Randomness (0 = deterministic). Default 0.2, good for translation. |

### Setting your API key (cloud engines)

1. Create a key in your provider's console (for Claude: console.anthropic.com).
2. Store it in the environment variable named in `api_key_env`:

   - **Windows (PowerShell), permanent:** `setx ANTHROPIC_API_KEY "your-key"` then **close and reopen** the terminal.
   - **Windows, current session only:** `$env:ANTHROPIC_API_KEY = "your-key"`
   - **macOS / Linux:** `export ANTHROPIC_API_KEY="your-key"` (add it to `~/.bashrc` / `~/.zshrc` to keep it)

3. If you use a different provider, pick any variable name (e.g. `OPENAI_API_KEY`) and write the same name in `api_key_env`.

### Setting up a local model (free, private)

1. Install Ollama (ollama.com) or LM Studio.
2. Download a model, e.g. `ollama pull qwen2.5:14b`. Larger models translate better; models under ~7B often
   mangle the `⟦N⟧` placeholders (the repair loop will catch many, but expect more blocked strings).
3. Use `type = "openai_compat"`, the matching `base_url`, and the model name. No API key needed.
4. Lower `batch_size` to 5–8.

### Example setups

**1. Full cloud (best quality, costs money)**: the default `config.example.toml`.

**2. Hybrid (cheap + good)**: local translator, cloud judges:

    game = "stardew"
    batch_size = 8

    [translator]
    type = "openai_compat"
    base_url = "http://localhost:11434/v1"
    model = "qwen2.5:14b"

    [judge_a]
    type = "anthropic"
    model = "claude-haiku-4-5-20251001"
    api_key_env = "ANTHROPIC_API_KEY"

    [judge_b]
    type = "anthropic"
    model = "claude-haiku-4-5-20251001"
    api_key_env = "ANTHROPIC_API_KEY"

**3. Fully local and free**: no `[judge_a]`, so Judge A uses only its built-in checks; Judge B and repair reuse the local model:

    game = "stardew"
    batch_size = 8

    [translator]
    type = "openai_compat"
    base_url = "http://localhost:11434/v1"
    model = "qwen2.5:14b"

**4. Pipeline test (no cost, no real translation)**:

    [translator]
    type = "mock"

### Choosing models

Model names change over time: check your provider's current model list. As a rule of thumb, put the
strongest model on `[translator]` (and `[repair]`), and a cheaper, fast model on the judges. The names in the
example file were valid when it was written.

---

## How a run works

1. Reads `i18n/default.json` and masks game codes (`@`, `#$b#`, `$h`, `{{Token}}`, `{0}`, …) so the LLM can't break them.
2. Skips strings already translated and unchanged (manifest) or known in the translation memory.
3. Translates the rest in batches, using the game preset (tone, characters) and the glossary.
4. Judge A and Judge B score each string → decision `PUBLISH`, `PUBLISH_WITH_NOTE`, `REPAIR`, `REVISION` (human), or `BLOCK`.
5. Rejected strings go through up to 2 repair attempts.
6. Backs up the previous state, then writes `i18n/<lang>.json` (and the translated `Description` in `manifest.json`;
   `content.json` for mods without i18n). `BLOCK`ed strings are left out, so the game shows the English text for them.

Translation memory, manifests and backups are kept **per target language**, so translating the same mod into several languages never mixes them up.

Strings that need a human look are listed in `review.json` inside the mod's folder under your `workdir`.
If the mod already ships its own translation file for the target language, the author's translations are kept and only missing keys are filled in.
