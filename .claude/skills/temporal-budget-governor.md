# Skill: Temporal Budget Governor

> Adapter Cursor della skill `temporal-budget-governor` definita in PATTERN.md.

Metadata skill (originale):
```yaml
id: temporal-budget-governor
version: v2.19
capability: EP-014
opt_in: temporal.budget.enabled
depends_on_skill: parallel-scheduling
pattern_refs: [circuit-breaker, evaluator-optimizer, fail-closed]
```

> **2° asse di terminazione del loop evaluator-optimizer** — bound economico complementare a `max_iterations` strutturale. Invocata inline dall'orchestrator a ogni step decisionale (review iteration, dev-agent retry, premortem deep-dive, wave dispatch). Comunica un verdict, **non lo esegue** (separation of concerns — pattern parallelo a `code-reviewer` CQRL R.Q2). [[circuit-breaker]] applicato al costo.

Riferimenti: ADR-043 (5 soglie + verdict separato dall'esecuzione), ADR-045
(bootstrap N=0, cascata 4-livelli + degraded mode), ADR-044 (granularità
multi-livello), ADR-046 (operazione canonica PATTERN §3 + dominio scheduler
`budget` §18.7), ADR-049 (EP-015 R.C7), [parallel-scheduling](mdc:.cursor/skills/parallel-scheduling/SKILL.md) §Temporal Budget Hook
(produce il wave plan §18.6, TSK-110), [[circuit-breaker]], [[evaluator-optimizer]],
[[fail-closed]].

## Prerequisiti

- `factory.config.yaml.temporal.budget.enabled: true` (altrimenti no-op — vedi Backward compat).
- Wave plan §18.6 prodotto da `parallel-scheduling` (TSK-110), con i campi `token_budget` / `elapsed` / `estimated_remaining` / `bootstrap_mode`.
- Almeno una fonte di budget disponibile lungo la cascata 4-livelli (Step 1). Se nessuna → degraded mode (verdict `disabled`, livello 4).

Il governor è **read-only** sul wave plan (`parallel-scheduling` è l'unico writer dei campi
`token_budget` / `elapsed` / `estimated_remaining`, §18.6). Il governor **comunica** un verdict;
il **chiamante esegue** (separation of concerns, ADR-043 §C).

## Step 1 — Read context

Legge da:
1. Wave plan §18.6 (prodotto da `parallel-scheduling`, TSK-110): campi `token_budget`, `elapsed`, `estimated_remaining`, `bootstrap_mode`.
2. P85 per-layer da EP-010 `estimate-project` output (se `analytics.estimation.enabled: true`).
3. Baseline metrics da `analytics/reports/baseline/` (EP-013, se `analytics.dogfooding.enabled: true`).
4. `factory.config.yaml.temporal.budget.bootstrap.*` (fallback fissi).

**Cascata 4-livelli bootstrap** (ADR-045 §A):
```
1. PERT seed di EP-010 (p85 per-layer, ex-ante)
   ↓ se EP-010 non attivo OR percentile P85 non disponibile
2. Baseline EP-013 (analytics/reports/baseline/, ex-post)
   ↓ se EP-013 non attivo o baseline assente
3. Fallback fisso `bootstrap.wave_default_tokens` (default 100000)
   ↓ se non configurato
4. Degraded mode: verdict = disabled, WARNING fail-loud in wiki/log.md, no enforcement
```

**Degraded mode (livello 4)** — fail-loud sull'osservatore, fail-open sull'osservato (ADR-045 §D):
- Emette WARNING strutturato in `wiki/log.md`:
  ```
  [temporal-budget-governor:degraded] wave=<id> ts=<ISO-8601>
    reason: no_source_available
    pert_active: false
    baseline_available: false
    fallback_tokens_configured: false
    enforcement: DISABLED
    recommendation: "Configure temporal.budget.bootstrap.wave_default_tokens or enable EP-010/EP-013"
  ```
- Il workflow osservato **prosegue senza enforcement**. Il governor restituisce verdict speciale `disabled` (no-op per il chiamante), `metadata.bootstrap_source: degraded`.

**Bootstrap mode**: attivo quando N eventi `state: finished` con `tokens` non nullo < `bootstrap.min_n` (default 10). Marker `bootstrap_mode: true` in tutti gli eventi emessi.

**Bootstrap multi-livello** (ADR-045 §E): valutato **per livello** abilitato:
- Wave-level: bootstrap se N_wave < `min_n` (N_wave = eventi `wave_completed` storici).
- TSK-level: bootstrap se N_tsk < `min_n` (N_tsk = eventi `finished` per task_type del TSK).
- Sprint-level: bootstrap se N_sprint < 3 (cap rigido 3 per evitare bootstrap eterno).

Ogni livello esce dal bootstrap indipendentemente; `bootstrap_mode: true` applicato solo ai livelli ancora in bootstrap.

**Auto-uscita dal bootstrap** (ADR-045 §F): a N >= `min_n`, il governor smette di marcare `bootstrap_mode: true`, re-computa le distribuzioni P85 dal nuovo dataset (se baseline EP-013 attivo) e usa la fonte primaria disponibile. Emette evento `state: governor_bootstrap_exit` con `metadata.exit_n: <N>`.

**`very_cautious_mode: true`** opt-in (ADR-045 §H, default `false`): durante bootstrap (N < `min_n`) il governor restituisce sempre verdict `disabled` (enforcement disabilitato, shadow-mode observe-only). Auto-attivazione a N >= `min_n` con la fonte primaria disponibile. A `false` (default): cascata 4-livelli normale.

## Step 2 — Compute ratio

Calcola `ratio = elapsed / token_budget` per ogni livello abilitato (wave, tsk, sprint).

**5 soglie configurabili** (ADR-043 §B, default da `temporal.budget.thresholds.*`):

| Zona | Soglia | Verdict | Azione del chiamante |
|------|--------|---------|---------------------|
| verde | `ratio < green (0.5)` | `proseguire` | nessuna; loop continua |
| gialla | `0.5 <= ratio < yellow (0.75)` | `downgrade` | switch profilo compression a `conservative` se in `aggressive`/`custom` + log |
| arancione | `0.75 <= ratio < orange (1.0)` | `escalate` | gate umano fail-loud informato |
| rossa | `1.0 <= ratio < red (2.0)` | `replan` | rollback ultima decisione + cambio strategia (o escalate se nessuna alternativa) |
| nera | `ratio >= red (2.0)` | `hard-stop` | terminazione immediata + marker `[hard-stop]` in wiki/log.md |

Le 4 soglie numeriche (`green: 0.5`, `yellow: 0.75`, `orange: 1.0`, `red: 2.0`) sono configurabili via `factory.config.yaml.temporal.budget.thresholds.*`. La zona verde è derivata (`ratio < green`); la zona nera è derivata (`ratio >= red`).

**Verdict aggregato multi-livello** (ADR-044 §E): se più livelli triggerano contemporaneamente, vince il più severo: `hard-stop > replan > escalate > downgrade > proseguire`.

## Step 3 — Apply decision (separation of concerns)

Il governor produce un **payload `governor_decision`** strutturato (ADR-043 §C) e lo comunica al chiamante. **Il governor non auto-esegue**:

```yaml
governor_decision:
  verdict: proseguire | downgrade | escalate | replan | hard-stop | disabled
  ratio: <float>
  threshold_zone: green | yellow | orange | red | black
  context:
    wave_id: <uuid|null>
    task_id: <task-id|null>
    sprint_id: <slug|null>
  triggering_levels: [wave, tsk, sprint]   # livelli che hanno triggerato
  level_details:                           # solo se multi-livello
    wave: { ratio, zone, verdict_local }
    tsk: { ratio, zone, verdict_local }
    sprint: { ratio, zone, verdict_local }
  payload:
    suggested_profile: conservative | null    # se verdict == downgrade
    escalate_message: <string>                 # se verdict == escalate
    rollback_target: <decision-id|null>        # se verdict == replan
    alternative_strategy: <slug|null>          # se verdict == replan
    termination_reason: <slug>                 # se verdict == hard-stop
  metadata:
    bootstrap_mode: <bool>
    bootstrap_source: pert | baseline | fixed | degraded
    bootstrap_n: <int>                         # eventi disponibili (< min_n se bootstrap)
    governor_tokens_used: <int>                # self-observation
    decided_at: <ISO-8601>
```

**Separation of concerns esplicita** (ADR-043 §C): il governor è observer + decisore, **mai writer/executor**. I chiamanti che eseguono il verdict:
- **[orchestrator](mdc:.cursor/rules/orchestrator.mdc)** (scheduler dispatch): decide se proseguire la wave o aprire gate umano.
- **`code-review-protocol`** (loop iterazione): decide se proseguire l'iterazione o terminare il loop.
- **[premortem-protocol](mdc:.cursor/skills/premortem-protocol/SKILL.md)** (deep-dive): decide se proseguire il deep-dive o concludere.
- **[parallel-scheduling](mdc:.cursor/skills/parallel-scheduling/SKILL.md)** (durante wave): decide se dispatch del sub-agent successivo o join wave.

**Semantica dettagliata per verdict** (ADR-043 §D):

- `proseguire`: loop continua. Telemetria emessa.
- `downgrade`: chiamante esegue switch profilo. Prima di switch, DEVE consultare R.C7 EP-015 (ADR-049): se R.C7 impone già `conservative` (chain profonda) → downgrade no-op idempotente, loggato. Marker in log: `"[temporal-budget-governor] downgraded compression.output.policy_profile: aggressive → conservative on wave=<id>, ratio=0.62"`.
- `escalate`: chiamante invoca gate umano fail-loud con messaggio strutturato:
  ```
  Wave <id> ha consumato <ratio*100>% del token_budget (<elapsed> / <token_budget>).
  Soglia escalate: <orange>. Distribuzione restante: P50=<X>, P85=<Y>, P95=<Z>.
  Opzioni:
    [c]ontinue (override budget, accetta rischio)
    [a]bort (terminazione esplicita)
    [r]eplan (rollback + cambio strategia, se disponibile)
  Conferma? [c/a/r]
  ```
- `replan`: rollback ultima decisione + `parallel-scheduling` per re-dispatch con strategia alternativa. **Prerequisito**: il TSK / wave plan ha un campo `alternative_strategy:` documentato. Se nessuna alternativa → fallback automatico a `escalate`. Marker in log: `"[temporal-budget-governor] replan on wave=<id>, rollback=<decision-id>, alternative=<slug>"`.
- `hard-stop`: terminazione immediata + marker `[hard-stop]` in `wiki/log.md`. **NO auto-restart** (richiede intervento umano esplicito). Report sintetico al maintainer: cosa è stato terminato, perché, stato dei TSK in-flight, cosa serve per ripartire. Pattern parallelo a circuit-breaker open state.
- `disabled`: degraded mode livello 4 (o `very_cautious_mode` durante bootstrap), nessun enforcement, WARNING in log.

**Cross-EP coordination con R.C7 EP-015** (ADR-043 §F, ADR-049): prima di eseguire un downgrade, il chiamante DEVE consultare R.C7 (PATTERN §20.4 — «profilo `aggressive` vietato quando chain profonda»):
- Se R.C7 impone già `conservative` (chain profonda detectata): downgrade è no-op (già conservative); verdict loggato ma non eseguito (l'osservatore non può degradare oltre la regola, né forzare `aggressive` al contrario).
- Se R.C7 permette `aggressive` (chain corta): downgrade `aggressive → conservative` eseguito normalmente.
- Mai forzare upgrade `conservative → aggressive` dal governor (il governor è "freno", non "acceleratore"; pattern circuit-breaker "fail-safe").

## Step 4 — Log decision

Emette evento `state: governor_decision` nel stream EP-013 (`analytics/events/<YYYY-MM>.jsonl`):

```json
{
  "state": "governor_decision",
  "task_id": "<wave_id|task_id>",
  "ts": "<ISO-8601>",
  "tokens": "<governor_tokens_used>",
  "governor": {
    "action": "<verdict>",
    "ratio": "<float>",
    "threshold_zone": "<zone>",
    "bootstrap_mode": <bool>,
    "bootstrap_source": "<pert|baseline|fixed|degraded>"
  }
}
```

**Idempotenza** (ADR-043 §E): deduplicazione via hash compound `(wave_id, step_id, ts)`. Chiamate ripetute sullo stesso step → 1 evento. Pattern parallelo a ADR-039 (P0).

**Self-observation** (ADR-043 §E): ogni evento `governor_decision` conta `governor_tokens_used` (overhead). Se l'overhead aggregato per wave > 5% di `wave.token_budget` → verdict forzato `escalate` con `escalate_message: "governor self-overhead exceeded"` ("governor che si auto-osserva è suspect"). Pattern parallelo a EP-015 consistency-checker self-observation budget (ADR-048 §H).

## Step 5 — Update baseline (se applicabile)

A fine wave/sprint: se EP-013 attivo (`analytics.dogfooding.enabled: true`), il governor contribuisce al re-calc del baseline P85 in `analytics/reports/baseline/`. In sinergia con l'auto-uscita dal bootstrap (Step 1, ADR-045 §F): l'incremento di N dovuto ai nuovi eventi `wave_completed` può triggerare `governor_bootstrap_exit` e la re-calibrazione delle distribuzioni. No obbligo se EP-013 non attivo.

## Cross-link

- [[circuit-breaker]]: il governor è materializzazione del pattern circuit-breaker applicato al costo.
- [[evaluator-optimizer]]: il governor è il 2° asse di terminazione accanto a `max_iterations`.
- [[fail-closed]]: degraded mode fail-loud sull'osservatore, fail-open sull'osservato.
- EP-015 R.C7 (ADR-049): consultare prima di `downgrade` compression.
- PATTERN §3 «Temporal Budget Governance» (ADR-046 §B): operazione canonica.
- PATTERN §18.7 (ADR-046 §C): dominio scheduler `budget` opt-in.

## Backward compat

`temporal.budget.enabled: false` (default): skill non invocata. Comportamento identico v2.18.
