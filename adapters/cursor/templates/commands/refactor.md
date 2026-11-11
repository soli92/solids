# Comando: /refactor

> Equivalente Cursor del comando Claude Code `/refactor` (`.claude/commands/refactor.md`).
> Invoca fleet-doctor per rifattorizzare in divulgazione progressiva una unita' di contesto agentica (skill/agente/command). Gated su refactor_agent_skills.enabled. Supporta --external per factory…

> Procedura: [refactor-agent-skills](mdc:.cursor/rules/skills/refactor-agent-skills.mdc)

> **Gate**: `factory.config.yaml.refactor_agent_skills.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

**Sintassi**:
```
/refactor <target>
/refactor <target> --dry-run
/refactor <target> --external <path>
/refactor <target> --external <path> --adapter=<claude|cursor>
/refactor <target> --external <path> --adapter=cursor --dry-run
/refactor .claude/agents/wiki-keeper.md
```

## Limitazioni Cursor

- Nessun fan-out nativo di sub-agenti (`profile: sequential`): dove la fonte dispatcha in parallelo, esegui in sequenza e aggrega a mano.
