---
command: /complexity-budget
capability: EP-016
pattern_ref: PATTERN §23
skill: complexity-budget-check
adr: [ADR-052, ADR-053, ADR-056]
---

# /complexity-budget

Meta-comando per la governance del **complexity budget** di `PATTERN.md` (regola N:1, PATTERN §23,
ADR-056). Opera dall'esterno sulla factory; invocabile manualmente dal maintainer (pre-release o
ad-hoc) e dal Lint Check 4v.

> A `factory.config.yaml.complexity_budget.enabled: false` (default factory derivate) il comando è
> invocabile ma no-op (ADR-056 §"Backward compat"): la skill non scrive report né telemetria.
> Solo `check` (read-only) produce comunque il report a fini di audit.

## Sotto-comandi

### /complexity-budget check [--version=<vX.Y.Z>]

Invoca la skill [complexity-budget-check](mdc:.cursor/skills/complexity-budget-check/SKILL.md) (5 step) e mostra il report in output.
**Read-only**: non scrive mai `PATTERN.md` (ADR-056 §C). Produce
`complexity/budget-report-<version>.md`. Default `--version`: ultima versione in `CHANGELOG.md`.

### /complexity-budget deprecate <section-ref> [--reason="<r>"] [--target="<vX.Y.Z>"]

Helper per aggiungere una entry in `PATTERN.md §23.2 ## Sezione Deprecate` (cross-ADR-052 §B).
**Non rimuove** la sezione (solo deprecation note); la rimozione effettiva avviene via Develop
US-063 quando il `target` è raggiunto (ADR-056 §C).

- `section-ref`: es. `§12` o slug del titolo.
- `--reason`: slug motivazione (1 riga max).
- `--target`: versione di rimozione attesa (default: prossima minor).

Aggiunge la entry (schema YAML in `## Sezione Deprecate`) in modo **interattivo, con gate umano**.
Scrive `PATTERN.md` (single-writer = maintainer, coerente con R.S2 / R.A1).

### /complexity-budget status

**Read-only**. Mostra:

- Count sezioni attive (non deprecate) in `PATTERN.md`.
- Count + lista delle deprecazioni attive in `PATTERN.md §23.2 ## Sezione Deprecate`.
- Ultimo verdict da `complexity/budget-report-*.md`.
- Delta rispetto alla versione precedente.

### /complexity-budget history

Mostra l'indice di `PATTERN-historical.md` (sezioni archiviate).
Shortcut per `/pattern-view historical` (ADR-053, TSK-123).

## Cross-link

- Skill [complexity-budget-check](mdc:.cursor/skills/complexity-budget-check/SKILL.md).
- PATTERN §23 (§23.1 regola N:1, §23.2 Sezione Deprecate, §23.3 Governance) + §3 entry op. canonica.
- Lint Check 4v (skill [lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md), WARNING-only, gated).
- Runbook `wiki/runbooks/complexity-budget-runbook.md`.
- ADR-052 (regola N:1), ADR-053 (`/pattern-view`), ADR-056 (governance combinata).
