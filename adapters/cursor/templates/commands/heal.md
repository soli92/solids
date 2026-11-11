# Comando: /heal

> Equivalente Cursor del comando Claude Code `/heal` (`.claude/commands/heal.md`).
> Procedura: vedi [heal-protocol](mdc:.cursor/rules/skills/heal-protocol.mdc).

**Sintassi**: `/heal [<report-path>]`

**Esempi**:
- `/heal` → usa il lint report più recente in `wiki/lint/*-lint-report.md`
- `/heal wiki/lint/2026-05-19-lint-report.md` → report specifico

## Comportamento

Ripara ERROR meccanici flaggati `heal-eligible` da un lint report. Loop evaluator-optimizer vincolato, max 3 iterazioni. Procedura via [heal-protocol](mdc:.cursor/rules/skills/heal-protocol.mdc):

**Prerequisiti**:
- Il report DEVE avere `heal_eligible_count > 0` nel frontmatter. Se assente → termina con "nessun error heal-eligible".
- `wiki-lint` deve aver girato di recente con scope coerente.

**Whitelist heal-eligible** (meccanici, non di giudizio):
- Frontmatter: campo mancante con default noto, valore `status:` illegale.
- Kanban: `depends_on:` punta a TSK inesistente (link dangling).

Per ogni iterazione (max 3):
1. Mostra diff aggregato delle correzioni proposte.
2. Attendi conferma `yes`/`no`.
3. Se `yes`: applica il diff, re-invoca lint sui file impattati.
4. Termina su: `closed | stuck | regression | empty-diff | user-rejected | max-iterations`.

Append `wiki/log.md` con template `heal` di [wiki-log-entry](mdc:.cursor/rules/skills/wiki-log-entry.mdc).

**Regola assoluta**: mai correzione fuori whitelist. WARNING e ERROR non-meccanici restano di competenza umana.

## Limitazioni Cursor

- Mostra le modifiche proposte in chat prima di applicarle (sostituisce il gate interattivo).
- Applica il diff file per file usando l'editor Cursor.
- La re-invocazione lint deve essere eseguita manualmente dopo ogni iterazione.
