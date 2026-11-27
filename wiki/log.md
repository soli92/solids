---
id: log
type: log
title: Wiki Log
status: draft
created: 2026-06-15
updated: 2026-07-17
---

# Wiki Log

`YYYY-MM-DD HH:MM | <agent> | <operazione> | <target> | <note>`

## Entries

2026-09-08 | docs-dev | upgrade v2.33 → v2.42 | .claude/ + factory.config.yaml + PATTERN.md + CLAUDE.md | 9 delta cumulativi additivi (v2.34..v2.42): Code Intelligence Stack EP-054 (§33), Semantic Purpose Layer EP-055 (§34), Wiki Keeper 2.0 EP-056 (§35), Ponytail Decision Ladder EP-057, MCP Server EP-058, Backport portale-servizi EP-059 (release-manager + tpm-reconcile + deep-functional-probe + statusline-ledger), Fleet Health EP-060 (§36 fleet-doctor + refactor-agent-skills), Session Observability EP-061+EP-062 (§37). Tutti opt-in default off. Backward compat totale v2.33.
2026-06-15 | docs-dev | bootstrap | solids | Factory minimale v2.21 scaffoldata per EP-019 design intelligence run v2.21.0.
2026-06-15 | docs-dev | TSK-001 done | wiki/concepts/design-system-overview.md | Overview scopo + architettura token + theming + consumer.
2026-06-15 | docs-dev | TSK-002 done | wiki/concepts/token-architecture.md | Struttura directory, naming base/semantici, come creare tema, CSS output.
2026-06-15 | docs-dev | TSK-003 done | wiki/concepts/component-inventory.md | Inventario 56 componenti categorizati per tipo.
2026-06-15 | docs-dev | TSK-004 done | design_&_architecture/token-naming-convention.md | Standard naming + critic pass 4 finding (R.N1..R.N4).
2026-06-15 | docs-dev | TSK-005 done | design_&_architecture/a11y-token-audit.md | WCAG AA audit coppie colore: 2 finding a rischio.
2026-06-15 | docs-dev | TSK-006 done | design_&_architecture/ep019-critic-report-solids.md | Critic report globale EP-019 sprint solids.
2026-06-15 | docs-dev | TSK-007 done | design_&_architecture/theme-spec-brutalist.md | Theme spec brutalist: zero radius, zero shadow, max contrast.
2026-07-17 | wiki-keeper | ingest | docs/raw/bonifica-repo-2026-07-17.txt | Bonifica repository 2026-07-17: 4 problemi critici risolti (icone duplicate, import path rotto, git corrotto, adapter Claude Code assente). Commit 87818cc. Pattern factory v2.33 post-bonifica.
2026-07-17 | wiki-keeper | create | wiki/incidents/bonifica-2026-07-17.md | Incident report bonifica: 4 incidenti, 18 artefatti prodotti, rischi residui. Status: closed.
2026-07-17 | wiki-keeper | create | wiki/decisions/da-001-icon-source-of-truth.md | DA-001: conservare glyphs-themed.tsx come source of truth icone tematiche.
2026-07-17 | wiki-keeper | create | wiki/decisions/da-002-icons-bridge-pattern.md | DA-002: bridge src/lib/icons/index.ts per compatibilita' registry shadcn.
2026-07-17 | wiki-keeper | create | wiki/decisions/da-003-gitignore-root-anchored.md | DA-003: pattern /solids/ root-anchored per non ignorare registry/solids/.
2026-07-17 | wiki-keeper | create | wiki/decisions/da-004-claude-worktrees-gitignored.md | DA-004: .claude/worktrees/ gitignored (checkout isolati Claude Code).
2026-07-17 | wiki-keeper | update | wiki/entities/soli-frames.md | Arricchita con frontmatter completo, descrizione piattaforma, flusso dispatch, invarianti R.CS1..R.CS4, stato factory solids.
2026-07-17 | wiki-keeper | update | wiki/index.md | Aggiunte sezioni Entities, Runbooks, Decisions, Incidents con tutti i riferimenti.
2026-07-17 | wiki-keeper | update | wiki/log.md | Aggiornato updated date + aggiunte entry ingest 2026-07-17.
2026-07-17 | wiki-keeper | ingest | docs/raw/analisi-repository-2026-07-17.txt | Analisi repository 2026-07-17: struttura docs/, 8 finding consistency check factory, mappa conoscenza emersa. Nuove pagine concept + gaps aperti.
2026-07-17 | wiki-keeper | create | wiki/concepts/design-principles.md | 6 principi SoliDS da principles.mdx (Token-first, Semantic over visual, Framework agnostic, SSOT, Progressive adoption, A11y by default). Status: draft.
2026-07-17 | wiki-keeper | create | wiki/concepts/icon-system.md | Sistema icone post-bonifica: SolidsIcon wrapper, glyphs/glyphs-themed, bridge @/lib/icons, icone tematiche, registry shadcn. Status: draft.
2026-07-17 | wiki-keeper | create | wiki/concepts/brand-assets.md | Brand assets docs/brand-assets/: soli-icons, soli-category-icons, workspace-icons, workspace-icons-normalized. Status: draft.
2026-07-17 | wiki-keeper | create | wiki/concepts/docs-structure.md | Anatomia docs/: foundations MDX (8 file), pipeline raw/inbox, roadmap stato corrente, doc root-level. Status: draft.
2026-07-17 | wiki-keeper | create | wiki/gaps.md | 5 gap aperti da analisi-repository-2026-07-17 (design_&_architecture/ misplaced, AI_LOG.md, AGENTS.md, MDX non ingested, registry/shadcn docs). 2 finding gia' risolti documentati.
2026-07-17 | wiki-keeper | update | wiki/index.md | Aggiunte 4 nuove pagine concepts (design-principles, icon-system, brand-assets, docs-structure).
2026-07-17 | wiki-keeper | ingest | AI_LOG.md | Storico 58 commit sviluppo AI-assisted: 5 fasi, decisioni architetturali, problemi risolti, pattern ricorrenti, integrazione soli-prof.
2026-07-17 | wiki-keeper | create | wiki/concepts/development-history.md | Storico sviluppo SoliDS: 5 fasi (token/shadcn bridge, registry/Storybook, kit UI/temi, Turbopack/steampunk, a11y/font/test), debiti tecnici, commit notevoli. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/registry-model-1.md | Architettura registry Model 1: flusso consumer, namespace @solids, blocchi shadcn CLI, workflow manutentori, alternative senza namespace.
2026-07-17 | wiki-keeper | create | wiki/concepts/registry-model-1.md | Registry Model 1: setup CSS/Tailwind/shadcn, blocchi @solids/solids-ui, build registry, sync-registry.mjs. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/shadcn-integration.md | Guida integrazione shadcn/ui: compatibility layer shadcn.css, setup Next.js, temi data-theme, token CSS variables, mapping shadcn vars, utility sd-*.
2026-07-17 | wiki-keeper | create | wiki/concepts/shadcn-integration.md | Integrazione shadcn/ui: setup rapido, 12 temi, solo-variables mode, mapping shadcn→SoliDS, classi utility. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/roadmap.mdx | Roadmap: stato attuale (token, test, CSS pipeline, Storybook, registry), prossimi step, visione DS.
2026-07-17 | wiki-keeper | create | wiki/concepts/roadmap.md | Roadmap SoliDS: completato (token, pipeline CSS, Storybook, registry shadcn), prossimi step a11y/framework/stories. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/typography.mdx | Tipografia: famiglie semantiche --sd-font-*, font per tutti i 12 temi, scale dimensioni/pesi, utility CSS.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/typography.md | Typography foundations: token --sd-font-*, font per tema (Inter/DM Sans/JetBrains default, Source Serif 4/Cinzel fantasy, ecc.), CDN Google Fonts. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/spacing.mdx | Spacing: scala numerica --sd-space-0..64, alias semantici, regole fondamentali.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/spacing.md | Spacing foundations: scala --sd-space-1 (4px) ... --sd-space-6 (24px), alias semantici, regole anti-arbitrary. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/colors.mdx | Colors: catalogo token semantico completo (text, bg, border, intent, icon, brand).
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/colors.md | Colors foundations: catalogo token semantico per gruppo (text, background, border, intent, icon, componenti). Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/radius.mdx | Radius: token --sd-radius-none..full, valori per tema, utility CSS, linee guida.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/radius.md | Border Radius foundations: token --sd-radius-*, valori --sd-radius-md per tema (4px cyberpunk/sasuke → 12px light/dark), utility. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/tokens.mdx | Tokens pipeline: struttura JSON (base/semantic/themes), ordine import CSS (variables→themes→shadcn→base→utilities), token motion MD3.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/tokens.md | Tokens pipeline: struttura dist/tokens/tokens.json, pipeline CSS 5-step, token easing/duration MD3. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/themes.mdx | Themes: 12 temi, token chiave per ciascuno (text/bg/primary/font/radius), attivazione data-theme, Tailwind dark:, CDN font.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/themes.md | Themes foundations: 12 temi con token chiave esatti, attivazione data-theme, comportamento prefers-color-scheme, CDN font. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/accessibility-and-motion.mdx | A11y e motion: WCAG 2.2/MD3/HIG, focus visibile, reduced-motion, touch target 44px, utility .sd-min-touch-target/.sd-link/.sd-transition-emphasized.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/accessibility-and-motion.md | A11y e Motion foundations: token layout.touch-target-min, utility motion, tabella riferimenti repo. Status: draft.
2026-07-17 | wiki-keeper | integrate | wiki/concepts/icon-system.md | Integrati docs/foundations/icons.mdx: px esatti size (16/20/24/32), gallery 24 icone base, tutti i componenti brand pack (mono/gold/theme-aware), custom icon pattern, esempi themed icons.
2026-07-17 | wiki-keeper | integrate | wiki/concepts/design-principles.md | Integrati docs/principles.mdx: testo autoritativo diretto per tutti e 6 i principi, riferimento a WCAG/MD3/HIG per principio A11y.
2026-07-17 | wiki-keeper | update | wiki/index.md | Aggiunte 4 nuove pagine concepts (development-history, registry-model-1, shadcn-integration, roadmap) + sezione Concepts/Foundations con 7 pagine. Aggiornata lista sources frontmatter.
2026-07-17 | wiki-keeper | close-gap | wiki/gaps.md | Chiusi: GAP-002 (AI_LOG.md ingested → development-history.md), GAP-004 (MDX foundations ingested), GAP-005 (registry-model-1.md + shadcn-integration.md ingested).

## [2026-11-11] upgrade | factory 2.42 → 2.45 (+ EP-090 dal branch feat/ep-090-mestiere-ui del master)

- **entry_type**: upgrade
- **trigger**: richiesta del maintainer: aggiornare all'ultima versione e abilitare le capability per testare EP-090
- **sources**: `tools/factory-upgrade-apply.py --meta-source <master>` (COPY 793, REPLACE 5, CONFLICT 148); backup `.factory-upgrade-backup/2.42-to-2.45-20261111-1511/`
- **files touched**: `.claude/`, `tools/`, `schemas/`, `adapters/cursor/templates/`, `PATTERN*.md`, `factory.config.yaml`
- **note**: i 150 conflitti NON erano personalizzazioni: 76 versioni upstream vecchie (blob presenti nella storia del master) e 74 conversioni Cursor dello scaffold v2.33 (`mdc:.cursor/...` dentro `.claude/`). Sostituiti dal master, originali in `conflitti/` del backup. Righe locali del PATTERN (40): testo upstream v2.27-v2.37, nessuna nota propria. Re-dry-run: COPY 0 REPLACE 0 CONFLICT 0. Accese: `topology: custom`, `ui_craft.*`, `code_quality.enabled`, `fe_correctness.functional_oracle.enabled`, `prototyping.enabled` + `variants: 3`. 6 ERROR di lint preesistenti (wiki content-share, EP-001).

## [2026-11-11] review | test delle capability EP-090 su soli-ds

- **entry_type**: review
- **trigger**: test delle capability di EP-090 del master sul design system
- **sources**: `code_quality/reports/motion-review-2026-11-11.md`, `code_quality/worst-case/2026-11-11-lista-membri/`, `output/prototypes/toast-notifica/index.html`
- **files touched**: `src/stories/lista-membri.{stories.tsx,fixtures.ts}`, report e screenshot in `code_quality/`, prototipo in `output/`, `vendor/`, correzioni del master alle skill EP-090
- **note**: proposte non applicate, sono decisioni di design. Motion: 23 finding (focus animato su ogni Tab, reduced-motion che azzera tutto, `origin-top-center` e `animate-caret-blink` senza CSS, `animate-in` con `ease` di default). Caso peggiore: 9 rotture (AvatarImage senza `object-cover`, email che esce a zoom 200%, troncamento silenzioso, badge a capo, nome mancante, iniziali con emoji, BiDi, 1284 righe senza virtualizzazione, plurale). Varianti del toast: Quieta / Pila / Banner, la scelta e' umana.

## [2026-11-13] upgrade | factory 2.45 → 2.46

- **entry_type**: upgrade
- **trigger**: richiesta del maintainer di aggiornare la flotta dopo EP-096 del master (perimetro unico installer/upgrade)
- **sources**: `tools/factory-upgrade-apply.py --prune-meta-only` dal master (main 6b0c0575 + fix/upgrade-gitattributes); classificazione dei CONFLICT per impronta git contro `git rev-list --all --objects` del master
- **files touched**: PATTERN.md e moduli (replace), 27 file di `.claude/` e `adapters/cursor/templates/` e `tools/tests/test_verify_vendor_multi.py` sostituiti dal master (tutti versioni storiche del master, nessuna personalizzazione; originali in `.factory-upgrade-backup/`), nuovi `tools/factory_scope.py`, `tools/tests/test_factory_scope.py`, `CAPABILITIES.md` per derivata, `.gitattributes`, `analytics/` (file di framework), rimossi `.claude/commands/release.md` e `tools/tests/test_installer.py` (solo meta-framework), `factory.config.yaml`
- **note**: in `factory.config.yaml` il blocco `factory:` diventa `project:` (lo schema e `smlib.factory_name` leggono `project.name`: prima il nome non si leggeva) e si toglie `wiki_purpose:` (chiave inesistente nel master, spenta, nessun lettore). Prima falliva `test_config_schema_coverage` anche su main; ora `pytest tools/tests` → 1174 passed, 25 skipped. Il driver di merge di `wiki/log.md` si registra in locale con `python3 tools/vcs/install_factory_hooks.py`.

## [2026-11-26] ingest | raw/2026-11-26-material-design-novita-2026.md

- **entry_type**: ingest
- **trigger**: richiesta del maintainer: ingest del report sulle novita' di Material Design (M3 Expressive) prima del confronto con i token di soli-ds
- **sources**: `raw/2026-11-26-material-design-novita-2026.md`
- **files touched**: creati `wiki/sources/material-design-novita-2026-11-26.md` e `wiki/concepts/material-3-expressive-2026.md`; aggiunti rimandi e note «M3 pre-Expressive» (sezioni Aggiornamenti) in `wiki/concepts/foundations/{spacing,radius,accessibility-and-motion,tokens,typography}.md` e `wiki/concepts/design-principles.md`; `wiki/gaps.md` (GAP-006..GAP-009 aperti); `wiki/index.md`
- **note**: nessun valore di token modificato, il refactor del codice non e' fatto. Gap aperti dagli scarti della sezione 9 (motion durata+easing vs molle, raggi, spaziatura, breakpoint). La sorgente dichiara la sezione 9 «non verificata a fondo»; il target 48 vs 44px (GAP-008) e' un'osservazione aggiunta dal keeper, non della sorgente. `wiki/purpose.md` descrive il meta-framework, non soli-ds: non applicato come contesto.

## [2026-11-26] develop | EP-002 US-002: token Material 3 Expressive additivi (TSK-008..013)

- **entry_type**: develop
- **trigger**: richiesta del maintainer di allineare soli-ds alle direttive M3 Expressive dopo l'ingest del report
- **sources**: `raw/2026-11-26-material-design-novita-2026.md`; tabella ufficiale molla→curva per il web e scala corner lette da m3.material.io/styles/motion/overview/specs e /styles/shape/corner-radius-scale
- **files touched (dichiarati)**: `src/tokens/base.json` (measurement, breakpoint, motion, layout.touch-target-material), `src/tokens/semantic.json` (corner, motion.spring), `src/tokens/themes/*.json` (12 temi, blocco corner), `scripts/build.mjs` (blocco `[data-motion="standard"]`), `src/css/utilities.css` (.sd-motion*, .sd-corner-*, .sd-touch-target-material), `src/css/tailwind.css` (ease-sd-*, @theme breakpoint), `scripts/tokens-sanity.mjs`, `docs/foundations/{spacing,radius,accessibility-and-motion,tokens}.mdx`, `management/kanban/EP-002-*`, `management/kanban/sprint.md`
- **verifica**: dist confrontato con la fotografia pre-modifica (0 righe rimosse, 0 token cambiati, 192 aggiunti); `npm run test:tokens` con i nuovi controlli M3, mutazione rossa (corner light 30px → FAIL); Chromium sul CSS generato (schema expressive/standard, corner per tema, 48px, reduced motion); `@tailwindcss/node` compila medium:/expanded:/large:/extra-large: e ease-sd-*; `npm test` exit 0
- **note**: tutto additivo, release minor. Restano decisioni del maintainer (breaking, 3.0.0): default `.sd-transition*` sulle molle, `--sd-radius-2xl/3xl` 20/24 → 28/32, target 44 → 48. Preset Tailwind v3 non toccato (legacy). Non coperti: typography emphasized (15 stili), layout scaffold come componenti
- **rilascio**: `@soli92/solids@2.1.0` pubblicata su npm (dist-tag latest) e GitHub Release v2.1.0 dal run Release 45818317065 sul commit 7d8071c, su autorizzazione del maintainer

## [2026-11-26] develop | EP-002 US-003: default allineati a M3 Expressive, rilascio 3.0.0 (TSK-014..017)

- **entry_type**: develop
- **trigger**: decisione del maintainer: eseguire in una major le tre «Decisioni aperte» di US-002
- **files touched (dichiarati)**: `src/tokens/base.json`, `src/tokens/semantic.json`, `src/tokens/themes/*.json` (radius 2xl/3xl per tema, touch target 48), `src/css/utilities.css` (.sd-transition*, .sd-link, .sd-min-touch-target), `src/css/base.css` (curva unica con reduced motion), `scripts/tokens-sanity.mjs`, `README.md` (migrazione 2.x → 3.0), `docs/foundations/{radius,accessibility-and-motion,tokens}.mdx`, kanban US-003 e TSK-014..017, EP-002 chiusa
- **verifica**: diff del dist contro la 2.1.0 limitato ai tre cambi; `tokens-sanity` con mutazione rossa; Chromium (raggi per tema, 48px, curve delle transizioni, schema standard, reduced motion); `npm test` exit 0
- **difetto trovato**: con reduced motion il colore ereditava la curva spatial con overshoot (anche `.sd-motion*` in 2.1.0); corretto in `base.css`
- **rilascio**: `@soli92/solids@3.0.0` su npm (latest) e GitHub Release v3.0.0 dal run Release 45820336531 sul commit e119b5a, su decisione del maintainer
- **note**: restano GAP-010 (typography emphasized, scaffold come componenti) e GAP-011 (overlay di `tailwind.css` ancora su `--sd-easing-ease-out`)

## [2026-11-26] develop | EP-003: scala tipografica M3, scaffold, overlay sulle molle (TSK-018..020)

- **entry_type**: develop
- **trigger**: richiesta del maintainer di chiudere GAP-010 e GAP-011
- **sources**: `TypeScaleTokens.kt` di Compose Material 3 (androidx-main), perche' m3.material.io carica i token da un servizio non leggibile; pagine m3.material.io su scaffold, breakpoint e applying type
- **files touched (dichiarati)**: `src/tokens/base.json` (typescale), `src/css/utilities.css` (type scale, scaffold), `src/css/tailwind.css` (overlay, accordion), `src/css/base.css` (`--tw-ease` con reduced motion), `scripts/tokens-sanity.mjs`, `docs/foundations/{typography,layout,accessibility-and-motion}.mdx`, `README.md`, kanban EP-003 (US-004..006, TSK-018..020)
- **verifica**: diff del dist contro la 3.0.0; `tokens-sanity` con due mutazioni rosse (peso emphasized, curva di uscita); Chromium a 400/900/1700px (scaffold, visibilita' per breakpoint, tipografia, variabili degli overlay); `npm test` exit 0 con la pagina Storybook «Layout scaffold»
- **difetto trovato**: le utility tipografiche leggevano `--sd-typescale-*-font`, risolto su `:root`, quindi un `[data-theme]` annidato non cambiava font (fantasy restava DM Sans); ora leggono `--sd-font-heading`/`--sd-font-body`, coperto da `tokens-sanity`
- **note**: commit c0a1ee2 non ancora pushato (il push pubblica la 3.1.0 su npm: in attesa del maintainer). Residui in GAP-012: language height, drag handle, levitate, reflow

## [2026-11-26] develop | EP-004: language height, drag handle, levitate, reflow (TSK-021, GAP-012)

- **entry_type**: develop
- **trigger**: richiesta del maintainer di chiudere GAP-012
- **files touched (dichiarati)**: `src/scaffold/{pane-resize,index}.ts` (nuovo export `./scaffold` con tipi), `scripts/build.mjs` (transpile + dichiarazioni), `package.json` (export, `test:scaffold`), `src/tokens/base.json` (`language-height`), `src/css/utilities.css`, `scripts/{tokens-sanity,scaffold-test}.mjs`, `docs/foundations/{layout,typography}.mdx`, `README.md`, kanban EP-004
- **verifica**: `test:scaffold` sulla logica pura dal dist (due attese sbagliate nel test, corrette: 385 e 386 sono fuori soglia da entrambe le larghezze); `tokens-sanity`; Chromium via HTTP locale (interlinea per lingua, tastiera, trascinamento con aggancio 405 → 412, persistenza dopo reload, focus del dialog, adaptive e reflow a 400/700/900/1300px); `npm test` exit 0; dist contro la 3.1.0: cambiano solo le 30 line-height `.sd-type-*`, identiche per il latino
- **note**: commit 1bbdc50 non pushato in attesa del maintainer (rilascio 3.2.0). Residui in GAP-013

## [2026-11-26] develop | EP-005: interlinee M3 ufficiali, scaffold React, difetti dalla plancia (TSK-022, TSK-023)

- **entry_type**: develop
- **trigger**: richiesta del maintainer di chiudere GAP-013; difetti segnalati dalla sessione della plancia del master adottando soli-ds 3.1.0 (LICENSE vuoto, contrasto dei colori di stato e di border-strong)
- **sources**: database token di Material caricato da m3.material.io (`_dsm/data/dsdb-m3/2026-11-19_06-20-01/TYPOGRAPHY.*.json`), trovato registrando le richieste di rete della pagina: smentisce che i valori per categoria non fossero leggibili
- **files touched (dichiarati)**: commit e2a9fa3 (base.json typescale-language, utilities.css, scaffold.tsx, lib/pane-resize.ts, storia, registry, sync-registry, tokens-sanity, docs typography/layout) e 083c9a0 (LICENSE, semantic.json e 12 temi con intent-*-text e border-strong, tailwind.css, docs colors); kanban EP-005
- **verifica**: `tokens-sanity` (tabella ufficiale 15×4, contrasto calcolato in JS su 12 temi, LICENSE); `tsc --noEmit` sui file nuovi; storia React in Chromium (400/900/1700px, tastiera, nessun errore); `npm test` exit 0; dei token cambiano solo i tre `border-strong` (le righe `info-border` solo per la virgola)
- **difetto trovato in verifica**: in reflow verticale il pannello ridimensionabile aveva altezza fissa 360px (presente in 3.2.0), corretto
- **rilascio**: `@soli92/solids@3.3.0` dal run Release 45850855036, su autorizzazione del maintainer

## [2026-11-27] develop | EP-006: spessori di bordo e anello di focus M3 (TSK-024)

- **entry_type**: develop
- **trigger**: richiesta della plancia del master (usava `--sd-measurement-space25/50` per i bordi); decisione del maintainer del 27/11: anello di focus a 3px come M3
- **sources**: DSDB di m3.material.io (`TOKEN_TABLE`): `md.comp.button.*.outlined.outline.width` 1/2/3dp, `md.sys.state.focus-indicator.thickness` 3dp e `outer-offset` 2dp
- **files touched (dichiarati)**: commit 8ef7cfe (base.json border-width e focus-indicator, utilities.css, base.css, tokens-sanity, docs tokens e accessibility-and-motion, README); kanban EP-006 (US-010, TSK-024), sprint.md
- **verifica**: `tokens-sanity` (valori e nessuno spessore scritto a mano); `npm test` exit 0; Chromium contro il pacchetto 3.3.0 scaricato da npm: bordi identici, cambiano solo l'anello di focus (2 → 3px) e l'anello interno della maniglia dello scaffold (2 → 3px)
- **note**: sospeso il 26/11 sera su branch locale, ripreso e chiuso il 27/11; il commit wip e' stato sostituito da 8ef7cfe. Rilascio 3.4.0 in attesa dell'ok al push
