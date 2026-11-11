---
name: scrivi-task
description: Template per un task TSK-ZZZ.md atomico, contractuale.
---
# Procedura per scrivere un task

Riferimenti: `citation-rules` (cascade: il task cita US/ADR/design).

Identificativo libero: `python3 tools/kanban/next-id.py tsk` (factory master, namespace unico). Se `kanban_namespaces.enabled: true`, usa `--namespace <PREFIX>` e prenota il range nel registro prima di creare i file — vedi `tools/kanban/README-namespaces.md`.

## Path

`management/kanban/EP-XXX-<slug>/US-YYY-<slug>/TSK-ZZZ.md`

## Frontmatter (minimal, v2.11)

```yaml
---
id: TSK-ZZZ
sprint: NN
layer: be | fe | db | qa | infra | docs  # v2.43: valori = chiavi di routing: in factory.config.yaml; fallback {be,fe,db,qa,infra,docs}
consumer: agent | human
priority: P0 | P1 | P2
estimate: XS | S | M | L
status: todo | in-progress | done
depends_on: []           # v2.11: lista TSK prerequisiti (es. [TSK-007, TSK-012]) — hard block
blocked_by: []           # v2.11: lista Q_NNN hard aperte che bloccano il TSK
code_path: []            # v2.11: lista path/glob L5 toccati (es. ["src/auth/**", "src/api/v1/login.py"])
# Campo EP-064 / US-253 (assegnazione nominativa umana) — opzionale e additivo.
# ADVISORY: il dispatch di `/run` NON lo legge per decidere cosa dispacciare, e non deve
# mai iniziare a farlo. Motivo e limiti dichiarati in `.claude/skills/references/scrivi-task/assignee-advisory.md`.
assignee:                # opzionale — identità umana (es. "soli92"); advisory, mai un filtro di dispatch
# Campi EP-018 (Functional Oracle) — opzionali/additivi; assenza = 0 ERROR di lint (no-op se fe_correctness.functional_oracle.enabled: false)
functional_status: pass | conditional | reject | skip | pending  # EP-018 opt-in; single-writer: skill functional-oracle-protocol (qa-dev)
functional_acceptance_spec: <path>  # EP-018 opt-in; path acceptance-spec YAML; scritto dal TPM/progetto al momento della tasking
# Campi CQRL (Code Quality Review Layer) — opzionali. review_status e' impostato dal dev-agent
# (dev-protocol Fase 4-quater) per i layer/consumer di code_quality.trigger_default; altrove si
# scrive a mano per chiedere la review.
review_status: pending | conditional | passed | rejected  # single-writer: dev-agent (pending), code-reviewer (gli altri)
review_iter: <int>       # iterazione corrente, aggiornata dal code-reviewer
review_report: <path>    # ultimo report (code_quality/reports/<TSK-id>-iter-<N>.md), scritto dal code-reviewer
# Campi EP-029 (Test Failure Taxonomy) — opzionali; solo per TSK layer: qa.
# Campo assente = nessun effetto sul routing (backward compat totale, US-102).
# Valori ammessi: APPLICATION_BUG | SSR_BUG | TEST_BUG | INFRASTRUCTURE | FLAKY
failure_classification:   # opzionale — omettere se non applicabile
# Date di lavoro: le scrive chi cambia lo stato, con la data del lavoro (Check 4be, ERROR da kanban_dates.required_from)
started_at:              # obbligatorio al passaggio a in-progress (YYYY-MM-DD); vuoto in un TSK nuovo
closed_at:               # obbligatorio al passaggio a done (YYYY-MM-DD, >= started_at); vuoto finche' non e' chiuso
# Deriva del codice citato (EP-090 / US-370) — opzionale; assenza = nulla cambia
base_commit:             # SHA corto (7-40 hex) del repo del code_path su cui il TSK e' stato scritto; solo se cita file:riga o estratti
# Pratiche di ingegneria (EP-077, solo con engineering_practices.enabled; assenza = invariato)
test_seams:              # lista di {seam, cattura, non_cattura} per pocock-tdd; li propone il TPM
test_seams_status: proposti | confermati   # confermati solo dal Tech Lead
regression_test:         # TSK di correzione: path della spec, o "nessun seam corretto: <motivo>"
---
```

Note:
- `story` ed `epic` deducibili dal path.
- `sprint` è facoltativo (v2.43); se omesso su TSK in-progress/review → WARNING `in-progress-senza-sprint` dal lint.
- `layer` sostituisce `team` (deprecato v2.7). Valori ammessi = chiavi di `routing:` in `factory.config.yaml`; fallback `{be, fe, db, qa, infra, docs}`.
- `consumer` = default da `factory.config.yaml.routing.<layer>`. Override esplicito ammesso.
- Se la topologia non include un dev-agent per `<layer>` ma `consumer: agent`, il `wiki-lint` segnalerà incoerenza.
- `assignee:` — single-writer: il TPM (vedi sezione dedicata).
- `base_commit:` — scrivilo (`git -C <code_path> rev-parse --short HEAD`) solo se il TSK cita righe o estratti di codice esistente (`file:riga`); altrimenti omettilo. Con `code_path` esterno e' lo SHA di quel repo, non della factory. Il dev-agent lo usa per fermarsi sulla deriva (`dev-protocol` Fase 0, step 5); se riscrivi un passo fermato, aggiorna lo SHA.
- `depends_on`/`blocked_by`/`code_path` — input per il parallel scheduler (PATTERN §18).

Se aggiungi `risk_classification:`, vedi PATTERN §5 per lo schema completo (opt-in v2.16).

## Corpo

```markdown
# TSK-ZZZ — <Titolo conciso>

## Context
<US riferita, perché serve questo task>
[^src: management/kanban/EP-XXX-<slug>/US-YYY-<slug>/US-YYY.md §AC]

## Technical Specs
- **BE:** endpoint OpenAPI specifico → `POST /api/v1/foo`
- **FE:** pagina/componente → `LoginPage` consuma `POST /api/v1/auth/login`
- **DB:** tabelle impattate
- **Auth:** ruoli abilitati

## Implementation Steps
1. <step 1>
2. <step 2>
3. <step 3>

## Definition of Done
- [ ] Test unitario passa
- [ ] Test integrazione passa
- [ ] Documentazione aggiornata
- [ ] Code review approvata

## Dependencies
<!-- v2.11: lista derivata dal frontmatter `depends_on:` + `blocked_by:`.
     Sezione OPZIONALE con rationale umano-leggibile. La verità per lo scheduler è il frontmatter. -->
- TSK-XXX — <rationale opzionale>
```

---

## Layer FE — State Matrix nel DoD (opt-in, US-021)

**Trigger**: TSK con `layer: fe` + `factory.config.yaml.fe_correctness.state_matrix_inject: true`.
A flag spento (default): nessun block iniettato — comportamento invariato.
Sezione `## DoD FE — stati obbligatori`, distinta da `## Acceptance Criteria`; senza il block: **0 ERROR**.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (block template VERBATIM 10 righe, regola di selezione
> TPM, motivazione 3 failure modes FE, cross-link visual oracle) si trova in:
> `.claude/skills/references/scrivi-task/fe-state-matrix.md`
>
> Leggi obbligatoriamente quella foglia prima di iniettare il block.
> Se il file manca → STOP e segnala.

---

## Layer FE — Granularity Rule (opt-in, US-022)

**Regola (forma OR)**: `estimate > max_estimate_hours` OPPURE `stati selezionati > max_states` →
valutare scomposizione. Default: `{max_estimate_hours: 8, max_states: 3}` (configurabili in
`factory.config.yaml.fe_correctness.granularity`); divergenza dal lint 4n (AND): ADR-011.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (regola OR VERBATIM, soglie configurabili, 3 pattern
> di scomposizione, nota divergenza OR(prompt)/AND(lint)) si trova in:
> `.claude/skills/references/scrivi-task/fe-granularity-rule.md`
>
> Leggi obbligatoriamente quella foglia prima di applicare la regola.
> Se il file manca → STOP e segnala.

---

## Layer FE — UX/UI Design Spec (opt-in, EP-008, US-032)

**Quando**: esiste un deliverable Design in `code_quality/reports/<TSK-id>-uxui-design.json`.
**Single-writer: il TPM** (ADR-020 §A/§F). Campo additivo: assenza = 0 ERROR.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (quando suggerirlo, procedura 4 step, schema
> single-shot, backward compat) si trova in:
> `.claude/skills/references/scrivi-task/fe-ux-ui-design-spec.md`
>
> Leggi obbligatoriamente quella foglia prima di valorizzare `ui_design_spec:`.
> Se il file manca → STOP e segnala.

---

## Layer FE — Functional Oracle (opt-in, EP-018, US-071)

**Quando**: esiste (o si intende creare) un'`acceptance-spec` YAML per il componente/app.
**Single-writer per campo**: `functional_acceptance_spec` → TPM; `functional_status` → functional-oracle-protocol.
Campo additivo: assenza = 0 ERROR (anche a flag `fe_correctness.functional_oracle.enabled: true`).

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (quando suggerirlo, single-writer per campo,
> procedura 4 step, opzionalità + no-op a flag spento, Lint Check 4z.1) si trova in:
> `.claude/skills/references/scrivi-task/fe-functional-oracle.md`
>
> Leggi obbligatoriamente quella foglia prima di valorizzare `functional_acceptance_spec:`.
> Se il file manca → STOP e segnala.

---

## Campo `assignee:` — advisory, mai vincolante sul dispatch (EP-064 / US-253)

Il campo è un'annotazione di pianificazione per il **lavoro umano pianificato**. Non è mai un filtro
di dispatch (BR1 US-253): aggiungere `assignee:` non lo rende visibile a `/run`; renderlo
vincolante annullerebbe R.S2 (§18.4). Campo assente = 0 ERROR.

> **[TRIGGER VINCOLANTE]** La normativa completa (perché non deve MAI diventare filtro di dispatch,
> i 2 fallimenti silenziosi FM-NEW-1/FM-NEW-4, la prelazione, copertura reale 0% traffico agentico,
> stato decisione a monte, emendamento PATTERN.md §5 pendente) si trova in:
> `.claude/skills/references/scrivi-task/assignee-advisory.md`
>
> Leggi obbligatoriamente quella foglia prima di introdurre `assignee:` in una factory.
> Se il file manca → STOP e segnala.

---

## Regole

- **Atomicità:** un task = una unità testabile. Mai "Crea modulo Login" → spezza
  in "Crea endpoint POST /auth/login" + "Crea LoginPage React".
- **Con `engineering_practices.enabled: true`** (da `to-tickets` di Matt Pocock): *fette
  verticali* (un comportamento verificabile da solo, componente, logica e test insieme; il
  prefactoring per primo); `depends_on:` solo per i blocchi veri; refactor ampi in
  *expand–contract* (forma nuova accanto alla vecchia, migrazioni a lotti, ultimo TSK toglie la vecchia).
- Cita endpoint OpenAPI o pagina FE specifica, non astratti.
- Estimate: XS=<2h, S=mezza giornata, M=1 giorno, L=2+ giorni.
- Citazioni: vedi `citation-rules` (cascade L4 → US/ADR).
