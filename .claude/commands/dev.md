---
description: Invoca un dev-agent su un singolo TSK (per layer derivato dal TSK, o forzato).
argument-hint: <TSK-id> [<layer>]
---

# /dev — Develop a single TSK (PATTERN §3, operazione `Develop`)

Argomenti utente: `$ARGUMENTS`

- Primo argomento: **TSK-id** (es. `TSK-042`), obbligatorio.
- Secondo argomento (opzionale): **layer** (`be|fe|db|qa`). Se omesso, dedotto
  dal campo `layer:` del frontmatter TSK.

## Procedura

1. **Validazione**
   - Trova il file TSK: `glob management/kanban/**/TSK-<id>.md`. Se 0 match o > 1
     match, STOP e segnala in chat.
   - Leggi il frontmatter. Estrai `layer:` e `consumer:`.
   - Se l'arg 2 è presente e diverge da `layer:` del file, segnala in chat e
     chiedi conferma esplicita (override consapevole).

2. **Selezione agente**
   - `layer: be`  → invoca `be-dev`
   - `layer: fe`  → invoca `fe-dev`
   - `layer: db`  → invoca `db-dev`
   - `layer: qa`  → invoca `qa-dev`
   - `layer: docs` → invoca `docs-dev` (documentazione, skill, agenti, config; v2.19)
   - `layer: infra` → nessun dev-agent disponibile (per ora); STOP e segnala.
   - Se l'agente richiesto non esiste in `.claude/agents/`, STOP: la topologia
     non lo include. Suggerisci di aggiungerlo (vedi `/topology`).

3. **Override consumer**
   - Se il TSK ha `consumer: human` e l'utente sta invocando `/dev`
     esplicitamente, è un **override one-shot**: l'agente procede per QUESTO
     singolo run senza modificare il file. Segnala in chat: "Override one-shot:
     TSK assegnato a human, eseguo come agent per questa invocazione".

4. **Invocazione**
   - Passa al dev-agent il TSK-id come focus. L'agente eseguirà `dev-protocol`
     (skill), tipicamente:
     - Fase 0 (gate) → Fase 5 (handoff `dev-handoff` su `wiki/log.md`)
   - Edit del TSK: `status: todo` → `in-progress` → `done` (oppure resta
     `in-progress` se la DoD non passa interamente).

5. **Report finale**
   - Output al chiamante:
     - TSK consumato + agente usato
     - File toccati (count o lista compatta)
     - DoD pass / partial
     - Link al commit (se applicabile) o all'entry log.md

6. **Verifica di chiusura** *(dopo `status: done`; informativa, mai bloccante)*

   **6a — Review CQRL non eseguita.** Il dispatch automatico del Code Quality Review Layer
   (PATTERN §19) lo fa l'orchestrator su `/run`: invocando `/dev` direttamente l'orchestrator
   non c'e', e un TSK eleggibile resta con `review_status: pending` senza che il code-reviewer
   parta. Il TSK e' eleggibile se ha `review_status: pending` (Fase 4-quater di `dev-protocol`
   con `code_quality.trigger_default`, oppure scritto da chi ha creato il TSK) e il suo layer e'
   in `code_quality.router.layer_filter` (assente = tutti). In quel caso segnala:

   > **CQRL — review non eseguita.** `<TSK-id>` (layer `<layer>`) e' eleggibile al Code Quality
   > Review Layer, ma su `/dev` il dispatch automatico non avviene. Per lanciarla: **`/review <TSK-id>`**

   Altrimenti nessun messaggio.

   **6b — Roll-up della storia.** Conta i TSK della stessa US con stato non di chiusura,
   escluso quello appena chiuso. Se sono 0:

   > **Roll-up disponibile.** `<TSK-id>` era l'ultimo TSK aperto di `<US-id>`: US ed epica possono
   > essere riconciliate (product-manager). Nessuna modifica automatica: il roll-up si propone.

   Se restano TSK aperti, nessun messaggio (niente avviso a ogni chiusura).

## Vincoli

- **Mai `/dev` su un TSK senza `layer:` esplicito.** Apri prima il TPM per
  taskizzare con il campo corretto.
- **Mai forzare `/dev` su TSK con dipendenze aperte.** L'agente STOP per gate.
- L'override consumer è **one-shot**: non cambia il file TSK né `factory.config.yaml`.
  Se vuoi cambiare il routing in modo persistente, edita `factory.config.yaml`
  (vedi `/topology`).
