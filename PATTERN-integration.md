> Modulo di PATTERN.md (§12–§17) — indice e versione: [`PATTERN.md`](PATTERN.md).

## §12 — Adapter (runtime-specific)
<!-- profiles: full -->

Ogni adapter implementa i ruoli §2 con i costrutti del proprio runtime. **In v2.13** il
contratto è formalizzato con un **manifest** per ciascun adapter (vedi §12.1) che
abilita lo scaffolding multi-adapter parallelo al bootstrap.

### §12.0 — Adapter registry

Il **registry degli adapter** vive in `adapters/<name>/` al root del repo
meta-framework. Ogni sub-folder contiene il manifest + i template + un README. La
factory generata può ospitare uno o più adapter (es. `.claude/` e `.cursor/`
coesistenti) — la scelta è fatta al bootstrap o aggiunta a runtime.

Adapter attualmente disponibili (registry aggiornato; vedi
`adapters/capability-matrix.yaml` + `adapters/README.md`):

| Adapter | Folder runtime | Maturity | Orchestration profile | Registry path |
|---|---|---|---|---|
| Claude Code | `.claude/` | full (reference) | `native` | `adapters/claude/` (manifest; tree live in `.claude/`) |
| Cursor | `.cursor/` | full | `sequential` | `adapters/cursor/` |
| Aider | `.aider/` | **core** (LTS) | `sequential` | `adapters/aider/` |
| OpenAI Assistants | `.openai/` | partial | `external` | `adapters/openai/` |
| Gemini Code Assist | `.gemini/` | manifest-only | `viewer` | `adapters/gemini/` |
| ChatGPT (Custom GPT / file tools) | `.chatgpt/` | manifest-only | `viewer` | `adapters/chatgpt/` |

Validazione registry: `python3 tools/adapters/check-adapter-lag.py`. Tool deterministici
canonici in `tools/` (non nuovi script in `<adapter_folder>/tools/`).

**Più adapter possono coesistere** nella stessa factory: condividono `raw/`, `wiki/`,
`management/`, `design_&_architecture/`, `memory/`, `code_quality/`,
`factory.config.yaml`, e `<code_path(s)>/`. Ogni adapter agisce sullo stesso state
filesystem; non c'è duplicazione di dati o operazioni.

### §12.1 — Manifest format

Ogni `adapters/<name>/manifest.yaml` dichiara:

```yaml
adapter_name: cursor                  # slug
adapter_folder: .cursor               # cartella in cui scaffoldare nella factory generata
runtime: cursor                       # nome runtime descrittivo
runtime_version_min: "0.45"           # versione minima del runtime supportata
maturity: full | core | partial | manifest-only
# full = core + opt-in EP fino a contract_version
# core = L1–L4 + develop/lint/query/heal (EP v2.14+ non in scaffold guarantee)
contract_version: 2.32                # versione PATTERN supportata dallo scaffold
role_profile: writer | viewer | hybrid

# Come lo scheduler §18 e i fan-out devono comportarsi su questo runtime
orchestration:
  profile: native | sequential | external | viewer
  features:
    local_fs_read: true|false
    local_fs_write: true|false
    subagent_fanout: true|false|partial
    parallel_dispatch: true|false|partial
    hooks: true|false|partial
    mcp: true|false
    shell: true|false|partial
  degrade: {}                         # optional: how to degrade when features missing

# Mapping dei costrutti runtime
mappings:
  agent:
    pattern_concept: "Agente specializzato (PATTERN §2 ruoli)"
    runtime_construct: "Cursor rules file con frontmatter `description` + `globs`"
    file_path_template: ".cursor/rules/{name}.mdc"
  skill:
    pattern_concept: "Procedura riusabile (PATTERN v2.3 'fat skills')"
    runtime_construct: "Cursor rules file in .cursor/rules/skills/"
    file_path_template: ".cursor/rules/skills/{name}.mdc"
  command:
    pattern_concept: "Slash command per invocazione esplicita"
    runtime_construct: "Cursor custom command"
    file_path_template: ".cursor/commands/{name}.md"
  tool_read:
    pattern_concept: "Lettura file"
    runtime_construct: "@<file>"
  tool_write:
    pattern_concept: "Scrittura file"
    runtime_construct: "Edit/Apply (Cursor built-in)"
  # ... altri mappings

# Lista template scaffoldabili
templates:
  agents:
    - { name: orchestrator, required: true,  path: .cursor/rules/orchestrator.mdc }
    - { name: wiki-keeper,  required: true,  path: .cursor/rules/wiki-keeper.mdc }
    - { name: be-dev,       required: false, path: .cursor/rules/be-dev.mdc, condition: "routing.be == agent" }
    # ...
  skills:
    - { name: ingest-protocol, required: true, path: .cursor/rules/skills/ingest-protocol.mdc }
    # ...
  commands:
    - { name: run,  required: true,  path: .cursor/commands/run.md }
    - { name: lint, required: true,  path: .cursor/commands/lint.md }
    - { name: dev,  required: false, path: .cursor/commands/dev.md, condition: "has_dev_agents" }
    # ...

# Skill che cambiano comportamento per questo runtime
runtime_overrides:
  parallel_dispatch:
    supported: false           # Cursor non ha multi-tool-call concept
    fallback: "sequential dispatch with manual confirmation"
  subagent_fanout:
    supported: false
    fallback: "manual user invocation of separate agents"

# Note operative
notes: |
  Cursor (≥0.45) supporta `.cursor/rules/*.mdc` con frontmatter `description` +
  `globs`. Adatta gli agenti del PATTERN come rules con `description` che spiega
  quando attivare la rule. I sub-agent (Agent tool di Claude Code) non hanno
  equivalente diretto in Cursor; emulati come "rules condizionali" che l'utente
  invoca manualmente con @.
```

### §12.2 — Multi-adapter coexistence (R.A1-R.A6)

Invarianti per la coesistenza di adapter multipli nella stessa factory:

- **R.A1 — Isolamento di cartella**: ogni adapter scrive **solo** nel proprio
  `adapter_folder` (es. `.claude/` per Claude Code, `.cursor/` per Cursor). Mai
  scritture cross-adapter (es. `.cursor/` rules che modificano `.claude/agents/`).
- **R.A2 — State filesystem condiviso**: tutti gli adapter leggono e scrivono lo
  stesso `wiki/`, `management/`, `raw/`, `memory/`, ecc. (i layer L1-L4 + memoria +
  code_quality side-channel). Le operazioni canoniche §3 hanno la stessa semantica
  per ogni adapter — cambia solo il *costrutto* di invocazione.
- **R.A3 — Single-committer preservato**: la regola §7 r.12 (wiki/ single-committer)
  vale globalmente, non per-adapter. Solo wiki-keeper (in qualunque adapter) scrive
  `wiki/`. Se l'utente invoca `wiki-keeper` da `.claude/` E da `.cursor/`
  contemporaneamente, è responsabilità sua serializzare.
- **R.A4 — Manifest immutabile a runtime**: il manifest di un adapter cambia solo
  via release PATTERN nuove. La factory generata non modifica il manifest.
- **R.A5 — Adapter aggiungibile a runtime**: l'utente può aggiungere un adapter
  dopo il bootstrap eseguendo `bootstrap-multiadapter-protocol` standalone (con il
  manifest target) — senza ri-scaffoldare l'intera factory.
- **R.A6 — Agent-agnostic preservato**: PATTERN.md, `factory.config.yaml`, e i
  layer L1-L5 NON contengono mai riferimenti a tool/costrutti specifici di un
  runtime. Tutto ciò che è runtime-specific vive negli adapter. Questo è
  l'invariante che rende il pattern truly portable.

### §12.3 — Configurazione adapter in `factory.config.yaml`

Nuovo blocco `adapters:` (v2.13) per dichiarare gli adapter installati:

```yaml
adapters:
  - name: claude       # adapter attivo (deve corrispondere a una cartella `<adapter_folder>`)
    folder: .claude
    maturity: full
  - name: cursor       # opzionale, secondo adapter
    folder: .cursor
    maturity: full
  # ...
```

In single-adapter (caso comune), una sola entry. In multi-adapter, N entry.
Backward compat: se `adapters:` è assente, la factory assume `[{name: claude, folder: .claude, maturity: full}]` (compatibile con v2.12 e precedenti).

### §12.4 — Principio di taglio adapter (v2.3 + multi-adapter v2.13)

- Gli **agenti** sono identità contrattuali (mappabili a sub-agent / rules / Assistants / role-prompts del runtime).
- Le **skill** sono procedure ricorrenti (mappabili a file markdown / rules / function tools / prompts).
- Una stessa procedura non è duplicata fra adapter — è scritta una volta come **contratto** in `<adapter>/skills/<name>.md` e implementata nel costrutto del runtime.
- Le **regole inviolabili §7** sono invariabili per tutti gli adapter (cambia il costrutto, non il contratto).

**Dev-agent opzionali (v2.7)**: i quattro dev-agent (`be-dev`, `fe-dev`, `db-dev`, `qa-dev`) esistono solo se la topologia li include. Bootstrap installa solo quelli necessari, **in ogni adapter installato**. A runtime, aggiungere/rimuovere il file agente cambia la topologia.

## §13 — Topology & consumer routing (nuovo in v2.7)
<!-- profiles: minimal, standard, full -->

### Topologie supportate

La topologia è codificata dalla **presenza dei file agente** in `.claude/agents/` (o equivalente per altri adapter) + dal blocco `topology:` in `factory.config.yaml`.

| Topologia | Dev-agent presenti | Caso d'uso |
|---|---|---|
| `knowledge-only` | nessuno | Knowledge factory pura (Sync→Analyst), no planning, no execution |
| `plan-only` | nessuno | Default storico v2.6: arriva fino a TSK, consumer umano |
| `full-stack-agents` | `be-dev`, `fe-dev`, `db-dev`, `qa-dev` | Tutto agentico end-to-end |
| `hybrid-be-agents` | `be-dev`, `db-dev` | BE/DB agentici, FE/QA umani |
| `hybrid-fe-agents` | `fe-dev` | FE agentico, BE/DB/QA umani |
| `custom` | sottoinsieme arbitrario | Mix esplicito (es. solo `qa-dev` per autotest) |

### `factory.config.yaml` (schema, v2.8 + v2.12 multi-repo)

```yaml
# Configurazione factory — versione PATTERN e topologia
pattern_version: "2.12"
topology: full-stack-agents  # vedi tabella sopra

# === Code paths (L5) — v2.12 multi-repo ===========================================
# Lista di repository / path target. Ogni entry rappresenta uno scope di scrittura
# distinto (FE+BE disaccoppiati, microservizi, micro-frontend, monorepo con
# pacchetti multipli, …). Il TSK punta a un'entry via `target:` (§5).
#
# Per setup single-repo (default storico), una sola entry è sufficiente.
code_paths:
  - name: default                   # univoco; usato come `target:` nel TSK
    path: ./src/                    # relativo al repo factory o assoluto
    layers: [be, fe, db, qa, infra] # quali layer di TSK puntano qui (1+ valori)
    tags: []                        # opzionale: descrittivi (monolith, microservice, mfe, ...)
    vcs:
      mode: monorepo                # monorepo | submodule | sibling | external | none
      submodule_path: ""            # solo se mode=submodule
      remote_url: ""                # opzionale; documentazione e bootstrap
      branch_strategy: shared       # shared | per-tsk | per-sprint
      commit_coupling: float        # pin | float

# === Backward compatibility (v2.7-v2.11) ==========================================
# Se `code_path:` (singolare) è valorizzato e `code_paths:` è vuoto/assente, viene
# auto-promosso a `code_paths: [{name: default, path: <code_path>, layers: <tutti>,
# vcs: <blocco vcs top-level>}]`. Il blocco `vcs:` top-level (v2.8) resta valido
# solo in questo caso legacy; in multi-repo v2.12 il `vcs:` vive dentro a ciascuna
# entry di `code_paths`.
code_path: ""
vcs:
  mode: none
# ===================================================================================

# Modalità di scelta dello stack tecnologico
stack_mode: guided  # manual | guided | auto

# Routing TSK → consumer (default per layer; override per-TSK via frontmatter)
routing:
  be: agent      # agent | human
  fe: agent
  db: agent
  qa: agent
  infra: human

# Stack (in multi-repo, può essere per-entry — vedi §13.x)
stack:
  backend: <es. FastAPI 0.115 + Python 3.13>
  frontend: <es. React 19 + Vite>
  database: <es. PostgreSQL 17>
  qa: <es. Pytest + Playwright>
```

### Esempi multi-repo (v2.12)

**a) FE + BE disaccoppiati (2 repo)**:

```yaml
code_paths:
  - name: backend-api
    path: /Users/me/repos/portal-api/
    layers: [be, db, qa]
    tags: [monolith]
    vcs: { mode: sibling, remote_url: "git@github.com:org/portal-api.git" }
  - name: frontend-web
    path: /Users/me/repos/portal-web/
    layers: [fe]
    tags: [react, spa]
    vcs: { mode: sibling, remote_url: "git@github.com:org/portal-web.git" }
```

I TSK con `layer: be` finiscono in `backend-api` (auto-derivato, `target:` opzionale —
una sola entry copre `be`). Idem per `fe`. Layer `qa` ambiguo? Solo `backend-api` lo
copre → ancora auto-derivabile. Aggiungi `qa` a `frontend-web.layers` se vuoi e2e su
entrambi → allora `target:` diventa **richiesto** per i TSK QA.

**b) Microservizi (N BE + 1 FE)**:

```yaml
code_paths:
  - name: service-auth
    path: /Users/me/repos/auth-service/
    layers: [be]
    tags: [microservice, oidc]
    vcs: { mode: sibling, remote_url: "git@github.com:org/auth-service.git" }
  - name: service-payments
    path: /Users/me/repos/payments-service/
    layers: [be]
    tags: [microservice, stripe]
    vcs: { mode: sibling, remote_url: "git@github.com:org/payments-service.git" }
  - name: service-orders
    path: /Users/me/repos/orders-service/
    layers: [be]
    tags: [microservice]
    vcs: { mode: sibling }
  - name: web-app
    path: /Users/me/repos/web-app/
    layers: [fe, qa]
    tags: [next-js]
    vcs: { mode: sibling }
```

Tutti i microservizi hanno `layers: [be]`: il TSK BE **deve** dichiarare `target:` per
disambiguare (es. `target: service-auth`). Il TPM, quando produce TSK, decide il target
in base alla US/EP (es. una US "OAuth flow" → TSK BE su `service-auth`).

**c) Micro-frontend (N FE + 1 BE shared)**:

```yaml
code_paths:
  - name: api-gateway
    path: /Users/me/repos/api-gateway/
    layers: [be, db]
    vcs: { mode: sibling }
  - name: mfe-shell
    path: /Users/me/repos/mfe-shell/
    layers: [fe]
    tags: [module-federation, host]
    vcs: { mode: sibling }
  - name: mfe-checkout
    path: /Users/me/repos/mfe-checkout/
    layers: [fe]
    tags: [module-federation, remote]
    vcs: { mode: sibling }
  - name: mfe-catalog
    path: /Users/me/repos/mfe-catalog/
    layers: [fe]
    tags: [module-federation, remote]
    vcs: { mode: sibling }
```

Analogo (b) per i `fe`. Si possono mescolare coupling diversi: alcuni `sibling`, alcuni
`submodule`, alcuni `monorepo` (se uno dei repo ospita anche la factory). Ogni entry è
indipendente.

**d) Monorepo logico con pacchetti separati** (1 repo fisico, target distinti per
clarity di routing):

```yaml
code_paths:
  - name: api
    path: ./apps/api/
    layers: [be, db, qa]
    vcs: { mode: monorepo }
  - name: web
    path: ./apps/web/
    layers: [fe]
    vcs: { mode: monorepo }
  - name: shared
    path: ./packages/shared/
    layers: [be, fe]
    tags: [shared-lib]
    vcs: { mode: monorepo }
```

Tutto nello stesso commit chain. Il valore aggiunto è chiarezza di routing + scheduler
conflict detection più granulare (TSK su `api` non conflitta con TSK su `web`).

### Regole di routing

1. **TPM legge `factory.config.yaml`** e per ogni TSK applica `consumer: <routing[layer]>` come default. Override esplicito a livello TSK è ammesso (utile per task una-tantum).
2. **Override runtime**: il comando `/dev <TSK-id>` forza un dev-agent su un TSK con `consumer: human` (non modifica il file; è un'invocazione one-shot).
3. **Cambio topologia a runtime**: aggiungi/rimuovi il file agente in `.claude/agents/` (o equivalente). Aggiorna `topology:` e `routing:` in `factory.config.yaml` per coerenza. TPM userà la nuova config al prossimo run.
4. **Coerenza obbligatoria**: se `routing.be: agent` ma `be-dev.md` non esiste, è errore di config (segnalato da *Lint*). In multi-repo (v2.12): se `routing.<layer>: agent` ma nessuna entry in `code_paths` dichiara `<layer>` in `layers`, è errore di config (segnalato da Check 4c del lint).
5. **Target resolution (v2.12 multi-repo)**: il TPM, quando produce un TSK con `consumer: agent`, valorizza `target:` se l'ambiguità lo richiede (≥ 2 entry in `code_paths` con `<layer>` in `layers`). Algoritmo (vedi §5 `target` paragraph):
   - 0 match per layer → ERROR di config (Check 4c lint).
   - 1 match → `target:` opzionale, dev-agent risolve via auto-derive.
   - ≥ 2 match → `target:` **obbligatorio** sul TSK; assenza segnalata dal lint Check 4j (drift target/code_paths).
6. **Mai mescolare `code_path:` (legacy) e `code_paths:` (v2.12)**: scegliere una forma. In presenza di entrambi, `code_paths` prevale e `code_path` legacy viene ignorato con warning lint.

### Esempio: progetto BE agentico + FE umano (single-repo, legacy v2.11-)

```yaml
topology: hybrid-be-agents
code_path: /Users/me/Repos/customer-portal/   # legacy singolare
stack_mode: guided
routing:
  be: agent
  db: agent
  fe: human   # gli sviluppatori React lavorano in IDE
  qa: human
stack:
  backend: FastAPI 0.115
  frontend: React 19 (umano)
  database: PostgreSQL 17
```

In questo setup, `.claude/agents/` contiene `be-dev.md` e `db-dev.md`; `fe-dev.md` e `qa-dev.md` non esistono. I TSK con `layer: fe` o `layer: qa` finiscono in TODO board per umani; quelli con `layer: be|db` sono raccolti dai dev-agent (via `/run` → suggerimento).

### Esempio: BE agentico + FE umano (multi-repo, v2.12 forma esplicita)

Stessa topologia logica, ma il BE e il FE vivono in repo distinti:

```yaml
topology: hybrid-be-agents
code_paths:
  - name: portal-api
    path: /Users/me/repos/portal-api/
    layers: [be, db]
    vcs: { mode: sibling, remote_url: "git@github.com:org/portal-api.git" }
  - name: portal-web
    path: /Users/me/repos/portal-web/
    layers: [fe, qa]    # umani lavorano qui in IDE, factory non genera codice qui
    vcs: { mode: sibling, remote_url: "git@github.com:org/portal-web.git" }
stack_mode: guided
routing:
  be: agent      # dev-agent genera codice in portal-api
  db: agent      # idem
  fe: human      # umani in portal-web
  qa: human      # idem
```

Notare: portal-web ha `layers: [fe, qa]` ma `routing.fe: human` → i dev-agent non
vengono mai invocati su portal-web; serve a documentare nella config che quel repo
contiene FE+QA umani (utile per `repo-sync`, `code-quality-review-layer`, e per il
lint Check 4c che verifica la coerenza routing↔layers).

## §14 — Tech stack modes (nuovo in v2.7)
<!-- profiles: full -->

Tre modalità (campo `stack_mode` in `factory.config.yaml`):

### `manual` (v2.6 default)
L'utente scrive `raw/tech_stack.md` a mano prima di invocare *Arch*. Nessuna automazione.

### `guided`
Bootstrap mostra opzioni curate per ciascun layer (es. backend: FastAPI / Express / Spring Boot; database: PostgreSQL / MongoDB / SQLite) con pro/contro brevi citati. L'utente sceglie; bootstrap scrive `raw/tech_stack.md` riempito.

### `auto`
La skill `tech-scout` (invocabile da *Arch* o on-demand) legge `wiki/` (requisiti business + vincoli normativi) e usa fonti web datate (2026) per proporre uno stack ottimo (scalabilità, stabilità, supporto LTS). Output: `raw/tech_stack.md.proposal` con citazioni `[^web: <url> §<sezione>] (accessed YYYY-MM-DD)`. Gate umano obbligatorio per promuovere `.proposal` → `raw/tech_stack.md`.

**Invariante**: tech-scout NON sostituisce mai uno standard normativo già fissato in `raw/**` (§11). Se il wiki cita SPID/OIDC/FHIR, la proposta li adotta verbatim.

## §15 — VCS integration (v2.8, esteso multi-repo in v2.12)
<!-- profiles: full -->

La relazione fra il factory repo e il codice prodotto (L5) è dichiarata
esplicitamente in `factory.config.yaml.vcs.mode` per single-repo legacy, oppure in
`factory.config.yaml.code_paths[i].vcs.mode` per multi-repo v2.12 (una relazione VCS
**per entry**). La skill `vcs-handoff` applica una procedura diversa per ciascun mode;
gate umano sempre obbligatorio per operazioni distruttive o cross-repo (§7 r.14).

**Multi-repo (v2.12)**: ciascuna entry di `code_paths` ha il proprio blocco `vcs:`. Le
entry possono avere mode diversi (es. `backend-api: sibling`, `db: submodule`,
`shared-lib: monorepo`). `vcs-handoff` opera **per-target**: legge il `target:` del
TSK, risolve l'entry, applica la procedura del relativo `vcs.mode`. Mai operazioni
cross-entry coordinate (ogni commit chain è indipendente).

In single-repo legacy (`code_path:` singolare valorizzato, `vcs:` top-level), la skill
opera come v2.8-v2.11. Backward compat preservata.

### Modi VCS

Validi per **ciascuna entry** di `code_paths` (v2.12) o per il `vcs:` top-level (legacy single-repo):

| Mode | Significato | Quando |
|---|---|---|
| `none` | Nessun L5 per questa entry — la factory non gestisce codice qui | Solo legacy single-repo con `code_path: ""` (in multi-repo, se l'entry esiste deve avere un mode reale; rimuovere l'entry se non serve) |
| `monorepo` | L5 dentro al factory repo, un solo commit chain | `path` relativo al repo factory (es. `./src/`, `./apps/api/`) |
| `submodule` | L5 come git submodule dentro al factory repo | `path` relativo + `vcs.submodule_path` valorizzato + entry in `.gitmodules` |
| `sibling` | L5 in un working tree separato (altro clone) | `path` assoluto (o relativo fuori dal repo) + `vcs.remote_url` opzionale per documentazione |
| `external` | Path opaco, factory non ne conosce la topologia VCS | `path` qualsiasi, factory si limita a leggere/scrivere senza coordinare git |

**Verifica dell'allineamento locale/remote** (v2.44, EP-068 US-299): capability nel bucket
di ingresso (§23.8), non normata qui prima dell'esercizio. Comportamento per `mode`:
`CAPABILITIES.md` §Repo align.

**Mix di mode in multi-repo (v2.12)**: legittimo e comune. Esempio: una factory in
nuovo repo che ospita `db-migrations` come submodulo, legge `frontend-web` e
`backend-api` come sibling (clone separati di repo esistenti), e ha un `shared-lib`
embedded in monorepo:

```yaml
code_paths:
  - { name: db-migrations, path: ./db/, layers: [db], vcs: { mode: submodule, submodule_path: ./db/, remote_url: "..." } }
  - { name: frontend-web, path: /Users/me/repos/web/, layers: [fe], vcs: { mode: sibling } }
  - { name: backend-api, path: /Users/me/repos/api/, layers: [be], vcs: { mode: sibling } }
  - { name: shared-lib, path: ./packages/shared/, layers: [be, fe], vcs: { mode: monorepo } }
```

### Procedura `vcs-handoff` (per mode)

Invocata dal `dev-protocol` Fase 5, dopo `dev-handoff` (entry log) e prima
del return finale al chiamante.

**`monorepo`**: `git status` nel factory repo; se ci sono modifiche in `code_path`, propone un messaggio di commit con riferimento al TSK; gate umano → commit. Nessuna operazione cross-repo.

**`submodule`**:
1. `cd <submodule_path> && git status` → mostra i cambiamenti.
2. Propone messaggio di commit nel submodule + branch (vedi `branch_strategy` sotto).
3. **Gate umano** → conferma commit nel submodule (e push opzionale).
4. `cd <factory> && git add <submodule_path>` → stagea il bump del ref.
5. Propone commit nel factory repo: `chore(<layer>): bump <submodule_path> for TSK-ZZZ`.
6. **Gate umano** → conferma commit factory.
7. Se `commit_coupling: pin` → aggiorna `.factory-lock` (vedi sotto).

**`sibling`**:
1. `cd <code_path> && git status` → mostra i cambiamenti.
2. Propone messaggio di commit + branch nel repo sibling.
3. **Gate umano** → conferma commit (e push opzionale, mai automatico).
4. Append a `wiki/log.md`: `develop TSK-ZZZ → <commit-hash> @ <code_path>` con avviso "ricorda di mergeare il PR su <remote_url>".
5. Se `commit_coupling: pin` → aggiorna `.factory-lock`.

**`external`**:
1. Nessuna operazione VCS (la factory non sa cosa c'è in `code_path`).
2. Solo append a `wiki/log.md` con il path e — se git-tracciato — il commit hash. Best-effort.

### `branch_strategy`

Solo per `submodule` e `sibling`:
- `shared` (default) — tutti i `develop` commit sul branch corrente (di solito `main`/`dev`).
- `per-tsk` — un branch per TSK (`tsk-<id>-<slug>`). La skill propone il `git checkout -b` al primo commit del TSK.
- `per-sprint` — un branch per sprint (`sprint-<NN>`). Letto da `factory.config.yaml` o dal frontmatter `sprint:` del TSK.

### `commit_coupling`

- `float` (default) — solo log entry su `wiki/log.md`, nessun file di lock. Più semplice, accetta drift.
- `pin` — la skill mantiene `.factory-lock` al root: un file YAML che mappa ogni `develop` chiuso al commit hash del codice. Garantisce reproducibilità (`git checkout <factory-commit>` → so esattamente quale commit di L5 corrispondeva).

`.factory-lock` (formato):
```yaml
# .factory-lock — generato da vcs-handoff, append-only
- tsk: TSK-042
  layer: be
  vcs_mode: submodule
  submodule_path: ./code/
  commit: a1b2c3d4
  date: 2026-05-20T14:32:00Z
```

### Vincoli inviolabili (estensione §7 r.14)

- **Mai `git push`** senza gate umano esplicito. La skill propone, l'umano esegue.
- **Mai `git submodule add|update --remote`** senza gate umano. Al bootstrap, la skill stampa il comando da eseguire, ma non lo lancia.
- **Mai `git clone`** automatico al bootstrap per `sibling`: stampa istruzioni, l'umano cloni.
- **Mai `--force` / `--no-verify`** in nessun caso.
- **Mai modificare `.gitmodules`** o `.factory-lock` fuori da `vcs-handoff`.

### Branch Awareness Layer (v2.25, EP-034, opt-in)

Fino a v2.24 la relazione VCS era gestita **solo a commit-time** (`vcs-handoff`, Fase 5 di
`dev-protocol`) e **solo in reazione** (STOP se HEAD detached). La responsabilità di trovarsi
sul branch giusto *prima* di invocare un dev-agent era interamente umana e **non verificata
programmaticamente** (*«l'utente decide su quale branch si trova prima di invocare il
dev-agent»*). Con i submodule questo genera disorientamento sistematico, non per indisciplina
ma per la struttura stessa dei submodule.

**Perché i submodule confondono — il problema dei due (o N) HEAD.**
1. Il parent repo registra un **commit fissato** (gitlink), non un branch. `git submodule update`
   fa checkout di *quel commit* → **detached HEAD by default**. È la prima causa del «su quale
   branch sto?».
2. Il branch del submodule è **indipendente** da quello del parent: «quale branch» non ha una
   risposta unica — c'è quello del parent *e* quello di ogni submodule, e driftano.
3. Il parent può puntare al commit X mentre il submodule è sul branch Y al commit Z (**drift
   parent-ref vs submodule-HEAD**, trappola silenziosa).

Il Branch Awareness Layer colma il gap con tre momenti — **declare → inspect → align** —
tutti **opt-in** (default off, backward compat totale R.P3, nessuna nuova invariante §7).

#### 1. Declare — il branch atteso è un valore calcolabile

`branch_strategy` (`shared` | `per-tsk` | `per-sprint`) resta la fonte, ma la sua risoluzione
in **«expected branch»** viene promossa a **resolver condiviso** (`branch-resolver`) usato sia
dal preflight (inspect) sia da `vcs-handoff` (commit), così non esistono due logiche divergenti.
Due aggiunte opzionali:

- `base_branch` (per entry) — il branch di integrazione (es. `develop`, `main`) che disambigua
  `shared` e fissa il fork-point per `per-tsk`/`per-sprint`.
- `.factory-branches.yaml` (per-sprint) — manifest opzionale al root: source of truth «quale
  branch atteso per ogni target nello sprint corrente». Se assente, il branch atteso è derivato
  puramente da `branch_strategy`.

**Regola di risoluzione `branch-resolver`** (deterministica):

| `branch_strategy` | expected branch |
|---|---|
| `shared` | `base_branch` se valorizzato, altrimenti il branch corrente (mai detached) |
| `per-tsk` | `tsk-<id-lowercase>-<slug-from-title>` |
| `per-sprint` | `sprint-<NN>` (da frontmatter `sprint:` del TSK) |

Override esplicito: una entry in `.factory-branches.yaml` per quel `target` vince sulla regola.

#### 2. Inspect — snapshot read-only `/vcs-status`

Comando + skill `vcs-preflight-protocol` che, per ogni entry `code_paths` (e per ogni
submodule), producono una tabella **read-only** (mai muta lo stato):

| target | mode | branch corrente | branch atteso | HEAD | drift parent-ref | verdict |
|---|---|---|---|---|---|---|
| backend-api | submodule | *(detached @a1b2)* | `tsk-042` | ⚠ detached | ✗ parent@a1b2 ≠ sub@c3d4 | **ACTION** |
| frontend-web | sibling | `develop` | `develop` | ✓ | — | OK |

Per ogni riga con verdict `ACTION` stampa **il comando esatto di remediation** (il `git checkout`
o `git submodule update --init` da lanciare a mano). Integrato nel dashboard di `/run`
(orchestrator) quando `branch_awareness.preflight: true`: la tabella appare prima del wave
dispatch, così lo stato branch è visibile *prima* di eseguire.

Controlli specifici submodule:
- **detached HEAD** → elenca i branch locali che contengono il commit registrato dal parent e
  suggerisce il checkout corretto (invece di un generico STOP).
- **submodule non inizializzato** (`.git` assente sotto `submodule_path`) → prerequisito hard:
  stampa `git submodule update --init <path>` (mai automatico).
- **drift parent-ref vs submodule-HEAD** → segnala che il commit puntato dal parent diverge dal
  commit checked-out nel submodule.

#### 3. Align — gate pre-dispatch in `dev-protocol` Fase 0

Prima che il dev-agent scriva, se `branch_awareness.dispatch_gate` ≠ `off`, si confronta lo
stato VCS del target risolto con l'expected branch (via `branch-resolver`):

- `dispatch_gate: block` → mismatch = **STOP** con il comando esatto di remediation.
- `dispatch_gate: warn` → mismatch = WARNING inline, procede (l'umano decide).
- `dispatch_gate: off` (default) → comportamento identico a v2.24.
- `auto_align: propose` (default `off`) → in caso di mismatch **propone** il `git checkout`
  sotto gate umano; non lo esegue mai in autonomia. `auto_align: off` si limita a STOP/WARNING.

#### Vincoli inviolabili Branch Awareness (estensione §15)

- **R.B7** — Il layer inspect (`vcs-status` / `vcs-preflight-protocol`) è **read-only**: usa solo
  `git status`, `git branch`, `git rev-parse`, `git symbolic-ref`, `git merge-base`, `git
  ls-files`. Mai `checkout`, `commit`, `fetch`, `pull`, `reset` o qualunque comando che muti lo
  stato del working tree o del ref.
- **R.B8** — Il gate align (`dispatch_gate`) **non esegue mai `git checkout` automatico**. Con
  `auto_align: propose` propone il comando sotto gate umano; con `off` si limita a STOP/WARNING +
  comando suggerito. Coerente con il vincolo esistente «mai cambiare branch».
- **R.B9** — L'expected branch è calcolato **esclusivamente** da `branch-resolver` (single source
  of truth): `vcs-preflight-protocol` e `vcs-handoff` non ridefiniscono la logica di naming.
- **R.B10** — A `branch_awareness.enabled: false` (o blocco assente) l'intero layer è **no-op**:
  `/vcs-status` resta invocabile esplicitamente (volontà esplicita = esecuzione), ma nessun gate
  automatico si attiva e il dashboard `/run` non mostra la tabella branch. Backward compat R.P3.

#### `factory.config.yaml.vcs.branch_awareness` (schema)

```yaml
vcs:
  mode: submodule
  submodule_path: ./code/backend
  branch_strategy: per-tsk        # shared | per-tsk | per-sprint
  base_branch: develop            # NEW v2.25 — disambigua "shared", fork-point per per-tsk
  branch_awareness:               # NEW v2.25 — blocco opt-in, default off
    enabled: false                # master switch del layer
    preflight: false              # tabella /vcs-status nel dashboard /run
    dispatch_gate: off            # off | warn | block  (gate Fase 0 dev-protocol)
    auto_align: off               # off | propose  (mai checkout silente, R.B8)
    drift_check: false            # rileva parent-ref vs submodule-HEAD divergence
```

Default globale off → zero cambio di comportamento. Il layer ha valore soprattutto per
`mode: submodule` e `sibling` (multi-HEAD); per `monorepo` è degenere (un solo HEAD) ma
ammesso.

## §16 — Sync adapters (multi-source L1, v2.9, esteso v2.14 Fase 2)
<!-- profiles: standard, full -->

Il ruolo *Sync* (§2) è l'unico ruolo della factory **pluralizzabile per sorgente**: per
ogni famiglia di input L1 (PDF, Figma, repo locale, **knowledge graph**, futuri
Notion/Confluence/…) esiste un sub-agent dedicato che scrive il proprio sotto-scope di
`raw/`. Tutti i sub-agent condividono `raw/.extraction-manifest.json` (append-only per
chiave). L'*Analyst* (`wiki-keeper`) resta agnostico alla sorgente: legge il manifest,
capisce quale shape gestire (`.txt` | `.kb.json` | …), applica la grammatica di
citazione corrispondente (§6).

### Sub-agent supportati (v2.14)

| Sub-agent | Input | Output L1 | Trigger |
|---|---|---|---|
| `sync-docs` | `raw/*.pdf` | `raw/*.txt`, `raw/images/*-fig-NN.md` | nuovi PDF in `raw/` |
| `figma-sync` (v2.9) | URL Figma o `file_key` (passato al comando, non vive in `raw/`) | `raw/YYYY-MM-DD-figma-<file-key>.kb.json`, opzionali `raw/images/*-frame-NN.{md,png}` | comando `/figma-sync <url>` |
| `repo-sync` (v2.12) | path locale a un repo esistente (passato al comando; mai vive in `raw/`) | `raw/YYYY-MM-DD-repo-<slug>.md` (documento di specifiche umano-leggibile + sezioni strutturate: stack rilevato, struttura, moduli chiave, API surface, dipendenze, vincoli normativi); opzionale companion `raw/images/YYYY-MM-DD-repo-<slug>-tree.md` (albero del filesystem fino a depth configurabile) | comando `/repo-sync <path>`; usato dal bootstrap quando `wiki_feed_source: existing-repo` |
| **`graphify-sync` (v2.14 Fase 2)** | **`code_path` (entry di `factory.config.yaml.code_paths`) — passato al comando, non vive in `raw/`** | **`raw/YYYY-MM-DD-graph-<slug>.md` (summary umano-leggibile del graph: god nodes, surprising connections, confidence breakdown EXTRACTED/INFERRED/AMBIGUOUS) + side-channel `.graphify-state/code_paths/<slug>/{graph.json, GRAPH_REPORT.md, last_full_rebuild.txt}` (consumato dai dev-agent come context replacement)** | **comando `/graphify-sync <target>`; usato dai dev-agent in modalità context-compression quando `compression.context.enabled: true` (§20.10)** |

### Contratto per un nuovo sync adapter

Aggiungere un sub-agent (es. ipotetico `notion-sync`) richiede:

1. File agente in `.claude/agents/<name>.md` (o equivalente per altro runtime) — **thin**, identità + scope (regola v2.3).
2. Skill di procedura in `.claude/skills/<name>-protocol.md` — **fat**, contiene Discovery → Estrazione → Serializzazione (regola v2.3).
3. Comando di invocazione in `.claude/commands/<name>.md`.
4. Naming dichiarato in §4 (path + pattern per gli artefatti prodotti). Convenzione: prefisso del source nel filename (`<source>-` o `<source>-<key>-`) per evitare collisioni cross-adapter.
5. Una voce in `raw/.extraction-manifest.json` per ciascuna estrazione, con chiave univoca derivata dal source.
6. Eventuale grammatica di citazione in §6, se lo shape non è `.txt`/`.md` (es. `.kb.json` ha la regola dotted-path).
7. Aggiornamento di `ingest-protocol` (Fase 0/1) per leggere il nuovo shape.
8. Aggiornamento di `lint-checks` Check 4e (coerenza manifest ↔ filesystem) per validare il nuovo tipo.

### Invariante di isolamento

Ogni sub-agent Sync scrive **solo** nel proprio scope di naming. Mai sovrapposizioni:
`sync-docs` non tocca `*.kb.json` né `*-repo-*.md` né `*-graph-*.md`; `figma-sync` non
tocca `*.txt` né `*-repo-*.md` né `*-graph-*.md`; `repo-sync` non tocca `*.txt` né
`*.kb.json` né `*-graph-*.md` (e mai i file della sorgente scansionata, §7 r.17);
`graphify-sync` (v2.14) non tocca `*.txt` né `*.kb.json` né `*-repo-*.md` (e mai il
`<code_path>` analizzato — §7 r.17 esteso a code_path scanning). Se due adapter
producono lo stesso slug per fonti diverse → ERROR di config (un sync adapter deve
scegliere un namespace univoco). Solo `.extraction-manifest.json` è condiviso, e
ciascun sub-agent vi appende **solo la propria entry** (mai overwrite di entries
altrui).

### Side-channel storage per `graphify-sync` (v2.14 Fase 2)

A differenza degli altri sync adapter, `graphify-sync` produce **due output paralleli**:

1. **`raw/YYYY-MM-DD-graph-<slug>.md`** — riepilogo umano-leggibile del graph,
   consumabile dal `wiki-keeper` come ingest L1→L2 standard (analogo a `repo-sync`).
2. **`.graphify-state/code_paths/<slug>/`** — side-channel storage (analogo a
   `code_quality/`, §19): graph completo machine-readable (`graph.json`,
   `GRAPH_REPORT.md`, `last_full_rebuild.txt`). **Non versionato in git**
   (`.gitignore`-d). Consumato a runtime dai dev-agent e dal code-reviewer come
   **context replacement** dei file sorgente raw (vedi §20.10 Context Compression).

Caratteristiche del side-channel:
- **Rebuildable**: full rebuild ricostruisce tutto da zero da `<code_path>` (zero
  perdita di stato, solo costo di rebuild — 2–20 $ token su primo build).
- **Scritto solo da `graphify-sync`** (analogo a R.Q2 di CQRL — scope di scrittura chiuso).
- **Letto da molti**: dev-agent, code-reviewer, wiki-query (in v2.15 sperimentale).
- **Filesystem è single source of truth**: il graph è una *view derivata*, mai
  authoritative. Se conflitto graph ↔ filesystem → vince filesystem.

### Riuso dello Stack Detector (v2.12)

La skill `stack-detector` (definita in §19.2 come componente del Code Reviewer) è
**riusabile** dal `repo-sync`: durante la fase di estrazione del repo esistente, il
sub-agent invoca `stack-detector` per popolare la sezione `## Stack rilevato` del
documento `raw/YYYY-MM-DD-repo-<slug>.md` con `language`, `framework`, `framework_version`,
`secondary_libs`, `patterns_expected`. Questa riusabilità rende la pipeline coerente:
ciò che il Code Reviewer userà a runtime sul codice prodotto da L5 è la stessa logica
che `repo-sync` usa al kick-off di un progetto pre-esistente.

### Bootstrap da repo esistente — coupling modes (v2.12)

Quando la factory viene scaffoldata con `wiki_feed_source: existing-repo` (cioè il
materiale iniziale per L1 è uno o più repo locali preesistenti), l'utente sceglie
**come accoppiare** la factory ad ogni repo. La scelta determina deterministicamente
le entry di `code_paths` (§13) — `path`, `layers`, `vcs.mode` — non chiesti
indipendentemente.

**Single-repo vs multi-repo** (v2.12):
- **Un solo repo sorgente** → una sola entry in `code_paths`, una sola scelta di coupling.
- **Più repo sorgente** (FE + BE disaccoppiati, micro-frontend, microservizi, ...) → N
  entry in `code_paths`, ciascuna con il proprio coupling. Coupling diversi per repo
  diversi sono legittimi (es. monorepo per il primo repo + sibling per gli altri,
  oppure tutti sibling — vedi sotto).

**Tre coupling canonici** (applicabili a ciascun repo indipendentemente):

| Coupling | Path destinazione factory | `code_path` (derivato) | `vcs.mode` (derivato) | Modifica al repo sorgente? |
|---|---|---|---|---|
| **`monorepo`** | = path del repo esistente | `./` (radice) o sub-path interno | `monorepo` | **Sì** (factory installata dentro il repo: `PATTERN.md`, `.claude/`, `wiki/`, `management/`, `factory.config.yaml`, `code_quality/` se on, …). Mai sovrascrive file esistenti del repo (i path del cascade L1-L4 sono nuovi). Gate umano obbligatorio per conferma (potenziale conflitto se il repo ha già file omonimi). |
| **`sibling-new-repo`** | Nuovo path separato (default: `<repo-path>-factory/` accanto) | path **assoluto** verso il repo esistente | `sibling` | **No**. Il repo sorgente resta intatto (§7 r.17). La factory legge `<code_path>` come working tree esterno. `vcs.remote_url` opzionale (URL git del repo esistente, per documentazione). |
| **`submodule-new-repo`** | Nuovo path separato | relativo (default: `./code/`) | `submodule` + `submodule_path: ./code/` | **No** al momento del bootstrap. L'utente esegue manualmente `git submodule add <remote-url-repo-esistente> ./code/` dopo il bootstrap (gate §7 r.14 — mai automatico). |

**Vincoli inviolabili del coupling**:

- **R.B1 — Il bootstrap non scrive mai nel repo esistente in modalità `sibling-new-repo`
  o `submodule-new-repo`.** Anche se `repo-sync` (durante il bootstrap stesso) lo legge,
  l'unico path di scrittura è la nuova factory directory.
- **R.B2 — In `monorepo`, conferma esplicita prima di toccare il repo esistente.** Il
  bootstrap mostra in chat la lista dei file/cartelle che verrebbero aggiunti
  (`PATTERN.md`, `CLAUDE.md` o equivalente adapter, `factory.config.yaml`, `wiki/`,
  `management/`, `design_&_architecture/`, `memory/`, `raw/`, `.claude/` o adapter
  scelto, `code_quality/` se on) e attende `y/N`. Se uno qualsiasi di questi path
  esiste già nel repo → ABORT con messaggio chiaro (no overwrite distruttivo).
- **R.B3 — `repo-sync` scansiona la sorgente in modalità read-only sempre** (§7 r.17),
  indipendentemente dal coupling. In `monorepo`, scansiona dopo che il bootstrap ha
  scaffoldato i file della factory: il documento `raw/<data>-repo-<slug>.md` osserverà
  l'esistenza della factory appena creata come parte dello stato del filesystem (caso
  *reflective*, legittimo). Per evitare rumore, la skill `repo-extraction-protocol`
  esclude dallo scope di scansione i path tipici della factory (`PATTERN.md`,
  `.claude/`, `wiki/`, `management/`, `design_&_architecture/`, `memory/`, `raw/`,
  `code_quality/`).
- **R.B4 — Il coupling è scelto al bootstrap e non muta a runtime.** Cambiare coupling
  dopo lo scaffolding richiede rifare il bootstrap o operazioni VCS manuali (cross-repo).
  Il `wiki-lint` check 4d (coerenza VCS) segnala drift fra coupling implicito e
  `vcs.mode` corrente.
- **R.B5 — Agent-agnostic preservato**: il coupling è una proprietà del *layout
  filesystem* e *VCS*, non del runtime di agenti. Qualsiasi adapter (`.claude/`,
  `.cursor/`, `.openai/`, …) può coesistere su una factory bootstrappata con qualsiasi
  coupling. La scelta dei tool (Read/Write/Bash di Claude Code, o equivalenti) è
  ortogonale.
- **R.B6 — Multi-repo coupling mix** (v2.12): in setup multi-repo, ogni entry di
  `code_paths` può avere un coupling distinto. Vincoli:
  - **Al massimo una** entry può avere `vcs.mode: monorepo` (un solo repo può ospitare
    fisicamente la factory). Più entry con `monorepo` simultanee → ERROR di config
    (segnalato dal lint Check 4d esteso).
  - Le altre entry coesistono come `sibling` (path assoluto, no operazioni cross-repo
    automatiche), `submodule` (referenziate dal factory repo via `.gitmodules`), o
    `external` (path opaco).
  - **`repo-sync` invocato N volte al bootstrap**, una per entry in `code_paths` con
    `wiki_feed_source: existing-repo`. Produce N file in `raw/` (uno per repo); il
    `wiki-keeper` può ingerirli in batch (§3 "Ingest" parallelo via
    `wiki-keeper-worker` se N ≥ 3).
  - **`vcs-handoff` opera per-target**: dato il `target:` del TSK, risolve l'entry,
    applica la procedura del relativo `vcs.mode`. Mai operazioni cross-target
    coordinate automaticamente (gate umano §7 r.14 invariato).
  - **Scheduler conflict-detection** (§18.4 R.S2): due TSK con `target` diversi sono
    sempre conflict-free (filesystem disgiunti). Conflict solo intra-target su
    overlap di `code_path` glob.

### Esempi multi-repo + coupling al bootstrap

**Caso a — microservizi all-sibling** (factory in nuovo repo, tutti i microservizi
restano intatti):

```
Bootstrap input:
- wiki_feed_source: existing-repo
- N = 3 repo (auth-service, payments-service, web-app)
- coupling per ciascuno: sibling-new-repo
- factory destination: /Users/me/repos/customer-portal-factory/ (NUOVO)
- Per ciascun repo: path assoluto + name + layers + remote_url

Risultato:
- /Users/me/repos/customer-portal-factory/ contiene la factory
- Auth/Payments/Web restano INTATTI (R.B1)
- code_paths in factory.config.yaml ha 3 entry, ciascuna sibling
- raw/ contiene 3 file *-repo-<slug>.md (uno per servizio)
```

**Caso b — monolite monorepo + servizio sidecar sibling**:

```
Bootstrap input:
- wiki_feed_source: existing-repo
- N = 2 repo (monolith-app, notification-service)
- coupling: monolith-app=monorepo (factory dentro), notification-service=sibling
- factory destination: /Users/me/repos/monolith-app/ (= path del monolith)

Risultato:
- Monolith-app contiene ora anche la factory (PATTERN.md, .claude/, ecc.)
- Notification-service resta intatto (R.B1)
- code_paths: 2 entry — uno monorepo (./ del monolith) + uno sibling
  (/Users/me/repos/notification-service/)
```

**Caso c — tutti submodule**:

```
Bootstrap input:
- N = 4 repo (frontend-web, backend-api, db-migrations, shared-lib)
- coupling per tutti: submodule-new-repo
- factory destination: /Users/me/repos/portal-factory/

Risultato:
- Factory in /Users/me/repos/portal-factory/
- code_paths: 4 entry, ciascuna submodule, submodule_path: ./code/<name>/
- Bootstrap stampa 4 comandi `git submodule add ...` per l'utente (mai automatici, §7 r.14)
```

### `raw/.extraction-manifest.json` (esteso v2.9)

Formato per entry (retrocompat: entries pre-v2.9 senza `source` sono interpretate come
`source: pdf` dal *Analyst* e dal *Lint*):

```json
{
  "<key>": {
    "source": "pdf | figma | notion | ...",
    "extracted_at": "ISO-8601",
    "primary_artifact": "raw/<path>",
    "secondary_artifacts": ["raw/images/<...>", "..."],
    "extractor_version": "<sub-agent>@<semver>",
    "extraction_metadata": { ... }
  }
}
```

`<key>` è il nome base senza estensione e senza directory (es. `2026-05-21-spid-tech` o
`2026-05-21-figma-ABC123`). I sub-agent **non scrivono mai** entry con `source` diverso
dal proprio.

### Vincoli inviolabili (estensione §7)

- **L1 read-only resta intatto** (§7 r.1): solo *Sync* scrive in `raw/`, e ciascun
  sub-agent solo nel proprio scope.
- **Mai chiamare API esterne automaticamente in altri ruoli**. Le chiamate ad
  Anthropic API, Figma MCP, Figma REST API, Notion API, ecc. vivono solo nelle skill
  dei sub-agent Sync. Gli altri ruoli (PM/Arch/TPM/Dev) leggono il manifest e i
  file di `raw/`, mai la fonte originale.
- **Mai scrittura cieca**: il sub-agent Sync mostra in chat la proposta (file da
  creare, dimensioni, fonti) e attende conferma esplicita prima di scrivere
  (analogo a `ingest-protocol` Fase 2).

## §17 — Publisher adapters (multi-target L3/L4, v2.10)
<!-- profiles: full -->

Simmetrico ai sync adapters (§16): se §16 definisce il contratto per ingerire L1 da
fonti eterogenee, §17 definisce il contratto per **pubblicare L3/L4 verso tool esterni
di project tracking** (GitHub Issues/Projects, GitLab Issues, Jira, Linear, …) come
mirror push-only. Il sub-agent Publisher è un nuovo ruolo (§2) pluralizzabile per
provider.

### Invariante di direzione (PATTERN §8, single source of truth)

- `management/kanban/**` resta **canonico**. Il provider esterno è un mirror.
- Pubblicazione è **push-only** in v2.10. Modifiche fatte direttamente nel tool
  esterno (body, label, milestone) verranno **sovrascritte** al prossimo publish.
  Solo i `comment` e gli assignee su issue esterne sono lasciati intatti
  (l'Publisher non li tocca).
- Bidirectional di `status:` (issue chiusa sul provider → `status: done` nel TSK
  locale) è candidato per v2.11, **non implementato in v2.10**.

### Provider supportati (v2.10)

| Provider | Sub-agent | Implementazione di riferimento | Auth env (default) |
|---|---|---|---|
| `github` | `github-publisher` | `gh` CLI (richiede `gh auth login` preventivo) | `GH_TOKEN` |
| `gitlab` | `gitlab-publisher` | `glab` CLI o REST API | `GL_TOKEN` (placeholder, non implementato in v2.10) |
| `jira` | `jira-publisher` | REST API Cloud | `JIRA_TOKEN` (placeholder, non implementato in v2.10) |
| `linear` | `linear-publisher` | GraphQL API | `LINEAR_TOKEN` (placeholder, non implementato in v2.10) |
| `none` | — | (publishing disabilitato) | — |

`v2.10` rilascia il solo `github-publisher` come riferimento. Gli altri provider
hanno il contratto pronto ma agent/skill **non scaffoldati**: aggiungerli è
seguire il contratto del nuovo adapter (vedi sotto), niente modifiche a PATTERN.

### `factory.config.yaml.kanban_publish` (schema, v2.10)

```yaml
kanban_publish:
  provider: github          # none | github | gitlab | jira | linear | custom
  target: "<org>/<repo>"    # provider-specific: GH "org/repo", GL "group/proj", JIRA "PROJ", LINEAR "team-id"
  auth_env: GH_TOKEN        # nome variabile d'ambiente che contiene il token
  mode: push-only           # v2.10: solo push-only; bidirectional candidato v2.11
  batch_limit: 10           # gate §7 r.15: max artefatti pubblicati per run senza secondo gate
  mapping:
    epic_to: milestone      # milestone | issue-label | project-column
    story_to: issue-label   # issue-label | issue-type-story
    task_to: issue-label    # issue-label
    sprint_to: milestone    # milestone | project-iteration | cycle
  labels:
    epic: "kanban:epic"
    story: "kanban:story"
    task: "kanban:task"
    layer_prefix: "layer:"  # produce label "layer:be", "layer:fe", ...
  filter:
    only_consumer: any      # any | agent | human (pubblica solo TSK con questo consumer)
    only_status: any        # any | todo | in-progress | done
```

### Contratto per un nuovo Publisher adapter

Aggiungere un sub-agent (es. `linear-publisher`) richiede:

1. Agente thin in `.claude/agents/<provider>-publisher.md` (o equivalente per altro runtime).
2. Skill provider-specific in `.claude/skills/<provider>-mapping.md` — mapping concreto EP/US/TSK ↔ artefatti del provider + comandi CLI/API.
3. La skill provider-agnostic `publisher-protocol` (5 fasi) **non va duplicata**: il provider-specific mapping è una skill *complementare* invocata da `publisher-protocol`.
4. Nessun nuovo comando: `/kanban-publish` è agnostico al provider — legge `kanban_publish.provider` da config e invoca il sub-agent corrispondente.
5. Aggiornamento di `lint-checks` Check 4f (lista provider noti).
6. **Mai modifiche a PATTERN.md** per un nuovo provider: il contratto §17 li copre tutti.

### Invariante di isolamento

Ogni Publisher scrive **solo** nel proprio scope:

- Frontmatter `external_id:` di `management/kanban/EP-*/US-*/TSK-*.md` — solo se il prefisso `<provider>:` corrisponde al sub-agent attivo.
- `wiki/log.md` (append-only, marker `publish`).
- Provider esterno via CLI/API (gate umano per ogni batch, §7 r.15).

**Mai sovrapposizioni**:
- Mai modificare il corpo dei file kanban (PM/TPM ownership).
- Mai modificare `external_id:` di altri provider (es. `github-publisher` non tocca `external_id: jira:...`).
- Mai cancellare/chiudere issue esterne (anti-pattern destruttivo, vedi §7 r.15).

### Procedura `publisher-protocol` (5 fasi, provider-agnostic)

1. **Bootstrap**: verifica auth (`<auth_env>` settato + provider raggiungibile via CLI/API ping). Read `factory.config.yaml.kanban_publish`. ABORT se config invalida.
2. **Discovery**: `Glob management/kanban/EP-*/EP-*.md`, `US-*/US-*.md`, `**/TSK-*.md`. Filtra in base a `kanban_publish.filter`. Estrai metadata (frontmatter + body markdown).
3. **Plan**: per ciascun artefatto, decidi CREATE vs UPDATE in base a `external_id:` frontmatter. Mostra in chat: `Plan: CREATE EP×N1, US×N2, TSK×N3; UPDATE EP×M1, US×M2, TSK×M3. Procedo? [y/N]`. **Attendi conferma esplicita** (§7 r.15). Se totale CREATE+UPDATE > `batch_limit`, secondo gate obbligatorio.
4. **Publish**: per ogni artefatto, invoca la skill provider-specific (`<provider>-mapping`) che esegue CREATE/UPDATE sul provider e ritorna l'`external_id`. Aggiorna il frontmatter locale **solo nel campo `external_id:`** (mai del corpo).
5. **Log**: append a `wiki/log.md` template `publish` (count CREATE/UPDATE/skipped, lista artefatti con nuovo `external_id`). Output a chat: link al milestone/board esterno.

