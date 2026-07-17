---
id: theme-spec-brutalist
type: design-rationale
title: "SoliDS — Theme Spec: brutalist"
status: draft
created: 2026-06-15
updated: 2026-06-15
---

# SoliDS — Theme Spec: "brutalist"

## ART-DIRECTOR STATEMENT (EP-019)

```
INTENT: Progettare un tema "brutalist" per SoliDS che esprima
coerenza con l'estetica brutalist web (tipografia forte, contrasto
massimo, colori ridotti, nessun ornamento).
PROBLEM: I temi esistenti (cyberpunk, fantasy, character) puntano
su palette colorate/espressive. Manca un tema che valorizzi la
struttura pura.
DESIGN RATIONALE: Il brutalism in UI design non è "brutto" — è
anti-ornamentale. Sfondo bianco o nero puro, tipografia bold as primary
visual element, colore usato solo per segnalazione (non decorazione).
Il tema brutalist è l'opposto del "card UI" — si vede la struttura.
CONSTRAINTS: compatibilità token semantici SoliDS, WCAG AA obbligatorio,
max 2 colori oltre a bianco/nero/grigio, font.body/heading già esistenti.
```

## DESIGN SPEC (DSL)

```
Theme name: brutalist
Data-theme attr: data-theme="brutalist"

Palette primitivi usati:
  WHITE:  color.white (#FFFFFF)
  BLACK:  color.black (#000000)
  GRAY-9: color.gray.900 (#111827)
  GRAY-5: color.gray.500 (#6B7280)
  GRAY-2: color.gray.200 (#E5E7EB)
  ACCENT: color.blue.700 (#1D4ED8)  — unico colore non-neutro (signal only)
  RED:    color.red.700 (#B91C1C)   — destructive/danger

Typography:
  Tutti i titoli: font-weight 900 (black)
  Body: Inter normal (invariato dal default)
  Mono: invariato

Radius:
  TUTTE le radius ridotte a 0 (nessun border-radius) — brutalismo = angoli duri
  radius.sm: 0 / radius.md: 0 / radius.lg: 0 / radius.xl: 0 / radius.full: 9999px (invariato)

Shadow:
  NESSUNA shadow — brutalismo = no elevation (flat)
  Sostituito da border 2px solid black come separazione

Surface:
  Canvas: bianco (#FFFFFF)
  Surface: bianco (#FFFFFF) — no layering
  Elevated: GRIGIO-200 (#E5E7EB) — unico differenziatore

Border:
  Bordi forti ovunque (default: 2px solid #111827)

Primary:
  Accento blu puro (#1D4ED8) — solo per CTA, focus ring, link
  Mai usato come sfondo decorativo
```

## Token overrides (JSON target)

```json
{
  "_comment": "Tema brutalist: tipografia forte, contrasto massimo, zero radius, nessuna shadow. Anti-ornamentale.",
  "color": {
    "text": {
      "primary":   "#000000",
      "secondary":  "#111827",
      "tertiary":   "#4B5563",
      "disabled":   "#9CA3AF",
      "inverse":    "#FFFFFF",
      "link":       "#1D4ED8",
      "link-hover": "#1E40AF"
    },
    "bg": {
      "canvas":   "#FFFFFF",
      "surface":  "#FFFFFF",
      "elevated": "#E5E7EB",
      "overlay":  "rgba(0, 0, 0, 0.6)",
      "hover":    "#F3F4F6",
      "active":   "#E5E7EB",
      "disabled": "#F9FAFB"
    },
    "border": {
      "default":  "#000000",
      "muted":    "#374151",
      "strong":   "#000000",
      "focus":    "#1D4ED8",
      "disabled": "#D1D5DB"
    },
    "intent": {
      "success":          "#15803D",
      "success-bg":       "#FFFFFF",
      "success-border":   "#15803D",
      "warning":          "#92400E",
      "warning-bg":       "#FFFFFF",
      "warning-border":   "#92400E",
      "danger":           "#B91C1C",
      "danger-bg":        "#FFFFFF",
      "danger-border":    "#B91C1C",
      "info":             "#1D4ED8",
      "info-bg":          "#FFFFFF",
      "info-border":      "#1D4ED8"
    },
    "primary": {
      "default":    "#000000",
      "hover":      "#111827",
      "active":     "#374151",
      "subtle":     "#F3F4F6",
      "foreground": "#FFFFFF"
    },
    "secondary": {
      "default":    "#E5E7EB",
      "hover":      "#D1D5DB",
      "active":     "#9CA3AF",
      "foreground": "#000000"
    },
    "destructive": {
      "default":    "#B91C1C",
      "foreground": "#FFFFFF"
    }
  },
  "radius": {
    "sm": "0px",
    "md": "0px",
    "lg": "0px",
    "xl": "0px"
  },
  "shadow": {
    "sm": "none",
    "md": "none",
    "lg": "none",
    "xl": "none"
  }
}
```

## CRITIC PASS EP-019

**Domanda critica**: "Il tema rispetta il vincolo brutalist E mantiene WCAG AA?"

### Finding #1: primary #000000 su bg.canvas #FFFFFF — contrasto 21:1 ✓

Massimo contrasto possibile. Brutalist puro. Pass WCAG AAA.

### Finding #2: border.muted #374151 è troppo chiaro per brutalismo puro

Se il bordo standard è `#000000`, `muted` dovrebbe essere `#6B7280` (ancora visibile ma
gerarchicamente sotto). `#374151` è "quasi nero" senza essere nero — ambiguità non brutalist.  
**Revisione**: cambiare `border.muted` a `#6B7280`.

### Finding #3: radius.full mantenuto a 9999px — incoerenza potenziale

I pill badge e avatar usano `radius.full`. In un tema brutalist, i pill potrebbero diventare
angoli duri. HOWEVER: le avatar hanno UX ragioni per rimanere circolari.  
**Giudizio**: CONDITIONAL. Lasciare `radius.full` invariato ma documentare che avatar/badge-pill
non sono "brutalist puri" — sono eccezioni accettabili.

### Finding #4: zero shadow può rompere l'accessibilità modal/dialog

I modal usano `shadow.xl` per segnalare l'elevazione. Con `shadow: none`, il dialog diventa
piatto e può confondersi con il contenuto sottostante.  
**Raccomandazione**: aggiungere un border `2px solid #000000` al dialog come compensazione.
Documentato come nota implementativa.

## Verdict

**Status**: DRAFT — spec pronta per implementazione  
**Finding bloccanti**: nessuno  
**Finding di attenzione**: 2 (border.muted + dialog shadow compensation)  
**Prossimo step**: implementare il JSON in `src/tokens/themes/brutalist.json` e aggiungere Storybook story.
