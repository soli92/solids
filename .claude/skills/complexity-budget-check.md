# Skill: Complexity Budget Check

> Adapter Cursor della skill `complexity-budget-check` definita in PATTERN.md.

Metadata skill (originale):
```yaml
id: complexity-budget-check
version: v2.19
capability: EP-016
pattern_ref: PATTERN §23
adr: [ADR-052, ADR-053, ADR-056]
```

> Misura il complexity budget di `PATTERN.md` per una versione target: conta le sezioni
> `##` top-level, calcola il delta vs la versione precedente, applica la **regola N:1**
> (PATTERN §23.1, default N=3), emette un report e logga la telemetria EP-013.
> 5 step deterministici. Invocata sia da **Lint Check 4v** ([lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md), gated
> `complexity_budget.required_on_release: true`) sia dal meta-comando `/complexity-budget check`.

**Verdict semantico — mai enforcement duro.** L'esito è `pass` / `warn` / `fail` / `skipped`;
nessuno di questi blocca `/lint`, il Develop o il release (governance documentale, R.P3 opt-in
totale, ADR-056 §A). `fail` è solo un livello di severità informativa più alto di `warn`.

## Step 1 — Read PATTERN

Leggi `PATTERN.md` e conta le sezioni top-level `##`:

- **Include**: tutti i `## §X — <titolo>` e `## <titolo>` senza namespace.
- **Esclude (whitelist, ADR-052 §C)**: TOC/index, esempi inline, `## Storia roadmap`,
  `## Fonti`, `## Note`, e `## §23` stessa (self-referential per design, ADR-052 §C §F).
- **Output**: `sections_current = int`, `sections_list = [slug, ...]`.

## Step 2 — Read CHANGELOG

Leggi `CHANGELOG.md` e identifica:

- `version_target`: ultima versione nel CHANGELOG (o versione passata via `--version`).
- `version_previous`: versione precedente.
- `release_kind`: parsing SemVer dell'heading `## vX.Y[.Z]?` (ADR-056 §F) →
  `major` (X change) | `minor` (Y change, Z=0) | `patch` (Z>0). **Su `patch` lo skill ritorna
  early con verdict `skipped` (reason `"patch release — cadenza pre-release minor/major"`)**:
  nessun check N:1 sulle patch (ADR-056 §F).
- `sections_added_changelog`: sezioni aggiunte nell'entry `version_target`
  (tag `[ADD §X]` / `## Added`).
- `sections_removed_changelog`: sezioni rimosse/deprecate nell'entry `version_target`
  (tag `[REMOVE §X]` / `[DEPRECATE §X]` / `## Removed`).
- `archived_count`: numero di sezioni archiviate (spostate in `PATTERN-historical.md`) per
  `version_target`.
- `skip_marker`: presenza di `[skip-complexity-budget --reason="<motivo>"]` nell'entry
  (ADR-056 §E). Se presente → cattura `skip_reason`.

## Step 3 — Apply rule N:1

Regola N:1 (PATTERN §23.1, ADR-052 §D + ADR-056 §B). `N` default `3`, override da
`factory.config.yaml.complexity_budget.rule_n`.

```python
def apply_rule_n_1(count_current, count_previous, archived_count, N=3,
                   skip_marker=False, skip_reason=None):
    if skip_marker:
        return {"verdict": "skipped", "ratio": None,
                "skipped": True, "skip_reason": skip_reason}

    delta_added = count_current - (count_previous - archived_count)  # net additions
    delta_removed = archived_count

    if delta_removed == 0 and delta_added > 0:
        if delta_added > N:
            return {"verdict": "fail", "ratio": "inf",
                    "reason": "additions without removals"}
        else:
            return {"verdict": "warn", "ratio": "inf",
                    "reason": "carry-over deficit to next release"}

    if delta_added <= 0 and delta_removed == 0:
        return {"verdict": "pass", "ratio": 0.0, "reason": "no change"}

    ratio = delta_added / max(delta_removed, 1)

    if ratio <= N:
        return {"verdict": "pass", "ratio": ratio}
    elif ratio <= N + 1:
        return {"verdict": "warn", "ratio": ratio, "reason": "1 above threshold"}
    else:
        return {"verdict": "fail", "ratio": ratio, "reason": "above threshold + 1"}
```

Nota: `warn` e `fail` differiscono solo per severità del messaggio; entrambi WARNING-only in
`/lint` (Check 4v non emette mai ERROR, ADR-056 §A §D).

## Step 4 — Emit report

Genera `complexity/budget-report-<version_target>.md` (side-channel, pattern parallelo a
`analytics/reports/`, ADR-056 §I). Scritto **anche a gate disabilitato** (per audit). Schema
verbatim (ADR-056 §I):

```markdown
---
type: complexity-budget-report
version: vX.Y.Z
generated_at: <ISO-8601>
generated_by: complexity-budget-check skill
verdict: pass | warn | fail | skipped
ratio: <float|inf|null>
delta_added: <int>
delta_removed: <int>
N: <int>
skipped: <bool>
skip_reason: <string|null>
---

# Complexity Budget Report — vX.Y.Z

PATTERN.md sections: <sections_current>

## Verdict: <pass|warn|fail|skipped>

Ratio: <delta_added>/<delta_removed> = <ratio> (vs limit N=<N>)

## Sezioni aggiunte (<delta_added>)

- §<numero> <titolo>
- ...

## Sezioni rimosse/archiviate (<delta_removed>)

- §<numero> <titolo> → PATTERN-historical.md
- ...

## Recommendation

<if warn|fail>
Ratio violato. Considerare deprecazioni in PATTERN §23.2 `## Sezione Deprecate`
(`/complexity-budget deprecate §X --reason="<r>"`) prima del release tag, oppure aggiungere
il marker `[skip-complexity-budget --reason="<motivo>"]` nel CHANGELOG.
</if>
<if pass|skipped>
Nessuna azione richiesta.
</if>

## Nota storica
Sezioni archiviate consultabili in `PATTERN-historical.md` (`/pattern-view historical`).
```

## Step 5 — Log telemetria EP-013

Emette un evento `state: complexity_budget_check` (nuovo enum coperto da ADR-042 P0
schema-permissive, ADR-056 §J). Gated dietro `measurement.enabled` come gli altri enum v2.19.

```yaml
event:
  state: complexity_budget_check
  task_id: <version|null>
  actor_id: complexity-budget-check
  actor_type: agent
  ts: <ISO-8601>
  complexity_budget:
    version: vX.Y.Z
    verdict: pass | warn | fail | skipped
    ratio: <float|inf|null>
    delta_added: <int>
    delta_removed: <int>
    N: <int>
  hop_id: <uuid>
```

## Cross-link

- **PATTERN §23** (Complexity Budget & Deprecations) — §23.1 regola N:1, §23.2 Sezione Deprecate,
  §23.3 Governance.
- **PATTERN §3** entry «Complexity Budget & Deprecations» (op. canonica, ADR-056 §G).
- **ADR-052** (regola N:1 + whitelist esclusioni), **ADR-053** (`/pattern-view`),
  **ADR-056** (governance combinata lint + meta-comando, §B pseudocode).
- **Comando** `/complexity-budget`.
- **Lint Check 4v** ([lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md), WARNING-only, gated).
- **Runbook** `wiki/runbooks/complexity-budget-runbook.md`.
