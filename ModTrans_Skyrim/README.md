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

## Editor delle stringhe (stile xTranslator)
Con il pulsante **Stringhe** si apre una tabella con ogni stringa della mod: tipo e file, **testo originale** e **traduzione** affiancati. Funziona in tre momenti:
- **Prima** della traduzione: sulla mod caricata (pulsante nella lista "Pronta"). Si vedono già tutte le righe e si possono scrivere traduzioni a mano: quando poi lanci la traduzione, quelle righe non vengono mandate all'AI e restano come le hai scritte.
- **Durante**: sulla mod in corso, le righe si riempiono man mano che l'AI traduce.
- **Dopo**: sulla mod finita. Correggi una riga e premi **Salva nel file**: il programma riscrive il risultato (zip della cronologia o cartella scelta) con le tue correzioni.

Cosa si può fare: cercare nel testo, filtrare per stato (da tradurre / tradotte dall'AI / modificate a mano / non riuscite) e per file, **modificare a mano** ogni traduzione, **tradurre con l'AI una singola riga** (pulsante "AI") o **tutte quelle filtrate** (una nuova risposta ogni volta, senza usare la memoria). Righe vuote o senza testo sono segnate e non si toccano.

Controlli sulle modifiche a mano: i tag e i segnaposto dell'originale (`<Alias=Player>`, `<mag>`, `%s`, `[pagebreak]`...) devono restare uguali, e il testo deve stare nella codifica del gioco; altrimenti la riga viene rifiutata con il motivo. Testo vuoto = torna alla traduzione dell'AI (o all'originale). Come sempre, il file riscritto viene verificato (struttura identica tranne i testi).

Limiti: restano aperte solo le ultime 3 mod (ognuna occupa lo spazio della mod estratta); una mod vecchia o della cronologia dopo il riavvio non si può riaprire nell'editor, va ritradotta. Per tradurre righe con l'AI da una mod non ancora in coda vengono usate le impostazioni del modulo della pagina; per una mod in coda, quelle della sua coda.

## Coda e cronologia (interfaccia)
- **Coda:** trascina più mod insieme (o aggiungine altre mentre una è in corso) e premi *Traduci*: vengono tradotte **una alla volta**, la successiva parte da sola. Ogni mod ha il suo contesto (clic su "Contesto" prima di avviare); le impostazioni (lingua, servizio AI, cartella di output...) sono quelle del momento in cui premi *Traduci*. Puoi annullare una mod in attesa, annullare tutte quelle in attesa o riprovare una mod fallita o annullata ("Riprova"; per una mod finita con stringhe non tradotte, "Riprova le fallite" riusa la memoria e rifà solo quelle).
- **Più code in parallelo:** ogni coda ha le **sue impostazioni** (servizio AI e chiave, modello, lingua, cartella di output...) e traduce una mod alla volta; code diverse girano **insieme**. Per aprirne una nuova scegli "Una nuova coda" accanto a *Traduci* (massimo 6). Esempi: Claude per le mod grandi e un modello locale per le piccole, oppure due chiavi API diverse per dimezzare i tempi. Quando aggiungi mod a una coda esistente valgono le impostazioni della coda. Per cambiarle usa **"Modifica"** nell'intestazione della coda: si apre una finestra con i valori attuali (servizio, modello, indirizzo, lingue, stringhe per richiesta) e cambi solo quello che ti serve, per esempio il modello, **tenendo la stessa API e la stessa chiave** (la chiave vuota = resta quella attuale; si sostituisce solo scrivendone una nuova). Vale per le mod in attesa e per quelle nuove; la mod già in corso finisce con le impostazioni di prima. "Usa le impostazioni qui sotto" copia invece tutto il modulo della pagina nella coda. "Chiudi" toglie una coda vuota (le mod finite restano in cronologia).
  - Con **la stessa chiave** su più code si raggiungono prima i limiti di richieste del servizio: il programma rallenta e riprova da solo, ma il guadagno di tempo può essere minore.
  - Code con lo stesso modello e la stessa lingua condividono la memoria delle traduzioni: se due code traducono lo stesso testo nello stesso momento, lo pagano entrambe.
- **Pausa automatica (per coda):** se il servizio AI non risponde o rifiuta la chiave, **quella** coda si ferma con un avviso, le altre continuano. "Riprendi" la fa ripartire dalla mod successiva.
- **Cronologia:** ogni mod tradotta resta in elenco anche dopo aver chiuso il programma, con data, numeri, avvisi e un pulsante per **scaricare** lo zip (o aprire la cartella, se l'hai salvata sul PC), anche mentre un'altra mod è in traduzione. Gli zip sono in `~/.skyrimtrans/history` (occupano spazio: "Elimina" e "Svuota la cronologia" li cancellano). Togliere dalla cronologia una mod salvata in una tua cartella **non** cancella mai quella cartella.
- **Code e chiavi salvate (facoltativo):** di base le code e le chiavi API restano solo in memoria e spariscono alla chiusura del programma. Spunta **"Ricorda le code e le chiavi API su questo PC"** (accanto a *Traduci*) per ritrovarle al prossimo avvio, ognuna con la sua chiave. Come funziona:
  - tutto è salvato in `~/.skyrimtrans/lanes.json` **in chiaro** (non cifrato), leggibile solo dal tuo utente (permessi 0600); non usarlo su un PC condiviso. Il programma chiede conferma prima di attivarlo.
  - la chiave non torna mai al browser: nella pagina vedi solo "chiave salvata"; se modifichi le impostazioni di una coda lasciando vuota la chiave, resta quella già salvata.
  - "Chiudi" su una coda la dimentica; togliendo la spunta il file con le chiavi viene **cancellato** e da quel momento non si salva più nulla. Le mod in attesa o in corso non vengono salvate, solo le code.
  - se `lanes.json` è illeggibile viene ignorato (si parte con una coda vuota) senza bloccare il programma.

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
- **Risposte rovinate del modello** (fuori formato, tagliate a metà, con virgolette non protette, stringhe saltate): il programma recupera quello che si può leggere e richiede solo il resto; se un lotto fallisce del tutto lo **divide a metà** e riprova ogni metà (40 → 20 → 10 ...), invece di ripetere la stessa richiesta. Con un modello che non risponde mai in formato valido l'esecuzione si ferma lo stesso presto, con le traduzioni già fatte al sicuro in memoria. Se capita spesso, un modello più capace o meno stringhe per richiesta restano la soluzione migliore.
- **Revisione finale con l'AI** (facoltativa, `--review` o casella): un secondo passaggio rilegge le traduzioni nuove e propone correzioni solo per errori evidenti. Le correzioni passano gli stessi controlli dei segnaposto; quelle non valide vengono scartate. Costa circa una richiesta in più ogni 30 stringhe.

## Cosa traduce
| File | Cosa |
|---|---|
| `.esp/.esm/.esl` non localizzati | solo i sottorecord testuali in `skyrimtrans/tables.py` (nomi, descrizioni, libri, dialoghi, quest, messaggi) |
| `*_ENGLISH.STRINGS/DLSTRINGS/ILSTRINGS` (anche dentro `.bsa`) | tutte le stringhe; crea `*_<LINGUA>.*`, il plugin non cambia |
| `Interface/Translations/*_ENGLISH.txt` (MCM) | solo il testo dopo il tab; crea `*_<LINGUA>.txt` |
| `*.json` | **l'AI decide quali campi sono testo** (vedi sotto); i campi `lines[].text` con `id` sono sempre tradotti. Il file mantiene nome e posizione e cambiano solo le stringhe scelte (spazi, rientri e ordine restano identici); dopo la scrittura si verifica che nient'altro sia cambiato, altrimenti il file resta originale |

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
- Entra solo ciò che il modello non sa già. Tolgo le traduzioni ovvie: le parole comuni con una sola parola per lato (`Gold → Oro`: «gold» compare in minuscolo spesso nei testi del gioco) e i nomi composti alla lettera (`Iron Sword → Spada di Ferro`, quando ogni parola ha già la sua traduzione nel gioco). Restano i nomi particolari (`Dragonborn → Sangue di Drago`) e, nel dubbio, tutto ciò che non so classificare.
- Entrano solo nomi (1-6 parole, iniziale maiuscola, senza tag). Restano fuori le frasi, i nomi uguali in entrambe le lingue e quelli con più traduzioni diverse nel gioco (si tiene quella usata più spesso se prevale).
- Il glossario è grande, quindi a ogni richiesta il modello riceve **solo i termini presenti in quel lotto**. Il tuo `--glossary` resta sempre intero nel prompt e ha la precedenza.

## JSON e dati delle mod: come si decide cosa tradurre
Molte mod (framework di dialoghi, ecc.) tengono i testi dentro JSON insieme a dati che il codice della mod usa (id, tag, tipi di evento, condizioni...). Per ogni mod il programma:
1. legge tutti i `.json` e raggruppa le stringhe per **percorso generico** (`answers[].text`, `questions[].label`...: i nomi delle sezioni cambiano da un blocco all'altro, il percorso no);
2. scarta in locale i valori che sono chiaramente codice (`>=0`, `ddf.va.sex1.12`, percorsi di file, `snake_case`, `camelCase`, numeri);
3. manda **una richiesta** all'AI con le istruzioni del lavoro, i percorsi, quante volte compaiono e qualche esempio; l'AI risponde quali sono testo per il giocatore (battute, risposte, domande, etichette...) e quali no. Nel dubbio deve rispondere no: tradurre per errore un codice rompe la mod, lasciare una frase in inglese no;
4. traduce solo quei campi, sostituendoli nel testo originale e verificando che il resto sia identico.

Se l'AI non risponde in modo utilizzabile (o in prova a secco) si usa un **ripiego** su nomi di campo tipici (`text`, `answer`, `question`, `label`, `title`, `description`...) con valori che sembrano frasi, e compare un avviso. L'elenco dei campi tradotti e di quelli lasciati com'erano è tra gli avvisi ("Info: campi JSON ...") e nel report. Se l'AI sbaglia un campo: da riga di comando `--json-include "answers[].label"` (traduci sempre) e `--json-exclude "questions[].mood"` (mai), ripetibili e con `*`; `--json-mode known` limita tutto a `lines[].text`. Non è ancora nell'interfaccia grafica.

## Coerenza dei termini
I nomi (armi, oggetti, luoghi...) vengono tradotti per primi e ricordati: quando lo stesso nome compare in un testo successivo (descrizioni, libri, dialoghi, quest, MCM), la traduzione già scelta viene ripassata al modello, anche se il testo cade in un altro lotto. Il glossario dell'utente ha sempre la precedenza.

## Limiti noti
- L'audio (`.fuz`/`.xwm`) e le scritte dentro le texture non si possono tradurre: i dialoghi parlati restano in inglese, cambia solo il sottotitolo.
- Non coperti: testi in `.pex`, file `.swf`, JSON/INI di SKSE.
- Skyrim: niente giapponese/cinese (richiedono font e codifiche specifiche).
- Testi dentro gli script Papyrus compilati (`.pex`) non sono toccati: se una mod mostra messaggi da script, quelli restano in inglese.
- Le tabelle dei campi sono conservative: vanno verificate su mod reali e ampliate.
- Per altri giochi basta aggiungere un modulo come `plugin.py` + una tabella.
