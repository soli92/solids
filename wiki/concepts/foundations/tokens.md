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

## Aggiornamenti (v2026-11-26)

Le corrispondenze «M3 standard / emphasized» della tabella easing si riferiscono a **M3 pre-Expressive**: M3 Expressive ha sostituito durata + easing con il motion a molle; vedi [[material-3-expressive-2026]] §4 e §8. Stato (EP-002, GAP-006 parziale): aggiunti, senza toccare gli esistenti, i gruppi `measurement` (space0..space900), `breakpoint`, `motion.expressive/standard` (12 curve) e `layout.touch-target-material` in `base.json`, e `corner` e `motion.spring` in `semantic.json`.[^src: src/tokens/base.json §measurement][^src: src/tokens/semantic.json §corner] Totale: 192 token aggiunti, nessun token esistente cambiato o rimosso. `--sd-duration-*` e `--sd-easing-*` (tabelle sopra) sono invariati.

## Test automatici

`scripts/tokens-sanity.mjs` verifica completezza di `dist/tokens/tokens.json` e `dist/css/variables.css` dopo ogni build. Eseguito come parte di `npm test`.

---

## Pagine correlate

- [[token-architecture]] — guida completa base/semantic/temi e naming
- [[foundations/colors]] — catalogo token colore
- [[material-3-expressive-2026]] — riferimento M3 Expressive (motion a molle, spaziatura, raggi)
- [[foundations/spacing]] — scala spacing
- [[foundations/radius]] — scala border radius
- [[foundations/typography]] — token font
- [[foundations/accessibility-and-motion]] — utility motion e token touch target
