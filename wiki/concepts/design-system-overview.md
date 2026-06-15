---
id: design-system-overview
type: concept
title: "SoliDS — Design System Overview"
status: stable
created: 2026-06-15
updated: 2026-06-15
---

# SoliDS — Design System Overview

## Scopo

SoliDS è il design system personale di soli92 — una fondamenta **agnostica** basata su **design tokens** e **CSS variables**, pronta all'uso con qualsiasi framework web. Compatibile con shadcn/ui.

**Filosofia**: i token sono la source of truth. I componenti React sono opzionali e consumano i token. L'integrazione CSS-first è prioritaria rispetto all'integrazione component-first.

## Architettura token

Il sistema è stratificato in tre livelli:

| Livello | File | Ruolo |
|---------|------|-------|
| **Primitivi** (base) | `src/tokens/base.json` | Valori assoluti: colori esadecimali, spacing in px, radii, font stack, shadow. Non hanno semantica. |
| **Semantici** | `src/tokens/semantic.json` | Alias semantici: `color.text.primary`, `color.bg.canvas`, `color.intent.success`. Mappano primitivi a ruoli UI. Defaults per tema light. |
| **Tema** | `src/tokens/themes/*.json` | Override per tema (`light`, `dark`, `cyberpunk`, `fantasy`, ecc.). Ridefiniscono i semantici per contesto. |

I token vengono compilati in CSS custom properties (`--sd-*`) e distribuiti in `dist/css/`.

## Theming model

- Tema attivato via `data-theme="<nome>"` sull'elemento `<html>`.
- Fallback automatico a `prefers-color-scheme: dark` quando nessun `data-theme` è impostato.
- 12 temi disponibili: `light`, `dark`, `fantasy`, `cyberpunk`, `90s-party`, `steampunk`, `ichigo`, `vegeta`, `zoro`, `captain-america`, `sasuke`, `inuyasha`.

## Consumer tipici

| Consumer | Pattern di integrazione |
|----------|------------------------|
| **Next.js + Tailwind** | `import '@soli92/solids/dist/css/index.css'` + preset Tailwind |
| **shadcn/ui** | `dist/css/shadcn.css` mappa le variabili shadcn → token SoliDS |
| **CSS puro** | `dist/css/variables.css` + `dist/css/themes.css` diretti |
| **React components** | `import { Button } from '@soli92/solids'` (componenti opzionali) |
| **soli-boy** | theme provider: `data-theme` su `<html>`, sd-* utility classes |

## Distribuzione

```
dist/
  css/
    index.css       — entrypoint unico (importa tutto nell'ordine corretto)
    variables.css   — CSS vars --sd-* tema light (default)
    themes.css      — override per tutti i temi
    shadcn.css      — mapping shadcn → SoliDS
    base.css        — reset, scroll, focus, box-sizing
    utilities.css   — classi sd-* (flex, spacing, colori, badge, card, link)
  tokens/
    tokens.json     — token JSON unificati
  brand-assets/     — Soli icons + category icons
```

## Integrazione con Soli Prof (RAG)

SoliDS è indicizzato nella knowledge base Soli Prof. Un push su `main` può notificare re-ingest tramite webhook. L'AI_LOG.md documenta le decisioni architetturali.
