# Skill: Wiki Log Entry

> Adapter Cursor della skill `wiki-log-entry` definita in PATTERN.md.

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

Marker emesso dalla skill [propagate-resolution](mdc:.cursor/skills/propagate-resolution/SKILL.md) quando il keeper chiude un
gap che cita una `Q_NNN` risolta contestualmente, ma una o più US dipendenti
hanno ancora `Q_NNN` in `blocked_by` o `pending_clarification`. Una riga
per US stale:

```
[YYYY-MM-DD HH:MM] reconcile-needed — US-YYY → Q_NNN closed (gap [[<slug>]]) — files touched: 0
```

`files touched: 0` perché il keeper non scrive sul kanban (proprietà PM,
§2). Il marker è surfaced dall'orchestrator in `/run` come "🔁 N reconcile-needed
pendenti" (vedi [state-scan](mdc:.cursor/skills/state-scan/SKILL.md)).

Chiusura del marker: implicita. Quando il PM (o l'umano) riconcilia la US,
non si appende nulla — la prossima esecuzione di [state-scan](mdc:.cursor/skills/state-scan/SKILL.md) ricalcola da
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
Propagato nel campo `wave_id` degli eventi analytics (`record-event.sh`) per ogni TSK consumato
nella wave, consentendo correlazione retrospettiva costo/tempo per wave.

### `migration` / `policy` / `docs` (eventi meta)

Per cambi di policy, refactor del framework, o aggiornamenti meta:

```
[YYYY-MM-DD HH:MM] <tipo> — <descrizione concisa> — files touched: <N>
```

Esempi reali in `wiki/log.md`:
- `[2026-05-18 13:30] migration — v2.x → v2.2 ...`
- `[2026-05-18 15:30] policy — model tuning per agente ...`

## Regole

- **Mai overwrite**: append-only è inviolabile (`PATTERN.md §7 r.5`).
- **Mai entry vuote**: se l'operazione non ha prodotto file modificati, non logga.
- **Sempre `files touched`**: numero intero, anche `0` se l'operazione è abortita.
- **Timestamp obbligatorio**: `YYYY-MM-DD HH:MM` in italiano (Europe/Rome).
- **One-line summary < 120 caratteri**: se serve dettaglio, va nella pagina dedicata
  (synthesis, runbook, incident), non nel log.

## Verifica

Il [wiki-lint](mdc:.cursor/rules/wiki-lint.mdc) non controlla `log.md` perché append-only (controllo strutturale
sarebbe rumore). Eventuali entry malformate emergono manualmente al review
periodico.
