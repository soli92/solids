---
id: foundations-spacing
type: concept
title: "Foundations — Spacing"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/foundations/spacing.mdx §Regole fondamentali"
  - "docs/foundations/spacing.mdx §Scala di esempio (token numerici)"
---

# Foundations — Spacing

Lo spacing in SoliDS e' basato su una **scala numerica** in `base.json` e su **alias semantici** in `semantic.json` che mappano su passi della scala.[^src: docs/foundations/spacing.mdx §Regole fondamentali]

**Obiettivi**: ridurre variazioni arbitrarie, migliorare l'allineamento, rendere il layout prevedibile e scalabile.

---

## Regole fondamentali

- Usa **solo** valori della scala: `var(--sd-space-*)` o alias `--sd-space-xs` …
- Evita `px` arbitrari nei componenti
- Preferisci token semantici allo spacing "ad hoc"

---

## Scala numerica (token base)

| Token | Valore tipico | Uso tipico |
|-------|---------------|------------|
| `--sd-space-0` | 0 | reset / collapse |
| `--sd-space-1` | 4px | gap minimo |
| `--sd-space-2` | 8px | padding interno stretto |
| `--sd-space-3` | 12px | separazione elementi |
| `--sd-space-4` | 16px | layout standard |
| `--sd-space-5` | 20px | respiro medio |
| `--sd-space-6` | 24px | separazioni piu' ampie |

La lista completa (fino a `--sd-space-64`, piu' `px` / frazioni) e' in `dist/tokens/tokens.json` e `dist/css/variables.css`.[^src: docs/foundations/spacing.mdx §Scala di esempio (token numerici)]

---

## Alias semantici (token semantic)

Gli alias in `semantic.json` (es. `--sd-space-xs`, `--sd-space-sm`, `--sd-space-md`, `--sd-space-lg`, `--sd-space-xl`, `--sd-space-2xl`, `--sd-space-3xl`) mappano sui passi numerici della scala. Preferire gli alias nei componenti per significato piu' chiaro.

---

## Note

- I valori in pixel **non cambiano** tra temi (solo colori, font e raggio variano per tema)
- Lo spacing uniforme garantisce layout consistenti tra tutti i temi

---

## Aggiornamenti (v2026-11-26)

Material Design ha introdotto una scala di spaziatura a 8dp con token `spaceXXX` e la convenzione padding/gap/margin (dettagli in [[material-3-expressive-2026]] §2). Stato in soli-ds (EP-002, GAP-008 chiuso): aggiunti **`--sd-measurement-space0..space900`** (18 token, valori M3: 0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32, 36, 40, 48, 56, 64, 72px).[^src: src/tokens/base.json §measurement] La scala numerica `--sd-space-*` e gli alias semantici sono **invariati**.

Breakpoint M3 aggiunti in parallelo: `--sd-breakpoint-*` (compact 0, medium 600, expanded 840, large 1200, extra-large 1600px) e varianti Tailwind v4 `medium:` `expanded:` `large:` `extra-large:` (`sm..2xl` invariati; preset v3 legacy non toccato).[^src: src/tokens/base.json §breakpoint]

## Pagine correlate

- [[material-3-expressive-2026]] — spaziatura, densita' e breakpoint M3 Expressive (riferimento esterno)
- [[token-architecture]] — struttura completa token base/semantic
- [[foundations/tokens]] — pipeline CSS e JSON tokens
- [[foundations/radius]] — token border radius (stessa logica scalare)
