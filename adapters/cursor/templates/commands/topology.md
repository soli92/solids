# Comando: /topology

> Equivalente Cursor del comando Claude Code `/topology` (`.claude/commands/topology.md`).

**Sintassi**: `/topology [show | set <topology>]`

Topologie valide: `knowledge-only | plan-only | full-stack-agents | hybrid-be-agents | hybrid-fe-agents | custom`

## Comportamento

### `/topology` o `/topology show`

Mostra read-only:
1. Topologia dichiarata (`factory.config.yaml.topology`)
2. Dev-agent presenti (file in `.claude/agents/*-dev.md`)
3. Routing attivo (`factory.config.yaml.routing.{be,fe,db,qa}`)
4. `code_path` + `stack_mode`
5. Coerenza: R1 (routing agent ha file), R2 (file ha routing), R3 (topology coerente)

### `/topology set <topology>`

1. Mostra topologia corrente.
2. Calcola diff proposto: agent file da creare / rimuovere + routing risultante.
3. STOP per conferma umana.
4. Su OK: crea file agente mancanti (da template baseline), sposta in `.claude/agents/.archive/` quelli da rimuovere (MAI delete), edita `factory.config.yaml` (`topology:` + `routing:`).
5. Append `wiki/log.md` con entry topology change.

**Invariante**: TSK esistenti non vengono ri-routati automaticamente. Solo TSK nuovi useranno il nuovo routing.

## Limitazioni Cursor

- Leggere `factory.config.yaml` con `@factory.config.yaml` mention.
- I file agente da creare/archiviare vanno gestiti manualmente con le operazioni file di Cursor.
- Nessun sub-agent per la verifica automatica — esegui i check di coerenza sequenzialmente.
