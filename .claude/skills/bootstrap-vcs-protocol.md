---
name: bootstrap-vcs-protocol
description: Skill di VCS bootstrap. Stampa i comandi git submodule add (mai automatici), crea .gitmodules placeholder, scrive .factory-lock se commit_coupling pin. Loop per-entry in multi-repo. Invocata da factory-bootstrap dopo bootstrap-scaffolding-protocol.
---
# Skill — Bootstrap VCS operations

Riferimenti: PATTERN §15 (VCS integration), §7 r.14 (gate umano per scritture VCS
distruttive/cross-repo), §16 (coupling modes). Invocata da `factory-bootstrap` v2.12
dopo `bootstrap-scaffolding-protocol`.

## Input atteso

Dict completo includendo:
- `factory_dest_path`
- `code_paths` (multi-repo v2.12) o `code_path` + `vcs` (single-repo legacy)
- `wiki_feed_source` (per ordering del repo-sync invoke nel meta-prompt)

## Loop per-entry (multi-repo) o single (legacy)

In multi-repo, itera su `code_paths`. In legacy, opera sull'unica `vcs:` top-level
(tratta come una sola "entry" virtuale).

Per ciascuna entry (o l'unica):

### Caso `vcs.mode: monorepo`

- Niente operazioni VCS speciali. La cartella L5 è già stata creata dallo scaffolding.
- Annota in chat: «entry `<name>`: L5 in monorepo a `<path>` — un solo commit chain.
  Suggerito commit dedicato al termine (es. `chore: bootstrap factory v2.12 in monorepo`)».

### Caso `vcs.mode: none`

- Niente operazioni. Tipicamente `topology ∈ {knowledge-only, plan-only}`.

### Caso `vcs.mode: submodule`

**Mai** lanciare `git submodule add` automaticamente (§7 r.14, R.B1).

Stampa il comando da eseguire:
```bash
cd <factory_dest_path>
git submodule add <remote_url> <submodule_path>
git config -f .gitmodules submodule.<submodule_path>.ignore dirty
git commit -m "chore: add <name> as submodule (TSK-bootstrap)"
```

La riga `ignore = dirty` evita che ogni `git status` sul padre apra un processo dentro il
submodule (lint 4ax, `lint-checks-config.md`); lo spostamento del puntatore resta visibile.

Se `remote_url` è empty (utente non l'ha fornito), avvisa: «Imposta `vcs.remote_url`
in `factory.config.yaml.code_paths[<name>].vcs.remote_url` prima di eseguire
`git submodule add`».

Crea (opzionalmente) `.gitmodules` placeholder vuoto solo se l'utente conferma di
NON eseguire `submodule add` subito. Altrimenti `git submodule add` lo creerà.

### Caso `vcs.mode: sibling`

**Mai** lanciare `git clone` automaticamente (§7 r.14).

Se l'utente ha fornito `remote_url` ma il path indicato non è ancora popolato (cartella
esiste ma è vuota o non è un git clone), stampa:
```bash
git clone <remote_url> <path>
```

Se il `path` è già un repo esistente popolato (caso comune in existing-repo coupling),
non serve cloning. Annota in chat: «entry `<name>`: sibling già clonato in `<path>` —
nessuna operazione necessaria».

### Caso `vcs.mode: external`

Nessuna istruzione VCS, è opaco per disegno. Annota: «entry `<name>`: external, factory
non coordina git».

## `.factory-lock` (commit_coupling: pin)

Se **almeno una entry** ha `vcs.commit_coupling: pin`:

Crea al root di `factory_dest_path` un file `.factory-lock`:

```yaml
# .factory-lock — generato da bootstrap-vcs-protocol (PATTERN §15)
# Append-only: ogni Develop chiuso aggiunge una entry corrispondente.
# Schema entry (generata da vcs-handoff a runtime):
# - tsk: TSK-XXX
#   target: <name>
#   layer: be|fe|db|qa
#   vcs_mode: <mode>
#   submodule_path: <path>  # solo se mode=submodule
#   commit: <hash>
#   date: <ISO-8601>
```

Solo le entry con `pin` contribuiscono al lock (le `float` no).

## Riepilogo finale in chat

Stampa per ciascuna entry:

```
VCS BOOTSTRAP — RIEPILOGO
=========================
| # | name             | vcs.mode   | path          | Azione |
|---|------------------|------------|---------------|--------|
| 1 | auth-service     | sibling    | /Users/.../   | nessuna (repo già clonato) |
| 2 | payments-service | sibling    | /Users/.../   | nessuna |
| 3 | db-migrations    | submodule  | ./code/db/    | esegui `git submodule add <url> ./code/db/` |
| 4 | web-app          | monorepo   | ./apps/web/   | nessuna (L5 in monorepo) |

.factory-lock creato: yes (1 entry con commit_coupling: pin)

Operazioni che richiedono azione umana:
  - cd <factory_dest_path>
    git submodule add <url-db-migrations> ./code/db/
    git commit -m "chore: add db-migrations submodule"
```

## Return value

```yaml
manual_commands: [<lista comandi git da eseguire>]
factory_lock_created: true | false
operations_summary: <tabella>
warnings: [...]   # missing remote_url, ecc.
```

## Vincoli inviolabili

- **§7 r.14** — Mai `git submodule add|update`, `git clone`, `git push`, `git commit --amend`,
  `--force`, `--no-verify` automatici. Sempre stampa il comando e gate umano.
- **§7 r.17** — Mai scrivere nel repo sorgente in modalità sibling/submodule (R.B1).
- **Mai modificare `.gitmodules`** fuori dal contesto del comando `git submodule add`
  (mai automatico).
- **Mai modificare `.factory-lock`** fuori da questa skill o da `vcs-handoff` (runtime).
- Backward compat: se input ha `code_path:` (singolare) e `vcs:` top-level, opera
  come v2.11 (una sola "entry").

## Estensione runtime (v2.13 candidate)

In v2.13, una skill `vcs-handoff-bootstrap` potrebbe automatizzare `git init` del
factory_dest_path se non è già un repo. Non implementato in v2.12 — l'utente lancia
`git init` manualmente dopo il bootstrap se serve. Annota nel report finale.
