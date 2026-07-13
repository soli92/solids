# Skill: Llm Generator Separation Protocol

> Adapter Cursor della skill `llm-generator-separation-protocol` definita in PATTERN.md. Riferimenti agent → `.cursor/rules/<name>.mdc`; skill → `.cursor/skills/<name>/SKILL.md`.

# Protocollo LLM-Generator Separation — spec parametrica → generatore deterministico

Skill procedurale a 5 fasi per il pattern [[llm-generator-separation]] (EP-019): il fe-dev
(LLM) produce la **spec parametrica** e delega l'espansione del boilerplate al generatore
deterministico (Plop.js / Yeoman), che garantisce coerenza strutturale per costruzione.
Budget token dello scaffolding: ~zero (il generatore non ragiona).

Invocata come **sub-step condizionale della Fase 4 Develop FE** in `dev-protocol`, gated
dall'agente `fe-dev` (ADR-069 §B): non è un livello DAG separato, è parte atomica del
Develop FE.

**Regola**: il generatore **non decide mai** — ogni decisione di design resta all'LLM.
Il branch fuori-template + la nuova-spec su reject del Critic/Judge preservano questa
separazione nel ciclo di refinement (ADR-069 §D §E).

Riferimenti: [`ADR-069`](../../design_&_architecture/decisions/ADR-069.md) (confine
responsabilità, opzione b, fuori-template, no-op), [`ADR-068`](../../design_&_architecture/decisions/ADR-068.md)
(tema read-only R.D1, theme_tokens dall'art_director_spec).
Wiki: [[llm-generator-separation]], [[art-director-coordination]].

[^src: management/kanban/EP-019-design-intelligence-layer/US-075-llm-generator-separation-opt-in-pipeline-fe-dev/US-075.md §Business Rules]
[^src: design_&_architecture/decisions/ADR-069.md §B §D §E §F]

---

## Costanti

```
REPORTS_DIR          = "code_quality/reports"
GENERATOR_OUTPUT_DIR = "<code_path>/<component_name>/"  # risolto da --cwd
RUNNER_PATH          = "tools/visual/run-generator.sh"
```

---

## Fase 1 — Bootstrap

**Input atteso**: `TSK-id`, `factory.config.yaml`, spec parametrica (da fe-dev).

**Azione**:

1. Leggere `factory.config.yaml.design_intelligence.enabled`.
   - Se `false` → **ABORT no-op**. Log: «LLM-Generator Separation disabilitata —
     `design_intelligence.enabled: false`. Fe-dev produce codice direttamente (v2.20).»

2. Leggere `factory.config.yaml.design_intelligence.generator_tool`.
   - Se `none` (default) → **ABORT no-op**. Log: «`generator_tool: none` — nessun
     generatore configurato. Fe-dev produce codice direttamente.»
   - Se `plop` o `yeoman` → procedere.

3. Verificare che il `TSK-id` sia risolvibile (frontmatter `code_path` o entry `code_paths`).
   - Se non risolto → ABORT con WARNING «code_path non risolvibile per TSK-id».

**Output**: `{enabled: true, generator_tool: "plop|yeoman", tsk_id, code_path_resolved}`.

**Criterio di completamento**: gate passato; `generator_tool` risolto.

---

## Fase 2 — Receive spec

**Input**: spec parametrica YAML dal fe-dev.

**Azione** — validare la spec parametrica. Campi **obbligatori** (ADR-069 §A):

```yaml
# spec parametrica obbligatoria (prodotta dal fe-dev)
name: "<ComponentName>"         # nome del componente — PascalCase
type: "<atom|molecule|organism|template>"  # livello design system
props:
  - name: "<prop_name>"
    type: "<TypeScript type>"
    required: true|false
    default: "<valore default, se presente>"
variants:                        # lista varianti dal design system
  - "<default>"
  - "<hover>"
  - "<disabled>"
  # ...
theme_tokens:                    # derivati dall'art_director_spec (ADR-068 §D)
  color_primary: "<token>"
  color_text: "<token>"
  spacing_unit: "<token>"
  font_family: "<token>"
  # altri token rilevanti per il componente
out_of_template: false           # true = caso fuori-template (Fase 5 branch alternativo)
```

**Validazione**:
- Campo mancante tra i 5 obbligatori (`name`, `type`, `props`, `variants`, `theme_tokens`) →
  **ABORT fail-loud**. Log canonico: «spec parametrica incompleta: campo `<campo>` mancante.
  Fe-dev deve produrre spec completa prima di invocare questa skill.»
- `out_of_template: true` → non validare il resto: procedere direttamente alla **Fase 5
  branch fuori-template** (saltare Fase 3 e Fase 4).

**Output**: `{spec_valid: true, spec, out_of_template: false|true}`.

**Criterio di completamento**: spec validata o ramo fuori-template identificato.

---

## Fase 3 — Resolve generator

**Input**: `generator_tool` (Fase 1) + `code_path_resolved` (Fase 1).

**Azione** — risolvere il binario del generatore nel `code_path` del progetto target:

1. **Mappa `generator_tool` → binario**:
   - `plop` → cerca `./node_modules/.bin/plop` o `plop` nel `PATH` della CWD target.
   - `yeoman` → cerca `yo` nel `PATH` della CWD target.

2. **Fail-loud su binario non trovato**: se il binario non è risolvibile →
   **ABORT**. Log canonico:
   «generatore `<nome>` non trovato nella CWD `<code_path>`;
   installare Plop.js (`npm install --save-dev plop`) o Yeoman (`npm install -g yo`)
   nel package target prima di abilitare `design_intelligence.generator_tool: <nome>`.»

3. **Verifica template**: controllare che il template del generatore esista nella CWD:
   - Plop: `plopfile.js` o `plopfile.mjs` nella radice del `code_path`.
   - Yeoman: generator package dichiarato in `package.json` o risolto via `yo`.
   - Template assente → **ABORT**. Log canonico:
     «template `<path>` non trovato; verificare che il template sia versionato nel design
     system (`code_path`). I template sono artefatti del progetto, non generati a runtime
     (ADR-069 §C).»

**Output**: `{binary_path, template_path, generator_tool}`.

**Criterio di completamento**: binario e template trovati; fail-loud emesso se assenti.

---

## Fase 4 — Invoke tool

**Input**: `binary_path`, `template_path`, `spec` (Fase 2), `code_path_resolved`.

**Azione** — invocare `tools/visual/run-generator.sh` con gli argomenti canonici:

```bash
bash tools/visual/run-generator.sh \
  --generator "<plop|yeoman>" \
  --spec "<path-spec-yaml-temporaneo>" \
  --cwd "<code_path_resolved>"
```

**Prima dell'invocazione**: scrivere la spec parametrica (Fase 2) su file temporaneo YAML
in `code_quality/reports/<TSK-id>-generator-spec.yaml` (input leggibile dal tool Bash).

**Output atteso del tool**:
- `exit 0` + lista di file generati su stdout (uno per riga) → successo.
- `exit 1` + messaggio canonico → fail-loud (ripropagare come ABORT con il messaggio del tool).

**Timeout**: se il tool non completa entro 60s → ABORT con WARNING «generatore timeout».

**Output**: `{generated_files[], exit_code, tool_output}`.

**Criterio di completamento**: `exit 0`; lista file generati non vuota.

---

## Fase 5 — Collect output

**Input**: `generated_files[]` (Fase 4) o ramo fuori-template (Fase 2).

### Branch normale (generatore invocato)

**Azione**:

1. Registrare la lista dei file generati come artefatto:
   ```yaml
   generator_output:
     tsk_id: "<TSK-id>"
     generator_tool: "<plop|yeoman>"
     generated_files:
       - "<code_path>/src/components/<ComponentName>/<ComponentName>.tsx"
       - "<code_path>/src/components/<ComponentName>/<ComponentName>.test.tsx"
       - "<code_path>/src/components/<ComponentName>/index.ts"
       # ... (uno per riga, dipende dal template)
     spec_path: "code_quality/reports/<TSK-id>-generator-spec.yaml"
   ```

2. Restituire il path/elenco al fe-dev. Il fe-dev **integra SOLO la logica custom** nei
   file generati (business logic, gestori eventi specifici, edge case non template).

3. Cleanup del file spec temporaneo (opzionale, il file è side-channel leggibile).

**Output**: `{status: "pass", generator_output}`.

### Branch fuori-template (generatore NON invocato)

**Azione** (ADR-069 §D):

1. Log dichiarativo:
   ```
   FUORI-TEMPLATE — generatore non invocato.
   Motivo: spec con nota "fuori-template" ricevuta dal fe-dev.
   Il fe-dev procede a sviluppo diretto del componente.
   ```

2. Restituire al fe-dev:
   ```yaml
   generator_output:
     status: "out_of_template"
     note: "componente fuori-template — sviluppo diretto fe-dev, nessun boilerplate generato"
     spec_path: "code_quality/reports/<TSK-id>-generator-spec.yaml"
   ```

**Il fe-dev riceve questa indicazione e sviluppa il componente da zero** (o da un riferimento
custom documentato nella spec). Il generatore non prende decisioni di design nel fallback.

**Output**: `{status: "out_of_template", generator_output}`.

---

## Output schema della skill

```json
{
  "skill": "llm-generator-separation-protocol",
  "tsk_id": "<TSK-id>",
  "status": "pass|out_of_template|fail|noop",
  "generator_tool": "plop|yeoman|none",
  "generator_output": {
    "generated_files": [],
    "spec_path": "code_quality/reports/<TSK-id>-generator-spec.yaml"
  }
}
```

A `design_intelligence.enabled: false` o `generator_tool: none` →
`{"status": "noop", "reason": "<motivo>"}`.

---

## Vincoli enforced

1. **Il generatore non decide mai** — ogni decisione di design (quando invocare, quale
   componente creare, quali varianti) resta al fe-dev (LLM). Il generatore espande
   meccanicamente la spec fornita (ADR-069 §D).
2. **Theme_tokens read-only** — il fe-dev li copia dall'`art_director_spec`, non li inventa.
   La skill non sovrascrive i token del tema (R.D1, ADR-068 §C).
3. **Template versionati** — i template (`plopfile.js`, generator Yeoman) sono artefatti del
   progetto, non generati a runtime. Non creare template al volo.
4. **Fail-loud su prerequisito mancante** — binario assente → exit, no-op silenzioso mai
   (ADR-069 §B, ADR-008).

---

## Pattern

- Istanza di [[llm-generator-separation]]: LLM decide (spec), deterministico espande.
- Complementare a [[art-director-coordination]]: la DSL art-director è il prerequisito dei
  `theme_tokens` della spec (ADR-068 §D → ADR-069 §A).
- Sub-step atomico del Develop FE (`dev-protocol`), non livello DAG separato (ADR-069 §B
  rationale: contrasto con ADR-066 che *aggiunge* dominio perché l'oracolo è gate separato).

[^src: design_&_architecture/decisions/ADR-069.md §B §C §D §E §F]
[^src: management/kanban/EP-019-design-intelligence-layer/US-075-llm-generator-separation-opt-in-pipeline-fe-dev/TSK-175.md §Technical Specs §A]
