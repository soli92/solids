# Comando: /ux-ui-design

> Equivalente Cursor del comando Claude Code `/ux-ui-design` (`.claude/commands/ux-ui-design.md`).
> EP-008 US-030, opt-in `ux_ui.agents.designer: true`.

**Sintassi**:
```
/ux-ui-design <brief> [--type=wireframe|component_spec|user_flow|copy] [--tsk=<id>] [--ephemeral]
```

> **Gate**: `factory.config.yaml.ux_ui.agents.designer: true`. Se `false` → si tenta fallback skill.

**Il designer non valuta il proprio output**: sempre passare al reviewer post-generazione. Separazione enforced (ADR-019).

## `<brief>` — 2 forme

| Forma | Esempio | Significato |
|---|---|---|
| **stringa descrittiva** | `/ux-ui-design "flusso onboarding 3 step mobile"` | brief inline |
| **path file brief.md** | `/ux-ui-design briefs/onboarding.md` | brief strutturato |

## Flag

- `--type=wireframe|component_spec|user_flow|copy` — default `wireframe`.
- `--tsk=<id>` — collega deliverable a un TSK FE. Il designer **suggerisce** `ui_design_spec: <path>` al TPM (non scrive direttamente il frontmatter TSK).
- `--ephemeral` — nessuna scrittura in `code_quality/reports/`.

## Comportamento

1. Verifica `ux_ui.agents.designer: true`.
2. Risolvi brief. Con `--tsk=<id>`: glob `management/kanban/**/TSK-<id>.md`.
3. Invocazione con fallback: agente `ui-designer` → skill `ux-ui-design-protocol` via `fe-dev`/`qa-dev` → fail-loud.
4. Produce deliverable con schema standard: deliverable + rationale + assunzioni esplicite + note accessibilita' by design.
5. Post-condizione: **suggerisce** `/ux-ui-review` — mai auto-chain (gate umano, ADR-019).

## Storage

- Con `--tsk=<id>`: `code_quality/reports/<TSK-id>-uxui-design.{json,md}` (single-pass, non `iter-N`)
- Standalone: `code_quality/reports/_adhoc/uxui-design-<YYYY-MM-DD-HH-MM>-<slug>.{json,md}`

## Vincoli

- Mai auto-valutazione: il designer non revisiona il proprio deliverable (ADR-019).
- Non scrive `ui_design_spec:` nel frontmatter TSK: lo **suggerisce** al TPM.

## Limitazioni Cursor

- Eseguire le fasi di design sequenzialmente nella sessione Chat.
- Il suggermento post-generazione di invocare `/ux-ui-review` va eseguito manualmente.
