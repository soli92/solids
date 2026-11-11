---
description: Produce il digest settimanale per il management (HTML e Word) con numeri calcolati da script su kanban, registro della wiki, gap, incidenti, costi e documenti prodotti.
argument-hint: "[--settimana=YYYY-Www] [--commento=<file.md>] [--json]"
---

# /digest-settimanale — Digest settimanale per il management

Argomenti utente: `$ARGUMENTS`

Il comando non ha logica propria: ogni numero viene da `tools/docs/weekly_digest.py`.
Chi esegue il comando non calcola, non arrotonda e non corregge nessun numero.

Gate: se `documentation.enabled` è `false` in `factory.config.yaml` (default di questa factory) lo script stampa un messaggio ed esce con codice 0 senza generare nulla: non è un errore. Riporta il messaggio all'utente e indica come attivare la capability (`documentation.enabled: true`).

## Procedura

### Step 1 — Argomenti

| Flag | Azione |
|---|---|
| (nessuno) | settimana ISO corrente (lunedì-domenica) |
| `--settimana=YYYY-Www` | settimana indicata, ad esempio `2026-W41` (5-11 ottobre 2026) |
| `--commento=<file.md>` | testo opzionale dell'autore, mostrato in un riquadro «Commento dell'autore» |
| `--json` | stampa i dati in JSON e non scrive file |

Il commento è l'unico testo scritto da una persona: va in un file a parte, mai dentro le
tabelle. Se l'utente chiede un commento, scrivilo in un file markdown temporaneo con
frasi che non contengano numeri non presenti nel digest, poi passalo con `--commento`.

### Step 2 — Esecuzione

```bash
python3 tools/docs/weekly_digest.py [--settimana YYYY-Www] [--commento FILE.md] [--out DIR]
```

Scrive `deliverables/digest/<YYYY-Www>.html` e, se `python-docx` è installato,
`deliverables/digest/<YYYY-Www>.docx`. Senza `python-docx` stampa un avviso e produce solo
l'HTML. La cartella di uscita si cambia con `documentation.weekly_digest.output_dir` in
`factory.config.yaml`.

Prima di scrivere, i dati sorgente (il JSON del digest e il testo del commento, prima di qualsiasi
render, quindi HTML e Word insieme) passano dal controllo dei segreti di `tools/docs/redact.py`
(attivo salvo `documentation.redaction.enabled: false` esplicito): se trova un segreto, nessun file
viene scritto e il comando termina con errore.

### Step 3 — Riporta all'utente

Percorsi dei file prodotti e i numeri della sintesi così come li stampa lo script. Riporta anche i
limiti che il digest dichiara nella sezione «Limiti dei dati».

## Fonti

| Sezione | Fonte |
|---|---|
| Attività chiuse, per iniziativa e per persona | `management/kanban/**/*TSK-*.md`: stato `done`/`completed` e data di chiusura (`closed_at`, o gli alias `closed`, `completed_at`, `completed`, `done_at`) nella settimana; persona da `done_by` (alias `closed_by`, `resolved_by`) |
| Punti stimati | taglia (`estimate` o `size`) con la scala di `analytics/velocity/config.json`, se presente |
| In corso e bloccate | campo `status` dei TSK, stato al momento della generazione |
| Rilasci | intestazioni «release …» e «promozione …» di `wiki/log.md` e `wiki/log-*.md` (forme `## 2026-10-07 — release X` e `## [2026-10-07] release | X`); l'etichetta del tipo viene da `documentation.weekly_digest.release_kinds`, altrimenti «altro» |
| Gap | `wiki/gaps.md`: gap con identificativo `G-…` in sezioni datate nella settimana; chiusura da «Risolto» / «Chiuso» / «[CLOSED]» |
| Incidenti | `wiki/incidents/*.md`: data dell'incidente e `date_resolved` |
| Costo token | `analytics/events/*.jsonl` con i prezzi di `analytics/pricing.yaml`, calcolati con `Pricer` di `tools/analytics/cost_alert.py`; gli eventi `session-aggregate` sono istantanee cumulative: per sessione ultima della settimana meno ultima precedente |
| Documenti prodotti | `deliverables/`: file e cartelle con la data della settimana nel nome |

Le date con ora sono convertite nel fuso Europe/Rome prima di assegnarle alla settimana.

## Riuso e limiti dichiarati

- Riusati, se presenti nella factory (altrimenti il digest usa codice proprio e lo dichiara nelle note): lettura dei campi kanban e alias (`tools/analytics/kanban_history.py`),
  attribuzione delle persone (`resolve_persona` in `tools/analytics/team-velocity.py`), prezzi
  e calcolo del costo (`tools/analytics/cost_alert.py`).
- Non riusati: il calcolo completo di `/velocity` (copre solo tre epiche e deduce le date anche
  dalla storia git) e il report PM (`tools/coordinamento/aggrega.py`, non ha funzioni per settimana).
  Per questo il digest conta tutte le epiche e usa solo le date scritte nei TSK.
- I TSK chiusi senza data di chiusura non sono attribuiti a nessuna settimana (il conteggio è
  nel digest).
- Attività in corso e bloccate: stato attuale, non a fine settimana, perché il kanban non
  conserva la storia degli stati.
- Il costo token copre solo i giorni in cui l'event store ha eventi: se i giorni sono meno di 7
  il costo è dichiarato parziale; se non ci sono eventi, la sezione dice «non disponibile» e perché.
- Un TSK con più autori in `done_by` è contato per ciascuno nella tabella per persona e una volta
  nel totale.
- I gap sono riconosciuti dai titoli datati di `wiki/gaps.md`: le sezioni senza data nel titolo non
  sono attribuite a nessuna settimana.

## Invio al manager

Il comando non invia nulla. Il file va controllato e inoltrato a mano da chi lo genera (HTML o
Word, come allegato o link a una cartella condivisa): la factory non ha canali di invio e la
condivisione è una decisione umana.

## Output

Riepilogo in chat: settimana, percorsi dei file, i 4-6 numeri della sintesi, avvisi di
`python-docx` assente o di costo parziale.
