# SoliDS

**SoliDS** è il design system personale di [soli92](https://github.com/soli92) —
una fondamenta **agnostica** basata su **design tokens** e **CSS variables**,
pronta all'uso con qualsiasi framework web e compatibile con **shadcn/ui**.

Contesto operativo per assistenti AI: **[`AGENTS.md`](./AGENTS.md)**.

**Storybook** (documentazione interattiva + esempi UI) è pubblicato su **[GitHub Pages](https://soli92.github.io/solids/)** dopo ogni release su npm. Per la prima volta sul repo: *Settings → Pages → Build and deployment: GitHub Actions*.

---

## Documentazione

| Dove | Contenuto |
|------|-----------|
| **[Storybook (online)](https://soli92.github.io/solids/)** | Foundations (token, colori, spacing, tipografia, radius, temi), *Getting Started*, *Design Principles*, *Roadmap*, story UI (es. Button) |
| **Questo repo, `docs/*.mdx`** | Stesse pagine narrative servite da Storybook in locale (`npm run storybook`) |
| **[`docs/shadcn-integration.md`](./docs/shadcn-integration.md)** | Integrazione completa Tailwind + shadcn/ui + temi |
| **[`docs/registry-model-1.md`](./docs/registry-model-1.md)** | Registry `@solids`, `registry/r/`, CLI `shadcn add` |

In sviluppo, dopo `npm install`: `npm run storybook` avvia la documentazione su `localhost` (prima viene rigenerato il CSS Tailwind di anteprima con `build:storybook-css`).

### Node e npm

- **Node.js 22+** consigliato (file **`.nvmrc`**, workflow CI su GitHub Actions).
- **`.npmrc`** in repo: `registry=https://registry.npmjs.org/` e `tag=latest` per evitare dist-tag globali non compatibili con il registry pubblico.

---

## Cosa include

| Layer | File | Descrizione |
|-------|------|-------------|
| 🎨 Tokens | `dist/tokens/tokens.json` | Palette completa, spacing, tipografia, shadow, radius, easing, z-index |
| 🔤 Variables | `dist/css/variables.css` | CSS vars `--sd-*` per tema light (default) |
| 🌗 Themes | `dist/css/themes.css` | Override **dark**, **fantasy**, **cyberpunk**, **90s-party**, **steampunk** + `prefers-color-scheme: dark` quando `data-theme` non è impostato |
| 🔗 shadcn | `dist/css/shadcn.css` | Mapping variabili shadcn/ui → token SoliDS |
| 🧱 Base | `dist/css/base.css` | Reset minimale, body, focus-visible, box-sizing |
| 🛠️ Utilities | `dist/css/utilities.css` | Classi utility `sd-*` (flex, spacing, colori, badge, card…) |
| 📦 Index | `dist/css/index.css` | Entrypoint unico che importa tutto nell'ordine corretto |

---

## Installazione

```bash
npm install @soli92/solids
```

---

## Quick Start

### Con Tailwind + shadcn/ui (Next.js, Vite…)

**Consigliato:** usa il **preset Tailwind** del pacchetto così tema, colori shadcn, font e shadow restano allineati ai token in un solo punto.

```css
/* globals.css */
@import "@soli92/solids/css/index.css";

@tailwind base;
@tailwind components;
@tailwind utilities;
```

```js
// tailwind.config.js
module.exports = {
  presets: [require("@soli92/solids/tailwind-preset")],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
};
```

Serve anche `tailwindcss-animate` (dipendenza tipica di shadcn):

```bash
npm install tailwindcss-animate
```

Poi inizializza shadcn e aggiungi i componenti: **tutto il kit** con `npx shadcn@latest add @solids/solids-ui` oppure singoli item (`@solids/solids-button`, …). I componenti usano le variabili `--background`, `--primary`, ecc., già mappate da SoliDS. Esempio `components.json`: [templates/components.json.example](./templates/components.json.example).

➡️ Guida completa: [docs/shadcn-integration.md](./docs/shadcn-integration.md)

### Senza framework

```html
<link rel="stylesheet" href="node_modules/@soli92/solids/dist/css/index.css" />
```

---

## Esportazioni disponibili

```js
import tokens from "@soli92/solids/tokens";           // tokens.json
import "@soli92/solids/css/index.css";                // tutto
import "@soli92/solids/css/variables.css";            // solo vars
import "@soli92/solids/css/themes.css";               // override temi + OS dark
import "@soli92/solids/css/shadcn.css";               // solo shadcn layer
import "@soli92/solids/css/base.css";                 // solo base
import "@soli92/solids/css/utilities.css";            // solo utilities
```

Preset Tailwind (shadcn): `require("@soli92/solids/tailwind-preset")` nel `tailwind.config`.

---

## Token Reference

### Colori (palette base)
`gray` · `blue` · `green` · `amber` · `red` · `violet` — ogni colore ha steps `50→900`.

### Token semantici (`--sd-color-*`)

**Testo**
- `--sd-color-text-primary` / `secondary` / `tertiary` / `disabled` / `inverse` / `link` / `link-hover`

**Background**
- `--sd-color-bg-canvas` / `surface` / `elevated` / `overlay` / `hover` / `active` / `disabled`

**Border**
- `--sd-color-border-default` / `muted` / `strong` / `focus` / `disabled`

**Intent**
- `--sd-color-intent-success` / `warning` / `danger` / `info` (+ `-bg` e `-border` per ognuno)

**Componenti**
- `--sd-color-primary-default` / `hover` / `active` / `subtle` / `foreground`
- `--sd-color-secondary-*` / `muted-*` / `accent-*` / `destructive-*`

### Spacing (`--sd-space-*`)
`xs` `sm` `md` `lg` `xl` `2xl` `3xl`

### Radius (`--sd-radius-*`)
`none` `sm` `md` `lg` `xl` `full`

### Tipografia
- `--sd-font-size-xs` → `6xl`
- `--sd-font-weight-light` → `extrabold`
- `--sd-font-body` / `--sd-font-heading` / `--sd-font-mono`

### Shadow (`--sd-shadow-*`)
`sm` `md` `lg` `xl`

### Motion
- `--sd-duration-fast` / `normal` / `slow`
- `--sd-easing-standard` (curva MD3) / `emphasized-decelerate` / `emphasized-accelerate` / `ease-inout` / `ease-out` / …

### Z-index (`--sd-z-*`)
`dropdown` `sticky` `overlay` `modal` `toast` `tooltip`

---

## Temi (light, dark, fantasy, cyberpunk, 90s-party, steampunk)

Temi globali tramite `data-theme` su `<html>`. Stessi token semantici (`--sd-*`), valori diversi per colore, font, raggio e ombre. I default **light** / **dark** sono orientati a superfici tonali, raggi più generosi e ombre a livelli in stile **Material Design 3**, mantenendo il blu **primary** tipico di shadcn.

```html
<html data-theme="light">      <!-- esplicito (spesso coincide con default :root) -->
<html data-theme="dark">
<html data-theme="fantasy">    <!-- pergamena / serif / Cinzel negli heading -->
<html data-theme="cyberpunk">  <!-- neon; il preset Tailwind tratta anche questo come "dark" per le utility dark: -->
<html data-theme="90s-party"> <!-- rave / magenta-teal-lime; stesso trattamento dark: del preset Tailwind -->
<html data-theme="steampunk"> <!-- ottone/rame, serif vittoriano; dark: come cyberpunk -->
```

Se **`data-theme` non è impostato**, `prefers-color-scheme: dark` applica i token **dark** (come `data-theme="dark"`). **Fantasy**, **cyberpunk**, **90s-party** e **steampunk** vanno scelti esplicitamente.

Con **next-themes**, usa `attribute="data-theme"` e, se vuoi tutti i temi nel selettore, estendi i temi oltre `light`/`dark` (vedi `docs/shadcn-integration.md`).

```tsx
<ThemeProvider attribute="data-theme" defaultTheme="system" enableSystem>
```

---

## Utility Classes (`sd-*`)

```html
<!-- Layout -->
<div class="sd-flex sd-items-center sd-gap-md sd-p-lg">

<!-- Tipografia -->
<h1 class="sd-text-3xl sd-font-bold sd-text-primary">Titolo</h1>
<p class="sd-text-base sd-text-secondary">Sottotitolo</p>

<!-- Card -->
<div class="sd-card">...</div>

<!-- Badge -->
<span class="sd-badge sd-badge-success">Attivo</span>
<span class="sd-badge sd-badge-danger">Errore</span>

<!-- Container -->
<main class="sd-container">...</main>
```

---

## Sviluppo

```bash
# Installa dipendenze
npm install

# Build (genera dist/)
npm run build

# Test smoke (build token/CSS + Storybook static)
npm test

# Storybook (build token + Tailwind preview, poi dev server)
npm run storybook

# Release (semantic-release — solo da CI; aggiorna CHANGELOG, versione npm, GitHub release)
npm run release

# Registry shadcn (sync src → registry/solids + JSON in registry/r)
npm run registry:build
```

Per Storybook, il CSS Tailwind viene precompilato in `.storybook/preview-tw.built.css` (file ignorato da git) dallo script `build:storybook-css`.

### Release, versioning e changelog

Su push a **`main`**, il workflow GitHub **Release** esegue **semantic-release**: analizza i commit (**Conventional Commits**, es. `feat:`, `fix:`), aggiorna **`CHANGELOG.md`** (plugin `@semantic-release/changelog`), bump di versione su npm, tag Git e **GitHub Release** con note generate. Non lanciare `npm run release` in locale salvo esigenze di debug: è pensato per CI (token `NPM_TOKEN`, `GITHUB_TOKEN`).

---

## Framework UI (progetti personali + shadcn)

SoliDS resta **agnostico**: i componenti UI vivono nelle tue app (modello shadcn: codice in repo, non solo in `node_modules`). Il flusso consigliato:

1. **Token e CSS** — `@soli92/solids` (`index.css` + opzionale solo layer).
2. **Tailwind** — `presets: [require("@soli92/solids/tailwind-preset")]` + `tailwindcss-animate`.
3. **shadcn/ui** — `npx shadcn@latest init` e `add` per ogni blocco (Radix + CVA + le tue classi).
4. **Tema** — `data-theme` / `next-themes` come in [docs/shadcn-integration.md](./docs/shadcn-integration.md).

In questo repository, **Storybook** include un esempio **Button** in stile shadcn in `src/components/ui/button.tsx` (solo sorgente di riferimento: **non** è incluso nell’artifact npm `dist/`; nei progetti veri aggiungi i componenti con la CLI shadcn).

Il **registry shadcn** per il modello 1 è in `registry/` (sorgenti) e `registry/r/` (JSON generati). Guida operativa: [docs/registry-model-1.md](./docs/registry-model-1.md).

---

## Struttura

```
src/
├── tokens/
│   ├── base.json           # Palette, spacing, tipografia, shadow, easing, z-index
│   ├── semantic.json       # Token semantici (testo, bg, border, intent, componenti)
│   └── themes/
│       ├── light.json      # Override tema light
│       ├── dark.json       # Override tema dark
│       ├── fantasy.json     # Tema fantasy (palette, font, radius, shadow)
│       ├── cyberpunk.json   # Tema cyberpunk
│       └── 90s-party.json    # Tema 90s party (rave / MTV)
├── tailwind/
│   └── preset.cjs          # Preset Tailwind (shadcn + token SD)
├── components/ui/          # Esempio shadcn in Storybook
├── css/
│   ├── shadcn.css          # Compatibility layer shadcn/ui
│   ├── base.css            # Reset + global styles
│   └── utilities.css       # Classi utility sd-*
scripts/
├── build.mjs               # Build script → genera dist/
└── sync-registry.mjs       # Copia src → registry/solids (per shadcn build)
registry/
│   └── solids/             # Sorgenti registry (sync da src/)
registry.json               # Indice item shadcn (root repo)
registry/r/                 # JSON pubblicati (`npm run registry:build`)
docs/
├── index.mdx               # Intro (Storybook)
├── getting-started.mdx
├── principles.mdx
├── roadmap.mdx
├── foundations/            # Colori, spacing, typography, radius, themes, tokens
├── shadcn-integration.md   # Guida integrazione completa (markdown)
└── registry-model-1.md     # Modello shadcn in repo + @solids
```

---

## Dove viene usato

Esempi di progetti che consumano **`@soli92/solids`** (preset Tailwind + CSS): portale **[soli-dome](https://github.com/soli92/soli-dome)**, app **[soli-agent](https://github.com/soli92/soli-agent)**. Lo **Storybook** pubblicato è linkato anche da soli-dome (categoria Design).

---

## License

MIT © [soli92](https://github.com/soli92)
