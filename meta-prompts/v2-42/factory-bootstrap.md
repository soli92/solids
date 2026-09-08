---
name: factory-bootstrap-v242
version: "2.42"
extends: v2-41
description: "Delta Session Observability bundle — EP-062 Fleet Telemetry Hardening (bugfix always-on) + EP-061 Session Agentic Analyser (opt-in) + PATTERN §37. Bundle release assorbe gate v2.41.0 PENDING."
gate: v2.42.0 BYPASS 2026-09-08 SLA v2.43 (3 RUN-REPORT)
backward_compat: v2.41
---

# factory-bootstrap v2.42 — delta da v2.41

> **Replicabilità**: questo file è il **delta seed** v2.42. Per la procedura completa
> di scaffolding **eredita verbatim `meta-prompts/v2-41/factory-bootstrap.md`** (vedi
> `extends:` nel frontmatter), che a sua volta eredita v2-40 → v2-39 → … → v2-13.
> v2.42 porta un unico bundle: **Session Observability** — EP-062 Fleet Telemetry
> Hardening (bugfix always-on) + EP-061 Session Agentic Analyser (opt-in). A flag
> `session_analysis.enabled: false` (default) la factory derivata è **identica a una v2.41**
> più il bugfix critico del walker `harvest-session-tokens.py`.

## §0 — Cambiamenti v2.42 vs v2.41

v2.42 **estende v2-41** (catena completa: v2-41 → v2-40 → v2-39 → … → v2-13). Eredita l'intero seed v2-41.

### Natura di v2.42: bundle Session Observability

Bundle release che chiude gate v2.41.0 PENDING (EP-060 Fleet Health, in main dal 2026-09-04)
e aggiunge due nuove capability sviluppate 2026-09-08 dopo Tavola Rotonda TR-c4e8f1b2
(forced-synthesis Round 3, 4/5 partecipanti convergenti).

Origine: `wiki/decisions/tavola-rotonda-c4e8f1b2-7a3d-4c96-b0e5-2d9f83a1c647-2026-09-08.md`

### Componente #1 — EP-062 Fleet Telemetry Hardening (bugfix always-on)

**Motivo**: `tools/analytics/harvest-session-tokens.py:52` usava `isSidechain` per
attribuire main vs subagent. Su Claude Code 2.1.258+ `isSidechain` è `false` ovunque
nel main JSONL — i sub-agenti vivono in `<session-uuid>/subagents/agent-<hash>.jsonl`
separata. Il ramo subagent non scattava mai. Token ledger EP-022 omettendo ~60%
dell'attività di flotta (fino a 134 sub-agenti su sessioni reali).

**Bugfix always-on**, nessun flag:

- **Walker fan-in** in `tools/analytics/harvest-session-tokens.py`:
  - Nuova funzione `collect_jsonl_files(transcript)` — glob `<session-uuid>/subagents/agent-*.jsonl`
  - Nuova funzione `fan_in_parse(transcript)` — aggregazione multi-file con deduplica per uuid
  - Nuovo parametro `force_scope` in `parse_transcript(path, force_scope=None)` — attribuzione
    per file-location (`main` vs `subagent`); `isSidechain` degradato a fallback retro-schema
  - Backward compat totale: se `subagents/` non esiste → walker gira come pre-fix
- **Schema-version guard** in `harvest-session-tokens.py`:
  - Costante `SUPPORTED_CC_VERSIONS = {"2.1.256", "2.1.257", "2.1.258", "2.1.263"}`
  - Funzione `detect_cc_version(path)` — fail-open su versione assente
  - WARNING su stderr + campo `schema_degraded: true` in output JSON per versioni ignote
  - MAI parsing "best effort" silenzioso (condizione Critico #2 TR)
- **Fixture reale versionata** in `tests/fixtures/transcripts/`:
  - `README.md` (documenta versione CC, provenienza, redazione applicata)
  - `cc-2.1.258-with-subagents/main.jsonl` (80 righe redatte, 0 match PII)
  - `cc-2.1.258-with-subagents/main/subagents/agent-*.jsonl` (3 file × 25 righe)
  - `cc-unsupported-version/main.jsonl`, `cc-no-version/main.jsonl`, `cc-no-subagents/main.jsonl`
    (fixture derivate minimali)
- **Contract-test** `tests/test_harvest_contract.py` (stdlib `unittest`, 7 test PASS):
  - `test_fan_in_discovers_subagents`
  - `test_scope_attribution_correct`
  - `test_supported_version_no_warning`
  - `test_unsupported_version_warning`
  - `test_missing_version_field_warning`
  - `test_backward_compat_no_subagents_dir`
  - `test_output_shape_stable`
- **`analytics/ANALYTICS-DIAGNOSIS.md`** aggiornato con sezione EP-062 + link regression test

### Componente #2 — EP-061 Session Agentic Analyser (opt-in totale, R-SAA-5)

**Motivo**: capability nuova per analisi critica post-hoc dell'attività agentica
di sessioni Claude Code chiuse. Determinism-first (rilevazione via regole, no LLM),
LLM advisory. Solo out-of-band. Zero dipendenze esterne (stdlib Python).

**Componenti**:

- **Skill** `.claude/skills/session-analysis-protocol.md` (422 righe): protocollo
  5 fasi (Bootstrap → Collect Sources → Parse & Normalize → Detect Anomalies →
  Report Generation), 10 invarianti R-SAA-1..10 referenziate per fase.
- **Comando** `.claude/commands/session-analysis.md`:
  ```
  /session-analysis [--current | --last N | <session-id>]
                    [--depth=quick|full] [--json] [--save]
  ```
  Gate `session_analysis.enabled: true` obbligatorio. Gate R-SAA-8 anti in-sessione.
- **Tool chain deterministica** in `tools/session-analysis/` (~3000 LOC, stdlib-only):
  - `__init__.py` (package marker)
  - `parse-transcript.py` (467 LOC): fan-in main+subagents, normalizzazione JSON,
    redazione R-SAA-3, gate R-SAA-8 (mtime <60s + env `CLAUDE_SESSION_ID`)
  - `fleet-metrics.py` (690 LOC): rollup per-agente/modello/wave, pricing da
    `analytics/pricing.yaml` + fallback hardcoded, `dispatch_efficiency` heuristica
  - `detect-anomalies.py` (935 LOC): 3 categorie deterministiche core enabled
    (ERROR/BUDGET/DISPATCH) + 2 opt-in roadmap (LATENCY/FLEET); PA-R3-4 risolto
    empiricamente (3 core enabled by default)
  - `generate-report.py` (981 LOC): dual md+JSON in `raw/`, 7 sezioni obbligatorie
    incluso `## Provenienza & limiti` (anti-compiacenza), frontmatter canonico
    R-SAA-5, redazione R-SAA-3, provenance R-SAA-7, `fleet_recommendations` per
    fleet-doctor con `fleet_doctor_command` popolato per subtype specifici
- **JSON Schema** `tools/session-analysis/schema-anomaly.json` (388 righe, Draft 2020-12):
  `Anomaly` + `Provenance` + `FleetRecommendation` + `AnomaliesEnvelope` +
  `SessionAnalysisReport`. `evidence_excerpt` maxLength 200 (R-SAA-3).
- **Config** `session_analysis:` in `factory.config.yaml` (default `enabled: false`, R-SAA-5):
  ```yaml
  session_analysis:
    enabled: false
    depth_default: quick
    auto_on_session_end: false
    read_transcript: false
    subagents_path: ""
    schema_version_guard: true
    anonymize_rules: [email, path, credentials]
    max_token_budget: 1000
    kill_criterion_ref: "management/kanban/EP-061-session-agentic-analyser/EP-061.md#sunset_condition"
  ```
  Il `kill_criterion_ref` NON duplica il `sunset_condition:` — punta al frontmatter EP-061.md
  come fonte unica di verità.
- **Test end-to-end** `tests/test_session_analysis_e2e.py` (10 test PASS):
  pipeline completa, schema conformance con `$defs` wrapping, R-SAA-3/5/7/8,
  kill_criterion regression, `fleet_recommendations`, anomalia BUDGET_OVERFLOW
  realmente rilevata su fixture reale (validazione empirica R-SAA-7 provenance).
- **Integrazione fleet-doctor** (§36) advisory: `fleet_doctor_command` popolato per
  subtype `SKILL_NOT_FOUND` / `DISPATCH_REDUNDANT` / `TIER_MISMATCH`. Flusso
  unidirezionale, mai auto-invoke (R-SAA-6).
- **Runbook** `wiki/runbooks/session-analysis-fleet-doctor-handoff.md` (48 righe):
  flusso advisory + anti-patterns (mai auto-invoke, mai in-sessione).
- **Wiki concept** `wiki/concepts/session-agentic-analyser.md` (200 righe,
  `status: stable`, `ingest_eligible: true`): overview, architettura, fonti dati,
  tassonomia v1, invarianti, kill criterion (link non-duplicato), integrazione
  fleet-doctor, perimetro (cosa NON è in scope), provenienza TR.

**Invarianti locali** (10 nuove, non §7 globali):

- **R-SAA-1**: read-only sul substrato sessione (mai scrittura in `~/.claude/`)
- **R-SAA-2**: confinamento scrittura in `raw/` (+ append `wiki/log.md`)
- **R-SAA-3**: redazione PII non negoziabile (path assoluti, email, credential shapes)
- **R-SAA-4**: nessun side-effect fuori da `raw/` (no rete, no git, no invocazione agenti)
- **R-SAA-5**: opt-in totale, `session_analysis.enabled: false` default
- **R-SAA-6**: nessun fix auto-applicato, mai auto-invoke fleet-doctor
- **R-SAA-7**: determinism-first + provenance obbligatoria (anti-fabbricazione)
- **R-SAA-8**: solo out-of-band su sessioni chiuse (mai in-sessione, mai self-analysis)
- **R-SAA-9**: schema-version guard obbligatorio, WARNING fail-loud su ignoto
- **R-SAA-10**: `kill_criterion` + `sunset_condition:` pre-codice nel frontmatter TSK EP

### Componente #3 — PATTERN §37 «Session Observability»

Nuovo pattern agent-agnostic formalizzato in `PATTERN.md §37`. 8 principi fondanti,
architettura di riferimento thin-agent/fat-skill/deterministic-tools (§29),
tassonomia anomalie deterministica, boundary con altri layer (Token Ledger,
Analytics, Fleet Doctor, CQRL, Wiki Keeper).

### Kill criterion §23.8 (attivo, hard)

Nel frontmatter di `management/kanban/EP-061-session-agentic-analyser/EP-061.md`:

- Anomalie rilevate <3% su 20 sessioni consecutive / 30 giorni → sunset
- False positive rate >35% su 3 sprint → sunset
- >1 TSK di fix per sprint per 2 sprint consecutivi → sunset
- **Hard sunset v2.44**: se ≥5 anomalie azionabili con TSK reale non emergono → sunset automatico senza bypass

## §1 — Trigger da applicare in factory derivata

### Fase A — EP-062 Fleet Telemetry Hardening (always-on, bugfix)

Scaffolding **automatico**, senza flag. In una factory derivata già v2.41:

1. Aggiorna `tools/analytics/harvest-session-tokens.py` con walker fan-in +
   schema-guard. Se il file è personalizzato → CONFLICT esplicito (mai auto-merge).
2. Crea `tests/fixtures/transcripts/cc-2.1.258-with-subagents/` con fixture del
   proprio adapter (se la factory non usa Claude Code, il maintainer produce
   la fixture equivalente).
3. Crea `tests/test_harvest_contract.py` (7 test).
4. Aggiorna `analytics/ANALYTICS-DIAGNOSIS.md` con sezione EP-062.
5. Verifica: `python3 -m unittest tests/test_harvest_contract.py -v` PASS.

### Fase B — EP-061 Session Agentic Analyser (opt-in, R-SAA-5)

A flag `session_analysis.enabled: false` (default) la factory è invariata rispetto
a v2.41. Per attivare:

1. Aggiungi blocco `session_analysis:` a `factory.config.yaml` (vedi §0).
2. Bumpa `session_analysis.enabled: true`.
3. Scaffolda skill + comando + tool chain + schema JSON (vedi §0).
4. Verifica precondizione: EP-062 done (Fase A) + `test_harvest_contract.py` PASS.
5. Prima invocazione: `/session-analysis --last 1 --save --json` su sessione chiusa.

## §2 — Backward compatibility

- **EP-062**: bugfix trasparente. Se `subagents/` non esiste → walker gira come pre-fix.
  Nessuna breaking change.
- **EP-061**: opt-in totale. `session_analysis.enabled: false` (default) → factory
  identica a v2.41. Nessun impatto se non attivata.

## §3 — Adapter portability

Il pattern §37 è agent-agnostic. Il walker in `tools/analytics/harvest-session-tokens.py`
è specifico a Claude Code (schema JSONL 2.1.258+). Adapter diversi (Cursor, Aider…)
devono fornire il proprio walker equivalente che rispetti il contratto:

- **Input**: path a transcript principale della sessione
- **Output**: JSON normalizzato con attribuzione `main` vs `subagent`, campi
  `usage` (input/output/cache), `timestamp`, `stop_reason`, `attribution_agent`
- **Fail-open**: righe malformate skippate, mai crash
- **Schema-guard**: WARNING fail-loud su versioni ignote

La skill `session-analysis-protocol.md` invoca il walker come contratto — è
riusabile cross-adapter senza modifiche.

## §4 — Assorbimento gate v2.41.0 PENDING

Il gate v2.41.0 EP-060 Fleet Health era **PENDING** dal 2026-09-04 (mai taggato).
v2.42.0 lo assorbe:

- Il codice EP-060 è già in main dal 2026-09-04
- L'entry `[v2.41.0]` in `CHANGELOG.md` rimane per continuità cronologica
  ma non ha tag separato
- Il tag `v2.42.0` include tutto il diff da `v2.40.0` (che era l'ultimo taggato)

Per factory derivate già a v2.41 (senza tag): nessuna azione, l'upgrade a v2.42
è additivo.

## §5 — Gate v2.42.0

**BYPASS** documentato (SLA: 3 RUN-REPORT entro v2.43).

Rationale del bypass:

- EP-062 è **bugfix critico** di un tool in produzione da >8 versioni (silent bug
  in `harvest-session-tokens.py`). L'urgenza del fix supera il costo di 3
  RUN-REPORT preliminari, che tra l'altro fallirebbero sotto lo stesso bug.
- EP-061 è **opt-in totale** (default off). Il rischio d'esercizio è zero per
  factory che non lo attivano.
- Battle-test evidence esistente:
  - 7/7 test EP-062 PASS su fixture reale
  - 10/10 test e2e EP-061 PASS su fixture reale
  - 1 anomalia reale BUDGET_OVERFLOW rilevata su fixture (validazione empirica R-SAA-7)
  - Dogfood in-flight: dopo TSK-545 il ledger conta correttamente 12+ sub-agenti live

Precedente identico: v2.38.0 BYPASS 2026-08-24 (SLA rispettata in v2.39).

## §6 — Riferimenti

- **Blackboard TR**: `wiki/decisions/tavola-rotonda-c4e8f1b2-7a3d-4c96-b0e5-2d9f83a1c647-2026-09-08.md`
- **CHANGELOG entry**: `CHANGELOG.md#v2420`
- **PATTERN §37**: `PATTERN.md#§37-session-observability`
- **Kanban EP-062**: `management/kanban/EP-062-fleet-telemetry-hardening/`
- **Kanban EP-061**: `management/kanban/EP-061-session-agentic-analyser/`
- **Wiki concept**: `wiki/concepts/session-agentic-analyser.md`
- **Runbook handoff fleet-doctor**: `wiki/runbooks/session-analysis-fleet-doctor-handoff.md`
- **Test EP-062**: `tests/test_harvest_contract.py`
- **Test EP-061**: `tests/test_session_analysis_e2e.py`
