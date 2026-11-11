# ux-ui-review-and-design-spec — fe-dev (EP-008, opt-in `ux_ui`)

**Ambito**: procedura dettagliata di (a) UX/UI Review in Fase 4-ter e (b) consumo del
deliverable `ui_design_spec:` (Design spec input) in Fase 4 per `fe-dev`. Entrambi
attivi tramite `ux_ui.enabled: true`. Foglia di dettaglio di
`.claude/agents/fe-dev.md §T3`.

---

## Sezione A — UX/UI Review (EP-008)

### Fase 4-ter — UX/UI Review (ADR-019 Punto 1)

Quando `ux_ui.enabled: true AND TSK.layer: fe`, il `dev-protocol` esegue un sub-step
**Fase 4-ter** subito dopo la Fase 4-bis (Visual Verification), **prima** di marcare
il TSK `status: done`. La review è eseguita via skill `ux-ui-review-protocol` (US-028)
come sub-procedura, oppure dispatchata all'agente `ux-ui-reviewer` (US-030) se
`ux_ui.agents.reviewer: true`. Non è un nuovo livello DAG: è un sub-step di L2 (develop).

**Ordering**: `Develop → Visual Verification → UX/UI Review → CQRL` (ADR-019). Il visual
oracle verifica l'aderenza alla specifica (oggettivo); la ux-ui-review valuta euristiche
(soggettivo strutturato sulla rubrica ux-ui-rubric-anti-subjectivity); il CQRL valuta
il codice finale. Composizione: la ux-ui-review attende `visual_status` non-pending;
se `visual_status: reject` → review **SKIPPED**, TSK resta in-progress.

### Esito + loop evaluator-optimizer

Il fe-dev riceve i finding (ciascuno con `rubric_ref`) come input di handoff:

| Esito | Azione |
|---|---|
| pass | `ux_ui_status: pass`; TSK procede a Fase 5 |
| conditional | loop fe-dev bounded da `ux_ui.max_iterations` (default 3); applica fix citando `rubric_ref` e re-invoca |
| reject | `ux_ui_status: reject`; TSK resta in-progress; **gate umano** |

**Single-writer**: `ux_ui_status:` e `ux_ui_report:` scritti dall'agente che esegue
la review (`ux-ui-reviewer` se scaffoldato, altrimenti fe-dev via skill US-028).
Report side-channel: `code_quality/reports/<TSK-id>-uxui-review-iter-<N>.{json,md}`.

**Loop conditional visual oracle (EP-023, opt-in)**: se
`ux_ui.parallel_during_conditional: true`, i finding UX arrivano nella stessa wave
del visual oracle. Applica entrambi i set di fix nell'iterazione successiva.

**No-op a flag spento**: se `ux_ui.enabled: false` (**default**) → Fase 4-ter no-op,
nessun `ux_ui_status:` scritto, comportamento v2.17 identico.

---

## Sezione B — UX/UI Design Spec Input (EP-008, ADR-020)

### `ui_design_spec:` come input visivo di prima classe in Fase 4

Quando il frontmatter del TSK valorizza `ui_design_spec: <path>` (scritto dal **TPM**
in fase di scrittura TSK — single-writer, ADR-020 §A/§F), il fe-dev lo legge in
**Fase 4 (Develop)** come specifica visiva di prima classe, con la stessa semantica
di `interaction_test_spec:` di EP-005 (ADR-012). Il path punta al deliverable prodotto
da `ui-designer` in `code_quality/reports/<TSK-id>-uxui-design.json` (+ `.md`), che
contiene wireframe, `component_spec`, `user_flow`, copy e il `rationale` del designer.

### Come il fe-dev lo consuma (ADR-020 §A workflow handoff punto 3)

- Legge `ui_design_spec:` se presente; implementa il componente seguendo wireframe +
  `component_spec` + rationale del designer come riferimento canonico.
- Le `assumptions[]` e `open_questions[]` del deliverable non risolte possono diventare
  `open_questions` del TSK.
- Il deliverable Design è **single-shot** per TSK (no iter-N): il path è stabile,
  eventuali ridisegni sovrascrivono il file (versioning via git).

**Separazione no auto-eval (ADR-020 §H)**: il fe-dev **non** progetta né auto-valuta il
design. Il fe-dev non scrive mai `ui_design_spec:` (scope esclusivo del TPM).

**No-op a campo assente**: un TSK FE senza `ui_design_spec:` è pienamente valido (0 ERROR).

Cross-link: [ADR-019](../../../design_&_architecture/decisions/ADR-019.md),
[ADR-020](../../../design_&_architecture/decisions/ADR-020.md),
[US-032](../../../management/kanban/EP-008-ux-ui-review-design-capability/US-032-integrazione-visual-oracle-cqrl-scheduler/US-032.md).
