---
description: Invoca il visual oracle su un TSK FE (EP-005, ADR-012). Esegue visual-oracle-protocol (render headless + screenshot multi-viewport/tema + critica visiva) e ritorna verdict pass | conditional | reject. Funziona indipendentemente da fe_correctness.enabled (esecuzione esplicita = volontà esplicita).
argument-hint: <TSK-id> [--dry-run]
allowed-tools: Read, Write, Edit, Bash, Glob
---

Sintassi:

```
/visual-oracle <TSK-id>            → visual oracle standard (aggiorna visual_status nel frontmatter TSK)
/visual-oracle <TSK-id> --dry-run  → esegue la skill ma NON aggiorna il frontmatter (solo logging)
```

Argomenti utente: `$ARGUMENTS`

- Primo argomento: **TSK-id** (es. `TSK-042`), obbligatorio.
- Flag opzionale: `--dry-run` → esegue il protocollo ma non scrive `visual_status:` nel
  frontmatter TSK (solo logging in chat + report side-channel).

## Comportamento

### `/visual-oracle <TSK-id>`

1. **Risoluzione TSK** — `Glob management/kanban/**/TSK-<id>.md`:
   - Se 0 match o > 1 match → ABORT «TSK non trovato / ambiguo».
   - Leggi il frontmatter. Estrai `layer:`.
2. **Fail-loud su layer** — se `layer ≠ fe` → ABORT
   «Visual oracle applicabile solo a TSK FE (layer attuale: <X>)».
3. **Invoca la skill `visual-oracle-protocol`** (US-017) sul TSK target. La skill esegue
   le 5 fasi (Bootstrap → Render Headless → Screenshot Multi-Viewport/Tema [+ Fase 3-bis
   Structured Checks] → Critica Visiva → Diff Azionabile + Loop) ed è il single-writer di
   `visual_status:` (ADR-012 §A, analogo R.Q2 di `review_status`).
4. **Aggiornamento frontmatter** — la skill scrive `visual_status:` (`pending | pass |
   conditional | reject`) nel frontmatter TSK al termine dell'esecuzione (più `updated:`).
5. **Output chat** (vedi sotto).

### `/visual-oracle <TSK-id> --dry-run`

Identico ai punti 1–3, ma la skill **non aggiorna** il frontmatter TSK (`visual_status:`
resta invariato). Il report side-channel viene comunque prodotto e il risultato loggato in
chat. Utile per un re-check su regressione senza mutare lo stato del TSK.

## Output chat

Al termine il comando mostra:

```
VISUAL ORACLE — <TSK-id> (iter <N>)
===================================
verdict:        pass | conditional | reject
defects_count:  <N critic_findings>
report_path:    code_quality/reports/<TSK-id>-visual-iter-<N>.md
```

(con `--dry-run` viene aggiunta la nota «dry-run: frontmatter NON aggiornato»).

Il `report_path` punta al digest umano nel side-channel `code_quality/reports/`
(riuso CQRL, slug `visual` per distinguere dagli iter di review — ADR-012 §B). Il JSON
strutturato gemello vive in `code_quality/reports/<TSK-id>-visual-iter-<N>.json`.

## Funzionamento indipendente da `fe_correctness.enabled`

A differenza del dispatch automatico (dominio scheduler `visual-oracle`, gated da
`fe_correctness.enabled: true`), l'invocazione esplicita di `/visual-oracle` **bypassa** il
master switch: l'esecuzione esplicita implica volontà esplicita (analogia con `/review` per
CQRL). Utile come gate manuale o re-check su regressione anche a flag spento.

## Prerequisiti (fail-loud)

- **Skill `visual-oracle-protocol` presente** (`.claude/skills/visual-oracle-protocol.md`,
  US-017). Se assente → ABORT «Skill `visual-oracle-protocol` non scaffoldata (US-017).
  Comando non eseguibile».
- **Browser headless disponibile** (es. Playwright/Chromium installato). Se assente → ABORT
  «Browser headless non disponibile: il visual oracle richiede rendering headless».
- **TSK con `layer: fe`** — vedi fail-loud al punto 2 sopra.

## Backward compat

L'assenza del file `.claude/commands/visual-oracle.md` **non** produce ERROR di lint: il
comando è opzionale e additivo (EP-005 opt-in, ADR-012 §Backward compat). Una factory che
non lo scaffolda mantiene comportamento identico.

## Vincoli (ADR-012)

- **Single-writer**: solo la skill `visual-oracle-protocol` scrive `visual_status:`. Il
  comando non lo scrive direttamente.
- Mai modificare il corpo del TSK (solo frontmatter `visual_status:` + `updated:`, e solo
  via skill, e solo se NON `--dry-run`).
- Mai bypassare `fe_correctness.max_iterations` (loop bounded dalla skill).
- `--dry-run` è sempre side-effect-free sul frontmatter TSK.

Vedi `visual-oracle-protocol` per la procedura completa, ADR-012 per lo schema dati
(frontmatter + side-channel + paths + config block `fe_correctness`).
