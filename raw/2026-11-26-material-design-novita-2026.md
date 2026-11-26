---
title: Material Design — novità e direttive al 26/11/2026
source: m3.material.io (pagine renderizzate con Chromium headless il 2026-11-26) + fonti terze dichiarate
date: 2026-11-26
type: research-report
---

# Material Design — novità e direttive al 26/11/2026

## Sintesi

- **Non esiste un "Material 4".** La generazione corrente resta **Material 3**, con l'estensione
  **M3 Expressive** (maggio 2025). Google lo ha dichiarato nel post di lancio: «this isn't "M4"».
- Le uscite del 2026 sono quattro, tutte ufficiali sul blog di Material:

| Data | Uscita | Contenuto |
|---|---|---|
| 19/05/2026 | What's new at Google I/O 2026 | Expressive layout: scaffold (bars, rails, panes), nuovo sistema di spaziatura a 8dp, breakpoint, guide per watch e XR, liste e menu Expressive, search Expressive |
| 19/05/2026 | Material Android is Compose-first | Material Views 1.14.0 è l'ultima release stabile delle View (da qui solo manutenzione); tutto lo sviluppo va su Compose; Styles API; Navigation3 |
| 16/11/2026 | Parametric prototyping | Metodo di design con prototipi parametrici generati con AI (con questo metodo sono nati il time picker Expressive e gli scroll field) |
| 18/11/2026 | Compose Material 3 1.5.0 stabile | API core ed Expressive diventano stabili; Compose Material 2 deprecato |

- Altre modifiche dalle pagine delle linee guida: **ago 2026** altezza della scrittura nella scala
  tipografica; **ott 2026** time picker Expressive con variante a scorrimento.

---

## 1. Layout Expressive (I/O 2026, maggio 2026)

### 1.1 Nomenclatura cambiata
- **Window size classes → breakpoints.**
- **Responsive layout → adaptive design.**
- Nuovi termini ufficiali: *rulers* (linee di allineamento globali), *safety region* (zone della UI
  di sistema: status bar, gesture bar), *drag handle* (ridimensiona i pannelli), *spacer* (spazio
  tra pannelli sui pieghevoli), *gap*, *margin*.

### 1.2 Scaffold: bars → rails → panes
Lo scaffold organizza ogni layout adattivo in tre livelli:

- **Bars**: incorniciano la pagina (app bar in alto, navigation bar in basso). Possono coprire un
  solo pannello o tutta la finestra. Stanno accanto alla safety region, che non deve contenere
  contenuto primario.
  - App bar: titolo più 1-2 azioni essenziali.
  - Navigation bar: da 3 a 5 viste primarie, nei breakpoint compact e medium.
- **Rails**: il perimetro attorno ai pannelli, subito dopo le bar.
  - Su compact, le rail in alto e in basso ospitano toolbar, input di chat, FAB e altri controlli
    primari della schermata (la toolbar può fluttuare).
  - Sugli schermi grandi ci sono anche le rail laterali: quella iniziale contiene la navigation
    rail, quella finale controlli di supporto o una toolbar verticale.
  - In XR le rail diventano **orbiter**, che fluttuano fuori dall'area dei contenuti.
- **Panes**: contengono il contenuto. Sono da **1 a 3 visibili** e si adattano ai breakpoint.

Implementazione: Figma M3 Design Kit, token di spaziatura, **Jetpack Compose: Rulers**,
Compose Canonical layouts, **Navigation3** (Material Adaptive ora è integrato con Navigation3).

### 1.3 Breakpoint

| Breakpoint | Larghezza | Dispositivi tipici | Pannelli consigliati (altri ammessi) |
|---|---|---|---|
| Compact | < 600dp | telefono in verticale | 1 |
| Medium | 600–839dp | tablet e pieghevole aperto in verticale | 1 (2) |
| Expanded | 840–1199dp | telefono in orizzontale, tablet e pieghevole in orizzontale, desktop | 2 (1) |
| Large | 1200–1599dp | desktop | 2 (1) |
| Extra-large | ≥ 1600dp | desktop, monitor ultra-wide | 2 (1, 3) |

- Su Android esistono anche i breakpoint in altezza (compact, medium, expanded), ma servono di rado.
- Si progetta per breakpoint, non per dispositivo: la finestra cambia con il multi-window e con
  l'apertura di un pieghevole, e la rotazione spesso cambia breakpoint.
- Passando da un breakpoint all'altro ci si fanno cinque domande: cosa **rivelare**, come
  **dividere**, cosa **ridimensionare**, cosa **riposizionare**, cosa **scambiare**.
- Righe di testo da **40 a 60 caratteri** a ogni breakpoint.
- Medium: 2 pannelli solo per contenuti a bassa densità con azioni chiare.
- Scambi tipici:

| Funzione | Compact | Medium | Expanded |
|---|---|---|---|
| Navigazione | navigation bar | navigation rail collassata | navigation rail collassata |
| Navigazione (espansa) | navigation rail espansa modale | navigation rail espansa modale | navigation rail espansa standard |
| Comunicazione | dialog semplice o a schermo intero | dialog semplice | dialog semplice |
| Selezione supplementare | bottom sheet | menu | menu |

- Gli scambi devono essere tra componenti funzionalmente equivalenti (mai un bottone al posto di
  un chip o di un menu).

### 1.4 Pannelli
- **Fixed** (larghezza fissa) o **flexible**. Ogni layout ha **almeno un pannello flessibile**.
  **Permanent** o **temporary**.
- **Split-pane**: spacer centrato visivamente, ogni pannello al 50 %. Con navigation rail, la
  rail più il primo pannello fanno il 50 %. È la scelta migliore sui pieghevoli.
- **Fixed-and-flexible**: tipico da expanded in su. Il pannello fisso è spesso temporaneo
  (side sheet, liste leggere).
- **Tre pannelli**: solo a extra-large, con un side sheet standard come terzo pannello. Mai più
  di tre. Pannelli fissi consigliati a **412dp** (il side sheet arriva al massimo a 400dp).
- **Ridimensionamento con drag handle**: larghezze di snap consigliate **360dp** e **412dp**. Il
  drag handle si aziona anche con tap, doppio tap o pressione lunga.
  - *Persistent*: la larghezza scelta si ricorda anche dopo la chiusura e il cambio di
    breakpoint. È il default.
  - *Temporary*: si torna al default alla riapertura (supporting pane).
- **Presentazione**: *co-planar* (affiancati: gli strumenti persistenti devono esserlo),
  *floating* (sopra: i task temporanei restano floating), *docked* (agganciato a un bordo, come
  il bottom sheet).
- **Strategie di adattamento**: *show/hide*, *levitate* (il pannello diventa floating o docked;
  sugli schermi grandi floating è il default e lo scrim è opzionale), *reflow* (riorganizzazione
  e impilamento verticale).
- Su schermi grandi i pannelli docked diventano preferibilmente co-planar.
- **Accessibilità**: l'ordine del focus segue la disposizione visiva. Un pannello floating
  modale porta il focus sul primo elemento e alla chiusura lo restituisce al trigger; se si è
  aperto da solo, il focus va all'elemento successivo più logico. Un pannello non modale è
  raggiungibile e lasciabile nell'ordine di lettura.
- **XR**: i pannelli diventano *spatial panel* separati, con contenimento esplicito.

### 1.5 Layout canonici
**Feed**, **list-detail** e **supporting pane** (il pannello primario occupa circa 2/3). Ognuno
ha configurazioni per compact, medium ed expanded. Per layout personalizzati si parte da questi
o si sovrappongono elementi dello scaffold. La strategia *levitate* serve i task focalizzati
(carrello, commenti, creazione di un evento).

---

## 2. Nuovo sistema di spaziatura (maggio 2026)

### 2.1 Principi
- Scala **lineare a 8dp**: `space100 = 8dp`. I token sono moltiplicatori: `space225 = 18dp`
  (8 × 2.25).
- Tre categorie: **padding** (dentro un elemento), **gap** (tra elementi in un contenitore o in
  una griglia), **margin** (fuori da un elemento).
- Posizioni: vertical, horizontal, top, bottom, **leading** e **trailing** (si invertono in RTL).
- **Usare padding e gap prima dei margin.** Nei componenti Material i margin sono rari. Si
  definiscono padding e gap sul contenitore padre, non margin sui figli.
- Componenti semplici: un gap orizzontale e uno verticale. Componenti complessi: gap nominati
  per gli elementi che separano (es. *icon-label gap*).
- **Testo scalato al 200 %: la spaziatura resta la stessa.**
- La spaziatura vive dentro ogni componente, diversamente dal colore che è globale: il token di
  padding del componente punta al token di sistema, che si risolve nel valore.

### 2.2 Token di sistema (`md.sys.measurement.spaceXXX`, solo su Jetpack Compose)

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

- Disponibilità: **Compose sì**, Android Views no, Web no. Il collegamento di tutti i componenti
  ai token è dichiarato ancora in corso.
- **Nuova convenzione dei nomi** per gli attributi di spaziatura dei componenti: `padding`,
  `margin` e `gap` più posizione (horizontal, vertical, leading, trailing, top, bottom). Esempio:
  «Medium button: leading padding». Sostituisce la vecchia forma `leading-space`,
  `trailing-space`, `top-space`, `bottom-space`, `between-space`.
- Esempio dalla specifica: il contenitore della search ha 8dp di padding verticale, 8dp di gap
  orizzontali e 24dp di margini orizzontali, che diventano **12dp quando ha il focus**.

### 2.3 Personalizzazione
1. **Rimappare un componente** in tutto il prodotto (es. padding superiore del bottone da
   `space125` a `space200`).
2. **Aggiungere token di sistema e pattern** (es. un token *surface content horizontal padding*
   condiviso da card e sheet).
3. **Adattare a layout e densità**: mappare token diversi per tipo di dispositivo; per la
   densità variare il padding verticale.

### 2.4 Uso espressivo e densità
- La spaziatura raggruppa (implicitamente con prossimità e spazio vuoto, esplicitamente con
  outline, divider e ombre), dirige l'attenzione (ritmo, somiglianza, prossimità, continuità) ed
  esprime carattere (punti focali, spazio negativo). Un layout denso comunica serietà e focus, uno
  arioso calma. Il desktop può essere più generoso del mobile.
- **Densità**: scala 0, −1, −2, −3; ogni passo toglie circa 4dp di altezza o di padding verticale.
  La densità è **opt-in dell'utente**, non cambia da sola tra breakpoint o orientamento e non si
  applica a componenti di task focalizzati (menu) o di allerta (snackbar, dialog). Il
  **target minimo resta 48×48dp** (48×48 CSS px sul web), anche se l'icona è più piccola. La
  dimensione del testo non cambia con la densità.

---

## 3. Componenti aggiornati nel 2025-2026

| Componente | Data | Novità |
|---|---|---|
| Search | feb 2025, Compose a I/O 2026 | «search bar» e «search view» diventano un solo componente, **search**. Stili *contained* (consigliato, contenitore pieno persistente) o *divided*. Gap tra gruppi di risultati. La barra si allarga al focus. Più flessibilità per le icone finali. Si aggiunge la **search app bar** come punto d'ingresso globale enfatizzato |
| Menus | nov 2025 | **Vertical menu** (consigliato per nuovi design): nuove forme, stili colore *standard* e *vibrant*, stati di selezione, sottomenu con motion rivisto, gap. Il menu base resta disponibile. Menu contestuali con clic secondario. Per azioni sempre visibili si usa una toolbar |
| Lists | dic 2025 | **Expressive list** (consigliata): stile *standard* o *segmented*, selezione evidenziata, slot flessibili. Altezze 56, 72 e 88dp; allineamento in alto da 88dp o da tre righe |
| Time pickers | ott 2026 | Nuova variante **scroll**: va inline, mentre la dial va in un modale; entrambe si possono scambiare con l'input da tastiera. Più contrasto sui campi ore/minuti e sul selettore del quadrante; bottoni AM/PM con forma, colore e comportamento Expressive; rimossa l'etichetta «Select time». In Compose lo stile Expressive si chiama **«vibrant»** |
| Scroll fields | nuovo | Selezione di unità di misura (distanza, peso, temperatura). Scorrimento o input; tre taglie: small (1-2 cifre), medium (3), large (4); lista finita o infinita; combinabili. Solo Compose Expressive |

---

## 4. Typography: altezza della scrittura (agosto 2026)
La scala tipografica adatta da sola l'interlinea alla **categoria di altezza della scrittura**
della lingua (small, medium, large, extra large) e i componenti possono adattare la propria
dimensione di conseguenza. La scala resta di **30 stili: 15 baseline e 15 emphasized**. In
Compose 1.5.0 si può impostare un **font di brand su tutta la scala** in un colpo solo.

## 5. Watch e XR (I/O 2026)
- **Watch (Wear OS, «GM3 Expressive»)**: contenitori e bottoni che seguono il bordo dello
  schermo rotondo, motion a molle, shape morphing per gli stati, colore dinamico con palette
  tonali profonde, nuovi ruoli tipografici **arc text** (titoli curvi) e **numeral text**.
- **XR immersivo**: pattern familiari (i componenti Material in 3D), comfort (contenuti al centro
  del campo visivo, posture seduta, in piedi e sdraiata), profondità (elevation spaziale, modelli
  3D), audio spaziale, aptica, accessibilità. Le **icon button XR hanno target di 56dp con
  offset di 4dp**. Componenti adattati: app bar, dialog, navigation bar, navigation rail, toolbar.
  *Home space* contro *full space*; spatial panel e orbiter esistono solo in full space.
- Correlato (Google Design): **Jetpack Compose Glimmer**, sistema di design per gli occhiali AI
  con display.

## 6. Piattaforme: Compose-first
- **Material Views (MDC-Android) 1.14.0** porta Expressive anche alle View (temi, lista
  Expressive, scala enfatizzata, stili Expressive per 11 componenti) ed è **l'ultima release
  con nuove funzionalità**. Da qui solo correzioni critiche.
- **Compose Material 3 1.5.0 + Jetpack Compose 1.13** (18/11/2026):
  - quasi tutte le API sperimentali diventano stabili;
  - ogni componente core di M2 ha un equivalente M3 stabile (app bar, search, slider, carousel,
    basic alert dialog);
  - componenti Expressive stabili: split button, button group, toggle button e chip con shape
    morphing, floating toolbar, wavy progress indicator, menu annidati, list item segmentati;
  - colori, forme e motion Expressive stabili;
  - accessibilità e navigazione da tastiera migliorate (date picker, time picker, slider,
    scaffold, navigazione);
  - **`androidx.compose.material` (M2) deprecato**;
  - Compose 1.13 aggiunge flexbox e grid stabili e un blur progressivo nativo.
- Dalle note di rilascio Android, lette in parte:
  - nuovo artefatto `material3-ripple` con focus ring interni;
  - `1.6.0-alpha01` (18/11/2026): transizioni di navigazione shared-axis e fade-through con
    predictive back, deprecazione degli overload `TextField(value, onValueChange)` a favore di
    `TextFieldState`, altezza dello ScrollField da 200 a 120dp.
- **In arrivo**: integrazione della **Compose Styles API** (personalizzazione senza
  ricomposizione) per i componenti Material.
- Design Kit Figma e linee guida seguono ciò che è disponibile in Compose.
- Su **Web** e **Flutter** le varianti Expressive risultano in gran parte «Unavailable» nelle
  tabelle di disponibilità. La spaziatura a token è solo su Compose; il motion fisico è
  «compatibile» sul web tramite conversione delle molle.

## 7. Metodo: prototipazione parametrica (novembre 2026)
Prototipi in codice, generati con strumenti AI (Google cita **Antigravity**), con slider per
le variabili (range di colore, padding, raggi, dimensione del testo) al posto di tavole Figma
statiche. Serve per componenti complessi (time picker, toolbar, tab) e per confronti tra
versioni. Le sei pratiche indicate:
1. mappare le combinazioni migliori e i limiti;
2. raffinare i parametri;
3. raggruppare i parametri legati;
4. sovrapporre keyline, token e misure così che il prototipo faccia da specifica;
5. salvare preset (export JSON da riusare nel prompt successivo);
6. aggiungere un pulsante «randomize» per uscire dai bias.

---

## 8. Base M3 Expressive (maggio 2025), ancora in vigore
- **Ricerca**: 46 studi con oltre 18.000 partecipanti; gli elementi chiave si trovano fino a
  **4 volte più in fretta** nelle schermate Expressive.
- **14 componenti nuovi o aggiornati**: button group, FAB menu, loading indicator, split button
  e toolbar sono nuovi; app bar, bottoni, extended FAB, FAB, icon button, navigation bar,
  navigation rail, progress indicator e slider sono aggiornati.
- **Motion fisico** (sostituisce il sistema durata + easing):
  - schemi *expressive* (default, con overshoot) e *standard* (utilitaristico);
  - molle definite da stiffness, damping e velocità iniziale;
  - token `md.sys.motion.spring.{fast|default|slow}.{spatial|effects}`: spatial per posizione,
    dimensione, rotazione e raggi, con overshoot; effects per colore e opacità, senza overshoot;
  - lo schema si sceglie a livello di prodotto;
  - 21 componenti Compose lo usano di default;
  - personalizzazione a 3 livelli: schema di default, `MotionScheme` custom, override per
    elemento.
- **Shape**:
  - libreria di **35 forme** con morphing integrato;
  - raggi: large **20dp**, extra-large **32dp**, nuovo extra-extra-large **48dp**;
  - il «pienamente arrotondato» usa `full` (non più il 50 %);
  - principi: tensione tra tondo e squadrato, forma non semantica, forme astratte con
    parsimonia, 2.5D.
- **Typography**: 15 stili baseline più 15 **emphasized**; Google Sans Flex è open source;
  Roboto Flex non fa ancora parte della scala.
- **Colore**: schemi vibranti ed espansi su colore dinamico.
- **Le 7 tattiche Expressive**:
  1. variare le forme;
  2. colori ricchi e contrastati;
  3. tipografia per guidare l'attenzione;
  4. contenere per enfatizzare;
  5. motion fluido;
  6. flessibilità dei componenti;
  7. **hero moment**, al massimo uno o due per prodotto.

---

## 9. Impatto su soli-ds (osservazione, non verificata a fondo)
Dalla wiki di `solids` (`wiki/concepts/design-principles.md`, `foundations/radius.md`):

| Area | soli-ds oggi | Direttiva M3 attuale | Scarto |
|---|---|---|---|
| Motion | token `standard` / `emphasized`, «allineati a M3» | M3 ha sostituito durata + easing con le molle (schemi expressive e standard, token spatial ed effects × fast, default, slow) | L'allineamento dichiarato si riferisce al sistema precedente |
| Radius | sm→xl = 8 / 12 / 16 / 20px | scala M3: large 20dp, extra-large 32dp, extra-extra-large 48dp, `full` | Da riallineare se si vuole restare «in linea con M3» |
| Spaziatura | da verificare | scala a 8dp con token `spaceXXX` e convenzione padding/gap/margin + posizione | Da confrontare |
| Breakpoint | da verificare | 600 / 840 / 1200 / 1600 dp | Da confrontare |

Proposta: confronto mirato dei token di soli-ds con le sezioni 2, 1.3 e 8, prima di qualunque
modifica. Questa sezione segnala gli scarti e non decide nulla.

---

## Fonti e metodo
**Primarie**: lette in testo integrale renderizzando le pagine con Chromium headless, perché il
sito è client-side e un fetch semplice restituisce solo il titolo.
- [Blog Material, indice](https://m3.material.io/blog)
- [What's new at Google I/O 2026](https://m3.material.io/blog/whats-new-at-io26)
- [Material Android is Compose-first](https://m3.material.io/blog/material-is-compose-first)
- [Compose Material 3 1.5.0 is stable](https://m3.material.io/blog/compose-material-3-is-stable)
- [Parametric prototyping](https://m3.material.io/blog/enhance-your-component-designs-with-parametric-prototyping)
- [Start building with M3 Expressive (2025)](https://m3.material.io/blog/building-with-m3-expressive)
- Layout: [overview](https://m3.material.io/foundations/layout/layout-overview), [scaffold](https://m3.material.io/foundations/layout/scaffold), [bars](https://m3.material.io/foundations/layout/scaffold/bars), [rails](https://m3.material.io/foundations/layout/scaffold/rails), [panes](https://m3.material.io/foundations/layout/scaffold/panes), [breakpoints](https://m3.material.io/foundations/layout/breakpoints/overview), [canonical](https://m3.material.io/foundations/layout/canonical-examples/overview), [grids & spacing](https://m3.material.io/foundations/layout/grids-spacing/overview), [spacing](https://m3.material.io/foundations/layout/grids-spacing/spacing), [density](https://m3.material.io/foundations/layout/grids-spacing/density)
- Spaziatura: [overview](https://m3.material.io/styles/spacing/overview), [applying](https://m3.material.io/styles/spacing/applying-spacing), [tokens](https://m3.material.io/styles/spacing/tokens)
- Stili: [motion](https://m3.material.io/styles/motion/overview/how-it-works), [shape](https://m3.material.io/styles/shape/overview-principles), [typography](https://m3.material.io/styles/typography/overview)
- Componenti: [lists](https://m3.material.io/components/lists/overview), [menus](https://m3.material.io/components/menus/overview), [search](https://m3.material.io/components/search/overview), [time pickers](https://m3.material.io/components/time-pickers/overview), [scroll fields](https://m3.material.io/components/scroll-fields/overview)
- Form factor: [watches](https://m3.material.io/foundations/watches/overview), [XR](https://m3.material.io/foundations/xr/design/overview)
- [Note di rilascio Compose Material3](https://developer.android.com/jetpack/androidx/releases/compose-material3): lette in parte (la pagina è stata troncata); il dettaglio di 1.6.0-alpha01 viene dal testo letto per intero

**Secondarie** (solo contesto):
- [9to5Google, time picker a scorrimento (17/11/2026)](https://9to5google.com/2026/11/17/material-3-expressive-scrolling-time-picker/)
- [9to5Google, Material 3 Expressive con Liquid Glass su iOS (26/09/2026)](https://9to5google.com/2026/09/26/material-3-liquid-glass/): su iPhone Google sta mescolando M3 Expressive e Liquid Glass (Photos 7.94, Health); non è una direttiva Material

**Scartate**: bytevikas.com (cronologia delle versioni smentita dalle note ufficiali) e la voce
«principi reintrodotti a giugno 2026», che riguarda le Apple HIG, non Material.

**Limiti**: le pagine *Specs* dei singoli componenti (valori dp e token per componente), le
sottopagine *Watches* e *XR* e i dettagli di `grids-spacing/grids` (colonne per breakpoint) non
sono stati letti.
