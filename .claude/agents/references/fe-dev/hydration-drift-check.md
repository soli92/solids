# hydration-drift-check — fe-dev (EP-030, opt-in `ssr_aware`)

**Ambito**: procedura dettagliata del Hydration Drift Check per `fe-dev`. Attiva SOLO
quando `fe_correctness.ssr_aware.enabled: true AND ssr_context.framework != 'none'` in
`factory.config.yaml`. Foglia di dettaglio di `.claude/agents/fe-dev.md §T5`.

---

## Precondizione

Questo check è attivo SOLO quando:
- `fe_correctness.ssr_aware.enabled: true` in `factory.config.yaml`, E
- `ssr_context.framework != 'none'` (framework SSR rilevato da `stack-detector` SSR section, EP-030 TSK-200).

A flag spento (`ssr_aware.enabled: false`, **default**) o con `framework: none` → check
**no-op silenzioso**: nessuna intercettazione console, nessun finding prodotto, nessun output.
Comportamento identico a v2.21 (backward compat totale, R.P3 opt-in).

## Natura del check

Osservativo. Il check monitora i console errors di hydration durante l'esecuzione degli
scenari SSR. I finding sono WARNING, **non** ERROR: non bloccano automaticamente il gate
pass/fail ma contribuiscono al verdict `conditional` se presenti. Il check **non** modifica
il flusso di esecuzione degli scenari, non fa rerun, non apre PR.

## Tecnica di intercettazione

Il fe-dev registra un listener console durante l'esecuzione degli scenari SSR, senza
dipendenze esterne aggiuntive:

- **Playwright**: `page.on('console', handler)` — registra messaggi `type == 'error'` o
  `type == 'warning'` e filtra per i pattern di hydration.
- **Cypress** (se usato): `cy.on('window:console', handler)` — analogo.

Il listener è attivo dall'apertura del browser (`page.on`) e si chiude al termine del
ciclo di vita dello scenario (cleanup garantito insieme al browser).

## Pattern di intercettazione (4 pattern esatti)

Match su stringa contenuta nel messaggio console (substring match case-sensitive):

| Pattern | Framework target |
|---|---|
| `"Hydration failed because the initial UI does not match"` | Next.js App Router |
| `"Text content does not match server-rendered HTML"` | React 18 |
| `"Warning: Expected server HTML to contain a matching"` | React legacy |
| `"Hydration mismatch"` | Nuxt 3 |

## Schema finding strutturato

Se almeno un messaggio console matcha uno dei 4 pattern:

```yaml
finding_type: HYDRATION_DRIFT
severity: WARNING
url: "https://localhost:3000/<path pagina>"
console_message: "<messaggio console completo che ha matchato il pattern>"
scenario_step: <indice dello step scenario acceptance-spec dove è stato rilevato>
framework: "<framework rilevato da stack-detector: nextjs-app-router | nuxt3 | ...>"
occurrence_count: 1
```

**Regola di aggregazione**: messaggi identici (stesso testo) rilevati nella stessa sessione
→ deduplicati in un **unico finding** con `occurrence_count:` incrementato.
Messaggi distinti (anche dello stesso tipo) → finding separati.

**Esempio**:

```json
{
  "finding_type": "HYDRATION_DRIFT",
  "severity": "WARNING",
  "url": "https://localhost:3000/dashboard",
  "console_message": "Hydration failed because the initial UI does not match",
  "scenario_step": 3,
  "framework": "nextjs-app-router",
  "occurrence_count": 1
}
```

## Comportamento a finding rilevato

Il finding è incluso come **sezione separata** nel report TSK del fe-dev (non come failure
dello scenario):

- Il finding **NON fa fallire lo scenario automaticamente** (severity: WARNING, non ERROR).
- Se presenti finding `HYDRATION_DRIFT`, il fe-dev contribuisce al verdict `conditional`
  (insieme agli altri finding advisory).
- Il finding è incluso nella sezione `critic_findings` del report JSON e nel digest MD del TSK.
- Il fe-dev **non** apre PR, non fa rerun, non modifica il flusso dello scenario.

## Comportamento a finding assente

Se nessun messaggio console matcha i 4 pattern durante l'intera esecuzione dello scenario:
il check è **silenzioso** — nessun output prodotto, nessuna nota nel report.

Cross-link: [EP-030](../../../management/kanban/EP-030-ssr-aware-test-generation/EP-030.md),
[US-106](../../../management/kanban/EP-030-ssr-aware-test-generation/US-106-hydration-drift-check/US-106.md).
