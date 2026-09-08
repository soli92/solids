---
type: runbook
status: stable
epic: EP-061
pattern_version: "2.41"
---

# Runbook — Session Analysis → Fleet Doctor Handoff

## Overview

Flusso **unidirezionale e advisory**: `session-analysis` produce `fleet_recommendations`
nel report JSON; fleet-doctor le legge opzionalmente nelle sessioni successive.
Nessuna dipendenza hard tra i due strumenti, nessun auto-invoke (R-SAA-6).

## Step operativi

1. `/session-analysis --last N --save --format=json`
   → produce `raw/YYYY-MM-DD-session-analysis-<id>.json`

2. Ispeziona `fleet_recommendations` nel JSON. Ogni entry:
   ```json
   { "anomaly_id": "ANO-XXX", "skill_affected": "<slug>",
     "recommendation": "...", "priority": "high|medium|low",
     "fleet_doctor_command": "/fleet-doctor analyze <target> --context=ANO-XXX" }
   ```

3. Se `fleet_doctor_command` non null: **valuta manualmente** se eseguirlo.
   Criteri tipici: `priority: high` + confermata da più sessioni + skill degradata.

4. Se decidi di procedere: esegui il comando in una **sessione futura** separata.
   Nota: `/fleet-doctor` è roadmap — usare `/refactor <target-path>` attualmente.

5. Fleet-doctor applica i propri gate G1–G11 (EP-060) — nessun auto-apply.

## Invarianti

- **R-SAA-6**: nessun fix auto-applicato — ogni azione è umana o delegata a fleet-doctor
- **R-SAA-8**: non eseguire fleet-doctor nella sessione corrente di analisi
- **R-SAA-2**: generate-report.py scrive solo in `raw/`, nessuna mutazione `.claude/`
- **R-SAA-1**: il report è deterministico e read-only rispetto allo stato factory

## Anti-patterns

- Mai eseguire `fleet_doctor_command` da script automatici — sempre umano deliberato
- Mai eseguire fleet-doctor su sessione ancora aperta
- Mai bypassare il gate umano di Fase 2 in fleet-doctor (EP-060 §kill_criterion)
- `fleet_doctor_command: null` non è un errore — è raccomandazione solo testuale

## Cross-link

- Skill: `.claude/skills/session-analysis-protocol.md`
- Agente: `.claude/agents/fleet-doctor.md`
- EP-060: `management/kanban/EP-060-fleet-health/`
- EP-061 kill_criterion: `management/kanban/EP-061-session-agentic-analyser/EP-061.md`
