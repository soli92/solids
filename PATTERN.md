# PATTERN — Agentic Factory `llm-wiki++` v2.32

> Contratto universale agent-agnostic. Qualsiasi runtime (Claude Code, OpenAI Assistants,
> Cursor, Aider, Gemini, ChatGPT, …) che rispetti questo file può operare sul repo. Gli
> adapter di runtime vivono in cartelle dedicate (`.claude/`, `.cursor/`, `.aider/`, …) e
> implementano i ruoli §2. **Multi-adapter v2.13**: scaffolding parallelo di adapter
> multipli supportato; ogni adapter ha un manifest formale (§12.x).

## §0 — Identità & versione
<!-- profiles: minimal, standard, full -->
Pattern version: **2.27**.
Origine: llm-wiki (Karpathy) + estensione PM/Arch + memory tree cross-conversazione + adapter `thin agents, fat skills` + execution layer L5 + topology + stack modes + VCS integration + sync adapters multi-sorgente (PDF, Figma, **repo esistenti**, **knowledge graph**) + publisher adapters multi-target (GitHub, GitLab, Jira, Linear, …) + parallel scheduler basato su DAG di dipendenze frontmatter + code quality review layer post-Develop con ruleset evolutivo stack-aware + multi-adapter scaffolding parallelo via registry manifest (v2.13) + **compression layer a due assi opt-in (output via Caveman, context via Graphify), consolidato in v2.15 con gate empirici Fase 1.5/3a riformulati come opt-in deferred (eseguibili a discrezione del derivatore su factory candidata, non bloccanti per il consolidamento)** + **FE Visual Oracle Integration opt-in (v2.17): variante Develop FE «Visual Verification» via skill `visual-oracle-protocol` + comando `/visual-oracle` + State Matrix nel DoD FE + ordering develop→visual-oracle→review; tutto opt-in via `factory.config.yaml.fe_correctness`, niente nuova invariante §7** + **A11y + UX/UI Integration opt-in (v2.18, EP-007/EP-008): capability `a11y` (Accessibility Testing WCAG 2.2 AA via tool `run_a11y_scan` + skill `accessibility-testing-protocol`) e `ux_ui` (Review & Design via `ux-ui-review-protocol` + `ux-ui-design-protocol`), ordering develop→visual-oracle→ux-ui-review→code-review** + **Task Analytics opt-in (v2.18, EP-009/EP-010): operazioni canoniche autonome di misurazione (`/analytics`) e stima (`/estimate`) costi/tempi; tutto opt-in via `factory.config.yaml.{a11y,ux_ui,analytics}`, niente nuova invariante §7** + **Hardening & Sustainability (v2.19, EP-012..017): §22 Release Governance (battle-test forcing function — gate `/release` + skill `release-validation-gate`, nessun tag senza ≥N RUN-REPORT validi, ADR-032..037) + §23 Complexity Budget & Deprecations (regola N:1, profili di adozione) + EP-013 Analytics Dogfooding (il framework si auto-misura, hook SessionEnd) + ADR-062 (criterio "run esterno denso") + ADR-063 (anti-fabbricazione review visiva, fail-loud su evidenza mancante); §22/§23 governance meta non scaffoldate in factory derivate (ADR-033 §C), niente nuova invariante §7 (resta 18)** + **FE Functional Oracle opt-in (v2.20, EP-018): operazione opzionale «Functional Oracle» che *esercita* il flusso reale dell'app (serve → fixture → interazione Playwright → asserzioni domain-agnostic → verdict deterministico, critic LLM solo advisory) — complementare a Visual Oracle (osserva il render) e UX/UI Review (giudica l'aspetto); chiude il failure mode «renderizza ma non funziona». Skill `functional-oracle-protocol` + `interaction-drive-protocol` + comando `/functional-oracle` + schema `acceptance-spec` (framework possiede schema+engine, progetto possiede contenuto) + dominio scheduler `functional-oracle`; tutto opt-in via `factory.config.yaml.fe_correctness.functional_oracle`, niente nuova invariante §7 (resta 18), ADR-065/066/067** + **Design Intelligence Layer opt-in (v2.21, EP-019): coordinamento tematico centralizzato (art-director DSL) + separazione LLM/generatore deterministico + gate reasoning-first + Critic/Judge Design + Intention Economy; §24 nuovo; niente nuova invariante §7 (resta 18), ADR-068..071** + **Token Ledger opt-in (v2.21, EP-022): visibilità token reali inline dopo ogni risposta con tool use via hook Stop + script `show-session-tokens.py`; sotto-blocco `analytics.token_ledger:` in `factory.config.yaml`** + **Semantic Drift Detection (v2.23, EP-031, research sprint): piramide a tre livelli (L1 staleness Check 4ag always-on + L2 LLM-judge + L3 embedding coseno opt-in); §25 nuovo; config `wiki_lint.semantic_check:`; skill `semantic-drift-scan-protocol` + comando `/semantic-drift-scan` (trigger manuale); convenzione frontmatter `pattern_section:`; ADR-EP031-001 GO-MODIFIED; niente nuova invariante §7 (resta 18)** + **Runtime Contextual Suggestions (v2.24, EP-033): capability push-based che inietta suggerimenti contestuali nel momento giusto, senza richiedere input esplicito. Tre artefatti: (A) Fase 6 Capability Relevance Check in `orchestrator.md` (6 regole, al `/run`); (B) sezione `## Suggerimento post-esecuzione` in `dev-handoff` (per-layer fe/be/db/qa/docs); (C) script `suggest-next.py` + hook Stop per copertura bypass `/run` (opt-in). Nessuna nuova invariante §7 (resta 18)** + **VCS Branch Awareness Layer opt-in (v2.25, EP-034): rende preciso e visibile «su quale branch sto / su quale devo stare» nei progetti multi-repo/submodule (problema dei due HEAD). Ciclo declare→inspect→align: skill `branch-resolver` (expected branch, single source of truth) + `vcs-preflight-protocol` (snapshot read-only) + comando `/vcs-status` + tabella dashboard `/run` + gate pre-dispatch `dev-protocol` Fase 0 + drift check in `vcs-handoff`; config `vcs.branch_awareness` (default off); invarianti locali §15 R.B7-R.B10; nessuna nuova invariante §7 (resta 18), ADR-EP034-001 GO** + **Prototype Generation Layer opt-in (v2.26, EP-035): cascata adattiva figma→penpot→react→html con fallback terminale html garantito (INV-1); skill `backend-resolver` + `prototype-generation-protocol` + `html-prototype-mapping` + `react-mapping`; agente `prototype-generator`; comandi `/prototype` + `/prototype-status`; config `prototyping:` (default off, R.P3); §27; INV-1..INV-6 locali; ADR-EP035-001..006 GO; backward compat totale v2.25** + **Tavola Rotonda opt-in (v2.27, EP-039): modalita' multi-agente collaborativa per problemi genuinamente complessi e multi-dominio; agente dedicato `tavola-rotonda-moderatore`; blackboard strutturato in `wiki/decisions/`; skill `tavola-rotonda-protocol` (5 fasi: Setup→Posizioni→Confronto→Convergenza→Sintesi); Critico con mandato anti-compiacenza; invarianti R.TR1-R.TR4 non overridabili; comando `/tavola-rotonda`; config `tavola_rotonda:` (default off); §28; ADR-EP039-001 GO; backward compat totale v2.26; benchmark self-consistency verdict `pass` (TSK-294)**.
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

**Operazioni canoniche analytics di misurazione (v2.18, opt-in EP-009)**. Cinque operazioni autonome, **tutte opt-in** via `factory.config.yaml.analytics.measurement.enabled: true` (default `false`, R.P3). A flag spento nessuna è invocata e la factory si comporta identica a v2.17. Non sono sub-step di `Develop` (a differenza di *Visual Verification*): sono operazioni canoniche autonome, invocate on-demand o periodicamente (es. cron settimanale `/analytics --sprint=current`). I tool sono script Bash/TS deterministici in `.claude/tools/analytics/*` (no MCP, coerente con ADR-008/ADR-014); le formule vivono nei tool, l'orchestrazione nella skill `cost-and-time-analytics` (thin-agent-fat-skill). Le invarianti elencate sono **invarianti operative della capability** (parallele alla regola di neutralità di EP-007), **non** invarianti di sistema §7.
- **Task Analytics — Event Recording** = instrumentazione: registra un evento di task (started/finished/blocked) nell'event store `analytics/events/<YYYY-MM>.jsonl` (default JSONL append-only; SQLite opt-in — ADR-021). Tool `record_task_event` (`.claude/tools/analytics/record-event.{sh,ts}`, US-033). Schema logico evento (11 campi, verbatim ADR-021 §E): `task_id`, `project_id`, `parent_id`, `actor_type` (`agent|human`), `actor_id`, `task_type`, `state` (`started|finished|blocked`), `ts` (ISO 8601 UTC), `tokens` (`input/output/cache_read/cache_write`), `model` (`<<model_id>>` canonical, ADR-022), `tool_calls[]`. **Single-writer** logico: tutti gli emittenti (orchestrator hook, skill, dev-agent) invocano il tool, mai scrivono il file direttamente. **Invariante**: prezzi/tariffe mai hardcodati nell'evento (il pricing è risolto a valle dal costo, ADR-022). Vedi ADR-021 §E.
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
- **Temporal Context Injection** = arricchimento del system prompt di ogni sub-agent con un blocco strutturato di contesto temporale (v2.18, EP-011, opt-in: `temporal.context_injection.enabled`). L'Orchestrator inietta: (a) un `session_id` (UUID-v4) generato al boot della sessione; (b) il `task_started_at` (UTC ISO-8601) al kickoff di ogni TSK; (c) un blocco YAML `TEMPORAL CONTEXT` con `current_utc`, `session_id`, `task_started_at`, `elapsed_ms` (wall-clock) calcolato via `.claude/tools/temporal/build-temporal-context.sh`. **Single-writer**: solo l'Orchestrator inietta questo blocco. A flag spento i sub-agent non ricevono il blocco (comportamento v2.17). Vedi ADR-030 §A.
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
  - `show-session-tokens.py` (`.claude/tools/analytics/`) legge il transcript JSONL della
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
  `show-session-tokens.py` (`.claude/tools/analytics/`), CLAUDE.md §Token Ledger (EP-022).

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

## §12 — Adapter (runtime-specific)
<!-- profiles: full -->

Ogni adapter implementa i ruoli §2 con i costrutti del proprio runtime. **In v2.13** il
contratto è formalizzato con un **manifest** per ciascun adapter (vedi §12.1) che
abilita lo scaffolding multi-adapter parallelo al bootstrap.

### §12.0 — Adapter registry

Il **registry degli adapter** vive in `adapters/<name>/` al root del repo
meta-framework. Ogni sub-folder contiene il manifest + i template + un README. La
factory generata può ospitare uno o più adapter (es. `.claude/` e `.cursor/`
coesistenti) — la scelta è fatta al bootstrap o aggiunta a runtime.

Adapter attualmente disponibili (v2.13):

| Adapter | Folder runtime | Stato | Registry path |
|---|---|---|---|
| Claude Code | `.claude/` | reference completo (default) | `adapters/claude/` (manifest only; il `.claude/` reale del meta-framework è la fonte) |
| Cursor | `.cursor/` | full v2.13 | `adapters/cursor/` (template + manifest) |
| Aider | `.aider/` | full v2.13 | `adapters/aider/` (template + manifest) |
| OpenAI Assistants | `.openai/` | partial v2.13 (manifest + setup.py stub) | `adapters/openai/` |
| Gemini Code Assist | `.gemini/` | manifest-only v2.13 | `adapters/gemini/` |
| ChatGPT (Custom GPT / file tools) | `.chatgpt/` | manifest-only v2.13 | `adapters/chatgpt/` |

**Più adapter possono coesistere** nella stessa factory: condividono `raw/`, `wiki/`,
`management/`, `design_&_architecture/`, `memory/`, `code_quality/`,
`factory.config.yaml`, e `<code_path(s)>/`. Ogni adapter agisce sullo stesso state
filesystem; non c'è duplicazione di dati o operazioni.

### §12.1 — Manifest format

Ogni `adapters/<name>/manifest.yaml` dichiara:

```yaml
adapter_name: cursor                  # slug
adapter_folder: .cursor               # cartella in cui scaffoldare nella factory generata
runtime: cursor                       # nome runtime descrittivo
runtime_version_min: "0.45"           # versione minima del runtime supportata
maturity: full | partial | manifest-only  # stato del manifest
contract_version: 2.13                # versione PATTERN supportata

# Mapping dei costrutti runtime
mappings:
  agent:
    pattern_concept: "Agente specializzato (PATTERN §2 ruoli)"
    runtime_construct: "Cursor rules file con frontmatter `description` + `globs`"
    file_path_template: ".cursor/rules/{name}.mdc"
  skill:
    pattern_concept: "Procedura riusabile (PATTERN v2.3 'fat skills')"
    runtime_construct: "Cursor rules file in .cursor/rules/skills/"
    file_path_template: ".cursor/rules/skills/{name}.mdc"
  command:
    pattern_concept: "Slash command per invocazione esplicita"
    runtime_construct: "Cursor custom command"
    file_path_template: ".cursor/commands/{name}.md"
  tool_read:
    pattern_concept: "Lettura file"
    runtime_construct: "@<file>"
  tool_write:
    pattern_concept: "Scrittura file"
    runtime_construct: "Edit/Apply (Cursor built-in)"
  # ... altri mappings

# Lista template scaffoldabili
templates:
  agents:
    - { name: orchestrator, required: true,  path: .cursor/rules/orchestrator.mdc }
    - { name: wiki-keeper,  required: true,  path: .cursor/rules/wiki-keeper.mdc }
    - { name: be-dev,       required: false, path: .cursor/rules/be-dev.mdc, condition: "routing.be == agent" }
    # ...
  skills:
    - { name: ingest-protocol, required: true, path: .cursor/rules/skills/ingest-protocol.mdc }
    # ...
  commands:
    - { name: run,  required: true,  path: .cursor/commands/run.md }
    - { name: lint, required: true,  path: .cursor/commands/lint.md }
    - { name: dev,  required: false, path: .cursor/commands/dev.md, condition: "has_dev_agents" }
    # ...

# Skill che cambiano comportamento per questo runtime
runtime_overrides:
  parallel_dispatch:
    supported: false           # Cursor non ha multi-tool-call concept
    fallback: "sequential dispatch with manual confirmation"
  subagent_fanout:
    supported: false
    fallback: "manual user invocation of separate agents"

# Note operative
notes: |
  Cursor (≥0.45) supporta `.cursor/rules/*.mdc` con frontmatter `description` +
  `globs`. Adatta gli agenti del PATTERN come rules con `description` che spiega
  quando attivare la rule. I sub-agent (Agent tool di Claude Code) non hanno
  equivalente diretto in Cursor; emulati come "rules condizionali" che l'utente
  invoca manualmente con @.
```

### §12.2 — Multi-adapter coexistence (R.A1-R.A6)

Invarianti per la coesistenza di adapter multipli nella stessa factory:

- **R.A1 — Isolamento di cartella**: ogni adapter scrive **solo** nel proprio
  `adapter_folder` (es. `.claude/` per Claude Code, `.cursor/` per Cursor). Mai
  scritture cross-adapter (es. `.cursor/` rules che modificano `.claude/agents/`).
- **R.A2 — State filesystem condiviso**: tutti gli adapter leggono e scrivono lo
  stesso `wiki/`, `management/`, `raw/`, `memory/`, ecc. (i layer L1-L4 + memoria +
  code_quality side-channel). Le operazioni canoniche §3 hanno la stessa semantica
  per ogni adapter — cambia solo il *costrutto* di invocazione.
- **R.A3 — Single-committer preservato**: la regola §7 r.12 (wiki/ single-committer)
  vale globalmente, non per-adapter. Solo wiki-keeper (in qualunque adapter) scrive
  `wiki/`. Se l'utente invoca `wiki-keeper` da `.claude/` E da `.cursor/`
  contemporaneamente, è responsabilità sua serializzare.
- **R.A4 — Manifest immutabile a runtime**: il manifest di un adapter cambia solo
  via release PATTERN nuove. La factory generata non modifica il manifest.
- **R.A5 — Adapter aggiungibile a runtime**: l'utente può aggiungere un adapter
  dopo il bootstrap eseguendo `bootstrap-multiadapter-protocol` standalone (con il
  manifest target) — senza ri-scaffoldare l'intera factory.
- **R.A6 — Agent-agnostic preservato**: PATTERN.md, `factory.config.yaml`, e i
  layer L1-L5 NON contengono mai riferimenti a tool/costrutti specifici di un
  runtime. Tutto ciò che è runtime-specific vive negli adapter. Questo è
  l'invariante che rende il pattern truly portable.

### §12.3 — Configurazione adapter in `factory.config.yaml`

Nuovo blocco `adapters:` (v2.13) per dichiarare gli adapter installati:

```yaml
adapters:
  - name: claude       # adapter attivo (deve corrispondere a una cartella `<adapter_folder>`)
    folder: .claude
    maturity: full
  - name: cursor       # opzionale, secondo adapter
    folder: .cursor
    maturity: full
  # ...
```

In single-adapter (caso comune), una sola entry. In multi-adapter, N entry.
Backward compat: se `adapters:` è assente, la factory assume `[{name: claude, folder: .claude, maturity: full}]` (compatibile con v2.12 e precedenti).

### §12.4 — Principio di taglio adapter (v2.3 + multi-adapter v2.13)

- Gli **agenti** sono identità contrattuali (mappabili a sub-agent / rules / Assistants / role-prompts del runtime).
- Le **skill** sono procedure ricorrenti (mappabili a file markdown / rules / function tools / prompts).
- Una stessa procedura non è duplicata fra adapter — è scritta una volta come **contratto** in `<adapter>/skills/<name>.md` e implementata nel costrutto del runtime.
- Le **regole inviolabili §7** sono invariabili per tutti gli adapter (cambia il costrutto, non il contratto).

**Dev-agent opzionali (v2.7)**: i quattro dev-agent (`be-dev`, `fe-dev`, `db-dev`, `qa-dev`) esistono solo se la topologia li include. Bootstrap installa solo quelli necessari, **in ogni adapter installato**. A runtime, aggiungere/rimuovere il file agente cambia la topologia.

## §13 — Topology & consumer routing (nuovo in v2.7)
<!-- profiles: minimal, standard, full -->

### Topologie supportate

La topologia è codificata dalla **presenza dei file agente** in `.claude/agents/` (o equivalente per altri adapter) + dal blocco `topology:` in `factory.config.yaml`.

| Topologia | Dev-agent presenti | Caso d'uso |
|---|---|---|
| `knowledge-only` | nessuno | Knowledge factory pura (Sync→Analyst), no planning, no execution |
| `plan-only` | nessuno | Default storico v2.6: arriva fino a TSK, consumer umano |
| `full-stack-agents` | `be-dev`, `fe-dev`, `db-dev`, `qa-dev` | Tutto agentico end-to-end |
| `hybrid-be-agents` | `be-dev`, `db-dev` | BE/DB agentici, FE/QA umani |
| `hybrid-fe-agents` | `fe-dev` | FE agentico, BE/DB/QA umani |
| `custom` | sottoinsieme arbitrario | Mix esplicito (es. solo `qa-dev` per autotest) |

### `factory.config.yaml` (schema, v2.8 + v2.12 multi-repo)

```yaml
# Configurazione factory — versione PATTERN e topologia
pattern_version: "2.12"
topology: full-stack-agents  # vedi tabella sopra

# === Code paths (L5) — v2.12 multi-repo ===========================================
# Lista di repository / path target. Ogni entry rappresenta uno scope di scrittura
# distinto (FE+BE disaccoppiati, microservizi, micro-frontend, monorepo con
# pacchetti multipli, …). Il TSK punta a un'entry via `target:` (§5).
#
# Per setup single-repo (default storico), una sola entry è sufficiente.
code_paths:
  - name: default                   # univoco; usato come `target:` nel TSK
    path: ./src/                    # relativo al repo factory o assoluto
    layers: [be, fe, db, qa, infra] # quali layer di TSK puntano qui (1+ valori)
    tags: []                        # opzionale: descrittivi (monolith, microservice, mfe, ...)
    vcs:
      mode: monorepo                # monorepo | submodule | sibling | external | none
      submodule_path: ""            # solo se mode=submodule
      remote_url: ""                # opzionale; documentazione e bootstrap
      branch_strategy: shared       # shared | per-tsk | per-sprint
      commit_coupling: float        # pin | float

# === Backward compatibility (v2.7-v2.11) ==========================================
# Se `code_path:` (singolare) è valorizzato e `code_paths:` è vuoto/assente, viene
# auto-promosso a `code_paths: [{name: default, path: <code_path>, layers: <tutti>,
# vcs: <blocco vcs top-level>}]`. Il blocco `vcs:` top-level (v2.8) resta valido
# solo in questo caso legacy; in multi-repo v2.12 il `vcs:` vive dentro a ciascuna
# entry di `code_paths`.
code_path: ""
vcs:
  mode: none
# ===================================================================================

# Modalità di scelta dello stack tecnologico
stack_mode: guided  # manual | guided | auto

# Routing TSK → consumer (default per layer; override per-TSK via frontmatter)
routing:
  be: agent      # agent | human
  fe: agent
  db: agent
  qa: agent
  infra: human

# Stack (in multi-repo, può essere per-entry — vedi §13.x)
stack:
  backend: <es. FastAPI 0.115 + Python 3.13>
  frontend: <es. React 19 + Vite>
  database: <es. PostgreSQL 17>
  qa: <es. Pytest + Playwright>
```

### Esempi multi-repo (v2.12)

**a) FE + BE disaccoppiati (2 repo)**:

```yaml
code_paths:
  - name: backend-api
    path: /Users/me/repos/portal-api/
    layers: [be, db, qa]
    tags: [monolith]
    vcs: { mode: sibling, remote_url: "git@github.com:org/portal-api.git" }
  - name: frontend-web
    path: /Users/me/repos/portal-web/
    layers: [fe]
    tags: [react, spa]
    vcs: { mode: sibling, remote_url: "git@github.com:org/portal-web.git" }
```

I TSK con `layer: be` finiscono in `backend-api` (auto-derivato, `target:` opzionale —
una sola entry copre `be`). Idem per `fe`. Layer `qa` ambiguo? Solo `backend-api` lo
copre → ancora auto-derivabile. Aggiungi `qa` a `frontend-web.layers` se vuoi e2e su
entrambi → allora `target:` diventa **richiesto** per i TSK QA.

**b) Microservizi (N BE + 1 FE)**:

```yaml
code_paths:
  - name: service-auth
    path: /Users/me/repos/auth-service/
    layers: [be]
    tags: [microservice, oidc]
    vcs: { mode: sibling, remote_url: "git@github.com:org/auth-service.git" }
  - name: service-payments
    path: /Users/me/repos/payments-service/
    layers: [be]
    tags: [microservice, stripe]
    vcs: { mode: sibling, remote_url: "git@github.com:org/payments-service.git" }
  - name: service-orders
    path: /Users/me/repos/orders-service/
    layers: [be]
    tags: [microservice]
    vcs: { mode: sibling }
  - name: web-app
    path: /Users/me/repos/web-app/
    layers: [fe, qa]
    tags: [next-js]
    vcs: { mode: sibling }
```

Tutti i microservizi hanno `layers: [be]`: il TSK BE **deve** dichiarare `target:` per
disambiguare (es. `target: service-auth`). Il TPM, quando produce TSK, decide il target
in base alla US/EP (es. una US "OAuth flow" → TSK BE su `service-auth`).

**c) Micro-frontend (N FE + 1 BE shared)**:

```yaml
code_paths:
  - name: api-gateway
    path: /Users/me/repos/api-gateway/
    layers: [be, db]
    vcs: { mode: sibling }
  - name: mfe-shell
    path: /Users/me/repos/mfe-shell/
    layers: [fe]
    tags: [module-federation, host]
    vcs: { mode: sibling }
  - name: mfe-checkout
    path: /Users/me/repos/mfe-checkout/
    layers: [fe]
    tags: [module-federation, remote]
    vcs: { mode: sibling }
  - name: mfe-catalog
    path: /Users/me/repos/mfe-catalog/
    layers: [fe]
    tags: [module-federation, remote]
    vcs: { mode: sibling }
```

Analogo (b) per i `fe`. Si possono mescolare coupling diversi: alcuni `sibling`, alcuni
`submodule`, alcuni `monorepo` (se uno dei repo ospita anche la factory). Ogni entry è
indipendente.

**d) Monorepo logico con pacchetti separati** (1 repo fisico, target distinti per
clarity di routing):

```yaml
code_paths:
  - name: api
    path: ./apps/api/
    layers: [be, db, qa]
    vcs: { mode: monorepo }
  - name: web
    path: ./apps/web/
    layers: [fe]
    vcs: { mode: monorepo }
  - name: shared
    path: ./packages/shared/
    layers: [be, fe]
    tags: [shared-lib]
    vcs: { mode: monorepo }
```

Tutto nello stesso commit chain. Il valore aggiunto è chiarezza di routing + scheduler
conflict detection più granulare (TSK su `api` non conflitta con TSK su `web`).

### Regole di routing

1. **TPM legge `factory.config.yaml`** e per ogni TSK applica `consumer: <routing[layer]>` come default. Override esplicito a livello TSK è ammesso (utile per task una-tantum).
2. **Override runtime**: il comando `/dev <TSK-id>` forza un dev-agent su un TSK con `consumer: human` (non modifica il file; è un'invocazione one-shot).
3. **Cambio topologia a runtime**: aggiungi/rimuovi il file agente in `.claude/agents/` (o equivalente). Aggiorna `topology:` e `routing:` in `factory.config.yaml` per coerenza. TPM userà la nuova config al prossimo run.
4. **Coerenza obbligatoria**: se `routing.be: agent` ma `be-dev.md` non esiste, è errore di config (segnalato da *Lint*). In multi-repo (v2.12): se `routing.<layer>: agent` ma nessuna entry in `code_paths` dichiara `<layer>` in `layers`, è errore di config (segnalato da Check 4c del lint).
5. **Target resolution (v2.12 multi-repo)**: il TPM, quando produce un TSK con `consumer: agent`, valorizza `target:` se l'ambiguità lo richiede (≥ 2 entry in `code_paths` con `<layer>` in `layers`). Algoritmo (vedi §5 `target` paragraph):
   - 0 match per layer → ERROR di config (Check 4c lint).
   - 1 match → `target:` opzionale, dev-agent risolve via auto-derive.
   - ≥ 2 match → `target:` **obbligatorio** sul TSK; assenza segnalata dal lint Check 4j (drift target/code_paths).
6. **Mai mescolare `code_path:` (legacy) e `code_paths:` (v2.12)**: scegliere una forma. In presenza di entrambi, `code_paths` prevale e `code_path` legacy viene ignorato con warning lint.

### Esempio: progetto BE agentico + FE umano (single-repo, legacy v2.11-)

```yaml
topology: hybrid-be-agents
code_path: /Users/me/Repos/customer-portal/   # legacy singolare
stack_mode: guided
routing:
  be: agent
  db: agent
  fe: human   # gli sviluppatori React lavorano in IDE
  qa: human
stack:
  backend: FastAPI 0.115
  frontend: React 19 (umano)
  database: PostgreSQL 17
```

In questo setup, `.claude/agents/` contiene `be-dev.md` e `db-dev.md`; `fe-dev.md` e `qa-dev.md` non esistono. I TSK con `layer: fe` o `layer: qa` finiscono in TODO board per umani; quelli con `layer: be|db` sono raccolti dai dev-agent (via `/run` → suggerimento).

### Esempio: BE agentico + FE umano (multi-repo, v2.12 forma esplicita)

Stessa topologia logica, ma il BE e il FE vivono in repo distinti:

```yaml
topology: hybrid-be-agents
code_paths:
  - name: portal-api
    path: /Users/me/repos/portal-api/
    layers: [be, db]
    vcs: { mode: sibling, remote_url: "git@github.com:org/portal-api.git" }
  - name: portal-web
    path: /Users/me/repos/portal-web/
    layers: [fe, qa]    # umani lavorano qui in IDE, factory non genera codice qui
    vcs: { mode: sibling, remote_url: "git@github.com:org/portal-web.git" }
stack_mode: guided
routing:
  be: agent      # dev-agent genera codice in portal-api
  db: agent      # idem
  fe: human      # umani in portal-web
  qa: human      # idem
```

Notare: portal-web ha `layers: [fe, qa]` ma `routing.fe: human` → i dev-agent non
vengono mai invocati su portal-web; serve a documentare nella config che quel repo
contiene FE+QA umani (utile per `repo-sync`, `code-quality-review-layer`, e per il
lint Check 4c che verifica la coerenza routing↔layers).

## §14 — Tech stack modes (nuovo in v2.7)
<!-- profiles: full -->

Tre modalità (campo `stack_mode` in `factory.config.yaml`):

### `manual` (v2.6 default)
L'utente scrive `raw/tech_stack.md` a mano prima di invocare *Arch*. Nessuna automazione.

### `guided`
Bootstrap mostra opzioni curate per ciascun layer (es. backend: FastAPI / Express / Spring Boot; database: PostgreSQL / MongoDB / SQLite) con pro/contro brevi citati. L'utente sceglie; bootstrap scrive `raw/tech_stack.md` riempito.

### `auto`
La skill `tech-scout` (invocabile da *Arch* o on-demand) legge `wiki/` (requisiti business + vincoli normativi) e usa fonti web datate (2026) per proporre uno stack ottimo (scalabilità, stabilità, supporto LTS). Output: `raw/tech_stack.md.proposal` con citazioni `[^web: <url> §<sezione>] (accessed YYYY-MM-DD)`. Gate umano obbligatorio per promuovere `.proposal` → `raw/tech_stack.md`.

**Invariante**: tech-scout NON sostituisce mai uno standard normativo già fissato in `raw/**` (§11). Se il wiki cita SPID/OIDC/FHIR, la proposta li adotta verbatim.

## §15 — VCS integration (v2.8, esteso multi-repo in v2.12)
<!-- profiles: full -->

La relazione fra il factory repo e il codice prodotto (L5) è dichiarata
esplicitamente in `factory.config.yaml.vcs.mode` per single-repo legacy, oppure in
`factory.config.yaml.code_paths[i].vcs.mode` per multi-repo v2.12 (una relazione VCS
**per entry**). La skill `vcs-handoff` applica una procedura diversa per ciascun mode;
gate umano sempre obbligatorio per operazioni distruttive o cross-repo (§7 r.14).

**Multi-repo (v2.12)**: ciascuna entry di `code_paths` ha il proprio blocco `vcs:`. Le
entry possono avere mode diversi (es. `backend-api: sibling`, `db: submodule`,
`shared-lib: monorepo`). `vcs-handoff` opera **per-target**: legge il `target:` del
TSK, risolve l'entry, applica la procedura del relativo `vcs.mode`. Mai operazioni
cross-entry coordinate (ogni commit chain è indipendente).

In single-repo legacy (`code_path:` singolare valorizzato, `vcs:` top-level), la skill
opera come v2.8-v2.11. Backward compat preservata.

### Modi VCS

Validi per **ciascuna entry** di `code_paths` (v2.12) o per il `vcs:` top-level (legacy single-repo):

| Mode | Significato | Quando |
|---|---|---|
| `none` | Nessun L5 per questa entry — la factory non gestisce codice qui | Solo legacy single-repo con `code_path: ""` (in multi-repo, se l'entry esiste deve avere un mode reale; rimuovere l'entry se non serve) |
| `monorepo` | L5 dentro al factory repo, un solo commit chain | `path` relativo al repo factory (es. `./src/`, `./apps/api/`) |
| `submodule` | L5 come git submodule dentro al factory repo | `path` relativo + `vcs.submodule_path` valorizzato + entry in `.gitmodules` |
| `sibling` | L5 in un working tree separato (altro clone) | `path` assoluto (o relativo fuori dal repo) + `vcs.remote_url` opzionale per documentazione |
| `external` | Path opaco, factory non ne conosce la topologia VCS | `path` qualsiasi, factory si limita a leggere/scrivere senza coordinare git |

**Mix di mode in multi-repo (v2.12)**: legittimo e comune. Esempio: una factory in
nuovo repo che ospita `db-migrations` come submodulo, legge `frontend-web` e
`backend-api` come sibling (clone separati di repo esistenti), e ha un `shared-lib`
embedded in monorepo:

```yaml
code_paths:
  - { name: db-migrations, path: ./db/, layers: [db], vcs: { mode: submodule, submodule_path: ./db/, remote_url: "..." } }
  - { name: frontend-web, path: /Users/me/repos/web/, layers: [fe], vcs: { mode: sibling } }
  - { name: backend-api, path: /Users/me/repos/api/, layers: [be], vcs: { mode: sibling } }
  - { name: shared-lib, path: ./packages/shared/, layers: [be, fe], vcs: { mode: monorepo } }
```

### Procedura `vcs-handoff` (per mode)

Invocata dal `dev-protocol` Fase 5, dopo `dev-handoff` (entry log) e prima
del return finale al chiamante.

**`monorepo`**: `git status` nel factory repo; se ci sono modifiche in `code_path`, propone un messaggio di commit con riferimento al TSK; gate umano → commit. Nessuna operazione cross-repo.

**`submodule`**:
1. `cd <submodule_path> && git status` → mostra i cambiamenti.
2. Propone messaggio di commit nel submodule + branch (vedi `branch_strategy` sotto).
3. **Gate umano** → conferma commit nel submodule (e push opzionale).
4. `cd <factory> && git add <submodule_path>` → stagea il bump del ref.
5. Propone commit nel factory repo: `chore(<layer>): bump <submodule_path> for TSK-ZZZ`.
6. **Gate umano** → conferma commit factory.
7. Se `commit_coupling: pin` → aggiorna `.factory-lock` (vedi sotto).

**`sibling`**:
1. `cd <code_path> && git status` → mostra i cambiamenti.
2. Propone messaggio di commit + branch nel repo sibling.
3. **Gate umano** → conferma commit (e push opzionale, mai automatico).
4. Append a `wiki/log.md`: `develop TSK-ZZZ → <commit-hash> @ <code_path>` con avviso "ricorda di mergeare il PR su <remote_url>".
5. Se `commit_coupling: pin` → aggiorna `.factory-lock`.

**`external`**:
1. Nessuna operazione VCS (la factory non sa cosa c'è in `code_path`).
2. Solo append a `wiki/log.md` con il path e — se git-tracciato — il commit hash. Best-effort.

### `branch_strategy`

Solo per `submodule` e `sibling`:
- `shared` (default) — tutti i `develop` commit sul branch corrente (di solito `main`/`dev`).
- `per-tsk` — un branch per TSK (`tsk-<id>-<slug>`). La skill propone il `git checkout -b` al primo commit del TSK.
- `per-sprint` — un branch per sprint (`sprint-<NN>`). Letto da `factory.config.yaml` o dal frontmatter `sprint:` del TSK.

### `commit_coupling`

- `float` (default) — solo log entry su `wiki/log.md`, nessun file di lock. Più semplice, accetta drift.
- `pin` — la skill mantiene `.factory-lock` al root: un file YAML che mappa ogni `develop` chiuso al commit hash del codice. Garantisce reproducibilità (`git checkout <factory-commit>` → so esattamente quale commit di L5 corrispondeva).

`.factory-lock` (formato):
```yaml
# .factory-lock — generato da vcs-handoff, append-only
- tsk: TSK-042
  layer: be
  vcs_mode: submodule
  submodule_path: ./code/
  commit: a1b2c3d4
  date: 2026-05-20T14:32:00Z
```

### Vincoli inviolabili (estensione §7 r.14)

- **Mai `git push`** senza gate umano esplicito. La skill propone, l'umano esegue.
- **Mai `git submodule add|update --remote`** senza gate umano. Al bootstrap, la skill stampa il comando da eseguire, ma non lo lancia.
- **Mai `git clone`** automatico al bootstrap per `sibling`: stampa istruzioni, l'umano cloni.
- **Mai `--force` / `--no-verify`** in nessun caso.
- **Mai modificare `.gitmodules`** o `.factory-lock` fuori da `vcs-handoff`.

### Branch Awareness Layer (v2.25, EP-034, opt-in)

Fino a v2.24 la relazione VCS era gestita **solo a commit-time** (`vcs-handoff`, Fase 5 di
`dev-protocol`) e **solo in reazione** (STOP se HEAD detached). La responsabilità di trovarsi
sul branch giusto *prima* di invocare un dev-agent era interamente umana e **non verificata
programmaticamente** (*«l'utente decide su quale branch si trova prima di invocare il
dev-agent»*). Con i submodule questo genera disorientamento sistematico, non per indisciplina
ma per la struttura stessa dei submodule.

**Perché i submodule confondono — il problema dei due (o N) HEAD.**
1. Il parent repo registra un **commit fissato** (gitlink), non un branch. `git submodule update`
   fa checkout di *quel commit* → **detached HEAD by default**. È la prima causa del «su quale
   branch sto?».
2. Il branch del submodule è **indipendente** da quello del parent: «quale branch» non ha una
   risposta unica — c'è quello del parent *e* quello di ogni submodule, e driftano.
3. Il parent può puntare al commit X mentre il submodule è sul branch Y al commit Z (**drift
   parent-ref vs submodule-HEAD**, trappola silenziosa).

Il Branch Awareness Layer colma il gap con tre momenti — **declare → inspect → align** —
tutti **opt-in** (default off, backward compat totale R.P3, nessuna nuova invariante §7).

#### 1. Declare — il branch atteso è un valore calcolabile

`branch_strategy` (`shared` | `per-tsk` | `per-sprint`) resta la fonte, ma la sua risoluzione
in **«expected branch»** viene promossa a **resolver condiviso** (`branch-resolver`) usato sia
dal preflight (inspect) sia da `vcs-handoff` (commit), così non esistono due logiche divergenti.
Due aggiunte opzionali:

- `base_branch` (per entry) — il branch di integrazione (es. `develop`, `main`) che disambigua
  `shared` e fissa il fork-point per `per-tsk`/`per-sprint`.
- `.factory-branches.yaml` (per-sprint) — manifest opzionale al root: source of truth «quale
  branch atteso per ogni target nello sprint corrente». Se assente, il branch atteso è derivato
  puramente da `branch_strategy`.

**Regola di risoluzione `branch-resolver`** (deterministica):

| `branch_strategy` | expected branch |
|---|---|
| `shared` | `base_branch` se valorizzato, altrimenti il branch corrente (mai detached) |
| `per-tsk` | `tsk-<id-lowercase>-<slug-from-title>` |
| `per-sprint` | `sprint-<NN>` (da frontmatter `sprint:` del TSK) |

Override esplicito: una entry in `.factory-branches.yaml` per quel `target` vince sulla regola.

#### 2. Inspect — snapshot read-only `/vcs-status`

Comando + skill `vcs-preflight-protocol` che, per ogni entry `code_paths` (e per ogni
submodule), producono una tabella **read-only** (mai muta lo stato):

| target | mode | branch corrente | branch atteso | HEAD | drift parent-ref | verdict |
|---|---|---|---|---|---|---|
| backend-api | submodule | *(detached @a1b2)* | `tsk-042` | ⚠ detached | ✗ parent@a1b2 ≠ sub@c3d4 | **ACTION** |
| frontend-web | sibling | `develop` | `develop` | ✓ | — | OK |

Per ogni riga con verdict `ACTION` stampa **il comando esatto di remediation** (il `git checkout`
o `git submodule update --init` da lanciare a mano). Integrato nel dashboard di `/run`
(orchestrator) quando `branch_awareness.preflight: true`: la tabella appare prima del wave
dispatch, così lo stato branch è visibile *prima* di eseguire.

Controlli specifici submodule:
- **detached HEAD** → elenca i branch locali che contengono il commit registrato dal parent e
  suggerisce il checkout corretto (invece di un generico STOP).
- **submodule non inizializzato** (`.git` assente sotto `submodule_path`) → prerequisito hard:
  stampa `git submodule update --init <path>` (mai automatico).
- **drift parent-ref vs submodule-HEAD** → segnala che il commit puntato dal parent diverge dal
  commit checked-out nel submodule.

#### 3. Align — gate pre-dispatch in `dev-protocol` Fase 0

Prima che il dev-agent scriva, se `branch_awareness.dispatch_gate` ≠ `off`, si confronta lo
stato VCS del target risolto con l'expected branch (via `branch-resolver`):

- `dispatch_gate: block` → mismatch = **STOP** con il comando esatto di remediation.
- `dispatch_gate: warn` → mismatch = WARNING inline, procede (l'umano decide).
- `dispatch_gate: off` (default) → comportamento identico a v2.24.
- `auto_align: propose` (default `off`) → in caso di mismatch **propone** il `git checkout`
  sotto gate umano; non lo esegue mai in autonomia. `auto_align: off` si limita a STOP/WARNING.

#### Vincoli inviolabili Branch Awareness (estensione §15)

- **R.B7** — Il layer inspect (`vcs-status` / `vcs-preflight-protocol`) è **read-only**: usa solo
  `git status`, `git branch`, `git rev-parse`, `git symbolic-ref`, `git merge-base`, `git
  ls-files`. Mai `checkout`, `commit`, `fetch`, `pull`, `reset` o qualunque comando che muti lo
  stato del working tree o del ref.
- **R.B8** — Il gate align (`dispatch_gate`) **non esegue mai `git checkout` automatico**. Con
  `auto_align: propose` propone il comando sotto gate umano; con `off` si limita a STOP/WARNING +
  comando suggerito. Coerente con il vincolo esistente «mai cambiare branch».
- **R.B9** — L'expected branch è calcolato **esclusivamente** da `branch-resolver` (single source
  of truth): `vcs-preflight-protocol` e `vcs-handoff` non ridefiniscono la logica di naming.
- **R.B10** — A `branch_awareness.enabled: false` (o blocco assente) l'intero layer è **no-op**:
  `/vcs-status` resta invocabile esplicitamente (volontà esplicita = esecuzione), ma nessun gate
  automatico si attiva e il dashboard `/run` non mostra la tabella branch. Backward compat R.P3.

#### `factory.config.yaml.vcs.branch_awareness` (schema)

```yaml
vcs:
  mode: submodule
  submodule_path: ./code/backend
  branch_strategy: per-tsk        # shared | per-tsk | per-sprint
  base_branch: develop            # NEW v2.25 — disambigua "shared", fork-point per per-tsk
  branch_awareness:               # NEW v2.25 — blocco opt-in, default off
    enabled: false                # master switch del layer
    preflight: false              # tabella /vcs-status nel dashboard /run
    dispatch_gate: off            # off | warn | block  (gate Fase 0 dev-protocol)
    auto_align: off               # off | propose  (mai checkout silente, R.B8)
    drift_check: false            # rileva parent-ref vs submodule-HEAD divergence
```

Default globale off → zero cambio di comportamento. Il layer ha valore soprattutto per
`mode: submodule` e `sibling` (multi-HEAD); per `monorepo` è degenere (un solo HEAD) ma
ammesso.

## §16 — Sync adapters (multi-source L1, v2.9, esteso v2.14 Fase 2)
<!-- profiles: standard, full -->

Il ruolo *Sync* (§2) è l'unico ruolo della factory **pluralizzabile per sorgente**: per
ogni famiglia di input L1 (PDF, Figma, repo locale, **knowledge graph**, futuri
Notion/Confluence/…) esiste un sub-agent dedicato che scrive il proprio sotto-scope di
`raw/`. Tutti i sub-agent condividono `raw/.extraction-manifest.json` (append-only per
chiave). L'*Analyst* (`wiki-keeper`) resta agnostico alla sorgente: legge il manifest,
capisce quale shape gestire (`.txt` | `.kb.json` | …), applica la grammatica di
citazione corrispondente (§6).

### Sub-agent supportati (v2.14)

| Sub-agent | Input | Output L1 | Trigger |
|---|---|---|---|
| `sync-docs` | `raw/*.pdf` | `raw/*.txt`, `raw/images/*-fig-NN.md` | nuovi PDF in `raw/` |
| `figma-sync` (v2.9) | URL Figma o `file_key` (passato al comando, non vive in `raw/`) | `raw/YYYY-MM-DD-figma-<file-key>.kb.json`, opzionali `raw/images/*-frame-NN.{md,png}` | comando `/figma-sync <url>` |
| `repo-sync` (v2.12) | path locale a un repo esistente (passato al comando; mai vive in `raw/`) | `raw/YYYY-MM-DD-repo-<slug>.md` (documento di specifiche umano-leggibile + sezioni strutturate: stack rilevato, struttura, moduli chiave, API surface, dipendenze, vincoli normativi); opzionale companion `raw/images/YYYY-MM-DD-repo-<slug>-tree.md` (albero del filesystem fino a depth configurabile) | comando `/repo-sync <path>`; usato dal bootstrap quando `wiki_feed_source: existing-repo` |
| **`graphify-sync` (v2.14 Fase 2)** | **`code_path` (entry di `factory.config.yaml.code_paths`) — passato al comando, non vive in `raw/`** | **`raw/YYYY-MM-DD-graph-<slug>.md` (summary umano-leggibile del graph: god nodes, surprising connections, confidence breakdown EXTRACTED/INFERRED/AMBIGUOUS) + side-channel `.graphify-state/code_paths/<slug>/{graph.json, GRAPH_REPORT.md, last_full_rebuild.txt}` (consumato dai dev-agent come context replacement)** | **comando `/graphify-sync <target>`; usato dai dev-agent in modalità context-compression quando `compression.context.enabled: true` (§20.10)** |

### Contratto per un nuovo sync adapter

Aggiungere un sub-agent (es. ipotetico `notion-sync`) richiede:

1. File agente in `.claude/agents/<name>.md` (o equivalente per altro runtime) — **thin**, identità + scope (regola v2.3).
2. Skill di procedura in `.claude/skills/<name>-protocol.md` — **fat**, contiene Discovery → Estrazione → Serializzazione (regola v2.3).
3. Comando di invocazione in `.claude/commands/<name>.md`.
4. Naming dichiarato in §4 (path + pattern per gli artefatti prodotti). Convenzione: prefisso del source nel filename (`<source>-` o `<source>-<key>-`) per evitare collisioni cross-adapter.
5. Una voce in `raw/.extraction-manifest.json` per ciascuna estrazione, con chiave univoca derivata dal source.
6. Eventuale grammatica di citazione in §6, se lo shape non è `.txt`/`.md` (es. `.kb.json` ha la regola dotted-path).
7. Aggiornamento di `ingest-protocol` (Fase 0/1) per leggere il nuovo shape.
8. Aggiornamento di `lint-checks` Check 4e (coerenza manifest ↔ filesystem) per validare il nuovo tipo.

### Invariante di isolamento

Ogni sub-agent Sync scrive **solo** nel proprio scope di naming. Mai sovrapposizioni:
`sync-docs` non tocca `*.kb.json` né `*-repo-*.md` né `*-graph-*.md`; `figma-sync` non
tocca `*.txt` né `*-repo-*.md` né `*-graph-*.md`; `repo-sync` non tocca `*.txt` né
`*.kb.json` né `*-graph-*.md` (e mai i file della sorgente scansionata, §7 r.17);
`graphify-sync` (v2.14) non tocca `*.txt` né `*.kb.json` né `*-repo-*.md` (e mai il
`<code_path>` analizzato — §7 r.17 esteso a code_path scanning). Se due adapter
producono lo stesso slug per fonti diverse → ERROR di config (un sync adapter deve
scegliere un namespace univoco). Solo `.extraction-manifest.json` è condiviso, e
ciascun sub-agent vi appende **solo la propria entry** (mai overwrite di entries
altrui).

### Side-channel storage per `graphify-sync` (v2.14 Fase 2)

A differenza degli altri sync adapter, `graphify-sync` produce **due output paralleli**:

1. **`raw/YYYY-MM-DD-graph-<slug>.md`** — riepilogo umano-leggibile del graph,
   consumabile dal `wiki-keeper` come ingest L1→L2 standard (analogo a `repo-sync`).
2. **`.graphify-state/code_paths/<slug>/`** — side-channel storage (analogo a
   `code_quality/`, §19): graph completo machine-readable (`graph.json`,
   `GRAPH_REPORT.md`, `last_full_rebuild.txt`). **Non versionato in git**
   (`.gitignore`-d). Consumato a runtime dai dev-agent e dal code-reviewer come
   **context replacement** dei file sorgente raw (vedi §20.10 Context Compression).

Caratteristiche del side-channel:
- **Rebuildable**: full rebuild ricostruisce tutto da zero da `<code_path>` (zero
  perdita di stato, solo costo di rebuild — 2–20 $ token su primo build).
- **Scritto solo da `graphify-sync`** (analogo a R.Q2 di CQRL — scope di scrittura chiuso).
- **Letto da molti**: dev-agent, code-reviewer, wiki-query (in v2.15 sperimentale).
- **Filesystem è single source of truth**: il graph è una *view derivata*, mai
  authoritative. Se conflitto graph ↔ filesystem → vince filesystem.

### Riuso dello Stack Detector (v2.12)

La skill `stack-detector` (definita in §19.2 come componente del Code Reviewer) è
**riusabile** dal `repo-sync`: durante la fase di estrazione del repo esistente, il
sub-agent invoca `stack-detector` per popolare la sezione `## Stack rilevato` del
documento `raw/YYYY-MM-DD-repo-<slug>.md` con `language`, `framework`, `framework_version`,
`secondary_libs`, `patterns_expected`. Questa riusabilità rende la pipeline coerente:
ciò che il Code Reviewer userà a runtime sul codice prodotto da L5 è la stessa logica
che `repo-sync` usa al kick-off di un progetto pre-esistente.

### Bootstrap da repo esistente — coupling modes (v2.12)

Quando la factory viene scaffoldata con `wiki_feed_source: existing-repo` (cioè il
materiale iniziale per L1 è uno o più repo locali preesistenti), l'utente sceglie
**come accoppiare** la factory ad ogni repo. La scelta determina deterministicamente
le entry di `code_paths` (§13) — `path`, `layers`, `vcs.mode` — non chiesti
indipendentemente.

**Single-repo vs multi-repo** (v2.12):
- **Un solo repo sorgente** → una sola entry in `code_paths`, una sola scelta di coupling.
- **Più repo sorgente** (FE + BE disaccoppiati, micro-frontend, microservizi, ...) → N
  entry in `code_paths`, ciascuna con il proprio coupling. Coupling diversi per repo
  diversi sono legittimi (es. monorepo per il primo repo + sibling per gli altri,
  oppure tutti sibling — vedi sotto).

**Tre coupling canonici** (applicabili a ciascun repo indipendentemente):

| Coupling | Path destinazione factory | `code_path` (derivato) | `vcs.mode` (derivato) | Modifica al repo sorgente? |
|---|---|---|---|---|
| **`monorepo`** | = path del repo esistente | `./` (radice) o sub-path interno | `monorepo` | **Sì** (factory installata dentro il repo: `PATTERN.md`, `.claude/`, `wiki/`, `management/`, `factory.config.yaml`, `code_quality/` se on, …). Mai sovrascrive file esistenti del repo (i path del cascade L1-L4 sono nuovi). Gate umano obbligatorio per conferma (potenziale conflitto se il repo ha già file omonimi). |
| **`sibling-new-repo`** | Nuovo path separato (default: `<repo-path>-factory/` accanto) | path **assoluto** verso il repo esistente | `sibling` | **No**. Il repo sorgente resta intatto (§7 r.17). La factory legge `<code_path>` come working tree esterno. `vcs.remote_url` opzionale (URL git del repo esistente, per documentazione). |
| **`submodule-new-repo`** | Nuovo path separato | relativo (default: `./code/`) | `submodule` + `submodule_path: ./code/` | **No** al momento del bootstrap. L'utente esegue manualmente `git submodule add <remote-url-repo-esistente> ./code/` dopo il bootstrap (gate §7 r.14 — mai automatico). |

**Vincoli inviolabili del coupling**:

- **R.B1 — Il bootstrap non scrive mai nel repo esistente in modalità `sibling-new-repo`
  o `submodule-new-repo`.** Anche se `repo-sync` (durante il bootstrap stesso) lo legge,
  l'unico path di scrittura è la nuova factory directory.
- **R.B2 — In `monorepo`, conferma esplicita prima di toccare il repo esistente.** Il
  bootstrap mostra in chat la lista dei file/cartelle che verrebbero aggiunti
  (`PATTERN.md`, `CLAUDE.md` o equivalente adapter, `factory.config.yaml`, `wiki/`,
  `management/`, `design_&_architecture/`, `memory/`, `raw/`, `.claude/` o adapter
  scelto, `code_quality/` se on) e attende `y/N`. Se uno qualsiasi di questi path
  esiste già nel repo → ABORT con messaggio chiaro (no overwrite distruttivo).
- **R.B3 — `repo-sync` scansiona la sorgente in modalità read-only sempre** (§7 r.17),
  indipendentemente dal coupling. In `monorepo`, scansiona dopo che il bootstrap ha
  scaffoldato i file della factory: il documento `raw/<data>-repo-<slug>.md` osserverà
  l'esistenza della factory appena creata come parte dello stato del filesystem (caso
  *reflective*, legittimo). Per evitare rumore, la skill `repo-extraction-protocol`
  esclude dallo scope di scansione i path tipici della factory (`PATTERN.md`,
  `.claude/`, `wiki/`, `management/`, `design_&_architecture/`, `memory/`, `raw/`,
  `code_quality/`).
- **R.B4 — Il coupling è scelto al bootstrap e non muta a runtime.** Cambiare coupling
  dopo lo scaffolding richiede rifare il bootstrap o operazioni VCS manuali (cross-repo).
  Il `wiki-lint` check 4d (coerenza VCS) segnala drift fra coupling implicito e
  `vcs.mode` corrente.
- **R.B5 — Agent-agnostic preservato**: il coupling è una proprietà del *layout
  filesystem* e *VCS*, non del runtime di agenti. Qualsiasi adapter (`.claude/`,
  `.cursor/`, `.openai/`, …) può coesistere su una factory bootstrappata con qualsiasi
  coupling. La scelta dei tool (Read/Write/Bash di Claude Code, o equivalenti) è
  ortogonale.
- **R.B6 — Multi-repo coupling mix** (v2.12): in setup multi-repo, ogni entry di
  `code_paths` può avere un coupling distinto. Vincoli:
  - **Al massimo una** entry può avere `vcs.mode: monorepo` (un solo repo può ospitare
    fisicamente la factory). Più entry con `monorepo` simultanee → ERROR di config
    (segnalato dal lint Check 4d esteso).
  - Le altre entry coesistono come `sibling` (path assoluto, no operazioni cross-repo
    automatiche), `submodule` (referenziate dal factory repo via `.gitmodules`), o
    `external` (path opaco).
  - **`repo-sync` invocato N volte al bootstrap**, una per entry in `code_paths` con
    `wiki_feed_source: existing-repo`. Produce N file in `raw/` (uno per repo); il
    `wiki-keeper` può ingerirli in batch (§3 "Ingest" parallelo via
    `wiki-keeper-worker` se N ≥ 3).
  - **`vcs-handoff` opera per-target**: dato il `target:` del TSK, risolve l'entry,
    applica la procedura del relativo `vcs.mode`. Mai operazioni cross-target
    coordinate automaticamente (gate umano §7 r.14 invariato).
  - **Scheduler conflict-detection** (§18.4 R.S2): due TSK con `target` diversi sono
    sempre conflict-free (filesystem disgiunti). Conflict solo intra-target su
    overlap di `code_path` glob.

### Esempi multi-repo + coupling al bootstrap

**Caso a — microservizi all-sibling** (factory in nuovo repo, tutti i microservizi
restano intatti):

```
Bootstrap input:
- wiki_feed_source: existing-repo
- N = 3 repo (auth-service, payments-service, web-app)
- coupling per ciascuno: sibling-new-repo
- factory destination: /Users/me/repos/customer-portal-factory/ (NUOVO)
- Per ciascun repo: path assoluto + name + layers + remote_url

Risultato:
- /Users/me/repos/customer-portal-factory/ contiene la factory
- Auth/Payments/Web restano INTATTI (R.B1)
- code_paths in factory.config.yaml ha 3 entry, ciascuna sibling
- raw/ contiene 3 file *-repo-<slug>.md (uno per servizio)
```

**Caso b — monolite monorepo + servizio sidecar sibling**:

```
Bootstrap input:
- wiki_feed_source: existing-repo
- N = 2 repo (monolith-app, notification-service)
- coupling: monolith-app=monorepo (factory dentro), notification-service=sibling
- factory destination: /Users/me/repos/monolith-app/ (= path del monolith)

Risultato:
- Monolith-app contiene ora anche la factory (PATTERN.md, .claude/, ecc.)
- Notification-service resta intatto (R.B1)
- code_paths: 2 entry — uno monorepo (./ del monolith) + uno sibling
  (/Users/me/repos/notification-service/)
```

**Caso c — tutti submodule**:

```
Bootstrap input:
- N = 4 repo (frontend-web, backend-api, db-migrations, shared-lib)
- coupling per tutti: submodule-new-repo
- factory destination: /Users/me/repos/portal-factory/

Risultato:
- Factory in /Users/me/repos/portal-factory/
- code_paths: 4 entry, ciascuna submodule, submodule_path: ./code/<name>/
- Bootstrap stampa 4 comandi `git submodule add ...` per l'utente (mai automatici, §7 r.14)
```

### `raw/.extraction-manifest.json` (esteso v2.9)

Formato per entry (retrocompat: entries pre-v2.9 senza `source` sono interpretate come
`source: pdf` dal *Analyst* e dal *Lint*):

```json
{
  "<key>": {
    "source": "pdf | figma | notion | ...",
    "extracted_at": "ISO-8601",
    "primary_artifact": "raw/<path>",
    "secondary_artifacts": ["raw/images/<...>", "..."],
    "extractor_version": "<sub-agent>@<semver>",
    "extraction_metadata": { ... }
  }
}
```

`<key>` è il nome base senza estensione e senza directory (es. `2026-05-21-spid-tech` o
`2026-05-21-figma-ABC123`). I sub-agent **non scrivono mai** entry con `source` diverso
dal proprio.

### Vincoli inviolabili (estensione §7)

- **L1 read-only resta intatto** (§7 r.1): solo *Sync* scrive in `raw/`, e ciascun
  sub-agent solo nel proprio scope.
- **Mai chiamare API esterne automaticamente in altri ruoli**. Le chiamate ad
  Anthropic API, Figma MCP, Figma REST API, Notion API, ecc. vivono solo nelle skill
  dei sub-agent Sync. Gli altri ruoli (PM/Arch/TPM/Dev) leggono il manifest e i
  file di `raw/`, mai la fonte originale.
- **Mai scrittura cieca**: il sub-agent Sync mostra in chat la proposta (file da
  creare, dimensioni, fonti) e attende conferma esplicita prima di scrivere
  (analogo a `ingest-protocol` Fase 2).

## §17 — Publisher adapters (multi-target L3/L4, v2.10)
<!-- profiles: full -->

Simmetrico ai sync adapters (§16): se §16 definisce il contratto per ingerire L1 da
fonti eterogenee, §17 definisce il contratto per **pubblicare L3/L4 verso tool esterni
di project tracking** (GitHub Issues/Projects, GitLab Issues, Jira, Linear, …) come
mirror push-only. Il sub-agent Publisher è un nuovo ruolo (§2) pluralizzabile per
provider.

### Invariante di direzione (PATTERN §8, single source of truth)

- `management/kanban/**` resta **canonico**. Il provider esterno è un mirror.
- Pubblicazione è **push-only** in v2.10. Modifiche fatte direttamente nel tool
  esterno (body, label, milestone) verranno **sovrascritte** al prossimo publish.
  Solo i `comment` e gli assignee su issue esterne sono lasciati intatti
  (l'Publisher non li tocca).
- Bidirectional di `status:` (issue chiusa sul provider → `status: done` nel TSK
  locale) è candidato per v2.11, **non implementato in v2.10**.

### Provider supportati (v2.10)

| Provider | Sub-agent | Implementazione di riferimento | Auth env (default) |
|---|---|---|---|
| `github` | `github-publisher` | `gh` CLI (richiede `gh auth login` preventivo) | `GH_TOKEN` |
| `gitlab` | `gitlab-publisher` | `glab` CLI o REST API | `GL_TOKEN` (placeholder, non implementato in v2.10) |
| `jira` | `jira-publisher` | REST API Cloud | `JIRA_TOKEN` (placeholder, non implementato in v2.10) |
| `linear` | `linear-publisher` | GraphQL API | `LINEAR_TOKEN` (placeholder, non implementato in v2.10) |
| `none` | — | (publishing disabilitato) | — |

`v2.10` rilascia il solo `github-publisher` come riferimento. Gli altri provider
hanno il contratto pronto ma agent/skill **non scaffoldati**: aggiungerli è
seguire il contratto del nuovo adapter (vedi sotto), niente modifiche a PATTERN.

### `factory.config.yaml.kanban_publish` (schema, v2.10)

```yaml
kanban_publish:
  provider: github          # none | github | gitlab | jira | linear | custom
  target: "<org>/<repo>"    # provider-specific: GH "org/repo", GL "group/proj", JIRA "PROJ", LINEAR "team-id"
  auth_env: GH_TOKEN        # nome variabile d'ambiente che contiene il token
  mode: push-only           # v2.10: solo push-only; bidirectional candidato v2.11
  batch_limit: 10           # gate §7 r.15: max artefatti pubblicati per run senza secondo gate
  mapping:
    epic_to: milestone      # milestone | issue-label | project-column
    story_to: issue-label   # issue-label | issue-type-story
    task_to: issue-label    # issue-label
    sprint_to: milestone    # milestone | project-iteration | cycle
  labels:
    epic: "kanban:epic"
    story: "kanban:story"
    task: "kanban:task"
    layer_prefix: "layer:"  # produce label "layer:be", "layer:fe", ...
  filter:
    only_consumer: any      # any | agent | human (pubblica solo TSK con questo consumer)
    only_status: any        # any | todo | in-progress | done
```

### Contratto per un nuovo Publisher adapter

Aggiungere un sub-agent (es. `linear-publisher`) richiede:

1. Agente thin in `.claude/agents/<provider>-publisher.md` (o equivalente per altro runtime).
2. Skill provider-specific in `.claude/skills/<provider>-mapping.md` — mapping concreto EP/US/TSK ↔ artefatti del provider + comandi CLI/API.
3. La skill provider-agnostic `publisher-protocol` (5 fasi) **non va duplicata**: il provider-specific mapping è una skill *complementare* invocata da `publisher-protocol`.
4. Nessun nuovo comando: `/kanban-publish` è agnostico al provider — legge `kanban_publish.provider` da config e invoca il sub-agent corrispondente.
5. Aggiornamento di `lint-checks` Check 4f (lista provider noti).
6. **Mai modifiche a PATTERN.md** per un nuovo provider: il contratto §17 li copre tutti.

### Invariante di isolamento

Ogni Publisher scrive **solo** nel proprio scope:

- Frontmatter `external_id:` di `management/kanban/EP-*/US-*/TSK-*.md` — solo se il prefisso `<provider>:` corrisponde al sub-agent attivo.
- `wiki/log.md` (append-only, marker `publish`).
- Provider esterno via CLI/API (gate umano per ogni batch, §7 r.15).

**Mai sovrapposizioni**:
- Mai modificare il corpo dei file kanban (PM/TPM ownership).
- Mai modificare `external_id:` di altri provider (es. `github-publisher` non tocca `external_id: jira:...`).
- Mai cancellare/chiudere issue esterne (anti-pattern destruttivo, vedi §7 r.15).

### Procedura `publisher-protocol` (5 fasi, provider-agnostic)

1. **Bootstrap**: verifica auth (`<auth_env>` settato + provider raggiungibile via CLI/API ping). Read `factory.config.yaml.kanban_publish`. ABORT se config invalida.
2. **Discovery**: `Glob management/kanban/EP-*/EP-*.md`, `US-*/US-*.md`, `**/TSK-*.md`. Filtra in base a `kanban_publish.filter`. Estrai metadata (frontmatter + body markdown).
3. **Plan**: per ciascun artefatto, decidi CREATE vs UPDATE in base a `external_id:` frontmatter. Mostra in chat: `Plan: CREATE EP×N1, US×N2, TSK×N3; UPDATE EP×M1, US×M2, TSK×M3. Procedo? [y/N]`. **Attendi conferma esplicita** (§7 r.15). Se totale CREATE+UPDATE > `batch_limit`, secondo gate obbligatorio.
4. **Publish**: per ogni artefatto, invoca la skill provider-specific (`<provider>-mapping`) che esegue CREATE/UPDATE sul provider e ritorna l'`external_id`. Aggiorna il frontmatter locale **solo nel campo `external_id:`** (mai del corpo).
5. **Log**: append a `wiki/log.md` template `publish` (count CREATE/UPDATE/skipped, lista artefatti con nuovo `external_id`). Output a chat: link al milestone/board esterno.

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
| **Incremental update** (AST only) | Post-commit, on-session-start | Zero token | Disallineamento file ↔ AST nodes |
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
  - Incremental update post-commit (via git hook o session-start, zero token)
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

## §21 — Versioning
<!-- profiles: standard, full -->

- **v2.18** (questa): **A11y + UX/UI Integration + Task Analytics** (tutto opt-in, EP-007..EP-010). **A11y (EP-007)**: pre-screening WCAG 2.2 AA stack-agnostico via tool deterministico `run_a11y_scan` (Playwright + axe-playwright, no MCP — riuso infra Visual Oracle) + skill `accessibility-testing-protocol` + agente opzionale `a11y-specialist` + comando `/a11y` + blocco config `a11y` (default `enabled: false`). Tre campi frontmatter TSK opzionali additivi `a11y_status` / `a11y_report` / `a11y_skip_reason` (§5). Lint **Check 4o** WARNING-only. **Regola di neutralità** (invariante operativa, non §7): mai conformità su soli `automated_findings`, sempre `manual_checks` N ≥ 1. **UX/UI (EP-008)**: review di usabilità via skill `ux-ui-review-protocol` (rubrica anti-soggettività 10 Nielsen + 6 dimensioni UI + 5 di flusso; ogni finding cita `rubric_ref`) + design via `ux-ui-design-protocol` + agenti opzionali `ux-ui-reviewer` / `ui-designer` (separazione enforced **no-auto-eval**) + comandi `/ux-ui-review` + `/ux-ui-design` + skill condivise `screenshot-capture-protocol` / `design-tokens-extraction` / `design-system-conformance-check` + blocco config `ux_ui`. Quattro campi frontmatter TSK opzionali `ux_ui_status` / `ux_ui_report` / `ui_design_spec` / `ux_ui_skip_reason` (§5). Lint **Check 4p** WARNING-only. Nuovo ordering pipeline FE **develop → visual-oracle → ux-ui-review → code-review** (§19.11, ADR-019). 7 ADR risolti (ADR-014..020). **Task Analytics (EP-009 misurazione + EP-010 stima)**: operazioni canoniche autonome opt-in (§3) via `analytics.measurement.enabled` / `analytics.estimation.enabled` (default `false`); comandi `/analytics` (misura il passato: costi/ROI, mai medie) e `/estimate` (stima il futuro: intervallo + confidenza + assunzioni + contingency, fallback PERT-only senza storico); agenti opzionali `analytics-reporter` / `estimation-analyst`; tool deterministici `.claude/tools/analytics/*` (no MCP); campi frontmatter TSK opzionali `cost_event_log` / `effort_hours` (EP-009) + `estimate_id` (EP-010). **Niente nuova invariante §7** (le 18 restano invariate; gli invarianti elencati sono invarianti operative delle capability, non di sistema). Nuovo seed `meta-prompts/v2-18/factory-bootstrap.md` (**estende v2-17** con la sola Fase 1.sexies opt-in) + variante consolidata self-contained `meta-prompts/v2-18/factory-bootstrap-full.md` (intera catena `extends` inlinata). Dispatcher `/factory-bootstrap` default `v2-18`. Nuovo meta-comando `/factory-upgrade` (skill `factory-upgrade-protocol`) per upgrade incrementale non distruttivo di factory esistenti (delta chain, target ≥ v2-13). Backward compat totale: factory con `a11y.*` / `ux_ui.*` / `analytics.*` tutti `false` (default) si comporta identica a v2.17. Vedi `design_&_architecture/proposta-a11y-uxui-integration-v218.md` + ADR-014..ADR-027.
- **v2.17**: **Visual Oracle Integration** (opt-in, EP-005/EP-006). Nuovi 3 campi frontmatter TSK opzionali additivi `visual_status` / `interaction_test_spec` / `visual_reference` (§5; single-writer `visual_status` = skill `visual-oracle-protocol`, analogo `review_status`; default implicito assente = `pending`). Nuova variante di Develop FE **«Visual Verification»** (§3, sub-step Fase 4-bis di `dev-protocol`) che chiude il loop visivo prima del `done`. Nuova nota ordering **develop → visual-oracle → review** (§19.11) con precondition additiva in `code-review-protocol` Fase 0 quando `fe_correctness.enabled: true` AND `TSK.layer: fe`. Side-channel report riusa `code_quality/reports/` con slug `visual` (cartelle PNG non versionate, file `.json`/`.md` versionati). **Niente nuova invariante §7** (sezione §7 invariata rispetto a v2.16; tutto opt-in, backward compat totale — `fe_correctness.enabled: false` default → comportamento v2.16 identico). Vedi ADR-012 (schema dati) + ADR-013 (ordering 3 punti) + ADR-009.
- **v2.16**: **Premortem Integration** (opt-in, Opzione B skill standalone). Nuova skill `premortem-protocol` (operazione opzionale §3, 5 fasi: Context Gathering → Frame Setting → Raw Premortem → Parallel Deep-Dives → Sintesi) + comando `/premortem` invocabile su 3 input shape (descrizione libera / artefatto kanban EP-US-TSK / pagina wiki). Output: Risk Registry strutturato con tassonomia Tigers/Paper Tigers/Elephants ([[risk-classification-tigers-paper-tigers-elephants]]). Nuovo blocco frontmatter opzionale `risk_classification:` (§5) su EP/US/TSK (6 enum tier + `premortem_ref` + `reviewed_by`). Nuovo lint **Check 4m** WARNING-only (coerenza `risk_classification` ↔ Risk Registry; 3 sotto-check, mai ERROR). Nuovo dominio scheduler **`premortem`** (§18.3, default `parallel`, composizione N×M sub-agent — cap interno Fase 4 `max_parallel: 8` hardcoded ADR-001). Pass CQRL opzionale **`premortem-on-merge`** (§19.3, 4° pass, default **off** — ADR-005). Telemetria d'uso `memory/episodic/premortem-runs.md` (single-file append-only, metadati only — ADR-006). Nuovo template `management/risk-registry.md` (append-only, schema 9 colonne — ADR-002). Nuovo seed `meta-prompts/v2-16/factory-bootstrap.md` (**estende v2-15** con la sola Fase 1.quater opt-in; la bozza del design proponeva v2-13 ma è stata corretta in Develop per non perdere il Compression Layer). Dispatcher `/factory-bootstrap` default `v2-16` (branch v2-11..v2-16). **Niente nuova invariante §7** (R.P1 output mai auto-applicato / R.P2 bar minimo fail-loud / R.P3 opt-in totale vivono nella skill, non in §7 — coerente con la filosofia opt-in deferred di v2.15). **Niente gate auto-enforcing**: `/premortem` è sempre esplicito (ADR-003, no phrase-trigger). Backward compat totale: factory che non opta-in si comporta identica a v2.15 (verificato TSK-009: `/lint` v2.15-only = 0 nuove ERROR/WARNING; Check 4m no-op senza blocco). v2.17+ valuterà promozione a operazione canonica + gate condizionali su evidenza telemetrica (gap aperto: soglia di rivalutazione non ancora definita — `premortem-v217-promotion-threshold-undefined`). Self-premortem applicato a v2.16 stessa come release gate (TSK-018, calibration valida). Vedi `design_&_architecture/proposta-premortem-integration-v216.md` + ADR-001..ADR-007 + [[premortem-skill]] + [[factory-premortem-integration]] + [[premortem-runbook]].

- **v2.15**: **Consolidation release**. Nessuna nuova feature di framework: bump versione del PATTERN per chiudere il ciclo v2.14 (Output Compression Layer Fase 1 + Context Compression Layer Fase 2) come baseline stabile. **Riformulazione gate empirici**: i due gate Fase 1.5 ([[compression-validation-template]] — validation empirica OCL su factory derivata con sprint reale) e Fase 3a ([[wiki-as-graph-poc-template]] — PoC karpathy preservation, pre-requisito per Fase 3b wiki-as-graph) restano **setup-ready** ma sono ora classificati come **opt-in deferred**: non bloccanti per il consolidamento del PATTERN, eseguibili a discrezione del derivatore quando dispone di factory candidata + parametri adeguati per misurazione. Il loro stato «pending run empirico» smette di essere un blocker della versione e diventa una *gate aperta che chiunque abbia setup adeguato può eseguire e poi proporre come input per v2.16+*. Motivazione: il meta-framework stesso non ha kanban significativo né sprint reale per essere candidate di validation, e applicazioni concrete del framework non hanno necessariamente parametri di baseline misurabili — bloccare il consolidamento del PATTERN sulla validation empirica significherebbe lasciare v2.14 in stato «WIP» indefinitamente. Tutti gli invarianti R.C1-R.C6 (output) + R.G1-R.G6 (context) restano in vigore identici. Default `compression.output.enabled: false` + `compression.context.enabled: false` invariati. Backward compat totale verso v2.14 (factory v2.14 si comportano identiche su v2.15; nessuna migration necessaria; solo aggiornamento referenze versione). Asse `wiki` come target Graphify (Fase 3b) resta gated da Fase 3a PoC come prima — la riformulazione del gate ne sposta l'attivazione ai termini «*se eseguita con esito positivo*», non «*quando eseguita*»; in assenza di esecuzione il gate resta chiuso. Vedi [[factory-compression-layer]] §«v2.15 consolidation» + [[migration-v215]] (runbook futuro, opzionale: la migration v2.14 → v2.15 è no-op di codice).
- **v2.14**: Compression Layer a due assi (§20) opt-in. **Fase 1 — Output Compression Layer** via [[caveman]] skill (§20.1-§20.9): meccanismo per ridurre i token generati su canali messaging agent-to-agent senza toccare gli artefatti persistenti. Tre `policy_profile` selezionabili: `conservative` (default, drift minimo + chain-depth severity ceiling), `aggressive` (risparmio massimo, factory mature), `custom` (matrice esplicita). Sei invarianti R.C1-R.C6 (§20.4 — invarianti non overridabili `to_user`/`to_artifact`/`propagate-resolution` sempre off, allow-list channel-aware, chain-depth ceiling, cross-factory off, drift fallback automatico su marker ambiguità, opt-in totale). Nuova regola §7 r.18 (compression mai sugli artefatti). Nuovo campo frontmatter agent opzionale `caveman_policy:` (§20.6) per override locale (può solo abbassare, mai abilitare canali R.C1). Nuova skill `caveman-protocol` (5 fasi: Bootstrap → Identify Channel → Apply Compression → Drift Check → Log) + nuovo comando `/compression [show|set|policy|dry-run]`. Hook in `parallel-scheduling` (§20.7): intercept inline nel dispatch della wave, calcolo `tokens_compressed/tokens_raw` per canale nel `wave_report.md`. Topology-aware default (§20.3): `knowledge-only` → `aggressive`, full-stack/hybrid → `conservative`. `wiki-lint` nuovo Check 4k (coerenza `policy_profile == custom` ⇒ `channels` block completo; R.C1 invariants enforced in `caveman-protocol` invocations). Default `compression.output.enabled: false`. **Fase 2 — Context Compression Layer** via [[graphify]] (§20.10-§20.11): quarto sync adapter `graphify-sync` (§16) che estrae knowledge graph da `code_path` (target di `factory.config.yaml.code_paths`) producendo `raw/YYYY-MM-DD-graph-<slug>.md` (summary umano-leggibile) + side-channel `.graphify-state/code_paths/<slug>/` (`graph.json`, `GRAPH_REPORT.md`, `last_full_rebuild.txt`, non versionato in git). Confidence-gated dispatch (§20.10.1): executor agent (dev) ricevono solo `EXTRACTED` (AST deterministico); explorer agent (lead-architect, wiki-query) ricevono `EXTRACTED + INFERRED`; reviewer (code-reviewer) tutto con flag. Sei invarianti R.G1-R.G6 (§20.11 — filesystem single source of truth, confidence-gated dispatch obbligatorio, blast radius pre-check su modifiche, drift mitigation obbligatoria con cron weekly full rebuild + drift monitoring, side-channel write-restricted, opt-in totale). Nuovo agent `graphify-sync` (analogo a `repo-sync` v2.12 + writes side-channel) + nuova skill `graphify-extraction-protocol` (5 fasi: Bootstrap → Discovery → Build Graph → Side-channel write → Log) + nuovo comando `/graphify-sync [<target>|show|status|refresh]`. Integrazione con CQRL (§20.10.3): `get_impact_radius(<file>)` pre-check incluso nel `task_package` come blast radius constraint (R.Q4-ter regression mitigation). Confidence-gated dispatch esteso in `parallel-scheduling` (§20.7 + R.G2). `.graphify-state/` aggiunto al `.gitignore` di bootstrap (R.G6). Default `compression.context.enabled: false`. CI strategy `cache-with-fallback` (zero token su cache hit, fallback scansione filesystem su stale > 7gg, full rebuild solo on-demand). Provider opt-in `graphify-cloud` (default) | `graphify-ollama` (enterprise data residency, 16+ GB VRAM). MCP server `per-agent` (default, isolato) | `shared` (factory mature). Asse `wiki` come target di Graphify (Fase 3, v2.15) gated da PoC karpathy preservation con 4 check non-negoziabili (citation/wikilink/frontmatter/layering); se anche uno fallisce → scartare wiki-as-graph. Fase 1.5 validation on derived factory (gate empirico pre-Fase 2 reale): runbook template [[compression-validation-template]] disponibile per esecuzione su factory derivata v2.14 + Caveman + sprint reale. Backward compat totale verso v2.13 (factory senza i blocchi compression.* si comporta identica). Vedi [[factory-compression-layer]] (design doc + 7 decisioni risolte + aggiornamenti Fase 1 + Fase 1.5) + [[caveman]] + [[graphify]] + [[token-compression]] + [[knowledge-graph-codebase]] + [[migration-v214]] (Fase 1) + [[migration-v214-fase2]] (Fase 2).
- **v2.13**: Multi-adapter scaffolding parallelo (§12 esteso) — formalizzazione del contratto adapter via `adapters/<name>/manifest.yaml`, registry al root del meta-framework con 5 adapter (`.claude/` reference completo, `.cursor/` + `.aider/` full v2.13, `.openai/` partial con setup.py stub, `.gemini/` + `.chatgpt/` manifest-only). Nuovo blocco `factory.config.yaml.adapters:` per dichiarare gli adapter installati nella factory generata. 6 nuove invarianti R.A1-R.A6 (§12.2 — isolamento cartella, state filesystem condiviso, single-committer preservato, manifest immutabile a runtime, adapter aggiungibile a runtime, agent-agnostic preservato). Nuova skill `bootstrap-multiadapter-protocol` come 6° skill del meta-prompt (selezione adapter + loop scaffolding parallelo). Meta-prompt seed riorganizzato: spostato da `~/.claude/factory-bootstrap/` (user-level) a `<meta-framework>/meta-prompts/{v2-11,v2-12,v2-13}/` (repo, versionato col PATTERN). Nuova folder `adapters/` al root del meta-framework. Backward compat: `factory.config.yaml` senza blocco `adapters:` assume `[{name: claude, folder: .claude, maturity: full}]`. PATTERN.md, layer L1-L5, e contratti di citazione (§6) restano agent-agnostic (R.A6). Vedi [[multi-adapter-scaffolding]] (concept futuro) + [[migration-v213]] (runbook futuro).
- **v2.12**: Code Quality Review Layer (§19) — nuovo ruolo *Code Reviewer* (`code-reviewer`, §2) opzionale, nuovo verbo `Review` (§3), nuova KB evolutiva `code_quality/rules/` (3 tier: `canonical`/`emergent`/`team-specific` con tassonomia ID gerarchica `{language}.{framework}.{category}.{specific}`), nuovo storage report `code_quality/reports/<TSK-id>-iter-N.{json,md}`. Nuovi campi frontmatter TSK opzionali: `review_status` (`pending|passed|conditional|rejected`), `review_iter`, `review_report` (§5). Nuovo blocco `code_quality:` in `factory.config.yaml` (§19.7) con `max_iterations` (default 3, R.Q4), thresholds (`confidence_min: 0.6`, `batching_split: 7`, `pass_rate_warn: 0.05`), `passes` (idiomaticity/design/robustness, §19.3), `router` (strategy + max_diff_lines, §19.4), `ruleset` + `reports`. Nuovo sync adapter `repo-sync` (§16) per ingerire repo esistenti — output `raw/YYYY-MM-DD-repo-<slug>.md` riusabile dal `wiki-keeper` per kick-off pipeline da codice pre-esistente. Stack Detector (§19.2) riusabile da `repo-sync` per popolare la sezione Stack del documento. Nuova sezione §16 «Bootstrap da repo esistente — coupling modes» con 3 opzioni (`monorepo` | `sibling-new-repo` | `submodule-new-repo`) che determinano deterministicamente `code_paths[i].path` + `vcs.mode`, e 6 invarianti R.B1-R.B6 (no-write a sorgente in modalità decoupling, conferma esplicita in monorepo, repo-sync read-only sempre, coupling immutabile a runtime, agent-agnostic preservato, multi-repo coupling mix con al più una entry monorepo). **Multi-repo (v2.12)**: schema `factory.config.yaml.code_paths:` come lista di entry `{name, path, layers, tags, vcs}` per supportare FE/BE disaccoppiati, microservizi (N BE), micro-frontend (N FE), monorepo logici con pacchetti multipli. Backward compat: `code_path:` singolare (v2.11-) accettato e auto-promosso a singola entry `default`. Nuovo campo TSK frontmatter `target:` (§5) per disambiguare quando ≥ 2 entry coprono lo stesso layer; obbligatorio in caso di ambiguità (segnalato dal lint Check 4j), opzionale altrimenti (auto-derive). `vcs-handoff` opera per-target. Scheduler R.S2 (§18.4) esteso a `(target, code_path)`: TSK con target diversi sono **sempre** conflict-free su file (filesystem disgiunti) — incremento naturale di parallelismo per microservizi/MFE. Nuove regole §7: r.16 (verdict `reject` = gate umano, mai auto-revert/auto-merge) + r.17 (sync read-only generalizzato — `repo-sync` non muta il repo scansionato). Nuove 7 invarianti del Reviewer R.Q1-R.Q7 (§19.6 — single-committer verdict, scope write chiuso, gate umano reject, bounded loop, stack-aware obbligatorio sopra confidence, ruleset write protetto, no security scope). Nuovo dominio scheduler `review` (§18.3) — TSK indipendenti parallelizzabili. Nuovo bootstrap option "wiki feeding source" (factory-bootstrap meta-prompt v2.12): `empty | pdf | figma | existing-repo`. Default `code_quality.enabled: false` (opt-in esplicito anche con topology dev-agent). Retrocompat: TSK pre-v2.12 senza `review_status` trattati come `pending` quando `code_quality.enabled: true`; report assenti per `enabled: false`. Vedi [[code-quality-review-layer]] + [[stack-aware-ruleset]] + [[code-quality-review-runbook]] + [[repo-sync]] (concept futuro) + [[migration-v212]] (runbook futuro).
- **v2.11**: parallel scheduler agent-agnostic basato su DAG di dipendenze dichiarate nei frontmatter (§18). Nuovi campi frontmatter opzionali: `depends_on` (EP/US/TSK), `blocked_by` esteso a TSK, `code_path` (TSK) — §5. Nuova sezione §18 «Parallel scheduling» con modello (DAG `E_dep ∪ E_conf`), algoritmo a 3 step (toposort + level grouping + graph-coloring partition per conflict detection su `code_path`), domini di parallelismo (§18.3), 8 regole inviolabili dello scheduler (R.S1–R.S8 — single-committer preservato, conflict-free su file, cap di fan-out, gate umano sopra threshold, no rollback collaterale, VCS sempre serializzato), nuovo blocco `scheduler:` in `factory.config.yaml`, output wave-plan in chat. L'Orchestrator espande lo scope con `dispatch` parallelo (multi-`Agent` call nello stesso turno). `wiki-lint` nuovo Check 4g (cicli in `depends_on`, drift `## Dependencies` body ↔ `depends_on` frontmatter). Default `scheduler.enabled: true` con `max_parallel: 4`, `parallel_gate_threshold: 3`. Retrocompat: artefatti senza `depends_on` sono trattati come "nessuna dipendenza" → finiscono al level 0; artefatti senza `code_path` sono trattati conservativamente come serializzanti (politica `empty_code_path_policy: serial`). Vedi [[migration-v211]] (runbook futuro) + [[parallel-scheduling]] (concept futuro) + [[dependency-ordered-dag]] (concept esistente, esteso).
- **v2.10**: Publisher adapters multi-target (L3/L4). Nuovo ruolo *Publisher* (§2) pluralizzabile per provider. Nuovo verbo `Publish` (§3). Nuovo campo frontmatter opzionale `external_id:` (§5) per EP/US/TSK. Nuova regola §7 r.15 (gate cross-tool: conferma esplicita prima di create/update batch su provider esterno; mai delete/close automatici; auth solo da env var). Nuovo blocco `kanban_publish:` in `factory.config.yaml`. Nuova sezione §17 «Publisher adapters» con contratto per nuovi adapter. `github-publisher` come implementazione di riferimento via `gh` CLI; placeholder per `gitlab|jira|linear`. `lint-checks` nuovo Check 4f (coerenza `external_id:` ↔ provider config; orphan se `provider: none`). `publisher-protocol` provider-agnostic + `<provider>-mapping` skill provider-specific. Push-only in v2.10; bidirectional candidato v2.11. Vedi [[migration-v210]] (runbook futuro) + [[publisher-adapters]] (concept futuro).
- v2.9: Sync role pluralizzato (multi-source L1). Nuovo sub-agent `figma-sync` per estrazione Figma via Anthropic API + Figma MCP, basato sul pattern [[chunked-extraction-pipeline]] già documentato. Nuovo shape `.kb.json` come artefatto L1 strutturato (oltre a `.txt`). Nuova grammatica citazione `[^src: <path>.kb.json §<dotted-path>]` (§6). Nuovo §16 «Sync adapters» con contratto per nuovi adapter. `ingest-protocol` esteso per leggere `.kb.json` (Fase 1 ramo strutturato). `lint-checks` Check 4e (coerenza manifest ↔ filesystem ↔ source dichiarata). `.extraction-manifest.json` esteso con `source`/`primary_artifact`/`secondary_artifacts`/`extractor_version`. Retrocompat: manifest pre-v2.9 (chiave-piatta) accettato come `source: pdf`; sync-docs aggiorna in-place quando reingerisce. Vedi [[migration-v29]] (runbook futuro) + [[sync-adapters]] (concept futuro).
- v2.8: VCS integration esplicita. Blocco `vcs:` in `factory.config.yaml` (`mode: monorepo|submodule|sibling|external|none`, + opzionali `submodule_path`, `remote_url`, `branch_strategy`, `commit_coupling`). Nuova skill `vcs-handoff` invocata dal `dev-protocol` Fase 5; nuovo lint check 4d (coerenza VCS). Citazione codice prodotto estesa con un terzo formato (`[^src5-sub:`). Regola §7 r.14 nuova (gate umano obbligatorio per scritture VCS distruttive/cross-repo). File `.factory-lock` opzionale (`commit_coupling: pin`) per reproducibilità. Vedi [[migration-v28]] (runbook) + [[vcs-and-code-path]] (synthesis).
- v2.7: execution layer L5, 4 dev-agent opzionali, operazione `Develop`, topologie esplicite, `factory.config.yaml`, stack modes (`manual/guided/auto`), frontmatter TSK `layer:`+`consumer:`. Vedi [[migration-v27]] + [[topology-and-dev-agents]].
- v2.6: gate L4 graduato (`blocking_level: hard|soft`), state propagation downstream (`Propagate` + `reconcile-needed`), auto-promotion suggerita.
- v2.5: operazione `Heal` (evaluator-optimizer vincolato, whitelist chiusa, max 3 iter).
- v2.4: ingest parallelo per batch ≥ 3.
- v2.3: refactor "thin agents, fat skills" (13 skill).
- v2.2: `memory/` tree, rimozione hook bash/python, two-phase commit, wiki-staging.
- v2.1 → v1.0: separazione PATTERN.md/adapter; rimozione `project_manifest.json` + `reviewer`.

<!-- NOTA NUMERAZIONE — §22 «Release Governance»: gap §21 → §23 chiuso da TSK-100
     (EP-012 P0). Il maintainer ha deliberato l'aggiunta della sezione §22 come da
     ADR-036 §A/§B (decisione: «aggiungi §22 come da ADR-036»). §22 precede §23 nell'ordine
     cronologico (§22 Release Governance EP-012 P0 prima di §23 Complexity Budget EP-016 P1
     — ADR-052 «Alternative considerate»). Edit additivo/non distruttivo (§7 r.7);
     nessuna nuova invariante §7 (restano 18, R.1-R.18). -->

## §22 — Release Governance (v2.19, EP-012, opt-in fuori repo framework)
<!-- profiles: standard, full -->

> Forcing function meccanicamente enforced per il rilascio di versioni del meta-framework.
> Audience: maintainer del framework, NON utenti delle factory derivate. Opt-in via
> `factory.config.yaml.release_governance.battle_test_gate.enabled` (default `false` factory
> derivate; `true` SOLO repo framework da v2.19). Materializza l'azione #1 del Revised Plan
> del premortem v2.18 (T1, Pre-Launch Checklist #1). Nessuna nuova invariante §7: la regola
> vive in §22 come invariante procedurale di release governance.

### §22.1 — Invariante procedurale (forcing function)

**Nessun tag di release del meta-framework senza ≥N RUN-REPORT validi (default N=3) in
`validation/runs/`** firmati dal maintainer dopo aver passato il pre-check meccanico
(ADR-032 §B 5 soglie quantitative) e la review umana (ADR-032 §D 3 criteri qualitativi).

**Forcing function** = regola procedurale meccanicamente enforced che impedisce il
proseguimento di un workflow finché un criterio empirico non è soddisfatto. Pattern
parallelo a [[fail-closed]] applicato alla governance di release.

### §22.2 — Audience

**Maintainer del meta-framework** (chi rilascia versioni del PATTERN). NON utenti
delle factory derivate (che vivono di `enabled: false` di default e non hanno mai
un tag di release del meta-framework da gestire). Pattern coerente con la natura
meta-comando di `/release` (ADR-033 §C): scaffoldato solo nel repo del meta-framework,
mai nelle factory derivate.

### §22.3 — Storia del cambio (promozione opt-in deferred → required)

CHANGELOG v2.15 dichiarò i gate empirici Fase 1.5 / Fase 3a come «opt-in deferred» per
assenza di kanban significativo nel meta-framework e per non bloccare il consolidamento
del PATTERN. v2.19 **ribalta** la dicitura per il gate battle-test: da "opt-in deferred"
a "required" SOLO nel repo framework. La nota storica resta append-only per integrità
(ADR-035 §C). La dicitura "opt-in deferred" originale resta nel CHANGELOG v2.15 per
integrità storica; una nota append-only cita la promozione + ADR-036.

### §22.4 — Backward compat

Il requisito vale **da v2.19 in poi**. Versioni v2.14-v2.18 sono storicizzate come
**"validate on specification, not battle-tested"** (frase canonica, ADR-035 §B).
Pattern coerente con la cumulatività del PATTERN: cambi di processo non sono
retroattivi (ADR-035 §A). Le release storiche restano valide e supportate.

### §22.5 — Override (`--bypass-validation-gate`)

Bypass esplicito disponibile via `/release ... --bypass-validation-gate --reason="<msg>"`
(ADR-033 §E). Produce un marker `[gate-bypassed]` nel CHANGELOG `## Validation evidence`
(ADR-034 §C) + entry `validation/release-gates/<version>/BYPASS.md` con
`deferred_validation: true` e SLA `bypass_sla_releases` (default 1 release di gap).

**Vincolo SLA**: alla release successiva, il gate richiede closure del bypass aperto
(sub-section "SLA bypass colmata" nel CHANGELOG della release successiva, ADR-034 §C
closure pattern). Bypass non chiuso → fail-loud al `/release` della release successiva.

### §22.6 — Auditabilità

Side-channel `validation/release-gates/<version>/`:
- `GATE-REPORT.md` — verdict aggregato (ADR-033 §D step 4).
- `<timestamp>-<verdict>.log` — audit append-only di ogni invocazione (anche `--dry-run`).
- `BYPASS.md` — solo se gate è stato bypassato.

Side-channel `validation/runs/`:
- Una cartella per ogni run di validazione (canonica, da v2.19).
- `validation/runs/TEMPLATE/RUN-REPORT.md` — template scaffoldato canonico.
- `validation/runs/fsc-trasf-demo-2026-05-19/RUN-REPORT.md` — run di reference storico
  (`[REFERENCE-ONLY, not gate-eligible]`).

### §22.7 — Cross-link

- Pattern: [[fail-closed]] (concept esistente, wiki).
- Sinergia: EP-013 (analytics dogfooding) fornisce evidenza quantitativa che integra
  il RUN-REPORT narrativo (ADR-041 §C cross-EP gate — `analytics_events_count > 0`
  obbligatorio quando entrambi i flag sono on).
- Riferimento concept: [[framework-critical-analysis-premortem]] §Sintesi premortem,
  §Ottimizzazioni prioritizzate (P0 verbatim: «imporre almeno tre run reali
  end-to-end prima di ogni nuova versione»).
- Premortem deep-dive T1: `pubblicazioni/premortem-report-v218-rischi.md` §Most
  Dangerous Failure, §Revised Plan #1, §Pre-Launch Checklist #1.

### §22.8 — Operazione canonica «Release Validation Gate»

Vedi §3 (operazioni canoniche): entry «Release Validation Gate» con `status: required`
se `release_governance.battle_test_gate.enabled: true`. Implementata da skill
`.claude/skills/release-validation-gate.md` (5 step deterministici) + comando meta
`.claude/commands/release.md`.

## §23 — Complexity Budget & Deprecations (v2.19, EP-016)
<!-- profiles: minimal, standard, full -->

> Il PATTERN cresce. §23 introduce un contrappeso sottrattivo strutturale: per ogni N sezioni
> aggiunte, almeno 1 rimossa o deprecata. Prima forcing function per la sostenibilità del framework.
> Governance documentale + sottrattiva (inversione del bias additivo del framework). Pattern
> parallelo a §22 (Release Governance): entrambe sono forcing function applicate a dimensioni
> diverse (release validation vs complexity governance). Audience: tutti i derivatori (la regola
> è del PATTERN, non delle factory). **Sezione documentale + governance, niente nuova invariante §7.**
> [^src: wiki/syntheses/framework-critical-analysis-premortem.md §E1]
> [^src: design_&_architecture/decisions/ADR-052.md §A §B §C §D §E §F §G §H]

### §23.1 — Regola N:1

«Per ogni `N` sezioni aggiunte alla versione `vX.Y`, almeno 1 sezione deve essere deprecata
(o rimossa se già deprecata nella versione precedente).»

> **Aggiornamento (2026-06-08, EP-016 US-063, ADR-055 §Revisione):** `N` ricalibrato da 3 a **5**
> (additivo, §7 r.7 — il resto di §23 resta invariato). Il finding empirico di TSK-125
> ([`AUDIT-REPORT.md`](validation/runs/v2.19-section-removal-audit/AUDIT-REPORT.md)) ha dimostrato
> che il bloat del PATTERN (rischio E1) è strutturalmente nei **sotto-blocchi**, nelle regole `R.xN`
> e nelle voci di changelog — **non in sezioni `##` top-level rimovibili** che decrementino
> `count_sections()`. N=3 avrebbe quindi forzato l'archiviazione di sezioni operative attive (il
> contrario del bene). N=5 + esclusione delle sezioni-capability dal trigger «must-remove» mantiene
> la pressione consolidativa sul contenuto realmente rimovibile (round v2.20+, semantica ADR-055 §B/§C).

- **Default `N=5`** (ricalibrato 2026-06-08, ADR-055 §Revisione; era `N=3` in ADR-052 §A §B):
  configurabile via `factory.config.yaml.complexity_budget.rule_n: 5` (meta-framework; default
  disabilitato per le factory derivate, cross-ADR-056). Le **sezioni-capability** (che documentano
  una capability opt-in attiva, es. §22, §23) sono **escluse dal trigger di rimozione obbligatoria**
  mentre la capability è viva — la regola punta a contenuto storico/duplicato/obsoleto reale, non a
  sezioni operative attive (coerente con §23.1 scope soft e «Alternative considerate» di ADR-055).
- **Definizione misurabile di "sezione"**: solo heading top-level `##` in `PATTERN.md`
  (sub-sezioni `###`/`####` NON contano — sono estensione di una sezione esistente). Esclusi
  dal conteggio (whitelist, ADR-052 §C):
  - Heading di indice/TOC (`## Table of Contents`, `## Indice`, `## Sommario`, `## TOC`).
  - Heading di esempi inline (`## Examples`, `## Esempi`).
  - Heading `## Storia` / `## History` / `## Roadmap` / `## Fonti` / `## Note` (cumulativi, non sostanziali).
  - La sezione §23 stessa (self-referential per design, ADR-052 §C §F).
- **Eccezioni**: release patch `x.y.Z` (bug-fix) **non** triggera la regola — nessuna aggiunta/rimozione
  strutturale. Triggera solo minor `x.Y` o major `X` (pattern parallelo a SemVer).
- **Conteggio (algoritmo)** — `count_sections(PATTERN.md)` = numero di righe che iniziano con `## `
  (escluse `### `) il cui heading non è in whitelist. **Calcolo delta + verdict** (ADR-052 §D):
  `ratio = delta_added / max(delta_removed, 1)`; `ratio ≤ N → pass`; `N < ratio ≤ N+1 → warn`;
  `ratio > N+1 → fail`. Edge case: `delta_added=0 ∧ delta_removed>0 → pass` (consolidamento puro);
  `delta_added>0 ∧ delta_removed=0 → fail` se `delta_added>N`, altrimenti `warn` (carry-over deficit).
- **Enforcement**: skill `complexity-budget-check` (TSK-122, ADR-056) + lint **Check 4v** WARNING-only
  (gated `complexity_budget.required_on_release: false`, default; slot "4t" riservato ad ADR-050 §I).
- **Cadenza**: check a ogni release tag minor/major, invocato esplicitamente con `/complexity-budget check`.
- **Scope soft formalizzato** (ADR-052 §E): la regola N:1 **NON** si applica a invarianti `§7 R.N`
  (immutabilità tradizionale), regole `R.xN` (R.C1-C7, R.G1-G6, R.S1-S8, R.A1-A6, R.Q1-Q7 — governate
  dalla sezione di appartenenza), ADR (cumulativi, mai rimossi; pattern «superseded»), entry tabellari
  §3/§5 (granularità diversa). Estensione del scope a v2.20+.

### §23.2 — Sezione Deprecate

*Lista vivente. Aggiornata dal maintainer con il meta-comando `/complexity-budget deprecate`.*

Schema entry (verbatim):

```yaml
### §<numero> <titolo>
- Deprecata da: vX.Y.Z (CHANGELOG link)
- Rimozione attesa: vX.Y.Z (target)
- Motivazione: <slug + 1 riga max>
- Sostituita da: §<numero> <titolo> | nessuna sostituzione (rimozione netta)
- Migration: <link a runbook | "nessuna — rimozione netta">
```

Pattern parallelo a Rust `#[deprecated]` e al deprecation lifecycle delle Python PEP.

*Le prime entries saranno aggiunte in US-063 (TSK-126 — primo round rimozioni v2.19).*

### §23.3 — Governance

| Ruolo | Responsabilità |
|-------|----------------|
| maintainer | esecuzione round rimozione + aggiornamento lista vivente |
| skill `complexity-budget-check` | misurazione automatica delta sezioni + verdict (`pass`/`warn`/`fail`) |
| lint Check 4v | WARNING se ratio violato su pre-release minor/major (slot "4t" riservato ad ADR-050 §I) |
| `/complexity-budget` | meta-comando per `check`, `deprecate`, `status` |

**Cadenza**: check esplicito prima di ogni release tag minor/major con `/complexity-budget check`.
**Esenzione**: marker `[skip-complexity-budget --reason="<motivo>"]` nel CHANGELOG (ADR-052 §B).
**Cross-link**: EP-012 §22 release governance (il gate di rilascio include il complexity budget verdict).

### §23.4 — Storia deprecazioni

Le sezioni rimosse (non solo deprecate) vivono in `PATTERN-historical.md` (TSK-125, ADR-055):
- Storia preservata byte-per-byte (integrità storica, fuori dal contratto attivo).
- Contenuto consultabile via `/pattern-view historical`.
- Non fa parte del contratto attivo `PATTERN.md`.

> Sezioni rimosse dal contratto attivo NON sono sezioni dimenticate: sono documenti storici
> con header note `> Archiviata da PATTERN.md alla versione vX.Y.Z.`

### §23.5 — Self-validation

§23 stessa è una nuova sezione top-level → trigger della regola N:1 che essa introduce. Bilanciamento
(ADR-052 §F, ricalibrato ADR-055 §Revisione 2026-06-08):
- v2.19 P0+P1 aggiunge **2 sezioni `##` top-level**: §22 (Release Governance, EP-012 P0) + §23
  (Complexity Budget, EP-016 P1). Gli EP P1 EP-014/EP-015 estendono sezioni esistenti (§3/§5/§18.7/§20.4) →
  **delta sezioni top-level = 0** (ADR-052 §G).
- **Calcolo con N=5 (ricalibrato)**: `added=2 < N=5` → la regola **non triggera alcuna rimozione
  obbligatoria** → **verdict `pass` con `removed=0`**. Nessuna sezione archiviata in v2.19
  (`PATTERN-historical.md` resta scheletro). Il finding di TSK-125 ha dimostrato che non esistono
  sezioni `##` top-level rimovibili senza forzature (il bloat è nei sotto-blocchi); §22 e §23 sono
  sezioni-capability attive, escluse dal trigger «must-remove».
- Debito di complessità (+2 sezioni) tracciato e monitorato verso v2.20:
  [`complexity/budget-report-v2.19.md`](complexity/budget-report-v2.19.md).

### §23.5.1 — Self-application nel repo del meta-framework (v2.21, EP-016 US-085)

> **Aggiornamento (2026-06-15, EP-016 US-085, TSK-166):** nel repo del meta-framework
> `complexity_budget.required_on_release: true` (promosso da v2.21 in poi). Il meta-framework
> applica a sé stesso la regola N:1 che prescrive alle factory derivate — pattern di self-application
> analogo a `release_governance.enabled` (v2.19, EP-012) e `analytics.dogfooding.enabled` (v2.19,
> EP-013). **Factory derivate restano `required_on_release: false` di default (R.P3 opt-in totale)**;
> il bootstrap le scaffolda con il check disabilitato, comportamento identico a v2.19/v2.20.
>
> **Comportamento Check 4v con `required_on_release: true`**: il check passa da WARNING no-op
> (a flag `false`) a **ERROR** su release minor/major del meta-framework con ratio N:1 violato
> e assenza del marker di esenzione `[skip-complexity-budget --reason="…"]`. Cadenza identica
> a prima: solo pre-release minor/major (skip su patch `x.y.Z`). Le factory derivate con
> `required_on_release: false` (default) non sono impattate — Check 4v resta no-op per loro.
>
> **Non-retroattività**: la promozione è prospettica — v2.19 e v2.20 non vengono rivalutate;
> il check si applica a partire da v2.21 in poi per il meta-framework (ADR-035 §A analogy).

### §23.6 — Cross-link

- §22 (Release Governance, EP-012 P0): pattern parallelo (forcing function) — sezione riservata, TSK-100 human, pending.
- §3 (Operazioni canoniche): entry «Complexity Budget & Deprecations» (indice, cross-ADR-056).
- §7 (invarianti): **invariato a 18** — §23 è governance documentale, non invariante runtime (ADR-052 §H).
- Skill `complexity-budget-check` (TSK-122, ADR-056) + lint Check 4v (slot "4t" riservato ad ADR-050 §I).
- Comando `/complexity-budget` (ADR-056) + `/pattern-view` (ADR-053).
- `PATTERN-historical.md` (TSK-125, ADR-055): storia preservata byte-per-byte.

### §23.7 — Profili di adozione (3 schede, v2.19 EP-016)

Opt-in via comando `/pattern-view <profilo>` (ADR-053). Il PATTERN resta un **file
unico**; i profili sono **viste filtrate** via tag `<!-- profiles: ... -->` posti sotto
ogni header `## §N` (ADR-054). Single source of truth (§8): mai materializzare copie
`PATTERN-minimal.md`. Tag default `full` per qualsiasi sezione senza tag (backward compat).

> Nota numerazione: ADR-054 §G citava «§23.5» per questa scheda, ma §23.5 era già
> occupata da «Self-validation» (TSK-121) → scheda collocata in §23.7 (prassi v2.19:
> prossimo slot libero, coerente con §18.8 e Check 4v).

#### Profilo `minimal` (~8 sezioni)

Il core per usare il framework in modalità knowledge-only / plan-only.
Sezioni: **§0, §1, §2, §3, §5, §7, §13, §23**. Subset intra-sezione (descritti a parole,
non con tag per `###` — granularità fine rinviata a v2.20+, ADR-054 §F):
- **§2 Ruoli** → solo i 5 ruoli core: orchestrator, wiki-keeper, product-manager, lead-architect, tpm (esclude dev-agent, publisher, code-reviewer, sync, …).
- **§3 Operazioni** → solo le 5 op essenziali: scrivi-wiki, scrivi-epica, scrivi-user-story, scrivi-task, apri-question (esclude op opt-in).
- **§5 Frontmatter** → solo i campi core obbligatori (`id`, `status`, `type`).
- **§7 Invarianti** → il subset core ~6: citazione obbligatoria, zero-invenzione, log append-only, scope di scrittura chiuso, single-committer, gate L4 graduato.
- **§13 Topology** → solo knowledge-only / plan-only (esclude full-stack-agents, multi-repo, routing dev).

#### Profilo `standard` (~14 sezioni)

`minimal` + capability mature per team che sviluppano con dev-agent + review.
Aggiunge: **§4** (naming), **§6** (grammatica citazioni), **§16** (sync adapters base),
**§18** (parallel scheduling), **§19** (Code Quality Review), **§21** (versioning).

#### Profilo `full` (~22 sezioni)

Tutto. `standard` + **§8** (state derivation), **§9** (memory), **§10** (wiki maintenance),
**§11** (standards), **§12** (adapter), **§14** (stack modes), **§15** (VCS), **§17**
(publisher), **§20** (compression layer), e **§22** (Release Governance, quando creata da
TSK-100). È la vista di default (identica a leggere `PATTERN.md` integrale).

| Profilo | Sezioni | Audience |
|---|---|---|
| `minimal` | ~8 | nuovo utente, knowledge-only / plan-only; base del PATTERN-in-1-pagina (EP-017) |
| `standard` | ~14 | team operativo con dev-agent + review |
| `full` | ~23 | manutentore / uso completo, tutte le capability opt-in |

---

## §24 — Design Intelligence Layer (v2.21, EP-019, opt-in)
<!-- profiles: full -->

> Capability opt-in che estende EP-008 (UX/UI Review & Design) con coordinamento tematico
> centralizzato (art-director), separazione LLM/generatore deterministico, gate reasoning-first,
> critica strutturata (Critic/Judge) e asse Intention Economy. Default off (R.P3): factory
> v2.20 identica a flag spenti. Dipendenza: `design_intelligence.enabled: true` richiede
> `ux_ui.enabled: true` (fail-loud al boot). **Sezione documentale + capability opt-in, nessuna
> nuova invariante §7** (resta 18, stessa natura di §20/§22/§23). Contabilizza +1 verso N:1
> (ADR-052/ADR-055 §Revisione, `N=5`).
> [^src: design_&_architecture/decisions/ADR-068.md §Decisione]
> [^src: design_&_architecture/decisions/ADR-069.md §Decisione]
> [^src: design_&_architecture/decisions/ADR-070.md §Decisione]
> [^src: design_&_architecture/decisions/ADR-071.md §A §B §C §D]

### §24.1 — Concetti e pipeline

Il Design Intelligence Layer introduce 5 concetti distinti nella factory:

| Concetto | Wiki | Skill |
|---|---|---|
| Art-Director Coordination | [[art-director-coordination]] | `art-director-coordination-protocol` |
| Design Rationale | [[design-rationale]] | gate inline in `ux-ui-design-protocol` Step 2-bis |
| LLM-Generator Separation | [[llm-generator-separation]] | `llm-generator-separation-protocol` + tool `run-generator.sh` |
| Critic/Judge Agent | [[critic-judge-agent]] | sub-passo Step 3-bis in `ux-ui-review-protocol` |
| Intention Economy | inline in Step 3-bis | sotto-dimensione del Critic/Judge |

**Pipeline a 4 fasi** (attiva solo con `design_intelligence.enabled: true`):

```
Fase 1 — Intent
  L'agente ui-designer riceve il brief.

Fase 2 — Art-Director (art-director-coordination-protocol)
  Produce DSL intermedia `art_director_spec` (colori, tipografia, spaziatura,
  gerarchia, varianti) — single-writer del tema. Il fe-dev è read-only sul tema (R.D1).
  Poi: design-rationale gate reasoning-first (art_director → rationale → deliverable, R.D2).

Fase 3 — Generatore deterministico (llm-generator-separation-protocol, condizionale)
  Se generator_tool != none: fe-dev produce spec parametrica → skill invoca
  .claude/tools/run-generator.sh → scaffold deterministico (token budget ~zero).
  Fuori-template → spec custom, generatore non invocato (ADR-069 §D).

Fase 4 — Critic/Judge (sub-passo Step 3-bis di ux-ui-review-protocol, condizionale)
  Se critic_enabled: true: valuta render su 6 principi visivi + asse Intention Economy
  (se rubric_intention_economy: true). Strumento di refinement, NON oracolo (R.D3).
```

### §24.2 — Configurazione (`design_intelligence:` block)

```yaml
design_intelligence:
  enabled: false                   # master switch; richiede ux_ui.enabled: true
  art_director: false              # gate art-director + design-rationale (ADR-068)
  generator_tool: none             # none | plop | yeoman (ADR-069)
  critic_enabled: false            # passo Critic/Judge 6 principi (ADR-070)
  rubric_intention_economy: false  # asse Intention Economy (ADR-070 §E)
```

Tutti i sotto-flag sono inerti se `enabled: false` (gating gerarchico). A tutti i flag
al default: factory identica a v2.20 (backward compat totale, R.P3).

**Validation fail-loud al boot**: se `design_intelligence.enabled: true` AND
`ux_ui.enabled: false` → messaggio canonico: «`design_intelligence` richiede
`ux_ui.enabled: true`» (ADR-071 §B).

### §24.3 — Confine con EP-005 e EP-008

| Capability | Scopo | Output | Sede |
|---|---|---|---|
| EP-005 Visual Oracle | Correttezza funzionale FE («il rendering aderisce alla spec») | Verdict **deterministico** pass/conditional/reject | `visual-oracle-protocol` (Fase 4-bis dev-protocol) |
| EP-008 UX/UI Review | Review euristica (Nielsen 10 + UI 6 + flusso 5) | Findings qualitativi + `rubric_ref` | `ux-ui-review-protocol` Step 3 |
| EP-019 Critic/Judge | Qualità visiva design («è UX-buono vs 6 principi») | Critiche di refinement qualitative (NON oracolo, R.D3) | `ux-ui-review-protocol` Step 3-bis |

Le tre capability sono **complementari nell'ordering** (`develop → visual-oracle → ux-ui-review
→ critic-judge`): nessuna sovrapposizione di scope, runtime cattura condiviso (ADR-017).

### §24.4 — Regole R.D1-R.D3

- **R.D1 — No bypass del canale DSL art-director**: la DSL prodotta da `art-director-coordination-protocol`
  è l'unico canale stilistico autorizzato tra art-director e fe-dev. Il tema non è comprimibile né
  bypassabile; il fe-dev è read-only sul tema. [ADR-068 §C]
  *Nota cross-link compression §20*: la DSL art-director è audit-trail, non comprimibile aggressivamente.

- **R.D2 — Ordine obbligatorio reasoning-first**: l'ordine è `art-director (tema/DSL) →
  design-rationale (reasoning) → produzione (deliverable/codice)`. L'LLM non produce prima
  di dichiarare il rationale strutturato (`decision`, `alternatives_considered`, `rationale`,
  `constraints_applied`, `consequences.resolution_velocity_impact`). [ADR-068 §B; US-074]

- **R.D3 — Il Critic/Judge non è oracolo**: il Critic/Judge Design è strumento di refinement
  qualitativo. Non emette verdict deterministico bloccante; correlazione con giudizio umano
  non garantita. Ancorare a checkpoint umani dove possibile. Ogni finding richiede
  `evidence_zone` (guard evidence-provenance, ADR-063 §B). [ADR-070 §C]

[^src: design_&_architecture/decisions/ADR-071.md §C]

---

## §25 — Semantic Drift Detection (v2.23, EP-031, opt-in L3 / always-on L1)
<!-- profiles: full -->

> Capability di monitoraggio della deriva semantica tra le pagine wiki e le sezioni PATTERN.md
> che referenziano tramite il campo frontmatter `pattern_section:`. Architettura a piramide a tre
> livelli (ADR-EP031-001, GO-MODIFIED, 2026-06-25): L1 staleness (always-on, age-based) →
> L2 LLM-judge (manuale, graceful degradation) → L3 embedding coseno (opt-in, API key richiesta).
> Check 4ag (L1) è **sempre attivo** in `/lint` indipendentemente dalla configurazione.
> Check 4af (L3) è **INFO-only, sperimentale**, non è mai un gate bloccante.
> **Nessuna nuova invariante §7** (resta 18). Complexity budget: §25 è +1 sezione; con N=5
> il ratio 1/1 = 1 ≤ 5 → pass.
> [^src: design_&_architecture/decisions/ADR-EP031-001-semantic-drift-embedding.md §Decisione]

### §25.1 — Architettura a piramide

La rilevazione di deriva semantica è organizzata in tre livelli crescenti di precisione e costo:

```
L1 — Staleness (Check 4ag)         [always-on, zero costo API]
  ▸ Misura: age in giorni dall'ultimo aggiornamento (campo updated_at nel frontmatter)
  ▸ Soglie: age > 180gg → INFO; age > 365gg → WARNING; MISSING-DATE → WARNING
  ▸ Attivazione: automatica nel ciclo /lint, nessuna configurazione richiesta
  ▸ Razionale: proxy oggettivo e a costo zero; una pagina non aggiornata da > 6 mesi
    rischia divergenza man mano che PATTERN.md evolve

L2 — LLM-judge (proxy qualitativo)  [manuale, zero costo API]
  ▸ Misura: score qualitativo [0.0–1.0] assegnato dal modello confrontando body della
    pagina wiki con estratto della sezione PATTERN.md referenziata
  ▸ Trigger: invocazione manuale del comando /semantic-drift-scan
  ▸ Graceful degradation: attivo anche quando l'API embedding è irraggiungibile
  ▸ Scope: corpus ≤ 50 pagine (costo lineare del modello)
  ▸ Razionale: nessun prerequisito di infrastruttura; adeguato per corpora piccoli

L3 — Embedding coseno              [manuale, costo API embedding, opt-in]
  ▸ Misura: similarità coseno tra embedding vettoriale della pagina e dell'estratto PATTERN
  ▸ Trigger: /semantic-drift-scan con wiki_lint.semantic_check.enabled: true + API key
  ▸ Scope: corpus > 50 pagine (costo sublineare grazie a batching API)
  ▸ Razionale: misura metrica riproducibile, indipendente dal modello di giudizio
```

**Decisione ADR-EP031-001 (GO-MODIFIED)**: la piramide è la struttura di riferimento.
L1 è l'unico livello con garanzia always-on. L2 e L3 si escludono per graceful degradation
(se L3 non disponibile → L2; se L2 non disponibile → L1 unico segnale). Il factory derivante
scegli il livello in base a disponibilità API e dimensione corpus; il framework non impone L3.

### §25.2 — Configurazione (`wiki_lint.semantic_check:` block)

```yaml
wiki_lint:
  semantic_check:
    enabled: false           # master switch L3 (R.P3 default off). L1 è SEMPRE attivo.
    similarity_threshold: 0.75  # soglia coseno (provvisoria — calibrazione empirica US-108)
    embedding_model: "voyage-3" # voyage-3 (Anthropic) | text-embedding-3-small (OpenAI)
    cost_warn_usd: 1.0          # gate di conferma esplicita (soglia costo stimato)
    output_report: true         # produce report YYYY-MM-DD in output_report_path
    output_report_path: "code_quality/reports/"
```

- `enabled: false` → L1 (Check 4ag) resta attivo; Check 4af e chiamate API embedding disabilitate.
- `enabled: true` → attiva L3 (Check 4af + chiamate API); L2 usato come fallback se API irraggiungibile.
- La soglia `0.75` è provvisoria: la baseline empirica 2026-06-25 (10 pagine, LLM-judge) mostra
  score medio 0.68 su corpus sotto-soglia; calibrazione su corpus più ampio è US-108 backlog.
- Il gate `cost_warn_usd` è una conferma esplicita analoga a `full_rebuild_cost_warn` di §20:
  nessuna chiamata API viene eseguita senza conferma se il costo stimato supera la soglia.

### §25.3 — Check 4ag e Check 4af (integrazione lint)

I due check si integrano nel ciclo `/lint` (skill `lint-checks`, vedi §10):

| Check | Livello | Severità | Trigger | Gate |
|---|---|---|---|---|
| **4ag** — Staleness threshold | L1 | INFO (>180gg) / WARNING (>365gg o MISSING-DATE) | Ogni `/lint` — always-on | Nessuna configurazione |
| **4af** — Embedding similarity | L3 | INFO-only (mai WARNING né ERROR) | `/lint` solo se `enabled: true` | `wiki_lint.semantic_check.enabled: true` |

Entrambi i check sono **non-bloccanti**: non impediscono la progressione di TSK, US, EP,
release gate o wave dispatch. Check 4af è classificato `sperimentale` fino alla calibrazione
empirica della soglia (US-108).

Il campo frontmatter rilevante per i check è `pattern_section: "§N"`: le pagine wiki senza
questo campo sono escluse silenziosamente dalla scansione e riportate nel report come
«non scansionate».

### §25.4 — Convenzione frontmatter `pattern_section:`

Le pagine wiki che documentano una specifica sezione PATTERN.md possono dichiarare la loro
intenzione tramite il campo opzionale `pattern_section:` nel frontmatter YAML:

```yaml
---
title: "Compressione output: approccio Caveman"
pattern_section: "§20"  # sezione PATTERN.md di riferimento
updated_at: "2026-06-20"
---
```

- **Obbligatorietà**: il campo è **opzionale**. La sua assenza non è un errore di lint.
- **Scope**: adatto a pagine `wiki/syntheses/`, `wiki/concepts/`, `wiki/runbooks/` che
  documentano o sintetizzano una sezione PATTERN.md specifica.
- **Esclusione esplicita**: `wiki/entities/` e `wiki/getting-started/` non sono mappate su
  sezioni PATTERN per design (scope diverso).
- **Falsi positivi**: il mapping errato (es. `pattern_section: "§18"` su una pagina che tratta §3)
  produce falsi positivi nelle scansioni. ADR-EP031-001 raccomanda di leggere il body prima
  dell'assegnazione — mai inferire dal titolo.

### §25.5 — Confine con §10 (wiki maintenance)

| Meccanismo | Sede | Segnale |
|---|---|---|
| §10 wiki feedback loop | `/lint` Check 1-4p (existing) | Orphan link, dangling wikilink, struttura mancante |
| §25 Staleness (L1) | `/lint` Check 4ag (always-on) | Pagine non aggiornate rispetto all'età |
| §25 LLM-judge (L2) | `/semantic-drift-scan` (manuale) | Deriva semantica qualitativa vs PATTERN |
| §25 Embedding (L3) | `/semantic-drift-scan` (manuale, opt-in) | Deriva semantica metrica vs PATTERN |

§25 **non sostituisce** §10: i check strutturali (orphan, dangling) restano in §10; §25 aggiunge
un livello semantico ortogonale. Il report `/semantic-drift-scan` è side-channel di
`code_quality/reports/` — analogo a §19 CQRL — e non modifica mai le pagine wiki direttamente
(rispetta §7 r.7: append-only, no auto-rewrite).

## §26 — Runtime Contextual Suggestions (v2.24, EP-033)

### §26.1 — Problema e motivazione

La factory è storicamente pull-based: l'utente chiede (`/help`, `/query`), la factory risponde.
EP-032 ha risolto la scopribilità intenzionale con `/help`. Rimane aperto il caso più frequente
in pratica: l'utente sta eseguendo un task e non sa che esiste una capability adiacente che
migliorerebbe il risultato o preverrebbe un problema.

Esempi di gap reali:
- Un dev-agent completa un TSK `layer=fe` senza che nessuno suggerisca `/a11y` o `/ux-ui-review`.
- `/lint` trova WARNING staleness senza suggerire `/semantic-drift-scan`.
- Si apre uno sprint con TSK FE senza segnalare che `fe_correctness.visual_oracle.enabled` è spento.

### §26.2 — Architettura a tre proposte

| Proposta | Punto di iniezione | Effort | Coverage |
|---|---|---|---|
| A — Orchestrator Fase 6 | `/run` (fine wave dispatch) | S | Sprint planning, tutti i TSK in coda |
| B — dev-handoff post-exec | Fine di ogni TSK | S | Post-esecuzione per layer fe/be/db/qa/docs |
| C — Hook Stop `suggest-next.py` | Dopo ogni comando configurato | M | Bypass `/run` e `/dev` |

A+B coprono il ciclo normale (90% dei casi) con effort S + S e rischio di regressione nullo
(modifica a file esistenti). C aggiunge copertura per utenti avanzati che bypassano il ciclo.

### §26.3 — Proposta A: Orchestrator Fase 6

`Fase 6 — Capability Relevance Check` aggiunta in fondo a `orchestrator.md`. Si attiva
al termine del wave dispatch; se non ci sono TSK `status: todo` → no-op silenzioso.

**6 regole di suggerimento:**

| Condizione rilevata | Suggerimento emesso |
|---|---|
| Sprint ha TSK `layer=fe` + `fe_correctness.visual_oracle.enabled: false` | Considera `/visual-oracle` |
| Sprint ha TSK `layer=fe` + `a11y.enabled: false` | Considera `/a11y` |
| ≥3 TSK done nella settimana + `analytics.measurement.enabled: true` | Considera `/analytics` |
| ≥1 epic `status: open` senza entry premortem in `wiki/log.md` | Considera `/premortem <epic-id>` |
| `wiki/log.md` ultima entry > 30 giorni fa | Considera `/semantic-drift-scan` o `/lint` |
| Sprint ha TSK `layer=fe/be` + `code_quality.enabled: false` | Considera `/review` |

Gate: prima di emettere un suggerimento, verificare che `.claude/commands/<comando>.md` esista.
Output condizionale: la sezione `## Suggerimenti contestuali` compare solo se ≥1 suggerimento supera il gate.

### §26.4 — Proposta B: dev-handoff post-esecuzione

Sezione `## Suggerimento post-esecuzione` aggiunta in fondo a `dev-handoff.md`. Condizionale:
compare nell'output dell'handoff solo se il layer del TSK ha capability adiacenti rilevanti
non ancora eseguite sulla US corrente (deduplication via `wiki/log.md`).

| Layer | Suggerimenti (se comando installato + non già eseguito per questa US) |
|---|---|
| fe | `/a11y`, `/ux-ui-review`, `/visual-oracle` (se rispettivi flag abilitati) |
| be | `/review` (focus robustezza) |
| db | `/review`, nota backup strategy se migration DDL |
| qa | `flakiness-detection-protocol` se test asincroni |
| docs | `/lint` per verifica integrazione wiki |

Max 3 suggerimenti per handoff. Gate installazione identico a Proposta A.

### §26.5 — Proposta C: Hook Stop `suggest-next.py`

Script Python (`~90 righe`, solo stdlib) invocato dall'hook Stop di Claude Code dopo i comandi
`/dev`, `/lint`, `/run`, `/review`. Opera fuori dal contesto LLM: regole statiche, deterministico.

```
matcher: /(dev|lint|run|review)
command: python3 "$CLAUDE_PROJECT_DIR/.claude/tools/suggest-next.py" --command="$CLAUDE_COMMAND"
timeout: 5
non-bloccante: 2>/dev/null || true
```

Flag `--dry-run` per debug. Adapter-specific: l'hook Stop è specifico di Claude Code;
documentare adattamento per Cursor/Aider in testa allo script.

### §26.6 — Invarianti (nessuna nuova rispetto a §7)

- **Suggerimenti non bloccanti**: non interrompono mai il flusso operativo. Sono informativi.
- **Gate installazione**: mai suggerire capability il cui comando non esiste nella factory.
- **Output condizionale**: nessuna sezione vuota o placeholder — o c'è almeno un suggerimento rilevante, o la sezione non compare.
- **Tono non imperativo**: "Considera", "Potresti valutare" — mai "Devi", mai imperativo.
- **Backward compat totale** (R.P3): factory derivate senza le capability suggerite → tutte le check falliscono silenziosamente → comportamento identico a v2.23.

### §26.7 — Artefatti scaffoldati in factory derivate

| Artefatto | Tipo | Note |
|---|---|---|
| `orchestrator.md` | modifica | Aggiunta Fase 6 in fondo |
| `dev-handoff.md` | modifica | Aggiunta sezione post-exec in fondo |
| `.claude/tools/suggest-next.py` | nuovo | Script Python hook-based (Proposta C) |
| `.claude/settings.json` | modifica | Hook Stop con matcher `/(dev|lint|run|review)` |

Nessun nuovo agente. Nessun nuovo campo `factory.config.yaml` per A e B (sempre attivi una
volta scaffoldati). Proposta C può essere gated da `runtime_suggestions.hook.enabled: false`
se la factory derivata vuole disabilitarla senza modificare `settings.json`.

Fonte: EP-033 | [[runtime-contextual-suggestions]] | [[runtime-suggestions-proposal-comparison]]

---

## §27 — Prototype Generation Layer (v2.26, EP-035)

### §27.1 — Problema e motivazione

La factory copre l'intero ciclo spec → codice → validazione per il design, ma si fermava
alle spec testuali: `ui-designer` (EP-008) produce wireframe/spec in Markdown, `figma-sync`
(v2.9) legge da Figma (solo read), `visual-oracle` (EP-017) e `functional-oracle` (EP-018)
verificano artefatti esistenti. Mancava il passo generativo: nessun agente produceva
l'artefatto grafico renderizzabile (prototipo cliccabile, file di design, componente reale)
che collega la spec testuale all'artefatto percepibile dall'utente.

EP-035 chiude questo gap introducendo un layer generativo adattivo: a partire da una spec
testuale (US, TSK o intent in linguaggio naturale), il **Prototype Generation Layer** produce
un prototipo nel backend disponibile piu' adatto, con cascata di fallback che garantisce sempre
almeno un artefatto self-contained (`html` T0 — INV-1).

**Estensione semantica di §24**: EP-035 non duplica il Design Intelligence Layer (§24/EP-019)
ma lo estende semanticamente aggiungendo il layer generativo. Se `design_intelligence.art_director`
e' attivo, il prototipo eredita il tema/tipografia/spacing coordinati dall'art-director DSL. Se
spento, la generazione procede in modo standalone. Il ruolo Prototyper e' distinto da
`ui-designer` (che produce spec testuali): il Prototyper consuma la spec e produce l'artefatto
renderizzabile, senza self-eval (INV-4) e senza riscrivere la spec sorgente (INV-3).

### §27.2 — Artefatti scaffoldati in factory derivate

| Artefatto | Tipo | Analogia con esistente |
|---|---|---|
| `agents/prototype-generator.md` | agente Prototyper (opt-in, gated) | `figma-sync`, `ui-designer` |
| `skills/prototype-generation-protocol.md` | skill 5 fasi, provider-agnostic | `publisher-protocol` (v2.10) |
| `skills/backend-resolver.md` | skill cascata detection + degradazione | `branch-resolver` (EP-034), `stack-detector` |
| `skills/html-prototype-mapping.md` | skill mapping provider-specific html (T0) | `github-mapping` (v2.10) |
| `skills/react-mapping.md` | skill mapping provider-specific React (T1) | `github-mapping` |
| `skills/figma-mapping.md` | skill mapping provider-specific Figma (T2) | `github-mapping` |
| `skills/penpot-mapping.md` | skill mapping provider-specific Penpot (T3) | `github-mapping` |
| `commands/prototype.md` | `/prototype <US-id\|TSK-id\|"intent">` | `/kanban-publish`, `/dev` |
| `commands/prototype-status.md` | `/prototype-status` — backend risolto + disponibilita' | `/vcs-status` (EP-034) |
| `factory.config.yaml` | blocco `prototyping:` (master switch + backends) | blocchi `compression:`, `code_quality:` |

Il pattern architetturale e' **provider-agnostic + provider-specific**: `prototype-generation-protocol`
non conosce Figma o Penpot; aggiungere un nuovo backend richiede solo una skill `*-mapping` +
una voce nel `fallback_chain`, senza modificare il protocollo core. Analogo al pattern
`publisher-protocol` / `github-mapping` (v2.10).

### §27.3 — Configurazione (blocco `prototyping:`)

Blocco verbatim da `factory.config.yaml` (righe 890–944):

```yaml
prototyping:
  enabled: false                    # master switch EP-035 (R.P3 default off)
  backend: auto                     # auto | html | react | figma | penpot
  fallback_chain: [figma, penpot, react, html]  # cascata di fallback (html = terminale garantito INV-1)
  degrade_policy: notify            # notify (default) | strict (STOP+gate umano se preferito UNAVAILABLE)
  fidelity: interactive             # static | interactive (default) | animated
  design_source: auto               # auto (cerca design-spec.md) | <path> | none
  art_director: inherit             # inherit | on | off (EP-019 DSL opt-in)
  output_path: "output/prototypes"  # directory root artefatti generati
  oracle_handoff: true              # Fase 4: suggerisce oracle/reviewer appropriato per backend
  scheduler_domain: prototype       # dominio scheduler (prototype, opt-in default false)
  backends:
    html:                           # T0 — fallback terminale garantito (INV-1), zero prerequisiti
      css_strategy: tailwind-cdn    # tailwind-cdn (default) | inline | vanilla
      single_file: true             # INVARIANTE INV-6 — non overridabile; un solo file HTML self-contained
    react:                          # T1 — production-ready (richiede code_path FE)
      component_lib: shadcn         # shadcn (default) | radix | mui | custom
      storybook: true               # true (default) → genera storie Storybook per ogni stato
      target: null                  # null = output_path; path = directory nel code_path target
    figma:                          # T2 — alta fedelta' (richiede MCP figma autenticato)
      mcp_server: "figma"           # nome MCP server Figma (deve essere installato e autenticato)
      file_key: ""                  # chiave file Figma target; "" → crea nuovo file
    penpot:                         # T3 — alta fedelta' open-source (richiede MCP penpot)
      mcp_server: "penpot"          # nome MCP server Penpot (deve essere installato e autenticato)
      instance_url: ""              # URL istanza Penpot (es. https://design.penpot.app)
```

Note di configurazione:

- `enabled: false` e' l'unico campo che attiva la capability (R.P3 opt-in). Tutti gli altri
  campi hanno default funzionanti — basta impostare `enabled: true` per il comportamento base.
- `backend: auto` attiva il `backend-resolver` che proba (ASSE 1: MCP figma/penpot;
  ASSE 2: stack-detector per react) e sceglie il backend piu' fedele disponibile.
- `degrade_policy: notify` (default) — il resolver degrada silenziosamente con marker
  `BACKEND_DEGRADED` in chat e log. `strict` => STOP + gate umano.
- `art_director: inherit` lega la capability a `design_intelligence.art_director` di §24;
  impostare `on`/`off` per override locale.
- `oracle_handoff: true` abilita la Fase 4 del protocollo: al termine della generazione,
  l'agente suggerisce il reviewer piu' adatto (visual-oracle, functional-oracle, ux-ui-review,
  a11y) in base al backend usato e alla fidelity prodotta.
- Per factory con `code_paths: []` vuoto (es. repo meta-framework reflexivo), il backend
  `react` (T1) risulta UNAVAILABLE (probe ASSE 2 senza target FE) e il resolver degrada a
  `html` (T0). Comportamento atteso e documentato.

### §27.4 — Invarianti locali (INV-1..INV-6)

Le seguenti invarianti si applicano alla capability EP-035 in tutte le factory derivate
che la attivano. Non fanno parte delle 18 invarianti globali §7 (invariate).

- **INV-1**: backend `html` sempre disponibile come fallback terminale — la capability non
  puo' hard-fail; se tutti i backend superiori falliscono, viene prodotto sempre un file
  HTML self-contained.
- **INV-2**: mai bloccare su MCP non autenticato — il resolver degrada con marker
  `BACKEND_DEGRADED` e prosegue (salvo `degrade_policy: strict` che chiede gate umano
  esplicito).
- **INV-3**: `prototype-generator` e' read-only verso la spec sorgente — non riscrive
  i file prodotti da `ui-designer` o da qualunque altro agente upstream.
- **INV-4**: no self-eval — il generatore non giudica il proprio output; la validazione
  e' delegata interamente agli agenti oracle/reviewer/a11y esistenti (analogo ad ADR-063
  anti-fabbricazione).
- **INV-5**: default off (R.P3) — a `prototyping.enabled: false` la factory v2.26 e'
  identica alla v2.25 (backward compat totale; nessun nuovo agente scaffoldato, nessun
  comando disponibile).
- **INV-6**: `single_file: true` per backend `html` e' un'invariante di self-containment
  non overridabile — un solo file HTML con tutto inline (unica eccezione ammessa:
  Tailwind CDN se `css_strategy: tailwind-cdn`), apribile offline senza server.

### §27.5 — ADR-EP035 accettati

Tutti i sei ADR EP-035 sono accettati (GO). ADR-EP035-001 (cascata backend adattiva) e'
l'ADR fondante: stabilisce che la capability e' multi-backend con fallback, non single-backend
hard-coded.

| ADR | Titolo | Decisione |
|---|---|---|
| **ADR-EP035-001** | Cascata backend adattiva vs singolo backend hard-coded | GO cascata adattiva — `backend-resolver` + `fallback_chain` configurable |
| ADR-EP035-002 | `html` single-file come fallback terminale garantito | GO — INV-1 + INV-6 |
| ADR-EP035-003 | Riuso pattern publisher (protocol agnostic + mapping specifico) | GO riuso — `prototype-generation-protocol` + `*-mapping` skills |
| ADR-EP035-004 | §27 nuova sezione PATTERN vs estendere §24 | GO sezione nuova — estende semanticamente §24 senza duplicarlo |
| ADR-EP035-005 | `degrade_policy` default `notify` vs `strict` | GO `notify` — minor friction, massima disponibilita' |
| ADR-EP035-006 | Figma vs Penpot primo nel `fallback_chain` di default | GO Figma prima (adozione maggiore); Penpot per ambienti self-contained-first |

### §27.6 — Integrazione con capability esistenti

EP-035 si integra con le capability esistenti senza duplicarle:

- **§24 Design Intelligence Layer (EP-019)**: se `design_intelligence.art_director: true`,
  il Prototyper eredita il tema/tipografia/spacing coordinati dall'art-director DSL (`art_director: inherit`).
  EP-035 e' l'estensione generativa di §24: §24 produce la spec di design, §27 produce
  l'artefatto renderizzabile da quella spec.
- **§26 Runtime Contextual Suggestions (EP-033)**: la Fase 6 dell'orchestrator include
  una regola push — "TSK layer=fe con spec testuale ma senza prototipo associato → considera
  `/prototype`". Handoff post-exec del dev-handoff segnala lo stesso.
- **visual-oracle (EP-017)**: backend `figma` e `penpot` (alta fedelta') suggeriscono in
  Fase 4 il visual-oracle come validatore naturale del prototipo prodotto.
- **functional-oracle (EP-018)**: backend `react` (T1) suggerisce in Fase 4 il
  functional-oracle per la validazione dell'interattivita' dei componenti generati.
- **a11y (EP-012/v2.18)**: `oracle_handoff: true` include sempre un suggerimento a11y
  in Fase 4 indipendentemente dal backend, in quanto il prototipo e' un artefatto UI
  consumabile dall'utente finale.
- **Scheduler (v2.11)**: nuovo dominio `prototype` configurabile in `scheduler.domains`
  (opt-in/out come tutti gli altri domini — `develop`, `lint`, `review`, ecc.). Default
  opt-in quando `prototyping.enabled: true`.
- **figma-sync (v2.9)**: a livello di sistema l'integrazione diventa bidirezionale —
  `figma-sync` legge da Figma (read), `prototype-generator` backend `figma` scrive su
  Figma (write via MCP) — round-trip design completo.

## §28 — Tavola Rotonda (modalita' multi-agente collaborativa)
<!-- profiles: full -->

### §28.1 — Scopo e quando usarla

La Tavola Rotonda e' una modalita' operativa **opt-in** (EP-039, v2.27) per la
risoluzione collaborativa di problemi **genuinamente complessi e multi-dominio** che
richiedono la sintesi di prospettive eterogenee — architettura, sicurezza, UX, delivery —
impossibile da ottenere con un singolo agente o con una pipeline a layer fissi.

**Usare la Tavola Rotonda quando:**

- Il problema e' multi-dominio e la soluzione richiede la sintesi di ≥2 aree di competenza
  (es. scelta architetturale con impatto su sicurezza + UX + costi operativi).
- Il rischio di anchoring e groupthink e' alto — una pipeline lineare non produce
  controllo incrociato, i rischi emergerebbero in produzione invece che prima.
- La decisione e' irreversibile o molto costosa da cambiare in seguito.
- Il problema ha ≥2 alternative concrete non ovviamente superiori l'una all'altra.

**Non usare la Tavola Rotonda quando:**

- La risposta e' lookup (wiki, ADR gia' accettato, regola codificata): usa `/query`.
- Il problema ha un solo esperto di dominio rilevante: usa il singolo dev-agent.
- Il costo di una sessione (5-15x un task normale) e' sproporzionato all'impatto della
  decisione.

Vedi il decision tree completo: [`wiki/runbooks/tavola-rotonda.md`](wiki/runbooks/tavola-rotonda.md).

### §28.2 — Componenti

| Componente | File | Responsabilita' |
|---|---|---|
| **Moderatore** | `.claude/agents/tavola-rotonda-moderatore.md` | Gestisce il protocollo a 5 fasi; unico writer del blackboard; non esprime opinioni di merito in Fasi 1-3; assume il ruolo di aggregatore in Fase 4 |
| **Partecipanti** | qualunque agente in `.claude/agents/<slug>.md` | Producono posizioni indipendenti in Fase 1 e interventi argomentati in Fase 2; comunicano solo tramite la lavagna (no messaggi diretti) |
| **Critico** | un agente della lista partecipanti (obbligatorio, R.TR2) | Mandato esplicito di dissenso attivo: identifica assunzioni fragili, scenari di failure, domande dirompenti; ha priorita' di intervento in Fase 2; non convergere per default |
| **Blackboard** | `wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md` | File strutturato con sezioni `## Posizioni Fase 1` / `## Accordi (congelati)` / `## Punti Aperti` / `## Sintesi`; formato normativo ADR-EP039-001; single-writer (solo moderatore) |
| **Registro decisioni** | blackboard completo di `## Sintesi` | Artefatto persistente della sessione in `wiki/decisions/`; sempre prodotto in Fase 4 (R.TR1 — non opt-in) |

### §28.3 — Protocollo a 5 fasi (sintesi normativa)

Il protocollo completo e' definito in `.claude/skills/tavola-rotonda-protocol.md`.
Le fasi sono sequenziali; il fallimento di un passo blocca la fase.

| Fase | Nome | Output chiave |
|---|---|---|
| **Fase 0** | Setup | Blackboard inizializzato, topic riformulato, criteri di successo, partecipanti verificati, Critico assegnato, budget confermato |
| **Fase 1** | Posizioni iniziali indipendenti | Ogni agente produce una posizione **in isolamento** (R.TR3) — nessun agente vede le posizioni degli altri prima che tutti abbiano risposto; posizioni trascritte verbatim nel blackboard |
| **Fase 2** | Confronto | Il Critico interviene per primo; gli altri agenti producono critiche, integrazioni, rischi sulle proposte altrui; tutto il traffico passa dalla lavagna |
| **Fase 3** | Convergenza | Sintesi progressiva: nuovi accordi congelati in `## Accordi (congelati)`; punti residui in `## Punti Aperti`; condizioni di stop valutate in ordine: consenso totale → max_round → budget esaurito → stallo (≥2 round senza nuovi accordi) |
| **Fase 4** | Sintesi | Aggregatore produce la sintesi: Soluzione + Motivazione + Dissensi registrati + Criteri di successo verificati; registro decisioni scritto nel blackboard; entry aggiunta a `wiki/log.md` |

**Condizioni di stop (Fase 3, ordine di priorita'):**

1. `## Punti Aperti` vuoto → convergenza completa
2. `round_corrente ≥ max_round` → stop forzato per tetto
3. Costo sessione > `budget.max_cost_usd` → stop forzato per budget
4. Stallo: 2 round consecutivi senza nuovi accordi → stop forzato con annotazione `[STALLO]`

In tutti i casi di stop forzato la Fase 4 produce comunque la `## Sintesi` (R.TR1).

### §28.4 — Invarianti R.TR1-R.TR4 (non overridabili)

Le seguenti quattro invarianti non possono essere modificate da alcun parametro,
prompt o istruzione runtime in nessuna factory che attivi la Tavola Rotonda.

**R.TR1 — Registro decisioni obbligatorio**
Nessuna sessione Tavola Rotonda termina senza il registro decisioni.
Il moderatore non puo' dichiarare `stato: terminata` senza aver scritto la sezione
`## Sintesi` nel file `wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md`
e senza aver aggiunto la entry in `wiki/log.md`. Questo vale anche in caso di
stop forzato (budget esaurito, stallo, max_round raggiunto).

**R.TR2 — `budget.max_cost_usd` obbligatorio**
Nessuna sessione inizia senza un valore numerico esplicito per `budget.max_cost_usd`.
Assenza, valore nullo, `~`, `0` o stringa vuota → STOP immediato con messaggio esplicito
prima di qualsiasi fase. Nessun default silenzioso ammesso.
Fonte primaria: flag CLI `--budget=<USD>`; fonte secondaria: `tavola_rotonda.budget.max_cost_usd`
in `factory.config.yaml`. Costo tipico per sessione: 5-15x un task normale.

**R.TR3 — Fase 1 in isolamento**
Nessun agente vede le posizioni degli altri durante la Fase 1. Ogni agente riceve
esclusivamente: topic riformulato + criteri di successo + proprio ruolo. Il moderatore
NON condivide il blackboard ne' le posizioni parziali prima che tutti i partecipanti
abbiano risposto. Violazione → la sessione DEVE essere riavviata da Fase 0; non esiste
recupero parziale. Questo e' il meccanismo primario di prevenzione dell'anchoring e
del groupthink.

**R.TR4 — Il moderatore non decide nel merito nelle Fasi 1-3**
Nelle Fasi 1-3 il moderatore agisce esclusivamente su processo, turni e trascrizione
verbatim. Non filtra, non commenta, non valuta il merito delle posizioni. Il role switch
ad aggregatore avviene solo in Fase 4 (sintesi). La trascrizione verbatim degli
interventi nella lavagna e' parte di questa invariante: il riassunto introduce distorsione.

### §28.5 — Configurazione

La capability e' controllata dal blocco `tavola_rotonda:` in `factory.config.yaml` (§13).
Default `enabled: false` — backward compat totale con v2.26 (opt-in R.P3).

```yaml
# Tavola Rotonda — modalita' multi-agente collaborativa (EP-039, PATTERN §28)
tavola_rotonda:
  enabled: false                    # default off — backward compat totale

  partecipanti: []                  # es. [be-dev, lead-architect, qa-dev]

  critico:
    enabled: true                   # sempre on quando abilitata
    mode: dedicated                 # dedicated | rotation

  max_round: 4                      # obbligatorio — nessuna sessione illimitata

  stop_su_consenso: true
  definizione_consenso: unanimity   # unanimity | supermajority | no_blocking_objection

  meccanismo_decisione: ibrido      # sintesi_moderatore | voto | voto_pesato | consenso | ibrido

  budget:
    max_cost_usd: ~                 # OBBLIGATORIO se enabled: true — fail se assente (R.TR2)
    max_tokens: ~                   # opzionale
    max_latency_s: ~                # opzionale

  topologia: lavagna                # lavagna (default, hub-and-spoke) | grafo_completo (sconsigliato)
  sintesi_progressiva: true         # riassunto accordi/punti-aperti a ogni round
```

Note di configurazione:

- `enabled: false` e' l'unico campo che attiva la capability. A flag spento la factory
  v2.27 e' identica alla v2.26 (backward compat totale; agente e skill non invocabili
  dal runner automatico, comando `/tavola-rotonda` disponibile ma non auto-attivato).
- `budget.max_cost_usd: ~` e' il valore di configurazione permanente raccomandata.
  Se assente, va fornito obbligatoriamente a ogni sessione via `--budget=<USD>` (R.TR2).
- `partecipanti: []` — selezione esplicita v1 (MVP). La selezione automatica per dominio
  del topic (`partecipanti: auto`) e' esclusa dall'MVP di EP-039; prevista per v2.
- `critico.mode: rotation` — il ruolo Critico ruota tra i partecipanti nei round
  successivi al primo (utile per sessioni con ≥3 agenti, evita la stanchezza del Critico).
- `topologia: grafo_completo` e' sconsigliato in v1: la comunicazione diretta tra agenti
  (senza moderatore) produce contesti O(n×m) e bypassa le invarianti di trascrizione
  verbatim. Usare solo con piena consapevolezza delle implicazioni.

### §28.6 — File chiave

| Tipo | Path |
|---|---|
| **Agente moderatore** | `.claude/agents/tavola-rotonda-moderatore.md` |
| **Skill protocollo** | `.claude/skills/tavola-rotonda-protocol.md` |
| **Comando** | `.claude/commands/tavola-rotonda.md` |
| **Runbook** | `wiki/runbooks/tavola-rotonda.md` |
| **ADR normativo blackboard** | `design_&_architecture/decisions/ADR-EP039-001-blackboard-format.md` |
| **Concept tavola-rotonda** | `wiki/concepts/tavola-rotonda.md` |
| **Concept blackboard-architecture** | `wiki/concepts/blackboard-architecture.md` |
| **Concept multi-agent-debate** | `wiki/concepts/multi-agent-debate.md` |
| **Registro decisioni (runtime)** | `wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md` |

### §28.7 — Integrazione con capability esistenti

EP-039 si integra con le capability esistenti senza duplicarle:

- **§18 Parallel Scheduler (v2.11)**: la Tavola Rotonda non usa il DAG scheduler per le
  sessioni — il moderatore gestisce direttamente il lancio sequenziale/parallelo dei
  partecipanti tramite sub-task (Fase 1 parallelo, Fase 2 Critico-prima poi parallelo).
  Il dominio `tavola-rotonda` e' escluso dallo scheduler automatico; la sessione e'
  invocata sempre esplicitamente.
- **§22 Release Governance (v2.19)**: la capability e' gated da benchmark pre-release
  (TSK-294, verdict `pass`) prima del bump di versione. Questo e' il modello di release
  validation applicato anche a §28: nessun rilascio senza evidenza empirica.
- **§24 Design Intelligence Layer (EP-019)**: la Tavola Rotonda puo' essere usata per
  le decisioni di design complesse che l'art-director non riesce a risolvere unilateralmente.
  Il registro decisioni `wiki/decisions/` diventa input per gli ADR successivi.
- **Token Ledger (EP-022)**: il costo di ogni sessione e' visibile inline via
  `show-session-tokens.py`. Il `budget.max_cost_usd` e' il guardrail di spesa; il Token
  Ledger e' lo strumento di osservabilita' del consumo reale durante la sessione.
- **wiki/decisions/ (R.TR1)**: il blackboard completato e' il registro decisioni naturale
  della factory — stesso layer `wiki/decisions/` usato da altri meccanismi di governance.
  La query `/query` lo indicizza automaticamente come fonte L2.

### §28.8 — ADR-EP039-001 accettato

| ADR | Titolo | Decisione |
|---|---|---|
| **ADR-EP039-001** | Formato normativo del blackboard | GO — file strutturato in `wiki/decisions/` con 9 campi frontmatter obbligatori + 3 sezioni (`## Posizioni Fase 1`, `## Accordi (congelati)`, `## Punti Aperti`) + `## Sintesi` aggiunta in Fase 4; single-writer (solo moderatore, R.TR4); UUID v4 come `session_id` |

Fonte: EP-035 | [[prototype-generation-capability]] | [[ep-035-prototype-generation-integration]]

---

## §29 — Factory Scalability Patterns (v2.27, factory-optimization-2026-07-07)

Questa sezione documenta i pattern architetturali introdotti dalla sessione di ottimizzazione
della factory (2026-07-07) che risolvono tre problemi di scalabilità identificati:

1. **Orchestrator troppo grasso** — ogni nuova EP aggiungeva logica di dispatch inline.
2. **Routing hardcoded** — aggiungere un agente richiedeva modifiche in più file.
3. **Tracciabilità wave limitata** — WAVE_ID generato ma non propagato al log umano.

### §29.1 — Thin Orchestrator + Fat Dispatch Policy

**Pattern**: estrarre tutta la logica di dispatch condizionale dall'orchestrator in una
skill dedicata `dispatch-policy.md`. L'orchestrator diventa un thin dispatcher che
invoca la skill senza replicarne il contenuto.

**Benefici**:
- Aggiungere una nuova EP di routing richiede modificare **solo** `dispatch-policy.md`.
- L'orchestrator resta ≤ 100 righe — comprensibile a colpo d'occhio.
- Single-writer chiaro: ogni sezione di `dispatch-policy` è firmata dalla EP che la introduce.

**File chiave**:
- `.claude/skills/dispatch-policy.md` — 8 sezioni numerate, una per capability di dispatch
- `.claude/agents/orchestrator.md` — thin (< 100 righe), punta a `dispatch-policy` §1-§7

**Invariante**: ogni nuova EP che introduce logica di routing DEVE aggiungere una sezione
numerata a `dispatch-policy.md` e NON espandere `orchestrator.md`.

### §29.2 — Capability Advertisement

**Pattern**: ogni agente dichiara nel frontmatter YAML un blocco `capabilities: [...]`
con slug descrittivi. Il blocco è opzionale e additivo — backward compat totale.

```yaml
capabilities:
  - <capability-slug>   # commento opzionale
```

**Benefici**:
- Tool e check di lint possono derivare "chi fa cosa" da YAML senza leggere il body testuale.
- `lint-checks` Check 4ai usa la lista per validare tool/skill/command reference.
- Routing futuro può essere basato su capability match invece di agent-name hardcoding.
- Il registro slug in `dispatch-policy.md §8` è la single source of truth del vocabolario.

**File chiave**:
- `.claude/agents/*.md` — tutti i 27 agenti dichiarano `capabilities:`
- `.claude/skills/dispatch-policy.md §8` — registry completo degli slug per layer
- `.claude/skills/lint-checks.md Check 4ai` — validator che usa tool/skill/command reference

**Invariante**: `capabilities:` è documentativo, non autorizzativo. Non configura permessi
né sostituisce le regole di scope nei body degli agenti.

### §29.3 — WAVE_ID Log Propagation

**Pattern**: il WAVE_ID (già generato dal parallel scheduler negli analytics events) viene
propagato anche nel log umano `wiki/log.md` via il template `wave` di `wiki-log-entry.md`.

**Formato WAVE_ID**: `W-<sprint>-<level>-<YYYYMMDD-HHMMSS>`

**Benefici**:
- Correlazione retrospettiva costo/tempo per wave (join WAVE_ID tra log.md e analytics events).
- Auditabilità delle wave: ogni entry di log wave ha un ID univoco.
- Il template `develop` del dev-agent include `wave: <wave_id>` opzionale per tracciare
  il TSK alla wave che lo ha generato.

**File chiave**:
- `.claude/skills/wiki-log-entry.md` — template `wave` e `develop` con WAVE_ID
- `.claude/skills/parallel-scheduling.md` — già genera `wave_id` negli analytics events

### §29.4 — Agent Infrastructure Check (Check 4ai)

**Pattern**: il lint verifica che ogni agente referenzi solo skill/command/tool esistenti.
WARNING-only, always-on, zero API cost (pure file existence check).

**File chiave**:
- `.claude/skills/lint-checks.md Check 4ai` — tre sotto-check (tool whitelist, skill reference, command reference)

### §29.5 — Invarianti globali

Questi pattern rispettano e non violano nessuna invariante §7 preesistente:
- `capabilities:` è additive-only: zero rimozioni da agent body, zero nuovi ERROR lint.
- `dispatch-policy.md` è read-only per l'orchestrator: single-committer invariant preservata.
- WAVE_ID nel log è additivo: log.md rimane append-only (R.S1 preservata).
- Check 4ai è WARNING-only: non blocca `/lint`, non è `heal-eligible` (R.P3 preservata).

---

## §30 — Voice Channel Layer (EP-041, v2.28, opt-in)
<!-- profiles: full -->

> Canale di interazione vocale (STT/TTS) opt-in per la factory multi-agente.
> Il canale vocale non modifica la factory ma si mette **davanti al runtime**,
> trasformandosi in un nuovo front-end di I/O per un sistema gia' esistente.

### §30.1 — Principio cardine: canale asimmetrico

Il Voice Channel Layer introduce un principio architetturale che lo distingue da ogni
altra capability del framework: e' un **front-end di I/O**, non un layer della pipeline.

- La factory (orchestratore, agenti, skill, config) e' **invariata**: nessun file
  all'interno di `.claude/` viene modificato da EP-041.
- Il modulo `voice/` si posiziona **davanti** al runtime LLM esistente, avvolgendolo
  tramite un'interfaccia astratta (`FactoryRuntime`) senza conoscerne i dettagli.
- Il canale e' **asimmetrico**: l'input vocale viene trascritto in testo prima di
  entrare nel runtime; l'output del runtime viene filtrato prima di essere sintetizzato
  in voce. Non esiste un percorso di codice che colleghi direttamente l'audio I/O agli
  agenti.
- Il principio non negoziabile: **artefatti mai al TTS**. Solo i tipi `SpokenSummary`,
  `Acknowledgment` e `Question` raggiungono il sintetizzatore vocale. `Artifact.content`
  (codice, diff, log, tabelle) e' instradato esclusivamente al canale visivo (stdout
  strutturato in MVP). L'invariante e' realizzata con un unico choke point in
  `voice/core/router.py` (allowlist, non denylist) e coperta da test automatizzato.

### §30.2 — Architettura: modulo voice/ esterno al meta-framework

Il modulo `voice/` vive alla radice del repo, fuori da `.claude/`. Questa posizione
e' deliberata: il canale vocale e' un front-end applicativo, non un componente del
meta-framework di orchestrazione.

```
voice/
├── audio/          # I/O audio real-time (PortAudio)
│   ├── capture.py       stream input, callback → coda thread-safe
│   ├── playback.py      stream output, .abort()/.stop() per barge-in
│   ├── devices.py       enumerazione e selezione device audio
│   └── aec.py           AECProcessor (Fase 4) + fallback chain NoOp
├── vad/            # Voice Activity Detection + endpointing
│   ├── base.py          interfaccia astratta VAD
│   ├── webrtc_vad.py    VAD frame-based, leggero (webrtcvad)
│   ├── silero_vad.py    VAD neurale (silero-vad + torch)
│   └── endpointing.py   rilevamento fine-turno su silenzio 500–800 ms
├── stt/            # Speech-to-Text
│   ├── base.py          interfaccia astratta STT
│   └── faster_whisper_stt.py  motore STT locale (faster-whisper)
├── tts/            # Text-to-Speech
│   ├── base.py          interfaccia astratta TTS
│   ├── piper_tts.py     motore TTS neurale locale (piper-tts)
│   └── sentence_splitter.py  split frase-per-frase per latenza ridotta
├── runtime/        # Adattatori FactoryRuntime (unico contatto con il runtime LLM)
│   ├── base.py                interfaccia astratta + tassonomia eventi
│   └── custom_loop_adapter.py Opzione B — loop LLM+tool custom (ADR-EP041-001)
├── core/           # Orchestrazione voice pipeline
│   ├── state_machine.py   macchina a stati 5 stati + INTERRUZIONE (barge-in)
│   ├── router.py          choke point allowlist TTS-safe
│   ├── cancellation.py    token/segnali di cancel propagabili (barge-in Fase 3)
│   └── session.py         contesto turno: session_id, codice
├── app.py          # Entry point CLI (python -m voice.app)
└── config.py       # Lettura sezione voice_channel: da factory.config.yaml
```

### §30.3 — Componenti

| Componente | File | Ruolo |
|---|---|---|
| **VoiceConfig** | `voice/config.py` | Lettura e validazione `voice_channel:` da `factory.config.yaml` |
| **AudioCapture** | `voice/audio/capture.py` | Stream input PortAudio; callback → coda thread-safe; push-to-talk gate |
| **AudioPlayback** | `voice/audio/playback.py` | Stream output; `.abort()` per barge-in senza thread appesi |
| **VAD + Endpointer** | `voice/vad/` | Rilevamento voce (webrtcvad o silero) + fine-turno su silenzio |
| **STT** | `voice/stt/faster_whisper_stt.py` | Trascrizione audio→testo via faster-whisper (locale, CTranslate2) |
| **TTS** | `voice/tts/piper_tts.py` | Sintesi testo→audio via piper-tts (neurale locale, voci italiane) |
| **FactoryRuntime** | `voice/runtime/base.py` | Interfaccia astratta: `submit()` + `cancel()` + `aclose()` |
| **CustomLoopAdapter** | `voice/runtime/custom_loop_adapter.py` | Implementazione concreta Opzione B (loop LLM+tool custom) |
| **VoiceStateMachine** | `voice/core/state_machine.py` | FSM 5 stati; gestisce concorrenza callback real-time ↔ task asyncio |
| **EventRouter** | `voice/core/router.py` | Choke point allowlist TTS; `Artifact` mai alla coda TTS |
| **BargeinDetector** | `voice/core/cancellation.py` | Token cancel propagabili; `cancel()` idempotente (Fase 3) |
| **AECProcessor** | `voice/audio/aec.py` | Fallback chain WebRTCAPM → SpeexDSP → NoOp (Fase 4 opt-in) |
| **App** | `voice/app.py` | Entry point CLI; costruisce la pipeline e avvia il loop asyncio |

### §30.4 — Macchina a stati

```
  (push-to-talk / VAD trigger)        (rilascio tasto / endpointing silenzio)
             │                                       │
             ▼                                       ▼
  ┌──────────────┐    ┌──────────┐      ┌──────────────┐      ┌───────────────┐
  │ IDLE/ASCOLTO │──▶ │ CATTURA  │ ───▶ │ TRASCRIZIONE │ ───▶ │  ELABORAZIONE │
  └──────────────┘    │  (mic)   │      │    (STT)     │      │  (runtime LLM │
        ▲             └──────────┘      └──────────────┘      │    + tool)    │
        │                  ▲                                   └───────┬───────┘
        │ Done / Error     │                                          │ SpokenSummary
        │                  │ barge-in (Fase 3):                       │ (router → coda TTS)
        │                  │ cancel() + flush buffer TTS              │
        │             ┌──────────┐                                    │
        └─────────────┤ PARLATO  │◀───────────────────────────────────┘
                      │  (TTS)   │
                      └──────────┘
```

Transizioni chiave:

| Da → A | Trigger |
|---|---|
| IDLE → CATTURA | push-to-talk (Fase 1) oppure trigger VAD hands-free (Fase 2+) |
| CATTURA → TRASCRIZIONE | rilascio tasto (Fase 1) oppure endpointing su silenzio 500–800 ms (Fase 2+) |
| TRASCRIZIONE → ELABORAZIONE | STT restituisce testo → `FactoryRuntime.submit(text, session_id)` |
| ELABORAZIONE → PARLATO | runtime emette `SpokenSummary`; router → coda TTS |
| PARLATO → IDLE | evento `Done` / `Error` chiude il turno |
| PARLATO → CATTURA | **barge-in** (Fase 3 only): VAD rileva voce → `cancel()` + flush |

Concorrenza: i callback audio PortAudio girano su thread real-time e non bloccano mai;
STT, runtime LLM e TTS sono task `asyncio` o thread executor. La comunicazione
thread ↔ event loop usa `queue.Queue` o `loop.call_soon_threadsafe`.

### §30.5 — Invariante: artefatti mai al TTS

Il vincolo e' realizzato con una **allowlist** nel router (non una denylist):

1. Solo gli eventi `SpokenSummary`, `Acknowledgment` e `Question` hanno il campo
   `.text` accodato alla coda TTS.
2. `Artifact.content` e' instradato esclusivamente al canale visivo (stdout strutturato
   in MVP); non esiste percorso di codice che lo passi a `piper_tts`.
3. Se un tipo non-allowlist arriva per errore alla coda TTS, il router lo **scarta**
   e logga a livello WARNING — degradazione sicura, mai pronuncia dell'artefatto.
4. L'invariante e' coperta da test automatizzato: data una sequenza mista di eventi,
   la coda TTS contiene esattamente i soli testi parlati; il canale visivo i soli
   artefatti.

### §30.6 — Config gate

```yaml
# Voice Channel (EP-041, opt-in, PATTERN §30)
voice_channel:
  enabled: false                # opt-in esplicito obbligatorio
  phase: 1                      # fase roadmap attiva (1..4)
  log_level: INFO               # DEBUG|INFO|WARNING
  stt:
    provider: faster-whisper    # motore STT locale
    model: base                 # tiny|base|small|medium|large
    language: it
  tts:
    provider: piper-tts         # motore TTS locale
    voice: it_IT-riccardo-medium
  audio:
    input_device: null          # null = default di sistema
    output_device: null
  vad:                          # Fase 2+ (hands-free/endpointing)
    provider: silero-vad        # silero-vad | webrtcvad
    threshold: 0.5
    endpoint_silence_ms: 700
  barge_in:                     # Fase 3 (US-144) — opt-in separato
    enabled: false
    vad_threshold: 0.7
  aec:                          # Fase 4 (US-147) — opt-in separato
    enabled: false
    provider: webrtc-apm        # webrtc-apm | speexdsp | noisereduce
```

`voice_channel.enabled: false` (default) — factory identica a v2.27; nessun import
avviene, nessuna dipendenza audio/STT/TTS viene caricata (integrazione no-op US-146 AC2).

`voice_channel.enabled: true` — avvia la pipeline vocale con `python -m voice.app`.
Prerequisito: `pip install -e ".[voice]"` + voce piper scaricata (runbook §3).

### §30.7 — Fasi implementative (roadmap a 4 fasi)

| Fase | Sprint | Contenuto | Stato |
|---|---|---|---|
| **Fase 1** — Push-to-talk MVP | SP41 | Ciclo end-to-end: cattura PTT → STT → LLM → TTS. Nessun VAD attivo; sequenziale. | DONE (US-143, US-145, US-146) |
| **Fase 3** — Barge-in | SP42 | Full-duplex: RMS pre-gate + VAD debounce; `cancel()` propagato; latenza interruzione < 300 ms. | DONE (US-144) |
| **Fase 4** — AEC opzionale | SP42 | Cancellazione eco altoparlanti: fallback chain WebRTCAPM → SpeexDSP → NoOp. Cuffie raccomandati senza AEC. | DONE (US-147) |
| **Fase 2** — VAD hands-free | roadmap | Trigger automatico via VAD (senza tasto push-to-talk); endpointing su silenzio. | roadmap |

> Nota: le fasi sono state consegnate in ordine 1 → 3 → 4 (Fase 2 posticipata a roadmap
> perche' Fase 3 barge-in era prerequisito piu' critico per il test dell'architettura
> concorrente).

### §30.8 — Dipendenze Python (opt-in)

Le dipendenze vocali non vengono mai importate quando `voice_channel.enabled: false`.
Installazione tramite extra group: `pip install -e ".[voice]"`.

| Package | Ruolo | Fase |
|---|---|---|
| `sounddevice` (PortAudio) | cattura + playback audio real-time | F1 |
| `faster-whisper` | STT (Whisper via CTranslate2, locale) | F1 |
| `piper-tts` | TTS neurale locale, voci italiane | F1 |
| `numpy` | frame math, RMS, buffer | F1, F3 |
| `webrtcvad` / `silero-vad` | VAD + endpointing + barge-in | F2–F3 |
| `speexdsp` | AEC leggero (alternativa a WebRTC APM) | F4 |
| `asyncio`, `threading`, `queue` (stdlib) | concorrenza real-time ↔ task lenti | F1+ |

### §30.9 — ADR

| ADR | Titolo | Decisione |
|---|---|---|
| **ADR-EP041-001** | Runtime adapter: Opzione A (agent SDK) vs Opzione B (custom loop) | **GO Opzione B** — custom loop adapter (`voice/runtime/custom_loop_adapter.py`); massima aderenza alla filosofia agnostica; interfaccia astratta `FactoryRuntime` consente aggiunta futura di `agent_sdk_adapter.py` senza modificare il layer vocale |

### §30.10 — File chiave

| Tipo | Path |
|---|---|
| **Entry point** | `voice/app.py` |
| **Config** | `voice/config.py` + `factory.config.yaml :: voice_channel:` |
| **Interfaccia runtime** | `voice/runtime/base.py` (`FactoryRuntime` + tassonomia eventi) |
| **Adapter Opzione B** | `voice/runtime/custom_loop_adapter.py` |
| **FSM** | `voice/core/state_machine.py` |
| **Router (choke point TTS)** | `voice/core/router.py` |
| **Runbook installazione** | `wiki/runbooks/voice-channel-installation.md` |
| **Concept** | `wiki/concepts/voice-channel-factory.md` |
| **Design source** | `wiki/sources/sistema-vocale-factory.md` |

### §30.11 — Integrazione con capability esistenti

EP-041 si integra con il framework esistente senza modificarlo:

- **factory.config.yaml**: aggiunge il blocco `voice_channel:` (opt-in, default off)
  senza toccare nessuna chiave esistente. A `enabled: false` la factory e' identica a v2.27.
- **Token Ledger (EP-022)**: il consumo della sessione vocale e' visibile inline via
  `show-session-tokens.py`. Il CustomLoopAdapter genera eventi LLM le cui chiamate
  contribuiscono al conteggio di sessione.
- **§29 Scalability Patterns**: la `voice/` directory e' fuori scope del dispatch degli
  agenti — nessuna interazione con lo scheduler, nessun agente `.claude/` scaffoldato.
  EP-041 non aggiunge nessuna sezione a `dispatch-policy.md`.
- **Backward compat totale**: nessuna factory v2.27 preesistente e' impattata.
  Il blocco `voice_channel:` con `enabled: false` e' l'unico artefatto aggiunto
  a `factory.config.yaml`; tutti gli altri file sono invariati (R.P3).

Fonte: EP-041 | [[voice-channel-factory]] | [[sistema-vocale-factory]]

### §30.12 — Voice Handsfree Improvements (EP-044, v2.31, opt-in)

EP-044 estende il Voice Channel Layer (EP-041) con cinque miglioramenti hands-free
consegnati negli Sprint 45-46. Nessuna nuova invariante §7. Backward compat totale v2.30.

| US | Problema | Soluzione | Campo config aggiunto |
|---|---|---|---|
| **US-155** | P1: doppio endpoint — VAD produce due trigger per una singola utterance | Debounce 500 ms in `Endpointer.feed_frame()`; campo `VADConfig.debounce_ms: int = 500` | `vad.debounce_ms: 500` |
| **US-156** | P2: wake-word catturata come primo comando utente | Flag `_skip_next_utterance` + distanza di Levenshtein (`levenshtein()`) per rigettare utterance foneticamente prossime alla wake-word | `wake_word.filter_threshold: 3` |
| **US-157** | P3: WER elevato con modello `small` su termini tecnici (10.4%) | Default STT promosso a `model: "medium"` — WER 2.9%, latenza ~2 s su CPU accettabile per l'uso hands-free | `stt.model` default: `"base"` → `"medium"` |
| **US-158** | P4: latenza file-pipe con polling fisso 500 ms | `FilePipeAdapter` riscritta event-driven (FSEvents macOS / inotify Linux) via dipendenza opzionale `watchdog`; fallback polling 100 ms sempre garantito | `runtime.pipe_poll_ms: 100`, `runtime.pipe_timeout: 180` |
| **US-159** | P5: doppia istanza e processi zombie al riavvio | PID lock file atomico (`VoiceConfig.pid_file_path`); avvio fallisce con errore esplicito se lock esiste; lock rimosso a `finally` | `voice_channel.pid_file_path: ".voice.pid"` |

**Dipendenza opzionale**: `pip install watchdog` abilita la modalita' event-driven per
US-158. Senza il pacchetto, il fallback polling 100 ms e' sempre attivo (no-op silenzioso).

**Config delta** (aggiunta al blocco `voice_channel:` di §30.6):

```yaml
# Voice Handsfree Improvements (EP-044, v2.31 opt-in)
voice_channel:
  pid_file_path: ".voice.pid"      # US-159: PID lock — no doppia istanza
  vad:
    debounce_ms: 500               # US-155: debounce doppio endpoint VAD
  wake_word:
    filter_threshold: 3            # US-156: Levenshtein distance max per filtrare wake-word
  stt:
    model: medium                  # US-157: default upgrade (WER 2.9% vs 10.4% small)
  runtime:
    pipe_poll_ms: 100              # US-158: fallback polling interval (ms)
    pipe_timeout: 180              # US-158: timeout attesa risposta file-pipe (s)
```

**Backward compat**: a `voice_channel.enabled: false` (default EP-041) tutti i miglioramenti
EP-044 sono no-op. Nessun import aggiuntivo avviene. Gate v2.31.0 PENDING.

Fonte: EP-044 | [[voice-channel-factory]]

## §31 — Hybrid Wiki Search Layer (EP-042, v2.29, opt-in)
<!-- profiles: full -->

> Ricerca semantica ibrida (vector + FTS + metadata filter) sul wiki, con fallback
> trasparente alla scansione lineare esistente. Potenzia la capability `wiki-query`
> senza modificarla: quando l'indice e' disponibile le query beneficiano del ranking
> semantico; quando e' assente (o disabilitato) il comportamento e' identico a v2.28.

### §31.1 — Problema e soluzione

Il wiki di una factory attiva cresce rapidamente (centinaia di pagine). La scansione
lineare `Glob wiki/**/*.md` + lettura selettiva per pertinenza gia' in uso in `wiki-query`
scala male: latenza lineare, nessun ranking semantico, nessun supporto a query in lingua
naturale che non matchino lessicalmente i titoli.

EP-042 introduce un **layer di ricerca semantica ibrida** opt-in:
- **LanceDB embedded** (zero server aggiuntivo) come store vettoriale + FTS (tantivy).
- **sentence-transformers** (`paraphrase-multilingual-MiniLM-L12-v2`) per embedding
  multilingua (italiano + inglese) a ~120 MB offline.
- **Reciprocal Rank Fusion (RRF k=60)** per combinare score vettoriali e FTS in un unico
  ranking calibrato.
- **Chunk per H2-section** (cap 2000 chars), ID stabile `<path>#<section-slug>`.
- **Fallback obbligatorio** (R.WS1): se l'indice e' assente o corrotto, `wiki-query` ricade
  silenziosamente sulla scansione lineare pre-EP-042 — nessuna risposta bloccata.

### §31.2 — Architettura

```
wiki/**/*.md  →  indexer  →  .wiki-search/index.lance  →  HybridSearcher  →  wiki-query
                               (LanceDB embedded)          tools/wiki-search/   (agente)
```

Il layer ha due percorsi indipendenti:

**Percorso di indicizzazione (write, off-band):**
`build-index.py` / `update-index.py` → crawl `wiki/` → chunk per H2-section →
embed (`sentence-transformers`) → upsert in LanceDB → aggiorna `index_state.json`
(per differenziale incrementale). L'indicizzazione avviene fuori-band tramite
comando esplicito (`/wiki-search reindex`), mai automaticamente durante una query.

**Percorso di ricerca (read-only, on-demand):**
`HybridSearcher.search(query, mode, top_k, filters)` → vector search (embedding coseno)
+ FTS (tantivy / scan TF fallback) → RRF merge → metadata filter push-down → top-K risultati
ordinati per score decrescente. La skill `wiki-search-protocol` incapsula questo percorso
in 4 step (check → query → inject → fallback) ed e' invocata da `wiki-query` come
PRE-LLM context injection.

### §31.3 — Componenti

| Componente | File | Responsabilita' | US |
|---|---|---|---|
| **IndexerCore** | `tools/wiki-search/indexer.py` | crawl/chunk/embed/upsert condiviso (importabile) | US-148 |
| **IndexBuilder CLI** | `tools/wiki-search/build-index.py` | full build entry point; `--rebuild` = drop + re-index | US-148 |
| **IncrementalUpdater CLI** | `tools/wiki-search/update-index.py` | update solo file modificati via `index_state.json`; `--full`; `--stats` | US-150 |
| **HybridSearcher** | `tools/wiki-search/searcher.py` | vector + FTS + filter → RRF → top-K; `.is_available()` gateway | US-149 |
| **wiki-search-protocol** | `.claude/skills/wiki-search-protocol.md` | thin-skill 4-step: check → query → inject → fallback | US-151 |
| **wiki-query** (esteso) | `.claude/agents/wiki-query.md` | primo consumatore della skill; fallback scan lineare se indice assente | US-149 |
| **Comando** | `.claude/commands/wiki-search.md` | `/wiki-search <query>` + `reindex [--full]` + `status` | US-150 |
| **Config** | `factory.config.yaml :: wiki_search:` | parametri layer: embedding, mode, top_k, exclude_types | US-151 |

### §31.4 — Invarianti locali (R.WS1..R.WS3)

Queste invarianti sono **locali al layer EP-042** — non aggiungono ne' modificano le 18
invarianti globali §7.

| Invariante | Titolo | Regola |
|---|---|---|
| **R.WS1** | Fallback garantito | Indice assente / `enabled: false` / import fail → `{"results": [], "fallback": true}`. Mai bloccare una risposta per mancanza di indice. `wiki-query` ricade silenziosamente sulla scansione lineare pre-EP-042. |
| **R.WS2** | Opt-in obbligatorio | `wiki_search.enabled: false` di default. A flag spento: nessun import di `lancedb` o `sentence_transformers`, nessuna directory `.wiki-search/` creata, comportamento identico a v2.28. |
| **R.WS3** | Read-only durante la query | Nessun write sull'indice durante `HybridSearcher.search()`. L'indice e' aperto in sola lettura; solo `build-index.py` e `update-index.py` eseguono scritture (su comando esplicito). |

### §31.5 — Config gate

```yaml
# Hybrid Wiki Search (EP-042, opt-in, PATTERN §31)
wiki_search:
  enabled: false                                           # opt-in esplicito (R.WS2)
  embedding_provider: local                                # local | voyage-api | openai-api
  embedding_model: paraphrase-multilingual-MiniLM-L12-v2  # 384d, IT+multilingua, offline ~120MB
  embedding_dim: 384                                       # deve combaciare col modello (invariante schema)
  index_path: .wiki-search/index.lance                     # dataset LanceDB dentro .wiki-search/ (gitignored)
  index_table: pages                                       # nome tabella
  chunk_strategy: h2-section                               # h2-section (default) | whole-page
  mode: hybrid                                             # hybrid (default) | vector | fts
  rrf_k: 60                                                # costante Reciprocal Rank Fusion
  candidate_k: 20                                          # candidati per ramo prima del merge RRF
  top_k: 5                                                 # risultati restituiti di default
  exclude_types: [meta]                                    # type esclusi di default (gaps/log)
```

`wiki_search.enabled: false` (default) — factory identica a v2.28; nessun import avviene,
nessuna dipendenza di ricerca viene caricata. Il blocco `wiki_search:` con `enabled: false`
e' l'unico artefatto aggiunto a `factory.config.yaml` dalle factory che aggiornano da v2.28.

`wiki_search.enabled: true` — attiva il layer ibrido. Prerequisiti: `pip install lancedb
sentence-transformers` + almeno un run di `/wiki-search reindex` completato con successo.
Vedi `wiki/runbooks/wiki-search-installation.md`.

### §31.6 — Comandi

| Comando | Azione |
|---|---|
| `/wiki-search <query>` | Ricerca ibrida diretta nell'indice; bypassa `wiki-query` (utile per testing/debug) |
| `/wiki-search <query> --mode=fts\|vector` | Solo full-text o solo embedding |
| `/wiki-search reindex` | Aggiornamento incrementale dell'indice |
| `/wiki-search reindex --full` | Full rebuild (drop + re-index completo) |
| `/wiki-search status` | Stato indice: chunk count, last updated, modello |

### §31.7 — Dipendenze Python (opt-in)

Le dipendenze non vengono importate quando `wiki_search.enabled: false`.

| Package | Ruolo |
|---|---|
| `lancedb` | Store vettoriale embedded + FTS (tantivy) |
| `sentence-transformers` | Modello embedding multilingua locale (~120 MB) |
| `numpy` | Calcoli vettoriali frame-level |
| `pyyaml` | Lettura `factory.config.yaml` |

### §31.8 — Integrazione con capability esistenti

EP-042 si integra con il framework esistente senza modificarlo:

- **wiki-query**: riceve context injection PRE-LLM dai risultati top-K quando l'indice e'
  disponibile; se no, comportamento invariato (scan lineare). Backward compat totale.
- **factory.config.yaml**: aggiunge il blocco `wiki_search:` (opt-in, default off) senza
  toccare nessuna chiave esistente. A `enabled: false` la factory e' identica a v2.28.
- **Dispatch policy §8**: `wiki_search` e' annunciato come capability opt-in nella tabella
  slug di `dispatch-policy.md §8` (Capability Advertisement, v2.27+).
- **Token Ledger (EP-022)**: le query di embedding e le ricerche FTS non generano chiamate
  LLM; il costo e' trascurabile e non registrato nel ledger (inferenza locale).
- **Backward compat totale**: nessuna factory v2.28 preesistente e' impattata. Il blocco
  `wiki_search:` con `enabled: false` e' l'unico artefatto aggiunto a `factory.config.yaml`
  (R.WS2). Tutti gli altri file sono invariati.

Fonte: EP-042 | [[hybrid-wiki-search-capability]] | `tools/wiki-search/` | `wiki/runbooks/wiki-search-installation.md`

Fonte: factory-optimization-2026-07-07 | `CLAUDE.md §Meta-prompt versioning`
