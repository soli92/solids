---
name: code-review-protocol
description: Protocollo di review qualitativa post-Develop (PATTERN §19, v2.12). 5 fasi (Bootstrap → Stack detection → 3 Passate parallele → Aggregator → Router). Invocata da code-reviewer; sub-skill stack-detector + feedback-router.
---
# Protocollo di Code Quality Review

Riferimenti: PATTERN §19 (CQRL completo), §19.2 (Stack Detector), §19.3 (3 Passate +
Aggregator), §19.4 (Feedback Router), §19.6 (invarianti R.Q1-R.Q7), §7 r.16 (gate
umano `reject`). Sub-skill: [`stack-detector`](./stack-detector.md),
[`feedback-router`](./feedback-router.md).

## Prerequisiti

- `factory.config.yaml.code_quality.enabled: true` (R.Q5 — STOP altrimenti).
- `<code_path>` accessibile in lettura.
- TSK target valido: `consumer: agent` + `status: done` + `review_status: pending`.
- `code_quality/rules/` esiste (o crealo vuoto al primo run).

## Costanti

```
MODEL                    = "claude-sonnet-5-5"
MAX_PARALLEL_PASSES      = 3
MAX_FINDINGS_PER_PASS    = 30
PROMPT_TEMPERATURE       = 0.2
```

---

## Fase 0 — Bootstrap

Layer filter gate (`code_quality.router.layer_filter`), precondizioni TSK target
(`review_status`, `review_iter < max_iterations`), precondizione visual oracle (hard ABORT
se `layer:fe` + `fe_correctness.enabled` + `visual_status != pass`), nota informativa UX/UI
(soft, no ABORT, opt-in `ux_ui.enabled`), calcolo `files_in_scope` (code_path → commit diff
→ best-effort scan).

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (layer filter gate verbatim, passi 1-5 della
> precondition, algoritmo `files_in_scope`, differenza hard ABORT visual vs nota soft UX/UI,
> backward compat per entrambe le precondition opt-in, Fase 1 Stack Detection, Fase 2 tre passate
> core con schema prompt, Passate 1/2/3 con role_persona e filtri, soglie complessità metriche)
> si trova in:
> `.claude/skills/references/code-review-protocol/fase-0-bootstrap.md`
>
> Leggi obbligatoriamente quella foglia prima di avviare il review.
> Se il file manca → STOP e segnala.

---

## Fase 2 — Passata 4: Premortem on Merge (opt-in v2.16, ADR-005)

**Pre-condizione**: `"premortem-on-merge" IN factory.config.yaml.code_quality.passes`.
A flag assente (default): **SKIP** — comportamento identico a v2.15.
Mini-premortem (max 3-5 finding, `timeframe: 3mo`). Non modifica il verdict aggregator.
Touchpoint #3: se `verdict == conditional` e TSK tagged `tiger-*` → suggerisci `/premortem`.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (pre-condizione verbatim, parametri invocazione
> `premortem-protocol`, output sotto-sezione, Touchpoint #2 out-of-scope v2.17+) si trova in:
> `.claude/skills/references/code-review-protocol/passata-4-premortem-on-merge.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il pass.
> Se il file manca → STOP e segnala.

---

## Fase 2 — Passata 5: YAGNI Decision Ladder (advisory, opt-in v2.39, EP-057)

**Pre-condizione**: `factory.config.yaml.ponytail.passes.yagni_ladder: true`.
A flag spento (default): **SKIP** — comportamento identico a v2.38.
7 livelli Decision Ladder valutati per file modificato. **Non cambia il verdict.**
Invariante R.PY1: non può mascherare findings security/a11y/trust-boundary (Passate 1-3).
Output: `### Pass 4 — YAGNI Ladder (advisory)` nel report.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (pre-condizione, tabella 7 livelli verbatim,
> schema output tabella candidati, nota di numerazione «Pass 4 advisory», relazione con
> `/ponytail-review` standalone) si trova in:
> `.claude/skills/references/code-review-protocol/passata-5-yagni-ladder.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il pass.
> Se il file manca → STOP e segnala.

---

## Fase 2 — Passata 6: Aderenza alla specifica (opt-in, EP-077)

**Pre-condizione**: `code_quality.passes.spec_adherence: true`, altrimenti **SKIP**. Finding con `pass: spec`.

> **[TRIGGER VINCOLANTE]** Leggi `.claude/skills/references/code-review-protocol/passata-6-aderenza-spec.md`;
> se manca → STOP.

---

## Fase 2 — Passata 7: Revisione del motion (advisory, opt-in, EP-090)

**Pre-condizione**: `ui_craft.enabled: true` e `ui_craft.motion_review: true`, **e** il diff tocca motion
(grep: `transition`, `animation`, `@keyframes`, `motion.`, `animate=`, `useSpring`, `ease-`,
`transform-origin`, `prefers-reduced-motion`); altrimenti **SKIP**. Advisory: **nessun verdict**, i
finding vanno in una sezione `### Pass 7 — Motion (advisory)` del report e non entrano nell'aggregatore (Fase 3), come la Passata 5.

> **[TRIGGER VINCOLANTE]** Leggi `.claude/skills/references/code-review-protocol/passata-7-motion.md`;
> se manca → STOP.

---

## Fase 3 — Aggregator (deterministico + mini-prompt)

### Step deterministico (no LLM call)

1. **Dedup**: raggruppa finding per `(file, lines, rule_id)`. Se ≥ 2 passate riportano
   lo stesso → una sola istanza con `detected_by: [pass1, pass2, …]` e severity = max.
2. **Soglie per stack**: applica `code_quality.thresholds` per filtri specifici.
3. **Cap finale**: se totale > 100, taglia per `severity DESC` + `fix_complexity ASC`,
   marca `truncated: true`.
4. **No-progress detection** (se `current_iter > 1`): `set(rule_id_iter_N) == set(rule_id_iter_N-1)`
   con tolerance esatta → `no_progress: true` → forza verdict `reject`.
5. **Regression detection** (se `current_iter > 1`): finding in file NON toccati dalla fix
   → `regression: true` → flag rosso nel digest, raccomanda rollback.

### Step mini-prompt (1 LLM call)

Regole di verdict:
- `pass`: 0 finding high/medium (esclusi low).
- `conditional`: ≥ 1 finding high o ≥ 3 medium, NESSUN marker rosso.
- `reject`: marker `no_progress` OR `regression` OR `current_iter == max_iterations`
  OR ≥ 5 finding high.

---

## Fase 4 — Scrittura report

1. **Write** `code_quality/reports/<TSK-id>-iter-<N>.json` con schema §19.3:
   ```json
   {
     "tsk_id": "...", "stack_descriptor": {...}, "iter": N,
     "passes_run": ["idiomaticity", "design", "robustness"],
     "findings": [...], "verdict": "pass | conditional | reject",
     "verdict_rationale": "...", "summary": "...",
     "markers": {"no_progress": false, "regression": false, "loop_exhausted": false, "degraded": false},
     "files_modified_by_fix": [...],
     "generated_at": "<ISO-8601>", "reviewer_version": "code-reviewer@2.12.0"
   }
   ```
2. **Write** `code_quality/reports/<TSK-id>-iter-<N>.md` (digest umano).
3. **Rotation**: se `code_quality.reports.retain_iterations: 5` e ci sono > 5 file per
   `<TSK-id>-iter-*`, elimina i più vecchi.

---

## Fase 5 — Router

Output del router per verdict:
- **`pass`** → aggiorna frontmatter TSK (`review_status: passed`, `review_iter: <N>`,
  `review_report: ...`, `updated: <ISO>`). Append `wiki/log.md`. Suggerisci `/promote`.
- **`conditional`** → produci `task_package` JSON, mostra in chat con conferma `y/N`.
  Se `y`: dispatch dev-agent corrispondente. Aggiorna frontmatter.
- **`reject`** → aggiorna frontmatter (`review_status: rejected`). **STOP** + escalation
  umana con digest + markers.

## Append a `wiki/log.md`

```markdown
- YYYY-MM-DD HH:MM — `review TSK-XXX iter-N → <verdict>`
  - Reviewer: code-reviewer@2.12.0
  - Stack: {language}/{framework} {version} (conf {x})
  - Finding: {high: H, medium: M, low: L}, dedup: {D}
  - Markers: {no_progress|regression|loop_exhausted|degraded se attivi}
  - Report: [code_quality/reports/<TSK-id>-iter-<N>.md](...)
```

## Loop exhausted (gate §7 r.16)

Se `current_iter == max_iterations` e `verdict: conditional` calcolato → forza `reject`
con `markers.loop_exhausted: true`. Router gestisce come `reject` standard → escalation umana.

## Regole anti-corner-case

- **Repo vuoto o files_in_scope vuoto**: ABORT pulito, verdict implicito `pass`. Segnala in chat.
- **Regole vuote per stack**: segnala in chat + ABORT con suggerimento «Popola
  `code_quality/rules/canonical/{language}.{framework}.*`». Mai inventare regole on-the-fly.
- **Conflitto cross-tier**: stesso `rule_id` in `canonical/` e `emergent/` → vince tier a
  priorità più alta + versione più recente come tiebreaker. Annota in `conflict_resolution[]`.
- **TSK senza commit-hash trackable**: procedi best-effort sull'intero `<code_path>` con
  `scope_inferred: true` nel report. Mai bloccare.

## Non in scope per questa skill

- **Eseguire codice** del repo — scope di `qa-dev` (test funzionali).
- **Modificare codice** — mai (R.Q2).
- **Promuovere regole** — `emergent` → `canonical` è gate umano §19.5.
- **Pubblicare findings su tool esterni** — il report resta locale.
