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

Dalla 3.1.0 (EP-003 / US-005, GAP-010 chiuso; completato in 3.2.0, componenti React in 3.3.0, vedi sotto) SoliDS offre lo scaffold Material 3 come **primitive CSS**, non come componente React. Riferimento esterno: [[material-3-expressive-2026]] §1.[^src: src/css/utilities.css §Layout scaffold M3 (bars → rails → panes)]

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

## Completamento (3.2.0, EP-004 / US-007, GAP-012 chiuso)

### Drag handle

Modulo `@soli92/solids/scaffold`, senza dipendenze, con tipi `.d.ts`: `attachPaneResize(handle, {pane, storageKey, mode})`.[^src: src/scaffold/pane-resize.ts §attachPaneResize]

- Aggancio a **360/412px** entro 24px; minimo 240, massimo 640; sotto meta' del minimo il pannello si chiude.
- Doppio clic, Enter o Spazio chiudono e riaprono il pannello; frecce (Shift ×5), Home, End; in RTL le frecce si invertono.
- `role="separator"` con `aria-controls`, `aria-valuenow`, `aria-expanded`.
- Modalita' `persistent` (localStorage) o `temporary`.
- Classi `.sd-pane-handle` e `.sd-pane-resizable`. Per React resta il componente `Resizable`.

### Levitate

- `.sd-pane-floating`: per un pannello modale usare `<dialog>` con `showModal()` (focus gestito dal browser); scrim opzionale.
- `.sd-pane-docked`: agganciato a un bordo.
- `.sd-pane-adaptive`: docked sotto 600px, floating 600–1199px, co-planar da 1200px.[^src: src/css/utilities.css §Levitate: floating and docked panes]

### Reflow

`.sd-panes-reflow-below-{medium,expanded,large}` e `.sd-panes-reflow-portrait`: i pannelli si impilano in verticale.[^src: src/css/utilities.css §Reflow: when there is not enough width, panes stack vertically]

### Verifica

`test:scaffold` (logica pura), `tokens-sanity`, Chromium end-to-end (US-007): frecce 368 / Shift 328 / End 640 / Home 240; trascinamento 405 → 412 al rilascio; Enter chiude (`aria-expanded=false`); adaptive fixed in basso a 400px, centrato a 700/900px, static a 1300px; reflow column a 400/700px, row a 900/1300px.[^src: management/kanban/EP-004-residui-m3/US-007-scaffold-completo/US-007.md §AC2-AC4]

## Componenti React (3.3.0, EP-005 / US-008, GAP-013 chiuso)

Nel registry: `Scaffold`, `ScaffoldBar`, `ScaffoldRail`, `ScaffoldPanes`, `Pane`, `PaneHandle` (`scaffold.tsx` in solids-ui). `pane-resize` e' spedito con solids-utils come `lib/pane-resize`.[^src: src/components/ui/scaffold.tsx §export] Verifica: `tsc --noEmit` pulito; storia «SoliDS / UI / Scaffold» in Chromium (visibilita' a 400/900/1700px, `aria-controls` corretto, frecce +8px, Enter chiude, nessun errore).[^src: management/kanban/EP-005-gap013-e-difetti-plancia/US-008-language-height-e-scaffold-react/US-008.md §AC3]

## Difetto corretto in 3.3.0 (reflow)

In colonna (`.sd-panes-reflow-*`) il pannello ridimensionabile aveva `flex-basis: 360px`, quindi altezza fissa 360px. Il difetto c'era gia' in 3.2.0 ed e' stato trovato in Chromium a 400px (segnalato dalla plancia); ora in colonna i pannelli ridimensionabili perdono la base fissa (GAP-014).[^src: management/kanban/EP-005-gap013-e-difetti-plancia/US-009-difetti-dalla-plancia/US-009.md §AC4]

## Non coperto

Nulla di noto: i residui GAP-012/013 sono chiusi.

## Pagine correlate

- [[material-3-expressive-2026]] — layout, breakpoint e pannelli M3
- [[foundations/spacing]] — token `--sd-measurement-*` e breakpoint
