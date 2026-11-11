/**
 * mascotte.js — indicatore di stato non testuale (EP-067 US-292/294).
 *
 * TRE INVARIANTI, e sono la ragione per cui questo file puo' esistere senza
 * peggiorare l'accessibilita' della plancia:
 *
 *   1. E' SEMPRE `aria-hidden`. Per chi usa uno screen reader la mascotte NON
 *      ESISTE — ed e' il trattamento corretto per contenuto decorativo, non una
 *      rinuncia.
 *   2. NON VEICOLA MAI un'informazione assente altrove. Ogni stato che mostra e'
 *      disponibile in forma testuale nella stessa vista. Un test fallisce se questa
 *      proprieta' si rompe.
 *   3. E' DISATTIVABILE senza perdita di informazione, e la scelta persiste.
 *
 * La mascotte non e' un canale di accesso: e' codifica RIDONDANTE, nel senso di
 * US-286. Per chi ha affaticamento da lettura o carico cognitivo alto un secondo
 * canale iconico aiuta; per tutti gli altri non toglie niente, perche' non porta
 * niente di esclusivo.
 *
 * TECNICA: due fogli 3x3 (nove direzioni, nove espressioni) mossi con
 * `background-position` — nessun JS per fotogramma, nessuna libreria. E' il
 * meccanismo di `nilbuild/page-mascot` (MIT, Kamran Ahmed), qui riscritto in
 * JavaScript semplice perche' la plancia non ha React, e con i nove stati mappati
 * sugli stati della factory invece che sul cursore.
 *
 * SENZA FOGLI: si disegna una faccia in SVG, generata qui. Nessun asset esterno,
 * nessuna dipendenza di rete (US-279 AC6), nessun binario committato. Puntare
 * `sheets` a due file veri resta possibile e usa lo stesso contratto di page-mascot.
 */

'use strict';

/** Nove stati della factory -> nove espressioni. La tabella e' DICHIARATA, non implicita. */
export const STATI = {
  'inattivo':        { cella: 6, nome: 'sleepy',    testo: 'Nessun lavoro in corso.' },
  'in-lavorazione':  { cella: 0, nome: 'blink',     testo: 'La factory sta lavorando.' },
  'attesa-risposta': { cella: 3, nome: 'surprised', testo: 'La factory attende una tua risposta.' },
  'concluso':        { cella: 8, nome: 'delighted', testo: 'Il lavoro si e\' concluso.' },
  'errore':          { cella: 7, nome: 'dizzy',     testo: 'Il turno si e\' chiuso con un errore.' },
  'non-osservabile': { cella: 5, nome: 'bashful',   testo: 'Una fonte non e\' osservabile.' },
  'stantio':         { cella: 4, nome: 'wink',      testo: 'Alcuni dati non sono freschi.' },
  'scrittura-off':   { cella: 2, nome: 'sparkle',   testo: 'Sola lettura: il runtime non risponde.' },
  'concorrenza':     { cella: 1, nome: 'heart',     testo: 'Un\'altra sessione e\' attiva sul repo.' },
};

const VOLTI = {
  sleepy:    { occhi: 'chiusi',  bocca: 'piccola',  segno: 'z' },
  blink:     { occhi: 'chiusi',  bocca: 'sorriso',  segno: null },
  surprised: { occhi: 'tondi',   bocca: 'o',        segno: '!' },
  delighted: { occhi: 'chiusi',  bocca: 'grande',   segno: null },
  dizzy:     { occhi: 'spirali', bocca: 'onda',     segno: null },
  bashful:   { occhi: 'chiusi',  bocca: 'piccola',  segno: null },
  wink:      { occhi: 'occhiolino', bocca: 'sorriso', segno: null },
  sparkle:   { occhi: 'aperti',  bocca: 'sorriso',  segno: '*' },
  heart:     { occhi: 'chiusi',  bocca: 'sorriso',  segno: '+' },
};

const occhio = (tipo, x) => ({
  chiusi:     `<path d="M${x - 7} 42 q7 -7 14 0" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>`,
  tondi:      `<circle cx="${x}" cy="42" r="8" fill="currentColor"/><circle cx="${x + 3}" cy="39" r="2.5" fill="var(--fondo)"/>`,
  aperti:     `<circle cx="${x}" cy="42" r="6" fill="currentColor"/><circle cx="${x + 2}" cy="40" r="2" fill="var(--fondo)"/>`,
  spirali:    `<path d="M${x} 42 m-6 0 a6 6 0 1 1 6 6 a4 4 0 1 1 -4 -4" fill="none" stroke="currentColor" stroke-width="2.5"/>`,
  occhiolino: x < 50
    ? `<path d="M${x - 7} 42 q7 -7 14 0" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>`
    : `<circle cx="${x}" cy="42" r="6" fill="currentColor"/>`,
}[tipo]);

const bocca = (tipo) => ({
  piccola: '<path d="M44 60 q6 4 12 0" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
  sorriso: '<path d="M38 58 q12 10 24 0" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
  grande:  '<path d="M36 56 q14 16 28 0 z" fill="currentColor"/>',
  o:       '<ellipse cx="50" cy="61" rx="6" ry="8" fill="currentColor"/>',
  onda:    '<path d="M38 60 q6 -6 12 0 q6 6 12 0" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
}[tipo]);

const segni = { z: 'z z', '!': '!', '*': '✦', '+': '♥' };

function disegna(nome) {
  const v = VOLTI[nome];
  return `<svg viewBox="0 0 100 100" width="100%" height="100%" focusable="false">
    <circle cx="50" cy="52" r="34" fill="var(--pannello)" stroke="currentColor" stroke-width="3"/>
    <circle cx="30" cy="26" r="9" fill="var(--pannello)" stroke="currentColor" stroke-width="3"/>
    <circle cx="70" cy="26" r="9" fill="var(--pannello)" stroke="currentColor" stroke-width="3"/>
    ${occhio(v.occhi, 38)}${occhio(v.occhi, 62)}${bocca(v.bocca)}
    <circle cx="26" cy="56" r="5" fill="currentColor" opacity=".25"/>
    <circle cx="74" cy="56" r="5" fill="currentColor" opacity=".25"/>
    ${v.segno ? `<text x="80" y="18" font-size="16" fill="currentColor">${segni[v.segno]}</text>` : ''}
  </svg>`;
}

const CHIAVE = 'plancia.mascotte';

export class Mascotte {
  /** @param {HTMLElement} host  @param {{directions?:string, reactions?:string}} sheets */
  constructor(host, sheets = {}) {
    this.host = host;
    this.sheets = sheets;
    this.stato = null;
    // `aria-hidden` qui e per sempre: e' l'invariante 1, non un default modificabile.
    host.setAttribute('aria-hidden', 'true');
    host.classList.add('mascotte');
    if (sheets.reactions) {
      host.style.backgroundImage = `url("${sheets.reactions}")`;
      host.style.backgroundSize = '300% 300%';
      host.style.backgroundRepeat = 'no-repeat';
    }
  }

  static attiva() {
    try { return localStorage.getItem(CHIAVE) !== 'off'; } catch { return true; }
  }

  static imposta(attiva) {
    try { localStorage.setItem(CHIAVE, attiva ? 'on' : 'off'); } catch { /* ignoto */ }
  }

  mostra(stato) {
    const voce = STATI[stato] || STATI['inattivo'];
    if (this.stato === stato) return;
    const primo = this.stato === null;
    this.stato = stato;

    if (this.sheets.reactions) {
      this.host.style.backgroundPosition =
        `${(voce.cella % 3) * 50}% ${Math.floor(voce.cella / 3) * 50}%`;
    } else {
      this.host.innerHTML = disegna(voce.nome);
    }

    // Il movimento e' un di piu' e si toglie per primo: `prefers-reduced-motion`
    // non e' una preferenza estetica.
    const fermo = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!primo && !fermo && this.host.animate) {
      this.host.animate(
        [{ transform: 'scale(1,1)' }, { transform: 'scale(1.08,0.94)', offset: 0.35 },
         { transform: 'scale(1,1)' }],
        { duration: 320, easing: 'ease-in-out' });
    }
  }
}

/** Deriva lo stato della factory dal payload di `/api/state`. Nessuna nuova verita':
 *  ogni ramo corrisponde a un'informazione gia' resa in forma testuale nella vista. */
export function statoDa(payload) {
  const turno = payload.turn || {};
  if (turno.phase === 'errore') return 'errore';
  if (turno.phase === 'attesa-risposta') return 'attesa-risposta';
  if (turno.phase === 'in-lavorazione') return 'in-lavorazione';
  if (payload.concorrenza && payload.concorrenza.altre_sessioni > 0) return 'concorrenza';
  if ((payload.panels || []).some((p) => !p.observable)) return 'non-osservabile';
  if ((payload.panels || []).some((p) => p.readings.some((r) => r.stale))) return 'stantio';
  if (payload.scrittura && !payload.scrittura.scrittura_disponibile) return 'scrittura-off';
  if (turno.phase === 'concluso') return 'concluso';
  return 'inattivo';
}
