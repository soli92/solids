# Fase 3-bis — Structured Checks (opt-in), dettaglio

Ambito: gate di attivazione, check `visual-regression`, `axe-a11y`, `interaction-test`, verdict aggregato. Foglia di `.claude/skills/visual-oracle-protocol.md` (testo originale spostato senza modifiche; la spina dorsale resta nella skill e prevale in caso di dubbio).

## Fase 3-bis — Structured Checks (opt-in)

**Posizione**: inserita **dopo Fase 3 (Screenshot)** e **prima di Fase 4 (Critica
Visiva)**. Materializza la Leva 2 (oracoli binari) della sintesi `fe-agent-correctness-strategy`.

**Gate di attivazione**: `factory.config.yaml.fe_correctness.checks: [<id>, ...]`.
- **Lista vuota** (default `checks: []`) → **fase skip**; comportamento **identico a
  US-017 base** (backward compat: nessuna ERROR, nessun cambio di flusso). I tre check
  riportano `status: skip` nel report.
- Ogni `<id>` configurato attiva il check corrispondente. I tre id canonici sono:
  `visual-regression`, `axe-a11y`, `interaction-test`.

**Fail-loud per check configurato ma tool assente** (messaggio verbatim):

> Check `<id>` richiede `<tool>`; vedi runbook.

### Check `visual-regression`

- **Prerequisito ambientale**: snapshot di baseline in
  `code_quality/reports/<TSK-id>-visual-baseline/`.
- **Input**: i PNG della Fase 3 + la baseline di riferimento.
- **Azione**: diff binario pixel-per-pixel contro lo snapshot di baseline. Se la baseline
  è **assente al primo run** → **auto-crea la baseline** dai PNG correnti (fail-loud
  documentato: il primo run stabilisce il riferimento, i successivi diffano contro di esso).
- **Output JSON**:
  ```json
  { "status": "pass|fail", "diff_pixels": 0, "baseline_path": "code_quality/reports/<TSK-id>-visual-baseline/" }
  ```

### Check `axe-a11y`

- **Prerequisito ambientale**: `axe-core` disponibile, **iniettato da Playwright** nella
  pagina renderizzata (stessa pagina della Fase 2/3).
- **Input**: il DOM della pagina renderizzata.
- **Azione**: esegue la scansione `axe-core` sulla pagina.
- **Fail-loud** se `axe-core` non installato: «Check `axe-a11y` richiede `axe-core`; vedi runbook».
- **Output JSON**:
  ```json
  { "status": "pass|fail", "violations": [ { "rule": "color-contrast", "severity": "serious", "selector": "..." } ] }
  ```

### Check `interaction-test`

- **Prerequisito ambientale**: campo `interaction_test_spec:` nel **frontmatter TSK**
  (path, relativo al code_path, a un file di test Playwright). Campo opzionale scritto dal
  TPM in fase di taskizzazione (ADR-012 §A).
- **Input**: il file Playwright indicato da `interaction_test_spec`.
- **Azione**: esegue gli scenari di interazione usando lo **stesso Playwright runtime
  della Fase 2** → zero overhead aggiuntivo, riusa l'install (ADR-008 §Rationale 1 +
  §Conseguenze: «US-020 `interaction-test` usa lo stesso Playwright runtime»).
- **Fail-loud** se `interaction_test_spec:` è valorizzato ma il file è assente:
  «Check `interaction-test` richiede il file `<path>`; vedi runbook».
- **Output JSON**:
  ```json
  { "status": "pass|fail", "scenarios": [ { "name": "click submit", "status": "pass" } ] }
  ```

### Verdict aggregato della Fase 3-bis

- **Qualsiasi check binario `fail`** → `verdict: reject` **automatico**: nessun critic
  LLM necessario per il rigetto (gli oracoli binari sono deterministici e sufficienti a
  rigettare). Si salta alla Fase 5 con `next_action: escalate-human`.
- **Tutti i check binari `pass`** (o `skip`) → si **procede alla Fase 4** (critica visiva
  LLM) per il giudizio finale.

**Output prodotto**: popola il campo `checks` del JSON report (vedi sezione «Schema
Report») con `checks.visual_regression`, `checks.axe_a11y`, `checks.interaction_test`.
Ogni check non configurato → `status: skip`.

**Criterio di completamento**: tutti i check configurati hanno prodotto il loro output
JSON; il verdict aggregato è calcolato (reject su qualsiasi fail, altrimenti pass-through
a Fase 4).

[^src: design_&_architecture/decisions/ADR-008.md §Rationale punto 1]
[^src: design_&_architecture/decisions/ADR-012.md §H]
[^src: management/kanban/EP-005-fe-visual-oracle/US-020-oracoli-strutturati-binari/TSK-025.md]
