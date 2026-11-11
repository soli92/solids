# Check 4x — CHANGELOG Validation evidence mancante (dettaglio completo)

Ambito: dettaglio del Check 4x in `lint-checks-governance.md`. Leggere prima di eseguire.

---

> **Nota di numerazione**: TSK-099, ADR-033 §I e US-050 prescrivono questo check come «Check 4t»;
> nel repo corrente lo slot **«4t»** è **riservato** alla migration ADR-050 §I, mentre gli slot
> **4q/4r/4s/4u/4v/4w** sono già occupati. Il check adotta quindi il prossimo slot libero **4x**
> (lezione TSK-112/118/122/096). I riferimenti «Check 4t» in TSK-099 / ADR-033 §I / US-050, e il
> riferimento «Check 4t companion» nel Check 4w, vanno intesi come questo **Check 4x**.

**Severità: WARNING — non ERROR** (coerente con R.P3, opt-in totale). Il `/release` gate fa già
fail-loud al momento dell'invocazione (skill `release-validation-gate` Step 5, ADR-033 §D); il lint
è solo un **reminder pre-tag** per il maintainer. Mai `heal-eligible` (la compilazione della sezione
richiede giudizio semantico). Distinto da Check 4w: 4w enforce lo schema RUN-REPORT, 4x enforce la
presenza dell'evidenza nel CHANGELOG.

**Pattern allineato a Check 4m/4n/4o/4p/4q/4r/4s/4u/4v (R.P3 opt-in totale)**: WARNING-only,
opt-in via flag config, nessun ERROR meccanico.

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
A gate `false` (default factory derivate) o assente → 4x no-op totale (backward compat ADR-033 §J, R.P3).

**Esenzione**: frontmatter `validation_evidence_skip: true` nel blocco release di `CHANGELOG.md`
(raramente usato, richiede audit reason esplicita). La presenza del marker `[gate-bypassed]` nella
sezione `## Validation evidence (v<version>)` **soddisfa** il check (bypass tracciato, ADR-033 §E).

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
| 1 | `false` (default) | `## v2.20` | assente | assente | no WARNING (gate off, R.P3) |
| 2 | `true` | `## v2.20` | presente | (qualsiasi) | no WARNING (evidenza nel CHANGELOG) |
| 3 | `true` | `## v2.20` | assente | presente | no WARNING (evidenza side-by-side) |
| 4 | `true` | `## v2.20` | assente | assente | **WARNING 4x** (`changelog-validation-evidence-missing`) |
| 5 | `true` | `## v2.20` | con marker `[gate-bypassed]` | (qualsiasi) | no WARNING (bypass tracciato, ADR-033 §E) |
| 6 | `true` | `## v2.20` | assente + `validation_evidence_skip: true` | assente | no WARNING (esente) |

**Cross-link**: 4x → ADR-033 §I (questo check) / §D Step 5 (enforcement primario) / §E (bypass
tracciato) + ADR-034 §A (schema sezione CHANGELOG `## Validation evidence`) + ADR-036 §B
(PATTERN §22 Release Governance) + Check 4w (companion ERROR, RUN-REPORT schema) + US-050 (origine).
