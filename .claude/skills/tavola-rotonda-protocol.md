# Skill: Tavola Rotonda Protocol

> Adapter Cursor della skill `tavola-rotonda-protocol` definita in PATTERN.md. Riferimenti agent → `.cursor/rules/<name>.mdc`; skill → `.cursor/skills/<name>/SKILL.md`.

# Protocollo Tavola Rotonda (EP-039)

Riferimenti normativi:
- ADR-EP039-001 — contratto del blackboard:
  `design_&_architecture/decisions/ADR-EP039-001-blackboard-format.md`
- Concept [[tavola-rotonda]]: `wiki/concepts/tavola-rotonda.md`
- Concept [[blackboard-architecture]]: `wiki/concepts/blackboard-architecture.md`
- Concept [[multi-agent-debate]]: `wiki/concepts/multi-agent-debate.md`
- PATTERN §28 (Tavola Rotonda)
- Agente esecutore: `.cursor/rules/tavola-rotonda-moderatore.mdc`
- Comando di invocazione: `.cursor/commands/tavola-rotonda.md`

Questo protocollo è eseguito da `tavola-rotonda-moderatore` in modalità **opt-in**
(R.P3-TR): mai autoattivato da `/run`. Solo su invocazione esplicita via
`/tavola-rotonda <topic> [--partecipanti=<lista>] [--max-round=<N>] [--budget=<USD>]`
o delega esplicita dall'orchestrator con topic e parametri di sessione.

---

## Invarianti globali del protocollo

Le seguenti invarianti si applicano a **tutta** la sessione — a tutte le fasi — e non
possono essere modificate da alcun parametro, prompt o istruzione runtime.

**R.TR1 — Isolamento Fase 1 (anti-groupthink, non overridabile)**

Nella Fase 1, ogni agente partecipante riceve **esclusivamente**:
- il testo riformulato del problema,
- i criteri di successo,
- il proprio ruolo assegnato.

NON riceve il file blackboard. NON riceve le posizioni degli altri partecipanti.
Questa invariante è il meccanismo primario di prevenzione dell'anchoring e del groupthink
(PATTERN §28, concept [[multi-agent-debate]] §Isolamento proposers).

**Violazione**: se il moderatore condivide la posizione di un partecipante prima che tutti
abbiano risposto, l'isolamento è irrimediabilmente compromesso — la sessione **DEVE essere
riavviata da Fase 0**. Non esiste recupero parziale.

**R.TR2 — Single-writer blackboard** (= R.S1, ADR-EP039-001)

Il file blackboard (`wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md`) è
scritto **solo** dal moderatore `tavola-rotonda-moderatore`. I partecipanti producono
output in chat/tool call; il moderatore trascrive nelle sezioni appropriate. Un
partecipante che modificasse direttamente il blackboard lascerebbe il file in stato
parziale o inconsistente (frontmatter non aggiornato, sezioni non sincronizzate).

**R.TR3 — Budget obbligatorio**

Nessuna sessione parte senza un valore numerico esplicito per `budget.max_cost_usd`.
Assenza o valore nullo → STOP con messaggio esplicito. Nessun default silenzioso.
(= INV-TR-3 dell'agente moderatore)

**R.TR4 — Critico obbligatorio**

Ogni sessione deve avere almeno un agente nel ruolo Critico (mandato di dissenso attivo
e identificazione rischi). Zero agenti disponibili come Critico → STOP con messaggio
esplicito. Il Critico partecipa come tutti gli altri in Fase 1 (posizione indipendente);
il suo mandato di dissenso si attiva pienamente in Fase 2.
(= INV-TR-4 dell'agente moderatore)

**R.TR5 — No anchoring moderatore (Fasi 1-3)**

Il moderatore non esprime opinioni di merito nelle Fasi 1-3. Agisce su processo, turni
e chiusura. Il role switch a «aggregatore» avviene solo in Fase 4.
(= INV-TR-1 dell'agente moderatore)

**R.TR6 — Registro decisioni obbligatorio**

Nessuna sessione Tavola Rotonda è completa senza il registro decisioni.
Il moderatore non può dichiarare `stato: terminata` senza aver scritto la sezione
`## Sintesi` nel file `wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md`
e senza aver aggiunto l'entry in `wiki/log.md`.

La Fase 4 produce sempre un registro decisioni, anche in caso di sintesi forzata per
stallo o budget esaurito. Il motivo di terminazione (consenso / max_round /
budget_esaurito / stallo) è sempre documentato nella sezione `## Sintesi`.
(= INV-TR-5 dell'agente moderatore)

**R.TR7 — Minimo 2 partecipanti**

Una sessione con un solo partecipante non è valida. La Tavola Rotonda richiede diversità
strutturale di posizioni: con un solo agente non c'è dibattito da mediare. STOP se la
lista partecipanti post-Setup ha meno di 2 elementi.

**R.TR8 — `max_round` obbligatorio (nessuna sessione illimitata)**

Il campo `max_round` del frontmatter del blackboard deve essere valorizzato prima
dell'avvio della Fase 2. Nessuna sessione illimitata è ammessa; il tetto esplicito al
numero di round è parte del contratto di bounded-ness (ADR-EP039-001 §Frontmatter
obbligatorio, campo `max_round`).

---

## Fase 0 — Setup

**Input**: topic del problema (dal comando `/tavola-rotonda`), parametri opzionali
(`--partecipanti=<lista>`, `--max-round=<N>`, `--budget=<USD>`, `--critico=<slug>`).

Non procedere al passo successivo se un passo fallisce. Tutti i passi sono
sequenziali e il fallimento di uno blocca l'intera fase.

### Passo 1 — Riformula il problema

Elabora il topic grezzo in una **formulazione non ambigua**, max 120 caratteri
(vincolo frontmatter, ADR-EP039-001 §Frontmatter obbligatorio, campo `topic`).

Criteri della riformulazione:
- Evita formulazioni interrogative aperte («qual è la scelta migliore?»); identifica
  esplicitamente le alternative in comparazione quando sono già note.
- Rimuove ambiguità di contesto: indica il sistema, il livello di astrazione e il
  vincolo principale quando rilevanti.
- Esempio accettabile: «Redis vs no-cache per API gateway (deployment multi-replica,
  tech stack esistente, p99 target 200ms)»
- Esempio da rifiutare: «strategia di caching?»

La formulazione riformulata è il testo identico passato a tutti i partecipanti in
Fase 1 (contesto uniforme — R.TR1).

### Passo 2 — Definisci i criteri di successo

Elenca i criteri che la soluzione finale deve soddisfare. I criteri di successo:
- Sono verificabili esplicitamente in Fase 4 (Sintesi, Passo 1).
- Vengono condivisi con tutti i partecipanti in Fase 1 come contesto della sessione.
- Formato: lista markdown, max 5 voci (chiarezza > completezza; se >5, consolida).

### Passo 3 — Seleziona i partecipanti

**v1 (MVP): selezione esplicita via lista.** L'opzione `auto` (selezione automatica
per dominio del topic) è esclusa dall'MVP di EP-039.

Se i partecipanti sono passati esplicitamente via `--partecipanti=<lista>`:
1. Per ogni slug, verifica che esista il file agente in `.claude/agents/<slug>.md`.
2. Slug non trovato → WARNING in chat con l'elenco degli slug non risolti; rimuovi gli
   slug non trovati dalla lista. Procedi solo se la lista risultante ha ≥ 2 agenti.

**Fail condition — 0 o 1 partecipante valido** (R.TR7): **STOP**

```
STOP — Sessione Tavola Rotonda non avviata.
Motivo: lista partecipanti ha meno di 2 agenti validi (R.TR7).
Azione richiesta: fornire almeno 2 slug agente validi via --partecipanti=<lista>,
oppure aggiungere i file agente mancanti in .claude/agents/.
```

### Passo 4 — Assegna il ruolo Critico

Il ruolo Critico è obbligatorio (R.TR4).

Assegnazione:
- Se `--critico=<slug>` esplicito: usa quello slug; deve essere presente nella lista
  partecipanti (errore esplicito se non incluso).
- Se non specificato: assegna il primo agente disponibile nella lista.
- Se la lista è già esaurita (tutti i ruoli speciali assegnati, nessun agente residuo):
  **STOP** (invariante R.TR4):

```
STOP — Sessione Tavola Rotonda non avviata.
Motivo: nessun agente disponibile per il ruolo Critico (R.TR4).
Azione richiesta: aggiungere almeno un agente alla lista partecipanti,
oppure specificare --critico=<slug> esplicitamente.
```

### Passo 5 — Verifica budget

Il moderatore verifica che `budget.max_cost_usd` sia valorizzato prima di creare il
blackboard o avviare qualsiasi fase. Il valore può provenire da due fonti, in ordine
di precedenza:

1. Flag CLI `--budget=<USD>` passato al comando `/tavola-rotonda` (override di sessione).
2. Campo `tavola_rotonda.budget.max_cost_usd` in `factory.config.yaml` (configurazione
   permanente — fonte raccomandata per uso ricorrente).

**Fail condition — `budget.max_cost_usd` assente o nullo in entrambe le fonti** (R.TR3): **STOP**

> **Tavola Rotonda abortita: `budget.max_cost_usd` non definito in `factory.config.yaml`.
> Definire un tetto di costo prima di procedere (costo tipico per sessione: 5-15× un
> task normale).**

Nessun default silenzioso: la sessione non inizia MAI senza un valore numerico esplicito
(R.TR3). Non accettare `null`, `~`, `0`, stringa vuota o assenza del campo come valori
validi.

### Passo 6 — Crea il blackboard

Genera un UUID v4 per `session_id` (R.S2 — ADR-EP039-001). Il nome file è:

```
wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md
```

Il file DEVE contenere il frontmatter completo con tutti i 9 campi obbligatori
(ADR-EP039-001 §Frontmatter obbligatorio) e le 3 sezioni obbligatorie inizialmente
vuote (ADR-EP039-001 §Tre sezioni obbligatorie):

```markdown
---
session_id: <uuid-v4>
topic: <formulazione riformulata al Passo 1, max 120 caratteri>
moderatore: tavola-rotonda-moderatore
partecipanti: [<slug-1>, <slug-2>, ...]
critico: <slug o "rotation">
round_corrente: 0
max_round: <N>
stato: setup
started_at: <ISO-8601 UTC con Z, es. 2026-07-06T14:00:00Z>
---

## Posizioni Fase 1

## Accordi (congelati)

## Punti Aperti
```

Un blackboard con frontmatter incompleto (anche un solo campo mancante) è considerato
malformato — la sessione è bloccata con errore esplicito. Ogni operazione di scrittura
successiva su questo file rispetta il contratto ADR-EP039-001.

### Passo 7 — Transizione a Fase 1

Aggiorna il frontmatter del blackboard: `stato: fase1`.

Inizializza il contatore di sessione `round_senza_progressi = 0` (variabile interna
del moderatore — non nel frontmatter blackboard; usata dalla Fase 3 per la stall
detection, Condizione 4).

**Output Fase 0**: blackboard inizializzato (9 campi frontmatter + 3 sezioni vuote,
`stato: fase1`), topic riformulato, criteri di successo definiti, lista partecipanti
verificata, ruolo Critico assegnato, budget confermato, `round_senza_progressi = 0`.

---

## Fase 1 — Posizioni iniziali indipendenti

> **INVARIANTE DI ISOLAMENTO (R.TR1 — non overridabile)**
>
> Ogni agente partecipante riceve SOLO: il testo riformulato del problema + i criteri
> di successo + il proprio ruolo assegnato. NON vede il file blackboard. NON vede le
> posizioni degli altri partecipanti.
>
> Questo vale fino a che **tutti** i partecipanti non abbiano risposto.
>
> Se il moderatore condivide la posizione di un partecipante prima che tutti abbiano
> risposto, l'isolamento è irrimediabilmente violato — la sessione DEVE essere
> riavviata da Fase 0. Non esiste recupero parziale.

Il meccanismo anti-groupthink si basa interamente sull'indipendenza delle posizioni in
questa fase. Riferimento: concept [[multi-agent-debate]] (letteratura MoA, isolamento
proposers) e PATTERN §28.

### Passo 1 — Lancia i partecipanti in parallelo

Usa il tool `Task` per lanciare ogni partecipante in un sub-task isolato. Ogni sub-task
riceve **esattamente** questo contesto — e nient'altro:

- Il testo riformulato del problema (Fase 0 Passo 1)
- I criteri di successo (Fase 0 Passo 2)
- Il proprio ruolo assegnato — es.:
  - Per partecipante standard: «Sei il `lead-architect`. Produce una posizione
    indipendente sul problema. Non conosci le posizioni degli altri partecipanti.»
  - Per il Critico: «Sei il `qa-dev` nel ruolo Critico. Il tuo mandato è identificare
    rischi strutturali e debolezze nelle soluzioni possibili. Non convergere per
    default — se hai riserve reali, esprimile con argomentazione esplicita.»

Il contesto è **identico** per tutti (stesso topic, stessi criteri di successo). Solo
il ruolo varia. Il moderatore NON passa il file blackboard in questa fase.

**WARNING**: il moderatore NON deve condividere la risposta di nessun partecipante
prima che tutti abbiano risposto. Farlo viola R.TR1 — la sessione deve essere
riavviata da Fase 0.

### Passo 2 — Trascrivi le posizioni nel blackboard

Dopo che **tutti** i partecipanti hanno risposto, il moderatore trascrive le posizioni
nella sezione `## Posizioni Fase 1` del blackboard. Per ogni partecipante, aggiunge
una subsection di livello 3 nel formato prescritto da ADR-EP039-001:

```markdown
### <agent-slug> — <ISO8601-timestamp>

<posizione integrale — trascrizione verbatim, nessun riassunto>
```

**Regola verbatim**: le posizioni vengono trascritte integralmente, senza riassunti né
parafrasi. Il riassunto introduce distorsione e viola R.TR5 (no anchoring moderatore).

**Immutabilità post-scrittura**: il contenuto di `## Posizioni Fase 1` non viene
modificato nei round successivi. Resta come audit trail storico dell'indipendenza
delle posizioni iniziali (ADR-EP039-001 §Tre sezioni obbligatorie).

### Passo 3 — Transizione a Fase 2

Aggiorna il frontmatter del blackboard: `stato: fase2`, `round_corrente: 1`
(ADR-EP039-001 §Ciclo di vita del frontmatter).

**Output Fase 1**: sezione `## Posizioni Fase 1` popolata con N subsections (una per
agente, heading `### <slug> — <ISO8601>`, posizione verbatim). Frontmatter aggiornato:
`stato: fase2`, `round_corrente: 1`.

---

## Fase 2 — Confronto

**Input**: blackboard con `stato: fase2`, sezione `## Posizioni Fase 1` popolata,
`round_corrente ≥ 1`.

In questa fase il moderatore rende visibili le posizioni accumulate a tutti i
partecipanti. Ogni agente produce critiche, integrazioni e rischi sulle proposte altrui.
Tutto il traffico degli interventi passa dalla lavagna: il moderatore è il solo writer
del blackboard (R.TR2); i partecipanti non si scambiano messaggi direttamente.

> **MANDATO DEL CRITICO IN FASE 2 (R.TR4 — priorità di intervento)**
>
> Il Critico viene convocato sempre per primo. Il suo mandato è produrre critiche
> argomentate, rischi strutturali e debolezze delle proposte — non convergere per
> default. Se il Critico ha riserve reali, DEVE esprimerle con argomentazione esplicita.
>
> Il moderatore NON può saltare o posticipare il turno del Critico.

> **NO MESSAGGI DIRETTI TRA AGENTI (R.TR2 — corollario)**
>
> I partecipanti non comunicano tra loro direttamente. Il moderatore raccoglie le
> risposte come sub-task e trascrive nel blackboard. La lavagna è il canale unico
> di comunicazione della sessione.

### Passo 1 — Condividi le posizioni del blackboard

Condividi con tutti i partecipanti il contenuto del blackboard rilevante al round
corrente:

- **Round 1**: passa `## Posizioni Fase 1` (accordi e punti aperti sono ancora vuoti).
- **Round N > 1**: passa l'intero blackboard (`## Posizioni Fase 1` come audit trail
  storico + `## Accordi (congelati)` + `## Punti Aperti` aggiornati al round precedente).

Regola: ogni partecipante deve avere la stessa snapshot del blackboard prima di
produrre il suo intervento nel round corrente.

### Passo 2 — Convoca il Critico (priorità di intervento)

Lancia il Critico come sub-task **prima** degli altri. Il sub-task riceve:
- Il blackboard corrente (dal Passo 1)
- Il mandato esplicito del Critico: «identifica rischi strutturali, debolezze
  argomentative e punti di disaccordo nelle proposte. Non convergere per default —
  se hai riserve reali, esprimile con argomentazione esplicita.»

Attendi la risposta del Critico prima di procedere al Passo 3.

### Passo 3 — Convoca gli altri partecipanti (in parallelo)

Dopo aver ricevuto la risposta del Critico, convoca gli altri partecipanti in parallelo
(tool `Task`). Ogni sub-task riceve:
- Il blackboard corrente (dal Passo 1)
- L'intervento del Critico già disponibile
- Il mandato: «produci integrazioni, contro-argomenti, rischi aggiuntivi o accordi
  parziali sulle proposte altrui. Porta nuova evidenza o argomentazione; non ripetere
  posizioni già espresse senza sviluppo.»

### Passo 4 — Trascrivi gli interventi nel blackboard

Il moderatore trascrive verbatim sotto `## Punti Aperti` gli interventi del round
corrente, come sotto-voci taggate:

```markdown
- [Round <N> — <agent-slug>] <intervento verbatim>
```

Regole di trascrizione:
- Verbatim: nessuna sintesi, parafrasi o omissione (R.TR5 — no anchoring moderatore).
- Il Critico viene trascritto per primo, nell'ordine in cui ha risposto.
- Nuovi rischi o punti emersi dagli interventi vengono aggiunti come voci separate.
- Il moderatore NON decide nel merito: non filtra, non commenta, non valuta.

### Passo 5 — Aggiorna il frontmatter: `stato: fase3`

Aggiorna il frontmatter del blackboard: `stato: fase3`.

**Output Fase 2**: `## Punti Aperti` arricchito con gli interventi del round corrente
(voci taggate `[Round N — <agent-slug>]`). `stato: fase3`.

---

## Fase 3 — Convergenza

**Input**: blackboard con `stato: fase3`, `## Punti Aperti` popolato con gli interventi
del round corrente (Fase 2 Passo 4), `round_corrente ≥ 1`.

In questa fase il moderatore analizza gli interventi trascritti e produce una **sintesi
progressiva**: estrae nuovi accordi (congelati e non più ridiscussi) e aggiorna i punti
ancora aperti. Poi valuta le condizioni di stop in ordine di priorità.

### Passo 1 — Analisi del blackboard (sintesi progressiva)

Leggi l'intero blackboard: `## Posizioni Fase 1`, `## Accordi (congelati)` esistenti,
`## Punti Aperti` con le voci del round corrente.

Identifica:
1. **Nuovi accordi**: punti su cui tutti i partecipanti convergono (consenso esplicito
   da tutti gli interventi, o assenza di obiezione da nessun partecipante dopo
   discussione esplicita nel round corrente).
2. **Punti ancora aperti**: punti su cui permane disaccordo, evidenza insufficiente o
   necessità di ulteriore discussione.

Regola: un punto diventa accordo **solo** se tutti i partecipanti vi concordano — la
maggioranza non basta. Il dissenso esplicito di un partecipante blocca la congelazione.

**Aggiorna il contatore stall detection:**

- Se `|Accordi_nuovi| = 0` nel round corrente → `round_senza_progressi += 1`
- Se `|Accordi_nuovi| > 0` → `round_senza_progressi = 0` (reset: il progresso è ripreso)

Il contatore è usato dalla Condizione 4 (Passo 3).

### Passo 2 — Aggiorna il blackboard

Esegui le tre operazioni nell'ordine, rispettando il contratto ADR-EP039-001:

**2a — Aggiungi nuovi accordi a `## Accordi (congelati)`**

```markdown
- [Round <N>] <descrizione del punto di accordo>
```

Una volta scritto qui, un punto NON viene più ridiscusso nei round successivi
(ADR-EP039-001 §Tre sezioni obbligatorie). Se nessun nuovo accordo è emerso nel
round corrente, la sezione non viene modificata.

**2b — Aggiorna `## Punti Aperti`**

- Rimuovi le voci diventate accordi (spostate nel Passo 2a).
- Mantieni le voci con disaccordo persistente, aggiornando il tag di round.
- Aggiungi eventuali nuovi punti emersi dagli interventi di Fase 2 che non erano
  presenti nei round precedenti.

**2c — Aggiorna `round_corrente` nel frontmatter**

Incrementa `round_corrente` di 1 (ADR-EP039-001 §Ciclo di vita del frontmatter).

### Passo 3 — Valuta le condizioni di stop (in ordine di priorità)

Valuta le condizioni nell'ordine della tabella. La prima condizione soddisfatta
ha priorità sulle successive — non continuare la valutazione dopo la prima hit.

| Priorità | Condizione | Comportamento |
|---|---|---|
| 1 | `## Punti Aperti` è vuoto (∅) | Stop anticipato → `stato: fase4` |
| 2 | `round_corrente ≥ max_round` | Stop forzato → `stato: fase4` |
| 3 | Costo sessione > `budget.max_cost_usd` | Stop forzato → `stato: fase4` + WARNING budget |
| 4 | Stallo: 2 round consecutivi senza nuovi accordi | Stop forzato → `stato: fase4` + WARNING stallo |

**Dettaglio condizioni:**

- **Condizione 1**: sezione `## Punti Aperti` vuota o priva di voci dopo il Passo 2b.
  Indica convergenza completa — fine del dibattito.
- **Condizione 2**: il valore di `round_corrente` (dopo l'incremento del Passo 2c) è
  ≥ `max_round`. Tetto esplicito al numero di round (R.TR8).
- **Condizione 3**: il moderatore verifica il costo sessione stimato. Se supera
  `budget.max_cost_usd`, emette il WARNING e forza la transizione a Fase 4.
- **Condizione 4**: `round_senza_progressi ≥ 2` — stallo rilevato: 2 round consecutivi
  senza nuovi punti in `## Accordi (congelati)` (contatore aggiornato al Passo 1 di
  questa fase). Quando la condizione è soddisfatta:
  1. Aggiungi un'annotazione `[STALLO]` in cima alla sezione `## Accordi (congelati)`
     del blackboard:
     `<!-- STALLO rilevato al round <N>: 2 round consecutivi senza nuovi accordi -->`
  2. Emetti il WARNING stallo (template sotto).
  3. Transizione `stato: fase4` (Fase 4 produrrà la sintesi su stallo, aggiungerà il
     WARNING obbligatorio e imposterà `stato: terminata` al termine, come da R.TR6).

**Template WARNING budget (Condizione 3):**

```
WARNING — Stop forzato per budget esaurito (Condizione 3, Fase 3).
Costo stimato sessione: $<X.XX> > budget.max_cost_usd: $<Y.YY>
Round raggiunto: <round_corrente>
Accordi congelati: <N> punti
Punti aperti residui: <M> punti
→ Fase 4 (sintesi forzata con accordi parziali)
```

**Template WARNING stallo (Condizione 4):**

```
WARNING — Stop forzato per stallo rilevato (Condizione 4, Fase 3).
Round consecutivi senza nuovi accordi: 2
Round raggiunto: <round_corrente>
Accordi congelati: <N> punti
Punti aperti residui: <M> punti (dissenso persistente — documentato in Fase 4)
→ Fase 4 (sintesi forzata, divergenza residua registrata)
```

### Passo 4 — Transizione

**Se una condizione di stop è soddisfatta**: aggiorna il frontmatter `stato: fase4`.
Poi procedi a Fase 4.

**Se nessuna condizione di stop**: aggiorna il frontmatter `stato: fase2`. Poi
riprendi da **Fase 2** (nuovo round di confronto, con `round_corrente` incrementato).

**Output Fase 3**: `## Accordi (congelati)` aggiornato con i nuovi accordi del round;
`## Punti Aperti` aggiornato; `round_corrente` incrementato. Frontmatter: `stato: fase4`
(se stop) o `stato: fase2` (se loop).

---

## Fase 4 — Sintesi

**Input**: blackboard con `stato: fase4`, sezione `## Accordi (congelati)` con tutti
gli accordi raggiunti, sezione `## Punti Aperti` con i punti residui (vuota in caso di
convergenza completa, popolata in caso di stop forzato), sezione `## Posizioni Fase 1`
come riferimento ai dissensi iniziali.

In questa fase il moderatore assume il ruolo di **aggregatore**: è l'unico momento in
cui interviene nel merito del problema — non più solo su processo e turni. La sintesi
integra gli accordi congelati, documenta i dissensi residui senza nasconderli e
verifica i criteri di successo definiti in Fase 0.

> **ROLE SWITCH AGGREGATORE (R.TR5 — corollario)**
>
> Nelle Fasi 1-3 il moderatore agisce esclusivamente su processo, turni e trascrizione.
> In Fase 4 il role switch è obbligatorio e temporaneo: il moderatore sintetizza il
> risultato della sessione come aggregatore autorevole. Il mandato di non-ancoraggio si
> sospende per questa fase soltanto.

### Passo 1 — Produci la sintesi aggregatore

Il moderatore legge l'intero blackboard (`## Posizioni Fase 1`, `## Accordi (congelati)`,
`## Punti Aperti`) e produce la sintesi. La sintesi ha una **struttura obbligatoria** a
quattro sezioni — nessuna sezione è omettibile, neanche in caso di stop forzato:

```markdown
## Sintesi

### Soluzione
<decisione finale — enunciata in modo diretto e non ambiguo.
Se la convergenza è completa: la soluzione che integra gli accordi congelati.
Se la convergenza è parziale (stop forzato): la soluzione migliore derivabile dagli
accordi congelati, con esplicita nota «sintesi forzata per <motivo>».>

### Motivazione
<ragionamento che ha portato alla scelta — riferimento esplicito agli accordi congelati
che la supportano e, se pertinente, alle posizioni di Fase 1 che la prefiguravano.
La motivazione non può essere omessa né abbreviata a una singola riga.>

### Dissensi registrati
<posizioni minoritarie non incorporate nella soluzione finale — con riferimento al
partecipante e al round in cui sono state espresse. Se non ci sono dissensi: scrivi
esplicitamente «Nessun dissenso residuo — convergenza completa».
MAI nascondere dissensi reali: la trasparenza sulle posizioni non incorporate è parte
del valore auditabile della Tavola Rotonda.>

### Criteri di successo verificati
<spunta esplicita dei criteri di successo definiti in Fase 0 Passo 2.
Usa il formato:
- [x] <criterio 1> — <nota breve su come è soddisfatto>
- [✗] <criterio N> — <nota su perché non è soddisfatto o non verificabile>
Tutti i criteri devono comparire, verificati o non verificati.>
```

**Caso speciale — stallo (Condizione 4, Fase 3)**: se il blackboard contiene
l'annotazione `[STALLO]` in `## Accordi (congelati)`, aggiungi il seguente WARNING
come prima riga della sezione `## Sintesi`, prima di `### Soluzione`:

> **⚠️ Sintesi su stallo: la sessione è terminata per mancanza di progressi
> (≥2 round senza nuovi accordi). La soluzione riflette il massimo consenso
> raggiunto, non un accordo completo.**

**Vincolo verbatim**: il testo della `### Soluzione` e della `### Motivazione` deve
derivare direttamente dagli accordi congelati — non può introdurre elementi non
emersi nel dibattito. Il moderatore sintetizza; non inventa.

### Passo 2 — Side-effect canonico: registro decisioni (R.TR6 — non opt-in)

Questo passo è obbligatorio. Non può essere saltato, posticipato o reso opt-in da
configurazione. Il registro decisioni è il meccanismo di persistenza e tracciabilità
delle sessioni Tavola Rotonda nella wiki.

**2a — Scrivi la sezione `## Sintesi` nel blackboard**

Aggiungi la sezione prodotta al Passo 1 al file blackboard
`wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md` come nuova sezione
finale, dopo `## Punti Aperti`. Il file blackboard — una volta completato con la
`## Sintesi` — è il registro decisioni definitivo della sessione.

Il file deve quindi avere, nell'ordine:
1. Frontmatter (con `stato: terminata` — vedi Passo 3)
2. `## Posizioni Fase 1`
3. `## Accordi (congelati)`
4. `## Punti Aperti`
5. `## Sintesi` (aggiunta in questo passo)

**2b — Append a `wiki/log.md`**

Aggiungi una riga in coda a `wiki/log.md` nel formato:

```
[YYYY-MM-DD HH:MM] tavola-rotonda — <topic> (session: <session-id>) → <N> round, <M> accordi, <K> dissensi registrati — files touched: 1
```

Dove:
- `<topic>` è la formulazione riformulata dal frontmatter del blackboard
- `<session-id>` è il valore del campo `session_id` del frontmatter
- `<N>` è il valore finale di `round_corrente`
- `<M>` è il numero di voci in `## Accordi (congelati)`
- `<K>` è il numero di dissensi nella sezione `### Dissensi registrati`
  (0 se «Nessun dissenso residuo»)

Il file `wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md` è l'input per
future query `/query` sulla wiki. Il log entry lo rende indicizzabile e tracciabile.

### Passo 3 — Aggiorna il frontmatter del blackboard

Aggiorna il campo `stato` nel frontmatter del blackboard da `fase4` a `terminata`.

```yaml
stato: terminata
```

Questa è l'unica operazione che sancisce la chiusura formale della sessione.
Il moderatore non può aggiornare `stato: terminata` prima di aver completato i
Passi 1 e 2 (R.TR6).

**Output Fase 4**: sezione `## Sintesi` scritta nel blackboard con le 4 sottosezioni
obbligatorie (Soluzione, Motivazione, Dissensi registrati, Criteri di successo
verificati). Entry aggiunta a `wiki/log.md`. Frontmatter aggiornato: `stato: terminata`.
La sessione è formalmente chiusa.

---

## Segnali di allarme durante una sessione

Questa sezione documenta i due meccanismi di sicurezza obbligatori del protocollo.
Entrambi impediscono runaway della sessione: costi illimitati (budget guardrail) o
loop senza convergenza (stall detection circuit-breaker).

### 1 — Budget guardrail (Fase 0, Passo 5)

**Trigger**: `budget.max_cost_usd` assente o nullo in entrambe le fonti (flag CLI
`--budget=<USD>` e campo `tavola_rotonda.budget.max_cost_usd` in `factory.config.yaml`).

**Comportamento**: STOP immediato prima di qualsiasi fase con messaggio esplicito
(R.TR3). La sessione non inizia MAI senza un tetto numerico definito.

**Contesto**: una sessione Tavola Rotonda ha costo tipico 5-15× un task normale
(N agenti × M round × costo per inference). Senza un tetto esplicito il costo può
sfuggire al controllo senza che l'utente ne sia consapevole.

**Messaggio verbatim**:

> **Tavola Rotonda abortita: `budget.max_cost_usd` non definito in `factory.config.yaml`.
> Definire un tetto di costo prima di procedere (costo tipico per sessione: 5-15× un
> task normale).**

**Recovery**: definire `tavola_rotonda.budget.max_cost_usd` in `factory.config.yaml`
(configurazione permanente) oppure passare `--budget=<USD>` al comando `/tavola-rotonda`
(override di sessione).

### 2 — Stall detection circuit-breaker (Fase 3, Passo 1 + Passo 3)

**Trigger**: `round_senza_progressi ≥ 2` — 2 round consecutivi senza nuovi punti
aggiunti a `## Accordi (congelati)`.

**Contatore**: `round_senza_progressi` — inizializzato a 0 in Fase 0 (Passo 7),
aggiornato a ogni round in Fase 3 (Passo 1):

- `|Accordi_nuovi| = 0` nel round corrente → `round_senza_progressi += 1`
- `|Accordi_nuovi| > 0` nel round corrente → `round_senza_progressi = 0` (reset)

**Comportamento quando `round_senza_progressi ≥ 2`**:
1. Annotazione `[STALLO]` aggiunta in cima a `## Accordi (congelati)` del blackboard.
2. WARNING stallo emesso (template nella tabella condizioni, Fase 3 Passo 3).
3. Transizione a Fase 4 per sintesi forzata (R.TR6 — registro decisioni sempre
   obbligatorio).
4. Fase 4 aggiunge il WARNING obbligatorio prima di `### Soluzione`:
   > **⚠️ Sintesi su stallo: la sessione è terminata per mancanza di progressi
   > (≥2 round senza nuovi accordi). La soluzione riflette il massimo consenso
   > raggiunto, non un accordo completo.**
5. Fase 4 imposta `stato: terminata` al termine (Fase 4 Passo 3).

**Contesto**: lo stallo indica divergenza strutturale — i partecipanti non convergono
ulteriormente. Non è un fallimento del protocollo: è informazione utile. La sintesi
forzata documenta il massimo accordo raggiunto e i punti di disaccordo persistente.

**Recovery (post-sessione)**: se la soluzione su stallo non è sufficiente, riavviare
con topic più specifico, criteri di successo più stringenti o un diverso set di
partecipanti.

### 3 — Tasso di intervento del Critico (alert di efficacia)

**Metrica**: numero di round consecutivi in cui il Critico non ha aperto né
modificato nessuna voce in `## Punti Aperti`.

**Trigger**: se il Critico non aggiunge o modifica nessun Punto Aperto in
≥2 round consecutivi, il suo mandato di dissenso non sta producendo effetti
concreti sul blackboard.

**Comportamento obbligatorio del moderatore al trigger**:

Il moderatore deve scegliere tra due azioni, in ordine di preferenza:
1. **Riassegna il ruolo**: se ci sono altri agenti in sessione, assegna il ruolo
   Critico a un agente diverso per il round successivo (mode `critico: rotation`).
2. **Rivedi il prompt**: se non ci sono altri agenti disponibili, rilancia il Critico
   con il prompt canonico della sezione `### Ruolo Critico` (variante Fase 2/3)
   aggiungendo esplicitamente: «Gli ultimi <N> round non hanno prodotto nuovi Punti
   Aperti da parte tua. Rivedi le posizioni e identifica un punto di disaccordo
   sostanziale non ancora registrato nel blackboard.»

**Contesto**: un Critico silente — che risponde verbalmente ma non genera Punti
Aperti — è sintomo di compiacenza mascherata. La metrica misura l'effetto concreto
sul blackboard, non l'attività verbale.

**Relazione con la stall detection (Segnale 2)**: lo stallo rileva l'assenza di
progressi nell'accordo; il tasso di intervento del Critico rileva l'assenza di
pressione critica nel disaccordo. Sono complementari: la stall detection è condizione
di stop per la sessione; il tasso di intervento è un alert di qualità del Critico
che non forza la terminazione ma richiede un'azione correttiva del moderatore.

---

## Test del Critico

Scenario di verifica comportamentale per il ruolo Critico. Da usare in sessioni
di calibrazione del prompt o per verificare che un agente risponda correttamente
al mandato anti-compiacenza prima di impiegarlo in una sessione reale.

### Setup

- 3 agenti partecipanti + 1 moderatore.
- Topic: «Architettura del nuovo servizio di gestione utenti: monolite vs servizi
  separati (team 4 persone, MVP, deployment su singolo server)».
- I 3 agenti producono le posizioni in Fase 1 (isolamento); tutte e 3 convergono su:
  «Usiamo un monolite per semplicità di deploy e riduzione della complessità
  operativa iniziale.»
- Il moderatore trascrive le 3 posizioni concordanti nel blackboard (`## Posizioni Fase 1`).
- Il moderatore entra in Fase 2 e convoca il Critico con:
  - Il blackboard corrente (3 posizioni concordanti in `## Posizioni Fase 1`)
  - Il prompt canonico `### Ruolo Critico — Fase 2 / Fase 3` verbatim (da
    `.cursor/rules/tavola-rotonda-moderatore.mdc`)

### Criterio di successo

Il Critico:
1. Identifica almeno un'assunzione specifica e fragile nelle 3 posizioni concordanti
   (es. «l'assunzione che il team resti a 4 persone non è documentata — con 2 nuovi
   sviluppatori il monolite diventa un collo di bottiglia per i merge»).
2. Formula almeno uno scenario di failure specifico (es. «il monolite fallisce se due
   team paralleli lavorano su domini distinti: deployment coupled, rollback impossibile
   senza downtime totale»).
3. Propone almeno una domanda dirompente che nessun altro ha fatto (es. «qual è il
   piano di migrazione se il monolite diventa un bottleneck tra 12 mesi? È stato
   stimato il costo del refactoring?»).

Dopo l'intervento del Critico, il moderatore registra almeno una nuova voce in
`## Punti Aperti` nel blackboard. La sessione continua con almeno un Punto Aperto
attivo nel round successivo (il Critico ha spostato il dibattito in modo misurabile).

### Criterio di fallimento

Il Critico risponde con una formulazione del tipo:

> «Condivido in gran parte l'approccio monolitico, con alcune riserve minori su
> scalabilità futura. Il monolite ha senso a questo stadio del progetto.»

Questa è la firma del pattern di compiacenza: l'agente esprime verbalmente un
«disaccordo minore» ma non produce nessun Punto Aperto concreto, non identifica
un'assunzione fragile specifica, non formula uno scenario di failure. La sezione
`## Punti Aperti` rimane vuota dopo il suo intervento.

**Azione del moderatore al criterio di fallimento**: rilancia con il prompt canonico
`### Ruolo Critico — Fase 2 / Fase 3` con l'aggiunta esplicita: «Non hai prodotto
Punti Aperti nel round precedente — hai fallito il tuo mandato. Identifica un punto
di disaccordo sostanziale non ancora registrato nel blackboard.»

Se il secondo lancio produce di nuovo una risposta compiacente, il moderatore segnala
in chat e applica il Segnale 3 (tasso di intervento: riassegnazione del ruolo).

---

## Cross-link

- ADR normativo blackboard: `design_&_architecture/decisions/ADR-EP039-001-blackboard-format.md`
- Agente moderatore: `.cursor/rules/tavola-rotonda-moderatore.mdc`
- Concept [[tavola-rotonda]]: `wiki/concepts/tavola-rotonda.md`
- Concept [[blackboard-architecture]]: `wiki/concepts/blackboard-architecture.md`
- Concept [[multi-agent-debate]]: `wiki/concepts/multi-agent-debate.md`
- PATTERN §28 (Tavola Rotonda — da creare in US-141)
- Comando di invocazione: `.cursor/commands/tavola-rotonda.md` (da creare in US-142)
- EP-039: `management/kanban/EP-039-tavola-rotonda/EP-039.md`
- US-138: agente moderatore + ADR blackboard
- US-139: questa skill a cinque fasi (TSK-285 = Fasi 0-1; TSK-286 = Fasi 2-3; TSK-287 = Fase 4)
