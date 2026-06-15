---
id: token-architecture
type: concept
title: "SoliDS — Token Architecture"
status: stable
created: 2026-06-15
updated: 2026-06-15
---

# SoliDS — Token Architecture

## Struttura directory

```
src/tokens/
  base.json          — primitivi assoluti (palette, spacing, radii, font, shadow, easing, z)
  semantic.json      — alias semantici con defaults tema light
  themes/
    light.json       — override light (ripete i defaults per explicitness)
    dark.json        — override dark
    cyberpunk.json   — neon cyan/magenta su base profonda
    fantasy.json     — ...
    90s-party.json
    steampunk.json
    ichigo.json / vegeta.json / zoro.json
    captain-america.json / sasuke.json / inuyasha.json
```

## Naming convention

### Primitivi (`base.json`)

Formato: `<categoria>.<scala-o-nome>`

| Categoria | Esempi | Note |
|-----------|--------|------|
| `color.<palette>.<step>` | `color.gray.500`, `color.blue.700` | Tailwind-style 50..950 |
| `color.white / .black / .transparent` | Speciali senza scala | |
| `space.<step>` | `space.4` (= 16px), `space.px` (= 1px) | Tailwind-style 0..96 |
| `radius.<step>` | `radius.sm` (8px) .. `radius.full` (9999px) | |
| `font.<role>` | `font.body`, `font.heading`, `font.mono` | Font stack completo |
| `shadow.<step>` | `shadow.sm` .. `shadow.xl` | rgba layered |
| `duration.<step>` | `duration.fast`, `duration.normal`, `duration.slow` | ms |
| `easing.<name>` | `easing.standard`, `easing.emphasized` | cubic-bezier |
| `layout.<name>` | `layout.max-width` | px |
| `z.<name>` | `z.modal`, `z.tooltip` | z-index scale |

### Semantici (`semantic.json`)

Formato: `color.<role>.<variant>`

| Gruppo | Esempi |
|--------|--------|
| `color.text.*` | `primary`, `secondary`, `tertiary`, `disabled`, `inverse`, `link`, `link-hover` |
| `color.bg.*` | `canvas`, `surface`, `elevated`, `overlay`, `hover`, `active`, `disabled` |
| `color.border.*` | `default`, `muted`, `strong`, `focus`, `disabled` |
| `color.intent.*` | `success`, `success-bg`, `success-border`, `warning-*`, `danger-*`, `info-*` |
| `color.primary.*` | `default`, `hover`, `active`, `subtle`, `foreground` |
| `color.secondary.*` | `default`, `hover`, `active`, `foreground` |
| `color.muted.*` | `default`, `foreground` |
| `color.accent.*` | `default`, `foreground` |
| `color.destructive.*` | `default`, `foreground` |
| `color.icon.*` | `default`, `muted`, `primary`, `on-primary` |
| `space.*` | `xs` (4px), `sm` (8px), `md` (16px), `lg` (24px), `xl` (32px), `2xl` (48px), `3xl` (64px) |
| `radius.*` | `sm`, `md`, `lg`, `xl`, `full` |
| `font.*` | `body`, `heading`, `mono` |
| `shadow.*` | `sm`, `md`, `lg`, `xl` |

## Differenza primitivi / semantici

| | Primitivi | Semantici |
|---|---|---|
| **Significato** | "questo è il valore" | "questo è il ruolo" |
| **Override per tema** | No — fissi | Sì — ogni tema può ridefinirli |
| **Naming** | Scala numerica (`gray.500`) | Ruolo (`text.primary`) |
| **Usati direttamente** | Solo per costruire i semantici | Usati da componenti e CSS |

**Regola**: i componenti non referenziano MAI i primitivi direttamente — sempre tramite i semantici.

## Come creare un nuovo tema

1. Crea `src/tokens/themes/<nome>.json`
2. Struttura uguale a `semantic.json` — includi SOLO i valori che vuoi sovrascrivere
3. Aggiungi `_comment` con nota sul mood del tema
4. Il sistema compila automaticamente CSS vars `--sd-*` per `[data-theme="<nome>"]`

### Esempio minimal (tema monochrome)
```json
{
  "_comment": "Tema monochrome: grigi puri, nessun colore brand.",
  "color": {
    "primary": {
      "default": "#111827",
      "hover": "#374151",
      "active": "#1F2937",
      "subtle": "#F9FAFB",
      "foreground": "#FFFFFF"
    }
  }
}
```

## CSS output

Tutti i token semantici vengono compilati in `dist/css/variables.css` come CSS custom properties:

```css
:root {
  --sd-color-text-primary: #111827;
  --sd-color-bg-canvas: #FAFBFC;
  --sd-color-primary-default: #2563EB;
  --sd-space-md: 16px;
  --sd-radius-md: 12px;
  /* ... */
}

[data-theme="dark"] {
  --sd-color-text-primary: #F9FAFB;
  --sd-color-bg-canvas: #0C0E12;
  /* ... override dark */
}
```
