#!/usr/bin/env node
// derivation-matrix.mjs — Asse D: matrice di derivazione oracolo (A) <-> target (B).
//
//   node tools/migration/derivation-matrix.mjs --oracle <slug-A> --target <slug-B>
//        [--join-by path|name] [--fork <commit-ish> | --since <data>] [--oracle-repo <path>]
//        [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]
//
// Legge i due import-map.json (asse A) e produce derivation-matrix.json nella cartella
// dello slug target:
//   onlyInA   -> ramo PORTING          inBoth    -> ramo AUDIT
//   onlyInB   -> nuovo o orfano: verifica esplicita
//   divergent -> in entrambi, ma l'oracolo e' cambiato dopo il fork: GATE UMANO
//
// Il punto di fork e' SOLO input umano: mai dedotto (niente merge-base). Senza
// --fork/--since la matrice di presenza e' completa ma la deriva resta
// `gated:fork-point-missing` e il verdetto non puo' essere `consolidated`.
//
// `--join-by name` appaia per basename quando la migrazione ha riorganizzato il layout;
// un basename con piu' candidati su un lato NON viene appaiato: finisce in `ambiguous[]`,
// gate umano. Ogni coppia porta `contentEqual` (hash con fine riga normalizzata).
//
// SOLA LETTURA: con il fork esegue solo `git log` sull'oracolo.

import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { createGuard, FACTORY_ROOT } from './lib/paths.mjs';
import { makeMeta, validateArtifact, isValidRelKey, JOIN_STRATEGIES, DRIFT_STATUS } from './lib/schema.mjs';
import { loadMigrationConfig, parseArgs, isMain } from './lib/config.mjs';

const base = (k) => k.split('/').pop();

/** Carica e valida un import-map.json. Fail-closed. */
export function loadImportMap(guard, slug) {
  const abs = guard.resolveOutputPath(slug, 'A');
  if (!fs.existsSync(abs)) {
    throw new Error(`input mancante: ${abs} (asse A per "${slug}"). Eseguire prima map-architecture.mjs`);
  }
  const map = JSON.parse(fs.readFileSync(abs, 'utf-8'));
  if (map?.meta?.kind !== 'A') throw new Error(`${abs} non e' un artefatto di asse A`);
  const problems = validateArtifact(map);
  if (problems.length) throw new Error(`${abs} non conforme: ${problems.slice(0, 5).join('; ')}`);
  return map;
}

/** File dell'oracolo cambiati dopo il fork, relativi alla root dell'oracolo. Sola lettura. */
export function changedInOracle(oracleRepo, { fork, since }) {
  const run = (args) => execFileSync('git', ['-C', oracleRepo, ...args], { encoding: 'utf-8', maxBuffer: 256 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
  if (fork) {
    try {
      run(['rev-parse', '--verify', '--quiet', `${fork}^{commit}`]);
    } catch {
      throw new Error(`fork "${fork}" non e' un commit valido in ${oracleRepo}`);
    }
  }
  const args = ['log', '--relative', '--name-only', '--pretty=format:'];
  if (since) args.push(`--since=${since}`);
  if (fork) args.push(`${fork}..HEAD`);
  args.push('--', '.');
  let out;
  try {
    out = run(args);
  } catch (e) {
    throw new Error(`git log fallito su ${oracleRepo}: ${String(e.stderr ?? e.message).split('\n')[0]}`);
  }
  const set = new Set();
  for (const raw of out.split(/\r?\n/)) {
    const f = raw.trim().split('\\').join('/');
    if (f && isValidRelKey(f)) set.add(f);
  }
  return set;
}

/**
 * Calcola la matrice (pura, salvo `changed` fornito dal chiamante).
 * @param {object} mapA  import-map dell'oracolo
 * @param {object} mapB  import-map del target
 * @param {{ joinBy?: 'path'|'name', changed?: Set<string>|null, forkPoint?: object }} o
 */
export function computeDerivation(mapA, mapB, { joinBy = 'path', changed = null, forkPoint = { commit: null, date: null } } = {}) {
  if (!JOIN_STRATEGIES.includes(joinBy)) throw new Error(`--join-by non valido: ${joinBy}`);
  const hashA = new Map(mapA.entries.map((e) => [e.file, e.hash]));
  const hashB = new Map(mapB.entries.map((e) => [e.file, e.hash]));
  const aKeys = [...hashA.keys()].sort();
  const bKeys = [...hashB.keys()].sort();

  let pairs = [];
  let ambiguous = [];
  let onlyInA;
  let onlyInB;
  if (joinBy === 'path') {
    const bSet = new Set(bKeys);
    const aSet = new Set(aKeys);
    onlyInA = aKeys.filter((k) => !bSet.has(k));
    onlyInB = bKeys.filter((k) => !aSet.has(k));
    pairs = aKeys.filter((k) => bSet.has(k)).map((k) => ({ a: k, b: k }));
  } else {
    const group = (keys) => {
      const g = new Map();
      for (const k of keys) g.set(base(k), [...(g.get(base(k)) ?? []), k]);
      return g;
    };
    const ga = group(aKeys);
    const gb = group(bKeys);
    onlyInA = [];
    onlyInB = [];
    for (const [name, al] of ga) {
      const bl = gb.get(name);
      if (!bl) onlyInA.push(...al);
      else if (al.length === 1 && bl.length === 1) pairs.push({ name, a: al[0], b: bl[0] });
      else ambiguous.push({ name, a: [...al].sort(), b: [...bl].sort() });
    }
    for (const [name, bl] of gb) if (!ga.has(name)) onlyInB.push(...bl);
    onlyInA.sort();
    onlyInB.sort();
    pairs.sort((x, y) => (x.b < y.b ? -1 : x.b > y.b ? 1 : 0));
    ambiguous.sort((x, y) => (x.name < y.name ? -1 : 1));
  }
  for (const p of pairs) {
    const ha = hashA.get(p.a);
    const hb = hashB.get(p.b);
    p.contentEqual = ha && hb ? ha === hb : null;
  }

  const driftStatus = changed ? DRIFT_STATUS.COMPUTED : DRIFT_STATUS.GATED;
  const divergentPairs = changed ? pairs.filter((p) => changed.has(p.a)) : [];
  const divB = new Set(divergentPairs.map((p) => p.b));
  for (const p of pairs) p.changedInOracleAfterFork = changed ? changed.has(p.a) : null;

  return {
    partition: {
      onlyInA,
      onlyInB,
      inBoth: pairs.filter((p) => !divB.has(p.b)).map((p) => p.b).sort(),
      divergent: [...divB].sort(),
    },
    joinStrategy: joinBy,
    pairs,
    ambiguous,
    driftStatus,
    forkPoint,
    // Cambiati nell'oracolo dopo il fork che NON hanno un corrispettivo appaiato: da guardare
    // (con join per nome finiscono qui i file ambigui modificati).
    changedUnpaired: changed ? [...changed].filter((f) => hashA.has(f) && !pairs.some((p) => p.a === f)).sort() : [],
    summary: {
      a: aKeys.length,
      b: bKeys.length,
      onlyInA: onlyInA.length,
      onlyInB: onlyInB.length,
      inBoth: pairs.length - divB.size,
      divergent: divB.size,
      ambiguous: ambiguous.length,
      identical: pairs.filter((p) => p.contentEqual === true).length,
    },
  };
}

export function buildMatrix({ guard, oracle, target, joinBy, fork, since, oracleRepo }) {
  const mapA = loadImportMap(guard, oracle);
  const mapB = loadImportMap(guard, target);
  let changed = null;
  if (fork || since) {
    if (!oracleRepo) throw new Error('--fork/--since richiedono --oracle-repo (il path dell\'oracolo, per git log in sola lettura)');
    changed = changedInOracle(path.resolve(oracleRepo), { fork, since });
  }
  const d = computeDerivation(mapA, mapB, { joinBy, changed, forkPoint: { commit: fork ?? null, date: since ?? null } });
  return {
    meta: makeMeta({ kind: 'D', slug: target, repo: { name: mapB.meta.repo.name, role: 'target' }, plugins: mapB.meta.plugins }),
    repos: { a: oracle, b: target },
    ...d,
  };
}

const USAGE = `Uso: node tools/migration/derivation-matrix.mjs --oracle <slug-A> --target <slug-B> [--join-by path|name]
       [--fork <commit-ish> | --since <data>] [--oracle-repo <path>] [--artifacts-home <dir>] [--factory-root <dir>] [--json] [--no-write]`;

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
    const guard = createGuard({
      factoryRoot,
      artifactsHome: flags['artifacts-home'] ?? config.artifacts_home,
      analyzedRoots: flags['oracle-repo'] ? [flags['oracle-repo']] : [],
    });
    const m = buildMatrix({
      guard,
      oracle: flags.oracle,
      target: flags.target,
      joinBy: flags['join-by'] ?? config.join_by,
      fork: flags.fork,
      since: flags.since,
      oracleRepo: flags['oracle-repo'],
    });
    const problems = validateArtifact(m);
    if (problems.length) throw new Error(`artefatto non conforme: ${problems.slice(0, 5).join('; ')}`);
    if (flags.json) console.log(JSON.stringify(m, null, 2));
    else {
      const s = m.summary;
      console.log(`Asse D — ${flags.oracle} -> ${flags.target} (join ${m.joinStrategy}, deriva ${m.driftStatus})`);
      console.log(`  onlyInA ${s.onlyInA} (PORTING) · inBoth ${s.inBoth} (AUDIT) · divergent ${s.divergent} (gate umano) · onlyInB ${s.onlyInB} · ambigui ${s.ambiguous} · identici ${s.identical}`);
    }
    if (!flags['no-write']) {
      const out = guard.writeArtifact(flags.target, 'D', m);
      if (!flags.json) console.log(`  scritto ${out}`);
    }
    return 0;
  } catch (e) {
    console.error(`errore: ${e.message}`);
    return 2;
  }
}

if (isMain(import.meta.url)) process.exitCode = await main();
