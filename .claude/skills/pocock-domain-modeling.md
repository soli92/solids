---
name: pocock-domain-modeling
description: Glossario del dominio difeso durante la conversazione - segnala termini ambigui o in conflitto, propone il termine canonico, confronta con il codice. Scrive solo il wiki-keeper; gli ADR il lead-architect. Opt-in engineering_practices. Adattata da mattpocock/skills domain-modeling @49dd158.
---
# Glossario del dominio

Pre-condizione: `engineering_practices.enabled: true`. Adattata da `domain-modeling` di Matt
Pocock (MIT, originale in `vendor/mattpocock-skills/skills/engineering/domain-modeling/`). Si
usa quando si cambia il modello del dominio, non quando si legge il glossario per usarne le parole.

## Dove vive

Nella wiki (`wiki/`), come pagina di concetti o glossario. Non si crea un `GLOSSARY.md` nel
repository né nel codice del cliente. La wiki ha un solo autore (R.12): questa skill
**propone**, il wiki-keeper scrive.

## Durante la conversazione

- **Conflitto con il glossario.** Un termine usato in modo diverso dalla definizione si segnala
  subito: «Il glossario dice X, qui sembra Y: quale vale?»
- **Termine vago.** Per una parola sovraccarica si propone il termine canonico: «"utente" è
  chi opera o chi riceve il servizio? Sono cose diverse.»
- **Scenari concreti.** Si inventano casi limite che costringono a tracciare il confine fra due
  concetti.
- **Confronto con il codice.** Se il codice contraddice quanto detto, lo si dice: «Il codice
  annulla l'intera pratica, ma qui si parla di annullamento parziale: quale è giusto?»

## Proposta per il glossario

Quando un termine si chiarisce, si annota subito la proposta, senza accumulare:

```
**<termine>** — <definizione nel dominio, una o due frasi, senza dettagli di implementazione>.
Da evitare: <sinonimi da non usare>. Fonte: <raw o pagina wiki che lo supporta>.
```

Senza fonte la definizione non entra (R.2, R.3): si apre un gap. A fine conversazione le proposte
si passano al wiki-keeper, che aggiorna il glossario e scrive l'entry in `wiki/log.md`.

## Decisioni

Un ADR si propone solo se valgono tutte e tre: **difficile da annullare**, **sorprendente senza
contesto**, **frutto di un compromesso vero** fra alternative reali. Va in
`design_&_architecture/decisions/ADR-*.md` e lo scrive il lead-architect. Se manca anche una
delle tre condizioni, niente ADR.
