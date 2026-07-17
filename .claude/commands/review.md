---
description: Invoca il code-reviewer su un TSK (PATTERN §19, v2.12). Esegue code-review-protocol 5 fasi e ritorna verdict pass | conditional | reject. Loop bounded da code_quality.max_iterations.
argument-hint: <TSK-id> [--strategy=<...>] [--force]
allowed-tools: Read, Write, Edit, Bash, Glob
---

Sintassi:

```
/review <TSK-id>                  → review standard (legge config code_quality)
/review <TSK-id> --strategy=split-by-area → override una-tantum di router.strategy
/review <TSK-id> --force          → forza review anche se review_status non è pending/conditional
/review show <TSK-id>             → mostra ultimo report senza ri-revieware
/review summary                   → riepilogo pass_rate, false_positive, escalation rate (analytics §19.8)
```

## Comportamento per sub-comando

### `/review <TSK-id>`

1. Read `factory.config.yaml.code_quality`. Se `enabled: false` → ABORT pulito,
   suggerisci «Abilita con `code_quality.enabled: true` e ri-prova».
2. Read TSK `<TSK-id>` (`Glob management/kanban/**/TSK-<id>.md`):
   - Se non trovato → ABORT «TSK non esiste».
   - Se `status` ≠ `done` → ABORT «Review applicabile solo a TSK done; status attuale: <X>».
   - Se `review_status ∈ {passed, rejected}` → mostra il report più recente e chiedi
     «TSK già in stato <X>. Re-invocare review (`--force`)? [y/N]».
3. Invoca l'agent `code-reviewer` (Claude Code `Agent` con `subagent_type: code-reviewer`)
   passando come prompt:
   - `tsk_id: <id>`
   - `override_strategy: <split-by-area|severity-tiered|all-in-one>` (se passato)
   - `force: true|false`
4. L'agent esegue `code-review-protocol` 5 fasi e aggiorna frontmatter + log.
5. Mostra in chat il risultato (verdict + summary + next step) come da
   `feedback-router`.

### `/review show <TSK-id>`

Read-only: legge `code_quality/reports/<TSK-id>-iter-*.md` (l'ultimo per `iter` DESC) e
mostra il digest in chat. Nessuna nuova chiamata al code-reviewer, nessuna scrittura.

Se nessun report esiste: «Nessun report per <TSK-id>. Esegui /review <TSK-id> per
generarlo».

### `/review summary`

Aggregato analytics da `wiki/log.md` + `code_quality/reports/`:

```
CODE REVIEW SUMMARY (last 30 days)
==================================
Total reviews:    <N>
Verdict mix:      pass <P> ({p%}) | conditional <C> ({c%}) | reject <R> ({r%})
Pass rate / stack:
  python/fastapi v0.x: <pr%>
  typescript/react v18: <pr%>
  ...
Mean review_iter to pass: <X.Y>
Top 5 rule_id violati:
  1. <rule_id> (<N> trigger, <FP> false positive)
  ...
Escalation rate (verdict=reject): <r%>
  - loop_exhausted: <X>
  - no_progress: <Y>
  - regression: <Z>

Warning:
{lista se pass_rate per stack < pass_rate_warn (default 0.05) → review theater}
{lista se false_positive / trigger per rule > false_positive_warn (default 0.30) → riformulare}
```

Read-only. Nessuna scrittura. Utile per tuning periodico del ruleset (loop evolutivo
§19.5 manuale in v2.12).

## Prerequisiti

- `factory.config.yaml.code_quality.enabled: true`.
- Topology include almeno un dev-agent (altrimenti non c'è codice da revieware).
- `.claude/agents/code-reviewer.md` presente.
- `code_quality/rules/` scaffoldato (almeno una regola `canonical/{language}.*` per lo
  stack del TSK; altrimenti review fallisce in Fase 2 di `code-review-protocol` con
  «no rules applicable»). Fallback language-agnostico disponibile out-of-the-box:
  `code_quality/rules/canonical/design-complexity.md` (5 regole `*.design.complexity.*`)
  — copre complexity violations su qualsiasi stack anche in assenza di regole specifiche
  di linguaggio.

## Idempotenza

L'`<TSK-id>-iter-<N>.{json,md}` è univoco per iterazione. Re-invocare `/review` su un
TSK con `review_status: passed` chiede conferma (`--force`); su `conditional` o
`pending` procede normalmente incrementando `review_iter`.

## Vincoli (PATTERN §7 r.16 + §19.6)

- Mai auto-revert codice (verdict reject = gate umano).
- Mai modificare il corpo del TSK (solo frontmatter `review_status:`/`review_iter:`/
  `review_report:` + `updated:`).
- Mai bypassare `max_iterations` (default 3). Raggiunto il cap → escalation umana.
- Mai applicare regole `emergent` con `status: candidate` (devono essere `active`).

Vedi `code-review-protocol` per la procedura completa, PATTERN §19 per il contratto
«Code Quality Review Layer».
