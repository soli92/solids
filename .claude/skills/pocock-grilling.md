---
name: pocock-grilling
description: Intervista a turni sulle decisioni di un tema, prima che il product-manager scriva l'epica. I fatti li cerca l'agente, le decisioni le prende la persona. Solo nella sessione principale. Opt-in engineering_practices. Adattata da mattpocock/skills grilling @49dd158.
---
# Intervista sulle decisioni

Pre-condizione: `engineering_practices.enabled: true`. Adattata da `grilling` di Matt Pocock (MIT,
originale in `vendor/mattpocock-skills/skills/productivity/grilling/`). Gira **solo nella
sessione principale**: un sub-agente non può fare domande all'utente.

Principio: **i fatti li cerca l'agente, le decisioni le prende la persona.** Non si chiede al
Tech Lead nulla che la wiki o il codice sappiano già.

## Prima: i gap del tema

1. Il wiki-keeper chiude i gap del tema che le fonti in `raw/` coprono già (`wiki-gap-protocol`).
2. Si misura lo stato reale, se `tools/wiki/verify_gap_closures.py` esiste:
   ```bash
   python3 tools/wiki/verify_gap_closures.py --tema '<regex del tema>' --elenco
   ```
   Una chiusura senza pagina della wiki che citi la fonte conta come gap aperto.
3. I gap rimasti si dividono in **fatti** che mancano perché manca un documento (si chiede la
   fonte, non una decisione; arrivata, si ingerisce) e **decisioni** da prendere (entrano
   nell'intervista).

Solo i gap del tema. Una domanda che non dipende da un gap ancora aperto si fa subito.

## L'intervista

Si costruisce l'**albero delle decisioni** del tema: ogni decisione apre quelle che ne dipendono,
comprese quelle che nessun gap ha segnalato.

Si procede a **turni**. La **frontiera** sono le decisioni i cui prerequisiti sono già decisi: in
un turno si fanno tutte le domande della frontiera, numerate, ognuna con la risposta consigliata,
formulata in modo che «sì» accetti la raccomandazione. Formato:

```
D1 — <titolo>: <domanda, anche con le alternative>
Consiglio: <risposta raccomandata e perché, con la fonte se è un fatto>

---

D2 — ...
```

Se una domanda ha bisogno di un fatto (wiki, codice, ambiente), lo cerca l'agente, anche con un
sub-agente di esplorazione, senza bloccare il turno: aspettano solo le domande che ne dipendono.
L'intervista finisce quando la frontiera è vuota. Prima di registrare, il Tech Lead conferma che
la comprensione è condivisa.

## Dove finiscono gli esiti

| Esito | Dove | Chi scrive |
|---|---|---|
| Risposta a una domanda bloccante | `management/questions.md`, sezione `[RISOLTE]` (`apri-question`) | sessione principale |
| Scelta architetturale difficile da annullare, sorprendente senza contesto, frutto di un compromesso vero | `design_&_architecture/decisions/ADR-*.md` | lead-architect |
| Termine del dominio chiarito | glossario della wiki, via `pocock-domain-modeling` | wiki-keeper |
| Fatto nuovo emerso | nota in `raw/` da ingerire | sync agent, poi wiki-keeper |

L'elenco delle decisioni, con il loro posto, si passa al product-manager nel prompt dell'epica.
