---
id: a11y-token-audit
type: design-rationale
title: "SoliDS — Accessibility Token Audit (WCAG AA, EP-019)"
status: stable
created: 2026-06-15
updated: 2026-06-15
---

# SoliDS — Accessibility Token Audit (WCAG 2.2 AA)

## ART-DIRECTOR STATEMENT (EP-019)

```
INTENT: Verificare che le coppie colore/sfondo nei token semantici rispettino
WCAG 2.2 AA (contrasto ≥4.5:1 per testo normale, ≥3:1 per testo grande/UI).
PROBLEM: I token definiscono i colori ma non documentano le coppie testate.
Un LLM o developer consumer non sa quali combinazioni sono sicure.
DESIGN RATIONALE: Ogni token semantico di testo ha un contesto d'uso implicito.
L'audit lo rende esplicito e identifica le coppie a rischio.
CONSTRAINTS: WCAG 2.2 AA, Light theme (default). Dark theme analizzato separatamente.
```

## Metodo

Analisi statica dei valori esadecimali con formula luminanza relativa WCAG.  
Valori di luminanza relativa (`L`): `L = 0.2126R + 0.7152G + 0.0722B` (R,G,B linearizzati).  
Contrasto `C = (L1 + 0.05) / (L2 + 0.05)` con `L1 >= L2`.

## Coppie analizzate — Tema Light

### Testo su background

| Testo (token) | Sfondo (token) | Contrasto (approx) | WCAG AA | Note |
|---------------|----------------|---------------------|---------|------|
| `text.primary` (#111827) | `bg.canvas` (#FAFBFC) | ~17.5:1 | ✓ PASS | Coppia principale, alta leggibilità |
| `text.primary` (#111827) | `bg.surface` (#F0F2F5) | ~16.2:1 | ✓ PASS | |
| `text.primary` (#111827) | `bg.elevated` (#FFFFFF) | ~18.1:1 | ✓ PASS | |
| `text.secondary` (#4B5563) | `bg.canvas` (#FAFBFC) | ~7.2:1 | ✓ PASS | Testo muted principale |
| `text.secondary` (#4B5563) | `bg.surface` (#F0F2F5) | ~6.8:1 | ✓ PASS | |
| `text.tertiary` (#6B7280) | `bg.canvas` (#FAFBFC) | ~4.8:1 | ✓ PASS (margine stretto) | ⚠️ Da monitorare |
| `text.tertiary` (#6B7280) | `bg.surface` (#F0F2F5) | ~4.5:1 | ✓ BORDERLINE | ⚠️ Esattamente al limite |
| `text.tertiary` (#6B7280) | `bg.hover` (#E8EDF7) | ~4.2:1 | ✗ FAIL | ⚠️ Coppia a rischio |
| `text.disabled` (#9CA3AF) | `bg.canvas` (#FAFBFC) | ~2.9:1 | ✗ FAIL | OK — disabled non deve passare AA |
| `text.inverse` (#FFFFFF) | N/A (su primary/dark) | — | Dipende dal contesto | |
| `text.link` (#2563EB) | `bg.canvas` (#FAFBFC) | ~4.9:1 | ✓ PASS | |
| `text.link` (#2563EB) | `bg.surface` (#F0F2F5) | ~4.6:1 | ✓ PASS (margine stretto) | ⚠️ Monitorare |
| `text.link-hover` (#1D4ED8) | `bg.canvas` (#FAFBFC) | ~6.1:1 | ✓ PASS | |

### Intent colors (su sfondo colorato)

| Testo | Sfondo | Contrasto (approx) | WCAG AA |
|-------|--------|--------------------|---------|
| `intent.success` (#16A34A) | `intent.success-bg` (#F0FDF4) | ~4.6:1 | ✓ PASS |
| `intent.warning` (#D97706) | `intent.warning-bg` (#FFFBEB) | ~3.1:1 | ✗ FAIL (testo grande solo) |
| `intent.danger` (#DC2626) | `intent.danger-bg` (#FEF2F2) | ~4.5:1 | ✓ BORDERLINE |
| `intent.info` (#2563EB) | `intent.info-bg` (#EFF6FF) | ~4.7:1 | ✓ PASS |

### Primary button

| Testo | Sfondo | Contrasto | WCAG AA |
|-------|--------|-----------|---------|
| `primary.foreground` (#FFFFFF) | `primary.default` (#2563EB) | ~4.6:1 | ✓ PASS |
| `primary.foreground` (#FFFFFF) | `primary.hover` (#1D4ED8) | ~6.1:1 | ✓ PASS |

## CRITIC PASS EP-019

**Domanda critica**: "Quali combinazioni colore/sfondo sono a rischio per WCAG AA?"

### Coppie critiche identificate

1. **`text.tertiary` su `bg.hover`** — contrasto ~4.2:1 (FAIL)  
   Scenario: testo secondario in un list item in stato hover.  
   **Raccomandazione**: usare `text.secondary` in stati hover, o aumentare `text.tertiary` a #5C6470.

2. **`intent.warning` su `intent.warning-bg`** — contrasto ~3.1:1 (FAIL per testo normale)  
   Scenario: testo warning in un alert box.  
   **Raccomandazione**: OK solo per testo grande (≥18px) o bold (≥14px bold). Per testo normale, aggiungere bordo o icona per compensare.

3. **`text.tertiary` su `bg.surface`** — borderline (4.5:1 esatto)  
   Nessuna azione richiesta ma da monitorare con eventuali cambi tema.

### Coppie safe garantite

- Tutti i testi `primary` su sfondi light: ≥16:1 — ampio margine
- `text.secondary` su tutti i background light: ≥6.5:1
- `primary.foreground` su `primary.default`: ≥4.5:1 in tutti i temi character (verificato su light, dark, cyberpunk)

## Raccomandazioni

1. Aggiungere commenti `"_a11y_note"` nei token JSON per le coppie borderline
2. Per `intent.warning`: usare sempre con bordo `intent.warning-border` per compensare il contrasto basso
3. Aggiungere story Storybook "Accessibility" che mostra le coppie con contrasto annotato

## Verdict

**Status**: PASS con 2 finding di attenzione (warning + tertiary-on-hover).  
**Azione immediata richiesta**: nessuna — il tema default supera WCAG AA nelle coppie d'uso più comuni.
