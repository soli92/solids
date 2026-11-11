---
name: pocock-tdd
description: TDD a fette verticali per i TSK con logica. Test prima del codice, solo sui seam concordati nel TSK (test_seams). Opt-in engineering_practices. Adattata da mattpocock/skills tdd @49dd158.
---
# TDD a fette verticali

Pre-condizione: `engineering_practices.enabled: true`, altrimenti non si applica.
Adattata da `tdd` di Matt Pocock (MIT, originale in `vendor/mattpocock-skills/skills/engineering/tdd/`).
Ciclo rosso, verde: prima un test che fallisce, poi il codice minimo che lo fa passare.

## Quando si applica

A ogni TSK con `test_seams:` nel frontmatter (vedi `scrivi-task`) e `test_seams_status: confermati`.
Senza seam confermati il dev-agent lavora come prima e **non inventa seam**: lo scrive
nell'handoff («seam non concordati»). Li propone il tpm alla taskificazione e li conferma il
Tech Lead nella sessione principale, perché un sub-agente non può chiedere conferma all'utente.

## Dove vivono i test

Dove li prevede lo stack: il comando e la cartella dei test stanno in `raw/tech_stack.md` e
nella configurazione del progetto (`code_path`). Si usa il runner che il progetto ha già; non se
ne introduce uno per il TSK. Le dipendenze esterne si sostituiscono con i doppi che il progetto
ha già.

## Seam

Un **seam** è il confine pubblico in cui si osserva il comportamento senza guardare dentro: la
funzione esportata, la risposta di un servizio, la schermata vista dall'utente. Ogni voce di
`test_seams:` dice il seam e, in una riga, cosa cattura e cosa no. Si testa solo lì. Per la forma
del seam vale il vocabolario di `pocock-codebase-design`.

## Un buon test

- Verifica il comportamento attraverso l'interfaccia pubblica e sopravvive a un refactor interno.
- Si legge come una specifica: «categoria non selezionata, il pulsante resta disabilitato».
- Il valore atteso viene da una fonte indipendente: un letterale noto, un esempio del requisito,
  la US. Mai ricalcolato come lo calcola il codice.
- Dove il comportamento dipende dall'ambiente di esecuzione (browser, sistema operativo, runtime),
  il rosso si cerca in più di un ambiente quando lo stack ne prevede più d'uno.

## Anti-pattern

- **Accoppiato all'implementazione**: mock di moduli interni, test di funzioni private. Segnale:
  si rompe con un refactor che non cambia il comportamento.
- **Tautologico**: l'atteso ripete il calcolo del codice, quindi passa per costruzione.
- **A fette orizzontali**: tutti i test prima, tutto il codice dopo. Si lavora una fetta alla volta.

## Regole del ciclo

1. Rosso prima di verde: il test fallisce per il motivo giusto, poi il codice minimo.
2. Un seam, un test, un'implementazione minima per giro.
3. Il refactor non fa parte del ciclo: va alla review (`/review`, CQRL).
4. Mock solo ai confini del sistema (rete, tempo, casualità, librerie esterne), mai dei propri moduli.

## Prova nell'handoff

Per ogni seam l'handoff riporta il comando, l'esito rosso prima della modifica e l'esito verde
dopo. Senza il rosso il test non dimostra nulla: va riscritto.
