# Passata 4 — Premortem on Merge (dettaglio completo)

Ambito: dettaglio della Passata 4 (opt-in) di `code-review-protocol.md`. Leggere prima
di eseguire il pass. Condizionale: solo se `"premortem-on-merge"` è in
`factory.config.yaml.code_quality.passes`.

---

**Pass aggiuntivo, additivo e non distruttivo**: non sostituisce le 3 passate primarie né
modifica la logica del verdict aggregator. Eseguito **solo** se attivato.

**Pre-condizione** (silenzia tutto il pass):

```
IF "premortem-on-merge" NOT IN factory.config.yaml.code_quality.passes:
    SKIP   # default off (R.P3 + ADR-005) — comportamento identico a v2.15
```

**Invocazione della skill `premortem-protocol`** (mini-premortem, non Fase 3 completa):

| Parametro | Valore |
|---|---|
| `target` | «diff of TSK-<id>» |
| `context` | file toccati dal diff (`files_in_scope`) — **no full TSK body** |
| `timeframe` | `3mo` (hardcoded — orizzonte "regression in production") |
| `scope` | `"regression in production"` |
| `max_findings` | `5` (mini-premortem: max 3-5 finding, non la Sintesi Fase 5 completa) |

**Output**: una sotto-sezione `### Premortem on Merge` (max 3-5 finding) **dentro il
verdict standard**. Non è un verdict separato; è contesto aggiuntivo per l'umano e
per il dev-agent. Il risultato della skill è un mini-Risk-Registry, non la Sintesi
completa.

**Touchpoint #3** (in-scope US-012): dopo l'aggregator, se
`verdict_aggregator == "conditional"` **AND** il TSK ha
`risk_classification.tier` MATCHES `/^tiger-/` → aggiungi nel `task_package`
consegnato al dev-agent la riga:

```
Considera /premortem prima del re-Develop (TSK tagged tiger-*)
```

**Touchpoint #2** (out-of-scope, **v2.17+ candidate**): il routing dei finding del
premortem verso un tier specifico via `feedback-router` non è implementato in v2.16.

[^src: design_&_architecture/decisions/ADR-005.md]
[^src: management/kanban/EP-001-premortem-skill-scaffolding/US-012-premortem-on-merge/US-012.md §Technical Specs]
