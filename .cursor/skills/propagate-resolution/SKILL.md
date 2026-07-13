# Skill: Propagate Resolution

> Adapter Cursor della skill `propagate-resolution` definita in PATTERN.md.

# Propagate Resolution (operazione canonica `Propagate`, PATTERN.md §3)

Skill del [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc). Eseguita **solo** come effetto collaterale della
chiusura di un gap che cita esplicitamente una `Q_NNN` in `management/questions.md`.

Riferimenti: [wiki-gap-protocol](mdc:.cursor/skills/wiki-gap-protocol/SKILL.md) (chiusura gap), [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md) (template
marker `reconcile-needed`), `PATTERN.md §3` (operazione `Propagate`) + `§7 r.9`
(gate L4 graduato).

## Chi può eseguirla

**Solo il [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc)**, automaticamente alla chiusura di un gap.
Single-committer §7 r.12 invariato — questa skill scrive **solo** su `wiki/log.md`
(append-only, già nello scope del keeper).

## Trigger

Il [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc), mentre marca un gap come `**Risolto:** YYYY-MM-DD — [[<pagina>]]`,
rileva che la sezione del gap (o la Q che ne dipendeva) cita una o più
`Q_NNN`. Esempio di gap chiuso che attiva il flow:

```markdown
## 2026-05-19 15:50 — integrazione-docspa-fattibilita
**Origine:** wiki-keeper @ ingest BBP
**Gap:** dettagli del contratto SOAP DocsPA non presenti in raw/
**Sospetta fonte:** EXEC_Protocollazione.md + FLOW_Protocollazione.md
**Impatto:** Q_001 in questions.md non risolvibile senza
**Risolto:** 2026-05-19 — [[protocollazione-docspa]]  ← chiusura
```

Se il gap cita una Q nella propria sezione (campo `**Impatto:**` o riga
`Q_NNN`), **e** la Q passa contestualmente a `[RISOLTE]`, propaga.

## Procedura

### 1. Identifica le Q chiuse dal gap

- Read `management/questions.md`. Estrai le `Q_NNN` in `[RISOLTE]` con
  `**Data risoluzione:** YYYY-MM-DD` uguale alla data di chiusura del gap.
- Per ognuna, raccogli `**Storie sbloccate:**` (lista esplicita) oppure,
  se assente, deriva grep su `management/kanban/**/US-*.md` per
  `blocked_by:.*Q_NNN` e `pending_clarification:.*Q_NNN`.

### 2. Verifica stato del kanban

Per ogni US trovata:

- Read `US-YYY.md`. Se `Q_NNN` **non** è più in `blocked_by` né in
  `pending_clarification` → riconciliazione già fatta a mano, SKIP.
- Se `Q_NNN` è ancora presente → marker da appendere.

### 3. Append marker a `wiki/log.md`

Una riga per US ancora non riconciliata. Template (vedi [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md)):

```
[YYYY-MM-DD HH:MM] reconcile-needed — US-YYY → Q_NNN closed (gap [[<slug>]]) — files touched: 0
```

`files touched: 0` perché il keeper NON modifica la US (proprietà del PM).

### 4. Surface in chat

Al termine della chiusura gap, mostra:

```
PROPAGATE — Q chiuse e riconciliazione downstream
==================================================
Q chiuse contestualmente: Q_NNN, Q_MMM
US ancora con blocked_by/pending_clarification stale:
  - US-017 (blocked_by: [Q_001])     ← reconcile-needed
  - US-024 (pending_clarification: [Q_001])  ← reconcile-needed
  - US-031 (blocked_by: [Q_001])     ← reconcile-needed
Suggerimento: invoca `product-manager` per un pass di riconciliazione
sulle 3 US elencate, oppure correggi a mano se hai chiarezza tu.
```

## Cosa NON fa questa skill

- **Mai scrittura su `management/kanban/**`** — proprietà esclusiva del PM
  (§2). Il keeper segnala, non riconcilia.
- **Mai notifiche fuori `wiki/log.md`** — il canale è il log, surfaced
  dall'orchestrator in `/run` (vedi [state-scan](mdc:.cursor/skills/state-scan/SKILL.md)).
- **Mai chiusura silenziosa di Q** — la chiusura di una Q resta una decisione
  che passa per [apri-question](mdc:.cursor/skills/apri-question/SKILL.md) (con `**Data risoluzione:**` + decisione esplicita).
  Questa skill reagisce *dopo* la chiusura, non la innesca.

## Idempotenza

Eseguire `propagate-resolution` due volte sullo stesso gap chiuso produce
markers duplicati nel log. **È accettabile** (log append-only, segnale ridondante
non rumore strutturale). Per evitare la duplicazione, il keeper esegue la
skill **una sola volta**, contestualmente alla chiusura del gap (Fase 5 di
[ingest-protocol](mdc:.cursor/skills/ingest-protocol/SKILL.md), prima della log-entry di ingest).

## Anti-pattern (vietati)

| Anti-pattern | Perché vietato |
|---|---|
| Modificare `US-YYY.md` rimuovendo `Q_NNN` da `blocked_by` | Violazione write-scope §2 (kanban è PM) |
| Riaprire la Q se la riconciliazione non avviene | Q resta in `[RISOLTE]`; il problema è il kanban stale, non la Q |
| Emettere marker per Q ancora aperte | La skill opera *post-chiusura*; per Q aperte usa [apri-question](mdc:.cursor/skills/apri-question/SKILL.md) |
| Marker senza riferimento esplicito al gap | Il marker DEVE citare `(gap [[<slug>]])` per audit trail |
