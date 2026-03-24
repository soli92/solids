# SoliDS

**SoliDS** è il design system personale di [Soli92](https://github.com/Soli92) —
un fondamenta **agnostica** basata su **design tokens** e **CSS variables**,
pronta all'uso con qualsiasi framework web e compatibile con **shadcn/ui**.

---

## Cosa include

| Layer | File | Descrizione |
|-------|------|-------------|
| 🎨 Tokens | `dist/tokens/tokens.json` | Palette completa, spacing, tipografia, shadow, radius, easing, z-index |
| 🔤 Variables | `dist/css/variables.css` | CSS vars `--sd-*` per tema light (default) |
| 🌗 Themes | `dist/css/themes.css` | Override dark + `prefers-color-scheme` |
| 🔗 shadcn | `dist/css/shadcn.css` | Mapping variabili shadcn/ui → token SoliDS |
| 🧱 Base | `dist/css/base.css` | Reset minimale, body, focus-visible |
| 🛠️ Utilities | `dist/css/utilities.css` | Classi utility `sd-*` (flex, spacing, colori, badge, card…) |
| 📦 Index | `dist/css/index.css` | Entrypoint unico che importa tutto nell'ordine corretto |

---

## Installazione

```bash
npm install @Soli92/solids
```

---

## Quick Start

### Con Tailwind + shadcn/ui (Next.js, Vite…)

```css
/* globals.css */
@import "@Soli92/solids/css/index.css";

@tailwind base;
@tailwind components;
@tailwind utilities;
```

```js
// tailwind.config.js
module.exports = {
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        background:  "var(--background)",
        foreground:  "var(--foreground)",
        primary:     { DEFAULT: "var(--primary)",   foreground: "var(--primary-foreground)" },
        secondary:   { DEFAULT: "var(--secondary)", foreground: "var(--secondary-foreground)" },
        muted:       { DEFAULT: "var(--muted)",     foreground: "var(--muted-foreground)" },
        accent:      { DEFAULT: "var(--accent)",    foreground: "var(--accent-foreground)" },
        destructive: { DEFAULT: "var(--destructive)",foreground: "var(--destructive-foreground)" },
        card:        { DEFAULT: "var(--card)",      foreground: "var(--card-foreground)" },
        popover:     { DEFAULT: "var(--popover)",   foreground: "var(--popover-foreground)" },
        border: "var(--border)",
        input:  "var(--input)",
        ring:   "var(--ring)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
};
```

➡️ Guida completa: [docs/shadcn-integration.md](./docs/shadcn-integration.md)

### Senza framework

```html
<link rel="stylesheet" href="node_modules/@Soli92/solids/dist/css/index.css" />
```

---

## Esportazioni disponibili

```js
import tokens from "@Soli92/solids/tokens";                    // tokens.json
import "@Soli92/solids/css/index.css";                         // tutto
import "@Soli92/solids/css/variables.css";                     // solo vars
import "@Soli92/solids/css/themes.css";                        // solo dark
import "@Soli92/solids/css/shadcn.css";                        // solo shadcn layer
import "@Soli92/solids/css/base.css";                          // solo base
import "@Soli92/solids/css/utilities.css";                     // solo utilities
```

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
- `--sd-font-body` / `heading` / `mono`

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

# Storybook
npm run storybook

# Release (semantic-release — solo da CI)
npm run release
```

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
├── css/
│   ├── shadcn.css          # Compatibility layer shadcn/ui
│   ├── base.css            # Reset + global styles
│   └── utilities.css       # Classi utility sd-*
scripts/
└── build.mjs               # Build script → genera dist/
docs/
└── shadcn-integration.md   # Guida integrazione completa
```

---

## License

MIT © [Soli92](https://github.com/Soli92)
