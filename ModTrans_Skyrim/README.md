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

Input: cartella, `.zip`, `.7z` o singolo `.esp/.esm/.esl`. Output: zip (o cartella) con la stessa struttura.

### Dove salvare il risultato
- **Interfaccia:** in "Dove salvare" scegli *Scarica dal browser* oppure una **cartella** del tuo PC (con selettore e "Nuova cartella"), come zip oppure come cartella già pronta da copiare in `Data`. Non sovrascrive mai: se il nome esiste aggiunge " (2)". Finito, "Apri la cartella".
- **Riga di comando:** `-o percorso.zip`, `--out-dir CARTELLA`, `--as-folder` (cartella invece di zip), `--overwrite`.

## Memoria e ripresa
Ogni traduzione riuscita viene salvata subito in `~/.skyrimtrans/memory` (una per lingua + modello + glossario). Se la corsa si interrompe (rete, limiti del servizio, chiusura del programma) rilanci la stessa mod e riparte da dove era: nulla viene rifatto né ripagato. Le stesse traduzioni vengono riusate in altre mod.
- Errori temporanei e limiti di richieste: nuovi tentativi con attesa crescente (rispetta `Retry-After`). Chiave/modello errati: ci si ferma subito con un messaggio chiaro. Tre lotti di fila senza risposta valida: la corsa si ferma, il lavoro fatto resta salvato.
- `--fresh` ritraduce tutto aggiornando la memoria; `--no-memory` non la usa. Nell'interfaccia: casella "Usa la memoria" e "Svuota la memoria".

## Mod con archivi `.bsa`
Le mod localizzate spesso tengono `Strings/*.STRINGS` e i file MCM dentro il proprio `.bsa`. Vengono letti da lì (Skyrim LE v104 e SE v105; l'archivio non viene mai modificato) e le traduzioni sono scritte come **file sciolti**, che in Skyrim hanno la precedenza sull'archivio. Un `.bsa` non leggibile genera un avviso, non un errore.

## Controlli di qualità
Locali e gratuiti, su ogni stringa tradotta:
- **numeri cambiati** (nomi, descrizioni, pulsanti, messaggi, obiettivi) e **premesse del modello** ("Ecco la traduzione...", virgolette aggiunte, blocchi di codice): la stringa viene richiesta di nuovo; se il difetto resta, rimane l'originale e compare nel report;
- **stringa identica all'originale** (di più parole): avviso, non viene scartata;
- **testi d'interfaccia troppo lunghi** (nomi, pulsanti, scelte di dialogo, obiettivi, voci MCM): un passaggio in più li fa riscrivere più brevi (attivo di default; `--no-shorten` o casella "Accorcia" per spegnerlo); se restano lunghi c'è un avviso.
- **Revisione finale con l'AI** (facoltativa, `--review` o casella): un secondo passaggio rilegge le traduzioni nuove e propone correzioni solo per errori evidenti. Le correzioni passano gli stessi controlli dei segnaposto; quelle non valide vengono scartate. Costa circa una richiesta in più ogni 30 stringhe.

## Cosa traduce
| File | Cosa |
|---|---|
| `.esp/.esm/.esl` non localizzati | solo i sottorecord testuali in `skyrimtrans/tables.py` (nomi, descrizioni, libri, dialoghi, quest, messaggi) |
| `*_ENGLISH.STRINGS/DLSTRINGS/ILSTRINGS` (anche dentro `.bsa`) | tutte le stringhe; crea `*_<LINGUA>.*`, il plugin non cambia |
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

## Glossario ufficiale dal gioco
I nomi di armi, luoghi, incantesimi, fazioni e creature hanno già una traduzione ufficiale: sta nei file del gioco. Il programma la ricava accoppiando, per ID, `Skyrim_english.STRINGS` e `Skyrim_italian.STRINGS` (e quelli di Dawnguard, Dragonborn, Hearthfire), sia sciolti in `Data/Strings` sia dentro i `.bsa`. Serve Skyrim installato nella lingua di destinazione.
```bash
python -m skyrimtrans glossario "C:\...\Skyrim Special Edition\Data" -l italian   # crea glossario_italian.json
python -m skyrimtrans MiaMod.zip -l italian --game-glossary glossario_italian.json
python -m skyrimtrans MiaMod.zip -l italian --game-data "C:\...\Data"              # lo costruisce al volo
```
Nell'interfaccia: campo "Nomi ufficiali del gioco" con la cartella Data. Il glossario si costruisce sul tuo PC dai tuoi file: nessun testo del gioco è incluso nel programma.
- Entrano solo nomi (1-6 parole, iniziale maiuscola, senza tag). Restano fuori le frasi, i nomi uguali in entrambe le lingue e quelli con più traduzioni diverse nel gioco (si tiene quella usata più spesso se prevale).
- Il glossario è grande, quindi a ogni richiesta il modello riceve **solo i termini presenti in quel lotto**. Il tuo `--glossary` resta sempre intero nel prompt e ha la precedenza.

## Coerenza dei termini
I nomi (armi, oggetti, luoghi...) vengono tradotti per primi e ricordati: quando lo stesso nome compare in un testo successivo (descrizioni, libri, dialoghi, quest, MCM), la traduzione già scelta viene ripassata al modello, anche se il testo cade in un altro lotto. Il glossario dell'utente ha sempre la precedenza.

## Limiti noti
- L'audio (`.fuz`/`.xwm`) e le scritte dentro le texture non si possono tradurre: i dialoghi parlati restano in inglese, cambia solo il sottotitolo.
- Non coperti: testi in `.pex`, file `.swf`, JSON/INI di SKSE.
- Skyrim: niente giapponese/cinese (richiedono font e codifiche specifiche).
- Testi dentro gli script Papyrus compilati (`.pex`) non sono toccati: se una mod mostra messaggi da script, quelli restano in inglese.
- Le tabelle dei campi sono conservative: vanno verificate su mod reali e ampliate.
- Per altri giochi basta aggiungere un modulo come `plugin.py` + una tabella.
