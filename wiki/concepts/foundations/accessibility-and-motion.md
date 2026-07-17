---
id: foundations-accessibility-and-motion
type: concept
title: "Foundations — Accessibilita' e Motion"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/foundations/accessibility-and-motion.mdx §Cosa fa gia' SoliDS"
  - "docs/foundations/accessibility-and-motion.mdx §Migliorie introdotte (token + CSS + utility)"
  - "docs/foundations/accessibility-and-motion.mdx §Cosa resta responsabilita' del consumer"
  - "docs/foundations/accessibility-and-motion.mdx §Riferimenti rapidi nel repo"
---

# Foundations — Accessibilita' e Motion

Come SoliDS si allinea a linee guida riconosciute (WCAG 2.2, Material Design 3, Apple HIG) con token e utility nel codice.[^src: docs/foundations/accessibility-and-motion.mdx §Cosa fa gia' SoliDS]

---

## Fonti di riferimento

| Argomento | Fonte |
|-----------|-------|
| WCAG 2.2 (contrasto, focus, riduzione movimento, target size) | [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) |
| Target size minimo (2.5.8) | [Understanding Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) |
| Animazioni e preferenze utente | [Understanding Animation from Interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html) |
| Material Design 3 — Motion | [M3 Motion overview](https://m3.material.io/styles/motion/overview) |
| Material Design 3 — Typography | [M3 Typography](https://m3.material.io/styles/typography/overview) |
| Apple HIG — Accessibility | [Accessibility — Apple Developer Documentation](https://developer.apple.com/design/human-interface-guidelines/accessibility) |

---

## Cosa fa gia' SoliDS

| Funzionalita' | Dettaglio |
|--------------|-----------|
| **Focus visibile** (`:focus-visible`) | Anello 2px + offset, colore `--sd-color-border-focus` |
| **`prefers-reduced-motion: reduce`** | In `base.css` vengono disattivate transizioni, animazioni e scroll animato globalmente |
| **Curve e durate** | `--sd-easing-*`, `--sd-duration-*` con naming coerente con MD3 (`standard`, `emphasized-decelerate`) |
| **Tema e `color-scheme`** | Valorizzato per light/dark e temi scuri, per controlli nativi coerenti |

[^src: docs/foundations/accessibility-and-motion.mdx §Cosa fa gia' SoliDS]

---

## Migliorie introdotte (token + CSS + utility)

### Tipografia e font

Font predefiniti ottimizzati per leggibilita': Inter / DM Sans / JetBrains Mono (light/dark). Vedi [[foundations/typography]] per font per tema.[^src: docs/foundations/accessibility-and-motion.mdx §Migliorie introdotte (token + CSS + utility)]

### Layout e scroll

- **`scroll-padding-top`** su `html`: riduce il rischio che barre sticky coprano il contenuto dopo navigazione ad anchor
- **`scroll-behavior: smooth`** solo se `prefers-reduced-motion: no-preference` — non forza movimento quando l'utente chiede riduzione animazioni

### Touch target e link

| Artefatto | Dettaglio |
|-----------|-----------|
| `--sd-layout-touch-target-min` | `44px` in `base.json` — allineato a WCAG 2.5.8 e Apple HIG 44×44px |
| `.sd-min-touch-target` | Applica `min-width` / `min-height` al token (pulsanti, chip, icone cliccabili) |
| `.sd-link` | Colore token + sottolineatura con offset e spessore minimi — non dipende solo dal colore (cfr. WCAG 1.4.1) |

### Motion nelle utility

| Classe | Comportamento |
|--------|--------------|
| `.sd-transition` | Durate e easing da token |
| `.sd-transition-fast` | Durata rapida da token |
| `.sd-transition-emphasized` | Attiva solo con `prefers-reduced-motion: no-preference`; durata `--sd-duration-emphasized` (350ms); easing emphasized-decelerate |

### Interlinea

`.sd-leading-*` usano `--sd-font-leading-*` da `base.json` dove disponibili (`none`, `tight`, `snug`, `normal`, `relaxed`, `loose`).

---

## Responsabilita' del consumer

- Verificare **contrasto** reale su combinazioni custom (tool: [APCA](https://readtech.org/ARC/), [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/))
- Fornire **testi alternativi**, **heading logici**, **ordine focus** nei componenti React/Vue
- Non disattivare `prefers-reduced-motion` con override aggressivi

[^src: docs/foundations/accessibility-and-motion.mdx §Cosa resta responsabilita' del consumer]

---

## Riferimenti rapidi nel repo

| Artefatto | Ruolo |
|-----------|-------|
| `src/tokens/base.json` | `layout.touch-target-min`, `duration.emphasized`, `font.leading.*` |
| `src/tokens/semantic.json` | Font default Inter / DM Sans / JetBrains Mono |
| `src/tokens/themes/*.json` | Override font per tema |
| `src/css/base.css` | Scroll, body, focus, reduced motion |
| `src/css/utilities.css` | `.sd-min-touch-target`, `.sd-link`, leading, `.sd-transition-emphasized` |

[^src: docs/foundations/accessibility-and-motion.mdx §Riferimenti rapidi nel repo]

---

## Pagine correlate

- [[design-principles]] — Principio 6: Accessibilita' by default
- [[design/a11y-token-audit]] — Audit WCAG AA coppie colore nei token
- [[foundations/tokens]] — token `--sd-duration-*`, `--sd-easing-*`
- [[foundations/typography]] — font stack per leggibilita'
