# Fase 5 — Diff+Loop bounded: report, loop, escalation

**Ambito**: §5.1 teardown server, §5.2 schema report JSON+MD, §5.4 diff azionabile
per feedback-router, §5.5 loop bound max_iterations, §5.7 blocco chat escalation umana,
§5.8 append wiki/log.md. Le gate §5.3 (routing verdict) e §5.6 (single-writer
functional_status) sono nel corpo principale di `functional-oracle-protocol.md`.
Foglia di supporto a `functional-oracle-protocol.md` (EP-018).

## §5.1 — Teardown server (garantito)

**Prima di qualunque scrittura su filesystem** — esegui il teardown del `server_pid`
registrato in Fase 1:

```bash
bash: kill <server_pid>          # graceful SIGTERM
# se dopo 5s il processo è ancora vivo:
bash: kill -9 <server_pid>
```

Obbligatorio indipendentemente dal verdict (pass, reject, abort, errore — ADR-064
§Conseguenze «Teardown del server obbligatorio»). Il mancato teardown è un errore
tecnico, non un warning.

## §5.2 — Scrittura report JSON + MD

**File JSON** (machine-readable):
`code_quality/reports/<TSK-id>-functional-iter-<N>.json` — 6 campi tutti obbligatori
(ADR-065 §Storage):

```json
{
  "verdict": "pass | conditional | reject | skip",
  "iterations": <N>,
  "assertions_results": [
    {
      "id": "<assertion-id>",
      "kind": "<kind>",
      "severity": "blocking | advisory",
      "outcome": "pass | fail",
      "detail": "<valore trovato vs atteso, count, ecc.>"
    }
  ],
  "critic_findings": [
    {
      "observation": "<osservazione qualitativa>",
      "evidence_ref": "<path artefatto reale>",
      "severity": "advisory"
    }
  ],
  "trace_path": "code_quality/reports/<TSK-id>-functional-iter-<N>/",
  "timestamp": "<ISO-8601 UTC>"
}
```

`critic_findings: []` se `critic: off` o nessun finding ha superato il filtro
evidence-provenance. `assertions_results` è l'array `AssertionResult[]` di Fase 4 §4.1.

**File MD** (digest umano-leggibile):
`code_quality/reports/<TSK-id>-functional-iter-<N>.md` — struttura minima:

```markdown
# Functional Oracle — <TSK-id> iter <N>

**Verdict**: `<verdict>` | **Timestamp**: <ISO-8601>

## Assertion Results

| id | kind | severity | outcome | detail |
|---|---|---|---|---|
| <id> | <kind> | blocking/advisory | pass/fail | <detail> |

Blocking: <X>/<Y> pass | Advisory: <X>/<Y> pass (fallite <Z>, soglia <advisory_max>)

## Critic Findings (advisory)

<elenco open_questions con evidence_ref; oppure «Nessun finding ammissibile» se vuoto>

## Trace

Artefatti in: `code_quality/reports/<TSK-id>-functional-iter-<N>/`
Screenshot: <elenco step-NN-action.png> | Console log: `console.log.json` | Network log: `network.log.json`

## Loop status

Iterazione <N> / <MAX_ITERATIONS>. Next action: `<next_action>`.
```

## §5.4 — Diff azionabile per feedback-router

Su `conditional` o `reject` con finding azionabili (almeno una `blocking` fail O almeno
un `critic_finding` con `evidence_ref` valido):

```json
{
  "tsk_id": "<TSK-id>",
  "iter": <N>,
  "constraint": {
    "scope": "fix only the functional findings below; no opportunistic refactor",
    "source": "functional-oracle-protocol"
  },
  "actions": [
    {
      "finding_id": "<assertion-id o critic-finding-index>",
      "kind": "<kind asserzione o 'critic_advisory'>",
      "severity": "blocking | advisory",
      "description": "<cosa non passa e perché>",
      "evidence_ref": "<path artefatto: step PNG, console.log.json, network.log.json>",
      "expected_fix": "<suggerimento concreto di correzione>",
      "acceptance_criteria": "<asserzione che deve passare alla prossima iterazione>"
    }
  ],
  "report_ref": "code_quality/reports/<TSK-id>-functional-iter-<N>.md"
}
```

Ordinamento: `blocking` prima di `advisory`; all'interno di ogni tier, ordine dichiarato
nell'acceptance-spec. Asserzioni `fail` con `detail` vuoto non sono azionabili →
nota «finding non azionabile: spec incompleta» (l'assenza di `acceptance_criteria`
verificabile renderebbe il loop infinito per definizione).

## §5.5 — Loop bound `max_iterations`

```
SE current_iter < MAX_ITERATIONS AND verdict IN {conditional}:
  → next_action = "loop"
  → chiama feedback-router con diff §5.4
  → functional_status = "conditional"
  → dev-agent fixa → ri-invoca functional-oracle-protocol (iter N+1)

SE current_iter >= MAX_ITERATIONS AND verdict NOT IN {pass, skip}:
  → loop esaurito senza convergenza
  → forza verdict = "reject", next_action = "escalate-human"
  → functional_status = "reject"
  → nota nel report JSON: max_iterations_reached: true (vedi sotto)
  → segnala in chat (vedi §5.7)

SE verdict == "reject" (indipendentemente da current_iter):
  → next_action = "escalate-human" direttamente (non entra nel loop)
  → functional_status = "reject"
```

La nota `max_iterations_reached` nel JSON come entry `critic_findings`:

```json
{
  "observation": "Loop esaurito: max_iterations (<N>) raggiunto senza convergenza a pass.",
  "evidence_ref": "code_quality/reports/<TSK-id>-functional-iter-<N>.json",
  "severity": "advisory"
}
```

## §5.7 — Blocco chat su escalation umana

Su `next_action: escalate-human` (reject diretto o loop esaurito):

```
FUNCTIONAL ORACLE — <TSK-id> iter <N> → ESCALATION UMANA (PATTERN §7 r.16)
============================================================================
Verdict: <reject>  [max_iterations_reached: <true|false>]
Blocking fail: <X> | Advisory fail: <Y>
Critic findings: <Z> (con evidenza)
Report: code_quality/reports/<TSK-id>-functional-iter-<N>.md
Trace:  code_quality/reports/<TSK-id>-functional-iter-<N>/

Possibili next step:
1. Re-Develop manuale con istruzioni dal report → poi /functional-oracle <TSK-id>.
2. Aggiorna l'acceptance-spec se le asserzioni risultano over-specified → /functional-oracle.
3. Accept-as-is con override → apri wiki/incidents/YYYY-MM-DD-tsk-<id>-functional-accepted.md.

CQRL functional loop non auto-procede.
```

## §5.8 — Append `wiki/log.md`

Append entry di chiusura (marker `functional-oracle`):

```
develop | functional-oracle <TSK-id> iter-<N> → <verdict> [max_iterations_reached: <true|false>] | <ISO-8601>
```

[^src: design_&_architecture/decisions/ADR-067.md §C — loop bounded max_iterations]
[^src: design_&_architecture/decisions/ADR-065.md §Storage/frontmatter]
[^src: design_&_architecture/decisions/ADR-009.md §Decisione — feedback-router CQRL riuso]
[^src: design_&_architecture/decisions/ADR-064.md §Conseguenze — teardown obbligatorio]
[^src: management/kanban/EP-018-fe-functional-oracle/US-068-skill-functional-oracle-protocol/US-068.md §Fase 5]
