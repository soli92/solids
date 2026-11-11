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
