# PATTERN — Agentic Factory `llm-wiki++`
<!-- version: see factory.config.yaml#pattern_version (authoritative source) -->

> Contratto universale agent-agnostic. Qualsiasi runtime (Claude Code, OpenAI Assistants,
> Cursor, Aider, Gemini, ChatGPT, …) che rispetti questo file può operare sul repo. Gli
> adapter di runtime vivono in cartelle dedicate (`.claude/`, `.cursor/`, `.aider/`, …) e
> implementano i ruoli §2. **Multi-adapter v2.13**: scaffolding parallelo di adapter
> multipli supportato; ogni adapter ha un manifest formale (§12.x).

## §0 — Identità & versione
<!-- profiles: minimal, standard, full -->
Pattern version: **2.45**. (authoritative source: `factory.config.yaml#pattern_version`)
Origine: llm-wiki (Karpathy) + estensione PM/Arch + memory tree cross-conversazione + adapter `thin agents, fat skills` + execution layer L5. Ogni capability aggiunta sopra questa baseline e' normata nella propria sezione del modulo pertinente (tabella §Moduli in fondo a questo file) — §13 topology, §14 stack modes, §15 VCS, §16 sync adapters multi-sorgente, §17 publisher adapters, §18 parallel scheduling, §19 code quality review, §20 compression layer, §21 versioning, §22 release governance, §23 complexity budget & deprecations, §24 design intelligence, §25 semantic drift, §26 runtime contextual suggestions, §27 prototype generation, §28 tavola rotonda, §29 scalability patterns, §30 voice channel, §31 hybrid wiki search, §32 content share, §33 code intelligence, §34 semantic purpose, §35 wiki keeper 2.0, §36 fleet health, §37 session observability — piu' gli oracoli FE (§3, `fe_correctness`), a11y/UX-UI e analytics (§3, flag omonimi). **La cronologia per versione vive in `CHANGELOG.md`, fonte unica: non e' duplicata qui.** (GAP-DOC-001)
Scope: knowledge-base eseguibile **e** (opzionale) produzione codice tramite dev-agent o consumo umano dei task; integrazione esplicita con git per layout monorepo/submodule/sibling/external; ingestione L1 da fonti eterogenee tramite sub-agent Sync dedicati (incluso reverse-engineering di repo esistenti via `repo-sync`); pubblicazione opzionale di L3/L4 su tool esterni di project tracking tramite sub-agent Publisher (provider-agnostic); orchestrazione parallela di operazioni indipendenti sui livelli L1→L5 con safety-by-default (single-committer e conflict detection su `code_path`); valutazione qualitativa del codice prodotto a valle di Develop (idiomaticità, design, robustezza) tramite Code Reviewer opzionale con loop evaluator-optimizer bounded.
Progetto host: **Soli Multi-Agents Factory** (`owner: soli92`, `language: it`).

## §1 — Modello a layer
<!-- profiles: minimal, standard, full -->
- **L1 `raw/`** — input multi-sorgente. Artefatti tipici: PDF + estrazioni `.txt` + `images/` (da `sync-docs`); KB JSON strutturate (`.kb.json`) da `figma-sync`; futuri sub-agent (Notion, Confluence) seguono lo stesso contratto. **Immutabile** (solo il ruolo *Sync*, nei suoi N sub-agent per sorgente, scrive in `raw/` — §16).
- **L2 `wiki/`** — wiki llm-style con `log.md` append-only. Unico autore: ruolo *Analyst* (`wiki-keeper`). Layout karpathy-style: `sources/concepts/entities/syntheses/runbooks/incidents/`.
- **L3 `management/`** — `kanban/EP-*/`, `roadmap.md`, `questions.md`. Autore: ruolo *PM*.
- **L4 `design_&_architecture/` + `management/kanban/**/TSK-*.md`** — autore: ruolo *Arch* (architettura) + *TPM* (task atomici).
- **L5 `<code_path>/`** — codice sorgente. `code_path` è configurabile in `factory.config.yaml` (default `./src/`) e **può puntare fuori dal repo** (path assoluto verso altro working tree). Autore: ruoli *Dev* (`be-dev`, `fe-dev`, `db-dev`, `qa-dev`) o sviluppatori umani — in base al routing §14. La **relazione VCS** fra L5 e factory repo è dichiarata in `factory.config.yaml.vcs.mode` (§15): `monorepo` (L5 dentro al factory repo), `submodule` (L5 come git submodule), `sibling` (L5 come clone separato), `external` (factory non conosce la topologia VCS), `none` (no L5).
- **`memory/`** — persistenza cross-conversazione (non un layer, ma side-channel).

Cascata: ogni layer è derivato dal precedente. L'aggiornamento di Lk rende Lk+1..L5 *stale*. Se `code_path` è esterno, la cascata si interrompe al boundary del repo: i dev-agent committano nel repo esterno, mentre `wiki/log.md` annota solo il fatto che è avvenuto un `develop` (puntatore al commit hash quando disponibile).

## §2 — Ruoli (responsabilità, non file)
<!-- profiles: minimal, standard, full -->
Ogni runtime mappa questi ruoli ai propri costrutti (agenti, assistant, modes, …).

**Principio**: `wiki/` è **read-universal** (ogni agente la legge), **write-restricted** (solo `wiki-keeper` scrive contenuto; eccezioni puntuali sotto). Tutti gli agenti L3+ possono e devono leggere `wiki/` per contesto, anche se la loro citazione formale resta cascade (Arch cita storie, non concept; ma può aprire il concept per capire cosa significa).

| Ruolo | Legge | Scrive | Trigger |
|---|---|---|---|
| **Orchestrator** | tutto (read-only) | `memory/episodic/**`, `wiki/log.md`, **eccezione**: edit `status:` frontmatter di `wiki/**/*.md` (operazione `/promote`) | richiesta dashboard di stato; comando `/promote` |
| **Sync** (`sync-docs`, `figma-sync`, …) — un sub-agent per sorgente (§16) | input di propria competenza (PDF locali, URL/`file_key` Figma, …) | `raw/**` nel proprio scope di naming (§4): `sync-docs` → `*.txt` + `images/*-fig-NN.md`; `figma-sync` → `*.kb.json` + `images/*-frame-NN.{png,md}`. Tutti scrivono `raw/.extraction-manifest.json` (append-only per chiave) | nuovo input nella sorgente del sub-agent |
| **Analyst** (`wiki-keeper`) | `raw/**` (`.txt`, `.kb.json`, `images/**/*.md`), `raw/tech_stack.md`, `memory/**`, `wiki/**` (rilegge per cross-link + `wiki/gaps.md` all'inizio di ogni ingest) | `wiki/**` (escluso `query/`, `lint/`) + append `wiki/log.md` | L1 aggiornato OR gap aperti OR `heal-eligible` nel lint report (operazione `Heal`, §3) |
| **PM** (`product-manager`) | `wiki/**`, `memory/**` | `management/kanban/EP-*/**`, `management/{roadmap,questions}.md`, **append-only**: `wiki/gaps.md` + sezione `## Storie collegate` di pagine wiki impattate | L2 aggiornato |
| **Arch** (`lead-architect`) | `management/kanban/**`, `management/questions.md`, `raw/tech_stack.md`, `factory.config.yaml`, `memory/**`, **`wiki/**`** (contesto) | `design_&_architecture/**`, **append-only**: `wiki/gaps.md` + (opzionale, se `stack_mode: auto`) `raw/tech_stack.md.proposal` via skill `tech-scout` | L3 OK + gate questions resolved |
| **TPM** (`tpm`) | `design_&_architecture/**`, `management/kanban/**`, `raw/tech_stack.md`, `factory.config.yaml`, `memory/**`, **`wiki/**`** (contesto) | `management/kanban/**/TSK-*.md` (con campi `layer:` e `consumer:` derivati dal routing §14), `management/kanban/sprint.md`, **append-only**: `wiki/gaps.md` | L4 architettura OK |
| **Query** (`wiki-query`) | `wiki/**` (esclusivo) | `wiki/query/` (opt-out con `--ephemeral`) + append `wiki/log.md` | domanda NL |
| **Lint** (`wiki-lint`) | `wiki/**`, `management/kanban/**`, `design_&_architecture/**`, `factory.config.yaml` | `wiki/lint/` + append `wiki/log.md` | richiesta health check |
| **Dev** (`be-dev`, `fe-dev`, `db-dev`, `qa-dev`) — opzionali (topologia §14) | `management/kanban/**/TSK-*.md` (filtrato per `layer:` proprio + `consumer: agent`), `design_&_architecture/**`, `raw/tech_stack.md`, `factory.config.yaml`, `<code_path>/**`, **`wiki/**`** (contesto) | `<code_path>/**` (path da `factory.config.yaml`, può essere esterno al repo), **append-only**: `wiki/log.md` (entry `develop`), `wiki/gaps.md` (se gap), `management/kanban/**/TSK-*.md` **solo per `status:` e `updated:`** (handoff: `todo → in-progress → done`, MAI editare il corpo) | TSK con `consumer: agent` + `layer:` corrispondente + `status: todo` + dipendenze risolte; OR comando manuale `/dev <TSK-id>` |
| **Publisher** (`github-publisher`, `gitlab-publisher`, …) — opzionali (§17) — un sub-agent per provider | `management/kanban/EP-*/**`, `management/kanban/sprint.md`, `management/{roadmap,questions}.md`, `factory.config.yaml`, `memory/**` | **append-only**: `wiki/log.md` (entry `publish`); **modifica del solo `external_id:` frontmatter** di `EP-*/US-*/TSK-*.md` (mai del corpo); chiamate read+write verso provider esterno (GitHub Issues/Projects, GitLab Issues, Jira, Linear, …) via CLI/API dedicate | comando esplicito `/kanban-publish run` OR (in modalità auto, gate umano) trigger su nuovo TSK con `status: todo` + provider != `none` |
| **Code Reviewer** (`code-reviewer`) — opzionale (v2.12, §19) | TSK con `status: done` + `review_status: pending` (filtrato per `consumer: agent`), `<code_path>/**` (read-only — diff/file toccati), `code_quality/rules/**`, `factory.config.yaml`, `wiki/**` (contesto), `memory/**` | `code_quality/reports/**` (artefatti report machine-readable + digest umano-leggibile), **append-only**: `wiki/log.md` (entry `review TSK-ZZZ iter-N → <verdict>`); **modifica del solo `review_status:`/`review_iter:`/`review_report:` frontmatter** di `TSK-*.md` (mai del corpo); opzionale (gate umano, modalità evolutiva): `code_quality/rules/emergent/**` come bozze candidate | TSK con `consumer: agent` + `status: done` + `review_status: pending` + `code_quality.enabled: true`; OR comando esplicito `/review <TSK-id>` |

## §3 — Operazioni canoniche (verbi)
<!-- profiles: minimal, standard, full -->
- **Ingest** = transizione L1 → L2 eseguita da *Sync* (uno o più sub-agent, §16) + *Analyst*. L'*Analyst* legge artefatti `.txt` (PDF), `.kb.json` (Figma), o futuri shape registrati nel manifest. Per batch ≥ 3 nuovi raw, l'*Analyst* può delegare la fase di analisi ad agenti subordinati paralleli; la scrittura su `wiki/` resta serializzata sull'*Analyst* (single-committer). Append a `wiki/log.md`.
- **Query** = domanda NL → risposta sintetizzata leggendo solo `wiki/`. Append a `wiki/log.md`.
- **Lint** = health check strutturale di L2+L3+L4. Append a `wiki/log.md`.
- **Plan** = transizione L2 → L3 eseguita dal *PM*.
- **Design** + **Execute** = transizione L3 → L4 eseguita da *Arch* poi *TPM*. *Arch* può invocare la skill `tech-scout` se `stack_mode: auto` (produce `raw/tech_stack.md.proposal` — mai overwrite di `raw/`, gate umano).
- **Develop** = transizione L4 → L5 eseguita da un ruolo *Dev*. Consuma un singolo TSK con `consumer: agent` + `layer:` corrispondente. Scrittura su `<code_path>/**`. Append a `wiki/log.md` (marker `develop TSK-ZZZ → <commit-hash o path>`). Mai edit del corpo del TSK; solo `status:` (`todo → in-progress → done`). A Fase 5 il dev-agent invoca la skill `vcs-handoff` (§15) che gestisce il bump del submodule ref, il branch per-TSK, o solo il logging — in base a `vcs.mode`.
- **Promote** = transizione di `status:` di una pagina wiki (`draft → review → approved`).
- **Heal** = ciclo evaluator-optimizer vincolato su ERROR meccanici flaggati dal *Lint* come `heal-eligible`. Opt-in, gated, bounded (max 3 iterazioni). Eseguito dall'*Analyst* in modalità heal (single-committer §7 r.12 preservato). Whitelist chiusa: mai correzione di WARNING né di ERROR fuori categoria. Append a `wiki/log.md` con marker `heal-iter-N`.
- **Propagate** = riconciliazione downstream quando *Analyst* chiude un gap che cita una `Q_NNN`. Skill `propagate-resolution`: trova le US con `blocked_by: [Q_NNN]` ancora in lista, appende a `wiki/log.md` un marker `reconcile-needed: US-XXX → Q_NNN closed`. L'umano (o il PM in pass successivo) sblocca le storie.
- **Tech-scout** = proposta automatica di stack tecnologico (skill omonima, v2.7). Invocabile da *Arch* o on-demand. Output: `raw/tech_stack.md.proposal` con citazioni a fonti web datate. Mai auto-applicato: gate umano per promuovere `.proposal` → `raw/tech_stack.md`.
- **Publish** = transizione L3/L4 → tool esterno di project tracking (v2.10). Eseguita da un sub-agent *Publisher* (§17). Mirror **push-only** di EP/US/TSK/sprint verso GitHub Issues, GitLab Issues, Jira, Linear, … in base a `factory.config.yaml.kanban_publish.provider`. Idempotente: l'`external_id:` frontmatter dell'artefatto pubblicato evita duplicazioni. Mai bidirectional in v2.10 (single source of truth resta `management/kanban/**`, §8). Append a `wiki/log.md` (marker `publish <provider> <count>`). Mai modifica del corpo dei TSK; solo aggiornamento di `external_id:` e `updated:` nel frontmatter.
- **Visual Verification** = variante di **Develop FE** (v2.17, opt-in). Quando `factory.config.yaml.fe_correctness.enabled: true` AND `TSK.layer: fe`, il `dev-protocol` esegue un sub-step **Fase 4-bis — Visual Verification** (skill `visual-oracle-protocol`) che chiude il loop visivo (render headless + screenshot multi-viewport/tema + critica) **prima** di marcare il TSK `status: done`. Esito: `pass` → `visual_status: pass` + TSK done; `conditional` → loop fe-dev bounded (`fe_correctness.max_iterations`, default 3); `reject` → `visual_status: reject` + gate umano. A flag spento la Fase 4-bis è no-op (comportamento identico a v2.16). Vedi ADR-012 §G + ADR-013 Punto 1.
- **Review** = transizione L5 → L5 post-Develop (v2.12, §19). Eseguita dal ruolo *Code Reviewer*. Legge diff/file toccati dal TSK appena chiuso (`status: done` + `review_status: pending`), invoca skill `code-review-protocol` (Stack Detector → 3 passate specializzate → Aggregator → Feedback Router). Produce `code_quality/reports/<TSK-id>-iter-<N>.{json,md}` e un verdict `pass | conditional | reject`. `pass` → TSK `review_status: passed`, ciclo chiuso. `conditional` → task_package machine-readable consegnato al dev-agent corrispondente, re-Develop dello stesso TSK con `review_iter+=1` (bounded da `max_iterations`, default 3; vedi §19.6 R.Q4). `reject` → gate umano (§7 r.16). Append a `wiki/log.md` entry `review TSK-ZZZ iter-N → <verdict>`. Mai modifica del corpo del TSK; solo `review_status:`/`review_iter:`/`review_report:` nel frontmatter.
- **Accessibility Scan** = pre-screening WCAG 2.2 AA stack-agnostico via tool
  `run_a11y_scan` (deterministico, no LLM judgment) consumato da skill
  `accessibility-testing-protocol`. Capability opt-in (v2.18,
  `factory.config.yaml.a11y.enabled`). Tre modalità d'uso: (a) inline a Fase 4-bis
  Visual Verification del dev-protocol (fe-dev); (b) batch post-Develop (qa-dev);
  (c) standalone via `/a11y <target>` (a11y-specialist o fallback). Vedi ADR-014.
  **Invariante operativa non negoziabile (regola di neutralità)**: mai dichiarare
  conformità sulla sola base di automated_findings; il report include sempre
  `manual_checks` con N ≥ 1 (default injection se calcolato vuoto). La capability
  è pre-screening interno: non sostituisce un audit indipendente per EAA / ADA /
  normative locali. Vedi [[wcag-automated-coverage-limit]],
  [[accessibility-testing-capability]], ADR-014/015/016.
- **UX/UI Review** = critica strutturata di usabilità via skill `ux-ui-review-protocol`,
  ancorata alla rubrica anti-soggettività di [[ux-ui-rubric-anti-subjectivity]]
  (10 euristiche Nielsen + 6 dimensioni UI visiva + 5 dimensioni di flusso UX).
  Capability opt-in (v2.18, `factory.config.yaml.ux_ui.enabled`). Tre modalità:
  (a) sub-step di Develop FE (Fase 4-ter di dev-protocol); (b) standalone via
  `/ux-ui-review <target>` con agente `ux-ui-reviewer` opzionale; (c) ad-hoc su
  URL/mockup. **Invariante operativa non negoziabile**: ogni finding cita un
  `rubric_ref` (Nielsen 1-10, dimensioni UI, dimensioni flusso, regola DS). Delega
  accessibilità a `run_a11y_scan` (EP-007) se attiva; altrimenti finding a11y →
  `open_questions`. **Guard anti-fabbricazione** (v2.19, ADR-063): la review fail-loud
  se l'evidenza visiva (screenshot/token) è indisponibile — mai produce finding senza
  evidenza verificabile. Lint Check 4p (v2.18, opt-in `ux_ui.required_on_fe_done`):
  WARNING se TSK FE done senza `ux_ui_status: pass`. Check 4ac (v2.22, opt-in
  `ux_ui.lint_check_4q`): verifica no-auto-eval — WARNING se `generated_by` coincide
  in `ui_design_spec` e `ux_ui_report` dello stesso TSK. Difesa di backup al vincolo
  strutturale (agenti fisicamente distinti). Gate: `ux_ui.lint_check_4q: false`
  (default). Vedi ADR-020 §H. Vedi ADR-017/018/019/020/063.
- **UX/UI Design** = produzione di deliverable di design (wireframe, component spec,
  user flow, copy) via skill `ux-ui-design-protocol`. Agente opzionale `ui-designer`.
  Capability opt-in (v2.18, `factory.config.yaml.ux_ui.enabled` + `agents.designer: true`).
  **Invariante operativa non negoziabile (no auto-eval)**: l'output del designer va
  sempre alla `UX/UI Review` prima di essere considerato pronto. Loop bounded da
  `ux_ui.max_iterations` (default 3). Handoff verso fe-dev tramite frontmatter TSK
  `ui_design_spec:` (TPM-only, analogo a `interaction_test_spec:` di ADR-012).
  Vedi ADR-020.
- **Functional Oracle** = accettazione funzionale app-level end-to-end via skill
  `functional-oracle-protocol` (v2.20, EP-018, opt-in). Esercita il flusso reale
  dell'app: serve deterministico (ADR-064) + interazione Playwright scriptata
  (skill condivisa `interaction-drive-protocol`, ADR-066 §B) + asserzioni
  domain-agnostic (ADR-065 §C: `selector_visible`, `attr_equals`, `canvas_pixel_variance`,
  `storage_key_present`, `console_no_error`, `network_no_5xx`) + verdict deterministico
  `pass | conditional | reject` (ADR-065 §D). Capability opt-in
  (`factory.config.yaml.fe_correctness.functional_oracle.enabled`, default `off`,
  R.P3). Esecutore: `qa-dev` in modalità functional-oracle (ADR-067 §A); fallback
  `fe-dev` se `qa-dev` non in topologia. Critic LLM multimodale **solo advisory** sul
  trace (ADR-067 §B) — **mai** nel path di pass/fail (anti-fabbricazione, ADR-063/064).
  Fail-loud se `enabled: true` e `acceptance-spec` assente/illeggibile (mai pass
  silenzioso). Spec vuota/`scenario: []` → verdict `skip` dichiarato (non pass).
  Ordering pipeline FE: `develop → visual-oracle → ux-ui-review → functional-oracle →
  code-review` (ADR-066 §C). Loop bounded da `functional_oracle.max_iterations`
  (default 3, ADR-067 §C). Storage report riusa `code_quality/reports/` con slug
  `functional` (es. `<TSK-id>-functional-iter-<N>.{json,md}`). Frontmatter TSK
  opzionali: `functional_status:` (single-writer skill, ADR-065 §Storage) +
  `functional_acceptance_spec:` (path spec, scritto da TPM, ADR-065 §B). Scheduler:
  dominio `functional-oracle` (serial same-app, parallel cross-app, §18.3). Niente
  nuova invariante §7. Vedi ADR-065 / ADR-066 / ADR-067.
- **Release Validation Gate** = forcing function procedurale di release del framework
  (v2.19, EP-012, opt-in). Quando `factory.config.yaml.release_governance.battle_test_gate.enabled: true`,
  il maintainer DEVE invocare `/release [version]` prima del git tag. La skill
  `release-validation-gate` verifica ≥3 RUN-REPORT validi in `validation/runs/`,
  schema conforme a ADR-032 §C, sezione CHANGELOG `## Validation evidence (vX.Y.Z)`
  presente (ADR-034 §A). Verdict `pass`/`fail`/`bypass`. Mai auto-tag (R.P1 + R.P3).
  Audit in `validation/release-gates/<version>/`. Audience: maintainer del framework
  (non utenti delle factory derivate, §22.2). Pattern: [[fail-closed]] applicato alla
  governance di release. Vedi ADR-032 / ADR-033 / ADR-034 / ADR-036 / §22.

**Operazioni canoniche analytics di misurazione (v2.18, opt-in EP-009)**. Cinque operazioni autonome, **tutte opt-in** via   `factory.config.yaml.analytics.measurement.enabled: true` (default `false`, R.P3). A flag spento nessuna è invocata e la factory si comporta identica a v2.17. Non sono sub-step di `Develop` (a differenza di *Visual Verification*): sono operazioni canoniche autonome, invocate on-demand o periodicamente (es. cron settimanale `/analytics --sprint=current`). I tool sono script Bash/TS deterministici in `tools/analytics/*` (canonici; `.claude/tools/analytics/*` è solo shim backward-compat — no MCP, coerente con ADR-008/ADR-014); le formule vivono nei tool, l'orchestrazione nella skill `cost-and-time-analytics` (thin-agent-fat-skill). Le invarianti elencate sono **invarianti operative della capability** (parallele alla regola di neutralità di EP-007), **non** invarianti di sistema §7.
- **Task Analytics — Event Recording** = instrumentazione: registra un evento di task (started/finished/blocked) nell'event store `analytics/events/<YYYY-MM>.jsonl` (default JSONL append-only; SQLite opt-in — ADR-021). Tool `record_task_event` (`tools/analytics/record-event.{sh,ts}`, US-033). Schema logico evento (11 campi, verbatim ADR-021 §E): `task_id`, `project_id`, `parent_id`, `actor_type` (`agent|human`), `actor_id`, `task_type`, `state` (`started|finished|blocked`), `ts` (ISO 8601 UTC), `tokens` (`input/output/cache_read/cache_write`), `model` (`<<model_id>>` canonical, ADR-022), `tool_calls[]`. **Single-writer** logico: tutti gli emittenti (orchestrator hook, skill, dev-agent) invocano il tool, mai scrivono il file direttamente. **Invariante**: prezzi/tariffe mai hardcodati nell'evento (il pricing è risolto a valle dal costo, ADR-022). Vedi ADR-021 §E.
- **Task Analytics — Agentic Cost** = calcolo deterministico del costo agentico di uno o più eventi. Tool `compute_agentic_cost` (US-034). **Invariante**: prezzi mai hardcodati — letti **solo** da `analytics/pricing.yaml` versionato (git history come storico autorevole, `valid_from` semi-aperto: un evento del 2026-01 è valutato col prezzo del 2026-01, mai col corrente). Formula concept §2.1 (token × prezzo-per-1M risolto al `ts` dell'evento). Resolution `<<model_id>>` (canonical + `aliases`) nella skill `cost-and-time-analytics` Step 2, fail-loud su modello sconosciuto. Vedi ADR-022.
- **Task Analytics — Human Cost** = calcolo deterministico del costo umano. Tool `compute_human_cost` (US-034). Legge `analytics/rates.yaml` (rate card per ruolo, `valid_from` semi-aperto); `actor_id` → `role_id` via `actors_map` separato dalla rate card (no PII nel dato commerciale, ADR-023 §D). Formula concept §2.2 (`effort_hours` × tariffa-oraria risolta). **Invarianti**: (a) **`rate_basis` esplicito** (`fully-loaded | bill-rate`) dichiarato letteralmente in **ogni** report che usa la rate card (regola di trasparenza, ADR-023 §E); (b) **aggregazione minima N≥5** per dati personali (vedi `<<policy_dati>>` sotto, ADR-023 §C).

  **Policy privacy `<<policy_dati>>`** (invariante operativa, parallela alla regola di neutralità di EP-007; ADR-023 §C-D). Vincola l'output di ogni report che espone costo umano riconducibile a individui:
  1. **Aggregazione minima**: report con `audience: executive` mostra **solo** aggregati per role/team; mai `actor_id` raw.
  2. **Soglia N≥5**: in una cella di aggregazione con meno di 5 `actor_id` distinti (soglia configurabile `analytics.measurement.privacy_aggregation_threshold`, default `5`, floor `1`, mai `0`), il sotto-totale è nascosto e si mostra solo l'aggregato di livello superiore (per ruolo). Default GDPR-safe k-anonymity k=5; override innalzante ammesso, abbassante documentato esplicitamente nel report.
  3. **Storage retention**: gli eventi raw in `analytics/events/<YYYY-MM>.jsonl` sono trattati come dati sensibili — `analytics/events/` è `.gitignore`-d di default per gli `actor_id` umani (ADR-021 §A); l'audit log `wiki/log.md` non logga mai `actor_id` umani raw.
  Il cross-link a normative locali (GDPR EU e altre) è responsabilità della factory derivata: il framework fornisce solo i meccanismi di aggregazione.
- **Task Analytics — Timeline Analysis** = metriche temporali su una finestra di eventi. Tool `analyze_timeline` (US-035, ADR-024 §C). **Invarianti**: (a) **percentili, mai medie** (`p50/p85/p95` con monotonicità `p85 ≥ p50`); (b) **4 concetti distinti** mai confusi — *lead time*, *cycle time*, *effort*, *wait time*. Identifica il bottleneck come `max(wait per stato)`. Warning se `n_samples < 10`. Vedi ADR-024 §C.
- **Task Analytics — Cost/Time Report** = report differenziato per audience (`operativa | project | executive`). Tool `generate_report` (US-037, ADR-024 §A-D). Documento standard «Analytics Report»: `schema_version: v1`, `type` discriminator (`cost_time_report | project_estimate | combined | accuracy_retrospective`), blocchi additivi opzionali `cost`/`time`/`split`/`estimate`/`accuracy`, `notes[]` obbligatorio. **Invariante**: **split umano vs agentico sempre presente** (blocco `split` con `agentic_pct + human_pct == 100`) in ogni report che misura costo/effort. Validation di schema eseguita dalla skill prima dell'emissione (fail-loud su shape non coerente con `type`). Vedi ADR-024 §A-D.

**Operazione canonica analytics di stima (v2.18, opt-in EP-010)**. Operazione autonoma, **opt-in** via `factory.config.yaml.analytics.estimation.enabled: true` (default `false`, R.P3). A flag spento non è invocata e la factory si comporta identica a v2.17. Come le operazioni di misurazione (EP-009 sopra) non è un sub-step di `Develop`: è operazione canonica autonoma, invocata on-demand (es. `/estimate <scope>` pre-progetto). Funziona standalone ma con utilità degradata senza EP-009 (no dati storici → modalità PERT-only). Le invarianti elencate sono **invarianti operative della capability** (parallele alla regola di neutralità di EP-007 e all'invariante «mai medie» della misurazione), **non** invarianti di sistema §7.
**Operazioni canoniche temporal awareness (v2.18, opt-in EP-011)**. Tre operazioni trasversali, **tutte opt-in** via `factory.config.yaml.temporal.enabled: true` + flag specifici (default `false`, R.P3). A flag spento nessuna è invocata e la factory si comporta identica a v2.17. Sono operazioni **trasversali** (cross-taggate nei flussi Develop / Scheduler / Handoff), non operazioni autonome come le analytics: modificano il *come* delle operazioni esistenti aggiungendo metadati temporali al loro flusso. **Nessuna nuova invariante §7** (R.P3). Vedi ADR-028 / ADR-029 / ADR-030 / ADR-031.
- **Temporal Context Injection** = arricchimento del system prompt di ogni sub-agent con un blocco strutturato di contesto temporale (v2.18, EP-011, opt-in: `temporal.context_injection.enabled`). L'Orchestrator inietta: (a) un `session_id` (UUID-v4) generato al boot della sessione; (b) il `task_started_at` (UTC ISO-8601) al kickoff di ogni TSK; (c) un blocco YAML `TEMPORAL CONTEXT` con `current_utc`, `session_id`, `task_started_at`, `elapsed_ms` (wall-clock) calcolato via `tools/temporal/build-temporal-context.sh`. **Single-writer**: solo l'Orchestrator inietta questo blocco. A flag spento i sub-agent non ricevono il blocco (comportamento v2.17). Vedi ADR-030 §A.
- **Temporal Handoff** = blocco YAML strutturato `temporal_handoff:` obbligatorio nel payload di handoff tra agenti quando `temporal.handoff_protocol.enabled: true` (v2.18, EP-011, opt-in). **5 campi obbligatori**: `handoff_id`, `elapsed_ms`, `estimated_remaining_ms`, `completed_steps[]`, `pending_steps[]`, più `context_summary` (mai vuoto). Contratto invariante cross-skill (identico in `dev-handoff.md` e `vcs-handoff.md`, ADR-031 §A). Canale: Sub-agent → Orchestrator return (§20.2) — comprimibile con livello `full`/`ultra` (il campo `context_summary` non è marcato `DO NOT COMPRESS`). A flag spento: no-op (R.P3). Vedi ADR-031.
- **Temporal State Tracking** = file di stato persistente per TSK XL o policy configurata (v2.18, EP-011, opt-in: `temporal.state_machine.enabled`). Formato JSON in `management/state/<TSK-id>.json`: `tsk_id`, `session_id`, `status` (`active | completed | suspended`), `task_started_at`, `last_updated_at`, `history[]` (append-only). Due modalità: `source: standalone` (agente scrive direttamente) o `source: events` (delega a `record-event.sh` + `rebuild-state-from-events.sh`). Activation policy: `always | estimate-xl (default) | never | explicit-only` (ADR-029 §B). Append-only enforce: `true` (default). **Single-writer logico**: un solo writer per TSK per volta. File versionati per audit (vedi `.gitignore` opt-out TSK-093). A flag spento: no-op (R.P3). Vedi ADR-028 / ADR-029.

**Operazione canonica temporal budget (v2.19, EP-014, opt-in)**. Operazione autonoma, **opt-in** via `factory.config.yaml.temporal.budget.enabled: true` (default `false`, R.P3; prerequisito `temporal.enabled: true` da EP-011). A flag spento non è invocata e la factory si comporta identica a v2.18. Le invarianti elencate sono **invarianti operative della capability** (parallele alla regola di neutralità di EP-007), **non** invarianti di sistema §7.
- **Temporal Budget Governance** = bound economico complementare a `max_iterations`
  strutturale (v2.19, EP-014, opt-in). Quando `factory.config.yaml.temporal.budget.enabled: true`,
  la skill `temporal-budget-governor` decide in-loop `proseguire`/`downgrade`/`escalate`/
  `replan`/`hard-stop` su 5 soglie configurabili (ADR-043 §B). Granularità annidata a 3 livelli
  (wave default + tsk + sprint opt-in, ADR-044). Bootstrap N=0 via PERT EP-010 + fallback fisso
  (ADR-045). Pattern: [[circuit-breaker]] + [[evaluator-optimizer]] esteso. Verdict separato
  dall'esecuzione (governor comunica, chiamante esegue, ADR-043 §C). Cross-EP R.C7 EP-015
  (ADR-049): `downgrade` consulta R.C7 prima dello switch. Vedi ADR-043..ADR-046 + §18.8 + skill
  `temporal-budget-governor`.

**Operazione canonica temporal estimate (v2.30, EP-043, opt-in)**. Operazione trasversale, **opt-in** via `factory.config.yaml.temporal.estimate_protocol.enabled: true` (default `false`, R.P3; prerequisito `temporal.enabled: true` da EP-011). A flag spento non è invocata e la factory si comporta identica a v2.29. **Nessuna nuova invariante §7**. Vedi skill `temporal-estimate-protocol.md`.
- `temporal-estimate-protocol` (opt-in v2.30, EP-043) — stima adattiva del tempo rimanente
  da progresso osservato. Skill: `.claude/skills/temporal-estimate-protocol.md`.
  Input: task_estimate + elapsed_ms + completed_steps/total_steps.
  Output: estimated_remaining_ms + confidence + recommendation (continue|warn|escalate).
  Invocato post temporal-budget-governor nel flusso pre-retry-wave dell'orchestratore.
  Config: `temporal.estimate_protocol.enabled` (default false, R.P3).

**Operazione canonica Consistency Check (v2.19, EP-015, opt-in)**. Operazione di verifica dell'integrità contestuale post-hop, **opt-in** via `factory.config.yaml.compression.output.consistency_check.enabled: true` (default `false`, R.P3). A flag spento è no-op e la factory si comporta identica a v2.18. **Nessuna nuova invariante §7**: capability di osservazione read-only, non processo critico.
- **Consistency Check** = verifica indipendente post-hop che l'output di un sub-agent non contraddica il `decision_anchor` del task in corso (v2.19, EP-015, opt-in). Eseguita dall'agente `consistency-checker` (read-only, single-purpose, no self-evaluation — R.C7, ADR-048), separato strutturalmente dal sub-agent valutato. Verdict: `consistent | inconsistent | skip`. `inconsistent` → WARNING in chat + entry `wiki/log.md` `consistency-warning TSK-ZZZ`; mai auto-rollback (gate umano §7 r.16). Esenzione per hop: campo frontmatter TSK `consistency_check_skip_reason` (string, richiede motivazione esplicita). A flag spento: no-op (R.P3). Vedi ADR-047 / ADR-048 / §20.4 R.C7.

**Operazione canonica Token Ledger display (v2.21, EP-022, opt-in)**. Operazione di display real-time, **opt-in** via `factory.config.yaml.analytics.token_ledger.enabled: true` (default `false`, R.P3). A flag spento nessun hook è installato e la factory si comporta identica a v2.20. **Nessuna nuova invariante §7**: capability di display, non processo critico (le 18 invarianti restano invariate). Nota complexity budget: questa sezione conta verso la regola N:1 EP-016 a partire dalla release v2.21 (ADR-052 applicazione prospettica).
<!-- Token Ledger EP-022: sezione aggiunta da TSK-159 (sprint 22). Conta N:1 per v2.21 (ADR-052). -->
- **Token Ledger** = visibilità economica inline dopo ogni operazione (v2.21, EP-022, opt-in).
  Complementa la reportistica batch EP-009 con un display real-time del costo di sessione,
  senza scrivere nell'event store (display-only, nessuna duplicazione di eventi EP-009/EP-013).

  **Scopo**: mostrare in chat, dopo ogni risposta Claude che include tool call, sub-agent o
  modifiche file, il conteggio token reali e il costo stimato della sessione corrente.
  Non sostituisce EP-009 (batch harvest) né EP-013 (dogfooding writer): è il pannello
  strumentazione «in diretta», mentre EP-009/EP-013 sono il log storico aggregato.

  **Architettura** (flusso completo):
  `hook Stop → show-session-tokens.py → transcript JSONL → pricing.yaml → display one-liner`
  - `hook Stop` (adapter Claude Code: `.claude/settings.json` `Stop` hook) invoca lo script
    Python dopo ogni risposta Claude.
  - `show-session-tokens.py` (`tools/analytics/`) legge il transcript JSONL della
    sessione corrente, somma i campi `message.usage` (input / output / cache_read /
    cache_write), risolve il prezzo da `analytics/pricing.yaml` (o fallback prefix-based),
    emette il one-liner `◉ TOKENS ...` su stdout (visibile in chat).
  - Il transcript JSONL è la fonte dati: token **reali** dal runtime, non stime.
  - `analytics/pricing.yaml` — versionato git, medesimo file usato da EP-009 `compute_agentic_cost`
    (riuso della pricing authority, ADR-022). Se assente o PyYAML non installato, fallback
    prefix-based hardcoded (Sonnet $3/$15, Opus $5/$25, Haiku $1/$5).

  **Confine EP-009 / EP-013**:
  - EP-009 (`harvest-session-tokens.py`): batch writer — scrive eventi nell'event store
    `analytics/events/<YYYY-MM>.jsonl` al termine della sessione (SessionEnd). Token ledger
    **non** invoca `record_task_event`, **non** scrive nel JSONL eventi. I token letti dal
    transcript restano nell'ambito del display; la persistenza è responsabilità di EP-009.
  - EP-013 (dogfooding): batch writer schedulato su SessionEnd — produce i record storici
    che EP-009 poi aggrega. Token ledger non interagisce con il path EP-013; è operativamente
    ortogonale (canale separato: display vs store).

  **Confine EP-014 (Temporal Budget Governor)**:
  - EP-014 `temporal-budget-governor`: **monitora** il ratio `elapsed/token_budget` e **decide**
    (`proseguire / downgrade / escalate / replan / hard-stop`) — è un governor con effetti
    sull'esecuzione.
  - Token Ledger: **mostra** i token reali consumati — è display-only, senza decisioni.
    I due sono complementari (il governor usa il budget; il ledger mostra il consumato) e
    indipendenti: possono coesistere entrambi abilitati o solo uno. Nessuna cross-dependency
    di flag (abilitare il ledger non richiede `temporal.budget.enabled: true`).

  **Flag di configurazione** (`factory.config.yaml.analytics.token_ledger.*`):
  - `enabled` — master switch (default `false`). `true` → hook Stop attivo in `settings.json`.
    `false` → hook no-op; il comando `/token-ledger` resta disponibile in query-only.
  - `display_mode` — `compact` (default, one-liner `◉ TOKENS ...`) | `full` (box con breakdown
    input/output/cache_read/cache_write + stima USD per modello).
  - `show_cache_savings` — `true` → mostra il risparmio da cache nel one-liner (suffisso `💾`
    con percentuale). Utile per valutare l'efficacia del prefix caching EP-009.
  - `auto_call_on_wave_close` — `true` → l'orchestrator invoca `show-session-tokens.py --full`
    al termine di ogni wave (default `false` per non inquinare l'output di wave brevi).
  - `pricing_fallback` — `prefix-based` (default) | `fail-loud`. Con `prefix-based`: se
    `analytics/pricing.yaml` è assente o illeggibile, applica i prezzi hardcoded in script.
    Con `fail-loud`: lo script stampa errore e non mostra il costo (solo il conteggio token).

  **Prerequisiti**:
  - Hook `Stop` configurato nell'adapter runtime (Claude Code: `.claude/settings.json`,
    entry `"Stop": [{"type": "command", "command": "python3 <path>/show-session-tokens.py"}]`).
    Negli adapter Cursor/Aider: hook equivalente nel rispettivo config (vedi `adapters/*/manifest.yaml`).
  - Python 3.8+ disponibile nel PATH al momento dell'invocazione dell'hook.
  - `analytics/pricing.yaml` — opzionale (fallback prefix-based se assente). Raccomandato:
    versionare `analytics/pricing.yaml` per avere costi coerenti con EP-009 (ADR-022).
  - `analytics/PRIVACY.md` — documento policy privacy (ADR-040 §G; non richiesto dall'hook,
    ma richiesto da EP-013 dogfooding se `analytics.dogfooding.enabled: true`).

  **Vincolo display-only** (invariante operativa): il Token Ledger **non scrive nell'event
  store** (`analytics/events/`). Non invoca `record_task_event`. Non produce report analytics.
  È un canale di osservazione in sola lettura del transcript, identico per responsabilità al
  `wiki/log.md` (append audit) ma su canale chat. La persistenza dei token ai fini storici
  resta esclusiva di EP-009/EP-013 (single-writer logico sull'event store, §3 Task Analytics).

  Vedi `analytics/pricing.yaml`, `analytics/PRIVACY.md` (ADR-040 §G), skill
  `show-session-tokens.py` (`tools/analytics/`), CLAUDE.md §Token Ledger (EP-022).

- **Project Estimation** = forecasting stack-agnostico del costo/durata di un progetto/EP via skill `project-estimation` (US-040) + tool `estimate_project` / `run_pert` / `run_monte_carlo` / `build_reference_class` (US-041). **Invariante non negoziabile «mai numero puntuale»**: ogni stima è **sempre un intervallo con livello di confidenza e assunzioni esplicite**, mai un valore singolo. Se il caller chiede un solo numero, la skill risponde col P85 + warning «Stima singola sconsigliata: range corretto P50=X, P85=Y» (mai eludere la regola). La regola è enforced **machine-checked** dallo schema, non per convenzione: l'output obbligatorio è il sub-schema `estimate:` con **6 campi obbligatori** (verbatim ADR-024 §E) — `method` (`RCF | PERT | monte-carlo | combined`), `intervals` (cost+duration con `p50`/`p85`, `p95` opzionale, monotonicità `p85 > p50`), `split_human_agentic` (`human_pct + agentic_pct == 100`), `assumptions[]` (lista non-vuota: scope, team, `model_id`, tariffe + `rate_basis`, stato compression layer), `contingency_pct` (≥ 0, **separata dal P50**, mai mescolata nel raw), `sensitivity_drivers[]` (lista non-vuota). Additivo allo schema EP-009 di US-037: rimuovendo `estimate:`, il documento resta un `cost_time_report` valido (backward compat). **Stima ≠ commitment**: ogni report contiene la nota «Questa è una stima statistica, non un impegno contrattuale». **Reference Class Sufficiency Policy** (ADR-025 §C-D): N→confidence (`high|medium|low|very_low`); con N=0 → `method: PERT` forzato + `contingency_pct ≥ 30` + warning testuale in evidenza «Nessun dato storico disponibile». Stima debole mai nascosta (parallelo a «manual_checks sempre presenti» di EP-007). **Telemetria accuracy retrospettiva**: pattern [[evaluator-optimizer]] applicato alla stima — la misurazione finale di EP-009 è l'evaluator; ogni stima ha un `estimate_id` univoco e, alla chiusura del progetto, è auto-generato `analytics/reports/accuracy/<estimate_id>.{json,md}` (P50/P85 stimato vs reale + delta + lessons_learned). Cross-link [[learning-accumulation]]. **Integrazione opzionale con il DAG / parallel-scheduler** (US-044): oltre alla stima aggregata, la skill US-040 e l'agente US-043 possono produrre una **distribuzione di durata per layer** (`docs/fe/be/qa/review`) filtrando `analyze_timeline` per `layer` → reference class per layer → P85 per layer. Dato un [[dependency-ordered-dag]] con nodi taggati per layer, propagando il P85 lungo il grafo si identifica il **critical path probabilistico** (il path che massimizza la durata totale al P85). Attivazione via flag `/estimate --critical-path=<DAG-source>` (es. percorso a un kanban): produce nel report la sezione opzionale `critical_path_analysis: {layers[], dominant_path[], bottleneck_layer}` derivata dai P85 per layer. Le distribuzioni storiche di EP-007/EP-008/EP-009 (a11y scan, ux-ui review, code review) entrano automaticamente nella stima per layer — nessuna istruzione esplicita. Cross-link [[dependency-ordered-dag]] + [[parallel-scheduler]] (vedi §18, dominio condiviso `analytics`). Vedi [[task-analytics-cost-estimation-capability]] §Due facce della capability + [[task-analytics-estimation-methods]] §Integrazione con il parallel-scheduler del framework + ADR-024 §E / ADR-025 §F / ADR-026 / ADR-027.

  **Reference Class Sufficiency Policy (EP-025, ADR-025 §A-C)** — La skill `project-estimation` implementa una policy data-driven per determinare il metodo di stima (RCF / PERT) e la contingency raccomandata in funzione della qualità della reference class storica (`N` task con lo stesso `task_type`/`layer`). Quattro livelli di confidence (`HIGH` / `MEDIUM` / `LOW` / `VERY_LOW`) derivati da `bucket_by_N` (soglie config `analytics.estimation`) + downgrade per similarity. Enforce hard su `VERY_LOW`: PERT obbligatorio + contingency >= 30%. Opt-in via `analytics.estimation.enabled: true` (default `false`, R.P3).

  **Loop learning-accumulation (EP-026, ADR-027 §D)** — Il ciclo di apprendimento estimation si chiude con tre fasi: **Cattura** (EP-010) — ogni `/estimate --review-accuracy` produce `analytics/reports/accuracy/<estimate_id>.json` con delta e verdict. **Aggrega** (EP-026) — `/estimate --aggregate-accuracy` invoca il tool `aggregate-accuracy` (`.claude/tools/analytics/aggregate-accuracy.md`) che scansiona tutti i file di accuracy e calcola statistiche per metodo (rcf/pert/combined) e per confidence bucket (high/medium/low/very_low). Utile con N >= 10 retrospettive; con N < 10 emette avviso orientativo e procede. Output: `analytics/reports/calibration/<YYYY-MM-DD>-calibration.{json,md}`. **Calibra** — i `calibration_signals` del report indicano il metodo più accurato e il confidence bucket più debole; il PM valuta se aggiornare le soglie in `factory.config.yaml` (mai auto-modify); riesegui `/lint` dopo ogni modifica config. Nessuna invariante §7 e' modificata: il tool e' una capability di ottimizzazione. Ref: ADR-027 §D. Seed meta-prompt v2.22 citerà EP-026 come `analytics.estimation.aggregate_accuracy` (deferred al ciclo v2.22).

## §4 — Naming conventions
<!-- profiles: standard, full -->
| Artefatto | Pattern |
|---|---|
| PDF | `YYYY-MM-DD-<nome>.pdf` (e `.txt` corrispondente) |
| Figura PDF | `YYYY-MM-DD-<nome>-fig-NN.md` |
| KB Figma | `raw/YYYY-MM-DD-figma-<file-key>.kb.json` (prodotto da `figma-sync`, §16) |
| Frame Figma | `raw/images/YYYY-MM-DD-figma-<file-key>-frame-NN.md` (companion stub; binario `.png` opzionale stesso slug) |
| Source page | `wiki/sources/<kebab-slug>.md` |
| Concept page | `wiki/concepts/<kebab-slug>.md` |
| Entity page | `wiki/entities/<kebab-slug>.md` |
| Synthesis page | `wiki/syntheses/<kebab-question>.md` |
| Runbook | `wiki/runbooks/<kebab-slug>.md` |
| Incident | `wiki/incidents/YYYY-MM-DD-<kebab-slug>.md` |
| Epica | `management/kanban/EP-XXX-<slug>/EP-XXX.md` |
| Storia | `management/kanban/EP-XXX-<slug>/US-YYY-<slug>/US-YYY.md` |
| Task | `management/kanban/EP-XXX-<slug>/US-YYY-<slug>/TSK-ZZZ.md` |
| Memoria episodica | `memory/episodic/YYYY-MM-DD-HH-MM-<slug>.md` |
| Memoria semantica | `memory/semantic/<slug>.md` |
| Memoria procedurale | `memory/procedural/<slug>.md` |
| Tech-stack proposal | `raw/tech_stack.md.proposal` (effimero, gate umano per promote → `raw/tech_stack.md`) |
| Repo spec (v2.12) | `raw/YYYY-MM-DD-repo-<slug>.md` (prodotto da `repo-sync`, §16); opzionale companion `raw/images/YYYY-MM-DD-repo-<slug>-tree.md` |
| Graph summary (v2.14 Fase 2) | `raw/YYYY-MM-DD-graph-<slug>.md` (prodotto da `graphify-sync`, §16; riepilogo umano-leggibile: god nodes, surprising connections, confidence breakdown) |
| Graph side-channel (v2.14 Fase 2) | `.graphify-state/code_paths/<slug>/{graph.json,GRAPH_REPORT.md,last_full_rebuild.txt}` (non versionato in git, rebuildable da `<code_path>`) |
| Code quality rule (v2.12) | `code_quality/rules/<tier>/<rule_id>.md` con `<tier> ∈ {canonical, emergent, team-specific}` e `<rule_id>` in formato dotted `{language}.{framework}.{category}.{specific}` |
| Code quality report (v2.12) | `code_quality/reports/<TSK-id>-iter-<N>.json` (machine-readable) + `code_quality/reports/<TSK-id>-iter-<N>.md` (digest umano-leggibile) |
| Factory config | `factory.config.yaml` (singolo file, root del repo) |

Slug: lowercase, spazi→`-`, rimuovi `()/'`, max 40 char. XXX/YYY/ZZZ = 3 cifre zero-padded.

## §5 — Frontmatter (minimo necessario, deduci dal path quando possibile)
<!-- profiles: minimal, standard, full -->
- **Wiki page:** `type`, `sources`, `status` (`draft|review|approved`)
- **Epica:** `id`, `title`, `status`, `priority`, `confidence`, `confidence_rationale`, `wiki_pages`, `created`, **opzionale (v2.10)**: `external_id` (`<provider>:<id>` se pubblicata su tool esterno via Publisher, §17), **opzionale (v2.11)**: `depends_on` (lista EP prerequisite, input per scheduler §18), **opzionale (v2.16)**: `risk_classification` (blocco strutturato: `tier`, `premortem_ref`, `reviewed_by` — vedi paragrafo dedicato sotto)
- **User Story:** `id`, `title`, `role`, `priority`, `status`, `wiki_page`, `blocked_by` (`epic` deducibile dal path), **opzionale (v2.10)**: `external_id`, **opzionale (v2.11)**: `depends_on` (lista US prerequisite), **opzionale (v2.16)**: `risk_classification` (idem EP)
- **Task:** `id`, `sprint`, `layer` (`be|fe|db|qa|infra`), `consumer` (`agent|human`), `priority`, `estimate`, `status` (`story`/`epic` deducibili dal path; `team` deprecato in v2.7 — usa `layer`), **opzionale (v2.10)**: `external_id`, **opzionale (v2.11)**: `depends_on` (lista TSK prerequisiti), `blocked_by` (lista `Q_NNN` hard aperte, simmetrico US), `code_path` (lista glob L5 toccati in scrittura — input per conflict detection §18; in multi-repo v2.12 i glob sono *relativi al target*), **opzionale (v2.12, §19)**: `review_status` (`pending|passed|conditional|rejected`, default `pending` se `code_quality.enabled: true`; assente se disabilitato), `review_iter` (integer, default `0`), `review_report` (path al report più recente in `code_quality/reports/`), **opzionale (v2.12, multi-repo §13)**: `target` (nome di un'entry in `factory.config.yaml.code_paths`; required se la combinazione `(routing.<layer>, code_paths)` produce ambiguità — vedi §13), **opzionale (v2.16)**: `risk_classification` (idem EP), **opzionale (v2.17, §G ADR-012)**: `visual_status` (`pending|pass|conditional|reject`, single-writer skill `visual-oracle-protocol`; default implicito assente = `pending`), `interaction_test_spec` (path test Playwright, scritto da TPM), `visual_reference` (path frame Figma/screenshot, scritto da TPM), **opzionale (v2.18, EP-009, ADR-023 §G)**: `cost_event_log` (path al log eventi del TSK), `effort_hours` (float ≥ 0, ore umane dichiarate dal closer) — vedi paragrafo dedicato sotto, **opzionale (v2.18, EP-010, ADR-027 §G)**: `estimate_id` (collega il TSK alla stima preliminare per accuracy retrospettiva) — vedi paragrafo dedicato sotto, **opzionale (v2.18, EP-007, ADR-016)**: `a11y_status` (`pending|pass|major|critical|skip`), `a11y_report` (path al report a11y più recente in `code_quality/reports/`), `a11y_skip_reason` (string, required se `a11y_status: skip`) — vedi paragrafo dedicato sotto, **opzionale (v2.18, EP-008, ADR-020 §F)**: `ux_ui_status` (`pending|pass|conditional|reject|skip`), `ux_ui_report` (path al report review più recente in `code_quality/reports/`), `ui_design_spec` (path al deliverable Design in `code_quality/reports/`), `ux_ui_skip_reason` (string, required se `ux_ui_status: skip`) — vedi paragrafo dedicato sotto, **opzionale (v2.19, EP-014, ADR-046 §F)**: `token_budget` (int|null, override esplicito del budget calcolato da P85), `temporal_budget_skip_reason` (slug|null, esenzione documentata dal Lint Check 4u), `budget_strategy` (`strict|adaptive`|null; null = `strict` default, `adaptive` rinviato v2.20+) — vedi paragrafo dedicato sotto, **opzionale (v2.19, EP-015, ADR-047/048)**: `consistency_check_skip_reason` (string|null, motivazione esplicita per esentare un hop del TSK dalla Consistency Check; required se l'hop è dichiarato esente con `compression.output.consistency_check.enabled: true`; WARNING di `wiki-lint` se assente con esenzione dichiarata; single-writer: il TPM in fase di taskizzazione) — vedi §20.4 R.C7, **opzionale (v2.20, EP-018, ADR-065 §Storage/§B)**: `functional_status` (`pending|pass|conditional|reject|skip`, single-writer skill `functional-oracle-protocol` — `qa-dev` in modalità functional-oracle, ADR-067 §A; default implicito assente = `pending`), `functional_acceptance_spec` (path all'acceptance-spec YAML del progetto/TSK, es. `code_quality/acceptance/<app>.acceptance.yaml`; scritto dal **TPM** in fase di taskizzazione — analogo a `interaction_test_spec:` di ADR-012; ADR-065 §B) — vedi paragrafo dedicato sotto, **opzionale (v2.18, EP-011, ADR-028/029)**: `temporal_state` (boolean, `true` se il TSK usa la State Machine — scritto dal **TPM** in fase di taskizzazione; default implicito assente = `false`), `temporal_state_path` (string, path esplicito al state file; implicito se assente e `temporal_state: true` → `management/state/<TSK-id>.json`; single-writer: l'agente con ownership del state file per quel TSK) — vedi paragrafo dedicato sotto, **opzionale (v2.22, EP-029)**: `failure_classification` (enum: `APPLICATION_BUG | SSR_BUG | TEST_BUG | INFRASTRUCTURE | FLAKY`; rilevante solo per TSK con `layer: qa`; impostabile da `qa-dev` auto-classificazione o da umano override; campo assente = comportamento invariato, backward compat totale; vedi paragrafo dedicato sotto)
- **Stato «in corso»** (v2.44, EP-072): `in-progress` e `in_progress` sono la stessa forma. Gli strumenti normalizzano il trattino (`-` → `_`) prima di confrontare; una factory ne sceglie una e la usa ovunque, ma un lettore che ne riconosce una sola e' un difetto (misurato: `sprint-progress` contava gli `in_progress` come todo).
- **Figura:** `source_pdf`, `page`, `figure_number`, `type`
- **Memoria:** `type` (`episodic`/`semantic`/`procedural`), `created`, `tags`

Regola: `id` e `status` (dove applicabile) sono **sempre obbligatori**; tutto il resto deducibile dal path va rimosso.

**`external_id` (v2.10)**: campo frontmatter scritto **solo** dal sub-agent Publisher (§17) corrispondente al provider configurato in `factory.config.yaml.kanban_publish.provider`. Forma canonica: `<provider>:<id>` dove `<provider>` ∈ {`github`, `gitlab`, `jira`, `linear`, …} e `<id>` è l'identificatore esterno (numero issue, key Jira, UUID Linear, …). Esempi: `github:1234`, `gitlab:567`, `jira:PROJ-89`, `linear:abc-uuid-…`. Funzione: idempotenza al re-publish (Publisher fa UPDATE se presente, CREATE se assente). PM/TPM/Dev **non scrivono mai** questo campo (è scope esclusivo del Publisher, vedi §17 invariante di isolamento).

**`depends_on` / `blocked_by` / `code_path` (v2.11)**: campi che codificano le dipendenze causali e gli scope di scrittura per il parallel scheduler (§18). Semantica:
- `depends_on: [<id>, ...]` — lista di artefatti dello stesso tipo (EP→EP, US→US, TSK→TSK) che DEVONO essere almeno in stato avanzato (`done` per TSK; `ready`/`done` per US; `in-progress`/`done` per EP) prima di poter procedere su questo artefatto. **Hard dependency**: gate non bypassabile. La semantica per tipo è formalizzata in §18.
- `blocked_by: [Q_NNN, ...]` — equivalente al campo omonimo su US (§5 v2.6): lista di `Q_NNN` con `Bloccante: hard` aperte che bloccano l'artefatto. Già definito per US in v2.6; **esteso a TSK in v2.11**.
- `code_path: ["<glob>", ...]` — solo TSK. Lista di glob in `<code_path>/**` che il TSK prevede di toccare in scrittura. Lo scheduler la usa per il **conflict-detection**: due TSK con intersezione non vuota di glob non sono parallelizzabili (race su file). Lista vuota = "scope sconosciuto" → trattamento conservativo (serializzante). Glob, non path assoluti; esempio: `["src/auth/**", "tests/integration/auth/**"]`.

PM, Arch, TPM scrivono `depends_on` quando producono l'artefatto (v2.11). I dev-agent **non lo modificano** (read-only su questo campo, come sui `## Dependencies` del body). Drift fra `depends_on` frontmatter e sezione `## Dependencies` body → warning di `wiki-lint` (frontmatter prevale).

**`review_status` / `review_iter` / `review_report` (v2.12)**: campi del solo TSK, scritti **esclusivamente** dal Code Reviewer (§2). Semantica:
- `review_status` — `pending` (TSK chiuso da Develop, in attesa di Review), `passed` (verdict `pass` dell'aggregator §19.3), `conditional` (verdict `conditional` — feedback loop attivo, dev-agent re-invocato), `rejected` (verdict `reject` o `max_iterations` raggiunto — gate umano §7 r.16).
- `review_iter` — contatore del round di review/fix corrente. Incrementato dal Code Reviewer prima di consegnare un nuovo `task_package` al dev-agent. Bounded da `code_quality.max_iterations` (default 3).
- `review_report` — path relativo al report più recente in `code_quality/reports/`. Esempio: `code_quality/reports/TSK-042-iter-2.md`.

PM/TPM/Dev **non scrivono mai** questi campi (scope esclusivo del Code Reviewer §19.6 R.Q2). Drift fra `review_status` frontmatter e ultima entry `review` in `wiki/log.md` → warning di `wiki-lint` (frontmatter prevale).

**`visual_status` / `interaction_test_spec` / `visual_reference` (v2.17)**: tre campi del solo TSK, **opzionali e additivi**, introdotti dal Visual Oracle (EP-005, ADR-012 §A/§G). Backward compat totale: assenza dei campi = comportamento v2.16 identico.
- `visual_status` — enum `pending | pass | conditional | reject`. **Single-writer: solo la skill `visual-oracle-protocol`** (analogo a `review_status:` di CQRL, R.Q2). Dev-agent, PM, TPM **non lo scrivono mai** a runtime. **Default implicito**: campo assente = `pending`. Letto da: `code-review-protocol` Fase 0 (gating precondition, §19 + ADR-009/ADR-013) e Oracle Pre-Check dell'orchestrator.
- `interaction_test_spec` — path (relativo al code_path) a un file di test Playwright. Scritto dal **TPM** in fase di taskizzazione (input di specifica, non output di runtime). Letto dalla Fase 3-bis di `visual-oracle-protocol`.
- `visual_reference` — path (relativo al repo) a un frame Figma o screenshot reference. Scritto dal **TPM** in fase di taskizzazione. Letto dal critic (Fase 4) di `visual-oracle-protocol` come specifica visiva contro cui criticare.

**`cost_event_log` / `effort_hours` (v2.18)**: due campi del solo TSK, **opzionali e additivi**, introdotti dalla capability analytics di misurazione (EP-009, ADR-023 §G). Backward compat totale: assenza dei campi = comportamento v2.17 identico (TSK pre-v2.18 continuano a parseare). Entrambi sono opt-in e non introducono alcun lint check obbligatorio.
- `cost_event_log` — path (relativo al repo) al log eventi del TSK (es. `analytics/events/per-task/T-1042.jsonl`, sottoinsieme filtrato dell'event store `analytics/events/<YYYY-MM>.jsonl`). **Single-writer**: il tool `record_task_event` (US-033) o l'`analytics-reporter` (US-038). Letto per audit puntuale sul TSK. Mai scritto da PM/Arch a mano.
- `effort_hours` — float ≥ 0: ore umane dichiarate dal closer del TSK (override del valore eventualmente auto-derivato dai timestamp degli eventi). **Single-writer**: il dev-agent o il closer umano del TSK (TPM se umano), analogo a `interaction_test_spec:` di EP-005. Raccomandato (non obbligatorio) quando `actor_type: human` e il lead time del TSK appare parallelo ad altri (per evitare overcounting nell'aggregazione effort).

**`estimate_id` (v2.18, EP-010)**: campo del solo TSK, **opzionale e additivo**, introdotto dalla capability analytics di stima (EP-010, ADR-027 §G; consolidamento di ADR-023 §G). Backward compat totale: assenza del campo = comportamento v2.17 identico. Opt-in, non introduce alcun lint check obbligatorio (il Check 4r è WARNING-only e gated da `analytics.estimation.required_on_kickoff`).
- `estimate_id` — string in formato `EST-<YYYY-MM-DD>-<NNN>` (`NNN` contatore incrementale per giorno, zero-padded a 3 cifre; es. `EST-2026-06-04-001`). Collega il TSK alla stima preliminare del progetto/EP cui appartiene, per la telemetria di accuracy retrospettiva (join «stima EST-XXX ↔ TSK del progetto», ADR-027 §F). **Single-writer**: chi ha generato la stima — la skill `project-estimation` (US-040) o l'agente `estimation-analyst` (US-043) — oppure il TPM umano al momento della scrittura del TSK se la stima è precedente. Mai scritto dai dev-agent a runtime. **Validation cross-file**: l'`estimate_id` referenziato deve esistere come file `analytics/reports/estimates/<...>` con quel id; mismatch (frontmatter cita id ma file inesistente) → WARNING di `wiki-lint` (ADR-027 §G). Vedi anche Check 4r (`.claude/skills/lint-checks.md`).

**`a11y_status` / `a11y_report` / `a11y_skip_reason` (v2.18, EP-007)**: tre campi del solo TSK, **opzionali e additivi**, introdotti dalla capability a11y (EP-007, ADR-016 §F). Backward compat totale: assenza dei campi = comportamento v2.17 identico (TSK pre-v2.18 continuano a parseare). Opt-in, gated dalla capability (`factory.config.yaml.a11y.enabled`); il solo lint check correlato (Check 4o) è WARNING-only e gated da `a11y.required_on_fe_done`.
- `a11y_status` — enum `pending | pass | major | critical | skip`. **Single-writer logico: l'agente che esegue lo scan** via skill `accessibility-testing-protocol` (US-024) — `a11y-specialist`, `qa-dev` o `fe-dev` a seconda della modalità (ADR-014). Nessun altro agente lo scrive. **Default implicito**: campo assente ≡ `pending` se `a11y.enabled: true`. Letto da: Lint Check 4o, qa-dev (skip su TSK già scan-ato), `code-review-protocol` (precondition opzionale, non strict).
- `a11y_report` — path (relativo al repo) al report più recente in `code_quality/reports/<TSK-id>-a11y-iter-<N>.json`. **Single-writer**: stesso agente di `a11y_status`.
- `a11y_skip_reason` — string, **required** se `a11y_status: skip`. **Single-writer: il TPM** in fase di scrittura del TSK (input di specifica, analogo a `interaction_test_spec:` di EP-005). Esempio: "componente già coperto da scan parent route". `skip` senza reason → WARNING di `wiki-lint` (Check 4o).

**`ux_ui_status` / `ux_ui_report` / `ui_design_spec` / `ux_ui_skip_reason` (v2.18, EP-008)**: quattro campi del solo TSK, **opzionali e additivi**, introdotti dalla capability UX/UI (EP-008, ADR-020 §F). Backward compat totale: assenza dei campi = comportamento v2.17 identico (TSK pre-v2.18 continuano a parseare). Opt-in, gated dalla capability (`factory.config.yaml.ux_ui.enabled`); il solo lint check correlato (Check 4p) è WARNING-only e gated da `ux_ui.required_on_fe_done`.
- `ux_ui_status` — enum `pending | pass | conditional | reject | skip`. **Single-writer logico: l'agente che esegue la review** via skill `ux-ui-review-protocol` (US-028) — `ux-ui-reviewer` se scaffoldato, altrimenti `fe-dev`/`qa-dev` a seconda della modalità (ADR-019). Nessun altro agente lo scrive. **Default implicito**: campo assente ≡ `pending` se `ux_ui.enabled: true`. Letto da: Lint Check 4p, `code-review-protocol` Fase 0 (precondition opzionale, nota informativa, **no ABORT** — ADR-019 Punto 2, differente dalla precondition hard di `visual_status`).
- `ux_ui_report` — path (relativo al repo) al report review più recente in `code_quality/reports/<TSK-id>-uxui-review-iter-<N>.json`. **Single-writer**: stesso agente di `ux_ui_status`.
- `ui_design_spec` — path (relativo al repo) al deliverable Design in `code_quality/reports/<TSK-id>-uxui-design.json`. **Single-writer: il TPM** in fase di scrittura del TSK (input di specifica, analogo a `interaction_test_spec:` di ADR-012 e `a11y_skip_reason:` di ADR-016). L'agente `ui-designer` **suggerisce** il path nel proprio output (logging), il TPM committa.
- `ux_ui_skip_reason` — string, **required** se `ux_ui_status: skip`. **Single-writer: il TPM**. `skip` senza reason → WARNING di `wiki-lint` (Check 4p).

**`functional_status` / `functional_acceptance_spec` (v2.20, EP-018)**: due campi del solo TSK, **opzionali e additivi**, introdotti dalla capability Functional Oracle (EP-018, ADR-065 §Storage/§B). Backward compat totale: assenza dei campi = comportamento v2.19 identico (TSK pre-v2.20 continuano a parseare). Opt-in, gated dalla capability (`factory.config.yaml.fe_correctness.functional_oracle.enabled`, default `false`).
- `functional_status` — enum `pending | pass | conditional | reject | skip`. **Single-writer: solo la skill `functional-oracle-protocol`** eseguita da `qa-dev` in modalità functional-oracle (ADR-067 §A; fallback `fe-dev` se `qa-dev` non in topologia). Dev-agent, PM, TPM **non lo scrivono mai** a runtime (analogo a `visual_status:` e `review_status:` di CQRL, R.Q2). **Default implicito**: campo assente ≡ `pending` se `functional_oracle.enabled: true`. Il verdict è deterministico — nasce esclusivamente dalle asserzioni binarie (ADR-065 §C/§D); il critic LLM è solo advisory e non può influenzare il campo (ADR-067 §B).
- `functional_acceptance_spec` — path (relativo al repo) all'`acceptance-spec` YAML del progetto o del TSK, es. `code_quality/acceptance/<app>.acceptance.yaml` o `code_quality/acceptance/<TSK-id>.acceptance.yaml`. **Single-writer: il TPM** in fase di taskizzazione (input di specifica, non output di runtime; analogo a `interaction_test_spec:` di ADR-012 e `a11y_skip_reason:` di ADR-016). Se `functional_oracle.enabled: true` e spec assente/illeggibile → fail-loud (mai pass silenzioso, ADR-065 §E). Schema dell'acceptance-spec definito in ADR-065 §B (campi: `fixtures`, `scenario`, `assertions`, `thresholds`).

**`failure_classification` (v2.22, EP-029)**: campo del solo TSK, **opzionale e additivo**, introdotto dalla tassonomia Test Failure Taxonomy (EP-029). Backward compat totale: assenza del campo = comportamento v2.21 identico (TSK pre-v2.22 continuano a parseare senza effetti). Rilevante **solo** per TSK con `layer: qa`; su altri layer viene ignorato.

```yaml
failure_classification:   # Opzionale; solo per TSK layer: qa (EP-029, v2.22).
                          # Enum: APPLICATION_BUG | SSR_BUG | TEST_BUG | INFRASTRUCTURE | FLAKY
                          # Assente = comportamento invariato (backward compat totale).
                          # Impostabile da qa-dev (auto) o da umano (override manuale).
```

Enum legale (5 valori exhaustivi):

| Valore | Descrizione | Routing differenziato |
|---|---|---|
| `APPLICATION_BUG` | Il test fallisce per un bug nell'applicazione (BE o FE) | → `be-dev` (tag: be) o `fe-dev` (tag: fe); human gate se ambiguo |
| `SSR_BUG` | Il test fallisce per un bug specifico di rendering server-side | → `fe-dev` con context aggiuntivo `"ssr"` nell'handoff |
| `TEST_BUG` | Il test stesso è errato o non aggiornato (falso negativo) | → `qa-dev` |
| `INFRASTRUCTURE` | Il test fallisce per problemi di ambiente/infrastruttura | → human gate obbligatorio (no dispatch automatico) |
| `FLAKY` | Il test è non deterministico (intermittente) | → quarantena EP-027 se `qa_layer.flakiness_detection.enabled: true`; human gate altrimenti |

**Single-writer**: il campo è impostabile da `qa-dev` in auto-classificazione oppure da un umano in override manuale. L'ultimo valore scritto è quello valido. Mai sovrascritto da altri agenti (dev-agent BE/FE, PM, Arch).

**Validation**: un valore fuori dall'enum è flaggato come WARNING da `wiki-lint` (Check 4ad, EP-029). Il campo assente non genera WARNING (backward compat totale).

**Allineamento con EP-028**: le categorie EP-028 (`STALE_SELECTOR` ecc.) sono a **grana fine** (classificazione interna al singolo test-case); `failure_classification` di EP-029 è a **grana grossa** (classificazione a livello TSK). I due campi sono su livelli distinti e non si sovrappongono: un TSK può avere `failure_classification: TEST_BUG` mentre singoli test-case nel corpo del TSK portano categorie EP-028 più specifiche.

**Nota di attivazione del routing**: il campo `failure_classification:` attiva la logica QA Failure Routing nella skill `feedback-router` (§ QA Failure Routing, EP-029) solo quando `qa_layer.failure_taxonomy.enabled: true` in `factory.config.yaml`. A flag spento, il campo è documentale (nessun enforcement routing runtime).

**`target` (v2.12, multi-repo)**: in setup multi-repo (`code_paths` con più di una entry per uno stesso `layer`), il TSK DEVE dichiarare il `target` per disambiguare a quale repo punta la scrittura. Scritto dal *TPM* quando produce il TSK; mai modificato a runtime dal Dev. Semantica di risoluzione:
- `target: <name>` valorizzato → cerca `code_paths[name == target]`. Se non trovato → ERROR del dev-agent.
- `target:` assente → filtra `code_paths` per `<layer> ∈ entry.layers`. Se 1 match → usa quello (auto-derive). Se ≥ 2 match → ERROR (TPM doveva valorizzare `target`). Se 0 match → ERROR di config (nessun repo dichiara questo layer).
- Backward compat: se `code_paths` ha una sola entry o `code_path` (singolare, legacy v2.11-) è in uso, `target:` è opzionale e ignorato.

**`risk_classification` (v2.16)**: blocco opzionale su EP/US/TSK con 3 sotto-campi. Introdotto dal pattern Premortem (operazione opzionale §3, vedi `.claude/skills/premortem-protocol.md`). Schema:

```yaml
risk_classification:
  tier: <enum>                 # required se il blocco è presente
  premortem_ref: <path#anchor> # opzionale
  reviewed_by: [<handle>, ...] # opzionale, lista
```

| Campo | Tipo | Required | Esempio |
|---|---|---|---|
| `tier` | enum (6 valori sotto) | sì se blocco presente | `tiger-launch-blocking` |
| `premortem_ref` | string `<path>#<anchor>` verso `management/risk-registry.md` | no | `management/risk-registry.md#pm-2026-05-29-EP-042` |
| `reviewed_by` | list[string] di handle `@user` o nomi team | no | `["@soli92", "@arch-team"]` |

Enum legale per `tier` (6 valori): `tiger-launch-blocking | tiger-fast-follow | tiger-track | paper-tiger | elephant | high-impact` (quest'ultimo è il catch-all per "alto impatto ma premortem non ancora eseguita").

Esempi positivi:

```yaml
# EP cross-cutting, alto impatto, premortem eseguita
risk_classification:
  tier: tiger-launch-blocking
  premortem_ref: management/risk-registry.md#pm-2026-05-29-EP-042
  reviewed_by: ["@soli92"]

# US con incertezza ma senza premortem formale
risk_classification:
  tier: high-impact
```

Esempi negativi (malformati, riconoscibili a colpo d'occhio):

```yaml
risk_classification:
  tier: maybe-risky        # ← tier non in enum legale
risk_classification: {}    # ← blocco vuoto: tier è required
tier: tiger-track          # ← tier fuori dal blocco risk_classification
```

**Default semantico**: assenza del blocco = `tier: untagged` (concetto, **non** un valore scritto nel file). Garantisce backward compat totale (R.P3 opt-in v2.16): una factory che non aggiunge mai il blocco si comporta identica a v2.15. Validato da `wiki-lint` Check 4m (**WARNING-only**, mai ERROR). PM/Arch/TPM possono scriverlo; il pattern premortem lo *suggerisce* ma non lo applica mai in autonomia (R.P1). Vedi `wiki/concepts/factory-premortem-integration.md` per il design doc.

I glob in `code_path` (TSK) sono **relativi al target risolto**: lo scheduler conflict-detection (§18.4 R.S2) opera su `(target, glob)` — due TSK con target diversi non confliggono mai (filesystem disgiunti).

**Frontmatter TSK temporal budget (v2.19, EP-014, opt-in, ADR-046 §F)**. Tre campi opzionali, additivi, **no migration richiesta** (assenza = comportamento v2.18 identico, R.P3):

```yaml
# Temporal Budget (v2.19, EP-014, opt-in)
token_budget: <int|null>                     # override esplicito del budget calcolato da P85 (ADR-044 §F)
temporal_budget_skip_reason: <slug|null>     # esenzione documentata dal Lint Check 4u (ADR-046 §E)
budget_strategy: <"strict"|"adaptive"|null>  # strategia replan (null = strict default, ADR-046 §F)
                                             # "strict": replan richiede strategia alternativa documentata
                                             # "adaptive": rinviato v2.20+
```

Consumati dalla skill `temporal-budget-governor` (§18.8) quando `temporal.budget.enabled: true`. A flag spento sono documentali (nessun enforcement runtime). Pattern parallelo a `risk_classification:` (EP-007) e `cost_event_log:` (EP-009): opzionali = no migration.

## §6 — Grammatica delle citazioni
<!-- profiles: standard, full -->
- Citazione fonte testuale: `[^src: <path-relativo>.{md,txt} §<sezione>]` su ogni claim ≥ 20 parole (la sezione è un header markdown del file citato).
- Citazione fonte strutturata (JSON, v2.9): `[^src: <path-relativo>.kb.json §<dotted-path>]` dove `<dotted-path>` segue la convenzione (a) chiavi punto-separate (`§project.name`, `§tokens.colors`), (b) indice positivo per array (`§screens[0]`), (c) selettore per chiave (`§components[name=Button]`). Solo notazioni leggibili a mano; vietato JSONPath complesso o JMESPath.
- Link interno wiki: `[[nome-pagina-senza-estensione]]`, **mai** path relativi `../../`.
- Citazione codice (factory): `[^code: <path>:<line>]`.
- Citazione codice prodotto (L5):
  - `vcs.mode: monorepo` → `[^src5: <code_path>/<path>:<line>]` (path relativo, commit factory).
  - `vcs.mode: submodule` → `[^src5-sub: <submodule_path>/<path>:<line> @ <commit-hash>]` (path interno al factory repo, commit del submodule).
  - `vcs.mode: sibling` o `external` → `[^src5-ext: <abs-path>:<line> @ <commit-hash>]` (path assoluto, commit del repo esterno).
- Claim senza citazione = claim invalido (segnalato dal *Lint*, mai bloccato deterministicamente).

## §7 — Regole inviolabili (18)
<!-- profiles: minimal, standard, full -->
1. **L1 read-only** (eccetto *Sync*).
2. **Zero invenzione.** Info assente → `wiki/gaps.md` o `management/questions.md`.
3. **Citazione obbligatoria** su ogni claim non triviale.
4. **Wikilink** per link interni, mai path relativi.
5. **`wiki/log.md` append-only.** Stesso vincolo per `wiki/gaps.md` e `wiki/incidents/`.
6. **Report preliminare e STOP** prima di scrivere file in batch.
7. **Update non distruttivo** su pagine `review|approved`: aggiungi `## Aggiornamenti (vYYYY-MM-DD)`.
8. **Scope di scrittura chiuso** per ruolo (§2). I dev-agent scrivono solo `<code_path>/**` + `status:`/`updated:` del proprio TSK; mai design o wiki.
9. **Gate L4 graduato (`blocking_level`).** `Q_NNN` con `blocking_level: hard` aperta blocca le US dipendenti; `soft` consente di procedere annotando `pending_clarification`. Idem per L5: TSK con `consumer: agent` e dipendenze `blocked_by` aperte (hard) → STOP del dev-agent corrispondente.
10. **`raw/tech_stack.md` priorità assoluta.** SAML/OIDC/SOAP citati non si sostituiscono con alternative. La skill `tech-scout` propone, mai applica: scrive `.proposal`, l'umano promuove.
11. **`memory/` non è wiki/.** Persistenza cross-conversazione vive in `memory/`, mai mescolata con `wiki/log.md`.
12. **`wiki/` è read-universal**, **single-committer**. Solo l'*Analyst* committa su `wiki/`. Eccezioni: `## Storie collegate` (PM), `wiki/gaps.md` (L3+ append), `status:` frontmatter via `/promote` (Orchestrator), entry `develop` su `wiki/log.md` (dev-agent, append-only).
13. **Topology & consumer routing dichiarati**. Se esistono dev-agent in `.claude/agents/` (o equivalente per altri adapter), DEVE esistere `factory.config.yaml` con `topology:`, `code_path:`, e `routing:` valorizzati (§13). Un dev-agent può rifiutarsi di operare se il TSK non ha `layer:` + `consumer:` espliciti.
14. **VCS dichiarato** (v2.8). Se `code_path:` è valorizzato, DEVE esistere `vcs.mode:` in `factory.config.yaml` (`monorepo | submodule | sibling | external | none`). Nessuna operazione `git submodule add|update`, `git clone`, `git push`, `git commit --amend`, o force-push viene MAI eseguita automaticamente: la skill `vcs-handoff` propone, l'umano conferma (gate non bypassabile per scritture VCS distruttive o cross-repo).
15. **Cross-tool publish gate umano** (v2.10). Se `kanban_publish.provider ≠ none` in `factory.config.yaml`, il sub-agent Publisher (§17) deve mostrare in chat il piano di pubblicazione (lista di CREATE + UPDATE proposti con conteggi per tipo) e **attendere conferma esplicita** prima di qualsiasi chiamata write sul provider esterno. Mai operazioni `delete`/`close` automatiche su issue/milestone esterne: solo `create` e `update`. Mai pubblicare più di `kanban_publish.batch_limit` artefatti in un singolo run senza ulteriore gate (default `batch_limit: 10`). Token di autenticazione **solo da variabile d'ambiente** (mai committati nel repo; nome var dichiarato in `kanban_publish.auth_env`).
16. **Code review verdict `reject` = gate umano** (v2.12, §19). Mai auto-revert del codice, mai auto-close/auto-merge del TSK, mai riapertura automatica del Develop. Quando il Code Reviewer emette verdict `reject` (o `max_iterations` viene raggiunto senza convergenza), il TSK resta `status: done` ma con `review_status: rejected`: l'umano decide il next step (re-Develop manuale con istruzioni, accept-as-is con override documentato in `wiki/incidents/`, o rollback del codice). `code_quality.max_iterations` (default 3) è invariante non bypassabile a runtime. No-progress detection (due iterazioni con stesso set di `rule_id` violate) e regression detection (finding nuovi in file non toccati dalla fix) accelerano l'escalation **prima** di raggiungere il cap.
17. **Sync read-only verso la sorgente** (v2.9 generalizzata in v2.12). Nessun sub-agent Sync (§2 + §16) modifica MAI la propria fonte di estrazione: `sync-docs` non riscrive i PDF, `figma-sync` non muta il file Figma (solo lettura via MCP/REST), `repo-sync` **non aggiunge né modifica file nel repo scansionato** — in particolare mai aggiungere `factory.config.yaml`, adapter `.claude/`, o file infrastrutturali al repo esterno. L'output del Sync vive esclusivamente nel proprio scope di `raw/**` + `raw/.extraction-manifest.json` (§16). Una factory esistente che ingerisce sé stessa via `repo-sync` (modalità reflective) resta legittima: la regola distingue la *sorgente di scansione* dall'*output di scansione*.
18. **Compression layer mai sugli artefatti** (v2.14, §20). Se `compression.output.enabled: true` in `factory.config.yaml`, la compressione (Caveman) si applica **solo** ai canali di messaging agent-to-agent / agent-to-tool / tool-to-agent. **Mai** sugli artefatti scritti su filesystem (`wiki/**`, `management/kanban/**`, `<code_path>/**`, `design_&_architecture/**`, `code_quality/**`, `memory/**`), **mai** sull'output verso l'utente finale, **mai** sul flow di `propagate-resolution` (§3 — coerenza referenze cross-page). Questi invarianti (`to_user`, `to_artifact`, `propagate_resolution` → sempre `off`) non sono mai overridabili neppure in `policy_profile: custom`. Vedi §20.4 R.C1–R.C6 per il dettaglio.

**Nota EP-011 (v2.18)**: EP-011 (Temporal Awareness Layer) NON introduce una nuova invariante §7. Il conteggio rimane **18**. Le tre operazioni temporali (Context Injection, Handoff Block, State Tracking) sono capability opt-in trasversali (R.P3): a flag spento sono no-op e la factory si comporta identica a v2.17. Coerente con il pattern delle capability opt-in v2.17+ (Visual Oracle, A11y, UX/UI, Analytics non aggiungono invarianti §7). Vedi ADR-028 / ADR-029 / ADR-030 / ADR-031.

## §8 — State derivation (single source of truth)
<!-- profiles: full -->
Lo stato del progetto si deduce SOLO da:
- Filesystem (presenza/assenza di file e cartelle, **inclusa la presenza di agenti dev in `.claude/agents/`** che codifica la topologia).
- `wiki/log.md` (ultima entry per tipo di operazione).
- `memory/episodic/` (ultimo run rilevante).
- Data modifica file (`git log` o `stat`).
- `factory.config.yaml` (configurazione, non stato — vedi distinzione sotto).

**Vietato:** `project_manifest.json` o qualsiasi file di **stato** scritto a mano (si desincronizza).
**Vietato:** doppia source-of-truth (es. `sprint.md` *e* cartelle TSK — `sprint.md` è view generata).

**Qualificatore di scope**: §8 governa lo **stato di progetto** — *cosa è stato fatto*, proprietà
durevole e ricostruibile dal filesystem. Non governa lo **stato di coordinamento runtime** —
*chi sta lavorando su cosa adesso*, proprietà effimera, con TTL e senza valore storico
(es. i claim di `memory/active-sessions.yaml`, coordinamento runtime multi-utente). Un'autorità esterna sullo stato
effimero di coordinamento non costituisce doppia source-of-truth ai sensi di §8, purché non
diventi autorità sullo stato di progetto (`status:` dei TSK resta canonico nel filesystem).

**Distinzione config vs stato**: `factory.config.yaml` è **configurazione utente** (topology, code_path, routing, stack_mode) — cambia raramente, sotto controllo umano. Non descrive *cosa è stato fatto* (stato), descrive *come la factory è configurata* (config). Lo stato resta derivato dal filesystem + log.

## §9 — Memoria cross-conversazione
<!-- profiles: full -->
- **`memory/episodic/`** — record narrativo del run. Scritto dall'*Orchestrator*. Letto dai run successivi per continuità.
- **`memory/semantic/`** — fatti consolidati cross-progetto. Promossi da episodic dopo validazione umana.
- **`memory/procedural/`** — playbook riutilizzabili. Curati a mano.

Distinto da `wiki/log.md` (narrazione operativa) e da `wiki/incidents/` (post-mortem operativi).

## §10 — Wiki maintenance & feedback loop
<!-- profiles: full -->

`wiki/` è la **source of truth** del progetto. Per restare tale deve essere:

1. **Accessibile a tutti** (read-universal). Anche i dev-agent leggono concept/entity/synthesis per contesto, ma citano cascade (TSK/ADR, non concept direttamente).
2. **Manutenuta con disciplina stringente** (single-committer). Solo `wiki-keeper` committa contenuto. Eccezioni (`## Storie collegate` PM, `status:` `/promote`, `develop` entry su `wiki/log.md`) sono operazioni meccaniche.
3. **Aggiornabile via feedback loop**. Agenti L3+ (PM, Arch, TPM, **dev**) che scoprono un gap lo formalizzano in `wiki/gaps.md`.

### Wiki feedback loop (canale formale per gap discovery)

`wiki/gaps.md` è **append-only condiviso in scrittura** fra PM, Arch, TPM, dev-agent, wiki-query. Formato gap:

```markdown
## YYYY-MM-DD HH:MM — <slug-gap>
**Origine:** <agente> @ <artefatto in lavorazione>
**Gap:** <cosa manca in wiki/>
**Sospetta fonte:** <raw da ingerire | "nessuna fonte chiara, serve nuovo raw">
**Impatto:** <quale produzione è frenata>
```

Ciclo: **Apertura** (L3+ → append `wiki/gaps.md`), **Pickup** (`wiki-keeper` legge in Fase 0), **Chiusura** (`**Risolto:** YYYY-MM-DD — [[<pagina>]]` + append `wiki/log.md` + `propagate-resolution`).

### Eventi che innescano un aggiornamento wiki/

| Evento | Trigger | Chi | Cosa |
|---|---|---|---|
| Nuovo PDF in `raw/` | `/sync-docs` completato | `wiki-keeper` | Ingest L1→L2 |
| Nuovo Figma in `raw/` (v2.9) | `/figma-sync <url>` completato; nuovo `*.kb.json` nel manifest | `wiki-keeper` | Ingest L1→L2 (touch many small files: una pagina per screen/component/flow/feature significativi) |
| Re-ingest stesso raw | `wiki/log.md` segnala precedente ingest | `wiki-keeper` | Append `## Aggiornamenti (vYYYY-MM-DD)` |
| Gap segnalato | append a `wiki/gaps.md` da L3+ (incluso dev) | `wiki-keeper` | Ingest mirato o nuova synthesis |
| Storia creata che impatta concept | PM completa US | `product-manager` | Append `## Storie collegate` |
| Risposta candidata a synthesis | `wiki-query` produce risposta ri-askable | `wiki-keeper` | Promote `wiki/query/<file>.md` → `wiki/syntheses/` |
| Promozione status | `promote` | `orchestrator` | Modifica `status:` + `updated:` |
| Auto-promotion suggerita | concept page citata da ≥ 2 US committed/in-progress | `orchestrator` (suggerimento `/run`) | Mai auto-promote |
| Gap chiuso che cita `Q_NNN` | `wiki-keeper` chiude → `propagate-resolution` | `wiki-keeper` (append-only log) | Marker `reconcile-needed: US-XXX` |
| Develop completato | dev-agent chiude TSK → `dev-handoff` | `<layer>-dev` | Append `wiki/log.md`: `develop TSK-ZZZ → <commit-hash o path>` |
| Kanban pubblicato (v2.10) | `/kanban-publish run` completato | `<provider>-publisher` | Append `wiki/log.md`: `publish <provider> created=<N> updated=<M>`. Lista degli artefatti con nuovo `external_id` |
| Lint findings | `wiki-lint` segnala errori | umano (mai auto-fix) | Eventualmente invoca `wiki-keeper` |

### Invarianti di manutenzione

- **Append-only** su `wiki/log.md`, `wiki/gaps.md`, `wiki/incidents/`.
- **Non distruttivo** su pagine `review`/`approved`.
- **Touch many small files**: un ingest sano = 5–15 piccole pagine.
- **Flag, don't resolve**: contraddizioni → `## Contradictions`.
- **Citation chain integrity**: ogni claim L3+L4+L5 traccia fino a `raw/` via `wiki/`.

## §11 — Standards as constraints (tenant-driven)
<!-- profiles: full -->
Quando un raw cita uno standard normativo (SPID, OIDC, OAuth2, SAML, eIDAS, FHIR, GDPR, HL7, ISO/IEC, RFC numerati), il `lead-architect` deve trattarlo come **vincolo verbatim** e produrre un ADR che lo adotta esplicitamente. La skill `tech-scout`, in modalità `auto`, deve rispettare gli standard già fissati in `raw/tech_stack.md` e in `raw/**` (non li sostituisce, anche se il mercato 2026 offre alternative "migliori").

## Moduli — §12–§37

Le sezioni dalla §12 in poi vivono **solo** nei moduli e non sono duplicate qui. Un
riferimento `PATTERN §N` (o `PATTERN.md §N`) con N ≥ 12 si risolve nel modulo indicato: la
numerazione è unica su tutti i file. Caricare solo il modulo che serve all'operazione in
corso — mappa per comando e agente: `.claude/skills/references/dispatch-policy/manifesto-caricamento.md`.

| Sezioni | Contenuto | Modulo |
|---|---|---|
| §12–§17 | Adapter, Topology & routing, Tech stack modes, VCS, Sync adapters, Publisher adapters | [`PATTERN-integration.md`](PATTERN-integration.md) |
| §18–§20 | Parallel scheduling, Code Quality Review Layer, Output Compression Layer | [`PATTERN-runtime.md`](PATTERN-runtime.md) |
| §21–§23 | Versioning, Release Governance, Complexity Budget & Deprecations | [`PATTERN-governance.md`](PATTERN-governance.md) |
| §24–§37 | Capability opt-in (Design Intelligence … Session Observability) | [`PATTERN-capabilities.md`](PATTERN-capabilities.md) |

Nuove sezioni vanno nel modulo più affine per dominio, mai in questo file. Un lettore
meccanico che cerca una sezione legge l'indice **e** i moduli elencati in questa tabella.
