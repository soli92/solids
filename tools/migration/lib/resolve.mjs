// resolve.mjs — Risoluzione degli specifier di import verso file del repo analizzato.
//
// Condiviso dai plugin (js-ts, svelte): relativo + estensioni + index + alias da
// `compilerOptions.paths`/`baseUrl` di tsconfig/jsconfig (con `extends` relativi).
// Gli alias sono letti factory-side dal tsconfig del repo: nessuna dipendenza
// (`tsconfig-paths`) va installata nel repo analizzato.
//
// Esiti per specifier:
//   { kind: 'file', path }       risolto a un file esistente del repo
//   { kind: 'external', pkg }    specifier bare non coperto da alias: pacchetto esterno
//   { kind: 'unresolved' }       relativo o alias che non risolve: va DICHIARATO, mai taciuto

import fs from 'node:fs';
import path from 'node:path';
import { isFile } from './walk.mjs';

/** Rimuove commenti e virgole finali da un JSONC. */
export function parseJsonc(text) {
  const noComments = text.replace(/\\"|"(?:\\"|[^"])*"|(\/\/[^\n\r]*|\/\*[\s\S]*?\*\/)/g, (m, c) => (c ? ' ' : m));
  return JSON.parse(noComments.replace(/,(\s*[}\]])/g, '$1'));
}

/**
 * Legge `paths`/`baseUrl` da tsconfig.json/jsconfig.json della root (segue `extends` relativi).
 * @returns {{ baseUrl: string|null, paths: Record<string,string[]>, source: string }|null}
 */
export function readTsPaths(repoRoot, file = null, seen = new Set()) {
  const candidates = file ? [file] : ['tsconfig.json', 'jsconfig.json'].map((n) => path.join(repoRoot, n));
  for (const cfgFile of candidates) {
    if (seen.has(cfgFile) || !isFile(cfgFile)) continue;
    seen.add(cfgFile);
    let cfg;
    try {
      cfg = parseJsonc(fs.readFileSync(cfgFile, 'utf-8'));
    } catch {
      continue;
    }
    const dir = path.dirname(cfgFile);
    const co = cfg.compilerOptions ?? {};
    let inherited = null;
    const ext = typeof cfg.extends === 'string' ? [cfg.extends] : Array.isArray(cfg.extends) ? cfg.extends : [];
    for (const e of ext) {
      if (!e.startsWith('.')) continue; // extends da pacchetto: non seguito (limite dichiarato)
      const target = path.resolve(dir, e.endsWith('.json') ? e : `${e}.json`);
      inherited = readTsPaths(repoRoot, target, seen) ?? inherited;
    }
    const baseUrl = co.baseUrl != null ? path.resolve(dir, co.baseUrl) : inherited?.baseUrl ?? null;
    const paths = co.paths ?? inherited?.paths ?? null;
    if (paths || baseUrl) {
      // Semantica TS: senza baseUrl i `paths` sono relativi alla dir del tsconfig che li dichiara.
      const pathsBase = co.paths ? (co.baseUrl != null ? baseUrl : dir) : inherited?.pathsBase ?? baseUrl ?? dir;
      return { baseUrl, paths: paths ?? {}, pathsBase, source: path.relative(repoRoot, cfgFile) || cfgFile };
    }
  }
  return null;
}

const TS_SWAP = { '.js': ['.ts', '.tsx'], '.jsx': ['.tsx'], '.mjs': ['.mts'], '.cjs': ['.cts'] };

/**
 * Crea un resolver per un repo.
 * @param {string} repoRoot
 * @param {{ extensions: string[], extraAliases?: Record<string,string[]> }} opts
 *        extensions = estensioni provate per specifier senza estensione (ordine = priorita').
 */
export function createResolver(repoRoot, { extensions, extraAliases = {} }) {
  const root = path.resolve(repoRoot);
  const ts = readTsPaths(root);
  const aliases = { ...extraAliases, ...(ts?.paths ?? {}) };
  const aliasBase = ts?.pathsBase ?? root;
  const aliasSource = ts ? `tsconfig:${ts.source}` : Object.keys(extraAliases).length ? 'plugin-default' : 'relative-only';

  const tryFile = (candidate) => {
    if (isFile(candidate)) return candidate;
    const ext = path.extname(candidate);
    for (const alt of TS_SWAP[ext] ?? []) {
      const swapped = candidate.slice(0, -ext.length) + alt;
      if (isFile(swapped)) return swapped;
    }
    for (const e of extensions) if (isFile(candidate + e)) return candidate + e;
    for (const e of extensions) {
      const idx = path.join(candidate, `index${e}`);
      if (isFile(idx)) return idx;
    }
    return null;
  };

  const inside = (abs) => {
    const rel = path.relative(root, abs);
    return !rel.startsWith('..') && !path.isAbsolute(rel) && !rel.split(path.sep).includes('node_modules');
  };

  function matchAlias(spec) {
    for (const [pattern, targetsRaw] of Object.entries(aliases)) {
      const targets = Array.isArray(targetsRaw) ? targetsRaw : [targetsRaw];
      const star = pattern.indexOf('*');
      let captured = null;
      if (star === -1) {
        if (spec !== pattern) continue;
        captured = '';
      } else {
        const pre = pattern.slice(0, star);
        const suf = pattern.slice(star + 1);
        if (!(spec.startsWith(pre) && spec.endsWith(suf) && spec.length >= pre.length + suf.length)) continue;
        captured = spec.slice(pre.length, spec.length - suf.length);
      }
      for (const t of targets) {
        const hit = tryFile(path.resolve(aliasBase, String(t).replace('*', captured)));
        if (hit) return { matched: true, hit };
      }
      return { matched: true, hit: null };
    }
    return { matched: false, hit: null };
  }

  /**
   * @param {string} spec
   * @param {string} fromFile assoluto
   */
  function resolve(spec, fromFile) {
    if (spec.startsWith('.') || spec.startsWith('/')) {
      const base = spec.startsWith('/') ? path.join(root, spec) : path.resolve(path.dirname(fromFile), spec);
      const hit = tryFile(base);
      return hit && inside(hit) ? { kind: 'file', path: path.resolve(hit) } : { kind: 'unresolved' };
    }
    const alias = matchAlias(spec);
    if (alias.matched) {
      return alias.hit && inside(alias.hit) ? { kind: 'file', path: path.resolve(alias.hit) } : { kind: 'unresolved' };
    }
    if (ts?.baseUrl) {
      const hit = tryFile(path.resolve(ts.baseUrl, spec));
      if (hit && inside(hit)) return { kind: 'file', path: path.resolve(hit) };
    }
    const pkg = spec.startsWith('@') ? spec.split('/').slice(0, 2).join('/') : spec.split('/')[0];
    return { kind: 'external', pkg };
  }

  return { resolve, aliasSource, root };
}
