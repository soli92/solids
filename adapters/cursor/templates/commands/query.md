# Comando: /query

> Equivalente Cursor del comando Claude Code `/query` (`.claude/commands/query.md`).
> Procedura: vedi [query-protocol](mdc:.cursor/rules/skills/query-protocol.mdc).

**Sintassi**: `/query <domanda in linguaggio naturale> [--ephemeral]`

## Comportamento

Risponde a una domanda leggendo solo `wiki/`. Procedura via [query-protocol](mdc:.cursor/rules/skills/query-protocol.mdc):

1. Bootstrap: leggi `wiki/concepts/`, `wiki/syntheses/`, `wiki/decisions/`.
2. Cerca: keyword match / semantic match (se `wiki_search.enabled: true`).
3. Risponde con citazioni `[^src: wiki/<path>]`.
4. Default: salva la risposta in `wiki/query/YYYY-MM-DD-<slug>.md`.
5. Con `--ephemeral`: risposta solo in chat, nessuna scrittura su disco; append `wiki/log.md` comunque.

**Regola assoluta**: rispondi SOLO da `wiki/`. Se l'informazione non c'è, dichiaralo e suggerisci quale raw coprire con un ingest. Mai inventare citazioni.

Se la risposta è candidata a essere ri-asked frequentemente → proponi di promuoverla a `wiki/syntheses/<question-slug>.md`.

## Limitazioni Cursor

- Usa `@wiki/` mention per includere le pagine rilevanti nel contesto.
- Se `wiki_search.enabled: true`, usa [wiki-search-protocol](mdc:.cursor/rules/skills/wiki-search-protocol.mdc) prima della scansione lineare.
- La persistenza in `wiki/query/` va effettuata manualmente se Cursor non ha accesso alla scrittura automatica.
