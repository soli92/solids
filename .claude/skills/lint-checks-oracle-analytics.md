---
skill: lint-checks-oracle-analytics
part_of: lint-checks (modular)
family: oracle-analytics
parent: lint-checks
description: "Check lint su Functional Oracle (acceptance-spec) e Analytics (measurement, estimation) — check-family oracle-analytics"
---

# Lint Checks — Oracle & Analytics

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 4z (acceptance-spec schema validation), Check 4q (TSK done senza event log/effort), Check 4r (TSK senza stima di riferimento kickoff)

Tutti check opt-in via gate config. Check ordinati per numero.

---

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

**Distinta da Check 4r** (EP-010 US-042): 4q **misura il done** (gate `required_on_done`,
trigger su `status: done` senza `cost_event_log`/`effort_hours`); 4r **enforce la stima al
kickoff** (gate `required_on_kickoff`, trigger su TSK `todo|in_progress` senza `estimate_id`). Asse
temporale opposto: 4q guarda indietro (consuntivo), 4r guarda avanti (preventivo).

---

### 4r — TSK in nuovo progetto senza stima di riferimento (Task Analytics Estimation, EP-010 US-042, ADR-027 §H)

**Pattern allineato a Check 4m/4n/4o/4q (R.P3 opt-in totale)**: WARNING-only, opt-in via flag
config, nessun ERROR meccanico. Check 4r eredita la stessa shape per coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione ADR-027 §H). La
produzione di una stima preliminare (`/estimate`, skill `project-estimation` US-040) è scelta
del derivatore di factory enterprise, non automatizzabile: il lint informa, non blocca mai
`/lint` né il Develop. Mai `heal-eligible` (giudizio semantico).

**Distinta da Check 4q** (EP-009 US-039): 4q **misura il done** (gate `required_on_done`,
trigger su `status: done` senza `cost_event_log`/`effort_hours`); 4r **enforce la stima al
kickoff** (gate `required_on_kickoff`, trigger su TSK `todo|in_progress` di un nuovo
progetto/EP senza `estimate_id`). Asse temporale opposto: 4q guarda indietro (consuntivo),
4r guarda avanti (preventivo). Gate, trigger e messaggio sono indipendenti.

**Trigger (AND — tutte le condizioni devono essere vere)**:

```
factory.config.yaml.analytics.estimation.required_on_kickoff == true
AND TSK.layer in ['fe', 'be', 'db', 'qa']
AND TSK.status in ['todo', 'in_progress']
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

---

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

**Cross-link**: 4z → ADR-065 §E (fail-loud spec assente) / §C (whitelist kind primitivi) / §B (schema
struttura spec) + schema `.claude/schemas/acceptance-spec.schema.yaml` + US-069 (origine) + EP-018
(Functional Oracle capability) + ADR-066 (vocabolario scenario) + ADR-064 (app-lifecycle serve, engine).
