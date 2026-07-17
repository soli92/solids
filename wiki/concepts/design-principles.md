---
id: design-principles
type: concept
title: "SoliDS — Design Principles"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/raw/analisi-repository-2026-07-17.txt §1.5 Documenti root-level di docs/"
  - "docs/raw/analisi-repository-2026-07-17.txt §Parte 2 — Concetti e conoscenza estratta"
  - "docs/principles.mdx §Token-first"
  - "docs/principles.mdx §Semantic over visual"
  - "docs/principles.mdx §Framework agnostic"
  - "docs/principles.mdx §Single Source of Truth"
  - "docs/principles.mdx §Progressive adoption"
  - "docs/principles.mdx §Accessibilita' e motion"
---

# SoliDS — Design Principles

I sei principi fondanti del design system, estratti da `docs/principles.mdx`.[^src: docs/raw/analisi-repository-2026-07-17.txt §1.5 Documenti root-level di docs/]

## 1. Token-first

Ogni decisione di design vive nei token, non nei componenti o stili locali. I token sono la fonte autoritativa per colori, tipografia, spacing e tutti i valori visivi.[^src: docs/raw/analisi-repository-2026-07-17.txt §Parte 2 — Concetti e conoscenza estratta]

Implicazione operativa: mai scrivere valori hardcoded in un componente React o in un file CSS. Se un valore non ha un token, il token va creato prima.

## 2. Semantic over visual

I consumer usano significati (`color.text.primary`), non valori (`#111827`). I token semantici descrivono il ruolo, non il valore — questo rende il sistema resiliente ai cambi di tema e alle variazioni cromatiche.

Implicazione operativa: un componente usa `--sd-color-text-primary`, mai `--sd-color-gray-900`. Il secondo potrebbe essere lo stesso valore in tema light, ma rompe nel momento in cui il tema cambia.

## 3. Framework agnostic

SoliDS non impone React o altri framework. La base e' CSS-first: le CSS variables `--sd-*` funzionano in qualsiasi contesto (React, Vue, Svelte, HTML puro).

Implicazione operativa: ogni feature del DS deve funzionare senza import React. I componenti React sono uno strato opzionale sopra la base CSS.

## 4. Single Source of Truth (SSOT)

I token `--sd-*` sono l'unica fonte per colori, spacing, tipografia e temi. Nessun valore hardcoded nei componenti o negli stili; nessuna duplicazione tra file di token.

Implicazione operativa: `src/tokens/` e' l'unico posto dove i valori vengono definiti. Il build pipeline genera tutto il resto (CSS variables, JSON esportati).

## 5. Progressive adoption

Adozione incrementale senza riscrittura. Un consumer puo' iniziare con solo le CSS variables e aggiungere i componenti React gradualmente, senza dover adottare tutto il DS in una volta.

Implicazione operativa: ogni parte del DS deve poter essere importata indipendentemente. Non ci sono dipendenze circolari tra livelli.

## 6. Accessibilita' by default

L'accessibilita' e' progettata, non aggiunta a posteriori. Il DS include:[^src: docs/raw/analisi-repository-2026-07-17.txt §1.2 docs/foundations/ — Storybook MDX]

- Utility `sd-min-touch-target` — area interattiva minima 44px (WCAG 2.2 SC 2.5.5)
- Utility `sd-link` — underline semantico per i link
- Motion: `standard` / `emphasized` (allineato a Material Design 3 + Apple HIG)
- Ratio di contrasto WCAG 2.2 AA verificati nei token semantici (vedi [wiki/design/a11y-token-audit.md](../design/a11y-token-audit.md))

## Applicazione pratica

| Principio | Regola operativa | Anti-pattern |
|-----------|-----------------|--------------|
| Token-first | Definire token prima di usare valori | `color: #1d4ed8` in un componente |
| Semantic over visual | `--sd-color-text-primary` | `--sd-color-gray-900` |
| Framework agnostic | Il CSS funziona senza React | Logica tema solo in JS |
| SSOT | Solo `src/tokens/` come origine | Valore ripetuto in due file |
| Progressive adoption | Import granulari disponibili | Require del package intero per un solo token |
| A11y by default | Ogni componente supera WCAG AA | A11y come post-launch task |

## Aggiornamento 2026-07-17 — Ingest diretto da docs/principles.mdx

Questa sezione integra il testo autoritativo da `docs/principles.mdx` (pagina Storybook), ora ingested direttamente.[^src: docs/principles.mdx §Token-first]

**Token-first**: "Ogni decisione di design deve vivere nei design tokens, non nei componenti o negli stili locali."[^src: docs/principles.mdx §Token-first]

**Semantic over visual**: "I consumer usano significati, non valori visivi. `color.text.primary` non `#111827`."[^src: docs/principles.mdx §Semantic over visual]

**Framework agnostic**: "SoliDS non impone React, Angular o altri framework."[^src: docs/principles.mdx §Framework agnostic]

**Single Source of Truth**: "I token rappresentano l'unica fonte di verita' per colori, spacing, tipografia e temi (light, dark, fantasy, cyberpunk, 90s-party, steampunk, piu' temi personaggio Ichigo / Vegeta / Zoro / Captain America / Sasuke / Inuyasha): stessi nomi `--sd-*`, valori diversi per `data-theme`. I default light/dark privilegiano superfici tonali e shape coerenti con Material Design 3, senza vincolare i temi nominati (fantasy, cyberpunk, ecc.)."[^src: docs/principles.mdx §Single Source of Truth]

**Progressive adoption**: "E' possibile adottare SoliDS gradualmente, senza riscrivere tutto."[^src: docs/principles.mdx §Progressive adoption]

**Accessibilita' e motion**: "Linee guida con fonti ufficiali (WCAG 2.2, Material Design 3, Apple HIG) e mapping su token/utility: in Storybook apri dalla sidebar Foundations → Accessibility and Motion (sorgente `docs/foundations/accessibility-and-motion.mdx`)."[^src: docs/principles.mdx §Accessibilita' e motion]

## Fonte primaria

Questi principi sono documentati in `docs/principles.mdx` (pagina Storybook). Questa pagina wiki integra sia il testo derivato dall'analisi (ingest 2026-07-17) sia il testo autoritativo diretto dal MDX (aggiornamento 2026-07-17).

## Pagine correlate

- [[token-architecture]] — architettura token (Principio 1+4)
- [[design-system-overview]] — scopo e consumer del DS
- [[docs-structure]] — struttura docs/ incluso principles.mdx
