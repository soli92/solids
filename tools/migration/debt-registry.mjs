#!/usr/bin/env node
// debt-registry.mjs — Registro dei debiti di migrazione: crea il template, controlla il formato.
//
//   node tools/migration/debt-registry.mjs init  --oracle <slug-A> --target <slug-B> [--file <path>]
//   node tools/migration/debt-registry.mjs check [--target <slug-B>] [--file <path>] [--json]
//
// Il registro accumula decisioni umane: e' versionato, non rigenerabile. `init` non
// sovrascrive mai un registro esistente. Default: <artifacts_home>/<target>/debt-registry.md.

import fs from 'node:fs';
import path from 'node:path';
import { createGuard, FACTORY_ROOT } from './lib/paths.mjs';
import { readDebtRegistry, debtTemplate } from './lib/debt.mjs';
import { loadMigrationConfig, parseArgs, isMain } from './lib/config.mjs';

export async function main(argv = process.argv.slice(2)) {
  const { flags, positional } = parseArgs(argv, ['json', 'help']);
  const cmd = positional[0];
  const factoryRoot = flags['factory-root'] ? path.resolve(flags['factory-root']) : undefined;
  const { config } = loadMigrationConfig(factoryRoot ?? FACTORY_ROOT);
  if (flags.help || !['init', 'check'].includes(cmd)) {
    console[flags.help ? 'log' : 'error']('Uso: debt-registry.mjs init --oracle <A> --target <B> [--file <p>] | check [--target <B>] [--file <p>] [--json]');
    return flags.help ? 0 : 2;
  }
  try {
    const guard = createGuard({ factoryRoot, artifactsHome: flags['artifacts-home'] ?? config.artifacts_home });
    if (!flags.file && !flags.target) throw new Error('indicare --target <slug> o --file <path>');
    if (cmd === 'init') {
      if (!flags.oracle || !flags.target) throw new Error('init richiede --oracle e --target');
      const file = flags.file ? path.resolve(flags.file) : guard.resolveSlugFile(flags.target, 'debt-registry.md');
      if (fs.existsSync(file)) {
        console.log(`registro gia' presente, non sovrascritto: ${file}`);
        return 0;
      }
      guard.guardedWriteFileSync(file, debtTemplate({ oracle: flags.oracle, target: flags.target }), { op: 'debt-init' });
      console.log(`creato ${file}`);
      return 0;
    }
    const file = flags.file ? path.resolve(flags.file) : path.join(guard.artifactsRoot, flags.target, 'debt-registry.md');
    const r = fs.existsSync(file) ? readDebtRegistry(file) : readDebtRegistry(null);
    if (flags.json) console.log(JSON.stringify({ file, ...r }, null, 2));
    else if (!r.observable) console.log(`NON OSSERVABILE — ${r.reason} (${file})`);
    else {
      const open = r.entries.filter((e) => e.bloccante && (e.stato === 'open' || e.stato === 'in-analysis'));
      console.log(`${file}: ${r.entries.length} voci, ${open.length} bloccanti aperte`);
      for (const e of open) console.log(`  ${e.id} — ${e.files.join(', ')}`);
    }
    return r.observable ? 0 : 1;
  } catch (e) {
    console.error(`errore: ${e.message}`);
    return 2;
  }
}

if (isMain(import.meta.url)) process.exitCode = await main();
