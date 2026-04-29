---

# AI Log — SoliDS (`@soli92/solids`)

Memoria di sviluppo AI-assisted. Annotazioni sui prompt, decisioni e pattern emersi costruendo questo progetto con il supporto di AI.

## Overview del progetto

**SoliDS** (pacchetto npm `@soli92/solids`): design system con **token** semantici (light/dark), layer di compatibilità **shadcn/ui**, preset **Tailwind**, **Storybook** su GitHub Pages, **semantic-release** per versioni npm, temi (fantasy, cyberpunk, **steampunk**, **90s-party**, sei temi **personaggio** ispirati a Ichigo / Vegeta / Zoro / Captain America / Sasuke / Inuyasha, MD3), doc **Accessibility and Motion** (WCAG/MD3/HIG), font stack **Inter** / **DM Sans** / **JetBrains Mono** (default) e affinamenti per fantasy/cyberpunk, script **`npm run test:tokens`** (`scripts/tokens-sanity.mjs`) nel flusso **`npm test`**, kit componenti e documentazione incrociata con consumer (soli-dome, soli-agent citati in README).

**Stack AI usato (inferito; aggiornato 2026-04-22)**: **Cursor** — `d4f4a3d` + `.cursor/rules/agents-context.mdc`. `package.json` / pipeline **semantic-release** / Storybook — nessun SDK LLM nel design system. README collega consumer (`b412550`).

**Periodo di sviluppo**: 2026-02-16 (`048e5de` first commit) → 2026-04-08 (`d9b4ca6` docs Storybook foundations).

**Numero di commit**: 58

---

## Aggiornamento 2026-04-27 — Soli Prof: webhook e documentazione incrociata

- **RAG / ingest**: SoliDS è in **`CORPUS_REPOS`** su [soli-prof](https://github.com/soli92/soli-prof). Documentato in **`AGENTS.md`** l’ingaggio **push** → `https://soli-prof.vercel.app/api/webhooks/github` (re-ingest, HMAC) e riferimenti a `setup-webhooks.sh` lato Soli Prof. I test locali `npm test` (token, Storybook, ecc.) **non** dipendono da quel flusso.

## Aggiornamento 2026-04-29 — Brand assets, loader e Storybook branding

- **Icone Soli**: introdotto pack brand con varianti mono/gold/theme-aware in `src/icons/glyphs.tsx` + stories dedicate.
- **Centralizzazione asset**: raccolta cross-repo in `docs/brand-assets/workspace-icons` (raw) e `workspace-icons-normalized` (naming `soli-icon-*`, `manifest.json`, `index.json`), con export typed (`index.js` + `index.d.ts`) generato in build.
- **Categoria Soli**: nuovo set `docs/brand-assets/soli-category-icons` con 5 categorie (`app-icon`, `apple-touch`, `favicon`, `logo`, `symbol`) in `svg/png` + `index.json`.
- **Loader UI**: aggiunti `LogoLoader` (default Soli 4:3 theme-aware, custom `svg/png`) e `LogoLoaderOverlay` (fullscreen, blur/message configurabili).
- **Storybook branding**: favicon/title/manager brand image/manifest Soli applicati in `.storybook/*` e static assets serviti via `staticDirs`.
- **Stories generate**: preset persistente per `logo-loader` in `scripts/ui-story-data.mjs`, così `npm run ui:stories` mantiene controlli realtime (`src`, `size`, `animation`, `durationMs`, `alt`).
- **Sanity test estesi**: `scripts/tokens-sanity.mjs` ora verifica anche completezza e presenza file per `workspace-icons-normalized` e `soli-category-icons`.

## Fasi di sviluppo (inferite dal history)

### Fase 1 — Token semantici, palette, shadcn bridge

**Timeframe**: `048e5de` → `915db2c` (shadcn compatibility layer).

**Cosa è stato fatto**: espansione palette e token, temi light/dark completi, `shadcn.css`, build script, guida integrazione shadcn, README token reference.

**Evidenza di AI-assist** (inferita):

- Commit molto granulari su file CSS/token con messaggi enciclopedici — compatibile con authoring assistito o template DS.

**Decisioni architetturali notevoli**:

- **Map shadcn vars → SoliDS tokens** come strategia di adozione (`915db2c`).

**Prompt chiave usati**

> **Prompt [inferito]**: "Espandi token semantici light/dark, genera `shadcn.css` e guida integrazione shadcn, aggiorna README token reference."
> *Evidenza*: `022b430`–`915db2c`, messaggi `feat(tokens)` / `feat(css)`.

**Lezioni apprese**

- **Bridge shadcn→SoliDS** consente adozione incrementale senza fork manuale di ogni componente (`915db2c`).

### Fase 2 — Registry shadcn, Storybook, release npm semantic-release

**Timeframe**: `0632416` → `71a3e36` / pipeline release `32851ea`–`214e1c8`.

**Cosa è stato fatto**: tailwind preset, registry `@solids`, Storybook button showcase, fix CI `NODE_AUTH_TOKEN`, allineamento URL GitHub a `soli92`, deploy Storybook su GitHub Release, fix semantic-release plugins/order, casing nome pacchetto npm.

**Evidenza di AI-assist** (inferita):

- Errori classici di **semantic-release** (ordine plugin, token npm) risolti in serie — tipico debugging assistito o documentazione ufficiale seguita al pixel.

**Decisioni architetturali notevoli**:

- **semantic-release** con changelog automatico e tag.
- **Storybook** su **GitHub Pages** con `.nojekyll` (`10176dc`).

**Prompt chiave usati**

> **Prompt [inferito]**: "Aggiungi preset Tailwind, registry `@solids`, Storybook showcase, fix CI NODE_AUTH_TOKEN, semantic-release con ordine plugin corretto."
> *Evidenza*: `0632416`, `32851ea`, `18aded4`, `f034751`, `b0e3dd9`.

**Lezioni apprese**

- **semantic-release**: il plugin **git** deve essere ultimo (`18aded4`).
- **npm publish in CI** richiede `NODE_AUTH_TOKEN` esplicito in `setup-node` (`32851ea`).

### Fase 3 — Kit UI completo, temi fantasy/cyberpunk, Storybook Pages

**Timeframe**: `e275dd5` → `86e02fe`.

**Cosa è stato fatto**: full shadcn kit, stories interattive, temi fantasy/cyberpunk, set icone, fix Storybook/React dedupe (`76dbe03`).

**Evidenza di AI-assist** (inferita):

- Volume e coerenza naming nei commit `feat:` UI.

**Decisioni architetturali notevoli**:

- Temi **multi-brand** come cittadini first-class nel design system.

**Prompt chiave usati**

> **Prompt [inferito]**: "Completa kit shadcn, stories interattive, temi fantasy/cyberpunk, set icone; fix dedupe React in Storybook Vite."
> *Evidenza*: `e275dd5`, `86e02fe`, `76dbe03`.

**Lezioni apprese**

- **Dedupe React** in Storybook Vite evita errori produzione noti (`76dbe03`).

### Fase 4 — Release 1.3.x–1.5.0, fix build Turbopack/Resizable, docs steampunk/MD3

**Timeframe**: `f22c134` fix Turbopack CSS → `d9b4ca6` docs Storybook steampunk/MD3/sidebar.

**Cosa è stato fatto**: sanitize segmenti custom properties per Turbopack, allineamento `react-resizable-panels` v4, revert release errata, grant `workflows` scope per tag push, release **1.4.0** / **1.5.0** con temi steampunk/MD3; AGENTS/Cursor e README consumer; Node 22 tooling (`0154d15`).

**Evidenza di AI-assist** (inferita):

- `d4f4a3d` menzione esplicita **Cursor** nella convenzione repo.

**Decisioni architetturali notevoli**:

- Supporto **Turbopack** nel pipeline CSS (`f22c134`).
- **Steampunk** + **MD3** come linee visive documentate in Storybook (`6005609`, `d9b4ca6`).

**Prompt chiave usati**

> **Prompt [inferito]**: "Sanifica segmenti CSS custom properties per Turbopack, allinea react-resizable-panels v4, documenta temi steampunk/MD3 in Storybook, bump release 1.4–1.5."
> *Evidenza*: `f22c134`, `8dce9c2`, `6005609`, `d9b4ca6`, `4b87298`.

**Lezioni apprese**

- **Turbopack** richiede sanitizzazione nomi segmenti variabili CSS (`f22c134`).
- **Major release errata** va revertata e riallineata la baseline semver (`9842ef6`).

### Fase 5 — Accessibilità, font Google, utility UX, test token (2026-04-24)

**Cosa è stato fatto**: pagina **Foundations / Accessibility and Motion** con link a WCAG 2.2, MD3 Motion/Typography, Apple HIG; token `--sd-layout-touch-target-min`, `--sd-duration-emphasized`; `base.css` (scroll-padding, scroll-behavior condizionato, `text-rendering`); utility `.sd-min-touch-target`, `.sd-link`, `.sd-leading-*` da token, `.sd-transition-emphasized`; font **Inter** / **DM Sans** / **JetBrains Mono** su semantic e light/dark; **Source Serif 4** (fantasy corpo), **Space Grotesk** (cyberpunk); due blocchi Google Fonts in `.storybook/preview-head.html`; script **`scripts/tokens-sanity.mjs`** e **`npm run test:tokens`** dentro **`npm test`**; README / AGENTS / roadmap / principles aggiornati.

**Lezioni**: smoke test su JSON/CSS generato costa poco e blocca regressioni su merge token; Storybook resta la superficie principale per doc foundations.

**Ecosistema (2026-04-24)**: release **npm 1.7.0**; repo consumer (soli-agent, soli-prof, soli-dome, soli-dm-fe, casa-mia-fe, pippify/frontend, bachelor-party-claudiano) allineati a **`^1.7.0`**, font in layout/HTML e piccoli test su `package.json`.

---

## Pattern ricorrenti identificati

- **Conventional commits** + `chore(release): X [skip ci]` generati da bot/release.
- **Ciclo release**: fix CI → tag → publish npm → deploy Storybook.
- **Documentazione README** come contract per consumer interni ed esterni.
- **AGENTS.md** + `.cursor/rules` come standard ecosistema.

---

## Tecnologie e scelte di stack

- **Framework**: libreria UI (React components), Storybook (Vite)
- **Styling**: CSS variables semantiche, Tailwind preset
- **Compatibilità**: shadcn/ui variable mapping
- **Deploy / distribuzione**: npm package; Storybook su GitHub Pages
- **Qualità**: `npm test` = `build` + `test:tokens` (sanity su `dist/`) + `build-storybook`
- **LLM integration**: nessuna nel package runtime

## Problemi tecnici risolti (inferiti)

1. **semantic-release plugin order / missing plugins**: `18aded4`, `f034751`.
2. **NPM auth in CI**: `32851ea`.
3. **Turbopack + CSS custom properties**: `f22c134`.
4. **react-resizable-panels v4 break**: `8dce9c2`.
5. **Storybook production error #130 / dedupe React**: `76dbe03`.
6. **Release semver baseline errata**: `9842ef6 revert: erroneous 1.1.0 release`.

---

## Appendice — Commit notevoli (estratto da `git log --oneline`)

Focus su release, CI, temi e fix infrastrutturali Storybook/npm.

- `d9b4ca6` docs: refresh Storybook and foundations (steampunk, MD3, sidebar)
- `4b87298` chore(release): 1.5.0 [skip ci]
- `6005609` feat: steampunk theme, MD3 tokens, Storybook refresh v1.4.0
- `d4f4a3d` chore: add AGENTS.md, README link, Cursor agents-context rule
- `b412550` docs: README completo + sezione Dove viene usato (soli-dome, soli-agent)
- `f22c134` fix(build): sanitize CSS custom property segments for Turbopack
- `8dce9c2` fix(ui): align Resizable with react-resizable-panels v4
- `76dbe03` fix(storybook): dedupe React in Vite to avoid production error #130
- `b0e3dd9` ci: deploy Storybook from Release workflow after semantic-release
- `e275dd5` feat: full shadcn/ui kit, Storybook UI stories, registry solids-ui block
- `0632416` feat: tailwind preset, shadcn registry @solids, Storybook button showcase
- `32851ea` fix(ci): pass NODE_AUTH_TOKEN for npm auth via setup-node
- `18aded4` fix(release): correct semantic-release plugin order (git must be last)
- `915db2c` feat(css): add shadcn/ui compatibility layer — maps shadcn vars to SoliDS tokens
- `048e5de` chore: first commit

---

## Punti aperti / note per il futuro

- **grep `TODO|FIXME|HACK|XXX`** in `src/`, `packages/`, `registry/`: nessun match prioritario in questa passata (campione workspace).
- **Roadmap temi**: nuove palette (es. oltre steampunk/MD3) non tracciate come issue in questo file.
- **Debito tecnico inferito**: breaking major su token/componenti richiede coordinamento con consumer elencati in README (soli-dome, soli-agent, …).
- **Debito tecnico inferito**: Storybook su GitHub Pages dipende da workflow release — failure release = docs pubbliche stale.
- **Debito tecnico inferito**: `semantic-release` + changelog automatico: errori di configurazione hanno generato revert storici (`9842ef6`) — monitorare permessi `workflows` su token GitHub.

---

> **Nota metodologica**: aggiornamento contenuti 2026-04-24 (Fase 5 a11y/font/test); completamento precedente 2026-04-22; allineare versione npm con tag dopo ogni release.

---

## Metodologia compilazione automatica

Completamento autonomo il **22 aprile 2026** (esteso **24 aprile 2026** per Fase 5) analizzando:

- **58+** commit (stima)
- **~15** file rilevanti (`package.json`, `CHANGELOG.md`, `AGENTS.md`, `scripts/tokens-sanity.mjs`, `docs/foundations/accessibility-and-motion.mdx`, workflow release/Storybook, `docs/shadcn-integration.md`, preset Tailwind, Storybook config)
- **0** TODO/FIXME rilevanti dal grep workspace limitato

**Punti di minore confidenza:**

- Copertura grep su tutto il monorepo (se presenti pacchetti multipli non aperti).
- Dettaglio interazioni consumer non lette file-per-file.

---
