# Temporal Handoff Block — dettaglio (opt-in v2.18+)

**Ambito**: estensione opt-in di `dev-handoff.md` per il blocco YAML strutturato
`temporal_handoff:`. Leggere obbligatoriamente prima di emettere qualsiasi handoff
quando `factory.config.yaml.temporal.handoff_protocol.enabled: true`.
Se il flag è spento → skip: comportamento identico a v2.7.

---

## Schema canonico

```yaml
temporal_handoff:
  handoff_id: "HO-<timestamp-utc>-<random-4char>"   # es. "HO-2026-06-04T14:32:00Z-a1b2"
  elapsed_ms: <integer ≥ 0>                          # wall-clock: epoch_ms(now()) - epoch_ms(task_started_at)
  estimated_remaining_ms: <integer | null>           # best-effort agente uscente; null se non stimabile
  completed_steps:                                   # append-only; può essere vuoto al primo handoff
    - step_id: "<id>"
      name: "<descrizione breve>"
      started_at: "<UTC ISO-8601 Z>"
      completed_at: "<UTC ISO-8601 Z>"
      agent: "<slug>"
  pending_steps:                                     # dichiarati nel piano TSK, NON stimati a runtime
    - step_id: "<id>"
      name: "<descrizione breve>"
      agent: "<slug previsto>"
  context_summary: |
    <testo multi-riga — mai vuoto; aggiunge informazioni di CONTENUTO
    non replicate da completed_steps (vincoli, decisioni, riferimenti file)>
```

## Punti di iniezione

- **Inter-wave handoff** (parallel-scheduler §18): tra una wave e la successiva.
- **Develop → Review** (CQRL v2.12): tra dev-agent e code-reviewer.
- **Develop → Visual Oracle** (FE v2.17): tra fe-dev e visual-oracle.
- **Escalation → Orchestrator**: quando un sub-agent fallisce o si blocca.

## Calcolo dei campi (ADR-030)

- `elapsed_ms`: `epoch_ms(now()) - epoch_ms(task_started_at)`. Wall-clock (include attese tool/API/gating). Granularità millisecondi. Fail-loud se negativo.
- Tutti i timestamp UTC ISO-8601 con `Z` (helper `tools/temporal/utc-now.sh`). Vedi ADR-030 §A.
- `estimated_remaining_ms`: best-effort agente uscente. `null` accettato + nota in `context_summary`.
  Se `temporal.handoff_protocol.use_reference_class: true` AND EP-009 attiva: il campo additivo
  `estimated_remaining_ms_from_history` viene popolato da `analyze_timeline` (ADR-030 §C).

## Esempio dual-format (narrative v2.7 + Temporal Handoff Block esteso)

```markdown
## 2026-06-04 14:32 — develop TSK-084

**Agente:** docs-dev
**TSK:** [[../management/kanban/EP-011-temporal-awareness-layer/US-046-temporal-handoff-protocol/TSK-084]]
**Layer:** docs
**Code path:** .claude/skills/dev-handoff.md
**Files touched:** 1
**Commit:** a1b2c3d
**DoD:** pass
**Note:** Aggiunta sezione Temporal Handoff Block (ADR-031 §A), additiva.
```

```yaml
temporal_handoff:
  handoff_id: "HO-2026-06-04T14:32:00Z-a1b2"
  elapsed_ms: 5400000
  estimated_remaining_ms: null
  completed_steps:
    - step_id: "append-temporal-handoff-section"
      name: "Append Temporal Handoff Block to dev-handoff.md"
      started_at: "2026-06-04T13:00:00Z"
      completed_at: "2026-06-04T14:32:00Z"
      agent: "docs-dev"
  pending_steps: []
  context_summary: |
    Sezione append-only aggiunta in coda. Sezioni v2.7 invariate.
    Backward compat: flag spento → no-op identico a v2.7 (R.P3).
```

## Proiezione da State Machine (se US-047 attiva)

Se `temporal.state_machine.enabled: true` AND TSK con State Machine attiva (ADR-029),
`completed_steps[]` e `pending_steps[]` **non sono compilati a mano** ma proiettati
dal `state_file` (ADR-031 §C.3). Il processo dipende dalla `source` configurata.

### Pseudocodice (ADR-031 §C.3)

```python
# ADR-031 §C.3 — proiezione completed/pending da state file
state = load_json(f"management/state/{tsk_id}.json")

completed_steps = [
    {
        "step_id":      h["step_id"],
        "name":         h["name"],
        "started_at":   h["started_at"],
        "completed_at": h["completed_at"],
        "agent":        h["agent"]
    }
    for h in state["history"]
    if h["status"] == "completed"
]

pending_steps = [
    {
        "step_id": h["step_id"],
        "name":    h["name"],
        "agent":   h.get("agent_expected")
    }
    for h in state["history"]
    if h["status"] == "pending"
]
```

### Modalità per `source`

**`standalone`** (`temporal.state_machine.source: standalone`, ADR-028 §B.1):
- L'agente che produce l'handoff legge il `state_file` READ-ONLY prima della proiezione.
- Diventa il nuovo **single-writer** del `state_file` dopo la proiezione (ownership transfer
  esplicita): scrive le transizioni successive direttamente, senza passare da `record-event.py`.
- Nessuna ricostruzione da eventi: il file è il ground truth.

**`events`** (`temporal.state_machine.source: events`, ADR-028 §B.2):
- Single-writer del `state_file` = tool `record-event.py` tramite `rebuild-state-from-events.sh`.
- L'agente che produce l'handoff legge il `state_file` aggiornato **sempre e solo READ-ONLY**.
- **Mai scrivere direttamente** il `state_file` in questa modalità: bypass del tool viola
  l'append-only enforcement (ADR-028 §B.2).

**Non attiva** (State Machine non attiva per questo TSK, ADR-029 §C):
- `completed_steps[]` e `pending_steps[]` compilati **manualmente** dall'agente dal contesto.
- Fonte: piano TSK (TPM), step eseguiti nella sessione, annotazioni `wiki/log.md`.
- **Non inventare step**: lista vuota → `[]` (mai `null`).
- Single source: la sessione corrente, non un file di stato persistente.

## Vincoli enforced

- **5 campi obbligatori quando flag attivo**: assenza di uno → STOP «missing required field in Temporal Handoff Block: <field>».
- **`context_summary` mai vuoto**: `null` o `""` → STOP «context_summary cannot be empty».
- **Append-only su `completed_steps[]`**: ogni handoff aggiunge, mai modifica retroattivamente.
- **No future prediction su `pending_steps[]`**: dichiarati nel piano TSK (TPM/Arch al kickoff), non stimati a runtime.
- **UTC ISO-8601 con Z** su tutti i timestamp (ADR-030 §A).

## Backward compat

- `temporal.enabled: false` (default) O `temporal.handoff_protocol.enabled: false`: skill si
  comporta identica a v2.7. Nessun nuovo ERROR/WARNING. R.P3.
- `temporal.handoff_protocol.enabled: true` AND `temporal.enabled: false`: fail-loud al boot
  «`temporal.handoff_protocol.enabled` richiede `temporal.enabled: true`. Vedi ADR-031 §B».
- `temporal.handoff_protocol.enabled: true` AND `temporal.context_injection.enabled: false`:
  WARNING-only (dipendenza soft su `task_started_at` per calcolo `elapsed_ms`).

Cross-link: [[temporal-awareness-multiagent-patterns]] §Pattern 4 | [[snapshot-on-context-switch]] |
ADR-031 (backward compat) | ADR-030 (time semantics) | ADR-028 (state file integration) |
ADR-029 (state machine activation policy). Gap chiuso: `temporal-handoff-protocol-fields-missing`
in `wiki/gaps.md` (2026-06-04 18:30 — closed by US-046 EP-011).
