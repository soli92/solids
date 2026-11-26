---
id: material-3-expressive-2026
type: concept
title: "Material 3 Expressive (stato al 26/11/2026)"
status: draft
created: 2026-11-26
updated: 2026-11-26
sources:
  - "raw/2026-11-26-material-design-novita-2026.md §1.3"
  - "raw/2026-11-26-material-design-novita-2026.md §1.4"
  - "raw/2026-11-26-material-design-novita-2026.md §2"
  - "raw/2026-11-26-material-design-novita-2026.md §4"
  - "raw/2026-11-26-material-design-novita-2026.md §8"
  - "raw/2026-11-26-material-design-novita-2026.md §9"
---

# Material 3 Expressive (stato al 26/11/2026)

Pagina di **riferimento esterno**: raccoglie cio' che Material Design prescrive oggi e che interessa un design system web. Le sezioni 1-7 sono riferimento esterno; lo **stato dei token soli-ds** e' nella sezione 8 (refactor additivo EP-002 implementato; GAP-008/009 chiusi, GAP-006/007 parziali in `wiki/gaps.md`). Sorgente: [[material-design-novita-2026-11-26]].

Premessa: **non esiste «Material 4»**; la generazione corrente e' Material 3 piu' l'estensione M3 Expressive (maggio 2025).[^src: raw/2026-11-26-material-design-novita-2026.md §Sintesi]

Avvertenza di disponibilita': la spaziatura a token e' solo su Jetpack Compose (Web: no); su Web le varianti Expressive risultano in gran parte «Unavailable», mentre il motion fisico e' «compatibile» sul web tramite conversione delle molle.[^src: raw/2026-11-26-material-design-novita-2026.md §6. Piattaforme: Compose-first]

---

## 1. Layout: breakpoint e pannelli

Terminologia cambiata: *window size classes* → **breakpoints**, *responsive layout* → **adaptive design**.[^src: raw/2026-11-26-material-design-novita-2026.md §1.1 Nomenclatura cambiata]

### Breakpoint

| Breakpoint | Larghezza | Pannelli consigliati (altri ammessi) |
|---|---|---|
| Compact | < 600dp | 1 |
| Medium | 600–839dp | 1 (2) |
| Expanded | 840–1199dp | 2 (1) |
| Large | 1200–1599dp | 2 (1) |
| Extra-large | >= 1600dp | 2 (1, 3) |

[^src: raw/2026-11-26-material-design-novita-2026.md §1.3 Breakpoint]

- Si progetta per breakpoint, non per dispositivo. Righe di testo da **40 a 60 caratteri** a ogni breakpoint.[^src: raw/2026-11-26-material-design-novita-2026.md §1.3 Breakpoint]
- Passando da un breakpoint all'altro: cosa rivelare, dividere, ridimensionare, riposizionare, scambiare. Gli scambi devono essere tra componenti funzionalmente equivalenti.[^src: raw/2026-11-26-material-design-novita-2026.md §1.3 Breakpoint]
- Scambi tipici: navigazione = navigation bar (compact) → rail collassata (medium, expanded); selezione supplementare = bottom sheet (compact) → menu (medium, expanded).[^src: raw/2026-11-26-material-design-novita-2026.md §1.3 Breakpoint]
- Lo scaffold ha tre livelli: **bars** (app bar, navigation bar con 3-5 viste primarie), **rails** (perimetro dei pannelli), **panes** (contenuto, da 1 a 3 visibili).[^src: raw/2026-11-26-material-design-novita-2026.md §1.2 Scaffold: bars → rails → panes]

### Pannelli

- **Fixed** o **flexible** (almeno un pannello flessibile per layout), **permanent** o **temporary**.[^src: raw/2026-11-26-material-design-novita-2026.md §1.4 Pannelli]
- **Split-pane** (50 % ciascuno, ideale sui pieghevoli) e **fixed-and-flexible** (da expanded in su). **Tre pannelli** solo a extra-large; mai piu' di tre. Pannelli fissi consigliati a **412dp**.[^src: raw/2026-11-26-material-design-novita-2026.md §1.4 Pannelli]
- Drag handle: larghezze di snap **360dp** e **412dp**; persistente (default) o temporaneo.[^src: raw/2026-11-26-material-design-novita-2026.md §1.4 Pannelli]
- Strategie di adattamento: *show/hide*, *levitate* (floating/docked), *reflow*. Su schermi grandi i pannelli docked diventano preferibilmente co-planar.[^src: raw/2026-11-26-material-design-novita-2026.md §1.4 Pannelli]
- Accessibilita': l'ordine del focus segue la disposizione visiva; un pannello floating modale porta il focus sul primo elemento e lo restituisce al trigger alla chiusura.[^src: raw/2026-11-26-material-design-novita-2026.md §1.4 Pannelli]
- Layout canonici: feed, list-detail, supporting pane (pannello primario ~2/3).[^src: raw/2026-11-26-material-design-novita-2026.md §1.5 Layout canonici]

---

## 2. Spaziatura

### Principi e regole

- Scala **lineare a 8dp**: `space100 = 8dp`; i token sono moltiplicatori (`space225 = 18dp`).[^src: raw/2026-11-26-material-design-novita-2026.md §2.1 Principi]
- Tre categorie: **padding** (dentro un elemento), **gap** (tra elementi di un contenitore o griglia), **margin** (fuori). Posizioni: vertical, horizontal, top, bottom, **leading**, **trailing** (invertiti in RTL).[^src: raw/2026-11-26-material-design-novita-2026.md §2.1 Principi]
- **Padding e gap prima dei margin**: si definiscono sul contenitore padre, non come margin sui figli. Componenti complessi: gap nominati (es. *icon-label gap*).[^src: raw/2026-11-26-material-design-novita-2026.md §2.1 Principi]
- **Testo scalato al 200 %: la spaziatura resta la stessa.**[^src: raw/2026-11-26-material-design-novita-2026.md §2.1 Principi]
- Nuova convenzione dei nomi degli attributi: `padding` / `margin` / `gap` + posizione (es. «Medium button: leading padding»), al posto di `leading-space`, `trailing-space`, `top-space`, `bottom-space`, `between-space`.[^src: raw/2026-11-26-material-design-novita-2026.md §2.2 Token di sistema]

### Token `md.sys.measurement.spaceXXX`

| Token | dp | Token | dp |
|---|---|---|---|
| space0 | 0 | space250 | 20 |
| space25 | 2 | space300 | 24 |
| space50 | 4 | space400 | 32 |
| space75 | 6 | space450 | 36 |
| space100 | 8 | space500 | 40 |
| space125 | 10 | space600 | 48 |
| space150 | 12 | space700 | 56 |
| space175 | 14 | space800 | 64 |
| space200 | 16 | space900 | 72 |

[^src: raw/2026-11-26-material-design-novita-2026.md §2.2 Token di sistema]

Il collegamento di tutti i componenti ai token e' dichiarato ancora in corso.[^src: raw/2026-11-26-material-design-novita-2026.md §2.2 Token di sistema]

### Personalizzazione

Tre leve: rimappare un componente nel prodotto; aggiungere token di sistema e pattern condivisi (es. *surface content horizontal padding*); adattare a layout e densita' mappando token diversi per tipo di dispositivo.[^src: raw/2026-11-26-material-design-novita-2026.md §2.3 Personalizzazione]

---

## 3. Densita' e target

- Scala di densita' **0, −1, −2, −3**; ogni passo toglie circa **4dp** di altezza o di padding verticale.[^src: raw/2026-11-26-material-design-novita-2026.md §2.4 Uso espressivo e densità]
- La densita' e' **opt-in dell'utente**: non cambia da sola tra breakpoint o orientamento e non si applica a componenti di task focalizzati (menu) o di allerta (snackbar, dialog).[^src: raw/2026-11-26-material-design-novita-2026.md §2.4 Uso espressivo e densità]
- **Target minimo 48×48dp** (48×48 CSS px sul web), anche se l'icona e' piu' piccola; la dimensione del testo non cambia con la densita'.[^src: raw/2026-11-26-material-design-novita-2026.md §2.4 Uso espressivo e densità]

Nota di confronto: il default di soli-ds resta `--sd-layout-touch-target-min = 44px` (vedi [[foundations/accessibility-and-motion]]); il target M3 da 48px e' disponibile come opt-in (`--sd-layout-touch-target-material`, `.sd-touch-target-material`). Il passaggio del default 44→48 e' una decisione breaking del maintainer (GAP-008, nota).

---

## 4. Motion a molle

Il **motion fisico sostituisce il sistema durata + easing**.[^src: raw/2026-11-26-material-design-novita-2026.md §8. Base M3 Expressive (maggio 2025), ancora in vigore]

| Aspetto | Regola |
|---|---|
| Schemi | *expressive* (default, con overshoot) e *standard* (utilitaristico); si sceglie a livello di prodotto |
| Parametri della molla | stiffness, damping, velocita' iniziale |
| Token | `md.sys.motion.spring.{fast\|default\|slow}.{spatial\|effects}` |
| `spatial` | posizione, dimensione, rotazione, raggi; con overshoot |
| `effects` | colore e opacita'; senza overshoot |
| Personalizzazione | 3 livelli: schema di default, `MotionScheme` custom, override per elemento |

[^src: raw/2026-11-26-material-design-novita-2026.md §8. Base M3 Expressive (maggio 2025), ancora in vigore]

Sul web il motion fisico e' «compatibile» tramite conversione delle molle (la sorgente non descrive la conversione).[^src: raw/2026-11-26-material-design-novita-2026.md §6. Piattaforme: Compose-first]

---

## 5. Shape

- Libreria di **35 forme** con morphing integrato.[^src: raw/2026-11-26-material-design-novita-2026.md §8. Base M3 Expressive (maggio 2025), ancora in vigore]
- Scala dei raggi: large **20dp**, extra-large **32dp**, extra-extra-large **48dp**; il «pienamente arrotondato» usa **`full`** (non piu' il 50 %).[^src: raw/2026-11-26-material-design-novita-2026.md §8. Base M3 Expressive (maggio 2025), ancora in vigore]
- Principi: tensione tra tondo e squadrato, forma non semantica, forme astratte con parsimonia, 2.5D.[^src: raw/2026-11-26-material-design-novita-2026.md §8. Base M3 Expressive (maggio 2025), ancora in vigore]

---

## 6. Typography

- Scala di **30 stili: 15 baseline + 15 emphasized**; Google Sans Flex e' open source, Roboto Flex non fa ancora parte della scala.[^src: raw/2026-11-26-material-design-novita-2026.md §8. Base M3 Expressive (maggio 2025), ancora in vigore]
- Da agosto 2026 l'interlinea si adatta alla **categoria di altezza della scrittura** della lingua (small, medium, large, extra large). In Compose 1.5.0 un font di brand si imposta su tutta la scala in un colpo solo.[^src: raw/2026-11-26-material-design-novita-2026.md §4. Typography: altezza della scrittura (agosto 2026)]

---

## 7. Componenti aggiornati (rilevanti per il web)

Search unico (contained/divided), vertical menu (standard/vibrant), expressive list (altezze 56, 72, 88dp). Time picker con variante scroll e scroll field sono Compose-only.[^src: raw/2026-11-26-material-design-novita-2026.md §3. Componenti aggiornati nel 2025-2026]

---

## 8. Stato in soli-ds (refactor additivo EP-002 / US-002, 2026-11-26)

La sezione 9 della sorgente registrava quattro scarti, **non verificati a fondo**.[^src: raw/2026-11-26-material-design-novita-2026.md §9. Impatto su soli-ds (osservazione, non verificata a fondo)] Il refactor **additivo** (TSK-008..013) e' implementato e verificato: nessun token esistente cambia nome o valore (dist: 0 righe rimosse, 192 token aggiunti).[^src: management/kanban/EP-002-allineamento-m3-expressive/US-002-token-m3-additivi/US-002.md §Esito (2026-11-26)]

| Area | Token aggiunti | Invariato | Gap |
|---|---|---|---|
| Spaziatura | `--sd-measurement-space0..space900` (18 token, valori M3)[^src: src/tokens/base.json §measurement] | scala `--sd-space-*` | GAP-008 chiuso |
| Breakpoint | `--sd-breakpoint-*` compact 0 / medium 600 / expanded 840 / large 1200 / extra-large 1600px[^src: src/tokens/base.json §breakpoint]; varianti Tailwind v4 `medium:` `expanded:` `large:` `extra-large:`[^src: src/css/tailwind.css §M3 breakpoints] | `sm..2xl`; preset Tailwind v3 non toccato (legacy) | GAP-009 chiuso |
| Corner | `--sd-corner-*` a 10 gradi, valori M3 esatti su light/dark (0/4/8/12/16/20/28/32/48/full)[^src: src/tokens/semantic.json §corner] | `--sd-radius-*` | GAP-007 parziale |
| Motion | 12 curve ufficiali molla→cubic-bezier in `base.motion.expressive/standard`[^src: src/tokens/base.json §motion]; alias `--sd-motion-spring-<fast\|default\|slow>-<spatial\|effects>-<easing\|duration>` su schema expressive[^src: src/tokens/semantic.json §motion.spring]; `[data-motion="standard"]` cambia schema (generato da `scripts/build.mjs`); utility `.sd-motion`, `.sd-motion-fast`, `.sd-motion-slow`[^src: src/css/utilities.css §Motion physics (M3 Expressive)]; `ease-sd-*` in Tailwind v4[^src: src/css/tailwind.css §ease-sd] | `--sd-duration-*`, `--sd-easing-*`, `.sd-transition*` | GAP-006 parziale |
| Target | `--sd-layout-touch-target-material` 48px + `.sd-touch-target-material` (opt-in)[^src: src/css/utilities.css §Touch target M3 (48×48dp)] | default `--sd-layout-touch-target-min` 44px | GAP-008 (nota) |

Dettagli:

- **Corner per tema**: per i temi nominati `small`..`large-increased` = radius sm..xl del tema, `extra-small` = sm/2, gradi ampi = xl x1.4 / x1.6 / x2.4 (`src/tokens/themes/*.json`, §corner).
- **Motion e reduced motion**: la regola globale di `base.css` resta valida (verificato in Chromium: restano solo colore e opacita' a 100ms). Le curve spatial hanno overshoot (y > 1), le effects no.[^src: management/kanban/EP-002-allineamento-m3-expressive/US-002-token-m3-additivi/US-002.md §Esito (2026-11-26)]
- **Breaking ancora aperto (decisione del maintainer, major 3.0.0)**: `.sd-transition*` sulle molle; `--sd-radius-2xl`/`3xl` da 20/24 a 28/32px; `--sd-layout-touch-target-min` da 44 a 48px.[^src: management/kanban/EP-002-allineamento-m3-expressive/US-002-token-m3-additivi/US-002.md §Decisioni aperte (maintainer)]

L'allineamento «a Material Design 3» dichiarato dai **default** delle pagine foundations resta riferito a **M3 pre-Expressive**; i token M3 Expressive sono disponibili in aggiunta.

## Pagine correlate

- [[material-design-novita-2026-11-26]] — pagina sorgente
- [[foundations/spacing]] · [[foundations/radius]] · [[foundations/typography]] · [[foundations/tokens]] · [[foundations/accessibility-and-motion]]
- [[design-principles]] — Principio 6 (motion allineato a MD3) e SSOT
- [[token-architecture]]
