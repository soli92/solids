# Fase 4 — Parallel Deep-Dives (dettaglio completo)

Ambito: dettaglio della Fase 4 di `premortem-protocol.md`. Leggere prima di eseguire la fase.

Ogni failure reason rilevante di Fase 3 viene approfondita in parallelo da un
sub-agent investigatore. È il **fan-out** della premortem, modellato sul pattern
`wiki-keeper-worker` v2.4: sub-agent stateless che ritornano output al caller,
**nessuna scrittura su filesystem dai worker**.

## Cap fan-out — `max_parallel: 8` (HARDCODED)

Il cap è **`max_parallel: 8`**, hardcoded nella skill e **non configurabile** in
v2.16 (ADR-001). Rationale: limite empirico sopra il quale la tassonomia
Tigers/Paper Tigers/Elephants di Fase 5 perde potere discriminante (troppi rischi
indifferenziati → calibrazione degenere). Il numero è fissato verbatim qui, non
deriva da `scheduler.max_parallel` (che vive a un livello diverso — vedi nota DAG).

## Pattern di riuso — `wiki-keeper-worker` v2.4

Non reinventare il fan-out: la Fase 4 riusa lo stesso pattern di
`.claude/agents/wiki-keeper-worker.md` (sub-agent di ingest paralleli, v2.4):

- il caller spawna N sub-agent (uno per failure reason, fino a 8);
- ogni sub-agent **non scrive su disco**: ritorna il proprio output al caller;
- **la scrittura/aggregazione è serializzata sul caller** → nessuna race su
  filesystem (preserva R.S1 single-committer, PATTERN §7 r.12).

## Output per sub-agent — la tripla obbligatoria

Ogni sub-agent ritorna esattamente **tre elementi** per la failure reason assegnata:

1. **Storia del fallimento** — narrazione di **3-7 frasi** (NO bullet list): come,
   in concreto, quella reason ha fatto fallire il piano.
2. **Assunzione nascosta** — l'assunzione che, se falsa, fa crollare lo scenario
   (1-2 frasi).
3. **Early warning signs** — **1-2** segnali osservabili in anticipo che la
   failure si sta materializzando.

Formato di ritorno atteso al caller (narrativo, non tabellare):

```
[Reason: <breve label dalla Fase 3>]
Storia: <3-7 frasi narrative>
Assunzione nascosta: <1-2 frasi>
Early warning: <1-2 segnali osservabili>
```

## Comportamento con > 8 failure reasons

Se Fase 3 ha prodotto **più di 8** reason rilevanti, **niente troncamento
silenzioso**: la skill esegue **2 round serializzati di max 8** ciascuno (es. 11
reason → round 1 di 8 + round 2 di 3), aggregando i risultati di entrambi i round
prima di Fase 5.

## Vincolo di scrittura dei sub-agent

I sub-agent della Fase 4 **non scrivono** in `wiki/`, `management/`,
`code_quality/`, `memory/` né altrove sul filesystem. Il loro unico output è verso
il caller. Ogni side-effect su disco avviene in Fase 5, serializzato dal caller.

## Compatibilità scheduler (PATTERN §18) e OCL (PATTERN §20)

- **DAG / scheduler v2.11**: il cap `max_parallel: 8` della Fase 4 è un **secondo
  livello** di parallelismo, annidato dentro la wave del dominio `premortem`. Con
  `scheduler.max_parallel: 4` e 3 `/premortem` simultanee → fino a 24 sub-agent
  contemporanei nel caso peggiore (composizione N × M — vedi PATTERN §18 e ADR-004).
- **OCL v2.14**: il canale sub-agent → caller è `agent_to_agent`, quindi
  **comprimibile** se l'Output Compression Layer (Caveman) è attivo.

**Criterio di completamento**: ogni failure reason rilevante ha il suo mini-dossier
(tripla) aggregato al caller, entro il cap di 8 per round.

[^src: management/kanban/EP-001-premortem-skill-scaffolding/US-003-parallel-deep-dives-subagent/TSK-003.md §Technical Specs]
[^src: design_&_architecture/decisions/ADR-001.md]
