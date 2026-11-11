# Passata 7 — Motion (advisory) — solids

Data: 2026-11-11 · Branch: `chore/upgrade-v2.45` · Skill: `kowalski-motion-review` · Nessun verdict, nessun task_package.

## Pre-condizione

| Controllo | Esito |
|---|---|
| `ui_craft.enabled` | true (`factory.config.yaml:209`) |
| `ui_craft.motion_review` | true (`factory.config.yaml:211`) |
| Diff tocca motion (grep protocollo: `transition`, `animation`, `@keyframes`, `motion.`, `animate=`, `useSpring`, `ease-`, `transform-origin`, `prefers-reduced-motion`) | SI. 61 file nel diff, 6611 righe aggiunte; 89 righe con corrispondenza (grep esteso a `animate-`, `duration-`, `keyframes`) |
| Esito | ESEGUITA |

Nota di metodo: l'hash dell'albero vuoto passato nell'incarico (`4b825dc6...0f4904`) non esiste (refuso). Quello reale e `4b825dc642cb6eb9a060e54bf8d69288fbee4904` (`git hash-object -t tree /dev/null`); usato quello. Il grep di attivazione e stato fatto su `HEAD`, equivalente al diff contro l'albero vuoto.

Stack: Tailwind 3.4.19 + `tailwindcss-animate` ^1.0.7 + Radix. Nessuna libreria JS di motion (`motion.`, `useSpring`, `animate=`: zero corrispondenze): gli standard 6 (spring) e 7 (scorciatoie `x`/`y`) di Motion non si applicano.

## Controllato, nessun finding

- **Origine dei popper**: `origin-[--radix-*-content-transform-origin]` presente su popover (`popover.tsx:22`), dropdown-menu (`:50`, `:69`), context-menu (`:47`, `:63`), menubar (`:95`, `:118`), hover-card (`:19`), select (`:78`), tooltip (`:21`). Verificato nei sorgenti di `@radix-ui/react-popper`: Radix espone solo `--radix-popper-transform-origin` e non applica mai `transform-origin` da se, quindi la classe e necessaria ed e presente. Unica eccezione: O1 (navigation-menu).
- **Modali centrati** esenti: `dialog.tsx:41`, `alert-dialog.tsx:39` (zoom-in-95 da centro, `duration-200`).
- **`scale(0)`**: zero occorrenze; tutte le entrate usano `zoom-in-95`/`zoom-out-95` + `fade-*-0`.
- **Hover**: solo `transition-colors`/`transition-opacity`; nessun `hover:scale/translate`, nessuna `active:scale`. Nessun movimento su hover, quindi lo standard 8 (protezione `@media (hover: hover)`) non e violato.
- **Durate** dei popper: `animate-in`/`animate-out` a 150ms di default (vedi R2), nell'intervallo 125-250ms.
- Spinner/skeleton/logo-loader (`animate-spin`, `animate-pulse`): indicatori di stato, `linear` corretto per moto costante.

## Finding per impatto

Impatto = peso sulla sensazione/prestazioni, non gravita (advisory). Alto 3 · Medio 8 · Basso 12 · Totale 23.

### 1. Rotture della sensazione

| ID | Imp. | Prima (file:riga, estratto verbatim) | Dopo | Perche | Standard / valore |
|---|---|---|---|---|---|
| R1 | Alto | `src/css/base.css:63` `transition: outline-offset var(--sd-duration-fast, 150ms)` | Eliminare la `transition` da `:focus-visible` (outline fisso a 2px) | Il focus-visible compare a ogni Tab: azione da tastiera, ripetuta centinaia di volte, ritarda il feedback; `outline-offset` non e `transform`/`opacity` | 2 (frequenza), 7. «Le azioni avviate da tastiera non si animano mai»; 100+/giorno: nessuna animazione |
| R2 | Alto | `src/components/ui/popover.tsx:22` `data-[state=open]:animate-in` (stesso schema in tooltip, dropdown-menu, context-menu, menubar, hover-card, select, dialog, alert-dialog, sheet, navigation-menu, toast) | Impostare una volta, nel preset/`utilities.css`, `animation-timing-function: cubic-bezier(0.23, 1, 0.32, 1)` su `.animate-in, .animate-out` (o `ease-[cubic-bezier(0.23,1,0.32,1)]` per componente) | `tailwindcss-animate` imposta solo `animationName` e `animationDuration` (`node_modules/tailwindcss-animate/index.js:6-16`), non il timing: ogni entrata/uscita usa il `ease` built-in, debole. Inferenza dal sorgente, non da computed style: da verificare a vista | 3. Entrata/uscita `ease-out`; «easing built-in deboli»; `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` |
| R3 | Medio | `src/components/ui/sidebar.tsx:235` `transition-[width] duration-200 ease-linear` (anche `:245`, `:311`, `:450`) | `ease-[cubic-bezier(0.77,0,0.175,1)]` | `linear` e riservato al moto costante; qui e movimento sullo schermo | 3. Movimento sullo schermo: `ease-in-out`; `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)`; `linear` solo per marquee/progress |
| R4 | Basso | `src/components/ui/sheet.tsx:34` `transition ease-in-out data-[state=closed]:duration-300 data-[state=open]:duration-500` | `ease-[cubic-bezier(0.32,0.72,0,1)]`, apertura 300ms (valutare) | Drawer: la curva dedicata esiste. L'apertura (risposta del sistema a un click) e piu lenta della chiusura: asimmetria inversa. 500ms e comunque nel range ammesso per i drawer, quindi e un giudizio, non una violazione | 3, 9, 4. `--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1)`; modali/drawer 200-500ms |
| R5 | Medio | `src/components/ui/sidebar.tsx:31` `const SIDEBAR_KEYBOARD_SHORTCUT = "b"` (il toggle e animato da `sidebar.tsx:235` `duration-200`) | Se il toggle da scorciatoia e frequente: `transition-none` quando innescato da tastiera (flag nel context); altrimenti lasciare e annotare la scelta | La scorciatoia (Cmd/Ctrl+B) innesca l'animazione di layout a 200ms. Quanto sia frequente non si legge dal codice: giudizio | 2. «Le azioni avviate da tastiera non si animano mai»; «Occasionale: animazione standard» (conflitto fra le due righe, vedi ambiguita) |
| R6 | Basso | `src/components/ui/tooltip.tsx:21` `animate-in fade-in-0 zoom-in-95` | Aggiungere `data-[state=instant-open]:animate-none` | Nessuna distinzione fra primo tooltip e successivi nella stessa toolbar | 2. «Dal secondo tooltip di una toolbar in poi, niente ritardo e niente animazione» |
| R7 | Medio | `src/components/ui/dropdown-menu.tsx:87` `transition-colors focus:bg-accent` (anche `:103`, `:127`) | `transition-none` sulle voci di menu | `focus:` si sposta con le frecce: navigazione di liste da tastiera, evidenziazione che sfuma a 150ms dietro il cursore | 2. «Decine di volte/giorno (hover, navigazione di liste): toglierla o ridurla molto» |

### 2. Semplificazioni mancate

| ID | Imp. | Prima | Dopo | Perche | Standard / valore |
|---|---|---|---|---|---|
| S1 | Basso | `src/components/ui/navigation-menu.tsx:72` `data-[motion=from-end]:slide-in-from-right-52` (e `from-start`, `to-end`, `to-start`) | `slide-in-from-right-4` o sola dissolvenza | Il contenuto scorre di 13rem a ogni passaggio fra trigger: hover ripetuto, spostamento ampio | 2, 1. «Decine di volte/giorno: toglierla o ridurla molto» |

### 3. Prestazioni

| ID | Imp. | Prima | Dopo | Perche | Standard / valore |
|---|---|---|---|---|---|
| P1 | Medio | `tailwind.config.cjs:15` `to: { height: "var(--radix-accordion-content-height)" },` (keyframe + `:23` `"accordion-down": "accordion-down 0.2s ease-out",`; uso in `accordion.tsx:47` `data-[state=open]:animate-accordion-down`) | Vedi nota: nessuna correzione GPU diretta; almeno `cubic-bezier(0.23, 1, 0.32, 1)` al posto di `ease-out` | Anima `height` (layout+paint) con un keyframe (non interrompibile, riparte da zero) e `ease-out` built-in. La regola «solo transform/opacity» e applicabile solo in parte: la sezione deve spingere il contenuto sottostante | 7, 6, 3. «`padding`/`margin`/`height`/`width`/`top`/`left` fanno scattare tutti e tre i passi»; `ease-out` forte `cubic-bezier(0.23, 1, 0.32, 1)` |
| P2 | Medio | `src/components/ui/sidebar.tsx:245` `transition-[left,right,width] duration-200 ease-linear md:flex` (anche `:235` `transition-[width]`, `:450` `transition-[margin,opacity]`, `:523` `transition-[width,height,padding]`) | Pannello fisso: `translate-x` al posto di `left/right`; lo spaziatore `width` resta | Proprieta di layout animate. Il pannello `fixed` si puo portare su `transform`; lo spaziatore che sposta il contenuto no | 7. Solo `transform` e `opacity` |
| P3 | Basso | `src/components/ui/accordion.tsx:29` `transition-all hover:underline` | `transition-colors` (o rimuovere) | `all` su un trigger che cambia solo underline/colore | 7. «`transition: all` ... sempre un finding» |
| P4 | Basso | `src/components/ui/tabs.tsx:30` `ring-offset-background transition-all focus-visible:outline-none` | `transition-[color,background-color,box-shadow]` | Cambiano solo colore, sfondo, ombra/ring fra stati | 7 |
| P5 | Basso | `src/components/ui/input-otp.tsx:42` `shadow-sm transition-all first:rounded-l-md` | `transition-[border-color,box-shadow]` (verificare quali proprieta cambiano con la cella attiva) | `all` | 7 |
| P6 | Basso | `src/components/ui/progress.tsx:21` `className="h-full w-full flex-1 bg-primary transition-all"` | `transition-transform` | Cambia solo `transform: translateX(...)` (riga 22) | 7 |
| P7 | Basso | `src/components/ui/toast.tsx:26` `shadow-lg transition-all data-[swipe=cancel]:translate-x-0` | `transition-[transform,opacity]` | Lo swipe muove solo `translate-x`; il resto e keyframe | 7 |
| P8 | Basso | `src/components/ui/sidebar.tsx:311` `-translate-x-1/2 transition-all ease-linear after:absolute` | `transition-colors ease-[cubic-bezier(0.77,0,0.175,1)]` | Il rail cambia solo il colore di `::after` all'hover | 7, 3 |

### 4. Interrompibilita e tempi

| ID | Imp. | Prima | Dopo | Perche | Standard / valore |
|---|---|---|---|---|---|
| I1 | Medio | `src/components/ui/toast.tsx:26` `data-[state=open]:animate-in ... data-[state=open]:slide-in-from-top-full` | Transizione/`@starting-style` (vedi limite) | Toast aggiunti in rapida successione con keyframe: ripartono da zero. Limite: Radix Presence rileva l'uscita via `animationend`, una transizione richiede di gestire lo smontaggio a parte | 6. «Per cio che si innesca spesso (toast aggiunti, toggle) servono transizioni» |
| I2 | Basso | `src/components/ui/navigation-menu.tsx:58` `transition duration-300 group-data-[state=open]:rotate-180` | `duration-200` | Rotazione di un chevron da 12px: icona piccola, 300ms eccessivo | 4. Tooltip/piccoli popover 125-200ms; «la UI resta sotto i 300ms» |
| I3 | Basso | `src/css/utilities.css:240` `transition-duration: var(--sd-duration-emphasized, 350ms);` | Dichiarare l'uso (marketing/esplicativo) o ridurre a 300ms | 350ms oltre la soglia UI senza ragione dichiarata nel codice. Nessun consumatore in `src/`: potrebbe essere voluto | 4. «La UI resta sotto i 300ms»; «Marketing o esplicativo: puo essere piu lungo» |

### 5. Origine, fisicita e coesione

| ID | Imp. | Prima | Dopo | Perche | Standard / valore |
|---|---|---|---|---|---|
| O1 | Medio | `src/components/ui/navigation-menu.tsx:89` `origin-top-center relative mt-1.5` | `origin-top` | `origin-top-center` non esiste nel tema Tailwind 3 (chiavi: center, top, top-right, ...): la classe e inerte e il viewport scala da centro mentre sta sotto i trigger. Dedotto dal tema di default (Node non disponibile per verificarlo; `preset.cjs` e `tailwind.config.cjs` non definiscono `transformOrigin`) | 5. «Popover, dropdown e tooltip scalano dal proprio trigger (`transform-origin`)» |
| O2 | Medio | `src/tokens/base.json:176` `"ease-out":  "cubic-bezier(0, 0, 0.2, 1)",` | Sostituire con `cubic-bezier(0.23, 1, 0.32, 1)` e farla usare ai componenti | Due sistemi di motion non collegati: i componenti `ui/` usano i default Tailwind/`ease`, i token `--sd-*` solo `base.css`/`utilities.css`; e il token `ease-out` e la curva Material (debole). `standard` (`0.2, 0, 0, 1`) e gia forte | 10 + «Coesione e token». `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` |
| O3 | Basso | `src/components/ui/menubar.tsx:118` `data-[state=open]:animate-in data-[state=closed]:fade-out-0` (manca `data-[state=closed]:animate-out`, presente a `:95`) | Aggiungere `data-[state=closed]:animate-out` | Le classi `fade-out-0`/`zoom-out-95` del sub-content in chiusura non hanno effetto senza `animate-out`: entrata animata, uscita secca, incoerente col resto | 10 (coesione) |

### 6. Accessibilita

| ID | Imp. | Prima | Dopo | Perche | Standard / valore |
|---|---|---|---|---|---|
| A1 | Alto | `src/css/base.css:78` `transition: none !important;` (e `:79` `animation: none !important;`) | `animation-duration`/`transition-duration` ridotti e mantenere opacita/colore; escludere `animate-spin`/`animate-pulse` o sostituirli con un indicatore statico | Azzera tutto: «piu gentile, non zero». Spegne anche spinner e skeleton (indicatori di stato) e, con `*`, non copre `::before/::after`. Dipende inoltre dal fatto che il consumatore importi `base.css` | 8. «Reduced motion significa meno animazioni e piu gentili, non zero»; si tengono opacita e colore |

## Osservazione fuori dai dieci standard

- `src/components/ui/input-otp.tsx:51` `<div className="h-4 w-px animate-caret-blink bg-foreground duration-1000" />`: `animate-caret-blink` non e definita in `tailwind.config.cjs` (solo `accordion-*`) ne in `src/tailwind/preset.cjs`; la stessa riga e nel registry (`registry/solids/input-otp/input-otp.tsx:51`). Il caret non lampeggia (classe inerte). Non conteggiata sopra.

## Da verificare a vista

| Che cosa | Passo concreto |
|---|---|
| R2: easing effettivo di `animate-in`/`animate-out` | DevTools, pannello Animations, rallentare al 10%: leggere `animation-timing-function` calcolata su popover/dropdown |
| R1: focus ring | Tab fra campi con Animations al 10%: l'`outline-offset` sfuma? Decidere se la sfumatura serve |
| R5: scorciatoia sidebar | Premere Cmd/Ctrl+B ripetutamente: l'animazione di 200ms ostacola? |
| R4: drawer | Sheet da destra e dal basso, al 10%: stacco apertura 500ms vs chiusura 300ms; curva `ease-in-out` vs drawer. Su dispositivo reale per il gesto |
| R6: tooltip in sequenza | Passare fra 3 pulsanti di una toolbar: dal secondo, istantaneo? (verificare anche il `delayDuration` del `TooltipProvider` nell'app) |
| P1/P2: accordion e sidebar | Pannello Performance con CPU 4x: frame persi su accordion con contenuto lungo e sul collasso della sidebar |
| I1: toast in sequenza | Aggiungere 3 toast in rapida successione e chiuderli: scatti o ripartenze |
| A1: reduced-motion | Rendering, Emulate `prefers-reduced-motion: reduce`: spinner, skeleton, popover e sheet |
| O1: viewport navigation-menu | Al 10%: da dove scala il viewport sotto un trigger lontano dal centro |
| P3-P8: `transition-all` | Verificare nel pannello Animations quali proprieta transitano davvero prima di restringere (specie `input-otp` e `tabs`) |
| S1: navigation-menu | Passare fra i trigger piu volte: il movimento di 13rem stanca? |
| Hover su touch | Emulazione touch: nessun falso hover rilevante (solo colori, atteso ok) |
| Caret OTP | Con la classe inerte il caret e statico: confermare se e voluto |

## Riepilogo (nessuna decisione)

Rotture della sensazione 7 · Semplificazioni 1 · Prestazioni 8 · Interrompibilita e tempi 3 · Origine/coesione 3 · Accessibilita 1. Totale 23 (Alto 3, Medio 8, Basso 12). Nessun Block/Approve; non altera alcun verdict.

## Applicazione (2026-11-11)

Applicato dopo la migrazione a Tailwind v4 (HEAD 2ddd9b7). Righe rilocalizzate sul codice attuale. Evidenza: build/test verdi, oracolo visivo (124 scatti, animazioni spente) e `getComputedStyle` con Playwright su storybook-static (con/senza `prefers-reduced-motion`).

| ID | Esito | Dove (nuovo) | Evidenza |
|---|---|---|---|
| R1 | fatto | `src/css/base.css:60-64` (transition tolta da `:focus-visible`) | CSS compilato: `:focus-visible{outline:2px solid ...;outline-offset:2px}` senza transition |
| R2 | fatto | `src/css/tailwind.css:165-185` (`--tw-ease` in `@layer base`) | `animate-in` v4 e `animation: enter dur var(--tw-ease,ease)...`: la curva si imposta via `--tw-ease`, non con `animation-timing-function` (la shorthand di un utility la azzererebbe). Computed: dialog `cubic-bezier(0.23, 1, 0.32, 1)`, tooltip e popover idem; un `ease-*` sul componente resta piu forte (layer utilities) |
| R2 (uscita piu rapida) | fatto | `tailwind.css:181-184` | `[data-state=closed][class*=animate-out]` imposta `--tw-animation-duration: var(--tw-duration,125ms)`. Popover in uscita: 0.125s contro 0.15s di ingresso; dialog/sheet seguono la durata dichiarata dal componente |
| R3 | fatto | `sidebar.tsx:235,245,311,450` | `ease-linear` sostituito da `ease-[cubic-bezier(0.77,0,0.175,1)]`; grep `ease-linear` in ui/: zero |
| R4 | fatto | `sheet.tsx:34` | `ease-[cubic-bezier(0.32,0.72,0,1)]`, apertura 300ms, chiusura 200ms. Computed: open 0.3s / close 0.2s con quella curva |
| R5 | non fatto (decisione 9) | `sidebar.tsx:31` | Cmd/Ctrl+B lasciata com'e: quanto sia frequente il toggle da tastiera non si legge dal codice; lo standard e in conflitto con se stesso («tastiera: mai» vs «occasionale: animazione standard»). Resta in «da verificare a vista». Mitigazione gia attiva: con reduce lo spaziatore scatta senza transizione |
| R6 | fatto | `tooltip.tsx:21` | `data-[state=instant-open]:animate-none`; presente nel CSS compilato. Non misurato a runtime lo stato `instant-open` (richiede due tooltip ravvicinati) |
| R7 | fatto | `dropdown-menu.tsx:87,103,127` | `transition-none` sulle voci |
| S1 | fatto | `navigation-menu.tsx:72` | `slide-*-52` (13rem) ridotti a `-4` (1rem), fade invariato |
| P1 | fatto (parziale per scelta) | `tailwind.css:112-113`; `accordion.tsx:47` | altezza mantenuta; curva `cubic-bezier(0.23,1,0.32,1)`, 0.2s. Computed accordion: `accordion-down 0.2s cubic-bezier(0.23, 1, 0.32, 1)`. Poiche l'ordine d'import del consumatore fa vincere la definizione di tw-animate-css, la curva e imposta anche via `--tw-ease` (`tailwind.css:174-176`) |
| P2 | fatto | `sidebar.tsx:245,247-248` | pannello fisso: `left/right` -> `translate-x-full` (offcanvas) e `transition-[translate,width]`; il `width` resta per la modalita icona; spaziatore `:235` resta su `width`. Oracolo: sidebar chiara identica a pixel, scura solo bordo |
| P3 | fatto | `accordion.tsx:29` | `transition-colors` |
| P4 | fatto | `tabs.tsx:30` | `transition-[color,background-color,box-shadow]` |
| P5 | fatto | `input-otp.tsx:42` | `transition-[border-color,box-shadow]` (con la cella attiva cambia il ring) |
| P6 | fatto | `progress.tsx:21` | `transition-transform` |
| P7 | fatto | `toast.tsx:26` | `transition-[transform,opacity]` |
| P8 | fatto (variante) | `sidebar.tsx:311` | non `transition-colors`: il rail cambia anche `translate` (`offcanvas:translate-x-0`), quindi `transition-[translate,background-color] duration-200` per non far scattare lo spostamento che prima animava |
| I1 | non fatto | `toast.tsx:26` | decisione 6: il toast resta a keyframe, Radix rileva l'uscita con `animationend` |
| I2 | fatto | `navigation-menu.tsx:58` | `duration-200` |
| I3 | fatto (dichiarato) | `src/css/utilities.css:238-239` | 350ms mantenuto con commento: solo motion esplicativo/marketing, nessun consumatore nei componenti |
| O1 | fatto | `navigation-menu.tsx:89` | `origin-top`. Nessuna differenza visiva negli scatti statici; l'origine incide solo durante lo zoom |
| O2 | non fatto | `src/tokens/base.json:176` | fuori perimetro (token sorgente); da portare alla sessione principale |
| O3 | fatto | `menubar.tsx:118` | aggiunto `data-[state=closed]:animate-out` |
| A1 | fatto | `base.css:72-114` | vedi misure sotto. Niente azzeramento globale: variabili `--tw-enter-*`/`--tw-exit-*` forzate (`!important`, valgono anche per tailwindcss-animate v3), durata 100ms, `transition-property` ristretta a colore/opacita/ombra, accordion/collapsible senza animazione (e altezza), `animate-spin` rallentato a 3s, `animate-pulse` (solo opacita) invariato |
| Caret OTP | fatto | `tailwind.css:114-126`; `input-otp.tsx:51` | `--animate-caret-blink` + keyframe `caret-blink` esplicitati; CSS compilato: `.animate-caret-blink{animation:1.25s ease-out infinite caret-blink}`. Nota: tw-animate-css la definisce gia, quindi il «caret inerte» era vero solo per i consumatori v3 / senza il plugin |
| Bordo di default | fatto (decisione 8) | `tailwind.css:158` | `border-color: var(--border, currentColor)`. Oracolo: unica differenza e nei temi scuri (e nel toast chiaro, bordo ora token) |

Fuori da questo elenco: il preset v3 (`src/tailwind/preset.cjs`) non e stato toccato: easing e caret sono in `tailwind.css` (solo v4, il preset e legacy senza nuove feature); focus e reduced-motion stanno in `base.css` e raggiungono anche i v3.

### Misure `getComputedStyle` (storybook-static, Chromium)

| Elemento | senza reduce | con reduce |
|---|---|---|
| dialog, apertura | enter 0.2s `cubic-bezier(0.23,1,0.32,1)`; y -48%, x -50%, scale .95, opacity 0 | enter 0.1s stessa curva; y 0, x 0, scale 1, opacity 0 (resta la dissolvenza) |
| dialog, chiusura | exit 0.2s stessa curva; scale .95 | exit 0.1s; scale 1, x 0 |
| sheet, apertura / chiusura | 0.3s / 0.2s, `cubic-bezier(0.32,0.72,0,1)`; x 100% | 0.1s / 0.1s; x 0 |
| tooltip, apertura | 0.15s `cubic-bezier(0.23,1,0.32,1)`; y 0.5rem, scale .95 | 0.1s; y 0, scale 1, opacity 0 |
| popover, chiusura | exit 0.125s `cubic-bezier(0.23,1,0.32,1)`, origine `128px 0px` (misura senza reduce) | non misurata |
| accordion, apertura | `accordion-down` 0.2s `cubic-bezier(0.23,1,0.32,1)` | `animation-name: none` |
| spinner | `spin` 1s linear | `spin` 3s linear |
| transition-property | (default dei componenti) | `color, background-color, border-color, text-decoration-color, fill, stroke, opacity, box-shadow` a 0.1s |

Nota: nei componenti con `duration-*` (dialog, sheet) il computed mostra `transition: all <durata>`: e il `transition-property` di default di v4 per la sola utility di durata, non una `transition-all` dichiarata, e non c'e nulla che transiti.

### Oracolo visivo

124 scatti (m1) contro a5: 107 identici, 17 diversi. 32 scatti con overlay aperto (m1o) contro a5o: 18 identici, 14 diversi. Tutte le differenze sono il bordo (`--border` al posto del grigio fisso): 16 dark piu `toast--statico__light` (bordo del toast); 800-3100 px per scatto, linee sottili. Nessun diverso nei temi chiari tranne il toast. Nessuna regressione di layout (sidebar chiaro e aperto identici).

### Da verificare a vista (non sono fix)

R5 (scorciatoia sidebar), I1 (toast in sequenza), R6 a runtime (`instant-open`), R4 (drawer su dispositivo), P1/P2 (frame persi con CPU 4x), O1 (origine viewport a 10%), S1 (stanchezza del movimento ridotto), hover su touch.
