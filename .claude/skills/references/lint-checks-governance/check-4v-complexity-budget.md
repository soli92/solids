# Check 4v — Complexity Budget regola N:1 (dettaglio completo)

Ambito: dettaglio del Check 4v in `lint-checks-governance.md`. Leggere prima di eseguire.

---

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
