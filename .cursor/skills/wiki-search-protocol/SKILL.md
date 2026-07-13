# Skill: Wiki Search Protocol

> Adapter Cursor della skill `wiki-search-protocol` definita in PATTERN.md.

Metadata skill (originale):
```yaml
id: wiki-search-protocol
version: v2.28
layer: docs
requires: wiki_search.enabled
```

**Versione:** v2.28 | **Invocabile da:** [wiki-query](mdc:.cursor/rules/wiki-query.mdc), [product-manager](mdc:.cursor/rules/product-manager.mdc), [lead-architect](mdc:.cursor/rules/lead-architect.mdc), [tpm](mdc:.cursor/rules/tpm.mdc), [wiki-lint](mdc:.cursor/rules/wiki-lint.mdc)
**Scope:** read-only — questa skill non scrive sull'indice (invariante R.WS3)

Contratto di interfaccia thin-skill per la ricerca semantica ibrida sul wiki (EP-042,
opt-in). Nessuna logica di implementazione in questa skill: quella vive in
`tools/wiki-search/searcher.py` (`HybridSearcher.search`).

Segue il pattern thin-skill del framework (cfr. [wiki-keeper-worker-protocol](mdc:.cursor/skills/wiki-keeper-worker-protocol/SKILL.md),
[parallel-scheduling](mdc:.cursor/skills/parallel-scheduling/SKILL.md)): definisce input / output / precondizioni / post-condizioni.

---

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

## Cross-link

- `tools/wiki-search/searcher.py` — implementazione `HybridSearcher` (EP-042, TSK-312)
- [wiki-query](mdc:.cursor/rules/wiki-query.mdc) §Wiki Search Enhancement — primo consumatore della skill
- `factory.config.yaml` blocco `wiki_search:` — configurazione del layer (TSK-319)
- `PATTERN.md §31` — Hybrid Wiki Search Layer (TSK-320)
- `wiki/runbooks/wiki-search-installation.md` — prerequisiti installazione indice
