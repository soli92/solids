---
name: deep-functional-probe
description: Skill procedurale per il sondaggio funzionale approfondito di un componente o flusso. Riceve (target, scenario, ac), identifica gli stati rilevanti, formula le verifiche per ognuno, genera l'acceptance-spec e delega l'esecuzione a functional-oracle-protocol (EP-018). Emette un verdetto PASS|FAIL deterministico con evidenza concreta. Tecnologia-agnostica. Complemento a functional-oracle-protocol, non sostituto.
---
# Deep Functional Probe — sondaggio funzionale approfondito

Skill procedurale per l'esplorazione sistematica degli stati funzionali di un componente
o flusso. Data una tripletta `(target, scenario, ac)`, identifica gli stati rilevanti del
target per lo scenario, formula per ognuno la verifica `input → azione → output atteso`,
genera il corpo dell'acceptance-spec e delega l'esecuzione al runtime di
`functional-oracle-protocol` (EP-018). Emette un verdetto `PASS | FAIL` deterministico
con evidenza osservata.

Questa skill opera **a monte** dell'esecuzione: produce il contratto di accettazione e
coordina il targeting. Non reimplementa il runtime (serve, interazione, asserzioni):
ogni responsabilità di esecuzione è di competenza di `functional-oracle-protocol`.

**Relazione con functional-oracle-protocol**:

```
deep-functional-probe                    functional-oracle-protocol (EP-018)
─────────────────────────                ─────────────────────────────────────
1. Riceve (target, scenario, ac)
2. Identifica stati rilevanti
3. Formula verifiche per stato          Riceve: acceptance-spec + target
4. Genera acceptance-spec      ──────►  Esegue: serve → fixture → drive → assert
5. Riceve il verdict           ◄──────  Restituisce: pass | conditional | reject | skip
6. Emette PASS | FAIL
```

La skill non apre browser, non scrive asserzioni di interazione inline, non modifica lo
stato dell'interfaccia osservata. È sola-lettura rispetto all'interfaccia; produce
artefatti factory-side (spec, copertura).

[^src: EP-018 — FE Functional Oracle (dipendenza funzionale)]
[^src: TSK-515 — analisi sezioni portale-specific e relazione con functional-oracle-protocol]
[^src: US-224 — AC1, AC2, AC3, AC4]

---

## Prerequisiti

- **`fe_correctness.functional_oracle.enabled: true`** (master gate — se il flag è
  `false` questa skill NON deve essere invocata; STOP con messaggio:
  «Deep functional probe richiede `fe_correctness.functional_oracle.enabled: true`.
  Abilitare il flag in `factory.config.yaml` prima di procedere.»).
- `functional-oracle-protocol.md` presente in `.claude/skills/` — prerequisito obbligatorio
  bloccante: la skill non reimplementa il runtime; senza il delegato di esecuzione STOP
  fail-loud.
- `.claude/schemas/acceptance-spec.schema.yaml` presente — lo schema governa la
  generazione dell'acceptance-spec in Passo 3.

---

## Interfaccia di input

| Parametro | Descrizione | Note |
|---|---|---|
| `target` | Componente o flusso da sondare | Descrittivo e non legato a un framework specifico (es. "form di login", "card prodotto", "checkout step 2", "pannello notifiche") |
| `scenario` | Descrizione dello scenario funzionale da verificare | Lingua naturale; include le azioni dell'utente e il contesto di partenza (es. "utente non autenticato accede alla pagina, inserisce credenziali valide e invia il form") |
| `ac` | Acceptance criterion specifico da testare | **Una sola AC per invocazione**; formula osservabile e verificabile (es. "dopo invio valido, il pannello di benvenuto è visibile e il form scompare") |

La skill accetta **una AC per invocazione**. Per target con più AC, invocare la skill
separatamente per ciascuna (ogni invocazione produce un verdetto autonomo).

---

## Procedura di probe (5 passi)

### Passo 1 — Ricezione input e gate

**Input atteso**: `target`, `scenario`, `ac`.

1. Verifica `fe_correctness.functional_oracle.enabled`. Se `false` → STOP (vedi
   Prerequisiti).
2. Verifica presenza di `functional-oracle-protocol.md` in `.claude/skills/`. Se assente
   → STOP fail-loud: «`functional-oracle-protocol` non trovato. Prerequisito obbligatorio
   (EP-018). Eseguire il bootstrap o aggiornare la factory.»
3. Verifica presenza di `.claude/schemas/acceptance-spec.schema.yaml`. Se assente →
   STOP fail-loud: «Schema `acceptance-spec.schema.yaml` non trovato. Necessario per la
   generazione della spec.»
4. Verifica che tutti e tre i parametri (`target`, `scenario`, `ac`) siano valorizzati e
   non vuoti. Se mancante uno → STOP con indicazione del parametro assente.

**Output**: gate superato; input validati.

---

### Passo 2 — Identificazione degli stati rilevanti

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

### Passo 3 — Formulazione delle verifiche e generazione dell'acceptance-spec

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

### Passo 4 — Esecuzione del probe via functional-oracle-protocol

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

---

### Passo 5 — Emissione del verdetto

**Input atteso**: `verdict_raw` + `evidence_data` (Passo 4), `ac`.

Calcola il verdetto finale secondo la regola:

| `verdict_raw` da functional-oracle-protocol | Verdetto emesso |
|---|---|
| `pass` | **`PASS`** |
| `conditional` | **`FAIL`** — le asserzioni advisory fallite oltre soglia indicano che l'AC non è pienamente soddisfatto |
| `reject` | **`FAIL`** |
| `skip` | **`FAIL`** — scenario non eseguibile (spec vuota o incomplete) |

Il verdetto è **deterministico e non ambiguo**. Non è mai opinion-based. Nessun LLM
determina il verdetto: deriva meccanicamente dal risultato delle asserzioni binarie
eseguite dal delegato.

Produce l'output strutturato del probe:

```yaml
verdict:  PASS | FAIL
evidence: |
  <osservazione concreta che supporta il verdetto — max 3 righe>
  <riferisce artefatti reali: step PNG, log, assertion results>
rationale: |
  <razionale sintetico che collega l'evidenza all'AC — max 2 righe>
```

**Regola di ammissibilità dell'evidenza**: ogni riga di `evidence` deve riferire un
artefatto reale prodotto dall'esecuzione (path screenshot, riga di log, risultato
di asserzione). Nessuna osservazione è ammessa senza riferimento concreto
(anti-fabbricazione — coerente con ADR-063 evidence-provenance).

**Output**: blocco `verdict / evidence / rationale` pronto per il consumer.

---

## Struttura output

Il probe emette sempre e solo il seguente blocco strutturato:

```yaml
# Deep Functional Probe — output
target:    <valore del parametro target in input>
scenario:  <sintesi dello scenario>
ac:        <testo dell'AC verificata>

verdict:   PASS | FAIL

evidence: |
  <riga 1 — osservazione concreta con riferimento ad artefatto reale>
  <riga 2 — ulteriore dettaglio se necessario (opzionale)>
  <riga 3 — ulteriore dettaglio se necessario (opzionale)>

rationale: |
  <riga 1 — razionale che collega evidenza all'AC>
  <riga 2 — complemento sintetico (opzionale)>
```

**Vincoli sul blocco output**:

- `verdict`: obbligatorio; valore enum `PASS` o `FAIL`; mai assente, mai ambiguo, mai
  opinion-based.
- `evidence`: obbligatorio; massimo 3 righe; ogni riga deve citare un artefatto reale
  (path file, step index, riga log, nome asserzione); nessuna osservazione senza
  riferimento concreto.
- `rationale`: obbligatorio; massimo 2 righe; sintetico; collega l'evidenza all'AC
  senza introdurre giudizi soggettivi.

---

## Vincolo sola-lettura (dichiarazione esplicita)

Questa skill **non modifica lo stato dell'interfaccia** osservata. In particolare:

- Non esegue operazioni di scrittura sull'applicazione sotto test.
- Non modifica database, storage o stato server del target.
- Non effettua deploy, promuove build o pubblica artefatti dell'applicazione.
- Non scrive il campo `functional_status:` nel frontmatter TSK (single-writer esclusivo:
  `functional-oracle-protocol`).

La skill produce esclusivamente **artefatti factory-side**:
- `code_quality/acceptance/<slug>.acceptance.yaml` — spec generata (Passo 3).
- Artefatti di trace (screenshot, log) prodotti dal delegato e visibili in
  `code_quality/reports/` — scritti da `functional-oracle-protocol`, non da questa skill.

La promozione della spec dentro il repository del target è un passo umano esplicito,
mai automatico.

---

## Pattern di riferimento

### Separazione spec-generation / runtime-execution

Questa skill incarna la separazione dichiarata in ADR-065 §A (framework vs contenuto
progetto): la generazione della spec (logica di dominio, stati, verifiche) è separata
dal runtime di esecuzione (serve, interazione, asserzioni binarie). Ogni layer è
aggiornabile indipendentemente. Un progetto che cambia framework FE non modifica
questa skill; un aggiornamento al runtime di interazione non modifica la logica di
generazione della spec.

### fail-closed (anti-fabbricazione)

Il verdetto nasce esclusivamente da asserzioni binarie deterministiche eseguite dal
delegato. Nessun LLM determina `PASS` o `FAIL`. Il blocco `evidence` richiede
riferimento obbligatorio a un artefatto reale — nessuna osservazione ammessa senza
provenance (coerente con ADR-063 §B). Un probe senza evidenza deterministica non può
emettere `PASS`.

### una AC per invocazione

Il probe verifica **una sola AC per invocazione**. Questo garantisce che evidenza e
rationale siano sempre riferiti a un singolo criterio osservabile, riducendo ambiguità
e facilitando il tracing dei risultati. Per target con più AC: invocare la skill N volte
e aggregare i verdetti nel chiamante.

---

## ADR di riferimento

| ADR | Rilevanza per questa skill |
|---|---|
| [`ADR-065`](../../design_&_architecture/decisions/ADR-065.md) | Schema acceptance-spec — 4 sezioni obbligatorie; 8 primitive domain-agnostic; semantica blocking/advisory; fail-loud su spec assente |
| [`ADR-066`](../../design_&_architecture/decisions/ADR-066.md) | Delega runtime a `interaction-drive-protocol`; ordering nel cascade |
| [`ADR-067`](../../design_&_architecture/decisions/ADR-067.md) | Verdict deterministico; critic LLM solo advisory; loop bounded |
| [`ADR-063`](../../design_&_architecture/decisions/ADR-063.md) | Evidence-provenance obbligatoria per ogni finding — nessuna osservazione senza artefatto reale |

[^src: design_&_architecture/decisions/ADR-065.md §A §C §E]
[^src: design_&_architecture/decisions/ADR-063.md §B]
[^src: design_&_architecture/decisions/ADR-067.md §B]
