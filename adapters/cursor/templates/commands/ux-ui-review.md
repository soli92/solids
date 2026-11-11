# Comando: /ux-ui-review

> Equivalente Cursor del comando Claude Code `/ux-ui-review` (`.claude/commands/ux-ui-review.md`).
> EP-008 US-030, opt-in `ux_ui.agents.reviewer: true`.

**Sintassi**:
```
/ux-ui-review <target> [--rubric=strict|loose] [--skip-a11y] [--ephemeral]
```

> **Gate**: `factory.config.yaml.ux_ui.agents.reviewer: true`. Se `false` → si tenta fallback skill.

**Il reviewer non progetta**: per wireframe/spec/flussi/copy usa `/ux-ui-design`. Separazione enforced (ADR-019).

## `<target>` — 4 forme

| Forma | Esempio | Significato |
|---|---|---|
| **URL** | `/ux-ui-review https://app.example.com/checkout` | route live |
| **TSK-id** | `/ux-ui-review TSK-051` | ricava target dal frontmatter TSK |
| **path mockup** | `/ux-ui-review designs/checkout-v2.png` | mockup statico |
| **path componente** | `/ux-ui-review src/components/Cart.tsx` | file componente |

## Flag

- `--rubric=strict|loose` — default `strict`. In `strict`: finding senza `rubric_ref` e' un blocco.
- `--skip-a11y` — non invoca `run_a11y_scan`.
- `--ephemeral` — nessuna scrittura in `code_quality/reports/`.

## Comportamento

1. Verifica `ux_ui.agents.reviewer: true`.
2. Risolvi target. Con TSK-id: glob `management/kanban/**/TSK-<id>.md`.
3. Invocazione con fallback: agente `ux-ui-reviewer` → skill `ux-ui-review-protocol` via `fe-dev`/`qa-dev` → fail-loud.
4. Report con schema standard: finding ancorati a `rubric_ref`, domande aperte, richiamo a11y.
5. Verdict `pass | conditional | reject`. Su TSK-id: aggiorna solo `ux_ui_status:`.

## Storage

- Con TSK-id: `code_quality/reports/<TSK-id>-uxui-review-iter-<N>.{json,md}`
- Standalone: `code_quality/reports/_adhoc/uxui-review-<YYYY-MM-DD-HH-MM>-<slug>.{json,md}`

## Vincoli

- Il reviewer non progetta mai (ADR-019): declina qualsiasi richiesta di alternative di design.
- Non modifica il corpo dei TSK: solo `ux_ui_status:`.

## Limitazioni Cursor

- Cattura screenshot via terminal Cursor per URL (o usa strumento screenshot manuale).
- Eseguire le fasi della review sequenzialmente nella sessione Chat.
