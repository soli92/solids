---
id: token-naming-convention
type: design-rationale
title: "SoliDS — Token Naming Convention (EP-019 Standard)"
status: stable
created: 2026-06-15
updated: 2026-06-15
---

# SoliDS — Token Naming Convention

## ART-DIRECTOR STATEMENT (EP-019)

```
INTENT: Definire lo standard definitivo di naming per i token SoliDS, identificare
ambiguità che potrebbero confondere un LLM o un developer consumer.
PROBLEM: I token di un design system devono essere self-documenting. Un nome ambiguo
crea coupling implicito e rende difficile l'adozione da parte di agenti AI.
DESIGN RATIONALE: Il naming segue due assi ortogonali:
  - BASE: <categoria>.<scala> — primitivi numerici/ordinali, nessuna semantica
  - SEMANTIC: <role>.<variant> — ruolo UI, nessun valore assoluto
CONSTRAINTS: Compatibilità shadcn/ui, Tailwind CSS convention, CSS custom property naming.
```

## Standard definitivo

### Livello base (primitivi)

```
<categoria>.<scala>

color.<palette>.<step>   — color.gray.500 / color.blue.700
space.<step>             — space.4 / space.px / space.0.5
radius.<name>            — radius.sm / radius.full
font.<role>              — font.body / font.heading / font.mono
shadow.<step>            — shadow.sm / shadow.xl
duration.<name>          — duration.fast / duration.normal / duration.slow
easing.<name>            — easing.standard / easing.emphasized
layout.<name>            — layout.max-width
z.<name>                 — z.modal / z.tooltip
```

**Regola R.N1**: i primitivi usano scale numeriche Tailwind-style (50..950) per i colori.  
**Regola R.N2**: i primitivi NON contengono mai ruoli semantici nel nome.  
**Regola R.N3**: `font.body` è l'unica eccezione — `body` è un ruolo, non una scala. Accettabile perché il livello font non ha primitivi "senza ruolo" (non esistono font "primari").

### Livello semantico

```
<role>.<variant>

color.text.primary        — testo principale
color.text.secondary      — testo secondario (muted)
color.bg.canvas           — sfondo pagina
color.bg.surface          — sfondo card/contenitore
color.bg.elevated         — sfondo elemento elevato (dropdown, modal)
color.border.default      — bordo standard
color.border.focus        — bordo stato focus
color.intent.success      — colore stato successo
color.intent.success-bg   — sfondo stato successo
color.primary.default     — colore brand principale (button, link)
color.primary.foreground  — testo su primary (sempre bianco)
color.secondary.*         — colore secondario
color.muted.*             — elemento muted/disabilitato
color.accent.*            — colore accent (hover state in shadcn)
color.destructive.*       — rosso danger (elimina, errore critico)
color.icon.*              — icone (diverso da text)
```

## CRITIC PASS EP-019

**Domanda critica**: "Ci sono token con nomi ambigui per un LLM?"

### Finding #1: `color.accent` vs `color.secondary` — ambiguità parziale

`color.accent.default` (#E8EAEF) e `color.secondary.default` (#E8EAEF) hanno lo **stesso valore nel tema light**. Per un LLM che legge i JSON, sono indistinguibili nella pratica.

**Cause**: shadcn/ui usa `accent` per hover states in list items; `secondary` per button variant. La semantica è diversa ma il valore coincide.  
**Giudizio**: CONDITIONAL. Non è un bug — la separazione ha senso in shadcn/ui. Da documentare esplicitamente nei commenti del token file.

### Finding #2: `color.muted` — ruolo generico, rischio over-use

`muted` è usato sia per testo (`color.muted.foreground`) che per superfici (`color.muted.default`). Il nome è generico e un LLM potrebbe applicarlo in contesti sbagliati.

**Giudizio**: CONDITIONAL. Il pattern shadcn/ui obbliga questo naming. Aggiungere note esplicite nell'inventario.

### Finding #3: `space` semantico vs base — collision di nomi

Nel livello semantico, `space.md` = 16px. Nel livello base, `space.4` = 16px. **Due nomi per lo stesso valore**. Un consumer non sa quale usare.

**Regola derivata R.N4**: i componenti React usano i **semantici** (`space.md`); i token base (`space.4`) sono usati solo come backup o per mapping Tailwind. Da documentare.

### Finding #4: naming non trova ambiguità strutturali — status PASS

La convenzione `<role>.<variant>` è chiara, consistente nei 12+ temi, e corrisponde 1:1 alle CSS vars `--sd-<role>-<variant>`. Un LLM può inferire `--sd-color-text-primary` da `color.text.primary` senza ambiguità.

## Inconsistenze trovate

| Token | Issue | Severità |
|-------|-------|---------|
| `color.accent` vs `color.secondary` | stesso valore tema light | LOW |
| `color.muted` | nome troppo generico | LOW |
| `space.md` vs `space.4` | duplicazione semantici/base | MEDIUM |
| `font.body` | usa role nel livello base | VERY LOW (accettabile) |

## Verdict globale

**Standard**: stabile e coerente. Nessuna inconsistenza critica.  
**Azione raccomandata**: aggiungere `_comment` espliciti nei JSON per i 3 finding LOW/MEDIUM.
