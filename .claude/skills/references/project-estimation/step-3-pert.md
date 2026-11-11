# Step 3 — PERT three-point (inside view) (dettaglio completo)

Ambito: dettaglio dello Step 3 di `project-estimation.md`. Leggere prima di invocare
`run-pert.py`. Prerequisito: voci con O/M/P dallo Step 1 (o derivate dalla reference class
dallo Step 2).

---

**Input atteso**: voci con O/M/P (esplicite dallo Step 1 o derivate da p15/mediana/p85 della
reference class dello Step 2).

**Tool invocato**:

```
python3 tools/analytics/run-pert.py --voices '<voci con O/M/P>' --unit days
```

**Azione** — applica le **formule PERT verbatim** (ADR-025 §E / synthesis §Metodo 2):

```
attesa   = (O + 4M + P) / 6
varianza = ((P - O) / 6)^2
```

Somma le attese e le varianze di tutte le voci → media e std (`sqrt(somma varianze)`) del
progetto totale; deriva P50 ≈ attesa, P85 ≈ attesa + ~1.04σ, P95 ≈ attesa + ~1.64σ.

**Quando applicare**:
- PERT è **metodo primario** se `confidence <= medium` (poco storico).
- È **cross-check** (inside view vs outside view) se `confidence: high`.
- Per `confidence: very_low` (N=0): PERT è l'**unico** metodo (fallback PERT-only, ADR-025 §D).

**Output prodotto**: `pert {p50, p85, p95, mean, std}` per durata e — derivando dal costo
unitario nelle assumptions — per costo.

**Criterio di completamento**: attese e varianze sommate, P50/P85 PERT prodotti per ogni
asse (durata + costo); formule applicate verbatim; nessuna media usata al posto dei
percentili.

[^src: design_&_architecture/decisions/ADR-025.md §E]
[^src: management/kanban/EP-010-task-analytics-estimation/US-040-skill-project-estimation/US-040.md §Business Rules]
