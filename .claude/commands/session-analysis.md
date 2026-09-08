---
command: /session-analysis
skill: session-analysis-protocol
opt_in: session_analysis.enabled
epic: EP-061
pattern_version: "2.41"
---

# /session-analysis

Argomenti utente: `$ARGUMENTS`

Analisi critica post-hoc dell'attivita' agentica di una sessione Claude Code chiusa.
Determinism-first: tool Python stdlib per detection; LLM advisory opzionale solo in
Fase 4 (depth=full). Solo out-of-band su sessioni gia' chiuse (R-SAA-8).

---

## Sintassi

```
/session-analysis [--current | --last N | <session-id>]
                  [--since <ts>]
                  [--depth=quick|full]
                  [--json]
                  [--save]
```

| Flag | Tipo | Default | Semantica |
|---|---|---|---|
| `--current` | flag | assente | Seleziona la sessione corrente — STOP per R-SAA-8 (race condition) |
| `--last N` | intero >= 1 | assente | Analizza l'N-esima sessione piu' recente (N=1 = ultima chiusa) |
| `<session-id>` | stringa | assente | ID sessione esplicito (timestamp-slug o UUID parziale) |
| `--since <ts>` | ISO8601 / "Nd" | assente | Filtra sessioni piu' recenti di `<ts>` (es. `--since 2026-09-01`, `--since 7d`) |
| `--depth=quick\|full` | enum | config `depth_default` | `quick` = solo Fasi 1-3 (deterministico); `full` = anche Fase 4 (LLM advisory, budget bounded) |
| `--json` | flag | assente | Emette il report JSON su stdout invece della sintesi human-readable |
| `--save` | flag | assente | Salva il report in `raw/` (dual md+json); stampa il path generato |

---

## Procedura

### Step 0 — Gate `session_analysis.enabled`

Leggi `factory.config.yaml` e controlla il flag:

```
SE factory.config.yaml.session_analysis.enabled == false (default opt-in):
  STOP — non invocare la skill, nessun side-effect.
  Emetti in chat:
    "EP-061 Session Agentic Analyser non abilitato.
     Aggiungi `session_analysis.enabled: true` in factory.config.yaml per attivare.
     Leggi CLAUDE.md §session_analysis e PATTERN §37 per prerequisiti e kill criterion."
```

Se `session_analysis.enabled: true`, prosegui.

### Step 1 — Parse argomenti + validazione

Dall'input `$ARGUMENTS` estrai:

- `flag_current` — `true` se `--current` presente, altrimenti `false`
- `flag_last_n` — valore intero di `--last N` se presente, altrimenti `null`
- `session_id` — primo token non-flag non-keyword se presente, altrimenti `null`
- `flag_since` — valore stringa di `--since` se presente, altrimenti `null`
- `flag_depth` — valore di `--depth` se presente, altrimenti leggi `factory.config.yaml.session_analysis.depth_default` (default: `quick`)
- `flag_json` — `true` se `--json` presente, altrimenti `false`
- `flag_save` — `true` se `--save` presente, altrimenti `false`

Validazioni:

- Se piu' di un selettore (`--current`, `--last N`, `<session-id>`) presenti: STOP —
  «Specificare al piu' un selettore: `--current`, `--last N`, o `<session-id>`.»
- Se nessun selettore e nessun `session_id`: STOP —
  «Selettore mancante. Esempi: `/session-analysis --last 1`, `/session-analysis --last 3 --since 7d`»
- Se `--last N` valorizzato e N <= 0: STOP —
  «`--last N` richiede N >= 1. Ricevuto: `<N>`.»
- Se `--depth` valorizzato e valore non in `{quick, full}`: STOP —
  «Valore --depth non valido: `<v>`. Valori ammessi: `quick`, `full`.»
- Se `--since` valorizzato: verifica che sia una data ISO8601 valida o un descrittore `Nd` (N intero >= 1). Se non valido: STOP —
  «`--since` non valido: `<v>`. Formati accettati: `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM:SS`, `Nd` (es. `7d`).»

### Step 2 — Gate R-SAA-8 (out-of-band)

Se `flag_current == true`:

```
STOP — In-session analysis vietata (R-SAA-8, race condition su subagents/*.jsonl in append).
Attenzione: la sessione corrente non puo' essere analizzata mentre e' aperta.
Motivo: i file subagents/*.jsonl sono open+append durante l'esecuzione —
        leggere una sessione aperta produce report incompleti e potenzialmente corrotti.
Azione: Attendi la chiusura della sessione, poi esegui:
        /session-analysis --last 1
```

### Step 3 — Invocazione skill `session-analysis-protocol`

Invoca la skill `.claude/skills/session-analysis-protocol.md` passando il payload:

```yaml
selector:
  type: last_n | session_id | all
  value: <N> | <session-id> | null
since: <ts> | null
depth: quick | full
output:
  json: <true|false>
  save: <true|false>
config:
  subagents_path: <factory.config.yaml.session_analysis.subagents_path>
  schema_version_guard: <factory.config.yaml.session_analysis.schema_version_guard>
  anonymize_rules: <factory.config.yaml.session_analysis.anonymize_rules>
  max_token_budget: <factory.config.yaml.session_analysis.max_token_budget>
  read_transcript: <factory.config.yaml.session_analysis.read_transcript>
```

La skill esegue:

| Fase | Nome | Azione |
|---|---|---|
| 0 | Bootstrap | Verifica prerequisiti (EP-062 walker, schema version, config) |
| 1 | Collect Sources | Fan-in main+subagents JSONL per la sessione selezionata |
| 2 | Parse & Normalize | Normalizzazione eventi, redazione anonimizzazione |
| 3 | Detect Anomalies | Tool deterministici (`fleet-metrics.py`, `detect-anomalies.py`) |
| 4 | Report Generation | Sintesi (quick: skip LLM; full: LLM advisory bounded) |

### Step 4 — Output

**Se `--json`**: emetti il JSON del report su stdout (il campo `ingest_eligible` e' sempre `false`, R-SAA-5).

**Se `--save`**: salva i report in `raw/`:
- `raw/YYYY-MM-DD-session-analysis-<id-8char>.md` — markdown human-readable
- `raw/YYYY-MM-DD-session-analysis-<id-8char>.json` — JSON machine-readable

Stampa in chat:
```
Report salvato:
  raw/YYYY-MM-DD-session-analysis-<id-8char>.md
  raw/YYYY-MM-DD-session-analysis-<id-8char>.json
```

**Altrimenti (default)**: sintesi human-readable in-chat:

```
SESSION ANALYSIS — <session-id-slug> (<depth>)
=============================================
Span           : <descrittore>
Anomalie       : <N> (<severity peggiore>)
Token          : in=<Xk>  out=<Yk>  cost=$<Z>
Dispatch eff.  : <pct>%

Anomalie principali:
  [CRITICAL] <ID>  <categoria>  wave <W>: <descrizione breve>
  [WARNING]  <ID>  <categoria>  wave <W>: <descrizione breve>

Per il report completo: /session-analysis --last N --save
```

Se `anomaly_count == 0`:
```
Nessuna anomalia rilevata (depth=<depth>).
Sessione <session-id-slug> analizzata — <N> eventi, <M> wave.
```

---

## Esempi d'uso

```bash
# Analizza l'ultima sessione chiusa (quick, solo output in-chat)
/session-analysis --last 1

# Analizza le 3 sessioni piu' recenti con report full salvato in raw/
/session-analysis --last 3 --depth=full --save

# Analizza sessioni degli ultimi 7 giorni, output JSON su stdout
/session-analysis --last 1 --since 7d --json

# Analisi con ID sessione esplicito (timestamp-slug o UUID parziale)
/session-analysis 20260908-a1b2c3d4 --depth=full --save

# Quick analysis dell'ultima sessione, risultato JSON (machine-readable)
/session-analysis --last 1 --json

# Tentativo su sessione corrente — bloccato da R-SAA-8
/session-analysis --current
# → STOP: In-session analysis vietata (R-SAA-8, race condition su subagents/*.jsonl)
```

---

## Vincoli

- **Solo su sessioni chiuse (R-SAA-8)**: l'analisi in-session non e' supportata.
  I file `subagents/*.jsonl` sono open+append durante l'esecuzione — analisi
  in-session produrrebbe report incompleti e potenzialmente corrotti.
- **No auto-fix (R-SAA-6)**: il comando produce raccomandazioni testuali con
  riferimento file. L'azione e' sempre umana o delegata esplicitamente a
  `fleet-doctor` (gate G1-G11 invarianti).
- **Report `ingest_eligible: false` (R-SAA-5)**: i report generati in `raw/`
  hanno il campo `ingest_eligible: false` nel frontmatter. `wiki-keeper` skippa
  totalmente questi file. Invariante non bypassabile.
- **Bounded token budget (R-SAA-3)**: il budget LLM e' limitato da
  `session_analysis.max_token_budget` (default: 1000 token). In modalita' `quick`
  non viene invocato nessun LLM (determinism-first). In `full`, il budget e' hard cap.
- **Read-only sul substrato sessione (R-SAA-1)**: nessuna scrittura in
  `~/.claude/`. Scrittura confinata a `raw/` e append `wiki/log.md` (R-SAA-2).
- **Schema version guard obbligatorio (R-SAA-9)**: se la versione dello schema
  JSONL della sessione e' sconosciuta, la skill entra in modalita' degradata
  esplicita e non fallisce silenziosamente.

---

## Prerequisiti

- `session_analysis.enabled: true` in `factory.config.yaml` (default: `false`, opt-in)
- EP-062 Fleet Telemetry Hardening done (walker subagent-aware verificato con contract-test)
- `.claude/skills/session-analysis-protocol.md` presente (TSK-550 done)
- Tool Python stdlib-only in `tools/session-analysis/`:
  - `parse-transcript.py` — fan-in main+subagents, normalize (TSK-551)
  - `fleet-metrics.py` — rollup per-agente/modello/wave (TSK-553)
  - `detect-anomalies.py` — regole deterministiche v1 (TSK-554)
- Python 3.9+ con `json`, `pathlib`, `argparse` (stdlib, zero dipendenze esterne)

---

## Cross-link

- **Skill**: `.claude/skills/session-analysis-protocol.md` (TSK-550, EP-061 US-243)
- **Tool**: `tools/session-analysis/parse-transcript.py` (TSK-551), `fleet-metrics.py` (TSK-553), `detect-anomalies.py` (TSK-554)
- **Kill criterion**: `management/kanban/EP-061-session-agentic-analyser/EP-061.md#sunset_condition`
  (§23.8 — hard sunset v2.44 se <5 anomalie azionabili con TSK reale; bypass: false)
- **Blackboard TR**: `wiki/decisions/tavola-rotonda-c4e8f1b2-7a3d-4c96-b0e5-2d9f83a1c647-2026-09-08.md`
- **PATTERN**: §37 Session Observability (EP-061, v2.43 target)
- **Config block**: `factory.config.yaml` blocco `session_analysis:` (questo TSK)
- **Integrazione fleet-doctor**: `fleet_recommendations[]` in report JSON (unidirezionale, advisory only)
- **Analogia strutturale**:
  - `/wiki-search` (EP-042) — gate config + flag + skill ibrida + output multi-format
  - `/refactor` (EP-060) — gate config + parse + dispatch skill + output artefatto

[^src: management/kanban/EP-061-session-agentic-analyser/EP-061.md §"Architettura v1" + §"Vincoli architetturali" + §"Invarianti R-SAA-1..10"]
[^src: wiki/decisions/tavola-rotonda-c4e8f1b2-7a3d-4c96-b0e5-2d9f83a1c647-2026-09-08.md §"Accordi Round 3"]
