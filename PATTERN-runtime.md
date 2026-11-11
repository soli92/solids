> Modulo di PATTERN.md (§18–§20) — indice e versione: [`PATTERN.md`](PATTERN.md).

## §18 — Parallel scheduling (DAG-driven, v2.11)
<!-- profiles: standard, full -->

La factory esegue **per default in serie** ogni operazione di un agente — invariante di sicurezza
(`wiki/` single-committer §7 r.12, append-only su `log.md` §7 r.5, gate cross-tool §7 r.15).
Il **parallel scheduler** è il meccanismo agent-agnostic con cui l'Orchestrator (§2) riconosce
**a runtime** le finestre in cui più operazioni o sub-agent possono essere lanciati in parallelo
senza violare gli invarianti. Vive nell'Orchestrator (Claude Code adapter: `.claude/agents/orchestrator.md`)
ed è alimentato dai campi `depends_on` / `blocked_by` / `code_path` introdotti in §5.

### §18.1 — Modello

Costruisci un DAG `G = (V, E)` dove:

- `V` = artefatti azionabili nello sprint corrente (EP/US/TSK) + operazioni one-shot
  in coda (es. N ingest paralleli su `raw/`).
- `E = E_dep ∪ E_conf`:
  - `E_dep` (causal): `v → u` se `u.depends_on ∋ v` (cascade L3→L4→L5) o se `u.blocked_by` contiene una `Q_NNN` non chiusa che cita `v` (resolution L2→L3).
  - `E_conf` (file-conflict, solo per TSK): `u — v` (arco non orientato) se `intersect(u.code_path, v.code_path) ≠ ∅`. Modellato come pseudo-arco che impedisce la co-esecuzione allo stesso level senza implicare ordine.

### §18.2 — Algoritmo (3 step)

```
schedule(sprint_context, factory_config):
  # 1. Build DAG
  V := candidates(sprint_context)         # status=todo|ready, consumer routing rispettato
  E_dep := { (v→u) | u.depends_on ∋ v OR Q-block(u, v) }
  E_conf := { (u—v) | TSK overlap(u.code_path, v.code_path) }

  # 2. Toposort + level grouping
  if cycle_detected(V, E_dep): ABORT "ciclo in depends_on" — report agli umani
  levels := topo_levels(V, E_dep)         # antichain per level

  # 3. Parallel-safe partition di ogni level
  for L in levels:
    groups := partition(L, E_conf)        # graph-coloring greedy
    # tutti i nodi di groups[i] sono parallelizzabili allo stesso wall-clock
    yield groups
```

**`topo_levels`** è una toposort che assegna a ogni nodo `v` il livello `1 + max(level(parents))`,
con `level(root) = 0`. Nodi senza dipendenze finiscono al level 0 e partono insieme.

**`partition(L, E_conf)`** è graph coloring greedy: itera nodi per `priority DESC, estimate ASC`
(quick wins prima), assegna ciascuno al primo gruppo che non ha conflitti di `code_path`. Output:
gruppi di TSK senza overlap fra loro → eseguibili in parallelo via multi-tool-call dell'Orchestrator
(adapter Claude Code: N `Agent` call nello stesso turno).

### §18.3 — Domini di parallelismo (cosa parallelizzare, cosa no)

| Dominio | Parallelizzabile? | Vincolo / strategia |
|---|---|---|
| **Ingest L1→L2** (`wiki-keeper-worker`) | Sì (già v2.4) | N ≥ 3 raw nel manifest → fan-out N sub-agent; merge serializzato (§16, `ingest-protocol` Fase 1.bis) |
| **Develop TSK→L5** (dev-agent) | Sì (nuovo v2.11) | Antichain calcolato come §18.2. Sub-agent dev distinti possono lavorare su layer/file disgiunti. `vcs-handoff` resta serializzato per ogni commit |
| **Lint check** (`wiki-lint`) | Sì (read-only) | I check sono read-only e indipendenti per file; fan-out trasparente |
| **Query** (`wiki-query`) | Sì (read-only) | Multiple query NL indipendenti — nessun side effect |
| **Plan L2→L3** (`product-manager`) | No (per ora) | Single-committer su `management/`. Candidate v2.12 con sub-agent PM per epica indipendente |
| **Design+Execute L3→L4** (`lead-architect`, `tpm`) | No | Coerenza globale del design — un solo arch per repo per run |
| **Publish L3/L4 → tool esterno** | No | Gate batch_limit §7 r.15, idempotenza via `external_id` richiede serializzazione |
| **Sync (`sync-docs`, `figma-sync`, `repo-sync`)** | Sì per sorgenti diverse | Due `figma-sync` su `file_key` diversi possono girare insieme; due `sync-docs` su PDF diversi anche; un `repo-sync` su path X e un `figma-sync` su `file_key` Y possono girare in parallelo (sorgenti disgiunte). Stessa sorgente → serial (`raw/.extraction-manifest.json` append-only single-writer) |
| **Review** (`code-reviewer`, v2.12) | Sì per TSK indipendenti | Antichain calcolato come `develop` ma su TSK con `status: done` + `review_status: pending`. Overlap `code_path` → serializza (R.S2). Le 3 passate del Reviewer (idiomaticità/design/robustezza, §19.3) sono sub-skill interne, **non sub-agent** — girano in parallelo all'interno della singola invocazione `code-reviewer`. `code_quality/reports/<TSK-id>-iter-N.*` write single-committer per file (R.S1) |
| **Promote `status:`** | No | Operazione meccanica, sub-second; parallelismo non paga |
| **Heal** | No | Loop evaluator-optimizer ha stato condiviso (max 3 iter, single-committer §7 r.12) |
| **Premortem** (`/premortem`, skill `premortem-protocol`, v2.16) | Sì per target distinti (default `parallel` — ADR-004) | Premortem su artefatti diversi sono indipendenti per costruzione: la skill scrive solo in chat + append serializzato sul caller (`wiki/log.md` + `management/risk-registry.md` opt-in + `memory/episodic/premortem-runs.md`). Vedi nota composizione N×M sotto. Opt-out via `domains.premortem: serial` |
| **Analytics** (`analyze_timeline`/`generate_report`, skill `cost-and-time-analytics`, v2.18, ADR-023 §H) | **Parallel cross-scope, serial same-scope** (default `false`, opt-in EP-009) | Report su `project_id`/audience diversi (cross-scope) → parallel. Stesso `scope` (stesso `project_id` o `estimate_id`) → serial: evita race sull'event store e su `analytics/reports/<scope>/`. Composto con EP-010 (stima): stesso dominio `analytics` condiviso → stima e misurazione sullo stesso `project_id` sono serial (la stima consuma la misurazione completata). Indipendente dagli altri domini: ogni tool emette `tool_calls[]` via `record_task_event`, `analytics` legge tutto |
| `a11y` (v2.18, EP-007) | sub-step L2 / tra L2-L3 / off-DAG | parallel cross-TSK, serial same-TSK | composto con `visual-oracle` (mod.1 inline), `ux-ui-review` (mod.2 parallel). Default `false`. |
| `ux-ui-review` (v2.18, EP-008) | sub-step L2 (develop), accodato dopo `visual-oracle` | parallel cross-TSK, serial same-TSK | Sub-step di L2 (no nuovo livello DAG). Cross-TSK → parallel (ogni TSK ha `code_quality/reports/<TSK-id>-uxui-review-iter-<N>/`). Same-TSK → serial (single-writer del report). Composto con `visual-oracle`: attende `visual_status` non-pending; se `visual_status: reject` → ux-ui-review SKIPPED. Composto con `a11y`: scrive `ux_ui_status` (campo distinto da `a11y_status`), no contesa. La sotto-capability `ux-ui-design` (US-029) è **off-DAG** (pre-TSK, input via `ui_design_spec:`). Default `false`. Vedi ADR-019 Punto 3/4. |
| `functional-oracle` (v2.20, EP-018) | gate separato / standalone, accodato dopo `ux-ui-review` (ordering: `develop → visual-oracle → ux-ui-review → functional-oracle → code-review`, ADR-066 §C) | **serial same-app, parallel cross-app** | Same-app → serial: accettazione funzionale app-level condivide serve-port + `code_quality/reports/<TSK-id>-functional-iter-<N>/`; race sul server Playwright e sui file di report evitata. Cross-app (target diversi, app diverse) → parallel (filesystem e server disgiunti). Esecutore: `qa-dev` modalità functional-oracle (ADR-067 §A). Verdict deterministico da asserzioni binarie (ADR-065 §C/§D) — LLM critic solo advisory (ADR-067 §B). Default `false`. Auto-attivato da `fe_correctness.functional_oracle.enabled: true`. Distinto da `visual-oracle` (screenshot statico, per-TSK) e da `review` (code quality). Vedi ADR-065 / ADR-066 / ADR-067. |

**Dominio condiviso `analytics` — pattern di composizione tra capability (v2.18, EP-009 + EP-010)**: EP-010 (stima) **non** introduce un nuovo dominio scheduler né un sotto-dominio: riusa il dominio `analytics` introdotto da EP-009 (misurazione). `analytics` è quindi un **dominio condiviso** tra due capability correlate che insistono sullo **stesso side-channel** (`analytics/events/` + `analytics/reports/`). Questo è il pattern di composizione canonico: *un dominio unico per capability correlate che condividono lo stesso side-channel*, invece di moltiplicare i domini (ADR-023 §rationale 12 — `analytics` è dominio separato dagli altri, ma unico al proprio interno). Conseguenze sulla policy di parallelismo, applicate all'**intero dominio** (non per-EP):
- **Cross-scope → parallel**: stime e/o misurazioni su `project_id`/`estimate_id`/audience diversi girano in parallelo (es. stima di P-8 e misurazione di P-7 insieme).
- **Same-scope → serial**: se misurazione (EP-009) e stima (EP-010) puntano allo stesso scope (stesso `project_id`, o `estimate_id` collegato al medesimo `project_id`) → serial. Ordine: la stima **consuma** la misurazione corrente completata (race su event store + su `analyze_timeline` evitata). La retrospettiva accuracy (`/estimate --review-accuracy=<estimate_id>`), operazione composita che invoca sia EP-009 che EP-010, è serial sul `project_id` collegato all'`estimate_id`. Coerente con la riga **Analytics** della tabella §18.3 sopra.

**Composizione visual ↔ ux-ui conditional (EP-023, v2.22)**: quando `visual_status: conditional`,
il dominio `ux-ui-review` può girare in parallelo al loop visual oracle se
`ux_ui.parallel_during_conditional: true` (opt-in, default `false`). Comportamento default
(flag `false`): serial — ux-ui-review aspetta `visual_status: pass`. Regola di sicurezza:
`visual_status: reject` → ux-ui-review SKIPPED (indipendente dal flag). Il fe-dev riceve
due set di finding nella stessa wave e li applica entrambi nell'iterazione successiva.
Composizione con a11y Modalità 2 sicura senza contesa: `visual_status`, `ux_ui_status`,
`a11y_status` sono campi frontmatter distinti, single-writer distinti. Source of truth:
ADR-019 §Rationale 7. Procedura operativa completa: `.claude/skills/parallel-scheduling.md`
§Dominio `ux-ui-review` → «Procedura di dispatch condizionale».

**Composizione N × M (premortem, v2.16)**: il dominio `premortem` introduce un **secondo livello** di parallelismo annidato. Lo scheduler dispatcha N invocazioni `/premortem` parallele (dominio sopra); ognuna **internamente** esegue la Fase 4 (Parallel Deep-Dives) con fan-out fino a `max_parallel: 8` sub-agent investigatori (cap **hardcoded** nella skill — ADR-001, distinto dal `scheduler.max_parallel`). Esempio peggiore con `scheduler.max_parallel: 4` e 3 `/premortem` attive: 3 × 8 = **24 sub-agent contemporanei**. R.S1 (single-committer, §7 r.12) è preservato automaticamente: i sub-agent della Fase 4 **non scrivono su filesystem**, ritornano solo al caller, che serializza ogni append. I due `max_parallel` (scheduler vs cap interno Fase 4) vivono a livelli diversi e non vanno confusi.

**Temporal Handoff Block inter-wave (v2.18, EP-011, opt-in, ADR-031 §A)**: quando `temporal.handoff_protocol.enabled: true`, ogni sub-agent che completa il proprio scope include nel payload di ritorno verso l'Orchestrator un blocco `temporal_handoff:` YAML (skill `dev-handoff.md` / `vcs-handoff.md`). Il blocco è **opzionale** a livello di scheduler (backward compat R.P3 — a flag spento il payload di ritorno non lo contiene, comportamento identico v2.17); se presente, l'Orchestrator lo consuma per aggiornare `session_context` (elapsed cumulativo, `completed_steps[]`). EP-011 **non introduce un nuovo dominio di parallelismo** (è trasversale, non un nuovo livello DAG). Canale payload: Sub-agent → Orchestrator (return) — vedi §20.2 tabella canali e la nota `to_agent` per `context_summary`.

### §18.4 — Regole inviolabili dello scheduler (estensione §7)

Lo scheduler **deve** rispettare:

- **R.S1 — Single-committer preservato** (§7 r.12). Anche con N dev-agent in parallelo, `wiki/log.md`
  e `wiki/gaps.md` ricevono entry **una alla volta** (il dispatcher accoda le scritture; ciascun
  dev-agent restituisce una entry-line, l'Orchestrator le appende seriali). Mai due agent scrivono
  sullo stesso file nello stesso turno.
- **R.S2 — Conflict-free su `(target, code_path)`** (v2.12 multi-repo aware). Due TSK
  con `intersect(code_path) ≠ ∅` **e** stesso `target` (o entrambi su single-repo legacy)
  **non** possono essere allo stesso group (§18.2 step 3). Due TSK con `target` diversi
  (multi-repo) sono **sempre** conflict-free su file (filesystem disgiunti) — possono
  girare in parallelo anche con glob identici. Glob vuoto = scope sconosciuto =
  serializzante (mai parallelizzato con altri TSK dello stesso target; resta
  parallelizzabile cross-target).
- **R.S3 — Cap di fan-out**. `factory.config.yaml.scheduler.max_parallel` (default `4`) è il
  numero massimo di sub-agent lanciati nello stesso turno. Lo scheduler taglia il group più
  grosso in chunk se eccede il cap.
- **R.S4 — Gate umano sopra `parallel_gate_threshold`** (default `3`). Se un group ha `≥ threshold`
  sub-agent, l'Orchestrator stampa il piano (lista TSK + sub-agent + estimate aggregato) e
  attende `y/N` prima di dispatchare. Analogo a §7 r.15 (publish) e `ingest-protocol` Fase 2.
- **R.S5 — Ciclo nelle dipendenze = ABORT**. Mai "rompere" un ciclo automaticamente: rapporto
  agli umani con la lista delle entry coinvolte.
- **R.S6 — Re-scheduling è idempotente**. Lo scheduler ricostruisce il DAG da capo a ogni `/run`;
  non mantiene stato fra invocazioni (lo stato è derivato §8: filesystem + `wiki/log.md` + `memory/episodic/`).
- **R.S7 — Fallimento di un sub-agent non rollba gli altri**. Se uno dei TSK paralleli fallisce
  (eccezione, output malformato), gli altri proseguono. Il fallimento è annotato in `wiki/log.md`
  come entry `develop-failed TSK-ZZZ` e il TSK resta `status: todo`. Convergenza opportunistica.
- **R.S8 — VCS sempre serializzato**. La skill `vcs-handoff` (§15) esegue commit/branch operations
  **uno per volta**, anche se i dev-agent producono il codice in parallelo. Il dispatcher accoda
  le richieste vcs-handoff alla fine del wave parallelo. (Ragione: `git index lock`, branch state,
  gate umano §7 r.14.)

### §18.5 — `factory.config.yaml.scheduler` (v2.11)

```yaml
scheduler:
  enabled: true                    # false → sempre seriale (modalità conservativa)
  max_parallel: 4                  # cap fan-out per turno (R.S3)
  parallel_gate_threshold: 3       # ≥ N parallel → gate umano (R.S4)
  code_path_conflict: strict       # strict | warn | off
                                   # strict (default): glob overlap → serializza
                                   # warn: glob overlap → warning e procede
                                   # off: disabilita conflict detection (sconsigliato)
  empty_code_path_policy: serial   # serial (default) | parallel
                                   # serial: lista vuota = serializzante
                                   # parallel: lista vuota = parallelizzabile (rischioso)
  domains:                         # opt-in/out per dominio (§18.3)
    ingest:        true
    develop:       true
    lint:          true
    query:         true
    plan:          false           # candidate v2.13
    design:        false
    publish:       false
    sync:          true            # per sorgenti distinte (PDF, Figma, repo)
    review:        true            # v2.12 — Code Reviewer su TSK indipendenti
    premortem:     true            # v2.16 — /premortem su target distinti (composizione N×M, ADR-004)
    analytics:     false           # v2.18 — opt-in EP-009/EP-010; parallel cross-scope, serial same-scope (ADR-023 §H)
    ux-ui-review:  false           # v2.18 — opt-in EP-008; sub-step L2, parallel cross-TSK, serial same-TSK (ADR-019 Punto 3)
    functional-oracle: false       # v2.20 — opt-in EP-018; serial same-app, parallel cross-app (ADR-066 §C); auto-attivato da fe_correctness.functional_oracle.enabled: true
    consistency-check: false       # v2.19 — opt-in EP-015; serial same-TSK (un solo decision_anchor per TSK); auto-attivato da compression.output.consistency_check.enabled: true (ADR-048)
```

Se `scheduler.enabled: false` o assente, comportamento pre-v2.11 (tutto seriale).

### §18.6 — Output dello scheduler (forma osservabile)

L'Orchestrator, alla `/run`, stampa il **wave plan** in chat prima di dispatchare:

```
WAVE PLAN (sprint NN, sched v2.11)
====================================
Level 0 — parallel (3 of max 4):
  ▸ Group A:
    • TSK-007 [be, S, P0] code_path=src/auth/**
    • TSK-012 [db, M, P1] code_path=db/migrations/0042_*.sql
    • TSK-019 [fe, S, P0] code_path=web/src/login/**
Level 1 — serial (2 nodes, depends_on Level 0):
  ▸ TSK-008 [be, S, P0] depends_on=[TSK-007] code_path=src/auth/handlers/**
  ▸ TSK-013 [qa, M, P1] depends_on=[TSK-007,TSK-012,TSK-019] code_path=tests/e2e/**

VCS hand-off accodato seriale dopo ogni wave.
Procedo? [y/N]
```

Se `len(Group) ≥ parallel_gate_threshold`, l'Orchestrator attende conferma esplicita
(R.S4); altrimenti dispatcha. Il piano è loggato in `memory/episodic/` per audit.

**Estensione wave plan temporal budget (v2.19, EP-014, gated `temporal.budget.enabled: true`)**:
quando il governor è attivo, il wave plan acquista 3 campi gated (`token_budget`,
`elapsed`, `estimated_remaining` con `P50`/`P85`/`P95`) + cosmetica `cost_per_1k_tokens`
opzionale (ADR-046 §D). Vedi skill `parallel-scheduling.md` §Temporal Budget Hook per lo
schema YAML completo e §18.8 per il dominio scheduler `budget`. A flag spento il wave plan
resta identico a v2.11 (soli tag `S|M|L`).

### §18.7 — Anti-pattern (cosa lo scheduler NON fa)

- **Mai** sostituirsi al ragionamento dell'Arch: lo scheduler ordina TSK già taskizzati,
  non genera architettura parallela.
- **Mai** parallelizzare un TSK con `consumer: human` (umano è single-threaded; lo scheduler
  filtra solo `consumer: agent`).
- **Mai** dedurre dipendenze "implicite" da `wiki_page:` o `related:` (sono soft references).
  Solo `depends_on` esplicito conta.
- **Mai** parallelizzare la fase di scrittura su `wiki/` (single-committer §7 r.12 invariato:
  i worker producono *proposte*; il `wiki-keeper` principale scrive).
- **Mai** auto-merge in caso di conflitto rilevato: surface al chiamante, no silent resolution.

### §18.8 — Temporal Budget Hook (v2.19, EP-014, opt-in)

> **Nota di numerazione**: ADR-046 §C prescrive questo sotto-paragrafo come «§18.7»; nel
> repo corrente lo slot §18.7 è già occupato dagli Anti-pattern dello scheduler, quindi la
> sezione adotta il prossimo slot libero **§18.8** preservando l'intento dell'ADR (correzione
> meccanica di numerazione, non cambio di intento).

Quando `factory.config.yaml.temporal.budget.enabled: true`, lo scheduler invoca il dominio
opzionale `budget` (gated `scheduler.domains.budget: on|off`, default `off`) che chiama la
skill `temporal-budget-governor` (ADR-043) a ogni step decisionale del loop evaluator-optimizer.
Pattern parallelo ai domini `a11y`, `ux-ui-review`, `premortem`.

- **Punto di iniezione**: inline in Fase 4 (Dispatch) per alimentare il wave plan §18.6 con
  i 3 nuovi campi (`token_budget`, `elapsed`, `estimated_remaining`); inline a ogni step del
  loop (`code-review-protocol` iteration, `dev-protocol` retry, `premortem-protocol` deep-dive)
  per consultare il governor.
- **Verdict**: comunicato al chiamante che esegue (ADR-043 §C). No auto-execution dal governor
  (separation of concerns, pattern parallelo a `code-reviewer`).
- **Gate umano §18.6**: quando `parallel_gate_threshold` triggera, il messaggio canonico mostra
  `token_budget`/`elapsed`/`estimated_remaining` (numeri reali, non solo tag `S|M|L` statici),
  con `~$<dollari>` se `cost_per_1k_tokens != null` (cosmetica ADR-046 §G).
- **Cross-EP**: l'azione `downgrade` consulta R.C7 EP-015 (ADR-049) prima di switchare profilo
  compression.

Vincolo lint: Check 4u (`.claude/skills/lint-checks.md`, WARNING-only, gated
`temporal.budget.required_on_wave_close: true`) intercetta le wave chiuse senza evento
`governor_decision`. A `temporal.budget.enabled: false` (default) l'intera sezione è documentale,
nessun enforcement runtime (comportamento identico a v2.18). Vedi ADR-043..ADR-046 + skill
`temporal-budget-governor.md`.

**Temporal Estimate Protocol (v2.30, EP-043, opt-in)**: se
`temporal.estimate_protocol.enabled: true`, l'orchestratore PUÒ invocare
`temporal-estimate-protocol` nel punto di decisione pre-retry di una wave (DOPO
`temporal-budget-governor`). La skill produce un segnale informativo temporale
complementare al vincolo economico del budget-governor. Il budget-governor
mantiene la priorità: se entrambi indicano `escalate`, il segnale è concordante
e la scelta è diretta; se discordanti, prevale il budget-governor.

## §19 — Code Quality Review Layer (v2.12)
<!-- profiles: standard, full -->

Il **Code Quality Review Layer** (CQRL) è il meccanismo agent-agnostic con cui la factory
valuta **qualità, idiomaticità e robustezza** del codice prodotto a valle di `Develop` (§3),
distinto e complementare al QA funzionale di `qa-dev` (che copre *correttezza*). Vive in
un nuovo ruolo *Code Reviewer* (§2) opzionale e si materializza in un loop
evaluator-optimizer vincolato con i dev-agent (`max_iterations` default `3`), governato
dalle invarianti §19.6 e dalla regola §7 r.16 (gate umano per verdict `reject`).

CQRL **non sostituisce mai** `qa-dev`: i test funzionali restano un gate ortogonale e
prerequisito. CQRL **non copre la sicurezza** (SAST, dependency scanning, secret
detection): quella resta su un layer dedicato fuori dallo scope v2.12.

### §19.1 — Modello a tre componenti

CQRL è un'istanza specializzata del pattern *orchestrator-workers*: il Quality Reviewer
funge da orchestratore di tre passate cognitive specializzate; il Feedback Router chiude
il loop verso il layer di esecuzione L5.

```
   commit / diff TSK ─────────────┐
                                  ▼
                       ┌───────────────────────┐
                       │  Stack Detector       │ → stack_descriptor
                       └───────────┬───────────┘
                                   ▼
                       ┌───────────────────────┐
                       │  Quality Reviewer     │
                       │   pass 1: idiomaticità│
                       │   pass 2: design      │ → finding[] (JSON schema)
                       │   pass 3: robustezza  │
                       │   aggregator          │ → verdict (pass|conditional|reject)
                       └───────────┬───────────┘
                                   ▼
                       ┌───────────────────────┐
                       │  Feedback Router      │ → task_package OR escalation
                       └───────────────────────┘
```

### §19.2 — Stack Detector

Riconosce **lingua + framework + versione** del codice toccato dal TSK leggendo file di
manifest (`package.json`, `pyproject.toml`, `pom.xml`, `go.mod`, `Cargo.toml`, …), config
del framework (`next.config.js`, `manage.py`, `nest-cli.json`, …), import statement e
signature usate. Produce uno **`stack_descriptor`** strutturato che alimenta tutte le fasi
successive.

Schema:

```json
{
  "language": "python",
  "framework": "fastapi",
  "framework_version": "0.110",
  "secondary_libs": ["pydantic@2.6", "sqlalchemy@2.0"],
  "patterns_expected": ["async", "pydantic_v2", "dependency_injection"],
  "ruleset_id": "python.fastapi.v2",
  "confidence": 0.94
}
```

`confidence` è una stima `[0..1]` di quanto il detector sia sicuro del riconoscimento
(manifest chiari + import coerenti → alto; codice senza manifest → basso). Quando
`confidence < code_quality.thresholds.confidence_min` (default `0.6`) il Reviewer opera
in **modalità degradata** (solo regole language-level, no framework-specific), segnala
l'incertezza nel report e raccomanda intervento umano per chiarire lo stack.

Lo `stack_descriptor` viene **allegato a ogni report** in `code_quality/reports/` per
garantire interpretabilità storica (i report restano leggibili anche dopo evoluzioni
del ruleset).

**Riuso**: lo Stack Detector è invocato anche da `repo-sync` (§16) durante l'estrazione
di un repo esistente per popolare la sezione `## Stack rilevato` del documento di
specifiche.

### §19.3 — Quality Reviewer (3 passate + aggregator)

Tre passate specializzate, ciascuna con schema di prompt a 5 sezioni (`role`, `context`,
`input`, `task`, `output_contract`). Principio: un LLM focalizzato su un singolo obiettivo
cognitivo produce review qualitativamente superiori rispetto a una passata
multi-obiettivo (vedi [[code-quality-review-layer]] §Quality Reviewer).

| Passata | `role` (persona) | Focus | Input deterministici extra |
|---|---|---|---|
| **1 — Idiomaticità** | "Core contributor di `{framework}`" | Astrazioni native, naming convention, style guide della community, no pattern deprecati per la versione | Output linter (`ruff`, `eslint`, `golangci-lint`, `clippy`, …) iniettato come contesto per ridurre allucinazioni su regole base |
| **2 — Design** | "Tech lead che dovrà mantenere il codice nei prossimi 2 anni" | Responsabilità, coesione, accoppiamento, naming, abstraction leak, complessità | Metriche pre-calcolate (complessità ciclomatica + cognitiva, nesting depth, fan-in/fan-out, LOC per funzione). Soglie operative: [[cyclomatic-complexity]] (>10 attenzione/>20 blocco), [[cognitive-complexity]] (>15/>30). Tool: `radon cc` (py) · `gocyclo` (go) · `lizard` (multi). Regole canone: `code_quality/rules/canonical/design-complexity.md`. Pattern di refactoring: [[code-complexity-review-rules]]. |
| **3 — Robustezza** | "SRE che ha visto questo codice fallire in produzione" | Error handling idiomatico, edge case, resource leak, concorrenza, validazione input, timeout/retry | — |

**Opzionale (v2.16)**: pass aggiuntivo **`premortem-on-merge`** (4° pass, default **off**, opt-in via `code_quality.passes`). Quando attivo, dopo le 3 passate il code-reviewer invoca la skill `premortem-protocol` con scope `diff of TSK-<id>`, `timeframe: 3mo`, `max_findings: 5` → output mini-Risk-Registry come sotto-sezione `### Premortem on Merge` del report standard (non un verdict separato; logica aggregator invariata). **Touchpoint #3**: se verdict aggregator = `conditional` e TSK ha `risk_classification.tier: tiger-*`, il `task_package` al dev-agent include il suggerimento «considera `/premortem` prima del re-Develop» (mai esecuzione automatica — R.P1/R.P3, ADR-005). Vedi `.claude/skills/code-review-protocol.md` Passata 4 e `wiki/concepts/factory-premortem-integration.md §4.4`.

**4° pass opzionale `accessibility` (v2.18, ADR-016 §H)**: se
`code_quality.passes.accessibility: true`, `code-review-protocol` aggiunge un
4° pass che invoca `run_a11y_scan` (EP-007 US-025) come check addizionale.
Compatibile con il pattern severity-tiered esistente. Indipendente dal dominio
`a11y` (può girare anche se `a11y` dominio off — un derivatore può volere a11y
solo nel CQRL, non in Develop).

**Aggregator**: NON è una 4a passata costosa. Combina due step:
- **Deterministico**: dedup finding per `(file, lines, rule_id)`; severity aggregata per
  `(file, area)`; applicazione di soglie configurabili per stack.
- **Mini-prompt di consolidamento**: produce *executive summary* (≤ 200 parole) e
  *verdict* finale `pass | conditional | reject`.

Output schema del Reviewer (single file JSON per iterazione):

```json
{
  "tsk_id": "TSK-042",
  "stack_descriptor": { "language": "...", "framework": "...", "confidence": 0.94 },
  "iter": 1,
  "findings": [
    {
      "rule_id": "python.fastapi.dependency_injection.misuse",
      "rule_version": "v3",
      "severity": "high | medium | low",
      "file": "src/auth/handlers.py",
      "lines": [42, 58],
      "rationale": "perché è un problema, citando la regola",
      "fix_complexity": "low | medium | high",
      "auto_fixable": false
    }
  ],
  "verdict": "pass | conditional | reject",
  "summary": "executive summary ≤ 200 parole",
  "generated_at": "ISO-8601",
  "reviewer_version": "code-reviewer@2.12.0"
}
```

Companion digest `.md` umano-leggibile (stesso slug, generato dall'aggregator) è
materializzato in `code_quality/reports/<TSK-id>-iter-<N>.md` con sezioni: Stack
rilevato, Verdict, Finding ordinati, Loop status, Prossimo step.

### §19.4 — Feedback Router

Il dev-agent **non legge il report**. Riceve un **`task_package` machine-readable** che
indica esattamente cosa fare, dove, con quali vincoli e criteri di accettazione. Il
report umano-leggibile resta in `code_quality/reports/` per audit e analytics.

**Ordinamento finding** (default): `(severity DESC, fix_complexity ASC)` — prima le cose
gravi e facili. Massimizza l'impatto del primo round e riduce il rischio di iterazioni
multiple.

**Strategie di batching** (`code_quality.router.strategy`):

| Strategia | Trigger | Effetto |
|---|---|---|
| **all-in-one** | `len(findings) ≤ thresholds.batching_split` (default `7`) | Singolo `task_package`, fix completo in un round |
| **severity-tiered** | `len(findings) > batching_split` | Round multipli: critical/high → medium → low, con mini-review intermedia per round |
| **split-by-area** | Finding distribuiti su moduli con `code_path` disgiunto | N `task_package` paralleli — invocazioni multiple del dev-agent abilitate dallo scheduler §18 (antichain conflict-free su `code_path`) |

**Loop control** (analogo strutturale a [[circuit-breaker]] e [[evaluator-optimizer]]):

| Meccanismo | Trigger | Azione |
|---|---|---|
| **Iteration counter** | `review_iter ≥ code_quality.max_iterations` (default `3`) | Verdict forzato a `reject`, escalation umana (§7 r.16) |
| **No-progress detection** | Due iterazioni consecutive con **stesso set di `rule_id` violate** | Escalation immediata: verdict `reject`, marker speciale `no-progress` nel report |
| **Regression detection** | In iter `N+1` emergono finding nuovi in file **non toccati** dalla fix dell'iter `N` | Flag rosso nel report, raccomandazione di rollback al chiamante umano |

Schema `task_package` (consegnato al dev-agent come input ortogonale al TSK):

```json
{
  "tsk_id": "TSK-042",
  "iter": 2,
  "constraint": {
    "scope": "fix only the findings below; no opportunistic refactor",
    "max_diff_lines": 80
  },
  "actions": [
    {
      "rule_id": "python.fastapi.dependency_injection.misuse",
      "file": "src/auth/handlers.py",
      "lines": [42, 58],
      "expected_fix": "descrizione concisa del fix atteso",
      "acceptance_criteria": "criterio verificabile alla prossima passata"
    }
  ],
  "report_ref": "code_quality/reports/TSK-042-iter-1.md"
}
```

**Feedback all'autore originale**: al termine di ogni iterazione, il Router produce un
**digest aggregato** in `code_quality/reports/_digests/<agent>-<YYYY-WW>.md` (settimanale
per dev-agent) — "sui tuoi ultimi N artefatti, errori frequenti su rule Y". Con memoria
persistente per agente (`memory/semantic/dev-<layer>-recurring-issues.md`), questo è il
canale per migliorare a monte e ridurre il carico futuro sul Reviewer (loop di
auto-miglioramento, non auto-modifica del codice).

### §19.5 — Stack-Aware Ruleset

Knowledge base evolutiva sotto `code_quality/rules/` — **side-channel** (simile a
`memory/`), non un layer del cascade L1→L5. Configurata in
`factory.config.yaml.code_quality.ruleset.path`.

**Tre tier** (priorità crescente):

| Tier | Origine | Stabilità | Priorità |
|---|---|---|---|
| **canonical** | Documentazione ufficiale, best practice consolidate | Alta — cambia raramente | Base |
| **emergent** | Pattern emersi da clustering dei finding storici (loop evolutivo) | Media — sotto osservazione | Sovrascrive canonical se più recente sullo stesso `rule_id` |
| **team-specific** | Convenzioni interne del progetto/team | Variabile | Massima — vince sempre |

**Tassonomia ID**: `{language}.{framework}.{category}.{specific_rule}`. Esempi:
- `python.fastapi.dependency_injection.misuse`
- `typescript.react.hooks.missing_dependency`
- `go.stdlib.error_handling.swallowed_error`
- `java.spring.transaction.scope_leak`

La gerarchia permette query naturali su qualsiasi dimensione (tutti i finding di React,
tutti gli error-handling indipendentemente dallo stack, ecc.).

**Anatomia di una regola** (file `code_quality/rules/<tier>/<rule_id>.md`, frontmatter
+ body):

```yaml
---
rule_id: python.fastapi.dependency_injection.misuse
version: v3
tier: canonical
title: "Misuse of FastAPI Depends() in non-route functions"
applies_to:
  language: python
  framework: fastapi
  framework_version_min: "0.95"
  context: ["routes", "handlers"]
severity_default: high
auto_fixable: false
status: active                    # active | disabled
metadata:
  created_at: "2026-04-12"
  author: "human:soli92"
  trigger_count: 47
  false_positive_count: 3
  last_review: "2026-05-20"
references:
  - "https://fastapi.tiangolo.com/tutorial/dependencies/"
---

# Regola

## Rationale
...

## Detection hints
...

## Examples

### Bad
```python
...
```

### Good
```python
...
```
```

Il campo `metadata.false_positive_count` è la metrica chiave per il **degrado attivo**:
regole con tasso `false_positive / trigger` elevato vengono riformulate o passate a
`status: disabled` (mai eliminate — lo stato resta per audit).

**Loop evolutivo del ruleset** (job periodico, cadenza suggerita settimanale; **NON
automatizzato in v2.12** — gate umano obbligatorio):

1. **Clustering** dei finding recenti per similarità semantica (embedding su `rationale`
   + `rule_id` raggruppati).
2. **Identificazione cluster orfani** — gruppi di finding che non mappano a una
   `rule_id` esistente: candidate per nuove regole `emergent`.
3. **Sintesi candidate rule** — un mini-prompt LLM genera una bozza di regola con
   descrizione, esempi reali tratti dai finding del cluster, detection hints. Scritta in
   `code_quality/rules/emergent/<rule_id>.md` con `status: candidate` (variante esplicita
   di `active`/`disabled` per il workflow di review).
4. **Coda di review umana** — la candidate **non viene attivata automaticamente**.
   L'umano (o un agente arbitro con gate) la promuove `status: candidate → active` o la
   scarta.
5. **Degrado regole rumorose** — regole con `false_positive_count / trigger_count` sopra
   soglia → riformulate o `status: disabled` (vedi sopra).

Il loop evolutivo è un'istanza del pattern [[evaluator-optimizer]]: clustering propone
candidati, coda di review è la condizione di terminazione con gate umano.

**Storage v2.12**: filesystem-based (markdown con frontmatter, retrievable via grep/glob).
Per volumi tipici sotto qualche centinaio di regole è sufficiente. Una migrazione verso
DB relazionale + estensione vettoriale (es. `pgvector`) è valutabile quando i volumi
superano la soglia — vedi [[code-quality-review-runbook]] §Storage e indicizzazione. Mai
sovra-ingegnerizzare prima di avere i volumi.

### §19.6 — Invarianti del Code Reviewer (estensione §7)

Il Code Reviewer **deve** rispettare le seguenti invarianti:

- **R.Q1 — Single source di verdict.** Una sola entry `review TSK-ZZZ iter-N → <verdict>`
  in `wiki/log.md` per iterazione. Mai sovrascrivere; sempre append (§7 r.5). Il
  frontmatter del TSK riflette il verdict più recente (`review_status`, `review_iter`,
  `review_report`); la storia completa vive in `wiki/log.md` + `code_quality/reports/`.
- **R.Q2 — Scope di scrittura chiuso.** Il Code Reviewer non scrive in `<code_path>/**`.
  Output esclusivo: `code_quality/reports/**`, append a `wiki/log.md` (entry `review`),
  e modifica del **solo** `review_status:` / `review_iter:` / `review_report:` nel
  frontmatter di TSK con `consumer: agent` (mai del corpo, mai di TSK altrui). In
  modalità *evolutiva* (gate umano, §19.5 loop step 3), scrive anche
  `code_quality/rules/emergent/**` come bozze candidate (mai `canonical/` né
  `team-specific/`).
- **R.Q3 — Verdict `reject` = gate umano.** Mai auto-revert del codice, mai
  auto-close/auto-merge del TSK, mai riapertura automatica del Develop. Vedi §7 r.16.
- **R.Q4 — Bounded loop.** `code_quality.max_iterations` (default `3`) è invariante non
  bypassabile a runtime. Mai bypass automatico; raggiunto il cap → verdict forzato
  `reject` + escalation. No-progress detection (R.Q4-bis) e regression detection
  (R.Q4-ter) accelerano l'escalation **prima** del cap.
- **R.Q5 — Stack-aware obbligatorio quando `confidence ≥ confidence_min`.** Sopra
  soglia, il Reviewer DEVE applicare il ruleset `{language}.{framework}.*`. Sotto
  soglia, modalità degradata (solo `{language}.*`) con flag esplicito nel report.
  Mai applicare regole framework-specific su stack non riconosciuto.
- **R.Q6 — Ruleset write protetto.** `code_quality/rules/canonical/` e
  `code_quality/rules/team-specific/` sono **write-restricted** (curati a mano o da
  agenti arbitri esplicitamente autorizzati, mai dal Code Reviewer). Il Code Reviewer
  può solo proporre bozze in `emergent/` con gate umano per la promozione (§19.5).
- **R.Q7 — Niente sicurezza.** CQRL **non** copre SAST, dependency scanning, secret
  detection. Un finding che identifica un secret in chiaro o una vulnerabilità nota va
  segnalato in `wiki/incidents/` (post-mortem) e mai mascherato come quality finding.

### §19.7 — `factory.config.yaml.code_quality` (schema v2.12)

```yaml
code_quality:
  enabled: false                  # default false; attivare richiede topology con dev-agent
  max_iterations: 3               # R.Q4 — bounded loop (invariante)
  thresholds:
    confidence_min: 0.6           # R.Q5 — sotto soglia → modalità degradata
    batching_split: 7             # |findings| > N → severity-tiered batching (§19.4)
    pass_rate_warn: 0.05          # pass_rate per stack < N → segnala review theater (§19.8)
    false_positive_warn: 0.30     # fp/trigger > N per regola → flag review umana (§19.5 step 5)
  passes:
    idiomaticity: true            # passata 1 (§19.3)
    design: true                  # passata 2
    robustness: true              # passata 3
  router:
    strategy: severity-tiered     # all-in-one | severity-tiered | split-by-area
    max_diff_lines: 80            # constraint passato al dev-agent nel task_package
    ordering: severity_then_complexity   # default; override possibile via `complexity_then_severity`
  ruleset:
    path: ./code_quality/rules/   # KB locale (v2.12 filesystem-based)
    tiers: [canonical, emergent, team-specific]
    evolve:
      enabled: false              # loop evolutivo §19.5 — manuale in v2.12 (gate umano)
      cadence_days: 7             # cadenza suggerita; nessun cron auto in v2.12
  reports:
    path: ./code_quality/reports/
    retain_iterations: 5          # mantieni gli ultimi N report per TSK (rotation)
    digest_cadence: weekly        # feedback all'autore (§19.4)
```

Coerenza inviolabile (segnalata da `wiki-lint`):
- `code_quality.enabled: true` ⇒ topology include almeno un dev-agent E
  `.claude/agents/code-reviewer.md` presente.
- `code_quality.enabled: false` ⇒ TSK senza `review_status` (campo opzionale); nessun
  contenuto in `code_quality/reports/` atteso.

### §19.8 — Anti-pattern (cosa CQRL NON fa)

- **Review theater**: il Reviewer trova sempre qualcosa anche su codice ottimo, perché
  incentivato a "trovare problemi". *Mitigazione*: budget di severity — verdict `pass`
  pulito quando nessun finding `high`/`medium` realmente fondato; tracciamento
  `pass_rate` per stack (`thresholds.pass_rate_warn`); se cronicamente sotto soglia, il
  layer va ricalibrato.
- **Loop infiniti**: dev-agent e Reviewer si rimbalzano lo stesso artefatto senza
  convergenza. *Mitigazione*: iteration counter + no-progress detection + regression
  detection (R.Q4).
- **Drift fra agenti e standard reali**: lo stack evolve (nuove release del framework),
  il Reviewer applica regole vecchie. *Mitigazione*: campo
  `applies_to.framework_version_min/max` su ogni regola; refresh periodico delle
  `canonical` rule basato su release notes (out-of-scope automatico in v2.12).
- **Fix cosmetico**: il dev-agent sposta righe senza capire il rationale per soddisfare
  formalmente la regola. *Mitigazione*: il `task_package` include `expected_fix` +
  `acceptance_criteria` verificabili; la passata successiva valida il rationale, non il
  pattern testuale.
- **Refactor opportunistico**: il dev-agent modifica codice non richiesto durante il
  fix. *Mitigazione*: `task_package.constraint.scope: "fix only the findings below; no
  opportunistic refactor"` + `max_diff_lines` (default `80`).
- **Hallucinated context**: il Reviewer inventa API o nomi inesistenti nei finding.
  *Mitigazione*: prompt delle 3 passate inietta snippet del codice circostante reale +
  linter output deterministici (vedi §19.3).
- **Auto-modifica del codice**: il Code Reviewer **non** committa fix. Le modifiche al
  codice restano scope esclusivo dei dev-agent (§2). Anche regole con
  `auto_fixable: true` producono `task_package` per il dev-agent, mai patch dirette.

### §19.9 — Integrazione con scheduler (§18)

Il dominio `review` (§18.3) è parallelizzabile per **TSK indipendenti**: due review su
TSK diversi possono girare nello stesso wave se i loro `code_path` non si sovrappongono
(R.S2 conflict-detection §18.4 invariato). Le 3 passate di una singola review sono
sub-skill **interne** (non sub-agent), parallele all'interno dell'unica invocazione del
`code-reviewer`.

`wiki/log.md` (append entry `review`) e `code_quality/reports/<TSK-id>-*.{json,md}`
restano single-committer per file (R.S1, §18.4). Il dispatcher accoda le scritture
report come fa per `develop`.

### §19.10 — Pipeline completa con Review (riepilogo)

```
TSK status:todo  ──Develop──▶  status:done, review_status:pending
                                      │
                                      ▼
                              ┌───────────────┐
                              │ code-reviewer │   (R.Q1-R.Q7)
                              └───────┬───────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
         verdict: pass         verdict: conditional      verdict: reject
              │                       │                       │
              ▼                       ▼                       ▼
   review_status:passed    review_iter+=1, task_package  review_status:rejected
        (chiusura)              ──▶ dev-agent re-invoke      gate umano §7 r.16
                                (loop bounded R.Q4)
```

### §19.11 — Ordering visual oracle → review (v2.17, opt-in)

Per i TSK FE con Visual Oracle attivo, l'ordering è **develop → visual-oracle → review**
(ADR-013): il rendering è epistemicamente più fondamentale del codice, quindi va validato
prima. Concretamente, se `factory.config.yaml.fe_correctness.enabled: true` AND
`TSK.layer: fe`, il visual oracle deve aver prodotto `visual_status: pass` **prima** di
invocare `/review`. La **Fase 0 (Bootstrap) di `code-review-protocol`** guadagna una
**precondition additiva**: se `visual_status != pass` la review è abortita con indicazione
di eseguire `/visual-oracle <TSK-id>` (o attendere la Fase 4-bis di `dev-protocol`). A flag
spento (`fe_correctness.enabled: false`, default) o per TSK non-FE la precondition è skip →
comportamento Fase 0 identico a v2.16. Vedi ADR-009 + ADR-013 Punto 2.

**Ordering pipeline FE con UX/UI Review (v2.18, ADR-019)**: la sequenza canonica per TSK FE con
tutti gli opt-in attivi è `develop → visual-oracle → ux-ui-review → code-review`. La UX/UI Review
(EP-008) si inserisce **tra** visual-oracle e code-review: il visual oracle verifica l'aderenza alla
specifica (oggettivo), la ux-ui-review valuta euristiche e dimensioni (soggettivo strutturato sulla
rubrica), il CQRL valuta il codice finale (post eventuali refactor indotti dai finding UX). Precondition
Fase 0 di `code-review-protocol`:
- `visual_status: pass` → **hard ABORT** se assente (ADR-013, vedi sopra).
- `ux_ui_status in [pass, skip]` → **nota informativa, no ABORT** (ADR-019 Punto 2): la review UX è
  additive value, non precondizione semantica del code-review; lo skip esplicito (`ux_ui_status: skip`
  + `ux_ui_skip_reason`) è scelta legittima del derivatore.

Combinazioni parziali (qualunque sotto-insieme di opt-in) preservano backward compat v2.17: solo
`ux_ui.enabled` → ux-ui-review subito dopo Develop FE; `fe_correctness + code_quality` (no ux_ui) →
comportamento v2.17 invariato. A `ux_ui.enabled: false` (default) la ux-ui-review è no-op. Vedi
ADR-019/ADR-020.

## §20 — Output Compression Layer (v2.14)
<!-- profiles: full -->

L'**Output Compression Layer** (OCL) è il meccanismo agent-agnostic con cui la factory
**riduce i token generati** dagli agenti applicando una grammatica di compressione
linguistica ([[caveman]]) ai soli canali di messaging effimero, lasciando intatti gli
artefatti persistenti (wiki/, management/kanban/, code/, …). È **opt-in**, configurato
in `factory.config.yaml.compression.output`, default `enabled: false`.

OCL **non sostituisce mai** la leggibilità degli artefatti karpathy-style (§7 r.18). È un
layer *trasversale* (intercetta i flussi di comunicazione tra agent e tool) e non un
nuovo verbo di operazione canonica (§3). La compressione è effettuata dal sub-skill
`caveman-protocol` invocato dall'agente prima di emettere un payload verso un altro
agente/tool.

Il design di alto livello vive in [[factory-compression-layer]] (concept wiki); questa
sezione fissa il contratto invariante. Il sotto-asse "context compression" (Graphify) è
**out-of-scope v2.14**: introduzione pianificata per v2.15 (vedi §21 Versioning).

### §20.1 — Modello a un asse (v2.14: solo output)

Caveman intercetta il **payload generato** da un agente prima che venga emesso al
destinatario (sub-agent, tool, orchestrator). Quattro operazioni grammaticali (vedi
[[caveman]] §Logica di funzionamento):

1. Rimozione funzioni grammaticali (articoli, verbi essere, preposizioni deducibili)
2. Eliminazione padding sociale (hedging, cortesia, preamboli, postamboli)
3. Abbreviazioni convenzionali (`fn`, `ret`, `→`, simboli quantificatori)
4. Strutturazione tabellare/lista (prosa non informativa → tabella o lista minimale)

Tre livelli di intensità: `lite` / `full` / `ultra`. L'asse context (Graphify) sarà
introdotto in v2.15.

### §20.2 — Allow-list per canale e policy profile

Il comportamento è **policy-driven** (configurato esternamente, non hardcoded nel codice
degli agent). Tre profili selezionabili in `factory.config.yaml.compression.output.policy_profile`:

| Profilo | Risparmio atteso | Caratteristica | Quando usarlo |
|---|---|---|---|
| `conservative` (**default**) | 50–70% | Drift minimo, audit trail ricco, chain-depth downgrade attivo | Factory new, primo deployment, topologie con chain lunghe |
| `aggressive` | 70–85% | Risparmio massimo, accetta drift cumulativo | Factory mature, topologia `knowledge-only`, dopo ≥ 2 settimane di validazione |
| `custom` | Variabile | Matrice esplicita (override completo dei preset, invarianti restano enforced) | Debugging di un drift specifico, esigenze esotiche |

**Matrice canale × profilo** (R.C2):

| Canale | `conservative` | `aggressive` | Override `custom` |
|---|---|---|---|
| Orchestrator → Sub-agent (dispatch) | `full` | `ultra` | ✓ |
| Sub-agent → Tool (Bash, Read, Grep, …) | `ultra` | `ultra` | ✓ |
| Tool → Sub-agent (result) | `lite` | `full` | ✓ |
| Sub-agent → Orchestrator (return) | `full` | `ultra` | ✓ |
| Sub-agent → Sub-agent (sibling, es. `wiki-keeper-worker` → `wiki-keeper`) | `full` | `ultra` | ✓ |
| `feedback-router` → dev-agent (task package) | `full` | `ultra` | ✓ |
| **Qualsiasi → utente finale (`to_user`)** | `off` | `off` | **NO (R.C1)** |
| **Qualsiasi → file artefatto (`to_artifact`)** | `off` | `off` | **NO (R.C1)** |
| **`propagate-resolution` → wiki page update** | `off` | `off` | **NO (R.C1)** |

`to_artifact` include: `wiki/**`, `management/kanban/**`, `<code_path>/**`,
`design_&_architecture/**`, `code_quality/**`, `memory/**`, `raw/**` (output dei Sync).

**Canale `to_agent` — `temporal_handoff.context_summary` (v2.18, EP-011, ADR-031 §G)**: il blocco `temporal_handoff:` emesso da un sub-agent nel payload di ritorno verso l'Orchestrator transita nel canale **Sub-agent → Orchestrator (return)** (`full` conservative, `ultra` aggressive — tabella sopra). Il campo `context_summary` all'interno del blocco è **comprimibile**: non è marcato `DO NOT COMPRESS` (a differenza di `decision_anchor`, non-comprimibile per R.C7). **Vincolo**: `context_summary` deve contenere informazioni di contenuto non replicate da `completed_steps[]` (ADR-031 §A, contratto cross-skill `dev-handoff.md` + `vcs-handoff.md`). A flag spento (`temporal.handoff_protocol.enabled: false`) il blocco non è emesso e questo canale non è attivato.

### §20.3 — Topology-aware default

Il `policy_profile` ha un default per topologia (modificabile dall'utente):

| Topologia (§13) | Default `policy_profile` | Rationale |
|---|---|---|
| `knowledge-only` | `aggressive` | Chain corte (ingest paralleli), rischio drift basso, no `code_path` |
| `plan-only` | `conservative` | Chain medie (PM → TPM), no `code_path` |
| `full-stack-agents` | `conservative` | Chain lunghe (orch → PM → TPM → dev), `code_path` attivo |
| `hybrid-be-agents` / `hybrid-fe-agents` | `conservative` | Solo il sotto-grafo agentificato beneficia di Caveman |
| `custom` | `conservative` | Default sicuro; utente esplicita override |

In topologie federate ([[federated-topology]]), la compressione **non attraversa il
boundary cross-factory** (R.C4): si applica solo intra-factory.

### §20.4 — Invarianti del Compression Layer (R.C1–R.C7, estensione §7)

Il Compression Layer **deve** rispettare le seguenti invarianti:

- **R.C1 — Invarianti non overridabili.** I canali `to_user`, `to_artifact` (qualsiasi
  scrittura su filesystem persistente) e `propagate-resolution → wiki page update` sono
  **sempre `off`** indipendentemente dal `policy_profile`. Anche in `custom`, l'override
  non può attivare la compressione su questi canali. Vincolato a §7 r.18.
- **R.C2 — Allow-list channel-aware.** Ogni payload emesso da un agente verso un altro
  agente/tool deve essere dichiarativamente associato a un *canale* (vedi tabella
  §20.2). Il `caveman-protocol` applica il livello di compressione configurato per quel
  canale + profilo. Un payload senza canale identificabile → fallback automatico a
  `normal mode` (no Caveman) + warning in `wiki/log.md`.
- **R.C3 — Chain-depth severity ceiling.** Solo nel profilo `conservative` (e in `custom`
  che lo abilita esplicitamente). Quando la chain di handoff (orchestrator → sub-agent →
  sub-agent → tool …) supera profondità `3`, il livello di compressione viene
  auto-degradato di un step (`ultra → full → lite`). Mitigation per drift cumulativo
  (vedi [[caveman]] §Rischi principali). `aggressive` disabilita questo meccanismo.
- **R.C4 — Cross-factory boundary OFF.** In topologie federate ([[federated-topology]]),
  la compressione è **sempre `off`** sull'handoff cross-factory. Modelli o versioni diverse
  fra factory hanno vocabolari Caveman incoerenti → handoff ellittico ambiguo. Questa
  regola non è bypassabile via `policy_profile`.
- **R.C5 — Drift fallback automatico.** Se un sub-agent risponde con marker di ambiguità
  riconosciuto (`AMBIGUOUS_HANDOFF`, `REQUEST_CLARIFY`, exception interpretativa
  documentata), l'orchestrator **rinvia la stessa request in normal mode** (no Caveman) e
  appende a `wiki/log.md` un marker `compression-drift TSK-ZZZ canale=<C> profilo=<P>`.
  Il fallback non termina il loop ma lo riporta a stato non compresso per quel TSK.
- **R.C6 — Opt-in totale, backward compatibility.** `compression.output.enabled: false`
  di default. Factory v2.13- senza il blocco `compression:` in `factory.config.yaml` si
  comportano identiche a v2.13. Nessuna migrazione obbligatoria del frontmatter agent
  o skill. Il campo `caveman_policy:` nei frontmatter agent (§20.6) è **opzionale**:
  agenti senza il campo ricevono il default conservative per il loro canale principale.
- **R.C7 — Decision-preserving compression + ban `aggressive` su chain profonde** (v2.19,
  EP-015, ADR-049/050/051). Due regole accoppiate, gated da `compression.output.enabled: true`
  (a flag spento R.C7 è no-op):
  - **Decision anchor non comprimibile.** Il blocco `decision_anchor` (US-058, ADR-047 —
    campo metadata YAML + sezione testuale marker `## DECISION ANCHOR (DO NOT COMPRESS)`,
    doppia ridondanza) è **NON comprimibile** dalla pipeline caveman, **indipendentemente
    dal profilo** (`conservative`, `aggressive`, `custom`). La pipeline isola il blocco
    prima di comprimere e lo passa through byte-equal (parallelo a "preserve metadata,
    compress content").
  - **Ban `aggressive` su chain profonde.** Il profilo `aggressive` è **vietato** quando
    `(chain_depth > 3 AND active_capabilities > 5) OR chain_depth > 5` (soglie strict `>`,
    ADR-049 §A/§C):
    - `chain_depth` = `len(handoff_chain)` al momento del check (counter monotòno da
      `task_started_at`, mai decrementato; regressione → ERROR `[chain-depth-regression]`).
    - `active_capabilities` = numero di capability opt-in attive nel workflow corrente
      (snapshot a `task_started_at`; 15 capability canoniche v2.19, lista in ADR-049 §A).
  - **Migration soft (default, `migration.strict: false`).** Su violazione: downgrade
    runtime automatico `aggressive → conservative` (NON persisted in config, R.A1) + WARNING
    fail-loud in `wiki/log.md` (marker `[R.C7-migration:soft]`) + telemetria EP-013
    `state: compression_downgrade` (ADR-050 §B/§D). Workflow prosegue. Con
    `migration.strict: true` (opt-in): hard fail con instruction per il maintainer (ADR-050 §C).
  - **R.C7 estende R.C3.** R.C3 (`chain_depth_downgrade`) era **spento da `aggressive`**;
    R.C7 reintroduce il safety net per `aggressive`. R.C3 resta invariato nella propria
    definizione (per `conservative`/`custom` che lo onorano già). Pattern belt + suspenders.
  - **Cross-EP coordination con EP-014 governor.** L'azione `downgrade` del governor
    (ADR-043 §F) **deve** consultare R.C7 prima dello switch di profilo, per non forzare
    upgrade `conservative → aggressive` (violazione di R.C7 al contrario); se R.C7 ha già
    downgrade-ato, il governor downgrade è no-op idempotente (ADR-049 §G).
  - **Niente nuova invariante §7.** R.C7 vive in §20.4 (sezione esistente), non in §7; §7
    resta a 18 invarianti (R.1–R.18). Pattern coerente v2.16–v2.19 (ADR-051 §G).

### §20.5 — `factory.config.yaml.compression` (schema v2.14)

```yaml
compression:
  output:
    provider: caveman           # caveman | none
    enabled: false              # default OFF, opt-in (R.C6)
    install_command: "curl -fsSL https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.sh | bash"
    policy_profile: conservative   # conservative | aggressive | custom
    # Invarianti R.C1 — mai overridabili, presenti per esplicitazione documentale:
    invariants:
      to_user: off
      to_artifact: off
      propagate_resolution: off
    # channels: usato SOLO se policy_profile == custom (override completo dei preset)
    channels:
      orchestrator_to_subagent: full
      subagent_to_tool: ultra
      tool_to_subagent: lite
      subagent_to_orchestrator: full
      sibling_to_sibling: full
      feedback_router_to_devagent: full
    chain_depth_downgrade: true       # R.C3 — auto-downgrade su chain depth > 3 (solo conservative)
    chain_depth_threshold: 3
    cross_factory: off                # R.C4 — sempre off in federated; off significa OFF cross-factory, on intra-factory
    drift_fallback:
      enabled: true                   # R.C5 — fallback automatico su marker ambiguità
      markers: [AMBIGUOUS_HANDOFF, REQUEST_CLARIFY]
    audit_trail_for:                  # canali sempre in normal mode anche se policy diversa
      - propagate-resolution
      - feedback-router               # task package interno: tracciabilità completa

  # Asse context (Graphify) — placeholder v2.14, attivazione v2.15
  context:
    provider: none                    # graphify-cloud | graphify-ollama | none (v2.14: solo none)
    enabled: false
```

Coerenza inviolabile (segnalata da `wiki-lint`):
- `compression.output.enabled: true` ⇒ `provider` valorizzato + Caveman installato (test
  empirico: `caveman --version` ritorna OK) + topology compatibile (qualsiasi tranne
  `knowledge-only` con `aggressive` di default).
- `compression.output.policy_profile == custom` ⇒ `channels` block valorizzato
  completamente (no fallback ai preset).
- `compression.output.enabled: false` ⇒ il blocco `channels` viene ignorato; nessun
  agent invoca `caveman-protocol`.

### §20.6 — Frontmatter agent: `caveman_policy:` (opzionale)

Un agent può dichiarare un override locale nel proprio frontmatter:

```yaml
---
name: be-dev
description: Backend developer agent
caveman_policy:                       # opzionale; se assente, default da factory.config.yaml
  to_subagent: full
  to_tool: ultra
  drift_fallback_enabled: true
---
```

Convenzione: il frontmatter agent **non può** mai abilitare un canale che la config
globale ha `off` (R.C1 enforced — il `caveman-protocol` esegue check pre-invocazione).
Può solo *abbassare* il livello (es. `ultra → full`) per debugging di drift locale.

### §20.7 — Integrazione con scheduler (§18)

Il dominio scheduler **`compression`** è introdotto come *concetto* ma non è un dominio
parallelizzabile separato: la compressione è un **intercept inline** nel dispatch della
wave. Per ogni payload emesso dall'orchestrator verso un sub-agent nella wave:

1. Lo scheduler determina il *canale* (es. `orchestrator_to_subagent`)
2. Invoca `caveman-protocol §Fase 2` con `payload`, `channel`, `profile`, `chain_depth`
3. Il payload compresso viene poi passato all'agent come argomento del tool call

Per i `return value` dei sub-agent (sub-agent → orchestrator), la compressione è
applicata dall'agent emittente prima del return (skill `caveman-protocol` chiamata
internamente). Il `wave_report.md` (output di `state-scan` esteso) include una colonna
`tokens_compressed / tokens_raw` per canale per misurare l'efficacia.

`compression.output.enabled: false` → l'intercept è no-op (zero overhead).

### §20.8 — Anti-pattern (cosa OCL NON fa)

- **Compressione su artefatto persistente**: rompe il pattern karpathy-style del wiki/
  e la struttura dei TSK/EP/US. *Mitigazione*: R.C1 invariante non overridabile + Check
  4k del lint (verifica enforcement R.C1 in caveman-protocol invocations).
- **Compressione `ultra` su chain depth > 3 in conservative**: drift cumulativo
  ambiguità di handoff. *Mitigazione*: R.C3 chain-depth severity ceiling automatico.
- **Compressione su modelli non testati**: Caveman è progettato per fraseggio
  Claude/GPT; modelli diversamente fine-tunati possono produrre output ambigui.
  *Mitigazione*: in `caveman-protocol` Fase 1 (Bootstrap) test empirico su `caveman
  --version` + matrice di compatibilità documentata; per modelli non testati, fallback
  conservativo a `lite`.
- **Allow-list inconsistente fra profilo e custom**: utente attiva `custom` ma dimentica
  campi → fallback ai preset oscuro. *Mitigazione*: `wiki-lint` Check 4k segnala
  `channels` block incompleto in `custom` come ERROR (no auto-fallback).
- **Auto-modifica delle policy a runtime**: nessun agente può scrivere
  `factory.config.yaml.compression.*` (config è user-controlled, §8). Solo via
  `/compression set <param> <value>` con gate umano.
- **Ignorare drift fallback marker**: orchestrator ignora `AMBIGUOUS_HANDOFF` e
  continua in compressed mode. *Mitigazione*: R.C5 fallback automatico obbligatorio
  con marker `compression-drift` in `wiki/log.md`.

### §20.9 — Pipeline completa con OCL attivo (riepilogo)

```
       config: compression.output.enabled: true, policy_profile: conservative
                                          │
              Orchestrator emette payload  │  → caveman-protocol intercept
                                          ▼
                         ┌────────────────────────────────────┐
                         │ caveman-protocol (Fase 2)          │
                         │   - identifica canale              │
                         │   - applica livello dal profilo    │
                         │   - check R.C1 invariants          │
                         │   - check R.C3 chain depth         │
                         │   - check R.C4 cross-factory       │
                         └────────────────┬───────────────────┘
                                          ▼
                              payload_compressed → sub-agent
                                          │
                              sub-agent risposta
                                          │
                         ┌────────────────┴───────────────────┐
                         │ Risposta contiene marker ambiguità?│
                         └─────┬──────────────────┬───────────┘
                               ▼ NO              ▼ SÌ (R.C5)
                       continua wave    ──────► fallback normal mode
                                                + log compression-drift
```

### §20.10 — Context Compression Layer (v2.14 Fase 2, Graphify code_path)

Il **secondo asse** del Compression Layer riduce i token **passati come contesto** ai
dev-agent (al posto dei file sorgente raw del `code_path`). L'implementazione canonica
è [[graphify]]: trasforma `<code_path>` in un knowledge graph queryabile
(`.graphify-state/code_paths/<slug>/GRAPH_REPORT.md`) che il dev-agent legge come
input contestuale. Opt-in, configurato in `factory.config.yaml.compression.context`.

L'asse context è **complementare e ortogonale** all'asse output (§20.1-§20.9):
Caveman riduce ciò che gli agent *generano*, Graphify riduce ciò che gli agent
*consumano*. Possono coesistere: una factory può attivare uno, l'altro, o entrambi.

#### §20.10.1 — Confidence-gated dispatch

Graphify produce nodi e archi taggati con tre livelli di confidenza:

| Tag | Origine | Affidabilità | Uso |
|---|---|---|---|
| `EXTRACTED` | AST tree-sitter (deterministico) | Alta — riproducibile | Eseguibili: dev-agent in modifica file |
| `INFERRED` | LLM-driven (semantica) | Media — variabile | Esplorativi: design proposals, query NL |
| `AMBIGUOUS` | Conflitto fra sorgenti AST/LLM | Bassa — da rivedere | Audit: code-reviewer in modalità review |

Lo scheduler (§18) applica un **gating per ruolo agent** quando dispatcha un TSK in
modalità context-compression:

| Ruolo agent | Nodi/archi consumati | Esempio operativo |
|---|---|---|
| **Executor** (modifica file: `be-dev`, `fe-dev`, `db-dev`, `qa-dev`) | Solo `EXTRACTED` | Task di refactor/fix con base AST garantita |
| **Explorer** (genera proposte: `lead-architect`, `wiki-query`) | `EXTRACTED` + `INFERRED` | Design ADR, esplorazione codebase per concept proposal |
| **Reviewer** (audit: `code-reviewer`) | Tutto con flag visibile | Review con blast radius analysis |

Specializzazione del pattern [[verifier-as-gate]] applicata al consumo di contesto.

#### §20.10.2 — `factory.config.yaml.compression.context` (schema v2.14 Fase 2)

```yaml
compression:
  context:
    provider: graphify-cloud        # graphify-cloud (default) | graphify-ollama | none
    enabled: false                  # default OFF, opt-in (R.G6)
    package: graphifyy              # safishamsi/graphify (PyPI: doppia y)
    # Privacy: graphify-cloud manda docs/immagini all'API LLM
    # graphify-ollama: locale, 16+ GB VRAM, qualità inferiore (enterprise data residency)
    ollama:
      model: llama3.1:8b
      vram_gb_min: 16
    targets:
      - kind: code_path
        name: backend              # match factory.config.yaml.code_paths[].name
        gitignore_patterns:
          - "*.env"
          - "secrets/**"
      # - kind: wiki                # v2.15 only, gated da PoC karpathy preservation
      #   path: wiki/
    update_strategy: incremental    # incremental | manual | always
    full_rebuild_cron: "0 0 * * 0"  # weekly (R.G4 drift mitigation)
    drift_alert_days: 7             # alert se delta last_ast vs last_full_rebuild > N gg
    ci_strategy:
      mode: cache-with-fallback     # cache-with-fallback (default) | disabled | always-rebuild
      cache_provider: actions       # actions (GitHub) | gitlab | s3 | local
      cache_key_prefix: graphify-state
      stale_threshold_hours: 168    # 7 giorni → fallback scansione filesystem
      full_rebuild_on_demand: true
    confidence_gating:
      executor: [EXTRACTED]
      explorer: [EXTRACTED, INFERRED]
      reviewer: [EXTRACTED, INFERRED, AMBIGUOUS]
    mcp_server:
      enabled: false                # opt-in con MCP runtime
      topology: per-agent           # per-agent (isolato) | shared (factory mature)
      crg_tools_max: 8              # CRG_TOOLS env var (riduce ~25 tool → ~8)
```

Coerenza inviolabile (segnalata da `wiki-lint`, Check 4l v2.15):
- `compression.context.enabled: true` ⇒ `provider` valorizzato + Graphify installato
  (`graphify --version` — binario singola-y, da `pip install graphifyy` doppia-y; o `graphify-ts --version`) + topology include
  almeno un dev-agent + `code_paths` non vuoto.
- `targets` non vuoto se `enabled: true`.
- `targets[i].kind == wiki` ⇒ riservato a v2.15 con PoC karpathy gate (vedi
  [[factory-compression-layer]] §Fase 3a).

#### §20.10.3 — Integrazione con code-reviewer (CQRL, §19)

Il [[code-quality-review-layer]] beneficia di Graphify come pre-check:

- Prima dell'invocazione del Reviewer su un TSK con `status: done`, lo scheduler
  invoca `graphify get_impact_radius(<file>)` per ciascun file toccato dalla fix.
- Output: lista di symbol/file dipendenti (downstream blast radius).
- Il `task_package` (§19.4) include il blast radius come constraint esplicito:
  `"non toccare i symbol [...] senza valutarne l'impatto su [downstream files]"`.
- Riduce il rischio di **regression detection** in iter `N+1` (R.Q4-ter §19.4).

#### §20.10.4 — Drift mitigation

`EXTRACTED` (AST) si aggiorna ad ogni commit via post-commit hook (zero token,
~0.4s/1k file). `INFERRED` (LLM-semantica) richiede full rebuild (2–20 $ token).
Questo causa drift asincrono se non gestito.

| Meccanismo | Frequenza | Costo | Mitigation di |
|---|---|---|---|
| **Incremental update** (AST only) | Post-commit, all'apertura di sessione | Zero token | Disallineamento file ↔ AST nodes |
| **Full rebuild semantico** | Cron weekly | 2–20 $ | Drift asincrono concept↔code |
| **Drift monitoring** | Daily check | Zero token | Alert se `delta(last_ast, last_full_rebuild) > drift_alert_days` |
| **Manual trigger** | Post-refactor maggiori | Su richiesta | `/graphify-sync <target> --force` |
| **CI cache-with-fallback** | Ogni pipeline | Zero (cache hit) o nessun build (fallback) | Costo CI |
| **Ghost duplicates dedup** | Post full rebuild | Zero token | Bug noto Graphify (AST↔semantica disagree su ID) |

#### §20.10.5 — Pipeline completa con context compression attiva

```
       config: compression.context.enabled: true, targets: [code_path=backend]
                                          │
                   Dev-agent invocato su TSK (status:todo, target:backend)
                                          ▼
                         ┌────────────────────────────────────┐
                         │ Scheduler context-resolve          │
                         │  read .graphify-state/code_paths/  │
                         │  filtra per confidence_gating role │
                         │  (executor → EXTRACTED only)       │
                         └────────────────┬───────────────────┘
                                          ▼
                              GRAPH_REPORT.md filtered → dev-agent
                                          │   (al posto dei file sorgente raw)
                                          ▼
                              Dev-agent legge contesto compresso
                                          │   (es. 200k token raw → 3k token graph)
                                          ▼
                              Dev-agent scrive file in <code_path>
                                          │
                              Post-commit hook: incremental update
                                          │   (.graphify-state/ aggiornato AST)
                                          ▼
                              [opzionale] Code reviewer:
                                  get_impact_radius(<files>) → blast radius
                                  task_package include constraint
```

### §20.11 — Invarianti del Context Compression (R.G1–R.G6, v2.14 Fase 2)

L'asse context **deve** rispettare le seguenti invarianti (parallele a R.C1–R.C6
dell'asse output):

- **R.G1 — Filesystem è single source of truth.** `.graphify-state/` è una *view
  derivata*, mai authoritative. In caso di conflitto graph ↔ filesystem (es. node
  nel graph che non corrisponde a un file reale, o file presente ma assente nel
  graph) → **vince filesystem**, graph viene rebuiltato. Mai sincronizzazione
  bidirezionale.
- **R.G2 — Confidence-gated dispatch obbligatorio.** Lo scheduler DEVE filtrare i
  nodi del graph per `confidence_gating` in base al ruolo dell'agent destinatario
  (executor/explorer/reviewer, §20.10.1). Mai consegnare `INFERRED` o `AMBIGUOUS`
  a un executor agent (R.G2 enforced dal `caveman-protocol §Fase 2` analogo per
  context). Violazione = chain di modifiche basate su relazioni inferite incerte.
- **R.G3 — Blast radius pre-check su modifiche.** Se `compression.context.enabled:
  true`, prima di ogni modifica del codice da parte di un dev-agent, lo scheduler
  invoca `graphify get_impact_radius(<files_to_modify>)` e include il risultato nel
  task_package del dev-agent come constraint esplicito (vedi §20.10.3). Il
  dev-agent può rifiutare la modifica se il blast radius eccede la soglia
  (`max_diff_lines × downstream_depth`). Mai fix silente con blast radius elevato.
- **R.G4 — Drift mitigation obbligatoria.** L'asse context DEVE prevedere:
  - Incremental update post-commit (via git hook o all'apertura di sessione, zero token)
  - Full rebuild semantico periodico (cron weekly default)
  - Drift monitoring (daily check di `delta(last_ast, last_full_rebuild)`)
  - Alert quando delta > `drift_alert_days` (default 7)
  In assenza di queste 4 protezioni → ERROR di config (segnalato da `wiki-lint`
  Check 4l).
- **R.G5 — Side-channel write-restricted.** Solo `graphify-sync` scrive in
  `.graphify-state/**`. Nessun altro agent (dev, code-reviewer, wiki-keeper, …) ci
  scrive. Il path è `.gitignore`-d in fase di scaffolding (R.G6 backward compat).
  Lettura aperta a tutti gli agent che hanno `<code_path>/**` o `wiki/**` nel proprio
  read scope.
- **R.G6 — Opt-in totale, backward compatibility.** `compression.context.enabled:
  false` di default. Factory v2.14 Fase 1-only (solo output axis) senza il blocco
  `context:` valorizzato si comportano identiche. Migration v2.14 Fase 1 → Fase 2
  è additiva: nessun cambio breaking del frontmatter agent / skill esistenti.
  `.graphify-state/` viene aggiunto al `.gitignore` come parte del bootstrap Fase 2
  (mai versionato).

### §20.12 — Telemetria `cache_savings_pct` per promotion evidence-based (v2.18, opt-in EP-009)

Quando la capability analytics di misurazione è attiva (`analytics.measurement.enabled: true`,
EP-009), ogni «Analytics Report» executive espone nel blocco `split` il campo derivato
**`cache_savings_pct`** (% di risparmio dovuto a cache token, `cache_read + cache_write`
vs prezzo input pieno; ADR-024 §D). È **telemetria automatica del Compression Layer v2.14**:
misura il ROI reale del caching prodotto da Caveman (asse output, §20.1-§20.9) e Graphify
(asse context, §20.10-§20.11). Il valore è **derivato** dagli eventi (mai inserito a mano)
e visibile a primo livello (dentro `split`) senza dover esplorare i breakdown. Fornisce
l'**evidenza misurata** per decisioni di promozione data-driven sul compression layer
(es. promuovere `policy_profile: conservative → aggressive`, o decidere se `compression.context.enabled`
ripaga il costo). Nessun automatismo: il framework misura e riporta, la decisione di promozione
resta umana. A `analytics.measurement.enabled: false` il campo non è prodotto (nessun report).
Attivazione esplicita via `analytics.measurement.report_compression_savings: true`.

