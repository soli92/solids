---
description: Risponde a una domanda NL leggendo solo wiki/. Flag --ephemeral per non salvare.
---

Se `wiki_search.enabled: true` in `factory.config.yaml`, prima di invocare l'agente cerca le pagine
pertinenti con l'indice full-text della wiki (a flag spento salta il passo: R.WS2, nessuna
directory `.wiki-search/` creata):

```bash
python3 tools/wiki-search/fts_index.py search "<domanda>" --top 8 --json --refresh
```

L'indice si costruisce da solo alla prima ricerca (pochi secondi). Se il comando fallisce, prosegui senza.

Invoca l'agente `wiki-query` via `Agent`, passando la domanda e, se la ricerca ha prodotto risultati,
l'elenco JSON delle pagine trovate (path, sezione, snippet): l'agente le legge per prime.

Default: la risposta viene salvata in `wiki/query/YYYY-MM-DD-<slug>.md`.
Con `--ephemeral`: rispondi solo in chat, nessuna scrittura su disco (l'entry su `wiki/log.md` viene comunque appesa).

Regola assoluta: rispondi SOLO da `wiki/`. Se l'informazione non c'è, dillo esplicitamente e suggerisci un ingest dei raw che la coprirebbero. Mai inventare citazioni.

Se la risposta è candidata a essere ri-asked → proponi di promuoverla a `wiki/syntheses/<question-slug>.md`.
