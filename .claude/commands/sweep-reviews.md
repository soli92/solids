---
description: Pass di qualità SEMANTICA su wiki/ — risolve (con gate) claim non supportati, wikilink dangling e deriva terminologica. Loop bounded, gated, opt-in. EP-056.
---

Invoca l'agente `wiki-keeper` via `Agent` in modalità sweep-reviews. Procedura: vedi
skill `sweep-reviews-protocol`.

## Gate di attivazione (precondizione assoluta)

Leggi `factory.config.yaml`:

```
SE wiki_sweep.enabled == false (default R.P3):
  STOP — non invocare l'agente, nessun side-effect. Emetti in chat:
    "sweep-reviews non abilitato. Aggiungi `wiki_sweep.enabled: true` in
     factory.config.yaml (PATTERN §35, EP-056)."
```

Il fail è sempre esplicito, mai silenzioso.

## Argomenti

- Nessun argomento → scan completo di `wiki/**` (escluso log/query/lint/decisions).
- `--categories=<lista>` → restringe le categorie (override one-shot di `wiki_sweep.categories`).
- `--confidence-min=<float>` → override one-shot della soglia.

## Natura (distinta da /heal e /review)

- `/heal` corregge ERROR **meccanici** (whitelist deterministica, no inferenza) — always-on.
- `/review` (CQRL) valuta il **codice** — gated da `code_quality.enabled`.
- `/sweep-reviews` risolve problemi **semantici** della **wiki** con inferenza gated — questo comando.

## Output

Per ogni iterazione (max `wiki_sweep.max_iterations`, default 3), l'agente mostra un diff
semantico aggregato con `confidence` per item e attende `yes`/`no` (gate bulk). Se `yes`,
applica via `## Aggiornamenti (vYYYY-MM-DD)` (mai in-place come heal), stub o gap, poi
ri-scansiona i file impattati. Termina su `closed | stuck | regression | empty-diff |
user-rejected | no-items | max-iterations`. Append a `wiki/log.md` (template `sweep`).

## Regole assolute

- **Mai auto-apply senza gate** (inferenza semantica supervisionata).
- **Mai risolvere `## Contradictions`** (§10 invariante) né toccare `## Storie collegate` (PM).
- `terminology-drift` richiede `wiki/purpose.md` (EP-055); se assente → item skippato.
- Foundation read-only su EP-042/EP-054 (stability window).
