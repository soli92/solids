# Fase 4-bis — Visual Verification (dettaglio, opt-in fe_correctness)

**Ambito**: sub-step di Develop FE, Class B (FE-only opt-in). Posizionata dopo la Fase 4
(build/typecheck verde) e prima della Fase 5 (handoff a `done`). Formalizza il Punto 1 di
ADR-013 (ordering `develop → visual-oracle → review`). Questa foglia contiene la procedura
completa; il trigger e il no-op esplicito vivono nel corpo di `dev-protocol.md`.

---

## Trigger (condizione AND)

- `TSK.layer == 'fe'` **AND** `factory.config.yaml.fe_correctness.enabled == true`.

## No-op esplicito (backward compat)

A flag spento (`fe_correctness.enabled: false`, default) **oppure** `TSK.layer != 'fe'`,
la Fase 4-bis è **no-op**: il TSK passa direttamente da Fase 4 a Fase 5, con
`visual_status` assente o `pending`. **Comportamento identico a v2.16.** Una factory
che non opta-in non vede alcuna differenza.

## Fail-loud

Se il trigger è soddisfatto (`layer: fe` + `fe_correctness.enabled: true`) ma la skill
`visual-oracle-protocol` **non è presente** nell'adapter → **ERROR** «`fe_correctness.enabled: true`
ma skill `visual-oracle-protocol` assente; impossibile eseguire la Fase 4-bis». STOP.
Mai degradare silenziosamente a no-op quando il flag è attivo.

## Azione

1. Invoca `visual-oracle-protocol` (skill) come sub-procedura, passando il `TSK-id` e il
   `resolved_code_path` (da Fase 0 step 2-bis). La skill produce un output strutturato
   `{verdict, defects}` (il critic è lo stesso `fe-dev` in passata multimodale, vedi ADR-009 §Conseguenze).

## Esiti

```
verdict: pass        → visual_status: pass; TSK transita a status: done (→ Fase 5).
verdict: conditional → loop fe-dev (bounded fe_correctness.max_iterations, default 3);
                       la lista difetti (defects) è l'input handoff dell'iterazione
                       successiva; il TSK resta in-progress fino a pass o esaurimento bound.
verdict: reject      → visual_status: reject; TSK resta in-progress; gate umano
                       (difetto strutturale, non risolvibile in 1-3 iter; coerente con
                       CQRL §19 reject → gate umano, non auto-loop).
```

- **Loop `conditional`**: bounded da `fe_correctness.max_iterations` (default `3`, analogo a
  `code_quality.max_iterations` / R.Q4 di CQRL). A ogni iterazione la lista `defects` è
  passata come handoff a `fe-dev`, che ri-implementa e ri-sottopone al visual oracle.
  Esaurito il bound senza `pass`, l'esito degrada a gate umano (non `done`).
- **`reject`**: il TSK **non** transita a `done`; resta `in-progress` con `visual_status: reject`.
  La review è bloccata a valle (precondition Fase 0 di `code-review-protocol`, ADR-013 §Punto 2).

**Input**: TSK FE con build/typecheck verde (output Fase 4); `factory.config.yaml.fe_correctness`.
**Output**: `visual_status: pass` (→ Fase 5) | loop fe-dev (`conditional`) | `visual_status: reject` + gate umano.
**Criterio**: `verdict == pass` → procedi a Fase 5; altrimenti loop bounded o STOP per gate umano.

[^src: design_&_architecture/decisions/ADR-013.md §Punto 1 — dev-protocol Fase 4-bis (flusso verbatim)]
[^src: design_&_architecture/decisions/ADR-009.md §Conseguenze — critic = stesso fe-dev, ordering visual → review]
