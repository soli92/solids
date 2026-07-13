# Skill: Lint Checks

> Adapter Cursor della skill `lint-checks` definita in PATTERN.md.

# Check del wiki-lint

Riferimenti: [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (per la definizione di "claim non citato"),
[wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md) (per il template del log report).

## Check 1 — Orphan + wikilink (scan unico)

1. `Glob wiki/**/*.md` (escludi `log.md`, `index.md`, `query/`, `lint/`).
2. Read `wiki/index.md`, estrai tutti i `[[…]]` e i path linkati.
3. Per ogni file: se non è linkato dall'index → **WARNING orphan**.
4. Read ogni pagina wiki: estrai `\[\[([^\]]+)\]\]`. Per ogni wikilink: verifica
   esista un file con slug corrispondente.
   - Wikilink che non risolve → **ERROR broken-link**.

## Check 2 — Claim senza fonte

Vedi [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) per la definizione canonica di "claim che richiede
citazione" (≥ 20 parole, esenzioni, ecc).

Procedura:
- Per ogni `wiki/**/*.md`, identifica frasi affermative che secondo
  [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) devono essere citate.
- Per ognuna: verifica che entro 3 righe successive (o nella stessa riga) ci sia
  un `[^src: …]` o un `[[…]]`.
- Assenza → **WARNING unsourced-claim**.

## Check 3 — Integrità kanban

Per ogni `management/kanban/EP-*/EP-*.md`:
- Frontmatter ha `id`, `title`, `status`, `priority`, `confidence`? Altrimenti **ERROR**.
- `id` matcha il pattern `EP-XXX` con XXX = nome cartella? Altrimenti **ERROR**.

Per ogni `US-*.md`:
- Frontmatter ha `id`, `title`, `role`, `priority`, `status`, `wiki_page`?
- `wiki_page` punta a file esistente? Altrimenti **ERROR**.

Per ogni `TSK-*.md` (v2.7):
- Frontmatter ha `id`, `sprint`, `layer`, `consumer`, `priority`, `estimate`, `status`?
- `id` univoco globalmente (cross-cartelle)?
- `layer` ∈ `{be, fe, db, qa, infra}` → altrimenti **ERROR invalid-layer**.
- `consumer` ∈ `{agent, human}` → altrimenti **ERROR invalid-consumer**.
- Campo legacy `team:` ancora presente → **WARNING deprecated-field** (v2.7,
  migrazione manuale a `layer:`).

## Check 4 — Coerenza wiki ↔ kanban

- Ogni US referenzia una pagina wiki: la pagina esiste?
- Ogni `## Storie collegate` in wiki ha solo storie esistenti?

### 4m — Coerenza `risk_classification` ↔ Risk Registry (v2.16 opt-in, PATTERN §3/§5)

**WARNING-only — nessun ERROR meccanico** (R.P3 opt-in totale). Il check non blocca
mai `/lint`. Eventuale promozione a ERROR è candidato v2.17+ post-evidenza.

**Pre-condizioni di silenzio** (no-op se):
- l'artefatto EP/US/TSK **non** ha il blocco `risk_classification:` nel frontmatter → no-op totale;
- `management/risk-registry.md` **non** esiste → 4m.1 e 4m.2 si skippano (il Registry è opt-in); solo 4m.3 (broken ref) può ancora scattare.

Tre sotto-check (per ogni artefatto con `risk_classification:` valorizzato):

- **4m.1 — Drift tier**: se `tier` MATCHES `/^tiger-/` e una sezione del Registry per quel target esiste, ma il tier nel Registry ≠ tier nel frontmatter → **WARNING `drift_tier`**.
- **4m.2 — Missing Registry row**: se `tier` MATCHES `/^tiger-/`, il Registry esiste, ma non c'è alcuna sezione/riga per quel target → **WARNING `missing_registry_row`** (suggerimento: esegui `/premortem <target>`).
- **4m.3 — Broken premortem_ref**: se `premortem_ref` è valorizzato e `(path, anchor)` non è risolvibile (file inesistente o anchor assente) → **WARNING `broken_premortem_ref`**.

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][risk_classification][4m.1] EP-042: drift_tier — frontmatter=tiger-launch-blocking, registry=tiger-fast-follow (suggerimento: riconciliare)
- [WARNING][risk_classification][4m.2] US-017: missing_registry_row — esegui /premortem US-017
- [WARNING][risk_classification][4m.3] TSK-103: broken_premortem_ref — management/risk-registry.md#pm-inesistente
```

**Numerazione**: «4m» è il check del pattern Premortem (v2.16). La lettera segue la
serie OCL/CCL prevista in v2.14 (4k/4l); non collide con alcun check esistente in
questo file (4b–4g). Mai `heal-eligible` (WARNING-only, giudizio semantico).

### 4n — Granularità TSK FE (State Matrix DoD, EP-006 US-022, ADR-011)

**Pattern allineato a Check 4m (EP-002 US-007)**: WARNING-only, opt-in via flag config,
soglie configurabili, nessun ERROR meccanico. Check 4n eredita la stessa shape per
coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione TPM). La
scomposizione di un task è decisione del TPM/Arch, non automatizzabile: il lint informa,
non blocca mai `/lint` né il Develop. Mai `heal-eligible` (giudizio semantico).

**Trigger (AND — tutte e 5 le condizioni devono essere vere; più conservativo del prompt
OR in [scrivi-task](mdc:.cursor/skills/scrivi-task/SKILL.md))**:

```
TSK.layer == 'fe'
AND factory.config.yaml.fe_correctness.granularity_lint == true
AND TSK ha sezione '## DoD FE — stati obbligatori'
AND TSK.estimate > granularity.max_estimate_hours
AND states_checked(TSK) > granularity.max_states
```

L'AND (non OR) è intenzionale: in fase di review il lint deve restare silente sui TSK che
violano solo una delle due dimensioni (es. 16h con 1 stato = task complesso a singola
dimensione; 4h con 5 stati = piccolo ma multi-variante). Il warning cattura solo il caso
patologico «grosso E complesso UI». Il prompt [scrivi-task](mdc:.cursor/skills/scrivi-task/SKILL.md) resta in forma OR (preventivo);
il lint è AND (curativo, riduce false positive). [^src: ADR-011 §Decisione + §Rationale]

**`states_checked(TSK)`**: numero di righe che MATCHANO la regex `^\s*-\s*\[x\]\s+` (checkbox
markdown checked, qualunque indentazione/label) **all'interno della sezione** `## DoD FE —
stati obbligatori` del TSK.

**Pre-condizione di silenzio** (sezione assente = check non si applica):
- se la sezione `## DoD FE — stati obbligatori` è **assente** → check **non si applica**, nessun
  warning. Un TSK FE legacy senza la sezione (US-021 non adottata) ha `states_checked == 0`,
  quindi il lato AND `states_checked > max_states` è sempre falso e il check degenera
  correttamente a no-op. Il Check 4n serve solo se il TPM ha già adottato la State Matrix.

**Gate**: `factory.config.yaml.fe_correctness.granularity_lint: false` (default off, opt-in
totale, backward compat). Se assente o `false` → no-op totale.

**Soglie configurabili**: `factory.config.yaml.fe_correctness.granularity.{max_estimate_hours,
max_states}`, default `{8, 3}`. Confronto **strict `>`** (non `≥`): boundary `estimate ==
max_estimate_hours` o `states_checked == max_states` → no warning.

**Messaggio (template verbatim, placeholder `<id>`, `<X>h`, `<N>`)**:

```
TSK <id> ha `estimate: <X>h` (> {max_estimate_hours}) e copre <N> stati FE (> {max_states}): considerare scomposizione. Vedi US-022 / fe-agent-correctness-strategy §Leva 5
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][granularity][4n] TSK-051: ha estimate: 16h (> 8) e copre 5 stati FE (> 3): considerare scomposizione. Vedi US-022 / fe-agent-correctness-strategy §Leva 5
```

**Scenari di verifica** (6 test case, ADR-011 §Conseguenze):

| # | layer | estimate | states_checked | flag `granularity_lint` | soglie | sezione DoD | esito atteso |
|---|---|---|---|---|---|---|---|
| 1 | fe | 16h | 5 | `true` | `{8,3}` | presente | **WARNING** (tutte le 5 condizioni AND vere) |
| 2 | fe | 16h | 1 | `true` | `{8,3}` | presente | no warning (AND non soddisfatto: `1 > 3` falso) |
| 3 | fe | 4h | 5 | `true` | `{8,3}` | presente | no warning (AND non soddisfatto: `4 > 8` falso) |
| 4 | fe | 16h | 5 | `false` | `{8,3}` | presente | no warning (gate off) |
| 5 | fe | 16h | — | `true` | `{8,3}` | **assente** | no warning (precondition fallita, check non si applica) |
| 6 | fe | 16h | 5 | `true` | `{16,5}` | presente | no warning (boundary: `>` strict non `≥`, `16 > 16` e `5 > 5` falsi) |

**Numerazione**: «4n» segue «4m» (Premortem v2.16) nella serie alfabetica; non collide con
alcun check esistente in questo file.

### 4o — TSK FE done senza scan a11y verificata (Accessibility Testing Capability, EP-007 US-027, ADR-016 §A/§I)

**Pattern allineato a Check 4m (EP-002 US-007) + Check 4n (EP-006 US-022)** (R.P3 opt-in
totale): WARNING-only, opt-in via flag config, nessun ERROR meccanico. Check 4o eredita la
stessa shape per coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione ADR-016 §A). Il
completamento di uno scan a11y prima del done è scope del derivatore di factory, non
automatizzabile come gate hard: il lint informa, non blocca mai `/lint` né il Develop. Mai
`heal-eligible` (giudizio semantico).

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
TSK.layer == 'fe'
AND factory.config.yaml.a11y.required_on_fe_done == true
AND TSK.status == 'done'
AND NOT (TSK.frontmatter.a11y_status IN ['pass', 'skip'])
AND NOT (TSK.frontmatter.a11y_status == 'skip' AND TSK.frontmatter.a11y_skip_reason valorizzato)
```

(In pratica: WARNING se `a11y_status` è assente, `pending`, `major` o `critical`, **oppure**
è `skip` ma `a11y_skip_reason` è vuoto/assente. La condizione `a11y_report` assente è
implicata: un report a11y produce `a11y_status: pass|major|critical`, non lascia il campo
assente/`pending`.)

**Gate**: `factory.config.yaml.a11y.required_on_fe_done: false` (default off, opt-in totale,
backward compat). Se assente o `false` → no-op totale (Check 4o non si applica,
indipendentemente dallo stato dei TSK FE). [^src: ADR-016 §A + §I + §J]

**Esenzione**: TSK FE che dichiara `a11y_status: skip` **con** `a11y_skip_reason:` valorizzato
→ no WARNING (il derivatore ha dichiarato esplicitamente che il TSK non è soggetto a scan,
es. "componente coperto da scan parent route"). L'esenzione richiede motivazione esplicita.

**Esenzione parziale (incoerenza)**: TSK FE con `a11y_status: skip` **senza**
`a11y_skip_reason:` → WARNING diverso (l'esenzione è dichiarata ma non motivata):

```
TSK <id> ha a11y_status: skip ma manca a11y_skip_reason. Aggiungere motivazione.
```

**Messaggio (template verbatim, placeholder `<id>`, `<value>`)**:

```
TSK <id> FE done senza scan a11y verificata (a11y_status: <value>). Eseguire `/a11y <id>` o aggiungere `a11y_status: skip` con `a11y_skip_reason: <motivazione>`. Vedi ADR-016, US-027.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][a11y][4o] TSK-051: FE done senza scan a11y verificata (a11y_status: pending). Eseguire /a11y TSK-051 o aggiungere a11y_status: skip con a11y_skip_reason. Vedi ADR-016, US-027.
- [WARNING][a11y][4o] TSK-052: ha a11y_status: skip ma manca a11y_skip_reason. Aggiungere motivazione.
```

**Scenari di verifica**:

| # | layer | status | a11y_status | a11y_skip_reason | flag `required_on_fe_done` | esito atteso |
|---|---|---|---|---|---|---|
| 1 | fe | done | assente | — | `false` (default) | no warning (gate off, backward compat) |
| 2 | fe | done | assente | — | `true` | **WARNING 4o** (scan a11y mancante) |
| 3 | fe | done | `pass` | — | `true` | no warning (scan verificata pass) |
| 4 | fe | done | `skip` | valorizzato | `true` | no warning (esenzione motivata) |
| 5 | fe | done | `skip` | assente | `true` | **WARNING 4o** (skip senza motivazione) |
| 6 | be | done | assente | — | `true` | no warning (layer != fe) |

**Numerazione**: «4o» segue «4n» (State Matrix v2.18, EP-006 US-022) nella serie alfabetica;
non collide con alcun check esistente in questo file (precede «4p»/«4q»/«4r»).

### 4p — TSK FE done senza review UX/UI verificata (UX/UI Review & Design Capability, EP-008 US-032, ADR-020 §G)

**Pattern allineato a Check 4m (EP-002 US-007) + Check 4n (EP-006 US-022) + Check 4o (EP-007
US-027)** (R.P3 opt-in totale): WARNING-only, opt-in via flag config, nessun ERROR meccanico.
Check 4p eredita la stessa shape per coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione ADR-020 §G). Il
completamento di una review UX/UI prima del done è scope del derivatore di factory, non
automatizzabile come gate hard (la review UX è additive value, non semantic precondition —
ADR-019 §Rationale 2): il lint informa, non blocca mai `/lint` né il Develop. Mai
`heal-eligible` (giudizio semantico).

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
TSK.layer == 'fe'
AND factory.config.yaml.ux_ui.required_on_fe_done == true
AND TSK.status == 'done'
AND NOT (TSK.frontmatter.ux_ui_status == 'pass')
AND NOT (TSK.frontmatter.ux_ui_status == 'skip' AND TSK.frontmatter.ux_ui_skip_reason valorizzato)
```

(In pratica: WARNING se `ux_ui_status` è assente, `pending`, `conditional` o `reject`,
**oppure** è `skip` ma `ux_ui_skip_reason` è vuoto/assente.)

**Gate**: `factory.config.yaml.ux_ui.required_on_fe_done: false` (default off, opt-in totale,
backward compat). Se assente o `false` → no-op totale (Check 4p non si applica,
indipendentemente dallo stato dei TSK FE). [^src: ADR-020 §G + §J]

**Esenzione**: TSK FE che dichiara `ux_ui_status: skip` **con** `ux_ui_skip_reason:` valorizzato
→ no WARNING (il derivatore ha dichiarato esplicitamente che il TSK non è soggetto a review UX/UI).
L'esenzione richiede motivazione esplicita.

**Esenzione parziale (incoerenza)**: TSK FE con `ux_ui_status: skip` **senza**
`ux_ui_skip_reason:` → WARNING diverso (l'esenzione è dichiarata ma non motivata):

```
TSK <id> ha ux_ui_status: skip ma manca ux_ui_skip_reason. Aggiungere motivazione.
```

**Messaggio (template verbatim, placeholder `<id>`, `<value>`)**:

```
TSK <id> FE done senza review UX/UI verificata (ux_ui_status: <value>). Eseguire `/ux-ui-review <id>` o aggiungere `ux_ui_status: skip` con `ux_ui_skip_reason: <motivazione>`. Vedi ADR-020, US-032.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][ux-ui][4p] TSK-051: FE done senza review UX/UI verificata (ux_ui_status: pending). Eseguire /ux-ui-review TSK-051 o aggiungere ux_ui_status: skip con ux_ui_skip_reason. Vedi ADR-020, US-032.
- [WARNING][ux-ui][4p] TSK-052: ha ux_ui_status: skip ma manca ux_ui_skip_reason. Aggiungere motivazione.
```

**Scenari di verifica**:

| # | layer | status | ux_ui_status | ux_ui_skip_reason | flag `required_on_fe_done` | esito atteso |
|---|---|---|---|---|---|---|
| 1 | fe | done | assente | — | `false` (default) | no warning (gate off, backward compat) |
| 2 | fe | done | assente | — | `true` | **WARNING 4p** (review UX/UI mancante) |
| 3 | fe | done | `pass` | — | `true` | no warning (review verificata pass) |
| 4 | fe | done | `skip` | valorizzato | `true` | no warning (esenzione motivata) |
| 5 | fe | done | `skip` | assente | `true` | **WARNING 4p** (skip senza motivazione) |
| 6 | be | done | assente | — | `true` | no warning (layer != fe) |

**Numerazione**: «4p» segue «4o» (a11y v2.18, EP-007 US-027) nella serie alfabetica; non
collide con alcun check esistente in questo file (precede «4q»/«4r» di EP-009/EP-010).
Distinto da Check 4o: 4o enforce lo scan a11y (`a11y.required_on_fe_done`, campo `a11y_status`),
4p enforce la review UX/UI (`ux_ui.required_on_fe_done`, campo `ux_ui_status`) — gate, trigger
e campi frontmatter indipendenti, possono coesistere (a11y e ux-ui sono capability distinte).

### 4q — TSK done senza event log/effort (Task Analytics Measurement, EP-009 US-039, ADR-023 §G)

**Pattern allineato a Check 4m/4n/4o (R.P3 opt-in totale)**: WARNING-only, opt-in via flag
config, nessun ERROR meccanico. Check 4q eredita la stessa shape per coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione ADR-023 §G). La
strumentazione analytics (`record_task_event`, US-033) o la dichiarazione manuale di
`effort_hours` è scelta del derivatore di factory, non automatizzabile: il lint informa,
non blocca mai `/lint` né il Develop. Mai `heal-eligible` (giudizio semantico).

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.analytics.measurement.required_on_done == true
AND TSK.status == 'done'
AND TSK.frontmatter.cost_event_log absent (o vuoto)
AND TSK.frontmatter.effort_hours absent (se TSK.frontmatter.actor_type == 'human')
AND NOT (TSK.frontmatter.analytics_skip == true)
```

**Gate**: `factory.config.yaml.analytics.measurement.required_on_done: false` (default off,
opt-in totale, backward compat). Se assente o `false` → no-op totale (Check 4q non si applica).

**Esenzione**: TSK con frontmatter `analytics_skip: true` + `reason:` valorizzato → no
WARNING (il derivatore ha dichiarato esplicitamente che il TSK non è soggetto a misurazione,
es. task di pura documentazione o spike). L'assenza di `reason:` con `analytics_skip: true`
non sopprime il warning (l'esenzione richiede motivazione esplicita).

**Messaggio (template verbatim, placeholder `<id>`)**:

```
TSK <id> done senza event log/effort. Verificare che `record_task_event` (US-033) sia attivo o aggiungere `effort_hours` manuale. Disabilita Check 4q impostando analytics.measurement.required_on_done: false; esenta il singolo TSK con analytics_skip: true + reason.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][analytics][4q] TSK-042: done senza event log/effort. Verificare che `record_task_event` (US-033) sia attivo o aggiungere `effort_hours` manuale.
```

**Numerazione**: «4q» segue «4p» (EP-008 US-032) nella serie alfabetica; non collide con
alcun check esistente in questo file. Distinta da «4r» (EP-010 US estimation, ADR-027 §H,
gate `analytics.estimation.required_on_kickoff`): 4q misura il done (EP-009), 4r enforce la
stima preliminare al kickoff (EP-010).

### 4r — TSK in nuovo progetto senza stima di riferimento (Task Analytics Estimation, EP-010 US-042, ADR-027 §H)

**Pattern allineato a Check 4m/4n/4o/4q (R.P3 opt-in totale)**: WARNING-only, opt-in via flag
config, nessun ERROR meccanico. Check 4r eredita la stessa shape per coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione ADR-027 §H). La
produzione di una stima preliminare (`/estimate`, skill `project-estimation` US-040) è scelta
del derivatore di factory enterprise, non automatizzabile: il lint informa, non blocca mai
`/lint` né il Develop. Mai `heal-eligible` (giudizio semantico).

**Distinta da Check 4q** (EP-009 US-039): 4q **misura il done** (gate `required_on_done`,
trigger su `status: done` senza `cost_event_log`/`effort_hours`); 4r **enforce la stima al
kickoff** (gate `required_on_kickoff`, trigger su TSK `todo|in-progress` di un nuovo
progetto/EP senza `estimate_id`). Asse temporale opposto: 4q guarda indietro (consuntivo),
4r guarda avanti (preventivo). Gate, trigger e messaggio sono indipendenti.

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.analytics.estimation.required_on_kickoff == true
AND TSK.layer in ['fe', 'be', 'db', 'qa']
AND TSK.status in ['todo', 'in-progress']
AND TSK in nuovo progetto/EP (project_id non visto in storia precedente)
AND TSK.frontmatter.estimate_id absent (o vuoto)
AND NOT (TSK.frontmatter.estimate_skip == true)
```

**Gate**: `factory.config.yaml.analytics.estimation.required_on_kickoff: false` (default off,
opt-in totale, backward compat). Se assente o `false` → no-op totale (Check 4r non si applica).
Il flag vive nel sub-blocco `analytics.estimation:` introdotto da US-044 (config + scheduler +
PATTERN per EP-010); l'intero sub-blocco è gated da `analytics.estimation.enabled: false` di
default, quindi su una factory v2.17 senza opt-in il flag è assente e il check è no-op.

**Esenzione**: TSK con frontmatter `estimate_skip: true` + `reason:` valorizzato → no
WARNING (il derivatore ha dichiarato esplicitamente che il TSK non richiede stima preliminare,
es. task di pura documentazione, spike, hotfix). L'assenza di `reason:` con `estimate_skip:
true` non sopprime il warning (l'esenzione richiede motivazione esplicita).

**Messaggio (template verbatim, placeholder `<id>`, `<project_id>`)**:

```
TSK <id> appartiene a un nuovo progetto/EP (<project_id>) e non referenzia un estimate_id. Eseguire `/estimate --from-kanban=<EP-id>` per produrre stima preliminare o aggiungere estimate_id: manuale. Vedi ADR-027 §H. Disabilita Check 4r impostando analytics.estimation.required_on_kickoff: false; esenta il singolo TSK con estimate_skip: true + reason.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][estimation][4r] TSK-080: nuovo progetto/EP (EP-012) senza estimate_id. Eseguire `/estimate --from-kanban=EP-012` o aggiungere estimate_id: manuale. Vedi ADR-027 §H.
```

**Numerazione**: «4r» segue «4q» (EP-009 US-039) nella serie alfabetica; non collide con
alcun check esistente in questo file.

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

**Numerazione**: «4s» segue «4r» (EP-010 US-042) nella serie alfabetica; non collide con alcun
check esistente in questo file (precede «4t-migration» di ADR-050 §I, pre-warning INFO opzionale
post-upgrade — distinto e additivo). Distinto da 4s.1/4s.2: 4s.1 enforce l'inter-hop consistency
check (gate `consistency_check.required_on_chain`, EP-015 US-059), 4s.2 replica documentalmente
il trigger R.C7 (gate `compression.output.enabled`, ADR-049 §B) — gate, trigger e messaggi
indipendenti, possono coesistere.

**Cross-link**: 4s.1 → skill `consistency-check-protocol.md` + agente `consistency-checker` +
ADR-048; 4s.2 → PATTERN §20.4 R.C7 + ADR-049 (definizione chain profonda) + ADR-050 (migration
soft/strict).

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

### 4ab-bis — TSK XL senza State Machine attiva (Temporal Awareness, EP-011 US-047, ADR-029 §E)

> Slot 4ab-bis (companion di 4ab, stesso EP-011). Nomenclatura originale in TSK-092: `4r-temporal-state`.

**Gate** (doppio, entrambi richiesti):
1. `temporal.enabled: true` (master switch EP-011).
2. `temporal.state_machine.required_on_xl: true` (default `false`).

A flag spento su uno dei due → 4ab-bis no-op totale (backward compat R.P3).

**Trigger**: TSK con `estimate: xl` AND `status: in-progress|done` AND assenza del file
`management/state/<TSK-id>.json` AND assenza di `temporal_state: false` esplicito nel frontmatter.

**Esenzione**: frontmatter TSK con `temporal_state: false` + `notes:` non vuoto → no WARNING
(opt-out documentato, pattern analogo a `a11y_skip_reason` / `ux_ui_skip_reason`).

**Caso edge `estimate` assente con policy `estimate-xl`**: TSK senza `estimate:` e
`temporal.state_machine.activation_policy: estimate-xl` → INFO-only (non WARNING): «TSK senza
estimate; State Machine non attivata automaticamente. Considerare `temporal_state: true` se
multi-step.» Solo se `temporal.state_machine.enabled: true`.

**Output** (messaggio):
```
[WARNING][temporal-state-missing][4ab-bis] TSK-<id> (estimate: xl) in-progress senza state file
management/state/<id>.json. Attivare temporal.state_machine.enabled: true o aggiungere
temporal_state: false con notes. Vedi ADR-029 §E.
```

**Severity**: WARNING. Mai ERROR. R.P3.

**Cross-link**: 4ab-bis → ADR-029 §E (check warrant) + ADR-028 §A (state file spec) +
PATTERN §3 «Temporal State Tracking» + factory.config.yaml `temporal.state_machine` + skill
`dev-handoff.md` §Proiezione da State Machine.

### 4ac — no-auto-eval UX/UI (EP-024, ADR-020 §H)

> **Nota di numerazione**: ADR-020 §G prescrive questo check come «Check 4q» (successivo a
> 4p, UX/UI review). Nel repo corrente lo slot 4q è occupato (EP-009 US-039 — analytics
> measurement), e gli slot 4r/4s/4u/4v/4w/4x/4y/4z/4aa/4ab/4ab-bis sono anch'essi occupati.
> Il check adotta il prossimo slot libero **4ac** preservando l'intento dell'ADR (correzione
> meccanica di numerazione, non cambio di intento — lezione TSK-112/118/122/096/137). Il gate
> config `ux_ui.lint_check_4q` mantiene il nome «4q» per coerenza con ADR-020 §B; la
> numerazione del check è **4ac**.

**Pattern allineato a Check 4m/4n/4o/4p/4y (R.P3 opt-in totale)**: WARNING-only, opt-in via
flag config, nessun ERROR meccanico. Check 4ac eredita la stessa shape per coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione ADR-020 §H). Il
vincolo no-auto-eval è già enforced strutturalmente da agenti fisicamente distinti
(`ui-designer` e `ux-ui-reviewer`); il Check 4ac è una difesa di backup che informa quando
il campo `generated_by` rivela una coincidenza anomala. Il lint informa, non blocca mai
`/lint` né il Develop. Mai `heal-eligible` (giudizio semantico).

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
TSK.layer == 'fe'
AND factory.config.yaml.ux_ui.enabled == true
AND factory.config.yaml.ux_ui.lint_check_4q == true
AND TSK.frontmatter.ui_design_spec valorizzato (path a file esistente)
AND TSK.frontmatter.ux_ui_report valorizzato (path a file esistente)
AND leggi generated_by da <ui_design_spec>.json
AND leggi generated_by da <ux_ui_report>.json
AND entrambi i campi generated_by presenti e non null
AND <ui_design_spec>.generated_by == <ux_ui_report>.generated_by
AND NOT (TSK.frontmatter.ux_ui_no_auto_eval_skip_reason valorizzato)
```

**Procedura di verifica**:

1. Leggi il file referenziato da `TSK.frontmatter.ui_design_spec` (report uxui-design JSON,
   US-086 schema).
2. Leggi il file referenziato da `TSK.frontmatter.ux_ui_report` (report uxui-review JSON,
   US-086 schema).
3. Estrai `generated_by` da ciascuno dei due report.
4. **Se uno o entrambi i `generated_by` sono assenti o null**: emit INFO `"generated_by
   assente in <file>, check 4ac skipped"` → **nessun WARNING** (no false positive su dati
   incompleti).
5. **Se entrambi presenti e `design.generated_by == review.generated_by`**: emit WARNING
   (violazione vincolo no-auto-eval).
6. **Se entrambi presenti e diversi**: no WARNING (vincolo rispettato).

**Gate**: `factory.config.yaml.ux_ui.lint_check_4q: false` (default off, opt-in totale,
backward compat — R.P3). Se assente o `false` → 4ac no-op totale (non si applica,
indipendentemente dal contenuto dei report). Richiede anche `ux_ui.enabled: true` (il gate
master della capability). [^src: design_&_architecture/decisions/ADR-020.md §G §H]

**Esenzione**: TSK FE con frontmatter `ux_ui_no_auto_eval_skip_reason: "<motivazione>"`
→ no WARNING (il derivatore ha dichiarato esplicitamente che la coincidenza è intenzionale,
es. "task prototipale con agente singolo, review formale non applicabile"). L'esenzione
richiede motivazione esplicita (pattern identico a `ux_ui_skip_reason` per Check 4p e
`a11y_skip_reason` per Check 4o).

**Messaggio WARNING (template verbatim, placeholder `<id>`, `<generated_by>`)**:

```
TSK <id>: lo stesso agente (<generated_by>) risulta autore sia del deliverable Design
(ui_design_spec) sia della review UX (ux_ui_report). Verificare il vincolo no-auto-eval
(ADR-020 §H). Se intenzionale, aggiungere ux_ui_no_auto_eval_skip_reason nel frontmatter TSK.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][ux-ui-no-auto-eval][4ac] TSK-051: lo stesso agente (ui-designer) risulta autore sia del deliverable Design (ui_design_spec) sia della review UX (ux_ui_report). Verificare il vincolo no-auto-eval (ADR-020 §H). Se intenzionale, aggiungere ux_ui_no_auto_eval_skip_reason nel frontmatter TSK.
```

**Scenari di verifica**:

| # | layer | `ux_ui.enabled` | `lint_check_4q` | `ui_design_spec` | `ux_ui_report` | `design.generated_by` | `review.generated_by` | `skip_reason` | esito atteso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | fe | `true` | `false` (default) | valorizzato | valorizzato | `"ui-designer"` | `"ui-designer"` | — | no warning (gate off, R.P3) |
| 2 | fe | `false` | `true` | valorizzato | valorizzato | `"ui-designer"` | `"ui-designer"` | — | no warning (gate master ux_ui off) |
| 3 | fe | `true` | `true` | valorizzato | valorizzato | `"ui-designer"` | `"ui-designer"` | — | **WARNING 4ac** (stesso agente) |
| 4 | fe | `true` | `true` | valorizzato | valorizzato | `"ui-designer"` | `"ux-ui-reviewer"` | — | no warning (agenti distinti) |
| 5 | fe | `true` | `true` | valorizzato | valorizzato | `null` | `"ux-ui-reviewer"` | — | no warning (generated_by assente in ui_design_spec, skip) |
| 6 | fe | `true` | `true` | valorizzato | valorizzato | `"ui-designer"` | `null` | — | no warning (generated_by assente in ux_ui_report, skip) |
| 7 | fe | `true` | `true` | valorizzato | valorizzato | `null` | `null` | — | no warning (entrambi assenti, skip) |
| 8 | fe | `true` | `true` | valorizzato | valorizzato | `"ui-designer"` | `"ui-designer"` | valorizzato | no warning (esenzione motivata) |
| 9 | be | `true` | `true` | valorizzato | valorizzato | `"ui-designer"` | `"ui-designer"` | — | no warning (layer != fe) |
| 10 | fe | `true` | `true` | assente | valorizzato | — | `"ux-ui-reviewer"` | — | no warning (trigger non soddisfatto: ui_design_spec assente) |

**Numerazione**: «4ac» segue «4ab-bis» (EP-011 US-047 — Temporal State Machine) nella serie
alfabetica; non collide con alcun check esistente in questo file. Il gate config
`ux_ui.lint_check_4q` mantiene il nome «4q» per coerenza con ADR-020 §B e US-088; la
numerazione del check nel file lint-checks è **4ac** (correzione meccanica documentata sopra).

**Distinto da Check 4p** (EP-008 US-032, gate `ux_ui.required_on_fe_done`): 4p verifica che la
review UX/UI sia stata eseguita (campo `ux_ui_status`); 4ac verifica il vincolo di separazione
degli autori (campo `generated_by` nei report). Gate, trigger e target indipendenti; possono
coesistere in una factory con entrambi i flag attivi.

**Distinto da Check 4y** (EP-008/ADR-063 §B, gate `ux_ui.enabled`): 4y verifica la sostanza
dell'evidenza nei finding (`evidence` tracciabile); 4ac verifica l'identità dell'autore
(`generated_by` coincidente). Gate, trigger e messaggi indipendenti.

**Cross-link**: 4ac → ADR-020 §H (vincolo no-auto-eval) / §G (Check 4q candidato) / §E (schema
report uxui-design e uxui-review) + US-086 (campo `generated_by`) + US-088 (gate config
`ux_ui.lint_check_4q` in `factory.config.yaml`) + EP-024 (questa epica).

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

- Il check **non** emette WARNING su TSK `done` o `in-progress`
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

**Numerazione**: `4ae` — prossimo slot libero dopo `4ad` (EP-029 v2.22), primo check della
serie QA `4a*` per EP-027 (il secondo, `4ad`, copre EP-029 failure taxonomy).

**Cross-link**: 4ae → skill `flakiness-detection-protocol.md` §Sezione 5 (schema registro
quarantena + campo `quarantined_since_runs`) + `factory.config.yaml.qa_layer.flakiness_detection`
+ EP-027 (US-097) + US-095/US-096 (event store + quarantena reversibile).

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

**Distinta da Check 4q** (EP-009): 4q misura il done del TSK (event log/effort); 4u verifica la
chiusura della wave (governor_decision). Gate, trigger e messaggi indipendenti.

**Cross-link**: 4u → PATTERN §18.8 (Temporal Budget Hook) + §3 «Temporal Budget Governance» +
skill `temporal-budget-governor.md` + ADR-043 (semantica) / ADR-044 (granularità) / ADR-045
(bootstrap) / ADR-046 §E (questo check).

### 4v — Complexity Budget regola N:1 violata pre-release (Complexity Budget & Deprecations, EP-016 US-061, ADR-056 §D)

**Pattern allineato a Check 4q/4r/4s/4u (R.P3 opt-in totale)**: WARNING-only, opt-in via flag
config, nessun ERROR meccanico. Check 4v eredita la stessa shape per coerenza framework.

> **Nota di numerazione**: ADR-056 §D + PATTERN §23 prescrivono questo check come «Check 4t»; nel
> repo corrente lo slot «4t-migration» è **riservato** alla migration ADR-050 §I (pre-warning INFO
> opzionale post-upgrade, non ancora implementata) e gli slot 4u (EP-014 US-057) sono già occupati,
> quindi il check adotta il prossimo slot libero **4v** preservando l'intento dell'ADR (correzione
> meccanica di numerazione, non cambio di intento — lezione TSK-112). Il riferimento «Check 4t» in
> PATTERN §23 / ADR-056 va inteso come questo Check 4v.

**Severità: WARNING su factory derivate; ERROR sul meta-framework** (ADR-056 §A + TSK-166 2026-06-15 + PATTERN §23.5.1).
- **`required_on_release: false`** (default, R.P3, factory derivate): WARNING-only — il lint informa preventivamente, non blocca mai `/lint` né il Develop né il release.
- **`required_on_release: true`** (meta-framework, PATTERN §23.5.1): il check scala a **ERROR** su release minor/major con ratio N:1 violato e assenza del marker di esenzione `[skip-complexity-budget --reason="…"]`; la release è bloccata. Cadenza identica: solo pre-release minor/major (skip su patch `x.y.Z`). Factory derivate con flag `false` (default) non sono impattate.
Mai `heal-eligible` (giudizio semantico). Replica documentalmente il gate empirico `complexity_budget.required_on_release` di EP-016.

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.complexity_budget.required_on_release == true
AND release pre-tag minor/major (heading CHANGELOG.md `## vX.Y` con Y change/Z=0, o `## vX` major;
    skip su patch `## vX.Y.Z` con Z>0 — cadenza ADR-056 §F)
AND skill `complexity-budget-check` (5 step) verdict in {warn, fail}
    (ratio delta_added > N * delta_removed, default N=3, ADR-056 §B)
AND NOT (marker `[skip-complexity-budget --reason="<motivo>"]` presente nel CHANGELOG della versione)
```

**Gate**: `factory.config.yaml.complexity_budget.required_on_release: false` (default off, opt-in
totale, backward compat — R.P3). Se assente o `false` → 4v no-op totale (non si applica,
indipendentemente dal verdict della skill). Su release **patch** → 4v non si applica (cadenza
pre-release minor/major, ADR-056 §F).

**Esenzione**: marker `[skip-complexity-budget --reason="<motivo>"]` nell'entry CHANGELOG della
versione (ADR-056 §E) → la skill ritorna `verdict: pass` con `skipped: true` → no WARNING.
L'esenzione richiede motivazione esplicita.

**Severità del messaggio per verdict** (entrambi WARNING-only):

- `warn` (ratio 1 above N) → WARNING `"ratio 1 above N=<N>, plan removal next release"`.
- `fail` (ratio above N+1) → WARNING `"ratio significantly above N=<N>, removal required"`.

**Messaggio (template verbatim, placeholder `<version>`, `<ratio>`, `<N>`, `<verdict>`)**:

```
Complexity Budget regola N:1 violata per <version> (verdict: <verdict>, ratio <ratio> > N=<N>) quando complexity_budget.required_on_release: true. Considerare deprecazioni in PATTERN §23.2 (`/complexity-budget deprecate §X --reason="<r>"`) o aggiungere il marker [skip-complexity-budget --reason="<motivo>"] nel CHANGELOG. Vedi PATTERN §23, ADR-052, ADR-056. Disabilita Check 4v impostando complexity_budget.required_on_release: false.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][complexity-budget][4v] v2.20: regola N:1 violata (verdict: warn, ratio 4 > N=3). Considerare deprecazioni in PATTERN §23.2 o aggiungere [skip-complexity-budget --reason] nel CHANGELOG. Vedi PATTERN §23, ADR-056.
```

**Scenari di verifica**:

| # | `required_on_release` | release_kind | skill verdict | skip marker | esito atteso |
|---|---|---|---|---|---|
| 1 | `false` (default) | minor | warn | — | no warning (gate off, R.P3) |
| 2 | `true` | minor | pass | — | no warning (regola rispettata) |
| 3 | `true` | minor | warn | assente | **WARNING 4v** (ratio 1 above N) |
| 4 | `true` | minor | fail | assente | **WARNING 4v** (ratio above N+1) |
| 5 | `true` | minor | warn | presente | no warning (esenzione motivata, `skipped: true`) |
| 6 | `true` | patch | warn | — | no warning (cadenza: patch skip, ADR-056 §F) |

**Cross-link**: 4v → skill `complexity-budget-check.md` (5 step, ADR-056 §B) + comando
`/complexity-budget` + PATTERN §23 (§23.1 regola N:1, §23.2 Sezione Deprecate) + §3 entry
«Complexity Budget & Deprecations» + ADR-052 (regola N:1) / ADR-053 (`/pattern-view`) /
ADR-056 §D (questo check) + runbook `wiki/runbooks/complexity-budget-runbook.md`.

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

### 4g — Coerenza scheduler/depends_on (v2.11, PATTERN §18)

Solo se almeno un EP/US/TSK in `management/kanban/**` ha frontmatter `depends_on:` valorizzato:

- Per ogni artefatto con `depends_on: [...]`:
  - Ogni `<id>` nella lista deve avere lo stesso prefisso dell'artefatto host (EP→EP, US→US, TSK→TSK). Cross-tipo (es. TSK in `depends_on` di US) → **ERROR `invalid-depends-on-type`**.
  - Ogni `<id>` deve essere file esistente in `management/kanban/**/<id>.md`. Assente → **WARNING `orphan-depends-on`** (referenza a artefatto eliminato o rinominato).
  - Auto-riferimento (`depends_on` contiene il proprio `id`) → **ERROR `self-depends-on`**.
- **Cycle detection**: costruisci DAG `E_dep` sull'insieme {EP, US, TSK} e applica toposort (algoritmo di Kahn). Se rimangono nodi con `in_degree > 0` a fine algoritmo → ciclo presente → **ERROR `depends-on-cycle`** con lista dei nodi nel ciclo. Non `heal-eligible` (richiede giudizio semantico).
- **Drift body ↔ frontmatter** (solo TSK): se il body contiene `## Dependencies\n- TSK-XXX` ma `TSK-XXX` non è in `depends_on:` frontmatter (o viceversa) → **WARNING `dependencies-drift`** (frontmatter prevale per lo scheduler; rinconciliare a mano).
- **`code_path` validation** (solo TSK con `code_path:` valorizzato):
  - Ogni glob deve essere stringa non vuota. Glob vuoto → **WARNING `empty-code-path-glob`**.
  - Se `factory.config.yaml.scheduler.code_path_conflict: strict` e ≥ 2 TSK al "level 0" (depends_on vuoto o tutti soddisfatti) condividono lo stesso glob esatto → **INFO `code-path-overlap`** (non error; informativo per chi pianifica lo sprint, segnala che i due TSK saranno serializzati dal partition step).
- **`blocked_by` su TSK** (v2.11, esteso da US):
  - Ogni `Q_NNN` referenziato deve esistere in `management/questions.md`. Assente → **WARNING `orphan-blocked-by-q`**.
  - Q in `[RISOLTE]` ancora in `blocked_by` di un TSK → **WARNING `stale-blocked-by-tsk`** (simmetrico al check 4b su US; genera `reconcile-needed`).
- **`scheduler:` block coerenza** (solo se `factory.config.yaml.scheduler` esiste):
  - `enabled` ∈ `{true, false}`. Altrimenti → **ERROR `invalid-scheduler-enabled`**.
  - `max_parallel` intero ≥ 1. Altrimenti → **WARNING `invalid-max-parallel`** (applica default 4).
  - `parallel_gate_threshold` intero ≥ 1 e ≤ `max_parallel`. Altrimenti → **WARNING `invalid-gate-threshold`** (applica default 3).
  - `code_path_conflict` ∈ `{strict, warn, off}`. Altrimenti → **ERROR `invalid-conflict-mode`**.
  - `empty_code_path_policy` ∈ `{serial, parallel}`. Altrimenti → **ERROR `invalid-empty-policy`**.

### 4f — Coerenza Publisher (v2.10, PATTERN §17)

Solo se `factory.config.yaml.kanban_publish` esiste:

- Read `factory.config.yaml.kanban_publish`. Estrai `provider`, `target`, `auth_env`, `mode`, `batch_limit`, `mapping`.
- `provider` ∈ `{none, github, gitlab, jira, linear, custom}`. Altrimenti **ERROR `invalid-publish-provider`**.
- `mode` ∈ `{push-only}` per v2.10 (`bidirectional` riservato a v2.11). Altrimenti **ERROR `invalid-publish-mode`**.
- Se `provider ≠ none`:
  - `target` non vuoto. Assenza → **ERROR `missing-publish-target`**.
  - `auth_env` non vuoto. Assenza → **ERROR `missing-publish-auth-env`**.
  - `batch_limit` intero ≥ 1. Altrimenti **WARNING `invalid-batch-limit`** (applica default 10).
  - Mapping coerente: `mapping.epic_to ∈ {milestone, issue-label, project-column}`, `mapping.story_to ∈ {issue-label, issue-type-story}`, `mapping.task_to ∈ {issue-label}`, `mapping.sprint_to ∈ {milestone, project-iteration, cycle}`. Altrimenti **ERROR `invalid-publish-mapping`**.
  - Esistenza sub-agent corrispondente in `.claude/agents/<provider>-publisher.md`. Assenza → **ERROR `publisher-agent-missing`**.
  - Esistenza skill `.claude/skills/<provider>-mapping.md`. Assenza → **ERROR `publisher-mapping-missing`**.
- Per ogni `management/kanban/EP-*/EP-*.md`, `US-*/US-*.md`, `**/TSK-*.md`:
  - Frontmatter `external_id:` valorizzato:
    - Forma `<prefisso>:<id>` con `<prefisso>` ∈ `{github, gitlab, jira, linear}`. Altrimenti **ERROR `invalid-external-id-format`**.
    - Se `kanban_publish.provider: none` → **WARNING `orphan-external-id`** (il file ha un `external_id:` ma il publish è disabilitato; eredità di config precedente).
    - Se `kanban_publish.provider ≠ none` e prefisso ≠ provider → **WARNING `external-id-cross-provider`** (il file è pubblicato su un provider diverso da quello attualmente configurato; il publisher attuale lo skipperà).
  - Frontmatter `external_id:` assente:
    - Se `kanban_publish.provider ≠ none` e `status: in-progress|done` → **WARNING `unpublished-active-artifact`** (l'artefatto è attivo ma mai pubblicato; suggerisci `/kanban-publish run`).
- `wiki/log.md` ultime 10 entry `publish`: presenza di `provider:` + `created=N`, `updated=M`. Assenza → **WARNING `publish-without-summary`**.

### 4e — Coerenza manifest ↔ raw filesystem (v2.9, PATTERN §16)

Solo se `raw/.extraction-manifest.json` esiste:

- Per ogni entry `<key>` nel manifest:
  - Campo `source` ∈ `{pdf, figma, notion, ...}`. Assente → assume `pdf` (retrocompat) ma emit **WARNING `manifest-source-implicit`** (suggerisce di esplicitare).
  - Campo `primary_artifact` (v2.9): file esistente in `raw/`. Mancante o broken path → **ERROR `manifest-primary-missing`**.
  - Per `source: pdf`: `primary_artifact` deve essere `raw/<key>.txt`. Mismatch → **ERROR `manifest-shape-mismatch`**.
  - Per `source: figma`: `primary_artifact` deve essere `raw/<key>.kb.json` ed essere JSON parsabile. Mismatch o JSON malformato → **ERROR `manifest-shape-mismatch`** (sub-categoria `kb-json-invalid` se malformed).
  - Per `source: figma`: il KB JSON deve avere top-level `project`, `screens`, `components`, `flows`, `features`, `tokens` (anche se vuoti). Top-level mancante → **WARNING `kb-schema-incomplete`** (l'estrazione potrebbe essere stata parziale; vedi `extraction_metadata.status`).
  - `secondary_artifacts[]` (v2.9): ogni path elencato deve esistere. File mancante → **WARNING `manifest-secondary-missing`**.
  - `extracted_at`: ISO-8601 parsabile. Mismatch → **WARNING `manifest-bad-timestamp`**.
  - `extractor_version` (v2.9): presente per entries scritte da v2.9+. Assenza in entries antecedenti accettata silenziosamente.

- **Inverso (filesystem → manifest)**:
  - Per ogni `raw/*.txt` non in `raw/images/`: deve avere entry corrispondente nel manifest. Assenza → **WARNING `orphan-raw-artifact`** (probabilmente sync-docs non è ancora stato eseguito; suggerisce `/sync-docs`).
  - Per ogni `raw/*.kb.json`: deve avere entry con `source: figma`. Assenza → **WARNING `orphan-raw-artifact`** (suggerisce di rieseguire `/figma-sync` o di aggiungere manualmente l'entry).

- **Isolamento (PATTERN §16 invariante)**:
  - `raw/<key>.txt` con manifest `source: figma` → **ERROR `sync-adapter-collision`**.
  - `raw/<key>.kb.json` con manifest `source: pdf` → **ERROR `sync-adapter-collision`**.

### 4d — Coerenza VCS (v2.8, PATTERN §7 r.14, §15)

Solo se `factory.config.yaml` esiste con `vcs.mode` valorizzato:

- `vcs.mode: none` → `code_path` DEVE essere `""`. Altrimenti **ERROR `vcs-mode-mismatch`**.
- `vcs.mode: monorepo` → `code_path` deve essere relativo e dentro al repo
  (non assoluto, non `../`). Altrimenti **ERROR `vcs-mode-mismatch`**.
- `vcs.mode: submodule`:
  - `vcs.submodule_path` valorizzato e non vuoto. Altrimenti **ERROR `missing-submodule-path`**.
  - File `.gitmodules` esistente al root del repo. Altrimenti **ERROR `missing-gitmodules`**.
  - Entry per `<submodule_path>` presente in `.gitmodules`. Altrimenti **ERROR `submodule-not-declared`**.
  - Submodule inizializzato (`<submodule_path>/.git` esiste come file o directory). Altrimenti **WARNING `submodule-not-initialized`** (suggerisce `git submodule update --init --recursive`).
- `vcs.mode: sibling` → `code_path` deve esistere sul filesystem (se valorizzato).
  Se assente → **WARNING `sibling-code-path-not-found`** (può essere intenzionale
  pre-clone). Se presente ma non git repo → **WARNING `sibling-not-git-repo`**.
- `vcs.mode: external` → nessun check (path opaco).
- `branch_strategy` ∈ `{shared, per-tsk, per-sprint}` → altrimenti **ERROR `invalid-branch-strategy`**.
- `commit_coupling` ∈ `{pin, float}` → altrimenti **ERROR `invalid-commit-coupling`**.
- Se `commit_coupling: pin` → file `.factory-lock` esiste al root (anche vuoto,
  almeno header). Assenza → **WARNING `missing-factory-lock`** (suggerisce di
  crearlo o cambiare a `float`).
- `wiki/log.md` ultime 10 entry `develop`: il campo `**VCS mode:**` è presente.
  Assenza in ≥ 1 entry → **WARNING `develop-without-vcs-info`** (entry pre-v2.8,
  retrocompat OK).

### 4c — Coerenza topology ↔ filesystem ↔ routing (v2.7, PATTERN §7 r.13)

Solo se `factory.config.yaml` esiste:

- Leggi `factory.config.yaml`: estrai `topology`, `routing`, `code_path`.
- Per ogni `routing.X: agent` in `{be, fe, db, qa}`: verifica esistenza
  `.claude/agents/<X>-dev.md`. Assenza → **ERROR routing-missing-agent**.
- Per ogni `<X>-dev.md` presente: verifica `routing.X: agent`. Mismatch →
  **ERROR orphan-dev-agent**.
- `topology:` ∈ `{knowledge-only, plan-only, full-stack-agents, hybrid-be-agents, hybrid-fe-agents, custom}`.
  Altrimenti → **ERROR invalid-topology**.
- Se topologia ∈ {`full-stack-agents`, `hybrid-*`, `custom` con almeno un dev}
  ma `code_path:` è stringa vuota → **WARNING dev-agents-without-code-path**.
- Per ogni TSK con `consumer: agent`: verifica esista l'agente `<layer>-dev.md`
  corrispondente. Assenza → **WARNING tsk-consumer-no-agent** (è valido, ma
  l'utente dovrà esplicitamente forzare via `/dev`).

### 4b — Coerenza Q ↔ kanban (v2.6, gate L4 graduato)

- Per ogni `Q_NNN` in `management/questions.md` `[APERTE]`: verifica presenza
  campo `**Bloccante:** hard | soft`. Assenza → **WARNING missing-blocking-level**
  (non ERROR, per compatibilità retroattiva pre-v2.6; default = `hard`).
- Per ogni `Q_NNN` in `[RISOLTE]`: cerca US con `blocked_by:.*Q_NNN` o
  `pending_clarification:.*Q_NNN`. Match → **WARNING stale-blocked-by**:
  la US referenzia una Q già chiusa. Suggerisce: invocare `product-manager`
  o riconciliare manualmente. (Vedi marker `reconcile-needed` in `wiki/log.md`
  generati da [propagate-resolution](mdc:.cursor/skills/propagate-resolution/SKILL.md).)
- Per ogni US con `pending_clarification:` non vuota: verifica che almeno
  un ADR la citi nel proprio `pending_clarification:` frontmatter. Mismatch →
  **WARNING orphan-pending-clarification**.

## Citation audit (periodico)

Per ogni `[^src: <path> §<sez>]` in `wiki/**`:
- Verifica che `<path>` esista.
- Verifica che `<sez>` sia presente (header markdown matching) nel file citato.
- Vedi [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) per la grammatica completa.

Output separato: `wiki/lint/YYYY-MM-DD-citation-audit.md`.

## Classificazione `heal-eligible` (deterministica)

Per ogni ERROR, marca `heal-eligible: true` SOLO se rientra nella whitelist
[heal-protocol](mdc:.cursor/skills/heal-protocol/SKILL.md):

- `broken-wikilink` → eligible iff esiste slug `Y` con `fuzzy(X, Y) ≥ 0.90`.
- `missing-frontmatter-field` → eligible iff il campo è deducibile dal path
  (`type` da `wiki/<kind>/`, `id` da `EP-XXX|US-YYY|TSK-ZZZ`).
- `citation-section-mismatch` → eligible iff esiste header `H` nel file citato
  con `edit_distance(<sez>, H) ≤ 3`.
- `id-duplicate` → **mai** eligible (rischio di rompere riferimenti esterni).
- WARNING / orphan / claim non citato / contradiction / gap / `missing-blocking-level` / `stale-blocked-by` / `orphan-pending-clarification` → mai eligible (richiedono giudizio semantico).

## Output report

Path: `wiki/lint/YYYY-MM-DD-lint-report.md`

```markdown
---
type: lint
date: YYYY-MM-DD
heal_eligible_count: N
heal_eligible_categories: [broken-wikilink, missing-frontmatter-field, citation-section-mismatch]
---
# Lint Report — YYYY-MM-DD

## Riepilogo
| Check | Errors | Warnings |
|---|---|---|
| 1 — Orphan + wikilink | N | N |
| 2 — Claim senza fonte | N | N |
| 3 — Integrità kanban | N | N |
| 4 — Coerenza wiki↔kanban | N | N |
| 4b — Coerenza Q↔kanban (v2.6) | N | N |
| 4c — Coerenza topology (v2.7) | N | N |
| 4d — Coerenza VCS (v2.8) | N | N |
| 4e — Coerenza manifest↔raw (v2.9) | N | N |
| 4f — Coerenza Publisher (v2.10) | N | N |
| 4g — Coerenza scheduler/depends_on (v2.11) | N | N |
| 4ac — no-auto-eval UX/UI (v2.22, EP-024) | N | N |
| 4ad — TSK QA failed no classification (v2.22, EP-029) | N | N |
| 4ae — Quarantena stale QA (v2.22, EP-027) | N | N |
| 4ag — Staleness wiki pages (EP-031) | — | N |
| 4ah — Branch Awareness config coherence (EP-034) | — | N |
| 4ai — Agent Infrastructure Integrity | — | N |
| 4aj — Model Registry Consistency (INFO) | — | — |

## ERROR meccanici (heal-eligible)
- [ERROR][broken-wikilink][heal-eligible] wiki/concepts/foo.md: `[[oidc-flow]]` → suggerito `[[oidc-flows]]` (fuzzy 0.95)
- [ERROR][missing-frontmatter-field][heal-eligible] wiki/sources/bar.md: manca `type`, deducibile da path → `source`

## ERROR non meccanici (manuali)
- [ERROR][id-duplicate] management/kanban/EP-002/US-013/US-013.md: id duplicato di US-007 (NON heal-eligible)

## WARNING (igiene, mai heal-eligible)
- [WARNING] wiki/concepts/orphan.md: pagina non linkata dall'index.
- [WARNING][missing-blocking-level] management/questions.md Q_003: campo `**Bloccante:**` assente, applico default `hard`.
- [WARNING][stale-blocked-by] management/kanban/EP-001/US-017/US-017.md: `blocked_by: [Q_001]` ma Q_001 è in `[RISOLTE]` dal 2026-05-19. Vedi `reconcile-needed` in `wiki/log.md`.
- [WARNING][orphan-pending-clarification] management/kanban/.../US-024.md: `pending_clarification: [Q_005]` ma nessun ADR cita Q_005.
```

## Log entry

Append a `wiki/log.md` secondo [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md) (template `lint`).

## Validation Schema Checks (opt-in v2.19+)

**Gate**: `factory.config.yaml.release_governance.battle_test_gate.enabled: true` (R.P3 opt-in).
A gate `false` (default factory derivate), questa intera sezione è skip — **0 check aggiuntivi
vs v2.18**, nessun ERROR/WARNING introdotto, comportamento identico (backward compat ADR-032
§Backward compat). Eseguito **solo** se il gate master è abilitato.

### Check 4w — RUN-REPORT schema validation (ERROR su schema malformato, EP-012 US-049, ADR-032 §C §J)

> **Nota di numerazione**: TSK-096, ADR-032 §J e US-049 prescrivono questo check come «Check 4s»;
> nel repo corrente lo slot **4s** è già occupato (EP-015 US-060 — Consistency / compression
> output, due sotto-check 4s.1/4s.2), lo slot **«4t-migration»** è **riservato** alla migration
> ADR-050 §I (pre-warning INFO opzionale post-upgrade, non ancora implementata), e gli slot **4u**
> (EP-014 US-057) e **4v** (EP-016 US-061) sono già occupati. Il check adotta quindi il prossimo
> slot libero **4w** preservando l'intento dell'ADR (correzione meccanica di numerazione, non
> cambio di intento — lezione TSK-112/118/122). I riferimenti «Check 4s» in TSK-096 / ADR-032 §J /
> US-049 vanno intesi come questo **Check 4w**.

**Severità: ERROR — non WARNING** (deroga motivata a R.P3). Lo schema del RUN-REPORT è un
**contratto binario** (o è rispettato integralmente o no): uno schema malformato è un bug
strutturale, non un soft warning di igiene. Pattern parallelo a Check 4i (frontmatter EP/US/TSK)
e distinto da Check 4o/4p/4q/4r/4s/4u/4v (WARNING-only per status/marker mancanti). La deroga è
**legittima** perché l'ERROR esiste solo dietro un gate **interamente opt-in**: l'utente sceglie
se accendere `battle_test_gate.enabled`; se lo accende, lo schema **deve** essere rispettato
(decisione ADR-032 §J + Alternative «Lint Check WARNING-only scartato»). Non `heal-eligible`
(la compilazione di una sezione mancante richiede giudizio semantico sul contenuto del run).

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.release_governance.battle_test_gate.enabled == true
AND esiste un file matching `validation/runs/<slug>/RUN-REPORT.md`
AND il file ha frontmatter valido (campo `pre_check_status:` presente, valore ∈ {pending, pass, fail})
AND il file NON è esente (vedi §Esenzione / File esclusi)
AND almeno una delle 9 sezioni obbligatorie (§1..§9, schema ADR-032 §C) è MANCANTE
    oppure il frontmatter è incoerente (vedi §Sotto-check)
```

**Le 9 sezioni obbligatorie** (heading verbatim, schema ADR-032 §C, ordine atteso ma non stretto —
tutte devono essere presenti):

1. `## §1 Pre-check meccanico`
2. `## §2 Capability attivate`
3. `## §3 Backlog esercitato`
4. `## §4 Cosa ha funzionato`
5. `## §5 Cosa si è rotto`
6. `## §6 Capability NON esercitate`
7. `## §7 Lezioni`
8. `## §8 Indipendenza del campione`
9. `## §9 Firma`

**Sotto-check (tutti ERROR, gate-coperti)**:

- **4w.a — frontmatter mancante/invalido**: nessun frontmatter YAML, oppure campo
  `pre_check_status:` assente, oppure valore ∉ {pending, pass, fail}. → ERROR `run-report-frontmatter-invalid`.
- **4w.b — sezioni §1..§9 incomplete**: ≥1 dei 9 heading obbligatori sopra è assente. → ERROR
  `run-report-section-missing` (un ERROR per ogni sezione mancante, messaggio canonico sotto).
- **4w.c — pre_check/review incoerenti**: `review_status: pass` con `pre_check_status` ∈
  {pending, fail} (la review umana non può passare se il pre-check non è `pass` — CRITERIA.md
  §Principio: review parte SOLO se pre-check `pass`). → ERROR `run-report-verdict-incoherent`.

**Gate**: `factory.config.yaml.release_governance.battle_test_gate.enabled: false` (default off,
opt-in totale R.P3). Se assente o `false` → 4w no-op totale (la sezione `validation/runs/**` non
viene nemmeno letta, comportamento identico a v2.18).

**Esenzione / File esclusi** (nessun ERROR su questi):

- `validation/runs/TEMPLATE/RUN-REPORT.md` — il template scaffoldato stesso (marker `<<...>>`,
  non un run reale).
- Qualsiasi file con nota `[REFERENCE-ONLY]` nel frontmatter o nel corpo (es.
  `validation/runs/fsc-trasf-demo-2026-05-19/RUN-REPORT.md`, run di reference ex-post non
  gate-eligible — ADR-032 §G).

Salvo questi due casi, **nessun'altra esenzione**: lo schema canonico deve essere rispettato
integralmente quando il gate è on (ADR-032 §J «Esenzione: nessuna»).

**Pattern di rilevamento (regex)**:

```
1. Glob `validation/runs/*/RUN-REPORT.md`.
2. Scarta i file esclusi: path contiene `TEMPLATE`, oppure il contenuto matcha `\[REFERENCE-ONLY`.
3. Per ogni file rimanente:
   a. Estrai il frontmatter YAML (blocco fra i primi due `---`). Se assente o senza
      `pre_check_status:` ∈ {pending|pass|fail} → ERROR 4w.a; salta gli altri sotto-check del file.
   b. Per ciascuno dei 9 heading obbligatori (`^## §<N> <nome>$`, regex case-sensitive sull'icona §N):
      se assente → ERROR 4w.b (uno per sezione mancante).
   c. Se `review_status: pass` AND `pre_check_status:` ∈ {pending, fail} → ERROR 4w.c.
```

**Messaggio (template verbatim, placeholder `<slug>`, `<N>`, `<nome>`)**:

- 4w.a — `"RUN-REPORT <slug>: frontmatter mancante o pre_check_status invalido (atteso pending|pass|fail). Schema obbligatorio quando battle_test_gate.enabled: true. (ADR-032 §C)"`
- 4w.b — `"RUN-REPORT <slug>: sezione §<N> (<nome>) mancante. Vedi validation/CRITERIA.md §5 per il template fields e validation/runs/TEMPLATE/RUN-REPORT.md per lo schema. (ADR-032 §C)"`
- 4w.c — `"RUN-REPORT <slug>: review_status: pass incoerente con pre_check_status: <valore> (la review umana parte solo se pre-check pass). Vedi validation/CRITERIA.md §Principio. (ADR-032 §A)"`

**Output format** (sezione `## ERROR non meccanici (manuali)` del report — non `heal-eligible`):

```
- [ERROR][run-report-section-missing][4w] validation/runs/v2.19-tag-run-1/RUN-REPORT.md: sezione §5 (Cosa si è rotto) mancante. Vedi validation/CRITERIA.md §5 + template. (ADR-032 §C)
- [ERROR][run-report-frontmatter-invalid][4w] validation/runs/foo/RUN-REPORT.md: pre_check_status assente. (ADR-032 §C)
- [ERROR][run-report-verdict-incoherent][4w] validation/runs/bar/RUN-REPORT.md: review_status: pass con pre_check_status: pending. (ADR-032 §A)
```

**Scenari di verifica**:

| # | `battle_test_gate.enabled` | file | sezioni | frontmatter | esito atteso |
|---|---|---|---|---|---|
| 1 | `false` (default) | run reale | §3 mancante | ok | no ERROR (gate off, R.P3 — 0 check vs v2.18) |
| 2 | `true` | run reale | tutte §1..§9 | ok + coerente | no ERROR (schema valido) |
| 3 | `true` | run reale | §3 mancante | ok | **ERROR 4w.b** (`run-report-section-missing`) |
| 4 | `true` | run reale | tutte | `pre_check_status` assente | **ERROR 4w.a** (`run-report-frontmatter-invalid`) |
| 5 | `true` | run reale | tutte | `review_status: pass` + `pre_check_status: pending` | **ERROR 4w.c** (`run-report-verdict-incoherent`) |
| 6 | `true` | `TEMPLATE` | con marker `<<...>>` | template | no ERROR (file escluso) |
| 7 | `true` | reference `[REFERENCE-ONLY]` | qualsiasi | ex-post | no ERROR (file escluso, ADR-032 §G) |

**Non duplica** la validazione dello Step 2 della skill `release-validation-gate` (ADR-033 §D):
il `/release` gate è l'**enforcement point primario** (fail-loud a tag-time), il Check 4w è il
**safety net** nel workflow di sviluppo ordinario (segnala lo schema malformato prima che il
maintainer invochi `/release`). La severity è ERROR — non WARNING come il companion Check 4t di
ADR-033 §I sul CHANGELOG — perché schema RUN-REPORT malformato è un bug strutturale, mentre
l'assenza della sezione CHANGELOG è un reminder pre-tag.

**Cross-link**: 4w → schema canonico RUN-REPORT (`validation/runs/TEMPLATE/RUN-REPORT.md`) +
criteri (`validation/CRITERIA.md` §1 §2 §5) + ADR-032 §C (schema 9 sezioni) / §J (questo check) +
ADR-033 (skill `release-validation-gate`, enforcement primario) + ADR-034 (schema sezione
CHANGELOG, Check 4x companion) + US-049 (origine) / US-050 (gate).

### Check 4x — CHANGELOG Validation evidence mancante (WARNING, EP-012 US-050, ADR-033 §I + ADR-034 §A)

> **Nota di numerazione**: TSK-099, ADR-033 §I e US-050 prescrivono questo check come «Check 4t»;
> nel repo corrente lo slot **«4t»** è **riservato** alla migration ADR-050 §I (pre-warning INFO
> opzionale post-upgrade, `compression.migration.audit_after_upgrade`, non ancora implementata),
> mentre gli slot **4q/4r/4s/4u/4v/4w** sono già occupati. Il check adotta quindi il prossimo
> slot libero **4x** preservando l'intento dell'ADR (correzione meccanica di numerazione, non
> cambio di intento — lezione TSK-112/118/122/096). I riferimenti «Check 4t» in TSK-099 / ADR-033 §I /
> US-050, e il riferimento «Check 4t companion» nel Check 4w sopra, vanno intesi come questo **Check 4x**.

**Severità: WARNING — non ERROR** (coerente con R.P3, opt-in totale). Il `/release` gate fa già
fail-loud al momento dell'invocazione (skill `release-validation-gate` Step 5, ADR-033 §D); il lint
è solo un **reminder pre-tag** per il maintainer (companion del Check 4w, che è invece ERROR sullo
schema RUN-REPORT). Mai `heal-eligible` (la compilazione della sezione richiede giudizio semantico
sull'evidenza del run). Distinto da Check 4w: 4w enforce lo schema RUN-REPORT (`validation/runs/**`),
4x enforce la presenza dell'evidenza nel CHANGELOG. [^src: design_&_architecture/decisions/ADR-033.md §I]

**Pattern allineato a Check 4m/4n/4o/4p/4q/4r/4s/4u/4v (R.P3 opt-in totale)**: WARNING-only, opt-in
via flag config, nessun ERROR meccanico. Check 4x eredita la stessa shape per coerenza framework.

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.release_governance.battle_test_gate.enabled == true
AND CHANGELOG.md contiene un heading versione `## v<version>` (es. `## v2.19` o `## v2.19.0`)
AND NON esiste la sub-sezione `## Validation evidence (v<version>)` nel CHANGELOG.md
AND NON esiste il file `validation/release-gates/v<version>/GATE-REPORT.md`
    (ricerca side-by-side: assenza di ENTRAMBI gli artefatti)
AND il blocco release di quella versione NON è esente (vedi §Esenzione)
```

**Gate**: `factory.config.yaml.release_governance.battle_test_gate.enabled: true` (R.P3 opt-in).
A gate `false` (default factory derivate) o assente → 4x no-op totale: nessun WARNING aggiuntivo
vs v2.18 (backward compat ADR-033 §J, R.P3).

**Esenzione**: frontmatter `validation_evidence_skip: true` nel blocco release di `CHANGELOG.md`
(raramente usato, richiede audit reason esplicita). La presenza del marker `[gate-bypassed]` nella
sezione `## Validation evidence (v<version>)` (bypass tracciato, ADR-033 §E) **soddisfa** il check
(la sezione esiste, il bypass è auditato): nessun WARNING.

**Messaggio (template verbatim, placeholder `<version>`)**:

```
CHANGELOG.md v<version>: sezione '## Validation evidence (v<version>)' assente e GATE-REPORT.md non trovato (validation/release-gates/v<version>/). Invocare `/release v<version> --dry-run` prima del tag per produrre l'evidenza. Disabilita Check 4x impostando release_governance.battle_test_gate.enabled: false; esenta la singola release con validation_evidence_skip: true + reason nel blocco CHANGELOG. (ADR-034 §A, ADR-033 §I)
```

**Output format** (sezione `## WARNING (igiene, mai heal-eligible)` del report):

```
- [WARNING][changelog-validation-evidence-missing][4x] CHANGELOG.md v2.20: sezione '## Validation evidence (v2.20)' assente e GATE-REPORT.md non trovato. Invocare `/release v2.20 --dry-run` prima del tag. (ADR-034 §A, ADR-033 §I)
```

**Scenari di verifica**:

| # | `battle_test_gate.enabled` | versione CHANGELOG | sezione `## Validation evidence` | GATE-REPORT.md | esito atteso |
|---|---|---|---|---|---|
| 1 | `false` (default) | `## v2.20` | assente | assente | no WARNING (gate off, R.P3 — 0 check vs v2.18) |
| 2 | `true` | `## v2.20` | presente | (qualsiasi) | no WARNING (evidenza nel CHANGELOG) |
| 3 | `true` | `## v2.20` | assente | presente | no WARNING (evidenza side-by-side in validation/release-gates/) |
| 4 | `true` | `## v2.20` | assente | assente | **WARNING 4x** (`changelog-validation-evidence-missing`) |
| 5 | `true` | `## v2.20` | con marker `[gate-bypassed]` | (qualsiasi) | no WARNING (bypass tracciato, ADR-033 §E) |
| 6 | `true` | `## v2.20` | assente + `validation_evidence_skip: true` | assente | no WARNING (esente, audit reason) |

**Non blocca** il workflow (WARNING-only). L'enforcement è nel comando `/release` (ADR-033, fail-loud
a tag-time). Il Check 4x è il safety net pre-tag nel workflow ordinario, companion del Check 4w
(ERROR sullo schema RUN-REPORT).

**Cross-link**: 4x → ADR-033 §I (questo check candidato) / §D Step 5 (enforcement primario nella skill
`release-validation-gate`) / §E (bypass tracciato) + ADR-034 §A (schema sezione CHANGELOG `## Validation
evidence`) + ADR-036 §B (PATTERN §22 Release Governance) + Check 4w (companion ERROR, RUN-REPORT schema) +
US-050 (origine).

### Check 4y — ux_ui evidence-provenance (SOSTANZA) nei report di review [ADR-063 §B]

**Pattern allineato a Check 4p (ux_ui forma) + Check 4o (a11y) (R.P3 opt-in totale)**: WARNING-only, opt-in
via flag `ux_ui.enabled`, nessun ERROR meccanico. Check 4y eredita la stessa shape per coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione ADR-063 §B, allineato a Check 4p che
è anch'esso WARNING-only). Il guard di sostanza complementa il guard di forma (Check 4p: `rubric_ref`),
informando sul campo `evidence` non verificabile; il lint non blocca mai `/lint` né il Develop. Mai
`heal-eligible` (giudizio semantico sul contenuto dell'evidenza). Non si applica a report prodotti prima di
ADR-063 (backward compat — §Non applicabilità retroattiva).

**Gate**: `factory.config.yaml.ux_ui.enabled: false` (default off, opt-in totale, no-op a flag spento — R.P3
e ADR-063 §B). Se assente o `false` → 4y no-op totale (la sezione `code_quality/reports/` non viene nemmeno
letta per questo check). [^src: design_&_architecture/decisions/ADR-063.md §B §Conseguenze]

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.ux_ui.enabled == true
AND TSK.frontmatter.ux_ui_status IN ['pass', 'conditional']
AND TSK.frontmatter.ux_ui_report valorizzato (path a report esistente)
AND il report ADR-063-eligible (vedi §Non applicabilità retroattiva)
AND almeno un finding nel report ha evidence non verificabile (vedi §Logica di verifica)
```

**Logica di verifica evidence tracciabile** (per ogni finding nel report `<ux_ui_report>`):

1. Campo `evidence` MANCANTE o NULL o VUOTO → flag WARNING.
2. `evidence` è un path: verificare che il file esista su disco. File inesistente → flag WARNING.
3. `evidence` è uno snippet/ref testuale: verificare che il campo NON contenga token generici
   (`"non disponibile"`, `"non verificabile"`, `"N/A"`, `"stimato"`, stringa vuota `""`).
   Token generico presente → flag WARNING.

**Non applicabilità retroattiva**: i report prodotti **prima** dell'introduzione di ADR-063 (marker assente
o path del report senza timestamp ≥ data di adozione ADR-063) NON vengono flaggati → 0 WARNING (backward
compat dichiarata). In pratica: il check si applica solo ai report che hanno già il campo `evidence` nel
proprio schema finding (introdotto dalla skill `ux-ui-review-protocol` Step 5 via TSK-134).

**Complementarità con Check 4p (forma)**:
- Check 4p verifica `rubric_ref` presente (forma).
- Check 4y verifica `evidence` tracciabile (sostanza).
- Entrambi WARNING-only, entrambi gated da `ux_ui.enabled`.
- Check 4p si applica allo stato TSK (`ux_ui_status` mancante/pending); Check 4y si applica al contenuto
  del report (`evidence` nei finding). I due check sono indipendenti e possono coesistere. [^src: design_&_architecture/decisions/ADR-063.md §B]

**Messaggio (template verbatim, placeholder `<finding_id>`, `<ux_ui_report>`)**:

```
Finding <finding_id> in <ux_ui_report> senza evidenza verificabile (evidence-provenance ADR-063 §B). Verificare che la review sia stata eseguita con tool visivi callable o in modalità no-visual con Read/Grep. Vedi ADR-063 §B, US-067.
```

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][ux-ui-evidence-provenance][4y] TSK-080: finding UX-01 in code_quality/reports/TSK-080-iter-1-uxui-review.md senza evidenza verificabile (evidence: null). Verificare review con tool visivi o Read/Grep. Vedi ADR-063 §B.
- [WARNING][ux-ui-evidence-provenance][4y] TSK-080: finding UX-03 in code_quality/reports/TSK-080-iter-1-uxui-review.md senza evidenza verificabile (evidence: "non disponibile"). Verificare review con tool visivi o Read/Grep. Vedi ADR-063 §B.
```

**Scenari di verifica**:

| # | `ux_ui.enabled` | `ux_ui_status` | report | finding `evidence` | backward-compat | esito atteso |
|---|---|---|---|---|---|---|
| 1 | `false` (default) | `pass` | presente | `null` | — | no warning (gate off, R.P3) |
| 2 | `true` | `pass` | presente | `"screenshots/desktop-1280.png"` (file esistente) | — | no warning (evidenza verificabile) |
| 3 | `true` | `pass` | presente | `null` | — | **WARNING 4y** (evidence null) |
| 4 | `true` | `pass` | presente | `""` | — | **WARNING 4y** (evidence vuoto) |
| 5 | `true` | `pass` | presente | `"non disponibile"` | — | **WARNING 4y** (token generico) |
| 6 | `true` | `pass` | presente | `"screenshots/missing.png"` (file inesistente) | — | **WARNING 4y** (path non resolvibile) |
| 7 | `true` | `todo` | assente | — | — | no warning (trigger non soddisfatto: ux_ui_status non in pass/conditional) |
| 8 | `true` | `pass` | presente | tutti i finding con evidence verificabile | — | no warning (tutti i finding OK) |
| 9 | `true` | `pass` | report pre-ADR-063 | `null` | presente | no warning (backward compat, report legacy) |

**Numerazione**: «4y» segue «4x» (EP-012 US-050, ADR-033/034, CHANGELOG validation) nella serie alfabetica;
non collide con alcun check esistente in questo file (precede «4z» e successivi riservati). Distinto da Check
4p: 4p enforce lo stato review sul TSK (`ux_ui_status` mancante/pending/conditional → WARNING sul TSK), 4y
enforce la sostanza dei finding nel report prodotto (`evidence` tracciabile → WARNING per finding). Gate,
trigger e target (TSK vs report) indipendenti; possono coesistere.

**Cross-link**: 4y → ADR-063 §B (guard evidence-provenance, questo check) / §A (fail-loud Step 1, skill) /
§C (tool Read/Grep agente) + skill `ux-ui-review-protocol.md` Step 5 (guard runtime, TSK-134) + Check 4p
(companion forma) + US-067 (origine EP-008).

### 4z — acceptance-spec schema validation (Functional Oracle, EP-018 US-069, ADR-065 §E)

**Pattern allineato a Check 4m/4n/4o/4p/4q/4r/4s/4u/4v/4x/4y (R.P3 opt-in totale)**: misto ERROR/WARNING,
opt-in via flag `fe_correctness.functional_oracle.enabled`, no-op a flag spento. Check 4z eredita la stessa
shape per coerenza framework.

> **Nota di numerazione**: TSK-145 e il TSK Technical Specs prescrivono questo check come «Check 4y»;
> nel repo corrente lo slot **4y** è già occupato (EP-008/ADR-063 §B — ux_ui evidence-provenance,
> TSK-137/138/139/140). Il check adotta quindi il prossimo slot libero **4z** preservando l'intento
> (correzione meccanica di numerazione, non cambio di intento — lezione TSK-112/118/122/096/137).
> I riferimenti «Check 4y» in TSK-145 / US-069 vanno intesi come questo **Check 4z**.

**Severità: mista** — ERROR su spec assente + `enabled: true` (config incoerente, fail-loud ADR-065 §E);
WARNING su `kind` non in whitelist (schema drift); no-op a `enabled: false` (R.P3 backward compat totale).
La deroga ERROR è **legittima** per lo stesso motivo di Check 4w (contratto binario opt-in): l'utente ha
scelto di abilitare il functional oracle senza fornire la spec → bug strutturale, non soft warning di igiene
(ADR-065 §E «MAI un pass silenzioso», anti-fabbricazione ADR-063/064). Non `heal-eligible` (la compilazione
di una spec mancante richiede contenuto del progetto). WARNING su `kind` non in whitelist → mai
`heal-eligible` (giudizio semantico: potrebbe essere schema drift legittimo del framework vs obsolescenza
nella spec).

**Gate**: `factory.config.yaml.fe_correctness.functional_oracle.enabled: false` (default off, opt-in
totale, backward compat — R.P3). Se assente o `false` → 4z no-op totale: `code_quality/acceptance/**`
non viene letto per questo check, 0 ERROR/WARNING aggiuntivi vs v2.18. [^src: design_&_architecture/decisions/ADR-065.md §E]

**Trigger (AND — tutte le condizioni devono essere vere per ogni sotto-check)**:

#### 4z.1 — Spec assente/illeggibile con `functional_oracle.enabled: true` (ERROR)

```
factory.config.yaml.fe_correctness.functional_oracle.enabled == true
AND almeno un TSK ha frontmatter.functional_acceptance_spec: valorizzato
AND il file referenziato da functional_acceptance_spec: NON esiste (o non è leggibile)
```

**Severità**: ERROR `acceptance-spec-missing`. Allineato ad ADR-065 §E: «`enabled: true` + spec
assente/illeggibile → fail-loud (config incoerente)». Non genera mai un pass silenzioso
(anti-fabbricazione).

**Messaggio (template verbatim, placeholder `<TSK-id>`, `<path>`)**:

```
TSK <TSK-id>: functional_acceptance_spec: '<path>' referenziata ma file assente (o illeggibile). Con fe_correctness.functional_oracle.enabled: true la spec è obbligatoria. Creare il file o correggere il path. Vedi ADR-065 §E, .claude/schemas/acceptance-spec.schema.yaml.
```

#### 4z.2 — `kind` non in whitelist (WARNING)

```
factory.config.yaml.fe_correctness.functional_oracle.enabled == true
AND almeno un TSK ha frontmatter.functional_acceptance_spec: valorizzato
AND il file referenziato esiste ed è leggibile
AND almeno un'asserzione nel blocco `assertions:` ha `kind` non appartenente alla whitelist:
    { selector_visible, selector_absent, attr_equals, text_matches,
      canvas_pixel_variance, storage_key_present, console_no_error, network_no_5xx }
```

**Severità**: WARNING `acceptance-spec-kind-unknown`. Segnala schema drift: il `kind` usato non è nel
set chiuso definito dal framework (ADR-065 §C). Può indicare: (a) primitiva custom non supportata
dall'engine → l'esecuzione fallirà a runtime; (b) refactoring del framework che ha rinominato/rimosso
una primitiva. Il lint informa ma non blocca (il progetto potrebbe aver introdotto la primitiva su una
versione del framework più recente del lint in uso).

**Messaggio (template verbatim, placeholder `<TSK-id>`, `<path>`, `<kind>`)**:

```
TSK <TSK-id>: acceptance-spec '<path>' usa kind '<kind>' non riconosciuto (whitelist ADR-065 §C). Verificare che il kind sia supportato dall'engine o aggiornare la spec. Vedi ADR-065 §C, .claude/schemas/acceptance-spec.schema.yaml.
```

**Gate** (stesso per 4z.1 e 4z.2): `fe_correctness.functional_oracle.enabled: false` (default) →
entrambi i sotto-check no-op totale. Coerente con R.P3: a flag spento `/lint` sulla factory
v2.19 senza opt-in = 0 nuovi ERROR/WARNING da 4z.

**Output format** (sezioni del report):

```
## ERROR non meccanici (manuali)
- [ERROR][acceptance-spec-missing][4z.1] TSK-101: functional_acceptance_spec: 'code_quality/acceptance/app.acceptance.yaml' referenziata ma file assente. Con functional_oracle.enabled: true la spec è obbligatoria. Vedi ADR-065 §E.

## WARNING (igiene)
- [WARNING][acceptance-spec-kind-unknown][4z.2] TSK-102: acceptance-spec 'code_quality/acceptance/app.acceptance.yaml' usa kind 'screenshot_match' non riconosciuto (whitelist ADR-065 §C). Verificare kind supportato o aggiornare spec. Vedi ADR-065 §C.
```

**Scenari di verifica**:

| # | `functional_oracle.enabled` | `functional_acceptance_spec` valorizzato | file esiste | `kind` in whitelist | esito atteso |
|---|---|---|---|---|---|
| 1 | `false` (default) | sì | no | — | no ERROR/WARNING (gate off, R.P3 — 0 check vs v2.18) |
| 2 | `true` | no | — | — | no ERROR/WARNING (TSK non referenzia spec, no trigger) |
| 3 | `true` | sì | no | — | **ERROR 4z.1** (`acceptance-spec-missing`) |
| 4 | `true` | sì | sì | tutti in whitelist | no ERROR/WARNING (schema valido) |
| 5 | `true` | sì | sì | almeno 1 fuori whitelist | **WARNING 4z.2** (`acceptance-spec-kind-unknown`) |
| 6 | `true` | sì | sì | misti in+fuori whitelist | **WARNING 4z.2** (per ogni kind non in whitelist) |
| 7 | `true` | sì | sì (vuoto / `scenario: []`) | — | no ERROR/WARNING (spec presente e leggibile → verdict `skip` dichiarato a runtime, non lint issue) |

**Numerazione**: «4z» segue «4y» (EP-008/ADR-063 §B — ux_ui evidence-provenance) nella serie
alfabetica; non collide con alcun check esistente in questo file. «4y» era il target originale (TSK-145 /
US-069), ma lo slot era già occupato; 4z è il prossimo slot libero (correzione meccanica di numerazione,
lezione TSK-112/118/122/096/137 — pattern consolidato).

**Distinto da Check 4p** (ux_ui forma, gate `ux_ui.required_on_fe_done`) e **da Check 4y** (ux_ui
evidence-provenance, gate `ux_ui.enabled`): 4z è gated da `fe_correctness.functional_oracle.enabled`,
opera su spec YAML di dominio funzionale (non su report di review UX/UI). Gate, trigger e target
indipendenti; possono coesistere in una factory con entrambe le capability attive.

**Cross-link**: 4z → ADR-065 §E (fail-loud spec assente) / §C (whitelist kind primitivi) / §B (schema
struttura spec) + schema `.claude/schemas/acceptance-spec.schema.yaml` + US-069 (origine) + EP-018
(Functional Oracle capability) + ADR-066 (vocabolario scenario) + ADR-064 (app-lifecycle serve, engine).

## Check 4af — Embedding Similarity Wiki vs PATTERN (INFO only, sperimentale — EP-031 research)

**Trigger**: `wiki_lint.semantic_check.enabled: true` (default: false → skip totale)
**Severità**: INFO — mai WARNING, mai ERROR. Non blocca pipeline. Non è criterio di gate.
**Audience**: maintainer e operatori che vogliono monitorare la deriva semantica della wiki.

### Algoritmo

1. **Scopri pagine candidate**: scansiona `wiki/**/*.md` con frontmatter `pattern_section: "§N"`.
   Pagine senza questo campo → skip silenzioso per quella pagina.
2. **Calcola embedding**: per ogni pagina candidata:
   - Embedding A = embedding del testo completo della pagina wiki.
   - Embedding B = embedding del testo della sezione `§N` estratta da `PATTERN.md`.
3. **Confronta similarità coseno**: `score = cosine_similarity(A, B)`.
4. **Emetti INFO se score < threshold** (default 0.75):
   ```
   INFO [Check 4af] wiki/concepts/compression-layer.md — §20 — score: 0.61 (< 0.75)
   ```
5. **Stima costo**: prima del scan, stima N_pagine × costo_per_embedding e confronta
   con `wiki_lint.semantic_check.cost_warn_usd`. Se costo_stimato > soglia → chiedi
   conferma esplicita (WARNING separato, non bloccante).
6. **Scrivi report** (se `output_report: true`):
   `<output_report_path>/wiki-lint-semantic-<YYYY-MM-DD>.md` — tabella con tutte le
   pagine sotto soglia ordinate per score crescente.

### Invarianti

- **No API call a flag spento**: `enabled: false` → zero chiamate embedding, zero side effect.
- **No ERROR mai**: questo check non cambia severità da INFO a WARNING/ERROR anche in futuro,
  finché EP-031 US-109 ADR non verte a GO con calibrazione validata.
- **Idempotente**: due run sulla stessa wiki e PATTERN.md producono lo stesso report.
- **Skip silenzioso su pagine senza `pattern_section:`**: non è un error, è una scelta del maintainer.

### Dipendenza esterna

Embedding API (Voyage-3 via Anthropic o configurabile via `embedding_model`). Se l'API
non è raggiungibile → WARNING separato + skip del check (graceful degradation, non fail-loud).

## Check 4ag — Staleness Threshold Wiki Pages (WARNING, always-on — EP-031 segnale economico)

**Trigger**: sempre attivo — nessun flag richiesto. Segnale economico complementare a Check 4af.
**Severità**: WARNING — blocca lint se sopra threshold critico (> 365 gg), altrimenti INFO.
**Audience**: maintainer che monitorano l'aggiornamento del corpus wiki.

### Razionale (ADR-EP031-001)

Implementa il segnale economico della piramide BM25→dense→LLM-judge: staleness è
gratuito, deterministico, zero falsi positivi del tipo "mapping errato", e scala a corpus
infinito senza costo API. Complementa Check 4af (embedding/LLM-judge) che rileva drift
semantico ma ha costo variabile.

### Algoritmo

1. **Scansiona** `wiki/**/*.md` (escludi `log.md`, `lint/`, `sources/`, `index.md`).
2. **Leggi** il campo `updated:` (o `created:` se `updated:` assente) dal frontmatter YAML.
3. **Calcola** `age_days = today − updated`.
4. **Emetti** in base all'età:
   - `age_days > 365` → **WARNING** `[Check 4ag] STALE: <path> — ultimo aggiornamento <N> giorni fa (soglia: 365)`
   - `age_days > 180` → **INFO** `[Check 4ag] INFO: <path> — non aggiornata da <N> giorni (soglia: 180)`
   - `age_days ≤ 180` → skip silenzioso.
5. **Pagine senza `updated:` e senza `created:`** → **WARNING** `[Check 4ag] MISSING-DATE: <path>`.

### Invarianti

- **Zero API call**: staleness è puro confronto di date — nessuna dipendenza esterna.
- **Deterministico**: stessa wiki + stessa data → stesso output (diversamente da LLM-judge).
- **Non blocca il lint totale**: le WARNING 4ag non impediscono il completamento degli altri check.
- **Esclusione lint/ e sources/**: i report di lint e i sorgenti raw non sono soggetti a staleness check.

### Relazione con Check 4af

Check 4ag e 4af sono complementari, non alternativi:
- **4ag** (staleness) → segnale economico, always-on, rileva pagine non toccate → suggerisce revisione.
- **4af** (embedding/LLM-judge) → segnale semantico, opt-in, rileva contenuto obsoleto anche se recentemente modificato.

## Check 4ah — Branch Awareness config coherence (WARNING, opt-in — EP-034)

**Trigger**: solo se `factory.config.yaml` contiene un blocco `vcs.branch_awareness` (a qualunque
livello: top-level `vcs:` o entry `code_paths[i].vcs`). A blocco assente → skip silenzioso (R.B10).
**Severità**: WARNING — non blocca il lint, segnala incoerenze di configurazione.
**Audience**: maintainer che abilitano il Branch Awareness Layer.

### Algoritmo

1. Per ogni blocco `vcs.branch_awareness` presente, verifica i valori enum:
   - `dispatch_gate ∈ {off, warn, block}` — altrimenti WARNING `[Check 4ah] invalid dispatch_gate`.
   - `auto_align ∈ {off, propose}` — altrimenti WARNING `[Check 4ah] invalid auto_align`.
   - `enabled`, `preflight`, `drift_check` booleani.
2. **Coerenza attivazione**: se `preflight: true` O `dispatch_gate != off` O `drift_check: true`
   ma `enabled: false` → WARNING `[Check 4ah] branch_awareness: sotto-flag attivo con enabled: false
   (il layer è no-op finché enabled resta false, R.B10)`.
3. **Coerenza mode**: se `branch_awareness.enabled: true` ma `vcs.mode ∈ {monorepo, external, none}`
   → INFO `[Check 4ah] branch_awareness degenere su mode <X> (single-HEAD): nessun effetto pratico`.
4. **Manifest**: se `.factory-branches.yaml` esiste e contiene target non presenti in
   `code_paths[].name` → WARNING `[Check 4ah] .factory-branches.yaml: target <X> non in code_paths`.

### Invarianti

- **Read-only**: il check non modifica config né esegue comandi git (coerente con R.B7).
- **Non blocca**: solo WARNING/INFO, mai ERROR — la config Branch Awareness è opt-in.
- **Skip a blocco assente**: factory senza `branch_awareness` non vedono questo check (R.B10).

## Check 4ai — Agent Infrastructure Integrity (WARNING, always-on)

**Trigger**: sempre attivo — verifica l'integrità strutturale del layer agenti (`.claude/agents/`).
**Severità**: WARNING — mai ERROR, mai `heal-eligible`. Non blocca il lint.
**Audience**: maintainer che aggiungono, rinominano o rimuovono agenti, skill o comandi.

> Nota adapter Cursor: la stessa logica si applica al layout Cursor — gli agenti vivono in
> `.cursor/rules/*.mdc`, le skill in `.cursor/skills/<name>/SKILL.md`, i comandi in
> `.cursor/commands/*`. La whitelist tool e la nomenclatura sotto restano il riferimento
> canonico del meta-framework Claude Code.

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
  comando potrebbe essere in sviluppo / in-progress).
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

### Numerazione

«4ai» segue «4ah» (Branch Awareness config coherence, EP-034). Pattern allineato a Check 4ah
(WARNING-only, always-on light, read-only). Non collide con alcun check esistente.

### Cross-link

4ai → `.claude/agents/` + `.claude/skills/` + `.claude/commands/` + `dispatch-policy.md` +
PATTERN §2 (thin-agents-fat-skills).

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

### Numerazione

«4aj» segue «4ai» nella serie alfanumerica. INFO-only (più lieve di WARNING — primo uso
del livello INFO come livello autonomo, analogo a Check 4ag §INFO > 180 gg).

### Cross-link

4aj → `factory.config.yaml.models` (Central Model Registry v2.27) + PATTERN §29.2 +
`.claude/agents/` (scope) + `dispatch-policy.md §8` (tier slug table).
