# skyrimtrans

Traduce le mod di Skyrim (LE/SE) con Claude, toccando **solo il testo**.

## Interfaccia grafica
```bash
pip install -e .[anthropic,7z]
skyrimtrans-gui          # si apre nel browser, trascini la mod e scegli lingua e servizio AI
```
Gira solo sul tuo PC (127.0.0.1). La chiave API non viene salvata su disco. "Solo analisi" mostra quante stringhe verrebbero tradotte senza chiamare nessuna AI.

## Eseguibile Windows (.exe)
Senza installare Python: su GitHub vai in **Actions → Build SkyrimTrans for Windows → Run workflow**, poi scarica `SkyrimTrans-windows.zip` dagli artifact. Dentro c'è `SkyrimTrans.exe`: lo avvii, si apre il browser e resta una finestra nera aperta (chiudila per spegnere il programma).
In alternativa, su un PC Windows con Python: doppio clic su `build_exe.bat` (crea `dist\SkyrimTrans.exe`).

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

## Contesto della mod
Il modello riceve, oltre alle stringhe, un breve contesto sulla mod e il tipo di record di ogni testo (arma, pozione, NPC...), per scegliere tono e termini giusti.
1. **Sempre, in locale:** autore, descrizione e dipendenze lette dal plugin (es. `Requiem.esp`).
2. **Facoltativo, Nexus Mods:** inserisci il link o l'ID della mod (viene proposto quello nel nome del file scaricato) e la tua chiave API personale (gratuita: Nexus → Account → API). Si usa l'API ufficiale; la chiave non viene salvata. Da riga di comando: `--nexus auto --nexus-key ...` (o `NEXUS_API_KEY`).
3. **Riassunto:** con i dati di Nexus il modello scrive un riassunto di massimo 120 parole, che nell'interfaccia puoi correggere prima di tradurre (o passare tu con `--brief` / `--brief-file`). Il testo preso dal web è trattato come dato, mai come istruzione.

## Coerenza dei termini
I nomi (armi, oggetti, luoghi...) vengono tradotti per primi e ricordati: quando lo stesso nome compare in un testo successivo (descrizioni, libri, dialoghi, quest, MCM), la traduzione già scelta viene ripassata al modello, anche se il testo cade in un altro lotto. Il glossario dell'utente ha sempre la precedenza.

## Limiti noti
- Skyrim: niente giapponese/cinese (richiedono font e codifiche specifiche).
- Testi dentro gli script Papyrus compilati (`.pex`) non sono toccati: se una mod mostra messaggi da script, quelli restano in inglese.
- Le tabelle dei campi sono conservative: vanno verificate su mod reali e ampliate.
- Per altri giochi basta aggiungere un modulo come `plugin.py` + una tabella.
