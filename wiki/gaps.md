---
id: gaps
type: gaps
title: Wiki Gaps
status: current
created: 2026-07-17
updated: 2026-07-17
---

# Wiki Gaps

Gap aperti nella knowledge base wiki — segnalati dall'analisi del repository (2026-07-17).

Formato entry: `GAP-NNN | YYYY-MM-DD | fonte | descrizione | priorita' | stato`

Per chiudere un gap: aggiungere `**Risolto:** <data> — <note>` alla entry corrispondente.

---

## GAP-001 — design_&_architecture/ fuori dalla wiki tree

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.5 FINDING MODERATO #4
**Priorita'**: P2 (Importante)

4 documenti referenziati da `wiki/index.md` si trovano fuori dalla wiki tree in `design_&_architecture/`:

- `a11y-token-audit.md`
- `ep019-critic-report-solids.md`
- `theme-spec-brutalist.md`
- `token-naming-convention.md`

Problema: il wiki-lint non li scansiona; il wiki-keeper non li aggiorna automaticamente; i path relativi `../design_&_architecture/` in `wiki/index.md` sono fragili (si rompono se wiki/ viene riorganizzata).

**Azione raccomandata**: spostare i 4 file in `wiki/design/` o `wiki/concepts/` e aggiornare i link in `wiki/index.md`.

**Stato**: APERTO

---

## GAP-002 — AI_LOG.md non ingested

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.6 FINDING MODERATO #5
**Priorita'**: P2 (Importante)

`AI_LOG.md` (root del repo) contiene storico prezioso attualmente non accessibile via wiki:

- 58 commit 2026-02-16 → 2026-04-08
- Decisioni architetturali per fase (token, registry, brand assets, ecc.)
- Integrazione soli-prof (webhook HMAC, re-ingest selettivo)
- Pattern e lezioni apprese

**Azione raccomandata**: copiare `AI_LOG.md` in `docs/raw/ai-log-<data>.txt` ed eseguire ingest con wiki-keeper.

**Stato**: CHIUSO

**Risolto:** 2026-07-17 — `AI_LOG.md` ingested direttamente. Creata `wiki/concepts/development-history.md` con 5 fasi di sviluppo, decisioni architetturali per fase, problemi tecnici risolti (con hash commit), pattern ricorrenti, debiti tecnici noti, integrazione soli-prof. Il file e' stato letto dalla root del repo senza copia in `docs/raw/`.

---

## GAP-003 — AGENTS.md root outdated (pre-factory)

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.4 FINDING MAGGIORE #3
**Priorita'**: P3 (Mantenibilita')

`AGENTS.md` root (aggiornato 2026-04-29) e' precedente alla factory scaffold (2026-07-17). Non contiene riferimenti a:

- Pattern factory v2.33
- Adapter `.claude/` e `.cursor/`
- Wiki in `wiki/` root (slash commands `/run`, `/query`, `/lint`, ecc.)
- Flusso wiki-keeper per ingest di `docs/raw/`

In topologia knowledge-only, `CLAUDE.md` e' il punto di ingresso principale — `AGENTS.md` root dovrebbe almeno rimandare a `CLAUDE.md`.

**Azione raccomandata**: aggiungere sezione "Factory / Agent Context" all'`AGENTS.md` root con rimando a `CLAUDE.md` e `wiki/`.

**Stato**: APERTO

---

## GAP-004 — docs MDX non ingested direttamente nella wiki

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.7 FINDING MODERATO #6
**Priorita'**: P4 (Nice to have)

`docs/principles.mdx` e `docs/roadmap.mdx` (e tutti i file in `docs/foundations/`) contengono conoscenza strutturata di produzione non ingested direttamente nella wiki factory. La wiki ha pagine derivate da analisi secondaria ma non dal MDX originale.

Conoscenza mancante (non ancora in wiki):
- Tipografia: font stack (Inter, DM Sans, JetBrains Mono), scale tipografica, token `--sd-font-*`
- Spacing: scala `--sd-spacing-*` con valori esatti
- Radius: scala `--sd-radius-*` con valori esatti
- Colori: dettaglio palette semantica light/dark con coppie di valori
- Motion: token `easing.standard`, `easing.emphasized`, `duration.*`

**Azione raccomandata**: ingestare `docs/principles.mdx`, `docs/roadmap.mdx` e selettivamente i file `docs/foundations/*.mdx` piu' rilevanti come raw sources.

**Stato**: CHIUSO

**Risolto:** 2026-07-17 — Ingested tutti i file MDX richiesti:
- `docs/principles.mdx` → integrato in `wiki/concepts/design-principles.md` (testo autoritativo diretto)
- `docs/roadmap.mdx` → `wiki/concepts/roadmap.md` (nuovo)
- `docs/foundations/typography.mdx` → `wiki/concepts/foundations/typography.md` (font stack per tutti i 12 temi)
- `docs/foundations/spacing.mdx` → `wiki/concepts/foundations/spacing.md` (scala numerica con valori px)
- `docs/foundations/colors.mdx` → `wiki/concepts/foundations/colors.md` (catalogo token semantico completo)
- `docs/foundations/radius.mdx` → `wiki/concepts/foundations/radius.md` (token e valori per tema)
- `docs/foundations/tokens.mdx` → `wiki/concepts/foundations/tokens.md` (pipeline CSS, token motion MD3)
- `docs/foundations/themes.mdx` → `wiki/concepts/foundations/themes.md` (token chiave per tutti i 12 temi)
- `docs/foundations/accessibility-and-motion.mdx` → `wiki/concepts/foundations/accessibility-and-motion.md`
- `docs/foundations/icons.mdx` → integrato in `wiki/concepts/icon-system.md`

---

## GAP-005 — docs/registry-model-1.md e docs/shadcn-integration.md non ingested

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.9 FINDING MINORE #8
**Priorita'**: P4 (Nice to have)

Due documenti tecnici di valore non ingested nella wiki:

- `docs/registry-model-1.md` — architettura registry Model 1: struttura blocchi, `registryDependencies`, naming convention
- `docs/shadcn-integration.md` — guida completa integrazione shadcn/ui: theming, token bridge, `shadcn.css`

**Azione raccomandata**: ingestare come raw sources in una sessione successiva.

**Stato**: CHIUSO

**Risolto:** 2026-07-17 — Entrambi i documenti ingested direttamente:
- `docs/registry-model-1.md` → `wiki/concepts/registry-model-1.md` (flusso consumer, namespace @solids, blocchi CLI, workflow manutentori)
- `docs/shadcn-integration.md` → `wiki/concepts/shadcn-integration.md` (setup rapido, 12 temi, token CSS, mapping shadcn vars, utility sd-*)

---

## GAP-006 — Motion: durata + easing vs molle M3 Expressive

**Data**: 2026-11-26
**Fonte**: raw/2026-11-26-material-design-novita-2026.md §9 (osservazione, non verificata a fondo)
**Priorita'**: P2 (Importante)

I token motion di soli-ds (`--sd-easing-standard`, `--sd-easing-emphasized-*`, `--sd-duration-*`), dichiarati «allineati a M3», seguono il sistema **durata + easing**. M3 Expressive lo ha sostituito con il motion a molle (schemi expressive/standard, token `spring.{fast|default|slow}.{spatial|effects}`). L'allineamento dichiarato si riferisce al sistema precedente. Vedi [[material-3-expressive-2026]] §4.

**Azione raccomandata**: confronto mirato prima di qualunque modifica; decidere se mantenere durata+easing (riformulando «allineato a M3») o introdurre un'equivalenza a molle sul web. Il refactor del codice non e' ancora fatto (altra sessione).

**Stato**: CHIUSO

**Risolto:** 2026-11-26 — 3.0.0 (EP-002 / US-003): `.sd-transition`, `.sd-transition-fast`, `.sd-transition-emphasized` (= molle slow) e `.sd-link` usano le molle M3 (`--sd-motion-spring-*`): spatial su transform, effects su colore/ombra/opacita'. In `base.css`, con reduced motion, una `transition-timing-function` unica (`--sd-motion-spring-fast-effects-easing`) evita che il colore erediti la curva spatial con overshoot (difetto trovato in Chromium, presente anche in 2.1.0 su `.sd-motion*`). `--sd-duration-*` e `--sd-easing-*` restano come fallback. In 2.x erano durata + easing. Migrazione: README §Migrazione 2.x → 3.0 (`data-motion="standard"` per meno rimbalzo).[^src: src/css/utilities.css §Transition (M3 Expressive springs, since 3.0.0)][^src: src/css/base.css §prefers-reduced-motion: reduce][^src: README.md §Migrazione 2.x → 3.0] Fuori da questa chiusura: GAP-010, GAP-011.

**Storico — aggiornamento 2026-11-26 (US-002, 2.1.0)** — aggiunti i 12 token ufficiali molla→cubic-bezier (`base.motion.expressive/standard`), gli alias `--sd-motion-spring-<fast|default|slow>-<spatial|effects>-<easing|duration>` (schema expressive di default, `[data-motion="standard"]` per lo standard), le utility `.sd-motion*` e `ease-sd-*` in Tailwind v4; `--sd-duration-*`, `--sd-easing-*`, `.sd-transition*` invariati.[^src: src/tokens/base.json §motion] **Resta aperta**, come decisione del maintainer (breaking, major 3.0.0): portare i default `.sd-transition*` sulle molle.[^src: management/kanban/EP-002-allineamento-m3-expressive/US-002-token-m3-additivi/US-002.md §Decisioni aperte (maintainer)]

---

## GAP-007 — Radius: scala 8/12/16/20px vs scala raggi M3

**Data**: 2026-11-26
**Fonte**: raw/2026-11-26-material-design-novita-2026.md §9
**Priorita'**: P3 (Mantenibilita')

I passi semantici sm→xl di light/dark (8/12/16/20px) sono dichiarati «in linea con Material Design 3». La scala M3 attuale e' large 20dp, extra-large 32dp, extra-extra-large 48dp, piu' `full` (non piu' 50 %). Da riallineare solo se si vuole restare «in linea con M3». Vedi [[material-3-expressive-2026]] §5.

**Azione raccomandata**: confronto token-per-token con la scala M3; decisione umana se riallineare o dichiarare lo scarto.

**Stato**: CHIUSO

**Risolto:** 2026-11-26 — 3.0.0 (EP-002 / US-003): `--sd-radius-2xl` / `--sd-radius-3xl` = 28/32px in `base.json`, light/dark e `semantic.json`; nei temi nominati = corner M3 `extra-large` / `extra-large-increased` del tema. In 2.x erano 20/24px in tutti i temi. Migrazione: README §Migrazione 2.x → 3.0.[^src: src/tokens/base.json §radius][^src: src/tokens/themes/light.json §radius][^src: README.md §Migrazione 2.x → 3.0]

**Storico — aggiornamento 2026-11-26 (US-002, 2.1.0)** — aggiunta la scala `--sd-corner-*` a 10 gradi con valori M3 esatti su light/dark (0/4/8/12/16/20/28/32/48/full), declinata per tema; `--sd-radius-*` invariati.[^src: src/tokens/semantic.json §corner] **Resta aperta**, come decisione del maintainer (breaking, major 3.0.0): `--sd-radius-2xl` / `--sd-radius-3xl` da 20/24px a 28/32px.[^src: management/kanban/EP-002-allineamento-m3-expressive/US-002-token-m3-additivi/US-002.md §Decisioni aperte (maintainer)]

---

## GAP-008 — Spaziatura: scala `--sd-space-*` vs scala 8dp `spaceXXX` e target 48

**Data**: 2026-11-26
**Fonte**: raw/2026-11-26-material-design-novita-2026.md §9 (spaziatura «da confrontare»); target 48dp da §2.4
**Priorita'**: P3 (Mantenibilita')

M3 ha una scala lineare a 8dp (`space100 = 8dp`, token `spaceXXX` da space0 a space900) e la convenzione padding/gap/margin + posizione (padding e gap prima dei margin). soli-ds ha `--sd-space-0..64` con base 4px e alias xs..3xl, senza una convenzione equivalente documentata. In piu' il target minimo M3 e' 48×48 contro `--sd-layout-touch-target-min = 44px` (osservazione aggiuntiva, non nella sezione 9 della sorgente). Nota: i token `spaceXXX` esistono solo su Compose. Vedi [[material-3-expressive-2026]] §2-§3.

**Azione raccomandata**: confronto con le sezioni 2 della sorgente; valutare tabella di corrispondenza e convenzione padding/gap/margin.

**Stato**: CHIUSO

**Risolto:** 2026-11-26 — EP-002 / US-002: aggiunti `--sd-measurement-space0..space900` (18 token, valori M3); la scala `--sd-space-*` e' invariata.[^src: src/tokens/base.json §measurement] Target (2.1.0): `--sd-layout-touch-target-material` 48px e `.sd-touch-target-material` come opt-in, default 44px.[^src: management/kanban/EP-002-allineamento-m3-expressive/US-002-token-m3-additivi/US-002.md §Decisioni aperte (maintainer)] **Target: default 48px dalla 3.0.0** (EP-002 / US-003): `--sd-layout-touch-target-min` = 48px e `.sd-min-touch-target` 48×48; in 2.x era 44px. Migrazione: README §Migrazione 2.x → 3.0 (`:root { --sd-layout-touch-target-min: 44px; }` per tornare indietro).[^src: src/tokens/base.json §layout][^src: src/css/utilities.css §Touch target (Material 3: 48×48)][^src: README.md §Migrazione 2.x → 3.0]

---

## GAP-009 — Breakpoint: 600/840/1200/1600dp da confrontare

**Data**: 2026-11-26
**Fonte**: raw/2026-11-26-material-design-novita-2026.md §9 + §1.3
**Priorita'**: P3 (Mantenibilita')

M3 definisce cinque breakpoint (compact <600, medium 600–839, expanded 840–1199, large 1200–1599, extra-large >=1600dp) con pannelli consigliati. La wiki di soli-ds **non documenta breakpoint**: lo stato dei breakpoint nel codice e' da verificare. Vedi [[material-3-expressive-2026]] §1.

**Azione raccomandata**: verificare nel codice (Tailwind preset / token layout) i breakpoint effettivi e confrontarli con M3.

**Stato**: CHIUSO

**Risolto:** 2026-11-26 — EP-002 / US-002 (TSK-008..013): token `--sd-breakpoint-{compact,medium,expanded,large,extra-large}` = 0/600/840/1200/1600px e varianti Tailwind v4 `medium:` `expanded:` `large:` `extra-large:`; `sm..2xl` invariati; preset Tailwind v3 non toccato (legacy). Verificato da `tokens-sanity` e compilazione Tailwind v4.[^src: src/tokens/base.json §breakpoint][^src: src/css/tailwind.css §M3 breakpoints]

---

## GAP-010 — Typography emphasized M3 e layout scaffold non coperti

**Data**: 2026-11-26
**Fonte**: raw/2026-11-26-material-design-novita-2026.md §4, §1.2, §8; escluso dal perimetro di EP-002
**Priorita'**: P3 (Mantenibilita')

Il refactor 3.0.0 non copre: (a) la scala tipografica M3 a 30 stili (15 baseline + 15 **emphasized**) e l'adattamento all'altezza della scrittura; (b) il **layout scaffold** (bars, rails, panes, pannelli fixed/flexible, drag handle) come componenti. Sono stati aggiunti solo i token dei breakpoint. Vedi [[material-3-expressive-2026]] §1 e §6.

**Azione raccomandata**: decidere se la scala emphasized e lo scaffold entrano nel perimetro di soli-ds (nuova storia di EP-002 o epica separata).

**Stato**: CHIUSO

**Risolto:** 2026-11-26 — EP-003 (US-004, US-005), rilascio 3.1.0. (a) Scala tipografica: `--sd-typescale-<stile>-{font,size,line-height,tracking,weight}` e `--sd-typescale-emphasized-<stile>-*` (15 + 15 stili) con utility `.sd-type-<stile>[-emphasized]`; valori da `TypeScaleTokens.kt` di Compose Material 3 (m3.material.io carica i token da un servizio non leggibile), rem = sp/16.[^src: src/tokens/base.json §typescale][^src: src/css/utilities.css §Type scale M3 (15 baseline + 15 emphasized)] (b) Scaffold come **primitive CSS** (non componente React): `.sd-scaffold`, `.sd-pane*`, `.sd-hide-below-*` / `.sd-hide-from-*`.[^src: src/css/utilities.css §Layout scaffold M3 (bars → rails → panes)] Residui in GAP-012. Vedi [[foundations/layout-scaffold]] e [[foundations/typography]].

---

## GAP-011 — Overlay Tailwind (animate-in/out) ancora su `--sd-easing-ease-out`

**Data**: 2026-11-26
**Fonte**: coordinatore 2026-11-26 (3.0.0)
**Priorita'**: P3 (Mantenibilita')

Gli overlay in `src/css/tailwind.css` (`animate-in` / `animate-out`) usano ancora `--sd-easing-ease-out` e non sono stati migrati alle molle M3, mentre `.sd-transition*` e `.sd-link` lo sono dalla 3.0.0 (vedi GAP-006).

**Azione raccomandata**: valutare la migrazione a `ease-sd-*` / `--sd-motion-spring-*`, tenendo conto dell'overshoot su overlay.

**Stato**: CHIUSO

**Risolto:** 2026-11-26 — EP-003 (US-006), rilascio 3.1.0 (minor: cambio visibile, non di API). `animate-in` → molla spatial fast 350ms; `animate-out` → effects fast 150ms; accordion/collapsible → spatial dello schema standard 350ms. Le classi `duration-*` ed `ease-*` del componente restano prioritarie. Con reduced motion `base.css` forza `--tw-ease` senza overshoot.[^src: src/css/tailwind.css §Overlay motion (M3 springs)][^src: src/css/base.css §prefers-reduced-motion: reduce]

---

## GAP-012 — Residui M3: language height e scaffold avanzato

**Data**: 2026-11-26
**Fonte**: EP-003 (US-004, US-005), coordinatore 2026-11-26
**Priorita'**: P4 (Nice to have)

Fuori dal perimetro di EP-003 / 3.1.0: (a) l'adattamento dell'interlinea alla **language height** M3 (small/medium/large/extra large) non e' gestito; (b) lo scaffold non copre **drag handle**, pannelli **floating/docked** (*levitate*) e **reflow**. Vedi [[material-3-expressive-2026]] §1.4, §6.

**Azione raccomandata**: valutare solo su richiesta di un consumer; il drag handle richiederebbe JS (non nel perimetro CSS-first).

**Stato**: CHIUSO

**Risolto:** 2026-11-26 — EP-004 (US-007, TSK-021), rilascio **3.2.0** (in attesa del maintainer). (a) Language height: le utility `.sd-type-*` calcolano `line-height` come `calc(token × --sd-language-height)`, con categoria da `:lang()` o `data-language-height`; moltiplicatori 1 / 1.07 / 1.3 / 2.[^src: src/tokens/base.json §language-height][^src: src/css/utilities.css §Language height (M3)] (b) Drag handle: modulo `@soli92/solids/scaffold` con `attachPaneResize`.[^src: src/scaffold/pane-resize.ts §attachPaneResize] Levitate: `.sd-pane-floating`, `.sd-pane-docked`, `.sd-pane-adaptive`. Reflow: `.sd-panes-reflow-*`.[^src: src/css/utilities.css §Levitate: floating and docked panes] Evidenza (Chromium, `test:scaffold`, `tokens-sanity`): US-007 §AC.[^src: management/kanban/EP-004-residui-m3/US-007-scaffold-completo/US-007.md §AC1-AC4] Residui in GAP-013. Vedi [[foundations/layout-scaffold]], [[foundations/typography]].

---

## GAP-013 — Residui M3 dopo 3.2.0: token language height e componente scaffold

**Data**: 2026-11-26
**Fonte**: EP-004 (US-007), coordinatore 2026-11-26
**Priorita'**: P4 (Nice to have)

(a) I **token M3 per categoria di language height** non sono leggibili: si usano i moltiplicatori percentuali pubblicati da M3 (1 / 1.07 / 1.3 / 2), non i valori di riga per stile. (b) Lo scaffold non ha un **componente React**: restano le primitive CSS, il modulo `attachPaneResize` e, per React, il componente `Resizable` esistente. Inoltre `medium` e' **opt-in** (M3 lo consiglia come default) per non cambiare le pagine latine: le lingue non elencate restano a 1.

**Azione raccomandata**: rivalutare se M3 pubblica i token per categoria; componente React solo su richiesta di un consumer.

**Stato**: APERTO

---

## Findings gia' risolti (per riferimento storico)

### FINDING #1 — docs/wiki/ ghost schema con alwaysApply:true [RISOLTO]

**Data**: 2026-07-17
**Risolto**: 2026-07-17 — `docs/wiki/` eliminata integralmente (commit 87818cc o sessione contestuale). La Cursor rule `alwaysApply: true` che iniettava lo schema incompatibile e' rimossa.

### FINDING #2 — factory.config.yaml: description stale + content_share incompleto [RISOLTO]

**Data**: 2026-07-17
**Risolto**: 2026-07-17 — `factory.config.yaml` aggiornato: description → "SoliDS — Design system React (@soli92/solids)"; `source_repo_slug: "solids"`; `source_repo: "soli92/solids"`.
