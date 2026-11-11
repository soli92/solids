# Step 4 — Monte Carlo + Combinazione + Output Obbligatorio (dettaglio completo)

Ambito: dettaglio degli Step 4 e 5 di `project-estimation.md`, più le 4 regole invarianti
del report e il fallback degradato. Leggere prima di invocare `run-monte-carlo.py` e
`estimate-project.py`. Prerequisito: output RCF (Step 2) + PERT (Step 3).

---

## Step 4 — Monte Carlo throughput + Combinazione

**Tool invocato** — Monte Carlo **solo** se `backlog noto + storico throughput >= 8 settimane`:

```
python tools/analytics/run-monte-carlo.py \
     --backlog <N_items> --throughput-history analytics/events/ --iterations 10000 --output json
```

Produce P50/P85/P95 di settimane → date (10.000 simulazioni). Se lo storico throughput è
< 8 settimane, Monte Carlo è **omesso** (non forzato su dati insufficienti).

**Azione — Combinazione**. Tabella «come combinare» verbatim (synthesis §Come combinare i
tre metodi / ADR-025 §C):

| Situazione | Approccio |
|---|---|
| Abbondanza dati storici | RCF primario, Monte Carlo per validare |
| Pochi dati, scope dettagliato | PERT bottom-up + RCF sanity-check |
| Backlog noto, storico throughput | Monte Carlo throughput primario |
| Prima stima enterprise critica | Tutti e tre in parallelo, riportare 3 confidence |

**Regola difensiva — massimo conservativo** (ADR-025 §C): quando più metodi producono un
intervallo per lo stesso asse, **P50/P85/P95 finale = massimo conservativo tra i metodi**
(si prende il valore più alto, mai la media ottimistica). Il metodo primario è scelto per
`confidence` (ADR-025 §C): high→RCF, medium→RCF+PERT, low→PERT, very_low→PERT-only.

**Sensitivity drivers** — identifica quale variabile cambia di più il P85 (es. team size,
tariffa media, scope assumptions): perturba ogni input e misura l'impatto sul P85. Output in
`sensitivity_drivers[]` con shape `{variable, impact_on_p85_pct, direction: direct|inverse}`.

**Output prodotto**: `intervals` combinato (P50/P85/P95 conservativi per costo + durata) +
`method` risultante + `sensitivity_drivers[]` non-vuoto.

**Criterio di completamento**: P50/P85/P95 finali = massimo conservativo tra i metodi
applicabili; `sensitivity_drivers[]` popolato con almeno 1 driver; Monte Carlo invocato sse
i prerequisiti (backlog + >=8 settimane) sono soddisfatti.

[^src: design_&_architecture/decisions/ADR-025.md §C]
[^src: wiki/syntheses/task-analytics-estimation-methods.md §Come combinare i tre metodi]

---

## Step 5 — Output Obbligatorio

**Tool invocato**:

```
python3 tools/analytics/estimate-project.py --scope '<voci con O/M/P>' \
     [--throughput-samples '<json>' --seed <n>] [--no-store]
```

**Azione** — emetti il report nello **schema standard ADR-024 §A** (`type: project_estimate`)
con il sub-schema `estimate:` (ADR-024 §E). La skill è **schema guardian**: esegue la
validation prima dell'emissione, fail-loud su shape invalida.

I **6 campi obbligatori** del sub-schema `estimate:` (presenti tutti, altrimenti fail-loud):

1. **`method`** — `RCF | PERT | monte-carlo | combined`.
2. **`intervals`** — intervallo con confidenza, **MAI numero puntuale**:
   `intervals.cost.{p50, p85, p95?, currency}` + `intervals.duration.{p50_days, p85_days, p95_days?}`.
   `p85 > p50` (monotonicità); `p95 > p85` se presente. **`intervals.cost.p85` è obbligatorio**.
3. **`split_human_agentic`** — `{human_pct, agentic_pct, human_cost_p50, agentic_cost_p50}`,
   `human_pct + agentic_pct == 100` (±0.01).
4. **`assumptions[]`** — lista **non-vuota** (scope, team, `model_id`, tariffe + `rate_basis`,
   aggiustamenti). `len >= 1`, sennò fail-loud «Stima senza assunzioni esplicite non ammessa.».
5. **`contingency_pct`** — buffer di rischio **separato dal P50** (`>= 0`); `contingency_cost_at_p50`
   derivato. Default per bucket (ADR-024 §G / ADR-025 §C): high 0-15, medium 15-25, low 25-35,
   very_low `>= 30`.
6. **`sensitivity_drivers[]`** — lista **non-vuota** `{variable, impact_on_p85_pct, direction}`.
   `len >= 1`, sennò fail-loud «Stima senza driver di sensibilità non ammessa.».

Più `reference_class_quality {N, period, similarity, confidence, mode?}` e i campi context
`model_id`, `compression_enabled`, `estimate_id`.

**`estimate_id`** (ADR-027 §B) — formato `EST-<YYYY-MM-DD>-<NNN>`, `NNN` contatore per giorno
zero-padded a 3 cifre. Generazione: conta i file con prefisso `YYYY-MM-DD-` in
`analytics/reports/estimates/` per il giorno corrente → `NNN = count + 1`.

**Persistenza** (ADR-027 §A) — due file paralleli (single-writer, immutabili):
`analytics/reports/estimates/<YYYY-MM-DD>-<slug>.json` (canonico) +
`<YYYY-MM-DD>-<slug>.md` (digest umano). Se la stima è collegata a un TSK target, aggiungi
`estimate_id: EST-...` al frontmatter del TSK (single-writer ADR-023 §G).

**Criterio di completamento**: 6 campi obbligatori presenti e validi, `intervals.cost.p85`
presente, monotonicità e cross-field rispettate, `estimate_id` generato, file persistiti.

[^src: design_&_architecture/decisions/ADR-024.md §E]
[^src: design_&_architecture/decisions/ADR-027.md §A §B]

---

## 4 regole invarianti del report (non negoziabili)

1. **Mai un numero puntuale** — l'output è SEMPRE un intervallo `[p50, p85]` con confidence e
   assunzioni esplicite. `intervals.cost.p85` è obbligatorio: un report con `p50` ma senza
   `p85` fallisce validation. Se il caller insiste «dammi solo un numero», risposta = P85 +
   warning «Stima singola sconsigliata: range corretto P50=X, P85=Y».
2. **Stima ≠ commitment** — il report contiene sempre la nota «Questa è una stima statistica,
   non un impegno contrattuale. Tenere separati i due artefatti.».
3. **Reference class debole esplicita** — con `confidence: low` o `very_low`, warning testuale
   in evidenza (in `warnings[]`, non solo nel JSON nascosto) — non si nasconde mai.
4. **Drift dei prezzi** — se `pricing.yaml`/`rates.yaml` è più vecchio di 90 giorni, nota in
   `notes[]` («Pricing table aggiornato l'ultima volta YYYY-MM-DD — verificare drift»).

[^src: wiki/concepts/task-analytics-cost-estimation-capability.md §Output obbligatorio di ogni stima]

---

## Vincoli della skill (enforced)

- **NON misura il passato**: se il caller chiede «quanto è costato? / quanto è durato?» →
  **declina** e suggerisci EP-009 (skill `cost-and-time-analytics` / agente
  `analytics-reporter`). Stima (futuro) e misurazione (passato) sono strutturalmente separate.
- **NON inventa la reference class**: se 0 dati storici per il `task_type` richiesto, dichiara
  `confidence: very_low` + PERT-only, **non** sostituire con default arbitrari (ADR-025 §D).
- **NON include la contingency nel P85**: il P85 è la statistica pura; la contingency è
  separata e dichiarata in `contingency_pct` (sopra il P50, mai sommata nei percentili).

---

## Fallback senza EP-009 (modalità degradata PERT-only)

Se `analytics.measurement.enabled: false` (nessuno storico, nessuna reference class, nessun
throughput per Monte Carlo):

- Metodo forzato a `method: PERT` (RCF/Monte Carlo non applicabili senza storico).
- `reference_class_quality: {N: 0, period: "n/a", similarity: "n/a", confidence: "very_low", mode: "PERT-only"}`.
- `contingency_pct >= 30` **enforced** (default 35 per very_low); se il caller passa un valore
  inferiore, la skill **auto-alza** e logga warning (no fail-loud).
- Warning automatico **obbligatorio** in `warnings[]`:
  «EP-009 non attiva / nessun dato storico: stima basata solo su elicitation. Bias di
  ottimismo non mitigato (Kahneman/Flyvbjerg). Calibrare contingency al rialzo (35%
  applicato di default).».

La stima viene **comunque prodotta** (una factory young al 1° progetto ha legittimo bisogno di
stimare) — mai degrada silenziosamente, mai fail-loud sul solo N=0.

[^src: design_&_architecture/decisions/ADR-025.md §D]
