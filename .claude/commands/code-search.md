---
command: code-search
version: v2.36
requires: code_intelligence.l2_semantic.enabled
description: "Ricerca semantica L2 su indice codice symbol-level (EP-054, PATTERN §33.3). Richiede code_intelligence.l2_semantic.enabled: true."
---

Comando della capability Code Intelligence Index (EP-054, opt-in). Invoca
`tools/code-intelligence/query-code.py` direttamente — ricerca semantica su
indice LanceDB `code_chunks` (tree-sitter chunking + nomic-embed-code embeddings).
Complementa `/wiki-search` per query su codice symbol-level.

## Sintassi

```
/code-search <query>                              # ricerca semantica (top 5 default)
/code-search <query> --top=<N>                   # top N risultati (max 20)
/code-search <query> --lang=<language>           # filtra per linguaggio (python|typescript|java|go|rust)
/code-search <query> --type=<type>               # filtra per tipo (function|class|interface|method|struct)
/code-search <query> --all                       # merge con wiki_search (RRF)
/code-search reindex [--full] [--slug=<name>]    # ricostruisce indice
/code-search status                              # stato indice e config
```

## Gate

Se `code_intelligence.l2_semantic.enabled: false` in `factory.config.yaml` (default opt-in) →
il comando e' **no-op** (R.CI2): mostra in chat:

```
[L2] Code search non abilitato.
Per abilitare:
  1. Installa dipendenze: pip install tree-sitter sentence-transformers lancedb
  2. Imposta code_intelligence.l2_semantic.enabled: true in factory.config.yaml
  3. Costruisci l'indice: /code-search reindex
Vedi: wiki/runbooks/code-intelligence.md
```

Nessuna altra azione viene eseguita. Il comando non blocca altri flussi.

## Sotto-comandi

### `/code-search <query> [--top=N] [--lang=<lang>] [--type=<type>]`

Ricerca semantica diretta sull'indice `code_chunks`.

**Step 1 — Check gate config**

Legge `factory.config.yaml.code_intelligence.l2_semantic.enabled`. Se `false` → no-op (vedi §Gate).

**Step 2 — Check indice**

Verifica che `.code-search/index.lance` esista al root del repo. Se assente → mostra:

```
[L2-FALLBACK] index not found — run /code-search reindex
```

**Step 3 — Invoca query-code.py**

```bash
python3 tools/code-intelligence/query-code.py "<query>" \
  --top=<N> \
  [--lang=<lang>] \
  [--type=<type>] \
  --db=.code-search/index.lance
```

Sostituire `<query>`, `<N>` (default 5, max 20), `<lang>` e `<type>` se forniti.

**Step 4 — Output formattato**

Se risultati presenti:

```
src/auth/middleware.py:42   [function] auth_middleware — 0.91
src/auth/base.py:17         [class]    AuthBase — 0.87
src/views/protected.py:8    [function] protected_view — 0.84
```

Ogni riga contiene: `<file>:<line>   [<type>] <symbol> — <score>`.

Se nessun risultato:

```
[L2] No results found for "<query>"
Suggerimento: prova senza filtri --lang/--type, oppure
/code-search reindex se il codice e' stato aggiornato di recente.
```

**Parametri**

| Parametro | Default | Descrizione |
|---|---|---|
| `--top=N` | 5 | Numero risultati (max 20) |
| `--lang=<lang>` | — | Filtra per linguaggio: `python`, `typescript`, `java`, `go`, `rust` |
| `--type=<type>` | — | Filtra per tipo simbolo: `function`, `class`, `interface`, `method`, `struct` |

**Nota**: questo sotto-comando bypassa `wiki-query` — utile per query su codice
in isolamento. Per una risposta sintetizzata sul progetto usa `/query <domanda>`.

---

### `/code-search <query> --all`

Merge cross-source: esegue `/code-search` e `/wiki-search` in parallelo, combina i
risultati via RRF (k=60).

**Esecuzione**:

```bash
# Parallelo
python3 tools/code-intelligence/query-code.py "<query>" --top=10 --json &
python3 -c "
import sys, os, json
sys.path.insert(0, os.path.join(os.getcwd(), 'tools', 'wiki-search'))
from searcher import HybridSearcher
s = HybridSearcher()
result = s.search('<query>', top_k=10, mode='hybrid')
print(json.dumps(result, ensure_ascii=False))
" &
wait
```

**Output unificato** (RRF merge):

```
[code] src/auth/middleware.py:42 [function] auth_middleware — 0.91
[wiki] wiki/architecture/auth.md#JWT — 0.85
[code] src/models/user.py:103   [class]    User — 0.82
[wiki] wiki/concepts/authentication.md#Overview — 0.79
```

Ogni riga contiene: `[<source>] <ref> — <score>`.

**Prerequisiti `--all`**: entrambe le capability abilitate (`code_intelligence.l2_semantic.enabled`
e `wiki_search.enabled`). Se una delle due e' disabilitata, esegue solo quella abilitata
con avviso.

---

### `/code-search reindex [--full] [--slug=<name>]`

Aggiorna l'indice LanceDB con le modifiche al codice.

**Senza `--full` (default — aggiornamento incrementale)**

Per ogni `code_path` configurato (o solo quello specificato da `--slug`):

```bash
python3 tools/code-intelligence/chunk-code.py <repo_path> <slug> \
  --output=/tmp/chunks-<slug>.jsonl --incremental

python3 tools/code-intelligence/index-code.py \
  /tmp/chunks-<slug>.jsonl <slug>
```

Output atteso:

```
[L2] Reindex <slug>: 47 chunks updated (12 added, 3 deleted, 32 unchanged) in 8.3s
```

**Con `--full` (full rebuild)**

```bash
python3 tools/code-intelligence/chunk-code.py <repo_path> <slug> \
  --output=/tmp/chunks-<slug>.jsonl

python3 tools/code-intelligence/index-code.py \
  /tmp/chunks-<slug>.jsonl <slug> --full-rebuild
```

Output atteso:

```
[L2] Full rebuild <slug>: 1247 chunks indexed in 42.1s
```

**Quando usare `--full`**

- Cambio del modello embedding in `factory.config.yaml.code_intelligence.embedding_model`
- Cambio della strategia di chunking in `chunk-code.py`
- Indice corrotto o inconsistente (verificato via `/code-search status`)
- Prima sincronizzazione dopo aver attivato `l2_semantic.enabled: true`

---

### `/code-search status`

Mostra lo stato corrente dell'indice senza eseguire ricerche.

```bash
python3 tools/code-intelligence/query-code.py --status \
  --db=.code-search/index.lance
```

Output formattato in chat:

```
CODE INTELLIGENCE INDEX STATUS (L2)
=====================================
index-path  : .code-search/index.lance
table       : code_chunks
rows        : 1247 chunks
slugs       : . (847), soli-boy (400)
model       : nomic-ai/nomic-embed-text-v1

Ultimo aggiornamento: 2026-07-30 14:22:07
Dimensione su disco : 18.4 MB
```

Se l'indice non esiste ancora:

```
CODE INTELLIGENCE INDEX STATUS (L2)
=====================================
index-path  : .code-search/index.lance — NON TROVATO

Esegui /code-search reindex per costruire l'indice.
Prerequisiti: vedi wiki/runbooks/code-intelligence.md
```

## Integrazione con L1 e L3

L2 (`/code-search`) e' per query semantiche — non per lookup esatti (usa L1 ctags):

```bash
# L1 — lookup esatto (simbolo noto)
grep "^<symbol>	" .ctags-state/<slug>/tags
```

Per blast radius e dependency graph: usa L3 `graphify affected` (integrato in
`dev-protocol` Fase 0.bis):

```bash
graphify affected "<symbol>" --repo=<slug>
```

## Prerequisiti

- `code_intelligence.l2_semantic.enabled: true` in `factory.config.yaml` (default: `false`, opt-in R.CI2)
- `lancedb` installato: `pip install lancedb`
- `sentence-transformers` installato: `pip install sentence-transformers`
- `tree-sitter` installato: `pip install tree-sitter`
- Indice costruito: almeno un run di `/code-search reindex` completato con successo
- Python 3.9+ con `pyyaml` disponibile (usato per leggere `factory.config.yaml`)

Vedi `wiki/runbooks/code-intelligence.md` per la guida completa all'installazione.

## Idempotenza

- `/code-search reindex` e' idempotente: se nessun file e' cambiato → zero scritture sull'indice.
- `/code-search status` e' read-only, sempre idempotente.
- La ricerca (`/code-search <query>`) e' read-only (R.CI4): nessuna modifica all'indice.

## Vincoli (EP-054, R.CI1-R.CI5)

- **R.CI1** — Isolamento layer: L1 (ctags), L2 (semantic), L3 (graphify) sono indipendenti;
  un layer disabilitato non blocca gli altri.
- **R.CI2** — Opt-in obbligatorio: il comando e' no-op se `l2_semantic.enabled: false`.
  Il comportamento pre-EP-054 (ricerca lineare) e' invariato.
- **R.CI3** — Single-writer indice: solo i tool `index-code.py` / `chunk-code.py` scrivono
  su `.code-search/`; gli agenti leggono via `query-code.py`.
- **R.CI4** — Read-only durante la ricerca: `query-code.py` non scrive mai sull'indice.
  Solo `reindex` e' un'operazione di scrittura.
- **R.CI5** — Fallback garantito: indice assente / import fail / `enabled: false` →
  messaggio `[L2-FALLBACK]` senza errori bloccanti. Nessun flusso agente e' bloccato.

## Logging

Il sotto-comando `reindex` appende a `wiki/log.md` una entry nel formato canonico:

```
[YYYY-MM-DD HH:MM] code-search reindex [--full] <slug> → N chunks updated (A added, D deleted)
```

I sotto-comandi `status` e la ricerca diretta non producono entry in `wiki/log.md`.

## Cross-link

- `tools/code-intelligence/query-code.py` — script di query LanceDB (EP-054, TSK-461)
- `tools/code-intelligence/chunk-code.py` — chunker tree-sitter (EP-054, TSK-458)
- `tools/code-intelligence/index-code.py` — indexer LanceDB (EP-054, TSK-460)
- `.claude/skills/code-search-protocol.md` — contratto thin-skill per agenti
- `factory.config.yaml` blocco `code_intelligence:` — configurazione del layer
- `PATTERN.md §33` — Code Intelligence Stack (EP-054)
- `wiki/runbooks/code-intelligence.md` — prerequisiti installazione
