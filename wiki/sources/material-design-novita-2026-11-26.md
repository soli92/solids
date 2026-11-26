---
id: source-material-design-novita-2026-11-26
type: source
title: "Sorgente — Material Design: novita' e direttive al 26/11/2026"
status: draft
created: 2026-11-26
updated: 2026-11-26
sources:
  - "raw/2026-11-26-material-design-novita-2026.md"
---

# Sorgente — Material Design: novita' e direttive al 26/11/2026

Report di ricerca (`type: research-report`, data 2026-11-26) sulle novita' di Material Design, ottenuto renderizzando le pagine di `m3.material.io` con Chromium headless (il sito e' client-side). File raw: `raw/2026-11-26-material-design-novita-2026.md`.[^src: raw/2026-11-26-material-design-novita-2026.md §Fonti e metodo]

## Cosa dice, in breve

- **Non esiste un «Material 4»**: la generazione corrente resta Material 3, con l'estensione **M3 Expressive** (maggio 2025).[^src: raw/2026-11-26-material-design-novita-2026.md §Sintesi]
- Uscite 2026: layout Expressive e spaziatura a 8dp (19/05, Google I/O), Compose-first (19/05), prototipazione parametrica (16/11), Compose Material 3 1.5.0 stabile (18/11).[^src: raw/2026-11-26-material-design-novita-2026.md §Sintesi]
- Per un design system web conta soprattutto: layout/breakpoint (§1), spaziatura (§2), densita' (§2.4), typography (§4), motion a molle, shape e raggi (§8).
- Il report **non e' una specifica per soli-ds**: la sezione 9 e' dichiarata «osservazione, non verificata a fondo» e propone solo un confronto mirato prima di qualunque modifica.[^src: raw/2026-11-26-material-design-novita-2026.md §9. Impatto su soli-ds (osservazione, non verificata a fondo)]

## Cosa e' stato ingerito

Tutto in [[material-3-expressive-2026]]. Fuori scope per un design system web e quindi **non riportati**: watch e XR (§5), dettagli per piattaforma Android/Compose (§6), metodo di prototipazione parametrica (§7), componenti Compose-only (time picker, scroll field, §3), salvo menzione come contesto.

## Limiti dichiarati dalla sorgente

- Le pagine *Specs* dei singoli componenti, le sottopagine Watches/XR e `grids-spacing/grids` (colonne per breakpoint) non sono state lette.[^src: raw/2026-11-26-material-design-novita-2026.md §Fonti e metodo]
- La spaziatura a token (`spaceXXX`) e' disponibile **solo su Jetpack Compose**; su Web e Flutter le varianti Expressive risultano in gran parte «Unavailable».[^src: raw/2026-11-26-material-design-novita-2026.md §6. Piattaforme: Compose-first]
- Fonti secondarie (9to5Google) solo come contesto; scartate bytevikas.com e la voce sulle Apple HIG.

## Pagine correlate

- [[material-3-expressive-2026]] — dati di riferimento per il design system web
- [[foundations/spacing]], [[foundations/radius]], [[foundations/accessibility-and-motion]], [[foundations/tokens]], [[foundations/typography]]
- `wiki/gaps.md` — GAP-006..GAP-009 (scarti soli-ds vs M3 attuale; aggiornamento 2026-11-26: GAP-008/009 chiusi, GAP-006/007 parziali dopo il refactor additivo EP-002)
