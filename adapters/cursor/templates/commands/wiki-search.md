# Comando: /wiki-search

> Equivalente Cursor del comando Claude Code `/wiki-search` (`.claude/commands/wiki-search.md`).
> Procedura: vedi [wiki-search-protocol](mdc:.cursor/rules/skills/wiki-search-protocol.mdc).

**Sintassi**:
```
/wiki-search <query>              → ricerca ibrida (default: hybrid, top 5)
/wiki-search <query> --mode=fts   → solo full-text
/wiki-search <query> --mode=vector → solo semantica
/wiki-search <query> --top=10     → numero risultati
/wiki-search reindex              → aggiornamento incrementale indice
/wiki-search reindex --full       → full rebuild indice
/wiki-search status               → stato indice (chunk count, last updated)
```

> **Gate**: `wiki_search.enabled: true` in `factory.config.yaml`. Se `false` → no-op (R.WS2).

## Comportamento

### `/wiki-search <query>`

Invoca `tools/wiki-search/searcher.py` via [wiki-search-protocol](mdc:.cursor/rules/skills/wiki-search-protocol.mdc):
```bash
python3 -c "
import sys, os, json
sys.path.insert(0, os.path.join(os.getcwd(), 'tools', 'wiki-search'))
from searcher import HybridSearcher
s = HybridSearcher()
result = s.search('<QUERY>', top_k=<TOP_K>, mode='<MODE>')
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

Modalita': `hybrid` (vector + FTS con RRF k=60), `fts` (full-text), `vector` (embedding coseno). Fallback se indice assente: scansione lineare `wiki/` (R.WS1 garantito).

### `/wiki-search reindex`

```bash
python3 tools/wiki-search/update-index.py        # incrementale
python3 tools/wiki-search/update-index.py --full  # full rebuild
```

### `/wiki-search status`

```bash
python3 tools/wiki-search/update-index.py --stats
```

## Vincoli (R.WS1–R.WS3)

- R.WS1: fallback garantito — mai blocco per indice assente.
- R.WS2: no-op se `wiki_search.enabled: false`.
- R.WS3: ricerca read-only — solo `reindex` scrive sull'indice.

## Limitazioni Cursor

- Usare terminal Cursor per invocare gli script Python.
- Prerequisiti: `pip install lancedb sentence-transformers`.
