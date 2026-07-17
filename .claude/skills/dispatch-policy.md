# Skill: Dispatch Policy

> Adapter Cursor della skill `dispatch-policy` definita in PATTERN.md.

**Versione:** v2.27 | **Autore:** orchestrator (single-writer di questa skill)
**Scope:** read-only — descrive routing condizionale, non esegue azioni dirette

Questo documento è il **contratto unico di dispatch condizionale** dell'orchestrator.
Ogni nuova EP che aggiunge logica di routing deve modificare **solo questo file**,
non [orchestrator](mdc:.cursor/rules/orchestrator.mdc). L'orchestrator si limita a invocare le sezioni pertinenti.

---

## 1. VCS Branch Preflight (EP-034, v2.25, opt-in)

Gate **informativo read-only** che rende visibile lo stato branch/HEAD dei target VCS
**prima** del wave dispatch — per progetti con repository sotto git submodule.

### Trigger

Attivo **se e solo se**: `factory.config.yaml.vcs.branch_awareness.enabled: true`
AND `branch_awareness.preflight: true`.
A flag spento (default) → **no-op silenzioso** (R.B10).

### Azione

Invocare la skill [vcs-preflight-protocol](mdc:.cursor/skills/vcs-preflight-protocol/SKILL.md) (read-only, R.B7) e stampare la tabella
dello stato (`target | mode | branch corrente | branch atteso | HEAD | drift | verdict`)
**in testa all'output di `/run`**, prima del wave summary.
Per ogni riga con verdict `ACTION` mostrare il comando esatto di remediation.

### Vincoli

- Non blocca il dispatch (è informativa).
- Read-only totale: nessun `checkout`/`commit`/`fetch` automatico (R.B7).
- Il blocco effettivo (opt-in) vive nel gate Fase 0 di `dev-protocol`.

---

## 2. Oracle Pre-Check FE (EP-006, v2.17, opt-in)

Gate **deterministico pre-dispatch** per i TSK frontend.

### Trigger

Attivo **se e solo se**:
1. `factory.config.yaml.fe_correctness.dispatch_gate: true`, AND
2. il TSK candidato ha `layer: fe` nel frontmatter.

A gate off (default) → no-op, comportamento identico a v2.16.

### Azione

Per ogni TSK FE candidato invocare la skill [oracle-precheck](mdc:.cursor/skills/oracle-precheck/SKILL.md) (grep deterministico,
**no LLM runtime**). Output atteso:

```json
{ "passed": true|false, "satisfied_by": "cond:X" | null, "message": "<stringa>" }
```

### Gestione esiti

- **`passed: true`** → dispatch normale. Il gate è trasparente.
- **`passed: false`** → fail-loud bloccante: NON dispatchare il TSK; mostrare `message`
  con le 4 strade per aggiungere un oracolo + link al runbook
  `wiki/runbooks/visual-oracle-installation.md`. In un wave, il TSK FE bloccato è
  escluso ma gli altri candidati procedono.

### Logging

Appendere una riga in `memory/episodic/oracle-gate.md`:
```
YYYY-MM-DD | TSK-id | passed|blocked (cond:X) | message
```

---

## 3. A11y Dispatch Fallback (EP-007, v2.18, opt-in)

Chain deterministica **`a11y-specialist > qa-dev > fe-dev`** per dispatch scan a11y.

### Trigger

Attivo **se e solo se** `factory.config.yaml.a11y.enabled: true`.
A flag spento (default) → no-op (R.P3).

### Precedenza ordinata

1. `a11y.agent: true` AND [a11y-specialist](mdc:.cursor/rules/a11y-specialist.mdc) scaffoldato →
   invocare [a11y-specialist](mdc:.cursor/rules/a11y-specialist.mdc).
2. Altrimenti, `qa-dev` in topologia AND TSK ha `layer: fe` + `status: done` →
   invocare `qa-dev` (skill [accessibility-testing-protocol](mdc:.cursor/skills/accessibility-testing-protocol/SKILL.md)).
3. Altrimenti, `fe-dev` scaffoldato →
   invocare `fe-dev` (Modalità 1, tool `a11y-scan.sh`).
4. Altrimenti → fail-loud: STOP, loggare warning in `wiki/log.md`
   (`«Nessun agente disponibile per a11y scan; topologia non compatibile»`).

### Vincolo single-writer

Qualunque agente della chain esegua lo scan è single-writer di `a11y_status:` sul TSK
(ADR-014 §Rationale 6). I tre trigger non sono mai concorrenti sullo stesso TSK.

---

## 4. UX/UI Dispatch Policy (EP-008, v2.18, opt-in)

### Trigger

Attivo **se e solo se** `factory.config.yaml.ux_ui.enabled: true`.
A flag spento (default) → no-op (R.P3).

### Separazione strutturale enforced

L'orchestrator **non assegna MAI** reviewer e designer allo stesso agente nella stessa
catena (ADR-020 §H). I due ruoli sono fisicamente distinti.

### Policy review (`ux-ui-review`)

1. `ux_ui.agents.reviewer: true` AND [ux-ui-reviewer](mdc:.cursor/rules/ux-ui-reviewer.mdc) scaffoldato →
   invocare [ux-ui-reviewer](mdc:.cursor/rules/ux-ui-reviewer.mdc).
2. Altrimenti → skill `ux-ui-review-protocol` via `fe-dev`/`qa-dev` attivi.

### Policy design (`ux-ui-design`, off-DAG)

1. `ux_ui.agents.designer: true` AND [ui-designer](mdc:.cursor/rules/ui-designer.mdc) scaffoldato →
   invocare [ui-designer](mdc:.cursor/rules/ui-designer.mdc).
2. Altrimenti → skill `ux-ui-design-protocol` via `fe-dev`/`qa-dev` attivi.

### Vincoli

- **Nessun auto-chain design → review**: dopo `/ux-ui-design` STOP, suggerire
  `/ux-ui-review` — gate umano obbligatorio (ADR-020 §Decisione).
- **Ordering pipeline FE**: `develop → visual-oracle → ux-ui-review → code-review`.
- `ux_ui_status:` scritto solo dall'agente che esegue la review (single-writer).
- `ui_design_spec:` scritto solo dal TPM nel frontmatter TSK (ADR-020 §A, §F).

### Logging

Appendere entry in `wiki/log.md` + riga in `memory/episodic/ux-ui-runs.md`:
```
YYYY-MM-DD-HH-MM | review|design | TSK-id|adhoc | verdict|deliverable | rubric_violations_count
```

---

## 5. Functional Oracle Dispatch Policy (EP-018, v2.20, opt-in)

### Trigger

Attivo **se e solo se**
`factory.config.yaml.fe_correctness.functional_oracle.enabled: true`.
A flag spento (default) → no-op (R.P3), cascade procede direttamente verso `review`.

### Posizione nel cascade FE

```
develop → visual-oracle → [a11y/ux-ui] → functional-oracle → review
```

Con flag parziali:
- Solo `functional_oracle.enabled: true`, visual-oracle off →
  `develop → functional-oracle → review`.
- Visual-oracle + functional-oracle →
  `develop → visual-oracle → functional-oracle → review`.

### Precondizione sequenziale

Se `fe_correctness.enabled: true` (visual-oracle attivo) e `visual_status: pending` →
**attendere** completamento visual oracle prima di schedulare functional oracle.
Se `visual_status: reject` → functional oracle **SKIPPED** (gate umano sul visual oracle).

### Esecutore

Chain deterministica **`qa-dev > fe-dev`** (precedenza per specializzazione, ADR-067 §A).

### Logging

Appendere entry in `wiki/log.md` + riga in `memory/episodic/functional-oracle-runs.md`:
```
YYYY-MM-DD-HH-MM | TSK-id | verdict | iterations | spec_path
```

---

## 6. Temporal Context Injection (EP-011, v2.18+, opt-in)

### Trigger

Attivo **se e solo se**
`factory.config.yaml.temporal.context_injection.enabled: true`.
A flag spento (default) → exit 0 silenzioso, system prompt invariato (R.P3).

### Azioni sequenziali

1. **Al boot di `/run`**: generare `session_id` (UUID v4) immutabile per la sessione.
2. **Al kickoff di ogni TSK**: impostare `task_started_at` via `tools/temporal/utc-now.sh`.
3. **A ogni invocazione di sub-agent**: invocare
   `tools/temporal/build-temporal-context.sh --task-started-at <ts> --session-id <uuid>`
   e iniettare il blocco come **prima sezione** del system prompt del sub-agent:
   ```
   # Temporal Context (UTC ISO-8601)
   current_datetime: <ricalcolato>
   task_started_at: <immutabile per il TSK>
   session_id: <immutabile per la sessione>
   ```

**Single-writer**: l'orchestrator costruisce e propaga il blocco; i sub-agent non lo
generano autonomamente.

---

## 7. Fase 6 — Capability Relevance Check (EP-033, v2.24)

Sezione informativa, puramente additiva. Non modifica stati, non lancia agenti.

### Trigger e no-op

Si attiva **al termine del wave dispatch** di `/run`. Se `sprint.md` non contiene
TSK con `status: todo` → no-op silenzioso.

### Dati letti

- `sprint.md` — layer e status TSK in coda
- `factory.config.yaml` — flag capability opt-in
- `wiki/log.md` — staleness (>30 giorni) + premortem per-epic

### Regole di suggerimento

| Condizione rilevata | Suggerimento emesso |
|---|---|
| TSK `layer=fe` + `fe_correctness.visual_oracle.enabled: false` | Considera `/visual-oracle` |
| TSK `layer=fe` + `a11y.enabled: false` | Considera `/a11y` |
| ≥3 TSK `done` nella settimana + `analytics.measurement.enabled: true` | Considera `/analytics` |
| ≥1 epic `status: open` + nessun premortem in `wiki/log.md` | Considera `/premortem <epic-id>` |
| `wiki/log.md` ultima entry > 30 giorni | Considera `/semantic-drift-scan` o `/lint` |
| TSK `layer=fe\|be` + `code_quality.enabled: false` | Considera `/review` |

### Gate per-suggerimento (verifica installazione)

Prima di emettere **ogni singolo suggerimento**, verificare che il comando `/<comando>`
sia installato nell'adapter. Se assente → suggerimento **soppresso
silenziosamente**. Garantisce zero suggerimenti di capability non installate.

### Formato output

Solo se ≥1 suggerimento non soppresso:
```
## Suggerimenti contestuali

Basato sul contesto dello sprint corrente:
- Considera `/a11y`: hai TSK FE in coda e `a11y.enabled` è spento.
- Considera `/analytics`: 4 TSK completati questa settimana.
```
Se 0 suggerimenti → sezione assente (mai placeholder vuoto).

### Tono

Formule non imperative: «Considera», «Potresti valutare». Mai forme imperative.

---

## 8. Capability Advertisement (v2.27, factory-optimization)

Pattern di auto-dichiarazione per gli agenti. Permette al dispatcher e alla
[lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md) skill di validare routing senza hardcoding dei nomi agente.

### Schema

Ogni agente `.cursor/rules/*.mdc` può includere nel frontmatter YAML un blocco:

```yaml
capabilities:
  - <capability-slug>   # commento descrittivo (opzionale)
```

Il blocco è **opzionale e additivo**: agenti senza `capabilities:` continuano a
funzionare normalmente (backward compat totale). La lista non configura permessi —
è una dichiarazione documentativa letta da tool e check di lint.

### Capability slug consolidati (v2.27)

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
| `gap-reporting` | `lead-architect`, `tpm`, `be-dev`, `fe-dev`, `db-dev`, `qa-dev` | append a `wiki/gaps.md` |

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

### Come usarlo in un nuovo §

Se una nuova EP aggiunge un capability slot (es. §9), dichiararlo in:
1. Il frontmatter dell'agente che la implementa (`capabilities: - <slug>`).
2. La tabella sopra (aggiungere una riga).
3. Il § corrispondente in questo file (con trigger, azione, esiti).

### Come lo usa Check 4ai

[lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md) Check 4ai.2 valida che le skill referenziate nel body di ogni agente
esistano in `.cursor/skills/`. Il blocco `capabilities:` non è letto da 4ai (è
documentativo), ma serve come input a futuri tool di routing dinamico che possano
derivare "chi può fare cosa" da YAML, senza leggere il body testuale degli agenti.

---

## Cross-link

- [orchestrator](mdc:.cursor/rules/orchestrator.mdc) — dispatcher di questa skill
- [vcs-preflight-protocol](mdc:.cursor/skills/vcs-preflight-protocol/SKILL.md) — §1
- [oracle-precheck](mdc:.cursor/skills/oracle-precheck/SKILL.md) — §2
- [accessibility-testing-protocol](mdc:.cursor/skills/accessibility-testing-protocol/SKILL.md) — §3
- `ux-ui-review-protocol`, `ux-ui-design-protocol` — §4
- [functional-oracle-protocol](mdc:.cursor/skills/functional-oracle-protocol/SKILL.md) — §5
- [parallel-scheduling](mdc:.cursor/skills/parallel-scheduling/SKILL.md) — algoritmo DAG sottostante al dispatch
- [lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md) Check 4ai — agent infrastructure integrity (tool + skill + command validation)
