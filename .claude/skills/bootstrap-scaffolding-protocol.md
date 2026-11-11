---
name: bootstrap-scaffolding-protocol
description: Skill di scaffolding file/directory L1-L5 + adapter .claude/. Genera root files (PATTERN.md, CLAUDE.md, factory.config.yaml), directory L1-L5 + side-channel, copia condizionale agenti/skill/commands in base a topology/CQRL/multi-repo. Invocata da factory-bootstrap dopo input + multirepo.
---
# Skill — Bootstrap scaffolding

Riferimenti: PATTERN §1 (modello a layer), §12 (adapter), §13 (topology + code_paths),
§16 (sync), §17 (publisher), §18 (scheduler), §19 (CQRL).

## Input atteso

Dict completo da `bootstrap-input-protocol` + eventualmente `bootstrap-multirepo-protocol`.
Include: `target_path` (o `factory_dest_path`), `topology`, `code_paths` (multi-repo) o
`code_path` (legacy), `vcs` (legacy) o per-entry, `routing`, `stack_mode`, `stack`,
`kanban_publish`, `scheduler`, `code_quality`, `wiki_feed_source`, `standards`.

## Sorgente di copia

Tutti i template/agenti/skill vengono copiati da:
```
/Users/simone.olivieri/Documents/Personal/Repos/soli-multi-agents-factory/
```

(Adatta il path se la meta-framework è stata spostata.)

## Fase 1 — Root files

Crea nel `factory_dest_path` (single-repo: stesso di target_path; multi-repo: derivato):

1. **`PATTERN.md`** — copia integrale dalla fonte di verità (v2.12, agent-agnostic).
2. **`CLAUDE.md`** — pointer all'adapter `.claude/` (template breve).
3. **`README.md`** — descrizione progetto (template breve, in lingua scelta).
4. **`factory.config.yaml`** — generato dai valori raccolti. Schema:
   - `pattern_version: "2.12"`
   - `topology: <scelto>`
   - **Multi-repo**: blocco `code_paths: [<entry>, ...]` valorizzato dalla multirepo-protocol.
   - **Single-repo legacy**: blocco `code_path:` (singolare) + `vcs:` top-level.
   - `stack_mode`, `routing`, `stack` (se guided).
   - `kanban_publish:` se `provider != none` (vedi schema PATTERN §17.7).
   - `scheduler:` con defaults (vedi schema §18.5).
   - `code_quality:` se `enabled: true` (vedi schema §19.7).

## Fase 2 — Directory L1-L5 + side-channel

Crea sempre (cwd = `factory_dest_path`):
- `raw/` (+ `raw/tech_stack.md` se `standards` non vuoto)
- `wiki/{sources,concepts,entities,syntheses,runbooks,incidents,query,lint}/`
- `wiki/{index.md,log.md,gaps.md}` (vuoti, head only)
- `management/kanban/`, `management/{roadmap.md,questions.md}`
- `design_&_architecture/{decisions,api_specs,db_schemas}/`
- `memory/{episodic,semantic,procedural}/`

**L5** (`<code_path>`): crea la cartella SOLO se:
- Single-repo: `code_path` non vuoto e relativo (dentro factory).
- Multi-repo: per ciascuna entry con `vcs.mode: monorepo` o `submodule`, crea la
  cartella relativa (es. `./apps/api/`, `./code/db/`). Per `sibling`/`external`,
  NON creare nulla (path esterno).

**Side-channel CQRL** (v2.12): solo se `code_quality.enabled: true`:
- `code_quality/rules/{canonical,emergent,team-specific}/`
- `code_quality/reports/{,_digests}/`
- `code_quality/rules/README.md` con istruzioni base (tassonomia ID, struttura `.md`
  + frontmatter, riferimento a PATTERN §19.5)

## Fase 3 — Adapter `.claude/`

### 3.a — Agenti core (sempre)

Copia in `.claude/agents/`:
`orchestrator`, `sync-docs`, `wiki-keeper`, `wiki-keeper-worker`, `product-manager`,
`lead-architect`, `tpm`, `wiki-query`, `wiki-lint`.

### 3.b — Sync adapters condizionali

- `figma-sync` (v2.9): se `wiki_feed_source == "figma"` OR opt-in esplicito.
- `repo-sync` (v2.12): se `wiki_feed_source == "existing-repo"` OR opt-in esplicito.

### 3.c — Dev-agents condizionali (topology)

| Topologia | Dev-agent da copiare |
|---|---|
| `full-stack-agents` | `be-dev`, `fe-dev`, `db-dev`, `qa-dev` |
| `hybrid-be-agents` | `be-dev`, `db-dev` |
| `hybrid-fe-agents` | `fe-dev` |
| `custom` | quelli scelti dall'utente |
| `knowledge-only` / `plan-only` | nessuno |

### 3.d — Publisher condizionale (kanban_publish.provider)

- `github` → `github-publisher.md`
- `gitlab|jira|linear` → placeholder (segnala: contratto §17 pronto, agent da scaffoldare)
- `custom` → nessuna copia automatica
- `none` → skip

### 3.e — Code Reviewer condizionale (CQRL v2.12)

`code-reviewer.md` solo se `code_quality.enabled: true`.

### 3.f — Skills condizionali

Sempre: skill canoniche/procedurali base (`ingest-protocol`, `lint-checks`,
`heal-protocol`, `propagate-resolution`, `parallel-scheduling` v2.11, template
`scrivi-*`, `apri-question`, `citation-rules`, `wiki-log-entry`,
`wiki-gap-protocol`, `query-protocol`, `state-scan`, `promote-status`).

Condizionali:
- `dev-protocol`, `dev-handoff` — se topology include dev-agent.
- `tech-scout` — se topology include dev-agent OR `stack_mode: auto`.
- `vcs-handoff` (v2.8) — se topology include dev-agent E almeno un `vcs.mode != none`.
- `figma-extraction-protocol` (v2.9) — se `figma-sync` agent presente.
- `repo-extraction-protocol` (v2.12) — se `repo-sync` agent presente.
- `stack-detector` (v2.12) — se almeno uno fra `code-reviewer` e `repo-sync` presenti.
- `code-review-protocol` + `feedback-router` (v2.12) — se `code-reviewer` presente.
- `publisher-protocol` + `<provider>-mapping` (v2.10) — se `kanban_publish.provider != none`.

### 3.g — Commands condizionali

Sempre: `/run`, `/sync-docs`, `/query`, `/lint`, `/promote`, `/heal`.

Condizionali:
- `/dev`, `/topology` — se topology include almeno un dev-agent.
- `/figma-sync` — se `figma-sync` agent presente.
- `/repo-sync` — se `repo-sync` agent presente.
- `/kanban-publish` — se `kanban_publish.provider != none`.
- `/review` — se `code-reviewer` agent presente.

### 3.h — Token Ledger scaffold (opt-in)

**Gate**: `analytics.token_ledger.enabled: true` nel blocco `factory.config.yaml.analytics.token_ledger:`.
SE `enabled: false` (default): EARLY RETURN — nessun artefatto Token Ledger creato.
Factory v2.20 derivate restano identiche (R.P3 backward compat totale).

**Cross-validation**: se `token_ledger.enabled: true` E `analytics.measurement.enabled: false`
→ emit WARNING (non bloccare lo scaffolding):
```
WARNING: analytics.token_ledger.enabled: true richiede analytics.measurement.enabled: true
come prerequisito. Token Ledger scaffoldato ma le sessioni non saranno tracciate nell'event store.
```

**Artefatti da scaffoldare** (in ordine, solo se `enabled: true`):

1. `tools/analytics/show-session-tokens.py` — copia da meta-framework.
2. `.claude/settings.json` — merge non distruttivo:
   - Leggi file esistente (o `{}` se assente).
   - Aggiungi chiave `hooks.Stop` SOLO se assente; se esiste → skip silente con nota.
   - Riscrivi il file. Mai sovrascrivere chiavi esistenti non Token Ledger.
3. `analytics/pricing.yaml` — copia da meta-framework se non esiste; skip silente se esiste.
4. `.claude/skills/token-ledger.md` — copia da meta-framework.
5. `.claude/commands/token-ledger.md` — copia da meta-framework.

## Fase 4 — Niente file vietati (PATTERN §8)

NEVER creare:
- `project_manifest.json` (stato auto-generato vietato)
- `wiki/confidences/` (defunto v2.1)
- `reviewer/` directory (defunto)
- `sprint.md` pre-popolato (è view generata, mai a mano)
- `code_quality/` se `code_quality.enabled: false`
- `.claude/agents/code-reviewer.md` se `code_quality.enabled: false`
- File per provider non scelti

## Fase 5 — Coerenza finale

Verifica prima di restituire:
- `topology` ↔ presenza dev-agent: `routing.<X>: agent` ⇔ `<X>-dev.md` presente.
- `routing.<X>: agent` ↔ almeno un'entry `code_paths` con `<X>` in `layers` (multi-repo) o `code_path` non vuoto (single-repo).
- `wiki_feed_source: existing-repo` ⇔ `repo-sync` agent + `/repo-sync` command + `repo-extraction-protocol` skill presenti.
- `code_quality.enabled: true` ⇔ `code-reviewer` agent + 4 skill CQRL + `/review` command presenti.
- `kanban_publish.provider ≠ none` ⇔ `<provider>-publisher` agent + `publisher-protocol` skill + `/kanban-publish` command presenti.

## Return value

```yaml
files_created: <N>
dirs_created: <M>
factory_dest_path: <abs-path>
artifact_inventory:
  agents: [...]
  skills: [...]
  commands: [...]
  side_channel: [code_quality/?, memory/]
warnings: [...]   # placeholder per gitlab/jira/linear, ecc.
```

## Vincoli inviolabili

- **Mai overwrite** di file esistenti nel target (in monorepo R.B2 questo è già garantito
  dal gate pre-scaffolding).
- **Mai modificare il repo sorgente** (multi-repo sibling/submodule, R.B1).
- **Agent-agnostic preservato**: `PATTERN.md` copiato senza modifiche al contenuto;
  `CLAUDE.md` può essere adapter-specifico (Claude Code).
- **Skill-driven**: i template (frontmatter, struttura corpo, formati output) vivono
  nelle skill, mai inlineati nei file agente.
