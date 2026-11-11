---
name: visual-oracle-protocol
description: Loop di verifica visiva per TSK FE — 5 fasi (Bootstrap → Render → Screenshot → Critica → Diff+Loop). Istanza del pattern evaluator-optimizer. Opt-in via fe_correctness.enabled.
---
# Protocollo Visual Oracle — loop di verifica visiva per TSK FE

Loop chiuso di verifica del rendering per TSK FE: renderizza il componente in un browser
headless, cattura screenshot su una matrice viewport × tema, lascia che il critic LLM
multimodale confronti il rendering con la specifica e produca difetti azionabili, poi
itera bounded fino a convergenza. È un'**operazione opzionale** (sub-step di Develop FE,
PATTERN §3 «Develop» — variante «Visual Verification») attivata solo da
`factory.config.yaml.fe_correctness.enabled: true`. A flag spento la skill è no-op
(backward compat totale, R.P3 opt-in totale).

Riferimenti: PATTERN §3 (operazioni canoniche — Visual Verification come variante di
Develop FE). Sintesi: [`wiki/syntheses/fe-agent-correctness-strategy.md §Leva 1`](../../wiki/syntheses/fe-agent-correctness-strategy.md).
ADR: [`ADR-008`](../../design_&_architecture/decisions/ADR-008.md) (Playwright via Bash,
no MCP, runner in `.factory-runners/`, fail-loud), [`ADR-009`](../../design_&_architecture/decisions/ADR-009.md)
(critic = stesso fe-dev in review multimodale), [`ADR-012`](../../design_&_architecture/decisions/ADR-012.md)
(schema dati §A/§H), [`ADR-013`](../../design_&_architecture/decisions/ADR-013.md) (ordering
develop → visual-oracle → review).

Sub-skill / cross-link: questa skill è invocata inline da `dev-protocol` Fase 4-bis
(US-018) e dal comando `/visual-oracle` (US-019). L'ordering è formalizzato in ADR-013:
visual oracle gira **dopo develop, prima di review**.

[^src: design_&_architecture/decisions/ADR-013.md §Punto 1]

## Prerequisiti

- `factory.config.yaml.fe_correctness.enabled: true` (master gate — STOP no-op altrimenti, R.P3).
- TSK target valido: `layer: fe`.
- Playwright disponibile nel project host (vedi Fase 1 Bootstrap, fail-loud altrimenti).
- `code_path` del TSK risolvibile (frontmatter `code_path:` o `target:` → entry in `code_paths`).

[^src: design_&_architecture/decisions/ADR-008.md §Decisione]

## Costanti

```
MAX_ITERATIONS  = fe_correctness.max_iterations   # bound del loop conditional (default 3, analogo R.Q4 di CQRL)
REPORTS_DIR     = "code_quality/reports"          # side-channel riusato (ADR-012 §B, slug `visual`)
RUNNER_DIR      = ".factory-runners"              # script Bash generati, gitignored (ADR-008 §Rationale 2)
```

---

## Fase 1 — Bootstrap

**Input atteso**: `TSK-id` (target del visual oracle), `factory.config.yaml`.

**Azione**:

1. Read `factory.config.yaml.fe_correctness`. Se `enabled: false` → ABORT pulito,
   log a chat «Visual oracle disabilitato; abilitare con `fe_correctness.enabled: true`».
2. Read TSK target: frontmatter (`id`, `layer`, `code_path`/`target`, `visual_status`,
   `interaction_test_spec`, `visual_reference`) + body markdown.
3. Verifica `TSK.layer == fe`. Se non FE → STOP no-op (trigger fallito: il visual oracle
   è solo per layer FE; ADR-013 Punto 1).
4. Verifica prerequisito **Playwright** via Bash: `npx playwright --version`. Se exit
   code `!= 0` → **STOP fail-loud** con messaggio azionabile **verbatim**:

   > Visual oracle richiede Playwright. Eseguire: `npm i -D @playwright/test && npx playwright install --with-deps chromium`. Vedi runbook `wiki/runbooks/visual-oracle-installation.md` se disponibile.

   Nessun degrado silenzioso a «solo critic senza screenshot» (ADR-008 §Rationale 5).
5. Risolve `code_path` dal frontmatter TSK (legacy `code_path:` singolo, oppure `target:`
   → entry in `code_paths`).
6. Calcola `current_iter`: se `visual_status` è assente/`pending` → `N = 1`; se è
   `conditional` (loop in corso) → `N = <ultimo iter> + 1`.
7. Crea la cartella side-channel per gli artefatti PNG:
   `code_quality/reports/<TSK-id>-visual-iter-<N>/` (ADR-012 §B).

**Output prodotto**: cartella `code_quality/reports/<TSK-id>-visual-iter-<N>/` creata;
`code_path` risolto; `current_iter` calcolato.

**Criterio di completamento**: `npx playwright --version` exit code `0` **AND** cartella
artefatti creata.

[^src: design_&_architecture/decisions/ADR-008.md §Conseguenze]
[^src: management/kanban/EP-005-fe-visual-oracle/US-017-skill-visual-oracle-protocol/TSK-020.md]

---

## Fase 2 — Render Headless

**Input atteso**: `code_path` risolto (Fase 1) + body del TSK (per dedurre l'entry-point
del componente / pagina da renderizzare).

**Azione**:

1. Genera uno **script runner Bash** (template-izzato dalla skill) e scrivilo in
   `.factory-runners/` (cartella **gitignored** — non inquina il code_path, ADR-008
   §Rationale 2). Lo script invoca Playwright via Bash, **NON un MCP tool** (ADR-008
   §Decisione: «niente MCP custom»).
2. Lo script avvia il dev-server del progetto (o serve il bundle esistente) e usa
   Playwright per navigare alla pagina/componente target.
3. **Fail-loud** se il browser headless non è disponibile / non avviabile (ADR-008
   §Rationale 5): STOP con messaggio che cita il comando di install della Fase 1. Nessun
   fallback silenzioso.

**Output prodotto**: script runner Bash in `.factory-runners/<TSK-id>-visual-iter-<N>.sh`;
sessione Playwright pronta a catturare screenshot.

**Criterio di completamento**: dev-server raggiungibile **OR** bundle esistente servibile,
e la pagina target renderizza senza errori di navigazione.

[^src: design_&_architecture/decisions/ADR-008.md §Rationale punto 2]
[^src: design_&_architecture/decisions/ADR-008.md §Rationale punto 5]


## Fase 3 — Screenshot Multi-Viewport/Tema

Prima di eseguire la Fase 3, leggi `.claude/skills/references/visual-oracle-protocol/fase-3-screenshot.md` (invocazione completa e naming).

**Input**: `viewports` + `themes` da `factory.config.yaml.fe_correctness`.

La cattura è **delegata** alla skill condivisa [`screenshot-capture-protocol`](./screenshot-capture-protocol.md)
(ADR-017; contratto pubblico invariato: stessi PNG, stessa cartella, stesso naming). La risoluzione
della matrice resta qui:

1. Matrice cartesiana `viewports × themes`. Default (ADR-012 §E): `mobile` 375 e `desktop` 1280 ×
   `light`, `dark` → 4 combinazioni. Override da `fe_correctness.viewports` / `themes` passati
   direttamente alla skill condivisa (N × M).
2. **INVOCA `screenshot-capture-protocol`** con `target` (da Fase 2), `viewports`, `themes`,
   `output_dir = code_quality/reports/<TSK-id>-visual-iter-<N>/`, `naming_pattern = "{viewport}-{theme}.png"`;
   output: lista `{ viewport, theme, path, bytes }` per la Fase 4. Fail-loud se Playwright manca.

**Output**: |viewports| × |themes| PNG `<viewport>-<theme>.png` nella cartella side-channel.
**Completamento**: tutti i PNG esistono e rispettano la convention.

---

## Fase 3-bis — Structured Checks (opt-in)

Prima di eseguire la Fase 3-bis (se `fe_correctness.checks` non è vuota), leggi
`.claude/skills/references/visual-oracle-protocol/fase-3-bis-structured-checks.md` (azione, output JSON e fail-loud di ogni check).

Posizione: dopo Fase 3, prima di Fase 4 (Leva 2, oracoli binari).

- **Gate**: `fe_correctness.checks: []` (default) → fase skip, comportamento identico a US-017 base;
  i tre check riportano `status: skip`. Id canonici: `visual-regression`, `axe-a11y`, `interaction-test`.
- **Fail-loud** se un check configurato manca del tool (messaggio verbatim nella foglia):
  «Check `<id>` richiede `<tool>`; vedi runbook».
- **Verdict aggregato**: qualsiasi check binario `fail` → `verdict: reject` automatico (nessun critic
  LLM), si salta alla Fase 5 con `next_action: escalate-human`; tutti `pass`/`skip` → Fase 4.
- **Output**: popola `checks.visual_regression`, `checks.axe_a11y`, `checks.interaction_test` del
  JSON report (non configurato → `skip`).

---

## Fase 4 — Critica Visiva

Prima di eseguire la Fase 4, leggi `.claude/skills/references/visual-oracle-protocol/fase-4-critica-e-pattern.md`.

**Input**: PNG della Fase 3 + specifica del TSK (body + eventuale `visual_reference:`, ADR-012 §A).

1. Il critic è lo **stesso `fe-dev`** in una passata di review multimodale, **NON** un sub-agent
   dedicato né `qa-dev` (ADR-009): sub-skill inline, il fe-dev passa da producer a critic.
2. Legge i PNG via **Read tool** (multimodale nativo, nessun MCP custom).
3. **Prompt del critic** (verbatim):

   > Confronta il rendering con la specifica del TSK e produce una lista di difetti azionabili.

   Confronta ogni PNG con (a) body / Technical Specs del TSK, (b) `visual_reference:` se presente.
4. Produce `critic_findings` (lista difetti, vuota `[]` se nessuno); struttura dei 5 campi in Fase 5.

**Completamento**: lista difetti prodotta (anche vuota). Istanza del pattern evaluator-optimizer
(producer fe-dev → critic fe-dev → iterazione bounded); ordering ADR-013: develop → visual-oracle → review.

---

## Fase 5 — Diff Azionabile + Loop bounded

Prima di scrivere il report, leggi `.claude/skills/references/visual-oracle-protocol/schema-report.md` (schema JSON del diff e del report).

**Input**: `critic_findings` + verdict aggregato della Fase 3-bis (se ha già forzato `reject`) +
`current_iter` / `MAX_ITERATIONS`.

**Azione**: produce `{ "verdict": "pass|conditional|reject", "defects": [...] }`. I **5 campi per
ogni defect**: `description`, `viewport`, `theme`, `severity` (enum `major | minor | trivial`), `fix_hint`.


### Routing verdict → azione

| `verdict`     | `visual_status` scritto | `next_action`     | Comportamento |
|---|---|---|---|
| `pass`        | `pass`     | `done`            | TSK transita a `status: done`; pronto per review (ADR-013 Punto 1). |
| `conditional` | `conditional` | `loop`         | Ri-dispatch al `fe-dev` con la lista difetti come input handoff; **bounded** da `MAX_ITERATIONS` (default 3, analogo R.Q4 di CQRL). |
| `reject`      | `reject`   | `escalate-human`  | **Gate umano**; TSK resta `in_progress`; difetto strutturale, non auto-loop (ADR-013 §Rationale 6). |

Schema `next_action`: enum `done | loop | escalate-human` (mappa direttamente sul flusso
di `dev-protocol` Fase 4-bis, ADR-012 §H).

### Bound `max_iterations`

- Il loop `conditional → fe-dev → visual-oracle (iter N+1)` è **bounded** da
  `fe_correctness.max_iterations` (default 3).
- Se dopo `MAX_ITERATIONS` iterazioni il verdict è ancora `conditional` (nessuna
  convergenza) → **fail-loud + gate umano**: forza `verdict: reject`,
  `visual_status: reject`, `next_action: escalate-human`, e segnala in chat lo sforamento
  del bound. Coerente con il loop exhausted di CQRL (§7 r.16: `reject` = gate umano, mai
  auto-revert/auto-merge).

**Output prodotto**:
- Write `code_quality/reports/<TSK-id>-visual-iter-<N>.json` (schema sotto, conforme
  ADR-012 §H).
- Write `code_quality/reports/<TSK-id>-visual-iter-<N>.md` (digest umano-leggibile:
  verdict + tabella difetti + screenshot referenziati + loop status).
- Edit del frontmatter TSK: scrive **solo** il campo `visual_status:` (vedi nota
  single-writer sotto).
- Append a `wiki/log.md` (marker `visual-oracle TSK-ZZZ iter-N → <verdict>`).

**Criterio di completamento**: report JSON + digest scritti, `visual_status` aggiornato,
`next_action` determinato.

[^src: design_&_architecture/decisions/ADR-012.md §H]
[^src: design_&_architecture/decisions/ADR-013.md §Punto 1]
[^src: management/kanban/EP-005-fe-visual-oracle/US-017-skill-visual-oracle-protocol/TSK-021.md]

### Nota single-writer su `visual_status` (ADR-012 §A)

**SOLO questa skill** (`visual-oracle-protocol`) scrive il campo `visual_status:` nel
frontmatter del TSK. È il **single-writer** del campo (analogo a `review_status` per CQRL,
R.Q2). Dev-agent, PM, TPM, orchestrator **NON** lo scrivono a runtime: lo leggono soltanto
(code-review-protocol Fase 0 come gating precondition, orchestrator Oracle Pre-Check).
Enum del campo: `pending | pass | conditional | reject`. Questo evita race condition e
drift sul campo.

[^src: design_&_architecture/decisions/ADR-012.md §A]

---

---

## Schema Report

Il report `code_quality/reports/<TSK-id>-visual-iter-<N>.json` segue ADR-012 §H; schema JSON completo,
campi opzionali e mapping `next_action` in `.claude/skills/references/visual-oracle-protocol/schema-report.md` (leggila prima di scrivere il report).
**Campi obbligatori**: `tsk_id`, `iter`, `verdict`, `next_action`. Mapping `next_action` → `dev-protocol`
Fase 4-bis: `done` → TSK `status: done`, `visual_status: pass`; `loop` → ri-dispatch fe-dev (bounded
`max_iterations`); `escalate-human` → TSK resta `in_progress`, `visual_status: reject`, gate umano.
Digest umano `code_quality/reports/<TSK-id>-visual-iter-<N>.md`; lo slug `visual` lo distingue dagli iter
CQRL (`<TSK-id>-iter-<N>.{json,md}`); stesso side-channel `code_quality/reports/` (ADR-012 §B).

## Pattern — evaluator-optimizer

Istanza esplicita del pattern (come `code-review-protocol`, CQRL v2.12), ma producer ed evaluator sono lo
stesso agente `fe-dev` (ADR-009 §Rationale 1). Ordering ADR-013: **develop → visual-oracle → review**.
Dettaglio in `.claude/skills/references/visual-oracle-protocol/fase-4-critica-e-pattern.md`.

[^src: wiki/syntheses/fe-agent-correctness-strategy.md §Leva 1]
[^src: design_&_architecture/decisions/ADR-009.md §Decisione]
[^src: design_&_architecture/decisions/ADR-013.md §Punto 1]
