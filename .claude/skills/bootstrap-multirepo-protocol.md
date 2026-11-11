---
name: bootstrap-multirepo-protocol
description: Skill di raccolta input multi-repo per existing-repo wiki feeding (PATTERN §13 + §16, v2.12). Loop su N repo, coupling per ciascuno, auto-deriva code_paths + vcs. Invocata dal meta-prompt factory-bootstrap quando wiki_feed_source == existing-repo.
---
# Skill — Bootstrap multi-repo + coupling

Riferimenti: PATTERN §13 (`code_paths` schema), §16 (sync adapters + coupling modes
R.B1-R.B6), §7 r.17 (sync read-only verso la sorgente), §15 (VCS multi-repo).
Invocata da `factory-bootstrap` v2.12 dopo `bootstrap-input-protocol` quando
`wiki_feed_source == "existing-repo"`.

## Input atteso

```yaml
target_path: <abs-path destinazione factory>
topology: <da input-protocol>
routing: <da input-protocol>
```

## Output schema (return value)

```yaml
code_paths:
  - name: <slug>
    path: <abs-or-relative>
    layers: [be|fe|db|qa|infra, ...]
    tags: [...]
    coupling: monorepo | sibling-new-repo | submodule-new-repo
    vcs:
      mode: <derivato>
      submodule_path: <se submodule>
      remote_url: <opzionale>
      branch_strategy: shared
      commit_coupling: float
  - ...
factory_dest_path: <derivato; può differire da target_path se coupling cambia il layout>
gates_passed: { rb1: ok, rb2: ok, rb6: ok }
```

## Fase 1 — Numero repo

Chiedi quanti repo esterni accoppiare:
- **1 repo** — single-repo classico (≡ esempio singleton di multi-repo)
- **2-3 repo** — FE/BE disaccoppiati / tri-tier
- **4+ repo** — architettura distribuita (microservizi / micro-frontend / polyrepo)

Per N ≥ 4 mostra reminder: «In multi-repo distribuito il TPM dovrà valorizzare
`target:` su ogni TSK BE/FE per disambiguare (PATTERN §5 + Lint Check 4j)».

## Fase 2 — Loop per ogni repo

Per ciascuno dei N repo, raccogli:

### 2.a — Path locale

Path assoluto o relativo a cwd. Verifica:
- `Bash test -d <path>` → esiste.
- È un repo: presenza di `.git/` o di un manifest noto (`package.json`, `pyproject.toml`,
  `pom.xml`, `go.mod`, `Cargo.toml`, `Gemfile`, `composer.json`). Se nessuno, chiedi
  conferma esplicita.
- **Mai cloning automatico**: se utente fornisce URL, ricorda `git clone` manuale
  prima (§7 r.17 + offline-only di `repo-extraction-protocol`).

### 2.b — Name logico (univoco)

Suggerisci dal nome cartella del repo + suffisso descrittivo se utile:
- `auth-service`, `web-app`, `db-migrations`, `mfe-checkout`, `api-gateway`, ...

Verifica univocità fra le entry della lista.

### 2.c — Layers

Multi-select fra `be`, `fe`, `db`, `qa`, `infra`. Almeno uno richiesto.

Esempi:
- Microservizio BE → `[be]` (o `[be, qa]` con test integrati host)
- Web app FE → `[fe]` (o `[fe, qa]` con e2e)
- Monolite full-stack → `[be, fe, db, qa]`
- Repo db-only (migrations) → `[db]`
- Shared lib usata da BE e FE → `[be, fe]` con `tags: [shared-lib]`

### 2.d — Tags

Free-text, opzionale. Suggerisci tag dal dominio: `monolith | microservice | mfe |
shared-lib | mobile | api-gateway | sidecar | ...`.

### 2.e — Coupling (PATTERN §16)

| Coupling | factory_dest | `path` derivato | `vcs.mode` derivato | Modifica al repo sorgente? |
|---|---|---|---|---|
| `monorepo` | = path del repo | `./` (radice) o sub-path | `monorepo` | **Sì** (R.B2 gate umano) |
| `sibling-new-repo` (default) | nuovo path separato | assoluto al repo sorgente | `sibling` | **No** (R.B1) |
| `submodule-new-repo` | nuovo path separato | `./code/<name>/` | `submodule` + `submodule_path` | **No** al bootstrap; submodule add manuale dopo (§7 r.14) |

**Mix consigliati per architettura**:

| Architettura | Coupling tipico |
|---|---|
| Single repo greenfield | 1× `monorepo` |
| FE + BE disaccoppiati | 2× `sibling-new-repo` |
| Monolite legacy + sidecar nuovo | 1× `monorepo` (monolite) + 1× `sibling` (sidecar) |
| Microservizi N ≥ 3 | N× `sibling-new-repo` (factory in nuovo repo dedicato) |
| Microservizi + db da versionare insieme | N× `sibling` + 1× `submodule` per db |
| Micro-frontend (N FE + 1 BE) | N× `sibling` per gli MFE + 1× `sibling`/`submodule` per BE |

### 2.f — Gate R.B2 (solo se coupling = monorepo)

Prima di accettare `monorepo`, verifica nel repo sorgente l'**assenza** di:
`PATTERN.md`, `factory.config.yaml`, `wiki/`, `management/`, `design_&_architecture/`,
`memory/`, `raw/`, `code_quality/`, `.claude/` (o altro adapter scelto).

- Se uno qualunque esiste → ABORT: «Repo target contiene già <lista>. Bootstrap monorepo
  richiede assenza. Opzioni: (a) rimuovi manualmente, (b) usa `sibling`/`submodule`».
- Se nessuno esiste → mostra **inventario** di cosa verrà aggiunto, attendi `y/N`.

### 2.g — Gate R.B1 (solo se coupling ∈ {sibling, submodule})

- Path destinazione factory **NON** è dentro né uguale a, né padre di `<path-repo-sorgente>`.
- Per `submodule`: chiedi `remote_url` opzionale (URL git, se noto).

## Fase 3 — Vincoli multi-repo (R.B6)

Verifica sull'intera lista:
- **`name` univoco** fra tutte le entry. Duplicati → ERROR.
- **`layers` non vuoto** per nessuna entry.
- **Coerenza routing↔layers**: per ogni `routing.<X>: agent`, almeno un'entry deve
  avere `<X>` in `layers`. Altrimenti ERROR config (Check 4c lint).
- **R.B6 — Max 1 monorepo**: contare le entry con `coupling: monorepo`. Se ≥ 2 →
  ABORT: «Solo un repo può ospitare la factory in monorepo. Scegli quale e usa
  sibling/submodule per gli altri».
- **Path disgiunti**: nessun path è sub-path di un altro (eccetto monorepo+sub-path
  interno consentito per pacchetti).

## Fase 4 — Derive factory_dest_path

- Se ≥ 1 entry ha `coupling: monorepo` → `factory_dest_path` = path di quell'entry
  (la factory vive lì).
- Altrimenti (tutto sibling/submodule) → `factory_dest_path` = path scelto dall'utente
  per la nuova factory (default: `<repo-principale-path>-factory/` accanto al primo
  repo).

## Fase 5 — Riepilogo + conferma

Mostra in chat tabella completa:

```
MULTI-REPO COUPLING — N = <N> repo
==================================
Factory destination: <factory_dest_path>

| # | name             | path                  | layers       | coupling           | vcs.mode  |
|---|------------------|-----------------------|--------------|--------------------|-----------|
| 1 | auth-service     | /Users/.../auth/      | [be]         | sibling-new-repo   | sibling   |
| 2 | payments-service | /Users/.../payments/  | [be]         | sibling-new-repo   | sibling   |
| 3 | web-app          | /Users/.../web/       | [fe, qa]     | sibling-new-repo   | sibling   |

Gates: R.B1 ✓ R.B2 N/A R.B6 ✓ (0 monorepo)
Routing↔layers coerenza: ✓ (be→[1,2], fe→[3], qa→[3])

Procedo? [y/N]
```

Attendi conferma esplicita. Mai procedere senza.

## Return value

Dict strutturato (vedi Output schema sopra), da passare a:
- `bootstrap-scaffolding-protocol` (popolerà `code_paths` in `factory.config.yaml`)
- `bootstrap-vcs-protocol` (gestirà submodule add stamps + `.factory-lock`)
- Step 4-ter del meta-prompt (loop `/repo-sync` per ciascuna entry)

## Vincoli inviolabili

- **R.B1** — coupling sibling/submodule: mai modificare il repo sorgente.
- **R.B2** — coupling monorepo: gate umano esplicito + verifica assenza path della factory.
- **R.B3** — `repo-sync` invocato sempre read-only verso la sorgente.
- **R.B4** — coupling immutabile a runtime.
- **R.B5** — agent-agnostic preservato.
- **R.B6** — max 1 entry monorepo.
- **No-self-ingest**: mai passare il `factory_dest_path` come path a `/repo-sync` (ABORT).
