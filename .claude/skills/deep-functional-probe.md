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

### Passi 2, 3, 4 — stati rilevanti, spec, esecuzione

**Leggi obbligatoriamente** `.claude/skills/references/deep-functional-probe/passi-2-3-4-probe.md`
dopo aver superato il Passo 1 — se il file manca, STOP e segnala.
Contiene: identificazione stati rilevanti, formulazione verifiche, generazione
acceptance-spec conforme allo schema, delega a `functional-oracle-protocol`.

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

## Pattern e ADR di riferimento

Leggi `.claude/skills/references/deep-functional-probe/pattern-e-adr.md` per i pattern
architetturali (separazione spec-generation/runtime-execution, fail-closed, una AC per
invocazione) e la tabella ADR completa (ADR-063, ADR-065, ADR-066, ADR-067).
