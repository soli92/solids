# Comando: /ponytail-review

> Equivalente Cursor del comando Claude Code `/ponytail-review` (`.claude/commands/ponytail-review.md`).
> Analizza un diff con la YAGNI Decision Ladder (Pass 4 advisory, EP-057). Wrapper standalone di code-review-protocol §Passata 5. Non produce verdict. Opt-in ponytail.enabled.

> Procedura: [ponytail-review](mdc:.cursor/rules/skills/ponytail-review.mdc)

> **Gate**: `factory.config.yaml.ponytail.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

**Sintassi**:
```
/ponytail-review TSK-<id>        → Decision Ladder sul diff del TSK (code_path da kanban)
/ponytail-review <branch>        → diff vs default-branch
/ponytail-review <file-path>     → diff del singolo file
/ponytail-review --staged        → diff staged corrente
/ponytail-review <target> --save → salva report in code_quality/reports/ (alimenta /ponytail-gain)
```

## Limitazioni Cursor

- HARD DEP su `code_quality.enabled`.
- Nessun verdict: la tabella e' advisory.
