# /onboarding — Cursor adapter

Sintassi:
```
/onboarding
```

Equivalente Claude Code: `.claude/commands/onboarding.md`.

## Comportamento

Invoca la skill `onboarding` (`.claude/skills/onboarding.md`).

Esegui i 4 passi della skill nell'ordine:
1. Leggi `factory.config.yaml` → Sezione 1 Factory corrente
2. Leggi `management/kanban/sprint.md` → Sezione 2 Task onboarding-friendly
3. Leggi `PATTERN.md §7` live → Sezione 3 5 invarianti critiche
4. Appendi Sezione 4 statica (CAPABILITIES.md, CLAUDE.md; QUICKSTART.md e `wiki/getting-started/` solo se esistono)

Output esclusivamente in-chat. Nessun file viene scritto.

## Limitazioni Cursor

Stesso comportamento del comando Claude Code (read-only in-chat). Se la skill
non è presente nello scaffold Cursor, leggi direttamente
`.claude/skills/onboarding.md` dal meta-framework o dalla factory derivata.
