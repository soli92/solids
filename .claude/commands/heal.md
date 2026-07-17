---
description: Ripara ERROR meccanici flaggati `heal-eligible` da un lint report. Loop evaluator-optimizer vincolato, gated, max 3 iterazioni.
---

Invoca l'agente [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) via `Agent` in modalità heal. Procedura: vedi
skill [heal-protocol](mdc:.cursor/skills/heal-protocol/SKILL.md).

Argomenti:
- Path del lint report (es. `/heal wiki/lint/2026-05-19-lint-report.md`)
- Senza argomento → il keeper risolve automaticamente l'ultimo report più recente
  in `wiki/lint/*-lint-report.md`.

Prerequisiti:
- Il report DEVE avere `heal_eligible_count > 0` nel frontmatter, altrimenti
  l'agente termina con messaggio "nessun error heal-eligible".
- `wiki-lint` deve aver girato di recente (idealmente con uno scope coerente).

Output: per ogni iterazione (max 3), l'agente mostra in chat un diff aggregato
e attende `yes`/`no`. Se `yes`, applica il diff e re-invoca [wiki-lint](mdc:.cursor/rules/wiki-lint.mdc) sui file
impattati. Termina su `closed | stuck | regression | empty-diff | user-rejected |
max-iterations`. Append a `wiki/log.md` (template `heal` di `wiki-log-entry`).

Regola assoluta: **mai correzione fuori whitelist** (vedi [heal-protocol](mdc:.cursor/skills/heal-protocol/SKILL.md)).
WARNING e ERROR non-meccanici restano di competenza umana.
