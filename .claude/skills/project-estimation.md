---
name: project-estimation
description: >-
  Skill Project Estimation, 5 step: Decomponi Scope → Reference Class → PERT/Monte Carlo → Combinazione+RCF → Output. Orchestra tool (run-pert, run-monte-carlo, build-reference-class, analyze-timeline). Mai numero puntuale, sempre intervallo con confidence.
---
# Protocollo Project Estimation — stima enterprise difendibile in 5 step

Skill procedurale fondante della capability Task Analytics — Estimation (EP-010): incapsula
la conoscenza metodologica per produrre **stime di tempi e costi enterprise difendibili**
applicando i 3 metodi quantitativi (Reference-Class Forecasting, PERT three-point, Monte
Carlo throughput) della [[task-analytics-estimation-methods]] e impone l'invariante non
negoziabile **«mai un numero puntuale»**. Caricabile da `orchestrator`, `tpm`,
`estimation-analyst` (pattern [[thin-agents-fat-skills-refactor]]).

La skill **orchestra**, i tool **calcolano** (ADR-023 §B). Le formule vivono nei tool; la
decisione di quale metodo applicare, la combinazione conservativa e la validation dello schema
vivono qui.

**Operazione opzionale** (PATTERN §3): attiva solo con `analytics.estimation.enabled: true`.
A capability spenta: no-op, assenza non produce ERROR (R.P3).

Tool orchestrati: `build-reference-class.py`, `run-pert.py`, `run-monte-carlo.py`,
`estimate-project.py`. Fonte storico: `analyze-timeline.py` (EP-009, prerequisito per RCF).

Riferimenti: ADR-024 (output schema §A+§E), ADR-025 (Reference Class Sufficiency Policy §A,
similarity §B, mapping confidence §C, fallback §D, scope ingestion §E), ADR-027 (storage §A,
`estimate_id` §B, retrospettiva §C-D).

[^src: management/kanban/EP-010-task-analytics-estimation/US-040-skill-project-estimation/US-040.md §Business Rules]

---

## Invariante principale: mai numero puntuale

L'output è **sempre** un intervallo `[p50, p85]` con confidence e assunzioni esplicite.
`intervals.cost.p85` è obbligatorio. Se il caller insiste per un numero solo: P85 + warning.

---

## Boot Validation (prima di ogni step)

Verifica coerenza soglie `analytics.estimation` da config. Fail-loud su mis-config.
Dettaglio completo nella foglia Step 1.

---

## Step 1 — Decomponi Scope

Input scope in due modalità: **esplicita** (`scope: [{name, task_type, O, M, P}]`) o
**`--from-kanban=<EP-id>`** (auto-decomposizione, richiede `analytics.measurement.enabled`).
Ogni voce non stimabile → `open_questions[]` al caller. Mai inventare dati.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (Boot Validation, schema scope-file YAML verbatim,
> modalità `--from-kanban`, Note di provenienza, criterio escalation, algoritmo bucket_by_N + downgrade
> similarity, mapping confidence → metodo + contingency, enforce VERY_LOW, warnings N=0) si trova in:
> `.claude/skills/references/project-estimation/step-1-decomponi-scope.md`
>
> Leggi obbligatoriamente quella foglia prima di avviare la skill.
> Se il file manca → STOP e segnala.

---

## Step 2 — Reference Class (outside view)

Per ogni voce invoca `build-reference-class.py --filter '{"task_type":"<X>"}'`. Applica
Reference Class Sufficiency Policy (ADR-025 §A): N campioni → bucket (high/medium/low/very_low),
downgrade per similarity. Output per voce: distribuzione percentili + `confidence_final`.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (tool invocato, algoritmo bucket + esempi, similarity
> factor tre modalità, output per voce, criterio di completamento) si trova in:
> `.claude/skills/references/project-estimation/step-2-reference-class.md`
>
> Leggi obbligatoriamente quella foglia prima di invocare `build-reference-class.py`.
> Se il file manca → STOP e segnala.

---

## Step 3 — PERT three-point (inside view)

Invoca `run-pert.py`. Formule verbatim: `attesa = (O + 4M + P) / 6`, `varianza = ((P-O)/6)²`.
Somma attese e varianze. Metodo primario se `confidence <= medium`; cross-check se `high`;
unico metodo se `very_low` (N=0, PERT-only).

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (tool invocato, formule PERT verbatim, quando
> applicare per confidence level, output P50/P85/P95, criterio di completamento) si trova in:
> `.claude/skills/references/project-estimation/step-3-pert.md`
>
> Leggi obbligatoriamente quella foglia prima di invocare `run-pert.py`.
> Se il file manca → STOP e segnala.

---

## Step 4 + 5 — Monte Carlo, Combinazione e Output Obbligatorio

Monte Carlo invocato solo se `backlog noto + storico >= 8 settimane`. Combinazione conservativa:
P50/P85/P95 finale = **massimo** tra i metodi (mai media ottimistica). Output obbligatorio: 6
campi (`method`, `intervals`, `split_human_agentic`, `assumptions[]`, `contingency_pct`,
`sensitivity_drivers[]`) + schema guardian fail-loud. `estimate_id` generato e file persistiti.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (tool Monte Carlo, tabella come combinare i 3 metodi,
> regola massimo conservativo, sensitivity drivers, 6 campi obbligatori sub-schema `estimate:` con
> monotonicità e cross-field check, `estimate_id` generazione, persistenza ADR-027, 4 regole invarianti
> del report, vincoli skill, fallback PERT-only senza EP-009) si trova in:
> `.claude/skills/references/project-estimation/step-4-monte-carlo-output.md`
>
> Leggi obbligatoriamente quella foglia prima di invocare `run-monte-carlo.py` e `estimate-project.py`.
> Se il file manca → STOP e segnala.

---

## Pattern

- [[thin-agents-fat-skills-refactor]]: metodologia vive qui (fat), agenti restano thin.
- [[evaluator-optimizer]]: misurazione retrospettiva EP-009 via `estimate_id` è l'evaluator
  del calibration loop (ADR-027 §C-D → [[learning-accumulation]]).
- PATTERN §3 — operazione opzionale «Project Estimation»: opt-in stack-agnostico.

[^src: design_&_architecture/decisions/ADR-023.md §B]
[^src: design_&_architecture/decisions/ADR-025.md §F]
