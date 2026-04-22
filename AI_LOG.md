---

# AI Log — SoliDS (`@soli92/solids`)

Memoria di sviluppo AI-assisted. Annotazioni sui prompt, decisioni e pattern emersi costruendo questo progetto con il supporto di AI.

## Overview del progetto

**SoliDS** (pacchetto npm `@soli92/solids`): design system con **token** semantici (light/dark), layer di compatibilità **shadcn/ui**, preset **Tailwind**, **Storybook** su GitHub Pages, **semantic-release** per versioni npm, temi (fantasy, cyberpunk, **steampunk**, **90s-party**, MD3), kit componenti e documentazione incrociata con consumer (soli-dome, soli-agent citati in README).

**Stack AI usato (inferito)**: **Cursor** — `d4f4a3d chore: add AGENTS.md, README link, Cursor agents-context rule`. Commit `b412550 docs: README completo + sezione Dove viene usato (soli-dome, soli-agent)` lega esplicitamente il DS agli assistiti da documentazione multi-repo.

**Periodo di sviluppo**: 2026-02-16 (`048e5de` first commit) → 2026-04-08 (`d9b4ca6` docs Storybook foundations).

**Numero di commit**: 58

---

## Fasi di sviluppo (inferite dal history)

### Fase 1 — Token semantici, palette, shadcn bridge

**Timeframe**: `048e5de` → `915db2c` (shadcn compatibility layer).

**Cosa è stato fatto**: espansione palette e token, temi light/dark completi, `shadcn.css`, build script, guida integrazione shadcn, README token reference.

**Evidenza di AI-assist** (inferita):

- Commit molto granulari su file CSS/token con messaggi enciclopedici — compatibile con authoring assistito o template DS.

**Decisioni architetturali notevoli**:

- **Map shadcn vars → SoliDS tokens** come strategia di adozione (`915db2c`).

**Prompt chiave usati**: > [TODO da compilare manualmente]

**Lezioni apprese**: > [TODO da compilare manualmente]

### Fase 2 — Registry shadcn, Storybook, release npm semantic-release

**Timeframe**: `0632416` → `71a3e36` / pipeline release `32851ea`–`214e1c8`.

**Cosa è stato fatto**: tailwind preset, registry `@solids`, Storybook button showcase, fix CI `NODE_AUTH_TOKEN`, allineamento URL GitHub a `soli92`, deploy Storybook su GitHub Release, fix semantic-release plugins/order, casing nome pacchetto npm.

**Evidenza di AI-assist** (inferita):

- Errori classici di **semantic-release** (ordine plugin, token npm) risolti in serie — tipico debugging assistito o documentazione ufficiale seguita al pixel.

**Decisioni architetturali notevoli**:

- **semantic-release** con changelog automatico e tag.
- **Storybook** su **GitHub Pages** con `.nojekyll` (`10176dc`).

**Prompt chiave usati**: > [TODO da compilare manualmente]

**Lezioni apprese**: > [TODO da compilare manualmente]

### Fase 3 — Kit UI completo, temi fantasy/cyberpunk, Storybook Pages

**Timeframe**: `e275dd5` → `86e02fe`.

**Cosa è stato fatto**: full shadcn kit, stories interattive, temi fantasy/cyberpunk, set icone, fix Storybook/React dedupe (`76dbe03`).

**Evidenza di AI-assist** (inferita):

- Volume e coerenza naming nei commit `feat:` UI.

**Decisioni architetturali notevoli**:

- Temi **multi-brand** come cittadini first-class nel design system.

**Prompt chiave usati**: > [TODO da compilare manualmente]

**Lezioni apprese**: > [TODO da compilare manualmente]

### Fase 4 — Release 1.3.x–1.5.0, fix build Turbopack/Resizable, docs steampunk/MD3

**Timeframe**: `f22c134` fix Turbopack CSS → `d9b4ca6` docs Storybook steampunk/MD3/sidebar.

**Cosa è stato fatto**: sanitize segmenti custom properties per Turbopack, allineamento `react-resizable-panels` v4, revert release errata, grant `workflows` scope per tag push, release **1.4.0** / **1.5.0** con temi steampunk/MD3; AGENTS/Cursor e README consumer; Node 22 tooling (`0154d15`).

**Evidenza di AI-assist** (inferita):

- `d4f4a3d` menzione esplicita **Cursor** nella convenzione repo.

**Decisioni architetturali notevoli**:

- Supporto **Turbopack** nel pipeline CSS (`f22c134`).
- **Steampunk** + **MD3** come linee visive documentate in Storybook (`6005609`, `d9b4ca6`).

**Prompt chiave usati**: > [TODO da compilare manualmente]

**Lezioni apprese**: > [TODO da compilare manualmente]

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

> [TODO da compilare manualmente: roadmap temi, breaking changes major, adozione nei consumer]

---

> **Nota metodologica**: questo file è stato generato retroattivamente analizzando la history del repo. Le sezioni con `> [TODO da compilare manualmente]` richiedono la memoria del developer e non possono essere inferite dalla sola analisi automatica. Integra progressivamente con annotazioni manuali mentre lavori alle prossime fasi del progetto.

---
