---
name: heal-protocol
description: Loop evaluator-optimizer vincolato. Corregge SOLO una whitelist chiusa di ERROR meccanici flaggati `heal-eligible` dal wiki-lint, con gate umano bulk e max 3 iterazioni. Skill del wiki-keeper.
---
# Protocollo Heal (canonico)

Riferimenti: `lint-checks` (input), `citation-rules`, `wiki-log-entry`,
`PATTERN.md §3` (operazione `Heal`) + `§7 r.6` (gate STOP) + `§7 r.12`
(single-committer).

## Chi può eseguirla

**Solo il `wiki-keeper`**, su invocazione esplicita dell'umano via `/heal`.
Single-committer preservato: nessun altro agente acquisisce write access su `wiki/`.

## Whitelist (chiusa e immutabile)

L'optimizer corregge SOLO queste tre categorie. Ogni altro ERROR è esplicitamente
**rifiutato** e va lasciato all'umano.

| Categoria | Condizione di applicabilità | Correzione |
|---|---|---|
| `broken-wikilink` | esiste slug `Y` con `fuzzy(X, Y) ≥ 0.90` | sostituisci `[[X]]` → `[[Y]]` |
| `missing-frontmatter-field` | il campo è deducibile dal path (`type` da `wiki/<kind>/`, `id` da `EP-XXX/US-YYY/TSK-ZZZ`) | aggiungi il campo derivato |
| `citation-section-mismatch` | esiste header `H` nel file citato con `edit_distance(<sez>, H) ≤ 3` | sostituisci `§<sez>` → `§H` |

**Esclusi categoricamente** (mai auto-fix):

- `id-duplicate` (può rompere riferimenti esterni — rinominare richiede grep cross-repo)
- claim non citati (giudizio sulla soglia 20 parole / esenzioni)
- orphan pages (decisione: cancellare o linkare?)
- gap aperti (richiede ingest, non fix locale)
- contradiction (mai risolvere silenziosamente — §10 invariante)

## Input

- Path del lint report più recente: `wiki/lint/YYYY-MM-DD-lint-report.md`
- Frontmatter del report DEVE avere `heal_eligible_count > 0`. Se è 0 → STOP, dillo all'umano.

## Procedura (loop fino a 3 iterazioni)

### Iter 0 — Bootstrap

1. `Read` del report. Estrai sezione `## ERROR meccanici (heal-eligible)`.
2. Parse di ogni riga `[ERROR][<categoria>][heal-eligible] <path>: <descrizione>`.
3. Verifica `heal_eligible_count == numero di entry parsate`. Se mismatch → STOP, segnala discrepanza.
4. Inizializza `iter_count = 0`, `prev_error_count = +∞`.

### Per ogni iterazione N ∈ {1, 2, 3}

**A. Produzione diff (read + analyze, no write)**

1. Per ogni ERROR heal-eligible: leggi il file impattato, deriva la correzione
   secondo la whitelist. Se la correzione **non è derivabile** (es. nessun slug
   ≥ 0.90, header con edit-distance ≤ 3 non univoco) → escludi dall'iterazione.
2. Costruisci un **diff aggregato** in forma testuale (formato unified diff per
   file impattato). Niente scrittura su disco.
3. Se il diff è vuoto (nessuna correzione derivabile) → **STOP** terminale,
   logga `heal-iter-N: empty-diff`.

**B. Gate umano (STOP, bulk)**

Mostra in chat:

```
HEAL — Iter <N> / 3
====================
Categorie: <broken-wikilink: K1, missing-frontmatter: K2, citation-section: K3>
File impattati: <M>
Diff aggregato (bulk):

<unified diff>

Confermi l'applicazione? [yes/no]
```

**Attendi risposta esplicita**. `no` → STOP, logga `heal-iter-N: user-rejected`,
termina. `yes` → procedi.

> Granularità: il gate è **bulk** (un solo yes/no per l'intero diff). Per
> escludere singoli error l'umano risponde `no` e ri-esegue manualmente il lint
> dopo una correzione mirata.

**C. Applicazione**

`Edit` mirato di ogni file secondo il diff confermato. Mai `Write` (preserva il
resto del file). Nessuna sezione `## Aggiornamenti` aggiunta — la correzione è
meccanica, non semantica (eccezione locale a §7 r.7).

**D. Re-evaluator**

Invoca `wiki-lint` (via Agent) sugli stessi file impattati (lint scoped).
Attendi nuovo report.

**E. Condizioni di terminazione**

Calcola `new_error_count` = numero di ERROR heal-eligible nel nuovo report,
limitato ai file impattati nell'iter N.

| Condizione | Azione |
|---|---|
| `new_error_count == 0` | STOP **success**. Log `heal-iter-N: closed`. |
| `new_error_count >= prev_error_count` | STOP **no-progress**. Log `heal-iter-N: stuck`. |
| Nuovi ERROR non presenti in N-1 (regressione) | STOP **regression**. Log `heal-iter-N: regression`. **No rollback** del diff applicato (resta in repo). Segnala in chat l'elenco di nuovi error. |
| `N == 3` | STOP **max-iterations**. Log `heal-iter-3: budget-exhausted`. |
| Altrimenti | `iter_count += 1`, `prev_error_count = new_error_count`, vai a A. |

## Log entry (template `heal`)

Append a `wiki/log.md` **una sola entry per intero ciclo** (non per iter):

```
## [YYYY-MM-DD] heal | report=<basename> | iter=<N> | esito=<closed|stuck|regression|empty-diff|user-rejected|max-iterations>
Iter 1: applied=<K>, residual=<R>
Iter 2: applied=<K>, residual=<R>
...
File touched: <M>
```

## Idempotenza

Eseguire `/heal` due volte di fila con lo stesso input lint report DEVE produrre
lo stesso risultato:

- Iter 1 della seconda esecuzione → applied=0 (tutto già corretto) → empty-diff → STOP.

Garantito dalla whitelist deterministica (fuzzy match e edit-distance sono
funzioni pure dello stato corrente del filesystem).

## Anti-pattern (vietati)

| Anti-pattern | Perché vietato | Correzione |
|---|---|---|
| Correggere ERROR non heal-eligible | Rompe whitelist chiusa | Lascia all'umano, segnala in chat |
| Applicare diff senza gate | Viola §7 r.6 + invariante PATTERN.md §3 `Heal` | STOP obbligatorio prima di ogni iter |
| Aggiungere `## Aggiornamenti` per le correzioni heal | Correzione meccanica, non semantica — gonfia la pagina | In-place edit puro |
| Eseguire `/heal` senza report recente | Senza evaluator non c'è loop | STOP, suggerisci `/lint` prima |
| Rollback automatico su regressione | Rompe append-only di `wiki/log.md` + complica l'atomicità | STOP + segnala, l'umano decide cosa fare |
| Inferire correzioni semantiche ("forse l'utente intendeva…") | Mai inferenza di intento — whitelist deterministica | Esclude dall'iter, lascia all'umano |
| Loop > 3 iter | Bounded per costruzione | Termina con `max-iterations` |
