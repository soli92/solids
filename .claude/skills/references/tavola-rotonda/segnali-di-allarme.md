# Segnali di allarme durante una sessione Tavola Rotonda
# Ambito: meccanismi di sicurezza obbligatori del protocollo (EP-039).
# Consumata da: tavola-rotonda-protocol.md al trigger di innesco di un segnale.
# Dipendenze: contatore `round_senza_progressi`, campo `budget.max_cost_usd`, blackboard corrente.

Questa foglia documenta i tre meccanismi di sicurezza del protocollo:
i primi due impediscono il runaway della sessione (budget guardrail + stall detection);
il terzo rileva l'inefficacia del ruolo Critico.

---

## Segnale 1 — Budget guardrail (Fase 0, Passo 5)

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

---

## Segnale 2 — Stall detection circuit-breaker (Fase 3, Passo 1 + Passo 3)

**Trigger**: `round_senza_progressi ≥ 2` — 2 round consecutivi senza nuovi punti
aggiunti a `## Accordi (congelati)`.

**Contatore**: `round_senza_progressi` — inizializzato a 0 in Fase 0 (Passo 7),
aggiornato a ogni round in Fase 3 (Passo 1):

- `|Accordi_nuovi| = 0` nel round corrente → `round_senza_progressi += 1`
- `|Accordi_nuovi| > 0` nel round corrente → `round_senza_progressi = 0` (reset)

**Comportamento quando `round_senza_progressi ≥ 2`**:
1. Annotazione `[STALLO]` aggiunta in cima a `## Accordi (congelati)` del blackboard.
2. WARNING stallo emesso (template in `.claude/skills/references/tavola-rotonda/fase-3-convergenza.md`,
   Passo 3 — Condizione 4, cross-ref informativo non procedurale).
3. Transizione a Fase 4 per sintesi forzata (R.TR6 — registro decisioni sempre
   obbligatorio).
4. Fase 4 aggiunge il WARNING obbligatorio prima di `### Soluzione`:
   > **Sintesi su stallo: la sessione è terminata per mancanza di progressi
   > (≥2 round senza nuovi accordi). La soluzione riflette il massimo consenso
   > raggiunto, non un accordo completo.**
5. Fase 4 imposta `stato: terminata` al termine (Fase 4 Passo 3).

**Contesto**: lo stallo indica divergenza strutturale — i partecipanti non convergono
ulteriormente. Non è un fallimento del protocollo: è informazione utile. La sintesi
forzata documenta il massimo accordo raggiunto e i punti di disaccordo persistente.

**Recovery (post-sessione)**: se la soluzione su stallo non è sufficiente, riavviare
con topic più specifico, criteri di successo più stringenti o un diverso set di
partecipanti.

---

## Segnale 3 — Tasso di intervento del Critico (alert di efficacia)

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

**Relazione con Segnale 2**: lo stallo rileva l'assenza di progressi nell'accordo;
il tasso di intervento del Critico rileva l'assenza di pressione critica nel disaccordo.
Sono complementari: la stall detection è condizione di stop per la sessione; il tasso
di intervento è un alert di qualità del Critico che non forza la terminazione ma
richiede un'azione correttiva del moderatore.
