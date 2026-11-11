# Manifesto caricamento per invocazione

> Foglia di [`dispatch-policy`](../../dispatch-policy.md) (US-319, TSK-728). Il core supera
> 12 KB: il manifesto vive qui e il core ne tiene il solo rimando.

Il PATTERN e' un indice piu' moduli (tabella `## Moduli` di `PATTERN.md`). Questa foglia
dice, per ogni comando e agente della flotta, **quali moduli caricare**: il resto non si
apre. La numerazione § e' unica, quindi un rimando `PATTERN §N` si risolve leggendo la
tabella §Moduli e aprendo un solo file.

| Sigla | File | Sezioni |
|---|---|---|
| **IDX** | `PATTERN.md` | §0-§11: ruoli §2, verbi §3, frontmatter §5, invarianti §7, state §8 |
| **INT** | `PATTERN-integration.md` | §12-§17: adapter, topology & routing, stack modes, VCS, sync, publisher |
| **RUN** | `PATTERN-runtime.md` | §18-§20: scheduler, code quality review, compression |
| **GOV** | `PATTERN-governance.md` | §21-§23: versioning, release governance, complexity budget & sunset |
| **CAP** | `PATTERN-capabilities.md` | §24-§37: capability opt-in |

**Regola base**: IDX si carica **sempre** (le invarianti §7 vincolano ogni unita'). Un
modulo «condizionale» si carica solo se il flag indicato e' acceso: a flag spento la sua
sezione e' no-op e leggerla e' solo costo.

**Metodo** (ripetibile): per ogni unita' si sono raccolte le ancore `§N` attribuite a
`PATTERN` nel file dell'unita' e nelle skill che nomina, poi mappate sul modulo; i rimandi
di sola prosa (es. il formato di log di `wiki-log-entry` che cita §15) non contano come
caricamento. Ricalcolo:
`grep -nE 'PATTERN[^§]*§[0-9]+' .claude/commands/<x>.md .claude/skills/<skill>.md`.

## Comandi

| Comando | Caricare (oltre a IDX) | Condizionale | Evidenza |
|---|---|---|---|
| `/dev` | INT | RUN se `compression.output.enabled` (§20 decision anchor); CAP se `code_intelligence.l3_impact.enabled` (§33) o `design_intelligence` attivo su FE (§24) | `dev-protocol`: §13 multi-repo, §15 branch gate; `dev-handoff`: §20 |
| `/review` | RUN | INT se serve `stack-detector` (§16); Passata 7 (`kowalski-motion-review`, nessun modulo PATTERN) solo con `ui_craft.motion_review` e motion nel diff | `review`, `code-review-protocol`: §19 |
| `/run` | RUN | INT se `vcs.branch_awareness.enabled` (§15 preflight); GOV se dominio release (§22); CAP se dominio refactor (§36) o suggerimenti contestuali (§26) | `orchestrator`, `parallel-scheduling`: §18, §20 |
| `/lint`, `/pattern-view`, `/factory-bootstrap`, `/factory-upgrade` | INT + RUN + GOV + CAP | — | `/lint`: famiglie `lint-checks-*` citano §15-§17, §18, §20, §21, §23, §29, §32, §36, §37. Gli altri tre leggono o copiano il PATTERN intero |
| `/topology`, `/kanban-publish`, `/figma-sync`, `/repo-sync`, `/sync-docs`, `/vcs-status`, `/repo-align`, `/sm-doctor`, `/session-close` | INT | — | §13 (`topology`), §17 (`kanban-publish`), §16 (sync, `session-close` via `session-sync`), §15 (VCS) |
| `/session-start`, `/init-check`, `/repo-handover` | — | INT se toccano submodule o pull (§15) | nessuna ancora PATTERN propria; il perimetro VCS e' §15 |
| `/graphify-sync` | INT + RUN | — | §16 sync, §20.10 asse context |
| `/compression` | RUN | — | §20 |
| `/ponytail-review` | RUN | — | Pass 4 di `code-review-protocol` (§19) |
| `/worst-case` | — | — | nessuna ancora PATTERN: skill `kowalski-worst-case-data` (+ `catalogo.md` in Fase 2); a `ui_craft.worst_case_data` spento fallback esplicito |
| `/ponytail-audit`, `/visual-oracle` | — | RUN se `code_quality.enabled` (§19) | `visual-oracle-protocol`: §19 |
| `/release` | GOV | — | `release-validation-gate`: §22 |
| `/complexity-budget`, `/ai-policy-check` | GOV | — | §23, §23.9 |
| `/plancia` | CAP + GOV | — | §30 canale asimmetrico, §23.8 |
| `/tavola-rotonda`, `/wiki-search`, `/share`, `/sweep-reviews`, `/session-analysis`, `/voice-install`, `/refactor`, `/semantic-drift-scan` | CAP | — | §28, §31, §32, §35, §37, §30, §36, §25 |
| `/code-search` | CAP | INT se l'indice e' per `code_paths` multipli (§13) | §33 |
| `/prototype`, `/prototype-status` | CAP | INT per `backend-resolver` (§15) | §26-§27 |
| `/cypress-gen` | INT | — | VCS (§15) per il commit nel repo di test, §23.9 `ai_policy`; skill `cypress-generation-protocol` |
| `/query`, `/promote`, `/heal`, `/premortem`, `/onboarding`, `/help`, `/a11y`, `/analytics`, `/estimate`, `/functional-oracle`, `/ux-ui-design`, `/ux-ui-review`, `/harvest-tokens`, `/token-ledger`, `/cost-alert`, `/sprint-progress`, `/velocity`, `/kanban-status`, `/release-artifact`, `/migration-verify`, `/coordinamento`, `/doc-tecnica`, `/doc-funzionale`, `/digest-settimanale`, `/ste-lite`, `/log`, `/db`, `/promemoria` | — | `/heal` via `wiki-keeper`: come la riga dell'agente | solo IDX: §2, §3, §5, §7, §10 |

## Agenti

| Agente | Caricare (oltre a IDX) | Condizionale | Evidenza |
|---|---|---|---|
| `be-dev`, `fe-dev`, `db-dev`, `qa-dev`, `docs-dev` | INT | RUN se `compression.output.enabled` (§20) o, per `qa-dev`, `code_quality.enabled` (§19); CAP per `fe-dev` se `design_intelligence` (§24), per tutti se `code_intelligence.l3_impact` (§33) | `dev-protocol` §13/§15, `dev-handoff` §20 |
| `code-reviewer`, `consistency-checker` | RUN | INT per `stack-detector` (§16) | §19, §20.4 |
| `a11y-specialist`, `analytics-reporter`, `estimation-analyst`, `ui-designer`, `ux-ui-reviewer` | — | RUN se il ciclo passa dal CQRL (§19) | §3 (operazioni opzionali), §19 citata per la separazione valutatore/esecutore |
| `cypress-test-analyst`, `cypress-test-reviewer` | INT | — | §15 (repo di test e submodule), §23.9 |
| `cost-alert` | — | — | solo IDX: §3 (operazione opzionale Cost Computation, via `cost_alert.py`) |
| `sync-docs`, `figma-sync`, `repo-sync`, `session-sync`, `wiki-keeper-worker` | INT | RUN per `repo-sync` e worker se fan-out parallelo (§18) | §16 sync multi-sorgente |
| `github-publisher` | INT | — | §17 |
| `graphify-sync` | INT + RUN | — | §16, §20.10 |
| `lead-architect`, `tpm` | INT | RUN per `tpm` se `scheduler.enabled` (§18, campi DAG del TSK) | §11 (IDX), §13-§14 routing e stack mode |
| `orchestrator` | RUN | INT se branch awareness (§15); GOV se dominio release (§22); CAP se dominio refactor (§36) | `dispatch-policy`, `parallel-scheduling` §18, §20 |
| `wiki-keeper` | — | RUN se `compression.output.enabled` (§20); CAP se `purpose.md` o Wiki Keeper 2.0 attivi (§34, §35) | |
| `wiki-lint` | INT + RUN + GOV + CAP | — | come `/lint` |
| `release-manager` | GOV | — | §21-§22 |
| `fleet-doctor`, `tavola-rotonda-moderatore`, `voice-channel-installer` | CAP | — | §36, §28, §30 |
| `prototype-generator` | CAP | INT per `backend-resolver` (§15) | §26-§27 |
| `tutor` | — | CAP se `wiki_search.enabled` (§31) | |
| `product-manager`, `kanban-coordinator`, `wiki-query`, `artifact-release-manager`, `pattern-b-testbed`, `code-cartographer`, `migration-verifier`, `pm-report-coordinator`, `log-operator`, `db-operator` | — | RUN per `product-manager` se `scheduler.enabled` (§18, `depends_on`) | solo IDX |

## Manutenzione

Un comando o agente nuovo entra in questa foglia nello stesso commit che lo crea
(`tools/tests/test_pattern_manifest.py` fallisce altrimenti). Una sezione PATTERN nuova va
nel modulo piu' affine (tabella §Moduli); se cambia il modulo di un'unita', cambia la sua riga.
