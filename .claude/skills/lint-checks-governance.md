---
skill: lint-checks-governance
part_of: lint-checks (modular)
family: governance
parent: lint-checks
description: "Check lint su governance, release gate, bypass SLA, versioning — check-family governance"
---

# Lint Checks — Governance

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 4v (Complexity Budget N:1), Validation Schema Checks header, Check 4w (RUN-REPORT schema), Check 4x (CHANGELOG validation evidence), Check 4al (CHANGELOG↔GATE-REPORT), Check 4am (versioni divergenti), Check 4ar (SUNSET scadute)

Check ordinati per severità: ERROR → WARNING.

---

### 4v — Complexity Budget regola N:1 violata pre-release (Complexity Budget & Deprecations, EP-016 US-061, ADR-056 §D)

**Severità**: WARNING su factory derivate; ERROR sul meta-framework (ADR-056 §A + PATTERN §23.5.1).
**Gate**: `factory.config.yaml.complexity_budget.required_on_release` (default `false`, R.P3 opt-in). Se assente o `false` → 4v no-op totale.
Su release **patch** (`x.y.Z` con Z>0) → 4v non si applica (cadenza pre-release minor/major, ADR-056 §F).
**Finding** (sezione `## WARNING (igiene)` del report): `[WARNING][complexity-budget][4v]`

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (trigger AND, esenzione, messaggi, scenari di verifica, cross-link) si trova in:
> `.claude/skills/references/lint-checks-governance/check-4v-complexity-budget.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il check.
> Se il file manca → STOP e segnala a wiki-lint.

---

## Validation Schema Checks (opt-in v2.19+)

**Gate master**: `factory.config.yaml.release_governance.battle_test_gate.enabled: true` (R.P3 opt-in).
A gate `false` (default factory derivate), questa intera sezione è skip — **0 check aggiuntivi
vs v2.18**, nessun ERROR/WARNING introdotto, comportamento identico (backward compat ADR-032
§Backward compat). Eseguito **solo** se il gate master è abilitato.

### Check 4w — RUN-REPORT schema validation (ERROR su schema malformato, EP-012 US-049, ADR-032 §C §J)

**Severità**: ERROR — non WARNING (contratto binario sullo schema RUN-REPORT, ADR-032 §J).
**Gate**: `battle_test_gate.enabled` (opt-in totale R.P3). Se `false` → 4w no-op totale.
**Heal-eligible**: no (la compilazione di una sezione mancante richiede giudizio semantico).
**Finding** (sezione `## ERROR non meccanici (manuali)` del report): `[ERROR][run-report-frontmatter-invalid][4w]` / `[ERROR][run-report-section-missing][4w]` / `[ERROR][run-report-verdict-incoherent][4w]`

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (le 9 sezioni obbligatorie, sotto-check 4w.a/b/c, esenzione/file esclusi, pattern rilevamento regex, messaggi, output format, scenari, cross-link) si trova in:
> `.claude/skills/references/lint-checks-governance/check-4w-run-report-schema.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il check.
> Se il file manca → STOP e segnala a wiki-lint.

### Check 4x — CHANGELOG Validation evidence mancante (WARNING, EP-012 US-050, ADR-033 §I + ADR-034 §A)

**Severità**: WARNING — non ERROR (coerente con R.P3 opt-in). L'enforcement primario è in `/release` (ADR-033 §D).
**Gate**: `battle_test_gate.enabled` (opt-in totale R.P3). Se `false` → 4x no-op totale.
**Heal-eligible**: no (richiede giudizio semantico sull'evidenza del run).
**Finding** (sezione `## WARNING (igiene)` del report): `[WARNING][changelog-validation-evidence-missing][4x]`

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (trigger AND, gate, esenzione, messaggio verbatim, output format, scenari, cross-link) si trova in:
> `.claude/skills/references/lint-checks-governance/check-4x-changelog-validation.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il check.
> Se il file manca → STOP e segnala a wiki-lint.

---

## Check 4al — CHANGELOG ↔ GATE-REPORT coerenza (ERROR se GATE mancante, WARNING se bypass — EP-049 US-179)

**Trigger**: sempre attivo — nessun flag richiesto. Invariante di governance non configurabile.
**Severità**: ERROR (GATE-REPORT mancante) / WARNING (GATE-REPORT con `verdict: bypass`).
**Esenzione**: versioni v2.18 e precedenti (il GATE-REPORT formale non esisteva).
**Heal-eligible**: no (la creazione del GATE-REPORT richiede giudizio semantico).
**Graceful degradation**: `CHANGELOG.md` assente → skip silenzioso, 0 ERROR/WARNING.
**Finding**: `[ERROR][changelog-gate-report-missing][4al]` / `[WARNING][changelog-gate-report-bypass][4al]`

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (algoritmo completo, invarianti, pseudocodice rilevamento, output format, 10 scenari di verifica, cross-link) si trova in:
> `.claude/skills/references/lint-checks-governance/check-4al-changelog-gate-coherence.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il check.
> Se il file manca → STOP e segnala a wiki-lint.

---

## Check 4am — Versioni divergenti da factory.config.yaml (WARNING, always-on — EP-052 US-187)

**Trigger**: sempre attivo — nessun flag richiesto. Fonte di verità: `factory.config.yaml.pattern_version`.
**Esecuzione**: `python3 tools/lint/check-version-coherence.py [--json]` (stdlib only, exit 0 sempre).
**Severità**: WARNING — non ERROR. Non `heal-eligible`.
**Esenzioni**: `CHANGELOG.md` (contiene versioni storiche per natura — non viene scansionato).
**Graceful degradation**: se `pattern_version` assente → skip silenzioso, 0 WARNING.
**Finding** (sezione `## WARNING (igiene)` del report): `[WARNING][version-divergent][4am]` / `[WARNING][version-site-missing][4am]` / `[WARNING][version-stale-candidate][4am]` (EP-080: un sito presente chiama «candidate» la versione corrente; `sprint.md` esente, le intestazioni degli sprint chiusi sono storia)

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (algoritmo completo, logica profilo framework/derived, lista siti obbligatori e opzionali, invariante «sito dichiarato che non matcha = finding», invarianti generali, output format, 8 scenari di verifica, cross-link) si trova in:
> `.claude/skills/references/lint-checks-governance/check-4am-version-divergent.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il check.
> Se il file manca → STOP e segnala a wiki-lint.

---

## Check 4ar — Annotazioni SUNSET scadute (ERROR, always-on — TR-9b4e7c02)

**Severità**: ERROR — non WARNING. Non `heal-eligible`.
**Esecuzione**: `python3 tools/lint/check-expired-sunset.py .`
**Finding** (sezione `## ERROR (governance, mai heal-eligible)` del report): `[ERROR][sunset-expired][4ar]`

Algoritmo completo, invarianti, comandi di esecuzione e output format:

> **[TRIGGER VINCOLANTE]** Il dettaglio completo (algoritmo, invarianti «citazione ≠ annotazione» e «artefatto pianificazione ≠ annotazione», tre uscite legittime, output format, provenienza TR-9b4e7c02) si trova in:
> `.claude/skills/references/lint-checks-governance/check-4ar.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il check.
> Se il file manca → STOP e segnala a wiki-lint.
