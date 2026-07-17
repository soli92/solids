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
| `--sd-radius-2xl` | Molto arrotondato | ~24px |
| `--sd-radius-3xl` | Ancora piu' ampio | ~32px |
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

## Pagine correlate

- [[foundations/themes]] — `--sd-radius-md` per tema
- [[shadcn-integration]] — come `--radius` mappa su `--sd-radius-md`
- [[token-architecture]] — struttura token base/semantic
