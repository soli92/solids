// schema.mjs — Contratti JSON degli artefatti della verifica di migrazione.
//
// Contratto stabile fra i produttori (assi A/B/C/D, verdetto) e i consumer
// (agenti code-cartographer e migration-verifier, skill code-migration-protocol).
// Validatori leggeri, nessuna dipendenza esterna.
//
// CHIAVE DI JOIN: `file` = path relativo alla root del repo analizzato, in POSIX
// (`src/lib/Button.tsx`). Mai assoluto: non deterministico e rivela il layout della
// macchina. Il join fra assi avviene su questa chiave.
//
// Storia:
//   2.0.0 — generalizzazione dal tooling della derivata (schema 1.1.0 della derivata):
//           chiave `file` al posto di `component`, plugin di linguaggio dichiarato in meta,
//           asse B su `library` configurabile, asse C con `observable`, artefatto V (verdetto).

export const SCHEMA_VERSION = '2.0.0';

/** Tipi di artefatto e nome-file canonico. */
export const ARTIFACT_FILES = Object.freeze({
  A: 'import-map.json', // albero degli import
  B: 'library-usage.json', // superficie di una libreria consumata
  C: 'mode-census.json', // modalita' di compilazione (plugin)
  D: 'derivation-matrix.json', // matrice di derivazione oracolo <-> target
  V: 'verdict.json', // verdetto della verifica
});

export const ARTIFACT_KINDS = Object.freeze(Object.keys(ARTIFACT_FILES));

/** Partizioni dell'asse D. */
export const DERIVATION_BUCKETS = Object.freeze([
  'onlyInA', // ramo PORTING: esiste nell'oracolo, manca nel target
  'onlyInB', // nuovo nel target oppure orfano: verifica esplicita
  'inBoth', // ramo AUDIT
  'divergent', // presente in entrambi, ma l'oracolo e' cambiato dopo il fork: gate umano
]);

/** Strategie di join A<->B dell'asse D. */
export const JOIN_STRATEGIES = Object.freeze(['path', 'name']);

/**
 * Severita' normalizzate dell'asse C. Ogni plugin mappa i propri stati su queste:
 *   error  — non compila: blocca (reject)
 *   risk   — compila ma con rischio comportamentale noto: blocca (reject)
 *   dirty  — migrato con residui del modello precedente: conditional
 *   legacy — non ancora migrato: conditional
 *   clean  — migrato senza residui (NON certifica il comportamento)
 */
export const MODE_SEVERITIES = Object.freeze(['error', 'risk', 'dirty', 'legacy', 'clean']);

/** Verdetti. */
export const VERDICTS = Object.freeze(['consolidated', 'conditional', 'reject']);

/** Stato della sezione deriva dell'asse D. */
export const DRIFT_STATUS = Object.freeze({
  GATED: 'gated:fork-point-missing',
  COMPUTED: 'computed',
});

/**
 * Envelope comune.
 * @param {{kind: string, slug: string, repo?: {name?: string, role?: string}, plugins?: string[], extra?: object}} o
 */
export function makeMeta({ kind, slug, repo = {}, plugins = [], extra = {} }) {
  if (!ARTIFACT_KINDS.includes(kind)) throw new TypeError(`kind non valido: ${kind}`);
  if (!slug || typeof slug !== 'string') throw new TypeError('slug mancante');
  return {
    schemaVersion: SCHEMA_VERSION,
    kind,
    slug,
    repo: { name: repo.name ?? slug, ...(repo.role ? { role: repo.role } : {}) },
    plugins: [...plugins],
    generatedAt: new Date().toISOString(),
    node: process.version,
    scan: 'full-scan',
    ...extra,
  };
}

const REL_KEY_RE = /^(?!\/|[A-Za-z]:)(?!.*\\)(?!.*(?:^|\/)\.\.(?:\/|$)).+/;

/** True se `k` e' una chiave di join valida (POSIX, relativa, senza `..`). */
export function isValidRelKey(k) {
  return typeof k === 'string' && k.length > 0 && REL_KEY_RE.test(k);
}

function parseSemver(v) {
  const m = /^(\d+)\.(\d+)\.(\d+)/.exec(String(v ?? ''));
  return m ? { major: +m[1], minor: +m[2] } : null;
}

/** Stessa major, minor dell'artefatto <= minor corrente. */
export function isSchemaCompatible(version) {
  const a = parseSemver(version);
  const cur = parseSemver(SCHEMA_VERSION);
  return Boolean(a && cur && a.major === cur.major && a.minor <= cur.minor);
}

/**
 * Valida envelope e coerenza minima. Ritorna la lista dei problemi (vuota = valido).
 * @param {object} artifact
 * @returns {string[]}
 */
export function validateArtifact(artifact) {
  const errs = [];
  const m = artifact?.meta;
  if (!m) return ['meta mancante'];
  if (!isSchemaCompatible(m.schemaVersion)) {
    errs.push(`schemaVersion ${m.schemaVersion} incompatibile con ${SCHEMA_VERSION}`);
  }
  if (!ARTIFACT_KINDS.includes(m.kind)) errs.push(`kind non valido: ${m.kind}`);
  if (!m.slug) errs.push('slug mancante');

  const badKeys = (arr, field) => {
    if (arr !== undefined && !Array.isArray(arr)) {
      errs.push(`${field}: atteso array`);
      return;
    }
    (arr ?? []).forEach((k) => {
      if (!isValidRelKey(k)) errs.push(`${field}: relKey non valida "${k}"`);
    });
  };

  switch (m.kind) {
    case 'A':
      if (!Array.isArray(artifact.entries)) errs.push('entries mancante');
      (artifact.entries ?? []).forEach((e, i) => {
        if (!isValidRelKey(e.file)) errs.push(`entries[${i}].file non valida`);
        badKeys(e.imports, `entries[${i}].imports`);
        badKeys(e.usedBy, `entries[${i}].usedBy`);
        if (e.shared !== (Array.isArray(e.usedBy) && e.usedBy.length > 1)) {
          errs.push(`entries[${i}].shared incoerente con usedBy`);
        }
      });
      badKeys(artifact.bottomUpOrder, 'bottomUpOrder');
      badKeys(artifact.cycles, 'cycles');
      break;
    case 'B':
      if (!artifact.library) errs.push('library mancante');
      (artifact.components ?? []).forEach((c, i) => {
        if (!c.name) errs.push(`components[${i}].name mancante`);
        (c.consumers ?? []).forEach((cs, j) => {
          if (!isValidRelKey(cs.file)) errs.push(`components[${i}].consumers[${j}].file non valida`);
        });
      });
      (artifact.byFile ?? []).forEach((f, i) => {
        if (!isValidRelKey(f.file)) errs.push(`byFile[${i}].file non valida`);
      });
      break;
    case 'C':
      if (typeof artifact.observable !== 'boolean') errs.push('observable mancante (booleano)');
      if (artifact.observable === false && !artifact.reason) errs.push('observable:false senza reason');
      (artifact.entries ?? []).forEach((e, i) => {
        if (!isValidRelKey(e.file)) errs.push(`entries[${i}].file non valida`);
        if (!MODE_SEVERITIES.includes(e.severity)) errs.push(`entries[${i}].severity non valida: ${e.severity}`);
      });
      break;
    case 'D':
      for (const b of DERIVATION_BUCKETS) badKeys(artifact.partition?.[b], `partition.${b}`);
      if (!JOIN_STRATEGIES.includes(artifact.joinStrategy)) errs.push(`joinStrategy non valido: ${artifact.joinStrategy}`);
      (artifact.pairs ?? []).forEach((p, i) => {
        if (!isValidRelKey(p?.a)) errs.push(`pairs[${i}].a non valida`);
        if (!isValidRelKey(p?.b)) errs.push(`pairs[${i}].b non valida`);
      });
      (artifact.ambiguous ?? []).forEach((am, i) => {
        if (!am?.name) errs.push(`ambiguous[${i}].name mancante`);
        badKeys(am?.a, `ambiguous[${i}].a`);
        badKeys(am?.b, `ambiguous[${i}].b`);
      });
      if (!Object.values(DRIFT_STATUS).includes(artifact.driftStatus)) {
        errs.push(`driftStatus non valido: ${artifact.driftStatus}`);
      }
      break;
    case 'V':
      if (!VERDICTS.includes(artifact.verdict)) errs.push(`verdict non valido: ${artifact.verdict}`);
      (artifact.files ?? []).forEach((f, i) => {
        if (!isValidRelKey(f.file)) errs.push(`files[${i}].file non valida`);
        if (!VERDICTS.includes(f.verdict) && f.verdict !== 'gated') errs.push(`files[${i}].verdict non valido`);
      });
      break;
    default:
      break;
  }
  return errs;
}
