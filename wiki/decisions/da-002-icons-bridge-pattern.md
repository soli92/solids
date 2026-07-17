---
id: da-002-icons-bridge-pattern
type: decision
title: "DA-002 — Bridge pattern per @/lib/icons (compatibilità registry shadcn)"
status: accepted
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/raw/bonifica-repo-2026-07-17.txt §DA-002 — Bridge pattern per @/lib/icons"
context: bonifica-2026-07-17
---

# DA-002 — Bridge pattern per `@/lib/icons`

## Contesto

`src/components/ui/logo-loader.tsx` importava `@/icons`, path che funziona in locale
(dove `@/` → `src/`) ma non per i consumer del registry shadcn.[^src: docs/raw/bonifica-repo-2026-07-17.txt §DA-002 — Bridge pattern per @/lib/icons]

I consumer del registry ricevono i file via `registry:lib` installati in `lib/`.
Il path `@/icons` non esiste nel loro progetto; il corretto è `@/lib/icons`.

Opzioni valutate:
1. Refactoring di tutti i path interni al repo (`@/icons` → `@/lib/icons`)
2. Bridge: creare `src/lib/icons/index.ts` che re-esporta da `@/icons`

## Decisione

Introdurre un bridge `src/lib/icons/index.ts` che re-esporta tutto da `@/icons`.
Modificare solo `logo-loader.tsx` per usare `@/lib/icons`.

## Motivazione

Il refactoring globale richiederebbe modifiche diffuse nel codebase e nei test, con
rischio di regressioni. Il bridge separa due preoccupazioni distinte:

- **Path del consumer del registry** (`@/lib/icons`) — stabile, non deve cambiare
- **Struttura interna del repo** (`src/icons/`) — flessibile, può evolvere

Il bridge è un indirection layer a costo zero: non introduce logica, solo un re-export.
In locale dev, `@/lib/icons` risolve via `src/lib/icons/index.ts` che re-esporta da
`@/icons` (= `src/icons/`). Per i consumer del registry, `@/lib/icons` risolve in
`lib/icons/` (file copiato dal registry build).

## Conseguenze

- Nuovo file: `src/lib/icons/index.ts` (1 riga: `export * from "@/icons"`)
- `src/components/ui/logo-loader.tsx`: import `@/icons` → `@/lib/icons`
- Il registry build (`npx shadcn build`) include `src/lib/icons/index.ts`

## Incident di riferimento

[[bonifica-2026-07-17]] — Incidente 2 (import path rotto)
