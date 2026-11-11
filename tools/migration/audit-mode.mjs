#!/usr/bin/env node
// audit-mode.mjs — Asse C: modalita' di compilazione per file, delegata al plugin.
//
//   node tools/migration/audit-mode.mjs <repo> [--slug <s>] [--plugin <p>] [--src <d1,d2>]
//        [--ignore <regex>] [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]
//
// Un plugin che definisce modeAudit() classifica i propri file e mappa i suoi stati sulle
// severita' normalizzate (error | risk | dirty | legacy | clean). Se nessun plugin caricato
// lo definisce, o se il plugin non trova il proprio compilatore nel repo analizzato,
// l'artefatto dice `observable: false` con la ragione: l'asse non e' mai «zero problemi»
// per assenza di osservazione.

import fs from 'node:fs';
import path from 'node:path';
import { createGuard, sanitizeSlug, FACTORY_ROOT } from './lib/paths.mjs';
import { makeMeta, validateArtifact, MODE_SEVERITIES } from './lib/schema.mjs';
import { walkSources } from './lib/walk.mjs';
import { loadPlugins, composePlugins } from './lib/plugins.mjs';
import { loadMigrationConfig, parseArgs, isMain } from './lib/config.mjs';

export function computeModeCensus({ repo, slug, plugins, src = [], ignore = null, role }) {
  const repoRoot = path.resolve(repo);
  if (!fs.existsSync(repoRoot)) throw new Error(`repo inesistente: ${repoRoot}`);
  const comp = composePlugins(plugins, repoRoot);
  const ignoreRe = ignore ? new RegExp(ignore) : null;
  const dirs = (src.length ? src : ['.']).map((d) => path.resolve(repoRoot, d));
  const files = [...new Set(dirs.flatMap((d) => walkSources(d, { accept: comp.accept, ignore: ignoreRe, relativeTo: repoRoot })))];

  const auditors = plugins.filter((p) => typeof p.modeAudit === 'function');
  const results = auditors.map((p) => ({ plugin: p.name, ...p.modeAudit(files.filter((f) => comp.owner(f) === p), repoRoot) }));
  const observed = results.filter((r) => r.observable);
  const entries = observed.flatMap((r) => r.entries).sort((a, b) => (a.file < b.file ? -1 : 1));
  const summary = Object.fromEntries(MODE_SEVERITIES.map((s) => [s, entries.filter((e) => e.severity === s).length]));

  let reason;
  if (!auditors.length) reason = `nessun plugin caricato (${comp.names.join(', ')}) definisce un audit di modalita'`;
  else if (!observed.length) reason = results.map((r) => `${r.plugin}: ${r.reason}`).join(' | ');
  else if (results.some((r) => !r.observable || r.reason)) reason = results.filter((r) => r.reason).map((r) => `${r.plugin}: ${r.reason}`).join(' | ');

  return {
    meta: makeMeta({ kind: 'C', slug: sanitizeSlug(slug ?? path.basename(repoRoot)), repo: { name: path.basename(repoRoot), role }, plugins: comp.names }),
    // applicable:false = il linguaggio non ha un concetto di modalita' (nessun plugin la
    // definisce): l'asse non esiste, non e' «non osservato».
    applicable: auditors.length > 0,
    observable: observed.length > 0,
    ...(reason ? { reason } : {}),
    auditors: results.map(({ entries: _e, ...rest }) => rest),
    entries,
    summary,
    total: entries.length,
  };
}

const USAGE = `Uso: node tools/migration/audit-mode.mjs <repo> [--slug <s>] [--plugin <p>] [--src <d1,d2>] [--ignore <regex>]
       [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]`;

export async function main(argv = process.argv.slice(2)) {
  const { flags, positional } = parseArgs(argv, ['json', 'no-write', 'help']);
  if (flags.help || !positional[0]) {
    console[flags.help ? 'log' : 'error'](USAGE);
    return flags.help ? 0 : 2;
  }
  const factoryRoot = flags['factory-root'] ? path.resolve(flags['factory-root']) : undefined;
  const { config } = loadMigrationConfig(factoryRoot ?? FACTORY_ROOT);
  try {
    const census = computeModeCensus({
      repo: positional[0],
      slug: flags.slug,
      plugins: await loadPlugins(flags.plugin ?? config.default_plugin),
      src: flags.src ? String(flags.src).split(',') : [],
      ignore: flags.ignore ?? null,
      role: flags.role,
    });
    const problems = validateArtifact(census);
    if (problems.length) throw new Error(`artefatto non conforme: ${problems.slice(0, 5).join('; ')}`);
    if (flags.json) console.log(JSON.stringify(census, null, 2));
    else if (!census.observable) console.log(`Asse C — ${census.meta.slug}: NON OSSERVABILE — ${census.reason}`);
    else console.log(`Asse C — ${census.meta.slug}: ${census.total} file · ${MODE_SEVERITIES.map((s) => `${s} ${census.summary[s]}`).join(' · ')}`);
    if (!flags['no-write']) {
      const guard = createGuard({ factoryRoot, artifactsHome: flags['artifacts-home'] ?? config.artifacts_home, analyzedRoots: [positional[0]] });
      const out = guard.writeArtifact(census.meta.slug, 'C', census);
      if (!flags.json) console.log(`  scritto ${out}`);
    }
    return 0;
  } catch (e) {
    console.error(`errore: ${e.message}`);
    return 2;
  }
}

if (isMain(import.meta.url)) process.exitCode = await main();
