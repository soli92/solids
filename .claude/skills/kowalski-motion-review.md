---
name: kowalski-motion-review
description: Revisione advisory del codice di animazione e motion (CSS, WAAPI, Motion) contro 10 standard di mestiere. Findings in tabella Prima/Dopo/Perché con file:riga, nessun verdetto. Opt-in ui_craft. Adattata da emilkowalski/skills review-animations @715c180.
---
# Revisione del motion (advisory)

Pre-condizione: `ui_craft.enabled: true` **e** `ui_craft.motion_review: true`, altrimenti non si applica.
Adattata da `review-animations` e dal metodo di `improve-animations/AUDIT.md` di Emil Kowalski
(MIT, originale in `vendor/emilkowalski-skills/`). Valori precisi (curve, durate, spring) in
[`references/kowalski-motion-review/standard.md`](references/kowalski-motion-review/standard.md):
caricalo quando un finding deve citare un valore, e non approssimare.

## Che cosa è, e che cosa non è

Esamina solo codice di animazione e motion. Non scrive feature, non corregge bug estranei, non
rivede codice che non anima.

**Advisory, nessun verdetto.** Le regole sono euristiche d'autore, non misure: un finding dice
«qui il motion probabilmente non è giusto», non «il codice è rotto». La skill non emette
Block/Approve e non può cambiare un verdetto. Il verdetto resta del CQRL
(`code-review-protocol`); quando gira come Passata 7 i finding finiscono in una sezione advisory.
Un finding può essere respinto con una motivazione scritta: è una conversazione, non un gate.

## I dieci standard

Ogni animazione nel diff si misura contro questi. Una violazione è un finding.

1. **Motion motivato.** Ogni animazione risponde a «perché si anima?»: coerenza spaziale,
   indicazione di stato, feedback, spiegazione, evitare un cambio brusco. «Fa scena» su un
   elemento visto spesso non è una ragione.
2. **Frequenza.** Il motion si commisura a quanto spesso si vede. Azioni da tastiera e 100+/giorno:
   nessuna animazione. Decine/giorno: ridotta o tolta. Occasionali: standard. Rare o di prima volta:
   può esserci piacere.
3. **Easing reattivo.** Entrate e uscite usano `ease-out` o una curva custom forte. `ease-in` sulla
   UI ritarda proprio il momento che l'utente guarda di più. Gli easing built-in sono deboli: ci si
   aspetta una `cubic-bezier` esplicita.
4. **Sotto i 300ms per la UI.** Oltre serve una ragione. I budget per elemento stanno in `standard.md`.
5. **Origine e correttezza fisica.** Popover, dropdown e tooltip scalano dal proprio trigger
   (`transform-origin`), non dal centro. Mai da `scale(0)`: si parte da `scale(0.9–0.97)` con
   opacità. I modali sono esenti: restano centrati.
6. **Interrompibilità.** Il motion innescato di rado o guidato da gesti (toast, toggle, drag) deve
   poter essere interrotto: transizioni CSS o spring che si riagganciano allo stato corrente, non
   keyframe che ripartono da zero.
7. **Solo `transform` e `opacity`.** Animare `width`/`height`/`margin`/`padding`/`top`/`left` è un
   problema di prestazioni, come le scorciatoie `x`/`y`/`scale` di Motion prima della 14.2 sotto carico.
8. **Accessibilità.** `prefers-reduced-motion` rispettato (più gentile, non zero: si tengono
   opacità e colore, si toglie il movimento). Il motion su hover sta dietro
   `@media (hover: hover) and (pointer: fine)`.
9. **Entrata e uscita asimmetriche.** La fase deliberata (pressione, hold, conferma distruttiva)
   è più lenta; la risposta del sistema scatta. Tempi simmetrici su press-and-release sono un finding.
10. **Coesione.** Il motion segue la personalità del componente e del prodotto: un gioco può
    rimbalzare, una dashboard resta secca. Personalità fuori tono, o un crossfade che mostra due stati
    sovrapposti dove un leggero blur li fonderebbe, sono finding. Nel dubbio, la mossa più forte è
    spesso cancellare il motion.

## Segnali d'allarme

Da segnalare a vista:

- `transition: all` (proprietà non delimitate)
- `scale(0)`, o entrate in sola dissolvenza senza trasformazione iniziale
- `ease-in` su qualunque interazione; easing built-in debole su un'animazione deliberata
- animazione su scorciatoia da tastiera, toggle di command palette o azione 100+/giorno
- durata UI oltre 300ms senza motivo dichiarato
- `transform-origin: center` su popover/dropdown/tooltip ancorato a un trigger
- keyframe su toast, toggle o qualunque cosa aggiunta in rapida successione
- animazione di proprietà di layout (`width`/`height`/`margin`/`padding`/`top`/`left`)
- `x`/`y`/`scale` di Motion prima della 14.2, o animazioni `layout` mentre la pagina è occupata
- variabile CSS aggiornata su un genitore per guidare la trasformazione di un figlio
- movimento senza gestione di `prefers-reduced-motion`
- `:hover` con motion non protetto
- tempi simmetrici su un'interazione press-and-release o hold
- entrata di un gruppo tutta insieme dove servirebbe una sfalsatura (stagger) di 30–80ms

## Ordine delle correzioni

Si propone la mossa più in alto possibile; si scende solo se la precedente non basta.

1. **Cancellare l'animazione** (alta frequenza, nessuno scopo, da tastiera).
2. **Ridurla**: durata più corta, trasformazione più piccola, meno proprietà.
3. **Correggere l'easing**: `ease-in` → `ease-out` o curva forte.
4. **Correggere origine e fisicità**: `transform-origin` giusto; `scale(0)` → `scale(0.95)` + opacità.
5. **Renderla interrompibile**: keyframe → transizioni, o spring per i gesti.
6. **Portarla sulla GPU**: proprietà di layout → `transform`/`opacity`; WAAPI per il CSS programmatico.
7. **Tempi asimmetrici**: rallentare la fase deliberata, far scattare la risposta.
8. **Rifinire**: blur per mascherare un crossfade, stagger per i gruppi, `@starting-style` per le entrate.
9. **Accessibilità e coesione**: reduced-motion, hover protetto, tono coerente col prodotto.

## Formato dei finding

Una tabella per impatto, una riga per problema, mai un elenco «Prima:/Dopo:». Ogni riga cita
`file:riga`. Il valore (curva, durata, spring) si copia da `standard.md`, non si stima.

| Prima | Dopo | Perché |
|---|---|---|
| `Button.css:42` `transition: all 300ms` | `transition: transform 200ms ease-out` | `all` anima proprietà non volute, fuori dalla GPU |
| `Menu.css:17` `transform: scale(0)` | `transform: scale(0.95); opacity: 0` | `scale(0)` sembra uscire dal nulla |
| `Dropdown.css:9` `ease-in` | `cubic-bezier(0.23, 1, 0.32, 1)` | `ease-in` ritarda il momento che l'utente guarda |

Raggruppa per impatto, dal più alto, omettendo i gruppi vuoti:

1. **Rotture della sensazione**: easing lento, «dal nulla», motion su azioni frequenti o da tastiera.
2. **Semplificazioni mancate**: animazioni da togliere o ridurre molto.
3. **Prestazioni**: proprietà non GPU, rischio di frame persi, ricalcoli di stile.
4. **Interrompibilità e tempi**: keyframe dove servono transizioni o spring; simmetria da rompere.
5. **Origine, fisicità e coesione**: origine sbagliata, personalità fuori tono, crossfade brusco.
6. **Accessibilità**: reduced-motion e protezione dell'hover.

Chiudi con un riepilogo senza decisione: numero di finding per gruppo e l'elenco «da verificare a vista».

## Da verificare a vista

La sensazione di una spring, di un crossfade, di un'accelerazione **non si giudica dal codice**:
non è un finding, è una voce in questa lista, con il passo concreto per verificarla.

| Che cosa | Come si verifica |
|---|---|
| Easing, origine, coordinamento tra proprietà | DevTools, pannello Animations: rallentare al 10% e controllare che i colori sfumino pulito, che l'easing non si fermi di colpo, che `transform-origin` sia giusto |
| Crossfade che mostra due stati sovrapposti | Rallentare al 10%, valutare se un `filter: blur(2px)` li fonde |
| Rispetto di `prefers-reduced-motion` | Emularlo in DevTools (Rendering → Emulate CSS media feature) e ripassare le interazioni |
| Hover su touch | Emulare un dispositivo touch e verificare che il tap non innesti falsi hover |
| Gesti (drawer, swipe, drag) | Dispositivo reale: telefono sul dev server per IP, ispezione remota |
| Coesione generale | Rivedere a occhi freschi il giorno dopo |

## Guida rapida

- Movimento predeterminato: CSS, `@starting-style`, WAAPI. Dinamico, interrompibile o da gesto: JS o spring.
- Le librerie (per esempio Base UI, Motion) sono esempi di dove compaiono i valori, non una scelta
  obbligata: i finding si formulano sul comportamento e si adattano allo stack del progetto.
- Questa skill non rilancia `/review` e non avvia altri agenti.
