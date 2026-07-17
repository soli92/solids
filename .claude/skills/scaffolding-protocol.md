# Skill: Scaffolding Protocol

> Adapter Cursor della skill `scaffolding-protocol` definita in PATTERN.md.
>
> Metadata originale — id: scaffolding-protocol; version: 1.0; scope: tutor EP-045 — scala di scaffolding adattivo; invoked_by: `tutor` dopo student_model_read (Step 3 loop Apprendimento). Descrizione: definisce la scala di scaffolding adattivo del tutor EP-045 a tre livelli basati sulla stima di padronanza (mastery) del nodo di competenza corrente. Implementa la "zona di sviluppo prossimale": Livello 1 worked example per mastery < 0.4, Livello 2 esempio con buchi per 0.4..0.7, Livello 3 problema autonomo per mastery >= 0.7. Gestisce la lettura mastery dallo Student Model, la calibrazione della domanda di richiamo in modalita' Apprendimento e il default per nodi assenti.

**Scaffolding Protocol (EP-045)**

Skill invocata da `tutor` (agente tutor) dopo aver ricevuto la mastery del nodo corrente da
`student_model_read`. Determina il livello di scaffolding da applicare alla risposta
e, in modalita' Apprendimento, calibra la tipologia di domanda di richiamo in base
al livello.

Il protocollo implementa il principio della zona di sviluppo prossimale del design
EP-045: non fornire troppo supporto quando lo studente gia' padroneggia il concetto
(demotivante) ne' troppo poco quando non lo padroneggia ancora (bloccante).

Riferimenti: [session-mode-protocol](mdc:.cursor/skills/session-mode-protocol/SKILL.md) (loop Apprendimento Step 3-4, P5),
[epistemic-tag-protocol](mdc:.cursor/skills/epistemic-tag-protocol/SKILL.md) (classificazione L1/L2/L3, INV-T4), INV-T4 (`tutor`),
US-162/TSK-357 (Student Model — prerequisito operativo a regime).

---

## Scala di scaffolding

La mastery letta dallo Student Model determina il livello di scaffolding applicato
alla risposta del tutor. La soglia si applica al nodo di competenza corrente
(`current_node_id` della sessione).

### Livello 1 — Worked Example (mastery < 0.4)

**Trigger**: `mastery_read < 0.4`.

**Comportamento**:
- Il tutor fornisce la risposta completa passo per passo, con spiegazione esplicita
  di ogni scelta e del perche' viene compiuta.
- L'output include: testo esplicativo + esempio integrale funzionante + eventuali
  snippet di codice con commenti che illustrano ogni passaggio rilevante.
- La risposta non lascia lacune da colmare: lo studente riceve un modello completo
  da cui apprendere per osservazione.

**Domanda di richiamo in modalita' Apprendimento**:
- Al **primo ciclo** sullo stesso nodo: non viene proposta domanda di richiamo
  (il tutor non presuppone che lo studente abbia ancora interiorizzato l'esempio).
- Ai **cicli successivi** sullo stesso nodo (stesso `current_node_id`): viene
  proposta una domanda a risposta chiusa (vedi §Calibrazione domanda di richiamo).

**Marker output**:

```
[SCAFFOLD:L1-worked-example]
```

---

### Livello 2 — Esempio con buchi (0.4 <= mastery < 0.7)

**Trigger**: `0.4 <= mastery_read < 0.7`.

**Comportamento**:
- Il tutor fornisce la struttura della risposta con parti mancanti da completare,
  usando placeholder espliciti nel formato `[??? — completa qui]`.
- L'output include: testo introduttivo + struttura parziale con placeholder + hint
  opzionale sul tipo di completamento atteso.
- Il numero di placeholder e' proporzionale alla complessita' del concetto; ogni
  placeholder corrisponde a un elemento che lo studente dovrebbe gia' saper dedurre
  con la padronanza stimata.

**Domanda di richiamo in modalita' Apprendimento**:
- Viene generata **dopo** che lo studente ha completato i buchi proposti: e' una
  domanda con completamento che verifica la comprensione del legame tra i placeholder
  risolti e il concetto piu' ampio (vedi §Calibrazione domanda di richiamo).

**Marker output**:

```
[SCAFFOLD:L2-guided-practice]
```

---

### Livello 3 — Problema autonomo (mastery >= 0.7)

**Trigger**: `mastery_read >= 0.7`.

**Comportamento**:
- Il tutor non fornisce la risposta: propone direttamente un problema o una domanda
  aperta che richiede allo studente di sintetizzare il concetto autonomamente.
- L'output include: enunciato del problema o della domanda aperta, senza soluzione
  ne' struttura guidata.
- Hint disponibile su richiesta esplicita dallo studente (trigger: frase semanticamente
  equivalente a `"ho bisogno di un suggerimento"`). L'hint e' minimale: indica la
  direzione senza rivelare la soluzione.

**Domanda di richiamo in modalita' Apprendimento**:
- Il problema autonomo **e' gia' la domanda di richiamo**: il tutor non genera una
  domanda separata ma attende che lo studente produca una risposta sintetica
  (vedi §Calibrazione domanda di richiamo, Livello 3).

**Marker output**:

```
[SCAFFOLD:L3-autonomous]
```

---

## Lettura mastery

### Contratto

```
INPUT:
  node_id: str   — identificatore del nodo di competenza nella query corrente
  student_id: str — identificatore dello studente (dalla sessione corrente)

PROCEDURA:
  1. Chiama student_model_read(student_id, node_id).
  2. Legge il campo mastery (float [0.0..1.0]).
     - Se il nodo non e' presente nello Student Model → mastery = 0.0 (default)
       e registra il nodo come nuovo (vedi §Gestione nodo assente).
  3. Applica la scala:
     - mastery < 0.4   → scaffold_level = 1 (worked_example)
     - 0.4 <= mastery < 0.7 → scaffold_level = 2 (guided_practice)
     - mastery >= 0.7  → scaffold_level = 3 (autonomous)

OUTPUT:
  scaffold_level: 1 | 2 | 3
  mastery_read: float        — valore letto (0.0 se nodo assente)
  note: str                  — motivazione della scelta (per log e marker output)
```

### Esempio di output

```
scaffold_level: 2
mastery_read: 0.55
note: "mastery 0.55 → Livello 2 (guided_practice); nodo 'list-comprehension' presente"
```

---

## Calibrazione domanda di richiamo

Applicabile **solo in modalita' Apprendimento** (`session_mode = Apprendimento`,
come determinato da [session-mode-protocol](mdc:.cursor/skills/session-mode-protocol/SKILL.md)). In modalita' Sblocco questa sezione
non viene eseguita.

La domanda di richiamo (Fase Generator, Step 4 del loop) e' calibrata in base al
`scaffold_level` determinato dalla lettura mastery.

### Livello 1 — Domanda a risposta chiusa

Applicabile al ciclo successivo al primo sul medesimo nodo (al primo ciclo non
viene proposta; vedi §Livello 1 — Worked Example).

**Forma**: domanda con risposta deterministica e verificabile, spesso riferita a
un output osservabile o a un fatto concreto appena illustrato nell'esempio.

Esempi di pattern:
- "Quale output produce questo snippet se l'input e' `X`?"
- "In quale riga dell'esempio viene effettuato il controllo `Y`?"
- "Vero o falso: il comportamento di `Z` in questo caso e' `W`?"

**Marker richiesto**: `[GENERATOR:domanda-richiamo]` (applicato da [epistemic-tag-protocol](mdc:.cursor/skills/epistemic-tag-protocol/SKILL.md)
§Separazione Generator/Validator P5).

---

### Livello 2 — Domanda con completamento

**Forma**: domanda che fa riferimento ai placeholder dell'esempio con buchi, chiedendo
allo studente di spiegare o generalizzare il valore inserito o il legame con il
concetto piu' ampio.

Esempi di pattern:
- "Quale valore hai inserito in `[??? — completa qui]` alla riga Y, e perche'?"
- "Perche' il completamento che hai scelto e' coerente con il vincolo Z?"
- "Se cambiassi `X` in `X'`, quale placeholder cambieresti?"

**Marker richiesto**: `[GENERATOR:domanda-richiamo]`.

---

### Livello 3 — Domanda aperta sintetica

Il problema autonomo proposto dal tutor costituisce gia' la domanda di richiamo.
Non viene generata una domanda aggiuntiva: il tutor attende la risposta sintetica
dello studente come step 5 del loop.

**Forma**: formulazione aperta che richiede sintesi, confronto o applicazione del
concetto in un contesto leggermente diverso da quello originale.

Esempi di pattern:
- "Spiega con parole tue il principio Z e in quale scenario lo applicheresti."
- "Confronta l'approccio A con l'approccio B: quale useresti e perche'?"
- "Mostra un caso in cui questo pattern sarebbe inappropriato."

**Marker richiesto**: `[GENERATOR:domanda-richiamo]`.

---

## Gestione nodo assente

Se `student_model_read` non trova il `node_id` richiesto (risposta con campo
`error` o nodo non incluso nel profilo studente), il protocollo applica il seguente
comportamento di default:

1. `mastery_read = 0.0` — lo studente e' considerato al livello minimo di padronanza.
2. `scaffold_level = 1` (worked example) — il tutor fornisce la risposta completa.
3. Il nodo viene registrato come **nuovo** nel campo `note` dell'output:
   ```
   note: "nodo '<node_id>' non trovato nello Student Model — mastery default 0.0; nodo registrato come nuovo"
   ```
4. In modalita' Apprendimento, al termine del ciclo (Step 7 del loop), il tutor
   invoca `student_model_write` per creare il nodo con `outcome` determinato dalla
   Fase Validator e mastery iniziale calcolata secondo la logica dello Student Model
   (US-162/TSK-357).

Questo comportamento garantisce che lo scaffolding operi correttamente anche in
assenza di dati storici per un nodo, senza richiedere un'inizializzazione esplicita
del profilo da parte dello studente.

---

## Nota di dipendenza: Student Model (US-162 / TSK-357)

> Questa skill richiede che lo Student Model (US-162) sia completato per
> operare a regime. In assenza dello Student Model — o fino a quando TSK-357
> non sara' marcato `done` e il wiring TSK-361 non sara' attivo — il tutor
> non dispone di dati reali di mastery e applica il default `mastery = 0.0`
> per tutti i nodi, posizionandosi sempre al Livello 1 (worked example).
>
> Il wiring completo Student Model → scaffolding e' pianificato in TSK-361
> (wave 3, US-162). Fino ad allora questa skill e' correttamente scritta ma
> opera in modalita' degradata (scaffold_level sempre 1, senza aggiornamento
> mastery al termine del ciclo).

---

[^src: management/kanban/EP-045-capability-formativa/US-161-tutor-modello-epistemico/TSK-352-scaffolding-protocol.md §Technical Specs]
[^src: management/kanban/EP-045-capability-formativa/US-161-tutor-modello-epistemico/US-161.md §Business Rules]
[^src: wiki/concepts/design-capability-formativa.md §Il loop di retrieval practice]
[^src: .claude/skills/session-mode-protocol.md §Loop di interazione]
[^src: .claude/agents/tutor.md §TODO wave 3 — wiring Student Model]
