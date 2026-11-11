# Schema Report e schema dei difetti

Ambito: JSON report ADR-012 §H (campi, mapping `next_action`, digest umano) e struttura JSON del diff della Fase 5. Foglia di `.claude/skills/visual-oracle-protocol.md` (testo originale spostato senza modifiche; la spina dorsale resta nella skill e prevale in caso di dubbio).

## Schema Report

File: `code_quality/reports/<TSK-id>-visual-iter-<N>.json`. Schema **verbatim** conforme
ad ADR-012 §H:

```json
{
  "tsk_id": "TSK-NNN",
  "iter": 1,
  "verdict": "pass|conditional|reject",
  "screenshots": [
    {
      "viewport": "mobile",
      "theme": "light",
      "path": "code_quality/reports/TSK-NNN-visual-iter-1/mobile-light.png",
      "bytes": 12345
    }
  ],
  "checks": {
    "visual_regression": {
      "status": "pass|fail|skip",
      "diff_pixels": 0,
      "baseline_path": "..."
    },
    "axe_a11y": {
      "status": "pass|fail|skip",
      "violations": [
        { "rule": "color-contrast", "severity": "serious", "selector": "..." }
      ]
    },
    "interaction_test": {
      "status": "pass|fail|skip",
      "scenarios": [
        { "name": "click submit", "status": "pass" }
      ]
    }
  },
  "critic_findings": [
    {
      "description": "Button padding inconsistent vs design token",
      "viewport": "desktop",
      "theme": "light",
      "severity": "major|minor|trivial",
      "fix_hint": "Apply var(--spacing-md) instead of hardcoded 12px"
    }
  ],
  "next_action": "done|loop|escalate-human"
}
```

**Campi obbligatori** per ogni report: `tsk_id`, `iter`, `verdict`, `next_action`.

**Campi opzionali** (vuoti = la fase corrispondente è skip):
- `screenshots` — array dei PNG catturati in Fase 3 (vuoto se Fase 3 non eseguita).
- `checks` — popolato dalla **Fase 3-bis** (US-020). I tre sotto-oggetti
  (`visual_regression`, `axe_a11y`, `interaction_test`) hanno le strutture rispettive
  documentate in Fase 3-bis. Ogni check non configurato → `status: skip` (es. zero
  structured checks configurati → tutti e tre `skip`).
- `critic_findings` — array dei difetti prodotti dalla **Fase 4** (vuoto `[]` se
  `verdict: pass` senza difetti). I 5 campi per finding: `description`, `viewport`,
  `theme`, `severity` (`major|minor|trivial`), `fix_hint`.

Mapping `next_action` → flusso `dev-protocol` Fase 4-bis (ADR-012 §H):
- `done` → TSK `status: done`, `visual_status: pass`.
- `loop` → ri-dispatch fe-dev (bounded `max_iterations`).
- `escalate-human` → TSK resta `in_progress`, `visual_status: reject`, gate umano.

**Digest umano**: `code_quality/reports/<TSK-id>-visual-iter-<N>.md` — sintesi
leggibile (verdict, tabella difetti, screenshot referenziati, loop status). Lo slug
`visual` nel nome distingue dagli iter CQRL (`<TSK-id>-iter-<N>.{json,md}`); stesso
side-channel (`code_quality/reports/`, ADR-012 §B) = un solo path da configurare,
gitignore, monitorare.

[^src: design_&_architecture/decisions/ADR-012.md §H]
[^src: design_&_architecture/decisions/ADR-012.md §B]

---

## Schema del diff della Fase 5 (output strutturato)

```json
{
  "verdict": "pass | conditional | reject",
  "defects": [
    {
      "description": "...",
      "viewport": "mobile | desktop | ...",
      "theme": "light | dark",
      "severity": "major | minor | trivial",
      "fix_hint": "..."
    }
  ]
}
```

I **5 campi per ogni defect** sono: `description`, `viewport`, `theme`, `severity`
(enum `major | minor | trivial`), `fix_hint`.
