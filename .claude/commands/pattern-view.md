---
description: Viste filtrate in sola lettura del PATTERN per profilo di adozione (minimal/standard/full).
---

# /pattern-view — Viste filtrate del PATTERN per profilo di adozione

Comando di sola lettura che filtra il PATTERN (indice `PATTERN.md` + moduli, US-319) per profilo via i tag
`<!-- profiles: ... -->` (applicati il 2026-06-08, TSK-123; mappatura in
`wiki/runbooks/adoption-profiles-runbook.md`
e scheda canonica `PATTERN §23.7`).

Capability opt-in v2.19 (EP-016, ADR-053). Read-only: non modifica MAI `PATTERN.md`.

## Sintassi

```
/pattern-view minimal      → stampa solo le sezioni taggate `minimal`
/pattern-view standard     → sezioni `standard`
/pattern-view full         → tutto (default, identico a leggere indice + moduli in ordine)
/pattern-view list         → tabella sezioni × profili (nessun corpo)
/pattern-view historical   → rimanda a PATTERN-historical.md (sezioni deprecate)
```

## Procedura (deterministica, no LLM judgment)

1. Leggi `PATTERN.md` **e i moduli elencati nella sua tabella `## Moduli`**, nell'ordine
   della tabella (§0-§11 nell'indice, §12+ nei moduli; numerazione unica). Mai un glob:
   `PATTERN-historical.md` non e' un modulo. Elenco dei file a comando:
   `python3 -c "import sys; sys.path.insert(0,'tools/lint'); from pattern_modules import pattern_files; print(*pattern_files('.'), sep='\n')"`.
   Un modulo linkato ma assente e' un WARNING nel footer, non uno skip silenzioso.
   Per ogni header `## §N — <titolo>`, cerca nella riga
   immediatamente successiva un commento `<!-- profiles: <lista-csv> -->`.
2. **Modalità degradata**: se un header non ha il tag → assumi `full` (default
   backward-compat, ADR-054 §E) e accumula un WARNING «N sezioni senza tag profilo».
3. Per `minimal|standard|full`: stampa in ordine le sole sezioni il cui tag include
   il profilo richiesto. Per le sezioni con **subset intra-sezione** (§2/§3/§5/§7/§13
   nel minimal), premetti la nota di subset dalla scheda `PATTERN §23.5`.
4. Per `list`: stampa solo la tabella `§N | titolo | profili | file`.
5. Per `historical`: stampa il sommario di `PATTERN-historical.md` (sezioni archiviate
   da TSK-126) + come consultarle.
6. Footer: conteggio sezioni mostrate / totali + eventuale WARNING tag mancanti.

## Vincoli

- **Read-only** su `PATTERN.md` e sui moduli (mai scrittura). Nessun side-effect su `wiki/log.md`.
- Single source of truth: il PATTERN resta unico; questo comando è una *vista*, non
  una copia. Mai materializzare file `PATTERN-minimal.md` ecc. (sarebbe doppia SoT, §8).
- Coerente con `/pattern-view full` ≡ contenuto integrale di indice + moduli. I moduli non
  sono viste: sono la sede unica delle sezioni §12+ (la tabella §Moduli dice dove sta §N).

## Cross-link

- Mappatura profili + decisione: `wiki/runbooks/adoption-profiles-runbook.md`
- PATTERN §23.5 (scheda profili) + §23 (Complexity Budget) — ADR-052/053/054.
- EP-017 PATTERN-in-1-pagina (TSK-131): il profilo `minimal` ne è la base.
