# visual-oracle-integration — fe-dev (EP-005, opt-in `fe_correctness`)

**Ambito**: procedura dettagliata del Visual Oracle per `fe-dev`. Attiva SOLO se
`fe_correctness.enabled: true` in `factory.config.yaml`. Foglia di dettaglio di
`.claude/agents/fe-dev.md §T1`.

---

## Regola guida

Prima di marcare un TSK FE `done`, verifica il rendering. Codice che compila e
passa il typecheck non implica un rendering corretto: lo strato di rendering è più
fondamentale dello strato di codice (un componente con codice idiomatico ma rendering
rotto è inutile; un componente con rendering corretto ma codice migliorabile ha già
valore di business).

## Trigger (opt-in)

La Visual Verification si attiva SOLO se:

```
TSK.layer == 'fe' AND factory.config.yaml.fe_correctness.enabled == true
```

A flag spento (`fe_correctness.enabled: false`, default) il sub-step è **no-op**:
il TSK passa direttamente da Fase 4 a Fase 5 con `visual_status` assente/`pending`.
Comportamento identico a v2.16.

## Pattern

Evaluator-optimizer: lo stesso `fe-dev` produce il codice (producer) e poi esegue una
**passata di critica visiva multimodale** (legge i PNG via `Read`) come sub-skill inline
— non un sub-agent dedicato né `qa-dev` (ADR-009 §Decisione). È lo stesso schema «stesso
agente in due ruoli» già istanziato in `code-review-protocol` (dev produce → reviewer
critica → dev fixa), qui mantenuto dentro `fe-dev` perché il critic visivo richiede la
stessa conoscenza di dominio del producer.

## Flusso pass/conditional/reject (esito Fase 4-bis)

| Esito | Azione | Stato |
|---|---|---|
| `pass` | `visual_status: pass`; TSK transita a `status: done` → pronto per review | done |
| `conditional` | loop `fe-dev` **bounded** (difetti rilevati = input handoff del re-Develop) | in-progress |
| `reject` | `visual_status: reject`; TSK resta `in-progress`; **gate umano** | in-progress |

Il loop `conditional → fe-dev → visual-oracle` è **bounded** da
`fe_correctness.max_iterations` (default **3**), analogo a `code_quality.max_iterations`
del CQRL (R.Q4). Esaurito il bound senza `pass` → forza `reject` → gate umano.
`reject` non auto-loop (PATTERN §7 r.16).

## Interazione con CQRL

Quando `fe_correctness.enabled: true`, la Fase 0 di `code-review-protocol` ha una
precondition additiva che **blocca** `/review` su un TSK FE finché `visual_status != pass`
(ADR-013 §Punto 2). A flag spento la review parte normalmente.

Cross-link: [US-017](../../../management/kanban/EP-005-fe-visual-oracle/US-017-skill-visual-oracle-protocol/US-017.md),
[ADR-009](../../../design_&_architecture/decisions/ADR-009.md),
[ADR-013](../../../design_&_architecture/decisions/ADR-013.md).
