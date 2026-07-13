---
description: Invoca estimation-analyst su uno scope (project/sprint/capacity/sales) per stima costi e tempi enterprise (EP-010 US-043). Stima il futuro (intervallo + confidenza + assunzioni + contingency), NON misura il passato. Flag --from-kanban, --review-accuracy, --aggregate-accuracy, --ephemeral. Fallback skill project-estimation (PERT-only se no storico).
argument-hint: <scope> [--method=rcf|pert|monte-carlo|hybrid|auto] [--contingency-pct=N] [--audience=executive|project] [--review-accuracy=<estimate_id>] [--aggregate-accuracy] [--output=<path>] [--ephemeral] [--similarity=high|medium|low] [--critical-path=<DAG-source>]
allowed-tools: Read, Write, Edit, Glob, Bash
---

Comando della capability [[task-analytics-cost-estimation-capability]] (faccia **Stima**,
EP-010). Delega la stima end-to-end (decomponi scope → recupera reference class → applica
RCF + PERT + Monte Carlo → intervallo + confidenza + assunzioni + contingency + split)
all'agente [estimation-analyst](mdc:.cursor/rules/estimation-analyst.mdc). **Stima il futuro, NON misura il passato**: per audit
consuntivo usa `/analytics` (`analytics-reporter`, EP-009).

Faccia speculare di `/analytics`. Riferimenti architetturali: EP-010
(`management/kanban/EP-010-task-analytics-estimation/EP-010.md`), ADR-025 (metodologia +
PERT scope ingestion §E), ADR-027 (storage stime + retrospettiva accuratezza + `estimate_id`).

## Sintassi

```
/estimate <scope> [--method=rcf|pert|monte-carlo|hybrid|auto] [--contingency-pct=N] [--audience=executive|project] [--review-accuracy=<estimate_id>] [--aggregate-accuracy] [--output=<path>] [--ephemeral] [--similarity=high|medium|low] [--critical-path=<DAG-source>]
```

## `<scope>` — 3 forme (ADR-025 §E)

| Forma | Esempio | Significato |
|---|---|---|
| `--scope-file=<path.json\|yaml>` | `/estimate --scope-file=./estimates/scope-q3.yaml --unit=days` | Input esplicito (default). Lista strutturata di voci `{name, O, M, P}` + `unit` + `context` opzionale. Schema in ADR-025 §E. |
| `--from-kanban=<EP-id>` | `/estimate --from-kanban=EP-011 --similarity=high` | Auto-decomposizione da una EP già decomposta in US/TSK: per ogni TSK cerca task storici simili → deriva O=P15 / M=mediana / P=P85 dalla reference class (ADR-025 §E). **Richiede EP-009 (measurement) attiva.** |
| `--from-brief=<path.md>` | `/estimate --from-brief=./briefs/acme-saas.md` | Stima a partire da un brief commerciale (sales engineering). La skill decompone il brief in work breakdown PERT. |

Per scope inline esplicito è ammesso anche `--scope='[{"name":...,"O":..,"M":..,"P":..}]' --unit=days` (ADR-025 §E modalità 1).

## Flag

- `--method=rcf|pert|monte-carlo|hybrid|auto` — default `auto` (= `mode_recommended` da
  `build_reference_class`: la Reference Class Sufficiency Policy sceglie RCF/PERT/PERT-only in
  base a confidence, ADR-025 §C). Override esplicito possibile; per `confidence: very_low` la
  skill **forza** comunque PERT (ADR-025 §D).
- `--contingency-pct=N` — default da `analytics.estimation.default_contingency_pct` (default 15).
  Per `confidence: very_low` la skill auto-alza a `>=30` (default 35) con warning (ADR-025 §C-D).
- `--audience=executive|project` — default `project`. Determina il livello di dettaglio del
  digest MD.
- `--similarity=high|medium|low` — override esplicito della similarity reference class. Default:
  **auto-stimata** se `--from-kanban` (tag/layer overlap, ADR-025 §B punto 2); altrimenti
  **richiede esplicito** (fallback conservativo `medium` se assente, ADR-025 §B punto 3).
- `--critical-path=<DAG-source>` — produce la sezione `critical_path_analysis` nel report
  (ADR-044 / US-044): identifica il cammino critico del work breakdown e i driver di slittamento.
- `--review-accuracy=<estimate_id>` — modalità retrospettiva: **non genera una nuova stima**, ma
  l'audit di accuratezza di una stima storica (vedi §`--review-accuracy` sotto).
- `--aggregate-accuracy` — modalità calibrazione: **non genera una nuova stima**, invoca il tool
  `aggregate-accuracy` sulle retrospettive accumulate e stampa il report di calibration in chat.
  Se `--output=<path>` è passato contestualmente, persiste il report in
  `analytics/reports/calibration/<YYYY-MM-DD>-calibration.{json,md}`.
  Ref: EP-026, ADR-027 §D (vedi §`--aggregate-accuracy` sotto).
- `--output=<path>` — usato con `--aggregate-accuracy`: persiste il report di calibration in
  `analytics/reports/calibration/<YYYY-MM-DD>-calibration.{json,md}`. Non applicabile alle
  altre modalità (stima forward, review-accuracy, ephemeral).
- `--ephemeral` — **non scrive** in `analytics/reports/estimates/`: il report va in
  `analytics/reports/_adhoc/` (analogo a `/query --ephemeral` e `/analytics --ephemeral`).
  L'entry su `wiki/log.md` viene comunque appesa.

## Comportamento

1. Read `factory.config.yaml.analytics.estimation`. Se `enabled: false` → ABORT pulito;
   suggerisci «Abilita con `analytics.estimation.enabled: true` e ri-prova».
2. Risolvi `<scope>` in una delle 3 forme sopra:
   - `--scope-file=<path>` / `--scope=<inline>` → carica il work breakdown esplicito.
   - `--from-kanban=<EP-id>` → `Glob management/kanban/EP-<id>*/EP-<id>.md` + US/TSK figli;
     **fail-loud** se `analytics.measurement.enabled: false` (vedi §`--from-kanban` sotto).
   - `--from-brief=<path.md>` → carica il brief.
   - Se `--review-accuracy` è passato → salta alla modalità retrospettiva (§ dedicata).
3. **Invocazione** (con fallback):
   - Se [estimation-analyst](mdc:.cursor/rules/estimation-analyst.mdc) è scaffoldato **e**
     `analytics.estimation.agent: true` → invoca l'agente `estimation-analyst` passando `scope`,
     `method`, `contingency_pct`, `audience`, `similarity`, `critical_path`, `ephemeral`.
   - **Fallback**: se l'agente non è scaffoldato (file assente) o `agent: false`, ma la skill
     [project-estimation](mdc:.cursor/skills/project-estimation/SKILL.md) (US-040) è presente → esegui la skill direttamente via
     orchestrator/tpm (chi è attivo nella topologia). La capability di stima resta disponibile
     come skill anche senza agente dedicato (PATTERN §3, albero Tool/Skill/Agente).
   - Se né agente né skill esistono → ABORT «Capability estimation non scaffoldata».
4. L'agente/skill applica la Reference Class Sufficiency Policy (ADR-025 §A-C) e produce il
   report nello schema standard US-042 / ADR-024 §E (sub-blocco `estimate:` con i 6 campi
   obbligatori: `intervals`, `split`, `assumptions[]`, `contingency_pct`,
   `sensitivity_drivers[]`, `reference_class_quality`). **Mai un numero puntuale**.
   - **Fallback PERT-only (N=0, ADR-025 §D)**: se non c'è storico, la stima è comunque emessa in
     modalità `reference_class_quality: {N: 0, mode: PERT-only, confidence: very_low}` +
     `contingency_pct >= 30` + warning «Nessun dato storico disponibile: stima basata solo su
     elicitation. Bias di ottimismo non mitigato. Calibrare contingency al rialzo (>=30%)». Mai
     degradare silenziosamente.
5. Mostra in chat il summary (P50/P85 cost + duration, confidence, mode, contingency, top
   sensitivity driver, `estimate_id`).

## `--from-kanban` — fail-loud se EP-009 non attiva

L'auto-decomposizione legge lo storico (`analytics/events/`) per derivare O/M/P dei TSK; senza
measurement non ha senso. Se `analytics.measurement.enabled: false` (o EP-009 non scaffoldata):

> **ABORT fail-loud**: «EP-009 (measurement) richiesta per `--from-kanban`. Vedi ADR-025 §E.»

Nessuna stima silenziosa, nessun fallback implicito a esplicito. Il caller deve o attivare la
measurement, o passare lo scope esplicito (`--scope-file` / `--from-brief`).

## `--review-accuracy=<estimate_id>` — retrospettiva accuratezza (ADR-027 §C)

`/estimate --review-accuracy=<estimate_id> [--force]`:

1. Carica la stima storica `analytics/reports/estimates/...` con quel `estimate_id`. Se non
   esiste → ABORT «estimate_id non trovato».
2. Invoca la **misurazione effettiva** della faccia Misurazione (EP-009 US-035, via
   `analytics-reporter` / skill [cost-and-time-analytics](mdc:.cursor/skills/cost-and-time-analytics/SKILL.md)) sul progetto chiuso collegato.
3. Produce/rigenera `analytics/reports/accuracy/<estimate_id>.{json,md}`
   (`type: accuracy_retrospective`, schema ADR-024 §F / ADR-027 §C): confronto P50/P85 stima vs
   valore reale, `delta`, `verdict`, `lessons_learned`, `calibration_signals`.
4. **Idempotenza**: una sola volta per `estimate_id`; se il file esiste → skip (override
   `--force` per ri-generare).

Nota: il retrospettivo è **single-writer della faccia Misurazione** (skill
[cost-and-time-analytics](mdc:.cursor/skills/cost-and-time-analytics/SKILL.md) / `analytics-reporter`, ADR-027 §C/§E). `estimation-analyst` fornisce
la stima storica come input + può delegare l'invocazione; non produce una nuova stima
forward-looking (il vincolo no-past resta intatto: qui si confronta con un actual già misurato).

## `--aggregate-accuracy` — calibrazione storico stime (EP-026, ADR-027 §D)

`/estimate --aggregate-accuracy [--output=<path>]`:

1. Legge `analytics/reports/accuracy/*.json` (tutti i file presenti).
2. Calcola statistiche aggregate per metodo (rcf/pert/combined) e per confidence
   bucket (high/medium/low/very_low): % within_p85 (= `verdict.overall == 'good'`).
3. Produce `calibration_signals`: metodo migliore, bucket più debole, suggerimento
   sulla soglia `rcf_medium_threshold`.
4. Se N=0: messaggio informativo + exit 0.
   Se N<10: avviso `'Storico insufficiente (N=<n>). Risultati orientativi.'` + procede.
5. Output: stampato in chat. Con `--output=<path>`: persiste in
   `analytics/reports/calibration/<YYYY-MM-DD>-calibration.{json,md}`.

Nota: non genera una nuova stima forward-looking. Non modifica `factory.config.yaml`.
I `calibration_signals` sono orientativi — il PM decide se aggiornare le soglie config.
Procedura completa: `tools/analytics/aggregate-accuracy.md`.

## Storage

- **Scope esplicito** → `analytics/reports/estimates/<YYYY-MM-DD>-<slug>.{json,md}` (JSON canonico
  + MD digest umano) con `estimate_id` univoco (`EST-<YYYY-MM-DD>-<NNN>`, ADR-027 §B) nel
  frontmatter/top-level. Slug kebab-case del scope (`--slug` opzionale; altrimenti derivato da
  `scope.project_id`/`scope.name`). **Immutabile**: una re-stima crea un nuovo file con nuovo
  `estimate_id` + `metadata.previous_estimate_id` (ADR-027 §A/§F).
- **Ad-hoc / `--ephemeral`** → `analytics/reports/_adhoc/estimate-<YYYY-MM-DD-HH-MM>-<slug>.{json,md}`
  (**nessuna scrittura** in `estimates/` quando `--ephemeral`).
- **Retrospettiva** → `analytics/reports/accuracy/<estimate_id>.{json,md}` (single-writer faccia
  Misurazione, ADR-027 §C).
- `analytics/reports/estimates/` **non è gitignored** di default (stime = documenti audit,
  paralleli agli ADR; opt-out documentato solo per NDA cliente, ADR-027 §A).

## Logging

Ogni invocazione appende a `wiki/log.md` (anche con `--ephemeral`) una entry nel formato
canonico, analogo alle entry `analytics`/`review`/`a11y`:

```
[YYYY-MM-DD HH:MM] estimate <scope> → p50=<X> p85=<Y> confidence=<level>
```

Inoltre l'agente scrive uno snapshot in `memory/episodic/estimation-runs.md` (single-writer per
file, input per il calibration loop, cross-link [[learning-accumulation]]).

## Prerequisiti

- `factory.config.yaml.analytics.estimation.enabled: true`.
- Per la via agente: `analytics.estimation.agent: true` + [estimation-analyst](mdc:.cursor/rules/estimation-analyst.mdc).
- Per la via fallback: skill [project-estimation](mdc:.cursor/skills/project-estimation/SKILL.md) (US-040) presente + topology con
  orchestrator/tpm attivo.
- Per `--from-kanban`: `analytics.measurement.enabled: true` (EP-009 attiva).
- `analytics/pricing.yaml` / `analytics/rates.yaml` presenti (tariffe mai hardcoded).

## Vincoli (R.P3 — opt-in totale)

- Comando **opt-in**: la sua assenza non è ERROR di lint (R.P3). Assenza di **entrambi** i file
  (agente + comando) → comportamento identico a v2.17 (backward compat, 0 nuove ERROR di lint con
  e senza il comando).
- **Mai** produrre stime consuntive su dati passati («quanto è costato»): è scope di `/analytics`
  (`analytics-reporter`). Il vincolo no-past-measurement è enforced dall'agente.
- **Mai numero puntuale**: ogni stima è un intervallo (P50/P85, +P95 se Monte Carlo) con
  assunzioni esplicite, contingency dichiarata separatamente, qualità della reference class
  (N, similarity, confidence, mode). Invariante PATTERN §3 `Project Estimation` (ADR-025 §F).
- L'agente non modifica il corpo dei TSK: al massimo il campo frontmatter `estimate_id:` del TSK
  target (+ `updated:`), single-writer (ADR-027 §G).

Vedi [estimation-analyst](mdc:.cursor/rules/estimation-analyst.mdc), skill [project-estimation](mdc:.cursor/skills/project-estimation/SKILL.md), EP-010, ADR-025/027 e
[[task-analytics-cost-estimation-capability]] per il contratto completo.
