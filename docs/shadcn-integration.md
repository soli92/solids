# Integrazione shadcn/ui con SoliDS

SoliDS include un **compatibility layer** (`shadcn.css`) che mappa automaticamente
tutte le CSS variables che shadcn/ui si aspetta sui token semantici di SoliDS.
In questo modo usi un solo sistema di token per tutti i tuoi progetti.

**Documentazione correlata:** [Storybook su GitHub Pages](https://soli92.github.io/solids/) (foundations e temi), [modello registry `@solids`](./registry-model-1.md), [README del repo](../README.md) (tabella documentazione e struttura).

---

## Setup rapido (Next.js + Tailwind v3 + shadcn/ui)

### 1. Installa SoliDS

```bash
npm install @soli92/solids
```

### 2. Importa il CSS nell'entrypoint globale

```css
/* app/globals.css  –oppure–  styles/globals.css */
@import "@soli92/solids/css/index.css";

/* Il tuo Tailwind (dopo SoliDS) */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

> ⚠️ `index.css` importa già **variables → themes → shadcn → base → utilities**
> nell'ordine corretto. Non devi importare i singoli file separatamente.

### 3. Configura Tailwind (preset SoliDS — consigliato)

```js
// tailwind.config.js  (o tailwind.config.ts con createRequire)
module.exports = {
  presets: [require("@soli92/solids/tailwind-preset")],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
};
```

Installa anche `tailwindcss-animate` (richiesto dal preset, come in shadcn):

```bash
npm install tailwindcss-animate
```

**Alternativa manuale:** se non vuoi il preset, copia l’estensione `theme.extend` completa dalla versione precedente di questa guida (colori `var(--background)`, chart, sidebar, font, shadow) nel tuo `tailwind.config`.

### 4. Inizializza shadcn/ui

```bash
npx shadcn-ui@latest init
```

Durante l'inizializzazione scegli:
- **CSS variables**: `yes`
- **Base color**: qualsiasi (verrà sovrascritto da SoliDS)
- Non aggiungere il blocco `@layer base` generato da shadcn in `globals.css`
  se usi già `@import "@soli92/solids/css/index.css"`.

Riferimento `components.json`: [templates/components.json.example](../templates/components.json.example).

**Modello 1 (componenti nel tuo repo + CLI):** vedi [registry-model-1.md](./registry-model-1.md) per il namespace `@solids`, il kit completo `npx shadcn add @solids/solids-ui` e il singolo `solids-button`.

---

## Temi (light, dark, fantasy, cyberpunk, 90s-party)

Oltre a **light** e **dark**, SoliDS espone i temi globali **fantasy**, **cyberpunk** e **90s-party** (`data-theme="fantasy"` / `"cyberpunk"` / `"90s-party"` su `<html>`). Ridefiniscono palette, font, raggio e ombre; il layer shadcn continua a leggere gli stessi token semantici.

| Strategia | Come funziona |
|-----------|--------------|
| `data-theme="dark"` / `"fantasy"` / `"cyberpunk"` / `"90s-party"` / `"light"` | Tema esplicito sul root |
| `@media (prefers-color-scheme: dark)` | Applica i token **dark** solo se **`data-theme` non è impostato** su `:root` |

Il preset Tailwind considera **dark** anche `data-theme="cyberpunk"` e **`data-theme="90s-party"`** per le utility `dark:`.

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
@import "@soli92/solids/css/variables.css";
@import "@soli92/solids/css/themes.css";
@import "@soli92/solids/css/shadcn.css";
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
import "@soli92/solids/css/index.css";
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
