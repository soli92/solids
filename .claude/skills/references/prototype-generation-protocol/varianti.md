# Varianti divergenti (`prototyping.variants` > 1)

**Ambito**: modalita' opzionale del `prototype-generation-protocol`. Va letta solo
quando `variants` effettivo e' maggiore di 1 (config `prototyping.variants` oppure flag
`--variants N` di `/prototype`, che vince). Con `variants: 1` (default) questa foglia non
si legge e il comportamento e' identico a quello senza la modalita'.

Adattata da una skill di terzi sotto licenza MIT (emilkowalski/skills, commit 715c180): il picker qui sotto e' markup e stili
propri della factory, non una copia.

---

## Principio

Il valore della modalita' e' la **divergenza**: tre tinte della stessa idea fanno sprecare
il selettore, perche' chi lo usa non impara nulla passando dall'una all'altra. Ogni
variante e' una direzione difendibile da sola. Condividere i token del design system non e'
convergenza: le varianti devono sembrare native del prodotto.

## Validazione di `N`

- `N` e' un intero in `2..5`. `N = 1` = modalita' spenta.
- `N > 5` → **rifiuto esplicito** (non troncamento silenzioso):
  `[prototype] --variants <N> non ammesso: massimo 5 (oltre, il confronto si diluisce). Usa un valore 2..5.`
- `N < 1` o non intero → rifiuto esplicito con lo stesso formato.
- Il backend deve supportare la modalita': oggi **`html`** (specificato qui sotto). Per
  `react | figma | penpot` il protocollo emette
  `[Fase 2] variants > 1 non supportato dal backend <b>: genero 1 variante` e prosegue con
  `variants: 1` (degrado dichiarato, mai silenzioso).

## Scelta delle direzioni (prima di scrivere codice)

Elenca le N direzioni in una tabella. Nome descrittivo della direzione («Quieta»,
«Editoriale», «Densa», «Giocosa»), **mai** «Opzione A/B/C» o «Variante 1/2».

| # | Nome | Asse | Posizione sull'asse |
|---|---|---|---|
| 1 | Quieta | motion | quasi assente, bordi al posto delle ombre |
| 2 | Editoriale | densita' | rada, tipografia grande, molto spazio |

Assi ammessi: **layout**, **densita'**, **personalita'**, **motion**, **modello di
interazione**. Regole:

1. Ogni variante dichiara asse e posizione in una frase **prima** di qualsiasi codice.
2. Due varianti che differiscono solo per colore o per copy sono **una sola**: se ne
   sostituisce una con un'alternativa reale (altro layout, altro modello di interazione,
   altra storia di motion).
3. **Criterio di completamento**: ogni variante ha nome e asse, e **nessuna coppia occupa
   la stessa posizione d'asse**. Due varianti possono condividere l'asse purche' le
   posizioni differiscano. Se il criterio non e' soddisfatto non si genera.
4. Se durante la costruzione due varianti convergono, se ne taglia una e lo si dichiara:
   un selettore con due direzioni distinte vale piu' di uno con tre di cui due uguali.

## Requisiti di ogni variante

- **Funziona davvero**: interazioni reali, stati raggiungibili, contenuti realistici
  (nomi, cifre e testi plausibili per il prodotto). Niente lorem ipsum, niente pulsanti
  morti, niente «immagina questa parte». Un `<!-- PLACEHOLDER -->` resta ammesso solo
  dove il contenuto e' davvero indeterminato (regola gia' vigente).
- **Token del design system** del progetto (`design_source`, art-director se attivo): colori,
  raggi, spaziature, font. Se non c'e' design system, default sobrio e neutro.
- Rispetta `fidelity` e, per `animated`, `prefers-reduced-motion`.
- Una sola cosa per esecuzione: se il brief copre piu' componenti si restringe al piu'
  influente e si propone il resto come esecuzione successiva.

## Selettore fra le varianti (cromo, non contendente)

Il selettore non e' una decisione di design: **non adotta token, font o colori del
progetto** e ha lo stesso aspetto in ogni esecuzione, cosi' non viene mai scambiato per
parte di cio' che si sta giudicando. E' una pillola scura, **in basso al centro**
(`data-position="top"` ammesso solo se una variante occupa il centro in basso: dock,
bottom sheet, stack di toast).

### Backend `html`: un unico file (INV-6)

Tutte le varianti stanno nello **stesso `index.html`** autocontenuto: ciascuna in un
`<template data-variant-name="...">`, stili della variante **scopati** sotto
`[data-proto-variant="<n>"]` (nessuna perdita di stile fra varianti), JS vanilla inline,
zero asset esterni (unica eccezione gia' prevista: Tailwind CDN se
`css_strategy: tailwind-cdn`). Nessun file per variante, nessun file aggiuntivo.

Markup (selettore a scelta singola → `radiogroup`; il replay sta fuori dal gruppo):

```html
<div class="pv-bar" data-ready-state="idle">
  <div class="pv-group" role="radiogroup" aria-label="Direzioni del prototipo">
    <span class="pv-mark" aria-hidden="true"></span>
    <button type="button" class="pv-opt" role="radio" aria-checked="true"  tabindex="0"  data-i="0">Quieta</button>
    <button type="button" class="pv-opt" role="radio" aria-checked="false" tabindex="-1" data-i="1">Editoriale</button>
  </div>
  <button type="button" class="pv-replay" aria-label="Rigioca l'animazione (tasto R)">&#8635;</button>
  <p class="pv-live" role="status" aria-live="polite"></p>
</div>
<main id="pv-stage"></main>
```

Il pulsante replay e' reso **solo** se almeno una variante ha un'entrata o una transizione
di stato da rigiocare; un confronto statico ha la pillola piu' corta.

Stili (prefisso `pv-`, valori fissi, nessun token del progetto):

```css
.pv-bar{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:2147483647;
  display:flex;align-items:center;gap:4px;padding:4px;border-radius:999px;
  background:rgba(20,20,22,.88);box-shadow:0 6px 20px rgba(0,0,0,.28);
  font:13px/1 system-ui,-apple-system,"Segoe UI",sans-serif;color:#fff;
  -webkit-user-select:none;user-select:none}
.pv-bar[data-position="top"]{bottom:auto;top:24px}
.pv-group{position:relative;display:flex;align-items:center;gap:2px}
.pv-mark{position:absolute;top:0;left:0;height:28px;border-radius:999px;
  background:rgba(255,255,255,.16);pointer-events:none}
.pv-bar[data-ready] .pv-mark{transition:transform 200ms cubic-bezier(.23,1,.32,1),width 200ms cubic-bezier(.23,1,.32,1)}
.pv-opt,.pv-replay{position:relative;height:28px;padding:0 12px;border:0;border-radius:999px;
  background:transparent;color:rgba(255,255,255,.72);font:inherit;cursor:pointer}
.pv-opt:hover,.pv-replay:hover{color:#fff}
.pv-opt[aria-checked="true"]{color:#fff;font-weight:600}
.pv-opt:focus-visible,.pv-replay:focus-visible{outline:2px solid #fff;outline-offset:2px}
.pv-live{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (prefers-reduced-motion:reduce){.pv-bar[data-ready] .pv-mark{transition:none}}
@media (forced-colors:active){.pv-bar{border:1px solid CanvasText;background:Canvas;color:CanvasText}
  .pv-opt[aria-checked="true"]{outline:2px solid Highlight}}
```

Il contrasto del testo attivo e di quello a riposo sullo sfondo scuro e' deliberatamente
alto; il cambio di stato non dipende dal solo colore (peso del font + `aria-checked`).

Comportamento (contratto fisso):

- **Tastiera**: `1`..`N` e `←`/`→` cambiano variante; `R` rigioca. Ignora l'evento se il
  focus e' in `input`, `textarea`, `select` o contenteditable, o se e' premuto un
  modificatore. Dentro il radiogroup frecce e Home/End seguono il pattern WAI-ARIA
  (roving `tabindex`, selezione che segue il focus), senza doppio salto.
- **Click** su un'opzione la seleziona: esattamente una ha `aria-checked="true"` e
  `tabindex="0"`, le altre `false` / `-1`.
- Lo **scambio di variante e' istantaneo** (si cambia spesso: nessuna animazione); solo il
  segnaposto `.pv-mark` scorre sul selettore stesso.
- La selezione persiste al reload con `?v=2` (default 1); il segnaposto prende la prima
  posizione senza animare (`data-ready` si aggiunge dopo il primo paint).
- Cambiare variante **rimonta** il contenuto (le animazioni d'entrata ripartono); `R`
  rimonta senza cambiare.
- A ogni cambio `.pv-live` annuncia il nome della direzione (`aria-live="polite"`).

Riferimento di cablaggio (il resto e' espressione idiomatica a discrezione del generatore):

```js
const tpls = [...document.querySelectorAll('template[data-variant-name]')];
const stage = document.getElementById('pv-stage');
const group = document.querySelector('.pv-group');
const opts = [...group.querySelectorAll('.pv-opt')];
const mark = group.querySelector('.pv-mark');
const live = document.querySelector('.pv-live');
let cur = 0;
function place(){ const o = opts[cur]; mark.style.width = o.offsetWidth+'px';
  mark.style.transform = 'translateX('+o.offsetLeft+'px)'; }
function mount(i){ stage.textContent = '';
  requestAnimationFrame(()=>{ const n = tpls[i].content.cloneNode(true);
    const root = n.firstElementChild; if (root) root.setAttribute('data-proto-variant', i+1);
    stage.appendChild(n); }); }
function select(i, focus){ if (i<0||i>=tpls.length) return; cur = i;
  opts.forEach((o,j)=>{ o.setAttribute('aria-checked', String(j===i)); o.tabIndex = j===i?0:-1; });
  if (focus) opts[i].focus();
  place(); live.textContent = tpls[i].dataset.variantName;
  const u = new URL(location); u.searchParams.set('v', i+1); history.replaceState(null,'',u);
  mount(i); }
opts.forEach((o,i)=>o.addEventListener('click',()=>select(i,false)));
document.querySelector('.pv-replay')?.addEventListener('click',()=>mount(cur));
addEventListener('resize', place);
document.addEventListener('keydown', e=>{
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable) return;
  if (e.metaKey||e.ctrlKey||e.altKey) return;
  const n = parseInt(e.key,10), inGroup = group.contains(e.target);
  if (n>=1 && n<=tpls.length) select(n-1, inGroup);
  else if (e.key==='ArrowRight'||e.key==='ArrowLeft'){ e.preventDefault();
    select((cur+(e.key==='ArrowRight'?1:-1)+tpls.length)%tpls.length, inGroup); }
  else if (e.key==='Home'&&inGroup){ e.preventDefault(); select(0,true); }
  else if (e.key==='End'&&inGroup){ e.preventDefault(); select(tpls.length-1,true); }
  else if (e.key==='r'||e.key==='R') mount(cur); });
select((parseInt(new URLSearchParams(location.search).get('v'),10)||1)-1, false);
requestAnimationFrame(()=>requestAnimationFrame(()=>document.querySelector('.pv-bar').setAttribute('data-ready','')));
```

### Altri backend

Il selettore resta cromo neutro con le stesse regole di comportamento; la resa e'
idiomatica del backend (es. una route isolata con un file per variante e un piccolo file
di harness) e non importa nulla nel codice di produzione. Finche' il backend non
dichiara il supporto vale il degrado a `variants: 1` descritto sopra.

## Check aggiuntivi in Fase 3 (solo meccanici, INV-4)

In aggiunta a quelli del backend, con `variants > 1`:

- [ ] `artifact_metadata.variants` elenca N voci `{nome, asse, posizione}`; nessun nome del
      tipo «Opzione/Variante + lettera o numero».
- [ ] Nessuna coppia con stessa posizione d'asse (criterio di completamento).
- [ ] Il file contiene N `<template data-variant-name>`; `html`: sempre **un solo file**
      (INV-6) e nessun asset esterno.
- [ ] Il selettore ha `role="radiogroup"`, una sola opzione con `aria-checked="true"`, e
      `:focus-visible` definito.
- [ ] Nessuna occorrenza di «lorem ipsum» nel file.

Sono verifiche di forma. Se la direzione sia buona, o quale funzioni meglio, **non** le
valuta il generatore.

## Dopo la scelta (INV-4)

Il protocollo presenta le direzioni e **si ferma**: la scelta e' umana o di un reviewer
separato (mai del generatore, mai nel log, mai «consigliata» nella tabella). Per ogni
direzione si riporta una riga su quando e' la scelta giusta e una su cosa costa; se
l'utente chiede quale sceglierebbe il generatore, rimanda al reviewer.

Alla scelta:

- la variante **promossa resta** (si integra dove deve stare seguendo le convenzioni del
  progetto, oppure resta come `index.html` ridotto a quella sola variante);
- le **altre si eliminano**, salvo richiesta esplicita di tenerle;
- se l'utente vuole un altro giro, si riparte dalla scelta delle direzioni divergendo
  *attorno* a quella preferita.
