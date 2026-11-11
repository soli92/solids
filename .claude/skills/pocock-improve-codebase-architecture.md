---
name: pocock-improve-codebase-architecture
description: Cerca nel codice i moduli superficiali da rendere profondi, presenta i candidati e ne approfondisce uno con un'intervista; l'esito è una proposta EP/US senza path del codice del cliente. Solo nella sessione principale. Opt-in engineering_practices. Adattata da mattpocock/skills improve-codebase-architecture @49dd158.
---
# Analisi dell'architettura a moduli profondi

Pre-condizione: `engineering_practices.enabled: true`. Adattata da `improve-codebase-architecture`
di Matt Pocock (MIT, originale in
`vendor/mattpocock-skills/skills/engineering/improve-codebase-architecture/`). Obiettivo:
testabilità e facilità di navigazione per gli agenti. Vocabolario: `pocock-codebase-design`.
Sola lettura su `<code_path>`.

## 1. Dove guardare

Si decide prima dove: rendere profondo un modulo ripaga quando quel codice cambia spesso.

- Se il Tech Lead indica una direzione (un modulo, un flusso, un fastidio), si parte da lì.
- Altrimenti si leggono i punti caldi dalla storia del repo
  (`git -C <code_path> log --oneline -200 --name-only`) e dai TSK di correzione (`fix`, `bug`,
  `regressione` nel titolo).
- Si leggono le pagine wiki e gli ADR dell'area. I seam mancanti segnalati da
  `pocock-diagnosing-bugs` («nessun seam corretto») sono candidati già pronti.

Un sub-agente di esplorazione annota dove c'è attrito: concetti sparsi fra molti moduli piccoli,
moduli superficiali, logica estratta solo per i test mentre i bug stanno nel modo in cui è
chiamata, moduli che si scavalcano i seam, parti difficili da testare dall'interfaccia attuale.
A ogni sospetto si applica il test di eliminazione.

## 2. Candidati

Per ogni candidato: moduli coinvolti, problema, soluzione in parole semplici, benefici in termini
di leva, località e test, forza della raccomandazione (`Forte`, `Da esplorare`, `Speculativa`).
Si chiude con il candidato da affrontare per primo.

Il report si mostra in chat, oppure come HTML autonomo in una cartella temporanea fuori dalla
factory (stili inline, nessuno script né risorsa da CDN), da cancellare a fine sessione. Nessun
report con path del codice del cliente resta nella factory (§ai_policy). Un candidato che
contraddice un ADR si mostra solo se l'attrito giustifica riaprirlo, e lo si dice.

Non si propongono ancora interfacce. Si chiede al Tech Lead quale candidato approfondire, oppure
di chiudere senza approfondire.

## 3. Approfondimento

Sul candidato scelto si usa `pocock-grilling` per vincoli, dipendenze, forma del modulo profondo,
cosa sta dietro il seam e quali test sopravvivono, e `pocock-domain-modeling` per i termini nuovi.
Se il candidato viene scartato con un motivo che servirà ancora, si propone un ADR al
lead-architect, così le analisi successive non lo ripropongono.

## 4. Uscita

Una proposta di EP o US per il product-manager, scritta con i nomi del dominio e dei moduli,
**senza path di file del codice del cliente**. Le proposte le redige il product-manager; i TSK
il tpm.
