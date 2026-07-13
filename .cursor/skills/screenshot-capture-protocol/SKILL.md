# Skill: Screenshot Capture Protocol

> Adapter Cursor della skill `screenshot-capture-protocol` definita in PATTERN.md. Riferimenti agent → `.cursor/rules/<name>.mdc`; skill → `.cursor/skills/<name>/SKILL.md`.

# Protocollo Screenshot Capture — cattura Playwright condivisa multi-viewport

Skill **interna condivisa** (single source of truth) per la cattura di screenshot di un
target via Playwright headless. Estrae la logica precedentemente inline nella **Fase 3 di
`visual-oracle-protocol`** (EP-005) in modo che sia riutilizzabile anche dalla capability
UX/UI review (`ux-ui-review-protocol`, EP-008). È un **refactor non distruttivo**: l'API
esterna del visual oracle resta invariata (ADR-017 §«Cosa NON cambia»).

Questa skill **non legge `factory.config.yaml`**: è agnostica della sorgente. Il caller
risolve la matrice `viewports × themes` e passa i parametri (ADR-017 §Rationale 5 —
viewports cascade nel caller, non nella skill). Niente MCP: usa lo stesso meccanismo
Bash + script runner di EP-005 (ADR-008).

Riferimenti: ADR-017 (riuso vs duplicazione, single source per la cattura Playwright),
ADR-008 (Playwright via Bash, no MCP, runner in `.factory-runners/`, fail-loud).
Pattern di skill interna condivisa già presente nel framework: `stack-detector`
(code-reviewer + repo-sync), `propagate-resolution` (analyst + lint), `oracle-precheck`
(orchestrator + linter).

[^src: design_&_architecture/decisions/ADR-017.md §Decisione]
[^src: design_&_architecture/decisions/ADR-008.md §Decisione]

---

## Contratto di invocazione

```
capture_screenshot(target, viewports, themes, output_dir, naming_pattern)

  target: string              # URL http/https | path file build | path componente harness
  viewports: [{name, width, height?}]   # risolti dal caller (cascade — vedi sotto)
  themes: [string]            # opzionale: "light" | "dark". Vuoto/omesso → un solo passaggio per viewport
  output_dir: string          # directory di destinazione dei PNG (il caller la possiede e la crea)
  naming_pattern: string      # default "{viewport}-{theme}.png" — o "{viewport}.png" se themes vuoto

  returns:
    screenshots: [{ viewport, theme, path, bytes }]
```

Forma minima usata in pratica — il caller passa **una cella alla volta** della matrice
(cascata viewports nel caller, non nella skill, ADR-017 §Rationale 5):

```
capture_screenshot(target, viewport)
  target: string
  viewport: {width: number, height?: number}
  returns: path PNG nella directory caller
```

---

## Logica interna (Playwright headless via Bash)

1. Genera/riusa uno **script runner Bash** in `.factory-runners/` (cartella **gitignored**,
   non inquina il code_path — ADR-008 §Rationale 2). Lo script pilota Playwright **via Bash**,
   **NON un MCP tool** (ADR-008 §Decisione: «niente MCP custom»).
2. `chromium.launch({ headless: true })` → `page = browser.newPage()`.
3. `page.goto(target, { waitUntil: 'load' })` (URL http/https; per path locale build → `file://`).
4. Per ogni `viewport`: `page.setViewportSize({ width, height })`.
5. Per ogni `theme` (se presente): `page.emulateMedia({ colorScheme: theme })` (`'light'` | `'dark'`).
6. `page.screenshot({ path: <output_dir>/<naming> })` → salva il PNG.
7. Ritorna la lista `{viewport, theme, path, bytes}` al caller.

---

## Naming convention PNG

- Con themes: `<viewport_name>-<theme>.png` → es. `mobile-light.png`, `desktop-dark.png`.
- Senza themes (lista vuota/omessa): `<viewport_name>.png` → es. `mobile.png`, `desktop.png`.

Pattern parametrizzato via `naming_pattern` (default `"{viewport}-{theme}.png"`); il caller
può overridarlo ma la convention sopra è quella attesa dai consumer (visual-oracle digest,
ux-ui-review report).

---

## Matrice viewports × themes — risolta dal caller (ADR-017)

La skill è **agnostica della sorgente**: riceve `viewports` (e opzionalmente `themes`) come
parametri e non legge mai la config. La risoluzione avviene nel caller:

- **Caller `visual-oracle-protocol`** (EP-005): passa `viewports` e `themes` da
  `factory.config.yaml.fe_correctness.viewports` / `.themes` (matrice cartesiana completa,
  default 4 celle: `mobile/desktop × light/dark`).
- **Caller `ux-ui-review-protocol`** (EP-008): compone `viewports` con la **cascade**:
  1. `factory.config.yaml.fe_correctness.viewports` se `fe_correctness.enabled: true` (riuso totale);
  2. fallback `factory.config.yaml.ux_ui.default_viewports`
     (default `[{name: mobile, width: 375}, {name: desktop, width: 1280}]`).
  - **Themes omessi di default** per la review euristica (un solo theme sufficiente, salvo
    override esplicito — ADR-017 §Rationale 9).

[^src: design_&_architecture/decisions/ADR-017.md §Rationale punto 5]
[^src: design_&_architecture/decisions/ADR-017.md §Rationale punto 9]

---

## CWD di esecuzione (ADR-064 §D)

Lo snippet Node fa `require('playwright')`, che risolve da `node_modules` **della CWD**. Esegui il
runner / lo script `tools/visual/capture_screenshot.sh` dalla **directory del code_path/package
target** (dove `package.json` installa Playwright), non dalla root del repo factory. Eseguirlo dalla
CWD sbagliata produce `Cannot find module 'playwright'`: è un **errore tecnico fail-loud** (exit ≠ 0),
non un degrado silenzioso a `no-visual`. Idem per la versione Node: allinea al `.nvmrc` del target.

## Fail-loud su Playwright mancante

Se Playwright non è disponibile nel project host → **STOP fail-loud**, nessun degrado
silenzioso (ADR-008 §Rationale 5). Messaggio azionabile **verbatim**:

> Cattura screenshot richiede Playwright. Eseguire: `npm i -D @playwright/test && npx playwright install --with-deps chromium`. Vedi runbook `wiki/runbooks/visual-oracle-installation.md` se disponibile.

---

## Refactor EP-005 — `visual-oracle-protocol` Fase 3 delega qui

La **Fase 3 (Screenshot Multi-Viewport/Tema)** di `visual-oracle-protocol` **delega a questa
skill** invece di implementare la cattura inline. Comportamento esterno **identico** a prima
del refactor: stessi PNG, stesso naming, stesso side-channel
`code_quality/reports/<TSK-id>-visual-iter-<N>/`, stesso schema dati (ADR-012 §H). Chi invoca
`/visual-oracle` o consuma la skill non vede differenze (backward compat totale — ADR-017
§Rationale 4).

Invocazione dal visual oracle:

```
Fase 3 → capture_screenshot(
  target        = <target risolto in Fase 2>,
  viewports     = factory.config.yaml.fe_correctness.viewports,
  themes        = factory.config.yaml.fe_correctness.themes,
  output_dir    = code_quality/reports/<TSK-id>-visual-iter-<N>/,
  naming_pattern= "{viewport}-{theme}.png"
)
→ lista screenshot path passata alla Fase 4 (Critica Visiva).
```

[^src: design_&_architecture/decisions/ADR-017.md §«Cosa cambia in EP-005 (refactor non distruttivo)»]

---

## Pattern

- **ADR-017** — single source of truth per la cattura Playwright: una sola infrastruttura
  screenshot nel framework, un solo punto dove correggere bug / aggiungere viewport / gestire
  il fail-loud. Coupling intenzionale e positivo EP-005 ↔ EP-008 (DRY al livello
  dell'operazione semantica, non della riga).
- **ADR-008** — Playwright via Bash, no MCP custom; runner generati in `.factory-runners/`
  (gitignored); fail-loud su prerequisito mancante.

[^src: design_&_architecture/decisions/ADR-017.md §Rationale]
[^src: design_&_architecture/decisions/ADR-008.md §Rationale]
