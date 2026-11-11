---
skill: code-chunk-protocol
version: "1.0"
ep: EP-054
description: >
  Protocollo L2 del Code Intelligence Stack (§33.3). Chunking symbol-level via
  tree-sitter: estrae funzioni, classi e interfacce come unità atomiche per
  embedding e retrieval semantico preciso.
gate: code_intelligence.l2_semantic.enabled
invariants: [R.CI2, R.CI3]
---

# Skill: code-chunk-protocol

Protocollo per il layer L2 del Code Intelligence Stack (PATTERN §33.3).
Converte file sorgente in chunk JSON a livello di simbolo, pronti per embedding
e indicizzazione in LanceDB via `index-code.py`.

## Fase 0 — Prerequisite Check

1. Verifica `code_intelligence.l2_semantic.enabled` in `factory.config.yaml`
   - Se `false` → **SKIP silenzioso**
2. Verifica `python3 -c "import tree_sitter"` → se fallisce: log `[L2-SKIP] tree-sitter not installed — pip install tree-sitter` e STOP con exit 0
3. Verifica `python3 -c "import lancedb"` → se fallisce: log `[L2-SKIP] lancedb not installed — pip install lancedb` e STOP con exit 0

## Fase 1 — Language Detection e Parse

**Input**: lista file del code_path (recursive glob, rispettando `exclude_patterns`)

**Mapping estensione → tree-sitter grammar package**:

| Estensione | Grammar package | Nodi target |
|---|---|---|
| `.py` | `tree-sitter-python` | `function_definition`, `class_definition`, `decorated_definition` |
| `.ts`, `.tsx` | `tree-sitter-typescript` | `function_declaration`, `class_declaration`, `interface_declaration`, `method_definition`, `arrow_function` (toplevel) |
| `.js`, `.jsx` | `tree-sitter-javascript` | `function_declaration`, `class_declaration`, `method_definition`, `arrow_function` (toplevel) |
| `.java` | `tree-sitter-java` | `method_declaration`, `class_declaration`, `interface_declaration`, `enum_declaration` |
| `.go` | `tree-sitter-go` | `function_declaration`, `method_declaration`, `type_declaration` |
| `.rs` | `tree-sitter-rust` | `function_item`, `impl_item`, `struct_item`, `enum_item`, `trait_item` |

**Fallback grammar**: se grammar package non installato per un linguaggio → log `[L2-SKIP] grammar not found: <lang> — pip install tree-sitter-<lang>`, skippa i file di quel linguaggio. Gli altri linguaggi vengono processati normalmente.

**File non riconosciuti** (estensione non in tabella): skip silenzioso.

## Fase 2 — Produzione Chunk JSON

**Schema chunk**:
```json
{
  "id": "<slug>:<relative_file>:<symbol_name>:<start_line>",
  "file": "src/auth/middleware.py",
  "symbol": "auth_middleware",
  "type": "function",
  "language": "python",
  "start_line": 42,
  "end_line": 67,
  "code": "def auth_middleware(request):\n    ...",
  "docstring": "Verifica il token JWT prima di ogni request autenticata."
}
```

**Estrazione docstring**: commento/docstring immediatamente precedente al nodo (entro 3 righe).
- Python: stringa letterale come primo statement del body (docstring standard)
- TypeScript/JavaScript: blocco `/** ... */` precedente alla dichiarazione
- Java: blocco `/** ... */` precedente
- Go: commento `//` precedente
- Rust: `///` o `//!` precedente

**Chunk troppo lungo** (supera `chunk_max_lines`, default 150):
- Split a metà con overlap di 10 righe
- ID: `<base_id>:part1`, `<base_id>:part2`

**Output**: JSONL (un chunk per riga) verso stdout o `--output=<file.jsonl>`

## Fase 3 — Incremental Update

**State file**: `.code-search/chunk-state/<slug>.json`
```json
{
  "files": {
    "src/auth/middleware.py": "sha256:<hash>",
    "src/models/user.py": "sha256:<hash>"
  },
  "generated": "<ISO8601>"
}
```

**Con `--incremental`**:
1. Leggi state file (se assente → full rebuild)
2. Per ogni file: calcola SHA256 → se uguale a state → skip (0 chunk emessi per quel file)
3. Per file modificati/nuovi: parse completo, emetti chunk
4. Per file eliminati: emetti marker di cancellazione `{"id": "<id>", "_delete": true}`
5. Aggiorna state file al termine

**Senza `--incremental`**: full rebuild (processa tutti i file)

## Vincoli

- **R.CI2**: grammar mancante → skip per linguaggio, non crash; exit 0 anche con skip parziali
- **R.CI3**: read-only verso repo sorgente; scrive solo `.code-search/chunk-state/`
- **R.CI5**: errore parse su file → skip file + log, continua con gli altri

## Tool di esecuzione

```bash
python3 tools/code-intelligence/chunk-code.py <repo_path> <slug> [--output=chunks.jsonl] [--incremental]
```

Output JSONL pronto per essere passato a `index-code.py`.

## Integrazione

- Invocato da `index-code.py` (che lo esegue come subprocess o legge il JSONL)
- Invocato da `/code-search reindex`
- Consumato da `wiki-search-protocol.md` §5 (source: code)
