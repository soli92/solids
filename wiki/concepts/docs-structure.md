---
id: docs-structure
type: concept
title: "SoliDS — Struttura docs/ e pipeline factory"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/raw/analisi-repository-2026-07-17.txt §Parte 1 — Anatomia della cartella docs/"
  - "docs/raw/analisi-repository-2026-07-17.txt §1.1 Struttura complessiva"
  - "docs/raw/analisi-repository-2026-07-17.txt §1.4 docs/raw/ e docs/inbox/ — Pipeline factory"
  - "docs/raw/analisi-repository-2026-07-17.txt §1.5 Documenti root-level di docs/"
---

# SoliDS — Struttura docs/ e pipeline factory

Anatomia della cartella `docs/` e del suo ruolo nella pipeline documentazione + factory.[^src: docs/raw/analisi-repository-2026-07-17.txt §Parte 1 — Anatomia della cartella docs/]

## Struttura complessiva[^src: docs/raw/analisi-repository-2026-07-17.txt §1.1 Struttura complessiva]

```
docs/
├── brand-assets/                   — Asset brand centralizzati
│   ├── soli-icons/                 (16 file: brand icon pack principale)
│   ├── soli-category-icons/        (11 file + webmanifest: icone Storybook)
│   ├── workspace-icons/            (raw per-project, 5 progetti)
│   └── workspace-icons-normalized/ (18 file normalizzati + manifest)
├── foundations/                    — 8 MDX: documentazione Storybook (produzione)
├── inbox/                          — scratch zone umana factory (solo .gitkeep)
├── raw/                            — input immutabili per wiki-keeper
├── getting-started.mdx
├── index.mdx
├── principles.mdx
├── registry-model-1.md
├── roadmap.mdx
└── shadcn-integration.md
```

## docs/foundations/ — Documentazione Storybook MDX

8 file MDX che alimentano il sito Storybook su GitHub Pages (pubblicato via GitHub Actions). Tutti usano il blocco `<Meta title="Foundations / ...">` di Storybook Blocks.[^src: docs/raw/analisi-repository-2026-07-17.txt §1.2 docs/foundations/ — Storybook MDX]

| File | Contenuto |
|------|-----------|
| `accessibility-and-motion.mdx` | WCAG 2.2, Material Design 3, Apple HIG; utility `sd-min-touch-target`, `sd-link`; motion `standard`/`emphasized` |
| `colors.mdx` | Palette semantica, token `color.*`, uso light/dark |
| `icons.mdx` | Sistema icone SVG React (`SolidsIcon`), prop variant/size, gallery, brand pack, icone tematiche |
| `radius.mdx` | Border radius tokens (`--sd-radius-*`) |
| `spacing.mdx` | Scale spacing (`--sd-spacing-*`) |
| `themes.mdx` | Sistema temi (`data-theme`): light, dark, fantasy, cyberpunk, 90s-party, steampunk + 6 temi personaggio |
| `tokens.mdx` | Panoramica design tokens: base → semantici, struttura directory, CSS output |
| `typography.mdx` | Font stack (Inter, DM Sans, JetBrains Mono), scale tipografica, token `--sd-font-*` |

Questi file sono la documentazione di **produzione** del DS — la fonte autoritativa per i consumer. La wiki factory ne e' un estratto strutturato.

## docs root-level — Documenti principali[^src: docs/raw/analisi-repository-2026-07-17.txt §1.5 Documenti root-level di docs/]

| File | Contenuto | Tipo |
|------|-----------|------|
| `getting-started.mdx` | Installazione npm, setup CSS, shadcn integration quickstart | Storybook page |
| `index.mdx` | Entry point del sito Storybook | Storybook page |
| `principles.mdx` | 6 principi di design | Storybook page |
| `roadmap.mdx` | Stato attuale (14 done) + prossimi step (3) + visione | Storybook page |
| `registry-model-1.md` | Architettura registry Model 1: struttura blocchi, naming, `registryDependencies` | Doc tecnica |
| `shadcn-integration.md` | Guida integrazione shadcn/ui: theming, token bridge, `shadcn.css` | Doc tecnica |

## Pipeline factory: docs/raw/ e docs/inbox/[^src: docs/raw/analisi-repository-2026-07-17.txt §1.4 docs/raw/ e docs/inbox/ — Pipeline factory]

### docs/raw/ — Input immutabili per il wiki-keeper

I file qui dentro sono sorgenti per l'ingest (`/sync-docs` → wiki-keeper agent). Una volta depositati, non vengono modificati — sono immutabili come fonte storica. Il wiki-keeper li legge e produce o aggiorna pagine in `wiki/`.

Flusso:
1. Documento raw depositato in `docs/raw/`
2. `/sync-docs` o trigger automatico attiva il wiki-keeper
3. Il wiki-keeper analizza, propone pagine, scrive in `wiki/`
4. Aggiorna `wiki/index.md` e `wiki/log.md`

### docs/inbox/ — Scratch zone umana

Area temporanea dove l'utente deposita file prima di promuoverli a `docs/raw/`. Il pattern prevede:
- Revisione in `inbox/` prima della promozione
- Promozione esplicita a `raw/` quando il file e' pronto per l'ingest
- `inbox/` svuotata dopo ogni promozione

## Roadmap — Stato corrente (2026-07-17)

Da `docs/roadmap.mdx`:[^src: docs/raw/analisi-repository-2026-07-17.txt §1.5 Documenti root-level di docs/]

**Completati (14)**: design tokens (12 temi), CSS variables, integrazione shadcn/Tailwind, Storybook, registry shadcn (Model 1).

**Prossimi step (3)**:
1. Esempi accessibilita' piu' estesi
2. Adapter altri framework
3. Evoluzione stories/registry

**Visione**: base solida, estendibile e manutenibile per prodotti reali.

## Nota: docs MDX vs wiki/

Le due strutture hanno ruoli diversi:

| Struttura | Audience | Aggiornamento | Stile |
|-----------|----------|---------------|-------|
| `docs/foundations/*.mdx` | Consumer del DS, Storybook | Manuale (dev) | MDX interattivo con Storybook Blocks |
| `wiki/` | Agenti factory, team interno | Wiki-keeper (ingest) | Markdown factory con frontmatter |

La wiki non sostituisce i docs MDX — li complementa con viste strutturate per il reasoning degli agenti.

## Pagine correlate

- [[brand-assets]] — dettaglio docs/brand-assets/
- [[design-principles]] — principi estratti da docs/principles.mdx
- [[token-architecture]] — architettura token (docs/foundations/tokens.mdx)
- [[icon-system]] — sistema icone (docs/foundations/icons.mdx)
