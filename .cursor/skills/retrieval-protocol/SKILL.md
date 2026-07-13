# Skill: Retrieval Protocol

> Adapter Cursor della skill `retrieval-protocol` definita in PATTERN.md.
>
> Metadata originale — name: retrieval-protocol; version: 1.0; scope: tutor EP-045 — retrieval vivo e citato. Descrizione: procedura per il retrieval vivo e citato del tutor EP-045. Definisce il contratto procedurale che il tutor esegue per ogni affermazione su concetti documentati o componenti del codebase: 4 fasi, marker di esito, schema gap-record compatibile con wiki/gaps.md.

**Protocollo di Retrieval Vivo e Citato (EP-045)**

Skill fondante per il tutor EP-045. Ogni affermazione del tutor su un concetto
documentato o su un componente del codebase deve essere ancorata a un artefatto
reale recuperato al momento della risposta. Il retrieval non usa cache di sessione
precedente: opera sempre sulla versione corrente degli artefatti (vedi §Vincoli).

Riferimenti: `wiki-search-protocol` (EP-042, opt-in Fase 2), PATTERN §31 (Hybrid
Wiki Search), `wiki-gap-protocol` (apertura lacune), PATTERN §6 (citazione).

---

## Fase 1 — Ricezione e classificazione query

**Input**: domanda dello studente + contesto sessione corrente.

**Procedura di classificazione**:

1. Analizza la domanda per identificare il dominio semantico principale:

   | Segnale nella domanda | Classificazione |
   |---|---|
   | Termini concettuali, pattern, principi, decisioni architetturali | `topic wiki` |
   | Nomi di file, funzioni, classi, moduli, percorsi, comandi | `componente codebase` |
   | Domanda ambigua o cross-dominio (es. "come funziona X nel codice?") | `ambigua` |

2. Per classificazione `ambigua`: applica entrambe le fasi 2 e 3; in Fase 4
   consolida i risultati da entrambe le sorgenti.

**Output**: classificazione query ∈ {`topic wiki`, `componente codebase`, `ambigua`}.

---

## Fase 2 — Ricerca wiki

Eseguita per tutte le classificazioni (`topic wiki`, `ambigua`).

**Estrai i termini chiave** dalla domanda originale (max 3-5 token rilevanti,
escludi stop-word).

### Branch EP-042 ON (`wiki_search.enabled: true` in `factory.config.yaml`)

Invoca `wiki-search-protocol` con la query originale (o i termini chiave se
la query è lunga). La skill restituisce una lista ordinata per rilevanza.

```
/wiki-search <query>
```

Usa il top-k restituito dalla skill (default 5, configurabile via `wiki_search.top_k`).

### Branch EP-042 OFF (default — `wiki_search.enabled: false`)

Esegui grep/ripgrep ricorsivo su `wiki/` con i termini chiave estratti:

```bash
# ricerca case-insensitive, mostra il file e la riga di match
grep -rli "<termine1>" wiki/
rg -l --ignore-case "<termine1>" wiki/

# per termini multipli (AND): filtra progressivamente
grep -rli "<termine1>" wiki/ | xargs grep -li "<termine2>"
```

Per ogni file trovato, leggi le sezioni più rilevanti (H2 intorno al match).

### Output Fase 2

Lista di corrispondenze (eventualmente vuota):

```
[
  { source: "wiki/<kind>/<slug>.md", section: "<H2 o H3 titolo>", excerpt: "<testo rilevante, max 200 char>" },
  ...
]
```

Se la lista è vuota → la Fase 2 non produce hit; procedi.

---

## Fase 3 — Ricerca codebase

Eseguita **solo per classificazione `componente codebase`** o `ambigua`.

**Estratto pattern** dalla domanda (nome file, nome funzione, nome classe, modulo,
path parziale).

Esegui glob ricorsivo sul repo (path configurato come `code_path` in
`factory.config.yaml`, default `.`):

```bash
# ricerca file per nome o pattern
find . -type f -name "*<pattern>*" -not -path "./.git/*"

# ricerca per contenuto (funzione o classe)
grep -rn "def <function>" .
grep -rn "class <Class>" .
rg -n "<pattern>" --type py .
```

**Output Fase 3**

Lista di corrispondenze (eventualmente vuota):

```
[
  { file: "<path/relativo/file.py>", function: "<nome_funzione>?", class: "<NomeClasse>?" },
  ...
]
```

I campi `function` e `class` sono opzionali (presenti solo se il match individua
con certezza una funzione o una classe specifica).

Se la lista è vuota → la Fase 3 non produce hit; procedi.

---

## Fase 4 — Formattazione risposta

In base alle liste prodotte dalle Fasi 2 e 3, scegli il caso applicabile:

### Caso A — Hit wiki (almeno un elemento in lista Fase 2)

Formula la risposta usando il contenuto estratto. Apponi la citazione esplicita
per ogni affermazione derivata da un artefatto wiki:

```
[^src: <source> §<section>]
```

Esempio:
```
Il modello epistemico a tre livelli garantisce che il tutor non affermi
nulla al di là di ciò che è documentato. [^src: wiki/concepts/design-capability-formativa.md §Modello epistemico]
```

Marker emesso: `RETRIEVAL_FOUND_WIKI`.

### Caso B — Hit codebase (almeno un elemento in lista Fase 3, nessun hit wiki rilevante)

Formula la risposta descrivendo la struttura trovata. Cita il percorso file e,
se disponibili, la funzione o la classe:

```
Il componente si trova in `<file>` [funzione `<function>`, se applicabile].
```

Marker emesso: `RETRIEVAL_FOUND_CODE`.

### Caso C — Hit da entrambe le sorgenti (classificazione `ambigua` con risultati su entrambi i fronti)

Formula la risposta integrando le due sorgenti. Apponi citazioni wiki per i
claim concettuali (formato `[^src: ...]`) e riferimenti file per i claim implementativi.

Marker emesso: `RETRIEVAL_FOUND_WIKI` e `RETRIEVAL_FOUND_CODE` (entrambi).

### Caso D — Miss totale (nessun hit da nessuna sorgente)

**Non generare contenuto non ancorato.** Dichiara esplicitamente la lacuna:

```
Non ho trovato documentazione su "<concetto estratto dalla query>" né nel wiki
né nel codebase analizzato. Questo argomento non è ancora coperto dalla base
di conoscenza del progetto.
```

Emetti immediatamente un gap-record (schema §Formati):

```yaml
concept: "<concetto estratto dalla query>"
original_query: "<testo originale della domanda>"
timestamp: "<ISO-8601 UTC>"
```

Appendi il gap-record a `wiki/gaps.md` (formato append-only, compatibile con il
formato esistente del file).

Marker emesso: `RETRIEVAL_NOT_FOUND`, poi `RETRIEVAL_GAP` dopo l'append.

---

## Schemi di citazione

I due schemi sotto definiscono il contratto strutturato tra `retrieval-protocol`
(produttore) e `tutor` / [epistemic-tag-protocol](mdc:.cursor/skills/epistemic-tag-protocol/SKILL.md) (consumatori). Ogni citazione
deve essere derivata dagli output delle Fasi 2 e 3.

### Schema `wiki_citation`

```yaml
# Prodotto da Fase 2 (RETRIEVAL_FOUND_WIKI)
wiki_citation:
  source: "wiki/concepts/design-capability-formativa.md"   # path relativo al repo — obbligatorio
  section: "Modello epistemico a tre livelli"               # heading H2/H3 più vicino — obbligatorio
  excerpt: "Il tutor opera secondo tre livelli..."          # estratto max 200 caratteri — opzionale
```

Campi:
- `source`: path relativo al repo (es. `wiki/concepts/<slug>.md`). Obbligatorio.
- `section`: testo del heading H2 o H3 più vicino al match. Obbligatorio.
- `excerpt`: estratto testuale dal documento, max 200 caratteri. Opzionale (può essere
  omesso se il retrieval restituisce solo la posizione senza testo circostante).

### Schema `code_citation`

```yaml
# Prodotto da Fase 3 (RETRIEVAL_FOUND_CODE)
code_citation:
  file: ".claude/skills/retrieval-protocol.md"  # path relativo al repo — obbligatorio
  function: "feed_frame"                         # nome funzione — opzionale
  class: "Endpointer"                            # nome classe — opzionale
```

Campi:
- `file`: path relativo al repo del file sorgente. Obbligatorio.
- `function`: nome della funzione specifica, se il retrieval individua uno scope
  funzione. Opzionale (omesso se la ricerca restituisce solo il file senza scope).
- `class`: nome della classe specifica, se il retrieval individua uno scope classe.
  Opzionale (omesso se la ricerca restituisce solo il file senza scope).

### Serializzazione in risposta (formato footnote markdown)

Il tutor serializza le citazioni come footnote markdown in coda all'affermazione
o al paragrafo da cui derivano:

```
[^wiki: wiki/concepts/design-capability-formativa.md §Modello epistemico a tre livelli]
[^code: voice/vad/silero_vad.py::Endpointer.feed_frame]
```

- Formato wiki: `[^wiki: <source> §<section>]`
- Formato code: `[^code: <file>::<class>.<function>]` (se `class` e `function` sono
  entrambi presenti); `[^code: <file>::<function>]` se solo funzione; `[^code: <file>]`
  se solo file.

### Invariante

> **Ogni affermazione di livello epistemico L2** (derivata da documentazione wiki)
> **deve avere almeno un `wiki_citation` allegato.**
>
> Violazioni di questa invariante sono rilevate da [epistemic-tag-protocol](mdc:.cursor/skills/epistemic-tag-protocol/SKILL.md)
> (TSK-351) e classificate come non-conformita'.

---

## Formati

### Marker di esito

I marker segnalano l'esito del retrieval e sono emessi nel log o nel contesto
di sessione per tracciabilità.

| Marker | Condizione |
|---|---|
| `RETRIEVAL_FOUND_WIKI` | Almeno un risultato wiki rilevante trovato e citato |
| `RETRIEVAL_FOUND_CODE` | Almeno un risultato codebase rilevante trovato e citato |
| `RETRIEVAL_NOT_FOUND` | Nessun risultato da nessuna sorgente |
| `RETRIEVAL_GAP` | Lacuna dichiarata e gap-record emesso su `wiki/gaps.md` |

### Schema gap-record

Formato YAML compatibile con il file `wiki/gaps.md` (append-only):

```yaml
concept: "<concetto estratto dalla query>"
original_query: "<testo originale della domanda>"
timestamp: "<ISO-8601 UTC, es. 2026-07-10T14:00:00Z>"
```

Campi obbligatori:
- `concept`: il termine o il concetto principale estratto dalla domanda. Stringa
  breve (max 80 char), non il testo completo della query.
- `original_query`: testo originale della domanda dello studente, verbatim.
- `timestamp`: momento dell'emissione del gap-record (UTC ISO-8601 con `Z`).

---

## Vincoli

1. **Freshness garantita da lettura filesystem corrente**: il retrieval opera sempre
   sulla versione corrente degli artefatti (`wiki/**`, `<code_path>/**`). Nessuno
   snapshot congelato di sessione precedente è usato come sorgente di risposta.
   Ogni esecuzione della skill legge i file al momento della query.

2. **Nessun contenuto non ancorato**: se il tutor non trova un artefatto che supporta
   un'affermazione, dichiara la lacuna (Caso D, Fase 4). Mai generare risposte
   plausibili ma non tracciate a una sorgente reale.

3. **Citazioni verbatim dal testo recuperato**: il contenuto restituito dalla Fase 2
   o 3 è citato fedelmente; il tutor può parafrasare solo se la citazione è
   esplicitamente attribuita (`[^src: ...]`).

4. **Gap-record append-only**: `wiki/gaps.md` è un file append-only. Mai sovrascrivere
   entry esistenti.

5. **Classificazione `ambigua` → doppia ricerca**: per domande cross-dominio non
   scartare una sorgente in anticipo; esegui entrambe le fasi (2 e 3).

---

[^src: management/kanban/EP-045-capability-formativa/US-160-retrieval-vivo-citato/TSK-346-retrieval-protocol-skill.md §Technical Specs]
[^src: management/kanban/EP-045-capability-formativa/US-160-retrieval-vivo-citato/TSK-346-retrieval-protocol-skill.md §Marker di esito]
[^src: management/kanban/EP-045-capability-formativa/US-160-retrieval-vivo-citato/TSK-346-retrieval-protocol-skill.md §Schema gap-record]
