---
tool: aggregate-accuracy
version: v2.22
capability: EP-026
adr_ref: ADR-027
---

# Tool: aggregate-accuracy

Scansiona `analytics/reports/accuracy/*.json` e produce statistiche di self-calibration
della capability di stima. Implementa il terzo anello del loop learning-accumulation
(ADR-027 §D): **Cattura (EP-010) → Aggrega (EP-026) → Calibra (update config)**.

Non genera una nuova stima forward-looking. Non modifica alcun file di input.
Invocabile via `/estimate --aggregate-accuracy` (documentato in `.claude/commands/estimate.md`)
oppure manualmente su qualunque set di file `analytics/reports/accuracy/*.json`.

## Input

**Path scansionato**: `analytics/reports/accuracy/*.json`

Campi letti per ogni file:

| Campo | Tipo | Note |
|---|---|---|
| `estimate_id` | string | Identificatore stima (`EST-YYYY-MM-DD-NNN`) |
| `estimate_original.method` | enum | `rcf` / `pert` / `combined` |
| `estimate_original.confidence` | enum | `high` / `medium` / `low` / `very_low` |
| `verdict.overall` | enum | `good` / `mixed` / `poor` |
| `delta.cost_pct_vs_p85` | number | Scostamento % costo vs P85 stimato |
| `delta.duration_pct_vs_p85` | number | Scostamento % durata vs P85 stimato |

Schema sorgente: ADR-027 §C (accuracy retrospective schema).

## Algoritmo

### Step 1 — Scansione

Individua tutti i file `analytics/reports/accuracy/*.json`. Conta N = numero di file
trovati. Applica le regole di **Graceful degradation** (sezione successiva) prima di
procedere.

### Step 2 — Raggruppamento per metodo

Raggruppa i file per valore di `estimate_original.method` (`rcf`, `pert`, `combined`).
Per ciascun gruppo calcola:

- **N**: numero di retrospettive nel gruppo.
- **pct_good**: percentuale con `verdict.overall == "good"` (= within P85 su entrambe
  le dimensioni costo e durata).
- **pct_mixed**: percentuale con `verdict.overall == "mixed"`.
- **pct_poor**: percentuale con `verdict.overall == "poor"`.

Le percentuali sono calcolate sul N del gruppo (non sul totale); `pct_good + pct_mixed +
pct_poor == 100.0` per ciascun gruppo.

### Step 3 — Raggruppamento per confidence bucket

Raggruppa i file per valore di `estimate_original.confidence` (`high`, `medium`, `low`,
`very_low`). Stessa struttura aggregati del Step 2:

- N, pct_good, pct_mixed, pct_poor per ciascun bucket.

### Step 4 — Calibration signals

Calcola i `calibration_signals` a partire dai risultati dei Step 2 e Step 3:

- **best_method**: metodo con `pct_good` massimo tra quelli con N >= 1.
- **weakest_confidence_bucket**: bucket con `pct_good` minimo tra quelli con N >= 1;
  candidato a rivedere la soglia `rcf_medium_threshold` in `factory.config.yaml`.
- **rcf_threshold_suggestion**:
  - `"raise"` se il bucket `medium` ha `pct_good` < 50%;
  - `"lower"` se il bucket `high` ha `pct_good` >= 90% e `medium` >= 80%;
  - `"ok"` altrimenti.
- **rationale**: testo umano che spiega il suggerimento in 1-2 frasi.

I calibration_signals sono **suggerimenti, non enforce**: il PM decide se aggiornare
le soglie in `factory.config.yaml`. Il tool non modifica mai `factory.config.yaml`.
Schema JSON completo in `## Output schema`.

## Graceful degradation

- **N = 0** (directory `analytics/reports/accuracy/` assente o vuota):
  Stampa il messaggio:
  ```
  Nessuna retrospettiva disponibile. Eseguire stime e attendere chiusura progetto.
  ```
  Termina con exit 0. Non fallire loud. Non emettere report JSON.

- **N < 10**:
  Stampa avviso prima del report:
  ```
  Storico insufficiente per calibrazione affidabile (N=<n>). Risultati orientativi.
  ```
  Procede comunque con il calcolo delle statistiche (Step 2 e Step 3).
  Il campo `warnings` dello schema JSON includerà l'avviso (vedi `## Output schema`).

## Output (stdout)

Quando N >= 1 il tool stampa un report testuale compatto in chat, strutturato come:

```
aggregate-accuracy report — N=<n> retrospettive
================================================
Per metodo:
  rcf      N=<n>  good=<pct>%  mixed=<pct>%  poor=<pct>%
  pert     N=<n>  good=<pct>%  mixed=<pct>%  poor=<pct>%
  combined N=<n>  good=<pct>%  mixed=<pct>%  poor=<pct>%

Per confidence bucket:
  high      N=<n>  good=<pct>%  mixed=<pct>%  poor=<pct>%
  medium    N=<n>  good=<pct>%  mixed=<pct>%  poor=<pct>%
  low       N=<n>  good=<pct>%  mixed=<pct>%  poor=<pct>%
  very_low  N=<n>  good=<pct>%  mixed=<pct>%  poor=<pct>%

Calibration signals:
  best_method: <method>
  weakest_confidence_bucket: <bucket>
  rcf_threshold_suggestion: raise|lower|ok
  rationale: <testo>
```

I gruppi con N = 0 (nessuna retrospettiva per quel metodo o bucket) sono omessi
dall'output testuale ma inclusi nel JSON con N = 0.

Con `--output=<path>`: il report JSON è persisto in
`analytics/reports/calibration/<YYYY-MM-DD>-calibration.{json,md}` (vedi
`## Argomenti` e `## Output schema`).

## Idempotenza

Il tool **non scrive mai sui file di input** (`analytics/reports/accuracy/*.json`).
L'output è esclusivamente:
- stdout (visualizzazione in chat), oppure
- un file di report su path esplicito via `--output=<path>`.

Eseguibile N volte sullo stesso set di file di input senza alcun effetto collaterale
sui dati sorgente. La directory `analytics/reports/accuracy/` non viene mai modificata.

## Output schema

Schema JSON del report di calibration prodotto con `--output=<path>` o stampato come
struttura machine-readable in chat:

```json
{
  "schema_version": "1.0",
  "generated_at": "<ISO8601>",
  "n_retrospectives": "<int>",
  "stats_by_method": [
    {
      "method": "rcf|pert|combined",
      "n": "<int>",
      "pct_good": "<float>",
      "pct_mixed": "<float>",
      "pct_poor": "<float>"
    }
  ],
  "stats_by_confidence": [
    {
      "confidence": "high|medium|low|very_low",
      "n": "<int>",
      "pct_good": "<float>",
      "pct_mixed": "<float>",
      "pct_poor": "<float>"
    }
  ],
  "calibration_signals": {
    "best_method": "<method con pct_good più alto>",
    "weakest_confidence_bucket": "<bucket con pct_good più basso>",
    "rcf_threshold_suggestion": "raise|lower|ok",
    "rationale": "<spiegazione testuale del suggerimento>"
  },
  "warnings": ["<avviso N<10 se applicabile>"],
  "notes": [
    "Calibration signals sono orientativi. Per aggiornare le soglie config, modificare factory.config.yaml analytics.estimation e rieseguire /lint per validazione."
  ]
}
```

### Regole calibration_signals

- `best_method`: metodo con `pct_good` massimo tra quelli con N >= 1.
- `weakest_confidence_bucket`: bucket con `pct_good` minimo tra quelli con N >= 1;
  candidato a rivedere la soglia `rcf_medium_threshold` in `factory.config.yaml`.
- `rcf_threshold_suggestion`: `"raise"` se il bucket `medium` ha `pct_good` < 50%;
  `"lower"` se il bucket `high` ha `pct_good` >= 90% e `medium` >= 80%; `"ok"` altrimenti.
- `rationale`: testo umano che spiega il suggerimento in 1-2 frasi.
- I calibration_signals sono **suggerimenti, non enforce**: il PM decide se aggiornare
  le soglie. Il tool non modifica `factory.config.yaml`.

### Output path

Senza `--output`: solo stdout.

Con `--output=<path>`: scrive in `analytics/reports/calibration/<YYYY-MM-DD>-calibration.{json,md}`.
Il report di calibration non e' gitignored di default (documento audit, come le stime).

## Argomenti

| Flag | Tipo | Note |
|---|---|---|
| `--output=<path>` | opzionale | Persiste il report in `analytics/reports/calibration/<YYYY-MM-DD>-calibration.{json,md}`. |

## Note

- ADR ref: ADR-027 §C (input schema retrospettive) + ADR-027 §D (ciclo Cattura→Aggrega→Calibra).
- EP ref: EP-026 (aggregate-accuracy calibrazione) — estende EP-010 (cattura accuracy).
- Il tool è una capability di ottimizzazione, non una regola di sistema: nessuna
  invariante §7 è modificata.
- Default off (R.P3): la sua assenza non genera ERROR di lint.
- I calibration_signals sono suggerimenti. Il PM decide se aggiornare le soglie in
  `factory.config.yaml analytics.estimation`. Il tool non modifica mai `factory.config.yaml`.
