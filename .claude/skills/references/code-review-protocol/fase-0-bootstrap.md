# Fase 0 Bootstrap + Fase 1 Stack Detection + Fase 2 Tre Passate Core (dettaglio completo)

Ambito: dettaglio di `code-review-protocol.md` Fasi 0-2. Copre: layer filter gate, tutte le
precondizioni di Fase 0, calcolo `files_in_scope`, stack detection, e le tre passate core
(idiomaticità, design, robustezza). Leggere prima di avviare qualsiasi review.

---

## Fase 0 — Bootstrap

### Step 0.0 — Layer filter gate (US-190)

Leggere `code_quality.router.layer_filter` da `factory.config.yaml`.

- **Se `layer_filter` è valorizzato** (es. `[be, fe, db, qa]`):
  - Controllare il campo `layer:` del TSK target.
  - Se `layer:` non è nel set: **STOP** — non avviare il review.
    Restituire `review_skipped: true, reason: "layer <X> non in layer_filter [be, fe, db, qa]"`.
  - Se `layer:` è nel set: procedere con le fasi successive.
- **Se `layer_filter` è assente o vuoto**: nessun filtro — review su tutti i layer.

**Backward compat**: factory senza `code_quality.router.layer_filter` non subiscono modifiche.

### Precondizioni Fase 0 (passi 1-5)

1. Read `factory.config.yaml.code_quality`. Se `enabled: false` → ABORT pulito,
   log «CQRL disabilitato; abilitare con `code_quality.enabled: true`».
2. Read TSK target: frontmatter (id, layer, code_path, review_status, review_iter,
   review_report) + body markdown.
3. Verifica preconditions:
   - `review_status ∈ {pending, conditional}` → procedi; altrimenti STOP no-op.
   - `review_iter < max_iterations` → procedi; altrimenti forza verdict `reject` (Loop exhausted).
   - **Precondition additiva visual oracle (opt-in, ADR-009 + ADR-013):**

     ```
     Fase 0 precondition additiva (opt-in):
       IF TSK.layer == 'fe' AND factory.config.yaml.fe_correctness.enabled == true:
         IF TSK.frontmatter.visual_status != 'pass':
           ABORT "Visual oracle non ancora passato (visual_status: {value}).
                  Eseguire /visual-oracle <TSK-id> o attendere completamento
                  della Fase 4-bis di dev-protocol prima di invocare /review.
                  Vedi ADR-009, ADR-013."
     ```

     Formalizza l'ordering `develop → visual-oracle → review` (ADR-013).
     **No-op a flag spento**: con `fe_correctness.enabled: false` (default) → non si valuta.

   - **Precondition additiva UX/UI (opt-in, v2.18, ADR-019 — NOTA INFORMATIVA, no ABORT):**

     ```
     Fase 0 precondition additiva (opt-in, soft):
       IF TSK.layer == 'fe' AND factory.config.yaml.ux_ui.enabled == true:
         IF TSK.frontmatter.ux_ui_status NOT IN ['pass', 'skip']:
           EMIT nota informativa:
             "UX/UI review non ancora completata (ux_ui_status: {value}).
              Considera /ux-ui-review {TSK-id} prima del code-review.
              Skip legittimo: ux_ui_status: skip + ux_ui_skip_reason."
           PROCEDI (no ABORT — la review UX è raccomandata, non obbligatoria).
     ```

     Differenza chiave: visual oracle = **hard ABORT**, UX/UI = **nota informativa**.
     Razionale (ADR-019 §Punto 2): la review UX è *additive value*, non *blocking gate*.
     Skip esplicito (`ux_ui_status: skip`) = scelta legittima del derivatore (simmetrica a
     `a11y_status: skip` di ADR-016). **No-op a flag spento**: con `ux_ui.enabled: false` → non si valuta.

4. Calcola `current_iter = review_iter + 1`.
5. Determina `files_in_scope`:
   - Se `tsk.code_path` valorizzato → usa quei glob.
   - Altrimenti, dal commit del Develop (se `wiki/log.md` ha entry `develop TSK-ZZZ → <hash>`),
     calcola diff `git diff <hash>^ <hash> --name-only` (per `monorepo|sibling`; per
     `submodule` cd nel submodule).
   - Fallback (nessuna delle due): scansiona `<code_path>/**` recente (modificato dopo
     `tsk.updated`). Segnala in chat che lo scope è "best-effort".

---

## Fase 1 — Stack Detection

Invoca skill [`stack-detector`](../../stack-detector.md) con `files_in_scope` + path radice
del progetto. Output: `stack_descriptor` (schema §19.2).

Se `stack_descriptor.confidence < code_quality.thresholds.confidence_min` (default 0.6):
- **Modalità degradata**: attiva flag `degraded: true` nel report.
- Le passate 1 e 3 useranno solo regole `{language}.*` (no framework-specific).
- La passata 2 (design) resta language-agnostic e non degrada.
- Segnala in chat: «Stack confidence <X> < soglia; modalità degradata».

Se `confidence == 0` o `language: "other"` → ABORT, log + suggerisci `tech-scout`.

---

## Fase 2 — Tre passate (parallele, R.Q1)

Le 3 passate sono sub-skill **interne** (non sub-agent §19.9). Lanciare in parallelo.

### Input comune a tutte e 3

- `stack_descriptor` (Fase 1)
- `files_in_scope` con contenuto (max 10 file per passata; se >10, sampling su file con
  maggior LOC modificate)
- Regole rilevanti: glob `code_quality/rules/{team-specific,emergent,canonical}/**`
  filtrato per `applies_to.language` + `applies_to.framework` + `applies_to.context`
  intersecato con la passata. Priorità tier: team-specific > emergent > canonical.
- Output linter deterministici (se `code_quality.passes.idiomaticity: true` e linter
  disponibile): `ruff` per python, `eslint` per JS/TS, `golangci-lint` per go, `clippy`
  per rust → iniettato come `linter_output` nel context della passata 1.

### Schema del prompt (5 sezioni)

```
[ROLE]
{role_persona_specifico_della_passata}

[CONTEXT]
- Stack: {stack_descriptor}
- Regole applicabili: {N regole filtrate per la passata}
- Linter output (se passata 1): {linter_output}
- File: {files_in_scope con contenuto}
- Iterazione: {current_iter} / {max_iterations}
- (Se current_iter > 1) Finding precedenti: {findings_iter_N-1}

[INPUT]
{Codice da revieware, con line numbers}

[TASK]
Identifica finding contro le regole {applicable_rules}. Per ogni finding produci:
- rule_id (deve esistere in regole applicabili — mai inventare)
- file, lines (range esatto)
- severity (high|medium|low — basato su severity_default della regola)
- rationale (≤ 50 parole, perché è un problema)
- fix_complexity (low|medium|high)
- auto_fixable (true se la regola è auto_fixable e il fix è meccanico)

Vincoli:
- Mai inventare rule_id che non esistono nelle regole applicabili.
- Mai duplicare finding (stesso rule_id su stesso file:lines).
- Max {MAX_FINDINGS_PER_PASS} finding per passata.
- Se nessun problema reale: ritorna findings: [].

[OUTPUT_CONTRACT]
JSON valido con schema:
{
  "pass": "idiomaticity | design | robustness",
  "findings": [...]
}
```

### Passata 1 — Idiomaticità (`role_persona: "Core contributor di {framework}"`)

Focus: astrazioni native, naming convention, style guide della community, no pattern
deprecati. Filtro regole: `applies_to.context` include "idiomaticity" o "style".

### Passata 2 — Design (`role_persona: "Tech lead che dovrà mantenere il codice per 2 anni"`)

Focus: responsabilità, coesione, accoppiamento, naming, abstraction leak, complessità.
Filtro regole: `applies_to.context` include "design" o "architecture".
Pre-calcola metriche deterministiche (`radon cc`, `madge`, `gocyclo`, `lizard`) e inietta
come `metrics_input`. Se tool non disponibile per lo stack: ometti quella metrica senza bloccare.

Soglie operative:

| Metrica | Tool suggerito | Soglia attenzione | Soglia blocco |
|---|---|---|---|
| Complessità ciclomatica | `radon cc` (py) · `gocyclo` (go) · `lizard` (multi) | > 10 | > 20 |
| Complessità cognitiva | `lizard --CCN` · SonarQube | > 15 | > 30 |
| Nesting depth | `lizard` · AST parser | > 3 | > 4 |
| LOC per funzione | `radon mi` (py) · `lizard` (multi) | > 50 | > 100 |

### Passata 3 — Robustezza (`role_persona: "SRE che ha visto questo codice fallire in prod"`)

Focus: error handling, edge case, resource leak, concorrenza, validazione input,
timeout/retry. Filtro regole: `applies_to.context` include "robustness" o "reliability".
**Scope explicit nel prompt**: «Non valutare security (SAST, secret, dependency scanning).
Quella è scope di un layer dedicato — vedi PATTERN §19.6 R.Q7».
