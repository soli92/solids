---
name: parallel-scheduling
description: Algoritmo DAG-based per riconoscere e dispatchare operazioni parallele in modo sicuro (PATTERN §18, v2.11). Invocato dall'orchestrator.
---
# Parallel scheduling protocol (v2.11)

Riferimenti: PATTERN §18 (modello DAG, regole R.S1–R.S8), `state-scan` (input
candidates), `wiki-log-entry` (log dei wave), §5 (campi frontmatter
`depends_on` / `blocked_by` / `code_path`).

Eseguito dall'**Orchestrator** in 5 fasi: Discovery → Build DAG → Toposort &
Partition → Gate → Dispatch.

## Fase 0 — Discovery dei candidati

Input: stato corrente del repo (`/run` → `state-scan`).

- `Glob management/kanban/**/TSK-*.md` filtrato per:
  - `status: todo`
  - `consumer: agent`
  - `consumer: <layer>` agent presente in `.claude/agents/` (es. `be-dev.md` per `layer: be`)
  - `factory.config.yaml.scheduler.domains.develop: true`
- `Glob management/kanban/**/US-*.md` per il **resolve** di `depends_on TSK` cross-storia.
- Read `factory.config.yaml.scheduler` (default valori in PATTERN §18.5 se assente).
- Read `wiki/gaps.md` per `blocked_by Q_NNN` ancora aperte.
- **Dominio `premortem` (v2.16)**: invocazioni su target distinti candidate alla wave quando
  `scheduler.domains.premortem: true` (default). **Due livelli `max_parallel` distinti**:
  `scheduler.max_parallel` limita le `/premortem` concorrenti (livello dominio); il cap
  `max_parallel: 8` hardcoded in `premortem-protocol` (ADR-001) limita il fan-out interno
  di ogni premortem. Si compongono in N×M. Il gate `parallel_gate_threshold` si applica a N.
- **Dominio `visual-oracle` (v2.17)**: candidato alla wave quando
  `scheduler.domains.visual-oracle: true` (default `true` se `fe_correctness.enabled: true`,
  altrimenti no-op). **Sub-step di L2 (develop), NON un nuovo livello DAG** (ADR-013 §Punto 3).
  Gira dopo Fase 4 di `dev-protocol` e prima della Fase 5 (status: done).
  Parallelizzazione: cross-TSK parallel (no shared state); same-TSK serial (single-writer
  per `visual_status`). Non aumenta livelli DAG; estende durata effettiva di L2.
  → Composizione dettagliata: `.claude/skills/references/scheduler-domain-policies.md`
- **Dominio `ux-ui-review` (v2.18)**: candidato alla wave quando
  `scheduler.domains.ux-ui-review: true` (default `false`, opt-in; richiede
  `ux_ui.enabled: true`). **Sub-step di L2**, dopo visual-oracle e prima della Fase 5 (ADR-019).
  Parallelizzazione: cross-TSK parallel; same-TSK serial (single-writer per `ux_ui_status`).
  Composizione con visual-oracle: `visual_status: reject` → SKIPPED;
  `visual_status: conditional` + `ux_ui.parallel_during_conditional: true` → dispatch parallelo.
  → Procedura condizionale completa (5 step, composizione a11y, sotto-capability design):
    `.claude/skills/references/scheduler-domain-policies.md`
  → In assenza del file: STOP e segnala path mancante.
- **Dominio `functional-oracle` (v2.20)**: candidato alla wave quando
  `scheduler.domains.functional-oracle: true` (auto-attivato da
  `fe_correctness.functional_oracle.enabled: true`). **Sub-step di L2**, dopo visual-oracle e
  ux-ui-review (ADR-066). Parallelizzazione: **cross-app parallel**; **same-app serial**
  (porta unica per app, stato DOM condiviso). Non aumenta livelli DAG.
  → Composizione dettagliata: `.claude/skills/references/scheduler-domain-policies.md`
- **Dominio `analytics` (v2.18)**: candidato alla wave quando
  `scheduler.domains.analytics: true` (default `false`, opt-in). **Operazione canonica
  autonoma**, NON sub-step di develop (gira su qualsiasi topology, inclusa `plan-only`).
  Parallelizzazione: cross-scope parallel; same-scope serial (race su `analytics/events/`
  e `analytics/reports/<scope>/`). Composizione misurazione↔stima: same-scope serial.
  → Dettaglio composizione e retrospettiva accuracy: `.claude/skills/references/scheduler-domain-policies.md`

> **TRIGGER**: se e solo se un dominio opt-in con comportamento composito è attivo,
> leggi `.claude/skills/references/scheduler-domain-policies.md` per la procedura completa.
> In sua assenza: **STOP** e segnala path mancante.

Output: lista candidati `V` con per ciascuno: `id`, `layer`, `priority`, `estimate`, `depends_on`, `blocked_by`, `code_path`.

## Fase 1 — Build DAG

Costruisci `G = (V, E_dep ∪ E_conf)`:

### `E_dep` (causal, oriented)

Per ogni `u ∈ V`:
- Per ogni `v_id ∈ u.depends_on`:
  - Read `management/kanban/**/<v_id>.md`
  - Se `v.status != done` → aggiungi arco `v → u`
  - Se `v.status == done` → la dipendenza è soddisfatta, **non** aggiungere arco
- Per ogni `q_id ∈ u.blocked_by`:
  - Cerca `q_id` in `management/questions.md` o `wiki/gaps.md`
  - Se aperta → aggiungi un **virtual root** `Q_NNN` con arco `Q_NNN → u` (mai resolvibile da uno scheduler → il TSK resta in coda, non eseguito)

### `E_conf` (file conflict, unoriented)

Solo per i TSK con `factory.config.yaml.scheduler.code_path_conflict ≠ off`:

```
for u, v in pairs(V):
  if u.code_path == [] or v.code_path == []:
    if empty_code_path_policy == 'serial':
      E_conf.add({u, v})    # entrambi serializzanti
    # else 'parallel': no arco
  elif glob_intersect(u.code_path, v.code_path):
    E_conf.add({u, v})
```

`glob_intersect(A, B)` = `True` se esiste un path che matcha sia un glob di `A`
sia un glob di `B`. Implementazione minimale: expand glob a regex, check
overlap su prefisso comune (es. `src/auth/**` vs `src/auth/handlers/**` →
overlap; `src/auth/**` vs `src/users/**` → no overlap).

### Validazione

- **Cycle detection** su `E_dep`: DFS con stack di visita. Se ciclo → `ABORT` con messaggio:
  ```
  ERRORE: ciclo in depends_on:
    TSK-A → TSK-B → TSK-C → TSK-A
  Risolvere a mano (rimuovere una dipendenza). /run non procede.
  ```
- **Orphan `depends_on`**: `v_id` referenziato ma file non trovato → warning, l'arco è ignorato (no blocco, ma loggato come anomalia per `wiki-lint`).

## Fase 2 — Toposort + level grouping

Algoritmo di Kahn modificato per assegnare i **level** (antichain):

```
in_degree := {v: |{e ∈ E_dep | e = (_, v)}| for v in V}
level := {}
ready := {v in V | in_degree[v] == 0}
current_level := 0

while ready not empty:
  level[v] := current_level for v in ready
  next_ready := {}
  for v in ready:
    for (v, u) in E_dep:
      in_degree[u] -= 1
      if in_degree[u] == 0:
        next_ready.add(u)
  ready := next_ready
  current_level += 1

if any v in V not in level:    # nodi orfani → c'era un ciclo
  ABORT "ciclo rilevato (post-validate)"
```

Output: `levels[i] = [v_1, v_2, ...]` (antichain al level `i`).

## Fase 3 — Partition per conflict detection

Per ogni level `L_i`, applica **graph coloring greedy** su `E_conf` ristretto a `L_i`:

```
def partition(level_nodes, E_conf):
  nodes_sorted := sort(level_nodes, key=lambda v: (-v.priority_score, v.estimate_score))
  # priority_score: P0=3, P1=2, P2=1
  # estimate_score: XS=1, S=2, M=3, L=4
  groups := []
  for v in nodes_sorted:
    placed := False
    for g in groups:
      if not any({v, u} in E_conf for u in g):
        if len(g) < max_parallel:    # R.S3
          g.append(v)
          placed = True
          break
    if not placed:
      groups.append([v])
  return groups
```

Output per level: lista di `groups`, dove ogni `group` è parallelizzabile.

## Fase 4 — Gate

Per ogni `group`:

- Se `len(group) >= scheduler.parallel_gate_threshold` (default 3):
  - Stampa il **wave plan** in chat (formato §18.6).
  - Attendi conferma esplicita `y/N`. Su `N` → ABORT (no parziali).
- Se `len(group) < threshold`:
  - Stampa il wave plan come info (no gate).
- **Costi in token** (`dispatch-policy` §13): `cost_alert.py check --gate` prima di ogni wave.
  Con una riga `⚠` il wave plan diventa gated anche sotto soglia: conferma esplicita `y/N`,
  una volta per alert.

> **TRIGGER**: per il formato canonico del wave plan (con o senza temporal budget), leggi
> `.claude/skills/references/scheduler-wave-templates.md`.
> In sua assenza: **STOP** — output wave plan non emesso.

## Fase 5 — Dispatch

Per ogni `level i`:
  Per ogni `group g in level[i]`:
    1. **Context compression resolve (v2.14 Fase 2, opzionale)**: se `compression.context.enabled: true`
       E esiste `.graphify-state/code_paths/<target>/GRAPH_REPORT.md`, applica **confidence-gated
       dispatch** (R.G2): filtra per ruolo agent (`executor` → `EXTRACTED` only;
       `explorer` → `+INFERRED`; `reviewer` → tutto). Se assente/stale → fallback
       scansione filesystem standard + log warning `compression-context-fallback`.
    2. **Compression intercept (v2.14 Fase 1, opzionale)**: se `compression.output.enabled: true`,
       invoca `caveman-protocol §Fase 2-3` per ogni payload `Agent(...)` con
       `channel: orchestrator_to_subagent`. Se `enabled: false` → no-op.
    3. **Multi-tool-call** nello stesso turno: N invocazioni `Agent` parallele, una per ogni
       TSK in `g` (adapter Claude Code: `subagent_type = <layer>-dev`).
    4. Attendi che TUTTI i sub-agent del group terminino (foreground).
    5. Per ognuno:
       - OK → `dev-handoff` ha già aggiornato `status: done` + appendato `wiki/log.md`.
       - FAIL → append `wiki/log.md` entry `develop-failed TSK-ZZZ rationale=...`.
         TSK resta `status: todo`. **Non rollba** gli altri (R.S7).
    6. **Compression drift check (v2.14 Fase 1)**: se attivo, invoca `caveman-protocol §Fase 4`.
       Marker ambiguità → fallback + log `compression-drift`. Se `drift_count >= 3` → switch
       globale normal mode + chat warning.
    7. **VCS hand-off serializzato** (R.S8): per ogni TSK ok, invoca `vcs-handoff` **uno alla
       volta** in coda al group.
    8. **Token Ledger wave_close hook (gated, v2.21)**: se `analytics.token_ledger.auto_call_on_wave_close: true`:
       ```
       python3 "$CLAUDE_PROJECT_DIR/tools/analytics/show-session-tokens.py" --full
       ```
       **Fail-open**: errori → skip silente + nota `WARNING token-ledger wave_close failed`.
       Mai bloccare il workflow per mancanza di metriche. A `false` (default): no-op assoluto.
    9. **Cost alert wave_close (gated, `analytics.cost_alert.enabled`)**:
       `python3 tools/analytics/cost_alert.py check --gate` → riga nel wave summary se non vuota.
       Il wave successivo passa dal gate della Fase 4 (conferma). Fail-open come il punto 8.

Quando `level i` è completo, passa a `level i+1`.

## Fase 6 — Log

Append a `wiki/log.md` (template canonico) + record episodico in `memory/episodic/`.

> **TRIGGER**: per il template canonico del log entry e del record episodico, leggi
> `.claude/skills/references/scheduler-wave-templates.md`.
> In sua assenza: **STOP** — log entry non emessa.

## Regole inviolabili (R.S1–R.S8, PATTERN §18.4)

- **R.S1**: Single-committer su `wiki/log.md` e `wiki/gaps.md` — l'orchestrator
  serializza le append, mai due agent scrivono nello stesso turno.
- **R.S2**: Conflict-free su `code_path` — `partition()` lo garantisce.
- **R.S3**: Cap `max_parallel` (default 4).
- **R.S4**: Gate umano sopra `parallel_gate_threshold` (default 3).
- **R.S5**: Ciclo in `depends_on` → ABORT, no auto-fix.
- **R.S6**: Re-scheduling idempotente — DAG ricostruito da zero ogni run.
- **R.S7**: Fallimento di un sub-agent non rollba gli altri.
- **R.S8**: VCS sempre serializzato — coda di `vcs-handoff` a fine wave.

## Quando NON eseguire (short-circuit)

- `factory.config.yaml.scheduler.enabled: false` → l'orchestrator esegue il
  comportamento pre-v2.11 (suggerisce **un solo** next-step, niente DAG).
- `|V| == 1` → un solo candidato, nessun DAG da costruire, dispatch diretto.
- `topology: knowledge-only` o `plan-only` → no L5 → niente da parallelizzare
  a livello develop (ma ingest e lint paralleli restano possibili).

---

## Analytics Instrumentation (opt-in v2.19+)

**Gate**: `analytics.dogfooding.enabled: true` AND `analytics.granularity` in `{wave, tool}`.
SE `dogfooding.enabled: false` (default factory derivate): EARLY RETURN — 0 side effect.
SE `granularity: tsk`: wave events skipped.

**Nessun nuovo dominio scheduler**: i punti di iniezione wave sono inline nelle Fasi 4 e 5.
NON è aggiunto un dominio `analytics:` per EP-013 (contrariamente a EP-009). Pattern diverso.
**Single-writer**: tool `record-event.py` (ADR-039 §B). **PII invariante**: payload
allowlist-compliant (ADR-040 §A).

> **TRIGGER**: quando `analytics.dogfooding.enabled: true`, leggi
> `.claude/skills/references/scheduler-analytics-instrumentation.md` per i payload JSON
> dei 3 punti di iniezione e il volume stimato.
> In sua assenza: **STOP** analytics instrumentation — non emettere payload parziali.

---

## Temporal Budget Hook (opt-in v2.19, EP-014)

> **Gated**: `temporal.budget.enabled: true`. A flag spento questa sezione è no-op:
> wave plan senza campi budget, comportamento identico v2.18 (R.P3).

**Invarianti**:
- `estimated_remaining` espone sempre P50/P85/P95, mai numero puntuale.
- `parallel-scheduling` è l'**unico writer** di `token_budget`/`elapsed`/`estimated_remaining`.
  Il governor (skill `temporal-budget-governor`) è read-only sul wave plan (ADR-044 §G).
- Wave plan **immutabile post-gate**: solo `elapsed` cresce a ogni `state: finished`.

> **TRIGGER**: quando `temporal.budget.enabled: true`, leggi
> `.claude/skills/references/scheduler-temporal-budget.md` per lo schema YAML esteso,
> i 3 metodi di calcolo `token_budget` e il template del messaggio gate umano.
> In sua assenza: **STOP** temporal budget hook — non estendere il wave plan.

---

## Temporal Awareness Integration (opt-in v2.18+, EP-011 ADR-028/029/030/031)

Sezione trasversale al parallel-scheduling: EP-011 non introduce un nuovo dominio scheduler
(come `analytics` in EP-009 o `a11y` in EP-007) — è una **capability trasversale** attivata
per flag su TSK e config, non un nuovo livello DAG. Documentazione qui per centralità del
single-source `parallel-scheduling.md` sull'algoritmo `is_state_machine_active`.

### Policy di attivazione State Machine

Algoritmo `is_state_machine_active(tsk_frontmatter, config)` — verbatim ADR-029 §C:

```python
def is_state_machine_active(tsk, config):
    # 1. Master switch OFF → False (R.P3)
    if not config.temporal.enabled: return False
    if not config.temporal.state_machine.enabled: return False

    # 2. Override per-TSK (prevale sempre sulla policy globale)
    if tsk.frontmatter.get("temporal_state") is True:  return True
    if tsk.frontmatter.get("temporal_state") is False: return False

    # 3. Policy globale
    policy = config.temporal.state_machine.activation_policy  # default "estimate-xl"
    if policy == "estimate-xl":
        return tsk.frontmatter.get("estimate") == "XL"
    if policy == "always":
        return True
    if policy == "explicit-only":
        return False  # solo override per-TSK
    raise ValueError(f"activation_policy non valida: {policy}")  # fail-loud ENUM
```

| Scenario | Risultato |
|---|---|
| `temporal.enabled: false` (default) | `False` — R.P3 no-op |
| `temporal_state: true` nel frontmatter TSK | `True` — prevale sempre |
| `temporal_state: false` nel frontmatter TSK | `False` — prevale sempre |
| `activation_policy: estimate-xl` + `estimate: XL` | `True` |
| `activation_policy: estimate-xl` + `estimate: M` | `False` |
| `activation_policy: always` | `True` (qualunque estimate) |
| `activation_policy: explicit-only` | `False` (senza override per-TSK) |
| `activation_policy: <valore_non_valido>` | **fail-loud** ENUM error |

### Validation cross-config al boot scheduler (ADR-028 §G, ADR-029 §C)

Unico punto di validation cross-config aggregato per EP-011. Eseguita allo start scheduler se
`temporal.enabled: true`:

| Condizione | Severity | Azione |
|---|---|---|
| `temporal_state: false` su TSK XL senza `notes:` | WARNING-only | Segnala in chat; non blocca |
| `temporal_state: true` su TSK XS/S | INFO-only | Segnala; attivazione forzata ok |
| `temporal.state_machine.source: events` AND `analytics.measurement.enabled: false` | **fail-loud** | STOP «temporal.state_machine.source: events richiede analytics.measurement.enabled: true» — ADR-028 §G |

### Lifecycle state file in modalità standalone (ADR-028 §B.1)

Quando `is_state_machine_active() == True` e `source: standalone`:

1. **Kickoff TSK** (`todo → in_progress`): la skill/agente possessor crea
   `management/state/<TSK-id>.json` con `history[]` inizializzata dai `pending_steps[]` del
   piano TSK come entry con `status: pending`.
2. **Transizioni step**: skill possessor aggiorna entry in history ad ogni cambio stato
   (`pending → in_progress → completed|blocked`). Append-only enforced (ADR-028 §B.1).
3. **Handoff fra agenti**: chi prende il TSK aggiunge la prossima entry e diventa single-writer.
4. **Chiusura TSK** (`status: done`): ultima entry → `completed`. File resta in
   `management/state/` (versionato per audit, ADR-028 §A).

### Integrazione con Temporal Handoff Block (ADR-031)

Se `temporal.handoff_protocol.enabled: true` AND State Machine attiva:
- `completed_steps[]` nel Handoff Block = proiezione di `history[]` filtrata per `status: completed`.
- `pending_steps[]` = proiezione di `history[]` filtrata per `status: pending`.
- Single source of truth = state file `management/state/<TSK-id>.json` (ADR-028 §B).
- Il Handoff Block **non duplica dati** — li legge dal state file.

**Coupling con il wave dispatch**: il Temporal Handoff Block è **opzionale** dal punto di vista
del dispatch (backward compat R.P3). Il wave dispatch procede **indipendentemente** dalla presenza
del blocco nel payload di ritorno. Se presente, l'Orchestrator lo consuma per aggiornare
`session_context`; se assente, il dispatch non è bloccato (warn solo se Check 4t gato attivo).
Schema del blocco in `dev-handoff.md`/`vcs-handoff.md` — non inline nel scheduler.

### Assenza di nuovo dominio scheduler

EP-011 **non introduce** un dominio scheduler dedicato (es. `temporal: true/false` nei
`scheduler.domains`). Rationale: la Temporal Awareness è una capability trasversale che:
- Non introduce nuovi agenti o tipi di TSK nel DAG.
- Non cambia la struttura degli antichain o la partizione delle wave.
- Si attiva/disattiva per-TSK tramite `is_state_machine_active()`, invisibile allo scheduler.

Pattern diverso da `analytics` (EP-009, dominio separato) o `a11y` (EP-007, sub-step FE):
EP-011 estende il **comportamento interno** degli agenti esistenti, non il topology del DAG.

### Cross-link

ADR-028 (state file schema + standalone/events) | ADR-029 (activation policy) |
ADR-030 (time semantics) | ADR-031 (handoff block) |
[[temporal-awareness-multiagent-patterns]] §Pattern 3 + §Pattern 4.
