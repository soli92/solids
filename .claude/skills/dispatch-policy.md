# Skill: dispatch-policy

**Versione:** v2.27 | **Autore:** orchestrator (single-writer di questa skill)
**Scope:** read-only — descrive routing condizionale, non esegue azioni dirette

Questo documento è il **contratto unico di dispatch condizionale** dell'orchestrator.
Ogni nuova EP che aggiunge logica di routing deve modificare **solo questo file**,
non `orchestrator.md`. L'orchestrator si limita a invocare le sezioni pertinenti.

---

## 0. Preflight locale della factory (opzionale)

Se esiste `.claude/skills/references/dispatch-policy/preflight-locale.md` (file della factory,
assente nel master: l'upgrade non lo tocca), `/run` lo esegue come **primo step**, prima di §1 e
prima di costruire il DAG. Serve alle factory che hanno una procedura di avvio propria (per
esempio una conferma esplicita sui claim in conflitto). Senza il file, nulla: i claim restano
advisory come in ogni altro punto del master (`tools/session/active_sessions.py`).

---

## 1. VCS Branch Preflight (EP-034, v2.25, opt-in)

Gate **informativo read-only** che rende visibile lo stato branch/HEAD dei target VCS
**prima** del wave dispatch — per progetti con repository sotto git submodule.

### Trigger

Attivo **se e solo se**: `factory.config.yaml.vcs.branch_awareness.enabled: true`
AND `branch_awareness.preflight: true`.
A flag spento (default) → **no-op silenzioso** (R.B10).

### Azione

Invocare la skill `vcs-preflight-protocol` (read-only, R.B7) e stampare la tabella
dello stato (`target | mode | branch corrente | branch atteso | HEAD | drift | verdict`)
**in testa all'output di `/run`**, prima del wave summary.
Per ogni riga con verdict `ACTION` mostrare il comando esatto di remediation.

### Vincoli

- Non blocca il dispatch (è informativa).
- Read-only totale: nessun `checkout`/`commit`/`fetch` automatico (R.B7).
- Il blocco effettivo (opt-in) vive nel gate Fase 0 di `dev-protocol`.

---

## 2. Oracle Pre-Check FE (EP-006, v2.17, opt-in)

Gate **deterministico pre-dispatch** per i TSK frontend.

### Trigger

Attivo **se e solo se**:
1. `factory.config.yaml.fe_correctness.dispatch_gate: true`, AND
2. il TSK candidato ha `layer: fe` nel frontmatter.

A gate off (default) → no-op, comportamento identico a v2.16.

### Azione

Per ogni TSK FE candidato invocare la skill `oracle-precheck` (grep deterministico,
**no LLM runtime**). Output atteso:

```json
{ "passed": true|false, "satisfied_by": "cond:X" | null, "message": "<stringa>" }
```

### Gestione esiti

- **`passed: true`** → dispatch normale. Il gate è trasparente.
- **`passed: false`** → fail-loud bloccante: NON dispatchare il TSK; mostrare `message`
  con le 4 strade per aggiungere un oracolo + link al runbook
  `wiki/runbooks/visual-oracle-installation.md`. In un wave, il TSK FE bloccato è
  escluso ma gli altri candidati procedono.

### Logging

Appendere una riga in `memory/episodic/oracle-gate.md`:
```
YYYY-MM-DD | TSK-id | passed|blocked (cond:X) | message
```

---

## 3. A11y Dispatch Fallback (EP-007, v2.18, opt-in)

Chain deterministica **`a11y-specialist > qa-dev > fe-dev`** per dispatch scan a11y.

### Trigger

Attivo **se e solo se** `factory.config.yaml.a11y.enabled: true`.
A flag spento (default) → no-op (R.P3).

### Precedenza ordinata

1. `a11y.agent: true` AND `.claude/agents/a11y-specialist.md` scaffoldato →
   invocare `a11y-specialist`.
2. Altrimenti, `qa-dev` in topologia AND TSK ha `layer: fe` + `status: done` →
   invocare `qa-dev` (skill `accessibility-testing-protocol`).
3. Altrimenti, `fe-dev` scaffoldato →
   invocare `fe-dev` (Modalità 1, tool `a11y-scan.sh`).
4. Altrimenti → fail-loud: STOP, loggare warning in `wiki/log.md`
   (`«Nessun agente disponibile per a11y scan; topologia non compatibile»`).

### Vincolo single-writer

Qualunque agente della chain esegua lo scan è single-writer di `a11y_status:` sul TSK
(ADR-014 §Rationale 6). I tre trigger non sono mai concorrenti sullo stesso TSK.

---

## 4. UX/UI Dispatch Policy (EP-008, v2.18, opt-in)

### Trigger

Attivo **se e solo se** `factory.config.yaml.ux_ui.enabled: true`.
A flag spento (default) → no-op (R.P3).

### Separazione strutturale enforced

L'orchestrator **non assegna MAI** reviewer e designer allo stesso agente nella stessa
catena (ADR-020 §H). I due ruoli sono fisicamente distinti.

### Policy review (`ux-ui-review`)

1. `ux_ui.agents.reviewer: true` AND `.claude/agents/ux-ui-reviewer.md` scaffoldato →
   invocare `ux-ui-reviewer`.
2. Altrimenti → skill `ux-ui-review-protocol` via `fe-dev`/`qa-dev` attivi.

### Policy design (`ux-ui-design`, off-DAG)

1. `ux_ui.agents.designer: true` AND `.claude/agents/ui-designer.md` scaffoldato →
   invocare `ui-designer`.
2. Altrimenti → skill `ux-ui-design-protocol` via `fe-dev`/`qa-dev` attivi.

### Vincoli

- **Nessun auto-chain design → review**: dopo `/ux-ui-design` STOP, suggerire
  `/ux-ui-review` — gate umano obbligatorio (ADR-020 §Decisione).
- **Ordering pipeline FE**: `develop → visual-oracle → ux-ui-review → code-review`.
- `ux_ui_status:` scritto solo dall'agente che esegue la review (single-writer).
- `ui_design_spec:` scritto solo dal TPM nel frontmatter TSK (ADR-020 §A, §F).

### Logging

Appendere entry in `wiki/log.md` + riga in `memory/episodic/ux-ui-runs.md`:
```
YYYY-MM-DD-HH-MM | review|design | TSK-id|adhoc | verdict|deliverable | rubric_violations_count
```

---

## 5. Functional Oracle Dispatch Policy (EP-018, v2.20, opt-in)

### Trigger

Attivo **se e solo se**
`factory.config.yaml.fe_correctness.functional_oracle.enabled: true`.
A flag spento (default) → no-op (R.P3), cascade procede direttamente verso `review`.

### Posizione nel cascade FE

```
develop → visual-oracle → [a11y/ux-ui] → functional-oracle → review
```

Con flag parziali:
- Solo `functional_oracle.enabled: true`, visual-oracle off →
  `develop → functional-oracle → review`.
- Visual-oracle + functional-oracle →
  `develop → visual-oracle → functional-oracle → review`.

### Precondizione sequenziale

Se `fe_correctness.enabled: true` (visual-oracle attivo) e `visual_status: pending` →
**attendere** completamento visual oracle prima di schedulare functional oracle.
Se `visual_status: reject` → functional oracle **SKIPPED** (gate umano sul visual oracle).

### Esecutore

Chain deterministica **`qa-dev > fe-dev`** (precedenza per specializzazione, ADR-067 §A).

### Logging

Appendere entry in `wiki/log.md` + riga in `memory/episodic/functional-oracle-runs.md`:
```
YYYY-MM-DD-HH-MM | TSK-id | verdict | iterations | spec_path
```

---

## 6. Temporal Context Injection (EP-011, v2.18+, opt-in)

### Trigger

Attivo **se e solo se**
`factory.config.yaml.temporal.context_injection.enabled: true`.
A flag spento (default) → exit 0 silenzioso, system prompt invariato (R.P3).

### Azioni sequenziali

1. **Al boot di `/run`**: generare `session_id` (UUID v4) immutabile per la sessione.
2. **Al kickoff di ogni TSK**: impostare `task_started_at` via `tools/temporal/utc-now.sh`.
3. **A ogni invocazione di sub-agent**: invocare
   `tools/temporal/build-temporal-context.sh --task-started-at <ts> --session-id <uuid>`
   e iniettare il blocco come **prima sezione** del system prompt del sub-agent:
   ```
   # Temporal Context (UTC ISO-8601)
   current_datetime: <ricalcolato>
   task_started_at: <immutabile per il TSK>
   session_id: <immutabile per la sessione>
   ```

**Single-writer**: l'orchestrator costruisce e propaga il blocco; i sub-agent non lo
generano autonomamente.

---

## 7. Fase 6 — Capability Relevance Check (EP-033, v2.24)

Sezione informativa, puramente additiva. Non modifica stati, non lancia agenti.

### Trigger e no-op

Si attiva **al termine del wave dispatch** di `/run`. Se `sprint.md` non contiene
TSK con `status: todo` → no-op silenzioso.

### Dati letti

- `sprint.md` — layer e status TSK in coda
- `factory.config.yaml` — flag capability opt-in
- `wiki/log.md` — staleness (>30 giorni) + premortem per-epic

### Regole di suggerimento

| Condizione rilevata | Suggerimento emesso |
|---|---|
| TSK `layer=fe` + `fe_correctness.visual_oracle.enabled: false` | Considera `/visual-oracle` |
| TSK `layer=fe` + `a11y.enabled: false` | Considera `/a11y` |
| ≥3 TSK `done` nella settimana + `analytics.measurement.enabled: true` | Considera `/analytics` |
| ≥1 epic `status: open` + nessun premortem in `wiki/log.md` | Considera `/premortem <epic-id>` |
| `wiki/log.md` ultima entry > 30 giorni | Considera `/semantic-drift-scan` o `/lint` |
| TSK `layer=fe|be` + `code_quality.enabled: false` | Considera `/review` |

### Gate per-suggerimento (verifica installazione)

Prima di emettere **ogni singolo suggerimento**, verificare che
`.claude/commands/<comando>.md` esista. Se assente → suggerimento **soppresso
silenziosamente**. Garantisce zero suggerimenti di capability non installate.

### Formato output

Solo se ≥1 suggerimento non soppresso:
```
## Suggerimenti contestuali

Basato sul contesto dello sprint corrente:
- Considera `/a11y`: hai TSK FE in coda e `a11y.enabled` è spento.
- Considera `/analytics`: 4 TSK completati questa settimana.
```
Se 0 suggerimenti → sezione assente (mai placeholder vuoto).

### Tono

Formule non imperative: «Considera», «Potresti valutare». Mai forme imperative.

---

## 8. Capability Advertisement (v2.27, factory-optimization)

Pattern di auto-dichiarazione per gli agenti. Permette al dispatcher e alla
`lint-checks` skill di validare routing senza hardcoding dei nomi agente.

### Schema

Ogni agente `.claude/agents/*.md` può includere nel frontmatter YAML un blocco:

```yaml
capabilities:
  - <capability-slug>   # commento descrittivo (opzionale)
```

Il blocco è **opzionale e additivo**: agenti senza `capabilities:` continuano a
funzionare normalmente (backward compat totale). La lista non configura permessi —
è una dichiarazione documentativa letta da tool e check di lint.

Per un nuovo slug: 1) frontmatter dell'agente, 2) tabella della foglia, 3) sezione qui se cambia il
dispatch. Tabelle complete (tutti i layer): `.claude/skills/references/dispatch-policy/capability-slugs.md`.

---

## 9. Release Domain Dispatch Policy (EP-059, opt-in)

### Trigger

Attivo **se e solo se** `scheduler.domains.release: enabled` (default `false`, opt-in).
A flag spento (default) → no-op silenzioso; il dominio `release` non viene schedulato
automaticamente (R.P3).

### Condizione di attivazione per TSK

Un TSK entra nel dominio `release` se e solo se ha `layer: release` nel frontmatter.

### Esecutore

Agente `release-manager` (`.claude/agents/release-manager.md`).
Chain deterministica: se `release-manager` non è scaffoldato nella factory →
**STOP fail-loud** con messaggio:
```
Dominio release: agente `release-manager` non trovato al path
`.claude/agents/release-manager.md`. Abilitare il dominio solo dopo aver scaffoldato
l'agente (vedi EP-059).
```

### Vincoli

- **Mai scheduling autonomo**: il dominio `release` viene attivato **solo su delega
  esplicita** dell'orchestrator. Non entra nei wave standard di `/run`.
- **Gate umano obbligatorio**: ogni TSK con `layer: release` richiede conferma esplicita
  prima del dispatch (PATTERN §7 r.16). L'orchestrator propone, non esegue direttamente.
- **Single-writer** `release_status:`: solo `release-manager` scrive questo campo nel
  frontmatter dei TSK `layer: release`.
- La capability slug corrispondente è `release-management` (tabella §8).

### Logging

Appendere entry in `wiki/log.md` al completamento di ogni TSK `layer: release`:
```
release | release-manager <TSK-id> → <verdict> | <ISO-8601>
```

---

## 10. Refactor Skill Layer Dispatch Policy (EP-060, opt-in)

### Trigger

Attivo **se e solo se** `factory.config.yaml.refactor_agent_skills.enabled: true`.
A flag spento (default) → no-op silenzioso; il dominio `refactor` non viene schedulato
automaticamente (R.P3).

### Condizione di attivazione per TSK

Un TSK entra nel dominio `refactor` se e solo se ha `layer: refactor` nel frontmatter,
oppure se l'utente invoca esplicitamente `/refactor <target-path>`.

### Esecutore

Agente `fleet-doctor` (`.claude/agents/fleet-doctor.md`).
Chain deterministica: se `fleet-doctor` non è scaffoldato nella factory →
**STOP fail-loud** con messaggio:
```
Dominio refactor: agente `fleet-doctor` non trovato al path
`.claude/agents/fleet-doctor.md`. Abilitare il dominio solo dopo aver scaffoldato
l'agente (vedi EP-060).
```

### Vincoli

- **Mai scheduling autonomo**: il dominio `refactor` viene attivato **solo su delega
  esplicita** dell'orchestrator o dell'utente. Non entra nei wave standard di `/run`.
- **Gate umano obbligatorio in Fase 2 (Piano)**: ogni refactor richiede approvazione
  esplicita del piano prima dell'esecuzione (PATTERN §7 r.16). L'orchestrator propone,
  non esegue direttamente.
- **Config-gate**: se `refactor_agent_skills.enabled: false` → STOP esplicito con
  istruzioni di attivazione (gestito da `fleet-doctor` al boot). Il dispatcher non
  bypassa questo gate.
- La capability slug corrispondente è `refactor-orchestration` (tabella §8).

### Logging

Appendere entry in `wiki/log.md` al completamento di ogni TSK `layer: refactor`:
```
refactor | fleet-doctor <target-path> → <verdetto> | <ISO-8601>
```

---

## §Testbed Pattern B (TSK-552, SUNSET-EXEMPT)

> Questo paragrafo è un **testbed permanente** per il regression-test di G11
> (dispatch-safety V-9). Non descrive logica di produzione. SUNSET-EXEMPT.

L'agente `pattern-b-testbed` esiste solo nel meta-framework (non arriva nelle derivate:
`META_ONLY_PATHS` di `tools/factory-upgrade-apply.py`) ed e' dispatched via body injection:
- l'orchestrator legge il file dell'agente;
- estrae il body (dopo il frontmatter di chiusura);
- `Task(prompt=body + task)` — il subagent riceve solo il body.

Nota: extract the body degli agenti in `agents/` → prompt="<body>" — Pattern B esplicito, testbed permanente per regression-test G11.

---

## 11. Manifesto caricamento per invocazione (US-319)

Il PATTERN e' indice (`PATTERN.md`, §0-§11) + moduli (§12+, tabella `## Moduli`). Prima di
dispatchare un comando o un agente, carica **solo** i moduli che la sua riga indica.
Mappa completa per comando e agente: leggi obbligatoriamente
`.claude/skills/references/dispatch-policy/manifesto-caricamento.md`; se la foglia manca,
carica indice + tutti i moduli (mai il solo indice: §12+ resterebbero irraggiungibili).

---

## 12. CQRL Auto-Dispatch (opt-in, `code_quality.trigger_default`)

**Trigger**: `code_quality.enabled: true` AND (`trigger_default.enabled: true` AND `TSK.layer ∈
trigger_default.layer` AND `TSK.consumer ∈ trigger_default.consumer`, oppure TSK con
`review_status: pending` scritto da chi lo ha creato). Altrimenti nulla. Con entrambi i trigger
il dispatch avviene una volta sola.
**Precondizione**: `status: done` + `review_status: pending` (impostato dalla Fase 4-quater di
`dev-protocol` o a mano). Assente, `passed` o `rejected` → nulla.
**Esecutore**: `code-reviewer`. Agente assente dalla topologia → WARNING; `review_status` resta `pending`.
**Verdict**: `pass` → `passed`; `conditional` → task_package e re-develop bounded (R.Q4, conferma
umana); `reject` → `rejected` + STOP (gate umano, R.16). Mai merge o deploy automatico.

> **[TRIGGER VINCOLANTE]** Prima di valutare le precondizioni composte (visual, functional) e di
> scrivere il log leggi `.claude/skills/references/dispatch-policy/cqrl-cascade-detail.md`; se la
> foglia manca, STOP e segnala.

---

## 13. Cost Alert prima del lancio (advisory, `analytics.cost_alert.enabled`)

Prima di lanciare agenti — dispatch di `/run`, `/dev`, `/review`, wave di
`parallel-scheduling`, round di `/tavola-rotonda` — esegui una volta:

```bash
python3 tools/analytics/cost_alert.py check --gate 2>/dev/null || true
```

- **Output vuoto** (nessuna regola superata, nessun alert pendente, capability spenta o
  errore): procedi senza dire nulla.
- **Una riga `◉ COSTI … ⚠`**: mostrala e chiedi conferma prima di lanciare. L'utente può
  procedere, ridimensionare (meno partecipanti o subagenti, un modello più economico) o
  fermarsi. La conferma vale per la sessione e per l'alert: non ripetere la domanda allo stesso
  alert nella stessa chat. Un alert nuovo (altro periodo, soglia superata dopo la conferma)
  richiede una nuova conferma.
- Non blocca mai da solo: il gate è la conferma umana, il tool resta fail-open (exit 0).
- In un run senza interazione (agente lanciato da un altro agente) non si chiede nulla: la
  riga va nell'output restituito al chiamante.

Dettaglio della capability: skill `cost-alert-protocol`.

## Cross-link

- `orchestrator.md` — dispatcher di questa skill
- `vcs-preflight-protocol.md` — §1
- `oracle-precheck.md` — §2
- `accessibility-testing-protocol.md` — §3
- `ux-ui-review-protocol.md`, `ux-ui-design-protocol.md` — §4
- `functional-oracle-protocol.md` — §5
- `parallel-scheduling.md` — algoritmo DAG sottostante al dispatch
- `lint-checks.md` Check 4ai — agent infrastructure integrity (tool + skill + command validation)
- `release-protocol.md` — skill orchestrazione release (4 fasi: preparazione → validazione → tag → post-release) — §9
- `refactor-agent-skills.md` — skill orchestrazione refactor (5 fasi: Ricognizione → Piano → Esecuzione → Verifica → Consegna) — §10
