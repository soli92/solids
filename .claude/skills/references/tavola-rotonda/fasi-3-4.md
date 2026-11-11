# Fase 3 e Fase 4 — procedura dettagliata

**Ambito**: passi di Fase 3 (convergenza) e Fase 4 (sintesi) del Protocollo Tavola Rotonda.
**Gate**: Fase 3 attivata dopo ogni Fase 2; Fase 4 attivata quando una condizione di stop è
soddisfatta in Fase 3.
**Riferimento origine**: `.claude/skills/tavola-rotonda-protocol.md` §Fase 3 e §Fase 4.
**Esecutore (ADR-EP073-001)**: il subagente `tavola-rotonda-moderatore`, invocato dalla sessione
principale con `modalita: convergenza` (Fase 3, dopo ogni round trascritto: restituisce
`stop: sì/no` e il motivo) e `modalita: sintesi` (Fase 4). I lanci dei round li esegue la
sessione principale.

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

### Passo 3 — Condizioni di stop: dettaglio e WARNING templates

Nota: la tabella delle 4 condizioni è nel backbone (consultata a ogni round). Qui
il dettaglio operativo di ogni condizione e i template WARNING obbligatori.

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

> **Sintesi su stallo: la sessione è terminata per mancanza di progressi
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
