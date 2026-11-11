# Layer FE — State Matrix nel DoD (dettaglio completo)

Ambito: dettaglio della sezione Layer FE State Matrix di `scrivi-task.md`. Leggere
prima di applicare il block. Condizionale: solo per TSK con `layer: fe`.

---

> Sezione opt-in (US-021, Leva 4). Contromisura strutturale al failure mode §2
> «esplosione combinatoria degli stati UI» di `wiki/concepts/fe-agent-failure-modes.md`.

**Trigger.** Si applica solo a TSK con `layer: fe` **e** `factory.config.yaml.fe_correctness.state_matrix_inject: true`.
Quando entrambe le condizioni sono vere, il task scritto include il block «DoD FE — stati obbligatori» qui sotto.

**Gate esplicito.** A flag `state_matrix_inject: false` (default) lo skill **non inietta nulla**:
comportamento identico a oggi. Nessun block, nessuna riga aggiunta.

**Block template (VERBATIM).** Inserire le seguenti 10 righe in una sezione `## DoD FE — stati obbligatori`:

```
## DoD FE — stati obbligatori (selezionare quelli applicabili)
- [ ] loading state
- [ ] empty state
- [ ] error state
- [ ] success state (happy path)
- [ ] responsive: mobile (≤ 768px)
- [ ] responsive: desktop (≥ 1280px)
- [ ] dark mode / tema alternativo
- [ ] accessibilità da tastiera (tab order, focus visible)
- [ ] contenuti di lunghezza variabile (testo corto / lunghissimo / overflow)
- [ ] stato disabled / read-only (se form o interazione)
```

**`## DoD FE — stati obbligatori` ≠ `## Acceptance Criteria`.** Sono due sezioni distinte e ortogonali:
- gli **Acceptance Criteria** descrivono *comportamenti misurabili end-to-end*.
- gli **stati FE obbligatori** descrivono *dimensioni di completezza UI ortogonali*.

Tenerle separate evita di confondere «il login funziona» (AC) con «il login è completo in tutti i suoi
stati visivi» (DoD FE).

**Regola di selezione (per il TPM).** Il TPM **deve** selezionare gli stati applicabili al singolo TSK.
**Lasciare il block intatto (10 righe non triage-ate) è un anti-pattern**.

**Motivazione.** I tre failure modes di `fe-agent-failure-modes.md`:

1. **Falso segnale di completamento** (§1) — il FE renderizza «qualcosa» quasi sempre; build verde non
   significa task finito.
2. **Esplosione combinatoria degli stati UI** (§2) — senza checklist esplicita l'agente implementa solo
   `success + default + desktop + light + testo breve` e considera chiuso il task.
3. **Specifica sotto-determinata** (§3) — in assenza di criteri misurabili l'agente inventa le intenzioni.

**Cross-link al visual oracle (EP-005).** La State Matrix è input naturale del visual oracle:
**ogni stato selezionato → uno screenshot da verificare** con `visual-oracle-protocol`.

**Backward compat.** Un TSK FE **senza** la sezione `## DoD FE — stati obbligatori` resta pienamente
valido: **0 ERROR di lint**. Il block è additivo e opt-in.
