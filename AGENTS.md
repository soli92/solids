# AGENTS.md — contesto per assistenti AI

Riassunto operativo per **SoliDS** (design system: token, CSS, Storybook, registry shadcn). Dettaglio e release: **`CHANGELOG.md`**, **`README.md`**. Stato file: **`git status`**.

**Aggiornato:** 2026-04-24

## Repo

Pacchetto **`@soli92/solids`**, Node **22+**, build in `dist/`. Documentazione interattiva: **Storybook** (`npm run storybook`). Temi: `light`, `dark`, `fantasy`, `cyberpunk`, `90s-party`, `steampunk`, più `captain-america`, `ichigo`, `inuyasha`, `sasuke`, `vegeta`, `zoro` (`data-theme`). Doc **Foundations / Accessibility and Motion** (WCAG/MD3/HIG + utility `sd-min-touch-target`, `sd-link`). Font default: Inter, DM Sans, JetBrains Mono; fantasy/cyberpunk con Source Serif 4 / Space Grotesk. Integrazione shadcn: `docs/shadcn-integration.md`, `docs/registry-model-1.md`.

## Cosa fare dopo (checklist)

1. **Modifiche a token/CSS** — `npm run build`; `npm run test:tokens` (o `npm test`: build + sanity token + `build-storybook`); verificare Storybook dopo cambi UI.
2. **Release npm** — flusso `semantic-release` / CI del repo; allineare versione in `CHANGELOG.md` se aggiorni a mano.
3. **Registry** — dopo cambi a componenti esposti: `npm run registry:sync` / `registry:build` come da README.

## Comandi

`npm run build` · `npm run test:tokens` · `npm test` · `npm run storybook` · `npm run build-storybook` · `npm run registry:sync` · `npm run registry:build`

## File utili

`README.md` · `CHANGELOG.md` · `AI_LOG.md` · `docs/foundations/accessibility-and-motion.mdx` · `docs/shadcn-integration.md` · `docs/registry-model-1.md` · `scripts/tokens-sanity.mjs` · `registry/`

## Regole per l’agente

- Non committare segreti; `.npmrc` in repo forza registry pubblico e `tag=latest`.
- Dopo cambi rilevanti a API pubbliche o token, aggiornare **CHANGELOG** / docs come da convenzione del repo.
