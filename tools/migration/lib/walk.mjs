// walk.mjs — Camminata READ-ONLY dei sorgenti, chiave di join, hash del contenuto.
//
// Usa solo fs.readdir/stat/readFile. Nessuna scrittura: le scritture passano da paths.mjs.

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

/** Directory sempre escluse. */
export const EXCLUDED_DIRS = Object.freeze([
  'node_modules',
  'dist',
  'build',
  'out',
  'coverage',
  '.git',
  '.svelte-kit',
  '.astro',
  '.next',
  '.nuxt',
  '.turbo',
  '.cache',
  'storybook-static',
]);

/**
 * Chiave di join: path relativo alla root, POSIX.
 * @param {string} absFile
 * @param {string} rootDir
 */
export function relKey(absFile, rootDir) {
  return path.relative(path.resolve(rootDir), path.resolve(absFile)).split(path.sep).join('/');
}

/**
 * Cammina `rootDir` in sola lettura e ritorna i path assoluti dei file accettati.
 * @param {string} rootDir
 * @param {{ accept: (absFile: string) => boolean, exclude?: string[], excludeHidden?: boolean, ignore?: RegExp|null, relativeTo?: string }} opts
 * @returns {string[]} ordinati.
 */
export function walkSources(rootDir, opts) {
  const { accept, exclude = [], excludeHidden = true, ignore = null, relativeTo = rootDir } = opts;
  const excluded = new Set([...EXCLUDED_DIRS, ...exclude]);
  const out = [];
  const visit = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const ent of entries) {
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        if (excluded.has(ent.name)) continue;
        if (excludeHidden && ent.name.startsWith('.')) continue;
        visit(full);
      } else if (ent.isFile()) {
        if (ignore && ignore.test(relKey(full, relativeTo))) continue;
        if (accept(full)) out.push(path.resolve(full));
      }
    }
  };
  if (fs.existsSync(rootDir)) visit(path.resolve(rootDir));
  return out.sort();
}

/** Legge un file in UTF-8. '' se illeggibile. */
export function readSource(absFile) {
  try {
    return fs.readFileSync(absFile, 'utf-8');
  } catch {
    return '';
  }
}

/**
 * SHA-256 del contenuto con fine riga normalizzata (CRLF -> LF), cosi' lo stesso file
 * clonato su Windows e su Linux ha lo stesso hash. null se illeggibile.
 */
export function contentHash(absFile) {
  try {
    const text = fs.readFileSync(absFile, 'utf-8').replace(/\r\n/g, '\n');
    return crypto.createHash('sha256').update(text).digest('hex');
  } catch {
    return null;
  }
}

/** True se `p` esiste ed e' un file. */
export function isFile(p) {
  try {
    return fs.statSync(p).isFile();
  } catch {
    return false;
  }
}
