# Step 2 — Reference Class (outside view) (dettaglio completo)

Ambito: dettaglio dello Step 2 di `project-estimation.md`. Leggere prima di invocare
`build-reference-class.py`. Prerequisito: `reference_class_quality` prodotto in Step 1b.

---

**Input atteso**: lista `scope[]` dallo Step 1, ognuna con `task_type`/layer.

**Tool invocato** — per ogni voce, recupera la distribuzione storica:

```
python3 tools/analytics/build-reference-class.py \
     --filter '{"task_type":"<task_type>","layer":"<layer>"}' [--similarity high|medium|low]
# che internamente legge lo storico via analyze-timeline.py (US-063/US-035, EP-009)
```

**Azione** — applica la **Reference Class Sufficiency Policy** (ADR-025 §A) per mappare il
numero di campioni storici `N` a un bucket di confidenza:

| N (campioni matchanti) | bucket_by_N |
|---|---|
| `N >= 30` (`rcf_high_confidence_threshold`) | `high` |
| `10 <= N < 30` (`rcf_medium_confidence_threshold`) | `medium` |
| `1 <= N < 10` (`rcf_low_confidence_threshold`) | `low` |
| `N == 0` | `very_low` → fallback PERT-only (ADR-025 §D) |

Soglie configurabili in `analytics.estimation.{rcf_high/medium/low_confidence_threshold}`
(default 30/10/1). **Validation al boot**: `1 <= rcf_low < rcf_medium < rcf_high`, sennò
fail-loud su mis-config.

**Similarity factor** (ADR-025 §B) — quanto il nuovo scope somiglia allo storico; modula
il bucket via downgrade:
- **Esplicito (default)**: il caller passa `--similarity=high|medium|low`.
- **Auto-stimato** (con `--from-kanban`): tag overlap (Jaccard) + layer overlap → `high`
  (>0.7), `medium` (0.4-0.7), `low` (<0.4).
- **Conservativo (fallback)**: se né esplicito né auto-stimabile, assume `medium`.

```
confidence_final = downgrade(bucket_by_N, similarity_factor[similarity])
  similarity high   → downgrade 0 livelli   (mantieni bucket)
  similarity medium → downgrade 1 livello   (high→medium, medium→low, ...)
  similarity low    → downgrade 2 livelli
  floor = very_low (mai sotto)

Esempi (ADR-025 §A): N=24,similarity=high → medium ; N=24,similarity=low → very_low ;
                     N=45,similarity=high → high ; N=8,similarity=high → low ; N=0 → very_low
```

**Output prodotto** — per voce: `{p50_duration, p85_duration, p95_duration, p50_cost,
p85_cost, N_samples, period_covered, similarity}` + `confidence_final`. Gli aggiustamenti
per differenze note (team size diverso, nuovo stack, scope più ampio) si esplicitano come
`assumptions[]` (Step 5), **mai** come modifica silenziosa della distribuzione.

**Criterio di completamento**: ogni voce ha la sua distribuzione storica (o `N=0` dichiarato)
e un `confidence_final` calcolato deterministicamente da N + similarity.

[^src: design_&_architecture/decisions/ADR-025.md §A §B]
