---
name: pocock-codebase-design
description: Vocabolario e principi dei moduli profondi (interfaccia piccola, molto comportamento dietro, seam pulito). Riferimento per lead-architect, dev-agent, code-reviewer e pocock-tdd. Opt-in engineering_practices. Adattata da mattpocock/skills codebase-design @49dd158.
---
# Moduli profondi: vocabolario comune

Pre-condizione: `engineering_practices.enabled: true`. Adattata da `codebase-design` di Matt
Pocock (MIT, originale e approfondimenti `DEEPENING.md` e `DESIGN-IT-TWICE.md` in
`vendor/mattpocock-skills/skills/engineering/codebase-design/`). Riferimento da consultare, non
una procedura.

## Termini

Si usano questi, sempre gli stessi: il lessico condiviso è lo scopo.

| Termine | Significato |
|---|---|
| **Modulo** | Qualsiasi cosa con un'interfaccia e un'implementazione: funzione, componente, store, middleware, servizio |
| **Interfaccia** | Tutto ciò che chi lo usa deve sapere: firma, props ed eventi, ma anche invarianti, ordine delle chiamate, errori, configurazione richiesta |
| **Implementazione** | Il codice dentro il modulo |
| **Profondità** | Comportamento ottenuto per unità di interfaccia da imparare. Profondo: interfaccia piccola, molto comportamento. Superficiale: interfaccia complessa quasi quanto il codice |
| **Seam** | Il punto in cui si può cambiare il comportamento senza modificare il codice lì; è dove vive l'interfaccia (Michael Feathers) |
| **Adapter** | Ciò che soddisfa l'interfaccia a un seam: il client reale, il doppio di test |
| **Leva** | Ciò che ottiene chi usa il modulo: più capacità per meno interfaccia |
| **Località** | Ciò che ottiene chi lo mantiene: modifiche, bug e verifiche concentrati in un posto solo |

Da evitare come sinonimi: «boundary» (si confonde con il bounded context), «API» per dire
interfaccia (troppo stretto).

## Principi

- **La profondità è una proprietà dell'interfaccia.** Un modulo profondo può avere dentro parti
  piccole e sostituibili: non fanno parte dell'interfaccia.
- **Test di eliminazione.** Immagina di cancellare il modulo. Se la complessità sparisce, era un
  passacarte. Se ricompare in N punti che lo usano, si guadagnava il posto.
- **L'interfaccia è la superficie di test.** Se serve testare oltre l'interfaccia, il modulo ha
  la forma sbagliata.
- **Un adapter è un seam ipotetico, due adapter sono un seam vero.** Non si introduce un seam se
  nulla varia davvero lì.

## Progettare per la testabilità

1. Ricevere le dipendenze invece di crearle (il client passato, non costruito dentro).
2. Restituire risultati invece di produrre effetti collaterali.
3. Interfaccia piccola: meno funzioni e meno parametri, meno test e setup più semplice.

## Esempi

- Un componente che inoltra dieci parametri a un figlio è superficiale: test di eliminazione,
  si inlinea o si sposta la logica dove sta il dato.
- Logica di validazione dentro un componente di interfaccia: estratta in un modulo puro diventa
  un seam su cui gira `pocock-tdd`.
- Le chiamate a un servizio esterno raccolte in un unico modulo client sono un seam con due
  adapter veri (reale e doppio di test).
