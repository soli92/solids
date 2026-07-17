# Skill: Art Director Coordination Protocol

> Adapter Cursor della skill `art-director-coordination-protocol` definita in PATTERN.md. Riferimenti agent → `.cursor/rules/<name>.mdc`; skill → `.cursor/skills/<name>/SKILL.md`.

# Protocollo Art-Director Coordination — DSL intermedia e coordinamento tema centralizzato

Skill procedurale a 5 fasi per il coordinamento del tema (EP-019, [[art-director-coordination]]):
l'art-director centralizzato produce una **DSL intermedia** con token vincolanti **prima** che
i generatori di componenti inizino a produrre, garantendo coerenza stilistica per costruzione,
non per speranza. È la skill che formalizza il pattern PrototypeFlow nella factory.

Eseguita dall'agente **`ui-designer`** come **step pre-generazione** dentro
`ux-ui-design-protocol` (gate condizionale, ADR-068 §B): si interpone prima del Step 3
(produzione deliverable), non lo sostituisce. A `design_intelligence.enabled: false` (default)
il gate non si attiva — il flusso EP-008 è identico a v2.20 (no-op totale, R.P3).

**Regola R.D1** (ADR-068 §C + ADR-071): l'art-director è il **single-writer** del tema.
Il fe-dev e i generatori sono **read-only** sul tema. La DSL (`art_director_spec`) è
l'**unico canale autorizzato** tra art-director e fe-dev per le istruzioni stilistiche —
nessun canale laterale, nessuno stile inline al di fuori della DSL. Bypass = violazione R.D1.

Riferimenti: [`ADR-068`](../../design_&_architecture/decisions/ADR-068.md) (forma skill,
single-writer, contratto DSL, no-op), [`ADR-071`](../../design_&_architecture/decisions/ADR-071.md)
(schema config `design_intelligence:`, R.D1 in PATTERN §24).
Wiki: [[art-director-coordination]], [[llm-generator-separation]].

[^src: management/kanban/EP-019-design-intelligence-layer/US-073-skill-art-director-coordination-protocol/US-073.md §Business Rules]
[^src: design_&_architecture/decisions/ADR-068.md §Decisione]

---

## Costanti

```
REPORTS_DIR          = "code_quality/reports"
ART_DIRECTOR_SPEC_MD = "<REPORTS_DIR>/<TSK-id>-art-director-spec.md"
ART_DIRECTOR_SPEC_JSON = "<REPORTS_DIR>/<TSK-id>-art-director-spec.json"
DS_CONFIG_KEY        = "factory.config.yaml.ux_ui.design_system_path"
MASTER_GATE          = "factory.config.yaml.design_intelligence.enabled"
```

---

## Fase 1 — Bootstrap

**Input atteso**: `TSK-id` (o richiesta di design con scope UX/UI), `factory.config.yaml`.

**Azione**:

1. Leggere `factory.config.yaml.design_intelligence.enabled`.
   - Se `false` (default) → **ABORT** no-op dichiarato. Log a chat:
     «Art-director coordination disabilitata — abilitare con
     `design_intelligence.enabled: true` (opt-in, EP-019).»
     Il flusso `ux-ui-design-protocol` continua al Step 2 standard (EP-008, R.P3).
   - Se `true` → procedere.

2. Verificare `factory.config.yaml.ux_ui.enabled: true`.
   - Se `false` → ABORT. Log: «`ux_ui.enabled: false` — design capability non attiva.»

3. Risolvere il **TSK-id** di riferimento (necessario per il path del side-channel).
   - Se invocata senza TSK-id esplicito: usare il TSK attivo corrente o generare slug da data
     `adhoc-<YYYYMMDD>` come fallback (con WARNING dichiarato).

4. Verificare esistenza del percorso `ux_ui.design_system_path` (se valorizzato).
   - Se il path non esiste o non è leggibile → **registrare come constraint mancante** (non ABORT:
     la Fase 2 gestisce la cascata DS).

**Output**: `{enabled: true, tsk_id, ds_path_status: "found|missing|not_configured", warnings[]}`.

**Criterio di completamento**: gate `design_intelligence.enabled` passato; TSK-id risolto;
status DS registrato.

---

## Fase 2 — Analisi tema

**Input**: output Fase 1 (`ds_path_status`, `tsk_id`), brief del task (scope UX/UI corrente).

**Azione** — estrarre i token del tema esistente con la **cascata a 3 livelli** (parallela ad
ADR-018 di `ux-ui-design-protocol`, Step 2):

1. **Design System ufficiale** — se `ds_path_status: found`: leggere `design_system_path`
   (JSON/YAML/Tailwind config). Estrarre: `colors`, `typography`, `spacing`, `elevation`,
   `component_patterns`. Questi sono i token **vincolanti hard** — i generatori non possono
   deviare.

2. **Token estratti** — se non c'è DS canonico ma esiste codice/CSS/Figma analizzabile:
   estrarre token osservabili dalla codebase (pattern analogo a Step 2 di `ux-ui-design-protocol`).
   Questi diventano token vincolanti **soft** (documentati come `extracted`, non `official`).

3. **Default ragionevoli** — in assenza di entrambi: applicare default conservativi documentati
   (ADR-018). Registrare tutto come assunzione esplicita nella Fase 5 (via
   `ux-ui-design-protocol` Step 5 a valle).

**Output**: `{ds_level: "official|extracted|defaults", tokens: {colors, typography, spacing, elevation, component_patterns}, constraints[]}`.

**Criterio di completamento**: livello di cascata dichiarato; token base estratti o defaults
documentati; constraint identificati.

---

## Fase 3 — Produzione DSL (`art_director_spec`)

**Input**: tokens e constraints (Fase 2) + scope UX/UI del task corrente.

**Azione** — produrre la **DSL intermedia** con almeno le 5 sezioni obbligatorie:

### Struttura `art_director_spec` (schema autoritativo)

```yaml
art_director_spec:
  version: "1.0"
  tsk_id: "<TSK-id>"
  ds_level: "official|extracted|defaults"  # livello cascata usato
  generated_at: "<ISO-8601>"

  colors:
    primary: "<hex|var>"
    secondary: "<hex|var>"
    background: "<hex|var>"
    surface: "<hex|var>"
    text_primary: "<hex|var>"
    text_secondary: "<hex|var>"
    error: "<hex|var>"
    warning: "<hex|var>"
    success: "<hex|var>"
    # token aggiuntivi specifici al task, se presenti nel DS

  typography:
    font_family_base: "<font-stack>"
    font_family_heading: "<font-stack>"
    scale:            # heading → body → caption (almeno 3 livelli)
      h1: {size, weight, line_height}
      h2: {size, weight, line_height}
      body: {size, weight, line_height}
      caption: {size, weight, line_height}

  spacing:
    unit: "<px|rem>"  # unità base (es. 4px, 0.25rem)
    scale: [0, 1, 2, 3, 4, 6, 8, 12, 16]  # moltiplicatori unità base
    component_padding: {xs, sm, md, lg}

  hierarchy:
    elevation:        # z-index semantici, NON numerici liberi
      base: 0
      raised: 1
      overlay: 2
      modal: 3
    visual_weight:    # dichiarazione esplicita del peso visivo
      primary_action: "high"
      secondary_action: "medium"
      tertiary_action: "low"

  component_variants:
    # per ogni componente nello scope UX/UI corrente:
    # <component_name>:
    #   variants: [default, hover, focus, disabled, active]
    #   size_variants: [sm, md, lg]  # se il DS li prevede
    #   allowed_overrides: []  # lista esplicita di proprietà overridabili dal fe-dev
    #   forbidden_overrides: []  # proprietà che il fe-dev NON può modificare (R.D1)
    # Esempio:
    # button:
    #   variants: [default, hover, focus, disabled]
    #   size_variants: [sm, md, lg]
    #   allowed_overrides: [label, icon, size_variant]
    #   forbidden_overrides: [color, border_radius, font_family]

  constraints:
    - "<constraint testuale — es. 'border-radius sempre da DS, mai inline'>"
    # lista di vincoli stilistici aggiuntivi non catturati dai token sopra

  rationale:
    - "<scelta non ovvia → motivo>"
    # ogni deviazione dal DS o scelta discrezionale richiede rationale esplicito
```

**Regola**: ogni sezione obbligatoria deve essere valorizzata. Se un token non è determinabile
dal DS → usare il valore di default e dichiararlo in `rationale` + `constraints`.

**Regola R.D1** — `forbidden_overrides` per ogni componente è la lista delle proprietà che
il fe-dev **non può modificare** fuori dalla DSL. L'assenza di voce in `forbidden_overrides`
**non autorizza** override impliciti: il fe-dev può overridare **solo** ciò che è in
`allowed_overrides`.

**Output**: `art_director_spec` YAML/JSON completo nelle 5 sezioni.

**Criterio di completamento**: tutte e 5 le sezioni (`colors`, `typography`, `spacing`,
`hierarchy`, `component_variants`) valorizzate; `rationale` e `constraints` presenti (anche
se `[]` dichiarati esplicitamente); R.D1 enforced via `forbidden_overrides`.

---

## Fase 4 — Validazione vs Design System

**Input**: `art_director_spec` (Fase 3) + DS letto in Fase 2.

**Azione** — validare la DSL prodotta contro il DS dichiarato:

1. **Token check**: ogni valore in `colors`, `typography`, `spacing` è tracciabile al DS?
   - Se sì → `validated: true`.
   - Se è un token estratto (livello 2) → `validated: "extracted"`, aggiungere a `constraints`.
   - Se è un default (livello 3) → `validated: "default"`, aggiungere a `rationale`.

2. **Component variants check**: i `component_variants` rispettano i pattern noti del DS?
   - Componenti non previsti nel DS → dichiarare come `new_component: true` (richiedono
     rationale esplicito).

3. **Vincoli contraddittori**: nessun token in `component_variants.allowed_overrides` deve
   essere contemporaneamente in `forbidden_overrides`.

4. **Severity**:
   - HARD_FAIL: token non tracciabile né al DS né ai default → **la skill si ferma**,
     restituisce `validation_status: fail` con lista degli item non risolti. Non procedere
     alla Fase 5.
   - WARN: token estratto o default — continua ma registra in `constraints`.

**Output**: `{validation_status: "pass|warn|fail", findings[], art_director_spec_validated}`.

**Criterio di completamento**: validation_status `pass` o `warn` → si procede alla Fase 5.
`fail` → STOP, iterare sulla Fase 3 (loop max **2 iterazioni** interne, poi gate umano).

---

## Fase 5 — Handoff al generatore

**Input**: `art_director_spec_validated` (Fase 4).

**Azione**:

1. **Scrivere la DSL nel side-channel** (ADR-068 §D, ADR-020 §E):
   - `code_quality/reports/<TSK-id>-art-director-spec.json` — versione machine-readable
     (input per generatori deterministici Plop/Yeoman, [[llm-generator-separation]]).
   - `code_quality/reports/<TSK-id>-art-director-spec.md` — versione human-readable
     candidata a review (tabella token + vincoli + rationale).
   - Entrambi i file sono **single-shot** (overwritten su ridesign); versioning via git.

2. **Registrare il path** nei metadati di output:
   - `art_director_spec_path: code_quality/reports/<TSK-id>-art-director-spec.{json,md}`
   - Questo path è l'input che il fe-dev e i generatori consumano. **Non passare la DSL
     inline come testo**: il path è il canale.

3. **Dichiarare il confine R.D1** nel summary di handoff:
   ```
   ART-DIRECTOR SPEC PRODOTTA — R.D1 ATTIVO
   Path: code_quality/reports/<TSK-id>-art-director-spec.{json,md}
   Art-director: SINGLE-WRITER (tema)
   Fe-dev: READ-ONLY (consuma DSL via path, nessuna istruzione stilistica inline)
   Canale autorizzato: SOLO via art_director_spec_path
   ```

4. **Restituire il controllo** a `ux-ui-design-protocol` (Step successivo: design-rationale
   gate → produzione deliverable). Il deliverable sarà prodotto **vincolato** dalla DSL:
   ogni scelta stilistica del deliverable si esprime **rispetto** al tema prodotto qui.

**Output**: `{art_director_spec_path, validation_status, handoff_summary}`.

**Criterio di completamento**: entrambi i file (JSON + MD) scritti nel side-channel; path
registrato; summary R.D1 dichiarato; controllo restituito a `ux-ui-design-protocol`.

---

## Output schema della skill

```json
{
  "skill": "art-director-coordination-protocol",
  "tsk_id": "<TSK-id>",
  "status": "pass|warn|fail|noop",
  "art_director_spec_path": "code_quality/reports/<TSK-id>-art-director-spec.{json,md}",
  "ds_level": "official|extracted|defaults",
  "validation_status": "pass|warn|fail",
  "r_d1_enforced": true,
  "findings": [],
  "warnings": []
}
```

A `design_intelligence.enabled: false` → `{"status": "noop", "reason": "design_intelligence.enabled: false"}`.

---

## Vincoli enforced (R.D1)

1. **Art-director SINGLE-WRITER sul tema** — solo questa skill produce/modifica i token del
   tema vincolante. Nessun agente esterno modifica `art_director_spec` dopo la produzione.
2. **Fe-dev READ-ONLY sul tema** — il fe-dev consuma la DSL tramite path. Non emette
   istruzioni di stile fuori dalla DSL. Non ha `allowed_overrides` impliciti.
3. **DSL unico canale stilistico** — nessun canale laterale, nessuno stile inline.
   Bypass = violazione R.D1 (documentata in PATTERN §24, ADR-071).
4. **No auto-eval** — la DSL prodotta non è valutata dalla stessa istanza art-director:
   la validazione (Fase 4) è strutturale, non soggettiva. La critica sull'output assemblato
   è responsabilità di `ux-ui-reviewer` + `visual-oracle` ([[critic-judge-agent]]).

---

## Pattern

- Istanza di [[art-director-coordination]] (pattern PrototypeFlow): coordinamento centralizzato
  tema, generatori read-only, DSL come unico canale stilistico.
- Complementare a [[llm-generator-separation]]: la DSL prodotta qui è l'input parametrico
  dei generatori deterministici (Plop/Yeoman) nella Fase 3 del pattern.
- Side-channel riusato da ADR-020 §E: stesso `code_quality/reports/` path degli spec UX/UI.
- PATTERN.md §24 — R.D1 (no bypass canale DSL art-director).

[^src: design_&_architecture/decisions/ADR-068.md §Decisione §C §D §E]
[^src: design_&_architecture/decisions/ADR-071.md §R.D1]
[^src: management/kanban/EP-019-design-intelligence-layer/US-073-skill-art-director-coordination-protocol/US-073.md §Acceptance Criteria]
