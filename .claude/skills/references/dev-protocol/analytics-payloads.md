# Analytics Instrumentation — dettaglio payload (opt-in v2.19+)

**Ambito**: documentazione completa dell'Analytics Instrumentation di `dev-protocol.md`.
Leggere se `analytics.measurement.enabled: true` AND `dogfooding.enabled: true`;
altrimenti EARLY RETURN (0 side effect, 0 eventi scritti).

---

**Gate**: `analytics.measurement.enabled: true` AND `dogfooding.enabled: true`.
SE entrambi `false` (default): EARLY RETURN — 0 side effect, 0 eventi scritti.
A `measurement.enabled: true` ma `dogfooding.enabled: false`: cabling no-op (comportamento v2.18).

**Single-writer**: `tools/analytics/record-event.py` è l'UNICO writer di
`analytics/events/<YYYY-MM>.jsonl` (R.G5). [^src: ADR-039 §B]

**Segnaposto**: `<project.name>` e' `project.name` di `factory.config.yaml`, mai un nome scritto qui:
la skill si copia nelle factory derivate e un valore fisso attribuirebbe i loro eventi a questa.

**PII invariante**: payload senza contenuto file, prompt LLM, env vars, segreti, PII utente (ADR-040 §A).

## Punti attivi

- Punto 1: `state: started` (Fase 2, todo → in-progress)
- Punto 2: `state: finished` (Fase 5, in-progress → done)

## Punto 3 — blocked

```bash
_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; _REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '.')"
python3 "$_REPO_ROOT/tools/analytics/record-event.py" \
  --event "{\"task_id\":\"<TSK-NNN-slug>\",\"project_id\":\"<project.name>\",\"actor_type\":\"agent\",\"actor_id\":\"<agent-slug>\",\"task_type\":\"<layer>\",\"state\":\"blocked\",\"ts\":\"$_TS\",\"tokens\":{\"input\":0,\"output\":0,\"cache_read\":0,\"cache_write\":0},\"model\":\"claude-sonnet-4-6\",\"tool_calls\":[],\"blocked_reason\":\"<slug-max-200-char>\"}" \
  2>/dev/null || true
```

## Punto 4 — aborted

Stesso call site di Punto 3, sostituendo `state: blocked` con `state: aborted` e
`blocked_reason` con `aborted_reason` (ADR-042 §A: timeout, override umano, errore non recuperabile).

Il motivo è un **slug strutturato max 200 char**, mai testo libero; Punto 3 ammette `blocking_artifacts`.

## Fail-open

Se la scrittura fallisce: **prosegui** (fail-open, ADR-039 §D), aggiungi
`[analytics-write-fail] TSK-NNN state=<state> at <ts>` a `wiki/log.md`, **nessun retry**.

[^src: design_&_architecture/decisions/ADR-038.md §B — 4 punti di iniezione TSK (started/finished/blocked/aborted); ADR-042.md §A — enum `aborted`]
[^src: design_&_architecture/decisions/ADR-040.md §A — payload allowlist, PII invariante]
