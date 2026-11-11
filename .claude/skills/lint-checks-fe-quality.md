---
skill: lint-checks-fe-quality
part_of: lint-checks (modular)
family: fe-quality
parent: lint-checks
description: "Check lint su qualità TSK FE — state matrix, a11y, UX/UI, no-auto-eval, evidence — check-family fe-quality"
---

# Lint Checks — FE Quality

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 4n (granularità DoD State Matrix), Check 4o (scan a11y mancante), Check 4p (review UX/UI mancante), Check 4ac (no-auto-eval UX/UI), Check 4y (ux_ui evidence-provenance)

Tutti check WARNING-only, opt-in via gate config. Check ordinati per numero.

---

### 4n — Granularità TSK FE (State Matrix DoD, EP-006 US-022, ADR-011)

**Pattern allineato a Check 4m (EP-002 US-007)**: WARNING-only, opt-in via flag config,
soglie configurabili, nessun ERROR meccanico. Check 4n eredita la stessa shape per
coerenza framework.

**Severità: WARNING-only — mai ERROR** (R.P3 opt-in totale + decisione TPM). La
scomposizione di un task è decisione del TPM/Arch, non automatizzabile: il lint informa,
non blocca mai `/lint` né il Develop. Mai `heal-eligible` (giudizio semantico).

**Trigger (AND — tutte e 5 le condizioni devono essere vere; più conservativo del prompt
OR in `scrivi-task`)**:

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
patologico «grosso E complesso UI». Il prompt `scrivi-task` resta in forma OR (preventivo);
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

---

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

---

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

---

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

**Cross-link**: 4ac → ADR-020 §H (vincolo no-auto-eval) / §G (Check 4q candidato) / §E (schema
report uxui-design e uxui-review) + US-086 (campo `generated_by`) + US-088 (gate config
`ux_ui.lint_check_4q` in `factory.config.yaml`) + EP-024 (questa epica).

---

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

**Cross-link**: 4y → ADR-063 §B (guard evidence-provenance, questo check) / §A (fail-loud Step 1, skill) /
§C (tool Read/Grep agente) + skill `ux-ui-review-protocol.md` Step 5 (guard runtime, TSK-134) + Check 4p
(companion forma) + US-067 (origine EP-008).
