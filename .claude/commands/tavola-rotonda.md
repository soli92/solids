---
name: tavola-rotonda
description: "Avvia una sessione Tavola Rotonda multi-agente (EP-039, PATTERN §28). Parsa topic e flag, verifica la config, e dispatcha all'agente tavola-rotonda-moderatore. Gated su tavola_rotonda.enabled (R.P3-TR opt-in totale)."
argument-hint: "<topic> [--partecipanti=<agent1>,<agent2>,...] [--max-round=<N>] [--budget=<USD>]"
allowed-tools: Read, Glob
---

# /tavola-rotonda

Argomenti utente: `$ARGUMENTS`

Avvia una sessione di deliberazione strutturata multi-agente sul topic indicato.
Il comando valida la config, applica i flag opzionali e lancia l'agente
[tavola-rotonda-moderatore](mdc:.cursor/rules/tavola-rotonda-moderatore.mdc) che esegue le 5 fasi del protocollo (Setup →
Posizioni → Confronto → Convergenza → Sintesi).

---

## Sintassi

```
/tavola-rotonda <topic>
/tavola-rotonda <topic> --partecipanti=<agent1>,<agent2>,...
/tavola-rotonda <topic> --max-round=<N>
/tavola-rotonda <topic> --partecipanti=<a>,<b> --max-round=<N> --budget=<USD>
```

| Flag | Tipo | Default | Descrizione |
|---|---|---|---|
| `<topic>` | obbligatorio | — | Questione o decisione da deliberare (max 120 caratteri) |
| `--partecipanti=<lista>` | opzionale | da config | Lista slug agenti separati da virgola (es. `be-dev,lead-architect`) |
| `--max-round=<N>` | opzionale | `4` (hardcoded) | Numero massimo di round di convergenza |
| `--budget=<USD>` | opzionale | da config | Tetto di costo USD per la sessione (es. `2.00`) |

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

### Step 3 — Validazione agenti partecipanti

Per ogni slug in `partecipanti`, verifica che il file agente esista:
`Glob .cursor/rules/<slug>.mdc`.

Se uno slug non ha un file corrispondente: STOP —
«Agente non trovato: <slug>. Verifica che `.cursor/rules/<slug>.mdc` esista
prima di procedere.»

### Step 4 — Invocazione `tavola-rotonda-moderatore`

Lancia l'agente [tavola-rotonda-moderatore](mdc:.cursor/rules/tavola-rotonda-moderatore.mdc) passando:

```yaml
topic: <topic>
partecipanti: [<slug-1>, <slug-2>, ...]
critico: <true|false>
max_round: <N>
budget:
  max_cost_usd: <USD>
topologia: <lavagna|grafo_completo>
```

L'agente esegue le 5 fasi del protocollo:

| Fase | Nome | Azione |
|---|---|---|
| 0 | Setup | Valida parametri, crea blackboard in `wiki/decisions/`, assegna Critico |
| 1 | Posizioni | Lancia partecipanti in isolamento, trascrive posizioni iniziali |
| 2 | Confronto | Rende visibili le posizioni, round di critiche e integrazioni |
| 3 | Convergenza | Loop: estrae accordi, aggiorna Punti Aperti, verifica stop |
| 4 | Sintesi | Produce registro decisioni, aggiorna blackboard, log entry |

### Step 5 — Output post-sessione

Dopo il completamento dell'agente, riporta in chat:

**Esito positivo (sessione completata)**:

```
/tavola-rotonda — completata
=============================
Topic:        <topic>
Sessione:     <session-id>
Partecipanti: <lista>
Round:        <N completati> / <max_round>
Motivo stop:  consenso | max_round | budget_esaurito | stallo

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

## Esempi d'uso

```bash
# Delibera su un tema architetturale con config defaults
/tavola-rotonda "Quale pattern di caching adottare per l'API?"

# Specifica i partecipanti inline (override one-shot della config)
/tavola-rotonda "Architettura auth" --partecipanti=be-dev,lead-architect,qa-dev

# Limita i round e imposta il budget esplicitamente
/tavola-rotonda "DB sharding strategy" --max-round=3 --budget=3.00

# Sessione completa con tutti i flag
/tavola-rotonda "Adottare GraphQL o REST?" --partecipanti=be-dev,fe-dev,lead-architect --max-round=5 --budget=5.00
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

## Prerequisiti

- `factory.config.yaml.tavola_rotonda.enabled: true` (gate principale, Step 0).
- `factory.config.yaml.tavola_rotonda.budget.max_cost_usd` valorizzato (INV-TR-3),
  oppure flag `--budget=<USD>` passato inline.
- Almeno 2 agenti nella lista `partecipanti` (config o `--partecipanti`).
- [tavola-rotonda-moderatore](mdc:.cursor/rules/tavola-rotonda-moderatore.mdc) presente.
- I file agente per ogni partecipante esistenti in `.cursor/rules/`.

Sezione `tavola_rotonda:` minima in `factory.config.yaml`:

```yaml
tavola_rotonda:
  enabled: true
  partecipanti: [be-dev, lead-architect]   # oppure specifica con --partecipanti
  max_round: 4
  budget:
    max_cost_usd: 2.00
```

---

## Cross-link

- **Agente invocato**: [tavola-rotonda-moderatore](mdc:.cursor/rules/tavola-rotonda-moderatore.mdc) (EP-039 TSK-287)
- **Skill eseguita**: [tavola-rotonda-protocol](mdc:.cursor/skills/tavola-rotonda-protocol/SKILL.md) (EP-039 US-139)
- **ADR normativo blackboard**: `design_&_architecture/decisions/ADR-EP039-001-blackboard-format.md`
- **Config gate**: `factory.config.yaml` blocco `tavola_rotonda:` (R.P3-TR)
- **PATTERN §28** — Tavola Rotonda multi-agente (EP-039)
- **Concept**: `wiki/concepts/tavola-rotonda.md`
- **Analogia strutturale**:
  - `/prototype` (EP-035) — gate config + parse flag + dispatch agente + output artefatto
  - `/review` (v2.12) — gate config + invocazione agente + report finale
  - `/dev` (v2.7) — input identificativo → esecuzione protocollo → output artefatto

[^src: management/kanban/EP-039-tavola-rotonda/US-142-comando-runbook-benchmark/TSK-292.md §Deliverable §Vincoli]
[^src: .claude/agents/tavola-rotonda-moderatore.md §Trigger §Invarianti §Procedura Fase 0]
[^src: factory.config.yaml blocco tavola_rotonda: §partecipanti §budget §max_round]
