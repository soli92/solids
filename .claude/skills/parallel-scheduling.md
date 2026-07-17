# Skill: Parallel Scheduling

> Adapter Cursor della skill `parallel-scheduling` definita in PATTERN.md. Riferimenti agent → `.cursor/rules/<name>.mdc`; skill → `.cursor/skills/<name>/SKILL.md`.

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
- `Glob management/kanban/**/US-*.md` per il **resolve** di `depends_on TSK` cross-storia (vedi §1).
- Read `factory.config.yaml.scheduler` (default valori in PATTERN §18.5 se assente).
- Read `wiki/gaps.md` per `blocked_by Q_NNN` ancora aperte.
- **Dominio `premortem` (v2.16)**: invocazioni `/premortem` su target distinti (EP/US/TSK/wiki-page/descrizione diverse) sono candidate alla wave parallela quando `scheduler.domains.premortem: true` (default). Sono indipendenti per costruzione (write serializzato sul caller). **Attenzione ai due livelli di `max_parallel`**: il `scheduler.max_parallel` limita quante `/premortem` girano insieme (livello dominio); il cap `max_parallel: 8` **hardcoded nella skill `premortem-protocol`** (Fase 4, ADR-001) limita il fan-out interno dei sub-agent deep-dive di **ogni** premortem. Sono distinti e si compongono in N×M (vedi PATTERN §18.3). Il gate `parallel_gate_threshold` si applica al numero di premortem (N), non ai sub-agent interni (M).
- **Dominio `visual-oracle` (v2.17)**: la verifica visiva (`visual-oracle-protocol`, EP-005) sui TSK FE è candidata alla wave quando `scheduler.domains.visual-oracle: true` (default `true` se `factory.config.yaml.fe_correctness.enabled: true`, altrimenti no-op). **Inquadramento: sub-step di L2 (develop), NON un nuovo livello DAG.** Il visual oracle gira logicamente dopo la Fase 4 di `dev-protocol` (build/typecheck verde) e prima della Fase 5 (handoff a `status: done`), cioè dentro L2 e prima di L3 (review) — vedi ADR-013 §Punto 3. Politica di parallelizzazione:
  - **Cross-TSK → parallel**: il visual oracle su **TSK FE diversi** è parallelizzabile senza contesa, perché ogni TSK scrive nella sua cartella isolata `code_quality/reports/<TSK-id>-visual-iter-<N>/` (no shared state, R.S2 soddisfatta per costruzione).
  - **Same-TSK → serial**: gli iter dello **stesso TSK** (iter N+1 dopo un verdict `conditional`) sono serializzati, perché il report `<TSK-id>-visual-iter-<N>` è single-writer per TSK (analogo a `review` e a `visual_status`, ADR-012 §F).
  - **Effetto sul DAG**: il visual oracle **non aumenta il numero di livelli DAG**; estende la **durata effettiva del livello L2** per i TSK FE quando `fe_correctness.enabled: true`. Lo scheduler continua a vedere L1 (plan/design) → L2 (develop, ora comprensivo di visual-oracle come sub-step) → L3 (review) → L4 (publish/sync), invariati. La stessa logica di parallelizzazione di develop si applica (cross-TSK parallel, same-TSK serial); promuovere il visual oracle a livello DAG separato (es. L2.5) è stato scartato in ADR-013 §Punto 3 perché non parallelizza diversamente da develop.
- **Dominio `ux-ui-review` (v2.18, EP-008)**: la review UX/UI (`ux-ui-review-protocol`, US-028, o agente `ux-ui-reviewer` se `ux_ui.agents.reviewer: true`) sui TSK FE è candidata alla wave quando `scheduler.domains.ux-ui-review: true` (default `false`, opt-in R.P3; richiede `factory.config.yaml.ux_ui.enabled: true`, altrimenti no-op). **Inquadramento: sub-step di L2 (develop), NON un nuovo livello DAG** — identico a `visual-oracle` (ADR-019 §Punto 3). La review UX/UI gira logicamente dopo la Fase 4-bis Visual Verification di `dev-protocol` (visual oracle) e prima della Fase 5 (handoff a `status: done`), cioè dentro L2 e prima di L3 (review). Politica di parallelizzazione:
  - **Cross-TSK → parallel**: la review UX/UI su **TSK FE diversi** è parallelizzabile senza contesa, perché ogni TSK scrive nella sua cartella isolata `code_quality/reports/<TSK-id>-uxui-review-iter-<N>/` (no shared state, R.S2 soddisfatta per costruzione).
  - **Same-TSK → serial**: gli iter dello **stesso TSK** (iter N+1 dopo un verdict `conditional`, loop bounded da `ux_ui.max_iterations`) sono serializzati, perché il report `<TSK-id>-uxui-review-iter-<N>` e il campo `ux_ui_status` sono single-writer per TSK (analogo a `review`, `visual_status` e `a11y_status`).
  - **Composizione con `visual-oracle` (EP-005, se `fe_correctness.enabled`)**: se entrambi i domini sono attivi, la `ux-ui-review` **attende `visual_status` non-pending** nel TSK (il visual oracle deve aver concluso: `pass`/`conditional`/`reject`). Se `visual_status: reject` → ux-ui-review SKIPPED (no point a revisionare un rendering rotto; TSK resta in-progress, gate umano sul visual oracle). Se `visual_status: pass` → parte normalmente. Se `visual_status: conditional` → la ux-ui-review può girare in parallel al loop visual oracle (ottimizzazione ADR-019 §Rationale 7: prepara findings sul rendering corrente per evitare round-trip). Ordering: `develop → visual-oracle → ux-ui-review → code-review` (ADR-019).
    Il dispatch parallelo nel caso `conditional` è controllato dal flag
    `ux_ui.parallel_during_conditional` in `factory.config.yaml`:
    - A flag `false` (default): comportamento serial — ux-ui-review attende `visual_status: pass`
      (no-op: comportamento identico a v2.21).
    - A flag `true` (opt-in): dispatch ux-ui-review in parallelo al loop visual oracle
      quando `visual_status: conditional`. Input: screenshot corrente (quello che ha
      generato il `conditional`). Regola invariante indipendente dal flag:
      `visual_status: reject` → ux-ui-review SKIPPED.
    Regola di non-contesa: `visual_status` e `ux_ui_status` sono campi frontmatter distinti,
    single-writer distinti (visual-oracle-protocol e ux-ui-review-protocol rispettivamente)
    → nessuna race condition indipendentemente dal flag.
  - **Procedura di dispatch condizionale (`visual_status: conditional`)** (EP-023, ADR-019 §Rationale 7):
    quando `TSK.visual_status == 'conditional'` AND `ux_ui.parallel_during_conditional == true`
    AND `ux_ui.enabled == true`, lo scheduler esegue la sequenza seguente:
    1. Il visual oracle ha emesso `visual_status: conditional` per un TSK FE (rendering
       parzialmente corretto: il loop `fe-dev → visual-oracle` è in corso).
    2. Lo scheduler, invece di attendere `visual_status: pass`, dispatcha il dominio
       `ux-ui-review` in parallelo al loop visual oracle. Input per la ux-ui-review:
       lo screenshot corrente (quello che ha generato il `conditional` — non uno
       screenshot aggiornato non ancora disponibile).
    3. Il fe-dev riceve due set di finding nella stessa wave:
       - Finding visual oracle: fix rendering (es. width overflow, palette non conforme).
       - Finding ux-ui-review: finding UX (es. gerarchia visiva, call-to-action, carico cognitivo).
    4. Il fe-dev applica entrambi i set nell'iterazione successiva. Il visual oracle ri-verifica.
    5. Se `visual_status: pass` a iterazione successiva: la ux-ui-review non viene
       ri-eseguita (ha già emesso il suo finding — salvo che `ux_ui_status: conditional`,
       che attiva il proprio loop bounded da `ux_ui.max_iterations`).
    Comportamento a flag false: no-op — ux-ui-review rimane serial (aspetta `visual_status: pass`).
    Composizione con a11y Modalità 2: se `a11y.enabled: true` e Modalità 2 (qa-dev
    post-Develop) è attiva, la triplice parallelizzazione (visual-loop + ux-ui + a11y) è
    sicura senza contesa: `visual_status`, `ux_ui_status`, `a11y_status` sono campi
    frontmatter distinti, ognuno con il proprio single-writer (visual-oracle-protocol,
    ux-ui-review-protocol, a11y-protocol). Nessuna race condition.
  - **Composizione con dominio `a11y` (EP-007, ADR-016)**: in Modalità 1 (a11y inline in visual-oracle Fase 3-bis) la `ux-ui-review` riceve sia `visual_status` sia `a11y_status` prima di partire (i finding a11y diventano `open_questions` nel report ux-ui, no duplicazione se `ux_ui.delegate_a11y_to_ep007: true`). In Modalità 2 (a11y batch post-Develop) `a11y` e `ux-ui-review` girano **in parallel** sullo stesso TSK FE done senza contesa (scrivono campi frontmatter diversi: `a11y_status` vs `ux_ui_status`).
  - **Effetto sul DAG**: la `ux-ui-review` **non aumenta il numero di livelli DAG**; estende la **durata effettiva del livello L2** per i TSK FE quando `ux_ui.enabled: true`. La stessa logica di parallelizzazione di develop si applica (cross-TSK parallel, same-TSK serial); promuoverla a livello DAG separato è stato scartato in ADR-019 §Rationale 3 (over-engineering, opera sullo stesso artefatto del develop con ordering naturale).
  - **Sotto-capability Design (`ux-ui-design`, US-029)**: **off-DAG** (no dominio scheduler dedicato, ADR-020 §C). Invocata umano-driven via `/ux-ui-design <brief>`; il deliverable diventa input «pre-TSK» di un TSK FE futuro tramite il campo frontmatter `ui_design_spec: <path>` (single-writer TPM). Non ha ordering con `visual-oracle`/`ux-ui-review`/`code-review` (è pre-TSK, non post-Develop).
- **Dominio `functional-oracle` (v2.20, EP-018 ADR-066)**: l'esecuzione del functional
  oracle (`functional-oracle-protocol`, eseguita da `qa-dev` Modalità functional-oracle,
  fallback `fe-dev` ADR-067 §A) sui TSK FE è candidata alla wave quando
  `scheduler.domains.functional-oracle: true` (default `false`, opt-in R.P3; attivato
  automaticamente quando `factory.config.yaml.fe_correctness.functional_oracle.enabled: true`,
  altrimenti no-op). **Inquadramento: sub-step di L2 (develop), NON un nuovo livello
  DAG** — identico a `visual-oracle` e `ux-ui-review` (ADR-066 §Conseguenze). Il
  functional oracle gira logicamente dopo il visual oracle (e dopo `ux-ui-review` se
  abilitato) e prima della Fase 5 (handoff a `status: done`), cioè dentro L2 e prima
  di L3 (review). Ordering nel cascade: `develop → visual-oracle → functional-oracle →
  review`. Politica di parallelizzazione:
  - **Cross-app → parallel**: il functional oracle su **applicazioni diverse** (diversi
    `code_path`/`app_target`) è parallelizzabile senza contesa — ogni esecuzione
    scrive nella sua cartella isolata `code_quality/reports/<TSK-id>-functional-iter-<N>/`
    (no shared state, R.S2 soddisfatta per costruzione).
  - **Same-app → serial**: le esecuzioni sulla **stessa applicazione** (stesso
    `app_target` o `code_path` sovrapposto) sono serializzate per evitare race
    condition su serve port e stato DOM (Playwright porta unica per app, stato
    condiviso tra scenari). Distinto da `visual-oracle` (policy `same-TSK serial,
    cross-TSK parallel`) e `ux-ui-review` (pure `same-TSK serial, cross-TSK
    parallel`): il functional oracle ha granularità **same-app** perché l'app serve è
    risorsa condivisa tra TSK diversi della stessa applicazione, non solo tra iter
    dello stesso TSK.
  - **Composizione con `visual-oracle` (EP-005, se `fe_correctness.enabled`)**: se
    entrambi i domini sono attivi, il `functional-oracle` **attende `visual_status`
    non-pending** nel TSK (il visual oracle deve aver concluso: `pass`/`conditional`/
    `reject`). Se `visual_status: reject` → functional oracle SKIPPED (no senso
    testare funzionalmente un rendering rotto; TSK resta in-progress, gate umano sul
    visual oracle). Se `visual_status: pass` → parte normalmente. Se `visual_status:
    conditional` → il functional oracle può girare (rendering parzialmente accettabile;
    i risultati sono annotati nel report come condizionali).
  - **Composizione con `ux-ui-review` (EP-008, se `ux_ui.enabled`)**: se abilitata,
    la `ux-ui-review` precede il functional oracle nello stesso cascade (ordering:
    `develop → visual-oracle → ux-ui-review → functional-oracle → review`). Il
    functional oracle non aspetta `ux_ui_status` come precondizione bloccante (la
    review UX/UI è informativa, no ABORT — ADR-019 Punto 2); parte dopo che la
    ux-ui-review ha terminato la propria esecuzione per ordering naturale del cascade.
  - **Activation link**: `fe_correctness.functional_oracle.enabled: true →
    scheduler.domains.functional-oracle: true` (auto-attivazione al cambio del flag
    master; non richiede edit manuale della sezione `domains`).
  - **Effetto sul DAG**: il `functional-oracle` **non aumenta il numero di livelli
    DAG**; estende la **durata effettiva del livello L2** per i TSK FE quando
    `functional_oracle.enabled: true`. La stessa logica di parallelizzazione di
    develop si applica (cross-app parallel, same-app serial); promuoverlo a livello
    DAG separato (es. L2.6) è scartato per gli stessi motivi di `visual-oracle`
    (ADR-013 §Punto 3) e `ux-ui-review` (ADR-019 §Rationale 3): nessun guadagno di
    parallelismo aggiuntivo rispetto al trattarlo come sub-step.
- **Dominio `analytics` (v2.18, EP-009 + EP-010)**: le invocazioni di `analytics-reporter` (misurazione, US-038) e `estimation-analyst` (stima, US-043) su uno scope (project/sprint/period/TSK/estimate) sono candidate alla wave quando `scheduler.domains.analytics: true` (default `false`, opt-in R.P3). **Inquadramento: operazione canonica autonoma, NON un sub-step di develop** (a differenza di `visual-oracle`/`ux-ui-review`/`code-review`): l'analytics è invocata su richiesta o periodicamente (es. cron settimanale `/analytics --sprint=current`) e gira su qualsiasi topology, anche `plan-only` che non ha dev-agent (ADR-023 §rationale 12, parallelo a `a11y`). Politica di parallelizzazione (ADR-023 §H, US-039):
  - **Cross-scope → parallel**: invocazioni su scope diversi (diversi `project_id`/`estimate_id` o diverse `audience`) sono parallelizzabili senza contesa — più report su progetti diversi possono girare concorrenti (es. `analytics-reporter` su P-7 e P-8 insieme).
  - **Same-scope → serial**: invocazioni sullo stesso `project_id` (o stesso `estimate_id`) sono serializzate per evitare race su `analytics/events/` e `analytics/reports/<scope>/` (single-writer per scope). Due `analyze_timeline` concorrenti sullo stesso project_id non sono ammessi.
  - **Composizione misurazione ↔ stima (same-scope serial, EP-010)**: stima e misurazione condividono lo stesso dominio `analytics`; su uno stesso `project_id` sono serializzate — la stima/retrospettiva di accuratezza (EP-010, ADR-027) ha bisogno della misurazione corrente completata (eventi tutti registrati, `analyze_timeline` aggiornato) come input, quindi la stima aspetta che la misurazione corrente finisca (race su event store + race su `analyze_timeline`). Cross-scope (es. misurazione P-7 + stima P-8) resta parallelo.
  - **Retrospettiva accuracy (`--review-accuracy=<estimate_id>`)**: operazione composita che invoca sia EP-009 (misurazione effettiva) sia EP-010 (rilettura della stima storica) per produrre `analytics/reports/accuracy/<estimate_id>.{json,md}` (ADR-027 §C). Serializzata sul `project_id` collegato all'`estimate_id`: nessun'altra invocazione `analytics` sullo stesso `project_id` può girare in parallelo (single-writer su `accuracy/<estimate_id>` + lettura coerente di eventi + stima). Cross-scope con altre retrospettive su `estimate_id` diversi resta parallelo.
  - **Nessun nuovo dominio (EP-010)**: EP-010 NON introduce un nuovo dominio scheduler — riusa il dominio `analytics` di EP-009 (US-039, ADR-023 §H). Coerente con il principio «ogni capability può popolare più operazioni canoniche dentro lo stesso dominio»: stima e misurazione sono operazioni distinte sotto lo stesso gate `scheduler.domains.analytics`. Pattern di composizione tra capability.
  - **Effetto sul DAG**: `analytics` non è un livello develop; è dispatchata come operazione canonica (analoga a `ingest`/`lint`/`query`/`publish`/`sync` in PATTERN §18). Cross-scope parallel, same-scope serial (inclusa la composizione misurazione↔stima e `--review-accuracy`); nessun nuovo livello DAG introdotto.

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

**Wave plan template**:

```
WAVE PLAN (sprint NN, sched v2.11)
====================================
Level 0 — parallel (3 of max 4):
  ▸ Group A:
    • TSK-007 [be, S, P0] code_path=src/auth/**
    • TSK-012 [db, M, P1] code_path=db/migrations/0042_*.sql
    • TSK-019 [fe, S, P0] code_path=web/src/login/**
Level 1 — serial (2 nodes, depends_on Level 0):
  ▸ TSK-008 [be, S, P0] depends_on=[TSK-007]
  ▸ TSK-013 [qa, M, P1] depends_on=[TSK-007,TSK-012,TSK-019]

VCS hand-off accodato seriale dopo ogni wave.
Procedo? [y/N]
```

## Fase 5 — Dispatch

Per ogni `level i`:
  Per ogni `group g in level[i]`:
    1. **Context compression resolve (v2.14 Fase 2, opzionale)**: se `factory.config.yaml.compression.context.enabled: true` E esiste `.graphify-state/code_paths/<target>/GRAPH_REPORT.md` per il TSK target, applica **confidence-gated dispatch** (R.G2, §20.10.1):
       - Determina il ruolo dell'agent destinatario: `executor` (dev-agent `be/fe/db/qa`), `explorer` (lead-architect, wiki-query), o `reviewer` (code-reviewer).
       - Filtra il `GRAPH_REPORT.md` per i tag confidence consentiti dalla config `compression.context.confidence_gating.<role>` (default: executor → `EXTRACTED` only; explorer → `EXTRACTED + INFERRED`; reviewer → tutto).
       - Pass il `GRAPH_REPORT.md` filtrato al posto dei file sorgente raw come context dell'`Agent(...)` tool call.
       - Se `.graphify-state/code_paths/<target>/` assente o stale > `drift_alert_days` → fallback automatico a scansione filesystem standard + log warning `compression-context-fallback target=<name> reason=<stale|missing>`.
    2. **Compression intercept (v2.14 Fase 1, opzionale)**: se `factory.config.yaml.compression.output.enabled: true`, prima del multi-tool-call invoca `caveman-protocol §Fase 2-3` per ogni payload `Agent(...)` con `channel: orchestrator_to_subagent`, `chain_depth: <depth corrente nella wave>`. Il payload compresso sostituisce quello originale nella tool call. Se `enabled: false` → no-op (skip Fase 2-3 di caveman-protocol).
    3. **Multi-tool-call** nello stesso turno: N invocazioni `Agent` parallele,
       una per ogni TSK in `g` (adapter Claude Code: subagent_type = `<layer>-dev`).
    4. Attendi che TUTTI i sub-agent del group terminino (foreground).
    5. Per ognuno:
       - Output OK → `dev-handoff` ha già aggiornato `status: done` + appendato `wiki/log.md`.
       - Output FAIL → append `wiki/log.md` entry `develop-failed TSK-ZZZ rationale=...`. Il TSK resta `status: todo`. **Non rollba** gli altri (R.S7).
    6. **Compression drift check (v2.14 Fase 1)**: se compression output attivo, invoca `caveman-protocol §Fase 4` per ogni response del sub-agent. Marker di ambiguità → fallback automatico a normal mode + log `compression-drift` (R.C5). Se `drift_count >= 3` nella sessione → switch globale a normal mode + chat warning.
    7. **VCS hand-off serializzato** (R.S8): per ogni TSK terminato con successo, invoca `vcs-handoff` **uno alla volta** in coda al group.
    8. **Token Ledger wave_close hook (gated, v2.21 EP-022)**: al termine del group (dopo il VCS hand-off), se `analytics.token_ledger.auto_call_on_wave_close: true`:
       ```
       python3 "$CLAUDE_PROJECT_DIR/tools/analytics/show-session-tokens.py" --full
       ```
       Display `--full`: box completo con breakdown per modello (non one-liner compatto).
       **Fail-open**: errori dello script (transcript non trovato, timeout, parsing fallito) → skip silente con nota `WARNING token-ledger wave_close failed: <reason>` appendata al log. Mai bloccare il workflow per mancanza di metriche.
       A `auto_call_on_wave_close: false` (default): questo step è no-op assoluto — flusso wave_close identico a v2.20.
       Vedi `.cursor/skills/token-ledger/SKILL.md` §Integrazione con parallel-scheduling per dettagli architetturali.

Quando `level i` è completo (tutti i group dispatched + VCS chiusi), passa a `level i+1`.

## Fase 6 — Log

Append a `wiki/log.md` (template `wave`):

```
## YYYY-MM-DD HH:MM — wave sprint-NN
**Levels:** 2 (0=3 parallel, 1=2 serial)
**Dispatched:** 5 TSK (4 ok, 1 failed)
**Failed:** TSK-013 (reason: vcs-handoff abortito da utente)
**Wall-clock saved:** ~estimated 60% vs serial baseline
**Compression (v2.14, se attivo):** profile=conservative, tokens_in=15.2k→7.4k, tokens_out=8.3k→3.9k, drift=0
```

Se `compression.output.enabled: true`, il `wave_report.md` companion in
`memory/episodic/` include una sezione `## Compression stats` con la matrice
`canale × (tokens_in_raw, tokens_in_compressed, tokens_out_raw, tokens_out_compressed,
ratio, drift_count)`. Vedi `caveman-protocol §Fase 5`.

E un record episodico in `memory/episodic/YYYY-MM-DD-HH-MM-wave-NN.md` con la
struttura completa del DAG (per audit + retroactive analysis).

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

## Esempio di esecuzione (dry-run su sprint con 5 TSK)

Input candidates:
```
TSK-001 [be, S, P0] depends_on=[]            code_path=[src/db/**]
TSK-002 [fe, S, P0] depends_on=[]            code_path=[web/src/login/**]
TSK-003 [be, M, P0] depends_on=[TSK-001]     code_path=[src/auth/**]
TSK-004 [be, S, P1] depends_on=[TSK-001]     code_path=[src/auth/handlers/**]
TSK-005 [qa, M, P0] depends_on=[TSK-003,TSK-004,TSK-002] code_path=[tests/e2e/**]
```

E_dep:
```
TSK-001 → TSK-003
TSK-001 → TSK-004
TSK-003 → TSK-005
TSK-004 → TSK-005
TSK-002 → TSK-005
```

E_conf:
```
{TSK-003, TSK-004} (overlap src/auth/** ∩ src/auth/handlers/**)
```

Levels:
- Level 0: TSK-001, TSK-002 → no conflict → 1 group di 2 → parallel
- Level 1: TSK-003, TSK-004 → conflict → 2 group di 1 ciascuno → serial fra loro
- Level 2: TSK-005 → 1 group di 1 → solo

Plan: 4 wave (Level 0 parallel; Level 1.a; Level 1.b; Level 2).
Wall-clock saved: 1 wave eliminato dal parallelismo del Level 0.

## Analytics Instrumentation (opt-in v2.19+)

**Gate**: `factory.config.yaml.analytics.dogfooding.enabled: true` AND
`factory.config.yaml.analytics.granularity` in `{wave, tool}` (non `tsk`).
SE `dogfooding.enabled: false` (default factory derivate): EARLY RETURN — 0 side effect.
SE `granularity: tsk`: wave events skipped (solo TSK events da dev-protocol).

**Nessun nuovo dominio scheduler**: i punti di iniezione wave sono inline nelle Fasi 4 e 5
dello scheduler. NON è aggiunto un dominio `analytics:` per EP-013 (contrariamente a EP-009
che usa il dominio `analytics` come operazione autonoma). Pattern diverso documentato in EP-009.
Pattern: EP-013 è cabling trasversale inline, non workflow autonomo schedulato.

**Single-writer**: stesso tool `record-event.sh` di dev-protocol (ADR-039 §B).
**PII invariante**: payload solo allowlist-compliant (ADR-040 §A). No contenuto, no prompt.

### Punto 1 — `state: wave_started` (Fase 4: inizio wave dispatch, NUOVO v2.19 ADR-042)

**Trigger**: `parallel-scheduling` inizia il dispatch di una wave (Fase 4 — invia i candidati ai sub-agent).
**Granularità**: attivo per `analytics.granularity` in `{wave, tool}`.
**Payload** (campi allowlist-compliant ADR-040 §A):
```json
{
  "task_id": "<wave_id>",
  "project_id": "<factory-slug>",
  "actor_type": "agent",
  "actor_id": "orchestrator",
  "task_type": "scheduler",
  "state": "wave_started",
  "ts": "<ISO-8601 UTC con Z>",
  "wave_id": "<UUID o slug wave, es. wave-2026-06-08T14:30:00Z-a1b2>",
  "wave_size": N,
  "candidates": ["<TSK-id-1>", "<TSK-id-2>", ...],
  "tokens": {"input": 0, "output": 0},
  "model": "<current-model-id>",
  "tool_calls": []
}
```

### Punto 2 — `state: wave_completed` (Fase 5: join wave, NUOVO v2.19 ADR-042)

**Trigger**: tutti i sub-agent della wave hanno completato (Fase 5 join).
**Granularità**: attivo per `analytics.granularity` in `{wave, tool}`.
**Payload**: payload di `wave_started` + estensioni:
```json
{
  "wave_elapsed_ms": "<wall-clock ms da wave_started>",
  "success_count": N,
  "failure_count": M
}
```

### Punto 3 — `state: sub_agent_dispatched` (opt-in granularity: tool)

**Trigger**: ogni singolo sub-agent viene dispatched (Fase 4, per ogni candidato nella wave).
**Granularità**: attivo SOLO per `analytics.granularity == tool`. Se `wave` → skip.
**Payload**:
```json
{
  "task_id": "<TSK-id specifico>",
  "wave_id": "<wave_id>",
  "actor_id": "<be-dev|fe-dev|...>",
  "actor_type": "agent",
  "state": "sub_agent_dispatched",
  "ts": "<ISO-8601 UTC>",
  "dispatch_ts": "<ISO-8601 UTC>",
  "completion_ts": "<ISO-8601 UTC, valorizzato a job completion>"
}
```

### Volume stimato

Stima sprint v2.19 (EP-012 + EP-013, ~30 TSK, ~4 wave parallele):

| Granularità | Eventi stimati |
|---|---|
| `tsk` | ~60 (solo TSK events da dev-protocol) |
| `wave` | ~68 (60 TSK + 4 wave×2 stati) |
| `tool` | ~92+ (68 + N sub-agent dispatch) |

[^src: design_&_architecture/decisions/ADR-038.md §D]

### Cross-link temporale (EP-011)

Il `ts` degli eventi wave è UTC ISO-8601 con suffisso `Z`, coerente con il tool
`utc-now.sh` di EP-011 US-045 (ADR-030). Allineamento totale tra EP-011 e EP-013.

### Riferimenti

ADR-038 §C §D (3 punti di iniezione + volume) · ADR-039 §A §B (single-writer,
dedup hash compound) · ADR-040 §A §B (allowlist PII) · ADR-042 §A §B (nuovi enum
`wave_started`/`wave_completed`/`sub_agent_dispatched`). Cabling inline nelle Fasi 4-5,
no nuovo dominio scheduler. Pattern additivo ADR-031 (sezione append-only).

---

## Temporal Budget Hook (opt-in v2.19, EP-014)

> **Gated**: `factory.config.yaml.temporal.budget.enabled: true`. A flag spento questa sezione è no-op: il wave plan NON contiene i campi budget, comportamento identico v2.18 (R.P3).

### Wave plan §18.6 — 3 nuovi campi obbligatori (gated)

Quando `temporal.budget.enabled: true` + `temporal.budget.wave.enabled: true` (default: true se master switch on), la Fase 4 (Dispatch) del parallel-scheduling estende lo schema YAML del wave plan con:

```yaml
wave:
  id: <wave-uuid>
  size: <N candidati>
  candidates: [<task-id>, ...]
  estimate: <S|M|L>                    # legacy v2.11, mantenuto invariato
  # === NUOVO v2.19 — gated temporal.budget.enabled: true ===
  token_budget: <int>                  # tetto wave: somma P85 per-layer dei candidati (ADR-044 §C)
  elapsed: <int>                       # token consumati: 0 a wave_started, incrementale a ogni state:finished del TSK
  estimated_remaining:
    P50: <int>
    P85: <int>
    P95: <int>
  bootstrap_mode: <bool>               # true se N eventi < temporal.budget.bootstrap.min_n (ADR-045 §C)
  cost_per_1k_tokens: <float|null>     # cosmetica per gate umano (ADR-046 §G), null = non mostrato
  # Opzionali se tsk.enabled o sprint.enabled (ADR-044 §D)
  tsk_budgets:                         # presente solo se temporal.budget.tsk.enabled: true
    - task_id: <id>
      token_budget: <int>
      elapsed: <int>
  sprint_budget:                       # presente solo se temporal.budget.sprint.enabled: true
    sprint_id: <slug>
    token_budget: <int>
    elapsed: <int>
```

### Calcolo `token_budget` (wave-level)

1. **Fonte primaria** (`token_budget_source: p85`): `sum(P85_layer for task in candidates)` da output `estimate-project` di EP-010 US-041 o da `analytics/reports/baseline/` di EP-013 US-053.
2. **Fallback bootstrap** (N eventi < `bootstrap.min_n: 10`): usa `temporal.budget.bootstrap.wave_default_tokens` (default: 100000). Marker `bootstrap_mode: true` nel wave plan.
3. **Fixed** (`token_budget_source: fixed`): usa `temporal.budget.wave.token_budget_fixed` direttamente.

### Invariante: `estimated_remaining` è sempre distribuzione

Il campo `estimated_remaining` espone **sempre** P50/P85/P95, mai numero puntuale. Coerente con EP-010 invariante "mai numero puntuale". Il governor (skill `temporal-budget-governor`, TSK-112) legge la distribuzione, non un valore singolo.

### Invariante single-writer (ADR-044 §G)

Il `parallel-scheduling` è l'**unico writer** dei campi `token_budget` / `elapsed` / `estimated_remaining` del wave plan. Il governor (skill) è **read-only** sul wave plan.

### Snapshot immutabile post-gate

Una volta esposto al gate umano (`parallel_gate_threshold` triggerato), il wave plan è **immutabile** per quella sessione: `token_budget` e `estimated_remaining` non vengono ricalcolati. Solo `elapsed` cresce a ogni `state: finished` di un TSK nella wave.

### Template canonico messaggio gate umano (PATTERN §18)

Quando `parallel_gate_threshold` triggera con `temporal.budget.enabled: true`, il messaggio "Procedo?" usa questo template canonico:

```
Wave proposta: <N> candidati, size <S|M|L>
Token budget wave: <token_budget>
Elapsed (corrente): <elapsed>
Estimated remaining: P50=<X>, P85=<Y>, P95=<Z>
[Cost stimato: ~$<dollari>]          (mostrato solo se cost_per_1k_tokens != null)
[BOOTSTRAP MODE: stime da PERT/fallback, calibrazione in corso]  (mostrato solo se bootstrap_mode: true)
Conferma? [y/N]
```

Il maintainer decide su numeri reali, non su S/M/L statici.

### Cross-link EP-011 (elapsed_ms)

Il campo `elapsed_ms` del Temporal Handoff Protocol (EP-011 US-046) contribuisce al calcolo di `elapsed` token quando il TSK ha sia tempo che token (doppia alimentazione). La skill `temporal-budget-governor` (TSK-112) decide quale metric è primaria in funzione di `temporal.budget.wave.token_budget_source`.

### Backward compat

`temporal.budget.enabled: false` (default factory derivate): nessun campo budget nel wave plan, comportamento identico v2.18. Lint `/lint` 0 ERROR su factory senza opt-in.

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
