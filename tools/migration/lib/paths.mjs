// paths.mjs — Guard read-only verso i repo analizzati + resolver/writer degli artefatti.
//
// Invariante: NESSUNA scrittura del tooling di migrazione puo' cadere dentro un repo
// analizzato. Ogni scrittura passa da un writer sanzionato (`guard.writeArtifact` /
// `guard.writeText`) che risolve il path sotto `<factoryRoot>/<artifactsHome>/<slug>/`
// e lo verifica prima di toccare il filesystem. Fail-closed: si lancia, non si ritorna.
//
// Rispetto all'originale della derivata, la radice vietata non e' piu' una costante
// (`code_repos/`): e' l'elenco dei repo passati all'analisi. I confronti avvengono sui
// path REALI (symlink risolti), cosi' un link nella directory degli artefatti che punta
// dentro un repo analizzato non apre una via di fuga.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ARTIFACT_FILES, ARTIFACT_KINDS } from './schema.mjs';

const LIB_DIR = path.dirname(fileURLToPath(import.meta.url));

/** Root della factory che ospita il tool: `tools/migration/lib/` -> 3 livelli su. */
export const FACTORY_ROOT = path.resolve(LIB_DIR, '..', '..', '..');

/** Directory degli artefatti di default, relativa alla root della factory. */
export const DEFAULT_ARTIFACTS_HOME = 'migration';

/** Violazione della guard. Fail-closed: si lancia, non si ritorna. */
export class ReadOnlyViolationError extends Error {
  constructor(message, target) {
    super(message);
    this.name = 'ReadOnlyViolationError';
    this.target = target;
  }
}

/**
 * Path reale di `p` anche se non esiste ancora: risolve il piu' vicino antenato
 * esistente con realpath e riattacca la coda. Serve a confrontare path con symlink
 * (macOS: /tmp -> /private/tmp) e a intercettare link che escono dalla radice.
 */
export function realish(p) {
  const abs = path.resolve(p);
  let head = abs;
  const tail = [];
  while (!fs.existsSync(head)) {
    const parent = path.dirname(head);
    if (parent === head) break;
    tail.unshift(path.basename(head));
    head = parent;
  }
  let real = head;
  try {
    real = fs.realpathSync.native(head);
  } catch {
    real = head;
  }
  return path.join(real, ...tail);
}

/** True se `child` e' dentro `parent` o coincide. */
export function isInsideOrEqual(childAbs, parentAbs) {
  const rel = path.relative(parentAbs, childAbs);
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel));
}

/** True se `child` e' strettamente dentro `parent`. */
function isStrictlyInside(childAbs, parentAbs) {
  const rel = path.relative(parentAbs, childAbs);
  return rel !== '' && !rel.startsWith('..') && !path.isAbsolute(rel);
}

/**
 * Slug di output sicuro: un solo segmento, niente traversal, separatori o NUL.
 * @param {string} slug
 */
export function sanitizeSlug(slug) {
  if (!slug || typeof slug !== 'string') throw new TypeError('slug mancante');
  const s = slug.trim();
  if (s === '' || s === '.' || s === '..' || /[\\/]/.test(s) || s.includes('\0')) {
    throw new ReadOnlyViolationError(`slug non valido (traversal/separatori): "${slug}"`, slug);
  }
  return s;
}

/**
 * Crea la guard per una sessione di analisi.
 *
 * @param {Object} opts
 * @param {string} [opts.factoryRoot]    root della factory (default: quella che ospita il tool).
 * @param {string} [opts.artifactsHome]  directory degli artefatti, relativa alla factory (default `migration`).
 * @param {string[]} [opts.analyzedRoots] repo analizzati: destinazioni VIETATE per ogni scrittura.
 * @returns guard
 * @throws {ReadOnlyViolationError} se la configurazione stessa e' insicura
 *         (artefatti fuori dalla factory, o dentro/sopra un repo analizzato).
 */
export function createGuard(opts = {}) {
  const factoryRoot = realish(opts.factoryRoot ?? FACTORY_ROOT);
  const home = opts.artifactsHome ?? DEFAULT_ARTIFACTS_HOME;
  if (typeof home !== 'string' || home.trim() === '') {
    throw new ReadOnlyViolationError('artifacts_home vuoto', home);
  }
  const artifactsRoot = realish(path.resolve(factoryRoot, home));
  const analyzedRoots = (opts.analyzedRoots ?? []).map((r) => realish(r));

  if (!isStrictlyInside(artifactsRoot, factoryRoot)) {
    throw new ReadOnlyViolationError(
      `artifacts_home deve stare dentro la factory (${factoryRoot}); risolto in ${artifactsRoot}`,
      artifactsRoot,
    );
  }
  for (const root of analyzedRoots) {
    if (isInsideOrEqual(artifactsRoot, root)) {
      throw new ReadOnlyViolationError(
        `artifacts_home (${artifactsRoot}) cade dentro un repo analizzato (${root}): ` +
          'gli artefatti vanno factory-side, mai nel repo che si legge. ' +
          'Se il repo analizzato e\' la factory stessa, analizzane una sottodirectory o un worktree.',
        artifactsRoot,
      );
    }
  }

  const label = (abs) => {
    const rel = path.relative(factoryRoot, abs);
    return rel.startsWith('..') ? abs : rel;
  };

  /** True se il candidato (risolto) cade dentro un repo analizzato. */
  function isForbidden(candidate) {
    const abs = realish(path.resolve(factoryRoot, candidate));
    return analyzedRoots.some((r) => isInsideOrEqual(abs, r));
  }

  /** GUARD 1 — vieta qualunque scrittura dentro un repo analizzato. */
  function assertNotInAnalyzed(candidate, ctx = {}) {
    if (typeof candidate !== 'string' || candidate.length === 0) {
      throw new TypeError('path di scrittura mancante o non stringa');
    }
    const abs = realish(path.resolve(factoryRoot, candidate));
    const hit = analyzedRoots.find((r) => isInsideOrEqual(abs, r));
    if (hit) {
      throw new ReadOnlyViolationError(
        `scrittura vietata dentro un repo analizzato (${ctx.op ?? 'write'} -> ${abs}; repo ${hit}). ` +
          'Il tooling di migrazione legge i repo in sola lettura; gli output vanno in artifacts_home.',
        abs,
      );
    }
    return abs;
  }

  /** GUARD 2 — un output ammesso sta dentro artifacts_home E fuori dai repo analizzati. */
  function assertWritableOutput(candidate, ctx = {}) {
    const abs = assertNotInAnalyzed(candidate, ctx);
    if (!isStrictlyInside(abs, artifactsRoot)) {
      throw new ReadOnlyViolationError(
        `output fuori dalla radice consentita ${label(artifactsRoot)} (${ctx.op ?? 'write'} -> ${label(abs)})`,
        abs,
      );
    }
    return abs;
  }

  /** Path canonico di un artefatto: `<artifactsRoot>/<slug>/<file>`. */
  function resolveOutputPath(slug, kind) {
    if (!ARTIFACT_KINDS.includes(kind)) {
      throw new TypeError(`tipo di artefatto non valido: ${kind} (attesi ${ARTIFACT_KINDS.join('|')})`);
    }
    const abs = path.join(artifactsRoot, sanitizeSlug(slug), ARTIFACT_FILES[kind]);
    return assertWritableOutput(abs, { op: `resolveOutput:${kind}` });
  }

  /** Path di un file libero (report .md) nella cartella dello slug. */
  function resolveSlugFile(slug, fileName) {
    const name = sanitizeSlug(fileName);
    return assertWritableOutput(path.join(artifactsRoot, sanitizeSlug(slug), name), { op: 'resolveSlugFile' });
  }

  /** L'unico punto che chiama fs.write*. */
  function guardedWriteFileSync(candidate, data, ctx = {}) {
    const abs = assertWritableOutput(candidate, ctx);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    // Ricontrollo dopo mkdir: una directory creata nel frattempo come symlink non deve passare.
    assertWritableOutput(abs, ctx);
    fs.writeFileSync(abs, data);
    return abs;
  }

  function writeArtifact(slug, kind, payload) {
    const abs = resolveOutputPath(slug, kind);
    return guardedWriteFileSync(abs, JSON.stringify(payload, null, 2) + '\n', { op: `writeArtifact:${kind}` });
  }

  function writeText(slug, fileName, text) {
    return guardedWriteFileSync(resolveSlugFile(slug, fileName), text, { op: 'writeText' });
  }

  return {
    factoryRoot,
    artifactsRoot,
    analyzedRoots,
    isForbidden,
    assertNotInAnalyzed,
    assertWritableOutput,
    resolveOutputPath,
    resolveSlugFile,
    guardedWriteFileSync,
    writeArtifact,
    writeText,
  };
}
