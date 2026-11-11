# Deep Functional Probe — Passi 2, 3, 4: stati, spec, esecuzione

**Ambito**: dettaglio dei Passi 2, 3 e 4 di `deep-functional-probe.md`.
Leggere obbligatoriamente all'ingresso del Passo 2 dopo che il Passo 1 ha superato
il gate — se il file manca, STOP e segnala.

---

## Passo 2 — Identificazione degli stati rilevanti

**Input atteso**: `target`, `scenario` (dal Passo 1).

Identifica l'insieme degli **stati rilevanti** del target per lo scenario dichiarato.
Gli stati sono le condizioni osservabili del target che influenzano il comportamento
verificabile dall'AC.

Categorie di stati da considerare (non esaustive — adattare al target specifico):

| Categoria | Esempi |
|---|---|
| Stati di attesa / caricamento | vuoto, caricamento in corso, schermata iniziale |
| Stati di input | campo vuoto, input parziale, input valido, input non valido |
| Stati di esito | successo, errore lato client, errore lato server, timeout |
| Stati di visibilità | elemento nascosto, elemento visibile, elemento disabilitato |
| Stati di transizione | durante navigazione, durante submit, durante aggiornamento |
| Casi limite | input vuoto su submit, caratteri speciali, lunghezza massima |

Seleziona solo gli stati **pertinenti allo scenario dichiarato** e all'AC da verificare.
Un probe non deve coprire tutti gli stati possibili del target — solo quelli che
l'AC richiede di osservare per emettere il verdetto.

**Output**: lista degli stati rilevanti `S = [s1, s2, ..., sN]` con descrizione per
ognuno.

---

## Passo 3 — Formulazione delle verifiche e generazione dell'acceptance-spec

**Input atteso**: stati rilevanti `S` (Passo 2), `scenario`, `ac`.

Per ogni stato `si` in `S`, formula la verifica secondo il modello:

```
stato:       <descrizione dello stato>
input:       <dati o azioni che portano il target in questo stato>
azione:      <interazione dell'utente o evento da simulare>
output_atteso: <comportamento osservabile atteso, collegato all'AC>
```

Dalle verifiche formulate, genera il corpo dell'acceptance-spec conforme allo schema
`.claude/schemas/acceptance-spec.schema.yaml` (4 sezioni obbligatorie: `fixtures`,
`scenario`, `assertions`, `thresholds`).

**Vincoli sulla generazione della spec**:

- Le `fixtures` devono essere dati reali o rappresentativi — mai mock vuoti che
  invalidano l'osservazione.
- I selettori nelle `assertions` devono usare identificatori stabili (ruolo ARIA, testo
  visibile, attributi `data-test`) — mai classi CSS di styling o selettori dipendenti
  da librerie di design specifiche.
- Le asserzioni `blocking` coprono il comportamento core dell'AC; le asserzioni
  `advisory` coprono aspetti qualitativi (log di errore, richieste 5xx, ecc.).
- Il `thresholds.advisory_max` è stringente di default (0 o valore basso) — la bar
  di accettazione è massima.
- La spec non deve fare assunzioni su framework FE, librerie di stato o strumenti di
  test specifici: usa le 8 primitive domain-agnostic di `functional-oracle-protocol`
  (`selector_visible`, `selector_absent`, `attr_equals`, `text_matches`,
  `canvas_pixel_variance`, `storage_key_present`, `console_no_error`, `network_no_5xx`).

**Output**: acceptance-spec generata (YAML, conforme allo schema); percorso di salvataggio
suggerito: `code_quality/acceptance/<slug-target>.acceptance.yaml`.

---

## Passo 4 — Esecuzione del probe via functional-oracle-protocol

**Input atteso**: acceptance-spec generata (Passo 3), `target`.

Delega l'intera esecuzione a `functional-oracle-protocol` (EP-018):

```
INVOCA functional-oracle-protocol con:
  acceptance_spec = <spec generata al Passo 3>
  target          = <target dichiarato in input>

Restituisce:
  verdict_raw:   pass | conditional | reject | skip
  evidence_data: assertion_results, trace, open_questions
```

**Invarianti della delega**:

- `functional-oracle-protocol` è il **single-writer** di `functional_status:` — questa
  skill non scrive mai quel campo.
- `functional-oracle-protocol` possiede l'intero runtime (serve, interazione, screenshot,
  asserzioni binarie) — questa skill non apre browser, non esegue interazioni inline.
- Il gate `fe_correctness.functional_oracle.enabled` governa l'esecuzione del delegato;
  nessun nuovo flag è necessario per questo probe.
- Se il delegato risponde `skip` (scenario vuoto), la skill lo riscritto come `FAIL` con
  rationale «scenario non eseguibile — spec vuota o incomplete».

**Vincolo sola-lettura**: questa skill osserva il comportamento del target attraverso
il delegato; non modifica lo stato dell'interfaccia osservata, non esegue operazioni di
scrittura sull'applicazione sotto test, non effettua deploy. Gli artefatti prodotti
(spec, coverage) vivono factory-side e non modificano il target.

**Output**: `verdict_raw` + `evidence_data` dal delegato.
