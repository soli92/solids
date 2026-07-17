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

## Pagine correlate

- [[token-architecture]] — struttura completa token base/semantic
- [[foundations/tokens]] — pipeline CSS e JSON tokens
- [[foundations/radius]] — token border radius (stessa logica scalare)
