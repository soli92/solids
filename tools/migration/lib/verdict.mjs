// verdict.mjs — Verdetto fail-closed della verifica di migrazione. Puro, senza I/O.
//
// Il verdetto e' CALCOLO, non opinione: nessun giudizio LLM nel percorso pass/fail.
//
//   consolidated  <=> nessun gate rosso, nulla di non osservato, nulla da portare,
//                     nessun gate umano aperto, parity_ratio osservato >= soglia
//   reject        <=> almeno un gate bloccante rosso (o parity_ratio < soglia)
//   conditional   altrimenti (lavoro residuo, osservazioni mancanti, gate umani aperti)
//
// Un'osservazione mancante non e' mai un verde: tiene il verdetto a `conditional`.
// `reject` e i file `divergent`/`ambiguous` producono gate umani in forma JSON
// ({gate, action, payload}): l'agente si ferma, l'umano decide.

import { blockingOpenFor } from './debt.mjs';

const order = (list) => new Map((list ?? []).map((k, i) => [k, i]));

function debtGate(debt, keys) {
  if (!debt?.observable) return { state: 'missing', why: debt?.reason ?? 'registro dei debiti non osservato' };
  const hits = [...new Set(keys)].flatMap((k) => blockingOpenFor(debt.entries, k));
  return hits.length
    ? { state: 'fail', why: `debito bloccante aperto: ${[...new Set(hits.map((h) => h.id))].join(', ')}` }
    : { state: 'pass' };
}

function modeGate(census, file) {
  if (!census) return { state: 'missing', why: 'asse C non eseguito' };
  if (census.applicable === false) return { state: 'n/a' };
  if (!census.observable) return { state: 'missing', why: `asse C non osservabile: ${census.reason}` };
  const e = census.entries.find((x) => x.file === file);
  if (!e) return { state: 'n/a' };
  if (e.severity === 'error' || e.severity === 'risk') return { state: 'fail', why: `modalita' ${e.status ?? e.severity}` };
  if (e.severity === 'dirty' || e.severity === 'legacy') return { state: 'partial', why: `modalita' ${e.status ?? e.severity}` };
  return { state: 'pass' };
}

function parityGate(parity, a, b) {
  if (!parity) return { state: 'missing', why: 'nessun esito di parita\' funzionale fornito' };
  const r = parity[b] ?? parity[a];
  if (!r) return { state: 'missing', why: 'file senza esito di parita\'' };
  if (r.a !== 'pass') return { state: 'fail', why: `oracolo non verde (${r.a}): la verifica stessa non e' valida` };
  if (r.b !== 'pass') return { state: 'fail', why: `target ${r.b} dove l'oracolo e' pass: regressione` };
  return { state: 'pass' };
}

function rowVerdict(gates, base) {
  const states = Object.values(gates).map((g) => g.state);
  if (states.includes('fail')) return 'reject';
  if (base === 'gated') return 'gated';
  if (base === 'conditional' || states.includes('missing') || states.includes('partial')) return 'conditional';
  return 'consolidated';
}

/**
 * @param {Object} o
 * @param {object} o.matrix   derivation-matrix (asse D)
 * @param {object} [o.mapA]   import-map dell'oracolo (ordine bottom-up dei file da portare)
 * @param {object} [o.mapB]   import-map del target (ordine bottom-up)
 * @param {object} [o.census] mode-census del target (asse C)
 * @param {object} [o.debt]   esito di readDebtRegistry
 * @param {Record<string,{a:string,b:string}>|null} [o.parity]  esiti per file (chiave: relKey B o A)
 * @param {number} [o.threshold] soglia di parity_ratio (default 0.95)
 */
export function computeVerdict({ matrix, mapA = null, mapB = null, census = null, debt = null, parity = null, threshold = 0.95 }) {
  const ordA = order(mapA?.bottomUpOrder);
  const ordB = order(mapB?.bottomUpOrder);
  const pairByB = new Map((matrix.pairs ?? []).map((p) => [p.b, p]));
  const divergent = new Set(matrix.partition.divergent);
  const rows = [];

  for (const a of matrix.partition.onlyInA) {
    const gates = { debt: debtGate(debt, [a]), mode: { state: 'n/a' }, parity: { state: 'n/a' } };
    rows.push({ file: a, side: 'oracle', partition: 'onlyInA', route: 'PORTING', gates, verdict: rowVerdict(gates, 'conditional'), _o: ordA.get(a) ?? 1e9 });
  }
  for (const b of [...matrix.partition.inBoth, ...matrix.partition.divergent]) {
    const p = pairByB.get(b) ?? { a: b, b };
    const isDiv = divergent.has(b);
    const gates = { debt: debtGate(debt, [p.a, b]), mode: modeGate(census, b), parity: parityGate(parity, p.a, b) };
    rows.push({
      file: b,
      ...(p.a !== b ? { oracleFile: p.a } : {}),
      side: 'target',
      partition: isDiv ? 'divergent' : 'inBoth',
      route: isDiv ? 'HUMAN-GATE' : 'AUDIT',
      contentEqual: p.contentEqual ?? null,
      gates,
      verdict: rowVerdict(gates, isDiv ? 'gated' : null),
      _o: ordB.get(b) ?? 1e9,
    });
  }
  rows.sort((x, y) => x._o - y._o || (x.file < y.file ? -1 : 1));
  for (const r of rows) {
    r.reasons = Object.entries(r.gates).filter(([, g]) => g.why).map(([k, g]) => `${k}: ${g.why}`);
    if (r.route === 'PORTING') r.reasons.unshift('da portare dall\'oracolo');
    if (r.route === 'HUMAN-GATE') r.reasons.unshift('oracolo cambiato dopo il fork: decisione umana');
    delete r._o;
  }

  // KPI parity_ratio = target pass / oracolo pass, sulle coppie appaiate con esito.
  const paired = [...matrix.partition.inBoth, ...matrix.partition.divergent];
  let withResult = 0;
  let aPass = 0;
  let bothPass = 0;
  if (parity) {
    for (const b of paired) {
      const p = pairByB.get(b) ?? { a: b };
      const r = parity[b] ?? parity[p.a];
      if (!r) continue;
      withResult++;
      if (r.a === 'pass') {
        aPass++;
        if (r.b === 'pass') bothPass++;
      }
    }
  }
  const parityRatio = aPass > 0 ? bothPass / aPass : null;
  const kpi = {
    parity_ratio: parityRatio,
    threshold,
    observed: parityRatio !== null,
    coverage: paired.length ? withResult / paired.length : null,
    ...(parityRatio === null ? { reason: parity ? 'nessuna coppia con oracolo pass' : 'nessun esito di parita\' fornito' } : {}),
  };

  const global = [];
  if (matrix.driftStatus !== 'computed') global.push({ state: 'missing', why: 'punto di fork non fornito: la deriva dell\'oracolo non e\' osservata' });
  if ((matrix.ambiguous ?? []).length) global.push({ state: 'gated', why: `${matrix.ambiguous.length} basename ambigui non appaiati` });
  if (kpi.observed && parityRatio < threshold) global.push({ state: 'fail', why: `parity_ratio ${parityRatio.toFixed(3)} < soglia ${threshold}` });
  if (!kpi.observed) global.push({ state: 'missing', why: `parity_ratio non osservato (${kpi.reason})` });
  if (debt && !debt.observable) global.push({ state: 'missing', why: debt.reason });

  const count = (v) => rows.filter((r) => r.verdict === v).length;
  let verdict;
  if (count('reject') || global.some((g) => g.state === 'fail')) verdict = 'reject';
  else if (count('consolidated') === rows.length && rows.length > 0 && global.length === 0) verdict = 'consolidated';
  else verdict = 'conditional';

  const gates = [];
  const base = { oracle: matrix.repos?.a ?? null, target: matrix.repos?.b ?? null };
  if (verdict === 'reject') {
    gates.push({
      gate: 'migration-verdict-reject',
      action: 'decisione-umana: correggere (attuatore) o accettare il debito con motivazione',
      payload: {
        ...base,
        files: rows.filter((r) => r.verdict === 'reject').map((r) => ({ file: r.file, reasons: r.reasons })),
        global: global.filter((g) => g.state === 'fail').map((g) => g.why),
      },
    });
  }
  const div = rows.filter((r) => r.route === 'HUMAN-GATE');
  if (div.length) {
    gates.push({
      gate: 'migration-divergent',
      action: 'decidere per ogni file: riportare la modifica dell\'oracolo nel target, o dichiararla non applicabile',
      payload: { ...base, forkPoint: matrix.forkPoint, files: div.map((r) => r.oracleFile ?? r.file) },
    });
  }
  if ((matrix.ambiguous ?? []).length) {
    gates.push({
      gate: 'migration-ambiguous-pairing',
      action: 'appaiare a mano i candidati (nessun accoppiamento e\' stato inventato)',
      payload: { ...base, ambiguous: matrix.ambiguous },
    });
  }

  return {
    verdict,
    files: rows,
    onlyInB: matrix.partition.onlyInB,
    global: global.map((g) => ({ state: g.state, reason: g.why })),
    kpi,
    gates,
    summary: {
      files: rows.length,
      consolidated: count('consolidated'),
      conditional: count('conditional'),
      reject: count('reject'),
      gated: count('gated'),
      porting: rows.filter((r) => r.route === 'PORTING').length,
      onlyInB: matrix.partition.onlyInB.length,
    },
  };
}

/** Exit code della CLI per verdetto. 2 resta riservato agli errori d'ingresso. */
export const EXIT = Object.freeze({ consolidated: 0, conditional: 1, reject: 3 });
