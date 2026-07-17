---
id: foundations-colors
type: concept
title: "Foundations — Colors"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/foundations/colors.mdx §Semantic color tokens"
  - "docs/foundations/colors.mdx §Anteprima visiva per tema"
---

# Foundations — Colors

SoliDS utilizza **color tokens semantici**, non colori grezzi. I valori dipendono dal **tema attivo** (`data-theme`): ogni JSON in `themes/` ridefinisce la stessa struttura semantica.[^src: docs/foundations/colors.mdx §Semantic color tokens]

**Regola fondamentale**: i consumer non devono mai usare direttamente la palette base (es. `gray.900`, `blue.600`), ma solo token con significato.

---

## Catalogo token semantico

### Text

| Token | Uso |
|-------|-----|
| `--sd-color-text-primary` | Testo principale |
| `--sd-color-text-secondary` | Testo secondario |
| `--sd-color-text-tertiary` | Testo terziario, note |
| `--sd-color-text-disabled` | Testo disabilitato |
| `--sd-color-text-inverse` | Testo su sfondo invertito |
| `--sd-color-text-link` | Link (testo) |
| `--sd-color-text-link-hover` | Link hover |

### Background

| Token | Uso |
|-------|-----|
| `--sd-color-bg-canvas` | Sfondo principale pagina |
| `--sd-color-bg-surface` | Superfici (card, panel) |
| `--sd-color-bg-elevated` | Elementi sovrapposti (modal, dropdown) |
| `--sd-color-bg-overlay` | Overlay trasparente |
| `--sd-color-bg-overlay-hover` | Overlay hover state |
| `--sd-color-bg-overlay-active` | Overlay active state |
| `--sd-color-bg-overlay-disabled` | Overlay disabled state |

### Border

| Token | Uso |
|-------|-----|
| `--sd-color-border-default` | Bordo standard |
| `--sd-color-border-muted` | Bordo attenuato |
| `--sd-color-border-strong` | Bordo enfatizzato |
| `--sd-color-border-focus` | Anello di focus (`:focus-visible`) |
| `--sd-color-border-disabled` | Bordo elemento disabilitato |

### Intent

| Token | Varianti disponibili |
|-------|---------------------|
| `--sd-color-intent-success` | + `-bg`, `-border` |
| `--sd-color-intent-warning` | + `-bg`, `-border` |
| `--sd-color-intent-danger` | + `-bg`, `-border` |
| `--sd-color-intent-info` | + `-bg`, `-border` |

### Icon

Token usati dalle icone SoliDS e utility `.sd-icon`, `.sd-icon-muted`, …

| Token | Uso |
|-------|-----|
| `--sd-color-icon-default` | Icona standard |
| `--sd-color-icon-muted` | Icona secondaria / decorativa |
| `--sd-color-icon-primary` | Icona in evidenza |
| `--sd-color-icon-on-primary` | Icona su sfondo primary |

### Componenti (brand)

| Gruppo | Prefisso |
|--------|---------|
| Primary | `--sd-color-primary-*` |
| Secondary | `--sd-color-secondary-*` |
| Muted | `--sd-color-muted-*` |
| Accent | `--sd-color-accent-*` |
| Destructive | `--sd-color-destructive-*` |

[^src: docs/foundations/colors.mdx §Semantic color tokens]

---

## Valori per tema (chiave light/dark)

Vedi [[foundations/themes]] per i valori esatti di ogni token per ciascuno dei 12 temi disponibili.

Valori light/dark rapidi:

| Token | Light | Dark |
|-------|-------|------|
| `--sd-color-text-primary` | `#111827` | `#F9FAFB` |
| `--sd-color-bg-canvas` | `#FAFBFC` | `#0C0E12` |
| `--sd-color-bg-surface` | `#F0F2F5` | `#161922` |
| `--sd-color-primary-default` | `#2563EB` | `#3B82F6` |
| `--sd-color-border-default` | `#E2E5EA` | `#2E3545` |

---

## Principio di isolamento tematico

Tutti i token semantici sono ridefiniti per ogni tema — un componente che usa solo token `--sd-color-*` non richiede modifiche al cambio di tema. Questo e' il nucleo del principio [[design-principles|Semantic over visual]].[^src: docs/foundations/colors.mdx §Anteprima visiva per tema]

---

## Pagine correlate

- [[foundations/themes]] — valori token per tutti i 12 temi
- [[shadcn-integration]] — mapping shadcn vars → SoliDS tokens
- [[token-architecture]] — struttura base/semantic/temi
- [[design/a11y-token-audit]] — audit WCAG AA coppie colore
