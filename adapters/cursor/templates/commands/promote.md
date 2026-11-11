# Comando: /promote

> Equivalente Cursor del comando Claude Code `/promote` (`.claude/commands/promote.md`).
> Procedura: vedi [promote-status](mdc:.cursor/rules/skills/promote-status.mdc).

**Sintassi**: `/promote <path-pagina> [<new-status>]`

**Esempi**:
- `/promote wiki/concepts/event-sourcing.md` → next state dal corrente
- `/promote wiki/concepts/event-sourcing.md approved` → target esplicito

## Comportamento

Promuove una pagina wiki lungo la catena di stati via [promote-status](mdc:.cursor/rules/skills/promote-status.mdc):

1. Legge la pagina target (frontmatter `status:`).
2. Calcola transizione legale: `draft → review → approved`, mai salti.
3. Edita **solo** `status:` e `updated:` nel frontmatter YAML. Mai il corpo.
4. Append `wiki/log.md` con riga di promotion.

Se la transizione è illegale → rifiuta e suggerisce il passo intermedio. Niente auto-fix.

## Limitazioni Cursor

- Edita il frontmatter direttamente con il file aperto in Cursor.
- Verifica le precondizioni gate di [promote-status](mdc:.cursor/rules/skills/promote-status.mdc) prima di applicare la transizione.
- Append `wiki/log.md` manualmente se necessario.
