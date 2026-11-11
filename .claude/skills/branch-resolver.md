---
name: branch-resolver
description: Calcola l'«expected branch» di un target VCS in modo deterministico da branch_strategy + base_branch + .factory-branches.yaml. Single source of truth condivisa da vcs-preflight-protocol e vcs-handoff (PATTERN §15, EP-034 R.B9). Read-only, pura funzione.
epic_id: EP-034
pattern_version: "2.25"
---
# Skill — branch-resolver

Pura funzione di risoluzione: dato un target VCS (entry `code_paths` o `vcs:` legacy) e un
TSK, ritorna il **branch atteso** (`expected_branch`). È la **single source of truth** (R.B9):
`vcs-preflight-protocol` (inspect) e `vcs-handoff` (commit) la invocano entrambi, così non
esistono due logiche di naming divergenti.

**Read-only**: non esegue mai comandi git che mutino lo stato. Legge config, frontmatter TSK,
e opzionalmente `.factory-branches.yaml`. Non fa checkout, non crea branch.

---

## Input

- `resolved_vcs` — blocco `vcs:` del target (mode, branch_strategy, base_branch, submodule_path, …).
- `tsk` (opzionale) — frontmatter del TSK corrente (`id`, `title`, `sprint`). Necessario solo per
  `per-tsk` / `per-sprint`. Assente quando il resolver è chiamato in modalità preflight su un
  target senza TSK in contesto (in quel caso vedi Step 3 fallback).
- `target_name` — nome dell'entry (per lookup in `.factory-branches.yaml`).

## Output

```yaml
expected_branch: <string | null>   # null = "branch corrente qualunque" (solo shared senza base_branch)
source: <manifest | base_branch | strategy | current>
notes: <string>                    # es. "manifest override", "detached non ammesso su shared"
```

---

## Step 1 — Manifest override (precedenza massima)

Se esiste `.factory-branches.yaml` al root del factory repo E contiene una entry per
`target_name` valida per lo sprint corrente:

```yaml
# .factory-branches.yaml — source of truth per-sprint (opzionale, EP-034)
sprint: "07"
targets:
  backend-api: tsk-042-add-login-endpoint
  frontend-web: develop
```

→ `expected_branch = targets[target_name]`, `source: manifest`. **STOP** (vince su tutto il resto).

Se il manifest esiste ma non ha entry per `target_name` → prosegui a Step 2 (non è un errore).

## Step 2 — Risoluzione da `branch_strategy`

Solo per `mode: submodule` e `sibling` (per `monorepo`/`external`/`none` → `expected_branch: null`,
`source: current`, il layer è degenere).

| `branch_strategy` | expected_branch | source |
|---|---|---|
| `shared` | `base_branch` se valorizzato; altrimenti `null` (= "il branch corrente, purché non detached") | `base_branch` o `current` |
| `per-tsk` | `tsk-<id-lowercase>-<slug>` dove `<slug>` = slug del `tsk.title` (kebab-case, ≤40 char) | `strategy` |
| `per-sprint` | `sprint-<NN>` dove `NN` = `tsk.sprint` zero-padded a 2 cifre | `strategy` |

**Naming `per-tsk`**: `tsk-042-add-login-endpoint` (id minuscolo, slug dal titolo). Identico al
naming storico di `vcs-handoff` Fase 1 — la regola è **spostata qui** e riusata da entrambe le
skill (R.B9). Lo slug: lowercase, spazi/underscore → `-`, rimuovi caratteri non `[a-z0-9-]`,
collassa `--`, taglia a 40 caratteri.

## Step 3 — Fallback senza TSK in contesto (solo preflight)

Quando il resolver è chiamato da `vcs-preflight-protocol` su un target **senza** un TSK
corrente (snapshot generale `/vcs-status`):

- `shared` → `expected_branch = base_branch` (o `null` se assente).
- `per-tsk` / `per-sprint` → `expected_branch: null`, `source: strategy`,
  `notes: "expected branch dipende dal TSK — non determinabile senza TSK in contesto"`.
  Il preflight in questo caso non emette verdict `ACTION` per il naming (non ha un atteso), ma
  segnala comunque detached HEAD, submodule non inizializzato e drift parent-ref.

## Vincoli

- **Read-only (R.B7)**: mai `git checkout`, `commit`, `fetch`. Solo lettura config/frontmatter/manifest.
- **Determinismo (R.B9)**: stesso input → stesso output. Nessuna euristica non riproducibile.
- **Nessun side-effect**: non scrive file (il manifest è scritto/curato a mano o da un flusso
  dedicato, mai da questa skill).

## Cross-link

- PATTERN §15 §«Branch Awareness Layer» — regola di risoluzione + R.B9.
- Consumatori: `vcs-preflight-protocol` (inspect), `vcs-handoff` Fase 1 (commit).
- ADR-EP034-001 §«Single source of truth per l'expected branch».
