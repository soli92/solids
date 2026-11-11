---
skill: lint-checks-compression
part_of: lint-checks (modular)
family: compression
parent: lint-checks
description: "Check lint su Compression Layer e Temporal Awareness — check-family compression"
---

# Lint Checks — Compression & Temporal

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 4s (chain profonda senza consistency-check + R.C7), Check 4u (wave chiusa senza governor_decision), Check 4aa (chain senza decision_anchor), Check 4ab (handoff inter-wave senza Temporal Handoff Block), Check 4ab-bis (TSK XL senza State Machine)

Tutti check WARNING-only, opt-in via gate config. Check ordinati per numero.

---

### 4s — Chain profonda senza consistency-check + R.C7 verification lint (Decision-Preserving Compression, EP-015 US-060, ADR-049 §B + ADR-050 §I)

**Pattern allineato a Check 4m/4n/4o/4p/4q/4r (R.P3 opt-in totale)**: WARNING-only, opt-in via
flag config, nessun ERROR meccanico. Check 4s eredita la stessa shape per coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione ADR-049/ADR-050). Il
ban hard di `aggressive` su chain profonda è gestito a runtime dalla pipeline caveman (soft
downgrade default ADR-050 §A, oppure hard fail se `migration.strict: true`): il lint **informa
preventivamente**, non blocca mai `/lint` né il Develop. Mai `heal-eligible` (giudizio
semantico). Coerente con la severity ladder ADR-050 (pre-warning INFO → soft downgrade WARNING
→ hard fail ERROR a runtime, NON nel lint).

Il Check 4s ha **due sotto-check indipendenti** con gate distinti:

#### 4s.1 — Chain inter-agent senza consistency_decision event (gate `consistency_check.required_on_chain`)

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.compression.output.consistency_check.required_on_chain == true
AND chain inter-agent con chain_depth > 3 nel log EP-013 per la chain corrente
AND nessun evento `state: consistency_decision` nel log EP-013 per quella chain
AND NOT (consistency_check_skip_reason valorizzato nel frontmatter TSK o nei metadata handoff)
```

**Gate**: `factory.config.yaml.compression.output.consistency_check.required_on_chain: false`
(default off, opt-in totale, backward compat — R.P3). Se assente o `false` → 4s.1 no-op totale
(non si applica, indipendentemente da `chain_depth`).

**Esenzione**: TSK che dichiara `consistency_check_skip_reason: "<motivo>"` nel frontmatter
(o nei metadata handoff) → no WARNING (il derivatore ha dichiarato esplicitamente che la chain
non è soggetta a inter-hop consistency check, es. "chain mono-dominio a basso rischio drift").
L'esenzione richiede motivazione esplicita.

**Messaggio (template verbatim, placeholder `<chain_id>`, `<N>`)**:

```
Chain <chain_id> ha chain_depth: <N> (> 3) senza alcun evento state: consistency_decision nel log EP-013. Eseguire il consistency-checker (skill `consistency-check-protocol.md`, agente consistency-checker) o aggiungere consistency_check_skip_reason. Vedi ADR-048, US-059. Disabilita 4s.1 impostando compression.output.consistency_check.required_on_chain: false.
```

#### 4s.2 — R.C7 verification lint: `aggressive` su chain profonda (gate `compression.output.enabled`)

**Indipendente da `required_on_chain`** (gate proprio): sempre attivo quando la compression
output è abilitata. Replica documentalmente il trigger R.C7 (PATTERN §20.4, ADR-049 §B/§C).

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.compression.output.enabled == true
AND factory.config.yaml.compression.output.policy_profile == 'aggressive'
AND chain_depth_estimated > 3
AND active_capabilities_count > 5
```

(Replica della formula R.C7 ADR-049 §A: `(chain_depth > 3 AND active_capabilities > 5) OR
chain_depth > 5`. Il sotto-check 4s.2 cattura il ramo combinato `depth > 3 AND caps > 5`; il
ramo shortcut `depth > 5` è gestito a runtime dal soft downgrade ADR-050 e qui resta
implicato dalla condizione `chain_depth_estimated > 3`. Confronto **strict `>`**: boundary
`caps == 5` o `depth == 3` → no warning — coerente con ADR-049 §C "vincolo strict `>`".)

**Gate**: se `compression.output.enabled: false` (default) → 4s.2 no-op totale. Se
`enabled: true` ma `policy_profile != aggressive` → no-op (R.C7 documentale per
`conservative`/`custom`, ADR-049 §D). Se `enabled: true` + `aggressive` → 4s.2 attivo.

**Messaggio (template verbatim, placeholder `<depth>`, `<caps>`)**:

```
R.C7 violation risk: aggressive profile on deep chain (chain_depth_estimated: <depth> > 3, active_capabilities_count: <caps> > 5). A runtime la pipeline caveman applicherà soft downgrade aggressive → conservative (o hard fail se compression.output.migration.strict: true). Considerare policy_profile: conservative. Vedi PATTERN §20.4 R.C7, ADR-049, ADR-050.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][consistency-check][4s.1] chain wave-2026-06-08-003: chain_depth 4 (> 3) senza evento state: consistency_decision. Eseguire consistency-check-protocol o aggiungere consistency_check_skip_reason. Vedi ADR-048, US-059.
- [WARNING][compression][4s.2] R.C7 violation risk: aggressive profile on deep chain (chain_depth_estimated: 4 > 3, active_capabilities_count: 6 > 5). Runtime: soft downgrade aggressive → conservative. Considerare policy_profile: conservative. Vedi PATTERN §20.4 R.C7, ADR-049, ADR-050.
```

**Scenari di verifica**:

| # | sotto-check | `enabled` | `policy_profile` | `required_on_chain` | chain_depth | caps | consistency_decision | skip_reason | esito atteso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 4s.1 | — | — | `false` (default) | 4 | — | assente | — | no warning (gate off, R.P3) |
| 2 | 4s.1 | — | — | `true` | 4 | — | assente | assente | **WARNING 4s.1** (chain profonda senza consistency event) |
| 3 | 4s.1 | — | — | `true` | 4 | — | presente | — | no warning (consistency event presente) |
| 4 | 4s.1 | — | — | `true` | 4 | — | assente | valorizzato | no warning (esenzione motivata) |
| 5 | 4s.1 | — | — | `true` | 3 | — | assente | assente | no warning (boundary: `3 > 3` falso, strict `>`) |
| 6 | 4s.2 | `false` (default) | — | — | 4 | 6 | — | — | no warning (compression off) |
| 7 | 4s.2 | `true` | `conservative` | — | 4 | 6 | — | — | no warning (R.C7 documentale per conservative) |
| 8 | 4s.2 | `true` | `aggressive` | — | 4 | 6 | — | — | **WARNING 4s.2** (R.C7 violation risk) |
| 9 | 4s.2 | `true` | `aggressive` | — | 4 | 5 | — | — | no warning (boundary: `5 > 5` falso, strict `>`) |
| 10 | 4s.2 | `true` | `aggressive` | — | 3 | 6 | — | — | no warning (boundary: `3 > 3` falso, strict `>`) |

**Cross-link**: 4s.1 → skill `consistency-check-protocol.md` + agente `consistency-checker` +
ADR-048; 4s.2 → PATTERN §20.4 R.C7 + ADR-049 (definizione chain profonda) + ADR-050 (migration
soft/strict).

---

### 4u — Wave chiusa senza governor_decision (Temporal Budget Governance, EP-014 US-057, ADR-046 §E)

**Pattern allineato a Check 4m/4n/4o/4p/4q/4r/4s (R.P3 opt-in totale)**: WARNING-only, opt-in via
flag config, nessun ERROR meccanico. Check 4u eredita la stessa shape per coerenza framework.

> **Nota di numerazione**: ADR-046 §E prescrive questo check come «Check 4r»; nel repo corrente
> gli slot 4r (EP-010 US-042), 4s (EP-015 US-060) e «4t» / «4t-migration» (riservato ADR-050 §I
> migration pre-warning + EP-011 US-046/047 → slot 4ab/4ab-bis) sono già occupati,
> quindi il check adotta il prossimo slot libero **4u** preservando l'intento dell'ADR (correzione
> meccanica di numerazione, non cambio di intento).

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale). Mai `heal-eligible` (giudizio
semantico). Replica documentalmente il gate empirico `required_on_wave_close` di EP-014.

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.temporal.budget.required_on_wave_close == true
AND wave chiusa (evento `state: wave_completed` nel log EP-013) senza evento `state: governor_decision`
    accompagnatore nel ts range della wave
AND NOT (temporal_budget_skip_reason valorizzato nel frontmatter TSK o nei metadata wave plan)
```

**Gate**: `factory.config.yaml.temporal.budget.required_on_wave_close: false` (default off, opt-in
totale, backward compat — R.P3). Se assente o `false` → 4u no-op totale (non si applica).

**Esenzione**: TSK che dichiara `temporal_budget_skip_reason: "<motivo>"` nel frontmatter (o nei
metadata wave plan) → no WARNING. L'esenzione richiede motivazione esplicita.

**Messaggio (template verbatim, placeholder `<wave_id>`)**:

```
Wave <wave_id> chiusa (state: wave_completed) senza alcun evento state: governor_decision quando temporal.budget.required_on_wave_close: true. Invocare il temporal-budget-governor (skill temporal-budget-governor.md, dominio scheduler budget) o aggiungere temporal_budget_skip_reason. Vedi PATTERN §18.8, ADR-043..ADR-046. Disabilita Check 4u impostando temporal.budget.required_on_wave_close: false.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][temporal-budget][4u] wave wave-2026-06-08-003: chiusa senza evento state: governor_decision (required_on_wave_close: true). Invocare temporal-budget-governor o aggiungere temporal_budget_skip_reason. Vedi PATTERN §18.8, ADR-046.
```

**Scenari di verifica**:

| # | `required_on_wave_close` | governor_decision nella wave | skip_reason | esito atteso |
|---|---|---|---|---|
| 1 | `false` (default) | assente | — | no warning (gate off, R.P3) |
| 2 | `true` | assente | assente | **WARNING 4u** (wave chiusa senza governor_decision) |
| 3 | `true` | presente | — | no warning (governor_decision presente) |
| 4 | `true` | assente | valorizzato | no warning (esenzione motivata) |

**Cross-link**: 4u → PATTERN §18.8 (Temporal Budget Hook) + §3 «Temporal Budget Governance» +
skill `temporal-budget-governor.md` + ADR-043 (semantica) / ADR-044 (granularità) / ADR-045
(bootstrap) / ADR-046 §E (questo check).

---

### 4aa — Chain profonda senza decision_anchor loggato (Decision-Preserving Compression, EP-015 US-084, ADR-049 §B)

> Slot 4aa (prossimo libero dopo 4v=EP-016, 4w=EP-012 RUN-REPORT, 4x=EP-012 CHANGELOG,
> 4y=EP-008 ux_ui evidence, 4z=EP-018 Functional Oracle).

**Gate**: `compression.output.consistency_check.required_on_chain: true` in `factory.config.yaml`
(default `false` → 4aa no-op totale, backward compat R.P3). Se assente o `false` → check non si
applica indipendentemente da qualsiasi altra condizione.

**Trigger** (tutti e tre devono essere soddisfatti):
1. Chain con `chain_depth > warn_threshold_chain_depth` (default `3`, configurabile in
   `compression.output.consistency_check.warn_threshold_chain_depth`).
2. Nessun evento `state: anchor_propagated` trovato in `analytics/events/<YYYY-MM>.jsonl`
   per il `task_id` corrente negli ultimi 10 eventi (lookback `10`).
3. TSK privo di `consistency_check_skip_reason:` nel frontmatter.

**Event store assente**: se `analytics/events/` non esiste o è vuota → silent INFO skip (non
WARNING, non ERROR). La capability analytics EP-009 è opzionale; la sua assenza non blocca il
workflow (backward compat R.P3).

**Esenzione**: aggiungere `consistency_check_skip_reason: "<motivo>"` nel frontmatter TSK
(single-writer: TPM in fase di taskizzazione). Il motivo è obbligatorio (stringa non vuota).

**Severity**: WARNING-only. Mai `heal-eligible` (giudizio semantico — nessun auto-fix meccanico).

**Messaggio**:
```
[WARNING][chain-no-anchor][4aa] chain '<chain_id>' depth > <N> senza decision_anchor loggato —
rischio T3 (context rot). Attivare compression.output.decision_anchor.enabled: true o aggiungere
consistency_check_skip_reason al TSK. Vedi wiki/concepts/consistency-checker.md e ADR-049.
```

**Algoritmo** (pseudocodice):
```
if not factory.config.compression.output.consistency_check.required_on_chain:
    return  # no-op

for each TSK in active_chain where chain_depth > warn_threshold:
    if TSK.frontmatter.consistency_check_skip_reason:
        continue  # esenzione esplicita

    events_dir = "analytics/events/"
    if not exists(events_dir):
        log INFO "4aa: event store assente, skip"
        continue

    last_10 = last_n_events(events_dir, task_id=TSK.id, n=10)
    if any(e.state == "anchor_propagated" for e in last_10):
        continue  # anchor propagato correttamente

    emit WARNING "[chain-no-anchor][4aa] ..."
```

**Cross-link**: 4aa → `wiki/concepts/consistency-checker.md §Lint Check 4aa` +
`wiki/concepts/decision-anchor.md §Configurazione` + ADR-049 §B (ban `aggressive` su chain
profonde) + ADR-047 (decision anchor schema) + `wiki/runbooks/consistency-checker-runbook.md`
(TSK-164). Skill parallela: skill `consistency-checker` (agente terzo read-only EP-015 US-058).

---

### 4ab — Handoff inter-wave senza Temporal Handoff Block (Temporal Awareness, EP-011 US-046, ADR-031 §F)

> **Nota di numerazione**: slot `4t` è **riservato** alla migration ADR-050 §I (pre-warning INFO
> opzionale post-upgrade, `compression.migration.audit_after_upgrade`, non ancora implementata —
> vedi note di numerazione in 4u/4v/4w/4x). Nomenclatura originale in TSK-092: `4r-temporal-handoff`.
> Adottato slot libero **4ab** (prossimo dopo 4aa=EP-015 US-084).

**Pattern allineato a Check 4o/4p/4q/4r/4s (R.P3 opt-in totale)**: WARNING-only, mai ERROR.

**Gate** (doppio, entrambi richiesti):
1. `temporal.enabled: true` (master switch EP-011).
2. `temporal.handoff_protocol.handoff_required_on_wave_close: true` (default `false`).

A flag spento su uno dei due → 4ab no-op totale (backward compat R.P3).

**Trigger**: handoff inter-wave con `temporal.handoff_protocol.enabled: true` in cui il payload di
ritorno del sub-agent verso l'Orchestrator manca del blocco `temporal_handoff:` oppure il blocco
presente ha ≥ 1 dei 5 campi obbligatori assenti (`handoff_id`, `elapsed_ms`,
`estimated_remaining_ms`, `completed_steps`, `context_summary`).

**Esenzione**: frontmatter TSK con `temporal_handoff_skip: true` + `reason:` non vuoto → no WARNING.

**Output** (messaggio):
```
[WARNING][temporal-handoff-missing][4ab] handoff wave <wave_id> TSK-<id>: Temporal Handoff Block
mancante o incompleto. Verificare che skill dev-handoff/vcs-handoff sia v2.18+ con
temporal.handoff_protocol.enabled: true, oppure aggiungere temporal_handoff_skip: true con reason.
Vedi ADR-031 §F.
```

**Severity**: WARNING. Mai ERROR. R.P3.

**Cross-link**: 4ab → skill `dev-handoff.md` §Temporal Handoff Block + skill `vcs-handoff.md`
§Temporal Handoff Block + ADR-031 §F (check warrant) + ADR-030 (time semantics elapsed_ms) +
PATTERN §18 nota inter-wave + §3 «Temporal Handoff».

---

### 4ab-bis — TSK XL senza State Machine attiva (Temporal Awareness, EP-011 US-047, ADR-029 §E)

> Slot 4ab-bis (companion di 4ab, stesso EP-011). Nomenclatura originale in TSK-092: `4r-temporal-state`.

**Gate** (doppio, entrambi richiesti):
1. `temporal.enabled: true` (master switch EP-011).
2. `temporal.state_machine.required_on_xl: true` (default `false`).

A flag spento su uno dei due → 4ab-bis no-op totale (backward compat R.P3).

**Trigger**: TSK con `estimate: xl` AND `status: in_progress|done` AND assenza del file
`management/state/<TSK-id>.json` AND assenza di `temporal_state: false` esplicito nel frontmatter.

**Esenzione**: frontmatter TSK con `temporal_state: false` + `notes:` non vuoto → no WARNING
(opt-out documentato, pattern analogo a `a11y_skip_reason` / `ux_ui_skip_reason`).

**Caso edge `estimate` assente con policy `estimate-xl`**: TSK senza `estimate:` e
`temporal.state_machine.activation_policy: estimate-xl` → INFO-only (non WARNING): «TSK senza
estimate; State Machine non attivata automaticamente. Considerare `temporal_state: true` se
multi-step.» Solo se `temporal.state_machine.enabled: true`.

**Output** (messaggio):
```
[WARNING][temporal-state-missing][4ab-bis] TSK-<id> (estimate: xl) in_progress senza state file
management/state/<id>.json. Attivare temporal.state_machine.enabled: true o aggiungere
temporal_state: false con notes. Vedi ADR-029 §E.
```

**Severity**: WARNING. Mai ERROR. R.P3.

**Cross-link**: 4ab-bis → ADR-029 §E (check warrant) + ADR-028 §A (state file spec) +
PATTERN §3 «Temporal State Tracking» + factory.config.yaml `temporal.state_machine` + skill
`dev-handoff.md` §Proiezione da State Machine.
