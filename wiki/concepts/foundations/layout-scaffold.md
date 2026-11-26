---
id: foundations-layout-scaffold
type: concept
title: "Foundations — Layout scaffold (M3)"
status: draft
created: 2026-11-26
updated: 2026-11-26
sources:
  - "src/css/utilities.css §Layout scaffold M3 (bars → rails → panes)"
  - "src/tokens/base.json §breakpoint"
  - "management/kanban/EP-003-completamento-m3/US-005-scaffold-css/US-005.md"
---

# Foundations — Layout scaffold (M3)

Dalla 3.1.0 (EP-003 / US-005, GAP-010 chiuso) SoliDS offre lo scaffold Material 3 come **primitive CSS**, non come componente React. Riferimento esterno: [[material-3-expressive-2026]] §1.[^src: src/css/utilities.css §Layout scaffold M3 (bars → rails → panes)]

## Struttura

`.sd-scaffold` e' una grid con aree `bar-top`, `rail-start | panes | rail-end`, `bar-bottom` (`min-height: 100dvh`).

| Classe | Ruolo |
|--------|-------|
| `.sd-scaffold` | Contenitore grid; `--sd-scaffold-margin` 16px (`space200`), 24px da medium; `--sd-scaffold-spacer` 24px (`space300`) |
| `.sd-scaffold-bar-top` / `-bar-bottom` | Bar; padding con `env(safe-area-inset-*)` (safety region) |
| `.sd-scaffold-rail-start` / `-rail-end` | Rail laterali (navigation rail a inizio, controlli di supporto a fine) |
| `.sd-scaffold-panes` | Area pannelli (flex, gap = spacer, padding orizzontale = margin) |
| `.sd-pane` | Pannello **flessibile** (`flex: 1 1 0`); i pannelli split si dividono 50/50 |
| `.sd-pane-fixed` / `.sd-pane-fixed-412` | Pannello fisso 360px (default) o 412px, via `--sd-pane-fixed-width` |
| `.sd-pane-scroll` | Scroll verticale interno con `overscroll-behavior: contain` |
| `.sd-hide-below-<bp>` / `.sd-hide-from-<bp>` | Visibilita' per breakpoint (`medium` 600, `expanded` 840, `large` 1200, `extra-large` 1600px) per rivelare pannelli o scambiare componenti (navigation bar su compact → rail da medium) |

[^src: src/css/utilities.css §Layout scaffold M3 (bars → rails → panes)]

Regole M3 rispettate: da 1 a 3 pannelli, almeno uno flessibile; pannelli fissi 360/412px; margine 16px su compact e 24px da medium; spacer 24px. Le misure usano i token `--sd-measurement-space*` e i breakpoint `--sd-breakpoint-*` (vedi [[foundations/spacing]]).[^src: src/tokens/base.json §breakpoint]

Verifica: in Chromium a 400, 900 e 1700px (US-005).[^src: management/kanban/EP-003-completamento-m3/US-005-scaffold-css/US-005.md]

## Non coperto

Drag handle, pannelli floating/docked (*levitate*), reflow: vedi GAP-012.

## Pagine correlate

- [[material-3-expressive-2026]] — layout, breakpoint e pannelli M3
- [[foundations/spacing]] — token `--sd-measurement-*` e breakpoint
