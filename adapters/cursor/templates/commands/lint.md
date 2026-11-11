# Comando: /lint

> Equivalente Cursor del comando Claude Code `/lint` (`.claude/commands/lint.md`).
> Procedura: vedi [lint-checks](mdc:.cursor/rules/skills/lint-checks.mdc).

**Sintassi**: `/lint [<namespace>] [citation-audit]`

## Comportamento

Health check di `wiki/` e `management/kanban/`. Solo report, mai auto-fix. Procedura via [lint-checks](mdc:.cursor/rules/skills/lint-checks.mdc):

- Senza argomento → lint completo (tutte le check 4a–4ae).
- `<namespace>` (es. `concepts`, `kanban`) → lint scoped al namespace.
- `citation-audit` → audit completo delle citazioni (verifica che ogni `[^src: ...]` punti a file e sezione esistenti).

Output: `wiki/lint/YYYY-MM-DD-lint-report.md` (o `-citation-audit.md`).
Formato report: frontmatter con `heal_eligible_count`, blocchi ERROR/WARNING per check.

**Regola assoluta**: il lint NON modifica mai gli artefatti. Solo report + severità ERROR/WARNING + fix suggeriti. Append `wiki/log.md` con riga di riepilogo.

## Limitazioni Cursor

- Usa `@management/kanban/` e `@wiki/` mention per scansione con il contesto.
- Per check che richiedono tool esterni (semantic check L3 embedding), indicare `[SKIP: tool non disponibile]`.
- Il report va scritto manualmente se Cursor non ha scrittura automatica su `wiki/lint/`.
