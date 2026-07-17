---
id: da-001-icon-source-of-truth
type: decision
title: "DA-001 — Conservare glyphs-themed.tsx come source of truth delle icone tematiche"
status: accepted
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/raw/bonifica-repo-2026-07-17.txt §DA-001 — Conservare glyphs-themed.tsx come source of truth"
context: bonifica-2026-07-17
---

# DA-001 — Conservare `glyphs-themed.tsx` come source of truth

## Contesto

Due file contenevano definizioni degli stessi 9 simboli SVG:[^src: docs/raw/bonifica-repo-2026-07-17.txt §DA-001 — Conservare glyphs-themed.tsx come source of truth]

- `src/icons/glyphs.tsx` — versioni semplificate (segnaposto)
- `src/icons/glyphs-themed.tsx` — versioni elaborate con SVG path definitivi (non esportato)

Era necessario scegliere quale file mantenere come source of truth e quale eliminare.

## Decisione

Conservare le versioni di `glyphs-themed.tsx` come design definitivo.
Rimuovere le 9 versioni semplificate da `glyphs.tsx` (righe 247–342).

## Motivazione

Le versioni in `glyphs-themed.tsx` contengono SVG path elaborati corrispondenti al
design definitivo approvato. Le versioni in `glyphs.tsx` erano placeholder creati
prima che il design fosse completato.

Se entrambi i file fossero stati esportati, TypeScript avrebbe generato errori di
binding duplicato. Mantenere le versioni elaborate garantisce che il design system
esponga le icone corrette ai consumer.

## Conseguenze

- `src/icons/index.ts`: aggiunto `export * from "./glyphs-themed"`
- `src/icons/glyphs.tsx`: rimosso blocco righe 247–342 (9 icone)
- **Icone interessate**: `IconFantasyScroll`, `IconFantasySword`, `IconFantasyGem`,
  `IconCyberpunkChip`, `IconCyberpunkEye`, `IconCyberpunkSignal`,
  `IconPartyBolt`, `IconPartyDiamond`, `IconPartyStar`

## Incident di riferimento

[[bonifica-2026-07-17]] — Incidente 1 (icone duplicate)
