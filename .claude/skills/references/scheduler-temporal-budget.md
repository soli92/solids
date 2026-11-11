---
scope: scheduler-temporal-budget
description: >
  Schema YAML esteso del wave plan, calcolo token_budget e template gate umano per il
  Temporal Budget Hook (EP-014, v2.19). Foglia di dettaglio per
  .claude/skills/parallel-scheduling.md — letta su trigger quando
  temporal.budget.enabled: true. Ambito: schema wave plan, 3 sorgenti token_budget,
  invarianti single-writer e snapshot, template messaggio gate, cross-link EP-011.
---
# Scheduler — Temporal Budget Hook (dettaglio schema e calcoli)

## Gate

`factory.config.yaml.temporal.budget.enabled: true`. A flag spento → no-op assoluto:
wave plan senza campi budget, comportamento identico v2.18 (R.P3).

## Schema wave plan esteso (§18.6, gated)

Quando `temporal.budget.enabled: true` + `temporal.budget.wave.enabled: true`
(default: true se master switch on), la Fase 4 del parallel-scheduling estende lo
schema YAML del wave plan con:

```yaml
wave:
  id: <wave-uuid>
  size: <N candidati>
  candidates: [<task-id>, ...]
  estimate: <S|M|L>                    # legacy v2.11, mantenuto invariato
  # === NUOVO v2.19 — gated temporal.budget.enabled: true ===
  token_budget: <int>                  # tetto wave: somma P85 per-layer (ADR-044 §C)
  elapsed: <int>                       # token consumati: 0 a wave_started, incrementale
  estimated_remaining:
    P50: <int>
    P85: <int>
    P95: <int>
  bootstrap_mode: <bool>               # true se N eventi < bootstrap.min_n
  cost_per_1k_tokens: <float|null>     # null = non mostrato al gate umano
  # Opzionali (ADR-044 §D)
  tsk_budgets:                         # presente solo se temporal.budget.tsk.enabled: true
    - task_id: <id>
      token_budget: <int>
      elapsed: <int>
  sprint_budget:                       # presente solo se temporal.budget.sprint.enabled: true
    sprint_id: <slug>
    token_budget: <int>
    elapsed: <int>
```

## Calcolo `token_budget` (wave-level) — 3 sorgenti

1. **Fonte primaria** (`token_budget_source: p85`): `sum(P85_layer for task in candidates)`
   da output `estimate-project` EP-010 US-041 o da `analytics/reports/baseline/` EP-013 US-053.
2. **Fallback bootstrap** (N eventi < `bootstrap.min_n: 10`): usa
   `temporal.budget.bootstrap.wave_default_tokens` (default: 100000). Marker `bootstrap_mode: true`.
3. **Fixed** (`token_budget_source: fixed`): usa `temporal.budget.wave.token_budget_fixed`
   direttamente.

## Invarianti

- `estimated_remaining` espone **sempre** P50/P85/P95, mai numero puntuale.
  Coerente con EP-010 invariante "mai numero puntuale". Il governor (skill
  `temporal-budget-governor`, TSK-112) legge la distribuzione, non un valore singolo.
- `parallel-scheduling` è l'**unico writer** dei campi `token_budget`/`elapsed`/
  `estimated_remaining` del wave plan. Il governor è **read-only** sul wave plan (ADR-044 §G).
- **Snapshot immutabile post-gate**: una volta esposto al gate umano
  (`parallel_gate_threshold` triggerato), il wave plan è **immutabile** per quella
  sessione. Solo `elapsed` cresce a ogni `state: finished` di un TSK nella wave.

## Template messaggio gate umano (PATTERN §18)

Quando `parallel_gate_threshold` triggerata con `temporal.budget.enabled: true`:

```
Wave proposta: <N> candidati, size <S|M|L>
Token budget wave: <token_budget>
Elapsed (corrente): <elapsed>
Estimated remaining: P50=<X>, P85=<Y>, P95=<Z>
[Cost stimato: ~$<dollari>]          (mostrato solo se cost_per_1k_tokens != null)
[BOOTSTRAP MODE: stime da PERT/fallback, calibrazione in corso]  (solo se bootstrap_mode: true)
Conferma? [y/N]
```

Il maintainer decide su numeri reali, non su S/M/L statici.

## Cross-link EP-011

Il campo `elapsed_ms` del Temporal Handoff Protocol (EP-011 US-046) contribuisce al
calcolo di `elapsed` token quando il TSK ha sia tempo che token (doppia alimentazione).
La skill `temporal-budget-governor` (TSK-112) decide quale metric è primaria in
funzione di `temporal.budget.wave.token_budget_source`.
