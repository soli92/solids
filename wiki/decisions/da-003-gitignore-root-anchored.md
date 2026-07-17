---
id: da-003-gitignore-root-anchored
type: decision
title: "DA-003 — Pattern .gitignore root-anchored per /solids/"
status: accepted
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/raw/bonifica-repo-2026-07-17.txt §DA-003 — Pattern .gitignore root-anchored"
context: bonifica-2026-07-17
---

# DA-003 — Pattern `.gitignore` root-anchored per `/solids/`

## Contesto

Durante la bonifica è stato eliminato un clone accidentale `solids/` nella root del
repository.[^src: docs/raw/bonifica-repo-2026-07-17.txt §DA-003 — Pattern .gitignore root-anchored]

Era necessario aggiungere un pattern `.gitignore` per prevenire che future clonazioni
accidentali nella stessa posizione finissero tracciate. Il repository contiene però
anche `registry/solids/` — directory legittima con le icone sincronizzate.

## Decisione

Usare il pattern root-anchored `/solids/` (con slash iniziale) nel `.gitignore`.

## Motivazione

I pattern `.gitignore` si comportano diversamente in base alla presenza della slash iniziale:

| Pattern | Effetto |
|---------|---------|
| `solids/` | Ignora qualsiasi directory chiamata `solids/` nell'intero albero — incluso `registry/solids/` |
| `/solids/` | Ignora solo la directory `solids/` nella root del repository |

Il pattern senza slash avrebbe ignorato `registry/solids/`, causando la scomparsa
delle icone sincronizzate (`glyphs.tsx`, `glyphs-themed.tsx`, `index.ts`, ecc.) dal
tracking git — un effetto collaterale inaccettabile.

Il pattern root-anchored protegge dalla clonazione accidentale in root senza impatti
su `registry/solids/`.

## Conseguenze

- `.gitignore`: aggiunto pattern `/solids/` (riga root-anchored)
- `registry/solids/` continua ad essere tracciato normalmente

## Incident di riferimento

[[bonifica-2026-07-17]] — Incidente 3 (struttura git corrotta, clone innestato `solids/`)
