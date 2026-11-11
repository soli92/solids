# Riepilogo in chat, regole di calcolo, controlli di qualita' del dato

> Foglia di [`coordinamento-giornaliero`](../../coordinamento-giornaliero.md), Passo 2.

## Cosa dire in chat (dal RIEPILOGO, 8-12 righe)

1. Commit del kanban misurato e data. `non_committati > 0`: «N file del kanban modificati e non
   committati: esclusi dalla misura». `non_pushati > 0`: lo stato misurato e' locale.
   `config_non_allineata > 0`: dillo e ricorda il Passo 1.
2. Per obiettivo (array `obiettivi`, in ordine di data): nome, data e giorni lavorativi rimasti. Poi:
   - per epica: `pct`% (`fatto`/`base`), chiusi senza esito esclusi, TSK in attesa di prerequisito;
   - sezioni (solo se l'obiettivo ne ha) da `riepilogo_sezioni`: quante per stato, avviate, senza TSK;
   - `per_sottoperimetro` (se presente): fatti/base e % per sviluppo, configurazione («Infra · rilascio»), test; `ambiente_rilascio` per il testo «rilascio in <ambiente>»;
   - `dipendenti`: sezioni di altri obiettivi che lo attendono;
   - `misurato` falso: «fuori dal kanban, nessuna misura» (mai una percentuale);
   - `avvisi`: quanti alti e medi, testo dei primi (regole, non giudizi).
3. Copertura: TSK non legati a una sezione; TSK illeggibili. Qualita' del dato: numero di anomalie.
4. Path completo dell'HTML.

Regole del riepilogo: ID sempre con una sintesi tra parentesi; nessun giudizio che i dati non
contengano; un dato che sembra sbagliato si segnala come osservazione, non si corregge nel report.

## Regole di calcolo (le stesse scritte nella pagina)

- **Avanzamento** = TSK fatti / (totali − chiusi senza esito). I chiusi senza esito (es.
  superseded, cancelled) si mostrano a parte; i sospesi restano nel denominatore.
- **Stato**: dalla tabella `stati` della config; un valore non previsto e' «sconosciuto», mai indovinato.
- **Appartenenza**: dal frontmatter (`story:`/`us:`, `epic:`/`ep:`); dal path solo in mancanza.
  Frontmatter e path discordanti = anomalia `appartenenza-discordante`, vale il frontmatter.
- **Sezione**: solo dalla mappa US→sezione della config. Il resto sta in «lavoro non legato a una
  sezione», raggruppato per US. Ogni TSK conta una volta.
- **Sottoperimetro**: solo da `sezioni[].sottoperimetro` della config, mai dedotto da titoli o path. Avanzamento per sottoperimetro con la stessa regola, sull'unione dei TSK delle sue sezioni: un TSK in piu' sezioni dello stesso sottoperimetro conta una volta, in sottoperimetri diversi una volta in ciascuno. L0 lo ricalcola in modo indipendente.
- **Prerequisito soddisfatto** solo se il TSK richiesto e' fatto. Annullato o superato = da
  riconciliare. Assente dal perimetro = indeterminato.
- **Giorni lavorativi**: lun-ven, festivita' non considerate.
- **Senza owner**: owner vuoto o fra `owner_non_persona`; l'eta' parte da `prima_vista` dello store.

## Stato «In linea / A rischio / Critico»

Etichetta calcolata dagli avvisi a regole, non una valutazione: ✖ Critico = almeno un avviso
alto; ▲ A rischio = solo avvisi medi; ✔ In linea = nessun avviso alto o medio. La regola e'
scritta in legenda.

## Controlli di qualita' del dato (deterministici, non cambiano i numeri)

- `superseded_by` non leggibile come ID o verso un ID inesistente;
- chiusura senza campi strutturati (`superseded_by`, `superseded_at`/`closed_at`, `superseded_reason`/`resolution`);
- `updated` piu' vecchio dell'ultimo commit sul file (solo entita' chiuse);
- US o epiche con status incoerente con i loro TSK (roll-up);
- giorno della settimana incoerente con la data (es. «mer 06/10» con il 06/10 martedi');
- US o epiche che nel testo dichiarano completato un TSK chiuso senza esito, o il contrario;
- `blocks`/`depends_on` scritti da una parte sola; dipendenze fuori dal perimetro;
- appartenenza discordante fra frontmatter e path.

Compaiono raggruppati per tipo nella scheda «Qualita' dato», ognuno con il suo prompt di verifica.
