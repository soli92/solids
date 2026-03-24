# Integrazione shadcn/ui con SoliDS

SoliDS include un **compatibility layer** (`shadcn.css`) che mappa automaticamente
tutte le CSS variables che shadcn/ui si aspetta sui token semantici di SoliDS.
In questo modo usi un solo sistema di token per tutti i tuoi progetti.

---

## Setup rapido (Next.js + Tailwind v3 + shadcn/ui)

### 1. Installa SoliDS

```bash
npm install @Soli92/solids
```

### 2. Importa il CSS nell'entrypoint globale

```css
/* app/globals.css  –oppure–  styles/globals.css */
@import "@Soli92/solids/css/index.css";

/* Il tuo Tailwind (dopo SoliDS) */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

> ⚠️ `index.css` importa già **variables → themes → shadcn → base → utilities**
> nell'ordine corretto. Non devi importare i singoli file separatamente.

### 3. Configura Tailwind per usare le CSS Variables di SoliDS

```js
// tailwind.config.js  (o tailwind.config.ts)
const { fontFamily } = require("tailwindcss/defaultTheme");

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class", '[data-theme="dark"]'],   // supporta sia class sia data-theme
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        /* ── shadcn/ui standard ───────────────────────────── */
        background:  "var(--background)",
        foreground:  "var(--foreground)",
        card:        { DEFAULT: "var(--card)",        foreground: "var(--card-foreground)" },
        popover:     { DEFAULT: "var(--popover)",     foreground: "var(--popover-foreground)" },
        primary:     { DEFAULT: "var(--primary)",     foreground: "var(--primary-foreground)" },
        secondary:   { DEFAULT: "var(--secondary)",   foreground: "var(--secondary-foreground)" },
        muted:       { DEFAULT: "var(--muted)",       foreground: "var(--muted-foreground)" },
        accent:      { DEFAULT: "var(--accent)",      foreground: "var(--accent-foreground)" },
        destructive: { DEFAULT: "var(--destructive)", foreground: "var(--destructive-foreground)" },
        border:  "var(--border)",
        input:   "var(--input)",
        ring:    "var(--ring)",

        /* ── SoliDS extras (disponibili come classi Tailwind) */
        "sd-primary":  "var(--sd-color-primary-default)",
        "sd-success":  "var(--sd-color-intent-success)",
        "sd-warning":  "var(--sd-color-intent-warning)",
        "sd-danger":   "var(--sd-color-intent-danger)",
        "sd-info":     "var(--sd-color-intent-info)",
      },
      borderRadius: {
        lg:   "var(--radius)",
        md:   "calc(var(--radius) - 2px)",
        sm:   "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--sd-font-body)", ...fontFamily.sans],
        mono: ["var(--sd-font-mono)", ...fontFamily.mono],
      },
      boxShadow: {
        sm:  "var(--sd-shadow-sm)",
        md:  "var(--sd-shadow-md)",
        lg:  "var(--sd-shadow-lg)",
        xl:  "var(--sd-shadow-xl)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
```

### 4. Inizializza shadcn/ui

```bash
npx shadcn-ui@latest init
```

Durante l'inizializzazione scegli:
- **CSS variables**: `yes`
- **Base color**: qualsiasi (verrà sovrascritto da SoliDS)
- Non aggiungere il blocco `@layer base` generato da shadcn in `globals.css`
  se usi già `@import "@Soli92/solids/css/index.css"`.

---

## Gestione del tema dark

SoliDS supporta **tre strategie** contemporaneamente:

| Strategia | Come funziona |
|-----------|--------------|
| `data-theme="dark"` sull'elemento root | Cambio manuale via JS |
| `data-theme="light"` | Forza light anche se il sistema è dark |
| `@media (prefers-color-scheme: dark)` | Rispetta le preferenze di sistema |

### Esempio con next-themes

```tsx
// app/providers.tsx
import { ThemeProvider } from "next-themes";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="data-theme"   // usa data-theme invece di class
      defaultTheme="system"
      enableSystem
    >
      {children}
    </ThemeProvider>
  );
}
```

---

## Solo le variabili (senza base/utilities)

Se vuoi solo le variabili e il layer shadcn, senza reset e utility:

```css
@import "@Soli92/solids/css/variables.css";
@import "@Soli92/solids/css/themes.css";
@import "@Soli92/solids/css/shadcn.css";
```

---

## Token disponibili come CSS Variables

### Colori semantici
| Variable | Valore light | Valore dark |
|----------|-------------|-------------|
| `--sd-color-text-primary` | `#111827` | `#F9FAFB` |
| `--sd-color-text-secondary` | `#4B5563` | `#D1D5DB` |
| `--sd-color-bg-canvas` | `#FFFFFF` | `#0B1220` |
| `--sd-color-bg-surface` | `#F9FAFB` | `#111827` |
| `--sd-color-bg-elevated` | `#FFFFFF` | `#1F2937` |
| `--sd-color-primary-default` | `#2563EB` | `#3B82F6` |
| `--sd-color-border-default` | `#E5E7EB` | `#243047` |

### Mapping shadcn/ui
| Variable shadcn | Mappa a |
|----------------|---------|
| `--background` | `--sd-color-bg-canvas` |
| `--foreground` | `--sd-color-text-primary` |
| `--primary` | `--sd-color-primary-default` |
| `--primary-foreground` | `--sd-color-primary-foreground` |
| `--secondary` | `--sd-color-secondary-default` |
| `--muted` | `--sd-color-muted-default` |
| `--accent` | `--sd-color-accent-default` |
| `--destructive` | `--sd-color-destructive-default` |
| `--border` | `--sd-color-border-default` |
| `--ring` | `--sd-color-border-focus` |
| `--radius` | `--sd-radius-md` |

---

## Utilizzo con React (Vite / CRA)

```tsx
// main.tsx
import "@Soli92/solids/css/index.css";
```

---

## Utilizzo con classi utility SoliDS

SoliDS espone classi utility prefissate con `sd-` che puoi usare senza Tailwind:

```html
<div class="sd-card sd-flex sd-flex-col sd-gap-md">
  <h2 class="sd-text-2xl sd-font-semibold sd-text-primary">Titolo</h2>
  <p class="sd-text-secondary sd-text-base">Descrizione</p>
  <span class="sd-badge sd-badge-success">Attivo</span>
</div>
```
