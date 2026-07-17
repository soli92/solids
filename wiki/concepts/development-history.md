---
id: development-history
type: concept
title: "SoliDS — Storico sviluppo AI-assisted"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "AI_LOG.md §Overview del progetto"
  - "AI_LOG.md §Fasi di sviluppo (inferite dal history)"
  - "AI_LOG.md §Pattern ricorrenti identificati"
  - "AI_LOG.md §Tecnologie e scelte di stack"
  - "AI_LOG.md §Problemi tecnici risolti (inferiti)"
---

# SoliDS — Storico sviluppo AI-assisted

Memoria di sviluppo del progetto `@soli92/solids`, ricostruita dall'analisi della git history (58 commit). Cattura decisioni architetturali, pattern emersi, problemi risolti e lezioni apprese per fase.[^src: AI_LOG.md §Overview del progetto]

## Overview

| Dato | Valore |
|------|--------|
| Pacchetto npm | `@soli92/solids` |
| Periodo sviluppo | 2026-02-16 (`048e5de` first commit) → 2026-04-08 (`d9b4ca6`) |
| Numero commit | 58 stimati |
| Stack AI usato | Cursor — `d4f4a3d` + `.cursor/rules/agents-context.mdc` |
| Release npm | Fino a **1.7.0** (2026-04-24) |
| Storybook | GitHub Pages — [soli92.github.io/solids](https://soli92.github.io/solids/) |

Consumer documentati in README: `soli-dome`, `soli-agent`, `soli-prof`, `soli-dm-fe`, `casa-mia-fe`, `pippify/frontend`, `bachelor-party-claudiano` — tutti allineati a `^1.7.0`.[^src: AI_LOG.md §Overview del progetto]

---

## Fase 1 — Token semantici, palette, shadcn bridge

**Timeframe**: `048e5de` → `915db2c`

**Cosa e' stato fatto**: espansione palette e token, temi light/dark completi, generazione `shadcn.css`, build script, guida integrazione shadcn, README token reference.[^src: AI_LOG.md §Fasi di sviluppo (inferite dal history)]

**Decisione architetturale chiave**: map shadcn vars → SoliDS tokens come strategia di adozione (`915db2c`). Il bridge consente adozione incrementale senza fork manuale di ogni componente.

**Lezione appresa**: il bridge shadcn→SoliDS e' la fondamenta per la compatibilita' con l'intero ecosistema shadcn/ui.

---

## Fase 2 — Registry shadcn, Storybook, release npm

**Timeframe**: `0632416` → `71a3e36` / pipeline release `32851ea`–`214e1c8`

**Cosa e' stato fatto**: preset Tailwind, registry `@solids`, Storybook button showcase, fix CI `NODE_AUTH_TOKEN`, allineamento URL GitHub a `soli92`, deploy Storybook su GitHub Release, fix semantic-release plugins/order, casing nome pacchetto npm.[^src: AI_LOG.md §Fase 2 — Registry shadcn]

**Decisioni architetturali chiave**:
- **semantic-release** con changelog automatico e tag — il plugin `git` deve essere l'ultimo (`18aded4`)
- **Storybook** su **GitHub Pages** con `.nojekyll` (`10176dc`)
- **npm publish in CI** richiede `NODE_AUTH_TOKEN` esplicito in `setup-node` (`32851ea`)

---

## Fase 3 — Kit UI completo, temi fantasy/cyberpunk

**Timeframe**: `e275dd5` → `86e02fe`

**Cosa e' stato fatto**: full shadcn kit, stories interattive, temi fantasy/cyberpunk, set icone, fix Storybook/React dedupe (`76dbe03`).[^src: AI_LOG.md §Fase 3 — Kit UI completo]

**Decisione architetturale chiave**: temi **multi-brand** come cittadini first-class nel design system — ogni tema ridefinisce gli stessi token `--sd-*` con palette dedicata.

**Lezione appresa**: dedupe React in Storybook Vite evita errori di produzione noti (`76dbe03`).

---

## Fase 4 — Release 1.3.x–1.5.0, Turbopack, steampunk/MD3

**Timeframe**: `f22c134` → `d9b4ca6`

**Cosa e' stato fatto**: sanitize segmenti custom properties per Turbopack, allineamento `react-resizable-panels` v4, revert release errata, grant `workflows` scope per tag push, release 1.4.0/1.5.0 con temi steampunk/MD3; Node 22 tooling (`0154d15`).[^src: AI_LOG.md §Fase 4 — Release 1.3.x–1.5.0]

**Decisioni architetturali chiave**:
- Supporto **Turbopack** nel pipeline CSS: i nomi dei segmenti di custom properties devono essere sanitizzati (`f22c134`)
- **Steampunk** + **MD3** come linee visive documentate in Storybook (`6005609`, `d9b4ca6`)

**Lezione appresa**: una major release errata va revertata e la baseline semver riallineata (`9842ef6 revert: erroneous 1.1.0 release`).

---

## Fase 5 — Accessibilita', font Google, utility UX, test token (2026-04-24)

**Cosa e' stato fatto**:[^src: AI_LOG.md §Fase 5 — Accessibilita']
- Pagina **Foundations / Accessibility and Motion** con link a WCAG 2.2, MD3 Motion/Typography, Apple HIG
- Token `--sd-layout-touch-target-min`, `--sd-duration-emphasized`
- `base.css`: scroll-padding, scroll-behavior condizionato, `text-rendering`
- Utility: `.sd-min-touch-target`, `.sd-link`, `.sd-leading-*`, `.sd-transition-emphasized`
- Font **Inter** / **DM Sans** / **JetBrains Mono** su semantic e light/dark
- **Source Serif 4** (fantasy corpo), **Space Grotesk** (cyberpunk)
- Script `scripts/tokens-sanity.mjs` → `npm run test:tokens` dentro `npm test`
- Release **npm 1.7.0**

**Lezione appresa**: smoke test su JSON/CSS generato costa poco e blocca regressioni su merge token.

---

## Aggiornamento 2026-04-27 — Integrazione soli-prof

SoliDS e' in `CORPUS_REPOS` su [soli-prof](https://github.com/soli92/soli-prof). Flusso push: `https://soli-prof.vercel.app/api/webhooks/github` con re-ingest HMAC. I test locali `npm test` non dipendono da questo flusso.[^src: AI_LOG.md §Aggiornamento 2026-04-27]

---

## Aggiornamento 2026-04-29 — Brand assets e Storybook branding

- Pack brand icone Soli: varianti mono/gold/theme-aware in `src/icons/glyphs.tsx`
- Centralizzazione asset cross-repo in `docs/brand-assets/workspace-icons` (raw) e `workspace-icons-normalized` (naming `soli-icon-*`, `manifest.json`, `index.json`)
- `LogoLoader` e `LogoLoaderOverlay` (fullscreen, blur/message)
- Storybook branding: favicon/title/manager brand image/manifest Soli
- `scripts/tokens-sanity.mjs`: ora verifica anche brand assets[^src: AI_LOG.md §Aggiornamento 2026-04-29]

---

## Pattern ricorrenti

| Pattern | Descrizione |
|---------|-------------|
| Conventional commits | `feat:`, `fix:`, `chore(release): X [skip ci]` generati da bot |
| Ciclo release | fix CI → tag → publish npm → deploy Storybook |
| Documentazione README | Contract per consumer interni ed esterni |
| AGENTS.md + `.cursor/rules` | Standard di ecosistema per l'AI-assist |

[^src: AI_LOG.md §Pattern ricorrenti identificati]

---

## Tecnologie e stack

| Layer | Scelta |
|-------|--------|
| Framework componenti | React (Storybook Vite) |
| Styling | CSS variables semantiche, Tailwind preset |
| Compatibilita' | shadcn/ui variable mapping |
| Deploy | npm package; Storybook su GitHub Pages |
| Qualita' | `npm test` = `build` + `test:tokens` (sanity su `dist/`) + `build-storybook` |
| LLM runtime | Nessuno nel package runtime |

[^src: AI_LOG.md §Tecnologie e scelte di stack]

---

## Problemi tecnici risolti (con commit)

| Problema | Commit |
|----------|--------|
| semantic-release plugin order / missing plugins | `18aded4`, `f034751` |
| NPM auth in CI (`NODE_AUTH_TOKEN`) | `32851ea` |
| Turbopack + CSS custom properties (sanitize) | `f22c134` |
| react-resizable-panels v4 break | `8dce9c2` |
| Storybook production error #130 / dedupe React | `76dbe03` |
| Release semver baseline errata | `9842ef6 revert` |

[^src: AI_LOG.md §Problemi tecnici risolti (inferiti)]

---

## Debiti tecnici noti

- Breaking major su token/componenti richiede coordinamento con tutti i consumer elencati in README
- Storybook su GitHub Pages dipende dal workflow release — failure release = docs pubbliche stale
- `semantic-release` + changelog automatico: errori di configurazione hanno generato revert storici — monitorare permessi `workflows` sul token GitHub

---

## Commit notevoli (estratto)

| Hash | Messaggio |
|------|-----------|
| `d9b4ca6` | docs: refresh Storybook and foundations (steampunk, MD3, sidebar) |
| `6005609` | feat: steampunk theme, MD3 tokens, Storybook refresh v1.4.0 |
| `915db2c` | feat(css): add shadcn/ui compatibility layer |
| `e275dd5` | feat: full shadcn/ui kit, Storybook UI stories, registry solids-ui block |
| `0632416` | feat: tailwind preset, shadcn registry @solids |
| `76dbe03` | fix(storybook): dedupe React in Vite |
| `f22c134` | fix(build): sanitize CSS custom property segments for Turbopack |
| `32851ea` | fix(ci): pass NODE_AUTH_TOKEN |
| `18aded4` | fix(release): correct semantic-release plugin order |
| `048e5de` | chore: first commit |

[^src: AI_LOG.md §Appendice — Commit notevoli]

---

## Pagine correlate

- [[token-architecture]] — architettura token (base/semantic/temi)
- [[shadcn-integration]] — guida completa integrazione shadcn
- [[registry-model-1]] — registry Model 1 e namespace `@solids`
- [[brand-assets]] — brand assets centralizzati
- [[icon-system]] — sistema icone post-bonifica
