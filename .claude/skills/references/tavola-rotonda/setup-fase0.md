# Fase 0 — Setup: procedura dettagliata

**Ambito**: passi 1-7 di Fase 0 (Setup) del Protocollo Tavola Rotonda.
**Gate**: ogni avvio sessione tramite `/tavola-rotonda`.
**Riferimento origine**: `.claude/skills/tavola-rotonda-protocol.md` §Fase 0.

---

## Input

Topic del problema (dal comando `/tavola-rotonda`), parametri opzionali
(`--partecipanti=<lista>`, `--max-round=<N>`, `--budget=<USD>`, `--critico=<slug>`).

Non procedere al passo successivo se un passo fallisce. Tutti i passi sono
sequenziali e il fallimento di uno blocca l'intera fase.

## Passo 0 — Modalità `setup` (ADR-EP073-001)

La Fase 0 la esegue `tavola-rotonda-moderatore` invocato con `modalita: setup`. Non lancia i
partecipanti: al termine restituisce alla sessione principale il path del registro, i
partecipanti verificati, il Critico e un prompt di Fase 1 per ciascuno (solo problema
riformulato, criteri di successo e ruolo). Le posizioni non si scrivono mai «a nome» dei
partecipanti (R.TR9, gap misurato su una factory derivata).

## Passo 1 — Riformula il problema

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

## Passo 2 — Definisci i criteri di successo

Elenca i criteri che la soluzione finale deve soddisfare. I criteri di successo:
- Sono verificabili esplicitamente in Fase 4 (Sintesi, Passo 1).
- Vengono condivisi con tutti i partecipanti in Fase 1 come contesto della sessione.
- Formato: lista markdown, max 5 voci (chiarezza > completezza; se >5, consolida).

## Passo 3 — Seleziona i partecipanti

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

## Passo 4 — Assegna il ruolo Critico

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

## Passo 5 — Verifica budget

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

## Passo 6 — Crea il blackboard

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
esecuzione: sessione-principale   # ADR-EP073-001
lanci: []                  # {agente, fase, round, agent_id}, scritte dalla sessione principale
partecipanti_lanciati: 0   # lanci effettivi di sub-agenti (R.TR9)
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

## Passo 7 — Transizione a Fase 1

Aggiorna il frontmatter del blackboard: `stato: fase1`.

Inizializza il contatore di sessione `round_senza_progressi = 0` (variabile interna
del moderatore — non nel frontmatter blackboard; usata dalla Fase 3 per la stall
detection, Condizione 4).

**Output Fase 0**: blackboard inizializzato (9 campi frontmatter + 3 sezioni vuote,
`stato: fase1`), topic riformulato, criteri di successo definiti, lista partecipanti
verificata, ruolo Critico assegnato, budget confermato, `round_senza_progressi = 0`.
