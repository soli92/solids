---
id: roadmap
type: concept
title: "SoliDS — Roadmap"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/roadmap.mdx §Stato attuale"
  - "docs/roadmap.mdx §Prossimi step"
  - "docs/roadmap.mdx §Visione"
---

# SoliDS — Roadmap

Stato attuale e prossimi passi del design system `@soli92/solids`, da `docs/roadmap.mdx`.[^src: docs/roadmap.mdx §Stato attuale]

---

## Stato attuale (completato)

| Categoria | Dettaglio |
|-----------|-----------|
| **Token** | Base + semantic + temi light, dark, fantasy, cyberpunk, 90s-party, steampunk, sei temi personaggio |
| **Test automatici** | `npm run test:tokens` — `scripts/tokens-sanity.mjs` su `dist/tokens/tokens.json` + `variables.css` |
| **CSS pipeline** | CSS variables e pipeline `index.css` con default MD3-oriented per light/dark |
| **Dark fallback** | `prefers-color-scheme: dark` senza `data-theme` |
| **Base + utility CSS** | `.sd-font-heading`, motion `standard` / `emphasized-*` |
| **Tailwind preset** | `fontFamily.heading`, `dark:` per temi scuri nominati, layer shadcn |
| **Storybook** | Foundations + SoliDS/UI; toolbar Tema DS (tutti i temi); `npm test` = build + static SB |
| **GitHub Pages** | Deploy automatico con release: [soli92.github.io/solids](https://soli92.github.io/solids/) |
| **Registry shadcn** | Modello 1, kit `solids-ui` con namespace `@solids` |

[^src: docs/roadmap.mdx §Stato attuale]

---

## Prossimi step

- Esempi e linee guida accessibilita' piu' estese
- Adapter / snippet per altri framework oltre a React (documentazione)
- Evoluzione continua delle story e del registry

[^src: docs/roadmap.mdx §Prossimi step]

---

## Visione

SoliDS vuole restare una base **solida, estendibile e manutenibile** per prodotti reali, con token e temi coerenti indipendentemente dallo stack UI.[^src: docs/roadmap.mdx §Visione]

---

## Pagine correlate

- [[token-architecture]] — architettura token
- [[registry-model-1]] — registry shadcn
- [[development-history]] — fasi di sviluppo passate
- [[design-principles]] — principi fondanti del DS
