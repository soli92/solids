---
scope: scheduler-analytics-instrumentation
description: >
  Payload JSON e volume stimato per i 3 punti di iniezione wave dell'analytics
  dogfooding nel parallel-scheduling (EP-013, v2.19). Foglia di dettaglio per
  .claude/skills/parallel-scheduling.md — letta su trigger quando
  analytics.dogfooding.enabled: true. Ambito: payload, volume table, ADR refs.
---
# Scheduler — Analytics Instrumentation (dettaglio payload)

## Gate

`factory.config.yaml.analytics.dogfooding.enabled: true` AND
`analytics.granularity` in `{wave, tool}`.
A flag spento → EARLY RETURN, 0 side effect.
Se `granularity: tsk` → wave events skipped (solo TSK events da dev-protocol).

**Single-writer**: stesso tool `record-event.py` di dev-protocol (ADR-039 §B).
**PII invariante**: payload solo allowlist-compliant (ADR-040 §A). No contenuto, no prompt.

## Punto 1 — `state: wave_started` (Fase 4, ADR-042)

**Trigger**: `parallel-scheduling` inizia il dispatch di una wave.
**Granularità**: attivo per `granularity` in `{wave, tool}`.

```json
{
  "task_id": "<wave_id>",
  "project_id": "<factory-slug>",
  "actor_type": "agent",
  "actor_id": "orchestrator",
  "task_type": "scheduler",
  "state": "wave_started",
  "ts": "<ISO-8601 UTC con Z>",
  "wave_id": "<UUID o slug wave, es. wave-2026-06-08T14:30:00Z-a1b2>",
  "wave_size": N,
  "candidates": ["<TSK-id-1>", "<TSK-id-2>"],
  "tokens": {"input": 0, "output": 0},
  "model": "<current-model-id>",
  "tool_calls": []
}
```

## Punto 2 — `state: wave_completed` (Fase 5 join, ADR-042)

**Trigger**: tutti i sub-agent della wave hanno completato.
**Granularità**: attivo per `granularity` in `{wave, tool}`.
Payload = `wave_started` + estensioni:

```json
{
  "wave_elapsed_ms": "<wall-clock ms da wave_started>",
  "success_count": N,
  "failure_count": M
}
```

## Punto 3 — `state: sub_agent_dispatched` (granularity: tool only)

**Trigger**: ogni singolo sub-agent viene dispatched (Fase 4, per ogni candidato).
**Granularità**: SOLO per `granularity == tool`. Se `wave` → skip.

```json
{
  "task_id": "<TSK-id specifico>",
  "wave_id": "<wave_id>",
  "actor_id": "<be-dev|fe-dev|...>",
  "actor_type": "agent",
  "state": "sub_agent_dispatched",
  "ts": "<ISO-8601 UTC>",
  "dispatch_ts": "<ISO-8601 UTC>",
  "completion_ts": "<ISO-8601 UTC, valorizzato a job completion>"
}
```

## Volume stimato

Stima sprint v2.19 (EP-012 + EP-013, ~30 TSK, ~4 wave parallele):

| Granularità | Eventi stimati |
|---|---|
| `tsk` | ~60 (solo TSK events da dev-protocol) |
| `wave` | ~68 (60 TSK + 4 wave×2 stati) |
| `tool` | ~92+ (68 + N sub-agent dispatch) |

[^src: ADR-038.md §D]

## Cross-link temporale (EP-011)

Il `ts` degli eventi wave è UTC ISO-8601 con suffisso `Z`, coerente con il tool
`utc-now.sh` di EP-011 US-045 (ADR-030). Allineamento totale tra EP-011 e EP-013.

## Riferimenti ADR

ADR-038 §C §D (3 punti di iniezione + volume) · ADR-039 §A §B (single-writer, dedup hash
compound) · ADR-040 §A §B (allowlist PII) · ADR-042 §A §B (nuovi enum
`wave_started`/`wave_completed`/`sub_agent_dispatched`).
Cabling inline nelle Fasi 4-5, no nuovo dominio scheduler. Pattern additivo ADR-031.
