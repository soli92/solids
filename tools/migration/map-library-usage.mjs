#!/usr/bin/env node
// map-library-usage.mjs — Asse B: superficie di una libreria consumata da un repo.
//
//   node tools/migration/map-library-usage.mjs <repo> --library <pkg> [--slug <s>] [--plugin <p>]
//        [--src <d1,d2>] [--ignore <regex>] [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]
//
// Per ogni simbolo importato da <pkg> (anche da subpath `<pkg>/x`): prop usate nei tag
// (`<Nome prop=...>`, JSX/Svelte/Astro), occorrenze di tag, riferimenti non-tag, file
// consumatori. Per file: peso di adeguamento (occorrenze + simboli distinti).
// Eseguito su oracolo e target, il confronto per `name` mostra cosa cambia nel contratto.
//
// La libreria e' un parametro (config `library_package` o --library): nessun nome cablato.
// Limiti dichiarati (regex): un `>` dentro un'espressione di attributo tronca il tag;
// l'uso via re-export locale (barrel del repo) non e' attribuito alla libreria.

import fs from 'node:fs';
import path from 'node:path';
import { createGuard, sanitizeSlug, FACTORY_ROOT } from './lib/paths.mjs';
import { makeMeta, validateArtifact } from './lib/schema.mjs';
import { walkSources, relKey, readSource } from './lib/walk.mjs';
import { loadPlugins, composePlugins } from './lib/plugins.mjs';
import { stripJsComments } from './plugins/js-ts.mjs';
import { loadMigrationConfig, parseArgs, isMain } from './lib/config.mjs';

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** localName -> nome esportato, per import dalla libreria (named, default, namespace). */
export function extractLibraryImports(src, library) {
  const code = stripJsComments(src);
  const map = new Map();
  const from = String.raw`from\s*['"]` + esc(library) + String.raw`(?:/[^'"]*)?['"]`;
  const re = new RegExp(String.raw`import\s+(?:type\s+)?([^;'"\x60]*?)\s*` + from, 'g');
  let m;
  while ((m = re.exec(code)) !== null) {
    let clause = m[1].trim();
    const named = /\{([^}]*)\}/.exec(clause);
    if (named) {
      for (const spec of named[1].split(',')) {
        const parts = spec.trim().replace(/^type\s+/, '').split(/\s+as\s+/);
        if (parts[0]) map.set((parts[1] ?? parts[0]).trim(), parts[0].trim());
      }
      clause = clause.replace(named[0], '');
    }
    const ns = /\*\s*as\s+([A-Za-z_$][\w$]*)/.exec(clause);
    if (ns) {
      map.set(ns[1], '*');
      clause = clause.replace(ns[0], '');
    }
    const def = /^([A-Za-z_$][\w$]*)/.exec(clause.replace(/^[\s,]+/, ''));
    if (def) map.set(def[1], 'default');
  }
  const req = new RegExp(String.raw`(?:const|let|var)\s+(\{[^}]*\}|[A-Za-z_$][\w$]*)\s*=\s*require\(\s*['"]` + esc(library) + String.raw`(?:/[^'"]*)?['"]\s*\)`, 'g');
  while ((m = req.exec(code)) !== null) {
    if (m[1].startsWith('{')) {
      for (const spec of m[1].slice(1, -1).split(',')) {
        const parts = spec.trim().split(/\s*:\s*/);
        if (parts[0]) map.set((parts[1] ?? parts[0]).trim(), parts[0].trim());
      }
    } else map.set(m[1], '*');
  }
  return map;
}

function stripAttrValues(attrs) {
  let out = attrs.replace(/"[^"]*"/g, '""').replace(/'[^']*'/g, "''");
  let prev;
  do {
    prev = out;
    out = out.replace(/\{[^{}]*\}/g, ' ');
  } while (out !== prev);
  return out;
}

/** Uso di un nome locale: tag + prop, e riferimenti non-tag. */
export function extractUsage(src, localName) {
  const props = new Set();
  let tags = 0;
  const tagRe = new RegExp(String.raw`<${esc(localName)}(?![\w$.-])(\s[^>]*?)?/?>`, 'gs');
  let m;
  while ((m = tagRe.exec(src)) !== null) {
    tags++;
    const attrs = stripAttrValues(m[1] ?? '');
    for (const a of attrs.matchAll(/(?:^|\s)((?:on:|bind:|use:|let:)?[\w:$-]+)(?==|[\s/>]|$)/g)) props.add(a[1]);
  }
  const refRe = new RegExp(String.raw`(?<![\w$<./-])${esc(localName)}(?![\w$])`, 'g');
  const refs = Math.max(0, (src.match(refRe) ?? []).length - 1); // -1: la dichiarazione nell'import
  return { props, tags, refs };
}

export function computeLibraryUsage({ repo, slug, plugins, library, src = [], ignore = null, role }) {
  if (!library) throw new Error('libreria non indicata: --library <pkg> o code_migration.library_package');
  const repoRoot = path.resolve(repo);
  if (!fs.existsSync(repoRoot)) throw new Error(`repo inesistente: ${repoRoot}`);
  const comp = composePlugins(plugins, repoRoot);
  const ignoreRe = ignore ? new RegExp(ignore) : null;
  const dirs = (src.length ? src : ['.']).map((d) => path.resolve(repoRoot, d));
  const files = [...new Set(dirs.flatMap((d) => walkSources(d, { accept: comp.accept, ignore: ignoreRe, relativeTo: repoRoot })))];

  const byName = new Map();
  const byFile = [];
  for (const abs of files) {
    const text = readSource(abs);
    const imports = extractLibraryImports(text, library);
    if (!imports.size) continue;
    const file = relKey(abs, repoRoot);
    const extras = comp.owner(abs)?.usageExtras?.(text) ?? {};
    let occ = 0;
    for (const [local, exported] of imports) {
      const name = exported === 'default' || exported === '*' ? `${exported}:${local}` : exported;
      const u = extractUsage(text, local);
      const agg = byName.get(name) ?? { props: new Set(), slots: new Set(), consumers: [], tags: 0, refs: 0 };
      u.props.forEach((p) => agg.props.add(p));
      (extras.slots ?? []).forEach((s) => agg.slots.add(s));
      agg.tags += u.tags;
      agg.refs += u.refs;
      agg.consumers.push({ file, count: u.tags + u.refs });
      byName.set(name, agg);
      occ += u.tags + u.refs;
    }
    byFile.push({ file, occurrences: occ, symbols: imports.size });
  }
  const components = [...byName.entries()]
    .map(([name, a]) => ({
      name,
      props: [...a.props].sort(),
      slots: [...a.slots].sort(),
      tags: a.tags,
      refs: a.refs,
      consumers: a.consumers.sort((x, y) => y.count - x.count || (x.file < y.file ? -1 : 1)),
    }))
    .sort((x, y) => y.consumers.length - x.consumers.length || (x.name < y.name ? -1 : 1));
  byFile.sort((x, y) => y.occurrences - x.occurrences || (x.file < y.file ? -1 : 1));
  return {
    meta: makeMeta({ kind: 'B', slug: sanitizeSlug(slug ?? path.basename(repoRoot)), repo: { name: path.basename(repoRoot), role }, plugins: comp.names }),
    library,
    components,
    byFile,
    summary: { filesScanned: files.length, consumers: byFile.length, symbols: components.length },
  };
}

const USAGE = `Uso: node tools/migration/map-library-usage.mjs <repo> --library <pkg> [--slug <s>] [--plugin <p>]
       [--src <d1,d2>] [--ignore <regex>] [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]`;

export async function main(argv = process.argv.slice(2)) {
  const { flags, positional } = parseArgs(argv, ['json', 'no-write', 'help']);
  if (flags.help) {
    console.log(USAGE);
    return 0;
  }
  const repo = positional[0];
  const factoryRoot = flags['factory-root'] ? path.resolve(flags['factory-root']) : undefined;
  const { config } = loadMigrationConfig(factoryRoot ?? FACTORY_ROOT);
  if (!repo) {
    console.error(USAGE);
    return 2;
  }
  try {
    const usage = computeLibraryUsage({
      repo,
      slug: flags.slug,
      plugins: await loadPlugins(flags.plugin ?? config.default_plugin),
      library: flags.library ?? config.library_package,
      src: flags.src ? String(flags.src).split(',') : [],
      ignore: flags.ignore ?? null,
      role: flags.role,
    });
    const problems = validateArtifact(usage);
    if (problems.length) throw new Error(`artefatto non conforme: ${problems.slice(0, 5).join('; ')}`);
    if (flags.json) console.log(JSON.stringify(usage, null, 2));
    else console.log(`Asse B — ${usage.meta.slug} · ${usage.library}: ${usage.summary.symbols} simboli in ${usage.summary.consumers} file`);
    if (!flags['no-write']) {
      const guard = createGuard({ factoryRoot, artifactsHome: flags['artifacts-home'] ?? config.artifacts_home, analyzedRoots: [repo] });
      const out = guard.writeArtifact(usage.meta.slug, 'B', usage);
      if (!flags.json) console.log(`  scritto ${out}`);
    }
    return 0;
  } catch (e) {
    console.error(`errore: ${e.message}`);
    return 2;
  }
}

if (isMain(import.meta.url)) process.exitCode = await main();
