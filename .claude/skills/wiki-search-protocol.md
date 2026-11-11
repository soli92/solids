---
id: wiki-search-protocol
version: v2.29
layer: docs
requires: wiki_search.enabled
description: Contratto thin-skill per la ricerca semantica ibrida vector+FTS+RRF sul wiki (EP-042, opt-in). Definisce input, output e precondizioni; logica implementata in tools/wiki-search/searcher.py. Sola lettura (R.WS3).
---

# Skill: wiki-search-protocol

**Versione:** v2.29 (ADR-C, TSK-504) | **Invocabile da:** wiki-query, product-manager, lead-architect, tpm, wiki-lint
**Scope:** read-only — questa skill non scrive sull'indice (invariante R.WS3)

Contratto di interfaccia thin-skill per la ricerca semantica ibrida sul wiki (EP-042,
opt-in). Nessuna logica di implementazione in questa skill: quella vive in
`tools/wiki-search/searcher.py` (`HybridSearcher.search`).

Segue il pattern thin-skill del framework (cfr. `wiki-keeper-worker-protocol.md`,
`parallel-scheduling.md`): definisce input / output / precondizioni / post-condizioni.

---

## Backend `fts5` (default senza dipendenze)

`wiki_search.backend` (`auto` | `fts5` | `hybrid`) sceglie il motore. Con `auto` si usa `hybrid`
solo se `lancedb` e `sentence_transformers` sono importabili, altrimenti `fts5`. Con `fts5`:

- `HybridSearcher.search()` delega a `tools/wiki-search/fts_index.py` e restituisce lo stesso
  formato `{results, fallback}`; `mode` e' ignorato, `filters` accetta `section` e `status`.
- La precondizione sull'indice `index.lance` non si applica: l'indice e' `.wiki-search/fts.sqlite`
  e, se manca, la prima ricerca lo costruisce (pochi secondi).
- CLI diretta, utile a un agente con Bash:
  `python3 tools/wiki-search/fts_index.py search "<query>" --top 5 --json`.
- Il `score` e' BM25 (piu' alto = piu' rilevante) e non e' confrontabile con quello RRF di `hybrid`.
- Gli step 1-4 sotto descrivono il percorso `hybrid`; con `fts5` lo Step 1 e' sempre "available"
  e il fallback lineare (Step 4) scatta solo se SQLite non ha il modulo FTS5.

## Input

| Parametro | Tipo | Obbligatorio | Default | Descrizione |
|---|---|---|---|---|
| `query` | string | si | — | Testo libero in linguaggio naturale da cercare nel wiki |
| `mode` | enum | no | `hybrid` | Modalita' di ricerca: `hybrid` (vector+FTS con RRF) \| `fts` (solo full-text) \| `vector` (solo embedding) |
| `filters` | dict | no | `{}` | Filtri su metadati frontmatter, push-down pre-rerank. Es. `{"type": "concept"}`, `{"status": "approved"}` |
| `top_k` | intero | no | da `wiki_search.top_k` in `factory.config.yaml` (default `5`) | Numero di risultati da restituire |

---

## Output

**Caso nominale** (indice disponibile, `wiki_search.enabled: true`):

```json
{
  "results": [
    {
      "path":    "wiki/concepts/example.md",
      "title":   "Example Concept",
      "section": "## Sezione rilevante",
      "score":   0.87,
      "snippet": "~200 caratteri attorno al miglior match FTS nel content",
      "type":    "concept",
      "status":  "approved"
    }
  ],
  "fallback": false
}
```

**Caso fallback** (precondizione non soddisfatta — vedi `## Precondizione`):

```json
{
  "results": [],
  "fallback": true
}
```

I risultati sono ordinati per `score` decrescente (R.WS3 post-condizione).

---

## Precondizione

La skill e' invocabile solo se **entrambe** le seguenti condizioni sono vere:

1. `factory.config.yaml` contiene `wiki_search.enabled: true`
2. La directory `.wiki-search/index.lance` esiste al root del repo

Se anche solo una condizione non e' soddisfatta → l'implementazione ritorna
`{"results": [], "fallback": True}` senza errori (R.WS1 — fallback garantito).

**L'agente chiamante deve gestire il fallback** passando alla scansione lineare
esistente. Nessuna risposta all'utente viene bloccata per mancanza dell'indice.

---

## Post-condizione

- I risultati in `results[]` sono ordinati per `score` decrescente.
- Nessuna scrittura sull'indice e' avvenuta durante l'invocazione (R.WS3 — read-only).
- Il campo `fallback` e' sempre presente nella risposta (`true` o `false`).

---

## Procedura (4 step)

### Step 1 — Check index

Verifica la disponibilita' dell'indice prima di qualsiasi altra operazione:

```bash
python3 -c "
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'tools', 'wiki-search'))
from searcher import HybridSearcher
s = HybridSearcher()
print('available' if s.is_available() else 'fallback')
"
```

| Output | Azione |
|---|---|
| `available` | Procedi a Step 2 |
| `fallback` | Salta a Step 4 (fallback lineare) |
| errore di esecuzione | Salta a Step 4 (R.WS1) |

`HybridSearcher.is_available()` ritorna `False` se `wiki_search.enabled: false` in
`factory.config.yaml`, se `.wiki-search/index.lance` e' assente, se `lancedb` non e'
installato, o se la tabella `pages` non e' presente nell'indice.

### Step 2 — Query ibrida

Invoca `HybridSearcher.search(query, mode, top_k, filters)`:

```bash
python3 -c "
import sys, os, json
sys.path.insert(0, os.path.join(os.getcwd(), 'tools', 'wiki-search'))
from searcher import HybridSearcher
s = HybridSearcher()
result = s.search('<QUERY>', top_k=5, mode='hybrid', filters=None)
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

**Modalita' disponibili:**

- `hybrid` (default) — combina ricerca vettoriale (embedding coseno) e full-text (FTS
  tantivy / scan TF fallback) con Reciprocal Rank Fusion (RRF k=60). Restituisce la
  migliore copertura semantica + lessicale.
- `fts` — solo full-text, senza embedding. Piu' veloce, meno sensibile a parafrasi.
- `vector` — solo embedding semantico. Utile per query concettuali senza termini esatti.

**Filtri frontmatter** (push-down pre-rerank, opzionale):

```python
filters = {"type": "concept"}          # solo pagine concept
filters = {"status": "approved"}       # solo pagine approvate
filters = {"type": "concept", "status": "approved"}  # AND logico
```

La risposta `result["results"]` contiene al piu' `top_k` oggetti `{path, title, section,
score, snippet, type, status}`. Se `result["fallback"] == True` procedi a Step 4.

### Step 3 — Context injection

Inietta i risultati top-K nel contesto LLM **prima** della fase di sintesi, nel formato:

```
---
Wiki search results (top-5 by relevance):
1. wiki/concepts/example.md §Sezione rilevante — snippet del contenuto (~200 char)
2. wiki/entities/tool.md §Panoramica — snippet del contenuto
3. ...
---
```

**Regola di lettura full-page**: per i risultati con `score > 0.7` leggi la pagina
completa via `Read` prima della sintesi — il snippet da 200 caratteri e' orientativo,
il contenuto integrale migliora la qualita' della risposta.

**Regola di citazione** (PATTERN §7 citation-rules): nella risposta all'utente cita le
pagine wiki (`wiki/path/to/page.md`), mai i concept diretti. Citazione cascade:
risposta → pagina wiki → TSK/ADR che la fonda.

### Step 4 — Fallback

Se `HybridSearcher.is_available() == False` oppure `wiki_search.enabled: false` in
`factory.config.yaml`, oppure il risultato della query ha `fallback: True`:

**Invariante R.WS1**: salta alla scansione lineare esistente dell'agente (`Glob wiki/**/*.md`
+ lettura selettiva per pertinenza). Il comportamento e' identico a pre-EP-042 — nessuna
risposta bloccata per mancanza di indice.

Non emettere WARNING o ERROR verso l'utente per l'assenza dell'indice. Il fallback e'
silenzioso e trasparente.

---

## Errori comuni

| Condizione | Causa probabile | Azione |
|---|---|---|
| `available` ma `results: []` | Query troppo specifica o nessuna pagina nel wiki | Procedi con scansione lineare (Step 4) |
| `ModuleNotFoundError: lancedb` | `lancedb` non installato | `fallback: True` → scansione lineare (R.WS1) |
| `ModuleNotFoundError: sentence_transformers` | Modello embedding non installato | `fallback: True` per mode=hybrid/vector; `fts` ancora disponibile |
| `index.lance` non trovato | `/wiki-search-index` non ancora costruito | Eseguire `/wiki-search-index` per costruire l'indice; intanto scansione lineare |
| `wiki_search.enabled: false` | Flag opt-in disattivato | Comportamento pre-EP-042 (R.WS1 + R.WS2: opt-in obbligatorio) |
| Score tutti bassi (< 0.3) | Wiki esiguo o query non in lingua wiki | Usa Step 4 fallback, segnala all'utente che i risultati potrebbero essere incompleti |

---

## Invarianti

| Invariante | Descrizione |
|---|---|
| **R.WS1** | Fallback garantito: indice assente / `enabled: false` / import fail → `{"results": [], "fallback": True}`. Mai bloccare una risposta per mancanza di indice. |
| **R.WS2** | Opt-in obbligatorio: la skill e' no-op se `wiki_search.enabled: false` (default). Nessuna ricerca ibrida senza consenso esplicito. |
| **R.WS3** | Read-only: nessun write sull'indice durante la query. L'indice e' aperto in sola lettura da `HybridSearcher`. |

---

## §4 — Chunking strategy (ADR-C, TSK-504, EP-042 Phase 2)

Il campo `wiki_search.chunking` in `factory.config.yaml` controlla l'algoritmo
di spezzamento dei documenti wiki in chunk prima dell'embedding:

```yaml
wiki_search:
  chunking: h2_section   # default, backward compat
  # chunking: ast_aware  # ADR-C: rispetta code fence per .md, tree-sitter per codice
```

| Valore | Descrizione | Dep |
|---|---|---|
| `h2_section` | Split su heading H2 (comportamento originale EP-042). Default. | nessuna |
| `ast_aware` | Rispetta i boundary di code fence (`` ``` `` e `~~~`) nei file `.md` (R.WS1): non spezza mai un chunk a metà fence. Per file `.py/.ts/.go/.rs` usa tree-sitter per estrarre boundary function/class (EP-054 L2). Fallback silente a `h2_section` se tree-sitter non disponibile (R.WS1). | tree-sitter (opz.) |

**Regole d'uso:**
- `chunking: h2_section` (default) — nessun requisito aggiuntivo, backward compat totale.
- `chunking: ast_aware` — consigliato per wiki con molti runbook contenenti code block lunghi.
  Richiede reindex (`/wiki-search reindex --full`) dopo aver cambiato il valore.
- Invariante R.WS1: se tree-sitter non e' installato, `ast_aware` degrada silenziosamente
  a `h2_section` senza errori verso l'utente o verso l'indice.
- Il campo `section` nel risultato di ricerca puo' diventare piu' granulare con `ast_aware`
  (es. `def my_func` invece di nome heading H2) ma il tipo resta `string` (schema invariato).

La strategia viene letta da `HybridSearcher.__init__` (campo `self._chunking_strategy`) e
passata a `WikiIndexer(chunking_strategy=...)` al momento del build index.

## Cross-link

- `tools/wiki-search/searcher.py` — implementazione `HybridSearcher` (EP-042, TSK-312)
- `tools/wiki-search/indexer.py` — `chunk_ast_aware`, `chunk_document` (ADR-C, TSK-504)
- `tools/wiki-search/tests/test_chunking.py` — test AC4 (fence non spezzata) + AC5 (fallback silente)
- `.claude/agents/wiki-query.md` §Wiki Search Enhancement — primo consumatore della skill
- `factory.config.yaml` blocco `wiki_search:` — configurazione del layer (TSK-319)
- `PATTERN.md §31` — Hybrid Wiki Search Layer (TSK-320)
- `wiki/runbooks/wiki-search-installation.md` — prerequisiti installazione indice
- `wiki/decisions/tavola-rotonda-TR-qmd-20260902-2026-09-02.md` — ADR-C (anchor TSK-504)

---

## §5 — Source: code (EP-054, v2.37, L2 Code Intelligence)

Estensione del protocollo per indicizzare e cercare chunk di codice symbol-level
estratti via tree-sitter (vedi `code-chunk-protocol.md`). Attiva solo se
`code_intelligence.l2_semantic.enabled: true` in `factory.config.yaml`.

### §5.1 — Attivazione

```yaml
# in factory.config.yaml
code_intelligence:
  enabled: true
  l2_semantic:
    enabled: true
    embedding_model: nomic-embed-code
    lancedb_path: .code-search/index.lance
```

Se disabilitato → source `code` non disponibile; `/code-search` mostra messaggio guida.
Fallback garantito (R.CI5): indice assente o corrotto → lista vuota + `fallback: true`, mai crash.

### §5.2 — Tabella LanceDB separata

| Aspetto | source: wiki (EP-042) | source: code (EP-054) |
|---|---|---|
| Tabella LanceDB | `wiki_chunks` | `code_chunks` |
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) | `nomic-embed-code` (768-dim) |
| Chunking | H2-section markdown | symbol-level tree-sitter |
| Indice path | `.wiki-search/index.lance` | `.code-search/index.lance` |

**IMPORTANTE**: i vettori delle due tabelle NON sono cross-compatibili (modelli distinti,
dimensioni diverse). Le query cross-source usano RRF (Reciprocal Rank Fusion) per mergiare
result list, non cosine similarity diretta sui vettori.

### §5.3 — Query Routing

| Comando | Source interrogata | Output |
|---|---|---|
| `/wiki-search <query>` | `wiki_chunks` (invariato EP-042) | chunk wiki ranked |
| `/code-search <query>` | `code_chunks` | chunk codice ranked |
| `/code-search <query> --all` | `wiki_chunks` + `code_chunks` (RRF merge) | output unificato con campo `source` |

Il routing e' determinato dal comando, non dalla query — nessuna detection automatica del tipo di query.

### §5.4 — Output Formato

Ogni risultato source:code:
```
src/auth/middleware.py:42 [function] auth_middleware — score:0.91
src/auth/base.py:17    [class]    AuthBase — score:0.87
```

Campi: `file:start_line [type] symbol — score:N`

Con `--all` (merge wiki + code):
```
[code] src/auth/middleware.py:42 [function] auth_middleware — score:0.91
[wiki] wiki/architecture/auth.md#JWT-Handling — score:0.85
[code] src/models/user.py:103   [class]    User — score:0.82
```

### §5.5 — Reindex

```bash
# Via comando (recommended)
/code-search reindex              # incrementale (solo file cambiati)
/code-search reindex --full       # full rebuild per tutti i slug
/code-search reindex --slug=api   # rebuild per slug specifico

# Via script diretto
python3 tools/code-intelligence/chunk-code.py <repo_path> <slug> --output=chunks.jsonl
python3 tools/code-intelligence/index-code.py chunks.jsonl <slug>
```

Trigger automatico post `/repo-sync` se `l2_semantic.enabled: true`.

### §5.6 — Integrazione con L1 (ctags)

L1 e L2 sono complementari, non sostitutivi:

| Query | Layer consigliato |
|---|---|
| "dove e' definita `auth_middleware`?" (simbolo esatto) | L1 ctags (O(1), ms) |
| "dove viene gestita l'autenticazione JWT?" (semantica) | L2 `/code-search` |
| "cosa si rompe se cambio `UserService`?" (impact) | L3 `graphify affected` |

Per query miste: L1 prima (zero token, millisecondi) → se non trovato → L2.
