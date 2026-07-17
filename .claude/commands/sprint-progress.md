---
name: sprint-progress
description: Segnale burndown del sprint corrente — TSK done/in-progress/todo, velocita', proiezione (EP-043 US-153, opt-in analytics.sprint_progress.enabled)
domain: analytics
---

Comando della capability [[task-analytics-cost-estimation-capability]] (faccia **Sprint Burndown**,
EP-043 US-153). Mostra lo stato di avanzamento del sprint corrente o di uno sprint specifico:
conteggio TSK per stato, velocita' rolling e proiezione al completamento. Delegato a
`tools/analytics/sprint-progress.py`.

## Sintassi

```
/sprint-progress              -> sprint corrente (sprint_current da sprint.md)
/sprint-progress <N>          -> sprint specifico (es. /sprint-progress 44)
/sprint-progress --json       -> output machine-readable (per script/hook)
```

## Comportamento

### Prerequisito opt-in

Il comando funziona sempre — non e' gated dal flag `analytics.sprint_progress.enabled`.
Il flag controlla solo se il dominio `analytics` e' nel scheduler (per invocazione automatica);
il comando e' invocabile manualmente indipendentemente dallo stato del flag.

### Esecuzione

Invoca:

```bash
python3 tools/analytics/sprint-progress.py [sprint_id] [--json]
```

- Senza `sprint_id`: lo script legge `sprint_current:` dal frontmatter di
  `management/kanban/sprint.md`.
- Con `sprint_id` (intero): analizza lo sprint indicato.
- Con `--json`: emette JSON machine-readable invece del formato rich text.

### Fallback

Se l'event store (`analytics/events/*.jsonl`) non contiene eventi per lo sprint richiesto
o non e' disponibile, lo script degrada automaticamente al conteggio kanban e mostra
il banner:

```
[Nota: velocita' non calcolabile — event store non disponibile. Uso conteggio kanban.]
```

In questo caso velocita' e proiezione sono omesse dall'output.

### TSK XL outlier

Se `temporal.estimate_protocol.enabled: true` in `factory.config.yaml`, l'output include
una sezione aggiuntiva con i TSK di stima XL in-progress che superano il tempo atteso,
la raccomandazione e il `time_ratio`. La sezione e' omessa senza errori se il flag e' `false`
o se non ci sono outlier.

### Output

- **Plain text** (default): leggibile in chat, con barre ASCII e separatori.
- **JSON** (`--json`): schema strutturato con tutti i campi del segnale burndown (usabile
  da script o hook); campi: `sprint`, `generated_at`, `source`, `done`, `in_progress`,
  `todo`, `total`, `completion_pct`, `velocity_per_day`, `projection_days`,
  `projection_uncertainty_days`, `xl_outliers`.

## Integrazione scheduler

- **Dominio**: `analytics` (gia' attivo in `factory.config.yaml.scheduler.domains.analytics: true`).
- Il comando puo' essere invocato da `suggest-next.py` (EP-033) via `--json` per aggiornamenti
  automatici di stato del sprint senza output interattivo.
- Operazione canonica autonoma: non e' un sub-step di `develop`; va in coda `analytics` del
  wave dispatcher (cross-scope parallel, same-scope serial — invariante race su event store).

## Esempio output

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

Esempio con fallback kanban (event store assente):

```
[Nota: velocita' non calcolabile — event store non disponibile. Uso conteggio kanban.]

Sprint SP-45 — Progress Signal (2026-07-09T14:00:00Z)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Done       :  3 TSK  [█████░░░░░░░░░░░]  33%
In-progress:  2 TSK
Todo       :  4 TSK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Velocita'  :  n/d — fallback kanban
Proiezione :  n/d
```

[^src: tools/analytics/sprint-progress.py]
