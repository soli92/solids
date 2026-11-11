---
skill: lint-checks-config
part_of: lint-checks (modular)
family: config
parent: lint-checks
description: "Check lint su factory.config.yaml, topology, routing, VCS, publisher, manifest — check-family config"
---

# Lint Checks — Config

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 4c (topology/routing), Check 4d (VCS), Check 4e (manifest↔raw), Check 4f (Publisher), Check 4ah (Branch Awareness config), Check 4ak (content_share config)

Check ordinati per severità: ERROR → WARNING → INFO.

---

### 4c — Coerenza topology ↔ filesystem ↔ routing (v2.7, PATTERN §7 r.13)

Solo se `factory.config.yaml` esiste:

- Leggi `factory.config.yaml`: estrai `topology`, `routing`, `code_path`.
- Per ogni `routing.X: agent` in `{be, fe, db, qa}`: verifica esistenza
  `.claude/agents/<X>-dev.md`. Assenza → **ERROR routing-missing-agent**.
- Per ogni `<X>-dev.md` presente: verifica `routing.X: agent`. Mismatch →
  **ERROR orphan-dev-agent**.
- `topology:` ∈ `{knowledge-only, plan-only, full-stack-agents, hybrid-be-agents, hybrid-fe-agents, custom}`.
  Altrimenti → **ERROR invalid-topology**.
- Se topologia ∈ {`full-stack-agents`, `hybrid-*`, `custom` con almeno un dev}
  ma `code_path:` è stringa vuota → **WARNING dev-agents-without-code-path**.
- Per ogni TSK con `consumer: agent`: verifica esista l'agente `<layer>-dev.md`
  corrispondente. Assenza → **WARNING tsk-consumer-no-agent** (è valido, ma
  l'utente dovrà esplicitamente forzare via `/dev`).

### 4d — Coerenza VCS (v2.8, PATTERN §7 r.14, §15)

Solo se `factory.config.yaml` esiste con `vcs.mode` valorizzato:

- `vcs.mode: none` → `code_path` DEVE essere `""`. Altrimenti **ERROR `vcs-mode-mismatch`**.
- `vcs.mode: monorepo` → `code_path` deve essere relativo e dentro al repo
  (non assoluto, non `../`). Altrimenti **ERROR `vcs-mode-mismatch`**.
- `vcs.mode: submodule`:
  - `vcs.submodule_path` valorizzato e non vuoto. Altrimenti **ERROR `missing-submodule-path`**.
  - File `.gitmodules` esistente al root del repo. Altrimenti **ERROR `missing-gitmodules`**.
  - Entry per `<submodule_path>` presente in `.gitmodules`. Altrimenti **ERROR `submodule-not-declared`**.
  - Submodule inizializzato (`<submodule_path>/.git` esiste come file o directory). Altrimenti **WARNING `submodule-not-initialized`** (suggerisce `git submodule update --init --recursive`).
- `vcs.mode: sibling` → `code_path` deve esistere sul filesystem (se valorizzato).
  Se assente → **WARNING `sibling-code-path-not-found`** (può essere intenzionale
  pre-clone). Se presente ma non git repo → **WARNING `sibling-not-git-repo`**.
- `vcs.mode: external` → nessun check (path opaco).
- `branch_strategy` ∈ `{shared, per-tsk, per-sprint}` → altrimenti **ERROR `invalid-branch-strategy`**.
- `commit_coupling` ∈ `{pin, float}` → altrimenti **ERROR `invalid-commit-coupling`**.
- Se `commit_coupling: pin` → file `.factory-lock` esiste al root (anche vuoto,
  almeno header). Assenza → **WARNING `missing-factory-lock`** (suggerisce di
  crearlo o cambiare a `float`).
- `wiki/log.md` ultime 10 entry `develop`: il campo `**VCS mode:**` è presente.
  Assenza in ≥ 1 entry → **WARNING `develop-without-vcs-info`** (entry pre-v2.8,
  retrocompat OK).

### 4e — Coerenza manifest ↔ raw filesystem (v2.9, PATTERN §16)

Solo se `raw/.extraction-manifest.json` esiste:

- Per ogni entry `<key>` nel manifest:
  - Campo `source` ∈ `{pdf, figma, notion, ...}`. Assente → assume `pdf` (retrocompat) ma emit **WARNING `manifest-source-implicit`** (suggerisce di esplicitare).
  - Campo `primary_artifact` (v2.9): file esistente in `raw/`. Mancante o broken path → **ERROR `manifest-primary-missing`**.
  - Per `source: pdf`: `primary_artifact` deve essere `raw/<key>.txt`. Mismatch → **ERROR `manifest-shape-mismatch`**.
  - Per `source: figma`: `primary_artifact` deve essere `raw/<key>.kb.json` ed essere JSON parsabile. Mismatch o JSON malformato → **ERROR `manifest-shape-mismatch`** (sub-categoria `kb-json-invalid` se malformed).
  - Per `source: figma`: il KB JSON deve avere top-level `project`, `screens`, `components`, `flows`, `features`, `tokens` (anche se vuoti). Top-level mancante → **WARNING `kb-schema-incomplete`** (l'estrazione potrebbe essere stata parziale; vedi `extraction_metadata.status`).
  - `secondary_artifacts[]` (v2.9): ogni path elencato deve esistere. File mancante → **WARNING `manifest-secondary-missing`**.
  - `extracted_at`: ISO-8601 parsabile. Mismatch → **WARNING `manifest-bad-timestamp`**.
  - `extractor_version` (v2.9): presente per entries scritte da v2.9+. Assenza in entries antecedenti accettata silenziosamente.

- **Inverso (filesystem → manifest)**:
  - Per ogni `raw/*.txt` non in `raw/images/`: deve avere entry corrispondente nel manifest. Assenza → **WARNING `orphan-raw-artifact`** (probabilmente sync-docs non è ancora stato eseguito; suggerisce `/sync-docs`).
  - Per ogni `raw/*.kb.json`: deve avere entry con `source: figma`. Assenza → **WARNING `orphan-raw-artifact`** (suggerisce di rieseguire `/figma-sync` o di aggiungere manualmente l'entry).

- **Isolamento (PATTERN §16 invariante)**:
  - `raw/<key>.txt` con manifest `source: figma` → **ERROR `sync-adapter-collision`**.
  - `raw/<key>.kb.json` con manifest `source: pdf` → **ERROR `sync-adapter-collision`**.

### 4f — Coerenza Publisher (v2.10, PATTERN §17)

Solo se `factory.config.yaml.kanban_publish` esiste:

- Read `factory.config.yaml.kanban_publish`. Estrai `provider`, `target`, `auth_env`, `mode`, `batch_limit`, `mapping`.
- `provider` ∈ `{none, github, gitlab, jira, linear, custom}`. Altrimenti **ERROR `invalid-publish-provider`**.
- `mode` ∈ `{push-only}` per v2.10 (`bidirectional` riservato a v2.11). Altrimenti **ERROR `invalid-publish-mode`**.
- Se `provider ≠ none`:
  - `target` non vuoto. Assenza → **ERROR `missing-publish-target`**.
  - `auth_env` non vuoto. Assenza → **ERROR `missing-publish-auth-env`**.
  - `batch_limit` intero ≥ 1. Altrimenti **WARNING `invalid-batch-limit`** (applica default 10).
  - Mapping coerente: `mapping.epic_to ∈ {milestone, issue-label, project-column}`, `mapping.story_to ∈ {issue-label, issue-type-story}`, `mapping.task_to ∈ {issue-label}`, `mapping.sprint_to ∈ {milestone, project-iteration, cycle}`. Altrimenti **ERROR `invalid-publish-mapping`**.
  - Esistenza sub-agent corrispondente in `.claude/agents/<provider>-publisher.md`. Assenza → **ERROR `publisher-agent-missing`**.
  - Esistenza skill `.claude/skills/<provider>-mapping.md`. Assenza → **ERROR `publisher-mapping-missing`**.
- Per ogni `management/kanban/EP-*/EP-*.md`, `US-*/US-*.md`, `**/TSK-*.md`:
  - Frontmatter `external_id:` valorizzato:
    - Forma `<prefisso>:<id>` con `<prefisso>` ∈ `{github, gitlab, jira, linear}`. Altrimenti **ERROR `invalid-external-id-format`**.
    - Se `kanban_publish.provider: none` → **WARNING `orphan-external-id`** (il file ha un `external_id:` ma il publish è disabilitato; eredità di config precedente).
    - Se `kanban_publish.provider ≠ none` e prefisso ≠ provider → **WARNING `external-id-cross-provider`** (il file è pubblicato su un provider diverso da quello attualmente configurato; il publisher attuale lo skipperà).
  - Frontmatter `external_id:` assente:
    - Se `kanban_publish.provider ≠ none` e `status: in-progress|done` → **WARNING `unpublished-active-artifact`** (l'artefatto è attivo ma mai pubblicato; suggerisci `/kanban-publish run`).
- `wiki/log.md` ultime 10 entry `publish`: presenza di `provider:` + `created=N`, `updated=M`. Assenza → **WARNING `publish-without-summary`**.

## Check 4ah — Branch Awareness config coherence (WARNING, opt-in — EP-034)

**Trigger**: solo se `factory.config.yaml` contiene un blocco `vcs.branch_awareness` (a qualunque
livello: top-level `vcs:` o entry `code_paths[i].vcs`). A blocco assente → skip silenzioso (R.B10).
**Severità**: WARNING — non blocca il lint, segnala incoerenze di configurazione.
**Audience**: maintainer che abilitano il Branch Awareness Layer.

### Algoritmo

1. Per ogni blocco `vcs.branch_awareness` presente, verifica i valori enum:
   - `dispatch_gate ∈ {off, warn, block}` — altrimenti WARNING `[Check 4ah] invalid dispatch_gate`.
   - `auto_align ∈ {off, propose}` — altrimenti WARNING `[Check 4ah] invalid auto_align`.
   - `enabled`, `preflight`, `drift_check` booleani.
2. **Coerenza attivazione**: se `preflight: true` O `dispatch_gate != off` O `drift_check: true`
   ma `enabled: false` → WARNING `[Check 4ah] branch_awareness: sotto-flag attivo con enabled: false
   (il layer è no-op finché enabled resta false, R.B10)`.
3. **Coerenza mode**: se `branch_awareness.enabled: true` ma `vcs.mode ∈ {monorepo, external, none}`
   → INFO `[Check 4ah] branch_awareness degenere su mode <X> (single-HEAD): nessun effetto pratico`.
4. **Manifest**: se `.factory-branches.yaml` esiste e contiene target non presenti in
   `code_paths[].name` → WARNING `[Check 4ah] .factory-branches.yaml: target <X> non in code_paths`.

### Invarianti

- **Read-only**: il check non modifica config né esegue comandi git (coerente con R.B7).
- **Non blocca**: solo WARNING/INFO, mai ERROR — la config Branch Awareness è opt-in.
- **Skip a blocco assente**: factory senza `branch_awareness` non vedono questo check (R.B10).

## Check 4ak — content_share config integrity (WARNING, opt-in — EP-048)

**Trigger**: solo se `factory.config.yaml` contiene `content_share.enabled: true`. A flag assente o
`false` → skip silenzioso (R.CS2, backward compat totale).
**Severità**: WARNING — non blocca il lint, segnala configurazione incompleta.
**Audience**: maintainer che abilitano la capability Content Share Consumer Layer (EP-048).

### Algoritmo

1. Leggi `factory.config.yaml`: se il blocco `content_share:` è assente O `content_share.enabled != true`
   → **skip silenzioso** (no-op totale, 0 WARNING).
2. Se `content_share.enabled == true`, verifica i quattro campi obbligatori:
   - `pat_env`: stringa non vuota.
   - `secret_env`: stringa non vuota.
   - `source_repo_slug`: stringa non vuota.
   - `source_repo`: stringa non vuota.
3. Se **almeno un campo è assente o stringa vuota** → emetti **WARNING** (un singolo WARNING per config,
   non uno per campo):

```
[WARN] content_share abilitato ma uno o più campi obbligatori sono vuoti.
Campi richiesti: pat_env, secret_env, source_repo_slug, source_repo.
/share fallirà in Fase 0 (Pre-flight) con errore esplicito.
Azione: compilare i campi mancanti in factory.config.yaml o disabilitare content_share.enabled: false.
Vedi wiki/runbooks/content-share-setup.md
```

### Invarianti

- **Warning-only**: non ERROR — la capability è opt-in, una config incompleta è recuperabile (R.CS2).
- **Never heal-eligible**: la compilazione dei valori richiede dati di progetto (nomi env var, slug repo).
- **Read-only**: legge solo `factory.config.yaml`.
- **No-op a flag spento**: factory senza blocco `content_share:` o con `enabled: false` non vedono mai
  questo check (backward compat totale).

### Output format

```
## WARNING (igiene, mai heal-eligible)
- [WARNING][content-share-config-incomplete][4ak] content_share abilitato ma uno o più campi obbligatori sono vuoti (pat_env, secret_env, source_repo_slug, source_repo). /share fallirà in Fase 0 (Pre-flight). Compilare i campi mancanti in factory.config.yaml o disabilitare content_share.enabled: false. Vedi wiki/runbooks/content-share-setup.md.
```

### Scenari di verifica

| # | `content_share.enabled` | campi compilati | esito atteso |
|---|---|---|---|
| 1 | assente / `false` (default) | — | no warning (gate off, R.CS2 — backward compat) |
| 2 | `true` | tutti compilati (pat_env, secret_env, source_repo_slug, source_repo) | no warning (config completa) |
| 3 | `true` | `pat_env` vuoto/assente | **WARNING 4ak** |
| 4 | `true` | `secret_env` vuoto/assente | **WARNING 4ak** |
| 5 | `true` | `source_repo_slug` vuoto/assente | **WARNING 4ak** |
| 6 | `true` | `source_repo` vuoto/assente | **WARNING 4ak** |
| 7 | `true` | più campi vuoti | **WARNING 4ak** (un solo WARNING per config, non uno per campo) |

### Cross-link

4ak → `factory.config.yaml.content_share` + EP-048 (Content Share Consumer Layer) +
`wiki/runbooks/content-share-setup.md` + PATTERN §32 (Content Share Layer) +
skill `content-share-protocol.md` (Fase 0 Pre-flight check).

---

## Check 4aq — Path portabili cross-platform (ERROR, mai heal-eligible)

**Cosa verifica**: che nessun path **tracciato da git** sia illegale sul filesystem
Windows. Un solo nome file invalido rende impossibile `git pull` e `git clone`
dell'**intero repo** per chi lavora su Windows:

```
error: invalid path 'validation/release-gates/v2.24.0/2026-06-26T18:00:00Z-pass.log'
fatal: unable to checkout working tree
```

Il difetto **non e' riparabile lato client**: il nome arriva dal repository. Per questo
il check e' ERROR e non WARNING — ed e' la ragione per cui non basta un hook locale.

> **[TRIGGER VINCOLANTE]** Origine (incidente 2026-09-16) e tabella delle 6 regole verificate:
> `.claude/skills/references/lint-checks-config/check-4aq.md`. Leggila prima di interpretare un finding.

### Esecuzione

Il check e' **deterministico e delegato a uno script**: non richiede giudizio del modello.

```bash
python3 tools/lint/check-portable-paths.py            # exit 1 se viola
python3 tools/lint/check-portable-paths.py --json     # machine-readable
```

Regressione coperta da `tools/tests/test_meta_framework.py::TestPortablePaths`
(3 test, incluso un test che verifica che il checker **fallisca** sui nomi cattivi).

### Vincoli

- **ERROR**: non e' igiene, e' rottura di accesso al repo per un'intera piattaforma.
- **Mai heal-eligible**: rinominare un file tracciato richiede `git mv` + aggiornamento
  dei riferimenti, quindi passa da un umano o da un TSK esplicito.
- **Read-only**: legge solo l'output di `git ls-files`.
- **Always-on**: nessun flag di config. Vale per ogni factory, derivata inclusa.

### Output format

```
## ERROR
- [ERROR][non-portable-path][4aq] validation/release-gates/v2.24.0/2026-06-26T18:00:00Z-pass.log contiene ':' (vietato su Windows): rende impossibile git pull/clone del repo su Windows. Rinominare con `git mv` usando la forma ISO-8601 basic (2026-06-26T180000Z-pass.log). Verificare con python3 tools/lint/check-portable-paths.py.
```

### Cross-link

4aq → `tools/lint/check-portable-paths.py` (implementazione) +
`tools/tests/test_meta_framework.py::TestPortablePaths` (regressione) +
`.claude/skills/release-validation-gate.md` §Post-Step 5 (vincolo sul nome del log,
causa dell'incidente) + `.claude/commands/release.md` (artefatti prodotti).

---

## Check 4ax — `ignore = dirty` sui submodule (WARNING, heal-eligible)

`python3 tools/lint/check-submodule-ignore.py` (dentro `run-deterministic.py`): ogni sezione di
`.gitmodules` dichiara `ignore = dirty`, altrimenti ogni `git status` sul padre apre un processo
per submodule. Heal: `git config -f .gitmodules submodule.<nome>.ignore dirty`.

> **[TRIGGER VINCOLANTE]** Misure, cosa resta visibile, output e cross-link:
> `.claude/skills/references/lint-checks-config/check-4ax.md`. Leggila prima di eseguire il check.
