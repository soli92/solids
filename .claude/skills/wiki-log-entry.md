---
name: wiki-log-entry
description: Template canonici per gli append a wiki/log.md. Riferimento unico per ogni agente che logga operazioni.
---
# Template di log entry (canonici)

`wiki/log.md` è **append-only** (vedi `PATTERN.md §7 r.5`). Questa skill è la
single source of truth dei formati di entry per tipo di operazione.

## Formato generale

```
[YYYY-MM-DD HH:MM] <operation> — <one-line summary> — files touched: <N>
```

Una riga per operazione. Mai editare entry passate. Mai cancellare.

## Template per operazione

### `ingest` (wiki-keeper)

```
## [YYYY-MM-DD] ingest | <nomi-pdf separati da +>
Pagine create: N | Figure: N | Aggiornamenti: N | Gap nuovi: N | Gap chiusi: N
```

Una riga aggiuntiva per ogni gap chiuso durante l'ingest:

```
[YYYY-MM-DD HH:MM] gap-closed — <slug> via [[<pagina>]] — files touched: 1
```

### `query` (wiki-query)

```
## [YYYY-MM-DD] query | <prime parole della domanda>
```

Se la query è stata salvata come synthesis:

```
[YYYY-MM-DD HH:MM] synthesis-promoted — wiki/query/<file>.md → wiki/syntheses/<question>.md — files touched: 2
```

### `lint` (wiki-lint)

```
## [YYYY-MM-DD] lint | check completo
Orphan: N | Broken: N | Unsourced: N | Kanban: N err | Coerenza: N err
```

Per il citation audit periodico:

```
[YYYY-MM-DD HH:MM] citation-audit — <total claims> verified, <N> broken — files touched: 1
```

### `promote` (orchestrator)

```
[YYYY-MM-DD HH:MM] promote — <path> <old-status> → <new-status> — files touched: 1
```

### `plan` (product-manager)

```
[YYYY-MM-DD HH:MM] plan — EP-XXX created (N stories) — files touched: <N>
```

### `design` (lead-architect)

```
[YYYY-MM-DD HH:MM] design — <componenti: BE/FE/DB/API> + ADR-NNN — files touched: <N>
```

### `execute` (tpm)

```
[YYYY-MM-DD HH:MM] execute — sprint NN with <N> tasks — files touched: <N>
```

### `bootstrap` (sync-docs)

```
[YYYY-MM-DD HH:MM] bootstrap — <N> PDF extracted to raw/ — files touched: <N>
```

### `reconcile-needed` (wiki-keeper via `propagate-resolution`, v2.6)

Marker emesso dalla skill `propagate-resolution` quando il keeper chiude un
gap che cita una `Q_NNN` risolta contestualmente, ma una o più US dipendenti
hanno ancora `Q_NNN` in `blocked_by` o `pending_clarification`. Una riga
per US stale:

```
[YYYY-MM-DD HH:MM] reconcile-needed — US-YYY → Q_NNN closed (gap [[<slug>]]) — files touched: 0
```

`files touched: 0` perché il keeper non scrive sul kanban (proprietà PM,
§2). Il marker è surfaced dall'orchestrator in `/run` come "🔁 N reconcile-needed
pendenti" (vedi `state-scan`).

Chiusura del marker: implicita. Quando il PM (o l'umano) riconcilia la US,
non si appende nulla — la prossima esecuzione di `state-scan` ricalcola da
filesystem e il conteggio scende.

### `develop` (dev-agent, v2.7)

Log entry emessa dal dev-agent (be-dev, fe-dev, db-dev, qa-dev) al completamento di un TSK.

```
[YYYY-MM-DD HH:MM] develop — TSK-NNN <layer> <status> — VCS mode: <vcs.mode> — files touched: <N>
```

Campi:
- `<layer>` ∈ `{be, fe, db, qa}`
- `<status>` ∈ `{done, blocked, skipped}`
- `**VCS mode:** <vcs.mode>` obbligatorio per check 4d (v2.8 PATTERN §15)

Se il TSK è stato prodotto in una wave parallela, aggiungere `— wave: <wave_id>` in coda:

```
[YYYY-MM-DD HH:MM] develop — TSK-NNN <layer> done — VCS mode: submodule — wave: W-<sprint>-<level>-<YYYYMMDD-HHMMSS> — files touched: <N>
```

### `wave` (orchestrator, parallel scheduler v2.11)

Emessa dall'orchestrator al termine di ogni wave durante `/run` con scheduler attivo.
Una entry per wave (non per agente nella wave).

```
## [YYYY-MM-DD] wave sprint-NN | wave-W
**WAVE_ID:** W-<sprint>-<level>-<YYYYMMDD-HHMMSS>
**Levels:** <L> (0=<N> parallel, 1=<M> serial, ...)
**Agenti:** <lista separata da ,>
**Outcome:** <done>/<total> done | <skipped> skipped | <blocked> blocked
**Duration:** <HH:MM:ss>
```

`WAVE_ID` — identificatore univoco per wave nel formato `W-<sprint>-<level>-<YYYYMMDD-HHMMSS>`.
Propagato nel campo `wave_id` degli eventi analytics (`record-event.py`) per ogni TSK consumato
nella wave, consentendo correlazione retrospettiva costo/tempo per wave.

### `sweep` (wiki-keeper, EP-056 US-203)

Emessa dal `wiki-keeper` al termine di un ciclo sweep-reviews. Una sola entry per ciclo
(non per iterazione), analoga al template `heal`.

```
## [YYYY-MM-DD] sweep | esito=<closed|stuck|regression|max-iterations|user-rejected|no-items|empty-diff>
Categorie: unsupported-claim=<N>, dangling-concept=<N>, terminology-drift=<N>
Iter <k>: applied=<A>, residual=<R> | Files touched: <M>
```

### `tavola-rotonda` (tavola-rotonda-moderatore, EP-039)

Emessa dal moderatore alla chiusura di una sessione. Registro completo in `wiki/decisions/`.

```
[YYYY-MM-DD tavola-rotonda] <session-id> chiusa — <motivo> | <topic> | files touched: <N>
```

### `migration` / `policy` / `docs` (eventi meta)

Per cambi di policy, refactor del framework, o aggiornamenti meta:

```
[YYYY-MM-DD HH:MM] <tipo> — <descrizione concisa> — files touched: <N>
```

Esempi reali in `wiki/log.md`:
- `[2026-05-18 13:30] migration — v2.x → v2.2 ...`
- `[2026-05-18 15:30] policy — model tuning per agente ...`

## Formato parseable canonico (EP-056 US-204)

Per consentire il consumo deterministico da `tools/analytics/sprint-progress.py` e dagli
analytics, le entry a riga singola seguono una **grammatica canonica**:

```
[YYYY-MM-DD HH:MM] <operation> — <summary> — files touched: <N>
```

Regex di parsing (riga singola):

```
^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] ([\w-]+) — (.+?) — files touched: (\d+)
```

**Elenco chiuso delle `operation` canoniche**:
`ingest`, `query`, `lint`, `promote`, `plan`, `design`, `execute`, `bootstrap`, `develop`,
`wave`, `heal`, `sweep`, `gap-closed`, `synthesis-promoted`, `citation-audit`,
`reconcile-needed`, `tavola-rotonda`, `migration`, `policy`, `docs`.

**Forma header multilinea** (usata da `ingest`/`query`/`lint`/`wave`/`heal`/`sweep`):
`## [YYYY-MM-DD] <operation> | <titolo>` seguita da righe di dettaglio. Il parser tollera
**entrambe** le forme (riga singola e header multilinea): per l'header multilinea usa
`^## \[(\d{4}-\d{2}-\d{2})\] ([\w-]+) \| (.+)`.

**Append-only, nessuna migrazione** (§7 r.5): le entry storiche antecedenti a questa
convenzione restano valide e **non vengono riscritte**. La grammatica vincola solo le nuove
entry; il parser degrada con grazia sulle righe che non matchano (le ignora, non fallisce).

## Regole

- **Mai overwrite**: append-only è inviolabile (`PATTERN.md §7 r.5`).
- **Mai entry vuote**: se l'operazione non ha prodotto file modificati, non logga.
- **Sempre `files touched`**: numero intero, anche `0` se l'operazione è abortita.
- **Timestamp obbligatorio**: `YYYY-MM-DD HH:MM` in italiano (Europe/Rome).
- **One-line summary < 120 caratteri**: se serve dettaglio, va nella pagina dedicata
  (synthesis, runbook, incident), non nel log.
- **Append senza leggere il file intero**: per appendere una entry a `wiki/log.md`
  non è necessario leggere l'intero file (può pesare centinaia di KB). Usa una di
  queste strategie:
  - Con **Bash**: `cat >> wiki/log.md <<'EOF'\n<entry>\nEOF` — nessuna lettura.
  - Con **Read + Edit**: leggi solo la coda (`Read` con `offset` sulle ultime ~40
    righe) e usa l'ultima entry visibile come ancora per l'Edit. Non leggere mai il
    file intero solo per appendere.
  Questa regola non contraddice l'invariante «entry sempre in coda»: l'ancora
  sull'ultima riga garantisce la posizione corretta senza caricare il file.

## Rotazione a soglia

`wiki/log.md` si ruota **quando raggiunge 180.000 byte**, non a scadenza di calendario. Misura su
una derivata: con la cadenza trimestrale, poi mensile, il file tornava sopra i 100 KB in pochi
giorni (49 entry in 7 giorni) e gli append con Edit fallivano gia' intorno ai 200 KB.

**Procedura** (mai durante una sessione che sta appendendo):

1. **Segnale.** Lo state-scan di `/run` lo ricorda (l'orchestrator non ha Bash e non misura): il
   coordinatore verifica con `wc -c wiki/log.md`. Sotto soglia non si fa nulla.
2. **Claim** su `wiki/log.md`, se la factory usa i claim, con la CLI:
   `python3 tools/session/active_sessions.py conflicts --domain wiki/log.md`, poi `claim`. Con
   claim attive di altri, aspetta; a fine rotazione `release`.
3. **Dry-run**: `python3 tools/wiki/rotate_log.py` — dimensione, soglia, righe, byte ed entry da
   spostare; sotto soglia «niente da fare».
4. **Esecuzione**: `python3 tools/wiki/rotate_log.py --apply` — sposta il prefisso di entry datate
   fino a oggi in `wiki/log-AAAA-MM-GG.md` (data della rotazione), verbatim, solo dopo aver
   verificato che archivio + log ricompongano lo sha256 dell'originale; aggiunge il link in
   `> **Archivi:**` in testa al log. Controlla la riga «ricomposizione verificata».
5. **Commit dedicato**, poi entry `migration` in `wiki/log.md`.

**Un archivio per rotazione**, con la data nel nome: le rotazioni a soglia cadono a meta' mese e
possono ripetersi nello stesso mese. Due rotazioni nello stesso giorno: lo script rifiuta (exit 1).
`--forza` ruota anche sotto soglia; `--soglia N` cambia la soglia per una esecuzione.

Lo esegue il coordinatore: il wiki-keeper (R.12) non ha Bash e con Write rischierebbe di
alterare il file. Il path di scrittura resta `wiki/log.md`; gli archivi sono read-only. Le entry
datate dopo il giorno di rotazione, e quelle scritte dopo di esse, restano nel log nell'ordine di
scrittura.

## Verifica

Il `wiki-lint` non controlla `log.md` perché append-only (controllo strutturale
sarebbe rumore). Eventuali entry malformate emergono manualmente al review
periodico.
