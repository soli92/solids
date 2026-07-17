# Skill: Project Estimation

> Adapter Cursor della skill `project-estimation` definita in PATTERN.md.

Metadata skill (originale):
```yaml
name: project-estimation
description: Skill procedurale Project Estimation — 5 step (Decomponi Scope → Reference Class outside-view → PERT/Monte Carlo inside-view → Combinazione + RCF → Output Obbligatorio). Orchestra i tool deterministici di stima (run-pert / run-monte-carlo / build-reference-class / analyze-timeline). Invariante: mai numero puntuale, sempre intervallo con confidence. Capability opt-in EP-010, PATTERN §3 Project Estimation.
```

# Protocollo Project Estimation — stima enterprise difendibile in 5 step

Skill procedurale fondante della capability Task Analytics — Estimation (EP-010): incapsula
la conoscenza metodologica per produrre **stime di tempi e costi enterprise difendibili**
applicando i 3 metodi quantitativi (Reference-Class Forecasting, PERT three-point, Monte
Carlo throughput) della [[task-analytics-estimation-methods]] e impone l'invariante non
negoziabile **«mai un numero puntuale»**. È caricabile al bisogno da [orchestrator](mdc:.cursor/rules/orchestrator.mdc), [tpm](mdc:.cursor/rules/tpm.mdc)
e [estimation-analyst](mdc:.cursor/rules/estimation-analyst.mdc) — istanza del pattern [[thin-agents-fat-skills-refactor]]: la
procedura di stima vive nella skill (fat), i tool restano puri trasformatori deterministici
e gli agenti restano thin senza duplicare la metodologia.

La skill **orchestra**, i tool **calcolano** (ADR-023 §B). Le formule (PERT, sampling Monte
Carlo, percentili della reference class) vivono nei tool; la decisione di **quale metodo
applicare con quale confidenza** (Reference Class Sufficiency Policy), la combinazione
conservativa, la composizione del report e la validation dello schema vivono qui.

È anche un'istanza del pattern [[evaluator-optimizer]]: la misurazione retrospettiva di
EP-009 (cost/time reali a chiusura progetto, confrontati con la stima via `estimate_id`) è
l'**evaluator** della stima — calibration loop che chiude il ciclo a fine progetto
(ADR-027 §D, [[learning-accumulation]]).

È un'**operazione opzionale** (PATTERN.md §3 «Project Estimation»), attiva solo con la
capability EP-010 abilitata (`factory.config.yaml.analytics.estimation.enabled: true`).
A capability spenta la skill è no-op: la sua assenza non produce ERROR di lint (R.P3 opt-in
totale).

Tool orchestrati (deterministici, `tools/analytics/`, no MCP):
`build-reference-class.sh` (US-041, sampling N + similarity), `run-pert.sh` (US-041,
formula PERT), `run-monte-carlo.py` (US-041, simulazione throughput), `estimate-project.sh`
(US-041, dispatcher + enforce contingency). Fonte storico per la reference class:
`analyze-timeline.sh` (US-035, EP-009) — prerequisito per RCF e Monte Carlo.

Riferimenti: ADR-024 (output schema standard — §A documento «Analytics Report» +
§E sub-schema `estimate` con 6 campi obbligatori invariante), ADR-025 (Reference Class
Sufficiency Policy §A, similarity factor §B, mapping confidence→metodo+contingency §C,
fallback no-history §D, scope ingestion §E), ADR-027 (storage stime §A, `estimate_id` §B,
retrospettiva accuratezza §C-D). Wiki source-of-truth:
[[task-analytics-cost-estimation-capability]] (faccia previsionale) +
[[task-analytics-estimation-methods]] (3 metodi).

[^src: management/kanban/EP-010-task-analytics-estimation/US-040-skill-project-estimation/US-040.md §Business Rules]
[^src: design_&_architecture/decisions/ADR-024.md §E]
[^src: design_&_architecture/decisions/ADR-025.md §A]
[^src: design_&_architecture/decisions/ADR-027.md §A]

---

## Boot Validation — analytics.estimation thresholds (ADR-025 §A)

Eseguita **una sola volta all'avvio della skill**, prima di qualsiasi step procedurale.
Applicabile solo se `analytics.estimation.enabled: true` (a `false` la skill è no-op, nessuna
validazione necessaria).

```
BOOT VALIDATION — analytics.estimation thresholds
  Leggi analytics.estimation dalla config.
  Verifica: 1 <= rcf_low_confidence_threshold
              < rcf_medium_confidence_threshold
              < rcf_high_confidence_threshold
  Se condizione non soddisfatta → FAIL-LOUD:
    "Mis-config analytics.estimation: soglie non valide. Vedi ADR-025 §A validation."
    (interrompi la skill, non produrre output parziale)
```

Se la validazione passa, prosegui con lo Step 1.

---

## Step 1 — Decomponi Scope

**Input atteso** — lo scope da stimare in una di due modalità:

- **Esplicito (default)**: il caller passa la lista `scope: [{name, task_type, O?, M?, P?}]`
  inline, o `--scope-file=<path>` per scope grandi. Schema scope-file verbatim
  (ADR-025 §E):
  ```yaml
  scope:
    - name:        "auth flow"
      task_type:   "fe-feature"        # per il match nella reference class (Step 2)
      O:           2.0                  # ottimistico (opzionale se derivato da RCF)
      M:           4.0                  # più probabile
      P:           8.0                  # pessimistico
      notes:       "include SAML SSO"
    - name:        "dashboard"
      task_type:   "fe-feature"
      O:           3.0
      M:           6.0
      P:           12.0
  unit:            days                 # days | hours
  context:                              # opzionale, override delle assumptions
    team_size:     3
    model_id:      claude-opus-4-7
  ```
- **`--from-kanban=<EP-id>` (opt-in, ADR-025 §E)**: auto-decomposizione di una EP esistente.
  La skill carica `management/kanban/EP-<id>/EP-<id>.md` + le US figlie, identifica i TSK
  figli come voci del PERT, e deriva O/M/P data-driven dalla reference class storica (Step 2):
  `O = p15`, `M = mediana`, `P = p85` della durata dei task simili. Richiede
  `analytics.measurement.enabled: true` (sennò nessuno storico → fail-loud
  «`--from-kanban` richiede `analytics.measurement.enabled: true`»). Per ogni TSK senza
  storico (reference class N=0), usa fallback soft `(O=M, M=default_M_per_layer, P=2*M)` +
  warning, **non** blocca. Nota di provenienza obbligatoria in `notes[]`: «Scope
  auto-decomposed from EP-<id>; X TSK con storico, Y TSK con fallback default». Per progetti
  contractual, raccomanda validazione umana del breakdown auto-decomposto.

**Tool invocato**: nessuno in modalità esplicita (passo cognitivo); in `--from-kanban`,
lettura kanban + `build-reference-class.sh` per voce (anticipa lo Step 2).

**Output prodotto**: lista `scope[]` di voci stimabili, ognuna con `{name, task_type, O, M, P}`
e `unit` coerente, + `context` opzionale per le assumptions.

**Criterio di completamento**: ogni voce dello scope è stimabile (ha `task_type` per il match
o O/M/P espliciti). **Escalation**: se una o più voci non sono stimabili autonomamente (scope
non descritto, task_type ignoto e nessun O/M/P), la skill **non inventa**: emette
`open_questions[]` al caller e si ferma sulle voci ambigue.

[^src: design_&_architecture/decisions/ADR-025.md §E]

---

## Step 2 — Reference Class (outside view)

**Input atteso**: lista `scope[]` dallo Step 1, ognuna con `task_type`/layer.

**Tool invocato** — per ogni voce, recupera la distribuzione storica:

```
bash tools/analytics/build-reference-class.sh \
     --task-type '<task_type>' --layer '<layer>' --output json
# che internamente legge lo storico via analyze-timeline.sh (US-063/US-035, EP-009)
```

**Azione** — applica la **Reference Class Sufficiency Policy** (ADR-025 §A) per mappare il
numero di campioni storici `N` a un bucket di confidenza:

| N (campioni matchanti) | bucket_by_N |
|---|---|
| `N >= 30` (`rcf_high_confidence_threshold`) | `high` |
| `10 <= N < 30` (`rcf_medium_confidence_threshold`) | `medium` |
| `1 <= N < 10` (`rcf_low_confidence_threshold`) | `low` |
| `N == 0` | `very_low` → fallback PERT-only (Step 5, ADR-025 §D) |

Soglie configurabili in `analytics.estimation.{rcf_high/medium/low_confidence_threshold}`
(default 30/10/1). **Validation al boot**: `1 <= rcf_low < rcf_medium < rcf_high`, sennò
fail-loud su mis-config.

**Similarity factor** (ADR-025 §B) — quanto il nuovo scope somiglia allo storico; modula
il bucket via downgrade:
- **Esplicito (default)**: il caller passa `--similarity=high|medium|low`.
- **Auto-stimato** (con `--from-kanban`): tag overlap (Jaccard) + layer overlap → `high`
  (>0.7), `medium` (0.4-0.7), `low` (<0.4).
- **Conservativo (fallback)**: se né esplicito né auto-stimabile, assume `medium`.

```
confidence_final = downgrade(bucket_by_N, similarity_factor[similarity])
  similarity high   → downgrade 0 livelli   (mantieni bucket)
  similarity medium → downgrade 1 livello   (high→medium, medium→low, ...)
  similarity low    → downgrade 2 livelli
  floor = very_low (mai sotto)

Esempi (ADR-025 §A): N=24,similarity=high → medium ; N=24,similarity=low → very_low ;
                     N=45,similarity=high → high ; N=8,similarity=high → low ; N=0 → very_low
```

**Output prodotto** — per voce: `{p50_duration, p85_duration, p95_duration, p50_cost,
p85_cost, N_samples, period_covered, similarity}` + `confidence_final`. Gli aggiustamenti
per differenze note (team size diverso, nuovo stack, scope più ampio) si esplicitano come
`assumptions[]` (Step 5), **mai** come modifica silenziosa della distribuzione.

**Criterio di completamento**: ogni voce ha la sua distribuzione storica (o `N=0` dichiarato)
e un `confidence_final` calcolato deterministicamente da N + similarity.

[^src: design_&_architecture/decisions/ADR-025.md §A]
[^src: design_&_architecture/decisions/ADR-025.md §B]

---

## Step 1b — Recupera reference class e calcola confidence (ADR-025 §A)

Step procedurale esplicito che formalizza l'algoritmo `bucket_by_N + downgrade similarity`
prodotto nello Step 2. Produce il campo di output `reference_class_quality` consumato dagli
Step successivi e dallo Step 5 (Output Obbligatorio).

### 1. Recupero N

```
Conta i task in analytics/events/ con task_type e layer matchanti il nuovo scope.
Periodo di osservazione: ultimi 12 mesi (o tutto lo storico se < 12 mesi disponibile).
Se EP-009 non attivo → N=0 (fallback PERT-only; non è un errore, no fail-loud).
```

### 2. Algoritmo bucket_by_N (ADR-025 §A)

```
if N >= rcf_high_confidence_threshold:    confidence_raw = HIGH
elif N >= rcf_medium_confidence_threshold: confidence_raw = MEDIUM
elif N >= rcf_low_confidence_threshold:   confidence_raw = LOW
else:                                     confidence_raw = VERY_LOW   # N=0 incluso
```

### 3. Similarity input — tre modalità (priorità decrescente, ADR-025 §B)

```
(a) Esplicita: --similarity high|medium|low passato dal caller
(b) Auto-stimata: tag overlap via --from-kanban se attivo
(c) Conservativa: medium (fallback se né (a) né (b) disponibili)
```

### 4. Downgrade per similarity

```
high_similarity:   0 livelli di downgrade
medium_similarity: -1 livello (HIGH→MEDIUM, MEDIUM→LOW, LOW→VERY_LOW)
low_similarity:    -2 livelli (HIGH→LOW, MEDIUM→VERY_LOW, LOW→VERY_LOW)
Floor: VERY_LOW (non scende oltre)
confidence_final = max(VERY_LOW, confidence_raw - downgrade_steps)
```

### 5. Output campo

```
reference_class_quality:
  N: <conteggio>
  period: "<periodo osservazione>"
  similarity: <high|medium|low>
  confidence_final: <HIGH|MEDIUM|LOW|VERY_LOW>
  mode: <RCF|PERT-only>   # PERT-only se N=0
```

Vedi Step confidence→metodo per enforce PERT-only e warnings N=0 (ADR-025 §D).

[^src: design_&_architecture/decisions/ADR-025.md §A]
[^src: design_&_architecture/decisions/ADR-025.md §B]

---

## Step 1c — Mapping confidence → metodo primario + contingency (ADR-025 §C)

Riceve `reference_class_quality.confidence_final` dallo Step 1b e determina il metodo
primario, il metodo di validazione e la contingency raccomandata.

| confidence_final | Metodo primario | Metodo secondario (validation) | Contingency raccomandata | Note |
|------------------|-----------------|-------------------------------|--------------------------|------|
| HIGH             | RCF             | PERT three-point               | 15% (default_contingency_pct) | — |
| MEDIUM           | RCF             | PERT three-point               | 15% (default_contingency_pct) | — |
| LOW              | PERT three-point | RCF (informativo)             | 20%                      | RCF informativo; N basso |
| VERY_LOW         | PERT three-point | —                             | >= 30% (enforce hard)    | N=0 o similarità bassa; vedi enforce |

### Enforce — confidence VERY_LOW

```
ENFORCE — confidence VERY_LOW
  method:          forzato a PERT (anche se il caller ha passato method=RCF; no override)
  contingency_pct: se il valore passato dal caller < 30
                   → auto-alza a 30
                   → log warning: "contingency_pct alzata a 30% (enforce very_low, ADR-025 §C)"
  Questo enforce NON è fail-loud: la skill continua e produce output.
```

### Note enforce — confidence LOW

```
NOTE ENFORCE — confidence LOW
  Aggiungere in notes[] del report:
  "Con N=<N> samples, RCF è informativo; PERT bottom-up dovrebbe essere il metodo
   primario. Vedi ADR-025 §C."
  Nessun enforce hard: il caller può sovrascrivere method.
```

### Warnings — N=0

```
WARNINGS — N=0
  Se N=0, aggiungere obbligatoriamente in warnings[] del report la seguente riga verbatim
  (ADR-025 §D):
  "Nessun dato storico disponibile: stima basata solo su elicitation. Bias di ottimismo
   non mitigato. Calibrare contingency al rialzo (35% applicato di default; raccomandato
   verificare con esperto)."
  Inoltre: contingency_pct forzata a 35 se N=0 (override del default 30 di very_low).
```

[^src: design_&_architecture/decisions/ADR-025.md §C]
[^src: design_&_architecture/decisions/ADR-025.md §D]

---

## Step 3 — PERT three-point (inside view)

**Input atteso**: voci con O/M/P (esplicite dallo Step 1 o derivate da p15/mediana/p85 della
reference class dello Step 2).

**Tool invocato**:

```
bash tools/analytics/run-pert.sh --scope '<voci con O/M/P>' --unit days --output json
```

**Azione** — applica le **formule PERT verbatim** (ADR-025 §E / synthesis §Metodo 2):

```
attesa   = (O + 4M + P) / 6
varianza = ((P - O) / 6)^2
```

Somma le attese e le varianze di tutte le voci → media e std (`sqrt(somma varianze)`) del
progetto totale; deriva P50 ≈ attesa, P85 ≈ attesa + ~1.04σ, P95 ≈ attesa + ~1.64σ.

**Quando applicare**: PERT è metodo primario se `confidence <= medium`; è cross-check (inside
view contro outside view) se `confidence: high`. Per `confidence: very_low` (N=0) PERT è
l'**unico** metodo (fallback, Step 5 / ADR-025 §D).

**Output prodotto**: `pert {p50, p85, p95, mean, std}` per durata e — derivando dal costo
unitario nelle assumptions — per costo.

**Criterio di completamento**: attese e varianze sommate, P50/P85 PERT prodotti per ogni
asse (durata + costo); formule applicate verbatim, nessuna media usata al posto dei
percentili.

[^src: design_&_architecture/decisions/ADR-025.md §E]
[^src: management/kanban/EP-010-task-analytics-estimation/US-040-skill-project-estimation/US-040.md §Business Rules]

---

## Step 4 — Monte Carlo throughput + Combinazione

**Input atteso**: output RCF (Step 2) + PERT (Step 3) + eventuale storico throughput.

**Tool invocato** — Monte Carlo solo se `backlog noto + storico throughput >= 8 settimane`:

```
python tools/analytics/run-monte-carlo.py \
     --backlog <N_items> --throughput-history analytics/events/ --iterations 10000 --output json
```

Produce P50/P85/P95 di settimane → date (10.000 simulazioni). Se lo storico throughput è
< 8 settimane, Monte Carlo è **omesso** (non forzato su dati insufficienti).

**Azione — Combinazione**. Tabella «come combinare» verbatim (synthesis §Come combinare i
tre metodi / ADR-025 §C):

| Situazione | Approccio |
|---|---|
| Abbondanza dati storici | RCF primario, Monte Carlo per validare |
| Pochi dati, scope dettagliato | PERT bottom-up + RCF sanity-check |
| Backlog noto, storico throughput | Monte Carlo throughput primario |
| Prima stima enterprise critica | Tutti e tre in parallelo, riportare 3 confidence |

**Regola difensiva — massimo conservativo** (ADR-025 §C): quando più metodi producono un
intervallo per lo stesso asse, **P50/P85/P95 finale = massimo conservativo tra i metodi**
(si prende il valore più alto, mai la media ottimistica). Il metodo primario è scelto per
`confidence` (ADR-025 §C): high→RCF, medium→RCF+PERT, low→PERT, very_low→PERT-only.

**Sensitivity drivers** — identifica quale variabile cambia di più il P85 (es. team size,
tariffa media, scope assumptions): perturba ogni input e misura l'impatto sul P85. Output in
`sensitivity_drivers[]` con shape `{variable, impact_on_p85_pct, direction: direct|inverse}`.

**Output prodotto**: `intervals` combinato (P50/P85/P95 conservativi per costo + durata) +
`method` risultante + `sensitivity_drivers[]` non-vuoto.

**Criterio di completamento**: P50/P85/P95 finali = massimo conservativo tra i metodi
applicabili; `sensitivity_drivers[]` popolato con almeno 1 driver; Monte Carlo invocato sse
i prerequisiti (backlog + >=8 settimane) sono soddisfatti.

[^src: design_&_architecture/decisions/ADR-025.md §C]
[^src: wiki/syntheses/task-analytics-estimation-methods.md §Come combinare i tre metodi]

---

## Step 5 — Output Obbligatorio

**Input atteso**: output aggregato Step 2-4 + assumptions accumulate.

**Tool invocato**:

```
bash tools/analytics/estimate-project.sh --payload '<aggregated>' --output json
```

**Azione** — emetti il report nello **schema standard ADR-024 §A** (`type: project_estimate`)
con il sub-schema `estimate:` (ADR-024 §E). La skill è **schema guardian**: esegue la
validation prima dell'emissione, fail-loud su shape invalida. I **6 campi obbligatori** del
sub-schema `estimate:` (presenti tutti, altrimenti fail-loud):

1. **`method`** — `RCF | PERT | monte-carlo | combined`.
2. **`intervals`** — intervallo con confidenza, **MAI numero puntuale**:
   `intervals.cost.{p50, p85, p95?, currency}` + `intervals.duration.{p50_days, p85_days, p95_days?}`.
   `p85 > p50` (monotonicità); `p95 > p85` se presente. **`intervals.cost.p85` è obbligatorio**.
3. **`split_human_agentic`** — `{human_pct, agentic_pct, human_cost_p50, agentic_cost_p50}`,
   `human_pct + agentic_pct == 100` (±0.01).
4. **`assumptions[]`** — lista **non-vuota** (scope, team, `model_id`, tariffe + `rate_basis`,
   aggiustamenti). `len >= 1`, sennò fail-loud «Stima senza assunzioni esplicite non ammessa.
   Vedi ADR-024 §E.».
5. **`contingency_pct`** — buffer di rischio **separato dal P50** (`>= 0`); `contingency_cost_at_p50`
   derivato. Default per bucket (ADR-024 §G / ADR-025 §C): high 0-15, medium 15-25, low 25-35,
   very_low `>= 30`.
6. **`sensitivity_drivers[]`** — lista **non-vuota** `{variable, impact_on_p85_pct, direction}`.
   `len >= 1`, sennò fail-loud «Stima senza driver di sensibilità non ammessa. Vedi ADR-024 §E.».

Più `reference_class_quality {N, period, similarity, confidence, mode?}` (effetto della
policy Step 2, ADR-024 §E / ADR-025) e i campi context `model_id`, `compression_enabled`,
`estimate_id`.

**`estimate_id`** (ADR-027 §B) — formato `EST-<YYYY-MM-DD>-<NNN>`, `NNN` contatore per giorno
zero-padded a 3 cifre. Generazione: conta i file con prefisso `YYYY-MM-DD-` in
`analytics/reports/estimates/` per il giorno corrente → `NNN = count + 1`.

**Persistenza** (ADR-027 §A) — scrivi due file paralleli (single-writer, immutabili):
`analytics/reports/estimates/<YYYY-MM-DD>-<slug>.json` (canonico) +
`<YYYY-MM-DD>-<slug>.md` (digest umano). Se la stima è collegata a un TSK target, aggiungi
`estimate_id: EST-...` al frontmatter del TSK (single-writer ADR-023 §G).

**Output prodotto**: report JSON `type: project_estimate` conforme a ADR-024 §A+§E + digest
Markdown, persistiti in `analytics/reports/estimates/`, + `estimate_id` generato.

**Criterio di completamento**: 6 campi obbligatori presenti e validi, `intervals.cost.p85`
presente, monotonicità e cross-field rispettate, `estimate_id` generato, file persistiti.

[^src: design_&_architecture/decisions/ADR-024.md §E]
[^src: design_&_architecture/decisions/ADR-027.md §A]
[^src: design_&_architecture/decisions/ADR-027.md §B]

---

## 4 regole invarianti del report (non negoziabili)

Parallele alla «regola di neutralità» di EP-007 — invarianti del report di stima:

1. **Mai un numero puntuale** — l'output è SEMPRE un intervallo `[p50, p85]` con confidence e
   assunzioni esplicite. `intervals.cost.p85` è obbligatorio: un report con `p50` ma senza
   `p85` fallisce validation (enforced dallo schema, non da convenzione). Se il caller insiste
   «dammi solo un numero», la skill risponde con il P85 + warning «Stima singola sconsigliata:
   range corretto P50=X, P85=Y».
2. **Stima ≠ commitment** — il report contiene sempre la nota «Questa è una stima statistica,
   non un impegno contrattuale. Tenere separati i due artefatti.».
3. **Reference class debole esplicita** — con `confidence: low` o `very_low`, warning testuale
   in evidenza (in `warnings[]`, non solo nel JSON nascosto) — non si nasconde mai.
4. **Drift dei prezzi** — se `pricing.yaml`/`rates.yaml` è più vecchio di 90 giorni, nota in
   `notes[]` («Pricing table aggiornato l'ultima volta YYYY-MM-DD — verificare drift»).

[^src: wiki/concepts/task-analytics-cost-estimation-capability.md §Output obbligatorio di ogni stima]
[^src: design_&_architecture/decisions/ADR-024.md §E]

---

## Vincoli della skill (enforced)

- **NON misura il passato**: se il caller chiede «quanto è costato? / quanto è durato?» →
  **declina** e suggerisci EP-009 (skill [cost-and-time-analytics](mdc:.cursor/skills/cost-and-time-analytics/SKILL.md) / agente
  [analytics-reporter](mdc:.cursor/rules/analytics-reporter.mdc)). La stima (futuro) e la misurazione (passato) sono strutturalmente
  separate. [^src: wiki/concepts/task-analytics-cost-estimation-capability.md §Albero decisionale]
- **NON inventa la reference class**: se 0 dati storici per il `task_type` richiesto, dichiara
  `confidence: very_low` + PERT-only, **non** sostituire con default arbitrari (ADR-025 §D).
- **NON include la contingency nel P85**: il P85 è la statistica pura; la contingency è
  separata e dichiarata in `contingency_pct` (sopra il P50, mai sommata nei percentili).

[^src: management/kanban/EP-010-task-analytics-estimation/US-040-skill-project-estimation/US-040.md §Business Rules]

---

## Fallback senza EP-009 (modalità degradata)

Se `analytics.measurement.enabled: false` (EP-009 non attiva → nessuno storico, nessuna
reference class, nessun throughput per Monte Carlo), la skill funziona in **modalità
degradata PERT-only** (ADR-025 §D):

- Metodo forzato a `method: PERT` (RCF/Monte Carlo non applicabili senza storico).
- `reference_class_quality: {N: 0, period: "n/a", similarity: "n/a", confidence: "very_low",
  mode: "PERT-only"}` — `confidence: very_low` automatico.
- `contingency_pct >= 30` **enforced** (default 35 per very_low); se il caller passa un valore
  inferiore, la skill **auto-alza** e logga warning (no fail-loud — rispetta il vincolo per
  safety).
- Warning automatico **obbligatorio** in `warnings[]`: «EP-009 non attiva / nessun dato storico:
  stima basata solo su elicitation. Bias di ottimismo non mitigato (Kahneman/Flyvbjerg).
  Calibrare contingency al rialzo (35% applicato di default).».

La stima viene **comunque prodotta** (una factory young al 1° progetto ha legittimo bisogno di
stimare) — mai degrada silenziosamente, mai fail-loud sul solo N=0.

[^src: design_&_architecture/decisions/ADR-025.md §D]

---

## Pattern

- Istanza di [[thin-agents-fat-skills-refactor]]: la metodologia di stima vive qui (fat skill),
  consumata da agenti thin ([orchestrator](mdc:.cursor/rules/orchestrator.mdc), [tpm](mdc:.cursor/rules/tpm.mdc), [estimation-analyst](mdc:.cursor/rules/estimation-analyst.mdc)) che non duplicano la
  procedura; i tool (`build-reference-class.sh`, `run-pert.sh`, `run-monte-carlo.py`,
  `estimate-project.sh`) restano puri trasformatori deterministici (ADR-023 §B). La skill
  orchestra + decide il metodo; i tool calcolano.
- Istanza di [[evaluator-optimizer]]: la misurazione retrospettiva di EP-009 (cost/time reali
  a chiusura progetto, collegati via `estimate_id`) è l'**evaluator** della stima — il
  calibration loop a chiusura progetto (ADR-027 §C-D) migliora le stime future
  ([[learning-accumulation]]).
- PATTERN.md §3 — operazione opzionale «Project Estimation»: forecasting opt-in stack-agnostico
  con l'invariante non negoziabile «mai numero puntuale» (intervallo + confidence + assumptions
  + contingency separata + qualità reference class), 6 campi obbligatori (ADR-024 §E),
  Reference Class Sufficiency Policy (ADR-025).

[^src: design_&_architecture/decisions/ADR-023.md §B]
[^src: design_&_architecture/decisions/ADR-025.md §F]
