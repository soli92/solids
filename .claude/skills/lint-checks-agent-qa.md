---
skill: lint-checks-agent-qa
part_of: lint-checks (modular)
family: agent-qa
parent: lint-checks
description: "Check lint su Agent Infrastructure Integrity e QA Layer — check-family agent-qa"
---

# Lint Checks — Agent Infrastructure & QA

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 4ad (TSK QA fallito senza failure_classification), Check 4ae (quarantena stale QA), Check 4ai (Agent Infrastructure Integrity), Check 4aj (Model Registry Consistency)

Check ordinati per numero.

---

### 4ad — TSK QA fallito senza failure_classification (EP-029, v2.22)

> Slot 4ad (prossimo libero dopo 4ac=EP-024). Promemoria operativo per sbloccare il routing
> differenziato EP-029 su TSK QA falliti da troppo tempo senza classificazione.

**Gate**: `qa_layer.failure_taxonomy.enabled: true` in `factory.config.yaml` (default `false`,
opt-in R.P3). Se assente o `false` → **4ad no-op totale**, indipendentemente da qualsiasi altra
condizione (backward compat: factory senza EP-029 non vede mai questo check).

Richiede anche `routing.qa: agent` in `factory.config.yaml`. Se `routing.qa != agent` →
skip silenzioso (senza qa-dev attivo, il check non è applicabile).

**Trigger** (AND — tutte le condizioni devono essere vere):

```
TSK.layer == qa
AND TSK.status == failed
AND failure_classification assente (o null) nel frontmatter TSK
AND (TSK.run_count > 5 OPPURE TSK.created_at > 7 giorni fa)
```

Se né `run_count:` né `created_at:` (o `updated:`) sono presenti nel frontmatter →
**skip silenzioso** (no false positive su dati incompleti).

**Severity**: WARNING-only. Mai ERROR. Mai `heal-eligible` (giudizio semantico — l'agente
non sa quale categoria applicare). Non blocca `/lint` né il Develop.

**Messaggio** (template verbatim, placeholder `<id>`, `<N>` giorni/run):

```
[WARNING][qa-no-classification][4ad] TSK <id> (layer:qa) ha status:failed ma non riporta failure_classification.
Aggiungere uno dei valori: APPLICATION_BUG | SSR_BUG | TEST_BUG | INFRASTRUCTURE | FLAKY
per attivare il routing automatico EP-029. Se intenzionale, impostare failure_classification: FLAKY
o aggiungere una nota nel corpo del TSK.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][qa-no-classification][4ad] TSK-0XX (qa, failed): nessuna failure_classification da N giorni. Aggiungere APPLICATION_BUG | SSR_BUG | TEST_BUG | INFRASTRUCTURE | FLAKY per attivare routing EP-029. Vedi PATTERN §5, skill feedback-router.md §QA Failure Routing.
```

Il report lint include per ogni WARNING: `tsk_id`, data prima occorrenza `status: failed`
(da `updated:` frontmatter o data file), giorni in stato failed.

**Backward compat**:

- Il check **non** emette WARNING su TSK `done` o `in_progress`
- Il check **non** emette WARNING su TSK `failed` con `failure_classification:` già compilato
- Il check **non** valida i valori dell'enum (responsabilità futura distinta); segnala solo
  l'assenza del campo su TSK falliti datati
- Nessun WARNING su factory senza EP-029 (guard gate sopra)
- Nessuna regressione su factory esistenti (no-op silenzioso se guard non soddisfatta)

**Scenari di verifica**:

| # | `failure_taxonomy.enabled` | `routing.qa` | layer | status | `failure_classification` | `run_count` / età | esito atteso |
|---|---|---|---|---|---|---|---|
| 1 | `false` (default) | agent | qa | failed | assente | 10 run | no warning (gate off, R.P3) |
| 2 | `true` | `human` | qa | failed | assente | 10 run | no warning (routing.qa != agent) |
| 3 | `true` | agent | be | failed | assente | 10 run | no warning (layer != qa) |
| 4 | `true` | agent | qa | done | assente | — | no warning (status != failed) |
| 5 | `true` | agent | qa | failed | `APPLICATION_BUG` | 10 run | no warning (campo presente) |
| 6 | `true` | agent | qa | failed | assente | 3 run, 2 giorni | no warning (sotto soglia) |
| 7 | `true` | agent | qa | failed | assente | 6 run | **WARNING 4ad** (run_count > 5) |
| 8 | `true` | agent | qa | failed | assente | 2 run, 8 giorni fa | **WARNING 4ad** (età > 7gg) |
| 9 | `true` | agent | qa | failed | assente | campi assenti | no warning (skip silenzioso, no false positive) |

**Cross-link**: 4ad → PATTERN §5 (campo `failure_classification:`, EP-029) + skill
`feedback-router.md` §QA Failure Routing (EP-029, v2.22) + EP-029 + US-103.

---

### 4ae — Quarantena stale QA (EP-027, v2.22)

**Pattern allineato a Check 4ad (EP-029) + Check 4m/4n/4o/4p/4q/4r/4s (R.P3 opt-in totale)**:
WARNING-only, opt-in via flag config, nessun ERROR meccanico. Check 4ae eredita la stessa shape
per coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale). Il meccanismo di alerting per
stale quarantine è informativo: il lead-architect decide se risolvere il test flaky o eliminarlo,
non automatizzabile. Il lint informa, non blocca mai `/lint` né il Develop. Mai `heal-eligible`
(giudizio semantico).

**Gate**: `qa_layer.flakiness_detection.enabled: true` in `factory.config.yaml` (default `false`,
opt-in R.P3). Se assente o `false` → **4ae no-op totale**, indipendentemente da qualsiasi altra
condizione (backward compat: factory senza EP-027 non vede mai questo check).

**Trigger**: file `analytics/qa/quarantine.json` esiste + almeno un record con:
- `status: "quarantined"` (non `"released"` e non `"monitoring"`)
- `quarantined_since_runs > qa_layer.flakiness_detection.stale_threshold` (default `100` run)

**Procedura**:

1. Se `qa_layer.flakiness_detection.enabled: false` → skip silenzioso (no output).
2. Se `analytics/qa/quarantine.json` assente o vuoto → **0 WARNING**, skip silenzioso
   (graceful degradation: factory senza opt-in EP-027 o primo avvio prima di qualsiasi
   test flaky).
3. Per ogni entry nel registro con `status: "quarantined"`:
   - Leggi `quarantined_since_runs` (aggiornato da `qa-dev` post-sessione, Sezione 5
     di `flakiness-detection-protocol.md`).
   - Se `quarantined_since_runs > stale_threshold` (default `100`, configurabile in
     `qa_layer.flakiness_detection.stale_threshold`):
     emettere **WARNING** con il seguente formato:

```
[Check 4ae] WARN: test '<test_id>' in quarantena da <quarantined_since_runs> run (score: <last_score>).
Quarantinato il: <quarantined_at>. Azione suggerita: risolvere il flakiness o eliminare il test.
Soglia: stale_threshold=<stale_threshold> run (configurabile in qa_layer.flakiness_detection.stale_threshold).
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][qa-quarantine-stale][4ae] test 'login-happy-path' in quarantena da 120 run (score: 0.34). Quarantinato il: 2026-05-01T10:00:00Z. Azione suggerita: risolvere il flakiness o eliminare il test. Soglia: stale_threshold=100 run.
```

**Campi del messaggio**:
- `test_id` — da `quarantine.json[].test_id`
- `quarantined_since_runs` — da `quarantine.json[].quarantined_since_runs`
- `last_score` — da `quarantine.json[].last_score`
- `quarantined_at` — da `quarantine.json[].quarantined_at`
- `stale_threshold` — da `factory.config.yaml.qa_layer.flakiness_detection.stale_threshold`

**Graceful degradation**:
- `analytics/qa/quarantine.json` assente o vuoto → skip silenzioso.
- Entry con `status: "released"` o `"monitoring"` → ignorate (solo `"quarantined"` triggera).
- Campo `quarantined_since_runs` assente nell'entry → skip silenzioso per quella entry
  (backward compat con entry prodotte prima dell'introduzione del campo).

**Scenari di verifica**:

| # | `flakiness_detection.enabled` | file esiste | entry `status` | `quarantined_since_runs` | `stale_threshold` | esito atteso |
|---|---|---|---|---|---|---|
| 1 | `false` (default) | — | — | — | — | no warning (gate off, R.P3) |
| 2 | `true` | no | — | — | 100 | no warning (file assente, graceful) |
| 3 | `true` | si (vuoto) | — | — | 100 | no warning (file vuoto, graceful) |
| 4 | `true` | si | `quarantined` | 120 | 100 | **WARNING 4ae** (stale oltre soglia) |
| 5 | `true` | si | `quarantined` | 80 | 100 | no warning (sotto soglia) |
| 6 | `true` | si | `quarantined` | 100 | 100 | no warning (boundary: `>` strict, `100 > 100` falso) |
| 7 | `true` | si | `released` | 200 | 100 | no warning (solo `quarantined` triggera) |
| 8 | `true` | si | `monitoring` | 150 | 100 | no warning (solo `quarantined` triggera) |
| 9 | `true` | si | `quarantined` | assente | 100 | no warning (campo assente, skip silenzioso) |

**Configurabilità**: `stale_threshold` da `factory.config.yaml`:

```
qa_layer.flakiness_detection.stale_threshold  (default: 100)
```

**Cross-link**: 4ae → skill `flakiness-detection-protocol.md` §Sezione 5 (schema registro
quarantena + campo `quarantined_since_runs`) + `factory.config.yaml.qa_layer.flakiness_detection`
+ EP-027 (US-097) + US-095/US-096 (event store + quarantena reversibile).

---

## Check 4ai — Agent Infrastructure Integrity (WARNING, always-on)

**Trigger**: sempre attivo — verifica l'integrità strutturale del layer agenti (`.claude/agents/`).
**Severità**: WARNING — mai ERROR, mai `heal-eligible`. Non blocca il lint.
**Audience**: maintainer che aggiungono, rinominano o rimuovono agenti, skill o comandi.

### Algoritmo

1. **Scopri tutti gli agenti**: Glob `.claude/agents/*.md`.
2. Per ogni agente estrai:
   - Frontmatter `tools: [...]` — lista tool dichiarati.
   - Riferimenti a skill nel body: token preceduti da `vedi`, `` ` ``, o path esplicito `.claude/skills/<name>.md`.
   - Riferimenti a comandi nel body: slash-command `/(<name>)` e path espliciti `.claude/commands/<name>.md`.
3. **Check 4ai.1 — Tool name validation**:
   - Whitelist tool validi per agenti Claude Code:
     `{Read, Write, Edit, Glob, Bash, TodoWrite, Task, Grep, WebFetch, WebSearch,
       Agent, SendMessage, Monitor, CronCreate, CronDelete, CronList, DesignSync,
       EnterPlanMode, ExitPlanMode, EnterWorktree, ExitWorktree, NotebookEdit,
       PushNotification, RemoteTrigger, TaskOutput, TaskStop}`.
   - Ogni tool in `tools: [...]` **non in whitelist** → **WARNING `[4ai.1] agent-invalid-tool`**.
4. **Check 4ai.2 — Skill reference validation**:
   - Per ogni `<name>` estratto come riferimento a skill:
     se `.claude/skills/<name>.md` **non esiste** → **WARNING `[4ai.2] agent-skill-missing`**.
5. **Check 4ai.3 — Command reference validation**:
   - Per ogni `<name>` estratto come riferimento a comando:
     se `.claude/commands/<name>.md` **non esiste** → **WARNING `[4ai.3] agent-command-missing`**.

### Invarianti

- **Warning-only**: nessun ERROR — un riferimento pendente non blocca la factory (la skill o il
  comando potrebbe essere in sviluppo / in_progress).
- **Never heal-eligible**: la risoluzione richiede giudizio semantico (creare la skill/command
  mancante o correggere il nome nel body dell'agente).
- **Read-only**: legge solo `.claude/agents/`, `.claude/skills/`, `.claude/commands/`.
- **Regex best-effort**: pattern text-search, non AST. False positive accettabili (allineato
  alla soglia R.Q5). Solo token preceduti da `vedi`, o path espliciti `.claude/skills/<name>.md`
  sono candidati — non ogni parola del body.
- **Agent-name exclusion**: i nomi degli agenti (`.claude/agents/*.md` senza `.md`) NON sono
  skill. Prima di emettere 4ai.2, escludere token che corrispondono a file esistenti in
  `.claude/agents/`. Es.: `` `wiki-keeper` `` in un body è riferimento ad agente, non skill mancante.

### Output format

```
## WARNING (igiene, mai heal-eligible)
- [WARNING][agent-invalid-tool][4ai.1] .claude/agents/foo.md: tool 'TodoList' non in whitelist. Correggi il frontmatter tools:.
- [WARNING][agent-skill-missing][4ai.2] .claude/agents/bar.md: referenzia skill 'my-draft-skill' ma .claude/skills/my-draft-skill.md non esiste.
- [WARNING][agent-command-missing][4ai.3] .claude/agents/baz.md: referenzia comando /my-cmd ma .claude/commands/my-cmd.md non esiste.
```

### Scenari di verifica

| # | Condizione | Esito atteso |
|---|---|---|
| 1 | `tools: [Read, Bash]` — tutti in whitelist | no WARNING |
| 2 | `tools: [Read, TodoList]` — `TodoList` fuori whitelist | **WARNING 4ai.1** |
| 3 | body: `vedi \`dispatch-policy\`` e `.claude/skills/dispatch-policy.md` esiste | no WARNING |
| 4 | body: `vedi \`my-draft-skill\`` e `.claude/skills/my-draft-skill.md` non esiste | **WARNING 4ai.2** |
| 5 | body: `/my-cmd` e `.claude/commands/my-cmd.md` non esiste | **WARNING 4ai.3** |
| 6 | body: `/run` e `.claude/commands/run.md` esiste | no WARNING |

### Cross-link

4ai → `.claude/agents/` + `.claude/skills/` + `.claude/commands/` + `dispatch-policy.md` +
PATTERN §2 (thin-agents-fat-skills).

---

## Check 4aj — Model Registry Consistency (INFO, always-on)

**Trigger**: solo se `factory.config.yaml.models.routing` è presente (Central Model Registry).
**Severità**: INFO — non blocca il lint, non è `heal-eligible`. Audience: maintainer che
aggiornano il model registry o aggiungono agenti.

### Algoritmo

1. Leggi `factory.config.yaml.models.routing`: estrai `tier_fast`, `tier_default`, `tier_deep`.
   Costruisci l'insieme dei model ID tier: `{tier_fast, tier_default, tier_deep}`.
2. Leggi `factory.config.yaml.models.overrides`: dizionario `{agent_name: model_id}`.
   Questi override sono esplicitamente scelti — non vengono flaggati.
3. Per ogni agente in `.claude/agents/*.md`:
   - Estrai `model:` dal frontmatter.
   - Se l'agente è in `models.overrides` → skip (override esplicito).
   - Se il `model:` non corrisponde **esattamente** ad alcun tier value →
     **INFO `[4aj] agent-model-not-in-registry`** (può essere shorthand o versione diversa).
4. **Skip silenzioso** se `models.routing` non esiste → backward compat totale.

### Invarianti

- **INFO-only** — più lieve di WARNING. Non blocca mai. Non `heal-eligible` (la scelta del
  modello richiede giudizio su costo/capacità).
- **Read-only** — legge solo `factory.config.yaml` e frontmatter agenti.
- **No-op senza registry**: factory che non usano il Central Model Registry non vedono mai 4aj.

### Output format

```
## INFO (igiene)
- [INFO][agent-model-not-in-registry][4aj] .claude/agents/orchestrator.md: model 'claude-haiku-4-5' non corrisponde a nessun tier value (tier_fast=claude-haiku-4-5-20251001, tier_default=claude-sonnet-4-6, tier_deep=claude-opus-4-8). Possibile shorthand o versione diversa. Verifica o aggiorna il registry.
```

### Cross-link

4aj → `factory.config.yaml.models` (Central Model Registry v2.27) + PATTERN §29.2 +
`.claude/agents/` (scope) + `dispatch-policy.md §8` (tier slug table).
