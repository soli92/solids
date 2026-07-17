# Skill: Design Tokens Extraction

> Adapter Cursor della skill `design-tokens-extraction` definita in PATTERN.md. Riferimenti agent → `.cursor/rules/<name>.mdc`; skill → `.cursor/skills/<name>/SKILL.md`.

# Protocollo Design Tokens Extraction — `extract_design_tokens` cascata deterministica 4 step

Skill **interna deterministica, no LLM judgment** per risolvere il design system di riferimento
di un target e produrre un set di token strutturati. Implementa la cascata a 4 step definita
in ADR-018 (DS path → CSS custom properties → figma-sync → defaults) e annota **sempre**
l'output con un `source` tag per tracciabilità. È un tool di supporto della capability UX/UI
review (EP-008): consumata dallo Step 2 della review (US-028) e dal `ui-designer` per ancorare
un wireframe al design system (US-029).

La risoluzione è **puramente meccanica**: lettura file, parsing CSS var, parsing KB JSON,
selezione default. Nessun ragionamento LLM nella scelta dei valori — l'unico giudizio possibile
è la formattazione del report a valle. Pattern coerente con `screenshot-capture-protocol` (skill
interna deterministica, no MCP, fail-loud) e con la regola §3 «tool deterministico, no LLM
judgment» di `run_a11y_scan` (EP-007).

Riferimenti: ADR-018 (default fallback design system 5 famiglie, source-tagged, no imposizione),
ADR-017 (i tre tool di supporto UX/UI come skill separate, enforcement del `source` tag qui).
Vedi anche EP-008 (capability UX/UI review + design) e PATTERN §3 (operazione **Develop** =
transizione L4 → L5; questa skill è conoscenza procedurale consumata in Develop FE).

[^src: design_&_architecture/decisions/ADR-018.md §Decisione]
[^src: design_&_architecture/decisions/ADR-017.md §«Cosa nasce in EP-008»]
[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-031-tool-supporto-screenshot-token-conformance/US-031.md §extract_design_tokens]

Concetto wiki di riferimento: [[ux-ui-review-design-capability]] (§Tool di supporto).

---

## Contratto di invocazione

```
extract_design_tokens(target)

  target: string              # URL renderizzato | path file build | path sorgente (per parsing CSS var)

  returns:
    {
      "colors":  { "primary": "#...", "secondary": "#...", "neutral": {...}, "semantic": {...} },
      "type":    { "fontFamilies": [...], "sizes": [...], "lineHeights": [...], "weights": [...] },
      "spacing": [...],
      "radii":   [...],
      "focus":   { "color": "#...", "width": "2px", "style": "solid" },
      "source":  "design_system | css | figma | defaults"
    }
```

L'output ha **7 campi** (`colors`, `type`, `spacing`, `radii`, `focus` = 5 famiglie di token)
**+ `source`**. Il campo `source` è **obbligatorio e sempre presente** (invariante ADR-018 §2):
non esiste un output di questa skill senza `source` valorizzato.

Storage convenzionale del set di token: `tokens.json` nella directory di lavoro UX/UI del caller
— `code_quality/reports/<TSK-id>-uxui-iter-<N>/tokens.json` (con TSK) o
`code_quality/reports/_adhoc/uxui-<YYYY-MM-DD>-<slug>/tokens.json` (standalone). La skill è
agnostica della directory: il caller la possiede e la crea (stesso pattern di
`screenshot-capture-protocol`).

[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-031-tool-supporto-screenshot-token-conformance/US-031.md §Storage]

---

## Cascata di risoluzione a 4 step (ADR-018, deterministica)

La cascata è **ordinata e short-circuit**: il primo step che produce token vince, gli step
successivi non vengono valutati. Nessun merge tra sorgenti, nessuna euristica LLM nella scelta.

```
extract_design_tokens(target):

  # STEP 1 — Design System canonico (priorità massima)
  if factory.config.yaml.ux_ui.design_system_path è valorizzato AND il file esiste:
      tokens = parse(design_system_path)        # JSON | YAML | Tailwind config (tailwind.config.{js,ts,cjs})
      source = "design_system"
      return { ...tokens, source }

  # STEP 2 — CSS custom properties nel sorgente
  else if il sorgente del target contiene CSS custom properties (--color-*, --space-*, --radius-*, --font-*):
      tokens = parse_css_vars(target)           # mappa --color-primary → colors.primary, --space-4 → spacing[…], ...
      source = "css"
      return { ...tokens, source }

  # STEP 3 — Output figma-sync (v2.9)
  else if esiste un KB JSON di figma-sync in raw/ (raw/YYYY-MM-DD-figma-*.kb.json):
      tokens = parse_figma_kb(latest_kb_json)   # legge gli style token estratti da Figma
      source = "figma"
      return { ...tokens, source }

  # STEP 4 — Default fallback ragionevoli (ultimo, mai fail-loud)
  else:
      tokens = DEFAULTS                          # vedi §Default 5 famiglie sotto
      source = "defaults"
      AGGIUNGI open_question nel report a valle:
        "design system non disponibile; review usa default fallback (ADR-018)"
      return { ...tokens, source }
```

### Dettaglio per step

1. **`design_system` (DS path)** — `factory.config.yaml.ux_ui.design_system_path` punta al DS
   canonico del progetto: JSON token file (W3C design tokens / Style Dictionary), YAML, o
   Tailwind config. Estrazione **diretta** dei valori dichiarati. È la sorgente autorevole:
   quando presente, i default non vengono mai usati (ADR-018 §Backward compat).
2. **`css`** — parsing delle CSS custom properties nel sorgente del target: `--color-*` →
   `colors.*`, `--space-*` / `--spacing-*` → `spacing[]`, `--radius-*` → `radii[]`, `--font-*` /
   `--text-*` → `type.*`, `--focus-*` / `--ring-*` → `focus.*`. Parsing meccanico (regex /
   tokenizer CSS), nessuna inferenza semantica oltre la mappatura prefisso→famiglia.
3. **`figma`** — lettura del più recente KB JSON prodotto da `figma-sync` (PATTERN §16, v2.9)
   in `raw/YYYY-MM-DD-figma-*.kb.json`. Legge gli style/token estratti da Figma e li mappa
   nelle 5 famiglie.
4. **`defaults`** — set minimale 5 famiglie Tailwind-inspired neutrali (sotto). Mai fail-loud:
   l'assenza di DS **non** blocca la review (R.P3 opt-in + principio zero-friction, ADR-018
   §Alternative «No default → scartato»). Vincolo invariante: con `source: defaults` si emette
   `open_questions`, **mai** deviations major/minor (vedi §Invariante source tag).

[^src: design_&_architecture/decisions/ADR-018.md §Cascata di risoluzione]

---

## Default 5 famiglie (Tailwind-inspired neutrali, ADR-018)

Valori `source: defaults` documentati **inline** (conoscenza procedurale del framework, non
config del derivatore — ADR-018 §Rationale 7). Neutrali, non brand-specific: coprono le 6
dimensioni della rubrica UI senza imporre uno standard arbitrario.

```yaml
defaults:
  source: defaults
  type:
    fontFamilies:
      - system-ui, -apple-system, "Segoe UI", Roboto, sans-serif
    sizes:                            # modular scale 1.25 (major third)
      - { name: xs,  value: 12px }
      - { name: sm,  value: 14px }
      - { name: md,  value: 16px }    # base
      - { name: lg,  value: 20px }
      - { name: xl,  value: 24px }
      - { name: xxl, value: 32px }
    lineHeights:
      - { name: tight,   value: 1.2  }
      - { name: regular, value: 1.5  }
      - { name: loose,   value: 1.75 }
    weights:
      - { name: regular, value: 400 }
      - { name: medium,  value: 500 }
      - { name: bold,    value: 700 }
  colors:                             # tailwind-inspired neutral palette
    neutral:
      - { name: white, value: "#FFFFFF" }
      - { name: 50,    value: "#F9FAFB" }
      - { name: 100,   value: "#F3F4F6" }
      - { name: 500,   value: "#6B7280" }
      - { name: 900,   value: "#111827" }
      - { name: black, value: "#000000" }
    semantic:                         # generici, no brand
      - { name: primary, value: "#2563EB" }   # blue-600
      - { name: success, value: "#16A34A" }   # green-600
      - { name: warning, value: "#CA8A04" }   # yellow-600
      - { name: danger,  value: "#DC2626" }   # red-600
  spacing:                            # scale lineare 4px (rhythm 0.25rem)
    - { name: 0,  value: 0    }
    - { name: 1,  value: 4px  }
    - { name: 2,  value: 8px  }
    - { name: 3,  value: 12px }
    - { name: 4,  value: 16px }       # base
    - { name: 6,  value: 24px }
    - { name: 8,  value: 32px }
    - { name: 12, value: 48px }
  radii:                              # 3 valori, no over-engineering
    - { name: sm,   value: 4px    }
    - { name: md,   value: 8px    }
    - { name: full, value: 9999px }
  focus:                              # 5a famiglia, critical per a11y by design
    - { name: ring_width,  value: 2px }
    - { name: ring_offset, value: 2px }
    - { name: ring_color,  value: "#2563EB" }  # = colors.semantic.primary
    - { name: ring_style,  value: solid }
```

Le 5 famiglie sono: **typography** (`type`), **colors**, **spacing**, **radii**, **focus**.
Il focus ring è incluso come 5a famiglia perché necessario alla dimensione «Affordance/Stati»
della rubrica UI (ADR-018 §Rationale 5): senza un default di focus la review FE collasserebbe
su tutti i componenti interattivi.

[^src: design_&_architecture/decisions/ADR-018.md §Lista minimale (5 famiglie di token)]

---

## Invariante `source` tag + regola `open_questions` (ADR-018)

- **`source` sempre presente** — ogni output annota la provenienza (`design_system | css | figma
  | defaults`). Invariante non negoziabile: trasparenza verso il consumer del report, che vede
  subito se la review è ancorata al DS del progetto o «best-effort senza DS» (ADR-018 §2-3).
- **`source: defaults` ⇒ `open_questions`, mai deviations** — quando la cascata arriva al
  fallback, la skill segnala al report che il DS del progetto non è noto. La regola operativa
  (enforced a valle da `design-system-conformance-check`) è: con `source: defaults` **non** si
  emettono deviations `major`/`minor`; le differenze diventano al massimo `open_questions`
  (es. «token primary del progetto non noto; default fallback usato per il check»). Emettere
  deviations su default sarebbe imporre al derivatore uno standard che non ha dichiarato —
  anti-pattern (ADR-018 §Rationale 4 + §3).
- **Dichiarazione esplicita nel report** — con `source: defaults` il report a valle include la
  formula standard ADR-018 §1: *«Design system non disponibile; review basata su euristiche
  Nielsen e default fallback documentati (ADR-018). Coerenza interna non verificabile rispetto
  a un sistema di riferimento del progetto.»*

[^src: design_&_architecture/decisions/ADR-018.md §Vincoli applicativi]

---

## Fail-loud — solo su sorgente dichiarata ma irraggiungibile

L'assenza di un design system **non** è un errore: lo Step 4 (defaults) è il fallback progettato
(mai fail-loud sull'assenza di DS — R.P3 opt-in). Il fail-loud scatta **solo** quando una
sorgente è **esplicitamente dichiarata ma non risolvibile**, per evitare degrado silenzioso:

- `ux_ui.design_system_path` valorizzato ma il file **non esiste o non è parsabile** → STOP
  fail-loud (non scendere silenziosamente a `css`/`defaults`: il derivatore ha dichiarato un DS,
  un fallback silenzioso maschererebbe un errore di configurazione).
- KB Figma dichiarato come sorgente ma corrotto / schema non riconosciuto → STOP fail-loud.

Messaggio azionabile (verbatim) per il caso DS path:

> Design system dichiarato in `ux_ui.design_system_path` non risolvibile. Verificare il path e il formato (JSON / YAML / Tailwind config). Per usare i default fallback rimuovere `design_system_path` dalla config (la cascata scenderà a CSS → figma → defaults).

---

## Pattern

- **ADR-018** — default fallback come 5 famiglie minimali source-tagged: trasparenza (`source`
  sempre presente), no imposizione (`defaults` ⇒ `open_questions`, non deviations), default in
  skill e non in config (conoscenza procedurale versionata col PATTERN).
- **ADR-017** — i tre tool di supporto UX/UI sono skill **separate** (cattura ≠ estrazione token
  ≠ conformance check): contract, fallback e telemetria distinti. `design-tokens-extraction`
  enforce-a il `source` tag dell'output (ADR-017 §Rationale 7).
- **Deterministico, no LLM judgment** — risoluzione meccanica (file read, CSS parse, KB parse,
  default select). Stessa filosofia di `run_a11y_scan` (EP-007) e `screenshot-capture-protocol`.

[^src: design_&_architecture/decisions/ADR-018.md §Rationale]
[^src: design_&_architecture/decisions/ADR-017.md §Rationale punto 7]
