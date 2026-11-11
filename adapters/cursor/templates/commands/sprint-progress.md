# Comando: /sprint-progress

> Equivalente Cursor del comando Claude Code `/sprint-progress` (`.claude/commands/sprint-progress.md`).
> EP-043 US-153, opt-in `analytics.sprint_progress.enabled`.

**Sintassi**:
```
/sprint-progress              → sprint corrente (sprint_current da sprint.md)
/sprint-progress <N>          → sprint specifico (es. /sprint-progress 44)
/sprint-progress --json       → output machine-readable
```

## Comportamento

Mostra stato di avanzamento dello sprint: conteggio TSK per stato, velocita' rolling, proiezione al completamento.

**Il comando funziona sempre**: il flag `analytics.sprint_progress.enabled` controlla solo l'invocazione automatica via scheduler; il comando manuale e' sempre disponibile.

**Esecuzione**:
```bash
python3 tools/analytics/sprint-progress.py [sprint_id] [--json]
```

- Senza `sprint_id`: legge `sprint_current:` dal frontmatter di `management/kanban/sprint.md`.
- Con `sprint_id`: analizza lo sprint indicato.
- Con `--json`: JSON machine-readable (schema: `sprint`, `done`, `in_progress`, `todo`, `completion_pct`, `velocity_per_day`, `projection_days`).

**Fallback**: se l'event store (`analytics/events/*.jsonl`) non e' disponibile → conteggio kanban diretto. Mostra banner `[Nota: velocita' non calcolabile — event store non disponibile]`.

## Output esempio

```
Sprint SP-45 — Progress Signal (2026-07-09T14:00:00Z)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Done       :  3 TSK  [█████░░░░░░░░░░░]  33%
In-progress:  2 TSK
Todo       :  4 TSK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Velocita'  :  1.5 TSK/giorno (rolling 7gg)
Proiezione :  ~3 giorni al completamento sprint (± 1 giorno)
```

## Limitazioni Cursor

- Usare terminal Cursor per invocare lo script: `python3 tools/analytics/sprint-progress.py`.
- Se lo script non esiste → contare manualmente i TSK per stato dal kanban.
