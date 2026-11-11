---
name: log-access-protocol
description: "Protocollo di lettura dei log applicativi su OpenSearch (per ambiente, cluster e app del registro) in sola lettura, con mascheramento dei dati personali attivo di default (opzionale, consigliato sugli ambienti protetti). Dal largo allo stretto, rumore per profilo, errori gestiti, seguire una richiesta tra i servizi via trace, analisi di ticket e di errori su una feature. Capability opt-in log_access. Tool: tools/logs/log_access.py."
---

# Protocollo di lettura dei log — 5 fasi

Skill procedurale della capability opt-in `log_access` (`factory.config.yaml → log_access`, `enabled: false` di default).
Invocata da `/log` e dall'agente `log-operator`. Tutte le operazioni passano da
`tools/logs/log_access.py`: **mai** `curl`, richieste dirette a OpenSearch o Dashboards,
credenziali in chiaro in chat, nei comandi o nei file.

## Fonti

| Cosa | Dove |
|---|---|
| Cluster, ambienti, app (index, namespace, mappa dei campi, profilo di rumore, `data_from`) | `tools/logs/log-targets.yaml` (copia di `log-targets.example.yaml`, che documenta ogni chiave) |
| Credenziali | file `env_file` del target (gitignored: `log_access.env_file`, sovrascrivibile per cluster/app nel registro), poi ambiente del processo; nomi delle variabili nel registro per cluster |
| Rumore escluso di default | `tools/logs/noise/<profilo>.json`, uno per profilo d'app |
| Errori gestiti (attesi, nascosti e riassunti) | `tools/logs/handled/<profilo>.json`, uno per profilo d'app |
| Politiche (ambienti protetti, fuso, pattern di mascheramento, limiti, timeout) | `factory.config.yaml → log_access` |
| Regole d'uso aggiornate | `log_access.py guide [<env> <app>]`: stanno nel programma, rileggile a inizio sessione |

## Invocazione del tool

```bash
PY=python3; command -v python3 >/dev/null && python3 -c '' 2>/dev/null || PY=python
$PY tools/logs/log_access.py <sottocomando> ...
```

Su Windows `python3` può essere l'alias dello Store: il ripiego su `python` è voluto. Niente
virgolette doppie dentro gli argomenti (con pyenv-win si perdono): usa frasi senza simboli.
`targets`, `check` e gli errori escono in JSON; `search`, `count`, `noise`, `fields`,
`namespaces` escono in testo compatto, con righe `#` di intestazione.

| Exit | Significato | Cosa fare |
|---|---|---|
| 0 | ok | — |
| 1 | uso/config (ambiente o app ignoti, credenziali assenti, capability spenta, data non valida, `--out` vietato su ambiente protetto, `bad_config`) | riportare `error` + `available` / `expected_vars` / `forbidden_dirs` |
| 2 | connessione, login o TLS | VPN attiva? credenziali giuste? per `tls` vedi i fingerprint nel JSON: certificato da riesportare. Un solo tentativo, mai in loop |
| 5 | il cluster ha rifiutato la ricerca | riportare `detail`; di solito campo o query errati |
| 6 | timeout | restringere finestra e filtri |

---

## Fase 1 — Boot

1. `log_access.enabled: false` → ABORT pulito (lo dice anche il tool).
2. Risolvi **ambiente** e **app**. Se l'utente non li indica o sono ambigui, chiedi. Non
   scegliere mai un ambiente protetto per default. Gli alias li dichiara il registro (nomi degli ambienti).
3. `log_access.py targets --env <env>`: la coppia esiste? `credentials_ready`? Se no → stop con
   le variabili da aggiungere al file `env_file` del target (`credential_candidates`, `env_file`).
   `unverified: true` → avvisa che il target va confermato (Fase 1.4). Un ambiente assente dal
   registro non si interroga: si propone di aggiungerlo (cluster + app in `log-targets.yaml`).
4. Prima operazione della sessione su un target: `check <env> <app>` e riporta in una riga
   ultimo evento, righe nell'ultima ora e `data_from`. `total_rows: 0` o `warning` = namespace o
   index sbagliati: `namespaces <env>` mostra i namespace realmente presenti (marca quelli registrati).
   Se un target `unverified` risulta corretto, segnalalo all'utente: toglie il flag lui, in un
   commit del registro.

## Fase 2 — Dal largo allo stretto

Ordine da seguire per non riempire il contesto:

1. **count** prima di **search**: `--by <campo container>`, `--by <campo livello>`, `--histogram 10m` (i nomi dei campi
   sono quelli del target: default `kubernetes.container_name`, `logLevel`; `fields <env> <app>` mostra quelli reali).
2. **Finestra breve**: `--since 15m..2h`, oppure `--since/--until` ISO (nel fuso `log_access.timezone`, default UTC), oppure
   `--around <orario evento> [--window 15m]` quando il ticket dà un orario preciso.
3. **search con filtri stretti**: `--container`, `--level ERROR --level WARN`, `--message`, `--size 20-50`.
4. **Seguire la richiesta**: dal `trace=` della riga d'errore, `--trace <id> --asc` (con `--with-noise`
   se serve anche il DEBUG). Per sapere quale chiamata HTTP l'ha causata: `--trace <id> --message` con la frase che il
   servizio scrive per ogni richiesta in ingresso.
5. `--max-chars 0`, `--full-stack`, `--raw` solo sulle poche righe che servono davvero.

Tre fatti di lettura che evitano diagnosi sbagliate (altri sono in `log_access.py guide`: ad esempio alcuni servizi
scrivono testo semplice, con livello e trace id dentro il `message`, quindi `--trace` non li trova):

- Un `ERROR` non è per forza un guasto: certi filtri di logging scrivono richieste e risposte a livello ERROR anche per i 4xx.
- La causa vera sta quasi sempre nello stack trace (campi `fields.stack`, default `stack_trace` o `err.stack`), non nel `message`:
  `search` lo mostra sotto, accorciato; `--full-stack` lo mostra intero.
- Una finestra senza righe **non prova** che l'evento non sia avvenuto: controlla `data_from`, il
  `namespace` e i filtri prima di scriverlo.

## Fase 3 — Rumore

- Le regole del profilo dell'app sono escluse di default; l'intestazione dice quante righe ha tolto ciascuna.
- Se l'output è dominato da uno schema ripetuto il tool lo segnala: lancia `noise <env> <app>` sulla
  stessa finestra. Le regole candidate escono numerate (`c1`, `c2`, …) con il comando `noise-add` pronto.

**Riconoscimento del rumore con conferma dell'utente** (nessuna regola entra da sola):

1. **Proposta.** Dai candidati di `noise` scegli quelli sensati e presentali all'utente con
   `AskUserQuestion` (multiselezione): per ognuno container/logger/livello/frase, la quota che pesa e un
   esempio di messaggio. Non proporre candidati ERROR/WARN come «rumore» se non è dimostrato che sono innocui.
2. **Anteprima.** Per ogni candidata scelta: `noise-add <env> <app> --container … [--logger …] [--level …]
   [--message …]` (senza `--confirm`). Il tool non scrive: misura sulla finestra quante righe toglierebbe, per
   livello, con avvisi (righe ERROR/WARN, regola troppo ampia o che non corrisponde a nulla, **app che
   condividono il profilo**) e un token valido 30 minuti. Se tocca ERROR/WARN il token non esce senza
   `--allow-error-level`: concedilo solo se l'utente ha confermato che sono innocui.
3. **Conferma.** Mostra all'utente regola, impatto e avvisi con `AskUserQuestion` («Aggiungi al profilo» /
   «Non aggiungere»). Il profilo è condiviso fra più app e fra più ambienti: dillo.
4. **Scrittura.** Solo dopo il sì: lo stesso comando con `--reason '<perché è rumore>' --confirm <token>`.
   Il tool aggiunge la regola a `tools/logs/noise/<profilo>.json` (con `reason` e `added`), senza connettersi
   al cluster; il token è monouso. Un subagente non esegue mai `--confirm`: restituisce le anteprime
   nel report (`noise_proposals`) e la conferma resta alla sessione principale.
5. **Traccia.** Il file di profilo è versionato: la modifica va in un commit normale, non resta silenziosa.
   Riporta all'utente quali regole sono state aggiunte e che il commit va fatto.
- Per lo smistamento degli errori di un servizio, `noise --container X --level ERROR --since 30d`
  raggruppa per logger e schema; in quel caso le «regole candidate» non vanno proposte.

## Fase 3-bis — Errori gestiti

Un **errore gestito** è un errore ATTESO che l'applicazione usa di proposito (esempio: un `409` del gateway che il
frontend usa per mostrare la scelta del tenant). Non è rumore da ignorare e non è un
guasto: per non saturare contesto e token **non compare nell'elenco** di `search` e `count`, ma l'intestazione
ne riassume una riga per regola (nome, conteggio, primo e ultimo orario).

- `--show-handled` li include nell'elenco, con l'etichetta `[gestito: nome]`: serve quando l'indagine riguarda
  proprio quel flusso.
- **Non sono un'assoluzione**: un errore gestito che cresce in modo anomalo va guardato. Confronta il conteggio fra
  finestre (`count --message <frase> --histogram 1h`) e dillo all'utente se il volume non è plausibile.
- Registrazione di un nuovo errore gestito: solo su indicazione dell'utente (è lui che sa che è atteso), con lo
  stesso flusso del rumore: `handled-add` senza `--confirm` (anteprima: righe, livelli, app che condividono il
  profilo, token), conferma esplicita con `AskUserQuestion`, poi `--reason '<perché è atteso>' --confirm <token>`.
  Diversamente dal rumore, ERROR/WARN sono ammessi senza `--allow-error-level`. Un subagente non esegue mai
  `--confirm`. Il file è `tools/logs/handled/<profilo>.json` (versionato: commit normale).
- Un errore simile e non registrato (es. un altro codice di stato) resta un errore a tutti gli effetti: non
  presumere che sia atteso, chiedilo all'utente.

## Fase 4 — Analisi di un ticket o di una feature

Ricetta, nell'ordine:

1. **Dal ticket**: ambiente, app, orario (o intervallo) dell'evento nel fuso configurato, eventuale
   URL/funzione/trace. Se l'orario manca, chiedilo o parti da `count --histogram` su una finestra larga.
2. **Perimetro**: `count --around <orario> --by kubernetes.container_name` poi `--by logLevel`.
3. **Errori**: `search --around <orario> --level ERROR --level WARN --container <svc> --size 30`.
4. **Causa**: stack trace della riga che coincide con il sintomo; trace → `--trace <id> --asc`.
5. **Confronto**: stessa finestra su un altro ambiente se l'utente vuole sapere se è un problema solo di quell'ambiente.
   Più cluster = più chiamate, una per ambiente: `targets` dice dove sta ciascuno.
6. **Esito**: causa probabile, evidenza, cosa non è stato possibile verificare.
7. **Con il DB**: se il sintomo riguarda un dato, passa gli identificativi trovati nei log a `/db`
   (`indagine-protocol`: i log dicono cosa è successo, il DB com'è lo stato adesso).

**Citazione dell'evidenza** (R.2, R.3): ogni affermazione sui log cita ambiente/app, finestra
nel fuso configurato, filtri e numero di righe, ad esempio
`(log prod/checkout, 2026-11-05 09:00–09:30, container=gateway level=ERROR: 14 righe)`.
Non si riporta mai un fatto dei log senza questa riga di provenienza e non si deduce quello
che i log non dicono.

**Blocco di evidenze** (quando l'analisi serve a un TSK o a un'indagine): stessi campi del report di
`db-access-protocol` (sezione «Blocco di evidenze»), così i due si uniscono:

```json
{"env": "prod", "window": {"from": "2026-11-05T09:00", "to": "2026-11-05T09:30", "tz": "<log_access.timezone>"},
 "ids": {"tenant": "...", "request_id": "...", "trace": "...", "utente": "..."},
 "findings": [{"claim": "...", "source": "log", "where": "prod/checkout", "how": "container=gateway level=ERROR",
               "rows": 14, "evidence": "log prod/checkout, 2026-11-05 09:00-09:30, container=gateway level=ERROR: 14 righe"}],
 "not_verified": ["..."]}
```

La finestra è nel fuso configurato. Su ambienti protetti `findings` riporta conteggi, schemi di messaggio e conclusioni,
non righe di log.

## Fase 5 — Presentazione e chiusura

- Il mascheramento dei dati personali è **attivo di default ed è consigliato**, soprattutto su
  gli ambienti protetti: email, nomi di persona nei campi strutturati e i pattern attivati in `log_access.mask_patterns`
  (insiemi nominati, ad esempio `it-codice-fiscale`, `it-partita-iva`; regex proprie in `mask_custom_patterns`) diventano
  segnaposto con hash HMAC (`<EMAIL#a1b2c3>`), con chiave nuova a ogni esecuzione: validi **solo nella stessa esecuzione**.
  Un pattern non attivato non maschera nulla: scegli quelli giusti per i dati che i tuoi log contengono. Per riconoscere lo stesso soggetto su
  più righe resta in UNA esecuzione. Per cercare un soggetto passalo a `--message`.
- `--no-mask` lascia i dati personali in chiaro per quell'esecuzione: si usa solo su richiesta
  dell'utente per quella indagine, quando il dato stesso è l'oggetto dell'analisi (es. capire perché
  un certo codice fiscale fallisce). Il tool lo scrive nell'intestazione dell'output. Prima su un
  ambiente protetto si prova senza `--no-mask`; con `--no-mask` valgono a maggior ragione il divieto
  di copiare righe fuori dalla sessione e quello di citarle in TSK, gap, wiki, commit. I segreti
  (token, JWT, password, chiavi) restano mascherati comunque. `log_access.mask_personal_data: false`
  inverte il default.
- Mostra al massimo le righe che servono, non l'intero risultato. Non incollare in chat output
  più lungo del necessario.
- Su ambienti protetti (`log_access.protected_envs`, default `[prod]`) **mai** copiare righe di log in `raw/`,
  `wiki/`, `deliverables/`, kanban, `wiki/log.md`, commit o report di sessione. In un TSK, gap
  o incidente si scrive la conclusione con la riga di provenienza della Fase 4, non le righe.
  La wiki resta di wiki-keeper (R.12): se serve una pagina, passa da lui con la sintesi.
  Non e' solo una regola di prompt: `--out` verso `raw/`, `wiki/`, `deliverables/` o `management/`
  (`log_access.protected_out_forbidden_dirs`) e' **rifiutato dal codice** per gli ambienti protetti, prima di ogni
  connessione, sul percorso reale (`..` e link simbolici compresi; exit 1, `protected_out_forbidden`).
  Resta un controllo sul canale `--out`: il copia-incolla da chat non e' intercettabile, vale la regola.
- Mai credenziali o URL con credenziali nel report di sessione.
- La capability è di sola lettura: nessuna scrittura sul cluster esiste, quindi nessun gate R.14.

## Invarianti

- **LG-1**: il tool esegue solo `_search`, `_count`, `_field_caps`, su index e namespace del
  registro. Non esiste passthrough di richieste arbitrarie e non c'è `--index`/`--namespace` libero.
- **LG-2**: i segreti sono sempre mascherati; i dati personali lo sono di default (anche per `--raw`,
  `--dry-run` ed errori) e restano in chiaro solo per scelta esplicita dell'utente con `--no-mask`.
- **LG-3**: nessun segreto in output, argomenti di comando, file versionati o log; la verifica
  del certificato TLS non si disattiva.
- **LG-6**: nessuna regola di rumore senza anteprima dell'impatto e conferma esplicita dell'utente sulla
  stessa regola; il token dell'anteprima è monouso e scade.
- **LG-7**: un errore è «gestito» solo se l'utente lo ha dichiarato atteso e la regola è stata registrata con
  anteprima e conferma; nascosto dall'elenco, resta sempre contato nell'intestazione.
- **LG-4**: nessun fatto dedotto dall'assenza di righe senza aver dichiarato finestra, filtri e
  `data_from`.
- **LG-8**: l'output di un ambiente protetto non si scrive con `--out` nelle cartelle di conoscenza
  (`protected_out_forbidden_dirs`): controllo nel codice (`check_out_path`), non solo istruzione.
- **LG-9**: nessun pattern di dati personali specifico di un paese o cliente e' cablato: si attivano per nome
  (`mask_patterns`) o con regex proprie (`mask_custom_patterns`); la mappa dei campi e' del target, non del codice.
- **LG-5**: il registro dichiara dove leggere; cosa si vede lo decide l'utenza OpenSearch, che ha
  l'ultima parola.
