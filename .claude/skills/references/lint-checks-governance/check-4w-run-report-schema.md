# Check 4w — RUN-REPORT schema validation (dettaglio completo)

Ambito: dettaglio del Check 4w in `lint-checks-governance.md`. Leggere prima di eseguire.

---

> **Nota di numerazione**: TSK-096, ADR-032 §J e US-049 prescrivono questo check come «Check 4s»;
> nel repo corrente lo slot **4s** è già occupato (EP-015 US-060 — Consistency / compression
> output, due sotto-check 4s.1/4s.2), lo slot **«4t-migration»** è **riservato** alla migration
> ADR-050 §I, e gli slot **4u** (EP-014 US-057) e **4v** (EP-016 US-061) sono già occupati. Il
> check adotta quindi il prossimo slot libero **4w** (lezione TSK-112/118/122). I riferimenti
> «Check 4s» in TSK-096 / ADR-032 §J / US-049 vanno intesi come questo **Check 4w**.

**Severità: ERROR — non WARNING** (deroga motivata a R.P3). Lo schema del RUN-REPORT è un
**contratto binario**: uno schema malformato è un bug strutturale, non un soft warning di igiene.
La deroga è **legittima** perché l'ERROR esiste solo dietro un gate **interamente opt-in**: l'utente
sceglie se accendere `battle_test_gate.enabled`; se lo accende, lo schema **deve** essere rispettato
(ADR-032 §J). Non `heal-eligible` (la compilazione di una sezione mancante richiede giudizio semantico).

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
  `run-report-section-missing` (un ERROR per ogni sezione mancante).
- **4w.c — pre_check/review incoerenti**: `review_status: pass` con `pre_check_status` ∈
  {pending, fail}. → ERROR `run-report-verdict-incoherent`.

**Gate**: `factory.config.yaml.release_governance.battle_test_gate.enabled: false` (default off,
opt-in totale R.P3). Se assente o `false` → 4w no-op totale.

**Esenzione / File esclusi** (nessun ERROR su questi):

- `validation/runs/TEMPLATE/RUN-REPORT.md` — il template scaffoldato stesso.
- Qualsiasi file con nota `[REFERENCE-ONLY]` nel frontmatter o nel corpo.

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
| 1 | `false` (default) | run reale | §3 mancante | ok | no ERROR (gate off, R.P3) |
| 2 | `true` | run reale | tutte §1..§9 | ok + coerente | no ERROR (schema valido) |
| 3 | `true` | run reale | §3 mancante | ok | **ERROR 4w.b** (`run-report-section-missing`) |
| 4 | `true` | run reale | tutte | `pre_check_status` assente | **ERROR 4w.a** (`run-report-frontmatter-invalid`) |
| 5 | `true` | run reale | tutte | `review_status: pass` + `pre_check_status: pending` | **ERROR 4w.c** (`run-report-verdict-incoherent`) |
| 6 | `true` | `TEMPLATE` | con marker `<<...>>` | template | no ERROR (file escluso) |
| 7 | `true` | reference `[REFERENCE-ONLY]` | qualsiasi | ex-post | no ERROR (file escluso, ADR-032 §G) |

**Non duplica** la validazione dello Step 2 della skill `release-validation-gate` (ADR-033 §D):
il `/release` gate è l'**enforcement point primario** (fail-loud a tag-time), il Check 4w è il
**safety net** nel workflow di sviluppo ordinario.

**Cross-link**: 4w → schema canonico RUN-REPORT (`validation/runs/TEMPLATE/RUN-REPORT.md`) +
criteri (`validation/CRITERIA.md` §1 §2 §5) + ADR-032 §C (schema 9 sezioni) / §J (questo check) +
ADR-033 (skill `release-validation-gate`, enforcement primario) + ADR-034 (schema sezione
CHANGELOG, Check 4x companion) + US-049 (origine) / US-050 (gate).
