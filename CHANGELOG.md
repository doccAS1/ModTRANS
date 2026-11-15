# Changelog

## ModTrans 1.2 (Stardew Valley)

### New
- Windows .exe: no Python needed. Download `ModTrans-windows.zip`, unzip it and run `ModTrans.exe`.
- API key field in the window: paste your key there. It is only used for your translator and never
  written to the config. You can optionally tick "Remember" (stored unencrypted on your PC).
- Warning when some strings were written to the mod but the reviewers were not sure about them:
  a message in the log and a warning window at the end of the run. Open "Manual Review" to check them.
- Configurable `timeout` setting for each AI engine (default 120 seconds).
- Review and Restore buttons are turned off while a translation is running, and Restore now tells
  you how many older backups are still available.
- The whole tool (messages, prompts, review notes) is now in English.
- Command line: choose the languages with `-l fr` and `-s English`, or with `target_lang_code` and
  `source_lang_name` in the config.

### Fixed
- Translating the same mod into several languages could mix or stack languages. Each language is now
  kept separate, and the original text of the mod is always remembered.
- A failing AI judge or repair step could crash the run and lose work. Errors are now handled per
  string, results are saved, and the run stops cleanly after repeated failures. Strings that could
  not be checked are retried on the next run.
- False "number changed" errors on values like `1,000g` or "three apples". Real changed or invented
  numbers are still caught.
- Slow AI replies: a timeout is now retried instead of failing straight away.
- AI replies with extra notes or braces around the JSON no longer break parsing.
- Glossary terms with punctuation (like `C++`) and Chinese/Japanese/Korean terms now match.
- More game codes are protected during translation: `[O 388]`, `$1`, `$A` and the arguments of `$q` / `$r`.
- Several backups made in the same second no longer overwrite each other.
- With only a language code in the config (e.g. `fr`), the AI was still told to translate into Italian.
- The backup count shown after Restore was wrong for languages other than Italian.
- The translation memory database is now always closed, and small files are closed right after reading.

### Security
- A text in the mod can no longer smuggle new game codes into the translation.
- Mod zip files are extracted safely (size and entry limits, no path escapes).
- Language codes and mod IDs are validated so they cannot point outside the work folder.
- Files are written atomically, so a crash cannot leave a half-written file.
- Your API key is never sent over plain http to a public server.

### Notes
- Strings the reviewers are unsure about are still written to the mod, so it stays complete and
  playable. Use "Manual Review" to correct them.
- Antivirus programs sometimes flag PyInstaller executables by mistake. The project is open source,
  so you can run it from source or build the .exe yourself.
