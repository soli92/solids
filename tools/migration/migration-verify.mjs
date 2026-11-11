#!/usr/bin/env node
// migration-verify.mjs — Esecuzione completa: assi A (entrambi), B (se c'e' una libreria),
// C (target), D, verdetto. E' il motore di `/migration-verify`.
//
//   node tools/migration/migration-verify.mjs <oracle_repo> <target_repo>
//        [--plugin js-ts|svelte|a,b] [--join-by path|name] [--fork <commit-ish> | --since <data>]
//        [--library <pkg>] [--entry full|dir:<d>|plugin:<kind>] [--src <d1,d2>] [--ignore <regex>]
//        [--debt <file.md>] [--parity <esiti.json>] [--threshold 0.95]
//        [--slug-a <s>] [--slug-b <s>] [--artifacts-home <dir>] [--factory-root <dir>] [--json]
//
// I due repo sono letti in sola lettura e sono destinazioni VIETATE della guard; gli
// artefatti vanno in <artifacts_home>/<slug>/. Exit: 0 consolidated · 1 conditional ·
// 3 reject (gate umano) · 2 errore d'ingresso.

import path from 'node:path';
import { createGuard, sanitizeSlug, FACTORY_ROOT } from './lib/paths.mjs';
import { validateArtifact } from './lib/schema.mjs';
import { loadPlugins } from './lib/plugins.mjs';
import { loadMigrationConfig, parseArgs, isMain } from './lib/config.mjs';
import { EXIT } from './lib/verdict.mjs';
import { renderVerdictMarkdown } from './lib/report.mjs';
import { computeImportMap } from './map-architecture.mjs';
import { computeLibraryUsage } from './map-library-usage.mjs';
import { computeModeCensus } from './audit-mode.mjs';
import { buildMatrix } from './derivation-matrix.mjs';
import { buildVerdict } from './verify.mjs';

function checked(art) {
  const problems = validateArtifact(art);
  if (problems.length) throw new Error(`artefatto ${art.meta?.kind} non conforme: ${problems.slice(0, 5).join('; ')}`);
  return art;
}

/** Slug distinti anche quando i due repo hanno lo stesso basename (due worktree). */
export function pickSlugs(oracleRepo, targetRepo, slugA, slugB) {
  let a = slugA ?? path.basename(path.resolve(oracleRepo));
  let b = slugB ?? path.basename(path.resolve(targetRepo));
  if (a === b) {
    if (slugA || slugB) throw new Error(`gli slug di oracolo e target coincidono ("${a}"): passarne due distinti`);
    a = `${a}-oracle`;
    b = `${b}-target`;
  }
  return { a: sanitizeSlug(a), b: sanitizeSlug(b) };
}

export async function runAll(o) {
  const factoryRoot = o.factoryRoot ? path.resolve(o.factoryRoot) : undefined;
  const { config, source } = loadMigrationConfig(factoryRoot ?? FACTORY_ROOT);
  const guard = createGuard({ factoryRoot, artifactsHome: o.artifactsHome ?? config.artifacts_home, analyzedRoots: [o.oracleRepo, o.targetRepo] });
  const slugs = pickSlugs(o.oracleRepo, o.targetRepo, o.slugA, o.slugB);
  const plugins = await loadPlugins(o.plugin ?? config.default_plugin);
  const common = { plugins, entry: o.entry ?? 'full', src: o.src ?? [], ignore: o.ignore ?? null };
  const written = [];
  const log = [];

  const mapA = checked(computeImportMap({ repo: o.oracleRepo, slug: slugs.a, role: 'oracle', ...common }));
  const mapB = checked(computeImportMap({ repo: o.targetRepo, slug: slugs.b, role: 'target', ...common }));
  written.push(guard.writeArtifact(slugs.a, 'A', mapA), guard.writeArtifact(slugs.b, 'A', mapB));
  log.push(`A oracolo: ${mapA.summary.files} file, ${mapA.summary.unresolvedImports} import non risolti`);
  log.push(`A target:  ${mapB.summary.files} file, ${mapB.summary.unresolvedImports} import non risolti`);

  const library = o.library ?? config.library_package;
  if (library) {
    for (const [repo, slug, role] of [[o.oracleRepo, slugs.a, 'oracle'], [o.targetRepo, slugs.b, 'target']]) {
      const u = checked(computeLibraryUsage({ repo, slug, role, library, plugins, src: common.src, ignore: common.ignore }));
      written.push(guard.writeArtifact(slug, 'B', u));
      log.push(`B ${role}: ${u.summary.symbols} simboli di ${library} in ${u.summary.consumers} file`);
    }
  } else {
    log.push('B: saltato — nessuna libreria indicata (--library o code_migration.library_package)');
  }

  const census = checked(computeModeCensus({ repo: o.targetRepo, slug: slugs.b, role: 'target', plugins, src: common.src, ignore: common.ignore }));
  written.push(guard.writeArtifact(slugs.b, 'C', census));
  log.push(
    census.applicable === false
      ? `C target: non applicabile — ${census.reason}`
      : census.observable
        ? `C target: ${census.total} file censiti (autorita' ${census.auditors.map((a) => a.authority ?? '-').join('/')})`
        : `C target: NON OSSERVABILE — ${census.reason}`,
  );

  const matrix = checked(
    buildMatrix({ guard, oracle: slugs.a, target: slugs.b, joinBy: o.joinBy ?? config.join_by, fork: o.fork, since: o.since, oracleRepo: o.oracleRepo }),
  );
  written.push(guard.writeArtifact(slugs.b, 'D', matrix));
  const s = matrix.summary;
  log.push(`D: onlyInA ${s.onlyInA} · inBoth ${s.inBoth} · divergent ${s.divergent} · onlyInB ${s.onlyInB} · ambigui ${s.ambiguous} (deriva ${matrix.driftStatus})`);

  const debtFile = o.debt
    ? path.resolve(o.debt)
    : config.debt_registry
      ? path.resolve(guard.factoryRoot, String(config.debt_registry).replace('{target}', slugs.b))
      : null;
  const verdict = checked(
    buildVerdict({ guard, oracle: slugs.a, target: slugs.b, debtFile, parityFile: o.parity ?? null, threshold: o.threshold ?? config.parity_threshold }),
  );
  written.push(guard.writeArtifact(slugs.b, 'V', verdict), guard.writeText(slugs.b, 'verdict.md', renderVerdictMarkdown(verdict)));
  return { verdict, log, written, slugs, configSource: source, artifactsRoot: guard.artifactsRoot };
}

const USAGE = `Uso: node tools/migration/migration-verify.mjs <oracle_repo> <target_repo> [--plugin js-ts|svelte|a,b]
       [--join-by path|name] [--fork <commit-ish> | --since <data>] [--library <pkg>] [--entry full|dir:<d>|plugin:<kind>]
       [--src <d1,d2>] [--ignore <regex>] [--debt <file.md>] [--parity <esiti.json>] [--threshold 0.95]
       [--slug-a <s>] [--slug-b <s>] [--artifacts-home <dir>] [--factory-root <dir>] [--json]`;

export async function main(argv = process.argv.slice(2)) {
  const { flags, positional } = parseArgs(argv, ['json', 'help']);
  if (flags.help) {
    console.log(USAGE);
    return 0;
  }
  if (positional.length !== 2) {
    console.error(USAGE);
    return 2;
  }
  try {
    const r = await runAll({
      oracleRepo: positional[0],
      targetRepo: positional[1],
      plugin: flags.plugin,
      joinBy: flags['join-by'],
      fork: flags.fork,
      since: flags.since,
      library: flags.library,
      entry: flags.entry,
      src: flags.src ? String(flags.src).split(',') : [],
      ignore: flags.ignore,
      debt: flags.debt,
      parity: flags.parity,
      threshold: flags.threshold,
      slugA: flags['slug-a'],
      slugB: flags['slug-b'],
      artifactsHome: flags['artifacts-home'],
      factoryRoot: flags['factory-root'],
    });
    const v = r.verdict;
    if (flags.json) {
      console.log(JSON.stringify({ verdict: v.verdict, kpi: v.kpi, summary: v.summary, global: v.global, gates: v.gates, written: r.written }, null, 2));
    } else {
      console.log(`Verifica di migrazione ${r.slugs.a} -> ${r.slugs.b}  (config: ${r.configSource})`);
      for (const l of r.log) console.log(`  ${l}`);
      console.log(`\nVERDETTO: ${v.verdict.toUpperCase()}`);
      console.log(`  parity_ratio: ${v.kpi.observed ? v.kpi.parity_ratio.toFixed(3) : `non osservato (${v.kpi.reason})`}`);
      for (const g of v.global) console.log(`  [${g.state}] ${g.reason}`);
      if (v.gates.length) {
        console.log('\nGATE UMANI APERTI (il verificatore si ferma; JSON completo in verdict.json):');
        const brief = v.gates.map((g) => {
          const files = g.payload.files ?? g.payload.ambiguous ?? [];
          const head = files.slice(0, 5);
          return { ...g, payload: { ...g.payload, ...(g.payload.files ? { files: head } : {}), ...(g.payload.ambiguous ? { ambiguous: head } : {}), ...(files.length > 5 ? { omessi: files.length - 5 } : {}) } };
        });
        console.log(JSON.stringify(brief, null, 2));
      }
      console.log(`\nArtefatti in ${r.artifactsRoot}: ${r.written.length} file`);
    }
    return EXIT[v.verdict];
  } catch (e) {
    console.error(`errore: ${e.message}`);
    return 2;
  }
}

if (isMain(import.meta.url)) process.exitCode = await main();
