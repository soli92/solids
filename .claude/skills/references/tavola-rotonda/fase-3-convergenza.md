# Fase 3 — Convergenza: dettaglio passi 1-4
# Ambito: procedura operativa della Fase 3 del protocollo Tavola Rotonda (EP-039).
# Consumata da: tavola-rotonda-protocol.md al trigger d'ingresso in Fase 3.
# Dipendenze: blackboard con `stato: fase3`, `## Punti Aperti` popolato, `round_corrente ≥ 1`.

---

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

---

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

---

### Passo 3 — Valuta le condizioni di stop (in ordine di priorità)

Valuta le condizioni nell'ordine della tabella. La prima condizione soddisfatta
ha priorità sulle successive — non continuare la valutazione dopo la prima hit.

| Priorità | Condizione | Comportamento |
|---|---|---|
| 1 | `## Punti Aperti` è vuoto (∅) | Stop anticipato → `stato: fase4` |
| 2 | `round_corrente ≥ max_round` | Stop forzato → `stato: fase4` |
| 3 | Costo misurato della tavola (+ prossimo round) > `budget.max_cost_usd` | Stop forzato → `stato: fase4` + WARNING budget |
| 4 | Stallo: 2 round consecutivi senza nuovi accordi | Stop forzato → `stato: fase4` + WARNING stallo |

**Dettaglio condizioni:**

- **Condizione 1**: sezione `## Punti Aperti` vuota o priva di voci dopo il Passo 2b.
  Indica convergenza completa — fine del dibattito.
- **Condizione 2**: il valore di `round_corrente` (dopo l'incremento del Passo 2c) è
  ≥ `max_round`. Tetto esplicito al numero di round (R.TR8).
- **Condizione 3**: il moderatore legge `costo_misurato_usd` e `costo_round_medio_usd`
  passati dalla sessione principale (misurati con `cost_alert.py`, comando §4.4). Stop se
  `costo_misurato_usd ≥ budget.max_cost_usd` **oppure** se `costo_misurato_usd +
  costo_round_medio_usd > budget.max_cost_usd` (il prossimo round sforerebbe). Con
  `fonte_costo: stima` vale la stessa regola sulla stima, e il WARNING lo dichiara.
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
Costo della tavola: $<X.XX> (fonte: cost_alert.py | stima), prossimo round ~$<R.RR>, budget.max_cost_usd: $<Y.YY>
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

---

### Passo 4 — Transizione

**Se una condizione di stop è soddisfatta**: aggiorna il frontmatter `stato: fase4`.
Poi procedi a Fase 4.

**Se nessuna condizione di stop**: aggiorna il frontmatter `stato: fase2`. Poi
riprendi da **Fase 2** (nuovo round di confronto, con `round_corrente` incrementato).

**Output Fase 3**: `## Accordi (congelati)` aggiornato con i nuovi accordi del round;
`## Punti Aperti` aggiornato; `round_corrente` incrementato. Frontmatter: `stato: fase4`
(se stop) o `stato: fase2` (se loop).
