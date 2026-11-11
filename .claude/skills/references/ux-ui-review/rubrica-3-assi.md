# Step 3 — Rubrica 3 Assi (dettaglio completo)

Ambito: dettaglio del Step 3 di `ux-ui-review-protocol.md`. Leggere prima di eseguire
la review rubrica anti-soggettività.

Valuta l'input visivo contro **tutti e tre gli assi** della
[[ux-ui-rubric-anti-subjectivity]]. Per ogni problema rilevato produci un `finding` con
`rubric_ref` obbligatorio, `severity`, `location`, `description`, `recommendation`, `evidence`.

---

## 3a — Euristiche di usabilità di Nielsen (10)

Scorri le 10 euristiche. Per ogni problema: euristica violata (`rubric_ref: "nielsen-N"`) →
severità → posizione → raccomandazione.

| ref | Euristica | Domanda operativa |
|---|---|---|
| `nielsen-1` | Visibilità dello stato del sistema | L'utente sa sempre cosa sta succedendo? |
| `nielsen-2` | Corrispondenza tra sistema e mondo reale | Il linguaggio rispecchia il dominio dell'utente? |
| `nielsen-3` | Controllo e libertà dell'utente | L'utente può annullare / tornare indietro facilmente? |
| `nielsen-4` | Coerenza e standard | Parole, situazioni e azioni simili si comportano allo stesso modo? |
| `nielsen-5` | Prevenzione degli errori | Il design previene i problemi prima che si verifichino? |
| `nielsen-6` | Riconoscere invece di ricordare | Istruzioni e opzioni sono visibili, non memorizzate? |
| `nielsen-7` | Flessibilità ed efficienza d'uso | Esistono acceleratori per utenti esperti? |
| `nielsen-8` | Design estetico e minimalista | Contiene solo informazioni rilevanti? |
| `nielsen-9` | Riconoscere, diagnosticare e recuperare dagli errori | I messaggi di errore sono utili e chiari? |
| `nielsen-10` | Aiuto e documentazione | Se serve aiuto, è facile trovarlo e usarlo? |

## 3b — Dimensioni di UI visiva (6)

`rubric_ref: "ui-<dimensione>"` (es. `ui-gerarchia`).

| ref | Dimensione | Domanda operativa |
|---|---|---|
| `ui-gerarchia` | Gerarchia | L'occhio segue l'ordine d'importanza? Il titolo è più prominente del body? |
| `ui-spaziatura` | Spaziatura / ritmo | Gli spazi sono coerenti? I raggruppamenti per prossimità sono corretti? |
| `ui-tipografia` | Tipografia | La scala è leggibile? Il numero di stili è contenuto? |
| `ui-colore` | Colore | L'uso è semantico e coerente? |
| `ui-coerenza` | Coerenza | Stessi pattern per stessi scopi? Aderenza al design system? |
| `ui-affordance` | Affordance / stati | Hover / focus / active / disabled / loading / empty / error sono visibili e distinti? |

**Contrasto cromatico delegato a Step 4 (axe-core), non duplicare.** La dimensione `ui-colore`
copre l'uso *semantico e coerente* del colore; il **contrasto WCAG AA** (e l'ordine di focus)
sono accessibilità → delegati a `run_a11y_scan` nello Step 4. Non emettere finding di contrasto
qui (eviti il doppio conteggio con il report a11y).

## 3c — Dimensioni di flusso UX (5)

Applicabile **solo se la review copre un flusso multi-passo**. `rubric_ref: "ux-<dimensione>"`.

| ref | Dimensione | Domanda operativa |
|---|---|---|
| `ux-passi-valore` | Numero di passi vs valore | Il flusso è proporzionato al valore che offre? |
| `ux-abbandono` | Punti di abbandono | Dove l'utente tipicamente si ferma o torna indietro? |
| `ux-prossimo-passo` | Chiarezza del prossimo passo | È sempre evidente cosa fare dopo? |
| `ux-errori-vuoti` | Gestione errori e stati vuoti | Errori e stati vuoti sono previsti e comunicati chiaramente? |
| `ux-reversibilita` | Reversibilità delle azioni | Le azioni distruttive sono reversibili o richiedono conferma? |

**Output**: `findings[]` (ciascuno con `rubric_ref`), `positive_findings[]`.

**Criterio di completamento**: i 3 assi sono stati scorsi; ogni `finding` ha un `rubric_ref`
valido; nessun finding di contrasto cromatico (delegato a Step 4); i punti opinabili marcati
`opinion: true`.

[^src: wiki/concepts/ux-ui-rubric-anti-subjectivity.md §Asse 1]
[^src: wiki/concepts/ux-ui-rubric-anti-subjectivity.md §Asse 2]
[^src: wiki/concepts/ux-ui-rubric-anti-subjectivity.md §Asse 3]
