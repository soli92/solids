---
skill: dispatch-policy
leaf_of: dispatch-policy.md
section: "§12"
description: "CQRL Auto-Dispatch: cascade FE, precondizioni composte, esiti e logging"
---

# dispatch-policy §12 — CQRL Auto-Dispatch: cascade e dettaglio

Trigger, precondizione ed esecutore sono nel core (`dispatch-policy.md` §12).

## Cascade FE

```
develop → [visual-oracle] → [a11y/ux-ui] → [functional-oracle] → CQRL-review
```

- solo `trigger_default.enabled: true`, altri gate spenti → `develop → CQRL-review`;
- visual-oracle attivo → `develop → visual-oracle → CQRL-review`;
- tutti i gate attivi → `develop → visual-oracle → [a11y/ux-ui] → functional-oracle → CQRL-review`.

## Precondizioni composte

- `fe_correctness.enabled: true`: `visual_status: pass` → procedi; `reject` → CQRL **SKIPPED**
  (gate umano sul visual oracle: rivedere codice su un rendering non validato non serve);
  `pending` → attendi.
- `fe_correctness.functional_oracle.enabled: true`: `functional_status ∈ {pass, conditional}` →
  procedi; `reject` → SKIPPED (gate umano); `pending` → attendi.

## Esiti (Layer-2, gate semantico advisory)

| Verdict | Azione automatica | Azione umana |
|---|---|---|
| `pass` | `review_status: passed` | nessuna |
| `conditional` | task_package → re-develop (bounded, R.Q4) | conferma del dispatch |
| `reject` | `review_status: rejected`; STOP | **decisione umana obbligatoria** (R.16) |

Il dispatcher non forza mai merge o deploy su `reject` (R.14 + R.16).

## Logging

Il `code-reviewer` appende la propria entry in `wiki/log.md` a fine review; l'orchestrator
registra solo il dispatch (o lo skip, con la precondizione che l'ha causato).

[^src: portale-servizi-factory — dispatch-policy §9 e foglia cqrl-cascade-detail (FAC-TSK-219, FAC-TSK-372); ritorno EP-072 TSK-778]
