---
scope: scheduler-domain-policies
description: >
  Dettaglio policy di composizione inter-dominio per il parallel-scheduling (v2.11).
  Foglia di dettaglio per .claude/skills/parallel-scheduling.md — letta su trigger
  "se e solo se un dominio opt-in con comportamento composito è attivo".
  Ambito: regole ADR visual-oracle, ux-ui-review condizionale, functional-oracle,
  analytics composizione misurazione↔stima.
---
# Scheduler — Domain Policies (dettaglio composizione)

## Dominio `visual-oracle` — dettaglio ADR

**Riferimento**: ADR-013 §Punto 3 (sub-step L2, no livello DAG separato).

Effetto sul DAG: non aumenta il numero di livelli; estende la durata effettiva di L2
per TSK FE quando `fe_correctness.enabled: true`. Promuoverlo a L2.5 è scartato:
nessun guadagno di parallelismo rispetto al trattarlo come sub-step.

Ordering nel cascade (se tutti i domini abilitati):
`develop → visual-oracle → ux-ui-review → functional-oracle → review`

## Dominio `ux-ui-review` — procedura condizionale completa

**Attivazione**: `ux_ui.enabled: true` AND `scheduler.domains.ux-ui-review: true`.
**Riferimento**: ADR-019 §Rationale 7 (parallel durante conditional).

### Composizione con `visual-oracle` (se `fe_correctness.enabled`)

- `visual_status: reject` → ux-ui-review **SKIPPED** (rendering rotto; gate umano su visual oracle).
- `visual_status: pass` → parte normalmente.
- `visual_status: conditional` + `ux_ui.parallel_during_conditional: false` (default):
  ux-ui-review attende `visual_status: pass`.
- `visual_status: conditional` + `ux_ui.parallel_during_conditional: true` (opt-in):
  dispatch ux-ui-review in parallelo al loop visual oracle.

### Procedura dispatch condizionale — 5 step (EP-023, ADR-019 §Rationale 7)

Quando `TSK.visual_status == conditional` AND `ux_ui.parallel_during_conditional: true`:

1. Il visual oracle ha emesso `visual_status: conditional` per un TSK FE (loop in corso).
2. Lo scheduler dispatcha `ux-ui-review` in parallelo. Input: screenshot corrente
   (quello che ha generato il `conditional` — non uno snapshot aggiornato non ancora disponibile).
3. Il fe-dev riceve due set di finding nella stessa wave:
   - Visual oracle: fix rendering (es. overflow, palette non conforme).
   - UX/UI review: finding UX (es. gerarchia visiva, CTA, carico cognitivo).
4. Il fe-dev applica entrambi i set. Il visual oracle ri-verifica.
5. Se `visual_status: pass` a iterazione successiva: ux-ui-review non viene ri-eseguita
   (salvo `ux_ui_status: conditional`, che attiva il proprio loop da `ux_ui.max_iterations`).

Non-contesa garantita: `visual_status` e `ux_ui_status` sono campi frontmatter distinti,
single-writer distinti. Nessuna race condition indipendentemente dal flag.

### Composizione con `a11y` (EP-007, ADR-016)

- **Modalità 1** (a11y inline in visual-oracle Fase 3-bis): ux-ui-review riceve sia
  `visual_status` sia `a11y_status` prima di partire. Finding a11y diventano
  `open_questions` nel report ux-ui se `ux_ui.delegate_a11y_to_ep007: true`.
- **Modalità 2** (a11y batch post-Develop): `a11y` e `ux-ui-review` girano in parallel
  sullo stesso TSK FE done senza contesa (scrivono campi distinti: `a11y_status` vs `ux_ui_status`).
- **Triplice parallelizzazione** (visual-loop + ux-ui + a11y Modalità 2): sicura
  senza contesa perché i tre status sono single-writer distinti.

### Sotto-capability Design (`ux-ui-design`, US-029)

Off-DAG (no dominio scheduler dedicato, ADR-020 §C). Invocata umano-driven via
`/ux-ui-design <brief>`; deliverable → campo frontmatter `ui_design_spec: <path>`
(single-writer TPM). Non ha ordering con `visual-oracle`/`ux-ui-review`/`code-review`
(è pre-TSK, non post-Develop).

## Dominio `functional-oracle` — dettaglio composizione

**Riferimento**: ADR-066 §Conseguenze + ADR-067 §A.
**Esecutore**: `qa-dev` Modalità functional-oracle, fallback `fe-dev` (ADR-067 §A).

### Composizione con `visual-oracle` (se `fe_correctness.enabled`)

- `visual_status: reject` → functional-oracle **SKIPPED**.
- `visual_status: pass` → parte normalmente.
- `visual_status: conditional` → il functional oracle può girare (risultati annotati come
  condizionali nel report).

### Composizione con `ux-ui-review` (se `ux_ui.enabled`)

La ux-ui-review precede il functional oracle nello stesso cascade. Il functional oracle
non aspetta `ux_ui_status` come precondizione bloccante (review UX informativa, no ABORT
— ADR-019 Punto 2). Parte dopo che la ux-ui-review ha terminato per ordering naturale.

**Activation link**: `fe_correctness.functional_oracle.enabled: true →
scheduler.domains.functional-oracle: true` (auto-attivazione al cambio del flag master;
no edit manuale della sezione `domains`).

## Dominio `analytics` — dettaglio composizione

**Riferimento**: ADR-023 §H (cross-scope parallel, same-scope serial).

### Composizione misurazione ↔ stima (same-scope serial, EP-010)

Su uno stesso `project_id`, la stima/retrospettiva di accuratezza (EP-010, ADR-027)
aspetta che la misurazione corrente sia completata (eventi tutti registrati,
`analyze_timeline` aggiornato) come input. Race su event store + `analyze_timeline`.
Cross-scope (es. misurazione P-7 + stima P-8) resta parallelo.

### Retrospettiva accuracy (`--review-accuracy=<estimate_id>`)

Operazione composita: EP-009 (misurazione effettiva) + EP-010 (rilettura stima storica)
→ `analytics/reports/accuracy/<estimate_id>.{json,md}` (ADR-027 §C).
Serializzata sul `project_id` collegato all'`estimate_id`. Cross-scope con retrospettive
su `estimate_id` diversi resta parallelo.

**Nessun nuovo dominio (EP-010)**: EP-010 riusa il dominio `analytics` di EP-009
(ADR-023 §H). Pattern: ogni capability può popolare più operazioni canoniche dentro
lo stesso dominio.
