---
id: foundations-radius
type: concept
title: "Foundations — Border Radius"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/foundations/radius.mdx §Token CSS (default light / base)"
  - "docs/foundations/radius.mdx §Utility"
  - "docs/foundations/radius.mdx §Linee guida"
---

# Foundations — Border Radius

I border radius sono esposti come **CSS variables** `--sd-radius-*`, da `src/tokens/base.json` con override in `semantic.json` e nei JSON tema.[^src: docs/foundations/radius.mdx §Token CSS (default light / base)]

Per **light** / **dark** i passi semantici tipici sono **8px / 12px / 16px / 20px** (sm → xl), in linea con Material Design 3. I temi nominati (fantasy, cyberpunk, 90s-party, steampunk, personaggio) possono sovrascrivere.

---

## Token CSS (default light/base)

| Variabile | Ruolo | Valore light tipico |
|-----------|-------|---------------------|
| `--sd-radius-none` | Nessun raggio | `0` |
| `--sd-radius-sm` | Piccolo | ~4–8px |
| `--sd-radius-md` | Standard (shadcn `--radius`) | 12px |
| `--sd-radius-lg` | Grande | ~16px |
| `--sd-radius-xl` | Extra large | ~20px |
| `--sd-radius-2xl` | Molto arrotondato | 28px (dalla 3.0.0; in 2.x 20px) |
| `--sd-radius-3xl` | Ancora piu' ampio | 32px (dalla 3.0.0; in 2.x 24px) |
| `--sd-radius-full` | Pill / cerchio | `9999px` |

`--sd-radius-md` e' il valore usato da shadcn/ui (`--radius` nel layer `shadcn.css`).

---

## Valori per tema (--sd-radius-md)

| Tema | `--sd-radius-md` |
|------|-----------------|
| Light / Dark | 12px |
| Fantasy | 10px |
| Cyberpunk | 4px |
| 90s Party | 6px |
| Steampunk | 6px |
| Ichigo | 6px |
| Vegeta | 8px |
| Captain America | 8px |
| Inuyasha | 10px |
| Sasuke | 4px |

[^src: docs/foundations/radius.mdx §Token CSS (default light / base)]

---

## Utility CSS

Classi in `utilities.css`:

| Classe | Token |
|--------|-------|
| `.sd-rounded-none` | `--sd-radius-none` |
| `.sd-rounded-sm` | `--sd-radius-sm` |
| `.sd-rounded-md` | `--sd-radius-md` |
| `.sd-rounded-lg` | `--sd-radius-lg` |
| `.sd-rounded-xl` | `--sd-radius-xl` |
| `.sd-rounded-full` | `--sd-radius-full` |

Con il preset Tailwind SoliDS, `rounded-lg` / `rounded-md` / `rounded-sm` dei componenti shadcn seguono `--radius` → `--sd-radius-md` del tema attivo.[^src: docs/foundations/radius.mdx §Utility]

---

## Linee guida

- Parti dal token piu' piccolo adeguato al contesto
- Evita valori arbitrari nei componenti; allinea componenti simili allo stesso step
- Per shadcn/ui, `--radius` nel layer `shadcn.css` punta a `--sd-radius-md` e segue i token del tema attivo[^src: docs/foundations/radius.mdx §Linee guida]

---

## Aggiornamenti (v2026-11-26)

Il «in linea con Material Design 3» di questa pagina si riferisce a **M3 pre-Expressive**. M3 Expressive ha una scala dei raggi diversa; vedi [[material-3-expressive-2026]] §5. Stato in soli-ds (EP-002, GAP-007 chiuso con la 3.0.0): in 2.1.0 aggiunta la scala **`--sd-corner-*` a 10 gradi** (`none`, `extra-small`, `small`, `medium`, `large`, `large-increased`, `extra-large`, `extra-large-increased`, `extra-extra-large`, `full`) con valori M3 esatti su light/dark: 0/4/8/12/16/20/28/32/48px/full.[^src: src/tokens/semantic.json §corner] Per i temi nominati: `small`..`large-increased` = radius sm..xl del tema, `extra-small` = sm/2, gradi ampi = xl x1.4 / x1.6 / x2.4. Utility `.sd-corner-*` in `utilities.css`.[^src: src/css/utilities.css §Corner scale (M3, 10 steps; per-theme values)] Dalla **3.0.0** (EP-002 / US-003, breaking) `--sd-radius-2xl` / `--sd-radius-3xl` valgono 28/32px su light/dark e nei temi nominati coincidono con il corner `extra-large` / `extra-large-increased` del tema (in 2.x: 20/24px in tutti i temi).[^src: src/tokens/base.json §radius][^src: src/tokens/themes/light.json §radius] Gli altri `--sd-radius-*` sono invariati. Migrazione e ripristino dei valori 2.x: README §Migrazione 2.x → 3.0.[^src: README.md §Migrazione 2.x → 3.0]

## Pagine correlate

- [[material-3-expressive-2026]] — scala raggi e shape M3 Expressive (riferimento esterno)
- [[foundations/themes]] — `--sd-radius-md` per tema
- [[shadcn-integration]] — come `--radius` mappa su `--sd-radius-md`
- [[token-architecture]] — struttura token base/semantic
