---
description: Invoca analytics-reporter su uno scope (project/sprint/period/TSK) per audit costi e ROI (EP-009 US-038). Misura il passato, NON stima il futuro. Flag --ephemeral per non salvare.
argument-hint: <scope> [--audience=operativa|progetto|executive] [--format=md|json|pdf|html] [--ephemeral] [--compression-savings]
allowed-tools: Read, Write, Edit, Glob, Bash
---

Comando della capability [[task-analytics-cost-estimation-capability]] (faccia **Misurazione**,
EP-009). Delega l'analisi end-to-end (lettura eventi → calcolo costi → metriche temporali →
bottleneck → report per audience) all'agente [analytics-reporter](mdc:.cursor/rules/analytics-reporter.mdc). **Misura il passato, NON
stima il futuro**: per forecast usa `/estimate` (`estimation-analyst`, EP-010).

## Sintassi

```
/analytics <scope> [--audience=operativa|progetto|executive] [--format=md|json|pdf|html] [--ephemeral] [--compression-savings]
```

## `<scope>` — 4 forme

| Forma | Esempio | Significato |
|---|---|---|
| `project_id` | `/analytics proj-checkout` | tutto il progetto |
| `sprint_id` | `/analytics sprint:10` | un singolo sprint |
| `period:from..to` | `/analytics period:2026-05-01..2026-05-31` | finestra temporale esplicita (ISO 8601) |
| `TSK-id` | `/analytics TSK-067` | un task: recupera `project_id` + `period` dal frontmatter/eventi del TSK |

## Flag

- `--audience=operativa|progetto|executive` — default `progetto`. Determina il livello di
  dettaglio e il mascheramento dati (policy N>=5: `executive`/`project` non mostrano
  `actor_id` raw sotto soglia, ADR-023 §C-D).
- `--format=md|json|pdf|html` — default `md+json`. `pdf`/`html` sono render del report base.
- `--ephemeral` — **non scrive** in `analytics/reports/` (analogo a `/query --ephemeral`):
  il report è restituito solo in chat. L'entry su `wiki/log.md` viene comunque appesa.
- `--compression-savings` — include il sub-campo `cache_savings_pct` nel report. Gated su
  `analytics.measurement.report_compression_savings` in `factory.config.yaml`; se off → flag
  ignorato con nota in chat.

## Comportamento

1. Read `factory.config.yaml.analytics.measurement`. Se `enabled: false` → ABORT pulito
   (nessun evento disponibile, ADR-023 §I); suggerisci «Abilita con
   `analytics.measurement.enabled: true`».
2. Risolvi `<scope>` nelle 4 forme sopra. Se `TSK-id`, `Glob management/kanban/**/TSK-<id>.md`
   e deriva `project_id` + `period`; se non trovato → ABORT «TSK non esiste».
3. **Invocazione** (con fallback):
   - Se [analytics-reporter](mdc:.cursor/rules/analytics-reporter.mdc) è scaffoldato **e**
     `analytics.measurement.agent: true` → invoca l'agente `analytics-reporter` passando
     `scope`, `audience`, `format`, `ephemeral`, `compression_savings`.
   - **Fallback**: se l'agente non è scaffoldato (file assente) o `agent: false`, ma la skill
     [cost-and-time-analytics](mdc:.cursor/skills/cost-and-time-analytics/SKILL.md) (US-036/TSK-064) è presente → esegui la skill direttamente via
     orchestrator/tpm/qa-dev (chi è attivo nella topologia). La capability di misurazione resta
     disponibile come skill anche senza agente dedicato (PATTERN §3, albero Tool/Skill/Agente).
   - Se né agente né skill esistono → ABORT «Capability analytics non scaffoldata».
4. L'agente/skill produce il report nello schema standard US-037 / ADR-024 (`type:
   cost_time_report`) rispettando le 4 invarianti (split umano/agentico, `rate_basis` esplicito,
   percentili non medie, drift prezzi notato).
5. Mostra in chat il verdict/summary (cost_total, split, p50/p85/p95, bottleneck).

## Storage

- **Scope esplicito** → `analytics/reports/<scope_slug>/<periodo>.{json,md}`.
- **Standalone / ad-hoc** → `analytics/reports/_adhoc/<YYYY-MM-DD-HH-MM>-<slug>.{json,md}`
  (analogo al pattern `_adhoc/` di EP-007/EP-008).
- **`--ephemeral`** → nessuna scrittura in `analytics/reports/` (solo chat + log).

## Logging

Ogni invocazione appende a `wiki/log.md` (anche con `--ephemeral`) una entry nel formato
canonico, analogo alle entry `review`/`a11y`:

```
[YYYY-MM-DD HH:MM] analytics <scope> → <audience> → cost_total=<X> <cur>
```

## Prerequisiti

- `factory.config.yaml.analytics.measurement.enabled: true` (eventi disponibili).
- Per la via agente: `analytics.measurement.agent: true` + [analytics-reporter](mdc:.cursor/rules/analytics-reporter.mdc).
- Per la via fallback: skill [cost-and-time-analytics](mdc:.cursor/skills/cost-and-time-analytics/SKILL.md) (US-036) presente + topology con
  orchestrator/tpm/qa-dev attivo.
- `analytics/pricing.yaml` / `analytics/rates.yaml` presenti (tariffe mai hardcoded).

## Vincoli (R.P3 — opt-in totale)

- Comando **opt-in**: la sua assenza non è ERROR di lint (R.P3). Assenza di **entrambi** i file
  (agente + comando) → comportamento identico a v2.17 (backward compat, 0 nuove ERROR).
- **Mai** produrre stime forward-looking ("quanto costerà/durerà"): è scope di `/estimate`
  (`estimation-analyst`). Il vincolo no-future-prediction è enforced dall'agente.
- L'agente non modifica il corpo dei TSK: al massimo il campo frontmatter `cost_event_log:`
  del TSK target (+ `updated:`), single-writer (US-039 / ADR-023 §G).

Vedi [analytics-reporter](mdc:.cursor/rules/analytics-reporter.mdc), skill [cost-and-time-analytics](mdc:.cursor/skills/cost-and-time-analytics/SKILL.md), EP-009, e
[[task-analytics-cost-estimation-capability]] per il contratto completo.
