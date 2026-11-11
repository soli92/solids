// plugins.mjs — Registro e composizione dei plugin di linguaggio/framework.
//
// `--plugin=svelte,js-ts` compone piu' plugin: ogni file appartiene al plugin che ne
// dichiara l'estensione (il primo in elenco vince sui conflitti). L'insieme dei nodi del
// grafo e' l'unione delle estensioni.

import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createResolver } from './resolve.mjs';

const PLUGIN_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'plugins');

/** Plugin inclusi. Un plugin esterno si passa per path (`--plugin=./mio-plugin.mjs`). */
export const BUILTIN_PLUGINS = Object.freeze(['js-ts', 'svelte']);

/** Verifica l'interfaccia minima. Ritorna i problemi (vuoto = valido). */
export function validatePlugin(p) {
  const errs = [];
  if (!p || typeof p !== 'object') return ['plugin non e\' un oggetto'];
  if (typeof p.name !== 'string' || !p.name) errs.push('name mancante');
  if (!Array.isArray(p.extensions) || p.extensions.some((e) => typeof e !== 'string' || !e.startsWith('.'))) {
    errs.push('extensions deve essere un array di estensioni (".ext")');
  }
  if (typeof p.resolveImports !== 'function') errs.push('resolveImports(file, src, ctx) mancante');
  for (const opt of ['entryPoints', 'modeAudit', 'prepare', 'accept', 'usageExtras']) {
    if (p[opt] !== undefined && typeof p[opt] !== 'function') errs.push(`${opt} deve essere una funzione`);
  }
  return errs;
}

/**
 * Carica i plugin per nome (inclusi) o per path.
 * @param {string|string[]} spec es. "svelte,js-ts"
 */
export async function loadPlugins(spec) {
  const names = (Array.isArray(spec) ? spec : String(spec).split(','))
    .map((s) => s.trim())
    .filter(Boolean);
  if (!names.length) throw new Error('nessun plugin richiesto');
  const plugins = [];
  for (const n of names) {
    const url = BUILTIN_PLUGINS.includes(n)
      ? pathToFileURL(path.join(PLUGIN_DIR, `${n}.mjs`)).href
      : n.includes('/') || n.endsWith('.mjs')
        ? pathToFileURL(path.resolve(n)).href
        : null;
    if (!url) throw new Error(`plugin sconosciuto: ${n} (inclusi: ${BUILTIN_PLUGINS.join(', ')}; esterni: path a un .mjs)`);
    const mod = await import(url);
    const p = mod.default ?? mod;
    const errs = validatePlugin(p);
    if (errs.length) throw new Error(`plugin ${n} non conforme all'interfaccia: ${errs.join('; ')}`);
    plugins.push(p);
  }
  return plugins;
}

/**
 * Composizione dei plugin per un repo.
 * @param {object[]} plugins
 * @param {string} repoRoot
 */
export function composePlugins(plugins, repoRoot) {
  const extensions = [...new Set(plugins.flatMap((p) => p.extensions))];
  const owner = (abs) => {
    for (const p of plugins) {
      if (p.extensions.some((e) => abs.endsWith(e)) && (!p.accept || p.accept(abs))) return p;
    }
    return null;
  };
  let extraAliases = {};
  for (const p of plugins) {
    if (p.prepare) extraAliases = { ...extraAliases, ...(p.prepare(repoRoot)?.extraAliases ?? {}) };
  }
  // Le estensioni provate per specifier senza estensione includono sempre quelle JS/TS:
  // un .svelte che importa `./store` deve trovare `store.ts` anche se js-ts non e' caricato.
  const probe = [...new Set([...extensions, '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'])];
  const resolver = createResolver(repoRoot, { extensions: probe, extraAliases });
  return {
    names: plugins.map((p) => p.name),
    plugins,
    extensions,
    owner,
    accept: (abs) => owner(abs) !== null,
    ctx: { resolver, repoRoot },
    aliasSource: resolver.aliasSource,
  };
}
