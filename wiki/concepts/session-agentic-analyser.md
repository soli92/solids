---
type: concept
status: stable
epic: EP-061
pattern_version: "2.41"
ingest_eligible: true
created: 2026-09-08
---

# Session Agentic Analyser

> Capability opt-in per l'analisi critica post-hoc dell'attivita agentica di sessioni
> Claude Code chiuse. Determinism-first (regole deterministiche, no LLM per detection),
> LLM advisory. Mai in-sessione (R-SAA-8).

## Overview

Il Session Agentic Analyser e una capability opt-in del meta-framework factory che
permette di analizzare — a sessione chiusa — le trascrizioni JSONL prodotte da Claude
Code per rilevare anomalie comportamentali, sprechi di budget, pattern di dispatch
inefficienti e altri segnali di salute della flotta.

La capability e progettata per essere consumata dal maintainer della factory (o dal
fleet-doctor in modalita advisory) dopo la conclusione di una sessione: non opera
mai in-sessione (R-SAA-8) e non modifica automaticamente nessun artefatto (R-SAA-3).
Il detection e puramente deterministico (niente LLM nel path di pass/fail); il contributo
LLM e esclusivamente advisory (osservazioni, raccomandazioni), mai bloccante.

Il flusso tipico di utilizzo e:
1. Sessione Claude Code termina e produce un file JSONL in `~/.claude/projects/<id>/`.
2. Il maintainer (o uno scheduler) invoca `/session-analysis [--last N | <session-id>]`.
3. La skill `session-analysis-protocol.md` coordina i tool deterministici in 5 fasi.
4. L'output e un report duale (`raw/*.md` + `raw/*.json`) con anomalie classificate.
5. Se `session_analysis.fleet_doctor_advisory: true`, i finding vengono proposti al
   fleet-doctor come input advisory (mai auto-invocato, R-SAA-6).

La capability diventa operativa in pieno solo dopo EP-062 (Fleet Telemetry Hardening),
che abilita il walker subagent-aware per il fan-in corretto dei file JSONL.

Primary source: [`management/kanban/EP-061-session-agentic-analyser/EP-061.md`](../../management/kanban/EP-061-session-agentic-analyser/EP-061.md)

## Architettura

La skill `session-analysis-protocol.md` orchestra 5 fasi sequenziali:

| Fase | Tool | Output |
|---|---|---|
| 0 — Bootstrap | (config gate) | Verifica `session_analysis.enabled`, identifica session-id |
| 1 — Parse Transcript | `tools/session-analysis/parse-transcript.py` | Struttura normalizzata eventi JSONL |
| 2 — Fleet Metrics | `tools/session-analysis/fleet-metrics.py` | Metriche aggregate (token, turni, tool-call rate) |
| 3 — Detect Anomalies | `tools/session-analysis/detect-anomalies.py` | Lista anomalie classificate via tassonomia v1 |
| 4 — Generate Report | `tools/session-analysis/generate-report.py` | Report duale md+json + campo `fleet_recommendations` |

Tutti i tool sono stdlib Python puro (zero dipendenze esterne). La validazione degli
output avviene contro `tools/session-analysis/schema-anomaly.json` (Draft 2020-12),
garantendo che nessun report malformato entri nel ciclo advisory (R-SAA-5).

Il comando di accesso e:
```
/session-analysis [--last N | <session-id>] [--depth=quick|full] [--json] [--save]
```
Con `--save` il report viene scritto in `raw/YYYY-MM-DD-session-analysis-<id-8char>.{md,json}`.

## Fonti dati

La capability legge trascrizioni JSONL prodotte da Claude Code. Post-EP-062 il walker
diventa subagent-aware e abilita il fan-in completo:

- **Main JSONL** (`~/.claude/projects/<session-id>/*.jsonl`): stream principale di eventi
  (tool call, token usage, messaggi agente/utente).
- **Subagents JSONL** (`~/.claude/projects/<session-id>/subagents/*.jsonl`): stream per
  ciascun sub-agent dispatch (abilitati da EP-062 Fleet Telemetry Hardening).
- **Correlazioni opt-in** (roadmap v2): linking cross-sessione per rilevare pattern
  ricorrenti su piu sessioni (LATENCY/FLEET anomaly types).

Prima di EP-062 il parser lavora solo sul main JSONL; le anomalie di tipo FLEET che
richiedono correlazione cross-subagent sono parziali o non disponibili.

## Tassonomia anomalie v1

La tassonomia v1 e deterministica: il detection non usa LLM.

### 3 tipi core (enabled in v1)

| Tipo | Trigger deterministico | Esempio finding |
|---|---|---|
| `ERROR` | Tool call con status error o eccezione non gestita | `bash tool returned exit 1 without retry` |
| `BUDGET` | Token usage > soglia configurata o spiral loop detection | `3 retry consecutivi stessa operazione, +8k token` |
| `DISPATCH` | Sub-agent dispatch senza gate umano su operazioni ad alto rischio | `write a file di produzione senza gate` |

### 2 tipi opt-in (roadmap v2)

| Tipo | Stato | Note |
|---|---|---|
| `LATENCY` | Roadmap (post-EP-062 subagent timing) | Richiede timestamp per-subagent da EP-062 |
| `FLEET` | Roadmap (cross-session correlation) | Richiede event store multi-sessione |

### Roadmap v2 (candidati)

Tipi aggiuntivi identificati nella Tavola Rotonda TR-c4e8f1b2 come candidati per
formalizzazione in un futuro sprint: GOVERNANCE, SAA-V (verbosity), SAA-C (correctness
drift), SAA-G (goal alignment), SAA-O (over-engineering), SAA-S (security surface).
Non inclusi in v1 per rispettare il kill criterion §23.8 (scope minimo verificabile).

## Invarianti R-SAA-1..10

- **R-SAA-1 Read-only**: la capability non modifica nessun file al di fuori di `raw/` con
  flag `--save` esplicito. Non tocca trascrizioni, kanban, wiki.
- **R-SAA-2 Redazione PII**: i report omettono o oscurano contenuto utente verbatim.
  Solo metadati strutturali (tipo evento, token count, tool name) nei finding.
- **R-SAA-3 No auto-fix**: nessuna anomalia comporta una modifica automatica al codice
  o alla configurazione. Il loop di rimedio e sempre umano-mediato.
- **R-SAA-4 Out-of-band storage**: i report vivono in `raw/` con frontmatter
  `ingest_eligible: false` e `wiki_ingest_policy: incidents-only`. Non entrano nel
  ciclo di ingest wiki ordinario.
- **R-SAA-5 Schema-guard**: il campo `anomalies` del JSON output e validato contro
  `schema-anomaly.json` prima di essere proposto al fleet-doctor. Report invalidi
  vengono rifiutati con errore esplicito, non silenziosamente ignorati.
- **R-SAA-6 No auto-invoke fleet-doctor**: il campo `fleet_recommendations` e advisory.
  Il fleet-doctor non viene invocato automaticamente; e il maintainer a decidere se
  aprire un TSK di follow-up.
- **R-SAA-7 Kill criterion attivo**: la capability e soggetta al sunset §23.8 (hard
  sunset v2.44 se <5 anomalie azionabili producono TSK reali). Vedi EP-061.md per
  le soglie esatte.
- **R-SAA-8 Solo out-of-band**: la capability opera SOLO su sessioni chiuse. Invocarla
  in una sessione attiva e un errore di configurazione; la Fase 0 termina con STOP.
- **R-SAA-9 TTL report**: i report in `raw/` hanno `ttl_days: 90`. Dopo 90 giorni
  possono essere rimossi dal maintainer senza impatto sul framework.
- **R-SAA-10 No LLM detection**: il path di rilevamento anomalie e puramente
  deterministico. Il contributo LLM (se abilitato) e advisory nel campo `critic_notes`,
  mai nel verdict `anomaly_type` o `severity`.

## Kill criterion §23.8

Il `sunset_condition:` canonico e definito nel frontmatter di EP-061.md e NON viene
duplicato qui (citation cascade: EP-061.md e la primary source).

Riferimento: [`management/kanban/EP-061-session-agentic-analyser/EP-061.md#sunset_condition`](../../management/kanban/EP-061-session-agentic-analyser/EP-061.md#sunset_condition)

Le 4 soglie fleet-doctor citate nel blackboard TR-c4e8f1b2 sono:

1. **Utilita minima**: almeno 5 anomalie azionabili (con TSK reale aperto) nelle prime
   3 factory che adottano la capability entro v2.44.
2. **Precisione detection**: false-positive rate <30% sui tipi ERROR e BUDGET.
3. **Costo operativo**: latenza media parse < 5s su trascrizioni fino a 10k eventi.
4. **Adozione**: almeno 1 factory derivata (soli-boy o equivalente) con
   `session_analysis.enabled: true` prima del gate v2.44.

Se nessuna soglia e soddisfatta entro v2.44, la capability viene rimossa e i TSK
correlati marcati `sunset`.

## Integrazione fleet-doctor

Il Session Agentic Analyser e un **input advisory** per fleet-doctor, non un trigger
automatico. Il flusso e:

1. `generate-report.py` (Fase 4) produce il campo `fleet_recommendations` nel JSON.
2. Il maintainer legge il report e, se i finding sono rilevanti, apre un TSK per
   fleet-doctor citando il report come evidence.
3. Fleet-doctor consuma il TSK con la propria skill `refactor-agent-skills.md` o
   la skill EP-060 appropriata.

Vincoli:
- Fleet-doctor NON viene invocato automaticamente dalla Fase 4 (R-SAA-6).
- Il campo `fleet_recommendations` e un array di stringhe advisory, non un comando.
- Il flusso di handoff e documentato in:
  [`wiki/runbooks/session-analysis-fleet-doctor-handoff.md`](../runbooks/session-analysis-fleet-doctor-handoff.md)

## Perimetro

**Cosa NON e in scope per questa capability:**

- **In-session analysis vietata** (R-SAA-8): la capability non analizza sessioni attive.
  Qualunque integrazione in-loop e fuori perimetro e richiederebbe un nuovo ADR.
- **Auto-fix vietato** (R-SAA-3): nessuna anomalia produce una modifica automatica.
  Il loop di rimedio e sempre mediato da un agente umano o da un TSK esplicito.
- **Ingest wiki vietato** (R-SAA-4): i report non entrano nel ciclo di ingest ordinario
  della wiki. `ingest_eligible: false` e `wiki_ingest_policy: incidents-only` sono
  frontmatter obbligatori su tutti i report.
- **LLM per detection vietato** (R-SAA-10): il path `detect-anomalies.py` e puramente
  deterministico. L'LLM non partecipa alla classificazione delle anomalie.
- **Cross-sessione in v1**: la correlazione multi-sessione (tipo FLEET) e roadmap,
  non in scope in v1. Richiede un event store dedicato.
- **Modifica trascrizioni originali**: i file JSONL in `~/.claude/projects/` sono
  read-only per la capability.

## Provenienza

Questa capability e stata progettata nella **Tavola Rotonda TR-c4e8f1b2** (2026-09-08),
forced-synthesis Round 3, con 4 partecipanti (lead-architect, tpm, fleet-doctor,
Critico anti-compiacenza).

Il blackboard della Tavola Rotonda e disponibile in:
`wiki/decisions/tavola-rotonda-c4e8f1b2-7a3d-4c96-b0e5-2d9f83a1c647-2026-09-08.md`

Primary source per TSK e architettura: `management/kanban/EP-061-session-agentic-analyser/EP-061.md`

Il PATTERN.md §37 (Session Analysis Pattern) e candidato per formalizzazione futura;
al momento della stesura di questo concetto (v2.43-candidate) non e ancora incluso
nel PATTERN.md stabile.
