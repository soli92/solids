---
skill: lint-checks
leaf_of: lint-checks-wiki-structure.md
section: "wiki-structure"
description: "Check 4bf: ordine cronologico delle voci di wiki/log.md"
---

> Eseguito da `tools/lint/run-deterministic.py` (registrato in `CHECKS`).

# 4bf — Ordine delle voci di `wiki/log.md` (always-on, ERROR)

**Eseguibile, non interpretato.** Lancia lo script (copre insieme 4bf e 4bg) e riporta le sue righe così come sono:

```bash
python3 tools/lint/check_dati_derivati.py .
```

**Cosa controlla.** Il merge union di `.gitattributes` concatena le voci aggiunte in coda da due
branch: ogni lato è in ordine, l'insieme può non esserlo. Il check legge la data di ogni voce
(`date:` dei blocchi `---`, oppure `## AAAA-MM-GG` per le voci a titolo) e segnala una voce più
vecchia di oltre la tolleranza rispetto alla più recente che la precede. Entro la tolleranza lo
scarto è solo conteggiato (due chat in parallelo si sovrappongono di qualche giorno).

**Configurazione.** Nessuna chiave in `factory.config.yaml`. Opzione a riga di comando
`--tolleranza N` (giorni, default 7). Argomento posizionale: radice del repo.

**Codice e severità.** `log-ordine-rotto` (ERROR), con riga, data, voce precedente e scarto.
Exit code 0 anche con finding; con `--strict` 1 se c'è almeno un finding. `--json` per l'output
strutturato.

**Esenzioni.** Nessuna per voce; la tolleranza è l'unica soglia. Il log è append-only :
non si riordina a mano, si controlla il merge e la data della voce nuova.

**Mai `heal-eligible`.** Correggere significherebbe riscrivere il log.

**Output format:**

```
- [ERROR][log-ordine-rotto][4bf] wiki/log.md riga 120: voce del 2026-11-01 dopo una del 2026-11-09 (riga 118), 8 giorni oltre la tolleranza di 7. ...
```

[^src: tools/lint/check_dati_derivati.py]
