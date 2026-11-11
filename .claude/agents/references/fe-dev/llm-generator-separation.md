# llm-generator-separation — fe-dev (EP-019, opt-in `design_intelligence`)

**Ambito**: procedura dettagliata LLM-Generator Separation per `fe-dev`. Attiva SOLO se
`design_intelligence.enabled: true AND generator_tool != none` in `factory.config.yaml`.
Foglia di dettaglio di `.claude/agents/fe-dev.md §T4`.

---

## Integrazione opt-in nella pipeline Develop FE (ADR-069 §B, US-075)

Quando `design_intelligence.enabled: true AND design_intelligence.generator_tool != none`,
il fe-dev **produce una spec parametrica** invece di espandere direttamente il boilerplate
via LLM, e delega l'espansione a un generatore deterministico (Plop.js / Yeoman) tramite
la skill `llm-generator-separation-protocol`.

## Trigger (opt-in)

```
factory.config.yaml.design_intelligence.enabled == true
AND factory.config.yaml.design_intelligence.generator_tool != none  (plop|yeoman)
AND TSK.layer == 'fe'
```

## Confine di responsabilità (ADR-069 §A)

- Il **fe-dev (LLM) produce SOLO la spec parametrica** — YAML con almeno:
  `name`, `type`, `props`, `variants`, `theme_tokens`.
  I `theme_tokens` derivano dall'`art_director_spec` (ADR-068 §D): il fe-dev è
  **read-only** sul tema (R.D1). Non produce l'import; non scrive stili inline.
- Il **generatore (deterministico) espande il boilerplate** — stesso input → stesso output.

## Flusso (sub-step della Fase 4 Develop FE)

```
fe-dev legge art_director_spec_path → produce spec parametrica YAML
  |
  v
skill llm-generator-separation-protocol
  (.claude/skills/llm-generator-separation-protocol.md)
  |
  v
tool run-generator.sh (tools/visual/run-generator.sh)
  |
  v
scaffold deterministico → fe-dev integra SOLO la logica custom
```

## Caso fuori-template (ADR-069 §D)

Se il componente richiede personalizzazione fuori dal template standard → il fe-dev
produce una **spec custom con nota esplicita `"fuori-template"`** e procede a sviluppo
diretto del componente. Il generatore **non viene invocato**.

## Loop Critic/Judge (ADR-069 §E)

Se il Critic/Judge (in `ux-ui-review-protocol`) boccia il risultato, la skill richiede
una **nuova spec** al fe-dev, **non** una riscrittura del template. Il loop è bounded
da `ux_ui.max_iterations`.

## No-op a flag spento (R.P3)

Se `design_intelligence.enabled: false` (**default**) o `generator_tool: none`: il fe-dev
produce codice direttamente (comportamento v2.20 invariato). La skill
`llm-generator-separation-protocol` non viene invocata, `run-generator.sh` non viene
eseguito. L'assenza di skill/tool non produce ERROR di lint (opt-in totale, R.P3).

Cross-link: [ADR-069](../../../design_&_architecture/decisions/ADR-069.md),
[ADR-068](../../../design_&_architecture/decisions/ADR-068.md),
[US-075](../../../management/kanban/EP-019-design-intelligence-layer/US-075-llm-generator-separation-opt-in-pipeline-fe-dev/US-075.md).
