# SoliDS

**SoliDS** è il design system personale di [Soli92](https://github.com/Soli92) —
una fondamenta **agnostica** basata su **design tokens** e **CSS variables**,
pronta all'uso con qualsiasi framework web e compatibile con **shadcn/ui**.

---

## Cosa include

| Layer | File | Descrizione |
|-------|------|-------------|
| 🎨 Tokens | `dist/tokens/tokens.json` | Palette completa, spacing, tipografia, shadow, radius, easing, z-index |
| 🔤 Variables | `dist/css/variables.css` | CSS vars `--sd-*` per tema light (default) |
| 🌗 Themes | `dist/css/themes.css` | Override dark + `prefers-color-scheme` |
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

Poi inizializza shadcn e aggiungi i componenti con la CLI (`npx shadcn@latest init` → `add button`, …). I componenti useranno le variabili `--background`, `--primary`, ecc., già mappate da SoliDS. Un esempio di `components.json` è in [templates/components.json.example](./templates/components.json.example).

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
import "@soli92/solids/css/themes.css";               // solo dark
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
- `--sd-easing-ease-inout` / `ease-out` / …

### Z-index (`--sd-z-*`)
`dropdown` `sticky` `overlay` `modal` `toast` `tooltip`

---

## Dark Mode

SoliDS supporta tre strategie contemporaneamente:

```html
<!-- Forza dark -->
<html data-theme="dark">

<!-- Forza light -->
<html data-theme="light">

<!-- Automatico (segue sistema, default) -->
<html>
```

Con **next-themes**:
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

# Storybook (build token + Tailwind preview, poi dev server)
npm run storybook

# Release (semantic-release — solo da CI)
npm run release

# Registry shadcn (sync src → registry/solids + JSON in registry/r)
npm run registry:build
```

Per Storybook, il CSS Tailwind viene precompilato in `.storybook/preview-tw.built.css` (file ignorato da git) dallo script `build:storybook-css`.

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
│       └── dark.json       # Override tema dark
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
├── shadcn-integration.md   # Guida integrazione completa
└── registry-model-1.md     # Modello shadcn in repo + @solids
```

---

## License

MIT © [Soli92](https://github.com/Soli92)
