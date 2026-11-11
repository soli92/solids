---
name: db-access-protocol
description: "Protocollo di accesso ai database PostgreSQL (capability opt-in db_access) con le credenziali personali di un file .env locale scelte per ambiente. Navigazione da servizio, schema o tabella al DB giusto (locate, tables, describe), catalogo DDL versionato con avviso di obsolescenza, mappa funzionalita' - servizio - tabella, gate di costo con EXPLAIN. Lettura validata e in transazione READ ONLY lato server; ambienti in read_only_envs mai scritti; scrittura SPENTA per default (db_access.write.enabled) e, se accesa, solo dopo dry-run con ROLLBACK e gate umano R.14. Tool: tools/db/db_access.py, db_catalog.py, db_map.py."
---

# Protocollo di accesso ai DB PostgreSQL — 5 fasi

Skill procedurale della capability `db_access` (`factory.config.yaml → db_access`).
Invocata da `/db` e dall'agente `db-operator`. Tutte le operazioni passano da
`tools/db/db_access.py`: **mai** `psql`, `psycopg` o stringhe di connessione scritte a mano,
mai credenziali in chiaro in chat, nei comandi o nei file.

## Fonti

| Cosa | Dove |
|---|---|
| Endpoint per ambiente (host, porta, database, schemi) | `tools/db/db-targets.yaml` (copia di `db-targets.example.yaml`, che ha solo host fittizi) |
| Servizio → database e schemi | `tools/db/db-targets.yaml → services` (ogni voce con `source`), poi `locate` |
| Credenziali | file `db_access.env_file` (default `.env.db`, **gitignored: verificarlo prima di compilarlo**), unica fonte; i nomi delle variabili per host stanno nel registro |
| TLS | `db_access.sslmode`, default `verify-full`; un valore piu' debole solo se dichiarato nel registro o nella config, e ogni connessione stampa un avviso |
| Ambienti in sola lettura | `factory.config.yaml → db_access.read_only_envs` (default `prod`) |
| Scrittura | `factory.config.yaml → db_access.write.enabled` (default `false`) |
| Politiche (ambienti protetti, timeout, TTL, audit) | `factory.config.yaml → db_access` |
| Privilegi effettivi | `db_access.py check <env> <target>`: **l'unica fonte**, il registro non li dichiara |
| Catalogo DDL (tabelle, colonne, vincoli, funzioni; mai dati di riga) | `<db_access.catalog.dir>/<env>/<db>/<schema>.sql` + `manifest.json` (default `memory/semantic/db-catalog`); stato con `tools/db/db_catalog.py` |
| Mappa funzionalità → servizio → tabella | `<db_access.catalog.dir>/feature-map.yaml`; validata e interrogata con `tools/db/db_map.py` (solo file, nessuna connessione) |
| Query di analisi riusabili | `memory/procedural/db-queries/<db>/<slug>.sql` (intestazione: scopo, ambiente, funzionalità, tabelle) |

## Invocazione del tool

```bash
PY=python3; command -v python3 >/dev/null && python3 -c '' 2>/dev/null || PY=python
$PY tools/db/db_access.py <sottocomando> ...
```

Su Windows `python3` può essere l'alias dello Store che non esegue nulla: il ripiego su
`python` è voluto. Il tool scrive JSON su stdout e diagnostica su stderr.

| Exit | Significato | Cosa fare |
|---|---|---|
| 0 | ok | — |
| 1 | uso/config (target ignoto, credenziali assenti, istruzione bloccata, capability spenta) | riportare `error` + `expected_vars` se presenti |
| 2 | connessione/autenticazione | rete/VPN richiesta dal proprio ambiente, certificato TLS (`verify-full`) o credenziali; mai riprovare in loop |
| 3 | scrittura sul percorso di lettura (rifiutata dal tool o dal server) | se `write.enabled` e ambiente scrivibile: Fase 4. Altrimenti file .sql per chi ha titolo (4.6) |
| 4 | gate: `write_disabled`, token, TTL, conferma ambiente, righe divergenti dal dry-run; `read_only_env`; `cost_gate` (stima di costo sopra soglia sugli ambienti in `cost_gate.envs`) | `write_disabled`: la scrittura e' spenta, non aggirarla; scritture: rifare dry-run e gate da capo, su `read_only_envs` nessuna scrittura. `cost_gate`: vedi Fase 2 |
| 5 | errore SQL (es. `42501` permesso negato) | riportarlo; per `42501` vedi Fase 4.6 |
| 6 | timeout (statement o lock) | restringere la query; per i lock non insistere |

---

## Fase 1 — Boot

1. `db_access.enabled: false` → ABORT pulito (lo dice anche il tool, exit 1).
2. Risolvi **ambiente** e **target**. Se l'utente non li indica, o sono ambigui, chiedi.
   Non scegliere mai `prod` per default. Gli alias degli ambienti (es. `produzione` → `prod`) sono
   quelli del registro: non inventarne.
   **Navigazione** quando l'utente indica un microservizio, uno schema, una tabella o una
   funzionalità invece del DB:
   - funzionalità → servizio → tabella: `python3 tools/db/db_map.py map-locate <termine> --env <env>`
     (se esiste la feature-map), altrimenti dalla wiki (`/query`);
   - servizio, schema, alias → target: `db_access.py locate <env> <termine>` (mappa del registro,
     con la fonte di ogni voce; `unverified` va detto all'utente);
   - tabella o schema non in mappa: `locate <env> <termine> --live` cerca nei cataloghi di tutti i DB
     dell'ambiente (exit 1 se alcuni DB non sono interrogabili per credenziali assenti: dillo);
   - quali DB esistono davvero sull'host: `databases <env>` (marca quelli registrati e quelli attesi ma assenti).
3. `db_access.py targets --env <env>`: il target esiste? `credentials_ready`? Se no →
   stop con le variabili da aggiungere a `.env.db` (o il file di `db_access.env_file`) (`credential_candidates`).
   `unverified_endpoint: true` → avvisa che l'endpoint va confermato.
4. Prima operazione della sessione su un target: `db_access.py check <env> <target>`, poi
   riporta in una riga l'utente DB, `write_capable` e gli schemi con privilegi.
5. **Catalog gate** (prima di analizzare o interrogare il target):

   ```bash
   $PY tools/db/db_catalog.py catalog-check <env> <target>   # una query per DB; offline: catalog-status <env>
   ```

   - Stati per DB e schema: `fresh`, `drift`, `missing`, `inaccessible`, `stale`, `unverified`.
   - Se il JSON ha `catalog_warning` valorizzato, riportalo come **riga di stato in testa alla risposta**
     (esempio: `catalogo test/app: drift su public (serve catalog-scan)`). Se è `null`, scrivi
     `catalogo <env>/<target>: fresh`.
   - **Non blocca mai** la lettura: l'avviso dice che la struttura nel catalogo può non essere quella
     del server. Con `drift` o `missing`, per i nomi di tabelle e colonne fa fede `describe`, non il catalogo.
   - `needs_sync` / `needs_commit` si riportano all'utente. `/db` non esegue `catalog-scan` di sua
     iniziativa (solo se l'utente lo chiede) e non committa mai la directory del catalogo: il commit del
     catalogo, con review, è dell'utente.
   - **Uso della DDL**: prima di scrivere una query leggi il file del catalogo dello schema per conoscere
     tabelle, colonne, tipi, vincoli e funzioni. Non inventare nomi. Se la libreria
     `memory/procedural/db-queries/<db>/` ha già una query per lo scopo, riusala.
   - Credenziali o VPN assenti: `catalog-check` esce con exit 2; riporta `catalog-status` (offline) e
     dichiara che lo stato non è stato verificato in sessione.

## Fase 2 — Lettura

Prima la struttura, poi i dati:

```bash
$PY tools/db/db_access.py tables   <env> <target> [<parte del nome>] [--schema S]   # righe stimate, dimensione
$PY tools/db/db_access.py describe <env> <target> <schema.tabella>                # colonne, vincoli, indici, viste
$PY tools/db/db_access.py query    <env> <target> --sql "<SQL>" [--schema S] [--limit N] [--explain] [--out F]
```

- Sul percorso di lettura il tool accetta solo `SELECT`, `WITH`, `TABLE`, `VALUES`; rifiuta prima di
  connettersi le parole di scrittura (anche dentro una CTE o `FOR UPDATE`) e le funzioni con effetti
  collaterali o che escono dalla transazione (`dblink`, `pg_sleep`, `set_config`, `lo_*`,
  `pg_terminate_backend`, `nextval`, pacchetti Oracle-compatibili `utl_*`/`dbms_*`, …). Ogni istruzione gira come
  `SELECT * FROM (<query>) q LIMIT n`: il limite vale anche per il lavoro del server.
- `--explain` mostra solo il piano stimato (niente ANALYZE): usalo prima di join pesanti su prod.
- **Controllo di costo** (`cost_gate.envs`, default `prod`): `query` esegue prima l'`EXPLAIN` della stessa
  query. Sopra soglia non parte: exit 4, errore `cost_gate`, con costo e righe stimate. Mostrali all'utente
  e **chiedi conferma** (`AskUserQuestion`), oppure restringi la query (colonne, `WHERE`, `LIMIT`).
  `--accept-cost` solo dopo il sì esplicito dell'utente, per quella sola esecuzione: mai per default,
  mai da un subagente.
- Nomi qualificati con lo schema quando un DB ne ha più d'uno; le tabelle `*_history` ricostruiscono
  chi ha cambiato cosa e quando.

- SQL lungo o con apici: scrivilo in un file nella scratchpad e usa `--file`.
- Garanzie del tool: `default_transaction_read_only=on` lato server, transazione chiusa
  sempre con ROLLBACK, `statement_timeout`, istruzioni di controllo transazione e `COPY`
  bloccate prima della connessione.
- Preferisci query mirate: colonne esplicite, `WHERE`, `ORDER BY`, aggregati. Un
  `SELECT *` senza filtro su tabelle grandi è da evitare anche in TEST.
- **Esplorazione dello schema**: `information_schema.columns`, `pg_catalog`, `\d` non
  esiste (niente psql), quindi interroga i cataloghi.
- Output oltre 32 KiB: fuori dagli ambienti protetti il tool lo scrive su file e
  restituisce il path; leggi solo le parti che servono.

## Fase 3 — Presentazione

- Tabella markdown compatibile con il terminale, al massimo circa 30 righe. Per il resto
  indica conteggi e `truncated`.
- Dati personali (email, codici fiscali, nominativi, telefoni): mostra solo ciò che serve
  alla domanda. Su ambienti protetti maschera di default (`m***@dominio.it`), salvo
  richiesta esplicita dell'utente per il singolo valore. Nel catalogo vale `db_access.catalog.pii_scrub`
  (default `true`): i letterali personali nella DDL sono mascherati e le tabelle di dominio con colonne
  personali sono rifiutate; spegnerlo e' una scelta esplicita del maintainer e il manifest lo dichiara.
- Cita sempre ambiente, database e schema da cui viene il dato.
- Quando la lettura serve a un'indagine (ticket, defect, verifica di un dato) restituisci le evidenze nel
  blocco sotto: ambiente, finestra, identificativi, query eseguite (testo o hash), righe o conteggi, fonti.

### Blocco di evidenze (indagini)

```json
{"env": "test", "window": {"from": "2026-11-05T09:00", "to": "2026-11-05T09:30", "tz": "UTC"},
 "ids": {"entita": "...", "request_id": "...", "utente": "..."},
 "catalog": "riga di stato della Fase 1.5",
 "findings": [{"claim": "...", "source": "db", "where": "test/billing schema invoicing",
               "how": "SQL oppure sha256 del testo", "rows": 3, "evidence": "..."}],
 "not_verified": ["..."]}
```

La finestra è quella dell'evento del ticket (per i dati senza orario, la data di lettura). Su ambienti
protetti `findings` riporta conteggi e conclusioni, non righe né dati personali in chiaro.
- **Mai** copiare risultati di ambienti protetti in `raw/`, `wiki/`, `deliverables/`,
  kanban, log o commit (il tool rifiuta già `--out` su quegli ambienti).

### Ricette per obiettivo

- **Controllo** (un record è nello stato atteso?): `locate` → `describe` della tabella → `query` per chiave
  (id, uuid, codice), colonne esplicite, `--limit` basso. Cita ambiente, database, schema.
- **Analisi** (quanti, da quando, perché): aggregati (`count`, `group by`, `min/max` delle date) prima delle
  righe; per la storia le `*_history`; per il «perché» incrocia con altre fonti (log applicativi: dicono cosa è
  successo, il DB com'è lo stato adesso).
- **Pulizia** (correggere o togliere dati): solo con `write.enabled: true` e fuori da `read_only_envs`. Prima la
  `query` che seleziona esattamente le righe da toccare (stesso `WHERE`), poi Fase 4 con `RETURNING`.
  Altrimenti si prepara il file per chi ha titolo (4.6) con la query di verifica allegata.

## Fase 4 — Scrittura (opt-in, gate umano R.14)

**Spenta per default.** Con `db_access.write.enabled: false` il tool rifiuta `write` (exit 4 `write_disabled`)
prima di leggere l'SQL: non si aggira e non si propone di accenderla al posto dell'utente. Accenderla e' una
scelta esplicita del maintainer, nella config.

**Mai sugli ambienti in `read_only_envs` (default prod)**, nemmeno a scrittura accesa: il tool rifiuta `write`,
dry-run compreso, prima di connettersi (exit 4 `read_only_env`), qualunque privilegio abbia l'utenza.
Una correzione li' si prepara come file per chi ha titolo (4.6). Negli altri ambienti, a scrittura accesa,
la scrittura è ammessa nei limiti dei privilegi dell'utenza, sempre in quattro passi. **`--commit` richiede
il token del dry-run E il sì umano esplicito (gate `AskUserQuestion`): il token da solo non basta, e un
subagente non esegue mai `--commit`.**

**4.1 Preparazione.** SQL esplicito, con `WHERE` su chiave dove possibile. `RETURNING`
consigliato (il dry-run mostra fino a 20 righe toccate). Vietati, li blocca anche il tool:
`BEGIN/COMMIT/ROLLBACK/SAVEPOINT`, `SET TRANSACTION`, `COPY`. DDL ammessa se i privilegi
la consentono, ma va dichiarata come tale nel gate.

**4.2 Dry-run.**

```bash
$PY tools/db/db_access.py write <env> <target> --file <sql> [--schema S] --dry-run
```

Esegue in transazione e fa ROLLBACK. Restituisce righe toccate per istruzione, anteprima
`RETURNING`, `token` e `expires_at` (TTL `pending_ttl_minutes`). Effetti che il ROLLBACK
**non** annulla e che vanno segnalati nel gate se presenti: `nextval` delle sequenze,
`dblink`/FDW, `pg_notify`.

**4.3 Gate.** Con `AskUserQuestion` (mai dedotto da messaggi precedenti, mai riusato fra
scritture diverse), mostra:

- ambiente + database + schema + utente DB (dalla Fase 1);
- l'SQL **completo**, così come verrà eseguito;
- righe toccate per istruzione e l'anteprima del dry-run;
- scadenza del token.

Opzioni: «Esegui il commit» / «Annulla». Su un ambiente in `protected_envs` che non sia anche in
`read_only_envs` il gate è **doppio**: prima la conferma come sopra, poi una seconda domanda separata che
ripete ambiente e numero di righe («Confermi di nuovo: N righe su <AMBIENTE>?»).

**4.4 Commit.** Solo dopo la conferma (o le due conferme):

```bash
$PY tools/db/db_access.py write <env> <target> --file <sql> [--schema S] --commit \
  --token <token> [--confirm-env <env>]   # --confirm-env obbligatorio sugli ambienti protetti
```

Il tool riesegue lo stesso SQL e conferma **solo** se le righe toccate coincidono con il
dry-run. Altrimenti annulla (exit 4 `rowcount_drift`): i dati sono cambiati nel frattempo e
si riparte da 4.2 con un nuovo gate. Il token vale una volta sola.

**4.5 Traccia.** Il tool appende la scrittura confermata a `db_access.audit_log`: hash
dell'SQL, istruzioni e righe, e il testo dell'SQL solo fuori dagli ambienti protetti.
Riporta all'utente l'esito e il path dell'audit. Se la scrittura serve a un TSK, cita
l'evento nel TSK. Non duplicare in `wiki/log.md`: la wiki è di wiki-keeper.

**4.6 Privilegi insufficienti** (exit 5, `sqlstate` `42501`), scrittura spenta, ambiente in sola lettura o
scrittura che va fatta da chi ne ha titolo (DBA): non cercare altre utenze né altri strumenti. Prepara il
file `.sql` in `deliverables/` (convenzione `AAAA-MM-GG-<descrizione>-dba.sql`, con un commento in testa
su ambiente, scopo e righe attese) e fermati.

## Fase 5 — Chiusura

- Nessun dry-run lasciato pendente senza dirlo: se l'utente annulla, dichiara che il
  token scade da solo, perché non c'è niente da revocare.
- Mai credenziali, stringhe di connessione con password o risultati di ambienti protetti
  nel report di sessione.

## Invarianti

- **DB-1**: la classificazione lettura/scrittura la fa il server (read-only), non il
  modello. Una query «che sembra una lettura» passa comunque dal percorso di lettura.
- **DB-2**: nessuna scrittura senza `write.enabled: true`, dry-run e gate umano esplicito sulla stessa
  invocazione. Un subagente non esegue mai `--commit` (R.14).
- **DB-3**: nessun segreto in output, argomenti di comando, file versionati o log.
- **DB-4**: il registro dichiara endpoint, non privilegi. Ciò che l'utenza può fare lo
  dice `check`, e il server ha l'ultima parola.
- **DB-5**: gli ambienti in `read_only_envs` non si scrivono mai, nemmeno in dry-run e nemmeno
  con un'utenza che ne avrebbe i privilegi.
- **DB-6**: il percorso di lettura esegue solo letture validate dal tool, con il LIMIT dentro la query;
  la sola lettura della sessione resta la seconda difesa, non l'unica.
- **DB-7**: ogni scrittura è confermata dall'utente sul dry-run e non si esegue mai per sostenere o verificare
  un'analisi. I file `.sql` per il DBA, i commenti SQL e i messaggi verso il DB non contengono riferimenti ad AI,
  a Claude o alla factory.
- **DB-8**: TLS `verify-full` per default; un `sslmode` piu' debole e' una deroga dichiarata e segnalata, mai silenziosa.
