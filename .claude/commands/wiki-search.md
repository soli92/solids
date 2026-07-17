---
id: wiki-search
version: v2.28
requires: wiki_search.enabled
description: Ricerca ibrida nel wiki (semantic + FTS) tramite HybridSearcher. Bypassa wiki-query per testing diretto dell'indice. Sub-comandi reindex e status per gestione indice.
---

Comando della capability [[hybrid-wiki-search-capability]] (EP-042, opt-in). Invoca
`HybridSearcher` direttamente — bypassa l'agente [wiki-query](mdc:.cursor/rules/wiki-query.mdc) e la sintesi LLM. Utile
per testare l'indice in isolamento, debug di query, e aggiornamento dell'indice.

## Sintassi

```
/wiki-search <query>                  # ricerca ibrida (default: hybrid mode, top 5)
/wiki-search <query> --mode=fts       # solo full-text (senza embedding)
/wiki-search <query> --mode=vector    # solo semantica (embedding coseno)
/wiki-search <query> --top=10         # numero risultati (default: 5)
/wiki-search reindex                  # aggiornamento incrementale dell'indice
/wiki-search reindex --full           # full rebuild (drop + re-index completo)
/wiki-search status                   # stato indice: chunk count, last updated
```

## Gate

Se `wiki_search.enabled: false` in `factory.config.yaml` (default opt-in) → il comando
e' **no-op** (R.WS2): mostra in chat:

```
wiki-search e' disabilitato.
Attiva con: wiki_search.enabled: true in factory.config.yaml
Vedi PATTERN §31 e wiki/runbooks/wiki-search-installation.md per i prerequisiti.
```

Nessuna altra azione viene eseguita. Il comando non blocca altri flussi.

## Sotto-comandi

### `/wiki-search <query> [--mode=hybrid|fts|vector] [--top=N]`

Ricerca diretta nell'indice LanceDB senza passare dall'agente `wiki-query`.

**Step 1 — Check gate config**

Legge `factory.config.yaml.wiki_search.enabled`. Se `false` → no-op (vedi §Gate).

**Step 2 — Check indice**

Verifica che `.wiki-search/index.lance` esista al root del repo. Se assente → mostra:

```
Indice non disponibile — esegui /wiki-search reindex per costruirlo.
```

**Step 3 — Invoca HybridSearcher**

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

Sostituire `<QUERY>`, `<TOP_K>` (default 5), `<MODE>` (`hybrid` | `fts` | `vector`).

**Step 4 — Output formattato**

Se `result["fallback"] == false` e `result["results"]` non e' vuoto:

```
Wiki search: "<query>" — N risultati (<mode> mode)

1. wiki/decisions/ADR-055.md §Performance Budget — score 0.87
   "Il complexity budget N:1 = n:3→5 implica..."

2. wiki/concepts/example.md §Panoramica — score 0.74
   "Il framework adotta un approccio incrementale..."

3. ...
```

Ogni riga di risultato contiene: `<path> §<section> — score <float>` + snippet (~200 char).

Se `result["fallback"] == true`:

```
Ricerca non disponibile (fallback attivo).
Cause possibili: lancedb non installato, modello embedding assente,
indice corrotto. Esegui /wiki-search status per diagnostica.
```

Se `result["results"] == []` con `fallback: false`:

```
Nessun risultato per "<query>" (mode: <mode>).
Suggerimento: prova --mode=fts per ricerca solo lessicale,
oppure /wiki-search reindex se il wiki e' stato aggiornato di recente.
```

**Modalita' disponibili (`--mode`)**

| Modalita' | Algoritmo | Quando usarla |
|---|---|---|
| `hybrid` (default) | vector + FTS con RRF k=60 | Query generali — massima copertura semantica + lessicale |
| `fts` | Full-text (tantivy / scan TF fallback) | Query con termini esatti, senza embedding |
| `vector` | Embedding coseno (paraphrase-multilingual-MiniLM-L12-v2) | Query concettuali senza match lessicale |

**Nota**: questo sotto-comando bypassa `wiki-query` — utile per testare l'indice in
isolamento senza la sintesi LLM dell'agente (US-150 AC5). Per una risposta sintetizzata
sul contenuto del wiki usa `/query <domanda>`.

---

### `/wiki-search reindex [--full]`

Aggiorna l'indice LanceDB con le modifiche al wiki.

**Senza `--full` (default — aggiornamento incrementale)**

Invoca `tools/wiki-search/update-index.py` che legge `.wiki-search/index_state.json`
per rilevare quali file `.md` in `wiki/` sono stati aggiunti, modificati o rimossi
dall'ultimo run, e re-indicizza solo quelli.

```bash
python3 tools/wiki-search/update-index.py
```

Output atteso:

```
wiki-root  : <repo>/wiki
index-path : <repo>/.wiki-search/index.lance
state-file : <repo>/.wiki-search/index_state.json

Updated 12 chunks (8 added, 3 deleted, 47 unchanged) in 4.2s
  files: +2 added, ~1 modified, -0 removed
```

Se lo state file non esiste (primo run o dopo `rm .wiki-search/`), il comando esegue
automaticamente un full rebuild e crea lo state file.

**Con `--full` (full rebuild)**

Invoca `tools/wiki-search/update-index.py --full` che esegue drop + re-index completo
di tutta la directory `wiki/`.

```bash
python3 tools/wiki-search/update-index.py --full
```

Output atteso:

```
wiki-root  : <repo>/wiki
index-path : <repo>/.wiki-search/index.lance
model      : paraphrase-multilingual-MiniLM-L12-v2

Updated 423 chunks (423 added, 0 deleted, 0 unchanged) in 38.7s
  files: +87 added (full rebuild), 0 removed
```

Equivalente documentato in EP-042 §Design Tecnico: `build-index.py --rebuild` produce
lo stesso risultato del full rebuild via `update-index.py --full`.

**Quando usare `--full`**

- Cambio del modello embedding in `factory.config.yaml.wiki_search.embedding_model`
- Cambio del chunking strategy in `indexer.py`
- Indice corrotto o inconsistente (verificato via `/wiki-search status`)
- Prima sincronizzazione dopo aver attivato `wiki_search.enabled: true`

---

### `/wiki-search status`

Mostra lo stato corrente dell'indice senza eseguire ricerche.

Invoca `tools/wiki-search/update-index.py --stats` e legge
`.wiki-search/index_state.json` per le informazioni di stato.

```bash
python3 tools/wiki-search/update-index.py --stats
```

Output formattato in chat:

```
WIKI SEARCH INDEX STATUS
========================
index-path : .wiki-search/index.lance
state-file : .wiki-search/index_state.json
rows       : 423 chunks
tracked    : 87 files

Ultimo aggiornamento: <mtime di index_state.json>
Modello embedding  : paraphrase-multilingual-MiniLM-L12-v2 (da factory.config.yaml)
```

Se l'indice non esiste ancora:

```
WIKI SEARCH INDEX STATUS
========================
index-path : .wiki-search/index.lance — NON TROVATO
state-file : .wiki-search/index_state.json — NON TROVATO

Esegui /wiki-search reindex per costruire l'indice.
Prerequisiti: vedi wiki/runbooks/wiki-search-installation.md
```

Per leggere il `mtime` dello state file:

```bash
python3 -c "
import os, datetime
p = '.wiki-search/index_state.json'
if os.path.exists(p):
    t = os.path.getmtime(p)
    print(datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S'))
else:
    print('not found')
"
```

## Prerequisiti

- `wiki_search.enabled: true` in `factory.config.yaml` (default: `false`, opt-in R.WS2)
- `lancedb` installato: `pip install lancedb`
- `sentence-transformers` installato: `pip install sentence-transformers`
- Indice costruito: almeno un run di `/wiki-search reindex` completato con successo
- Python 3.9+ con `pyyaml` disponibile (usato per leggere `factory.config.yaml`)

Vedi `wiki/runbooks/wiki-search-installation.md` per la guida completa all'installazione.

## Idempotenza

- `/wiki-search reindex` e' idempotente: se nessun file e' cambiato dall'ultimo run →
  «Nessuna modifica rilevata — indice gia' aggiornato» (zero scritture sull'indice).
- `/wiki-search status` e' read-only, sempre idempotente.
- La ricerca (`/wiki-search <query>`) e' read-only (R.WS3): nessuna modifica all'indice.

## Vincoli (EP-042, R.WS1–R.WS3)

- **R.WS1** — Fallback garantito: indice assente / `enabled: false` / import fail →
  risposta vuota senza errori bloccanti. Nessuna risposta utente e' mai bloccata per
  mancanza dell'indice.
- **R.WS2** — Opt-in obbligatorio: questo comando e' no-op se `wiki_search.enabled: false`.
  Il comportamento pre-EP-042 (scansione lineare `wiki/`) e' invariato.
- **R.WS3** — Read-only durante la ricerca: `HybridSearcher.search()` non scrive mai
  sull'indice. Solo `reindex` e' un'operazione di scrittura.
- Il comando non scaffolda se `wiki_search.enabled` e' assente o `false` nelle factory
  derivate; resta disponibile come file ma e' no-op (coerente con tutti i comandi opt-in).

## Logging

Il sotto-comando `reindex` appende a `wiki/log.md` una entry nel formato canonico:

```
[YYYY-MM-DD HH:MM] wiki-search reindex [--full] → N chunks updated (A added, D deleted)
```

I sotto-comandi `status` e la ricerca diretta non producono entry in `wiki/log.md`
(operazioni leggere / diagnostiche).

## Cross-link

- `tools/wiki-search/searcher.py` — implementazione `HybridSearcher` (EP-042, TSK-312)
- `tools/wiki-search/update-index.py` — CLI incrementale (EP-042, TSK-315)
- [wiki-search-protocol](mdc:.cursor/skills/wiki-search-protocol/SKILL.md) — contratto thin-skill per agenti (TSK-318)
- [wiki-query](mdc:.cursor/rules/wiki-query.mdc) §Wiki Search Enhancement — agente che usa la skill
- `factory.config.yaml` blocco `wiki_search:` — configurazione del layer (TSK-319)
- `PATTERN.md §31` — Hybrid Wiki Search Layer (TSK-320)
- `wiki/runbooks/wiki-search-installation.md` — prerequisiti installazione
