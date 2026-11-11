---
name: premortem-protocol
description: >-
  Protocollo premortem strutturata via prospective hindsight. 5 fasi: Context → Frame → Raw Premortem → Parallel Deep-Dives → Sintesi. Output Risk Registry con tassonomia Tigers/Paper Tigers/Elephants. Opt-in totale (output mai auto-applicato).
---

# Protocollo Premortem (analisi del rischio via prospective hindsight)

Riferimenti: PATTERN §3 (operazione opzionale `Premortem` v2.16), §5 (frontmatter
opt-in `risk_classification:`), §7 (no nuova invariante — R.P1-R.P3 vivono in
questa skill), [[premortem-skill]] (concept teorico), [[risk-classification-tigers-paper-tigers-elephants]]
(tassonomia output), [[factory-premortem-integration]] (design doc v2.16).

Questa skill è **provider-agnostic**: l'inferenza viene fatta dall'LLM ospitante.
Definisce le 5 fasi che ogni invocazione di premortem deve seguire. È invocata
dal comando `/premortem` (Claude Code), o direttamente come skill da agent che
ne fanno uso esplicito (PM, Arch, Code Reviewer in modalità suggerimento).

## Chi può eseguirla

| Ruolo | Trigger naturale | Note |
|---|---|---|
| **Utente diretto** | `/premortem <descrizione \| EP-XXX \| US-YYY \| TSK-ZZZ \| wiki-page>` | Modalità on-demand, sempre disponibile |
| **PM** (`product-manager`) | prima di `Promote EP draft → review` su epica `high-impact` | Suggerito, mai automatico |
| **Arch** (`lead-architect`) | prima di `Promote design doc draft → approved` su decisioni cross-cutting | Suggerito, mai automatico |
| **Code Reviewer** (`code-reviewer`) | verdict `conditional` su TSK con `risk_classification.tier: tiger-*` | Solo come suggerimento nel `task_package`; mai esecuzione automatica |
| **Orchestrator** | `/run` su wave con artefatti `risk_classification: high-impact` | Solo come suggerimento in dashboard; mai dispatch automatico |

In tutti i casi: invocazione manuale via `/premortem`. Mai auto-trigger (R.P3 opt-in totale).

## Quando attivarla

**Usare** quando il costo di sbagliare è alto e si può ancora cambiare rotta:

- prima di un PATTERN bump major (es. v2.x → v3.0) o di una nuova invariante §7
- prima di promote di un'**epica `high-impact`** draft → review
- prima di promote di un **design doc** con touchpoint cross-cutting
- prima di una migrazione architetturale importante
- prima di un'assunzione chiave non verificabile a priori
- quando la confidence degli stakeholder è alta e va stress-testata
- quando il team ha una brutta sensazione non articolata

**NON usare** per: validazione/feedback generico, domande fattuali, brainstorming
creativo, decisioni già irrevocabilmente prese.

Regola pratica: invoca premortem **quando hai ancora margine di manovra e la
posta è alta**. [^src: wiki/concepts/premortem-skill.md §Quando usarla]

## Invarianti R.P1-R.P3

Tre regole leggere specifiche di questa skill. **Non sono regole §7 PATTERN** —
vivono qui, possono essere violate in casi specifici senza rompere il framework.

- **R.P1 — Output mai auto-applicato**. Il `revised_plan` e la `pre-launch
  checklist` sono **sempre** suggerimenti per l'utente. Mai modifica automatica
  del piano originale (EP/US/TSK body invariato).
- **R.P2 — Bar minimo del contesto**. La skill **non procede** se Fase 1 Context
  Gathering non soddisfa le 3 domande chiave (cosa stai facendo, per chi, come
  appare il successo). Preferire fail-loud, non fail-silent.
- **R.P3 — Opt-in totale**. Factory v2.15 senza la skill scaffoldata si comporta
  identica. Niente lint ERROR se la skill è assente. Niente trigger automatico
  per parole chiave nel testo (ADR-003: solo `/premortem` esplicito).

## Anti-pattern

| Anti-pattern | Motivo | Cosa fare invece |
|---|---|---|
| Auto-apply del `revised_plan` modificando il file target | Viola R.P1 | Emetti suggerimenti in chat, lascia all'utente l'edit |
| Output sanitizzato con contesto insufficiente | Viola R.P2 — produce premortem inutile | Fail-loud, chiedi 1 domanda alla volta |
| Trigger automatico su parole chiave | Viola R.P3 (ADR-003) | Solo `/premortem` esplicito |
| Modifica del body di EP/US/TSK target | Viola R.7 PATTERN | Edita solo frontmatter (e solo se l'utente conferma) |
| Risk Registry con calibrazione degenere (tutto Tiger o tutto Paper Tiger) | Frame Fase 2 non ha funzionato | Riemetti la frase Fase 2 verbatim e richiedi passata più severa |
| Premortem su decisione già irrevocabile | Spreca token e produce ansia inutile | Suggerisci `/premortem` per la prossima decisione |
| Sovrapposizione con CQRL post-merge | CQRL fa evaluation post-fact; la premortem è pre-fact | Usa CQRL pass `premortem-on-merge` (ADR-005, opt-in v2.16) |

## Le 5 Fasi

Le fasi sono dettagliate in foglie dedicate (pattern EP-060 divulgazione progressiva).
Ogni foglia va letta obbligatoriamente prima di eseguire la rispettiva fase.

### Fase 1 — Context Gathering

Costruisce il **dossier** su cui le fasi 2-5 lavorano. Niente premortem parte
finché il **bar minimo** non è soddisfatto (R.P2): 3 domande esatte (cosa stai
facendo / per chi / come appare il successo). Input shape: artefatto kanban,
pagina wiki, o descrizione libera.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (input shapes e loading strategy, logica di deduzione preventiva, comportamento una domanda alla volta, R.P2 fail-loud verbatim, criterio completamento) si trova in:
> `.claude/skills/references/premortem/fase-1-context-gathering.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire la fase.
> Se il file manca → STOP e segnala.

### Fase 2 — Frame Setting

Il **meccanismo psicologico centrale**: enunciare verbatim «È [N mesi] da oggi.
Questo piano è fallito.» Timeframe inferito dal target (TSK=2-4w, US=1-3mo,
EP=6mo, PATTERN-bump=12-18mo), override-abile con `--timeframe=<N>w|<N>mo`.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (tabella timeframe-default per tipologia, input/output, criterio completamento) si trova in:
> `.claude/skills/references/premortem/fase-2-frame-setting.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire la fase.
> Se il file manca → STOP e segnala.

### Fase 3 — Raw Premortem

Genera failure reasons per **5 categorie** (Execution, External, People, Technical,
Assumptions). Numero non fisso: completezza, non padding. Stop quando non emergono
più ragioni non-banali.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (le 5 categorie con esempi narrativi, input/output atteso, criterio completamento) si trova in:
> `.claude/skills/references/premortem/fase-3-raw-premortem.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire la fase.
> Se il file manca → STOP e segnala.

### Fase 4 — Parallel Deep-Dives

Fan-out parallelo, `max_parallel: 8` (hardcoded, ADR-001, non configurabile).
Pattern riusa `wiki-keeper-worker` v2.4. Ogni sub-agent ritorna **tripla**: storia
del fallimento (3-7 frasi) + assunzione nascosta (1-2 frasi) + early warning signs.
Sub-agent non scrivono mai su disco.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (cap fan-out 8 hardcoded rationale, pattern riuso wiki-keeper-worker, tripla obbligatoria, comportamento con >8 reasons, vincolo scrittura sub-agent, compatibilità scheduler e OCL) si trova in:
> `.claude/skills/references/premortem/fase-4-parallel-deep-dives.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire la fase.
> Se il file manca → STOP e segnala.

### Fase 5 — Sintesi

Aggrega i mini-dossier di Fase 4 in **6 sezioni canoniche in ordine obbligatorio**:
Most Likely Failure, Most Dangerous Failure, Hidden Assumption, Revised Plan,
Pre-Launch Checklist, Risk Registry. Calibration check: almeno un Tiger, un Paper
Tiger, un Elephant — altrimenti WARNING esplicito.

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (6 sezioni canoniche con requisiti, schema tabella Risk Registry 9 colonne, header conteggio, calibration check verbatim, esempio completo, output side-effects, telemetria premortem-runs.md, R.P1 riaffermato) si trova in:
> `.claude/skills/references/premortem/fase-5-sintesi.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire la fase.
> Se il file manca → STOP e segnala.
