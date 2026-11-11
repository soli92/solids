# Fase 4-ter — UX/UI Review (dettaglio, opt-in ux_ui)

**Ambito**: sub-step di Develop FE, Class B doubly opt-in (FE-only, ux_ui.enabled + visual_status
non-pending). Posizionata dopo la Fase 4-bis (Visual Verification) e prima della Fase 5
(handoff a `done`). Formalizza il Punto 1 di ADR-019 (ordering `develop → visual-oracle →
ux-ui-review → code-review`). Questa foglia contiene la procedura completa; il trigger e il
no-op esplicito vivono nel corpo di `dev-protocol.md`.

---

## Trigger (condizione AND)

- `TSK.layer == 'fe'` **AND** `factory.config.yaml.ux_ui.enabled == true`.

## No-op esplicito (backward compat)

A flag spento (`ux_ui.enabled: false`, default) **oppure** `TSK.layer != 'fe'`,
la Fase 4-ter è **no-op**: il TSK passa direttamente dalla Fase 4-bis alla Fase 5,
con `ux_ui_status` assente o `pending`. **Comportamento identico a v2.17.** Una factory
che non opta-in non vede alcuna differenza nella pipeline FE (ADR-019 §Rationale 4).

## Pre-condizione (composizione con Fase 4-bis, ADR-019 §Punto 3)

- `visual_status` deve essere **non-pending** nel TSK: la Fase 4-bis deve aver concluso
  (`pass`, `conditional` o `reject`) se `fe_correctness.enabled: true`. Se
  `fe_correctness.enabled: false`, la pre-condizione **non è applicabile** (no visual
  oracle nella pipeline) e la Fase 4-ter parte immediatamente dopo la Fase 4.
- Se `visual_status: reject` → la Fase 4-ter è **SKIPPED** (no point reviewing un
  rendering rotto): il TSK resta `in-progress` con gate umano sul visual oracle. Mai
  procedere a review UX su rendering non validato.
- Se `visual_status: conditional` → la Fase 4-ter **può** partire in parallel al loop
  visual oracle (ottimizzazione ADR-019 §Rationale 7): la ux-ui-review prepara findings
  sul rendering corrente mentre il fe-dev applica i fix visual, riducendo round-trip.

## Fail-loud

Se il trigger è soddisfatto (`layer: fe` + `ux_ui.enabled: true`) ma né la skill
`ux-ui-review-protocol` né l'agente `ux-ui-reviewer` (se `ux_ui.agents.reviewer: true`)
sono presenti nell'adapter → **ERROR** «`ux_ui.enabled: true` ma nessun esecutore
ux-ui-review disponibile (skill `ux-ui-review-protocol` assente e agente
`ux-ui-reviewer` non gating); impossibile eseguire la Fase 4-ter». STOP.
Mai degradare silenziosamente a no-op quando il flag è attivo.

## Azione

1. Invoca `ux-ui-reviewer` (agente, se `ux_ui.agents.reviewer: true`) **oppure** la skill
   `ux-ui-review-protocol` (US-028) via agente attivo nella topologia (fallback),
   passando il `TSK-id` e il `resolved_code_path` (da Fase 0 step 2-bis). La separazione
   designer ↔ reviewer è enforced (mai auto-valutazione, US-030).
2. Produce report side-channel in
   `code_quality/reports/<TSK-id>-uxui-review-iter-<N>.{json,md}` (slug `uxui-review`
   distingue da `visual`/`a11y`/CQRL, ADR-019 §Schema dati).
3. Aggiorna frontmatter TSK: `ux_ui_status: pending|pass|conditional|reject` +
   `ux_ui_report: <path>` (single-writer = reviewer, US-032 §Frontmatter).

## Esiti

```
verdict: pass        → ux_ui_status: pass; TSK transita a status: done (→ Fase 5).
verdict: conditional → loop fe-dev (bounded ux_ui.max_iterations, default 3);
                       i findings con rubric_ref sono l'input handoff dell'iterazione
                       successiva; il TSK resta in-progress fino a pass o esaurimento bound.
verdict: reject      → ux_ui_status: reject; TSK resta in-progress; gate umano
                       (difetto strutturale UX non risolvibile in 1-3 iter; coerente con
                       CQRL §19 reject → gate umano e con Fase 4-bis, non auto-loop).
```

- **Loop `conditional`**: bounded da `ux_ui.max_iterations` (default `3`, analogo a
  `fe_correctness.max_iterations` della Fase 4-bis e a `code_quality.max_iterations` /
  R.Q4 di CQRL). A ogni iterazione la lista findings (ciascuno con `rubric_ref`,
  invariante anti-soggettività) è passata come handoff a `fe-dev`, che ri-implementa e
  ri-sottopone alla ux-ui-review. Esaurito il bound senza `pass`, l'esito degrada a gate
  umano (non `done`).
- **`reject`**: il TSK **non** transita a `done`; resta `in-progress` con
  `ux_ui_status: reject`. Diversamente dal `visual_status: reject` (che blocca a valle la
  review codice, Fase 0 di `code-review-protocol`), il `ux_ui_status` non blocca il
  code-review (precondition solo informativa, ADR-019 §Punto 2).

**Input**: TSK FE con `visual_status` non-pending (output Fase 4-bis se
`fe_correctness.enabled: true`; altrimenti output Fase 4 diretto);
`factory.config.yaml.ux_ui`.
**Output**: `ux_ui_status: pass` (→ Fase 5) | loop fe-dev (`conditional`) |
`ux_ui_status: reject` + gate umano | SKIPPED se `visual_status: reject`.
**Criterio**: `verdict == pass` → procedi a Fase 5; altrimenti loop bounded o STOP per gate umano.

[^src: design_&_architecture/decisions/ADR-019.md §Punto 1 — dev-protocol Fase 4-ter (flusso verbatim)]
[^src: design_&_architecture/decisions/ADR-019.md §Punto 3 §Composizione — visual_status non-pending, reject → SKIPPED]
[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-032-integrazione-visual-oracle-cqrl-scheduler/US-032.md §Estensione dev-protocol]
