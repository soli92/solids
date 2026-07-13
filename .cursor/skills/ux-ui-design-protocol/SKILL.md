# Skill: UX/UI Design Protocol

> Adapter Cursor della skill `ux-ui-design-protocol` definita in PATTERN.md.
>
> Metadata originale — name: ux-ui-design-protocol. Descrizione: skill procedurale design UX/UI — 6 step (Brief → DS → Deliverable → A11y by Design → Assunzioni → Handoff Review). No auto-eval: ogni output va a ux-ui-review-protocol. Capability opt-in v2.18, PATTERN §3 UX/UI Design.

**Protocollo UX/UI Design — produzione deliverable in 6 step + handoff obbligatorio**

Skill procedurale fondante della sotto-capability **Design** di EP-008
([[ux-ui-review-design-capability]]): incapsula la conoscenza operativa per produrre
deliverable di design UX/UI (wireframe, component spec, user flow, copy) ancorati al design
system, con **accessibilità by design** e **handoff obbligatorio** alla Review (no
auto-eval). È caricabile al bisogno dall'agente `ui-designer` (US-030, gated da
`ux_ui.agents.designer: true`) — istanza del pattern [[thin-agents-fat-skills-refactor]]: la
conoscenza vive nella skill (fat), l'agente resta thin e non duplica la procedura.

Questa skill è il **lato optimizer/producer** del pattern [[evaluator-optimizer]] applicato
al dominio UX/UI: il designer produce, il `ux-ui-reviewer` valuta. Il loop è separato e
bounded — **mai auto-valutazione**.

È un'**operazione opzionale** (PATTERN.md §3 «UX/UI Design»), attiva solo con la capability
EP-008 abilitata (`factory.config.yaml.ux_ui.enabled: true`). A capability spenta la skill è
no-op: assenza del file non produce ERROR di lint (R.P3, opt-in totale).

Riferimenti: ADR-020 (schema EP-008 consolidato — handoff designer → fe-dev via frontmatter
`ui_design_spec:`, config block `ux_ui:`, deliverable single-shot), ADR-017 (riuso infra
screenshot + `render_component` come **snippet inline** in questa skill con fallback
testuale, NON skill autonoma), ADR-018 (cascata default Design System). Runbook narrativo
source-of-truth: [`wiki/runbooks/ux-ui-design-runbook.md`](../../wiki/runbooks/ux-ui-design-runbook.md).
Wiki: [[ux-ui-review-design-capability]], [[ux-ui-rubric-anti-subjectivity]].

[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-029-skill-ux-ui-design-protocol/US-029.md §Business Rules]
[^src: design_&_architecture/decisions/ADR-020.md §Decisione]
[^src: design_&_architecture/decisions/ADR-017.md §Decisione]

---

## Step 1 — Brief (obiettivo + contesto + vincoli + assunzioni)

**Input**: la richiesta di design (brief libero, eventualmente `--tsk=<id>` o `--type=<...>`).

**Azione** — prima di produrre qualsiasi artefatto, chiarire **4 elementi**:

1. **Obiettivo utente** — cosa deve poter fare l'utente al termine?
2. **Contesto** — da dove arriva l'utente? Stato cognitivo (primo accesso vs esperto)?
3. **Vincoli** — piattaforma (web/mobile), viewport, accessibilità, pattern del design system.
4. **Assunzioni** — qualsiasi ipotesi non confermata deve essere esplicitata da subito.

**Regola — chiarimento prima di procedere**: se il contesto **non è sufficiente** a coprire
i 4 elementi → **chiedere chiarimento PRIMA di procedere**. Niente design su assunzioni
errate: un design costruito su presupposti sbagliati genera debito di revisione (loop
inutili con il reviewer).

**Output**: `{objective, context, constraints, assumptions[]}`.

**Criterio di completamento**: i 4 elementi sono valorizzati, oppure è stata posta una
domanda di chiarimento bloccante e si è in attesa di risposta.

---

## Step 2 — Ancora al Design System (cascata 3 livelli)

**Input**: i `constraints` dello Step 1.

**Azione** — risolvere il design system di riferimento con la **cascata a 3 livelli**
(identica a US-028 Step 2 / ADR-018):

1. **DS ufficiale** — `factory.config.yaml.ux_ui.design_system_path` (JSON/YAML/Tailwind
   config). Se valorizzato e leggibile → fonte primaria di token, componenti, pattern.
2. **Token estratti** — se non c'è DS canonico ma esiste codice/CSS/Figma: estrarre i token
   osservabili (delega a [design-tokens-extraction](mdc:.cursor/skills/design-tokens-extraction/SKILL.md), ADR-017) come secondo livello.
3. **Default ragionevoli** — in assenza di entrambi: default conservativi documentati
   (ADR-018), **dichiarati come assunzioni** nello Step 5.

**Regola**: **preferire pattern noti del DS a invenzioni ex-novo**. La coerenza con il DS
esistente è una dimensione valutabile dalla review; un'invenzione richiede rationale
esplicito (Step 3).

**Output**: `{ds_source: "official|extracted|defaults", tokens, known_patterns[]}`.

**Criterio di completamento**: il livello di cascata è risolto e dichiarato; i default
eventualmente usati sono tracciati per lo Step 5.

---

## Step 2-bis — Gate pre-generazione Design Intelligence (condizionale, opt-in EP-019)

**Trigger**: eseguire questo step **SOLO** se `factory.config.yaml.design_intelligence.enabled: true`.
A flag spento (default): **SKIP** — procedere direttamente allo Step 3 (no-op totale, R.P3).

**Ordine obbligatorio** (ADR-068 §B): `art-director (tema/DSL) → design-rationale gate (reasoning-first) → Step 3`.

### Sub-step A — Art-Director Coordination

**Azione**: invocare la skill [art-director-coordination-protocol](mdc:.cursor/skills/art-director-coordination-protocol/SKILL.md) come step pre-generazione.

La skill produrrà `art_director_spec` (token di colore, tipografia, spaziatura, gerarchia,
varianti ammesse) in:
`code_quality/reports/<TSK-id>-art-director-spec.{json,md}`

**Se la skill ritorna `status: fail`** → STOP. Non procedere alla produzione del deliverable
(tema non risolto contro il DS — blocco strutturale).

**Se la skill ritorna `status: pass|warn`** → registrare il path come `art_director_spec_path`
e procedere al Sub-step B.

**Output**: `{art_director_spec_path, ds_level, r_d1_enforced: true}`.

### Sub-step B — Design Rationale Gate (reasoning-first)

**Azione** — prima di produrre il deliverable, dichiarare un **`design_rationale` strutturato**
per ogni scelta non ovvia. Il rationale si esprime **rispetto** al tema vincolante prodotto
dall'art-director (Sub-step A) — non in astratto.

**Schema `design_rationale`** (obbligatorio se EP-019 attivo, aggiunto al deliverable):

```yaml
design_rationale:
  decision: "<scelta adottata per questo deliverable — es. 'componente card, non tabella'>"
  alternatives_considered:
    - option: "<alternativa 1>"
      reason_rejected: "<perché scartata>"
  rationale: "<perché questa scelta rispetto al tema art-director e ai vincoli DS>"
  constraints_applied:
    - "<constraint del tema che influenza direttamente questa scelta>"
  consequences:
    resolution_velocity_impact: >
      "<impatto sull'intention economy: quanti step richiede all'utente?
      Elimina elementi distrattivi? Preferisce chiarezza su novità visiva?
      (input per asse Intention Economy in ux-ui-review-protocol, ADR-070 §E)>"
```

**Regola reasoning-first**: il deliverable (Step 3) **non inizia** finché `design_rationale`
non è completo. Produrre il rationale prima del codice/wireframe, non a posteriori.

**Output**: `design_rationale` strutturato (allegato al deliverable dello Step 3).

**Criterio di completamento Sub-step B**: `design_rationale` prodotto con tutti i campi obbligatori;
`consequences.resolution_velocity_impact` dichiarato (anche come `"no impact identified"` se
non applicabile — non ometterlo).

---

## Step 3 — Produci il deliverable (4 tipi)

**Input**: brief (Step 1) + ancoraggio DS (Step 2).

**Azione** — produrre **uno** dei 4 tipi di deliverable:

| Tipo | Quando | Forma |
|---|---|---|
| `wireframe` | Prototipazione rapida, validazione struttura | Sketch testuale/ASCII + immagine opzionale (vedi `render_component`) |
| `component_spec` | Componente riusabile dettagliato | JSON/YAML strutturato + annotazioni |
| `user_flow` | Mappatura flusso multi-passo | Diagramma passo-passo + decision points |
| `copy` | Microcopy (label, errori, empty state, CTA) | Lista per elemento con contesto |

**Regola — rationale esplicito**: per ogni scelta **non ovvia** → `rationale[]` esplicito
(«perché questa soluzione e non un'alternativa?»). Il rationale rende il design **difendibile
in review** e riduce le iterazioni.

### `render_component` — snippet inline (ADR-017, fallback testuale)

`render_component` **NON è una skill autonoma**: è uno **snippet inline** di questa skill,
opzionale e degradato (ADR-017 §Decisione punto 8). Serve a produrre un'**anteprima** del
deliverable per il consumer a valle (il `fe-dev` che riceve `ui_design_spec`).

```
render_component(deliverable):
    if host ha generazione immagine disponibile:
        → produce preview grafica (PNG) del wireframe/component_spec
        → opzionale: cattura via screenshot-capture-protocol se esiste un harness
    else:                                  # FALLBACK (caso di default)
        → output descrittivo testuale STRUTTURATO:
            - struttura/layout (ASCII o bullet gerarchici)
            - elementi interattivi + stati (default/hover/focus/disabled)
            - token applicati (colore, spaziatura, tipografia) per elemento
            - note a11y inline (vedi Step 4)
```

(La cattura opzionale delega a [screenshot-capture-protocol](mdc:.cursor/skills/screenshot-capture-protocol/SKILL.md).)

Il fallback testuale **non è un degrado d'errore**: è l'output atteso quando l'host non ha
generazione immagine (tool grafico reale out-of-scope v2.18, ADR-017). Il deliverable resta
valido e consumabile dal `fe-dev`.

**Output**: `artifacts[]` (il deliverable nel formato del tipo scelto) + `rationale[]`.

**Criterio di completamento**: deliverable prodotto in una delle 4 forme; ogni scelta non
ovvia ha rationale; eventuale anteprima via `render_component` (o relativo fallback).

---

## Step 4 — A11y by Design (5 dimensioni)

**Input**: il deliverable dello Step 3.

**Azione** — includere l'accessibilità **dal wireframe**, non come post-processing.
Coprire le **5 dimensioni**:

1. **Focus visibile** — stato di focus visibile su ogni elemento interattivo.
2. **Label** — label su ogni input, icona, azione (non solo `placeholder`).
3. **Contrasto** — vs minimi WCAG 2.2 AA. Se non calcolabile in fase di design → **delegare a
   `run_a11y_scan` in review** (EP-007, ADR-014). Questa skill non dichiara mai conformità.
4. **Ordine navigazione da tastiera** — coerente con il flusso logico del deliverable.
5. **Empty state / error state** — previsti e comunicati in linguaggio chiaro.

**Output**: il deliverable arricchito con annotazioni a11y per le 5 dimensioni.

**Criterio di completamento**: tutte le 5 dimensioni indirizzate (o esplicitamente delegate
a `run_a11y_scan` in review per il contrasto non calcolabile).

---

## Step 5 — Assunzioni + Open Questions (obbligatori)

**Input**: assunzioni accumulate negli Step 1-4 (default DS, ipotesi di contesto, ecc.).

**Azione** — ogni deliverable include **esplicitamente** due liste:

- **`assumptions[]`** — ipotesi fatte per mancanza di contesto (es. default DS usati allo
  Step 2, viewport assunti, stato cognitivo dell'utente).
- **`open_questions[]`** — domande che richiedono input PM/stakeholder/ricerca utente.

**Regola**: **non procedere a iterazioni successive senza risposta alle domande bloccanti**
(debito di specifiche). Le `assumptions[]`/`open_questions[]` possono diventare ulteriori
`open_questions` nel TSK FE se non risolte (ADR-020 §A, workflow handoff punto 3).

**Output**: `assumptions[]` + `open_questions[]` (entrambe presenti, anche se vuote vanno
dichiarate esplicitamente come `[]`).

**Criterio di completamento**: entrambe le liste presenti nel deliverable; le domande
bloccanti sono marcate come tali.

---

## Step 6 — Handoff Review (OBBLIGATORIO, no auto-eval)

**Input**: il deliverable completo (Step 3-5).

**Azione** — il design **non si auto-valida**. Chiude con il passaggio strutturato alla
Review (US-028, [ux-ui-review-protocol](mdc:.cursor/skills/ux-ui-review-protocol/SKILL.md)):

```
ui-designer produce deliverable
  |
  v
ux-ui-reviewer riceve deliverable come input visivo
  |
  v
report review con findings + open_questions
  |
  v
ui-designer itera se necessario (loop bounded)
```

**Bounded loop**: il loop designer ↔ reviewer è bounded da
`factory.config.yaml.ux_ui.max_iterations` (default **3**, analogo a R.Q4 di CQRL). Oltre il
bound → gate umano.

**Separazione strutturale** (verbatim, US-029 / ADR-020 §H):

> Se sei l'agente `ui-designer`, NON puoi invocare `ux-ui-review-protocol` su tuo stesso
> output — devi delegare all'agente `ux-ui-reviewer`.

I due agenti sono **fisicamente distinti** (file separati, system prompt che dichiarano
"NON sei l'altro agente"). Questo enforce architetturalmente il no-auto-eval (ADR-020 §H).

**Handoff verso fe-dev** (ADR-020 §A): il deliverable viene scritto in
`code_quality/reports/<TSK-id>-uxui-design.{json,md}` (single-shot, overwritten su ridesign).
Il `ui-designer` **suggerisce** nel proprio output il path da allegare al TSK FE; il **TPM**
(single-writer) committa il frontmatter `ui_design_spec: <path>`. Il `fe-dev` legge
`ui_design_spec:` come input di specifica (analogo a `interaction_test_spec:`).

**Output**: deliverable consegnato alla Review (e suggerimento path per `ui_design_spec`).

> Il deliverable scritto in `code_quality/reports/<TSK-id>-uxui-design.{json,md}` deve
> includere il campo `generated_by` valorizzato con il nome canonico dell'agente/skill
> (ADR-020 §E, US-086). Questo campo consente al Check 4ac (EP-024) di verificare il
> vincolo no-auto-eval.

**Criterio di completamento**: il deliverable è stato passato a [ux-ui-review-protocol](mdc:.cursor/skills/ux-ui-review-protocol/SKILL.md) via
l'agente `ux-ui-reviewer` — **mai** auto-valutato dal designer.

---

## Output schema standard

Ogni deliverable Design segue lo schema verbatim (US-029 §Output standard, §4.4 del design):

```json
{
  "type": "ux_ui_design",
  "deliverable": "wireframe|component_spec|user_flow|copy",
  "artifacts": [],
  "rationale": [],
  "assumptions": [],
  "open_questions": [],
  "design_rationale": null,
  "generated_by": null
}
```

> `generated_by` (opzionale, backward-compat): nome canonico dell'agente o della skill
> che ha prodotto questo deliverable (es. `"ui-designer"`, `"fe-dev (skill ux-ui-design-protocol)"`).
> Valorizzare nello step di output (Step 6 — Handoff Review). Assenza → Check 4ac (EP-024)
> emette `skipped` (nessun WARNING, nessun false positive).

`design_rationale` è `null` a `design_intelligence.enabled: false`; valorizzato con lo schema
completo (Sub-step B) a `design_intelligence.enabled: true`. Mai omettere il campo quando EP-019
è attivo.

`art_director_spec_path` è aggiunto come campo opzionale del deliverable quando EP-019 è attivo:
`"art_director_spec_path": "code_quality/reports/<TSK-id>-art-director-spec.{json,md}"`.

[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-029-skill-ux-ui-design-protocol/US-029.md §Business Rules]

---

## Vincoli del designer (enforced)

1. **NON auto-valutare** — l'output va sempre in review prima di essere considerato "pronto"
   (Step 6, separazione strutturale).
2. **Preferire pattern noti del DS** — invenzioni ex-novo richiedono rationale esplicito
   (Step 2-3).
3. **Accessibilità by design** — non rimandare l'a11y alla review; progettarla dal wireframe
   (Step 4).
4. **Assunzioni esplicite** — mai produrre design su presupposti impliciti (Step 1, Step 5).

---

## Pattern

- Istanza di [[evaluator-optimizer]] applicato a UX/UI, **lato optimizer/producer**: il
  designer produce, il `ux-ui-reviewer` valuta. Handoff obbligatorio, loop bounded.
- Istanza di [[thin-agents-fat-skills-refactor]]: la procedura vive qui (fat skill), consumata
  dall'agente thin `ui-designer` (US-030) — nessuna duplicazione della procedura nel system
  prompt dell'agente.
- PATTERN.md §3 — operazione opzionale «UX/UI Design» (output deliverable + handoff
  obbligatorio a review, no auto-eval, bounded loop `ux_ui.max_iterations`).
- Anti-soggettività della review a valle: [[ux-ui-rubric-anti-subjectivity]] (ogni finding del
  reviewer cita un `rubric_ref`).

[^src: design_&_architecture/decisions/ADR-020.md §Rationale]
[^src: design_&_architecture/decisions/ADR-017.md §Rationale]
