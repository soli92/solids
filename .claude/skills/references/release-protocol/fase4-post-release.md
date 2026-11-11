# Fase 4 — Post-release: dettaglio step 4.1–4.4

**Ambito**: dettaglio degli step post-release di `release-protocol.md`. Leggere
obbligatoriamente all'ingresso della Fase 4 — se il file manca, STOP e segnala.

> Scopo: aggiornare la memoria di progetto con la milestone completata.
> Idempotenza: verificare che le entry non siano già presenti prima di appendere.

---

## Step 4.1 — sprint.md milestone

```
Azione:
  - Apri management/kanban/sprint.md (o file sprint corrente se percorso diverso).
  - Verifica se la release v<version> è già annotata come milestone completata.
  - SE già presente → log "sprint.md: milestone v<version> già annotata. Skip." e prosegui.
  - SE assente → appendi in fondo alla sezione del sprint corrente:
      ## Milestone completata — v<version>
      - data: <YYYY-MM-DD>
      - tag: v<version>
      - validation_verdict: <pass | bypass | gate-disabled>
      - gate_report: validation/release-gates/v<version>/GATE-REPORT.md
```

## Step 4.2 — memory/episodic/ entry release

```
Azione:
  - Crea (o aggiorna se già esiste) memory/episodic/release-<version>.md con:

      ---
      type: release
      version: v<version>
      date: <YYYY-MM-DD>
      validation_verdict: <pass | bypass | gate-disabled>
      gate_report: validation/release-gates/v<version>/GATE-REPORT.md
      tag_pushed: true
      actor: <git user o "unknown">
      ---

      ## Release v<version>

      - EP inclusi: <lista EP dalla sezione CHANGELOG>
      - Validation verdict: <pass | bypass | gate-disabled>
      - Gate umano: confermato dall'utente
      - GATE-REPORT: validation/release-gates/v<version>/GATE-REPORT.md

  SE il file esiste già (idempotenza) → verifica che `tag_pushed` sia `true`; se mancante
  aggiunge il campo; se già corretto → skip.
```

## Step 4.3 — wiki/log.md entry (append-only)

```
Azione: append a wiki/log.md (append-only, mai sovrascrivere righe esistenti).

Entry formato:
  <ISO-8601> develop release-protocol version=v<version> verdict=<pass|bypass|gate-disabled> \
  gate_report=validation/release-gates/v<version>/GATE-REPORT.md actor=<git-user|agent>

SE la riga per v<version> è già presente in wiki/log.md (idempotenza):
  - log "wiki/log.md: entry v<version> già presente. Skip."
  - non appendere duplicati.
```

## Step 4.4 — Checkpoint Fase 4 e chiusura

```
Log finale:
  "Fase 4 completata. Release v<version> conclusa.
   ✓ management/kanban/sprint.md — milestone annotata
   ✓ memory/episodic/release-<version>.md — entry creata/verificata
   ✓ wiki/log.md — entry appesa

   Release v<version> completata con successo. Tag: v<version> su origin."
```
