# Comando: /estimate

> Equivalente Cursor del comando Claude Code `/estimate` (`.claude/commands/estimate.md`).
> Invoca estimation-analyst su uno scope (project/sprint/capacity/sales) per stima costi e tempi enterprise (EP-010 US-043). Stima il futuro (intervallo + confidenza + assunzioni + contingency), NON…

> Procedura: [project-estimation](mdc:.cursor/rules/skills/project-estimation.mdc)

> **Gate**: `factory.config.yaml.analytics.estimation.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

**Sintassi**:
```
/estimate <scope> [--method=rcf|pert|monte-carlo|hybrid|auto] [--contingency-pct=N] [--audience=executive|project] [--review-accuracy=<estimate_id>] [--aggregate-accuracy] [--output=<path>] [--ephemeral] [--similarity=high|medium|low] [--critical-path=<DAG-source>]
```

## Limitazioni Cursor

- I tool deterministici sotto `tools/` sono invocati da terminale e si comportano in modo identico: la differenza sta solo nell'agente che li chiama.
- `--from-kanban` e `--review-accuracy` leggono gli stessi file.
