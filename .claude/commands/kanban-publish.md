---
description: Pubblica il kanban (EP/US/TSK/sprint) su un tool esterno di project tracking come mirror push-only. Provider-agnostic, configurato in factory.config.yaml.kanban_publish (PATTERN §17, v2.10).
---

Sintassi:

```
/kanban-publish              → equivalente a `/kanban-publish run`
/kanban-publish show         → mostra config kanban_publish corrente + ultimo run
/kanban-publish set <provider> → cambia provider (richiede target/auth_env successivamente)
/kanban-publish run [filter] → esegue Publish (publisher-protocol §3 chiede conferma)
/kanban-publish dry-run      → esegue Fasi 1-3 (no chiamate al provider, solo piano)
```

## Comportamento per sub-comando

### `show`

Legge `factory.config.yaml.kanban_publish` e mostra in chat:

```
PUBLISH CONFIG
==============
Provider:    <name>           (o "none" se disabilitato)
Target:      <target>
Auth env:    <var-name>       (settata: yes/no)
Mode:        push-only
Batch limit: <n>
Mapping:     epic→<...>, story→<...>, task→<...>, sprint→<...>
Filter:      consumer=<...>, status=<...>

ULTIMO RUN (da wiki/log.md, marker `publish <provider>`):
  Data: <data>
  Operazioni: created=<N>, updated=<M>, skipped=<K>
  Link: <url-provider>
```

Read-only: nessuna modifica.

### `set <provider>`

Esempi: `/kanban-publish set github`, `/kanban-publish set none`.

Modifica `factory.config.yaml.kanban_publish.provider`. Se il nuovo provider
richiede campi obbligatori non valorizzati (target, auth_env, mapping), chiede
in chat in modalità conversazionale e li scrive nel file. **Mai** scrive il
token: solo il **nome** della variabile d'ambiente.

Coerenza: se il sub-agent `<provider>-publisher` non esiste in `.claude/agents/`,
emit ERROR «Provider <provider> non scaffoldato in questo adapter. Esegui
factory-bootstrap con `kanban_publish.provider=<provider>` oppure scaffolda
manualmente seguendo PATTERN §17 §Contratto».

### `run [filter]`

Invoca il sub-agent `<provider>-publisher` letto da config. L'agente esegue
`publisher-protocol` 5 fasi:

1. **Bootstrap** — verifica auth, config, prerequisiti CLI.
2. **Discovery** — `Glob` di EP/US/TSK/sprint da `management/kanban/`.
3. **Plan & Gate** — mostra il piano (CREATE/UPDATE/SKIP per tipo) e
   **attende conferma esplicita** (PATTERN §7 r.15). Se totale > `batch_limit`,
   secondo gate obbligatorio.
4. **Publish** — esegue CREATE/UPDATE sul provider, aggiorna `external_id:`
   nei frontmatter locali.
5. **Log** — append marker `publish <provider> ...` a `wiki/log.md`.

Filter opzionale (override una-tantum del `kanban_publish.filter`):

```
/kanban-publish run --only-consumer=agent --only-status=todo
/kanban-publish run --epic=EP-001         (solo EP-001 + i suoi US/TSK)
/kanban-publish run --task=TSK-014        (solo questo TSK)
```

### `dry-run`

Identico a `run`, ma alla Fase 3 (Plan) NON chiede conferma: stampa il piano e
ABORT pulito senza chiamate al provider. Utile per verificare cosa farebbe il
publisher prima di committarsi.

## Prerequisiti

- `factory.config.yaml.kanban_publish.provider ≠ none`.
- Variabile d'ambiente `<auth_env>` settata.
- Sub-agent `<provider>-publisher.md` presente in `.claude/agents/`.
- Provider-specific CLI installato e autenticato:
  - GitHub: `gh` (https://cli.github.com/) + `gh auth login` fatto.
  - GitLab: `glab` (placeholder v2.10, non implementato).
  - Jira/Linear: out-of-scope v2.10.

## Idempotenza

Il publisher è **idempotente per artefatto**: ri-eseguire `run` non duplica.
Ogni EP/US/TSK con `external_id: <provider>:<id>` viene UPDATE; senza
`external_id` viene CREATE. La fonte di verità è il file locale.

## Vincoli (PATTERN §7 r.15)

- Mai CREATE/UPDATE su provider senza conferma esplicita.
- Mai DELETE/CLOSE automatici di artefatti esterni.
- Mai pubblicare > `batch_limit` (default 10) senza secondo gate.
- Token solo da variabile d'ambiente; mai committato.

Vedi `publisher-protocol` per la procedura completa, PATTERN §17 per il
contratto «Publisher adapters».
