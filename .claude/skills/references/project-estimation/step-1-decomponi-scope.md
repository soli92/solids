# Step 1 — Decomponi Scope + Boot Validation + Confidence Policy (dettaglio completo)

Ambito: Fase di ingestion di `project-estimation.md`. Copre Boot Validation, Step 1
(decomposizione scope), Step 1b (calcolo confidence reference class) e Step 1c (mapping
confidence → metodo + contingency). Leggere prima di avviare qualsiasi stima.

---

## Boot Validation — analytics.estimation thresholds (ADR-025 §A)

Eseguita **una sola volta all'avvio della skill**, prima di qualsiasi step procedurale.
Applicabile solo se `analytics.estimation.enabled: true` (a `false` la skill è no-op).

```
BOOT VALIDATION — analytics.estimation thresholds
  Leggi analytics.estimation dalla config.
  Verifica: 1 <= rcf_low_confidence_threshold
              < rcf_medium_confidence_threshold
              < rcf_high_confidence_threshold
  Se condizione non soddisfatta → FAIL-LOUD:
    "Mis-config analytics.estimation: soglie non valide. Vedi ADR-025 §A validation."
    (interrompi la skill, non produrre output parziale)
```

Se la validazione passa, prosegui con lo Step 1.

---

## Step 1 — Decomponi Scope

**Input atteso** — lo scope da stimare in una di due modalità:

- **Esplicito (default)**: il caller passa la lista `scope: [{name, task_type, O?, M?, P?}]`
  inline, o `--scope-file=<path>` per scope grandi. Schema scope-file verbatim (ADR-025 §E):
  ```yaml
  scope:
    - name:        "auth flow"
      task_type:   "fe-feature"        # per il match nella reference class (Step 2)
      O:           2.0                  # ottimistico (opzionale se derivato da RCF)
      M:           4.0                  # più probabile
      P:           8.0                  # pessimistico
      notes:       "include SAML SSO"
    - name:        "dashboard"
      task_type:   "fe-feature"
      O:           3.0
      M:           6.0
      P:           12.0
  unit:            days                 # days | hours
  context:                              # opzionale, override delle assumptions
    team_size:     3
    model_id:      claude-opus-4-7
  ```
- **`--from-kanban=<EP-id>` (opt-in, ADR-025 §E)**: auto-decomposizione di una EP esistente.
  La skill carica `management/kanban/EP-<id>/EP-<id>.md` + le US figlie, identifica i TSK
  figli come voci del PERT, e deriva O/M/P data-driven dalla reference class storica (Step 2):
  `O = p15`, `M = mediana`, `P = p85` della durata dei task simili. Richiede
  `analytics.measurement.enabled: true` (sennò nessuno storico → fail-loud
  «`--from-kanban` richiede `analytics.measurement.enabled: true`»). Per ogni TSK senza
  storico (reference class N=0), usa fallback soft `(O=M, M=default_M_per_layer, P=2*M)` +
  warning, **non** blocca. Nota di provenienza obbligatoria in `notes[]`: «Scope
  auto-decomposed from EP-<id>; X TSK con storico, Y TSK con fallback default». Per progetti
  contractual, raccomanda validazione umana del breakdown auto-decomposto.

**Tool invocato**: nessuno in modalità esplicita (passo cognitivo); in `--from-kanban`,
lettura kanban + `build-reference-class.py` per voce (anticipa lo Step 2).

**Output prodotto**: lista `scope[]` di voci stimabili, ognuna con `{name, task_type, O, M, P}`
e `unit` coerente, + `context` opzionale.

**Criterio di completamento**: ogni voce è stimabile (ha `task_type` per il match o O/M/P
espliciti). **Escalation**: se voci non stimabili autonomamente → emetti `open_questions[]`
al caller e fermati sulle voci ambigue. Mai inventare dati.

[^src: design_&_architecture/decisions/ADR-025.md §E]

---

## Step 1b — Recupera reference class e calcola confidence (ADR-025 §A)

Step procedurale che formalizza l'algoritmo `bucket_by_N + downgrade similarity`.
Produce `reference_class_quality` consumato dagli Step successivi e dallo Step 5.

### 1. Recupero N

```
Conta i task in analytics/events/ con task_type e layer matchanti il nuovo scope.
Periodo di osservazione: ultimi 12 mesi (o tutto lo storico se < 12 mesi disponibile).
Se EP-009 non attivo → N=0 (fallback PERT-only; non è un errore, no fail-loud).
```

### 2. Algoritmo bucket_by_N (ADR-025 §A)

```
if N >= rcf_high_confidence_threshold:    confidence_raw = HIGH
elif N >= rcf_medium_confidence_threshold: confidence_raw = MEDIUM
elif N >= rcf_low_confidence_threshold:   confidence_raw = LOW
else:                                     confidence_raw = VERY_LOW   # N=0 incluso
```

### 3. Similarity input — tre modalità (priorità decrescente, ADR-025 §B)

```
(a) Esplicita: --similarity high|medium|low passato dal caller
(b) Auto-stimata: tag overlap via --from-kanban se attivo
(c) Conservativa: medium (fallback se né (a) né (b) disponibili)
```

### 4. Downgrade per similarity

```
high_similarity:   0 livelli di downgrade
medium_similarity: -1 livello (HIGH→MEDIUM, MEDIUM→LOW, LOW→VERY_LOW)
low_similarity:    -2 livelli (HIGH→LOW, MEDIUM→VERY_LOW, LOW→VERY_LOW)
Floor: VERY_LOW (non scende oltre)
confidence_final = max(VERY_LOW, confidence_raw - downgrade_steps)
```

### 5. Output campo

```
reference_class_quality:
  N: <conteggio>
  period: "<periodo osservazione>"
  similarity: <high|medium|low>
  confidence_final: <HIGH|MEDIUM|LOW|VERY_LOW>
  mode: <RCF|PERT-only>   # PERT-only se N=0
```

[^src: design_&_architecture/decisions/ADR-025.md §A §B]

---

## Step 1c — Mapping confidence → metodo primario + contingency (ADR-025 §C)

Riceve `reference_class_quality.confidence_final` e determina il metodo primario,
il metodo di validazione e la contingency raccomandata.

| confidence_final | Metodo primario | Metodo secondario | Contingency | Note |
|---|---|---|---|---|
| HIGH | RCF | PERT three-point | 15% | — |
| MEDIUM | RCF | PERT three-point | 15% | — |
| LOW | PERT three-point | RCF (informativo) | 20% | N basso |
| VERY_LOW | PERT three-point | — | >= 30% (enforce hard) | N=0 o similarità bassa |

### Enforce — confidence VERY_LOW

```
ENFORCE — confidence VERY_LOW
  method:          forzato a PERT (anche se il caller ha passato method=RCF; no override)
  contingency_pct: se valore passato < 30 → auto-alza a 30
                   → log warning: "contingency_pct alzata a 30% (enforce very_low, ADR-025 §C)"
  Questo enforce NON è fail-loud: la skill continua e produce output.
```

### Note enforce — confidence LOW

```
NOTE — confidence LOW
  Aggiungere in notes[] del report:
  "Con N=<N> samples, RCF è informativo; PERT bottom-up dovrebbe essere il metodo primario."
  Nessun enforce hard: il caller può sovrascrivere method.
```

### Warnings — N=0

```
WARNINGS — N=0
  Aggiungere obbligatoriamente in warnings[] del report (ADR-025 §D):
  "Nessun dato storico disponibile: stima basata solo su elicitation. Bias di ottimismo
   non mitigato. Calibrare contingency al rialzo (35% applicato di default;
   raccomandato verificare con esperto)."
  contingency_pct forzata a 35 se N=0 (override del default 30 di very_low).
```

[^src: design_&_architecture/decisions/ADR-025.md §C §D]
