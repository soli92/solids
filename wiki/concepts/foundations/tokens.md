---
id: foundations-tokens
type: concept
title: "Foundations — Design Tokens (pipeline)"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/foundations/tokens.mdx §Struttura del JSON pubblicato"
  - "docs/foundations/tokens.mdx §Pipeline CSS (ordine di import)"
  - "docs/foundations/tokens.mdx §Motion (base)"
---

# Foundations — Design Tokens (pipeline)

I token sono la **singola fonte di verita'** per colori, spazi, tipografia, raggio, ombre, motion e z-index. SoliDS li espone come JSON e come CSS variables.[^src: docs/foundations/tokens.mdx §Struttura del JSON pubblicato]

Per l'architettura generale dei token (naming, base/semantic/temi, come creare un tema), vedi [[token-architecture]].

---

## Struttura del JSON pubblicato

`dist/tokens/tokens.json` unisce tre livelli:

| Livello | Contenuto |
|---------|-----------|
| **`base`** | Palette grezza, scala spacing numerica, radius base, font base, shadow, easing, z-index |
| **`semantic`** | Significati (testo, sfondo, border, intent, primary, …) con default "light" |
| **`themes`** | Override per ogni file in `src/tokens/themes/*.json` (light, dark, fantasy, cyberpunk, 90s-party, steampunk, temi personaggio) |

Accesso in JavaScript:

```js
import tokens from "@soli92/solids/tokens";

// tokens.semantic, tokens.base, tokens.themes.dark, …
```

[^src: docs/foundations/tokens.mdx §Struttura del JSON pubblicato]

---

## Pipeline CSS (ordine di import)

L'entrypoint `@soli92/solids/css/index.css` importa nell'ordine:

| Step | File | Contenuto |
|------|------|-----------|
| 1 | `variables.css` | `:root` con base + semantic + merge tema light |
| 2 | `themes.css` | Blocchi `[data-theme="…"]` per ogni tema + fallback `prefers-color-scheme: dark` |
| 3 | `shadcn.css` | Mapping verso variabili shadcn (`--background`, `--primary`, …) |
| 4 | `base.css` | Reset e stili globali |
| 5 | `utilities.css` | Classi `sd-*` |

[^src: docs/foundations/tokens.mdx §Pipeline CSS (ordine di import)]

---

## Motion (token base)

In `base.json`: durate e curve MD3-friendly.

### Token durata

Prefisso `--sd-duration-*`. Token chiavi:

| Token | Uso |
|-------|-----|
| `--sd-duration-emphasized` | Transizioni enfatizzate (default 350ms) |
| (altri) | Vedi `dist/css/variables.css` |

### Token easing

| Token | Corrispondenza MD3 |
|-------|-------------------|
| `--sd-easing-standard` | M3 standard |
| `--sd-easing-emphasized-decelerate` | M3 emphasized decelerate |
| `--sd-easing-emphasized-accelerate` | M3 emphasized accelerate |
| `--sd-easing-ease-in` | ease-in |
| `--sd-easing-ease-out` | ease-out |
| `--sd-easing-ease-inout` | ease-in-out |

[^src: docs/foundations/tokens.mdx §Motion (base)]

---

## Test automatici

`scripts/tokens-sanity.mjs` verifica completezza di `dist/tokens/tokens.json` e `dist/css/variables.css` dopo ogni build. Eseguito come parte di `npm test`.

---

## Pagine correlate

- [[token-architecture]] — guida completa base/semantic/temi e naming
- [[foundations/colors]] — catalogo token colore
- [[foundations/spacing]] — scala spacing
- [[foundations/radius]] — scala border radius
- [[foundations/typography]] — token font
- [[foundations/accessibility-and-motion]] — utility motion e token touch target
