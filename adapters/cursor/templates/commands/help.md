# /help — Cursor adapter

Sintassi:
```
/help [<domanda in linguaggio naturale>]
```

Equivalente Claude Code: `.claude/commands/help.md`.

## Comportamento

### Con argomento

Esegui la skill `help-router-protocol` con la query utente, usando
`CAPABILITIES.md` come fonte di verità per il matching.

### Senza argomento

Elenca le aree `##` di `CAPABILITIES.md` (escludi le note introduttive) e invita
l'utente a porre una domanda concreta.

## Limitazioni Cursor

Se la skill non è nello scaffold `.cursor/`, usa
`.claude/skills/help-router-protocol.md` e `CAPABILITIES.md` dalla factory root.
