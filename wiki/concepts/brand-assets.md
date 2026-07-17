---
id: brand-assets
type: concept
title: "SoliDS — Brand Assets"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/raw/analisi-repository-2026-07-17.txt §1.3 docs/brand-assets/ — Asset centralizzati"
  - "docs/raw/analisi-repository-2026-07-17.txt §2.4 Consumer integration"
---

# SoliDS — Brand Assets

Documentazione della struttura `docs/brand-assets/` — asset centralizzati per il brand soli92 e i workspace projects.[^src: docs/raw/analisi-repository-2026-07-17.txt §1.3 docs/brand-assets/ — Asset centralizzati]

## Struttura

```
docs/brand-assets/
├── soli-icons/                    — Brand icon pack principale (16 file)
├── soli-category-icons/           — Icone branding Storybook (11 file + webmanifest)
├── workspace-icons/               — Raw per-project (originali, 5 progetti)
└── workspace-icons-normalized/    — Normalizzati per distribuzione npm (18 file)
```

## soli-icons/ — Brand icon pack principale

16 file con varianti sistematiche:[^src: docs/raw/analisi-repository-2026-07-17.txt §1.3 docs/brand-assets/ — Asset centralizzati]

| Dimensione di variazione | Valori |
|--------------------------|--------|
| Formato output | JPG, PNG, SVG, WebP |
| Aspect ratio | 1×1, 4×3 |
| Contenuto | symbol-only, with-text |
| Colorazione | gold, mono |

Include versioni **theme-aware** (`soli-icon-*-theme`) che si adattano al `data-theme` attivo via token CSS. Esportate come componenti React da `@soli92/solids/icons`.

## soli-category-icons/ — Branding Storybook

11 file per il branding del sito Storybook pubblicato su GitHub Pages. 5 categorie, ciascuna disponibile in SVG + PNG:[^src: docs/raw/analisi-repository-2026-07-17.txt §1.3 docs/brand-assets/ — Asset centralizzati]

| Categoria | Uso |
|-----------|-----|
| `app-icon` | Icona applicazione principale |
| `apple-touch` | Icona iOS home screen |
| `favicon` | Favicon browser |
| `logo` | Logo completo |
| `symbol` | Solo simbolo |

Include `webmanifest` per la PWA del Storybook.

## workspace-icons/ — Raw per-project

Raccolta cross-repo degli icon pack originali, organizzati per progetto:[^src: docs/raw/analisi-repository-2026-07-17.txt §1.3 docs/brand-assets/ — Asset centralizzati]

| Progetto | N. file | Asset inclusi |
|----------|---------|---------------|
| `Koollector/` | 10 | App-icon, favicon, android-icon-bg/fg/mono, splash, react-logo variants |
| `bachelor-party-claudiano/` | 3 | App-icon SVG, apple-touch PNG, favicon-32 PNG |
| `pippify/` | 2 | Logo SVG (frontend/public + frontend/src) |
| `soli-agent/` | 1 | Favicon SVG |
| `soli-dm-fe/` | 4 | d20-icon SVG, apple-touch PNG, icon-192/512 PNG (PWA) |
| `soli-dome/` | 2 | icon-192/512 SVG (PWA) |

`workspace-icons/manifest.json` — elenco completo dei file raw con metadati.

## workspace-icons-normalized/ — Per distribuzione npm

18 file con prefisso uniforme `soli-icon-*`, rinominati dal formato raw per distribuzione coerente.[^src: docs/raw/analisi-repository-2026-07-17.txt §1.3 docs/brand-assets/ — Asset centralizzati]

| File indice | Ruolo |
|-------------|-------|
| `manifest.json` | Lookup file → categoria per i consumer |
| `index.json` | Indice rapido per categoria |

Questa directory e' ciò che viene effettivamente distribuito via npm ai consumer del package. I consumer possono importare con TypeScript autocomplete via:

```typescript
import { ... } from "@soli92/solids/brand-assets/workspace-icons-normalized"
```

## Consumer tipici[^src: docs/raw/analisi-repository-2026-07-17.txt §2.4 Consumer integration]

| Consumer | Asset usati | Note |
|----------|-------------|------|
| `soli-dome` | icon-192/512 SVG (PWA) | App con service worker |
| `soli-dm-fe` | PNG 192/512 (PWA) + d20-icon SVG | App DM, icone specifiche |
| `soli-agent` | favicon SVG | Solo favicon |
| `Koollector` | Full Android/iOS set | App mobile Expo |
| `bachelor-party-claudiano` | App-icon + apple-touch + favicon | Web app |
| `pippify` | Logo SVG | Solo logo |

## Integrazione con soli-prof (RAG)

SoliDS e' in `CORPUS_REPOS` di soli-prof. Un push su `main` notifica re-ingest via webhook `push` → `https://soli-prof.vercel.app/api/webhooks/github` (HMAC). Gli asset brand sono inclusi nell'indicizzazione.

## Pagine correlate

- [[icon-system]] — sistema icone SolidsIcon + tematiche (diverso dagli asset brand)
- [[design-system-overview]] — panoramica distribuzione e consumer
- [[docs-structure]] — struttura docs/ e ruolo di brand-assets/ nel repo
