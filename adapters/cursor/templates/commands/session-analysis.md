# Comando: /session-analysis

> Equivalente Cursor del comando Claude Code `/session-analysis` (`.claude/commands/session-analysis.md`).
> session-analysis

> Procedura: [session-analysis-protocol](mdc:.cursor/rules/skills/session-analysis-protocol.mdc)

> **Gate**: `factory.config.yaml.session_analysis.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

**Sintassi**:
```
/session-analysis [--current | --last N | <session-id>]
/session-analysis --last 1
/session-analysis --last 1
/session-analysis --last 3 --depth=full --save
/session-analysis --last 1 --since 7d --json
/session-analysis 20260908-a1b2c3d4 --depth=full --save
```

## Limitazioni Cursor

- **Solo out-of-band** (R-SAA-8).
- Il percorso dei transcript e' specifico del runtime e va configurato.
