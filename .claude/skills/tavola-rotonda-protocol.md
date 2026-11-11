---
name: tavola-rotonda-protocol
description: >-
  Protocollo 5 fasi per la Tavola Rotonda (Setup→Posizioni→Confronto→Convergenza→Sintesi)
  con blackboard condiviso. L'isolamento in Fase 1 e' il meccanismo primario contro
  anchoring e groupthink. Eseguito da /tavola-rotonda (ADR-EP073-001): la sessione principale lancia
  e trascrive i partecipanti, tavola-rotonda-moderatore cura setup, convergenza e sintesi.

---
# Protocollo Tavola Rotonda (EP-039)

Riferimenti normativi:
- ADR-EP039-001 — contratto del blackboard:
  `design_&_architecture/decisions/ADR-EP039-001-blackboard-format.md`
- Concept [[tavola-rotonda]]: `wiki/concepts/tavola-rotonda.md`
- Concept [[blackboard-architecture]]: `wiki/concepts/blackboard-architecture.md`
- Concept [[multi-agent-debate]]: `wiki/concepts/multi-agent-debate.md`
- PATTERN §28 (Tavola Rotonda)
- Agente esecutore: `.claude/agents/tavola-rotonda-moderatore.md`
- Comando di invocazione: `.claude/commands/tavola-rotonda.md`

**Chi esegue cosa (ADR-EP073-001).** Da Claude Code 2.1.289 un subagente non lancia altri agenti
(gap misurato su una factory derivata). Per questo le Fasi 1 e 2 (lancio dei partecipanti, trascrizione verbatim,
voci `lanci` con agent id) le esegue la sessione principale che ha invocato `/tavola-rotonda`;
`tavola-rotonda-moderatore` viene invocato come subagente nelle modalità `setup` (Fase 0),
`convergenza` (Fase 3) e `sintesi` (Fase 4) e non lancia nessuno. Dove sotto si legge «il
moderatore» per Fasi 1 e 2, si intende la sessione principale nel ruolo di moderatore, con gli
stessi vincoli.

Il protocollo è attivato in modalità **opt-in**
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

Il file blackboard (`wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md`) ha **un
solo scrittore per volta** (ADR-EP073-001 D3): la sessione principale (frontmatter dei lanci,
posizioni, interventi dei round) oppure il moderatore (setup, accordi, sintesi), mai in
parallelo. I partecipanti non lo scrivono mai: producono output nella risposta al lancio e
chi modera trascrive nelle sezioni appropriate. Un
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

**R.TR9 — Nessuna simulazione non dichiarata**

Ogni posizione sul blackboard viene da un partecipante lanciato davvero come sub-agente e
porta l'agent id del lancio (voce in `lanci` del frontmatter). Nessuno scrive posizioni a
nome di altri agenti, neanche per colmare un partecipante assente. A fine sessione
`/tavola-rotonda` verifica con `tools/tavola-rotonda/verifica-lanci.py --registro` che ogni
agent id abbia una trascrizione nella sessione con il tipo di agente atteso: senza almeno due
agenti distinti verificati l'esito è NON VALIDO. (= INV-TR-6 dell'agente moderatore; gap
misurato su una derivata; ADR-EP073-001)

---

## Fase 0 — Setup

> TRIGGER VINCOLANTE: leggi `.claude/skills/references/tavola-rotonda/setup-fase0.md`
> all'avvio di ogni sessione per la procedura completa (Passi 1-7: riformulazione
> problema, criteri successo, selezione partecipanti, assegnazione Critico, budget,
> creazione blackboard, transizione).

Condizioni fail-closed obbligatorie (verificate in Fase 0 prima di procedere):

- **≤1 partecipante valido** (R.TR7) → STOP — sessione non avviata
- **Nessun agente disponibile per Critico** (R.TR4) → STOP — sessione non avviata
- **`budget.max_cost_usd` assente o nullo** (R.TR3) → STOP — sessione non avviata

Nessun default silenzioso per nessuna di queste condizioni. Dettaglio messaggi STOP
e logica passi in `.claude/skills/references/tavola-rotonda/setup-fase0.md`.

**Output Fase 0**: blackboard inizializzato (`stato: fase1`), topic riformulato,
criteri successo definiti, partecipanti verificati, Critico assegnato, budget confermato.

---

## Fase 1 — Posizioni iniziali indipendenti

> **INVARIANTE DI ISOLAMENTO (R.TR1 — non overridabile)**
>
> Ogni agente partecipante riceve SOLO: testo riformulato + criteri successo + ruolo.
> NON vede il blackboard. NON vede le posizioni degli altri partecipanti.
> Violazione → RESTART OBBLIGATORIO da Fase 0. Non esiste recupero parziale.

> TRIGGER VINCOLANTE: leggi `.claude/skills/references/tavola-rotonda/fasi-1-2.md`
> §Fase 1 per la procedura completa (Passi 1-3: lancio parallelo sub-agenti isolati dalla
> sessione principale, trascrizione verbatim con agent id, transizione Fase 2).

**Output Fase 1**: `## Posizioni Fase 1` popolata, `stato: fase2`, `round_corrente: 1`.

---

## Fase 2 — Confronto

> **MANDATO CRITICO (R.TR4 — priorità di intervento)**
>
> Il Critico viene convocato SEMPRE PRIMA degli altri partecipanti. Attendi la sua
> risposta prima di lanciare gli altri in parallelo. Il moderatore NON può saltare
> o posticipare il turno del Critico.

> **NO MESSAGGI DIRETTI TRA AGENTI (R.TR2 — corollario)**
>
> I partecipanti non comunicano tra loro. Il moderatore raccoglie le risposte come
> sub-task e trascrive nel blackboard. La lavagna è il canale unico della sessione.

> TRIGGER VINCOLANTE: leggi `.claude/skills/references/tavola-rotonda/fasi-1-2.md`
> §Fase 2 per la procedura completa (Passi 1-5: condivisione blackboard, convoca
> Critico first, convoca altri in parallelo, trascrizione verbatim, frontmatter `fase3`).

**Output Fase 2**: `## Punti Aperti` arricchito, `stato: fase3`.

---

## Fase 3 — Convergenza

Valuta le condizioni di stop nell'ordine della tabella. La prima condizione soddisfatta
ha priorità sulle successive.

| Priorità | Condizione | Comportamento |
|---|---|---|
| 1 | `## Punti Aperti` è vuoto (∅) | Stop anticipato → `stato: fase4` |
| 2 | `round_corrente ≥ max_round` | Stop forzato → `stato: fase4` |
| 3 | Costo misurato della tavola (+ prossimo round) > `budget.max_cost_usd` | Stop forzato → `stato: fase4` + WARNING budget |
| 4 | Stallo: 2 round consecutivi senza nuovi accordi | Stop forzato → `stato: fase4` + WARNING stallo |

> TRIGGER VINCOLANTE: leggi `.claude/skills/references/tavola-rotonda/fasi-3-4.md`
> §Fase 3 per la procedura completa (Passi 1-4: analisi blackboard, update 2a/2b/2c,
> dettaglio condizioni stop + WARNING templates budget/stallo, transizione).

**Se nessuna condizione stop**: `stato: fase2`, riprendi da Fase 2 (round successivo).
**Se condizione stop**: `stato: fase4`, procedi a Fase 4.

---

## Fase 4 — Sintesi

> **ROLE SWITCH AGGREGATORE (R.TR5 — corollario)**
>
> Nelle Fasi 1-3 il moderatore agisce solo su processo e trascrizione.
> In Fase 4 il role switch è obbligatorio e temporaneo: il moderatore sintetizza
> come aggregatore autorevole. Il mandato di non-ancoraggio si sospende per questa
> fase soltanto.

> TRIGGER VINCOLANTE: leggi `.claude/skills/references/tavola-rotonda/fasi-3-4.md`
> §Fase 4 per la procedura completa (Passi 1-3: sintesi 4-sezioni obbligatorie,
> registro decisioni R.TR6, wiki/log.md append, `stato: terminata`).

Fail-closed R.TR6: il moderatore NON può impostare `stato: terminata` prima di aver
completato la sezione `## Sintesi` nel blackboard E l'entry in `wiki/log.md`.

**Output Fase 4**: `## Sintesi` scritta, entry `wiki/log.md` appesa, `stato: terminata`.

---

## Segnali di allarme durante una sessione

> TRIGGER VINCOLANTE: leggi `.claude/skills/references/tavola-rotonda/segnali-allarme.md`
> al trigger specifico:
> - Segnale 1 (budget guardrail): `budget.max_cost_usd` assente → STOP immediato
> - Segnale 2 (stall detection): `round_senza_progressi ≥ 2` → WARNING + Fase 4
> - Segnale 3 (tasso Critico): Critico silente ≥2 round → riassegna o rivedi prompt

---

## Test del Critico

> TRIGGER VINCOLANTE: leggi `.claude/skills/references/tavola-rotonda/test-critico.md`
> per il setup completo dello scenario di calibrazione (3 agenti, topic monolite,
> criterio di successo 3-bullet, criterio di fallimento con esempio compiacenza).
>
> Citato da `.claude/agents/tavola-rotonda-moderatore.md` §Ruolo Critico come
> scenario di riferimento per il mandato anti-compiacenza.

---

## Cross-link

- ADR normativo blackboard: `design_&_architecture/decisions/ADR-EP039-001-blackboard-format.md`
- Agente moderatore: `.claude/agents/tavola-rotonda-moderatore.md`
- Concept [[tavola-rotonda]]: `wiki/concepts/tavola-rotonda.md`
- Concept [[blackboard-architecture]]: `wiki/concepts/blackboard-architecture.md`
- Concept [[multi-agent-debate]]: `wiki/concepts/multi-agent-debate.md`
- PATTERN §28 (Tavola Rotonda — da creare in US-141)
- Comando di invocazione: `.claude/commands/tavola-rotonda.md` (da creare in US-142)
- EP-039: `management/kanban/EP-039-tavola-rotonda/EP-039.md`
- US-138: agente moderatore + ADR blackboard
- US-139: questa skill a cinque fasi (TSK-285 = Fasi 0-1; TSK-286 = Fasi 2-3; TSK-287 = Fase 4)

## Foglie di dettaglio

| Foglia | Path | Sezione coperta |
|---|---|---|
| setup-fase0 | `.claude/skills/references/tavola-rotonda/setup-fase0.md` | §Fase 0 Passi 1-7: riformulazione, partecipanti, Critico, budget, blackboard template |
| fasi-1-2 | `.claude/skills/references/tavola-rotonda/fasi-1-2.md` | §Fase 1 (3 passi) + §Fase 2 (5 passi) full detail |
| fasi-3-4 | `.claude/skills/references/tavola-rotonda/fasi-3-4.md` | §Fase 3 (4 passi + WARNING templates) + §Fase 4 (3 passi + sintesi 4-sezioni + wiki/log) |
| segnali-allarme | `.claude/skills/references/tavola-rotonda/segnali-allarme.md` | §Segnali 1-3: budget guardrail, stall detection, tasso Critico |
| test-critico | `.claude/skills/references/tavola-rotonda/test-critico.md` | §Test del Critico: setup, criterio successo/fallimento |
