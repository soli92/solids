---
skill: session-analysis-protocol
version: "1.0"
description: >
  Protocollo 5 fasi per analisi critica post-hoc dell'attivita agentica di
  una sessione Claude Code chiusa. Determinism-first, LLM advisory. Solo
  out-of-band. Produce report dual md+JSON in raw/.
owner: session-analyst (roadmap v2; v1: invocabile da qualsiasi agente su delega)
depends_on_tools:
  - tools/session-analysis/parse-transcript.py
  - tools/session-analysis/fleet-metrics.py
  - tools/session-analysis/detect-anomalies.py
opt_in: session_analysis.enabled
pattern_version: "2.41"
epic: EP-061
traceability_source: wiki/decisions/tavola-rotonda-c4e8f1b2-7a3d-4c96-b0e5-2d9f83a1c647-2026-09-08.md
---

# Session Analysis Protocol — analisi critica post-hoc dell'attivita agentica

## Scopo e contesto

Questa skill analizza una sessione Claude Code **chiusa** per rilevare anomalie
deterministiche nell'attivita degli agenti: dispatch ridondanti, sforamenti di
budget, loop di errore, latenza anomala, mismatch di versione skill, gate
bypassati. Non sostituisce `/lint` (analisi statica wiki) ne l'analytics-reporter
(writer time-series): e un lettore episodico post-hoc, ortogonale a entrambi.

**Quando invocarla**: solo dopo la chiusura di una sessione, su richiesta esplicita
(`/session-analysis`) o via hook `auto_on_session_end: true` (solo tool deterministici,
nessuna chiamata LLM alla chiusura automatica).

**Quando NON invocarla**:
- Mai durante una sessione attiva (R-SAA-8 — race condition su file open+append).
- Mai su sessioni per cui `session_analysis.enabled: false` (R-SAA-5).
- Mai come sostituto di un'analisi architettuale (usa Tavola Rotonda o lead-architect).

**Relazione con analytics-reporter**: i due agenti sono reader/writer ortogonali su
`analytics/events/`. analytics-reporter e writer della time-series economico-progettuale;
session-analysis-protocol e reader episodico (DAG → concorrenza → anomalie). Nessun
conflitto di ownership, nessun nuovo silo di dati.

---

## Fase 0 — Bootstrap

### Input
- `session_id` target: stringa opzionale (default `--last 1`), oppure flag `--current`
  (che attiva il gate R-SAA-8 con STOP immediato).
- Blocco `session_analysis:` di `factory.config.yaml`.

### Output
- Config risolta: `depth`, `max_token_budget`, `anonymize_rules`, `transcript_path`,
  `subagents_path`, `schema_version_guard`, `kill_criterion`.
- `session_id` normalizzato (formato `YYYY-MM-DD-HHmmss` o hash UUID).
- Contesto pronto per Fase 1.

### Gate

**R-SAA-5 (opt-in)**: verifica `session_analysis.enabled: true` in `factory.config.yaml`.
Se `false` o chiave assente → STOP con messaggio:
```
STOP: session_analysis.enabled = false (default off).
Abilitare in factory.config.yaml per usare questa skill.
```

**R-SAA-8 (out-of-band — CRITICO)**:
- Se il chiamante passa `--current` OPPURE se `session_id` coincide con la sessione
  attiva corrente → **STOP IMMEDIATO** con errore esplicito:
  ```
  STOP: analisi in-session vietata (R-SAA-8).
  I file subagents/agent-*.jsonl sono open+append durante l'esecuzione;
  una lettura in-session produce race condition e partial JSON.
  Invocare /session-analysis su una sessione gia chiusa.
  ```
- La verifica si fa confrontando `session_id` con il metadata della sessione corrente
  (campo `session_closed: true` nel metadata JSONL, oppure assenza del processo attivo).
  In caso di dubbio → STOP per sicurezza.

**R-SAA-3 (budget)**: verifica che `session_analysis.max_token_budget` sia valorizzato.
Se assente → imposta default conservativo (1000 token). Log WARNING se budget < 500.

### Tool invocato
Legge `factory.config.yaml` blocco `session_analysis:`. Nessuno script Python in questa
fase (solo config read).

### Invarianti applicabili
- **R-SAA-5**: `session_analysis.enabled: true` obbligatorio prima di procedere.
- **R-SAA-8**: mai analizzare la sessione corrente attiva — gate fail-closed.
- **R-SAA-3**: bounded token budget verificato all'avvio.

---

## Fase 1 — Collect Sources

### Input
- `session_id` normalizzato (da Fase 0).
- Config risolta (da Fase 0): `transcript_path`, `subagents_path`, `read_transcript`.

### Output
- Manifest fonti: lista di path verificati:
  - JSONL principale: `<transcript_path>/<session_uuid>.jsonl`
  - Sub-agenti: glob `<session_uuid>/subagents/agent-*.jsonl` (fan-in EP-062)
  - Fonti correlazione opt-in: `analytics/events/`, `wiki/log.md`,
    `memory/episodic/wave-*.md`, `code_quality/reports/` (solo se abilitato in config)
- Conteggio file trovati per tipo (main: N, subagents: M).

### Gate
Le fonti primarie (JSONL main + almeno un file subagents/) devono esistere e essere
leggibili. Se il main JSONL manca → STOP con path non trovato. Se la directory
subagents/ e vuota → WARNING (analisi degradata, solo main), ma continua.

### Tool invocato
Reuse walker fan-in EP-062:
`tools/analytics/harvest-session-tokens.py` — funzione `collect_jsonl_files`
(riparata in EP-062 per gestire `subagents/agent-*.jsonl` su Claude Code 2.1.258+).

**Nota**: il walker fan-in EP-062 e il prerequisito tecnico verificato (TSK-549 DONE).
Senza quella riparazione il fan-in omette il 60%+ dell'attivita (tutti i sub-agenti).

### Invarianti applicabili
- **R-SAA-1**: read-only — nessuna scrittura nelle fonti, nessuna modifica a
  `~/.claude/` o ai transcript.
- **R-SAA-4**: nessun side-effect fuori da `raw/` — questa fase non scrive nulla.

---

## Fase 2 — Parse & Normalize

### Input
- Manifest fonti (da Fase 1): lista di path JSONL (main + subagents/).

### Output
- JSON normalizzato: lista di eventi strutturati secondo lo schema definito in
  `tools/session-analysis/parse-transcript.py` (TBD — TSK-551).
  Schema atteso per ogni evento:
  ```json
  {
    "event_id": "<uuid>",
    "session_id": "<slug>",
    "timestamp": "<ISO8601>",
    "source": "main|subagent",
    "agent_slug": "<slug-or-null>",
    "event_type": "tool_use|tool_result|assistant|user",
    "tool_name": "<name-or-null>",
    "model": "<model-id-or-null>",
    "usage": {"input_tokens": 0, "output_tokens": 0},
    "is_error": false,
    "content_digest": "<sha256-first-8>",
    "redacted": true
  }
  ```

### Gate
**Schema-version guard (R-SAA-9)**:
- Il parser verifica il campo `cc_version` (o equivalente) nel JSONL prima di parsare.
- Versione nota (set `SUPPORTED_CC_VERSIONS` in parse-transcript.py) → parsing normale.
- Versione ignota → modalita degradata con WARNING esplicito:
  ```
  WARNING: Claude Code version <X> non nel set SUPPORTED_CC_VERSIONS.
  Parsing in modalita best-effort. Risultati potrebbero essere incompleti.
  ```
  Il protocollo **continua** (fail-open su versione ignota) ma il caveat viene
  propagato nel frontmatter del report (`schema_degraded: true`).

**Nota**: parsing silenzioso di versione ignota e vietato (R-SAA-9).

### Tool invocato
`tools/session-analysis/parse-transcript.py` (TBD — TSK-551).

### Invarianti applicabili
- **R-SAA-3**: redazione applicata durante il parsing — solo digest dei contenuti,
  MAI corpi completi di `tool_result` o file; snippet-evidenza capati a
  `evidence_max_chars`. Se `redaction.enabled: false` nel config → WARNING fail-loud.
- **R-SAA-9**: schema-version guard — mai parsing silenzioso di versione ignota.

---

## Fase 3 — Detect Anomalies

### Input
- JSON eventi normalizzati (da Fase 2).
- Config soglie: `max_token_budget`, categorie abilitate, thresholds per categoria.

### Output
- Lista anomalie strutturata:
  ```json
  [
    {
      "id": "ANO-001",
      "category": "BUDGET|DISPATCH|ERROR|LATENCY|FLEET|GOVERNANCE",
      "severity": "critical|warning|info",
      "wave": "<wave-id-or-null>",
      "evidence_snippet_redacted": "<testo-breve-redatto>",
      "fix_suggestion": "<testo-azione-concreta>",
      "pattern_eligible": true,
      "evidence_count": 3,
      "provenance": "<campo-jsonl-sorgente>"
    }
  ]
  ```
- Se nessuna regola scatta → output = lista vuota `[]`. Questo e valido (nessun
  risultato non implica un errore del protocollo).

### Gate
Nessun gate bloccante in questa fase: il rilevamento e puramente deterministico.
Se tutte le regole producono zero match → output lista vuota, continua a Fase 4.

**Tassonomia v1 (scope da confermare in scaffolding EP-061)**:
Consenso Tavola Rotonda su determinism-first + no LLM in v1. Le categorie candidate
(BUDGET, DISPATCH, ERROR, LATENCY, FLEET, GOVERNANCE) coprono il lead-architect;
il sottoinsieme minimalista (ERROR, BUDGET, DISPATCH) e la proposta Critico.
La regola di risoluzione: chi implementa EP-061 misura empiricamente con fixture
reali quale sottoinsieme ha signal/noise ratio >= soglia (>3 anomalie azionabili per
20 sessioni, coerente con kill criterion §23.8), e ferma la tassonomia li.

### Tool invocato
- `tools/session-analysis/fleet-metrics.py` (TBD — TSK-553): calcola metriche
  aggregate (token totali main+sub, latency per wave, dispatch count per agente).
- `tools/session-analysis/detect-anomalies.py` (TBD — TSK-554): applica le regole
  deterministiche sugli eventi normalizzati e sulle metriche aggregate; produce la
  lista anomalie strutturata.

### Invarianti applicabili
- **R-SAA-7**: determinismo-first + anti-fabbricazione. Ogni anomalia nel report
  deve tracciare a un campo specifico dell'output di un tool (`provenance`). Se
  una metrica manca di provenance → WARNING fail-loud, anomalia esclusa dal report.
  LLM non partecipa alla detection: interpreta solo aggregati nella Fase 4 (advisory).
- **R-SAA-6**: nessun fix auto-applicato — ogni entry `fix_suggestion` e testuale
  con riferimento al file da modificare; l'azione e sempre umana o delegata
  esplicitamente a fleet-doctor (con i propri gate G1-G11).

---

## Fase 4 — Report Generation

### Input
- Lista anomalie strutturata (da Fase 3).
- Metriche aggregate (da Fase 3 / fleet-metrics.py).
- Config: `depth`, `factory_version`, `session_id`, `span`.

### Output
Dual format obbligatorio in `raw/`:
- `raw/YYYY-MM-DD-session-analysis-<id-8char>.md` — markdown human-readable
- `raw/YYYY-MM-DD-session-analysis-<id-8char>.json` — JSON machine-readable

**Frontmatter canonico** (markdown — obbligatorio, non modificabile):
```yaml
---
type: session-analysis-report
session_id: <timestamp-slug>
depth: quick|full
span: <descriptor>
generated_at: <ISO8601>
factory_version: <pattern_version>
anomaly_count: <int>
worst_severity: critical|warning|info|none
ingest_eligible: false
wiki_ingest_policy: incidents-only
ttl_days: 90
schema_degraded: false
---
```

**Sezioni obbligatorie** del report markdown:
1. `## Executive Summary` — metriche chiave: wave analizzate, task count, anomalie
   per severity, costo sessione, dispatch efficiency score.
2. `## Anomalie Rilevate` — tabella:
   `| ID | Categoria | Severity | Wave | Descrizione | Fix proposto |`
   Ogni riga include `pattern_eligible: si|no` e `evidence_count: N`.
3. `## Metriche Sessione` — token in/out/cost (main + subagent separati),
   latency summary, model tier usage.
4. `## Fix Proposti` — lista ordinata per severity, ogni fix con file da modificare
   + azione concreta + effort stimato.
5. `## Punti Aperti` — anomalie non classificabili deterministicamente, richiedono
   giudizio umano.
6. `## Limiti dell'Analisi` — obbligatorio (anti-compiacenza, R.SA-Critic interiorizzato):
   documenta esplicitamente cosa questo report NON ha potuto rilevare (es. errori
   semantici nel contenuto tool_result, ragionamento scorretto dell'agente,
   side-effect esterni non tracciati).

**Fleet-doctor handoff** (campo JSON):
```json
{
  "fleet_recommendations": [
    {
      "anomaly_id": "ANO-001",
      "skill_affected": "<slug>",
      "recommendation": "<testo-azione>",
      "priority": "high|medium|low",
      "fleet_doctor_command": "/fleet-doctor check-skill <slug>"
    }
  ]
}
```

Append `wiki/log.md`: una riga `develop | session-analysis done — raw/<filename>.md`.

### Gate

**R-SAA-3 (redazione prima della scrittura)**: verificare che nessun body di
`tool_result` o contenuto file completo sia presente negli snippet-evidenza prima
di scrivere su disco. Se la verifica fallisce → STOP, non scrivere il report.

**R-SAA-2 (confinamento)**: la scrittura avviene SOLO in:
- `raw/YYYY-MM-DD-session-analysis-<id>.md`
- `raw/YYYY-MM-DD-session-analysis-<id>.json`
- Append `wiki/log.md`
Nessuna scrittura altrove (no rete, no git, no modifica a `.claude/` o `memory/`).

**R-SAA-5 (ingest_eligible: false)**: il frontmatter `ingest_eligible: false` e
`wiki_ingest_policy: incidents-only` devono essere presenti nel report scritto.
Il wiki-keeper interpreta questi campi come skip totale (contratto EP-061 / Round 1).

**R-SAA-10 (kill criterion)**: se il blocco `session_analysis.kill_criterion` non e
valorizzato in `factory.config.yaml` → WARNING nel report (campo `kill_criterion_declared:
false`). Non blocca la scrittura ma segnala l'assenza della soglia di sunset §23.8.

### Tool invocato

`tools/session-analysis/generate-report.py` (TSK-556 DONE):

```
python3 tools/session-analysis/generate-report.py \
  <anomalies-json> <metrics-json> <parsed-json> \
  [--output-dir raw/] \
  [--session-id-short <id-8char>] \
  [--depth quick|full] \
  [--span <descriptor>] \
  [--dry-run]
```

**Step dettagliati**:

1. **Carica i tre input**: anomalies-json (output detect-anomalies.py, struttura
   `AnomaliesEnvelope`), metrics-json (output fleet-metrics.py, struttura con
   `session_totals` + `dispatch_efficiency`), parsed-json (output parse-transcript.py,
   struttura `{meta, records}`).

2. **Risolve session_id e span**: da `parsed.meta.session_id` (primi 8 char come
   `session_id_short`). Override via `--session-id-short` e `--span`.

3. **Legge factory_version** da `factory.config.yaml` (campo `pattern_version`) via
   walk-up dal path dello script. Fallback documentato `"2.41"` se non trovato.

4. **Applica redazione R-SAA-3** su tutte le anomalie e i valori stringa prima della
   scrittura: `/Users/<name>/` → `/Users/USER/`, email → `user@example.com`,
   credenziali (`sk-*`, `Bearer *`, `*_TOKEN=*`) → `[REDACTED_CREDENTIAL]`.
   Verifica invariante `evidence_excerpt` cap 200 char.

5. **Deriva `fleet_recommendations`**: per ogni anomalia con categoria FLEET/DISPATCH/BUDGET,
   inferisce `skill_affected` via regex su evidence_excerpt/attribution_agent/fix_suggestion;
   mappa severity → priority (critical→high, warning→medium, info→low);
   `fleet_doctor_command: null` in v1 (TSK-558 lo popola).

6. **Costruisce il report JSON** conforme a `tools/session-analysis/schema-anomaly.json`
   def `SessionAnalysisReport` (additionalProperties: false):
   - `ingest_eligible: false` — invariante R-SAA-5, hardcoded, non-bypassabile.
   - `wiki_ingest_policy: "incidents-only"`.
   - `session_metrics` da `session_totals` + `dispatch_efficiency.score`.
   - Validazione via `jsonschema` se disponibile; skip con WARNING se non installato.

7. **Costruisce il report Markdown** con frontmatter canonico e 7 sezioni obbligatorie:
   1. `## Executive Summary` — wave/record/anomalie per severity/costo/efficiency
   2. `## Anomalie Rilevate` — tabella ID/Categoria/Subtype/Severity/Wave/Agent/Fix/Evidence
   3. `## Metriche Sessione` — token in/out/cache/costo/efficiency con colonna Provenance
   4. `## Fix Proposti` — lista ordinata critical→warning→info con provenance R-SAA-7
   5. `## Punti Aperti` — anomalie non completamente deterministiche (LLM advisory ammesso)
   6. `## Perimetro analizzato` — cosa incluso/escluso, categorie abilitate/disabilitate
   7. **`## Provenienza & limiti`** — sezione anti-compiacenza obbligatoria (R-SAA-Critic):
      categorie non abilitate + motivo; limiti detector (es. ERROR_LOOP su regex testuale
      non is_error flag); cosa il report NON può dire; dipendenze e rischi noti.

8. **Gate R-SAA-3 post-build**: verifica che nessun path `/Users/<name>/`, `sk-*`,
   `Bearer *` sia sopravvissuto alla redazione. Se trovato → STOP, report non scritto.

9. **Scrittura** (R-SAA-2): solo in `<output-dir>/`:
   - `YYYY-MM-DD-session-analysis-<id-8char>.md`
   - `YYYY-MM-DD-session-analysis-<id-8char>.json`
   - Nessun'altra scrittura (no `.claude/`, no `memory/`, no git).

**Referenza schema**: `tools/session-analysis/schema-anomaly.json` def
`SessionAnalysisReport` — fonte autoritativa per i campi del JSON report.

**`--dry-run`**: stampa entrambi i file su stdout senza scrivere su disco.

### Invarianti applicabili
- **R-SAA-2**: confinamento scrittura a `raw/` + append `wiki/log.md` — nient'altro.
- **R-SAA-3**: redazione applicata e verificata prima di ogni scrittura su disco.
- **R-SAA-5**: `ingest_eligible: false` — invariante frontmatter non bypassabile.
- **R-SAA-10**: kill criterion nel frontmatter TSK EP-061 — WARNING se assente nel config.

---

## Invarianti (R-SAA-1..10)

Referenza rapida. Le invarianti in **grassetto** sono enforce attivo da una fase specifica.

| ID | Sintesi | Fase(i) |
|---|---|---|
| R-SAA-1 | Read-only sul substrato sessione: mai scrivere in `~/.claude/`, mai modificare transcript. | **Fase 1** |
| R-SAA-2 | Confinamento scrittura: solo `raw/` (naming Sync-family) + append `wiki/log.md`. | **Fase 4** |
| R-SAA-3 | Redazione non negoziabile: solo metadati/digest, MAI corpi tool_result o file; snippet capati a `evidence_max_chars`. `redaction.enabled: false` = WARNING fail-loud. | **Fase 2**, **Fase 4** |
| R-SAA-4 | Nessun side-effect fuori da `raw/`: no rete, no git, no invocazione agenti che scrivono. | **Fase 1** |
| R-SAA-5 | Opt-in gated: `session_analysis.enabled: false` default; assenza config = no-op. Report ha `ingest_eligible: false` invariante. | **Fase 0**, **Fase 4** |
| R-SAA-6 | Nessun auto-fix: raccomandazioni testuali con riferimento file; azione sempre umana o delegata a fleet-doctor (gate G1-G11). | **Fase 3** |
| R-SAA-7 | Determinismo-first + anti-fabbricazione: ogni metrica traccia a un campo di output tool (`provenance`); fail-loud se metrica manca di provenance. LLM solo advisory su aggregati. | **Fase 3** |
| R-SAA-8 | Solo out-of-band su sessioni chiuse: mai in-session, mai analisi della sessione corrente attiva — STOP fail-closed. | **Fase 0** |
| R-SAA-9 | Schema-version guard: parsing silenzioso di versione Claude Code ignota vietato; versione ignota = modalita degradata esplicita con caveat propagato al report. | **Fase 2** |
| R-SAA-10 | Kill criterion + `sunset_condition:` obbligatori nel frontmatter TSK EP-061; soglie fleet-doctor formalizzate; hard sunset v2.44 senza bypass. | **Fase 4** (WARNING se assente) |

---

## Cross-link

- `.claude/commands/session-analysis.md` — comando `/session-analysis` (TBD — TSK-552)
- `tools/session-analysis/parse-transcript.py` — parser JSONL normalizzatore (TBD — TSK-551)
- `tools/session-analysis/fleet-metrics.py` — calcolo metriche aggregate (TBD — TSK-553)
- `tools/session-analysis/detect-anomalies.py` — rilevamento anomalie deterministico (TBD — TSK-554)
- `tools/analytics/harvest-session-tokens.py` — walker fan-in EP-062 (riparato TSK-549 DONE)
- `management/kanban/EP-061-session-agentic-analyser/EP-061.md` — kill_criterion §23.8
- `wiki/decisions/tavola-rotonda-c4e8f1b2-7a3d-4c96-b0e5-2d9f83a1c647-2026-09-08.md` — blackboard TR autoritativo (sintesi finale + 10 invarianti)
