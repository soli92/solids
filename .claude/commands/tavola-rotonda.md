---
name: tavola-rotonda
description: "Avvia una sessione Tavola Rotonda multi-agente (EP-039, PATTERN §28, ADR-EP073-001). Parsa topic e flag, verifica la config; la sessione principale lancia i partecipanti e il moderatore cura setup, convergenza e sintesi. Verifica dei lanci a fine sessione. Gated su tavola_rotonda.enabled (R.P3-TR opt-in totale)."
argument-hint: "<topic> [--partecipanti=<agent1>,<agent2>,...] [--max-round=<N>] [--budget=<USD>]"
allowed-tools: Read, Glob, Write, Edit, Bash, Agent
---

# /tavola-rotonda

Argomenti utente: `$ARGUMENTS`

Avvia una sessione di deliberazione strutturata multi-agente sul topic indicato.
Il comando valida la config, applica i flag opzionali ed esegue le 5 fasi del protocollo
(Setup → Posizioni → Confronto → Convergenza → Sintesi) **nella sessione principale**: è
la sessione principale a lanciare i partecipanti, perché da Claude Code 2.1.289 un subagente
non lancia altri agenti (misurato su una factory derivata, ADR-EP073-001). Il subagente `tavola-rotonda-moderatore`
viene invocato solo per le parti di giudizio: setup, convergenza a ogni round, sintesi.

---

Per la tavola dei flag, gli esempi d'uso, i prerequisiti di configurazione e i cross-link
alle risorse correlate, leggi obbligatoriamente
`.claude/skills/references/tavola-rotonda/esempi-e-prerequisiti.md`;
se il file manca, fermati e segnala prima di procedere.

---

## Procedura

### Step 0 — Gate `tavola_rotonda.enabled` (precondizione assoluta)

Leggi `factory.config.yaml` e controlla il flag:

```
SE factory.config.yaml.tavola_rotonda.enabled == false (default R.P3-TR):
  STOP — non invocare l'agente, non creare file, nessun side-effect.
  Emetti in chat:
    "Tavola Rotonda non abilitata. Aggiungi `tavola_rotonda.enabled: true` +
     `budget.max_cost_usd` in factory.config.yaml"
```

Non emettere un STOP silenzioso: il messaggio deve essere esplicito e orientare
l'azione. Se `tavola_rotonda.enabled: true`, prosegui.

### Step 1 — Parse argomenti

Dall'input `$ARGUMENTS` estrai:

- `topic` — prima stringa non-flag (obbligatoria); se assente, STOP:
  ```
  [/tavola-rotonda] Topic mancante.

  Utilizzo: /tavola-rotonda <topic> [--partecipanti=<a>,<b>] [--max-round=<N>] [--budget=<USD>]

  Esempi:
    /tavola-rotonda "Quale pattern di caching adottare per l'API?"
    /tavola-rotonda "Architettura auth" --partecipanti=be-dev,lead-architect
    /tavola-rotonda "DB sharding strategy" --max-round=3 --budget=3.00

  Fornisci un topic che descriva la questione da deliberare.
  ```
- `flag_partecipanti` — valore di `--partecipanti` se presente (stringa CSV), altrimenti `null`
- `flag_max_round` — valore di `--max-round` se presente (intero), altrimenti `null`
- `flag_budget` — valore di `--budget` se presente (float USD), altrimenti `null`

Validazioni:
- `--max-round` deve essere un intero ≥ 1. Se non valido: STOP — «Valore --max-round non
  valido: <v>. Deve essere un intero ≥ 1.»
- `--budget` deve essere un numero float > 0. Se non valido: STOP — «Valore --budget non
  valido: <v>. Deve essere un numero positivo (es. 2.00).»
- `topic` non può superare 120 caratteri. Se più lungo: tronca a 120 caratteri e segnala
  in chat: «[/tavola-rotonda] Topic troncato a 120 caratteri.»

### Step 2 — Risoluzione parametri (ordine di precedenza)

Applica la cascata di precedenza per ciascun parametro:

**`partecipanti`** (lista agenti):
1. Se `flag_partecipanti` valorizzato → usa i valori CSV splittati (override one-shot)
2. Altrimenti leggi `factory.config.yaml.tavola_rotonda.partecipanti`
3. Se entrambe le fonti producono una lista vuota → **STOP** (gate partecipanti):
   ```
   Specifica almeno 2 partecipanti con `--partecipanti=<a>,<b>` o nella config
   ```

**`max_round`** (intero):
1. Se `flag_max_round` valorizzato → usa quel valore (override one-shot)
2. Altrimenti leggi `factory.config.yaml.tavola_rotonda.max_round`
3. Default hardcoded: `4`

**`budget_max_cost_usd`** (float USD):
1. Se `flag_budget` valorizzato → usa quel valore (override one-shot)
2. Altrimenti leggi `factory.config.yaml.tavola_rotonda.budget.max_cost_usd`
3. Se il valore risultante è `null` o `~` o assente → **STOP** (gate budget):
   ```
   STOP — Sessione Tavola Rotonda non avviata.
   Motivo: budget.max_cost_usd non definito (INV-TR-3).
   Azione richiesta: definire un tetto di costo prima di procedere, aggiungendo
   a factory.config.yaml:
       tavola_rotonda:
         budget:
           max_cost_usd: <valore-USD>   # es. 2.00
   oppure passa il budget inline: /tavola-rotonda <topic> --budget=2.00
   ```

**`critico`** (bool/slug):
1. Leggi `factory.config.yaml.tavola_rotonda.critico.enabled`
2. Default hardcoded: `true`

**`topologia`** (stringa):
1. Leggi `factory.config.yaml.tavola_rotonda.topologia`
2. Default hardcoded: `lavagna`

Dopo la risoluzione, verifica la cardinalità della lista partecipanti: se contiene
meno di 2 agenti → **STOP** con il messaggio del gate partecipanti (cf. sopra).

Segnala in chat i valori risolti:

```
[/tavola-rotonda] Parametri risolti:
  topic:        <topic>
  partecipanti: <lista> (fonte: flag|config)
  max_round:    <N> (fonte: flag|config|default)
  budget_usd:   <USD> (fonte: flag|config)
  critico:      <true|false>
  topologia:    <lavagna|grafo_completo>
```

### Step 2-bis — Costi in token (advisory)

`dispatch-policy` §13: `python3 tools/analytics/cost_alert.py check --gate`. Con una riga `⚠`
mostrala accanto ai parametri risolti e chiedi conferma prima della Fase 0: una tavola lancia
decine di subagenti. Output vuoto → prosegui.

### Step 3 — Validazione agenti partecipanti

Per ogni slug in `partecipanti`, verifica che il file agente esista:
`Glob .claude/agents/<slug>.md`.

Se uno slug non ha un file corrispondente: STOP —
«Agente non trovato: <slug>. Verifica che `.claude/agents/<slug>.md` esista
prima di procedere.»

### Step 4 — Esecuzione delle fasi (ADR-EP073-001)

Annota l'id di questa sessione (`CLAUDE_CODE_SESSION_ID`, o l'UUID della cartella di
scratchpad): serve alla verifica dello Step 5. Ogni lancio di sub-agente restituisce un
agent id: conservali tutti.

**4.0 — Costo di partenza (sessione principale).** Prima della Fase 0 misura quanto è già
costata la chat:

```bash
python3 tools/analytics/cost_alert.py breakdown --period session --json   # campo cost_usd
```

È la base da cui si conta la tavola: il budget vale per la tavola, non per la chat intera.
Dopo il setup scrivila nel frontmatter del registro come `costo_base_usd`. Se il tool non
risponde, scrivi `costo_base_usd: null`: la tavola procede con la stima (4.4), dichiarata come
tale.

**4.1 — Fase 0, setup (moderatore, modalità `setup`).** Lancia `tavola-rotonda-moderatore`
con:

```yaml
modalita: setup
topic: <topic>
partecipanti: [<slug-1>, <slug-2>, ...]
critico: <true|false>
max_round: <N>
budget:
  max_cost_usd: <USD>
topologia: <lavagna|grafo_completo>
ora_utc: <date -u +%Y-%m-%dT%H:%M:%SZ>   # il moderatore non ha Bash: passagli l'ora
```

Restituisce: path del registro creato, partecipanti verificati, Critico, un prompt di Fase 1
per ciascun partecipante. Se restituisce uno STOP (budget, Critico, partecipanti < 2),
fermati e riportalo.

**4.2 — Fase 1, posizioni isolate (sessione principale).** Lancia **in parallelo** ogni
partecipante con il tool Agent (`subagent_type` = slug) e il suo prompt di Fase 1, che
contiene solo problema riformulato, criteri di successo e ruolo (R.TR1: niente registro,
niente posizioni altrui). Quando hanno risposto **tutti**, trascrivi ogni risposta verbatim in
`## Posizioni Fase 1`:

```markdown
### <slug> — <ISO8601> — agent_id <id>

<risposta integrale>
```

Aggiorna il frontmatter: una voce in `lanci` per partecipante
(`{agente: <slug>, fase: 1, round: 0, agent_id: <id>}`), `partecipanti_lanciati`,
`stato: fase2`, `round_corrente: 1`. Se un lancio fallisce, scrivi il partecipante come
assente: non ricostruire la sua posizione (INV-TR-6).

**4.3 — Round di confronto (sessione principale).** Per il round corrente lancia **prima il
Critico** con il registro corrente e il mandato del Critico
(`.claude/agents/tavola-rotonda-moderatore.md` §Ruolo Critico, prompt Fase 2); poi gli altri
in parallelo con registro e intervento del Critico. Mandato del round 1: critiche e
integrazioni (`.claude/skills/references/tavola-rotonda/fasi-1-2.md` §Fase 2); dal round 2:
posizione su ciascun Punto Aperto (`.claude/agents/tavola-rotonda-moderatore.md` §Fase 3
Passo 1). Trascrivi verbatim sotto
`## Punti Aperti` come `- [Round <N> — <slug> — agent_id <id>] <intervento>`, aggiungi le voci
in `lanci` (`fase: 2, round: <N>`), `stato: fase3`. In Fasi 1-2 la sessione principale non
esprime giudizi di merito, non riassume e non filtra (R.TR5).

**4.4 — Fase 3, convergenza (moderatore, modalità `convergenza`).** Lancia il moderatore con
`modalita: convergenza`, path del registro e `ora_utc`. Aggiorna Accordi e Punti Aperti,
valuta le condizioni di stop e restituisce `stop: sì|no` con il motivo. Con `stop: no` torna
a 4.3 per il round successivo; con `stop: sì` vai a 4.5.

Il costo va **misurato**, non stimato. Prima di ogni lancio del moderatore in `convergenza`
rimisura (`cost_alert.py breakdown --period session --json`) e passagli:

```yaml
costo_misurato_usd: <cost_usd attuale − costo_base_usd>          # principale + subagenti
costo_round_medio_usd: <costo_misurato_usd / round completati>   # proiezione del prossimo round
fonte_costo: cost_alert.py                                       # oppure: stima (tool assente)
```

Senza `costo_base_usd` (tool assente o in errore) passa la tua stima con
`fonte_costo: stima`. Il moderatore non decide mai sul budget a numeri inventati.

**4.5 — Fase 4, sintesi (moderatore, modalità `sintesi`).** Lancia il moderatore con
`modalita: sintesi`, path del registro e `ora_utc`: scrive sintesi e registro decisioni,
appende la voce in `wiki/log.md` e imposta `stato: terminata`.

In nessuna modalità il moderatore lancia altri agenti. Il registro ha un solo scrittore per
volta: la sessione principale (lanci, posizioni, interventi) o il moderatore (setup, accordi,
sintesi), mai in parallelo; i partecipanti non lo scrivono (R.TR2, ADR-EP073-001 D3).

### Step 5 — Verifica dei lanci e output post-sessione

**Prima di riportare l'esito**, verifica dal registro che ogni intervento venga da un
partecipante lanciato davvero (R.TR9 / INV-TR-6, ADR-EP073-001 D5):

```bash
python3 tools/tavola-rotonda/verifica-lanci.py --registro <path del registro> --sessione <id di questa sessione>
```

- codice 0 → `verdetto: multi-agente`: tutti gli agent id dichiarati hanno una trascrizione in
  questa sessione con il tipo di agente atteso, almeno due agenti distinti;
- codice 1 → `verdetto: non valido` (lanci mancanti, tipo diverso o meno di due agenti):
  l'esito è **NON VALIDO**. Riportalo così, non presentare consenso né accordi come delibera,
  e proponi all'utente di annotarlo nel registro;
- codice 2 → registro o trascrizioni non leggibili: dichiara che la verifica non è stata
  possibile.

Per i registri prodotti prima di ADR-EP073-001 (moderatore che lanciava da solo) resta la modalità
`--agent-id <id del moderatore> --sessione <id>`.

Poi riporta in chat:

**Esito positivo (sessione completata)**:

```
/tavola-rotonda — completata
=============================
Topic:        <topic>
Sessione:     <session-id>
Partecipanti: <lista>
Lanci verificati: <N> su <dichiarati> (verifica-lanci.py: multi-agente | non valido | non verificabile)
Costo:        <costo_misurato_usd> USD su <budget_usd> (fonte: cost_alert.py | stima)
Round:        <N completati> / <max_round>
Motivo stop:  consenso | max_round | budget_esaurito | stallo | nessun_lancio

Registro decisioni: wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md
Log entry:          wiki/log.md (entry develop aggiunta)
```

**Esito con sintesi forzata** (stallo, budget o max_round):

Include il riepilogo positivo + nota:

```
Nota: sessione terminata per <motivo>. La sintesi riflette il massimo
      consenso raggiunto — i Punti Aperti residui sono documentati nel
      registro decisioni.
```

**Esito con STOP** (gate o errore):

```
/tavola-rotonda — STOP
=======================
Step <N> — <motivo del blocco>
Azione richiesta: <descrizione azione>
```

---

## Vincoli

- **Gate `tavola_rotonda.enabled`** (Step 0): il comando non procede e non e' silenzioso
  a flag spento — emette un errore esplicito con le istruzioni di attivazione (R.P3-TR).
- **Budget obbligatorio** (Step 2, INV-TR-3): nessuna sessione parte senza un valore
  numerico per `budget.max_cost_usd`. Il fail e' sempre esplicito, mai silenzioso.
- **Almeno 2 partecipanti** (Step 2): la Tavola Rotonda richiede diversita' strutturale
  minima. 1 solo partecipante e' un errore esplicito.
- **Override one-shot**: `--partecipanti`, `--max-round` e `--budget` non modificano
  `factory.config.yaml`. Per cambiare la config in modo persistente, edita direttamente
  il file.
- **No auto-eval**: il comando non esprime giudizi qualitativi sulla decisione emergente.
  La valutazione e' delegata al registro decisioni prodotto dall'agente.
- **Topic max 120 caratteri**: limite coerente con il frontmatter del blackboard
  (ADR-EP039-001 §Frontmatter obbligatorio).

---

[^src: management/kanban/EP-039-tavola-rotonda/US-142-comando-runbook-benchmark/TSK-292.md §Deliverable §Vincoli]
[^src: .claude/agents/tavola-rotonda-moderatore.md §Trigger §Invarianti §Procedura Fase 0]
[^src: factory.config.yaml blocco tavola_rotonda: §partecipanti §budget §max_round]
