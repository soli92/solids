---
name: release-validation-gate
description: Release validation gate «Nessun tag senza ≥N RUN-REPORT validi». 5 step deterministici (Discover → Schema → Threshold+cross-EP → Aggregate → CHANGELOG) + bypass con SLA. Mai auto-tag. Opt-in via release_governance.battle_test_gate.enabled. Invocata da /release o direttamente in chat.
---
# Skill: release-validation-gate

> Parte di EP-012 (Battle-test forcing function). Invocata da `.claude/commands/release.md`.
> Implementa il gate procedurale «nessun tag senza ≥N RUN-REPORT validi» (PATTERN §22 candidata, ADR-033).
> 5 step deterministici. Mai auto-tag (R.P1). Opt-in via `release_governance.battle_test_gate.enabled` (R.P3).
> Caricabile sia dal comando sia direttamente in chat (es. il maintainer chiede "valida la release v2.19").
> [^src: design_&_architecture/decisions/ADR-033.md §D]
> [^src: design_&_architecture/decisions/ADR-032.md §B §C §D] [^src: design_&_architecture/decisions/ADR-037.md §D]
> [^src: validation/CRITERIA.md §1 §2 §3 §5] [^src: design_&_architecture/decisions/ADR-041.md §C]
> Pattern parallelo: [`code-review-protocol`](./code-review-protocol.md) (5 fasi) + [`caveman-protocol`](./caveman-protocol.md) (5 fasi).
> Concetti: [[fail-closed]] + [[framework-critical-analysis-premortem]].

Riferimenti normativi: ADR-033 §D (5 step) §E (bypass+SLA) §F (`bypass_allowed`) §G (audit log) §H (cross-EP),
ADR-032 §B (5 soglie pre-check) §C (schema RUN-REPORT: 13 campi frontmatter + 9 sezioni) §D (review umana) §F (immutabilità),
ADR-034 §A (schema `## Validation evidence`) §C (schema bypass), ADR-035 (gate da v2.19, non retroattivo),
ADR-036 (release governance), ADR-037 §A §B §C §D §E (transitional bootstrap rule v2.19.0),
ADR-040 §F + ADR-041 §C (cross-EP-013 gate), `validation/CRITERIA.md` (soglie versionate, criteri review §2,
soft gate indipendenza §3, soft cross-EP §5).

## Costanti

```
DEFAULT_MIN_RUN_REPORTS   = 3       # release_governance.battle_test_gate.min_run_reports (ADR-033 §D Step 3)
DEFAULT_BYPASS_SLA        = 1       # release_governance.battle_test_gate.bypass_sla_releases (ADR-033 §E)
FRONTMATTER_FIELDS_REQ    = 13      # 9 base + 4 extension v2.19 (ADR-032 §C)
MARKDOWN_SECTIONS_REQ     = 9       # §1..§9 ordinate (ADR-032 §C)
RUN_REPORTS_GLOB          = "validation/runs/*/RUN-REPORT.md"
GATE_DIR                  = "validation/release-gates/<version>/"
```

## Boot check

```
1. Read factory.config.yaml.release_governance.battle_test_gate.

   SE enabled == false (default factory derivate):
     OUTPUT: "Gate disabilitato (release_governance.battle_test_gate.enabled: false). R.P3 opt-in."
     EXIT (no-op — R.P3 invariata, backward compat v2.18, ADR-033 §J).

2. SE bypass_allowed == false (default true) AND flag --bypass-validation-gate presente:
     FAIL-LOUD (ADR-033 §F):
       "release_governance.battle_test_gate.bypass_allowed: false in factory.config.yaml.
        Bypass non consentito. Aggiungere i ≥<min_run_reports> RUN-REPORT richiesti
        o cambiare config."
     EXIT.

3. SE flag --bypass-validation-gate presente (e bypass_allowed != false):
     → vai a sezione «Bypass» (Step 1-5 saltati).

4. SLA check a boot (ADR-033 §E vincolo SLA, prima di procedere):
     Cerca validation/release-gates/*/BYPASS.md con deferred_validation: true
     e nessun closure marker, per versioni PRECEDENTI a <version>.
     SE trovato ≥1:
       FAIL-LOUD: "Bypass aperto da release v<prev>: deve essere colmato entro v<version>.
                   Esegui i ≥<min_run_reports> RUN-REPORT mancanti o estendi l'SLA con un nuovo ADR."
       EXIT.

5. Altrimenti → procedi a Step 1.
```

> Pattern parallelo `kanban_publish.mode: push-only` (gate hard del publisher) per `bypass_allowed: false`.

## Step 1 — Discover RUN-REPORTs

```
Input: <version> (es. v2.19.0)
Action: Glob validation/runs/*/RUN-REPORT.md
Filter:
  - frontmatter.framework_version == <version>
    SPECIALE v2.19.0 (ADR-037 §E): accetta come prefix le release candidate →
    frontmatter.framework_version matches "v2.19.0(-rc\.\d+)?"
    (es. v2.19.0-rc.1, v2.19.0-rc.2 sono raccolti per il gate v2.19.0).
    Da v2.20+ il filter è strict (no prefix rc.* di versioni diverse).
  - frontmatter.framework_version NOT in [REFERENCE-ONLY, DEFERRED-RECONSTRUCTION]
    (esclude i reference ex-post, es. fsc-trasf-demo-2026-05-19 = v2.6 [REFERENCE-ONLY], ADR-032 §G).
Output: lista candidati {slug, path, frontmatter estratto}.
```

## Step 2 — Schema validation

Per ogni RUN-REPORT candidato (schema canonico `validation/runs/TEMPLATE/RUN-REPORT.md`, ADR-032 §C):

```
- Verifica 13 campi frontmatter (9 base + 4 extension v2.19, ADR-032 §C):
    base: id, slug, started_at, completed_at, framework_version, factory_path,
          signed_by, pre_check_status, review_status
    extension v2.19: analytics_events_count (ADR-041 §C),
          same_author_as_framework, same_machine_as_dev, same_factory_as_previous_runs (ADR-032 §D)
    (independence_justification è condizionale §3 → verificato sotto, non conta nei 13).
- Verifica 9 sezioni Markdown ordinate (§1 Pre-check meccanico, §2 Capability attivate,
  §3 Backlog esercitato, §4 Cosa ha funzionato, §5 Cosa si è rotto, §6 Capability NON
  esercitate, §7 Lezioni, §8 Indipendenza del campione, §9 Firma).
- Verifica §5 «Cosa si è rotto» con ≥1 entry (sezione NON vuota — ADR-032 §C; CRITERIA.md
  §2 criterio 2: run senza rupture sono sospetti per campione bias).
- Verifica pre_check_status == pass (le 5 soglie meccaniche §1, vedi sotto «Pre-check vs CRITERIA.md»).
- Verifica review_status == pass (firma maintainer §2 + soft gate §3, vedi sotto).
Fail-loud sul PRIMO malformato (ADR-032 §C; ordine causale §D rationale 3):
  verdict immediato `fail`, "RUN-REPORT <slug>: <problema specifico>. Vedi ADR-032 §C."
Output: lista RUN-REPORT VALIDI (passano schema AND pre-check AND review).
```

### Pre-check meccanico vs `validation/CRITERIA.md` §1 (deterministico)

Il `pre_check_status: pass` del RUN-REPORT attesta che tutte e 5 le soglie quantitative
di CRITERIA.md §1 (versionate, ogni modifica richiede ADR — ADR-032 §H) sono `pass`. Una
sola soglia `fail` → `pre_check_status: fail` e la review umana §2 non parte (AND sequenziale,
CRITERIA.md §Principio):

| # | Soglia (CRITERIA.md §1) | Valore default |
|---|---|---|
| 1 | `backlog_size_min` | 20 TSK reali |
| 2 | `layers_covered_min` | 4 su 5 (L1 → almeno L4) |
| 3 | `capabilities_active_min` | 3 capability opt-in |
| 4 | `duration_min` | 1 sprint (≥5d walltime, ≥3 commit) |
| 5 | `wiki_log_markers_min` | ≥1 marker reale in `wiki/log.md` |

La skill NON ricalcola le soglie (sono attestate dal RUN-REPORT, sezione §1 + frontmatter
`pre_check_status`); verifica che il marker sia `pass`. Pattern: `/lint` (meccanico) +
review PR (umano) — mai solo l'uno (solo-meccanico = gameable; solo-umano = bus-factor-1).

### Review umana §2 + soft gate indipendenza §3 (CRITERIA.md)

```
- review_status == pass attesta i 3 criteri qualitativi CRITERIA.md §2 (firma maintainer, §9 RUN-REPORT):
    (1) marker reali presenti; (2) ≥1 finding non previsto; (3) ≥1 capability rotta/iterata.
- SOFT GATE indipendenza (CRITERIA.md §3, decisione maintainer 2026-06-08):
    SE same_author_as_framework AND same_machine_as_dev AND same_factory_as_previous_runs
       (TUTTI e 3 == true):
      REQUIRE frontmatter.independence_justification NON vuoto.
      SE vuoto/null → il RUN-REPORT NON è VALIDO:
        fail-loud "RUN-REPORT <slug>: 3 flag di indipendenza tutti true ma
                   independence_justification vuoto. review_status:pass bloccato finché
                   il maintainer non argomenta la significatività. Vedi CRITERIA.md §3."
    Il pre-check meccanico §1 resta pass (i flag non bloccano §1); è il verdict umano §2 a
    non poter passare senza la giustificazione (soft gate, anti-self-validation E2).
```

## Step 3 — Threshold check + Cross-EP-013

```
Input: lista RUN-REPORT VALIDI (output Step 2).
Soglia: factory.config.yaml.release_governance.battle_test_gate.min_run_reports (default 3).

IF count(VALIDI) < soglia:
  verdict = "fail"
  message = "trovati <N> RUN-REPORT validi, soglia ≥<soglia>. Run mancanti: ..."
ELSE:
  verdict_candidate = "pass" (procede a Step 4).

Cross-EP-013 (ADR-040 §F → ADR-041 §C) — CONDIZIONALE a dogfooding (ADR-033 §H):
  SE factory.config.yaml.analytics.dogfooding.enabled == true:
    PER OGNI RUN-REPORT VALIDO:
      IF frontmatter.analytics_events_count == 0:
        verdict = "fail"
        message = "RUN-REPORT <slug>: analytics_events_count=0 (run senza ground truth).
                   Vedi ADR-041 §C cross-EP gate."
  SE analytics.dogfooding.enabled == false:
    criterio cross-EP SKIPPED (R.P3 — configurazione legittima: gate empirico senza analytics).
```

> **Cross-EP gate `analytics_events_count > 0` è condizionale a dogfooding** (ADR-041 §C):
> il criterio è esercitato **solo se** `analytics.dogfooding.enabled: true` (i.e. EP-013 attivo).
> In factory con `battle_test_gate.enabled: true` ma `dogfooding.enabled: false` (configurazione
> legittima: gate empirico senza analytics) il criterio è skipped, coerente con R.P3 (opt-in
> indipendente di ogni capability — ADR-033 §H §9). Da rivalutare verso hard quando
> l'instrumentation è matura (CRITERIA.md §5; modifica via ADR).
>
> Nota sui due punti d'azione del criterio: nel RUN-REPORT (pre-check, CRITERIA.md §5) un
> `analytics_events_count: 0` è **WARNING** soft (il run passa). Nel release gate (qui, ADR-041 §C)
> è **fail-loud** sull'aggregato quando dogfooding è on. La skill applica la regola del gate.

## Step 4 — Aggregate report

```
Action: produce GATE_DIR/GATE-REPORT.md (validation/release-gates/<version>/GATE-REPORT.md).
Schema (frontmatter + 4 sezioni, ADR-033 §D):

  ---
  id: GATE-<version>
  version: <version>
  invoked_at: <ISO-8601 UTC>
  verdict: pass | fail | bypass
  consumed_run_reports:
    - slug: <run-slug-1>
      verdict: pass
      analytics_events_count: <N>
    - slug: <run-slug-2>
      ...
  ---

  ## §1 Verdict aggregato
  <pass | fail | bypass> — rationale in 2-3 righe.

  ## §2 Pre-check meccanico aggregato
  Tabella: ogni run + le 5 soglie CRITERIA.md §1 + valori reali (riassunto delle §1 dei singoli RUN-REPORT).

  ## §3 Findings consolidati (cross-run)
  Lista dei §5 «Cosa si è rotto» di tutti i run, deduplicato + classificato (capability impattata, severity).

  ## §4 Capability non esercitate aggregate
  Unione delle §6 dei run, evidenziando capability non esercitate in NESSUNO dei N run (le più sospette).
```

## Step 5 — CHANGELOG section validation

```
Input: CHANGELOG.md.
Action:
  - Trova sezione release `## v<version>` (regex case-insensitive, es. `## v2.19` o `## v2.19.0`).
  - Dentro il blocco release, cerca `## Validation evidence (v<version>)`
    (regex: ^## Validation evidence \(v<version>\) , ADR-034 §A).
  - Verifica schema ADR-034 §A: sub-sezioni
      ### Run consumati        (≥<min_run_reports>, default ≥3, entry con link a RUN-REPORT)
      ### Findings consolidati
      ### Capability non esercitate
      ### Riferimenti          (link a GATE-REPORT.md)
  - Status marker check (ADR-034 §A status markers + ADR-037 §D):
      SE verdict == bypass AND marker [gate-bypassed] mancante → fail-loud (ADR-034 §C).
      SE version == v2.19.0 (transitional bootstrap rule, ADR-037 §A §C §D):
        REQUIRE marker [transitional-bootstrap]
          → fail-loud "ADR-037 §A richiede marker [transitional-bootstrap] su v2.19.0".
        REQUIRE sub-section `### Transitional bootstrap rule`
          → fail-loud "ADR-037 §C richiede sezione 'Transitional bootstrap rule' nello schema v2.19.0".
      SE version != v2.19.0 AND marker == [transitional-bootstrap]:
        → fail-loud "ADR-037 §B marker [transitional-bootstrap] ammesso SOLO per v2.19.0".
Fail-loud (sezione assente): "CHANGELOG.md: sezione `## Validation evidence (v<version>)`
           mancante. Vedi ADR-034 §A."
Output: verdict finale (pass | fail) + GATE-REPORT.md (aggiornato con verdict finale) + audit log.
```

> Vincoli versionati nel codice della skill, non interpretabili dal maintainer (R.P3-coerente, ADR-037 §D).

## Post-Step 5 — Audit log

```
Append (append-only) a GATE_DIR/<timestamp>-<verdict>.log
(validation/release-gates/<version>/<timestamp>-<verdict>.log), 1 entry per invocazione (anche --dry-run):

  <ISO-8601> verdict=<v> invoked-by=<actor> bypass=<true|false> dry-run=<true|false> runs-consumed=<N>

Esempio: 2026-06-15T14:32:00Z verdict=pass invoked-by=@soli92 bypass=false dry-run=false runs-consumed=3
```

**Formato di `<timestamp>` nel NOME del file — vincolo, non preferenza.**

Usa la forma ISO-8601 **basic** (senza separatori nell'ora): `YYYY-MM-DDTHHMMSSZ`.

```
corretto:  2026-06-15T143200Z-pass.log
SBAGLIATO: 2026-06-15T14:32:00Z-pass.log
```

I due punti sono un carattere **vietato nei nomi file su Windows** (e' il separatore
di unita': `C:`). Un file che li contiene rende impossibile il `git pull` e il
`git clone` del repo su Windows, con l'errore `error: invalid path ...` +
`fatal: unable to checkout working tree` — e non e' riparabile lato client, perche'
il nome arriva dal repo. Il timestamp **dentro** al file resta invece in forma
estesa (`2026-06-15T14:32:00Z`): il vincolo riguarda solo il nome.

Stesso vincolo per ogni altro artefatto generato: mai `: < > " | ? *` nei nomi di
file o cartella, mai spazio o punto finale, mai nomi riservati DOS (`CON`, `PRN`,
`AUX`, `NUL`, `COM1`-`COM9`, `LPT1`-`LPT9`). Verifica con
`python3 tools/lint/check-portable-paths.py`.

> Side-channel dedicato per-version (ADR-033 §G), pattern parallelo a `memory/episodic/`,
> `code_quality/reports/`, `analytics/events/`. Permette audit storico (quante release hanno
> bypassato, quante passate al primo apply, quanti dry-run prima del primo apply).

## Verdict finale + mai auto-tag (R.P1)

```
verdict ∈ {pass, fail, bypass}.
- pass:   tutti gli step superati. SE invocata con --apply → PROPONI all'utente i comandi git
          per il tag (output strutturato), MA NON eseguire `git tag` (R.P1 — output mai
          auto-applicato; il maintainer esegue il tag a mano dopo aver letto il GATE-REPORT).
          SE --dry-run (default safe) → mostra GATE-REPORT, NON proporre azioni.
- fail:   STOP con messaggio strutturato (lo step che ha fallito + rimedio). Nessun comando git proposto.
- bypass: vedi sezione «Bypass».
```

> Mai auto-tag (ADR-033 §A §B §D rationale 4): il framework propone, l'umano dispone.
> Coerente con R.P1 (output mai auto-applicato) + R.P3 (opt-in totale, umano nel loop su azioni outward).
> `--dry-run` è il default safe (ADR-033 §B); solo `--apply` dichiara intenti.

## Bypass (`--bypass-validation-gate --reason="<msg>"`)

Esplicito, tracciato, mai silenzioso. Pattern parallelo a `a11y_skip`/`ux_skip`/`temporal_handoff_skip`
(ADR-016 §F / ADR-020 §G / ADR-031 §F). Prerequisito boot: `bypass_allowed != false` (altrimenti
fail-loud, vedi Boot check).

```
SE --bypass-validation-gate AND --reason="<msg>" presenti (e bypass_allowed != false):
  Step 1-5 vengono saltati.
  Action:
    - Produce GATE_DIR/BYPASS.md con frontmatter (schema ADR-033 §E):
        ---
        version: <version>
        bypassed_at: <ISO-8601>
        bypassed_by: <actor>
        reason: <msg>
        deferred_validation: true
        sla_releases: <release_governance.battle_test_gate.bypass_sla_releases, default 1>
        ---
        ## Rationale del bypass
        <msg>
        ## SLA di colmamento
        Entro la release v<next>: il maintainer DEVE eseguire i ≥<min_run_reports> RUN-REPORT
        mancanti e produrre validation/release-gates/v<next>/GATE-REPORT.md con verdict: pass
        + sezione "## §5 SLA bypass v<version> colmata" che cita questo BYPASS.md.
    - Append marker [gate-bypassed] al CHANGELOG.md sezione `## Validation evidence (v<version>)`
      (schema bypass ADR-034 §C: reason + link a BYPASS.md + SLA).
    - Produce GATE_DIR/GATE-REPORT.md con verdict: bypass, §1 = "BYPASSED: <msg>", §2..§4 = "N/A (bypassed)".
    - Audit log: verdict=bypass bypass=true.
  Verdict = "bypass" (NON "pass").
```

> SLA forzato (ADR-033 §E): il bypass è un'eccezione documentata, non uno slittamento silente.
> Pattern coerente con [[fail-closed]]. Il vincolo SLA è verificato a boot della release
> successiva (vedi Boot check punto 4).

## Backward compat (ADR-035 + ADR-033 §J)

- `enabled: false` (default factory derivate): boot check no-op, zero file letti/scritti,
  comportamento identico a v2.18. Il comando `/release` non è scaffoldato in factory derivate
  (meta-comando, ADR-033 §C).
- `enabled: true` (default repo framework da v2.19): skill caricabile, gate attivo.
- Gate valido da v2.19 in poi, non retroattivo (CRITERIA.md §4; ADR-035). Le release v2.14–v2.18
  sono "validate on specification, not battle-tested" — nessun RUN-REPORT retroattivo richiesto.
