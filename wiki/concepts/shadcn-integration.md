---
id: shadcn-integration
type: concept
title: "SoliDS — Integrazione shadcn/ui"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/shadcn-integration.md §Setup rapido"
  - "docs/shadcn-integration.md §Temi"
  - "docs/shadcn-integration.md §Token disponibili come CSS Variables"
  - "docs/shadcn-integration.md §Solo le variabili"
  - "docs/shadcn-integration.md §Utilizzo con classi utility SoliDS"
---

# SoliDS — Integrazione shadcn/ui

SoliDS include un **compatibility layer** (`shadcn.css`) che mappa automaticamente tutte le CSS variables che shadcn/ui si aspetta sui token semantici di SoliDS. In questo modo si usa un solo sistema di token per tutti i progetti.[^src: docs/shadcn-integration.md §Setup rapido]

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

/* Tailwind (dopo SoliDS) */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`index.css` importa gia' **variables → themes → shadcn → base → utilities** nell'ordine corretto. Non occorre importare i singoli file separatamente.

### 3. Configura Tailwind (preset SoliDS — consigliato)

```js
// tailwind.config.js
module.exports = {
  presets: [require("@soli92/solids/tailwind-preset")],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
};
```

```bash
npm install tailwindcss-animate  # richiesto dal preset
```

### 4. Inizializza shadcn/ui

```bash
npx shadcn-ui@latest init
```

- **CSS variables**: `yes`
- **Base color**: qualsiasi (sovrascritto da SoliDS)
- Non aggiungere il blocco `@layer base` generato da shadcn se si usa gia' il CSS di SoliDS

### 5. Utilizza il registry @solids

Vedi [[registry-model-1]] per la configurazione del namespace `@solids` e l'installazione dei blocchi.

[^src: docs/shadcn-integration.md §Setup rapido]

---

## Temi

Oltre a **light** e **dark**, SoliDS espone **fantasy**, **cyberpunk**, **90s-party**, **steampunk** e sei temi **personaggio** — tutti attivati con `data-theme="…"` su `<html>`. I temi ridefiniscono palette, font, raggio e ombre; il layer shadcn continua a leggere gli stessi token semantici.[^src: docs/shadcn-integration.md §Temi]

| Tema | `data-theme` |
|------|-------------|
| Light | `light` (default) |
| Dark | `dark` |
| Fantasy | `fantasy` |
| Cyberpunk | `cyberpunk` |
| 90s Party | `90s-party` |
| Steampunk | `steampunk` |
| Personaggio | `ichigo`, `vegeta`, `zoro`, `captain-america`, `sasuke`, `inuyasha` |

Il preset Tailwind considera **dark** anche `cyberpunk`, `90s-party`, `steampunk` e i temi personaggio per le utility `dark:`.

`prefers-color-scheme: dark` applica i token dark solo se `data-theme` non e' impostato su `:root`.

### Esempio con next-themes

```tsx
import { ThemeProvider } from "next-themes";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="data-theme"
      defaultTheme="system"
      enableSystem
      themes={["light", "dark", "fantasy", "cyberpunk", "90s-party", "steampunk",
               "captain-america", "ichigo", "inuyasha", "sasuke", "vegeta", "zoro"]}
    >
      {children}
    </ThemeProvider>
  );
}
```

---

## Solo le variabili (senza base/utilities)

Per usare solo le variabili e il layer shadcn, senza reset e utility:

```css
@import "@soli92/solids/css/variables.css";
@import "@soli92/solids/css/themes.css";
@import "@soli92/solids/css/shadcn.css";
```

[^src: docs/shadcn-integration.md §Solo le variabili]

---

## Token CSS Variables

### Colori semantici (light / dark)

| Variable | Valore light | Valore dark |
|----------|-------------|------------|
| `--sd-color-text-primary` | `#111827` | `#F9FAFB` |
| `--sd-color-text-secondary` | `#4B5563` | `#D1D5DB` |
| `--sd-color-bg-canvas` | `#FAFBFC` | `#0C0E12` |
| `--sd-color-bg-surface` | `#F0F2F5` | `#161922` |
| `--sd-color-bg-elevated` | `#FFFFFF` | `#1E2430` |
| `--sd-color-primary-default` | `#2563EB` | `#3B82F6` |
| `--sd-color-border-default` | `#E2E5EA` | `#2E3545` |

Valori indicativi da `themes/light.json` e `themes/dark.json`. I temi nominati sostituiscono la stessa struttura con palette dedicate.[^src: docs/shadcn-integration.md §Token disponibili come CSS Variables]

### Mapping shadcn/ui → SoliDS

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

## Classi utility SoliDS (senza Tailwind)

SoliDS espone classi utility prefissate `sd-` utilizzabili senza Tailwind:

```html
<div class="sd-card sd-flex sd-flex-col sd-gap-md">
  <h2 class="sd-text-2xl sd-font-semibold sd-text-primary">Titolo</h2>
  <p class="sd-text-secondary sd-text-base">Descrizione</p>
  <span class="sd-badge sd-badge-success">Attivo</span>
</div>
```

[^src: docs/shadcn-integration.md §Utilizzo con classi utility SoliDS]

---

## Pagine correlate

- [[registry-model-1]] — Model 1: configurazione namespace `@solids` e blocchi
- [[token-architecture]] — architettura token base/semantic/temi
- [[foundations/themes]] — identita' visiva e valori token per ogni tema
- [[foundations/colors]] — catalogo token colore semantico
- [[development-history]] — Fase 1: origini del compatibility layer
