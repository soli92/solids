---
name: ux-ui-review-protocol
description: Skill procedurale review UX/UI — 5 step ancorati alla rubrica anti-soggettività (Nielsen 10 + dimensioni UI 6 + flusso 5). Capability opt-in v2.18, PATTERN §3 UX/UI Review.
---
# Protocollo UX/UI Review — review strutturata in 5 step ancorata alla rubrica anti-soggettività

Skill procedurale fondante della capability UX/UI Review (EP-008) lato Review: incapsula la
conoscenza operativa per eseguire una review UX/UI **ancorata alla rubrica anti-soggettività**
([[ux-ui-rubric-anti-subjectivity]]), così che ogni finding sia ripetibile e difendibile, mai
"a sensazione". È caricabile al bisogno da `fe-dev`, `qa-dev` e dall'agente `ux-ui-reviewer`
(US-030, se scaffoldato) — istanza del pattern [[thin-agents-fat-skills-refactor]].

**Regola invariante**: **ogni `finding` cita almeno un `rubric_ref`** (asse 1/2/3 o regola del
design system). **Niente finding "a sensazione".** Le domande aperte → `open_questions`, mai
`findings`. Punti opinabili → `opinion: true`.

È un'**operazione opzionale** (PATTERN.md §3 «UX/UI Review»), attiva solo con
`factory.config.yaml.ux_ui.enabled: true`. A capability spenta la skill è no-op.

Riferimenti: ADR-017 (riuso single-source infra screenshot), ADR-018 (default fallback DS),
ADR-019 (ordering pipeline), ADR-020 (schema consolidato), ADR-063 (anti-fabbricazione).
Runbook: [`wiki/runbooks/ux-ui-review-runbook.md`](../../wiki/runbooks/ux-ui-review-runbook.md).

[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-028-skill-ux-ui-review-protocol/US-028.md §Business Rules]

---

## Step 1 — Input Visivo

**Cascata a 4 modalità** (url → component-harness → mockup → no-visual):

```
if target è URL/route http/https:        modalità = "url"
elif componente isolato + harness:       modalità = "component-harness"
elif mockup statico (immagine/PNG):      modalità = "mockup"
elif mode == "no-visual" esplicito:      modalità = "no-visual"
else:                                    → STOP-condition fail-loud (ADR-063 §A)
```

**Step 1.0 — Serve & ambiente** (prerequisito prima di `capture_screenshot`): avviare server
effimero se necessario, registrare pid per teardown, gestire fail-loud se Node/CWD errato.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (procedura avvio server, STOP-condition fail-loud
> ADR-063 §A verbatim, note modalità no-visual, matrice viewports) si trova in:
> `.claude/skills/references/ux-ui-review/serve-ambiente.md`
>
> Leggi obbligatoriamente quella foglia prima di avviare il server o invocare capture_screenshot.
> Se il file manca → STOP e segnala.

**Output Step 1**: `{target, modalità, screenshots: [{viewport, theme, path}]}`.

---

## Step 2 — Token + Design System

Invoca `extract_design_tokens(target)` + `check_design_system_conformance(target, ref)`.
**Cascata DS a 3 livelli** (ADR-018): design_system_path configurato → token estratti dal codice
/ figma-sync → default ragionevoli (5 famiglie minimali).

Con `source: defaults`: NON emettere deviations `major/minor` — solo `open_questions`.
Annotare nel report la formula verbatim DS non disponibile.

> **[TRIGGER VINCOLANTE]** Il dettaglio delle 5 famiglie di token di default (type, colors,
> spacing, radii, focus) e la regola applicativa per `source: defaults` si trovano in:
> `.claude/skills/references/ux-ui-review/default-design-system.md`
>
> Leggi obbligatoriamente quella foglia se la cascata DS raggiunge il fallback.
> Se il file manca → STOP e segnala.

**Output Step 2**: `{tokens_source, tokens, conformance: {deviations[], open_questions[]}}`.

---

## Step 3 — Rubrica 3 Assi (core della review)

Valuta l'input visivo contro tutti e tre gli assi: Asse 1 (Nielsen 10), Asse 2 (UI visiva 6),
Asse 3 (flusso UX 5, solo su flussi multi-passo). Ogni finding: `rubric_ref` obbligatorio.
Contrasto cromatico delegato a Step 4 (axe-core), non duplicare.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo delle 3 tabelle (10 euristiche Nielsen con
> domanda operativa, 6 dimensioni UI visiva, 5 dimensioni flusso UX) e il criterio di
> completamento si trovano in:
> `.claude/skills/references/ux-ui-review/rubrica-3-assi.md`
>
> Leggi obbligatoriamente quella foglia prima di scorrere gli assi.
> Se il file manca → STOP e segnala.

**Output Step 3**: `findings[]` (ciascuno con `rubric_ref`), `positive_findings[]`.

---

## Step 3-bis — Critic/Judge Design (condizionale, opt-in EP-019)

**Trigger**: SOLO se `factory.config.yaml.design_intelligence.critic_enabled: true`.
A flag spento (default): **SKIP** — procedere direttamente allo Step 4 (R.P3).
In modalità `no-visual` → SKIPPED automaticamente.

6 dimensioni di qualità visiva (ADR-070 §D): critic-gerarchia, critic-contrasto,
critic-allineamento, critic-ritmo, critic-spaziatura, critic-coerenza-tema.
Ogni finding: `evidence_zone` obbligatoria, `is_refinement_suggestion: true` (R.D3).
Sotto-dimensione Intention Economy: eseguire SOLO se `rubric_intention_economy: true`.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (R.D3, confine EP-005 verbatim, schema finding
> Critic/Judge, bounded loop, sotto-dimensione Intention Economy con 3 domande operative,
> anti-pattern Attention Economy, schema output intention_economy_section) si trova in:
> `.claude/skills/references/ux-ui-review/critic-judge.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il passo.
> Se il file manca → STOP e segnala.

**Output Step 3-bis**: `critic_findings[]` in `critic_judge_section` (separata da `findings[]`).

---

## Step 4 — Delega a11y

Se EP-007 attiva (`a11y.enabled: true` e `delegate_a11y_to_ep007: true`): invoca
`run_a11y_scan(target, standard: "wcag22aa")`. Incorpora i risultati in sezione separata
(`a11y_section`), **non** nei `findings[]` UX (ADR-014).
Se EP-007 non attiva: `open_questions: ["a11y scan non eseguita — EP-007 disabilitata"]`.

---

## Step 5 — Report Standard

Produce il report nello **schema JSON standard** (6 campi top-level: target, type, summary,
findings, positive_findings, open_questions; + tokens_source, critic_judge_section,
intention_economy_section, generated_by) + digest Markdown.

Guard forma: ogni finding con `rubric_ref` (`rubric_strict: true` default).
Guard sostanza (ADR-063 §B): ogni finding con `evidence` che referenzia artefatto reale — finding
senza evidence → **rigettato**. I due guard sono complementari e indipendenti.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (schema JSON verbatim, campo evidence obbligatorio
> con valori ammessi per modalità, regola invariante rubric_ref, guard evidence-provenance ADR-063
> §B con regola di rigetto, storage side-channel ADR-020, criterio di completamento) si trova in:
> `.claude/skills/references/ux-ui-review/report-standard.md`
>
> Leggi obbligatoriamente quella foglia prima di scrivere il report.
> Se il file manca → STOP e segnala.

---

## Esito della review (handoff Fase 4-ter, ADR-019)

Quando invocata come sub-step di Develop FE, l'esito popola il frontmatter TSK `ux_ui_status`:
- **pass** → procede a Fase 5 (handoff a `done`).
- **conditional** → loop `fe-dev` bounded da `ux_ui.max_iterations` (default 3).
- **reject** → gate umano (difetto strutturale UX non recuperabile in N iter).

---

## Vincoli del reviewer

1. **NON progettare**: critica descrittiva, non prescrittiva nel dettaglio implementativo.
2. **NON auto-valutare**: se il caller ha contribuito al design, raccomandare agente distinto.
3. **NON dichiarare conformità a11y**: accessibilità delegata a EP-007 (Step 4).

---

## Fallback senza input visivo (modalità `no-visual` esplicita)

Richiede dichiarazione esplicita. NON si attiva da `screenshots: []` su target visivo (→ STOP-condition).
Cosa si può fare: struttura logica flusso (Asse 3) + coerenza codice/DS (Step 2 conformance check).
Cosa NON si può fare: **NIENTE finding su dimensioni visive** (Asse 2) — sarebbero "a sensazione".
Annotare `summary.coverage_note: "solo codice sorgente, nessun rendering — review ridotta"`.

---

## Pattern

- Istanza di [[evaluator-optimizer]] (lato evaluator): conditional → fix → re-review, bounded da `ux_ui.max_iterations`.
- Istanza di [[thin-agents-fat-skills-refactor]]: la procedura vive qui (fat skill), consumata da agenti thin.
- PATTERN.md §3 operazione opzionale «UX/UI Review». Opt-in `factory.config.yaml.ux_ui.enabled`.
