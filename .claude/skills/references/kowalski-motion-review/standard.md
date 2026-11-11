# Standard del motion — valori citabili

Ambito: valori precisi per `kowalski-motion-review.md` e per la Passata 7 del
`code-review-protocol`. Un finding cita da qui il valore, non lo approssima. Origine: STANDARDS.md
di `review-animations` di Emil Kowalski (MIT, `vendor/emilkowalski-skills/`), adattato.
Sono euristiche d'autore, non misure.

## Frequenza

| Frequenza | Decisione |
|---|---|
| 100+ volte/giorno (scorciatoie da tastiera, toggle command palette) | Nessuna animazione |
| Decine di volte/giorno (hover, navigazione di liste) | Toglierla o ridurla molto |
| Occasionale (modali, drawer, toast) | Animazione standard |
| Rara o di prima volta (onboarding, celebrazioni) | Può avere piacere |

Le azioni avviate da tastiera non si animano mai: si ripetono centinaia di volte al giorno.
Scopi validi: coerenza spaziale, indicazione di stato, spiegazione, feedback, evitare un cambio brusco.

## Easing

- Entrata o uscita: `ease-out`
- Movimento o trasformazione sullo schermo: `ease-in-out`
- Hover o cambio colore: `ease`
- Moto costante (marquee, progress): `linear`
- Predefinito: `ease-out`

`ease-in` sulla UI è sempre un finding. Gli easing built-in sono deboli: curve forti.

```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);        /* ease-out forte per la UI */
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);    /* ease-in-out forte per il movimento sullo schermo */
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);     /* curva da drawer in stile iOS */
```

Le curve si cercano su easing.dev o easings.co, non si inventano da zero.

## Durate

| Elemento | Durata |
|---|---|
| Feedback di pressione di un pulsante | 100–160ms |
| Tooltip, piccoli popover | 125–200ms |
| Dropdown, select | 150–250ms |
| Modali, drawer | 200–500ms |
| Marketing o esplicativo | Può essere più lungo |

Regola: la UI resta sotto i 300ms. Un dropdown da 180ms sembra più reattivo di uno da 400ms. Dal
secondo tooltip di una toolbar in poi, niente ritardo e niente animazione.

## Fisicità

- Mai `scale(0)`: si parte da `scale(0.9–0.97)` con `opacity: 0`.
- Popover, dropdown, tooltip scalano dal trigger: `transform-origin` ancorato al trigger (con Base UI,
  `var(--transform-origin)`). **I modali sono esenti**: restano al centro, non si segnalano.
- Pressione: `transform: scale(0.97)` su `:active` con `transition: transform 160ms ease-out`.
  Delicato: 0.95–0.98.

## Spring

Simulano la fisica: nessuna durata fissa, si fermano sui parametri. Per drag con inerzia, elementi
«vivi», gesti interrompibili, motion decorativo legato al mouse.

```js
// stile Apple, più facile da ragionare (consigliata)
{ type: "spring", duration: 0.5, bounce: 0.2 }

// fisica tradizionale, più controllo
{ type: "spring", mass: 1, stiffness: 100, damping: 10 }
```

Rimbalzo contenuto, 0.1–0.3; nella UI corrente evitarlo, riservandolo a drag-to-dismiss e momenti
giocosi. Una spring mantiene la velocità se interrotta, un keyframe riparte da zero. Per il motion
legato al mouse, interpolare con `useSpring` invece di agganciare il valore alla posizione, e solo
se il motion è decorativo.

## Interrompibilità

Le transizioni CSS si interrompono e si riagganciano; i keyframe ripartono da zero. Per ciò che si
innesca spesso (toast aggiunti, toggle) servono transizioni.

```css
.toast { transition: transform 400ms ease; }   /* interrompibile */
/* da evitare per la UI dinamica: @keyframes slideIn { from { transform: translateY(100%); } ... } */
```

Entrata senza JS con `@starting-style`:

```css
.toast {
  opacity: 1; transform: translateY(0);
  transition: opacity 400ms ease, transform 400ms ease;
  @starting-style { opacity: 0; transform: translateY(100%); }
}
```

Ripiego: `useEffect(() => setMounted(true), [])` più attributo `data-mounted`.

## Tempi asimmetrici

Lento dove l'utente decide, rapido dove risponde il sistema.

```css
.overlay { transition: clip-path 200ms ease-out; }            /* rilascio: rapido */
.button:active .overlay { transition: clip-path 2s linear; }  /* pressione: lenta, deliberata */
```

## Prestazioni

- Solo `transform` e `opacity`: saltano layout e paint. `padding`/`margin`/`height`/`width`/`top`/`left` fanno scattare tutti e tre i passi.
- `transition: all` anima proprietà non volute fuori dalla GPU: sempre un finding.
- Non guidare la trasformazione di un figlio con una variabile CSS sul genitore (ricalcola lo stile di tutti i figli):
  ```js
  element.style.setProperty('--swipe-amount', `${d}px`); // male
  element.style.transform = `translateY(${d}px)`;        // bene
  ```
- Le scorciatoie `x`/`y`/`scale` di Motion sono accelerate in hardware da `motion` 14.2. Prima, girano sul thread principale e perdono frame sotto carico: aggiornare, oppure la stringa `transform` completa. Le animazioni `layout`/`layoutId` girano sul thread principale in ogni versione.
  ```jsx
  <motion.div animate={{ x: 100 }} />                          // motion 14.2+: accelerata
  <motion.div animate={{ transform: "translateX(100px)" }} />  // accelerata in ogni versione
  ```
- Sotto carico il CSS batte il JS basato su rAF: CSS per il predeterminato, JS per il dinamico.
- WAAPI dà controllo da JS con le prestazioni del CSS:
  ```js
  element.animate([{ clipPath: 'inset(0 0 100% 0)' }, { clipPath: 'inset(0 0 0 0)' }],
    { duration: 1000, fill: 'forwards', easing: 'cubic-bezier(0.77, 0, 0.175, 1)' });
  ```
- `filter: blur()` in transizione sotto i 20px: un blur forte costa, specie su Safari.

## Transform e clip-path

- Le percentuali di `translate` sono relative all'elemento: `translateY(100%)` sposta della sua altezza, meglio dei pixel fissi.
- `scale()` scala anche i figli (testo, icone): è voluto per il feedback di pressione.
- 3D: `rotateX/Y` con `transform-style: preserve-3d` per profondità, orbita, flip senza JS.
- `clip-path: inset(t r b l)`: ogni valore «mangia» dal proprio lato. Usi: rivelazione allo scroll (`inset(0 0 100% 0)` → `inset(0 0 0 0)`), overlay hold-to-delete, transizioni di colore tra tab, slider di confronto.

## Gesti e drag

- Dismiss a inerzia: velocità `Math.abs(distanza)/tempoMs`, dismiss se `> ~0.11`. Una sventola basta, senza soglia di distanza.
- Smorzamento ai bordi: oltre il limite naturale si muove sempre meno.
- Pointer capture a drag iniziato, perché continui fuori dai limiti.
- Protezione multi-touch: ignorare i punti aggiuntivi a drag iniziato (`if (isDragging) return`).
- Attrito invece di arresti netti: sovra-trascinamento con resistenza crescente.

## Crossfade e stagger

- Un crossfade che mostra due stati sovrapposti nonostante easing e durata ben tarati: `filter: blur(2px)` durante la transizione, sotto i 20px.
- Stagger per le entrate di gruppo: 30–80ms tra gli elementi; di più sembra lento. È decorativo e non deve mai bloccare l'interazione.
  ```css
  .item { opacity: 0; transform: translateY(8px); animation: fadeIn 300ms ease-out forwards; }
  .item:nth-child(2) { animation-delay: 50ms; }
  .item:nth-child(3) { animation-delay: 100ms; }
  @keyframes fadeIn { to { opacity: 1; transform: translateY(0); } }
  ```

## Accessibilità

```css
@media (prefers-reduced-motion: reduce) {
  .element { animation: fade 0.2s ease; } /* si tengono opacità e colore, si toglie il movimento */
}
@media (hover: hover) and (pointer: fine) {
  .element:hover { transform: scale(1.05); } /* sul touch il tap innesca falsi hover */
}
```

```jsx
const reduce = useReducedMotion();
const closedX = reduce ? 0 : '-100%';
```

Reduced motion significa meno animazioni e più gentili, non zero: restano le transizioni che aiutano
la comprensione, spariscono movimenti e cambi di posizione.

## Coesione e token

- Il motion segue la personalità del componente: gioco più rimbalzante, dashboard secca e rapida.
- Curve e durate come token condivisi: cinque `cubic-bezier` scritte a mano quasi uguali sono un finding di consolidamento.
- Liste di entrata con opacità e altezza: nessuna formula, si regola finché funziona.

## Verifica a vista

- Rallentare: durata ×2–5 o pannello Animations dei DevTools.
- Fotogramma per fotogramma: pannello Animations di Chrome, deriva di tempo tra proprietà coordinate.
- Dispositivo reale per i gesti (drawer, swipe): telefono sul dev server per IP, ispezione remota di Safari.
- Occhi freschi il giorno dopo.
