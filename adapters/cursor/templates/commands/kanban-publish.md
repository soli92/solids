# Comando: /kanban-publish

> Equivalente Cursor del comando Claude Code `/kanban-publish` (`.claude/commands/kanban-publish.md`).
> Procedura: vedi [publisher-protocol](mdc:.cursor/rules/skills/publisher-protocol.mdc) + [github-mapping](mdc:.cursor/rules/skills/github-mapping.mdc).

**Sintassi**:
```
/kanban-publish              → equivalente a `/kanban-publish run`
/kanban-publish show         → mostra config kanban_publish corrente + ultimo run
/kanban-publish set <provider> → cambia provider
/kanban-publish run [filter] → esegue Publish (chiede conferma piano)
/kanban-publish dry-run      → Fasi 1-3 senza chiamate al provider
```

## Comportamento per sub-comando

### `show`

Legge `factory.config.yaml.kanban_publish` e mostra config (Provider, Target, Auth env, Mode, Batch limit, Mapping, Filter) + ultimo run da `wiki/log.md`. Read-only.

### `set <provider>`

Modifica `factory.config.yaml.kanban_publish.provider`. Chiede campi obbligatori mancanti in modalità conversazionale. Mai scrive token, solo nome variabile env. Se sub-agent `<provider>-publisher` non esiste → ERROR.

### `run [filter]`

Esegue [publisher-protocol](mdc:.cursor/rules/skills/publisher-protocol.mdc) 5 fasi:
1. Bootstrap (verifica auth, config, CLI)
2. Discovery (Glob EP/US/TSK/sprint da `management/kanban/`)
3. Plan & Gate — STOP per conferma. Se totale > `batch_limit` → secondo gate
4. Publish (CREATE/UPDATE sul provider, aggiorna `external_id:`)
5. Log (append `wiki/log.md`)

Filter opzionale: `--only-consumer=agent`, `--only-status=todo`, `--epic=EP-001`, `--task=TSK-014`.

### `dry-run`

Identico a `run` ma ABORT pulito alla Fase 3 senza chiamate al provider.

## Vincoli

- Mai CREATE/UPDATE senza conferma esplicita (PATTERN §7 r.15).
- Mai DELETE/CLOSE automatici di artefatti esterni.
- Mai pubblicare > `batch_limit` senza secondo gate.
- Token solo da variabile d'ambiente.

## Limitazioni Cursor

- Il provider GitHub richiede `gh` CLI installato e `gh auth login` eseguito.
- Usare terminal Cursor per le chiamate `gh` se necessario.
