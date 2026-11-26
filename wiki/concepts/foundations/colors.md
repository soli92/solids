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

## Aggiornamenti (v2026-11-26, 3.3.0)

Difetti segnalati dalla sessione della plancia, corretti in EP-005 / US-009 (GAP-014):

- **Intent come testo**: i colori `--sd-color-intent-*` usati come testo erano sotto AA in vari temi (light success 2.94, warning 2.84, danger 4.31; captain-america info 2.82; fantasy warning 3.48; zoro, vegeta, 90s-party danger < 4.5). Nuovi token **`--sd-color-intent-{success,warning,danger,info}-text`**: >= 4.5:1 su canvas/surface/elevated in ogni tema, 7:1 dove la tinta lo consente (light e dark tutti a 7:1). Per il testo usare `-text`, non il token base.[^src: management/kanban/EP-005-gap013-e-difetti-plancia/US-009-difetti-dalla-plancia/US-009.md §AC2][^src: src/tokens/themes/light.json §intent]
- **`--sd-color-border-strong`** portato a >= 3:1 (WCAG 1.4.11): light 2.26 → 3.14, dark 2.06 → 3.11, captain-america 2.18 → 3.11.[^src: management/kanban/EP-005-gap013-e-difetti-plancia/US-009-difetti-dalla-plancia/US-009.md §AC3]

Aggiornamento alla tabella Intent sopra: ogni intent ha anche la variante `-text`. Verifica: `tokens-sanity` (calcolo WCAG in JS).

## Principio di isolamento tematico

Tutti i token semantici sono ridefiniti per ogni tema — un componente che usa solo token `--sd-color-*` non richiede modifiche al cambio di tema. Questo e' il nucleo del principio [[design-principles|Semantic over visual]].[^src: docs/foundations/colors.mdx §Anteprima visiva per tema]

---

## Pagine correlate

- [[foundations/themes]] — valori token per tutti i 12 temi
- [[shadcn-integration]] — mapping shadcn vars → SoliDS tokens
- [[token-architecture]] — struttura base/semantic/temi
- [[design/a11y-token-audit]] — audit WCAG AA coppie colore
