// Plancia — resa dello stato (EP-067). Nessuna dipendenza, nessun passo di build.
//
// Tre regole che il resto del file rispetta ovunque:
//   1. `available: false` NON diventa mai 0. Diventa «non osservabile» + la ragione.
//   2. Le etichette arrivano dal server, mai dal frontend. Chi produce una misura sa
//      come si chiama; chi la disegna no — e infatti la pagina ha mostrato per un po'
//      `events.by_state` a esseri umani.
//   3. Ogni transizione di stato passa da annuncia(), che scrive in una regione live
//      senza spostare il focus, e annuncia solo i CAMBIAMENTI.

'use strict';

import { Mascotte, statoDa, STATI } from '/mascotte.js';

const INTERVALLO_MS = 5000;
let ultimaFase = null;
let ultimeAssenti = '';
let ultimaDomanda = null;
let inSospeso = null;
let mascotte = null;

const $ = (id) => document.getElementById(id);

function elemento(tag, testo, classe) {
  const el = document.createElement(tag);
  if (testo !== undefined && testo !== null) el.textContent = String(testo);
  if (classe) el.className = classe;
  return el;
}

function eta(secondi) {
  if (secondi === null || secondi === undefined) return 'mai';
  if (secondi < 60) return `${Math.round(secondi)} s fa`;
  if (secondi < 3600) return `${Math.round(secondi / 60)} min fa`;
  return `${Math.round(secondi / 3600)} h fa`;
}

function annuncia(messaggio) {
  const regione = $('annuncio');
  if (regione.textContent !== messaggio) regione.textContent = messaggio;
}

async function chiama(percorso, corpo) {
  const risposta = await fetch(percorso, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo),
  });
  return { codice: risposta.status, esito: await risposta.json() };
}

// ── Testata ────────────────────────────────────────────────────────────

function renderTestata(payload) {
  // La frase di stato e' scritta SEMPRE, prima del ramo che decide se disegnare la
  // mascotte: se stesse dopo, spegnere la mascotte spegnerebbe anche l'informazione.
  const chiave = statoDa(payload);
  $('stato-frase').textContent = STATI[chiave].testo;

  const host = $('mascotte');
  const accesa = Mascotte.attiva();
  host.hidden = !accesa;
  if (accesa) {
    if (!mascotte) mascotte = new Mascotte(host);
    mascotte.mostra(chiave);
  }

  const id = payload.identity;
  const dl = $('identita');
  dl.replaceChildren();
  const voci = [
    ['Plancia', `v${id.plancia_version}`],
    ['Pattern factory', id.pattern_version + (id.pattern_version_drift ? ' — divergente' : '')],
    ['Dati', id.read_only ? 'sola lettura' : 'scrittura'],
    ['Aggiornamento', `ogni ${INTERVALLO_MS / 1000} s`],
  ];
  for (const [nome, valore] of voci) {
    const riga = document.createElement('div');
    riga.append(elemento('dt', nome), elemento('dd', valore));
    dl.append(riga);
  }
}

// ── Turno ──────────────────────────────────────────────────────────────

function renderTurno(turno, attesa) {
  const box = $('turno');
  box.replaceChildren();

  if (turno.phase === 'inattivo') {
    box.append(elemento('p', 'Nessun turno in corso.', 'attesa'));
  } else {
    box.append(elemento('p', STATI[statoDa({ turn: turno, panels: [] })]?.testo || turno.phase, 'valore'));

    if (turno.question) box.append(elemento('p', `Domanda: ${turno.question}`));
    if (turno.acknowledgment) box.append(elemento('p', turno.acknowledgment));

    // Gli adapter non-streaming non emettono avanzamenti: fra l'acknowledgment e la fine non arriva
    // alcun `Progress`. La plancia non puo' inventare un avanzamento che non le e' stato
    // comunicato, ma puo' dire da quanto attende e quanto manca — e «immobile» era
    // indistinguibile da «rotta».
    if (attesa) {
      const rimane = attesa.scade_fra_secondi;
      box.append(elemento('p',
        `In attesa da ${Math.round(attesa.da_secondi)} s — scade fra ${rimane} s.`,
        rimane < 30 ? 'ragione' : 'eta'));
      const barra = document.createElement('progress');
      barra.max = attesa.da_secondi + rimane;
      barra.value = attesa.da_secondi;
      barra.setAttribute('aria-label', `attesa del runtime, ${rimane} secondi alla scadenza`);
      box.append(barra);

      // Il dettaglio viene dal transcript della sessione figlia, non dal contratto: il
      // adapter non fa streaming e fra l'acknowledgment e la fine non arriva nulla.
      // Senza questo la sezione resta su una riga sola per minuti.
      const azioni = attesa.attivita || [];
      if (azioni.length) {
        box.append(elemento('p', `Sta facendo — ${azioni.length} azioni finora`, 'etichetta'));
        const lista = document.createElement('ol');
        lista.className = 'azioni-turno';
        lista.setAttribute('aria-label', 'azioni della sessione che esegue la direttiva');
        for (const azione of azioni) {
          const voce = document.createElement('li');
          voce.append(elemento('span', azione.strumento, 'strumento'));
          if (azione.su) voce.append(elemento('span', azione.su));
          lista.append(voce);
        }
        box.append(lista);
      } else {
        box.append(elemento('p',
          'Nessuna azione ancora visibile: la sessione che esegue la direttiva non ha ' +
          'ancora scritto nel proprio transcript.', 'eta'));
      }
    }

    if (turno.progress) {
      const barra = document.createElement('progress');
      if (!turno.progress.indeterminate) { barra.max = 1; barra.value = turno.progress.pct; }
      barra.setAttribute('aria-label', turno.progress.text || 'avanzamento');
      box.append(elemento('p', turno.progress.text || 'in corso'), barra);
    }
    if (turno.summary) box.append(elemento('p', turno.summary));
    if (turno.error) box.append(elemento('p', `Errore: ${turno.error}`, 'ragione'));
    if (turno.artifact_count) {
      box.append(elemento('p',
        `${turno.artifact_count} artefatto/i — resi solo qui, mai pronunciati.`, 'eta'));
    }
  }

  // Il modulo NON dipende da `turno.question`: nessuno dei sei adapter emette mai quel
  // tipo, e una domanda dell'agente («Palla a te: approvi Wave 1?») arriva dentro la
  // sintesi, con il turno che si chiude normalmente. Legare il modulo al `Question`
  // mandava la domanda in un vicolo cieco.
  const modulo = $('risposta');
  const concluso = turno.phase === 'concluso' || turno.phase === 'errore';
  modulo.hidden = !(turno.question || concluso);
  $('risposta-etichetta').textContent = turno.question
    ? 'Risposta alla domanda della factory'
    : 'Rispondi o prosegui la conversazione';

  // Il focus va sul campo solo per un `Question` esplicito, e solo alla PRIMA comparsa:
  // strapparlo a ogni ciclo a chi sta scrivendo sarebbe peggio che non darlo. Su un turno
  // concluso non si prende il focus — la conversazione la riprende l'utente quando vuole.
  if (turno.question && turno.question !== ultimaDomanda) {
    ultimaDomanda = turno.question;
    $('risposta-testo').focus();
  }
  if (!turno.question) ultimaDomanda = null;

  if (turno.phase !== ultimaFase) {
    ultimaFase = turno.phase;
    annuncia(turno.phase === 'attesa-risposta'
      ? `La factory attende una tua risposta. ${turno.question || ''}`
      : `Stato della factory: ${turno.phase}.`);
  }
}

// ── Comandi ────────────────────────────────────────────────────────────

function mostraConferma(azione, esito) {
  inSospeso = azione;
  $('conferma-testo').textContent = esito.conseguenza;
  $('conferma').hidden = false;
  $('conferma-si').focus();
  annuncia(`Serve una conferma. ${esito.conseguenza}`);
}

function nascondiConferma() {
  inSospeso = null;
  $('conferma').hidden = true;
}

async function esegui(azione, conferma) {
  const { codice, esito } = await chiama('/api/invia', { testo: azione.direttiva, conferma });
  if (esito.stato === 'conferma-richiesta') return mostraConferma(azione, esito);
  nascondiConferma();
  const messaggi = {
    'avviato': `Avviato: ${azione.nome}.`,
    'non-disponibile': `Comandi non disponibili: ${esito.ragione}`,
    'occupato': `Un turno è già in corso: ${esito.ragione}`,
  };
  annuncia(messaggi[esito.stato] || `Esito ${codice}: ${esito.stato}`);
  aggiorna();
}

function renderComandi(scrittura, concorrenza) {
  const nota = $('scrittura-stato');
  nota.className = 'sezione-nota';
  nota.textContent = scrittura.scrittura_disponibile
    ? (scrittura.turno_in_corso
        ? `Turno ${scrittura.turno_in_corso.id} in corso. I comandi tornano disponibili alla fine.`
        : 'Runtime raggiungibile. Ogni comando passa dalla sessione: la plancia non scrive.')
    : `Comandi non disponibili — ${scrittura.ragione_indisponibile}`;

  const contenitore = $('azioni');
  contenitore.replaceChildren();
  for (const azione of scrittura.azioni) {
    const b = document.createElement('button');
    b.type = 'button';
    b.append(elemento('span', azione.nome));
    if (azione.difficile_da_annullare) b.append(elemento('span', 'conferma', 'pastiglia'));
    b.setAttribute('aria-label', `${azione.nome}: ${azione.descrizione}` +
      (azione.difficile_da_annullare ? '. Richiede conferma esplicita' : ''));
    b.title = azione.descrizione;
    b.disabled = !scrittura.scrittura_disponibile || !!scrittura.turno_in_corso;
    b.addEventListener('click', () => esegui(azione, false));
    contenitore.append(b);
  }

  const avviso = $('concorrenza');
  if (concorrenza && concorrenza.avvertenza) {
    avviso.textContent = `${concorrenza.avvertenza} Osservato ${eta(concorrenza.eta_osservazione_s)}.`;
    avviso.hidden = false;
  } else {
    avviso.hidden = true;
  }
}

// Etichetta STATICA + `aria-pressed` + una pastiglia che dice lo stato a chi vede.
// Cambiare etichetta e `aria-pressed` insieme e' un antipattern noto: lo screen reader
// legge «Disattiva il canale vocale, premuto» e chi ascolta non sa piu' se e' acceso.
function interruttore(elementoBottone, etichetta, acceso, parolaOn, parolaOff) {
  // La pastiglia e' `aria-hidden`: lo stato lo dice gia' `aria-pressed`, e lasciarla
  // leggere produceva il nome accessibile «Canale vocalespento» — due informazioni
  // attaccate, una delle quali gia' ridondante. Per chi vede resta, perche' `aria-pressed`
  // non si vede.
  const pastiglia = elemento('span', acceso ? parolaOn : parolaOff, 'pastiglia');
  pastiglia.setAttribute('aria-hidden', 'true');
  elementoBottone.replaceChildren(elemento('span', etichetta), pastiglia);
  elementoBottone.setAttribute('aria-pressed', String(acceso));
}

function renderVoce(voce) {
  const b = $('voce-toggle');
  interruttore(b, 'Canale vocale', voce.attivo, 'attivo', 'spento');
  b.disabled = !voce.disponibile && !voce.attivo;

  const nota = $('voce-stato');
  if (!voce.disponibile && !voce.attivo) {
    nota.className = 'sezione-nota ragione';
    nota.textContent = `Canale vocale non disponibile — ${voce.ragione}`;
  } else if (voce.attivo) {
    nota.className = 'sezione-nota';
    nota.textContent = `Voce ${voce.voce} · ${voce.pronunciati} frasi pronunciate · ` +
      `${voce.artefatti_non_pronunciati} artefatti non pronunciati (mai, per contratto).`;
  } else {
    nota.className = 'sezione-nota';
    nota.textContent = 'Il canale vocale legge la stessa sequenza dello schermo. Gli artefatti non vengono mai pronunciati.';
  }
}

// ── Fonti ──────────────────────────────────────────────────────────────

function renderValore(lettura) {
  const valore = lettura.value;

  if (Array.isArray(valore) && valore.length && typeof valore[0] === 'object') {
    const frammento = document.createDocumentFragment();
    // Il singolare lo dichiara il server, come il «vuoto»: dedurlo da `unit` al plurale
    // produceva «1 avvisi».
    const unita = valore.length === 1 && lettura.detail && lettura.detail.singolare
      ? lettura.detail.singolare : (lettura.unit || 'voci');
    frammento.append(elemento('p', `${valore.length} ${unita}`, 'valore'));
    const tabella = document.createElement('table');
    const colonne = Object.keys(valore[0]);
    const testa = document.createElement('thead');
    const riga = document.createElement('tr');
    colonne.forEach((c) => riga.append(elemento('th', c)));
    testa.append(riga);
    tabella.append(testa);
    const corpo = document.createElement('tbody');
    // Il taglio a 8 righe e' il default; una misura che va letta per intero lo dichiara
    // (`detail.righe: null`). Deciderlo qui nasconderebbe in silenzio meta' di un report.
    const limite = lettura.detail && 'righe' in lettura.detail ? lettura.detail.righe : 8;
    valore.slice(0, limite ?? valore.length).forEach((voce) => {
      const tr = document.createElement('tr');
      colonne.forEach((c) => tr.append(elemento('td', voce[c] ?? '—')));
      corpo.append(tr);
    });
    tabella.append(corpo);
    const scorrevole = elemento('div', null,
      valore.length > 8 && limite === null ? 'scorrevole lunga' : 'scorrevole');
    scorrevole.setAttribute('tabindex', '0');     // scorribile da tastiera (2.1.1)
    scorrevole.setAttribute('role', 'region');
    scorrevole.setAttribute('aria-label', `dettaglio: ${lettura.label}`);
    scorrevole.append(tabella);
    frammento.append(scorrevole);
    return frammento;
  }

  if (valore && typeof valore === 'object' && !Array.isArray(valore)) {
    const dl = elemento('dl', null, 'coppie');
    for (const [k, v] of Object.entries(valore)) {
      const riga = document.createElement('div');
      riga.append(elemento('dt', k), elemento('dd', v));
      dl.append(riga);
    }
    return dl;
  }

  if (Array.isArray(valore)) {
    // Il testo del «vuoto» arriva dal server con l'accordo giusto. Comporlo qui da
    // `unit` al plurale produceva «nessuna sessioni».
    return elemento('p', valore.length ? valore.join(', ')
                                       : (lettura.vuoto || 'nessun elemento'), 'valore');
  }
  // Un collegamento lo dichiara il server (`detail.href`), mai il frontend: chi produce
  // la misura sa dove sta la sua vista completa.
  if (lettura.detail && lettura.detail.href) {
    const p = elemento('p', null, 'valore');
    const a = elemento('a', valore);
    a.href = lettura.detail.href;
    a.target = '_blank';
    a.rel = 'noopener';
    a.append(elemento('span', ' (si apre in una nuova scheda)', 'solo-lettori'));
    p.append(a);
    return p;
  }
  if (valore === null || valore === undefined) return elemento('p', '—', 'valore');
  if (typeof valore === 'number') {
    const n = Number.isInteger(valore) ? valore : valore.toFixed(2);
    return elemento('p', `${n}${lettura.unit ? ' ' + lettura.unit : ''}`, 'valore');
  }
  return elemento('p', `${valore}${lettura.unit ? ' ' + lettura.unit : ''}`, 'valore');
}

function renderLettura(lettura, etaRiquadro) {
  const blocco = elemento('div', null, 'lettura');
  blocco.append(elemento('p', lettura.label, 'etichetta'));

  if (!lettura.available) {
    blocco.append(elemento('p', 'non osservabile', 'valore'));
    blocco.append(elemento('p', lettura.reason || 'ragione non dichiarata', 'ragione'));
    return blocco;
  }

  blocco.append(renderValore(lettura));

  // DUE ETA' DIVERSE, e confonderle era il difetto: «letto 0 s fa» su un event store
  // fermo da due giorni e' vero e inutile. L'eta' della LETTURA sta una volta sola
  // nell'intestazione del riquadro; qui compare l'eta' del DATO, che e' l'unica che
  // dice se cio' che vedi e' ancora vero.
  const note = [];
  if (lettura.data_age_seconds !== null && lettura.data_age_seconds !== undefined
      && lettura.data_age_seconds > 90) {
    note.push(`dato di ${eta(lettura.data_age_seconds)}`);
  }
  const scarto = Math.abs(lettura.age_seconds - etaRiquadro);
  if (lettura.stale || scarto > 3) note.push(`letto ${eta(lettura.age_seconds)}`);
  if (lettura.stale) note.push('lettura stantia');
  if (note.length) blocco.append(elemento('p', note.join(' · '), 'eta'));
  return blocco;
}

function renderFonti(pannelli) {
  const contenitore = $('riquadri');
  contenitore.replaceChildren();
  const assenti = [];

  for (const pannello of pannelli) {
    const sezione = document.createElement('article');
    sezione.className = 'riquadro';
    sezione.setAttribute('aria-labelledby', `titolo-${pannello.key}`);

    const testa = elemento('div', null, 'riquadro-testa');
    const titolo = elemento('h3', pannello.titolo || pannello.key);
    titolo.id = `titolo-${pannello.key}`;
    const stantio = pannello.readings.some((r) => r.stale);
    const [classe, parola] = pannello.observable
      ? (stantio ? ['stantio', 'dato stantio'] : ['ok', 'osservabile'])
      : ['assente', 'non osservabile'];
    testa.append(titolo, elemento('span', parola, `marcatore ${classe}`));
    sezione.append(testa);
    if (pannello.descrizione) sezione.append(elemento('p', pannello.descrizione, 'riquadro-nota'));

    if (!pannello.observable) assenti.push(pannello.titolo || pannello.key);
    const etaRiquadro = Math.min(...pannello.readings.map((r) => r.age_seconds));
    if (pannello.observable) {
      testa.append(elemento('span', `letto ${eta(etaRiquadro)}`, 'eta'));
    }
    pannello.readings.forEach((l) => sezione.append(renderLettura(l, etaRiquadro)));
    sezione.append(elemento('p', `Fonte: ${pannello.source}`, 'fonte'));
    contenitore.append(sezione);
  }

  const firma = assenti.slice().sort().join(',');
  if (firma !== ultimeAssenti) {
    ultimeAssenti = firma;
    if (assenti.length) annuncia(`Fonti non osservabili: ${assenti.join(', ')}.`);
  }
}

// ── Ciclo ──────────────────────────────────────────────────────────────

async function aggiorna() {
  try {
    const risposta = await fetch('/api/state', { cache: 'no-store' });
    if (!risposta.ok) throw new Error(`il servizio ha risposto ${risposta.status}`);
    const stato = await risposta.json();
    renderTestata(stato);
    renderTurno(stato.turn, stato.scrittura.turno_in_corso);
    renderComandi(stato.scrittura, stato.concorrenza);
    renderVoce(stato.voce);
    renderFonti(stato.panels);
    $('aggiornamento').textContent =
      `Ultima lettura ${new Date(stato.observed_at).toLocaleTimeString('it-IT')}`;
  } catch (problema) {
    // Distinguere «il servizio non risponde» da «la resa e' rotta»: due guasti diversi
    // con due rimedi diversi. Un catch che li chiama entrambi «non raggiungibile» manda
    // a controllare la rete mentre il difetto e' nel codice — e' successo davvero.
    const rete = problema instanceof TypeError && /fetch|network|failed/i.test(problema.message);
    const diagnosi = (rete || problema.name === 'AbortError')
      ? `Plancia non raggiungibile: ${problema.message}`
      : `Errore nella resa della vista: ${problema.name}: ${problema.message}`;
    $('aggiornamento').textContent = diagnosi;
    annuncia(diagnosi);
    console.error('[plancia]', problema);
  }
}

// ── Comandi dell'interfaccia ───────────────────────────────────────────

$('conferma-si').addEventListener('click', () => inSospeso && esegui(inSospeso, true));
$('conferma-no').addEventListener('click', () => {
  nascondiConferma();
  annuncia('Azione annullata.');
});

$('risposta').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const campo = $('risposta-testo');
  if (!campo.value.trim()) return;
  const { esito } = await chiama('/api/rispondi', { testo: campo.value.trim() });
  campo.value = '';
  annuncia(esito.stato === 'avviato'
    ? 'Risposta inviata.'
    : `Risposta rifiutata: ${esito.ragione || esito.stato}`);
  aggiorna();
});

$('voce-toggle').addEventListener('click', async () => {
  // `evento.currentTarget` e' `null` dopo il primo `await`: la propagazione dell'evento
  // e' gia' finita quando la promessa si risolve. Il riferimento va preso PRIMA.
  const bottone = $('voce-toggle');
  const attiva = bottone.getAttribute('aria-pressed') !== 'true';
  bottone.disabled = true;
  const { esito } = await chiama('/api/voce', { attiva });
  bottone.disabled = false;
  renderVoce(esito);
  annuncia(esito.attivo
    ? 'Canale vocale attivo.'
    : (esito.disponibile ? 'Canale vocale disattivato.' : `Canale vocale non disponibile: ${esito.ragione}`));
});

$('mascotte-toggle').addEventListener('click', (evento) => {
  const accesa = !Mascotte.attiva();
  Mascotte.imposta(accesa);
  interruttore(evento.currentTarget, 'Mascotte', accesa, 'visibile', 'nascosta');
  // Si applica SUBITO, senza aspettare il prossimo `aggiorna()`. Prima l'effetto arrivava
  // solo col fetch successivo: lo stato della mascotte e' locale al browser e non ha
  // niente da chiedere al server, ma il codice lo trattava come se lo avesse. Con cinque
  // collettori quel fetch e' abbastanza lento da far sembrare il comando rotto — e un
  // comando che sembra rotto viene premuto due volte.
  $('mascotte').hidden = !accesa;
  annuncia(accesa ? 'Mascotte mostrata.' : 'Mascotte nascosta. Nessuna informazione è andata persa.');
  aggiorna();
});
interruttore($('mascotte-toggle'), 'Mascotte', Mascotte.attiva(), 'visibile', 'nascosta');

$('ricarica').addEventListener('click', aggiorna);

aggiorna();
setInterval(aggiorna, INTERVALLO_MS);
