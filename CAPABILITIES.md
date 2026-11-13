# Capability della factory — per scenario d'uso

> Copia per factory derivata, generata da `tools/factory_scope.py`: senza i comandi del meta-framework e con i rimandi a pagine che questa factory non ha resi come testo.

## Come leggere questo documento

Ogni sezione risponde a una domanda concreta: "quando devo fare X, quale capability uso?".
Ogni riga di tabella e' un punto di ingresso operativo: il comando e' eseguibile direttamente,
l'agente e' il motore che lo esegue. La colonna **Approfondimento** linka alle pagine wiki
con il design dettagliato della capability (concept, runbook). Un trattino (`—`) indica che
non esiste ancora una pagina wiki dedicata.

Questo file e' l'**indice operativo corrente** ed e' la fonte che `/help` interroga. La
mappa di design `wiki/concepts/capability-map.md` copre
il ragionamento per cluster ma e' allineata alla v2.23: in caso di divergenza vale questo
file (o, per i flag, `factory.config.yaml`).

---

## Nota: capability sempre attive e capability opt-in

Alcune capability sono **sempre attive** in ogni factory (colonna "Sempre attiva?" = si).
Altre sono **opt-in**: disabilitate di default, si abilitano impostando il flag indicato
in `factory.config.yaml`. Un flag spento = comportamento identico alla versione precedente
(nessun impatto su factory esistenti).

---

## Quando sono nuovo o non so quale capability usare

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Onboarding in-chat | `/onboarding` | si | Sei nuovo sulla factory: report contestuale (versione, TSK facili, 5 invarianti, next step) senza scrivere file | — |
| Router capability | `/help <domanda>` | si | Hai una domanda in linguaggio naturale e vuoi il comando/agente giusto | questo file (`CAPABILITIES.md`) |
| Da dove partire | leggi `docs/START-HERE.md` (o `.it.md`) | si | Vuoi un ordine di lettura per il tuo ruolo: valutare, usare, estendere, governare | START-HERE |

---

## Quando devo ingestare nuovi dati nella knowledge base

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Ingest PDF | `/sync-docs` + `sync-docs` | si | Hai un PDF in `raw/` da trasformare in wiki | — |
| Ingest Figma | `/figma-sync <url>` + `figma-sync` | si | Hai un file Figma con wireframe o spec | figma-extraction-agent |
| Ingest repo esistente | `/repo-sync <path>` + `repo-sync` | si | Vuoi estrarre spec da un codebase esistente | — |
| Ingest knowledge graph | `/graphify-sync <target>` + `graphify-sync` | opt-in: `compression.context.enabled: true` | Vuoi sostituire il codice raw con un grafo di dipendenze come contesto per i dev-agent | knowledge-graph-codebase · graphify · installazione |
| Costruzione wiki | `wiki-keeper` + `wiki-keeper-worker` | si | Dopo ogni ingest: trasforma `raw/` in pagine `wiki/` strutturate | — |

---

## Quando voglio interrogare la knowledge base o controllare lo stato

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Dashboard stato + wave dispatch | `/run` + `orchestrator` | si | Vuoi sapere cosa e' pronto, cosa e' bloccato, suggerimento prossimo step | parallel-scheduler |
| Query knowledge base | `/query <domanda>` + `wiki-query` | si | Hai una domanda in linguaggio naturale sulla wiki o sul kanban | — |
| Health check | `/lint` + `wiki-lint` | si | Vuoi verificare integrita' strutturale, link rotti, staleness, errori | — |
| Riparazione errori meccanici | `/heal` | si | Il lint ha trovato ERROR meccanici e vuoi ripararli in automatico | evaluator-optimizer |
| Pass di qualita' semantica wiki | `/sweep-reviews` | opt-in: `wiki_sweep.enabled: true` | Vuoi risolvere claim non supportati, wikilink dangling e deriva terminologica (loop bounded, gated) | — |
| Scopo semantico della wiki | `wiki/purpose.md` (letto da `wiki-keeper`) | opt-in: file presente | Vuoi dichiarare dominio, entita' prioritarie, tono ed esclusioni che guidano l'ingest | — |
| Promozione status | `/promote <path> <status>` | si | Vuoi avanzare lo status di una pagina wiki o di un TSK | promotion-pipeline |
| Topologia e routing | `/topology [show\|set]` | si | Vuoi vedere o cambiare la topologia della factory | routing |
| Stato branch VCS (submodule) | `/vcs-status [target]` | si (read-only) | Progetti multi-repo/submodule: vuoi sapere su quale branch sei e su quale dovresti stare (detached HEAD, drift parent-ref, submodule non init) + comando di remediation | vcs-and-code-path |
| Allineamento repo con il remote | `/repo-align [--repos=<lista>] [--json]` | opt-in: `repo_align.enabled: true` (eseguibile anche a flag spento) | Vuoi sapere se il tuo lavoro locale e' gia' sul remote — per tutti i `vcs.mode` di PATTERN §15 (monorepo, submodule, sibling, external). Zero mutazione: usa solo `git ls-remote`. Per `diverged` distingue **avanti** (commit locali non pushati, silenzio invisibile) da **indietro** (remote avanti). Non allinea, non pusha, non fetcha: osserva e dichiara | US-299 |
| Check attribution AI su repo cliente | `/ai-policy-check [--repos=...] [--strict]` | opt-in: `ai_policy_check.enabled: true` (eseguibile anche a flag spento) | Stai lavorando su un repo cliente con `suppress_ai_traces: true` e vuoi verificare che attribution AI e ID kanban factory non siano finiti nella history. Layer-2 detective (non sostituisce gli hook git Layer-1). Il repo della factory e' rifiutato esplicitamente. `--strict` per gate pre-push | — |
| Ricerca semantica wiki | `/wiki-search <query>` | opt-in: `wiki_search.enabled: true` | Vuoi ricerca su `wiki/`: con `backend: auto` fts5 senza dipendenze (indice costruito alla prima ricerca), ibrida vector+FTS (LanceDB) se installata; `/wiki-search reindex` per l'indice ibrido | attivazione |
| Burndown sprint | `/sprint-progress [N]` | opt-in: `analytics.sprint_progress.enabled: true` | Vuoi il burndown dello sprint corrente (o N) con fallback kanban | — |
| Velocity del team | `/velocity [--epiche A,B] [--settimane N] [--dal DATA] [--per-persona] [--json]` | si, su richiesta (config facoltativa: `analytics/velocity/config.example.json`) | Vuoi la serie storica su tutto il kanban: punti e TSK chiusi per settimana ISO, media sulle ultime settimane concluse, proiezione sul backlog, tempo di attraversamento. Data di chiusura da `closed_at`, altrimenti dalla storia git; dichiara la qualita' dei dati (registrazioni in blocco, TSK senza taglia o senza inizio). Vista per persona solo con `--per-persona`. Diverso da `/sprint-progress`, che fa il burndown dello sprint corrente da `sprint.md` | [`tools/analytics/team-velocity.py`](tools/analytics/team-velocity.py) |
| Date di lavoro dei TSK | `python3 tools/lint/check-date-lavoro.py [--strict]` · Check 4be | si (ERROR; a `kanban_dates.required_from` assente non segnala nulla) | Vuoi che `/velocity` abbia le date vere: un TSK che passa a `in-progress` dalla data di adozione ha `started_at`, uno che passa a `done` ha `started_at` e `closed_at` (AAAA-MM-GG, `closed_at >= started_at`), con la data del lavoro. Include i cambi non committati; lo storico e' esente; non verifica chi ha lavorato | [`tools/kanban/date_lavoro_check.py`](tools/kanban/date_lavoro_check.py) |
| Report PM deterministico | `/coordinamento` + `pm-report-coordinator` | opt-in: `pm_report.enabled: true` | Vuoi sapere a che punto sono gli obiettivi misurando il kanban a un commit: avanzamento per epica (e per sezione e sottoperimetro — sviluppo, configurazione, test — se configurati, con l'ambiente di rilascio dell'obiettivo), TSK senza owner con eta', avvisi a regole; ogni numero e' ricalcolato da una verifica L0 indipendente prima di essere mostrato. Con `--pianifica` (blocco `pianificazione` della config) classifica i TSK aperti per priorita', urgenza e sblocco e propone un owner (`tools/coordinamento/pianifica.py`, deterministico). **Non scrive nel kanban** (proposte al tpm su gate PO), non arbitra | [tools/coordinamento/README.md](tools/coordinamento/README.md) |
| Dati derivati della wiki | `python3 tools/lint/check_dati_derivati.py [--tolleranza N]` · Check 4bf, 4bg | si (WARNING) | Vuoi sapere se `wiki/log.md` ha voci fuori ordine cronologico oltre `N` giorni (default 7: tipico dopo un merge a unione) e se il contatore `## Sources (N)` dell'index corrisponde alle fonti elencate (no-op se la sezione manca) | [`tools/lint/check_dati_derivati.py`](tools/lint/check_dati_derivati.py) |
| Evidenza dei test BE | `python3 tools/lint/check_evidenza_test_be.py` · Check 4bh | opt-in: `lint.kanban.be_test_evidence: warning\|error` (default `off`) | Vuoi che un TSK `layer: be` chiuso abbia un TSK qa chiuso con `## Esito` verificabile; `be_test_evidence_consumers` (default `[agent]`) e `be_test_evidence_since` (i chiusi prima sono esenti) | [`tools/lint/check_evidenza_test_be.py`](tools/lint/check_evidenza_test_be.py) |
| Target dei TSK | `python3 tools/lint/check_target_tsk.py` · Check 4j | opt-in: `lint.kanban.tsk_target: warning\|error` (default `off`) | Vuoi che un TSK aperto con `consumer: agent` abbia un `target:` e un repository risolvibile (il Check 4j del gate di Fase 0); `tsk_target_gitmodules: true` richiede che un `code_path` sotto `code_repos/` sia in `.gitmodules` | [`tools/lint/check_target_tsk.py`](tools/lint/check_target_tsk.py) |
| Lint deterministico | `python3 tools/lint/run-deterministic.py [--out wiki/lint/AAAA-MM-GG-deterministic.md] [--json] [--strict]` | si | Vuoi i check di `/lint` eseguiti su tutta la popolazione invece che stimati: 1, 4, 4ag, 3, 4as, 4b, 4au, 4am, 4ar, 4aq, 4ax, 4bb, 4bc, 4bd, 4be, 4bf, 4bg, 4bh, 4j. `wiki-lint` li esegue e cita le righe | — |
| Registro della wiki append-only | `python3 tools/wiki/log_append_guard.py [--commit <sha> | --storia N]` · Check 4bb · hook `pre-commit` da `tools/vcs/install_factory_hooks.py` | check sempre; hook opt-in: `wiki_lint.log_append_guard.hook: true` | Vuoi sapere se un commit ha tolto o riscritto righe di `wiki/log.md` senza archiviarle (`rotate_log.py`), o bloccarlo prima del commit. Le entry perse si recuperano verbatim dalla storia con `tools/wiki/recover_log_entries.py` | — |
| Chiusure dei gap verificate | `python3 tools/wiki/verify_gap_closures.py [--tema RE] [--elenco] [--json] [--check]` · Check 4bc | si | Vuoi sapere quali gap chiusi lo sono davvero: conta come chiuso solo il gap la cui chiusura rimanda a una pagina della wiki esistente che cita un raw presente. Gli altri vanno trattati come aperti (WARNING, mai ERROR) | — |
| Registro dei gap append-only | `python3 tools/wiki/gaps_append_guard.py [--storia N] [--strict]` · Check 4bd | si (solo avviso; `--strict` per uscire con errore) | Vuoi sapere se un commit ha tolto o riscritto righe di `wiki/gaps.md`: sono ammessi solo righe aggiunte, il passaggio `- [ ]` → `- [x]` e la sostituzione di un **Aggiornamento** con **Risolto:** nel commit di chiusura. Non agganciato al pre-commit | [`wiki-gap-protocol`](.claude/skills/wiki-gap-protocol.md) §Chiusura con evidenza |
| Citazioni verbatim | `python3 tools/docs/verify_verbatim.py <documento> [--pattern ETICHETTA=REGEX] [--pattern-file F]` | si | Vuoi controllare che un documento derivato riporti alla lettera citazioni e blocchi copiati dalla fonte e non esponga codici interni (ID kanban, ADR, regole; i codici di progetto si passano con `--pattern`) | — |
| Regole del lint per factory | blocco `lint:` in `factory.config.yaml` · `tools/lint/checks_locali.py` · `tools/lint/version_sites_locali.py` | opzionale (senza blocco valgono le regole del master) | La tua factory ha convenzioni proprie: campi obbligatori e raccomandati per tipo, severita' del layer, ID duplicati, scope sui soli aperti, orfani per raggiungibilita', campi data; check propri eseguiti dal runner; siti di versione propri per il 4am. File che il master non ha: l'upgrade non li tocca | `.claude/skills/lint-checks.md` §Check eseguiti da script |
| Contatori a fine TSK | `python3 tools/vcs/contatore_chiusure.py --tsk <id>` (da `dev-handoff`) | opt-in: `repo_align` / `ai_policy_check` con `triggers.on_tsk_closed_count` > 0 | Vuoi che `/repo-align` o `/ai-policy-check` partano da soli ogni N TSK chiusi; contatori in `memory/*-counter.yaml`, mai bloccante | `.claude/skills/dev-handoff.md` |
| Rotazione di `wiki/log.md` | `python3 tools/wiki/rotate_log.py [--apply] [--soglia N] [--forza]` | si | Il log raggiunge 180.000 byte: sposti in `wiki/log-AAAA-MM-GG.md` il prefisso di entry datate fino a oggi, verbatim (sha256 verificato). Dry-run di default | — |
| Lookup simbolo nel codice (L1) | `tools/code-intelligence/ctags-index.sh` + `grep` su `.ctags-state/` | opt-in: `code_intelligence.l1_ctags.enabled: true` | Vuoi sapere dove e' definito un simbolo, senza ML (richiede `universal-ctags`) | code-intelligence |
| Ricerca semantica nel codice (L2) | `/code-search <domanda>` | opt-in: `code_intelligence.l2_semantic.enabled: true` | Vuoi sapere dove viene gestita una funzionalita', a livello di simbolo; `/code-search reindex` per l'indice | code-intelligence |
| Impact graph / blast radius (L3) | `graphify affected "<symbol>"` (Fase 0.bis `dev-protocol`) | opt-in: `code_intelligence.l3_impact.enabled: true` | Vuoi sapere cosa si rompe se cambi un simbolo, prima di toccarlo | code-intelligence |
| Coordinamento kanban multi-utente | `/kanban-status` + `kanban-coordinator` | opt-in: `kanban_coordination.enabled: true` | Siete in piu' persone sullo stesso kanban e vuoi sapere **chi sta su cosa**: cosa hanno pushato gli altri che non vedi, **cosa hai fatto tu che gli altri non vedono**, l'igiene di `assignee:` (assegnazioni ferme) e la contesa misurata. **Non impedisce la doppia presa, non risolve la contesa, non garantisce latenza**: la visibilita' e' al ciclo di push (minuti, non secondi). Se ti serve un lock vero, questa non e' la capability giusta — e non esiste (EP-064 §Esito 2026-09-18) | kanban-coordination |
| Plancia — canale visivo | `/plancia` (`python3 -m visual`) | opt-in: `visual_channel.enabled: true` | Vuoi **vedere** cosa sta facendo la factory invece di ricostruirlo dal transcript: sessione in corso, event store, sprint, costo — ognuno con la propria fonte e la propria eta'. Da li' puoi anche avviare lavoro e rispondere ai gate umani, e accendere il canale vocale. **Non e' uno scrittore**: ogni azione passa dalla sessione. **Non arbitra** la concorrenza. Accessibile per progetto (WCAG 2.2 AA), ma il verde non dichiara «accessibile»: la validazione con persone e' bloccata (EP-067 US-287) | `.claude/commands/plancia.md` |
| Apertura di sessione | `/session-start [--auto\|--quick]` | opt-in: `session_start.enabled: true` (eseguibile anche a flag spento) | Vuoi aprire una sessione di lavoro: ambiente, claim advisory, pull e submodule, raw/ non ingestati, briefing su gap, sprint e sessione precedente. I claim sono advisory: avvisano, non bloccano. Con `session_start.auto_launch` l'hook `tools/session/auto_start_hook.py` e' registrato su `UserPromptSubmit` (su `SessionStart` non raggiungeva la chat nell'estensione VS Code): salta i messaggi che sono gia' `/session-start` e le chat riprese | `.claude/commands/session-start.md` |
| Chiusura di sessione | `/session-close` + `session-sync` | opt-in: `session_close.enabled: true` | Vuoi produrre il documento L1 di fine sessione in `raw/sessions/` (git log, delta wiki/log.md, gap): report citabile, non storico verbatim. La Fase 0 si raccoglie in un passo con `tools/session/close_collect.py` (busta JSON in sola lettura, controlli in parallelo, exit 3 se incompleta); il mutex fra chiusure e' `tools/session/close_lock.py` (acquire/release, TTL, lock orfani) | `.claude/commands/session-close.md` |
| Log applicativi su OpenSearch | `/log` + `log-operator` | opt-in: `log_access.enabled: true` + registro `tools/logs/log-targets.yaml` | Devi analizzare un ticket o un errore guardando i log di un cluster OpenSearch: dal largo allo stretto (count, search, trace), rumore ed errori gestiti per app con conferma, dati personali mascherati di default (HMAC per esecuzione; CF/P.IVA come insiemi opt-in). Sola lettura (`_search`, `_count`, `_field_caps`), solo lato client; l'output di un ambiente protetto non si scrive con `--out` in `raw/`, `wiki/`, `deliverables/`, `management/` (rifiuto nel codice) | skill `log-access-protocol` · `indagine-protocol` |
| Database PostgreSQL | `/db` + `db-operator` | opt-in: `db_access.enabled: true` + registro `tools/db/db-targets.yaml` e `.env.db` | Devi leggere un database partendo da ambiente e servizio, schema, tabella o funzionalita': catalogo DDL versionato (`db_catalog.py`) con avviso di obsolescenza, mappa funzionalita'-servizio-tabella (`db_map.py`), gate di costo con EXPLAIN e timeout per ambiente. Lettura con whitelist + transazione READ ONLY lato server; TLS `verify-full`; scrub dei dati personali nel catalogo acceso. Scrittura spenta (`db_access.write.enabled`), mai su `read_only_envs`, `--commit` solo con token e gate umano | skill `db-access-protocol` |
| Test Cypress da TSK qa | `/cypress-gen <TSK-id>` + `cypress-test-analyst` / `qa-dev` (modalita' Cypress) / `cypress-test-reviewer` | opt-in: `cypress_pipeline.enabled: true` + repo in `cypress_pipeline.repos[]` | Hai un TSK `layer: qa` che chiede spec Cypress in un repo di test registrato: analisi, generazione, review statica con 2 gate umani; artefatti in `code_quality/cypress/<TSK-id>/`, mai nel repo di test; report dei lanci con `tools/cypress/run_report.py` (profilo `generic` o custom) | skill `cypress-generation-protocol` · [`tools/cypress/README.md`](tools/cypress/README.md) |
| Promemoria fra operatori | `/promemoria` | opt-in: `promemoria_operatori.enabled: true` | Vuoi lasciare un promemoria a te o a un altro operatore della factory, consegnato a chi apre la sessione, con ricevute di lettura e anagrafica (`memory/promemoria/operatori/`, esempio `.example`). Remote e ramo configurabili; ogni push passa da un gate di conferma (`--yes` solo dopo consenso esplicito). Il mittente viene da `git config`, non e' firmato | `.claude/commands/promemoria.md` |
| Onboarding Day 0 per ruolo | `/onboarding [--ruolo R] [--compact] [--check-env]` | opt-in: `onboarding_day0.enabled: true` (spento: `/onboarding` v1.0) | Un nuovo contributor deve partire dal suo ruolo: passi Day 0 da `day0-per-ruolo.md` o da `onboarding_day0.roles`, verifica con `tools/onboarding/verifica_day0.py`. Funziona senza `/promemoria` | skill `onboarding` |
| Controllo ambiente factory | `/init-check [--probes] [--json]` | si (no flag; blocco `environment:` opzionale in config) | Vuoi verificare che l'ambiente locale sia pronto: python3/git/shell/autocrlf/code_paths/submodule + binari (anche alternativi, `any_of`)/env_file/variabili (dall'ambiente o da un file `.env`, `variables.source_file`)/`.nvmrc` per code_path/sonde dichiarate in `environment:`. Sonde di rete solo con `--probes` | `tools/env/init_check.py` |
| Vista gap aperti | `python3 tools/wiki/gaps_open_view.py` | si | Vuoi i gap wiki ancora aperti (`wiki/gaps.md`) in forma compatta in `memory/gaps-open.md`; riconosce il formato (sezioni chiuse da `**Risolto:**` o voci `- [ ]` / `- [x]`) | `tools/wiki/gaps_open_view.py` |
| Registro namespace kanban | `tools/kanban/next-id.py --namespace <ns>` | opt-in: `kanban_namespaces.enabled: true` | Vuoi generare ID con prefisso di namespace (derivate multi-namespace). A flag spento il namespace e' assente. Indipendente dal flag: `next-id.py` unisce gli ID del ramo remoto (`--remote`/`--branch`, default `origin`/`main`; `git fetch` fail-open, `--no-fetch`), cosi' due macchine non assegnano lo stesso ID; `--no-remote` o `NEXT_ID_OFFLINE=1` lo spengono, `--strict` fallisce se il remoto non e' leggibile, `--json` per gli script | `tools/kanban/README-namespaces.md` |
| Sprint come vista generata | `python3 tools/kanban/generate_sprint.py [--check] [--stdout] [--root]` | opzionale (adottarlo = `sprint.md` non piu' curato a mano) | Vuoi che `sprint.md` non deragli dal frontmatter: lo rigenera dai TSK aperti (sprint corrente e lookahead per epica); `--check` esce 1 se la vista non e' aggiornata | `tools/kanban/generate_sprint.py` |
| Resolver session_id canonico | `tools/session/session_id.py` | si (stdlib) | Vuoi un session_id univoco per sessione (env → scratchpad → generato, mai in silenzio). Usato da session-close/start e da harvest-tokens | `tools/session/session_id.py` |

---

## Quando devo pianificare o gestire il prodotto

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Trasformazione wiki in backlog | `product-manager` | si | Hai la wiki pronta e vuoi produrre EP/US dal materiale ingestato | prd-driven-autonomy |
| Design architetturale | `lead-architect` | si | Hai EP/US e vuoi disegnare BE/FE/API/DB | — |
| Task planning | `tpm` | si | Hai US approvate e vuoi scomporle in TSK atomici con `sprint.md` | — |
| Riconciliazione periodica del kanban | `tpm` + skill `tpm-reconcile` | si (sola lettura) | Vuoi sapere dove il kanban dichiarato diverge dall'esecuzione: dipendenze insoddisfatte, drift temporale, blocco silenzioso, assegnazione ferma; report con una raccomandazione per anomalia, nessuna scrittura | `.claude/skills/tpm-reconcile.md` |
| Chiusura di una wave | `tpm` + skill `tpm-wave-close` | si | A fine wave, prima di report e push: gate DoD, patch git↔status proposta, gap CRITICAL senza `bridge_tsk`, commit atomico del kanban (gate umano su patch e apertura TSK) | `.claude/skills/tpm-wave-close.md` |
| Query kanban | `wiki-query` | si | Vuoi rispondere a domande sullo stato di epiche, sprint, TSK | — |

---

## Quando voglio sviluppare codice o documentazione con agenti

Richiede `topology: full-stack-agents` o `hybrid-*` in `factory.config.yaml`.

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Sviluppo backend | `/dev <TSK-id>` → `be-dev` | topologia | Hai un TSK `layer: be` pronto (status: todo) | topology-and-dev-agents |
| Sviluppo frontend | `/dev <TSK-id>` → `fe-dev` | topologia | Hai un TSK `layer: fe` pronto | topology-and-dev-agents |
| Sviluppo database | `/dev <TSK-id>` → `db-dev` | topologia | Hai un TSK `layer: db` (migration, schema) | — |
| Sviluppo QA | `/dev <TSK-id>` → `qa-dev` | topologia | Hai un TSK `layer: qa` (test unit/integration/e2e) | — |
| Sviluppo documentazione | `/dev <TSK-id>` → `docs-dev` | topologia | Hai un TSK `layer: docs` (skill, command, agente, config, wiki) | — |
| Submodule tooling guidato | `/sm-doctor` + `sm_commit --coordinated` | opt-in: `vcs_tooling.submodule_doctor.enabled: true` | Vuoi gestire i submodule dichiarati in `code_paths[]` (doctor, status, checkout, update, hook pre-commit); con `vcs_tooling.submodule_scope: gitmodules` tutti quelli di `.gitmodules`. Senza entry submodule in config: exit 0 + messaggio esplicito. Zero costanti verticali cablate | `tools/vcs/README-submodule.md` |
| Sito di documentazione tecnica | `/doc-tecnica [--out DIR] [--sections a,b] [--dry-run]` | opt-in: `documentation.enabled: true` | Vuoi pubblicare la wiki come sito statico HTML autocontenuto (indice, navigazione, ricerca), dopo un controllo segreti bloccante | `tools/docs/build_tech_site.py` |
| Documentazione funzionale di un servizio | `/doc-funzionale <servizio> --pubblico=cliente\|utente\|entrambi` + skill `functional-docs-protocol` | opt-in: `documentation.enabled: true` | Vuoi manuale per il cliente e/o guida utente di un servizio, scritti dalla sola wiki con fonti e lacune dichiarate (bozza fino ad approvazione umana) e resi in HTML/Word | `.claude/skills/functional-docs-protocol.md` |
| Digest settimanale per il management | `/digest-settimanale [--settimana=YYYY-Www] [--commento=<file.md>] [--json]` | opt-in: `documentation.enabled: true` | Vuoi un riepilogo settimanale (TSK chiusi, rilasci, gap, incidenti, costi) con numeri calcolati da script, mai dal modello | `tools/docs/weekly_digest.py` |
| Portabilita' shell script | skill `shell-portability` | si (skill, no gate) | Vuoi scrivere script shell portabili su bash/zsh/gitbash/wsl; la skill elenca i costrutti da evitare e le alternative POSIX | `.claude/skills/shell-portability.md` |
| Scrittura controllata (STE-lite) | `/ste-lite <file> [--rewrite]` + skill `ste-lite-protocol` | opt-in: `ste_lite.enabled: true` (su file espliciti gira anche spenta) | Un testo che legge una persona e' troppo denso: il linter deterministico `tools/lint/ste_lite.py` controlla le regole strutturali di ASD-STE100 (frasi, paragrafi, un'istruzione per frase, voce attiva nelle procedure, glossario); `--rewrite` riscrive tenendo tutti i fatti e chiude con la sezione «Omesso». Il verdetto e' del linter, non di chi scrive. Il dizionario dello standard resta fuori. Resta spenta per decisione (EP-076 TSK-809): su richiesta, solo variante lite. Allunga il testo, non lo accorcia | sorgente |

---

## Quando voglio verificare la qualita' del codice

Si attiva con `code_quality.enabled: true` in `factory.config.yaml`.

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Code review automatizzato | `/review <TSK-id>` + `code-reviewer` | opt-in: `code_quality.enabled: true` | Hai un TSK `status: done` e vuoi un verdict idiomaticita'/design/robustezza | code-quality-review-layer · runbook |
| Review CQRL di default | Fase 4-quater di `dev-protocol` + `dispatch-policy` §12 | opt-in: `code_quality.trigger_default.enabled: true` | Vuoi che la review parta da sola sui TSK dei layer/consumer scelti: il dev-agent imposta `review_status: pending`, l'orchestrator dispatcha `code-reviewer` su `/run` (su `/dev` lo segnala la verifica di chiusura) | `.claude/skills/references/dev-protocol/fase4-quater-cqrl-trigger.md` |
| Rilevamento test instabili | `flakiness-detection-protocol` (skill) | opt-in: `qa_layer.flakiness_detection.enabled: true` | Vuoi identificare test flaky su rolling window di run | flakiness-detector |
| YAGNI review di un diff | `/ponytail-review <TSK\|branch\|file>` | opt-in: `ponytail.enabled: true` (HARD DEP su `code_quality.enabled`) | Vuoi i candidati alla semplificazione via Decision Ladder a 7 livelli (advisory, nessun verdict) | decision-ladder · ponytail |
| YAGNI audit full-repo | `/ponytail-audit [<path>]` | opt-in: `ponytail.enabled: true` | Vuoi lo scan YAGNI su tutto il `code_path`; alimenta la riga `ponytail-gain` del token ledger | ponytail-ab-study |
| Verifica consistenza output | `consistency-checker` (agente) | opt-in: `compression.output.consistency_check.enabled: true` | Vuoi verificare che un sub-agent non contraddica le decision anchor | consistency-checker · runbook |
| Verifica migrazione codice | `/migration-verify` + `code-cartographer` + `migration-verifier` | opt-in: `code_migration.enabled: true` (eseguibile anche a flag spento) | Hai migrato o stai migrando un codebase fra due repo (es. Vue 2 → Vue 3, CRA → Vite) e vuoi misurare la parita' funzionale su quattro assi. Oracolo, non attuatore: `reject`/`divergent`/`ambiguous` sono gate umani JSON | `.claude/commands/migration-verify.md` |

---

## Quando voglio analizzare il rischio prima di iniziare

Si attiva con `premortem.enabled: true` in `factory.config.yaml`.

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Analisi premortem | `/premortem` | opt-in: `premortem.enabled: true` | Vuoi identificare failure mode probabili prima di iniziare un epic o TSK | premortem-skill · factory-premortem-integration · runbook |

---

## Quando voglio lavorare su design, UX o accessibilita'

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Design UI | `/ux-ui-design` + `ui-designer` | opt-in: `ux_ui.enabled: true` | Vuoi produrre wireframe, spec, flussi con rationale esplicito | ux-ui-review-design-capability · runbook |
| Review UX/UI | `/ux-ui-review` + `ux-ui-reviewer` | opt-in: `ux_ui.enabled: true` | Vuoi valutare un'implementazione contro rubrica Nielsen + 6 dimensioni UI | ux-ui-review-design-capability · rubrica anti-soggettivita' · runbook |
| Accessibilita' WCAG 2.2 AA | `/a11y` + `a11y-specialist` | opt-in: `a11y.enabled: true` | Vuoi uno scan accessibilita' end-to-end con report | accessibility-testing-capability · runbook |
| Visual Oracle FE | `/visual-oracle` | opt-in: `fe_correctness.enabled: true` | Vuoi confrontare screenshot expected vs actual per regressioni visive | correctness-oracle · installazione |
| Functional Oracle FE | `/functional-oracle <TSK-id\|app>` | opt-in: `fe_correctness.functional_oracle.enabled: true` | Vuoi verificare il comportamento funzionale navigando l'app con scenari | correctness-oracle |
| Design Intelligence Layer | protocolli interni EP-019 | opt-in: `design_intelligence.enabled: true` | Vuoi coordinamento tematico centralizzato (art-director DSL), separazione LLM/generatore, Critic/Judge design | art-director-coordination · llm-generator-separation · critic-judge-agent · intention-economy |

---

## Quando devo analizzare costi e tempi

Si attiva con `analytics.measurement.enabled: true` in `factory.config.yaml`.

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Misurazione costi/tempi reali | `/analytics` + `analytics-reporter` | opt-in: `analytics.measurement.enabled: true` | Vuoi misurare costi e tempi effettivi per TSK, sprint, periodo. Faccia retrospettiva | task-analytics-cost-estimation-capability · runbook · prezzi |
| Stima costi/tempi futuri | `/estimate` + `estimation-analyst` | opt-in: `analytics.estimation.enabled: true` | Vuoi produrre stime difendibili: intervallo + confidenza + contingency. Faccia previsionale | task-analytics-cost-estimation-capability |
| Token ledger inline | automatico + `/token-ledger [--full]` | opt-in: `analytics.token_ledger.enabled: true` | Vuoi vedere token reali e costo stimato a fine di ogni risposta con tool call (o su richiesta) | — |
| Alert sui costi in token | `/cost-alert [--period=...] [--breakdown] [--pending] [--ack=<id>]` + agente `cost-alert` | opt-in: `analytics.cost_alert.enabled: true` (+ `agent: true` per il path escalate) | Vuoi sapere se sessione, giornata, settimana o mese hanno superato le soglie di `analytics/alert-rules.yaml`: regole generali, regole personali per operatore (`operator`, che per il suo periodo sostituisce la generale) e quota inclusa nel piano di abbonamento dell'operatore (`plans` + `subscriptions`, con stima di addebito). Gira anche da solo: statusLine, `/session-start`, `/session-close`, `/run`, `/analytics`, `/session-analysis`, prima di lanciare agenti (`dispatch-policy` §13), nei wave e nella plancia. Misura solo le sessioni Claude Code della macchina | skill `cost-alert-protocol` |
| Stima adattiva di durata | `temporal-estimate-protocol` (skill) | opt-in: `temporal.estimate_protocol.enabled: true` | Vuoi stime elapsed/progress adattive durante l'esecuzione agentica | — |
| Session analysis post-hoc | `/session-analysis [--depth=full] [--retro]` | opt-in: `session_analysis.enabled: true` (`--retro` anche `engineering_practices.enabled`) | Vuoi analizzare anomalie (ERROR/BUDGET/DISPATCH) di una sessione Claude Code **chiusa** (out-of-band, no auto-fix). Con `--depth=full` una nota LLM advisory sugli aggregati redatti, solo in «Punti Aperti» (`llm-advisory.py` via `claude -p`, budget, STOP su fughe, modello da `session_analysis.advisory_model` o `models.routing.tier_fast`); con `--retro` la retrospettiva di `pocock-retro` | [session-agentic-analyser](wiki/concepts/session-agentic-analyser.md) · [handoff fleet-doctor](wiki/runbooks/session-analysis-fleet-doctor-handoff.md) |

---

## Quando affronto un problema complesso multi-dominio o voglio un prototipo

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Tavola Rotonda | `/tavola-rotonda "<topic>"` | opt-in: `tavola_rotonda.enabled: true` | Problema genuinamente complesso/multi-dominio: deliberazione strutturata multi-agente con Critico anti-compiacenza. I partecipanti li lancia la sessione principale (un subagente non lancia altri agenti); il moderatore cura setup, convergenza e sintesi; `tools/tavola-rotonda/verifica-lanci.py --registro` verifica che i lanci siano reali (ADR-EP073-001) | runbook |
| Prototype generation | `/prototype [--variants=N]` + `prototype-generator` | opt-in: `prototyping.enabled: true` | Vuoi un prototipo grafico (cascata figma→penpot→react→html, fallback html garantito) | — |
| Diagnostica prototyping | `/prototype-status` | opt-in: `prototyping.enabled: true` | Vuoi sapere quale backend verrebbe scelto e cosa e' disponibile, senza generare nulla | — |
| Tutoring adattivo | `tutor` (agente) | opt-in: `capability_formativa.enabled: true` | Vuoi spiegazioni con tag epistemici L1/L2/L3, retrieval citato e scaffolding adattivo (Student Model SM-2) | design-capability-formativa |
| Fleet health / skill hygiene | `/refactor` + `fleet-doctor` | opt-in: `refactor_agent_skills.enabled: true` | Vuoi rifattorizzare skill/agenti sovradimensionati in divulgazione progressiva | [skill-hygiene](wiki/runbooks/skill-hygiene.md) |

---

## Quando devo gestire la governance del framework

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Complexity budget | `/complexity-budget` | opt-in: `complexity_budget.required_on_release: true` | Vuoi verificare che ogni EP rispetti il budget N:1 (aggiunta vs deprecazione) | complexity-budget · runbook |
| Semantic drift detection | `/semantic-drift-scan` | opt-in: `wiki_lint.semantic_check.enabled: true` | Vuoi rilevare divergenza tra wiki e codice reale (L1 staleness always-on, L2 LLM-judge, L3 embedding) | semantic-drift-prerequisites |
| Wiki gap detection | `wiki-gap-protocol` (skill) | si | Vuoi identificare lacune nella wiki rispetto al kanban | — |
| Temporal budget governor | `temporal-budget-governor` (skill) | opt-in: `temporal.budget.enabled: true` | Vuoi vincolare la durata economica di processi agentici (anti-runaway) | temporal-budget-governor · runbook |
| Viste filtrate del PATTERN | `/pattern-view [profilo]` | si | Vuoi leggere solo le sezioni del PATTERN pertinenti al tuo profilo di adozione (minimal/standard/full) | — |
| Ciclo di vita delle capability | campo `status:` nei blocchi di `factory.config.yaml` (PATTERN-governance §23.11) | si (metadata) | Vuoi dichiarare se una capability accesa e' davvero in uso: `active` / `dormant` / `deprecated` / `removed`; nessuna transizione cambia `enabled` senza decisione umana | `PATTERN-governance.md` §23.11 |
| Handover fra repo senza history | `/repo-handover` | opt-in: `repo_handover.enabled: true` | Vuoi esportare lo stato corrente di un code_path su un repo vergine (SHA fisso, nessuna history, push mai automatico, gate locali opzionali su SHA immutabile) | `.claude/commands/repo-handover.md` |
| Registro namespace kanban (config) | `tools/kanban/id_registry_check.py` · `namespace_orphans.py` | opt-in: `kanban_namespaces.enabled: true` | Vuoi verificare la coerenza del registro dei namespace e trovare ID orfani nelle derivate multi-namespace | `tools/kanban/README-namespaces.md` |
| PATTERN in moduli + manifesto | `PATTERN.md` (indice §0-§11) + `PATTERN-{integration,runtime,governance,capabilities}.md` | si | Il PATTERN e' diviso in un indice e quattro moduli tematici: carica solo il modulo pertinente al tuo comando o agente consultando il manifesto | `.claude/skills/references/dispatch-policy/manifesto-caricamento.md` |
| Copertura schema config | `python3 tools/lint/check-config-schema-coverage.py [--json] [--root]` | si (stdlib) | Vuoi verificare che tutte le chiavi top-level di `factory.config.yaml` siano dichiarate in `schemas/factory.config.schema.json`. Exit 1 se ci sono chiavi non dichiarate (UNDECLARED); schema-only e' solo INFO | `tools/lint/check-config-schema-coverage.py` |
| Stato degli adapter dai manifest | `python3 tools/docs/gen-status.py [--check]` | si (stdlib, in CI) | Vuoi che la maturita' degli adapter abbia una sola fonte: il blocco generato di `docs/STATUS.md` e `docs/STATUS.it.md` nasce da `adapters/*/manifest.yaml`; `--check` (exit 1) segnala un blocco indietro o una riga della tabella «Adapter registry» di CLAUDE.md con maturita' o contract diversi dal manifest (EP-080) | `docs/STATUS.md` |
| Traccia di un'epica | `python3 tools/docs/trace-epic.py EP-NNN [--ref R] [--out F]` | si, su richiesta (stdlib + git) | Vuoi mostrare la catena decisione → criteri → task con date e chiusure alla lettera → commit → PR → voce di log, generata da kanban e git invece che scritta a mano. Sola lettura sul kanban (EP-080) | `docs/trace/` |
| Esempio eseguibile | `examples/hello-factory/` · `python3 -m pytest tools/tests/test_hello_factory.py` | si (in CI) | Vuoi vedere la catena completa in miniatura senza installare nulla: fonte, pagina wiki citata, epica, storia, task chiuso con evidenza, codice, review, log. Il test esegue i check deterministici sull'esempio e verifica che un anello rotto venga trovato (EP-081) | `examples/hello-factory/README.md` |
| CI sulle PR | `.github/workflows/ci.yml` | si, su ogni PR e push su main | Vuoi che i check deterministici e la suite girino senza che qualcuno li lanci: bloccanti i check verdi (4au, 4am, 4ar, 4aq, 4ax, 4bb, 4bc, 4bd, 4be), `gen-status --check` e pytest; 1 e 3 in sola lettura finche' il loro debito non e' a zero (EP-080) | `docs/GUARANTEES.md` |

---

## Quando devo pubblicare il kanban, usare piu' adapter o creare una nuova factory

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Publish kanban esterno | `/kanban-publish` + `github-publisher` | opt-in: `kanban_publish.provider: github` | Vuoi un mirror push-only di EP/US/TSK su GitHub Issues/Milestones (o GitLab/Jira/Linear) | publisher-adapters |
| Multi-adapter | `adapters/<name>/` | si (dichiarazione) | La factory deve girare su Claude Code, Cursor, Aider, OpenAI, Gemini contemporaneamente | multi-adapter-scaffolding |
| Condivisione artefatti HTML | `/share <html-path> [--dry-run]` | opt-in: `content_share.enabled: true` | Vuoi pubblicare un artefatto HTML su soli-frames via `repository_dispatch` (gate umano obbligatorio R.CS3) | content-share-hub-pattern · [setup](wiki/runbooks/content-share-setup.md) |
| Canale vocale handsfree | `/voice-install` + `voice-channel-installer` | opt-in: `voice_channel.enabled: true` | Vuoi parlare con la factory: STT/TTS/VAD, wake word, state machine 5 stati, LaunchAgent macOS | voice-channel · installazione · uso |
| Factory come MCP server | `adapters/mcp/` | opt-in: `mcp_server.enabled: true` | Vuoi esporre la factory in read-only a un client MCP esterno (R.MCP1 no-write) | — |
| Release artefatti applicativi | `/release-artifact <target> [--dry-run]` + `artifact-release-manager` | opt-in: `artifact_release.enabled: true` + `release_targets: [...]` non vuoto | Vuoi rilasciare un artefatto (container-gitops, package-registry, manifest-edit) a partire da SHA immutabile verificato da `worktree-gate`. Gate umano R.14 obbligatorio; push mai automatico | `.claude/commands/release-artifact.md` |

---

## Quando voglio ridurre i token usati dagli agenti

Si attiva con i flag `compression.*` in `factory.config.yaml`.

| Capability | Comando | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Output compression (Caveman) | `/compression` | opt-in: `compression.output.enabled: true` | Vuoi ridurre la verbosita' degli output degli agenti interni (Fase 1) | factory-compression-layer · token-compression |
| Context compression (Graphify) | `/graphify-sync` | opt-in: `compression.context.enabled: true` | Vuoi sostituire il codice sorgente con un knowledge graph come contesto per i dev-agent (Fase 2) | factory-compression-layer · knowledge-graph-codebase · installazione |
| Token harvest compatto | `/harvest-tokens` | si | Vuoi contare i token usati nella sessione corrente senza path cablati: discovery automatica del transcript via session_id | `.claude/commands/harvest-tokens.md` |

Caveman comprime solo i messaggi fra agenti: verso l'utente e verso gli artefatti e' spento (PATTERN §20.2, R.C1). Per i testi che legge una persona c'e' la grammatica opposta, STE-lite (`/ste-lite`), che vieta di togliere articoli e verbi.

---

## Quando applico le pratiche di ingegneria (EP-077, opt-in)

Adattate dalle skill di Matt Pocock (MIT, copia fedele al commit 49dd158 in `vendor/mattpocock-skills/`).
Provenienza: pilota della derivata portale-servizi-factory. **Stato: spente** (`engineering_practices.enabled: false`);
la misura finale del pilota nella derivata non e' ancora disponibile. Le skill interattive girano solo nella sessione principale.

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| TDD a fette verticali | skill `pocock-tdd` (dev-protocol Fase 3) | opt-in: `engineering_practices.enabled`, sui TSK con `test_seams_status: confermati` | TSK con logica testabile: test rosso, codice minimo, verde, seam per seam | `.claude/skills/pocock-tdd.md` |
| Diagnosi dei bug difficili | skill `pocock-diagnosing-bugs` | opt-in: `engineering_practices.enabled` | Bug con causa ignota: segnale rosso, ipotesi, gate del Tech Lead, test di regressione | `.claude/skills/pocock-diagnosing-bugs.md` |
| Intervista sulle decisioni | skill `pocock-grilling` | opt-in: `engineering_practices.enabled` | Prima di un'epica: domande a turni con risposta consigliata | `.claude/skills/pocock-grilling.md` |
| Aderenza alla specifica in CQRL | `/review` (Passata 6) | opt-in: `code_quality.passes.spec_adherence: true` | Il diff confrontato con TSK, US e constraints dell'epica | `.claude/skills/references/code-review-protocol/passata-6-aderenza-spec.md` |
| Retrospettiva sull'ambiente | skill `pocock-retro` | opt-in: `engineering_practices.enabled` | Su una sessione chiusa: proposte, con gli errori meccanici trasformati in controlli | `.claude/skills/pocock-retro.md` |
| Glossario e moduli profondi | `pocock-domain-modeling`, `pocock-codebase-design`, `pocock-improve-codebase-architecture` | opt-in: `engineering_practices.enabled` | Si chiarisce un termine del dominio; si progetta o si cerca un modulo superficiale | `.claude/skills/pocock-codebase-design.md` |
| Indicatori e bilancio N:1 | `python3 tools/pocock/kpi_pilota.py --dal <data>` · `python3 tools/pocock/bilancio_n1.py` · `python3 tools/pocock/verify_vendor.py` | si (stdlib + pyyaml) | Gli 8 indicatori, il bilancio delle parole aggiunte e potate, la verifica della copia vendorizzata | `analytics/pocock-pilota/README.md` |

---

## Quando curo il mestiere della UI (EP-090, opt-in)

Adattate da emilkowalski/skills (MIT, copia fedele al commit 715c180 in `vendor/emilkowalski-skills/`).
Si adotta il metodo, non il gusto come legge: le regole del motion sono euristiche d'autore, quindi la passata
e' **advisory** e non produce verdetto. **Stato: spente** (`ui_craft.enabled: false`, `prototyping.variants: 1`).

| Capability | Comando / Agente | Sempre attiva? | Quando usarla | Approfondimento |
|---|---|---|---|---|
| Dati del caso peggiore | `/worst-case <componente\|TSK-id\|path>` · fase opzionale del functional oracle | opt-in: `ui_craft.enabled` + `ui_craft.worst_case_data` | Una UI che regge solo con i dati demo: valori dallo schema reale, fixture Empty/One/Huge, toggle solo dev, report delle rotture prima di correggere | `.claude/skills/kowalski-worst-case-data.md` |
| Revisione del motion in CQRL | `/review` (Passata 7) | opt-in: `ui_craft.enabled` + `ui_craft.motion_review`, solo diff con motion | 10 standard (easing, durate, origine, interrompibilita', GPU, reduced-motion), tabella Prima/Dopo/Perche', nessun verdetto | `.claude/skills/kowalski-motion-review.md` |
| Varianti divergenti | `/prototype --variants N` (2..5) | opt-in: `prototyping.enabled`; N anche da `prototyping.variants` | Esplorare N direzioni su assi nominati dietro un selettore neutro; la scelta e' umana. Solo backend html, gli altri degradano a 1 | `.claude/skills/references/prototype-generation-protocol/varianti.md` |
| Stop sulla deriva del TSK | campo TSK `base_commit:` | opt-in per presenza del campo | TSK che cita `file:riga`: se il codice e' cambiato dal commit, il dev-agent si ferma (`blocked`) invece di improvvisare | `.claude/skills/references/dev-protocol/base-commit-deriva.md` |
| Verifica delle copie vendorizzate | `python3 tools/pocock/verify_vendor.py [--vendor <cartella>\|--all] [--clone <path>]` | si (stdlib) | Le copie in `vendor/` coincidono con il commit dichiarato in `ORIGINE.md` | `vendor/emilkowalski-skills/ORIGINE.md` |

---

## §kanban_coordination — Kanban Multi-User Coordination (EP-064, v2.43, opt-in)

Capability opt-in per il coordinamento fra piu' persone che lavorano lo stesso kanban
su git. Read-only sul kanban, zero dipendenze esterne (stdlib Python), zero processi
permanenti. `kanban_coordination.enabled: false` di default.

**Cosa da':**

| | Segnale |
|---|---|
| Disgiunzione in **pianificazione** | campo `assignee:` advisory (US-253) — chi si e' preso cosa, prima di iniziare |
| **Visibilita' bidirezionale** al ciclo di push | cosa hanno fatto gli altri che non vedi **e cosa hai fatto tu che gli altri non vedono** (US-266) — la seconda meta' e' quella che previene la collisione: rende visibile all'autore il proprio silenzio |
| **Misura** della contesa | collisioni reali nella finestra, con la condizione di riapertura eseguibile in un comando (US-251) |

**Cosa NON da'** — vincolante (US-267 AC8), non ammorbidibile in nessun documento: non impedisce la doppia presa; non risolve la contesa a runtime (nessun lock, nessun lease, nessun arbitro); non garantisce alcuna latenza (visibilita' al ciclo di push, minuti non secondi). Dettaglio in `CLAUDE.md §kanban_coordination`.

| Aspetto | Valore |
|---|---|
| Agente owner | `kanban-coordinator` (`.claude/agents/kanban-coordinator.md`) |
| Skill | `.claude/skills/kanban-coordination-protocol.md` |
| Comando | `/kanban-status` (`.claude/commands/kanban-status.md`) — report in-chat; fallback esplicito a capability non configurata, mai errore |
| Tool | `tools/kanban-observer/kanban-observe.py` (visibilita', `[--json] [--no-fetch]`), `tools/kanban-trial/collision-oracle.py` (misura, `--days N`) |
| Config gate | `kanban_coordination.enabled: false` (default) + `oracle_window_days: 30` + `stale_assignment_days: 7` |
| Soglia assegnazione ferma | riferimento per `assegnazione_ferma_soglia_giorni` di [`tpm-reconcile`](.claude/skills/tpm-reconcile.md) §3.4 (FM-NEW-1) |
| Runbook | `wiki/runbooks/kanban-coordination.md` |
| Vincoli | read-only sul kanban; nessun `git push`/`git pull` (§7 r.14); nessuna scrittura in `wiki/` (§7 r.12); nessuna modifica di `status:`. Osserva, misura, **raccomanda** (US-267 AC4) |
| Provenienza | Tavola Rotonda TR-9b4e7c02 — `wiki/decisions/tavola-rotonda-9b4e7c02-5a1d-4f38-8c61-2d7a3e9f5b40-2026-09-17.md` (§Sintesi + §Addendum) |

### L'oracolo e' asimmetrico — invariante di lettura

```bash
python3 tools/kanban-trial/collision-oracle.py --days 30
```

- `>=1` collisione ⇒ il problema **e' reale**: i **43 TSK** chiusi (US-254..US-261, l'arbitro
  self-hosted con lease) si riaprono col loro contenuto tecnico intatto. La condizione e'
  eseguibile e **non discrezionale**.
- `0` collisioni ⇒ **nessuna informazione**. Mai «il problema non esiste». Su questo repo
  `management/kanban/` ha **320 commit da un solo autore**: lo zero e' inevitabile **per
  costruzione**, non e' un'evidenza di assenza di contesa.

L'agente non deve poter concludere che la contesa non esiste (US-267 AC3).

### Perche' l'arbitro non e' stato costruito

EP-064 ha chiuso **43 TSK come superflui, non rinviati**: l'arbitro con lease costava
**12-23 sprint della capacita' totale** della factory per risolvere una contesa misurata
**zero volte** su questo repo, su un host che dietro NAT domestico o aziendale **non e'
raggiungibile**. Nessuna variante sposta la stima — designazione, non-24/7 e mesh attaccano
tutte la periferia mentre il costo e' nel core. **Tre istruttorie indipendenti convergono**
(US-252 modello di allocazione, US-263 stima ricalcolata, US-265 variante host designato).

Cosa si perde rispetto alla richiesta iniziale: il blocco duro sulla doppia presa e la
latenza 1-5 s. Cosa si ottiene: la disgiunzione in pianificazione e la visibilita'
bidirezionale, a **meno dell'1% del costo**. Dettaglio in
`EP-064.md`
§«Esito 2026-09-18».

---

## §visual_channel — Plancia, canale visivo (EP-067, v2.44, opt-in)

Implementazione del **canale visivo** che il contratto `FactoryRuntime` di EP-041 dichiara
e che era rimasto «stdout strutturato in MVP» (PATTERN §30.13). Gemello dello stesso porto
del Voice Channel: voce e schermo leggono **la stessa sequenza di eventi**, distribuita da
un unico `Tee`.

```bash
python3 -m visual --force          # http://127.0.0.1:8756
python3 -m visual --check          # configurazione risolta, senza avviare
python3 -m visual --root ../altra-factory
```

**Cosa mostra**: sessione in corso (dal transcript del runtime), event store, sprint,
avanzamento delle attivita' (report PM di EP-070, numeri del motore verificati da L0, con
link al report completo), sessioni con claim, costo. Ogni misura dichiara **fonte, eta' della lettura e eta' del
dato** — tre cose distinte. Una fonte illeggibile dice «non osservabile» con la ragione,
**mai zero**.

**Cosa NON fa** — vincolante: non e' uno scrittore (ogni azione e' una `submit()`, lo scrittore
resta la sessione); non arbitra la concorrenza (dichiara le altre sessioni, nessun lock ne'
lease); la mascotte non e' un canale di accesso (codifica ridondante, sempre nascosta alle
tecnologie assistive, mai unico veicolo di un'informazione); il verde WCAG non dichiara
«accessibile» (la validazione con persone e' US-287, bloccata). Dettaglio in `CLAUDE.md §visual_channel`.

| Aspetto | Valore |
|---|---|
| Comando | `/plancia` (`.claude/commands/plancia.md`) |
| Pacchetto | `visual/` — solo stdlib, nessuna dipendenza nuova |
| Config gate | `visual_channel.enabled: false` (default) + `host` + `port` + `runtime_timeout_seconds` + `stale_after_seconds` + `coordinamento.{fonte,config}` |
| Report PM | riquadro `coordinamento`: rilancia `tools/coordinamento/run.py` solo quando cambia l'impronta del kanban; richiede `pm_report.enabled: true`; uscite in una cartella temporanea fuori dal repo |
| Canale vocale | si accende dalla plancia; stesso flusso, stesso filtro `tts_payload` |
| A11y | axe 0/0/0 + 17 check deterministici (`tools/a11y/target-checks.mjs`) |
| Documentazione | `.claude/commands/plancia.md` — uso, configurazione, diagnostica |
| Pattern | §30 (canale asimmetrico). Nessuna sezione propria: §23.8 vieta la cerimonia prima dell'esercizio |

---

## §code_intelligence — Code Intelligence Stack (EP-054, v2.37, opt-in)

Stack a tre layer local-first per navigazione codice da parte degli agenti.
Zero dipendenze esterne. `code_intelligence.enabled: false` di default (R.CI1).

| Layer | Tool | Risponde a | Comando |
|---|---|---|---|
| L1 Symbol Resolver | universal-ctags | "dove è definita X?" | `grep` su `.ctags-state/` |
| L2 Semantic Search | tree-sitter + nomic-embed-code + LanceDB | "dove viene gestita Y?" | `/code-search <query>` |
| L3 Impact Graph | graphify (EP-052) | "cosa si rompe se cambio Z?" | Fase 0.bis dev-protocol |

Installazione e configurazione completa: `wiki/runbooks/code-intelligence.md`

---

## §refactor_agent_skills — Fleet Health (EP-060, v2.41, opt-in)

Capability opt-in per il refactor di skill/agenti/flotte via divulgazione
progressiva. Zero dipendenze esterne (stdlib Python).

| Aspetto | Valore |
|---|---|
| Skill | `.claude/skills/refactor-agent-skills.md` |
| Foglie | `.claude/skills/references/refactor/` (5 file) |
| Script | `tools/refactor/{analizza_target,mappa_riferimenti,verifica_flotta}.py` |
| Agente owner | `fleet-doctor` (`.claude/agents/fleet-doctor.md`) |
| Config gate | `refactor_agent_skills.enabled: false` (default) |
| Lint check | Check 4ap (WARNING-only, `.claude/skills/lint-checks-agent-fleet.md`) |
| Runbook | [`wiki/runbooks/skill-hygiene.md`](wiki/runbooks/skill-hygiene.md) |

Vedi PATTERN.md §36 per il pattern completo.

---

## §session_analysis — Session Agentic Analyser (EP-061, v2.42, opt-in)

Capability opt-in per analisi critica post-hoc dell'attivita agentica di sessioni
Claude Code chiuse. Determinism-first (regole deterministiche, no LLM per detection),
LLM advisory. Solo out-of-band (mai in-sessione, R-SAA-8). Zero dipendenze esterne
(stdlib Python).

| Aspetto | Valore |
|---|---|
| Skill | `.claude/skills/session-analysis-protocol.md` (5 fasi) |
| Comando | `/session-analysis [--last N|<session-id>] [--depth=quick|full] [--json] [--save]` |
| Tool | `tools/session-analysis/{parse-transcript,fleet-metrics,detect-anomalies,generate-report}.py` |
| Schema | `tools/session-analysis/schema-anomaly.json` (Draft 2020-12) |
| Config gate | `session_analysis.enabled: false` (default) |
| Precondizione HARD | EP-062 Fleet Telemetry Hardening (walker subagent-aware) |
| Report output | `raw/YYYY-MM-DD-session-analysis-<id-8char>.{md,json}` (dual) |
| Frontmatter invariante | `ingest_eligible: false`, `wiki_ingest_policy: incidents-only`, `ttl_days: 90` |
| Tassonomia v1 (deterministica) | ERROR, BUDGET, DISPATCH (3 core enabled); LATENCY, FLEET (2 opt-in roadmap) |
| Integrazione fleet-doctor | Advisory (`fleet_recommendations` campo JSON), mai auto-invoke (R-SAA-6) |
| Runbook handoff | [`wiki/runbooks/session-analysis-fleet-doctor-handoff.md`](wiki/runbooks/session-analysis-fleet-doctor-handoff.md) |
| Kill criterion §23.8 | Hard sunset v2.44 se <5 anomalie azionabili con TSK reale (vedi `EP-061.md#sunset_condition`) |
| Invarianti | R-SAA-1..10 (read-only, redazione, no auto-fix, out-of-band, schema-guard, kill criterion) |
| Provenienza | Tavola Rotonda TR-c4e8f1b2 (forced-synthesis Round 3) — `wiki/decisions/tavola-rotonda-c4e8f1b2-...-2026-09-08.md` |

Concept wiki: [`wiki/concepts/session-agentic-analyser.md`](wiki/concepts/session-agentic-analyser.md)

---

## Pipeline tipica con CQRL attivo (v2.12)

```
TSK status:todo ─/dev─▶ status:done, review_status:pending
                              │
                              ▼ (auto via /run, dominio scheduler `review`)
                       /review <TSK-id>
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
       pass: chiusura  conditional: dispatch  reject: gate umano
                       dev-agent (loop max 3) (PATTERN §7 r.16)
```

---

## Memoria cross-conversazione e Storage CQRL

**Memoria cross-conversazione**: il tree `memory/{episodic,semantic,procedural}/` persiste tra
conversazioni. L'orchestrator scrive in `episodic/`; `semantic/` e `procedural/` sono curati
a mano o promossi. Con CQRL attivo (v2.12), il `feedback-router` aggiorna
`memory/semantic/dev-<layer>-recurring-issues.md` con i pattern ricorrenti per dev-agent →
input per i prossimi Develop ("miglioramento a monte").

**Storage CQRL (v2.12)**:

- `code_quality/rules/{canonical,emergent,team-specific}/<rule_id>.md` — KB evolutiva (filesystem-based)
- `code_quality/reports/<TSK-id>-iter-<N>.{json,md}` — report per iterazione (JSON machine-readable + digest umano)
- `code_quality/reports/_digests/<dev-agent>-<YYYY-WW>.md` — digest aggregati settimanali per dev-agent

Side-channel (non un layer del cascade L1→L5), analogo a `memory/`. Scritto solo da
`code-reviewer` (R.Q2 + R.Q6). Le regole `canonical` e `team-specific` sono curate a mano.

---

## Riferimento chiavi factory.config.yaml

> Spostato da CLAUDE.md (US-305). Sta qui e non in `wiki/runbooks/`: e' un indice di
> configurazione, non un runbook, e un runbook su una capability del bucket di ingresso e'
> cerimonia (PATTERN §23.8, `tests/test_fleet_contract.py` asse 4).

[`factory.config.yaml`](factory.config.yaml) al root del repo configura tutte le capability
della factory. Ogni chiave e' documentata qui. Per le capability opt-in, a flag spento la factory
e' identica alla versione precedente (nessun impatto su factory esistenti).

## Central Model Registry (v2.27)

`models.routing.tier_fast` / `tier_default` / `tier_deep` — unico posto dove aggiornare i model ID
per tutti gli agenti; `models.overrides: {}` per eccezioni per-agente.
Tier di default: `tier_fast: claude-haiku-5-5`, `tier_default: claude-sonnet-5-5`,
`tier_deep: claude-opus-5-5` (PATTERN §29.2, cap fan-out + costo ottimizzato).

## Topologia e Stack mode

- **Topologia**: `knowledge-only` | `plan-only` | `full-stack-agents` | `hybrid-be-agents` | `hybrid-fe-agents` | `custom`
- **Stack mode**: `manual` | `guided` | `auto`
- **Routing** TSK → consumer (`agent` | `human`) per layer

## Code paths (v2.12 multi-repo, PATTERN §13)

Lista di entry `{name, path, layers, tags, vcs}` per supportare FE/BE disaccoppiati, microservizi,
micro-frontend, monorepo logico. Legacy `code_path:` (singolare) accettato e auto-promosso.
TSK guadagna campo `target:` opzionale (required solo se ambiguità).

## VCS mode (v2.8, PATTERN §15)

Per ciascuna entry (multi-repo) o top-level (legacy): `monorepo` | `submodule` | `sibling` | `external` | `none`
+ `branch_strategy` + `commit_coupling`. Al massimo **una** entry può essere `monorepo` (R.B6).

## Kanban publish (v2.10, PATTERN §17)

`kanban_publish.provider` (`none` | `github` | `gitlab` | `jira` | `linear` | `custom`)
+ `target` + `auth_env` + `mode: push-only` + `batch_limit` + `mapping` + `labels` + `filter`

## Parallel scheduler (v2.11, PATTERN §18)

`scheduler.enabled` (default `true`) + `max_parallel` (cap fan-out, default `4`)
+ `parallel_gate_threshold` (gate umano sopra N parallel, default `3`)
+ `code_path_conflict` (`strict|warn|off`) + `empty_code_path_policy` (`serial|parallel`)
+ `domains:` (opt-in/out per dominio: ingest/develop/lint/query/plan/design/publish/sync/**review v2.12**)

## Date di lavoro dei TSK (EP-079)

`kanban_dates.required_from` (AAAA-MM-GG, default assente = nessun controllo): data di adozione del Check 4be, conta il giorno del commit che cambia lo stato. Schema in `schemas/factory.config.schema.json`.

## Lint (v2.44, opzionale)

`lint.kanban`: `scope` (`all` | `open`), `required` e `warning` per tipo (`EP`/`US`/`TSK`: elenchi di
campi), `layer_severity` (`error` | `warning`), `layer_segment`, `id_duplicate`, `equivalents`
(campo → alternative accettate), `in_progress_needs_sprint`, `be_test_evidence` (+ `_consumers`, `_since`, Check 4bh), `tsk_target` (+ `tsk_target_gitmodules`, Check 4j). `lint.wiki`: `orphan` (`index` |
`reachability`), `append_only_links` (`error` | `info`), `date_fields`. Blocco assente = regole del
master (`tools/lint/lint_comune.py`, `REGOLE_DEFAULT`); mappe solo in forma a blocco (una mappa
inline `{...}` e' un errore esplicito). `wiki/log.md` ha in `.gitattributes` il merge driver
`factory-log-union` (`tools/wiki/log_union_driver.py`: unione delle voci append-only, nessuna persa):
registrazione locale con `tools/vcs/install_factory_hooks.py` (anche `--only <hook>`), da ripetere in
ogni clone; senza registrazione git usa il merge di default. L'installer calcola la cartella degli hook
con `git rev-parse --git-path hooks`, quindi funziona anche da un worktree. `wiki_lint.log_append_guard.hook` (default `false`): con `true`
`tools/vcs/install_factory_hooks.py` installa il hook `pre-commit` che rifiuta il commit se una riga di
`wiki/log.md` sparisce senza archivio `wiki/log-*.md`; il Check 4bb resta attivo a flag spento. Hook
locale: ogni collaboratore rilancia l'installer.

## Code quality review (v2.12, PATTERN §19)

`code_quality.enabled` (default `false`) + `max_iterations` (default 3, R.Q4)
+ `thresholds` (`confidence_min: 0.6`, `batching_split: 7`, `pass_rate_warn: 0.05`, `false_positive_warn: 0.30`)
+ `passes` (idiomaticity/design/robustness)
+ `router` (`strategy: severity-tiered`, `max_diff_lines: 80`)
+ `ruleset.path` + `reports.path`
+ `trigger_default` (`enabled`, `layer[]`, `consumer[]`, `review_status_field`, `review_status_default`: review di default, Fase 4-quater + dispatch §12)

## Compression layer (v2.14, PATTERN §20)

**Asse output (Fase 1)**: `compression.output.enabled` (default `false`, opt-in R.C6)
+ `provider: caveman` + `policy_profile` (`conservative` default | `aggressive` | `custom`)
+ `invariants` non overridabili (`to_user`/`to_artifact`/`propagate_resolution` sempre off, R.C1)
+ `channels` (solo se `custom`) + `chain_depth_downgrade` (R.C3)
+ `cross_factory: off` (R.C4 in federated) + `drift_fallback` (R.C5, marker `AMBIGUOUS_HANDOFF`/`REQUEST_CLARIFY`)

**Asse context (Fase 2)**: `compression.context.enabled` (default `false`, opt-in R.G6)
+ `provider` (`none` | `graphify-cloud` | `graphify-ollama`)
+ `targets` (lista `{kind: code_path|wiki, name|path, gitignore_patterns}`)
+ `update_strategy` (default `incremental`) + `full_rebuild_cron` (weekly drift mitigation R.G4)
+ `ci_strategy` (`cache-with-fallback` default)
+ `confidence_gating` (R.G2: executor → `EXTRACTED` only / explorer → `+INFERRED` / reviewer → tutto)
+ `full_rebuild_cost_warn` (USD soglia conferma esplicita)
+ `mcp_server` (per-agent default | shared opt-in)

## Hybrid Wiki Search (v2.29, EP-042, PATTERN §31, opt-in)

`wiki_search.enabled` (default `false`) + `backend: auto` (auto|fts5|hybrid; auto = fts5 se mancano
`lancedb`/`sentence-transformers`) + `fts_db: .wiki-search/fts.sqlite` + `embedding_model: paraphrase-multilingual-MiniLM-L12-v2`
+ `mode: hybrid` (hybrid|vector|fts) + `top_k: 5` + `exclude_types: [meta]`;
a flag spento factory identica a v2.28; dipendenze `lancedb`/`sentence-transformers` non importate (R.WS2);
indice in `.wiki-search/index.lance` (gitignored); aggiornamento via `/wiki-search reindex`

## Temporal Estimate Protocol (v2.30, EP-043, opt-in)

`temporal.estimate_protocol.enabled` (default `false`) + `budget_ms` (S/M/L/XL in ms)
+ `thresholds` (warn/escalate_time_ratio, escalate_confidence_min);
skill `.claude/skills/temporal-estimate-protocol.md` 4 fasi;
invocazione post temporal-budget-governor pre-retry-wave

## Sprint Progress Signal (v2.30, EP-043, opt-in)

`analytics.sprint_progress.enabled` (default `false`) + `velocity_rolling_days: 7`;
tool `tools/analytics/sprint-progress.py`; comando `/sprint-progress`; fallback kanban garantito

## Ponytail Decision Ladder (v2.39, EP-057, opt-in)

`ponytail.enabled` (default `false`) + `passes.yagni_ladder` (richiede `code_quality.enabled: true`, HARD DEP)
+ `lint.severity` (warning|info, forzato info su `code_path: "."`) + `audit.exclude_patterns`;
YAGNI gate a 7 livelli (Lint Check 4ao WARNING-only post-develop + Pass 4 advisory in code-review-protocol mai determinante);
comandi `/ponytail-review` + `/ponytail-audit` + riga `ponytail-gain` nel token ledger;
invariante locale R.PY1 (security/a11y/trust-boundary inviolabili, non bypassabile);
a flag spento factory identica a v2.38; vedi `wiki/concepts/decision-ladder.md`

## Documentazione (EP-075, opt-in)

`documentation.enabled` (default `false`) + `redaction.enabled` (default `true`) + `tech_site`
(`output_dir`, `include_sections`, `exclude_sections`) + `functional_docs` (`output_dir`, `services`:
catalogo servizio -> pagine wiki, vuoto = si usano i file di `wiki/user-flows/`) + `weekly_digest`
(`output_dir`, `release_kinds`: lista di `{prefix, label}` per etichettare i rilasci del registro).
Tre comandi: `/doc-tecnica`, `/doc-funzionale`, `/digest-settimanale`. Ogni output passa da
`tools/docs/redact.py` (PAT, token, JWT, chiavi private, `password:`, `Authorization:`): un
segreto blocca la scrittura (exit 2/3), il controllo non si aggira. A `documentation.enabled: false`
gli script stampano un avviso ed escono con codice 0. Gli output generati (`deliverables/doc-tecnica/`,
`deliverables/doc-funzionale/`, `deliverables/digest/`) non si versionano. Nasce dalla derivata
portale-servizi-factory, generalizzata (nessun servizio o cliente cablato).

## Cost alert (EP-074, EP-075, opt-in)

`analytics.cost_alert.enabled` (default `false`) + `agent` (default `false`: con `true` il path
escalate scrive un record in `alerts_dir`) + `rules_file: analytics/alert-rules.yaml` +
`alerts_dir: analytics/alerts` (record locali, non versionati). Nel file delle regole: `rules[]`
(`period` session|daily|weekly|monthly, `threshold_usd`, `action` warn|escalate, `notes`,
`operator` per una regola personale), `plans` (`license_usd_month`, `central_funding_usd_month`,
`included_usd`, `included_period` weekly|monthly, `action`) e `subscriptions[]` (`operator`,
`plan`). Precedenza per periodo: regola personale > quota del piano > regola generale. Le soglie
del master sono esempi; i costi sono a listino API, in USD (`analytics/pricing.yaml`).

## STE-lite (EP-076, opt-in)

`ste_lite.enabled` (default `false`, spenta per decisione TSK-809) + `targets` (glob controllati da
`tools/lint/ste_lite.py --targets` a flag acceso) + `limits` (`procedural_words: 20`,
`descriptive_words: 25`, `paragraph_sentences: 6`) + `glossary` (termine preferito → sinonimi
vietati) + `max_fact_loss: 0.10` (soglia di `tools/lint/fact_loss.py`). `/ste-lite <file>` su
file espliciti gira anche a flag spento.

## Pratiche di ingegneria (EP-077, opt-in)

`engineering_practices.enabled` (default `false`, R.P3) + `kanban_path` (default `management/kanban`)
+ `analytics_path` (default `analytics/pocock-pilota`, registri `controlli.yaml`, `invenzioni.yaml`,
`bilancio-n1.yaml`). Gli agganci in dev-protocol, scrivi-task, tpm, product-manager, lead-architect,
fe-dev e code-reviewer valgono solo a flag acceso; la Passata 6 ha il proprio flag
`code_quality.passes.spec_adherence` (default `false`). Registri vuoti: gli indicatori nascono dall'uso.
Non adottate dalla derivata: setup-matt-pocock-skills, triage, to-spec, implement, implement-spec,
wizard, pr; wayfinder rinviata.

## Mestiere della UI (EP-090, opt-in)

`ui_craft.enabled` (default `false`, R.P3) + `worst_case_data` (skill `kowalski-worst-case-data`, `/worst-case`,
fase opzionale del functional oracle) + `motion_review` (Passata 7 advisory di `code-review-protocol`).
`prototyping.variants` (intero 1..5, default 1 = invariato). Campo TSK `base_commit:` opzionale, nessun flag.
Non adottate: emil-design-eng, apple-design, animate, animate-expo, choreograph, gestures, mobile-native,
write-swift, ask-sonner, pick-ui-library, animation-vocabulary, find/remove-animations, animation-performance.

## Repo align (v2.44, EP-068, opt-in)

`repo_align.enabled` (default `false`) + `triggers.on_explicit: true`
(il comando funziona anche a flag spento) + `on_tsk_closed_count` (0 = disabilitato; contato a fine TSK
da `tools/vcs/contatore_chiusure.py`, chiamato da `dev-handoff`, anche per `ai_policy_check`)
+ `auth_domains: []` (opzionale, per remote privati: lookup per `name` o `path`, token da `token_env`/`token_env_var`)
+ `env_file` (opzionale, file `KEY=VALUE` letto e mai eseguito).
Zero mutazione: `git ls-remote` e' l'unica operazione con effetti remoti (R.14, R.B8)

> Spostato da PATTERN (§15) nel 2026-10-05: per §23.8 una capability non ancora esercitata
> non ha norma nel PATTERN (`tests/test_fleet_contract.py` asse 4).

**Verifica dell'allineamento** (v2.44, EP-068 US-299): `/repo-align` risponde a «il lavoro
locale e' gia' sul remote?» per ciascuna entry, **secondo il suo `mode`** — `monorepo` e
`sibling` confrontano HEAD locale con il tip del remote, `submodule` confronta il
**gitlink-SHA registrato nel parent** (mai HEAD del checkout: un detached HEAD del submodule
non e' segnale di divergenza), `external` restituisce `unverified: opaque_topology` per
definizione, `none` e' escluso dal set. `git ls-remote` e' l'unica operazione con effetti
remoti: mai `fetch`, `pull`, `checkout`, `reset`, `submodule update` (R.14, R.B8). Per
`diverged` distingue **avanti** da **indietro**; la prima meta' e' quella che rende visibile
il proprio silenzio. Opt-in via `repo_align:`, ma il comando funziona anche a flag spento.

## §ai_policy — AI policy check (v2.44, EP-068, opt-in)

`ai_policy_check.enabled` (default `false`) + `scope: []`
(i soli path scansionati; vuoto = «nulla da scansionare», exit 0, **non** un errore)
+ `triggers.on_explicit: true`.

**Due layer**:

| | Layer-1 — preventivo | Layer-2 — detective |
|---|---|---|
| Dove | hook git in `.git/hooks/` | `tools/vcs/ai-policy-scan.py` + `/ai-policy-check` |
| Quando | prima del commit | dopo, sulla finestra `@{u}..HEAD` + diff staged |
| Limite | locale, non committato, non condiviso; un runner di hook di progetto che ridirige `core.hooksPath` lo rende inerte | non impedisce nulla: segnala |


> Spostato da PATTERN §23.9 nel 2026-10-05, stessa ragione (§23.8).

**Enforcement a due layer** (v2.44, EP-068 US-300):

| | Layer-1 — preventivo | Layer-2 — detective |
|---|---|---|
| Meccanismo | hook git `pre-commit` / `commit-msg` in `.git/hooks/` | `tools/vcs/ai-policy-scan.py`, comando `/ai-policy-check` |
| Momento | prima del commit | dopo: finestra `@{u}..HEAD` + diff staged, messaggio **e** righe aggiunte |
| Visibilita' | locale, non committato, **non condiviso** fra i clone | committato in `.claude/` e `tools/`, visibile a tutti |
| Limite | un runner di hook di progetto che ridirige `core.hooksPath` lo rende **inerte** | non impedisce nulla: segnala |
| Config | — | `ai_policy_check:` in `factory.config.yaml`, default `enabled: false` |

I due layer sono complementari, non alternativi: il Layer-1 previene, il Layer-2 **vede**
cio' che il Layer-1 non ha prevenuto. Output partition `{clean, violations, unscanned}`,
advisory per default (exit 0 sempre), `--strict` per l'uso come gate pre-push.

> **Guardia di scope — invariante, non convenzione.** Il repo della factory stessa **non e'
> mai scansionato**, nemmeno se passato esplicitamente a `--repos`; il tentativo produce un
> rifiuto esplicito, mai uno skip silenzioso. Nel repo del framework l'attribution AI e'
> **dovuta**, non vietata (quarta regola qui sopra): uno scan indiscriminato segnalerebbe
> ogni commit, e un check che urla sempre e' un check che viene spento. Si scansionano
> soltanto i path dichiarati in `ai_policy_check.scope[]`.

Per il pattern (policy di attribution): PATTERN §23.9.

## Kanban coordination (v2.43, EP-064, opt-in)

`kanban_coordination.enabled` (default `false`) + `oracle_window_days: 30` + `stale_assignment_days: 7`

## Visual channel (v2.44, EP-067, opt-in)

`visual_channel.enabled` (default `false`) + `host` + `port` + `runtime_timeout_seconds` + `stale_after_seconds`
+ `coordinamento.fonte` (`worktree` | `commit`, default `worktree`) + `coordinamento.config` (default
`analytics/coordinamento/config-<git user.name>.json`)

## Session analysis (v2.42, EP-061, opt-in)

`session_analysis.enabled` (default `false`). Precondizione HARD: EP-062 Fleet Telemetry Hardening.
`session_analysis.advisory_model` (default `""` = `models.routing.tier_fast`): modello della nota LLM
advisory di `--depth=full` (`tools/session-analysis/llm-advisory.py`, via `claude -p`).

## Velocity e report PM (EP-078)

`/velocity`: config facoltativa `analytics/velocity/config.json` (copia di `config.example.json`; senza
file valgono i default), tutte chiavi opzionali: `kanban`, `epiche` (vuoto = tutte, o `{id, gruppo}`),
`includi_archivio`, `punti` (taglia → punti), `giorni` (taglia → giorni), `stati_chiusi_esclusi`,
`finestra_settimane` (3), `soglia_chiusura_in_blocco` (5), `team` (per `--per-persona`), `agenti`,
`obiettivo`.

`/coordinamento --pianifica`: blocco `pianificazione` della config operatore
(`analytics/coordinamento/config-schema.json`; senza, `pianifica.py` esce con codice 2). Obbligatori:
`persone_assegnabili`, `orizzonte_giorni_lavorativi`, `dimensione_predefinita`, `punti_priorita`,
`fasce_urgenza`, `punti_sblocco_per_tsk`. Opzionali: `persone_da_riassegnare`, `referente_bloccanti`,
`dimensioni_giorni` (taglia → giorni; obbligatoria salvo `velocity_config`), `velocity_config` (path di
una config di `/velocity`: fornisce la tabella taglia → giorni e la velocity misurata per persona, come
dato di confronto), `velocity_misurata` (default `true`), `dimensione_minima_giorni`. Per obiettivo:
`ambiente_rilascio` (default `test`); per sezione: `tsk` e `sottoperimetro`.

## Altre capability opt-in (riferimenti PATTERN)

Vedi `PATTERN.md` §13 (topology), §14 (stack modes), §15 (VCS),
§16 (sync adapters multi-sorgente — PDF + Figma + repo esistente v2.12 + **graph v2.14 Fase 2**),
§17 (publisher adapters multi-target), §18 (parallel scheduling v2.11),
§19 (code quality review layer v2.12), §20 (compression layer a due assi v2.14),
**§29 (factory scalability patterns v2.27: thin-orchestrator, capability advertisement, WAVE_ID propagation, Check 4ai)**.
