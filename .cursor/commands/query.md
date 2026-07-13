---
description: Risponde a una domanda NL leggendo solo wiki/. Flag --ephemeral per non salvare.
---

Invoca l'agente [wiki-query](mdc:.cursor/rules/wiki-query.mdc) via `Agent`, passando la domanda come argomento.

Default: la risposta viene salvata in `wiki/query/YYYY-MM-DD-<slug>.md`.
Con `--ephemeral`: rispondi solo in chat, nessuna scrittura su disco (l'entry su `wiki/log.md` viene comunque appesa).

Regola assoluta: rispondi SOLO da `wiki/`. Se l'informazione non c'è, dillo esplicitamente e suggerisci un ingest dei raw che la coprirebbero. Mai inventare citazioni.

Se la risposta è candidata a essere ri-asked → proponi di promuoverla a `wiki/syntheses/<question-slug>.md`.
