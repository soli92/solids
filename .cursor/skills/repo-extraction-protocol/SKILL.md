# Skill: Repo Extraction Protocol

> Adapter Cursor della skill `repo-extraction-protocol` definita in PATTERN.md.

Metadata skill (originale):
```yaml
name: repo-extraction-protocol
description: Protocollo di estrazione di un documento di specifiche markdown da un repository locale (PATTERN §16, v2.12). 5 fasi (Bootstrap → Discovery → Sampling → Proposta → Scrittura). Invocata da repo-sync; sub-skill stack-detector.
```

Riferimenti: PATTERN §16 (sync adapters), §7 r.1 (L1 read-only), §7 r.17 (sync
read-only verso la sorgente, generalizzata in v2.12), §19.2 (Stack Detector riusato),
[citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md), `wiki-log-entry`. Sub-skill: [stack-detector](mdc:.cursor/skills/stack-detector/SKILL.md).

## Quando viene invocata

| Caller | Trigger | Output |
|---|---|---|
| [repo-sync](mdc:.cursor/rules/repo-sync.mdc) agent | comando `/repo-sync <path>` | `raw/YYYY-MM-DD-repo-<slug>.md` + manifest entry |
| `factory-bootstrap` (skill) | utente sceglie `wiki_feed_source: existing-repo` | come sopra, eseguito al termine del bootstrap |

## Prerequisiti

- Path locale al repo (assoluto o relativo a cwd).
- Read access su tutti i file del repo. Nessun write access richiesto sulla sorgente
  (§7 r.17 — la skill **non scrive mai** nel repo scansionato).
- `raw/` esistente nella factory che invoca (target di scrittura).

## Costanti

```
SAMPLING_DEPTH      = 3                # profondità albero filesystem riassunto
MAX_FILES_SAMPLED   = 30               # cap difensivo Fase 3
MAX_FILE_BYTES      = 50_000           # mai leggere file più grandi (skip + nota nel doc)
TARGET_DOC_SIZE_KB  = (5, 15)          # lunghezza target del documento prodotto
SLUG_MAX_LEN        = 40               # vedi §4 naming
```

## Fase 0 — Bootstrap

1. **Valida path**: `Bash test -d <path>` → se no, ABORT.
2. **Verifica repo-ish**: deve esistere almeno uno di:
   - `.git/` directory (preferito)
   - Un manifest di lingua noto (`package.json`, `pyproject.toml`, `go.mod`, …)
   Se nessuno → ABORT con messaggio: «<path> non sembra un repo (no `.git/` né
   manifest noti). Procedi comunque? [y/N]».
3. **Calcola slug**: dal nome dell'ultima directory del path, lowercase, spazi → `-`,
   max `SLUG_MAX_LEN`. Esempio: `/Users/me/customer-portal-api/` → `customer-portal-api`.
4. **Calcola key manifest**: `<YYYY-MM-DD>-repo-<slug>`.
5. **Read `raw/.extraction-manifest.json`**:
   - Se chiave esiste con `status: success` → mostra entry esistente, chiedi:
     «Re-estrazione (overwrite con `## Aggiornamenti` semantics)? [y/N]».
   - Se `status: partial` / `error` → procedi (retry trasparente).
6. **Read `raw/tech_stack.md`** (se esiste) per contesto (non condiziona la scansione).

## Fase 1 — Piano di estrazione (STOP iniziale)

Mostra in chat:

```
PIANO ESTRAZIONE REPO
=====================
Sorgente:        <abs-path>
Slug:            <slug>
Output primario: raw/YYYY-MM-DD-repo-<slug>.md
Manifest key:    <key>
Companion:       raw/images/YYYY-MM-DD-repo-<slug>-tree.md (opzionale)
Modalità:        read-only verso la sorgente (PATTERN §7 r.17)
File totali nel repo: <N> (escluso .git, node_modules, vendor, dist, build, target)
Procedo con Discovery?
```

**Attendi conferma esplicita.** Se l'utente nega → ABORT pulito.

## Fase 2 — Discovery

### Step 2.a — Git metadata (se `.git/` presente)

```bash
git -C <path> rev-parse --abbrev-ref HEAD       # branch corrente
git -C <path> log -1 --format='%H|%ai|%s'       # ultimo commit
git -C <path> log --format='%an' | sort -u | head -10  # top contributors
git -C <path> log --since='1 year ago' --format='%ai' | wc -l  # attività
```

Salva in struct `git_metadata`.

### Step 2.b — Stack detection

Invoca [stack-detector](mdc:.cursor/skills/stack-detector/SKILL.md) con `<path>` come root. Output:
`stack_descriptor` (schema §19.2). Per repo multi-stack (monorepo
multi-language), `stack-detector` ritorna `stack_descriptor[]` — preserva tutti.

### Step 2.c — Struttura ad alto livello

Glob `<path>/*` (depth 1) + `<path>/*/*` (depth 2) escludendo:

```
.git/  node_modules/  vendor/  dist/  build/  target/  .venv/  __pycache__/
.next/  .nuxt/  coverage/  .pytest_cache/  .mypy_cache/  .DS_Store
```

Annota:
- Directory top-level con conteggio file ricorsivo.
- Pattern di layout: `monorepo` (es. presenza di `apps/` + `packages/` + lockfile root),
  `multi-package`, `flat`, `src-layout`, `layered` (`controllers/`, `services/`, `models/`).
- README path se presente.

### Step 2.d — Documenti correlati

Glob ricorsivo limitato a:
- `README*`
- `docs/**/*.md`
- `ADR/**/*.md`, `adr/**/*.md`
- `RFC*`
- `CHANGELOG*`, `HISTORY*`

Salva path (non leggere contenuti completi — saranno in `## Documenti correlati` come
lista di link).

## Fase 3 — Sampling mirato

Apri selettivamente, max `MAX_FILES_SAMPLED` file totali, max `MAX_FILE_BYTES` ciascuno:

### File obbligatori (se esistono)

1. **README** (top-level) — estrai descrizione (primi 500 char), badge, sezione "Installation"
   per identificare comandi di build/run.
2. **Manifest principale** (`package.json` / `pyproject.toml` / `pom.xml` / `go.mod` /
   `Cargo.toml` / `Gemfile` / `composer.json`) — estrai `name`, `description`, `version`,
   `dependencies` top-level.
3. **Config principale del framework**:
   - Next.js: `next.config.{js,mjs}`
   - NestJS: `nest-cli.json`, `tsconfig.json`
   - Django: `settings.py`, `urls.py`
   - FastAPI: file con `FastAPI()` instance (cerca con `Grep`)
   - Spring: `application.{yml,properties}`
   - Rails: `config/routes.rb`, `config/application.rb`

### File euristici (priorità)

- Entrypoint: `main.py`, `app.{py,ts,tsx,js}`, `index.{ts,tsx,js}`,
  `cmd/*/main.go`, `src/main/java/**/Application.java` — apri primi 100 righe.
- Routing/API: file con regex match su `@app.route|@app.get|@router|router.HandleFunc|@RestController|@Controller`.
- Schema DB: `prisma/schema.prisma`, `migrations/*.sql`, `models.py`, `schema.sql`,
  `*.proto`. Apri ma riassumi (lista entità).
- OpenAPI/Swagger: `openapi.{yaml,json}`, `swagger.{yaml,json}` → estrai
  `info.title`, `info.version`, conteggio path.

### Heuristic per moduli core (fan-in)

Per lingue con import statici (Python/TS/Go/Java), `Bash grep -r` per import statements
e classifica i file più importati (top-5) come "moduli core". Nessuna analisi semantica,
solo conteggio.

### Detection di vincoli normativi

Grep top-level su `README*` + `docs/**` per parole-chiave (case-insensitive):

```
SPID | OIDC | OAuth2 | SAML | eIDAS | FHIR | GDPR | HIPAA | PCI-DSS | HL7 | ISO 27001 | RFC \d+
```

Trascrivi **verbatim** la frase circostante (max 200 char per match) → input per
sezione `## Vincoli normativi` (regola §11).

### Detection di secret

Grep su `*.env*`, `*.config.*`, `secrets/**`, file con regex per pattern noti
(API keys, JWT, password literals). **Non trascrivere** i valori. Conteggia e
metti in `extraction_metadata.secrets_redacted`. Nota nel `.md`: «N file con
possibili secret non riportati nel documento; vedi raw repo per dettagli».

## Fase 4 — Proposta (STOP, §7 r.6)

Mostra in chat:

```
DOCUMENTO PRONTO
================
Lunghezza stimata: ~<X> KB ({sezioni})
Stack rilevato:    {language}/{framework} (conf {c})
File sampled:      <N> / <M> totali
Standards:         {lista verbatim}
Secrets:           <K> redacted
Companion tree:    {yes|no}
Procedo con la scrittura?
```

**Attendi conferma esplicita.** Se l'utente vuole rivedere il piano (sezioni
troppe/troppo poche, sampling diverso), torna a Fase 3 con i nuovi parametri.

## Fase 5 — Scrittura

### Step 5.a — Documento primario

**Write** `raw/<YYYY-MM-DD>-repo-<slug>.md` con sezioni canoniche
(vedi [repo-sync](mdc:.cursor/rules/repo-sync.mdc) per la lista). Template:

```markdown
---
source_path: <abs-path>
source_type: repo
git_branch: <branch>
git_commit: <hash>
extracted_at: <ISO-8601>
extractor: repo-sync@2.12.0
---

# Specifiche estratte: <nome>

> Documento generato da `repo-sync` v2.12 il <YYYY-MM-DD>. Sorgente: `<path>`
> @ commit `<hash>` (ramo `<branch>`). Read-only verso la sorgente.

## Identità

- **Nome**: <name dal manifest o slug>
- **Descrizione** (da README primi 500 char): ...
- **Owner / top contributors**: <list>
- **Ultimo commit**: <date>, `<hash>`, "<subject>"
- **Attività (ultimo anno)**: <N> commit

## Stack rilevato

<output dello stack-detector, formattato come sub-sezioni se multi-stack>

## Struttura ad alto livello

```
<albero filesystem depth 2, in code block>
```

Pattern di layout rilevato: <monorepo | multi-package | flat | layered | ...>

## Entrypoint e moduli chiave

- **Entrypoint**: `<path>:<line>` — `<descrizione 1 riga estratta dal sampling>`
- **Moduli core** (per fan-in):
  - `<path>` (N import in altri moduli)
  - ...

## API surface (se rilevata)

<sezione presente solo se trovati endpoint, schema OpenAPI, ecc.>

## Schema dati (se rilevato)

<sezione presente solo se trovati schema DB, .proto, ecc.>

## Dipendenze esterne

- Top-level da manifest (con versioni):
  - `<name>@<version>`
- Servizi esterni rilevati da config: DB, message queue, cache, ...

## Vincoli normativi / Standard

<list verbatim §11; sezione vuota se nessuno>

## Documenti correlati nel repo

- [README](README.md)
- [docs/architecture.md](docs/architecture.md)
- ...

## Test coverage rilevato

- Framework di test: <nome+version se da manifest>
- Suite presenti: `<path/tests/>`, ...
- Coverage tool config: `<path>` (se presente)

## Gap evidenti

> Quello che il sampling NON ha potuto chiarire. Input per `wiki-keeper` durante
> l'ingest L1→L2.

- ...
- ...

## Note di estrazione

- File sampled: <N>/<M>
- Secret redacted: <K>
- Estrazione: <status: success | partial | error>
```

### Step 5.b — Companion tree (opzionale)

Se l'utente ha confermato il companion in Fase 4 OPPURE se il repo ha > 50 directory
top-level, **Write** `raw/images/<YYYY-MM-DD>-repo-<slug>-tree.md`:

```markdown
---
source_repo: <slug>
source_path: <abs-path>
type: repo-tree
depth: 3
extracted_at: <ISO-8601>
---

# Albero filesystem — <slug> (depth 3)

```
<output di `Bash find <path> -maxdepth 3 -type d` filtrato e formattato>
```

Companion stub per `raw/<data>-repo-<slug>.md §Struttura ad alto livello`.
```

### Step 5.c — Append manifest

**Edit** `raw/.extraction-manifest.json`:

```json
{
  "<YYYY-MM-DD>-repo-<slug>": {
    "source": "repo",
    "extracted_at": "<ISO-8601>",
    "primary_artifact": "raw/<YYYY-MM-DD>-repo-<slug>.md",
    "secondary_artifacts": ["raw/images/<YYYY-MM-DD>-repo-<slug>-tree.md"],
    "extractor_version": "repo-sync@2.12.0",
    "extraction_metadata": {
      "source_path": "<abs-path>",
      "git_commit": "<hash-or-empty>",
      "git_branch": "<branch-or-empty>",
      "stack": { "language": "...", "framework": "...", "confidence": <x> },
      "files_sampled": <N>,
      "files_total_in_repo": <M>,
      "secrets_redacted": <K>,
      "status": "success | partial | error"
    }
  }
}
```

### Step 5.d — Suggest next step

Mostra in chat:

```
ESTRAZIONE COMPLETATA
=====================
Primary:   raw/<YYYY-MM-DD>-repo-<slug>.md (<X> KB)
Companion: raw/images/<YYYY-MM-DD>-repo-<slug>-tree.md
Manifest:  aggiornato (key: <key>)

Prossimo step:
- Invoca wiki-keeper per l'ingest L1→L2 (pipeline standard).
- L'ingest produrrà pagine wiki (concept/entity/synthesis) e aprirà gap mirati.
- Dopo l'ingest: invoca product-manager per il planning iniziale (US/EP da `wiki/`).
```

Mai chiamare [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) automaticamente: l'orchestrazione cross-ruolo è
responsabilità dell'utente o dell'orchestrator (§7 r.12).

## Regole anti-corner-case

- **Repo gigante (> 10000 file)**: chiedi conferma esplicita in Fase 1 prima di
  iniziare la Discovery. Riduci `MAX_FILES_SAMPLED` a 15 e segnala nell'output.
- **Repo binario / asset-heavy** (es. repo di dati con CSV/JSON/binari, no codice):
  `stack-detector` ritorna `confidence: 0`. Procedi comunque ma `## Stack rilevato`
  riporta «No stack di codice rilevato; sorgente sembra repository di dati/asset».
- **Repo senza .git** (snapshot, ZIP estratto): salta Step 2.a, lascia `git_*` vuoti
  nel manifest. Procedi normalmente.
- **Secret abbondanti**: se `secrets_redacted > 20` → segnala in chat WARNING e
  chiedi conferma di procedere («Molti file con possibili secret; il documento NON li
  conterrà, ma valuta se il repo è safe da scansionare»).
- **Stessa estrazione doppia**: se l'utente conferma la re-estrazione e l'output
  esiste già, scrivi `## Aggiornamenti (vYYYY-MM-DD)` in fondo invece di overwrite
  della prima parte (analogo a `ingest-protocol` §7 r.7).

## Non in scope per questa skill

- **Decidere quali sezioni del repo diventano pagine wiki** — scope dell'*Analyst*
  (`wiki-keeper`) durante `ingest-protocol`.
- **Eseguire codice del repo** (`npm install`, `pip install`, …) — mai. La skill
  è puramente filesystem-local + `git log` read-only.
- **Modificare il repo scansionato** — mai (§7 r.17 — invariante chiave).
- **Generare wikilink** `[[...]]` nel `.md` prodotto — i wikilink vivono in L2.
- **Aprire gap o storie** — lo fa `wiki-keeper` durante l'ingest.
- **Chiamate API GitHub/GitLab** — questa skill è offline (no network); per estrarre
  metadati di repo remoti, sarà un futuro `git-remote-sync` adapter (out-of-scope v2.12).
```
