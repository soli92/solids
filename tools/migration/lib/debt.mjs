// debt.mjs — Registro dei debiti di migrazione (lettura e template).
//
// Il registro e' un markdown factory-side, versionato: accumula DECISIONI UMANE e quindi
// non e' rigenerabile. Il verdetto lo legge come gate d'ingresso: una voce `open` e
// `bloccante: si` che tocca un file impedisce il `consolidated` di quel file.
//
// Formato di una voce (i campi in grassetto sono quelli letti dal tool):
//
//   ## DEBT-001 — titolo breve
//   - **stato:** open            (open | in-analysis | resolved | wontfix)
//   - **bloccante:** si          (si | no)
//   - **categoria:** <libera>
//   - **file:** src/a.ts, src/b.ts
//   - **decisione:** —           (chi, quando, quale opzione: la chiusura e' umana)
//   - **verifica:** —            (comando o test che dimostra la chiusura)

import fs from 'node:fs';

export const DEBT_STATES = Object.freeze(['open', 'in-analysis', 'resolved', 'wontfix']);

const FIELD_RE = /^\s*[-*]\s+\*\*([a-zA-Z_À-ſ]+):\*\*\s*(.*)$/;

function yes(v) {
  return /^(s[iì]|yes|true|y)$/i.test(String(v).trim());
}

/**
 * Parsa il testo di un registro.
 * @param {string} text
 * @returns {{ entries: object[], problems: string[] }}
 */
export function parseDebtRegistry(text) {
  const entries = [];
  const problems = [];
  let cur = null;
  const push = () => {
    if (!cur) return;
    if (!DEBT_STATES.includes(cur.stato)) problems.push(`${cur.id}: stato non valido "${cur.stato ?? ''}"`);
    if (cur.bloccante === undefined) problems.push(`${cur.id}: campo bloccante mancante`);
    if (!cur.files.length) problems.push(`${cur.id}: campo file mancante`);
    entries.push(cur);
  };
  for (const line of text.split(/\r?\n/)) {
    const h = /^##\s+(DEBT-[A-Za-z0-9-]+)\s*(?:[—\-:]\s*(.*))?$/.exec(line);
    if (h) {
      push();
      cur = { id: h[1], title: (h[2] ?? '').trim(), stato: undefined, bloccante: undefined, files: [] };
      continue;
    }
    if (!cur) continue;
    const f = FIELD_RE.exec(line);
    if (!f) continue;
    const key = f[1].toLowerCase();
    const val = f[2].replace(/<!--.*?-->/g, '').trim();
    if (key === 'stato') cur.stato = val.split(/\s+/)[0].toLowerCase();
    else if (key === 'bloccante') cur.bloccante = yes(val.split(/\s+/)[0]);
    else if (key === 'file') cur.files = val.split(',').map((s) => s.trim().replace(/^`|`$/g, '')).filter(Boolean);
    else cur[key] = val;
  }
  push();
  return { entries, problems };
}

/**
 * Legge un registro da disco. Fail-closed: assente o malformato e' un esito esplicito.
 * @returns {{ observable: boolean, reason?: string, entries: object[], problems: string[] }}
 */
export function readDebtRegistry(file) {
  if (!file) return { observable: false, reason: 'nessun registro dei debiti dichiarato', entries: [], problems: [] };
  let text;
  try {
    text = fs.readFileSync(file, 'utf-8');
  } catch (e) {
    return { observable: false, reason: `registro dei debiti illeggibile (${e.code ?? e.message})`, entries: [], problems: [] };
  }
  const { entries, problems } = parseDebtRegistry(text);
  if (problems.length) {
    return { observable: false, reason: `registro dei debiti malformato: ${problems.slice(0, 3).join('; ')}`, entries, problems };
  }
  return { observable: true, entries, problems };
}

/** Voci bloccanti aperte che toccano `file`. `in-analysis` conta come aperta. */
export function blockingOpenFor(entries, file) {
  return entries.filter((e) => e.bloccante && (e.stato === 'open' || e.stato === 'in-analysis') && e.files.includes(file));
}

/** Template di un registro vuoto. */
export function debtTemplate({ oracle, target }) {
  return [
    '---',
    `oracolo: ${oracle}`,
    `target: ${target}`,
    'punto_di_fork: —   # input umano: commit o data dell\'oracolo da cui il target e\' derivato',
    `aggiornato: ${new Date().toISOString().slice(0, 10)}`,
    '---',
    '',
    '# Registro dei debiti di migrazione',
    '',
    'Una voce per debito. La chiusura richiede `decisione` E `verifica` compilate: nessuna',
    'voce si chiude per deduzione di un agente.',
    '',
    '<!-- esempio',
    '## DEBT-001 — titolo breve',
    '- **stato:** open',
    '- **bloccante:** si',
    '- **categoria:** comportamento-divergente',
    '- **file:** src/esempio.ts',
    '- **evidenza_oracolo:** cosa fa l\'oracolo',
    '- **effetto:** cosa cambia nel target',
    '- **decisione:** —',
    '- **verifica:** —',
    '-->',
    '',
  ].join('\n');
}
