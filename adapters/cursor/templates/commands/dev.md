# Comando: /dev

> Equivalente Cursor del comando Claude Code `/dev` (`.claude/commands/dev.md`).
> Procedura: vedi [dev-protocol](mdc:.cursor/rules/skills/dev-protocol.mdc) + [dev-handoff](mdc:.cursor/rules/skills/dev-handoff.mdc).

**Sintassi**: `/dev <TSK-id> [<layer>]`

- Primo argomento: **TSK-id** (es. `TSK-042`), obbligatorio.
- Secondo argomento (opzionale): **layer** (`be|fe|db|qa|docs`). Se omesso, dedotto dal campo `layer:` del frontmatter TSK.

## Comportamento

1. **Validazione**: trova `management/kanban/**/TSK-<id>.md`. Se 0 o >1 match → STOP. Leggi frontmatter (`layer:`, `consumer:`). Se arg 2 diverge da `layer:`, chiedi conferma.
2. **Selezione agente**: `be` → `be-dev`, `fe` → `fe-dev`, `db` → `db-dev`, `qa` → `qa-dev`, `docs` → questo agente stesso. Se l'agente non esiste nella topologia → STOP.
3. **Override consumer one-shot**: se `consumer: human` e l'utente invoca `/dev` esplicitamente → override per questa sola esecuzione. Segnala in chat.
4. **Esecuzione**: applica [dev-protocol](mdc:.cursor/rules/skills/dev-protocol.mdc) (Fase 0 gate → Fase 5 handoff).
5. **Handoff**: edit TSK `status: todo` → `in-progress` → `done` + append [dev-handoff](mdc:.cursor/rules/skills/dev-handoff.mdc) su `wiki/log.md`.

## Vincoli

- Mai `/dev` su TSK senza `layer:` esplicito.
- Mai forzare su TSK con dipendenze aperte.
- Override consumer è **one-shot**: non cambia il file TSK né `factory.config.yaml`.

## Limitazioni Cursor

- Eseguire le fasi di [dev-protocol](mdc:.cursor/rules/skills/dev-protocol.mdc) sequenzialmente nella sessione Chat.
- Non esiste delega automatica a sub-agent: la selezione agente in Cursor è convenzionale (stessa sessione, ruolo dichiarato).
