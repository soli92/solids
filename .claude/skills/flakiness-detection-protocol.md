---
name: flakiness-detection-protocol
description: >
  Procedura per il rilevamento statistico di test flaky in qa-dev (EP-027).
  Definisce lo schema JSONL degli eventi test_run, l'algoritmo del flakiness
  score con rolling window 50 run, e il gate opt-in qa_layer.flakiness_detection.
version: v2.22-candidate
introduced: EP-027 (Sprint 28)
depends_on:
  - analytics/events/qa-events.jsonl  # event store side-channel EP-009
---

# flakiness-detection-protocol

Skill procedurale per `qa-dev`. Documenta il contratto dati (schema JSONL)
e l'algoritmo di calcolo del flakiness score che `qa-dev` usa per decidere
se un test è flaky.

**Gate**: no-op totale se `qa_layer.flakiness_detection.enabled: false` in
`factory.config.yaml`. Con il flag spento, `qa-dev` si comporta identicamente
a v2.21 senza side effect.

---

## Sezione 1 — Schema JSONL evento `test_run`

### Path store canonico

```
analytics/events/qa-events.jsonl
```

Separato da `task-events.jsonl` (EP-009) per isolamento schema. Non gitignored
di default (audit trail — il registro storico è necessario per il calcolo del
flakiness score nel tempo).

### Record JSONL

Ogni record appendato a `analytics/events/qa-events.jsonl` ha il seguente formato
(una riga JSON per record, newline-delimited):

```jsonl
{"type":"test_run","test_id":"<stringa univoca>","tsk_id":"TSK-NNN","outcome":"pass|fail|skip","run_at":"<ISO 8601>","suite":"<stringa opzionale>"}
```

### Campi

| Campo | Tipo | Obbligatorio | Descrizione |
|---|---|---|---|
| `type` | stringa | SI | Costante `"test_run"` — discrimina dagli eventi TSK di EP-009 (`type: "tsk_*"`) |
| `test_id` | stringa | SI | Stringa univoca per test: `scenario.id` + `suite` per test EP-018; hash deterministico del nome file per gli altri |
| `tsk_id` | stringa | SI | TSK padre che ha originato l'esecuzione (es. `"TSK-123"`) |
| `outcome` | enum | SI | Risultato dell'esecuzione: `"pass"` \| `"fail"` \| `"skip"` |
| `run_at` | stringa | SI | Timestamp ISO 8601 UTC dell'esecuzione (es. `"2026-06-25T10:30:00Z"`) |
| `suite` | stringa | NO | Nome della suite o del file di test (stringa opzionale) |

### Esempio

```jsonl
{"type":"test_run","test_id":"login-happy-path","tsk_id":"TSK-201","outcome":"pass","run_at":"2026-06-25T10:30:00Z","suite":"e2e/auth"}
{"type":"test_run","test_id":"login-happy-path","tsk_id":"TSK-201","outcome":"fail","run_at":"2026-06-25T11:45:00Z","suite":"e2e/auth"}
{"type":"test_run","test_id":"login-happy-path","tsk_id":"TSK-205","outcome":"pass","run_at":"2026-06-25T14:00:00Z","suite":"e2e/auth"}
```

---

## Sezione 2 — Algoritmo flakiness score (rolling window)

### Formula

```
flakiness_score = failure_count / min(total_runs, 50)
```

dove:
- `total_runs` = numero totale di record con il `test_id` target in `qa-events.jsonl`
- `window_size` = `min(total_runs, 50)` — le ultime N run considerate (rolling window)
- `failure_count` = numero di record con `outcome: "fail"` nella window

### Procedura di calcolo (read-only, idempotente)

1. **Filtra** il JSONL per `test_id` target (scan lineare del file o query se indicizzato).
2. **Seleziona** le ultime `min(total_runs, 50)` run ordinate per `run_at` decrescente
   (rolling window degli eventi più recenti).
3. **Conta** `failure_count` = numero di record con `outcome: "fail"` nella window.
4. **Calcola** `flakiness_score = failure_count / window_size`.
5. **Arrotonda** a 2 decimali (es. `0.33` non `0.3333...`).

### Proprietà

- **Output**: float nel range `[0.0, 1.0]` arrotondato a 2 decimali, oppure stringa
  `"insufficient_data"` (vedi sotto).
- **Idempotente**: rileggere lo stesso JSONL produce lo stesso score.
- **Read-only**: la procedura non scrive sul JSONL (scrittura eventi solo al termine
  della sessione test da parte di `qa-dev`).

### Label `insufficient_data`

Se `total_runs < 10`:
- **Non emettere** il flakiness score (dati insufficienti per una stima affidabile).
- **Non produrre** verdetto di quarantena.
- Restituire la stringa `"insufficient_data"`.

Questa soglia evita falsi positivi su test appena introdotti o eseguiti raramente.

### Esempi

| total_runs | failure_count (window) | flakiness_score |
|---|---|---|
| 5 | 2 | `"insufficient_data"` (< 10 run) |
| 10 | 3 | `0.30` |
| 20 | 4 | `0.20` |
| 50 | 10 | `0.20` |
| 80 | 10 | `0.20` (window = 50, non 80) |
| 50 | 0 | `0.00` |
| 50 | 50 | `1.00` |

---

## Sezione 3 — Gate opt-in

La skill è **no-op** quando `qa_layer.flakiness_detection.enabled: false` in
`factory.config.yaml`. Se il flag è spento:

- `qa-dev` non legge `analytics/events/qa-events.jsonl` per il calcolo score.
- `qa-dev` non legge né scrive `analytics/qa/quarantine.json`.
- La pipeline si comporta identicamente a v2.21 (backward compat totale, R.P3).

Attivazione:

```yaml
# factory.config.yaml
qa_layer:
  flakiness_detection:
    enabled: true   # attiva l'intera procedura
```

---

## Sezione 4 — Allineamento EP-009 (event store JSONL)

**Dipendenza hard**: EP-009 (event store JSONL) è prerequisito. Il path
`analytics/events/` deve esistere e `analytics.measurement.enabled: true` in
`factory.config.yaml`.

**Discriminazione degli eventi**: il campo `type: "test_run"` discrimina gli
eventi QA dagli eventi TSK di EP-009 (che usano `type: "tsk_*"`, es.
`"tsk_start"`, `"tsk_done"`). I due schemi sono **affiancati** nello stesso
side-channel `analytics/events/`, ma in **file separati**:

| File | Schema | Prodotto da |
|---|---|---|
| `analytics/events/task-events.jsonl` | eventi TSK (`type: "tsk_*"`) | EP-009 harvest-session-tokens + qa-dev |
| `analytics/events/qa-events.jsonl` | eventi test run (`type: "test_run"`) | qa-dev (questa skill) |

La separazione in file distinti evita la contaminazione dello schema EP-009 e
mantiene la retrocompatibilità con factory che usano EP-009 senza EP-027.

**Decisione architetturale**: l'uso di sotto-schema affiancato (vs estensione
dello schema EP-009) è la proposta operativa di EP-027. La formalizzazione in ADR
è residuo del 28% di confidence (vedi EP-027 §Confidence).

---

## Sezione 5 — Quarantena automatica reversibile

### Path canonico registro quarantena

```
analytics/qa/quarantine.json
```

Separato da `analytics/events/` (side-channel EP-009). Il file è committato nel
repo (non gitignored di default): è audit trail esplicito per PM e lead-architect.

> **Nota runtime**: `analytics/qa/quarantine.json` non viene creato come template
> versionato. Il file è prodotto a runtime da `qa-dev` alla prima messa in quarantena
> di un test. Factory senza EP-027 attivo non producono questo file.

### Schema registro quarantena

```json
{
  "quarantined": [
    {
      "test_id": "<stringa>",
      "quarantined_at": "<ISO 8601>",
      "reason": "score_exceeded_threshold",
      "last_score": 0.34,
      "consecutive_passing_runs": 0,
      "quarantined_since_runs": 0,
      "status": "quarantined"
    }
  ]
}
```

### Campi obbligatori

| Campo | Tipo | Descrizione |
|---|---|---|
| `test_id` | stringa | Corrisponde al `test_id` del sotto-schema JSONL (Sezione 1) |
| `quarantined_at` | stringa | Timestamp ISO 8601 UTC della prima messa in quarantena |
| `reason` | stringa | Costante `"score_exceeded_threshold"` (unica causa in EP-027) |
| `last_score` | float | Ultimo `flakiness_score` calcolato al momento dell'ingresso o aggiornamento |
| `consecutive_passing_runs` | int | Contatore run consecutive con `outcome: "pass"` post-quarantena |
| `quarantined_since_runs` | int | Numero di run totali eseguite dal momento della quarantena (aggiornato da `qa-dev` a ogni sessione; usato da Lint Check 4ae) |
| `status` | enum | `"quarantined"` \| `"monitoring"` \| `"released"` |

### Transizioni di stato

```
                        score > threshold_quarantine (default 0.20)
(non in quarantena) ─────────────────────────────────────────────────▶ quarantined
                                                                             │
                        score < threshold_release (default 0.05)            │
                        ────────────────────────────────────────────▶ monitoring
                                                                             │
                        consecutive_passing_runs >= release_consecutive_runs │
                        (default 10)                                         │
                        ────────────────────────────────────────────▶ released
```

**Regole**:

- **Ingresso** (`→ quarantined`): `flakiness_score > threshold_quarantine` (default
  `0.20`) e test NON già in quarantena. `qa-dev` aggiunge la entry al registro dopo
  la sessione test con `status: "quarantined"`, `consecutive_passing_runs: 0`,
  `quarantined_since_runs: 0`.

- **Monitoraggio** (`quarantined → monitoring`): step intermedio quando
  `flakiness_score < threshold_release` (default `0.05`) ma il contatore
  `consecutive_passing_runs` non ha ancora raggiunto la soglia. Implementato come
  `status: "monitoring"` quando `consecutive_passing_runs > 0` e lo score è sotto
  la soglia di release.

- **Uscita** (`monitoring → released`): `flakiness_score < threshold_release` PER
  `consecutive_passing_runs >= release_consecutive_runs` (default `10`). Entrambe le
  condizioni simultanee. `status` transisce a `"released"`.

### Comportamento pipeline con quarantena attiva

- **Gate pass/fail**: i test con `status: "quarantined"` sono **ESCLUSI** dal verdetto
  finale della wave QA. Non contribuiscono al conteggio di successo/fallimento del gate.
- **Report QA**: i test in quarantena appaiono con label `[QUARANTINED]` in sezione
  separata del report QA.
- **Modalità advisory**: `qa-dev` esegue i test in quarantena in modalità non-blocking
  per continuare a raccogliere dati. L'esito advisory NON contribuisce al gate.
- **Orchestratore**: la wave advisory è gated da `qa_layer.flakiness_detection.enabled:
  true`.

### Procedura `qa-dev` post-sessione

1. Per ogni `test_id` eseguito, calcola `flakiness_score` (algoritmo Sezione 2).
2. **Nuovo test flaky**: se `score > threshold_quarantine` e test non già nel registro:
   - Aggiunge entry in `analytics/qa/quarantine.json` con `status: "quarantined"`,
     `consecutive_passing_runs: 0`, `quarantined_since_runs: 0`.
3. **Test già in quarantena**: per ogni test presente nel registro con `status` in
   `["quarantined", "monitoring"]`:
   - Se `outcome == "pass"`: incrementa `consecutive_passing_runs`.
   - Se `outcome == "fail"`: azzera `consecutive_passing_runs`.
   - Incrementa `quarantined_since_runs` di 1 per ogni sessione post-quarantena.
   - Se `score < threshold_release` AND `consecutive_passing_runs >= release_consecutive_runs`:
     transisce a `status: "released"`.
   - Se `score < threshold_release` AND `consecutive_passing_runs > 0` (ma non ancora
     a soglia): transisce a `status: "monitoring"` (se non già in monitoring).
4. Scrive il registro aggiornato in `analytics/qa/quarantine.json`.

### Gate opt-in

Tutta la procedura di quarantena è **no-op** se `qa_layer.flakiness_detection.enabled:
false`. Il file `analytics/qa/quarantine.json` non viene né letto né scritto.

### Soglie configurabili

Tutte le soglie sono configurabili in `factory.config.yaml` sotto
`qa_layer.flakiness_detection.*`:

| Chiave config | Default | Descrizione |
|---|---|---|
| `score_threshold` | `0.20` | Soglia ingresso quarantena (`flakiness_score > soglia`) |
| `release_threshold` | `0.05` | Soglia per iniziare monitoring verso uscita |
| `release_consecutive_runs` | `10` | Run consecutive passing richieste per `released` |
| `rolling_window` | `50` | Dimensione rolling window score (Sezione 2) |
| `stale_threshold` | `100` | Run in quarantena senza revisione → Lint Check 4ae WARNING |
