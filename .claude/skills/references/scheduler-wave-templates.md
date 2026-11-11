---
scope: scheduler-wave-templates
description: >
  Template canonici per il wave plan (Fase 4), log entry (Fase 6) ed esempio dry-run
  completo del parallel-scheduling (v2.11). Foglia di dettaglio per
  .claude/skills/parallel-scheduling.md — letta sempre per output strutturato canonico.
  Ambito: wave plan template, log entry template, compression stats, dry-run example.
---
# Scheduler — Wave Templates (template canonici)

## Wave plan (Fase 4)

```
WAVE PLAN (sprint NN, sched v2.11)
====================================
Level 0 — parallel (3 of max 4):
  ▸ Group A:
    • TSK-007 [be, S, P0] code_path=src/auth/**
    • TSK-012 [db, M, P1] code_path=db/migrations/0042_*.sql
    • TSK-019 [fe, S, P0] code_path=web/src/login/**
Level 1 — serial (2 nodes, depends_on Level 0):
  ▸ TSK-008 [be, S, P0] depends_on=[TSK-007]
  ▸ TSK-013 [qa, M, P1] depends_on=[TSK-007,TSK-012,TSK-019]

VCS hand-off accodato seriale dopo ogni wave.
Procedo? [y/N]
```

## Log entry (Fase 6)

```
## YYYY-MM-DD HH:MM — wave sprint-NN
**Levels:** 2 (0=3 parallel, 1=2 serial)
**Dispatched:** 5 TSK (4 ok, 1 failed)
**Failed:** TSK-013 (reason: vcs-handoff abortito da utente)
**Wall-clock saved:** ~estimated 60% vs serial baseline
**Compression (v2.14, se attivo):** profile=conservative, tokens_in=15.2k→7.4k, tokens_out=8.3k→3.9k, drift=0
```

Se `compression.output.enabled: true`, il companion `wave_report.md` in `memory/episodic/`
include una sezione `## Compression stats` con la matrice:
`canale × (tokens_in_raw, tokens_in_compressed, tokens_out_raw, tokens_out_compressed, ratio, drift_count)`.
Vedi `caveman-protocol §Fase 5`.

Record episodico in `memory/episodic/YYYY-MM-DD-HH-MM-wave-NN.md` (struttura completa
DAG per audit + retroactive analysis).

## Dry-run example (5 TSK)

Input candidates:

```
TSK-001 [be, S, P0] depends_on=[]            code_path=[src/db/**]
TSK-002 [fe, S, P0] depends_on=[]            code_path=[web/src/login/**]
TSK-003 [be, M, P0] depends_on=[TSK-001]     code_path=[src/auth/**]
TSK-004 [be, S, P1] depends_on=[TSK-001]     code_path=[src/auth/handlers/**]
TSK-005 [qa, M, P0] depends_on=[TSK-003,TSK-004,TSK-002] code_path=[tests/e2e/**]
```

E_dep:

```
TSK-001 → TSK-003
TSK-001 → TSK-004
TSK-003 → TSK-005
TSK-004 → TSK-005
TSK-002 → TSK-005
```

E_conf: `{TSK-003, TSK-004}` (overlap `src/auth/**` ∩ `src/auth/handlers/**`)

Levels:

- Level 0: TSK-001, TSK-002 → no conflict → 1 group di 2 → parallel
- Level 1: TSK-003, TSK-004 → conflict → 2 group di 1 ciascuno → serial fra loro
- Level 2: TSK-005 → 1 group di 1 → solo

Plan: 4 wave (Level 0 parallel; Level 1.a; Level 1.b; Level 2).
Wall-clock saved: 1 wave eliminato dal parallelismo del Level 0.
