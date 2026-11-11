#!/usr/bin/env node
// map-architecture.mjs — Asse A: albero degli import di un repo.
//
//   node tools/migration/map-architecture.mjs <repo> [--slug <s>] [--plugin js-ts|svelte|a,b]
//        [--entry full|dir:<d1,d2>|plugin:<kind>] [--src <d1,d2>] [--ignore <regex>]
//        [--role oracle|target] [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]
//
// Produce <artifacts_home>/<slug>/import-map.json: per file importati, importatori,
// condivisi (usedBy > 1), profondita', ordine bottom-up (foglie -> radici), cicli,
// import NON risolti (dichiarati, mai taciuti), pacchetti esterni, hash del contenuto.
//
// SOLA LETTURA sul repo. L'unica scrittura e' l'artefatto, via guard.

import path from 'node:path';
import fs from 'node:fs';
import { createGuard, sanitizeSlug, FACTORY_ROOT } from './lib/paths.mjs';
import { makeMeta, validateArtifact } from './lib/schema.mjs';
import { walkSources, relKey, readSource, contentHash } from './lib/walk.mjs';
import { loadPlugins, composePlugins } from './lib/plugins.mjs';
import { analyzeGraph } from './lib/graph.mjs';
import { loadMigrationConfig, parseArgs, isMain } from './lib/config.mjs';

/**
 * Calcola l'asse A (nessuna scrittura).
 * @param {{ repo: string, slug?: string, plugins: object[], entry?: string, src?: string[], ignore?: string|null, role?: string }} o
 */
export function computeImportMap({ repo, slug, plugins, entry = 'full', src = [], ignore = null, role }) {
  const repoRoot = path.resolve(repo);
  if (!fs.existsSync(repoRoot) || !fs.statSync(repoRoot).isDirectory()) throw new Error(`repo inesistente: ${repoRoot}`);
  const theSlug = sanitizeSlug(slug ?? path.basename(repoRoot));
  const comp = composePlugins(plugins, repoRoot);
  const ignoreRe = ignore ? new RegExp(ignore) : null;

  const scanDirs = (src.length ? src : ['.']).map((d) => path.resolve(repoRoot, d));
  const missingDirs = scanDirs.filter((d) => !fs.existsSync(d));
  if (missingDirs.length === scanDirs.length) throw new Error(`nessuna directory sorgente esistente: ${missingDirs.join(', ')}`);
  const universe = new Set(
    scanDirs.flatMap((d) => walkSources(d, { accept: comp.accept, ignore: ignoreRe, relativeTo: repoRoot })),
  );

  // Entry point.
  let entryFiles = [];
  let entryMode = 'full';
  if (entry === 'full') {
    entryFiles = [...universe];
  } else if (entry.startsWith('dir:')) {
    entryMode = entry;
    const dirs = entry.slice(4).split(',').map((d) => path.resolve(repoRoot, d.trim()));
    entryFiles = dirs.flatMap((d) => walkSources(d, { accept: comp.accept, ignore: ignoreRe, relativeTo: repoRoot }));
  } else if (entry.startsWith('plugin:')) {
    entryMode = entry;
    const kind = entry.slice(7);
    const provider = plugins.find((p) => typeof p.entryPoints === 'function');
    if (!provider) throw new Error(`--entry ${entry}: nessun plugin caricato fornisce entryPoints()`);
    entryFiles = provider.entryPoints(repoRoot, kind).filter((f) => !ignoreRe || !ignoreRe.test(relKey(f, repoRoot)));
  } else {
    throw new Error(`--entry non valido: ${entry} (attesi full | dir:<d> | plugin:<kind>)`);
  }
  if (entry !== 'full' && entryFiles.length === 0) {
    throw new Error(`--entry ${entry}: nessun entry point trovato (non e' uno zero: e' un input sbagliato)`);
  }

  // Visita: in modalita' full tutti i file, altrimenti i raggiungibili dagli entry.
  const info = new Map(); // abs -> { imports:Set, unresolved:[], externals:[] }
  let edgesOutside = 0;
  const pending = [...entryFiles];
  while (pending.length) {
    const abs = pending.pop();
    if (info.has(abs)) continue;
    const owner = comp.owner(abs);
    const rec = { imports: new Set(), unresolved: [], externals: [] };
    info.set(abs, rec);
    if (!owner) continue;
    const r = owner.resolveImports(abs, readSource(abs), comp.ctx);
    rec.unresolved = r.unresolved ?? [];
    rec.externals = r.externals ?? [];
    for (const f of r.files ?? []) {
      if (!comp.accept(f) || (ignoreRe && ignoreRe.test(relKey(f, repoRoot)))) {
        edgesOutside++;
        continue;
      }
      rec.imports.add(f);
      if (!info.has(f)) pending.push(f);
    }
  }

  const rk = (abs) => relKey(abs, repoRoot);
  const nodes = [...info.keys()].map(rk).sort();
  const edges = new Map([...info.entries()].map(([abs, r]) => [rk(abs), [...r.imports].map(rk).sort()]));
  const g = analyzeGraph(nodes, edges, entryFiles.map(rk).sort());

  const entries = g.bottomUp.map((file) => {
    const abs = path.join(repoRoot, file);
    const r = info.get(abs) ?? info.get(path.resolve(abs));
    const usedBy = g.usedBy.get(file) ?? [];
    return {
      file,
      depth: g.depth.get(file),
      imports: edges.get(file) ?? [],
      usedBy,
      shared: usedBy.length > 1,
      plugin: comp.owner(abs)?.name ?? null,
      hash: contentHash(abs),
      unresolved: r?.unresolved ?? [],
    };
  });
  const externals = [...new Set([...info.values()].flatMap((r) => r.externals))].sort();
  const unresolvedCount = entries.reduce((n, e) => n + e.unresolved.length, 0);

  return {
    meta: makeMeta({
      kind: 'A',
      slug: theSlug,
      repo: { name: path.basename(repoRoot), role },
      plugins: comp.names,
      extra: { aliasSource: comp.aliasSource },
    }),
    entryPoint: { mode: entryMode, count: entryFiles.length, src: src.length ? src : ['.'] },
    entries,
    bottomUpOrder: g.bottomUp,
    roots: g.roots,
    cycles: g.cycles,
    externals,
    summary: {
      files: entries.length,
      shared: entries.filter((e) => e.shared).length,
      roots: g.roots.length,
      cycles: g.cycles.length,
      unresolvedImports: unresolvedCount,
      edgesOutsidePlugins: edgesOutside,
    },
  };
}

const USAGE = `Uso: node tools/migration/map-architecture.mjs <repo> [--slug <s>] [--plugin js-ts|svelte|a,b]
       [--entry full|dir:<d>|plugin:<kind>] [--src <d1,d2>] [--ignore <regex>] [--role oracle|target]
       [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]`;

export async function main(argv = process.argv.slice(2)) {
  const { flags, positional } = parseArgs(argv, ['json', 'no-write', 'help']);
  if (flags.help) {
    console.log(USAGE);
    return 0;
  }
  const repo = positional[0] ?? flags.repo;
  if (!repo) {
    console.error(USAGE);
    return 2;
  }
  const factoryRoot = flags['factory-root'] ? path.resolve(flags['factory-root']) : undefined;
  const { config } = loadMigrationConfig(factoryRoot ?? FACTORY_ROOT);
  try {
    const plugins = await loadPlugins(flags.plugin ?? config.default_plugin);
    const map = computeImportMap({
      repo,
      slug: flags.slug,
      plugins,
      entry: flags.entry ?? 'full',
      src: flags.src ? String(flags.src).split(',') : [],
      ignore: flags.ignore ?? null,
      role: flags.role,
    });
    const problems = validateArtifact(map);
    if (problems.length) throw new Error(`artefatto non conforme: ${problems.slice(0, 5).join('; ')}`);
    if (flags.json) console.log(JSON.stringify(map, null, 2));
    else {
      const s = map.summary;
      console.log(`Asse A — ${map.meta.slug} (plugin ${map.meta.plugins.join('+')}, alias ${map.meta.aliasSource})`);
      console.log(`  file ${s.files} · condivisi ${s.shared} · radici ${s.roots} · cicli ${s.cycles} · import non risolti ${s.unresolvedImports}`);
    }
    if (!flags['no-write']) {
      const guard = createGuard({ factoryRoot, artifactsHome: flags['artifacts-home'] ?? config.artifacts_home, analyzedRoots: [repo] });
      const out = guard.writeArtifact(map.meta.slug, 'A', map);
      if (!flags.json) console.log(`  scritto ${out}`);
    }
    return 0;
  } catch (e) {
    console.error(`errore: ${e.message}`);
    return 2;
  }
}

if (isMain(import.meta.url)) process.exitCode = await main();
