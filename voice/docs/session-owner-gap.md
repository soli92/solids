---
id: VOICE-GAP-001
title: "Session-owner gap: nessun componente è responsabile della fine semantica di una sessione vocale"
status: OPEN
created: 2026-07-10
source: wiki/decisions/tavola-rotonda-3f8a1c2d-7b4e-4d5f-8e6a-9c0b1d2e3f47-2026-07-10.md
related: ADR-EP046-001 §C7
---

## Context

Nessun componente del voice channel è oggi responsabile di decidere quando la
sessione vocale è "finita semanticamente". La FSM (`VoiceStateMachine`) gestisce
le transizioni di stato del singolo turno, ma non ha il concetto di "sessione
conclusa" tra turni multipli.

Il problema emerge in tre scenari distinti, identificati durante la sessione Tavola
Rotonda 3f8a1c2d (fonte: Critico qa-dev):

- **Pausa naturale**: l'utente si ferma a riflettere prima di riprendere.
- **Distrazione**: l'utente si allontana temporaneamente ma intende tornare.
- **Abbandono definitivo**: l'utente ha terminato la sessione ma non l'ha chiusa esplicitamente.

Il sistema non distingue tra i tre casi. Il contesto accumulato nei turni precedenti
(prompt chain, session_id, turn_count) continua a crescere senza limite, aumentando
il rischio di degradazione della latenza su sessioni lunghe (Scenario C, ADR-EP046-001).

## Seam corrente (EP-046)

`VoiceSessionManager` (in `voice/core/session.py`) è il candidato owner nominale
introdotto da US-170 EP-046. Nell'implementazione corrente:

- `should_reset()` è no-op: ritorna sempre `False`.
- `end()` è stub: nessuna azione.
- Contratto minimo dichiarato: `session.end()` come trigger di reset, `should_reset()`
  come hook di controllo.

La FSM (`voice/core/state_machine.py`) chiama `should_reset()` prima della
transizione a IDLE al termine di ogni turno (`trigger: turno_completato`), con
log DEBUG del risultato. Il valore `False` non innesca nessuna azione.

## Decision: OPEN

Il timeout semantico completo è out-of-scope per EP-046. Richiede un follow-up ADR
quando il contratto sarà chiaro (almeno 50 sessioni >10 min di campione reale, §C6).

La presenza del seam (interfaccia `VoiceSessionManager` + `SessionContext`) riduce
il rischio di un futuro refactor invasivo della FSM.

## Domande aperte

- Chi chiama `session.end()`? La FSM, il runtime adapter, o un layer esterno?
- Qual è il trigger di reset? Timeout di inattività? Fine esplicita dell'utente? Cambio contesto factory?
- Come si gestisce il contesto accumulato nelle sessioni lunghe?
- Dove si posiziona il timeout semantico rispetto al `pipe_timeout` del file-pipe adapter?

## Conseguenze

- **Scenario C (latenza)**: rischio di degradazione della latenza in sessioni lunghe
  per accumulo contesto. Mitigato parzialmente dal campo `pipe_timeout: 180s`.
- **Riduzione rischio refactor**: la presenza del seam evita modifiche invasive alla
  FSM quando il contratto sarà definito.
- **Debito esplicito**: questo documento serve da reminder per il follow-up ADR.
  Non procedere all'implementazione del timeout semantico senza un ADR approvato.
