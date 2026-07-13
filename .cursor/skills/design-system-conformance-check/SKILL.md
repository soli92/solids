# Skill: Design System Conformance Check

> Adapter Cursor della skill `design-system-conformance-check` definita in PATTERN.md. Riferimenti agent → `.cursor/rules/<name>.mdc`; skill → `.cursor/skills/<name>/SKILL.md`.

# Protocollo Design System Conformance Check — `check_design_system_conformance` confronto deterministico

Skill **interna deterministica, no LLM judgment** per confrontare i valori misurati su un
rendering con i token del design system di riferimento e produrre una lista di **deviazioni
tipizzate** (`major` / `minor`). È un tool di supporto della capability UX/UI review (EP-008),
invocata dallo **Step 2** del `ux-ui-review-protocol` (US-028) dopo che `design-tokens-extraction`
ha risolto i token di riferimento.

Il confronto è **valore-per-valore, puramente meccanico**: per ciascuna proprietà osservata si
compara il valore renderizzato con il valore atteso nel set di token; la severità è derivata da
una **tabella interna fissa**, non da ragionamento LLM. Nessun giudizio soggettivo, nessuna
inferenza: stesso valore → nessuna deviazione; valore diverso → deviazione con severity da
tabella. Questo separa nettamente il livello «misura deterministica» (questa skill) dal livello
«review euristica Nielsen» (LLM, nel `ux-ui-review-protocol`).

Riferimenti: ADR-017 (i tre tool di supporto UX/UI come skill separate; conformance check
deterministico, no LLM judgment per il confronto valore-per-valore — §«Cosa nasce in EP-008»),
ADR-018 (regola `source: defaults` ⇒ niente deviations, solo `open_questions`). Vedi anche EP-008
(capability UX/UI review + design) e PATTERN §3 (operazione **Develop**: questa skill è
conoscenza procedurale consumata in Develop FE / review UX/UI).

[^src: design_&_architecture/decisions/ADR-017.md §«Cosa nasce in EP-008»]
[^src: design_&_architecture/decisions/ADR-018.md §Vincoli applicativi punto 3]
[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-031-tool-supporto-screenshot-token-conformance/US-031.md §check_design_system_conformance]

Concetto wiki di riferimento: [[ux-ui-review-design-capability]] (§Tool di supporto).

---

## Contratto di invocazione

```
check_design_system_conformance(target, ref)

  target: string                       # URL renderizzato (i valori effettivi vengono misurati qui)
  ref:    { colors, type, spacing, radii, focus, source }   # output di design-tokens-extraction

  returns:
    {
      "deviations": [
        {
          "property": "color.primary",    # path tipizzato del token
          "expected": "#0066CC",          # valore atteso (da ref)
          "actual":   "#1976D2",          # valore misurato sul rendering
          "location": "css selector",     # dove osservato (selettore / componente)
          "severity": "major | minor"
        }
      ],
      "open_questions": [...]             # popolato SOLO se ref.source == "defaults" (vedi sotto)
    }
```

Lo `ref` proviene da `design-tokens-extraction` e porta con sé il campo `source` (invariante
ADR-018), che governa il comportamento di questa skill (vedi §Regola `source: defaults`).

Storage convenzionale del report: `conformance.json` nella directory di lavoro UX/UI del caller
— `code_quality/reports/<TSK-id>-uxui-iter-<N>/conformance.json` (con TSK) o
`code_quality/reports/_adhoc/uxui-<YYYY-MM-DD>-<slug>/conformance.json` (standalone). La skill è
agnostica della directory: il caller la possiede.

[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-031-tool-supporto-screenshot-token-conformance/US-031.md §Storage]

---

## Logica deterministica (no LLM judgment)

Il confronto è **valore-per-valore**, senza ragionamento LLM. Per ogni token osservabile nel
rendering:

```
check_design_system_conformance(target, ref):

  # Guardia ADR-018 — DS del progetto non noto
  if ref.source == "defaults":
      # confronto vs default fallback NON produce deviations imposte
      open_questions = ["design system non disponibile; review usa default fallback (ADR-018)"]
      # eventuali differenze rilevate sono al massimo open_questions, mai severity major/minor
      return { deviations: [], open_questions }

  deviations = []
  for property in proprietà_osservabili(target):       # colore, font-family, size, spacing, radius, focus
      actual   = misura_valore(target, property)        # valore renderizzato (deterministico)
      expected = lookup(ref, property)                  # valore atteso dal set di token
      if expected è definito AND normalize(actual) != normalize(expected):
          severity = SEVERITY_TABLE[classe(property), entità(actual, expected)]   # tabella interna fissa
          deviations.append({ property, expected, actual, location: selector(property), severity })

  return { deviations, open_questions: [] }
```

Note deterministiche:

- **`normalize`** — normalizzazione meccanica prima del confronto (es. `#FFF` ≡ `#FFFFFF`,
  `rgb(0,0,0)` ≡ `#000000`, `0` ≡ `0px`, lowercase hex). Non è inferenza: è canonicalizzazione
  di rappresentazioni equivalenti dello stesso valore.
- **`entità(actual, expected)`** — per lo spacing, distanza assoluta in px usata dalla tabella
  (micro-deviazione `< 4px` → `minor`). Calcolo numerico, non giudizio.
- **Nessun LLM** — la skill non interpreta «se la deviazione è grave nel contesto»: la severità
  è sempre derivata dalla tabella. Il giudizio contestuale appartiene alla review euristica
  (`ux-ui-review-protocol`, LLM), non a questa skill.

---

## Tabella severity per tipo di deviazione (interna, fissa)

| Proprietà / classe          | Condizione                                   | Severity |
|-----------------------------|----------------------------------------------|----------|
| `color.primary`             | valore diverso dal token                     | major    |
| `color.semantic.*`          | valore diverso (success/warning/danger/...)  | major    |
| `type.fontFamilies`         | font-family diversa dal token                | major    |
| `focus.*` (ring color/width/style) | focus assente o diverso dal token      | major    |
| `spacing`                   | micro-deviazione (`< 4px` diff)              | minor    |
| `spacing`                   | deviazione `>= 4px`                          | major    |
| `radii`                     | valore radius diverso dal token              | minor    |
| `type.sizes` / `lineHeights`| size/line-height fuori scala                 | minor    |

Regole di classificazione (deterministiche):

- **Colori semantici e primary = `major`** — sono identità di brand / segnali funzionali;
  uno scostamento è una violazione sostanziale (US-031 §Tabella severity).
- **Font-family = `major`** — cambia l'identità tipografica del prodotto.
- **Focus ring = `major`** — impatta affordance/stati e accessibilità (coerente con il ruolo
  della 5a famiglia di token, ADR-018 §Rationale 5).
- **Spacing micro (`< 4px`) = `minor`**, spacing oltre la soglia = `major` — la soglia 4px è il
  rhythm base dei default (ADR-018 §spacing).
- **Radii = `minor`** — scostamento estetico a basso impatto funzionale.

La tabella è la **single source of truth** della severità: se serve aggiungere una classe di
proprietà, si estende qui (un solo punto), non nella logica del caller.

[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-031-tool-supporto-screenshot-token-conformance/US-031.md §Tabella severity per tipo di deviazione]

---

## Regola `source: defaults` (ADR-018 §3)

Quando `ref.source == "defaults"` (design system del progetto non noto), la skill **non** emette
deviations `major`/`minor`: confrontare il rendering contro default fallback significherebbe
dire al derivatore «il tuo codice non rispetta uno standard che tu non hai dichiarato»
(anti-pattern, ADR-018 §Rationale 4).

Comportamento:

- `deviations` resta **vuota** (nessuna severità imposta).
- Si popola `open_questions` con la stringa standard: *«design system non disponibile; review
  usa default fallback (ADR-018)»* — domanda al derivatore (quale è il primary di brand?), non
  imposizione.
- Il report a valle aggiunge la dichiarazione esplicita ADR-018 §1 (review best-effort senza DS,
  coerenza interna non verificabile).

Con `ref.source` in `{design_system, css, figma}` la skill opera normalmente (deviations
tipizzate dalla tabella).

[^src: design_&_architecture/decisions/ADR-018.md §Vincoli applicativi punto 3]

---

## Fail-loud su rendering non misurabile

Se il `target` non è raggiungibile / non renderizzabile (impossibile misurare i valori
effettivi) → **STOP fail-loud**, nessun degrado silenzioso. La skill non «inventa» valori
`actual` né emette un report vuoto silenzioso. Messaggio azionabile (verbatim):

> Conformance check richiede un rendering misurabile del target. Verificare che `target` sia raggiungibile (URL / file build) e che gli screenshot dello Step 1 (`screenshot-capture-protocol`) siano stati prodotti. Nessuna deviazione può essere calcolata senza valori renderizzati.

---

## Pattern

- **Deterministico, no LLM judgment** — confronto valore-per-valore + tabella severity fissa.
  Il giudizio contestuale appartiene alla review euristica (`ux-ui-review-protocol`), non qui.
  Separazione netta misura vs giudizio (stessa filosofia di `run_a11y_scan`, EP-007).
- **ADR-017** — skill separata dai tool gemelli (`screenshot-capture-protocol`,
  `design-tokens-extraction`): contract e telemetria distinti, riuso indipendente (es. il
  `ui-designer` può validare un wireframe senza fare la review completa).
- **ADR-018** — `source: defaults` ⇒ `open_questions`, mai deviations imposte: il framework non
  «preme» il derivatore verso uno standard arbitrario.

[^src: design_&_architecture/decisions/ADR-017.md §Rationale punto 7]
[^src: design_&_architecture/decisions/ADR-018.md §Rationale punto 4]
