---
name: indagine-protocol
description: "Indagine combinata log dei pod + (se db_access e' attivo) database come percorso standard di ogni analisi che tocca dati o comportamento a runtime: ticket, defect, errore su una funzionalita', verifica di un dato. Sequenza (ambiente e finestra, log, mappa funzionalita'-servizio-tabella, catalogo DDL, letture mirate, correlazione) e blocco di evidenze per il TSK. Sola lettura: nessuna scrittura per sostenere l'analisi. Compone log-access-protocol e, se attivo, db-access-protocol. Richiede almeno una fra log_access e db_access."
---

# Protocollo di indagine — log dei pod + database (se attivo)

Percorso standard quando un'analisi tocca **dati o comportamento a runtime**: ticket, defect,
errore su una funzionalita', verifica di un dato ("il record e' nello stato giusto?"). Non
serve per domande sul codice o sulla wiki che non richiedono di guardare un ambiente.

Non rifa' le due skill di accesso: le compone. Come si usano gli strumenti, i codici di uscita,
il mascheramento e i limiti sono in `.claude/skills/log-access-protocol.md` (`/log`,
`log-operator`) e, **se `db_access` e' attivo**, in `.claude/skills/db-access-protocol.md` (`/db`, `db-operator`).
Le capability sono opt-in e indipendenti: se `log_access.enabled` o `db_access.enabled` e' `false`, il passo
corrispondente si salta e il motivo va nel blocco di evidenze. Con **entrambe spente** il protocollo non ha
strumenti: dillo all'utente invece di inventare un'indagine dalla memoria. I passi 3-6 e il campo «Dato» valgono
**solo se `db_access.enabled: true`**; altrimenti l'indagine si ferma ai log e dichiara nel blocco che il lato dato non e' verificato.

## Regole che valgono per tutta l'indagine

- **Sola lettura.** Nessuna scrittura su alcun ambiente per sostenere o verificare un'analisi.
  Se l'analisi fa emergere una correzione, e' un lavoro a parte: passa dal gate di `db-access-protocol`
  (Fase 4) o dal file per il DBA, mai dentro l'indagine.
- **Dati veri, tracciati in modo coerente.** Si interroga con gli identificativi veri del ticket
  (tenant, utente, request id, codice) e si riportano nel blocco cosi' come sono, per
  poter ripercorrere l'analisi. Nessuno scrub sull'analisi. Resta la regola degli ambienti protetti
  (`log_access.protected_envs` / `db_access.read_only_envs`): nel TSK vanno conteggi e conclusioni con la provenienza, non righe di log o di tabella.
- **Zero invenzione.** Nomi di container, tabelle e colonne vengono dagli strumenti (`fields`,
  `count --by`, `locate`, `describe`, DDL del catalogo), non dalla memoria. Una finestra vuota o una
  tabella senza righe non prova che un evento non sia avvenuto: va in `not_verified`.
- **Mai un ambiente protetto per default.** Se ambiente o finestra mancano, si chiedono.

## Sequenza

### 1. Ambiente e finestra

Dal ticket: ambiente (uno di quelli del registro), orario o intervallo dell'evento **nel fuso
configurato (`log_access.timezone`)**, identificativi disponibili (tenant, request id, trace, utente pseudonimo, codice del
record). Se l'orario manca, parti da una finestra larga e restringila con `count --histogram`.
Per sapere se il problema e' solo di un ambiente, ripeti la stessa finestra su un altro.

### 2. Log dei pod

Con `log-operator` (indagini lunghe) o `/log` (Fase 4 di `log-access-protocol`): perimetro con
`count`, errori in finestra, stack trace della riga che coincide col sintomo, `--trace` per seguire la
richiesta. Dai log si estraggono gli **identificativi** che servono al passo 5 (id di record, tenant,
request id, trace) e il **servizio** che ha risposto.

Senza credenziali OpenSearch o senza VPN: un solo tentativo, poi si dichiara nel blocco e si prosegue
dal dato (passi 3-5). L'indagine non si ferma su una sola delle due fonti, ma lo dice.

### 3. Mappa funzionalita' → servizio → tabella (solo se `db_access` e' attivo)

Primo strumento: `python tools/db/db_map.py map-locate <termine> --env <env>` sulla mappa
`<db_access.catalog.dir>/feature-map.yaml` (funzionalita', servizi, tabelle, relazioni logiche tra DB,
ognuna con fonti e `confidence: verified|derived|unverified`; per ogni tabella `catalog_ref` file:riga della
DDL dell'ambiente). Il termine puo' essere una funzionalita', un servizio, una tabella o una colonna. Nel
blocco di evidenze: `map: feature-map` e la confidenza dei legami usati.

Se il termine non c'e' nella mappa (`found: false`) si ripiega, dichiarandolo (`map: locate+wiki`):

- funzionalita' → servizio: `wiki/**` via `/query`;
- servizio → database e schemi: `db_access.py locate <env> <termine>` (con `--live` per tabelle non in
  mappa), `tools/db/db-targets.yaml` blocco `services:` (ogni voce ha la fonte), le pagine della wiki sui database;
- una voce `unverified` o `derived` va detta come tale: una relazione `derived` e' un'ipotesi da
  confermare con una lettura, non un fatto.

### 4. Tabelle e catalogo (solo se `db_access` e' attivo)

Sul target individuato:

```bash
$PY tools/db/db_catalog.py catalog-check <env> <target>      # offline: catalog-status <env>  ($PY come in db-access-protocol)
```

Se `catalog_warning` non e' vuoto, la **riga di avviso va in testa** al blocco di evidenze (non
blocca: il dato letto resta valido, la struttura potrebbe essere cambiata). `needs_sync` e
`needs_commit` si riportano all'utente senza eseguire `catalog-scan` ne' committare. La DDL del
catalogo (`<db_access.catalog.dir>/<env>/<db>/<schema>.sql`) dice tabelle, colonne e vincoli:
leggila prima di scrivere le query. In mancanza, `tables` e `describe` di `db_access.py`.
Se la libreria `memory/procedural/db-queries/<db>/` ha una query per la funzionalita', riusala.

### 5. Letture mirate (solo se `db_access` e' attivo)

Con `db-operator` o `/db` (Fasi 2-3 di `db-access-protocol`): `SELECT` mirate, colonne esplicite,
chiave del record, aggregati prima delle righe, `*_history` per la storia, `--limit` basso. Su un ambiente protetto:
sola lettura, `--explain` prima delle join pesanti e controllo di costo (`cost_gate`: si chiede
conferma all'utente, mai `--accept-cost` di propria iniziativa). Senza credenziali o VPN: un
tentativo, poi `not_verified`.

### 6. Correlazione log ↔ dato (richiede entrambe le fonti)

Metti in relazione cio' che dicono i log (cosa e' successo, quando, con quale errore) con lo stato
del dato (com'e' ora, da quando, cosa dicono le `*_history`). Ogni affermazione cita la sua fonte.
Distingui sempre **fatto osservato**, **ipotesi** e **non verificato**: il nesso causale non si
afferma se i due lati non si agganciano a un identificativo comune.

## Blocco di evidenze per il TSK

E' l'output dell'indagine. Stessi campi per log e DB: li produce ciascun operatore (vedi la sezione
"Output" dei due agenti) e la sessione principale li unisce.

```markdown
### Evidenze runtime
- **Ambiente:** <ambiente del registro>
- **Finestra:** 2026-11-05 09:00-09:30 (fuso configurato)
- **Identificativi:** tenant=<...> · request id=<...> · trace=<...> · utente=<pseudonimo del ticket>
- **Catalogo:** <riga catalog_warning in testa se non fresco; "fresh" altrimenti; "non disponibile">
- **Mappa:** feature-map (confidenza dei legami usati) | locate+wiki se il termine non e' in mappa
- **Log** (se `log_access` attivo; log <env>/<app>, finestra, filtri: N righe):
  - <cosa mostrano, con la riga di provenienza>
- **Dato** (se `db_access` attivo; db <env>/<target>.<schema>):
  - <cosa mostra> — query: `<SQL>` (oppure `sha256:<hash>` se contiene valori da non copiare) — righe/conteggio: N
- **Correlazione:** <fatto osservato / ipotesi, con gli identificativi che li legano>
- **Non verificato:** <cosa manca e perche': VPN, credenziali, finestra prima di `data_from`, tabella fuori catalogo>
- **Fonti:** `<file:riga o comando>` per ogni voce sopra
```

Un campo senza contenuto si scrive con il motivo, non si omette. In un ambiente protetto il campo "Dato"
riporta conteggi e conclusioni, non righe.

## Quando manca qualcosa

| Situazione | Cosa fare |
|---|---|
| Credenziali assenti (`credentials_ready: false`) | Stop su quel passo, riporta le variabili da aggiungere al file `env_file` del target (mai il valore); proseguire con l'altra fonte |
| VPN non attiva (exit 2) | Un tentativo, causa nel blocco (rete/VPN richiesta dal cluster); non riprovare in loop |
| Catalogo `missing` o `stale` | Avviso in testa, si procede con `tables`/`describe`; il sync lo decide l'utente |
| Controllo di costo su ambiente protetto | Chiedi conferma con la stima; senza sì esplicito, restringi la query |
| Ambiente o app non nel registro | Non si interroga: si propone la voce da aggiungere |

## Chiusura

- Il blocco va nel TSK (defect) o nel documento dell'analisi; in un ambiente protetto solo conteggi e conclusioni.
- Mai credenziali, stringhe di connessione o URL con credenziali.
- La wiki resta di wiki-keeper: una pagina di sintesi passa da lui.
