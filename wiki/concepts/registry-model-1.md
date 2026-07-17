---
id: registry-model-1
type: concept
title: "SoliDS — Registry Model 1"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/registry-model-1.md §Flusso in un progetto nuovo"
  - "docs/registry-model-1.md §Sviluppo nel repo SoliDS (mantenitori)"
  - "docs/registry-model-1.md §Alternative senza namespace"
  - "docs/registry-model-1.md §Storybook su GitHub Pages"
---

# SoliDS — Registry Model 1

Nel **Modello 1** i componenti UI stanno nel progetto applicativo consumer (`components/`, `lib/`, …). SoliDS fornisce **token + CSS + preset Tailwind**; il registry in questo repository fornisce **snippet ufficiali** allineati a SoliDS, installabili con la CLI shadcn.[^src: docs/registry-model-1.md §Flusso in un progetto nuovo]

Documentazione correlata: [[shadcn-integration]] per il setup completo shadcn, [[token-architecture]] per l'architettura token.

---

## Flusso in un progetto nuovo (consumer)

### 1. Dipendenze fondazione

```bash
npm install @soli92/solids tailwindcss tailwindcss-animate
```

### 2. CSS globale

In `globals.css` (o equivalente): importare SoliDS prima di Tailwind.

```css
@import "@soli92/solids/css/index.css";
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### 3. Tailwind preset

Usa il preset SoliDS nel `tailwind.config.js`:

```js
module.exports = {
  presets: [require("@soli92/solids/tailwind-preset")],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
};
```

### 4. shadcn init

```bash
npx shadcn@latest init
```

Scegliere CSS variables: `yes`. Non aggiungere il blocco `@layer base` generato da shadcn se si usa gia' `@import "@soli92/solids/css/index.css"`.

### 5. Configurare il namespace registry SoliDS

Nel `components.json` del progetto consumer:

```json
{
  "registries": {
    "@solids": {
      "url": "https://raw.githubusercontent.com/soli92/solids/main/registry/r/{name}.json"
    }
  }
}
```

### 6. Installare i blocchi SoliDS

**Kit completo** (tutti i componenti shadcn/ui allineati a SoliDS):

```bash
npx shadcn@latest add @solids/solids-ui
```

Installa anche `@solids/solids-utils` e le dipendenze npm elencate nel payload del registry.

**Solo il Button** (progetti minimali):

```bash
npx shadcn@latest add @solids/solids-button
```

**Icone SVG** (token `--sd-color-icon-*`):

```bash
npx shadcn@latest add @solids/solids-icons
```

### 7. Componenti extra da shadcn

Per blocchi non ancora nel registry SoliDS, usare `npx shadcn@latest add @shadcn/…` dopo aver allineato CSS e preset.

[^src: docs/registry-model-1.md §Flusso in un progetto nuovo]

---

## Sviluppo nel repo SoliDS (mantenitori)

**Sorgente canonica** dei componenti esposti: `src/lib/utils.ts`, `src/icons/*` e `src/components/ui/*`.

### Build registry per GitHub Raw

```bash
npm run registry:build
```

Lo script copia i file in `registry/solids/` e genera `registry/r/*.json`.

### Workflow dopo modifiche

1. Modifica componenti in `src/components/ui` o hook
2. `npm run ui:stories` (o `npm run storybook` / `build-storybook`)
3. `npm run registry:build`
4. Committare `registry/solids/**`, `registry/r/**` e `registry.json`

**Attenzione**: `scripts/sync-registry.mjs` sovrascrive `registry.json` ad ogni run — le modifiche al registry vanno sempre fatte nello script, non nei JSON generati.

### Nuove dipendenze npm nei blocchi

Se si aggiungono dipendenze con `shadcn add`, aggiornare anche `scripts/solids-ui-npm-deps.json` affinche' il blocco `@solids/solids-ui` installi i pacchetti corretti nei consumer.

[^src: docs/registry-model-1.md §Sviluppo nel repo SoliDS (mantenitori)]

---

## Alternative senza namespace

Per installazione diretta (prove rapide, senza `components.json`):

```bash
npx shadcn@latest add https://raw.githubusercontent.com/soli92/solids/main/registry/r/solids-utils.json
npx shadcn@latest add https://raw.githubusercontent.com/soli92/solids/main/registry/r/solids-button.json
```

Nota: `solids-button` potrebbe non risolvere automaticamente `solids-utils` se la CLI si aspetta il namespace. Preferire il flusso con `@solids` nel `components.json`.[^src: docs/registry-model-1.md §Alternative senza namespace]

---

## Storybook su GitHub Pages

A ogni **GitHub Release** (creata da semantic-release insieme al publish npm), il workflow **Deploy Storybook** genera lo static e lo pubblica su `https://soli92.github.io/solids/`.

Prima attivazione: *Repository → Settings → Pages → Build and deployment → Source: GitHub Actions*.[^src: docs/registry-model-1.md §Storybook su GitHub Pages]

---

## Struttura file registry

| File | Contenuto |
|------|-----------|
| `registry/r/solids-ui.json` | Kit principale — tutti i componenti |
| `registry/r/solids-button.json` | Solo Button |
| `registry/r/solids-utils.json` | Utility `cn()` e helpers |
| `registry/r/solids-icons.json` | Icone tematiche |
| `registry.json` | Indice registry (generato da script) |

---

## Riferimenti schema

- [registry-json shadcn](https://ui.shadcn.com/docs/registry/registry-json)
- [registry-item-json shadcn](https://ui.shadcn.com/docs/registry/registry-item-json)
- [Namespace shadcn](https://ui.shadcn.com/docs/registry/namespace)

---

## Pagine correlate

- [[shadcn-integration]] — guida setup shadcn/ui completa (theming, token bridge)
- [[icon-system]] — icone SoliDS (`@solids/solids-icons`)
- [[token-architecture]] — architettura token base/semantic/temi
- [[development-history]] — Fase 2: origini del registry `@solids`
