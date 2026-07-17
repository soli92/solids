# Skill: Cost And Time Analytics

> Adapter Cursor della skill `cost-and-time-analytics` definita in PATTERN.md.

Metadata skill (originale):
```yaml
name: cost-and-time-analytics
description: Skill procedurale Task Analytics — 5 step (Scope → Lettura Eventi + resolution model_id → Calcolo Costi + Metriche Temporali → Colli di Bottiglia + Trend → Report Standard). Orchestra i tool analytics deterministici (no MCP). Capability opt-in EP-009, PATTERN §3 Cost/Time Report.
```

# Protocollo Cost & Time Analytics — analisi costi e tempi in 5 step

Skill procedurale fondante della capability Task Analytics — Measurement (EP-009): incapsula
la conoscenza operativa per orchestrare i tool deterministici di EP-009 e produrre un report
costi/tempi nello schema standard. È caricabile al bisogno da [orchestrator](mdc:.cursor/rules/orchestrator.mdc), [tpm](mdc:.cursor/rules/tpm.mdc),
`qa-dev` e [analytics-reporter](mdc:.cursor/rules/analytics-reporter.mdc) — istanza del pattern [[thin-agents-fat-skills-refactor]]:
la procedura vive nella skill (fat), i tool restano puri trasformatori deterministici e gli
agenti restano thin senza duplicare l'orchestrazione.

La skill **orchestra**, i tool **calcolano** (ADR-023 §B). Le formule di costo vivono nei
tool (`compute-agentic-cost.sh`, `compute-human-cost.sh`); la resolution `model_id`, il
mascheramento privacy, la composizione del report e la validation dello schema vivono qui.

È un'**operazione opzionale** (PATTERN.md §3 «Cost/Time Report»), attiva solo con la
capability EP-009 abilitata (`analytics.measurement.enabled: true`). A capability spenta la
skill è no-op: la sua assenza non produce ERROR di lint (R.P3 opt-in totale).

Tool orchestrati (Bash standalone in `tools/analytics/`, ADR-023 §A, no MCP):
`analyze-timeline.sh` (US-035), `compute-agentic-cost.sh` (US-034),
`compute-human-cost.sh` (US-034), `generate-report.sh` (US-037). Sorgente eventi:
`record-event.sh` (US-033, instrumentazione a monte).

Riferimenti: ADR-022 (schema `pricing.yaml`/`rates.yaml` + resolution `model_id` §D),
ADR-023 (registrazione tool §A + policy dati N>=5 §C + `actors_map` §D + `rate_basis`
trasparente §E), ADR-024 (output schema standard §A-D), ADR-027 §C (auto-detection chiusura
progetto). Wiki source-of-truth: [[task-analytics-cost-estimation-capability]].

[^src: management/kanban/EP-009-task-analytics-measurement/US-036-skill-cost-and-time-analytics/US-036.md §Business Rules]
[^src: design_&_architecture/decisions/ADR-022.md §D]
[^src: design_&_architecture/decisions/ADR-023.md §C]
[^src: design_&_architecture/decisions/ADR-024.md §A]

---

## Step 1 — Scope

**Input atteso**: richiesta del caller (es. «quanto è costato lo sprint v2.17?», «qual è il
collo di bottiglia del flusso FE?»).

**Azione** — definisci il perimetro dell'analisi con 4 elementi:

- `scope.project_id?` — singolo progetto vs cross-progetto (omesso = tutti).
- `scope.period?: {from, to}` — finestra temporale (default: ultimo sprint).
- `scope.actor_filter?` — `agent` | `human` | `both` (default `both`).
- `scope.audience` — `operativa | progetto | executive` (determina la forma del report
  finale e la policy di mascheramento, vedi US-037).

**Regola anti-inferenza**: se lo scope è ambiguo (es. solo «ultimo progetto» senza ID, o
periodo non determinabile) → **chiedere chiarimento prima di procedere, non inferire**.

**Tool invocato**: nessuno (passo cognitivo).

**Output prodotto**: oggetto `scope` completo + filtro derivato per `analyze-timeline.sh`.

**Criterio di completamento**: i 4 elementi di scope sono risolti (o esplicitamente
defaultati) e l'`audience` è uno dei 3 valori ammessi.

[^src: management/kanban/EP-009-task-analytics-measurement/US-036-skill-cost-and-time-analytics/US-036.md §Business Rules]

---

## Step 2 — Lettura Eventi + Resolution `model_id`

**Input atteso**: filtro derivato dallo Step 1.

**Tool invocato**: `analyze-timeline.sh` (US-035) sul filtro derivato dallo scope.

```
bash tools/analytics/analyze-timeline.sh \
     --filter '<scope-derived>' --output json
```

**Azione**:

- **STOP su event store vuoto** — se il filtro produce 0 eventi, fermarsi con messaggio
  azionabile (verbatim):

  > Event store vuoto per il filtro specificato. Suggerimenti: (a) ampliare il periodo,
  > (b) verificare che `record_task_event` sia attivo (US-033 / `tools/analytics/record-event.sh`).

  Senza eventi non si analizza: l'instrumentazione a monte è prerequisito (US-033).

- **Resolution `model_id`** (ADR-022 §D, single-source qui) — per ogni evento `e` con campo
  `e.model`:
  1. `norm = lowercase(e.model).replace('.', '-')` (normalizzazione canonica).
  2. lookup `pricing.yaml.models[].id == norm` **OR** `pricing.yaml.models[].aliases[*] == norm` **OR** `== e.model` raw.
  3. Nessun match → **fail-loud**: «Modello sconosciuto '{e.model}'. Aggiungere in
     `analytics/pricing.yaml` come canonical id o come alias. Vedi ADR-022.» — **mai**
     sostituire con un default silente.
  4. Sui match, scegli `pricing[i]` con `pricing[i].valid_from <= e.ts` AND
     (`i` ultimo OR `pricing[i+1].valid_from > e.ts`).
  5. Nessun `valid_from <= e.ts` → fail-loud: «Nessun pricing valido per modello '{id}' al
     timestamp {e.ts}. Estendere `pricing.yaml` con `valid_from` anteriore.»
  - **Cache in-memory** del mapping `(model_str, ts) → pricing_entry` per la durata della
    invocazione (no persistence; idempotente e deterministico per design).
  - Stesso pattern per gli umani: `actor_id` → `role_id` via `actors_map` (ADR-023 §D), poi
    `role_id` su `rates.yaml.roles[].id`/`aliases[]` time-based.

**Output prodotto**: metriche temporali grezze di `analyze-timeline` (`time`, `bottlenecks[]`,
`operational.trend[]`) + eventi arricchiti con `pricing_entry` risolto.

**Criterio di completamento**: ≥ 1 evento letto e ogni evento ha `pricing_entry`/`rate_entry`
risolto (o fail-loud esplicito su modello/ruolo sconosciuto).

[^src: design_&_architecture/decisions/ADR-022.md §D]

---

## Step 3 — Calcolo Costi + Metriche Temporali

**Input atteso**: eventi arricchiti dallo Step 2.

**Tool invocati** (in parallelo o sequenziale — decisione di scheduling intra-skill):

```
bash tools/analytics/compute-agentic-cost.sh \
     --events '<agent-events>' --pricing analytics/pricing.yaml --output json
bash tools/analytics/compute-human-cost.sh \
     --events '<human-events>' --rates analytics/rates.yaml --output json
```

- `compute-agentic-cost.sh` (US-034) → costo agentico aggregato + breakdown per modello e
  token kind.
- `compute-human-cost.sh` (US-034) → costo umano aggregato + breakdown per ruolo.
- Metriche temporali: già prodotte da `analyze-timeline.sh` allo Step 2.

**Azione** — calcola i derivati:
- `TCO = costo_agentico + costo_umano (+ overhead se applicabile)`.
- `split_human_pct = human / TCO`, `split_agent_pct = agentic / TCO`.

**Mascheramento privacy N>=5** (ADR-023 §C) — applicato **prima** di passare al tool / prima
dell'emissione, per ogni cella di aggregazione `c` con dimension `actor_id`:
```
N = |distinct actor_id in c|
Se N < 5 AND audience IN ['executive', 'progetto']:
    sostituisci dimension actor_id → role_id (via actors_map) e ricalcola a livello ruolo
Se N < 5 AND audience == 'operativa':
    se analytics.measurement.operational_show_actor_id == false (default): stesso mascheramento
    else: mantieni actor_id MA logga warning «cella mostrata con N=<n>, sotto soglia GDPR default»
```
Soglia configurabile via `analytics.measurement.min_aggregation_n` (default 5, floor 1, mai 0);
il report dichiara sempre la soglia applicata.

**Vincoli enforced** (3, non negoziabili):
1. **Prezzi/tariffe SOLO da `pricing.yaml`/`rates.yaml`**: se i tool falliscono per `model_id`
   sconosciuto, **NON** sostituire con default — propagare il fail.
2. **4 concetti distinti**: distinguere lead / cycle / effort / wait — mai sommare ore-persona
   (effort) come tempo di calendario (lead).
3. **Percentili p50/p85/p95**, mai medie.

**Output prodotto**: `cost {agentic, human, total, currency, rate_basis, breakdown?}`,
`split {agentic_pct, human_pct, ...}`, `time` (dallo Step 2).

**Criterio di completamento**: `total == agentic + human`, `agentic_pct + human_pct == 100`
(±0.01), mascheramento applicato per l'audience, nessun prezzo defaultato silenziosamente.

[^src: design_&_architecture/decisions/ADR-023.md §C]
[^src: design_&_architecture/decisions/ADR-024.md §B]

---

## Step 4 — Colli di Bottiglia + Trend

**Input atteso**: `bottlenecks[]` e `operational.trend[]` di `analyze-timeline` (Step 2) +
costi (Step 3).

**Tool invocato**: nessuno (interpretazione degli output dello Step 2).

**Azione**:
- **Bottlenecks** — per ogni stato con `bottleneck: true`, annotare nel report con il
  `share_of_lead` esplicito (es. «`review` = 41% del lead time»). Lo stato top diventa
  `time.bottleneck` (human-readable) + `time.bottleneck_state` (machine-readable).
- **Trend** — leggere `operational.trend[]` settimanale: p50/p85 **crescenti** = peggioramento,
  **decrescenti** = miglioramento. Annotare la direzione.
- **Cost-per-task / cost-per-finding** — per i `task_type` rilevanti, calcolare derivati
  come `cost-per-review-iteration` (CQRL, EP-009/EP-007), `cost-per-a11y-scan` (EP-007),
  ecc., dividendo il costo aggregato per il numero di unità del `task_type`.

**Output prodotto**: `time.bottleneck` + `time.bottleneck_state`, sintesi trend, metriche
cost-per-X per i task_type rilevanti.

**Criterio di completamento**: bottleneck top identificato con `share_of_lead`, direzione del
trend dichiarata, almeno le metriche cost-per-X dei task_type presenti nello scope calcolate.

[^src: management/kanban/EP-009-task-analytics-measurement/US-036-skill-cost-and-time-analytics/US-036.md §Business Rules]

---

## Step 5 — Report Standard

**Input atteso**: output aggregato degli Step 2-4 + `scope.audience` dallo Step 1.

**Tool invocato**: `generate-report.sh` (US-037) con l'audience.

```
bash tools/analytics/generate-report.sh \
     --payload '<aggregated>' --audience '<scope.audience>' --output json
```

**Azione** — emetti il report nello **schema standard ADR-024 §A** (`type: cost_time_report`),
con sotto-schemi `cost`/`time`/`split` (ADR-024 §B-D) e `notes[]` **obbligatorio** (anche se
vuoto). La skill esegue la **schema validation** prima dell'emissione (è "schema guardian":
fail-loud su shape non coerente con `type`).

```json
{
  "schema_version": "v1",
  "scope":   { "project_id": "...", "period": "...", "type": "project|sprint|task|adhoc" },
  "type":    "cost_time_report",
  "audience": "operativa | progetto | executive",
  "generated_at": "<ISO8601>",
  "generated_by": "cost-and-time-analytics (skill)",
  "cost":  { "agentic": ..., "human": ..., "total": ..., "currency": "EUR",
             "rate_basis": "fully-loaded|bill-rate" },
  "time":  { "lead_p50_days": ..., "lead_p85_days": ..., "lead_p95_days": ...,
             "bottleneck": "...", "bottleneck_state": "...", "n_samples": ... },
  "split": { "agentic_pct": ..., "human_pct": ... },
  "operational": { "throughput_per_week": ..., "wip_avg": ..., "trend": [...] },
  "notes": [ "..." ]
}
```

+ sintesi leggibile in Markdown sotto il JSON, con highlight per `audience`.

**4 invarianti del report** (regole obbligatorie):
1. **Split umano vs agentico sempre presente** — metrica di prima classe, mai omessa.
2. **`rate_basis` esplicito** (`fully-loaded` o `bill-rate`) quando `cost.human > 0` — mai
   ambiguo. Validation: `cost.human > 0 → rate_basis presente`, altrimenti fail-loud
   (ADR-023 §E). Riportato sia nel JSON sia nel digest Markdown.
3. **Drift dei prezzi** — se l'ultimo aggiornamento di `pricing.yaml` è > 90 giorni, aggiungere
   `notes[]: "Pricing table aggiornato l'ultima volta YYYY-MM-DD — verificare drift modelli"`.
4. **Limiti dichiarati** (garbage-in-garbage-out) — se l'event store ha gap evidenti (es.
   `record_task_event` attivato solo a metà periodo), aggiungere
   `notes[]: "Instrumentazione attiva da YYYY-MM-DD; eventi precedenti potrebbero mancare"`.

**Output prodotto**: report JSON (schema standard) + digest Markdown. Output principale in
`analytics/reports/` (ADR-024 / ADR-023 §A).

**Criterio di completamento**: report JSON conforme allo schema ADR-024 §A, validation passata,
4 invarianti rispettate, `notes[]` presente.

[^src: design_&_architecture/decisions/ADR-024.md §A]

---

## Vincoli della skill (enforced)

- **NON stima il futuro**: se il caller chiede «quanto durerà / quanto costerà?» → **declina**
  e suggerisci EP-010 (skill [project-estimation](mdc:.cursor/skills/project-estimation/SKILL.md) / agente [estimation-analyst](mdc:.cursor/rules/estimation-analyst.mdc)). La
  misurazione (passato) e la stima (futuro) sono strutturalmente separate.
- **NON inventa eventi mancanti**: garbage-in-garbage-out è un limite documentato, non
  risolvibile dalla skill. Gap nell'event store si dichiarano (Step 5 invariante #4), non si
  riempiono.

[^src: management/kanban/EP-009-task-analytics-measurement/US-036-skill-cost-and-time-analytics/US-036.md §Business Rules]

---

## Auto-detection chiusura progetto (ADR-027 §C)

Quando la skill è invocata su uno **scope di progetto** (`scope.project_id` valorizzato),
esegue una verifica aggiuntiva per la retrospettiva di accuratezza:

1. **Segnale**: tutti i TSK del progetto (filtrati per `project_id`) hanno `status: done` (o
   `closed`) **e** esiste un `estimate_id` collegato al progetto (frontmatter TSK `estimate_id`,
   ADR-023 §G).
2. **Detector**: se il segnale è vero **e** non esiste già il file
   `analytics/reports/accuracy/<estimate_id>.json` → genera la retrospettiva di accuratezza
   (schema `accuracy`, ADR-024 §F / ADR-027).
3. **Idempotenza**: la retrospettiva è generata **una sola volta** per `estimate_id`;
   invocazioni successive rilevano il file esistente e fanno skip.

Se non c'è `estimate_id` collegato o non tutti i TSK sono done → nessuna auto-generazione
(silenziosa, non è un errore).

[^src: design_&_architecture/decisions/ADR-027.md §C]

---

## Pattern

- Istanza di [[thin-agents-fat-skills-refactor]]: la procedura di orchestrazione vive qui (fat
  skill), consumata da più agenti thin ([orchestrator](mdc:.cursor/rules/orchestrator.mdc), [tpm](mdc:.cursor/rules/tpm.mdc), `qa-dev`, [analytics-reporter](mdc:.cursor/rules/analytics-reporter.mdc)),
  allineandosi a EP-007 US-024 ([accessibility-testing-protocol](mdc:.cursor/skills/accessibility-testing-protocol/SKILL.md)) e EP-008 US-028. La skill
  orchestra + interpreta; i tool (`compute-agentic-cost.sh`, `compute-human-cost.sh`,
  `analyze-timeline.sh`, `generate-report.sh`) restano puri trasformatori deterministici
  (ADR-023 §B).
- PATTERN.md §3 — operazione opzionale «Cost/Time Report» con invarianti di trasparenza
  (`rate_basis` esplicito ADR-023 §E) + aggregazione minima N>=5 (ADR-023 §C).

[^src: design_&_architecture/decisions/ADR-023.md §B]
[^src: design_&_architecture/decisions/ADR-024.md §A]

---

## Step 6 — Baseline report generation (opt-in v2.19+)

**Gate**: `analytics.dogfooding.enabled: true` AND ≥3 run reali completati.
SE gate false: step SKIP.

**Trigger**: invocazione `/analytics report --baseline --version=<vX.Y.Z>` (on-demand, mai automatico).

**Action**:
1. Legge tutti gli eventi in `analytics/events/` prodotti dai run della versione target.
2. Invoca `analyze-timeline.sh` per produrre P50/P85/P95 per layer.
3. Aggrega token consumption per capability (da campo `task_type`).
4. Calcola wave parallelism efficacy dagli eventi `wave_started`/`wave_completed`.
5. Identifica outlier (elapsed_ms > P95*2).
6. Produce `analytics/reports/baseline/v<X.Y.Z>-baseline.md` con schema US-053 §Business Rules.

**Output**: `analytics/reports/baseline/v<X.Y.Z>-baseline.md` con frontmatter + 7 sezioni.
**Consumer naturale**: EP-014 (temporal budget governor) consuma §1 (P85 per layer) come reference class.

**Nota**: il baseline è on-demand perché generarlo automaticamente aggiungerebbe overhead su ogni `/run`. Il maintainer lo genera manualmente dopo i 3 run di EP-012. [^src: design_&_architecture/decisions/ADR-041.md §D]
