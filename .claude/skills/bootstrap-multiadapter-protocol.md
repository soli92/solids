---
name: bootstrap-multiadapter-protocol
description: Skill di scaffolding multi-adapter per factory-bootstrap. Legge il registry adapters/{name}/manifest.yaml, risolve template condizionali, scaffolda negli {adapter_folder} della factory. Supporta scaffolding parallelo di piu' adapter.
---
# Skill — Bootstrap multi-adapter scaffolding

Riferimenti: PATTERN §12 (Adapter contract), §12.0 (registry), §12.1 (manifest
format), §12.2 (invarianti R.A1-R.A6 multi-adapter coexistence), §12.3
(`factory.config.yaml.adapters[]`), §12.4 (principio taglio adapter).

## Input atteso

Dict completo da `bootstrap-input-protocol` + `bootstrap-multirepo-protocol` (se
applicabile), con in più:

```yaml
adapters_selected: [<name1>, <name2>, ...]    # lista adapter da scaffoldare (default: ["claude"])
adapter_registry_path: <abs-path-to-adapters/>   # path al registry (es. <meta-framework>/adapters/)
```

## Output schema (return value)

```yaml
adapters_scaffolded:
  - name: claude
    folder: .claude
    maturity: full
    files_written: <N>
  - name: cursor
    folder: .cursor
    maturity: full
    files_written: <M>
  # ...
warnings: [...]   # placeholder per manifest-only adapters
config_adapters_block: [<entry-yaml>, ...]   # da scrivere in factory.config.yaml.adapters
```

## Fase 0 — Discovery del registry

1. Read `<adapter_registry_path>/README.md` per lista adapter disponibili.
2. Read `<adapter_registry_path>/capability-matrix.yaml` (capability × runtime).
3. Read `<adapter_registry_path>/<name>/manifest.yaml` per ciascun `<name>` in
   `adapters_selected`.
4. Verifica `manifest.contract_version >= 2.13` per ciascuno (compat check).
5. Calcola `maturity` aggregata: se uno solo è `manifest-only`, lo segnala come
   warning ma procede.
6. **Fase 0.5 — Capability / orchestration gate (Sprint 1)**:
   - Richiedi `orchestration.profile` ∈ `{native, sequential, external, viewer}`.
   - Se `maturity: full` e `contract_version` è major/minor indietro rispetto a
     `factory.config.yaml.pattern_version` → **ERROR** (usa `core` o catch-up).
   - Se `orchestration.profile: viewer` e l'utente ha chiesto topology con
     `routing.*.agent` / develop → **WARNING**: viewer non è writer L2–L5;
     consiglia Claude/Cursor/Aider.
   - Se `orchestration.profile: external` → **WARNING**: L2–L5 bloccati finché
     non esiste un runner FS sync (documentato nel manifest).
   - Se `maturity: core` → **WARNING**: EP opt-in v2.14+ fuori scaffold guarantee;
     elenca capability dalla matrix che richiedono fan-out/hooks e non sono
     coperte.
   - Opzionale: esegui `python3 tools/adapters/check-adapter-lag.py` dalla root
     del meta-framework e include stdout nel report Fase 6.

## Fase 1 — Selezione adapter (se non già in input)

Se `adapters_selected` è vuoto o assente, chiedi all'utente:

```
SELEZIONA ADAPTER DA SCAFFOLDARE (multi-select):

Disponibili (registry adapters/):
  [x] claude       (full, native)             — .claude/
  [ ] cursor       (full, sequential)         — .cursor/
  [ ] aider        (core-LTS, sequential)     — .aider/
  [ ] openai       (partial, external)        — .openai/
  [ ] gemini       (manifest-only, viewer)    — .gemini/
  [ ] chatgpt      (manifest-only, viewer)    — .chatgpt/

Default raccomandato: [claude] (single-adapter).
Multi-adapter use case: scegli 2+ se l'utente userà più runtime (es. team con Claude
Code per dev + Cursor per refactoring + Aider per quick edits).
```

**Vincoli R.A1-R.A6**:
- Almeno 1 adapter selezionato (altrimenti ABORT — la factory richiede ≥ 1 adapter
  per essere operativa).
- Mai più di 1 adapter con `vcs.mode: monorepo` (ma è vincolo di `code_paths`, non di
  adapter — qui sempre OK).

## Fase 2 — Risoluzione template condizionali (per ciascun adapter)

Per ciascun `<name>` in `adapters_selected`, legge `manifest.yaml.templates` e applica
le `condition:` di ciascun template:

Condizioni supportate:
- `routing.<layer> == agent` — vero se topology include dev-agent per quel layer.
- `has_dev_agents` — vero se almeno un layer ha `routing == agent`.
- `has_figma_sync` — vero se `wiki_feed_source == figma` o opt-in esplicito.
- `has_repo_sync` — vero se `wiki_feed_source == existing-repo` o opt-in.
- `has_code_reviewer` — vero se `code_quality.enabled == true`.
- `kanban_publish.provider == <X>` — vero se config match.
- `kanban_publish.provider != none` — true if any provider.
- `code_quality.enabled == true` — true if CQRL on.
- `scheduler.enabled == true` — usually true (default).
- `stack_mode == auto` — true if tech-scout mode.
- `any_vcs_mode_not_none` — true se almeno una entry `code_paths[i].vcs.mode != none`.

Risultato: `active_templates` = lista filtrata di `(name, path, source_path)` per ciascun adapter.

## Fase 3 — Scaffolding template (per ciascun adapter)

Per ciascun adapter, per ciascun `(name, path)` in `active_templates`:

### Caso A — adapter `.claude/` (reference completo)

I file vivono già nel meta-framework repo. Scaffolding = **copia** da
`<meta-framework>/.claude/<file>` a `<factory_dest>/.claude/<file>`.

### Caso B — adapter con templates inline (cursor, aider, openai)

Il manifest ha template **starter** in `adapters/<name>/templates/<path>`. Se il file
template esiste:
- Copia + sostituzione placeholder `{{...}}` con valori della factory (`{{topology}}`,
  `{{code_paths}}`, ecc.).

Se il template NON esiste in `adapters/<name>/templates/` (caso comune — solo i pochi
template "esempio" sono inline):
- **Traduzione automatica** dal `.claude/<corrispondente>.md` del meta-framework
  applicando le `manifest.yaml.mappings`:
  - Frontmatter: rimuovi/converti chiavi (es. Claude `tools:` → Cursor `globs:`).
  - Body: sostituisci tool name (Read/Write/Bash) con `runtime_construct` da mappings.
  - Skill references: aggiorna i `wikilink` da `[[skill-name]]` a `[<skill>](mdc:.cursor/rules/skills/<skill>.mdc)` per Cursor, ecc.
- Scrivi a `<factory_dest>/<path>`.

### Caso C — adapter `manifest-only` (gemini, chatgpt)

Mostra in chat le `scaffolding_instructions` del manifest. **Non scaffolda
automaticamente file** — l'utente segue le istruzioni manualmente.

Crea solo la cartella `<factory_dest>/<adapter_folder>/` vuota + un README.md con
le istruzioni di setup manuale.

## Fase 4 — Aggiornamento `factory.config.yaml.adapters[]`

Per ciascun adapter scaffoldato, aggiungi una entry a `factory.config.yaml`:

```yaml
adapters:
  - name: claude
    folder: .claude
    maturity: full
  - name: cursor
    folder: .cursor
    maturity: full
  # ... per ciascuno
```

## Fase 5 — Validation per-adapter

Per ciascun adapter scaffoldato:

1. **R.A1 — Isolamento cartella**: verifica che nessun file scaffoldato sia fuori
   dal proprio `adapter_folder`. Errori → segnala in chat e ABORT.
2. **Frontmatter validity** (per Cursor `.mdc`, Aider prompts, OpenAI assistants `.json`):
   verifica sintassi minima.
3. **Cross-references**: i file scaffoldati citano altri file (skill, command) che
   devono esistere — verifica nessun broken link.
4. **Manifest compliance**: i file scaffoldati corrispondono a quelli dichiarati in
   `manifest.yaml.templates` (no extra, no missing per le condizioni applicabili).

## Fase 6 — Report

Mostra in chat:

```
MULTI-ADAPTER SCAFFOLDING — REPORT
==================================
Adapter scaffoldati: <N>

| Adapter | Folder    | Maturity      | Profile     | File creati |
|---------|-----------|---------------|-------------|-------------|
| claude  | .claude/  | full          | native      | 45          |
| cursor  | .cursor/  | full          | sequential  | 38          |
| aider   | .aider/   | core          | sequential  | 23          |
| openai  | .openai/  | partial       | external    | 8           |
| gemini  | .gemini/  | manifest-only | viewer      | 1 (README)  |

Warning:
  - aider: core-LTS — EP v2.14+ non nello scaffold guarantee.
  - openai: profile external — L2–L5 bloccati senza runner FS sync; esegui
    `python .openai/setup.py` per Assistants (OPENAI_API_KEY).
  - gemini/chatgpt: viewer — query/lettura only; non usare come writer.
  - check-adapter-lag: vedi output di `tools/adapters/check-adapter-lag.py`.

factory.config.yaml.adapters[] aggiornato con <N> entry.

Coesistenza (R.A1-R.A6): tutti gli adapter scrivono solo nel proprio folder.
State filesystem condiviso (wiki/, management/, raw/, memory/, code_quality/).
```

## Aggiunta adapter post-bootstrap (R.A5)

Questa skill è invocabile **standalone** dopo il bootstrap iniziale per aggiungere un
nuovo adapter a una factory esistente:

```
Invoca bootstrap-multiadapter-protocol con:
  factory_dest_path: <existing-factory>
  adapters_selected: [<new-adapter>]
  adapter_registry_path: <meta-framework>/adapters/
  factory_config: <read da existing factory.config.yaml>
```

La skill:
1. Verifica che `<new-adapter>` non sia già in `factory.config.yaml.adapters[]`.
2. Esegue Fase 2-5 solo per il nuovo adapter.
3. Aggiorna `factory.config.yaml.adapters[]` aggiungendo l'entry.
4. Append entry `add-adapter <name>` a `wiki/log.md`.

## Vincoli inviolabili

- **R.A1**: ogni adapter scrive solo nel proprio `<adapter_folder>`. Mai cross-write.
- **R.A2**: state filesystem condiviso (wiki/, management/, ecc.) — adapter agnostic.
- **R.A3**: single-committer wiki/ enforced globalmente. La skill non bypassa.
- **R.A4**: manifest immutabile a runtime. La skill LEGGE il manifest, non lo modifica.
- **R.A5**: adapter aggiungibile a runtime invocando la skill standalone.
- **R.A6**: PATTERN.md / factory.config.yaml / layer L1-L5 mai runtime-specific.
  Verifica: dopo scaffolding, `PATTERN.md` non deve contenere riferimenti a tool
  Claude-specifici (Read/Write/Glob, ecc.) né a `.claude/` come unico adapter.

## Non in scope per questa skill

- Modifica del manifest stesso (R.A4).
- Customizzazione del template content (sono starter, l'utente li raffina).
- Gestione delle risorse API (es. creazione Assistants OpenAI) — quella è scope di
  `setup.py` post-scaffolding per `.openai/`.
- Coordinazione cross-adapter a runtime (es. wave plan parallelo across adapter) —
  scope dell'orchestrator di ciascun adapter, non del bootstrap.
