> Modulo di PATTERN.md (§21–§23) — indice e versione: [`PATTERN.md`](PATTERN.md).

## §21 — Versioning
<!-- profiles: standard, full -->

- **v2.40**: Backport selettivo delta portale-servizi-factory EP-059 (2026-09-02): agente `release-manager` (§2, orchestrazione release 4 fasi + R.21 domain:release) + skill `tpm-reconcile` (riconciliazione periodica kanban, sola lettura, filtro epica) + skill `deep-functional-probe` (probe FE avanzato, complemento EP-018) + skill `release-protocol` (orchestrazione release, gate umano pre-tag invariante) + tool `statusline-ledger.py` (statusline compatta token ledger, stdin-based, stdlib) + `dispatch-policy.md §9` (Release Domain Dispatch Policy). Backward compat totale v2.39. Pattern-steal §23.10 inapplicabile (stessa factory fleet). Nessuna nuova invariante §7 globale.

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

### §23.8 — Sunset Policy per Layer Non Esercitati (v2.33, EP-051)

> Meccanismo complementare a §23.1 (N:1): mentre la regola N:1 controlla il bloat
> numerico delle sezioni, la sunset policy controlla il bloat qualitativo — layer
> opt-in che esistono nel meta-framework ma non vengono mai usati su factory derivate
> esterne. Introdotta in EP-051 (Bus Factor Mitigation) come PA-3 degli accordi
> Tavola Rotonda v2.33.
> **Condizione di falsificazione**: «Una capability con `enabled: true` che non produce artefatti
> misurabili entro N giorni dall'attivazione è candidata a sunset alle stesse condizioni di una capability non adottata.»
> Il valore di `N` sta in `factory.config.yaml`, il divieto d'ingresso e la sua allowlist in `.claude/skills/lint-checks-agent-fleet.md` (severità ERROR), la metrica che li ricalcola in `tools/fleet-observer/observe.py --load`.
> [^src: management/kanban/EP-051-bus-factor-mitigation/US-186-secondo-maintainer-sunset-policy/TSK-428.md §Technical Specs]

#### Soglia di attivazione

Un layer opt-in non esercitato su **nessuna factory derivata esterna** entro **N=3
release** riceve un `sunset_date`. Il conteggio N parte dalla release in cui il layer
e' stato introdotto come opt-in stabile (non experimental).

«Esercitato» significa: almeno una factory derivata pubblica (fuori dal repo
`soli-multi-agents-factory`) ha il flag di abilitazione del layer impostato a `true`
in `factory.config.yaml` e ha almeno un TSK `done` che usa la capability.

#### Formato `sunset_date`

Quando un layer raggiunge la soglia, il campo `sunset_date` viene aggiunto in due
posti:

1. **Blocco config in `factory.config.yaml`** (nel repo del meta-framework):

   ```yaml
   <layer_key>:
     enabled: false
     sunset_date: "YYYY-MM-DD"  # SUNSET: non esercitato su factory derivate esterne
   ```

2. **Annotazione in `PATTERN.md`** nella sezione del layer:

   ```
   # SUNSET: <data> — non esercitato su factory derivate esterne
   ```

   L'annotazione va aggiunta come prima riga del blocco `>` (blockquote) di
   presentazione della sezione.

#### Processo di deprecazione

Dopo il `sunset_date`:

1. **Grace period di 1 release**: il layer rimane in posizione ma riceve il tag
   `[DEPRECATED]` nel titolo della sezione e nell'entry di `CHANGELOG.md`.
2. **Spostamento in `experimental/`**: se entro la release successiva nessuna factory
   derivata ha attivato il layer, la sezione viene spostata in `experimental/`
   (sotto-directory o sezione `## Experimental` in coda a `PATTERN.md`) con
   migrazione documentata nel CHANGELOG.
3. **Rimozione**: dopo un'ulteriore release in `experimental/` senza adozione, la
   sezione viene rimossa. La rimozione richiede un TSK esplicito con `consumer: human`
   (gate umano obbligatorio) e documentazione della migrazione per eventuale recupero.

La rimozione non e' retroattiva: factory derivate che avevano attivato il layer
mantengono i propri file e la propria config; la rimozione riguarda solo il
meta-framework.

#### Esenzione automatica

Un layer e' **esentato** dalla sunset policy se:

- ha una dipendenza esplicita attiva su ≥1 factory derivata **pubblica** (repo
  pubblico o documentato nel registry adapters), **oppure**
- e' referenziato come `depends_on` da un altro layer non in sunset, **oppure**
- e' dichiarato `required: true` in `factory.config.yaml` del meta-framework.

L'esenzione e' auto-applicata: non richiede TSK, ma il manutentore puo' annotarla
con un commento `# EXEMPT: <motivo>` nel blocco config per chiarezza.

#### Cross-link

- §23.1 (N:1): la sunset policy si attiva *prima* che N:1 forzi una rimozione —
  e' il segnale precoce; N:1 e' il trigger tardivo.
- §23.2 (Sezione Deprecate): il processo di deprecazione di §23.8 produce sezioni
  deprecate gestite secondo §23.2.
- §22 (Release Governance): il `sunset_date` e' calcolato in release (tag semver),
  non in date di calendario.

### §23.9 — ai_attribution_policy (opt-in, v2.36, EP-053)

Pattern per factory con un `code_path` appartenente a un cliente o organizzazione esterna
che non vuole esporre l'uso di strumenti AI nei commit del repository.

**Quando usarlo**: quando il cliente richiede esplicitamente che i commit non contengano
attributi AI (`Co-Authored-By: Claude`, footer, commenti che citano AI); oppure quando
esiste una policy aziendale che vieta l'esposizione degli strumenti AI utilizzati.

**Componenti**:
- `tools/vcs/sm_commit.py` — script Python stdlib-only (cross-platform, Windows nativo) che
  esegue `git commit` applicando i filtri di `tools/vcs/ai_policy.py`. Uso:
  `python3 tools/vcs/sm_commit.py "msg" [path] [--dry-run] [--yes]`.
  `tools/vcs/sm-commit.sh` resta come **shim** retro-compatibile (v2.44, EP-068 US-301).
  Quando i filtri **alterano** il messaggio, il risultato si mostra e il commit si conferma:
  rimuovere un ID incastonato nella prosa rompe la frase, e committarla in silenzio e'
  peggio che non filtrare affatto, perche' la history non si disfa.
- `factory.config.yaml` campo `ai_attribution_policy.suppress_ai_traces: true` (opt-in,
  default `false`). Quando `true`, i dev-agent devono usare `sm_commit.py` (o lo shim
  `sm-commit.sh`) per commit nel/i `code_path` marcati.
- `CLAUDE.md §ai_policy` — nota che ricorda agli agenti di usare `sm-commit.sh` quando
  il flag è attivo.

**Regole**:
- Il pattern è **opt-in**: factory che non lo attivano sono identiche a prima.
- Applicabile solo ai `code_path` del cliente; non ai commit del repo factory stesso.
- Non modifica il comportamento di nessun'altra sezione del PATTERN.
- I commit del framework (factory config, wiki, kanban) possono mantenere l'attributo AI.
- **Testi del repo senza riferimenti alla factory** (v2.44, EP-072, esercitata su una
  derivata): con il flag attivo, commenti, documentazione, test, config e pipeline del
  `code_path` cliente spiegano solo il funzionamento del codice. Vietati ID kanban
  (`XX-TSK-N`, `US-N`, `EP-N`), gap, question, ADR e regole della factory (`R.N`, `INV-*`) e
  il gergo di processo. Ammessi i riferimenti del cliente (ticket, work item) e quelli
  pubblici (RFC, WCAG, CVE, issue di progetti open source). Il commento dice il *perché*,
  non *da dove* arriva la richiesta: `// TSK-249 — elimina race condition` diventa
  `// attende la risposta di login prima di navigare: evita la race sul cookie di sessione`.
  Il codice copiato da un altro repo si ripulisce nel commit che lo introduce.

**Enforcement** (v2.44, EP-068 US-300): oltre agli hook preventivi esiste un layer
detective opt-in. E' una capability nel bucket di ingresso (§23.8): niente norma qui prima
dell'esercizio. Meccanismo, limiti e guardia di scope: `CAPABILITIES.md` §ai_policy.

`tools/vcs/ai_policy.py` e' la **fonte unica** dei pattern — attribution AI e ID kanban —
condivisa da `sm_commit.py`, dallo scan e dagli hook. Nessun altro file li ridefinisce.
Il prefisso di namespace negli ID e' **opzionale**, perche' le factory della flotta usano
convenzioni diverse (`TSK-690` nel meta-framework, `XX-TSK-268` nelle derivate
multi-namespace): un pattern che ne accetta una sola rompe l'altra meta' della flotta.

[^src: portale-servizi-factory CLAUDE.md §ai_policy + scripts/sm-commit.sh — EP-053 backport 2026-07-30]

---

### §23.10 — Third-Party License & Pattern-Stealing Policy (v2.37, TR-llmwiki-20260824)

Policy che governa l'importazione di idee, architetture e pattern da progetti di terze
parti nel meta-framework e nelle factory derivate. Nasce dalla deliberazione Tavola Rotonda
`TR-llmwiki-20260824` (analisi di `llm_wiki`, GPL v3) ma è di applicazione **generale** a
qualunque sorgente esterna analizzata sotto `repo_codes/`.

**Principio (non overridabile)**: distinzione netta tra *pattern-stealing concettuale* e
*riuso di codice sorgente*.

| Attività | Con sorgente permissiva (MIT/BSD/Apache-2.0) | Con sorgente copyleft (GPL/AGPL/LGPL) |
|---|---|---|
| Riuso letterale di codice sorgente (copia/adattamento snippet) | Ammesso con rispetto dell'attribution della licenza | **Vietato** — contaminerebbe la factory con obblighi copyleft |
| Porting di pattern concettuali (architettura, procedura, formato dati) reimplementati da zero | Ammesso | **Ammesso** — le idee non sono coperte da copyright |
| Dipendenza runtime dal binario/servizio di terze parti | Valutare caso per caso (vedi §33 — local-first, zero dipendenze esterne) | Ammesso solo come integrazione black-box opt-in, mai capability core |

**Regole**:
- Prima di aprire qualsiasi EP che importa pattern da una sorgente esterna, **verificare la
  licenza** della sorgente e registrarla nell'EP (campo `source` + nota licenza).
- Per sorgenti **copyleft**: zero righe di codice sorgente entrano nella factory. Solo
  pattern concettuali reimplementati indipendentemente, con documentazione esplicita
  dell'origine (`source:` nell'EP + citazione nel registro decisioni / ADR).
- Ogni pattern importato deve essere **riconoscibile come reimplementazione originale**, non
  come derivazione strutturale 1:1 del codice sorgente (la somiglianza strutturale alta è la
  difesa debole nei contenziosi copyleft).
- Le dipendenze runtime da desktop app non-headless (es. Tauri) o servizi SaaS esterni non
  sono capability core del framework: al massimo integration-test opt-in senza garanzia di
  manutenzione (coerente con il principio local-first «zero dipendenze esterne» di §33).
- Il submodule della sorgente vive sotto `repo_codes/<nome>` (read-only, per analisi); non è
  un `code_path` della factory e non viene mai indicizzato dai layer L1/L2/L3 (§code_intelligence).

**Caso di riferimento** — `llm_wiki` (GPL v3): esclusi come capability core l'MCP adapter
(Tauri non-headless) e la Deep Research pipeline (dipendenza SaaS web search); ammesso il
porting concettuale di `purpose.md`, del 2-step CoT ingest e del sweep-reviews semantico
(EP-055 / EP-056), reimplementati da zero senza toccare il codice sorgente originale.

[^src: wiki/decisions/tavola-rotonda-TR-llmwiki-20260824-2026-08-24.md — Accordo Round 1 GPL v3 policy]

---

### §23.11 — Capability lifecycle (status: active | dormant | deprecated | removed)

> Dalla factory derivata portale-servizi-factory (Tavola Rotonda del 2026-08-03, Addendum 3), dove
> e' in uso; ritorno EP-072 TSK-785. Qui definisce il campo `status` gia' presente in config.

*Questo paragrafo NON introduce una nuova invariante §7 numerata. E' un contratto operativo
descrittivo.*

#### Il gap strutturale

La factory sa aggiungere capability (ogni EP introduce una §N, un blocco in `factory.config.yaml`,
artefatti scaffoldati) ma non dispone di un protocollo per ritirarle. Il rischio strutturale
quantificato nell'Addendum 3: ~9/18 capability `enabled: true` non hanno tracce operative
verificabili nella vita della factory. Il rischio concreto: `enabled: true` smette di essere
informativo — i nuovi agenti che leggono `factory.config.yaml` come ground-truth ottengono
un segnale falso su cosa e' operativo.

#### Stati

| Stato | Significato |
|---|---|
| `active` | Capability con ≥1 artefatto tracciabile in `wiki/log.md`, `deliverables/`, `code_quality/reports/` o `analytics/` negli ultimi `dormancy_threshold_days` giorni (default 90). |
| `dormant` | Capability `enabled: true` senza tracce d'uso recenti; candidata a revisione umana. **Non disabilitata automaticamente.** |
| `deprecated` | Capability dismessa tramite ADR accettato + `enabled: false`, con gate umano obbligatorio. Precede la rimozione dei file (ADR separato). |
| `removed` | Capability ritirata con nuovo ADR dedicato. La rimozione dei file e' una decisione separata e distinta dalla deprecazione (vedi Constraint marker-file sotto). |

#### Transizioni

```
active
  → dormant    (≥dormancy_threshold_days senza traccia operativa; advisory, gate umano consigliato)
  → deprecated (ADR + enabled:false, gate umano obbligatorio — branch dedicato + PR)
  → removed    (nuovo ADR separato; mai rimozione file automatica)
```

#### Regola operativa

Una capability e' `active` se esiste ≥1 artefatto tracciabile in
`wiki/log.md`/`deliverables/`/`code_quality/reports/` negli ultimi `dormancy_threshold_days`
giorni (default 90, configurabile in `factory.config.yaml`). In assenza di tracce, e'
candidata `dormant`.

**Nessuna transizione di `status` altera il valore di `enabled` senza decisione umana
in un branch dedicato + PR.** Il campo `status` (`active|dormant|deprecated`) in
`factory.config.yaml` e' **metadata puro**: `factory-bootstrap` legge `enabled`, non `status`.

`enabled: true` + `status: dormant` = *"dichiarata attiva, evidenza operativa assente"*
— e' un segnale informativo per il Tech Lead, non un gate di dispatch ne' un blocco automatico.

#### Esclusione delle capability `enabled: false`

Le capability con `enabled: false` (es. `tavola_rotonda`, `voice_channel`, `prototyping`)
sono gia' nello stato opt-in legittimo del framework. La logica dormancy **non si applica**
a queste capability: lo `status` su di esse e' irrilevante; la loro gestione e'
esclusivamente tramite il flag `enabled`.

Non duplicare la semantica di `enabled: false` con `status: deprecated` per le capability
opt-in intenzionalmente spente.

#### Constraint marker-file (factory-upgrade)

Nessuna rimozione automatica di file capability e' ammessa. `factory-upgrade` usa la
**presenza di file specifici** (es. presenza di `visual-oracle-protocol.md` per inferire ≥v2.17)
per determinare la versione della factory derivata e selezionare i seed di aggiornamento.
La rimozione di un file di capability romperebbe la catena upgrade e i seed `-full` per
le factory derivate che aggiornano dalla versione precedente.

La rimozione di file e' esclusivamente una decisione umana, documentata in un ADR dedicato
(distinto dall'ADR di deprecazione).

#### Configurazione in `factory.config.yaml`

Il campo `status` e' aggiunto come metadata a ogni blocco capability `enabled: true`.
Il parametro `dormancy_threshold_days` (default 90) e' configurabile a livello globale.
Il seeding iniziale dei valori `status` e' derivato da audit read-only delle evidenze
operative esistenti (`wiki/log.md`, `deliverables/`, `code_quality/reports/`, `analytics/`):
se l'evidenza e' assente o ambigua, `dormant` e' il default conservativo (R.2 — nessuna
invenzione di stato non supportato da evidenza).

Vedi `factory.config.yaml` per i valori attuali.
