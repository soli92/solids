---
skill: ctags-index-protocol
version: "1.0"
ep: EP-054
description: >
  Protocollo L1 del Code Intelligence Stack (§33). Genera e aggiorna un indice
  universal-ctags nel side-channel .ctags-state/ per lookup esatto di simboli
  (funzioni, classi, interfacce) senza consumare token LLM.
gate: code_intelligence.l1_ctags.enabled
invariants: [R.CI2, R.CI3]
---

# Skill: ctags-index-protocol

Protocollo per il layer L1 del Code Intelligence Stack (PATTERN §33.2).
Risponde a query esatte: "dove è definita `authMiddleware`?", "in quale file è dichiarata `IUserRepository`?".

## Fase 0 — Prerequisite Check

1. Verifica `code_intelligence.l1_ctags.enabled` in `factory.config.yaml`
   - Se `false` → **SKIP silenzioso**, non eseguire le fasi successive
2. Esegui `which ctags` → se non trovato: log `[L1-SKIP] universal-ctags not installed — brew install universal-ctags` e **STOP con exit 0**
3. Verifica versione: `ctags --version | grep -i universal`
   - Se output non contiene "Universal Ctags" → log `[L1-SKIP] found Exuberant Ctags (incompatible) — install universal-ctags` e **STOP con exit 0**

## Fase 1 — Generate / Update Index

**Input**: `<repo_path>` (path assoluto al repo), `<slug>` (identificatore del code_path)

**Esecuzione**:
```bash
bash tools/code-intelligence/ctags-index.sh <repo_path> <slug>
# Per update incrementale (file modificati):
bash tools/code-intelligence/ctags-index.sh <repo_path> <slug> --update
```

**Output** (side-channel — R.CI3: read-only verso repo sorgente):
```
.ctags-state/<slug>/
  tags          # indice ctags formato standard (UTF-8, LF)
  meta.json     # {"generated": "<ISO8601>", "symbols": <N>, "slug": "<slug>", "repo": "<path>"}
```

**Linguaggi indicizzati** (da `l1_ctags.languages` in config, default):
python, typescript, javascript, java, go, rust, c, cpp

**Tipi di simbolo indicizzati**:
function, class, interface, method, struct, enum, typedef, variable (solo toplevel)

**Triggering automatico**: lo step viene eseguito alla fine di ogni `/repo-sync` se `l1_ctags.enabled: true` (integrato in `repo-extraction-protocol.md`).

## Fase 2 — Query

**Input**: nome simbolo (stringa esatta) o pattern regex

**Lookup esatto (O(1))**:
```bash
grep -P "^<symbol_name>\t" .ctags-state/<slug>/tags
```

**Output per riga**:
```
auth_middleware   src/middleware.py    /^def auth_middleware(request):$/;"   f   line:42
```
Campi: `symbol TAB file TAB ex-command TAB kind TAB line:N`

**Output formattato per agente** (interpreta grep e presenta come):
```
src/middleware.py:42 [function] auth_middleware(request)
src/auth/base.py:17 [function] auth_middleware(request, next)
```

**Pattern search**:
```bash
grep -P "^auth_" .ctags-state/<slug>/tags | head -20
```

**Fallback** (R.CI5): se `.ctags-state/<slug>/tags` assente → log `[L1-FALLBACK] index not found — run: bash tools/code-intelligence/ctags-index.sh <path> <slug>`, ritorna lista vuota.

## Fase 3 — Side-channel Management

**Struttura**:
```
.ctags-state/           ← gitignored (aggiungere a .gitignore se assente)
  <slug>/
    tags                ← indice ctags
    meta.json           ← metadata generazione
```

**Gitignore**: verificare che `.ctags-state/` sia in `.gitignore`. Se assente, aggiungerlo.

**Pulizia**: `.ctags-state/` è eliminabile liberamente — rigenerabile con `ctags-index.sh`.
Non contiene dati permanenti: è un cache locale del repo sorgente.

**Multi-repo**: ogni `code_path` ha il proprio slug. Esempio:
```
.ctags-state/
  backend/          ← slug per code_path "backend"
  frontend/         ← slug per code_path "frontend"
```

## Vincoli

| Vincolo | Dettaglio |
|---|---|
| R.CI2 | Prerequisito mancante (ctags non installato, versione sbagliata) → SKIP non STOP |
| R.CI3 | Read-only verso il repo sorgente; scrive SOLO in `.ctags-state/` |
| R.CI5 | Indice assente → lista vuota + fallback message, mai crash |

## Integrazione

- Invocato da `repo-extraction-protocol.md` post-sync (se L1 enabled)
- Output consumabile direttamente con grep da qualsiasi agente
- Complementa L2 (`code-chunk-protocol`): L1 per lookup esatto, L2 per ricerca semantica
