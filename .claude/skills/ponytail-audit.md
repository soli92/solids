---
name: ponytail-audit
description: "Scan YAGNI Decision Ladder sull'intero code_path (o sottoinsieme via glob). Full-repo counterpart di /ponytail-review. Produce report in code_quality/reports/ e alimenta /ponytail-gain. Opt-in EP-057."
status: stable
epic_id: EP-057
pattern_version: "2.39-candidate"
---

# Skill — ponytail-audit

Esegue la Decision Ladder ([[decision-ladder]]) sull'**intero code_path** (o un sottoinsieme
via glob), producendo un catalogo dei candidati alla semplificazione raggruppati per livello.
È il counterpart full-repo di `/ponytail-review` (che lavora sul diff): stessa scala, scope
diverso. Analogo a `/lint` (full scan) vs Check 4ao (post-develop incrementale).

Invocata dal comando `/ponytail-audit`.

## Gate (precondizione)

```
IF factory.config.yaml.ponytail.enabled != true:
    STOP — "Ponytail non abilitato. Aggiungi `ponytail.enabled: true` in factory.config.yaml."
```

## Input

| `[<path-glob>]` | opzionale — sottoinsieme del code_path (default: tutto il `code_path` da config) |

Rispetta sempre `ponytail.audit.exclude_patterns` (glob) e i pattern gitignored.

## Procedura (5 step)

### Step 1 — Risolvi lo scope
`code_path` da `factory.config.yaml` (o argomento). Enumera i file sorgente escludendo:
gitignored + `ponytail.audit.exclude_patterns`.

### Step 2 — Cap di sicurezza
Se lo scope supera **200 file**: split in batch da 200, avvisa l'utente
(`"Scope <N> file > 200: audit sul primo batch. Ripeti con <path-glob> per i restanti."`) e
procedi col primo batch. Campionamento intelligente entro il batch: preferisci file `>50` righe
e ultima modifica `<90` giorni (dove i saving sono più probabili e rilevanti).

### Step 3 — Applica la Decision Ladder
Per ogni file, valuta il livello più alto (più economico) applicabile (7 livelli, cf.
`code-review-protocol` §Passata 5). Registra i candidati con livello suggerito.

### Step 4 — Stima saving
Per ogni candidato, stima le righe risparmiabili (differenza tra implementazione attuale e
livello suggerito). La stima è euristica e dichiarata tale.

### Step 5 — Scrivi il report
`code_quality/reports/ponytail-audit-<YYYY-MM-DD>.md`:

```markdown
---
type: ponytail-audit
date: YYYY-MM-DD
code_path: <path>
files_scanned: <N>
candidates: <M>
estimated_saving_lines: <K>
---

# Ponytail Audit — <YYYY-MM-DD>

file scansionati: <N>   candidati: <M>   saving stimato: ~<K> righe

## Sommario per livello
| Livello | Candidati | Saving stimato (righe) |
|---|---|---|
| 4 (Platform-native) | 3 | 380 |
| 3 (Stdlib) | 2 | 24 |

## Dettaglio
| File | Costrutto | Livello | Saving stimato |
|---|---|---|---|

## Top 5 quick wins
1. src/components/DatePicker.tsx — livello 4 — ~381 righe (max impatto / min effort)
```

I campi `files_scanned`, `candidates`, `estimated_saving_lines` nel frontmatter sono letti da
`/ponytail-gain` (tool `show-session-tokens.py`).

## Invariante R.PY1

L'audit **non valuta, non sopprime e non modifica** findings di security, accessibilità o
trust-boundary. Non applica mai le semplificazioni — le cataloga soltanto (read-only sul codice).

## Cross-link

- Scala canonica: `.claude/skills/code-review-protocol.md §Passata 5`
- Concetto: `wiki/concepts/decision-ladder.md`, `wiki/concepts/ponytail.md`
- Comando: `.claude/commands/ponytail-audit.md`
- Consumer del report: `/ponytail-gain` (riga nel token ledger), companion `/ponytail-review` (diff)
