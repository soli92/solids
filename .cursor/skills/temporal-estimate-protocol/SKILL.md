# Skill: Temporal Estimate Protocol

> Adapter Cursor della skill `temporal-estimate-protocol` definita in PATTERN.md.

Metadata skill (originale):
```yaml
name: temporal-estimate-protocol
description: Stima adattiva del tempo rimanente da progresso osservato (Layer 3 — Generative Time Model semplificato, EP-043)
version: v2.30-candidate
capability: EP-043
opt_in: temporal.estimate_protocol.enabled
depends_on_skill: temporal-budget-governor
pattern_refs: [generative-time-model, circuit-breaker, evaluator-optimizer]
```

> **Layer 3 — Generative Time Model semplificato**: stima adattiva del tempo rimanente da progresso osservato a runtime. Complementa [temporal-budget-governor](mdc:.cursor/skills/temporal-budget-governor/SKILL.md) (vincolo economico) con una stima temporale basata su velocità osservata. Comunica un payload strutturato `temporal_estimate`, **non lo esegue** (separation of concerns). [[generative-time-model]] applicato al coordinamento real-time multi-agente.

Riferimenti: `wiki/syntheses/temporal-awareness-multiagent-patterns.md §Layer 3 — Coordinazione real-time`, `factory.config.yaml.temporal.estimate_protocol.*`, `temporal-budget-governor` (ordine di invocazione).

[^src: wiki/syntheses/temporal-awareness-multiagent-patterns.md §Layer 3 — Coordinazione real-time]

## Prerequisiti

- `factory.config.yaml.temporal.estimate_protocol.enabled: true` (altrimenti no-op — vedi §Condizione di no-op).
- Input obbligatori presenti e validi: `task_estimate` (S|M|L|XL), `elapsed_ms` (intero >= 0), `completed_steps` (intero >= 0), `total_steps` (intero > 0).
- `total_steps > 0` e `completed_steps <= total_steps`.

La skill è **read-only** sullo stato del task. **Comunica** un payload `temporal_estimate`; il **chiamante esegue** l'eventuale reazione (escalation, log, gate umano).

## Fase 1 — Bootstrap (check flag + input validation)

### 1.1 Check flag

Legge `factory.config.yaml.temporal.estimate_protocol.enabled`.

- Se `false` (default): return immediato `temporal_estimate: null` senza calcoli. Nessun log, nessun errore. Vedi §Condizione di no-op.

### 1.2 Validazione input

Campi obbligatori da verificare:

| Campo | Tipo | Vincolo |
|-------|------|---------|
| `task_estimate` | string | uno di: S, M, L, XL |
| `elapsed_ms` | integer | >= 0 |
| `completed_steps` | integer | >= 0 |
| `total_steps` | integer | > 0, >= `completed_steps` |

Se uno o più campi assenti o invalidi: return `temporal_estimate: null` con `rationale: "Input insufficienti per la stima"`. Nessuna computazione parziale.

### 1.3 Conversione task_estimate → budget_reference_ms

Converte `task_estimate` in `budget_reference_ms` dalla tabella configurata in `factory.config.yaml.temporal.estimate_protocol.budget_ms`.

**Tabella di default** (usata se la chiave è assente in config):

| task_estimate | budget_reference_ms |
|---------------|---------------------|
| S | 900_000 (15 min) |
| M | 3_600_000 (1 h) |
| L | 14_400_000 (4 h) |
| XL | 57_600_000 (16 h) |

Se `task_estimate` non corrisponde a nessuna chiave nota: return `temporal_estimate: null` con `rationale: "task_estimate non riconosciuto: <valore>"`.

**Output di Fase 1**: `budget_reference_ms` (integer).

## Fase 2 — Progress Ratio Calc

Calcola:

```
progress_ratio = completed_steps / total_steps
```

**Caso edge — progresso zero**:

Se `progress_ratio == 0` (ossia `completed_steps == 0`): return immediato con:

```yaml
temporal_estimate:
  estimated_remaining_ms: null
  confidence: 0.0
  recommendation: continue
  rationale: "Progresso zero: impossibile stimare senza dati osservati"
  budget_reference_ms: <integer>
  progress_ratio: 0.0
  time_ratio: 0.0
```

Rationale: senza almeno uno step completato la velocità osservata è undefined; nessuna proiezione lineare è affidabile. Il valore `time_ratio` viene impostato a `0.0` per uniformità dello schema (non c'è budget consumato rispetto al `budget_reference_ms` rilevante in questo caso, ma `elapsed_ms / budget_reference_ms` può essere calcolato e restituito se utile al chiamante — vedere Fase 3).

**Nota**: se `completed_steps == 0` ma `elapsed_ms > 0`, il chiamante potrebbe avere già consumato budget senza avanzare. Il return `recommendation: continue` riflette che non ci sono basi per escalare — ma il chiamante può a sua discrezione verificare il vincolo economico via `temporal-budget-governor` (vedi §Complementarietà).

**Output di Fase 2**: `progress_ratio` (float, range `(0.0, 1.0]`).

## Fase 3 — Time Estimate + Confidence

### 3.1 Proiezione temporale lineare

```
estimated_total_ms    = elapsed_ms / progress_ratio
estimated_remaining_ms = estimated_total_ms - elapsed_ms
time_ratio             = elapsed_ms / budget_reference_ms
```

`estimated_remaining_ms` può essere negativo se la proiezione lineare risulta inferiore al già trascorso (caso incoerente — da trattare come `null` con rationale di incoerenza; vedi §Fase 4).

### 3.2 Calcolo confidence

**Con `reference_class_ms` fornito** (storico di task analoghi, opzionale):

```
raw_confidence = 1 - abs(estimated_total_ms - reference_class_ms) / reference_class_ms
confidence     = clamp(raw_confidence, 0.1, 0.9)
```

Dove `clamp(x, lo, hi) = max(lo, min(hi, x))`.

**Senza `reference_class_ms`** (default, nessun storico):

```
confidence = min(0.9, progress_ratio)
```

Questa formula calibra la fiducia sulla quantità di dati osservati: con `progress_ratio = 0.5` si ottiene `confidence = 0.5`; con `progress_ratio = 0.1` si ottiene `confidence = 0.1`. La formula non usa il fattore `0.5` per garantire che a metà avanzamento (`progress_ratio = 0.5`) la stima sia considerata abbastanza affidabile da non innescare `warn` per sola confidence (AC2).

### 3.3 Recommendation

Valutazione in ordine di priorità decrescente (il primo match vince):

**escalate** se almeno una delle seguenti:
- `time_ratio > escalate_time_ratio` (default config: `5.0`)
- `confidence < escalate_confidence_min` (default config: `0.1`)
- `estimated_remaining_ms > 3 * budget_reference_ms`

**warn** (se non escalate) se almeno una delle seguenti:
- `time_ratio > warn_time_ratio` (default config: `1.5`)
- `confidence < warn_confidence_min` (default config: `0.3`)

**continue** altrimenti.

Le soglie sono configurabili via `factory.config.yaml.temporal.estimate_protocol.thresholds`:

```yaml
temporal:
  estimate_protocol:
    thresholds:
      escalate_time_ratio: 5.0
      escalate_confidence_min: 0.1
      warn_time_ratio: 1.5
      warn_confidence_min: 0.3
```

### 3.4 Esempio AC2 (verifica leggendo la skill)

Input: `task_estimate: M, elapsed_ms: 1_800_000, completed_steps: 2, total_steps: 4`

```
budget_reference_ms    = 3_600_000  (M, dalla tabella default)
progress_ratio         = 2 / 4 = 0.5
estimated_total_ms     = 1_800_000 / 0.5 = 3_600_000
estimated_remaining_ms = 3_600_000 - 1_800_000 = 1_800_000
time_ratio             = 1_800_000 / 3_600_000 = 0.5
confidence             = min(0.9, 0.5) = 0.5
→ escalate? 0.5 > 5.0? No. 0.5 < 0.1? No. 1_800_000 > 10_800_000? No.
→ warn?     0.5 > 1.5? No. 0.5 < 0.3? No.
→ recommendation: continue  ✓
```

### 3.5 Esempio AC3 (verifica leggendo la skill)

Input: `task_estimate: M, elapsed_ms: 5_400_000, completed_steps: 1, total_steps: 4`

```
budget_reference_ms    = 3_600_000
progress_ratio         = 1 / 4 = 0.25
estimated_total_ms     = 5_400_000 / 0.25 = 21_600_000
estimated_remaining_ms = 21_600_000 - 5_400_000 = 16_200_000
time_ratio             = 5_400_000 / 3_600_000 = 1.5
confidence             = min(0.9, 0.25) = 0.25
→ escalate? 1.5 > 5.0? No. 0.25 < 0.1? No. 16_200_000 > 10_800_000? Yes → escalate  ✓
```

## Fase 4 — Output strutturato

### 4.1 Schema output

```yaml
temporal_estimate:
  estimated_remaining_ms: integer | null   # null se progresso zero o incoerenza proiezione
  confidence: float                        # 0.0–1.0; 0.0 solo se progress_ratio == 0
  recommendation: continue | warn | escalate
  rationale: string                        # SEMPRE non vuota (invariante AC6)
  budget_reference_ms: integer             # valore usato per il calcolo (da tabella o config)
  progress_ratio: float                    # completed_steps / total_steps
  time_ratio: float                        # elapsed_ms / budget_reference_ms
```

### 4.2 Invariante rationale (AC6)

Il campo `rationale` è **sempre** una stringa non vuota. Non sono ammessi valori `null`, stringa vuota `""` o placeholder. Esempi di rationale per ogni scenario:

| Scenario | Rationale |
|----------|-----------|
| continue, stima normale | `"Progresso regolare: time_ratio=0.5, confidence=0.50, proiezione entro budget"` |
| warn per time_ratio | `"Tempo trascorso supera 1.5× il budget di riferimento (time_ratio=1.8)"` |
| warn per confidence bassa | `"Confidenza bassa (0.20): pochi step completati, stima poco affidabile"` |
| escalate per remaining_ms | `"Tempo residuo stimato (16.2s) supera 3× il budget di riferimento (3.6s)"` |
| escalate per time_ratio | `"Consumo budget critico: time_ratio=6.2, soglia escalate=5.0"` |
| no-op flag disabilitato | (non raggiunto: return immediato in Fase 1) |
| input invalidi | `"Input insufficienti per la stima"` |
| progress_ratio == 0 | `"Progresso zero: impossibile stimare senza dati osservati"` |
| estimated_remaining_ms < 0 | `"Proiezione incoerente: remaining negativo (stima < elapsed). Possibile undercount steps."` |

### 4.3 Gestione estimated_remaining_ms negativo

Se `estimated_remaining_ms < 0` (incoerenza nella proiezione): emettere `estimated_remaining_ms: null` con `rationale` che segnala l'incoerenza e `recommendation: warn` (segnale che qualcosa è anomalo nel tracking dei passi).

## Condizione di no-op

La skill restituisce `temporal_estimate: null` senza calcoli in **due** path distinti:

**Path 1 — flag disabilitato** (`factory.config.yaml.temporal.estimate_protocol.enabled: false`, default):

```yaml
temporal_estimate: null
# rationale: non emessa (flag off, nessuna computazione)
```

Nessun log, nessun errore, nessun side-effect. Comportamento identico a un agente che non conosce la skill (backward compat). Questo è il default per tutte le factory (R.P3 opt-in totale).

**Path 2 — input insufficienti/invalidi** (flag abilitato, ma campi mancanti o non validi):

```yaml
temporal_estimate: null
# rationale: "Input insufficienti per la stima"
# (o "task_estimate non riconosciuto: <valore>")
```

In questo caso il flag è attivo ma mancano i dati minimi per produrre una stima. Il chiamante deve loggare il rationale se disponibile.

**Distinzione**: Path 1 è always-no-op progettuale; Path 2 è un errore soft di input. Solo Path 2 emette un rationale.

## Complementarietà con temporal-budget-governor

### Ordine di invocazione

La skill [temporal-budget-governor](mdc:.cursor/skills/temporal-budget-governor/SKILL.md) e `temporal-estimate-protocol` affrontano due dimensioni ortogonali del tempo:

| Skill | Dimensione | Input primario | Output |
|-------|------------|----------------|--------|
| `temporal-budget-governor` | costo economico | token consumati vs budget token | `governor_decision` (proseguire/downgrade/escalate/replan/hard-stop) |
| `temporal-estimate-protocol` | tempo residuo | step completati vs trascorso | `temporal_estimate` (continue/warn/escalate) |

**Ordine raccomandato**: invocare prima `temporal-budget-governor`, poi `temporal-estimate-protocol`:

```
1. temporal-budget-governor  →  governor_decision (vincolo economico)
2. temporal-estimate-protocol →  temporal_estimate  (stima temporale)
3. chiamante aggrega i due verdict (severity-max: hard-stop > escalate > replan > downgrade/warn > continue)
```

### Precedenza del vincolo economico

Il vincolo economico (`temporal-budget-governor`) ha **precedenza assoluta** sul vincolo temporale (`temporal-estimate-protocol`):

- Se `governor_decision.verdict == hard-stop`: il chiamante DEVE terminare; `temporal_estimate.recommendation` non viene valutato.
- Se `governor_decision.verdict == escalate | replan`: il chiamante apre gate umano o rollback; `temporal_estimate` è informativo aggiuntivo per il messaggio di gate.
- Se `governor_decision.verdict == downgrade | proseguire`: il chiamante considera `temporal_estimate.recommendation` per decidere se proseguire o aprire warning temporale.

Questo schema preserva la semantica del `temporal-budget-governor` come circuito di protezione principale ([[circuit-breaker]]) e posiziona `temporal-estimate-protocol` come sensore di velocità advisory.

### Indipendenza dei flag

I due flag sono indipendenti:

```yaml
temporal:
  budget:
    enabled: true   # governor attivo
  estimate_protocol:
    enabled: false  # stima temporale no-op → solo governor governa
```

Un chiamante può abilitare solo il governor (vincolo token), solo la stima (proiezione temporale), o entrambi.

## Backward compat

`temporal.estimate_protocol.enabled: false` (default): skill non invocata, `temporal_estimate: null`. Comportamento identico a factory senza EP-043.
