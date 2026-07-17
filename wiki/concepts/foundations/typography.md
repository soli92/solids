---
id: foundations-typography
type: concept
title: "Foundations — Typography"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/foundations/typography.mdx §Famiglie semantiche"
  - "docs/foundations/typography.mdx §Per tema (indicativo)"
  - "docs/foundations/typography.mdx §Dimensioni e pesi"
  - "docs/foundations/typography.mdx §Utility"
---

# Foundations — Typography

La tipografia in SoliDS e' guidata da **token CSS** (`--sd-font-*`, `--sd-font-size-*`, `--sd-font-weight-*`, `--sd-line-height-*`). I font stack per corpo, titoli e mono sono semantici: cambiano con il tema attivo.[^src: docs/foundations/typography.mdx §Famiglie semantiche]

## Obiettivi

- Leggibilita'
- Coerenza
- Scalabilita'

**Regola fondamentale**: nessun `font-size` hardcoded nei componenti quando esiste un token. Usare la scala coerente `--sd-font-size-*`. Separare famiglia (body / heading / mono), peso e interlinea.

---

## Famiglie semantiche

| Variabile | Uso |
|-----------|-----|
| `--sd-font-body` | Testo corrente, UI |
| `--sd-font-heading` | Titoli |
| `--sd-font-mono` | Codice, dati tabellari |

---

## Font per tema

| Tema | Body | Heading | Mono |
|------|------|---------|------|
| **Light / Dark** | Inter | DM Sans | JetBrains Mono |
| **Fantasy** | Source Serif 4 | Cinzel | JetBrains Mono |
| **Cyberpunk** | Space Grotesk | Orbitron | Share Tech Mono / JetBrains |
| **90s Party** | Tahoma / Verdana | Russo One / Impact | VT323 |
| **Steampunk** | Libre Baskerville / Baskerville | Cinzel / Copperplate | JetBrains Mono / Courier Prime |
| **Ichigo** | (sistema) | Bebas Neue | JetBrains Mono |
| **Captain America** | (sistema) | Oswald | JetBrains Mono |
| **Vegeta / Sasuke** | (sistema) | Rajdhani | JetBrains Mono |
| **Zoro / Inuyasha** | Merriweather | Merriweather / Crimson Text | JetBrains Mono |

I font Google vengono caricati in Storybook via `.storybook/preview-head.html`. Nei consumer: aggiungere gli stessi `@import` Google Fonts o self-host secondo policy.[^src: docs/foundations/typography.mdx §Per tema (indicativo)]

---

## Scala dimensioni e pesi

- **Dimensioni**: `--sd-font-size-xs` … `--sd-font-size-6xl` (valori completi in `dist/css/variables.css` o `tokens.json`)
- **Pesi**: `--sd-font-weight-light` … `--sd-font-weight-extrabold`

---

## Utility CSS

In `utilities.css`:

| Classe | Uso |
|--------|-----|
| `.sd-font-sans` | Font body dal token |
| `.sd-font-heading` | Font heading dal token |
| `.sd-font-mono` | Font mono dal token |
| `.sd-text-*` | Utility testo `--sd-font-size-*` |

Con il **preset Tailwind**: `font-heading` e `font-serif` usano `--sd-font-heading`.[^src: docs/foundations/typography.mdx §Utility]

**Nota**: la tipografia puo' evolvere nei JSON tema senza cambiare l'API dei consumer — restano gli stessi nomi di variabile.

---

## CDN Google Fonts (riferimento rapido)

- **Default UI**: [Inter](https://fonts.google.com/specimen/Inter), [DM Sans](https://fonts.google.com/specimen/DM+Sans), [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono)
- **Fantasy**: [Cinzel](https://fonts.google.com/specimen/Cinzel), [Source Serif 4](https://fonts.google.com/specimen/Source+Serif+4)
- **Cyberpunk**: [Orbitron](https://fonts.google.com/specimen/Orbitron), [Space Grotesk](https://fonts.google.com/specimen/Space+Grotesk), [Share Tech Mono](https://fonts.google.com/specimen/Share+Tech+Mono)
- **90s Party**: [Russo One](https://fonts.google.com/specimen/Russo+One), [VT323](https://fonts.google.com/specimen/VT323)
- **Steampunk**: [Cinzel](https://fonts.google.com/specimen/Cinzel), [Libre Baskerville](https://fonts.google.com/specimen/Libre+Baskerville)
- **Personaggio**: [Bebas Neue](https://fonts.google.com/specimen/Bebas+Neue), [Oswald](https://fonts.google.com/specimen/Oswald), [Rajdhani](https://fonts.google.com/specimen/Rajdhani), [Merriweather](https://fonts.google.com/specimen/Merriweather), [Crimson Text](https://fonts.google.com/specimen/Crimson+Text)

---

## Pagine correlate

- [[foundations/themes]] — identita' visiva per tema con valori token
- [[token-architecture]] — struttura token base/semantic
- [[foundations/tokens]] — pipeline CSS e JSON tokens
- [[foundations/accessibility-and-motion]] — utility `.sd-leading-*` e font access
