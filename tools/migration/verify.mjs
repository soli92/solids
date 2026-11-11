#!/usr/bin/env node
// verify.mjs — Verdetto della verifica di migrazione (oracolo, non attuatore).
//
//   node tools/migration/verify.mjs --oracle <slug-A> --target <slug-B>
//        [--debt <file.md>] [--parity <esiti.json>] [--threshold 0.95]
//        [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]
//
// Legge gli artefatti gia' prodotti (A di entrambi, D, C del target se presente), il
// registro dei debiti e gli esiti di parita' funzionale; scrive verdict.json e verdict.md
// nella cartella dello slug target. Non corregge nulla.
//
// Esiti di parita' (--parity): JSON `{ "<relKey>": { "a": "pass|fail", "b": "pass|fail" } }`,
// tipicamente raccolti con la skill deep-functional-probe su oracolo e target.
//
// Exit: 0 consolidated · 1 conditional · 3 reject (gate umano) · 2 errore d'ingresso.

import fs from 'node:fs';
import path from 'node:path';
import { createGuard, FACTORY_ROOT } from './lib/paths.mjs';
import { makeMeta, validateArtifact } from './lib/schema.mjs';
import { readDebtRegistry } from './lib/debt.mjs';
import { computeVerdict, EXIT } from './lib/verdict.mjs';
import { renderVerdictMarkdown } from './lib/report.mjs';
import { loadImportMap } from './derivation-matrix.mjs';
import { loadMigrationConfig, parseArgs, isMain } from './lib/config.mjs';

function readOptional(guard, slug, kind) {
  const abs = guard.resolveOutputPath(slug, kind);
  if (!fs.existsSync(abs)) return null;
  const art = JSON.parse(fs.readFileSync(abs, 'utf-8'));
  const problems = validateArtifact(art);
  if (problems.length) throw new Error(`${abs} non conforme: ${problems.slice(0, 5).join('; ')}`);
  return art;
}

/** Default del registro: <artifacts_home>/<target>/debt-registry.md. */
export function defaultDebtPath(guard, target) {
  return path.join(guard.artifactsRoot, target, 'debt-registry.md');
}

export function buildVerdict({ guard, oracle, target, debtFile = null, parityFile = null, threshold = 0.95 }) {
  const matrix = readOptional(guard, target, 'D');
  if (!matrix) throw new Error(`matrice di derivazione assente per "${target}": eseguire prima derivation-matrix.mjs`);
  if (matrix.repos?.a !== oracle) throw new Error(`la matrice di "${target}" confronta "${matrix.repos?.a}", non "${oracle}"`);
  const mapA = loadImportMap(guard, oracle);
  const mapB = loadImportMap(guard, target);
  const census = readOptional(guard, target, 'C');

  // Registro: dichiarato e assente = errore d'ingresso (fail-closed). Non dichiarato e
  // assente al default = non osservato (il verdetto resta conditional).
  const declared = Boolean(debtFile);
  const file = debtFile ?? defaultDebtPath(guard, target);
  if (declared && !fs.existsSync(file)) throw new Error(`registro dei debiti dichiarato ma assente: ${file}`);
  const debt = fs.existsSync(file) ? readDebtRegistry(file) : readDebtRegistry(null);
  if (declared && !debt.observable) throw new Error(debt.reason);

  let parity = null;
  if (parityFile) {
    try {
      parity = JSON.parse(fs.readFileSync(path.resolve(parityFile), 'utf-8'));
    } catch (e) {
      throw new Error(`esiti di parita' illeggibili (${parityFile}): ${e.message}`);
    }
  }
  const v = computeVerdict({ matrix, mapA, mapB, census, debt, parity, threshold: Number(threshold) });
  return {
    meta: makeMeta({ kind: 'V', slug: target, repo: { name: mapB.meta.repo.name, role: 'target' }, plugins: mapB.meta.plugins }),
    repos: matrix.repos,
    joinStrategy: matrix.joinStrategy,
    forkPoint: matrix.forkPoint,
    inputs: {
      census: !census
        ? 'non eseguito'
        : census.applicable === false
          ? `non applicabile — ${census.reason}`
          : census.observable
            ? `osservato (${census.total} file)`
            : `non osservabile — ${census.reason}`,
      debt: debt.observable ? `${path.relative(guard.factoryRoot, file) || file} (${debt.entries.length} voci)` : debt.reason,
      parity: parityFile ? path.basename(parityFile) : null,
    },
    ...v,
  };
}

const USAGE = `Uso: node tools/migration/verify.mjs --oracle <slug-A> --target <slug-B> [--debt <file.md>] [--parity <esiti.json>]
       [--threshold 0.95] [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]`;

export async function main(argv = process.argv.slice(2)) {
  const { flags } = parseArgs(argv, ['json', 'no-write', 'help']);
  if (flags.help) {
    console.log(USAGE);
    return 0;
  }
  if (!flags.oracle || !flags.target) {
    console.error(USAGE);
    return 2;
  }
  const factoryRoot = flags['factory-root'] ? path.resolve(flags['factory-root']) : undefined;
  const { config } = loadMigrationConfig(factoryRoot ?? FACTORY_ROOT);
  try {
    const guard = createGuard({ factoryRoot, artifactsHome: flags['artifacts-home'] ?? config.artifacts_home });
    const v = buildVerdict({
      guard,
      oracle: flags.oracle,
      target: flags.target,
      debtFile: flags.debt
        ? path.resolve(flags.debt)
        : config.debt_registry
          ? path.resolve(guard.factoryRoot, String(config.debt_registry).replace('{target}', flags.target))
          : null,
      parityFile: flags.parity ?? null,
      threshold: flags.threshold ?? config.parity_threshold,
    });
    const problems = validateArtifact(v);
    if (problems.length) throw new Error(`verdetto non conforme: ${problems.slice(0, 5).join('; ')}`);
    if (flags.json) console.log(JSON.stringify(v, null, 2));
    else {
      console.log(`Verdetto ${flags.oracle} -> ${flags.target}: ${v.verdict.toUpperCase()}`);
      for (const g of v.global) console.log(`  [${g.state}] ${g.reason}`);
      if (v.gates.length) console.log(`  gate umani aperti: ${v.gates.map((g) => g.gate).join(', ')}`);
    }
    if (!flags['no-write']) {
      const out = guard.writeArtifact(flags.target, 'V', v);
      const md = guard.writeText(flags.target, 'verdict.md', renderVerdictMarkdown(v));
      if (!flags.json) console.log(`  scritto ${out}\n  scritto ${md}`);
    }
    return EXIT[v.verdict];
  } catch (e) {
    console.error(`errore: ${e.message}`);
    return 2;
  }
}

if (isMain(import.meta.url)) process.exitCode = await main();
