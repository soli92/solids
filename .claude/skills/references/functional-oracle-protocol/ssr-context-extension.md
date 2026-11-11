# SSR Context Extension (EP-030, v2.22)

**Ambito**: schema `ssr_context:` nello schema acceptance-spec, semantica sotto-campi,
regola guardia `qa-dev`, categorie SSR minime, invarianti. Foglia di supporto a
`functional-oracle-protocol.md`. La precondizione di attivazione è nel corpo principale.

## Schema `ssr_context:` nello acceptance-spec

Campo **opzionale** additivo e backward-compatible (sezione 1b dello schema
`.claude/schemas/acceptance-spec.schema.yaml`). Spec senza `ssr_context:` → valide (0 ERROR lint).

```yaml
# ssr_context: opzionale — attivato quando fe_correctness.ssr_aware.enabled: true (EP-030, v2.22)
# Campo assente = comportamento invariato (backward compat totale)
ssr_context:
  javascript_enabled: true     # false = assertion su HTML iniziale senza idratazione JS
  revalidate_before_run: false # true = invalida cache ISR prima dell'esecuzione del test
```

**Semantica dei sotto-campi**:

| Campo | Default se assente | Semantica |
|---|---|---|
| `javascript_enabled` | `true` (compat) | `false` → verifica HTML iniziale renduto dal server, senza esecuzione JS (critical path SSR). `true` → comportamento CSR standard (idratazione completa). |
| `revalidate_before_run` | `false` (compat) | `true` → invalida cache ISR prima dell'esecuzione (rilevante SOLO se `revalidation_support: true` da stack-detector). |

**Esempio completo** (scenario SSR con `ssr_context:`):

```yaml
scenario_id: homepage-server-html
description: "Il contenuto critico è presente nell'HTML iniziale senza JS"
ssr_context:
  javascript_enabled: false
  revalidate_before_run: false
steps:
  - action: navigate
    url: "/"
  - action: assert_text_present
    selector: "h1"
    value: "Benvenuto"
```

## Regola guardia `qa-dev` — generazione scenari SSR

`qa-dev` genera scenari con `ssr_context:` **SOLO** quando entrambe le condizioni sono
soddisfatte:
1. `fe_correctness.ssr_aware.enabled: true` (config flag, `factory.config.yaml`).
2. `ssr_context.framework != 'none'` (output `stack-detector` SSR section — EP-030 TSK-200).

Se entrambe soddisfatte, categorie minime di scenari SSR per framework rilevato:

| Categoria | Condizione | `javascript_enabled` | `revalidate_before_run` |
|---|---|---|---|
| Critical path SSR | Sempre (framework != none) | `false` — verifica HTML senza idratazione | `false` |
| ISR revalidation | Solo se `revalidation_support: true` (Next.js App Router / Pages Router) | `true` | `true` |
| Hydration check | Sempre (scenario osservativo, accoppiato con US-106 Hydration Drift) | `true` | `false` |

## Invarianti

- `qa-dev` **NON modifica** acceptance-spec esistenti. Aggiunge solo nuovi scenari.
- `framework: none` → nessuno scenario SSR, nessun campo `ssr_context:` aggiunto.
- `framework: unknown-ssr` → solo scenari `javascript_enabled: false` generici; nessuno
  scenario ISR o router-specific.

[^src: EP-030 TSK-200 — stack-detector SSR section]
[^src: design_&_architecture/decisions/ADR-065.md §B — schema acceptance-spec estensione additiva]
