---
description: Genera il sito statico di documentazione tecnica dalla wiki (HTML autocontenuto, con indice, navigazione per sezione e ricerca) dopo un controllo di redazione bloccante.
argument-hint: "[--out DIR] [--sections a,b] [--dry-run]"
---

# /doc-tecnica — Sito di documentazione tecnica

Argomenti utente: `$ARGUMENTS`

Il comando non ha logica propria: esegue `tools/docs/build_tech_site.py` e riporta
l'esito. Non modifica la wiki.

Gate: se `documentation.enabled` è `false` in `factory.config.yaml` (default di questa factory) lo script stampa un messaggio ed esce con codice 0 senza generare nulla: non è un errore. Riporta il messaggio all'utente e indica come attivare la capability (`documentation.enabled: true`).

## Procedura

1. Esegui, dalla radice della factory:

   ```bash
   python3 tools/docs/build_tech_site.py $ARGUMENTS
   ```

   Senza argomenti scrive in `deliverables/doc-tecnica/<YYYY-MM-DD>/`.

2. Riporta all'utente il riepilogo stampato dallo script: pagine per sezione, tempo,
   numero di wikilink non pubblicati.
3. Se lo script esce con codice 2 (redazione), riporta l'elenco `file:riga [tipo] excerpt`
   così com'è e non aggirare il controllo e non correggere la wiki: chi la gestisce
   decide se togliere il segreto o se il finding è un falso positivo.

## Argomenti

| Flag | Effetto |
|---|---|
| `--out DIR` | cartella di output (default `<output_dir>/<data>`) |
| `--sections a,b` | solo queste sezioni (default: `documentation.tech_site.include_sections`) |
| `--dry-run` | conta le pagine e controlla la redazione, senza scrivere nulla |

## Output

`index.html` (sezioni, conteggi, data di generazione, commit della factory, ricerca),
una pagina HTML per pagina wiki con lo stesso percorso (`wiki/runbooks/x.md` →
`runbooks/x.html`), `search-index.js`. Ogni pagina mostra stato (draft, review, approved),
fonte dichiarata nel frontmatter, briciole di pane, barra laterale della sezione e link di
ritorno all'indice. Le pagine sono autocontenute: CSS inline, nessuna risorsa esterna, si
aprono da disco anche senza rete. La ricerca gira nel browser sull'indice incluso.

I wikilink si risolvono per nome file o per percorso. Se la pagina di destinazione è in una
sezione esclusa o non esiste, il testo resta ma senza link (`non pubblicata`).

## Cosa è escluso

- Sezioni: `documentation.tech_site.exclude_sections` (di default `sources`, `sessions`, `lint`, `gaps`).
- I file `wiki/log*.md`, `wiki/gaps.md`, `wiki/index.md` e `wiki/purpose.md`: si includono solo
  le cartelle elencate in `include_sections`.

## Redazione

Prima di scrivere, ogni pagina (frontmatter compreso) passa da `tools/docs/redact.py`: PAT
Azure DevOps, token GitHub, JWT, chiavi private, `password:`, `Authorization: Basic|Bearer`,
chiavi AWS, `token=`. Valori che sono segnaposto (`<token>`, `$VAR`, `...`) e nomi di
variabili senza valore non contano. Se c'è anche un solo finding il build termina con
codice 2 senza scrivere nulla: l'output si costruisce in una cartella temporanea e si
rinomina solo a controllo superato. Un eventuale output precedente resta intatto.

## Condivisione

Il comando produce solo la cartella locale. Pubblicare o inviare il sito fuori dal team è
un passo manuale, da decidere caso per caso: il contenuto è documentazione interna.
