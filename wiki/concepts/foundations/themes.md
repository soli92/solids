---
id: foundations-themes
type: concept
title: "Foundations — Themes"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/foundations/themes.mdx §Temi disponibili"
  - "docs/foundations/themes.mdx §Identita' visiva e palette"
  - "docs/foundations/themes.mdx §Attivazione"
  - "docs/foundations/themes.mdx §Font opzionali (CDN)"
---

# Foundations — Themes

SoliDS applica i temi con **override dei token semantici** (colori, font, raggio, ombre): gli stessi nomi di variabile CSS (`--sd-*`) cambiano valore in base a `data-theme` su `<html>` (o `:root`). Nessuna duplicazione di componenti — cambiano solo i token.[^src: docs/foundations/themes.mdx §Temi disponibili]

---

## Temi disponibili

| Tema | `data-theme` | Identita' visiva |
|------|-------------|-----------------|
| **Light** | `light` o default `:root` | Interfaccia pulita MD3; corpo Inter, titoli DM Sans |
| **Dark** | `dark` | Profondita' elevata su slate quasi-nero; accenti blu elettrico |
| **Fantasy** | `fantasy` | Pergamena medievale: canvas avorio, accenti oro antico |
| **Cyberpunk** | `cyberpunk` | Neon cyan/magenta su fondi quasi-neri; font tecnici |
| **90s Party** | `90s-party` | Esplosione rave: magenta/teal/lime su viola profondo |
| **Steampunk** | `steampunk` | Laboratorio vittoriano in ottone e cuoio |
| **Ichigo** | `ichigo` | Minimalismo Bankai: nero profondo con fiamme arancio-rosse |
| **Vegeta** | `vegeta` | Armatura saiyan: blu royal su notte scura, accenti oro |
| **Zoro** | `zoro` | Dojo del vento: verde profondo e acciaio katana |
| **Captain America** | `captain-america` | Patriottico: blu notte, rosso primario, bianco argento |
| **Sasuke** | `sasuke` | Chidori nella notte: nero slate e viola indaco freddo |
| **Inuyasha** | `inuyasha` | Haori rosso su terra feudale: canvas legno scuro |

---

## Comportamento sistema

- Se `data-theme` non e' impostato, `prefers-color-scheme: dark` applica i token **dark**
- Con temi espliciti, il tema resta quello scelto indipendentemente dalla preferenza OS
- Tailwind `dark:` tratta come scuri: `dark`, `cyberpunk`, `90s-party`, `steampunk`, `captain-america`, `ichigo`, `inuyasha`, `sasuke`, `vegeta`, `zoro`

[^src: docs/foundations/themes.mdx §Temi disponibili]

---

## Token chiave per tema

### Light

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#111827` |
| `--sd-color-bg-canvas` | `#FAFBFC` |
| `--sd-color-primary-default` | `#2563EB` |
| `--sd-color-icon-default` | `#111827` |
| `--sd-color-icon-primary` | `#2563EB` |
| `--sd-font-body` | Inter |
| `--sd-font-heading` | DM Sans |
| `--sd-radius-md` | 12px |

### Dark

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#F9FAFB` |
| `--sd-color-bg-canvas` | `#0C0E12` |
| `--sd-color-primary-default` | `#3B82F6` |
| `--sd-color-icon-default` | `#F9FAFB` |
| `--sd-color-icon-primary` | `#60A5FA` |
| `--sd-font-body` | Inter |
| `--sd-font-heading` | DM Sans |
| `--sd-radius-md` | 12px |

### Fantasy

Icone tema: **Scroll**, **Sword**, **Gem**.

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#2c1810` |
| `--sd-color-bg-canvas` | `#f0e6d2` |
| `--sd-color-primary-default` | `#8b6914` |
| `--sd-color-icon-default` | `#3d2914` |
| `--sd-color-icon-primary` | `#a67c00` |
| `--sd-font-body` | Source Serif 4 |
| `--sd-font-heading` | Cinzel |
| `--sd-radius-md` | 10px |
| `--sd-shadow-md` | warm sepia tones |

### Cyberpunk

Icone tema: **Chip**, **Eye**, **Signal**.

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#e8e9ff` |
| `--sd-color-bg-canvas` | `#070714` |
| `--sd-color-primary-default` | `#06b6d4` |
| `--sd-color-icon-default` | `#e0e7ff` |
| `--sd-color-icon-primary` | `#22d3ee` |
| `--sd-font-body` | Space Grotesk |
| `--sd-font-heading` | Orbitron |
| `--sd-radius-md` | 4px |
| `--sd-shadow-md` | cyan neon glow |

### 90s Party

Icone tema: **Bolt**, **Diamond**, **Star**.

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#f8f5ff` |
| `--sd-color-bg-canvas` | `#0f0520` |
| `--sd-color-primary-default` | `#e019dd` |
| `--sd-color-icon-default` | `#f0abfc` |
| `--sd-color-icon-primary` | `#d4ff00` |
| `--sd-font-body` | Tahoma/Verdana |
| `--sd-font-heading` | Russo One |
| `--sd-radius-md` | 6px |
| `--sd-shadow-md` | offset + magenta glow |

### Steampunk

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#ede4d3` |
| `--sd-color-bg-canvas` | `#120e0b` |
| `--sd-color-primary-default` | `#c9a227` |
| `--sd-color-icon-default` | `#ede4d3` |
| `--sd-color-icon-primary` | `#c9a227` |
| `--sd-font-body` | Libre Baskerville |
| `--sd-font-heading` | Cinzel |
| `--sd-radius-md` | 6px |
| `--sd-shadow-md` | brass border glow |

### Ichigo

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#fafafa` |
| `--sd-color-bg-canvas` | `#09090b` |
| `--sd-color-primary-default` | `#ea580c` |
| `--sd-color-icon-primary` | `#ea580c` |
| `--sd-font-heading` | Bebas Neue |
| `--sd-radius-md` | 6px |

### Vegeta

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#f8fafc` |
| `--sd-color-bg-canvas` | `#0c1929` |
| `--sd-color-primary-default` | `#2563eb` |
| `--sd-color-icon-primary` | `#3b82f6` |
| `--sd-font-heading` | Rajdhani |
| `--sd-radius-md` | 8px |

### Zoro

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#ecfdf5` |
| `--sd-color-bg-canvas` | `#022c22` |
| `--sd-color-primary-default` | `#10b981` |
| `--sd-color-icon-primary` | `#34d399` |
| `--sd-font-body` | Merriweather |
| `--sd-font-heading` | Merriweather |
| `--sd-radius-md` | 6px |

### Captain America

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#f1f5f9` |
| `--sd-color-bg-canvas` | `#0f172a` |
| `--sd-color-primary-default` | `#dc2626` |
| `--sd-color-icon-primary` | `#dc2626` |
| `--sd-font-heading` | Oswald |
| `--sd-radius-md` | 8px |

### Sasuke

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#e2e8f0` |
| `--sd-color-bg-canvas` | `#020617` |
| `--sd-color-primary-default` | `#8b5cf6` |
| `--sd-color-icon-primary` | `#a78bfa` |
| `--sd-font-heading` | Rajdhani |
| `--sd-radius-md` | 4px |

### Inuyasha

| Token | Valore |
|-------|--------|
| `--sd-color-text-primary` | `#fef3c7` |
| `--sd-color-bg-canvas` | `#1c1917` |
| `--sd-color-primary-default` | `#b91c1c` |
| `--sd-color-icon-primary` | `#b91c1c` |
| `--sd-font-body` | Merriweather |
| `--sd-font-heading` | Crimson Text |
| `--sd-radius-md` | 10px |

[^src: docs/foundations/themes.mdx §Identita' visiva e palette]

---

## Attivazione

```html
<html data-theme="light"></html>
<html data-theme="dark"></html>
<html data-theme="fantasy"></html>
<html data-theme="cyberpunk"></html>
<html data-theme="90s-party"></html>
<html data-theme="steampunk"></html>
<html data-theme="ichigo"></html>
<html data-theme="vegeta"></html>
<html data-theme="zoro"></html>
<html data-theme="captain-america"></html>
<html data-theme="sasuke"></html>
<html data-theme="inuyasha"></html>
```

[^src: docs/foundations/themes.mdx §Attivazione]

---

## Font CDN opzionali

- **Default UI**: Inter, DM Sans, JetBrains Mono
- **Fantasy**: Cinzel, Source Serif 4
- **Cyberpunk**: Orbitron, Space Grotesk, Share Tech Mono
- **90s Party**: Russo One, VT323
- **Steampunk**: Cinzel, Libre Baskerville
- **Personaggio**: Bebas Neue, Oswald, Rajdhani, Merriweather, Crimson Text

Senza CDN, gli stack degradano su serif/sans/mono di sistema.[^src: docs/foundations/themes.mdx §Font opzionali (CDN)]

---

## Pagine correlate

- [[shadcn-integration]] — setup shadcn con temi SoliDS
- [[foundations/typography]] — dettaglio font per tema
- [[foundations/colors]] — catalogo token colore
- [[foundations/radius]] — `--sd-radius-md` per tema
- [[icon-system]] — icone tematiche per fantasy/cyberpunk/90s-party
