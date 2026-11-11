---
skill: dispatch-policy
leaf_of: dispatch-policy.md
section: "§8"
description: "Tabelle complete dei capability slug dichiarati nel frontmatter degli agenti"
---

# dispatch-policy §8 — Capability slug consolidati

Fonte autoritativa: il campo `capabilities:` di ogni `.claude/agents/*.md`. Aggiornare in sincronia
con ogni nuovo agente o epica.

Tabella completa — fonte autoritativa: `capabilities:` frontmatter di ogni agente.

**Orchestration layer**

| Slug | Agente | Significato operativo |
|---|---|---|
| `scheduling` | `orchestrator` | dispatch parallelo wave (v2.11) |
| `promote` | `orchestrator` | transizioni status in `wiki/` |
| `state-scan` | `orchestrator` | dashboard `/run` + episodic memory |
| `log-entry` | `orchestrator` | append a `wiki/log.md` (single-committer) |

**Knowledge layer**

| Slug | Agente | Significato operativo |
|---|---|---|
| `ingest` | `wiki-keeper` | raw/ → wiki/ transformation (karpathy) |
| `gap-management` | `wiki-keeper` | write + close in `wiki/gaps.md` |
| `wiki-authorship` | `wiki-keeper` | unico autore di `wiki/**` |
| `candidate-page-json` | `wiki-keeper-worker` | output machine-readable per ingest parallelo |
| `knowledge-query` | `wiki-query` | risponde a domande NL da wiki/ |
| `synthesis-promotion` | `wiki-query` | query → wiki/syntheses/ se salvata |
| `health-check` | `wiki-lint` | check 1-4ai su wiki/ e management/kanban/ |
| `lint-report` | `wiki-lint` | wiki/lint/YYYY-MM-DD-lint-report.md |

**Planning layer**

| Slug | Agente | Significato operativo |
|---|---|---|
| `epic-creation` | `product-manager` | EP-*.md da wiki/ |
| `story-decomposition` | `product-manager` | US-*.md con blocked_by / pending_clarification |
| `kanban-management` | `product-manager` | management/kanban/ struttura |
| `architecture-design` | `lead-architect` | BE/FE/API/DB design + ADR (Fase 1 L4) |
| `tech-scout` | `lead-architect` | technology decisions da raw/tech_stack.md |
| `task-decomposition` | `tpm` | TSK-*.md production (Fase 2 L4) |
| `sprint-planning` | `tpm` | sprint.md + DAG scheduling |
| `gap-reporting` | `lead-architect`, `tpm`, `be-dev`, `fe-dev`, `db-dev`, `qa-dev`, `cypress-test-analyst`, `cypress-test-reviewer` | append a `wiki/gaps.md` |

**Develop layer**

| Slug | Agente | Significato operativo |
|---|---|---|
| `code-development` | `be-dev`, `fe-dev`, `db-dev`, `qa-dev`, `docs-dev` | implementa TSK in code_path |
| `be-specialist` | `be-dev` | backend logic, API, services |
| `fe-specialist` | `fe-dev` | frontend, components, UI |
| `db-specialist` | `db-dev` | migration, schema, query |
| `qa-specialist` | `qa-dev` | test authoring (unit/integration/e2e) |
| `docs-specialist` | `docs-dev` | documentazione, skill, command, agent, config |
| `meta-framework-edit` | `docs-dev` | modalità riflessiva (code_path='.') |

**Quality layer**

| Slug | Agente | Significato operativo |
|---|---|---|
| `code-review` | `code-reviewer` | 3-pass CQRL (idiomaticity/design/robustness) |
| `cqrl-evaluation` | `code-reviewer` | verdict pass/conditional/reject + task_package |
| `yagni-ladder` | `code-reviewer` | Pass 4 advisory (EP-057, opt-in) — **non partecipa al calcolo del verdict**; findings advisory nel report/task_package. R.PY1: mai sopprime security/a11y/trust-boundary |
| `feedback-routing` | `code-reviewer` | handoff feedback-router → dev-agent |
| `a11y-scan` | `a11y-specialist` | WCAG 2.2 AA scan + result interpretation |
| `ux-ui-review` | `ux-ui-reviewer` | rubrica Nielsen 10 + UI 6 + flusso 5 |
| `rubric-evaluation` | `ux-ui-reviewer` | finding con rubric_ref (ADR-063 §B) |
| `ui-design` | `ui-designer` | wireframe, spec, flussi, copy con rationale |
| `consistency-check` | `consistency-checker` | output vs decision_anchor (EP-015) |

**Sync layer**

| Slug | Agente | Significato operativo |
|---|---|---|
| `raw-sync` | `sync-docs`, `figma-sync`, `repo-sync`, `graphify-sync` | scrive in raw/ (scope esclusivo) |
| `pdf-extraction` | `sync-docs` | PDF → raw/*.txt + raw/images/ |
| `figma-extraction` | `figma-sync` | Figma → raw/*.kb.json via Figma MCP |
| `repo-extraction` | `repo-sync` | repo locale → raw/*.md |
| `graph-extraction` | `graphify-sync` | code_path → knowledge graph via Graphify CLI |

**Analytics layer**

| Slug | Agente | Significato operativo |
|---|---|---|
| `cost-measurement` | `analytics-reporter` | retrospettiva costi/tempi reali (EP-009) |
| `cost-alert-escalation` | `cost-alert` | registra gli alert escalate in `analytics/alerts/` (skill `cost-alert-protocol`) |
| `analytics-reporting` | `analytics-reporter` | report schema ADR-024 |
| `project-estimation` | `estimation-analyst` | stima enterprise difendibile (EP-010) |
| `pert-analysis` | `estimation-analyst` | PERT three-point |
| `monte-carlo` | `estimation-analyst` | Monte Carlo throughput |

**Opt-in specialty layer**

| Slug | Agente | Significato operativo |
|---|---|---|
| `kanban-publish` | `github-publisher` | EP/US/TSK → GitHub Issues/Milestones |
| `prototype-generation` | `prototype-generator` | figma→penpot→react→html (EP-035) |
| `tavola-rotonda-moderation` | `tavola-rotonda-moderatore` | 5 fasi collaborazione multi-agente (EP-039) |
| `wiki_search` | `wiki-query` (enhanced) | Hybrid search (vector+FTS) su wiki/ via LanceDB embedded; `wiki_search.enabled` → HybridSearcher disponibile; `/wiki-search <query>` (EP-042, v2.29) |
| `tutoring` | `tutor` | EP-045 opt-in — risposta epistemica L1/L2/L3 + scaffolding adattivo + Student Model SM-2 (`capability_formativa.enabled`); invocato direttamente dall'utente in sessione formativa |
| `voice-channel-setup` | `voice-channel-installer` | EP-041 opt-in — installazione e configurazione Voice Channel end-to-end (`voice_channel`); invocato da `/voice-install` |

**Data access layer (opt-in, EP-086/EP-087)**

| Slug | Agente | Significato operativo |
|---|---|---|
| `log-read` | `log-operator` | search, count, check, fields, namespaces in sola lettura su OpenSearch (`log_access`) |
| `log-noise-profile` | `log-operator` | noise: candidati di rumore; noise-add/handled-add solo anteprima, `--confirm` alla sessione principale |
| `log-masking` | `log-operator` | mascheramento di segreti e dati personali, per esecuzione (HMAC con chiave nuova a ogni run) |
| `db-read` | `db-operator` | lettura validata, transazione READ ONLY, gate di costo con EXPLAIN (`db_access`) |
| `db-navigation` | `db-operator` | locate, tables, describe, feature-map (servizio -> tabella) |
| `db-catalog-status` | `db-operator` | stato del catalogo DDL: avviso di obsolescenza, mai scan |
| `db-write-gate` | `db-operator` | solo dry-run e gate JSON; scrittura spenta per default |

**Test layer (opt-in, EP-088)**

| Slug | Agente | Significato operativo |
|---|---|---|
| `cypress-test-analysis` | `cypress-test-analyst` | Fase 0/0-bis/1 di `cypress-generation-protocol`: casi, selettori, piano in `code_quality/cypress/` |
| `cypress-test-review` | `cypress-test-reviewer` | Fase 3: review statica per spec, correzioni sicure, report per spec |

### Come usarlo in un nuovo §

Se una nuova EP aggiunge un capability slot (es. §9), dichiararlo in:
1. Il frontmatter dell'agente che la implementa (`capabilities: - <slug>`).
2. La tabella sopra (aggiungere una riga).
3. Il § corrispondente in questo file (con trigger, azione, esiti).

### Come lo usa Check 4ai

`lint-checks` Check 4ai.2 valida che le skill referenziate nel body di ogni agente
esistano in `.claude/skills/`. Il blocco `capabilities:` non è letto da 4ai (è
documentativo), ma serve come input a futuri tool di routing dinamico che possano
derivare "chi può fare cosa" da YAML, senza leggere il body testuale degli agenti.
