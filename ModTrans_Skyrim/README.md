# skyrimtrans

Traduce le mod di Skyrim (LE/SE) con Claude, toccando **solo il testo**.

## Interfaccia grafica
```bash
pip install -e .[anthropic,7z]
skyrimtrans-gui          # si apre nel browser, trascini la mod e scegli lingua e servizio AI
```
Gira solo sul tuo PC (127.0.0.1). La chiave API non viene salvata su disco. "Solo analisi" mostra quante stringhe verrebbero tradotte senza chiamare nessuna AI.

## Riga di comando
```bash
pip install -e .
export ANTHROPIC_API_KEY=...
python -m skyrimtrans MiaMod.zip -l italian            # -> MiaMod_italian.zip
python -m skyrimtrans MiaMod.esp -l italian -o out.zip --glossary glossario.json
```

### Altri provider (API compatibili OpenAI, anche locali)
Nessuna dipendenza extra. Esempi:
```bash
# Ollama
python -m skyrimtrans MiaMod.zip -l italian --provider openai --model qwen2.5:14b \
    --base-url http://localhost:11434/v1 --batch-items 8
# LM Studio
python -m skyrimtrans MiaMod.zip -l italian --provider openai --model <nome-modello> \
    --base-url http://localhost:1234/v1 --batch-items 8
# OpenAI / OpenRouter (chiave in OPENAI_API_KEY)
python -m skyrimtrans MiaMod.zip -l italian --provider openai --model gpt-4o-mini
```
Con modelli piccoli usa `--batch-items` basso: se perdono i segnaposto la stringa resta in originale (vedi il report).

Input: cartella, `.zip` o singolo `.esp/.esm/.esl`. Output: zip con la stessa struttura.

## Cosa traduce
| File | Cosa |
|---|---|
| `.esp/.esm/.esl` non localizzati | solo i sottorecord testuali in `skyrimtrans/tables.py` (nomi, descrizioni, libri, dialoghi, quest, messaggi) |
| `*_ENGLISH.STRINGS/DLSTRINGS/ILSTRINGS` | tutte le stringhe; crea `*_<LINGUA>.*`, il plugin non cambia |
| `Interface/Translations/*_ENGLISH.txt` (MCM) | solo il testo dopo il tab; crea `*_<LINGUA>.txt` |

Tutto il resto (script `.pex`, mesh, texture, SKSE, ecc.) viene copiato senza modifiche.

## Come protegge la struttura
1. **Whitelist**: un campo è tradotto solo se (tipo record, sottorecord) è in tabella e il contenuto è una zstring valida. Il resto resta byte per byte.
2. **Segnaposto**: tag `<Alias=...>`, `<mag>`, a capo, `[pagebreak]`, `%d`, `{0}`, `$CHIAVE` sono sostituiti con `<x0/>`... prima di inviare il testo all'AI; se la risposta non li contiene tutti, esattamente una volta, la traduzione è scartata e resta l'originale.
3. **Ricostruzione**: si ricalcolano solo le dimensioni (sottorecord, record, gruppi) e si ricomprimono i record compressi.
4. **Verifica finale**: ogni file prodotto viene riletto e confrontato con l'originale; se cambia altro oltre alle stringhe ammesse, il file resta originale.
5. Caratteri non supportati dalla codifica del gioco (cp1252/1251/1250): la stringa resta originale.

## Limiti noti
- Skyrim: niente giapponese/cinese (richiedono font e codifiche specifiche).
- Testi dentro gli script Papyrus compilati (`.pex`) non sono toccati: se una mod mostra messaggi da script, quelli restano in inglese.
- Le tabelle dei campi sono conservative: vanno verificate su mod reali e ampliate.
- Per altri giochi basta aggiungere un modulo come `plugin.py` + una tabella.
