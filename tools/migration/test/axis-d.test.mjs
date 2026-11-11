// axis-d.test.mjs — Asse D (matrice di derivazione) e verdetto, su due mini-repo.
//
// Fixture: oracolo `repo-a` (con una history git costruita qui: commit al punto di fork
// dallo stato `repo-a-fork`, poi la modifica di `divergent.ts`) e target `repo-b`.
//   src/only-a.ts     solo nell'oracolo        -> onlyInA (PORTING)
//   src/same.ts       in entrambi, identico    -> inBoth, contentEqual true
//   src/divergent.ts  oracolo cambiato dopo il fork -> divergent (gate umano)
//   src/only-b.ts     solo nel target          -> onlyInB

import { describe, test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { computeImportMap } from '../map-architecture.mjs';
import { computeDerivation, changedInOracle, buildMatrix } from '../derivation-matrix.mjs';
import { buildVerdict } from '../verify.mjs';
import { runAll } from '../migration-verify.mjs';
import { createGuard, loadPlugins, validateArtifact, computeVerdict, parseDebtRegistry } from '../lib/index.mjs';

const FX = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures');
let tmp;
let oracle;
let target;
let plugins;
let fork;

const git = (cwd, ...args) =>
  execFileSync('git', ['-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false', ...args], {
    cwd,
    encoding: 'utf-8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();

before(async () => {
  tmp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'mig-d-')));
  oracle = path.join(tmp, 'oracle');
  fs.cpSync(path.join(FX, 'repo-a-fork'), oracle, { recursive: true });
  git(oracle, 'init', '-q');
  git(oracle, 'add', '-A');
  git(oracle, 'commit', '-q', '-m', 'stato al punto di fork');
  fork = git(oracle, 'rev-parse', 'HEAD');
  fs.cpSync(path.join(FX, 'repo-a'), oracle, { recursive: true });
  git(oracle, 'add', '-A');
  git(oracle, 'commit', '-q', '-m', 'oracolo evolve dopo il fork');
  target = path.join(FX, 'repo-b');
  plugins = await loadPlugins('js-ts');
});
after(() => fs.rmSync(tmp, { recursive: true, force: true }));

const maps = () => [computeImportMap({ repo: oracle, slug: 'a', plugins }), computeImportMap({ repo: target, slug: 'b', plugins })];

describe('asse D — matrice di presenza', () => {
  test('senza fork: partizione completa, deriva gated, nessun divergent inventato', () => {
    const [a, b] = maps();
    const d = computeDerivation(a, b);
    assert.deepEqual(d.partition.onlyInA, ['src/only-a.ts']);
    assert.deepEqual(d.partition.onlyInB, ['src/only-b.ts']);
    assert.deepEqual(d.partition.inBoth, ['src/divergent.ts', 'src/index.ts', 'src/same.ts', 'src/util/helper.ts']);
    assert.deepEqual(d.partition.divergent, []);
    assert.equal(d.driftStatus, 'gated:fork-point-missing');
  });
  test('contentEqual: identico vero, migrato falso', () => {
    const [a, b] = maps();
    const d = computeDerivation(a, b);
    const eq = Object.fromEntries(d.pairs.map((p) => [p.b, p.contentEqual]));
    assert.equal(eq['src/same.ts'], true);
    assert.equal(eq['src/divergent.ts'], false);
  });
  test('con il fork (input umano): il file cambiato nell\'oracolo e\' divergent', () => {
    const changed = changedInOracle(oracle, { fork });
    assert.deepEqual([...changed], ['src/divergent.ts']);
    const [a, b] = maps();
    const d = computeDerivation(a, b, { changed, forkPoint: { commit: fork, date: null } });
    assert.deepEqual(d.partition.divergent, ['src/divergent.ts']);
    assert.ok(!d.partition.inBoth.includes('src/divergent.ts'));
    assert.equal(d.driftStatus, 'computed');
  });
  test('un fork inesistente e\' un errore, non un fork vuoto', () => {
    assert.throws(() => changedInOracle(oracle, { fork: 'non-esiste-0000' }), /non e' un commit valido/);
  });
  test('join per nome: layout riorganizzato appaiato, ambiguita\' mai risolta da sola', () => {
    const mk = (files) => ({ entries: files.map((f) => ({ file: f, hash: f })) });
    const A = mk(['lib/Icon.svelte', 'lib/a/Card.svelte', 'lib/b/Card.svelte', 'lib/Old.svelte']);
    const B = mk(['lib/Icon/Icon.svelte', 'lib/Card/Card.svelte', 'lib/New.svelte']);
    const d = computeDerivation(A, B, { joinBy: 'name' });
    assert.deepEqual(d.pairs.map((p) => [p.a, p.b]), [['lib/Icon.svelte', 'lib/Icon/Icon.svelte']]);
    assert.deepEqual(d.ambiguous, [{ name: 'Card.svelte', a: ['lib/a/Card.svelte', 'lib/b/Card.svelte'], b: ['lib/Card/Card.svelte'] }]);
    assert.deepEqual(d.partition.onlyInA, ['lib/Old.svelte']);
    assert.deepEqual(d.partition.onlyInB, ['lib/New.svelte']);
  });
});

describe('verdetto fail-closed', () => {
  const fullMatrix = () => {
    const [a, b] = maps();
    return { mapA: a, mapB: b, matrix: { repos: { a: 'a', b: 'b' }, forkPoint: { commit: fork }, ...computeDerivation(a, b, { changed: changedInOracle(oracle, { fork }) }) } };
  };
  const cleanDebt = { observable: true, entries: [] };
  const allPass = (m) => Object.fromEntries([...m.partition.inBoth, ...m.partition.divergent].map((f) => [f, { a: 'pass', b: 'pass' }]));

  test('fixture reale: conditional (da portare + divergent), con gate umano JSON sul divergent', () => {
    const { matrix, mapA, mapB } = fullMatrix();
    const v = computeVerdict({ matrix, mapA, mapB, debt: cleanDebt, parity: allPass(matrix) });
    assert.equal(v.verdict, 'conditional');
    const gate = v.gates.find((g) => g.gate === 'migration-divergent');
    assert.ok(gate && gate.action && gate.payload.files.includes('src/divergent.ts'));
    assert.equal(v.files.find((f) => f.file === 'src/only-a.ts').route, 'PORTING');
    assert.equal(v.kpi.parity_ratio, 1);
  });
  test('consolidated solo quando tutto e\' osservato e verde', () => {
    const { mapA, mapB } = fullMatrix();
    const m = { repos: { a: 'a', b: 'b' }, ...computeDerivation(mapA, mapA, { changed: new Set() }) };
    const noMode = { applicable: false, observable: false, reason: 'js-ts non ha modalita\'', entries: [] };
    const v = computeVerdict({ matrix: m, mapA, mapB: mapA, census: noMode, debt: cleanDebt, parity: allPass(m) });
    assert.equal(v.verdict, 'consolidated');
    // lo stesso run senza asse C eseguito resta conditional: non eseguito non e' non applicabile
    assert.equal(computeVerdict({ matrix: m, mapA, mapB: mapA, debt: cleanDebt, parity: allPass(m) }).verdict, 'conditional');
    assert.deepEqual(v.gates, []);
  });
  test('osservazione mancante non e\' mai un verde', () => {
    const { mapA } = fullMatrix();
    const m = { repos: { a: 'a', b: 'b' }, ...computeDerivation(mapA, mapA, { changed: new Set() }) };
    assert.equal(computeVerdict({ matrix: m, mapA, mapB: mapA, debt: cleanDebt, parity: null }).verdict, 'conditional');
    assert.equal(computeVerdict({ matrix: m, mapA, mapB: mapA, debt: null, parity: allPass(m) }).verdict, 'conditional');
    const noFork = { repos: { a: 'a', b: 'b' }, ...computeDerivation(mapA, mapA) };
    assert.equal(computeVerdict({ matrix: noFork, mapA, mapB: mapA, debt: cleanDebt, parity: allPass(noFork) }).verdict, 'conditional');
  });
  test('debito bloccante aperto -> reject con gate umano', () => {
    const { mapA } = fullMatrix();
    const m = { repos: { a: 'a', b: 'b' }, ...computeDerivation(mapA, mapA, { changed: new Set() }) };
    const debt = { observable: true, ...parseDebtRegistry('## DEBT-001 — x\n- **stato:** open\n- **bloccante:** si\n- **file:** src/same.ts\n') };
    const v = computeVerdict({ matrix: m, mapA, mapB: mapA, debt, parity: allPass(m) });
    assert.equal(v.verdict, 'reject');
    assert.equal(v.gates[0].gate, 'migration-verdict-reject');
  });
  test('regressione funzionale e parity_ratio sotto soglia -> reject', () => {
    const { mapA } = fullMatrix();
    const m = { repos: { a: 'a', b: 'b' }, ...computeDerivation(mapA, mapA, { changed: new Set() }) };
    const parity = { ...allPass(m), 'src/same.ts': { a: 'pass', b: 'fail' } };
    const v = computeVerdict({ matrix: m, mapA, mapB: mapA, debt: cleanDebt, parity });
    assert.equal(v.verdict, 'reject');
    assert.ok(v.kpi.parity_ratio < 0.95);
  });
  test('asse C: error/risk bloccano, legacy tiene conditional', () => {
    const { mapA } = fullMatrix();
    const m = { repos: { a: 'a', b: 'b' }, ...computeDerivation(mapA, mapA, { changed: new Set() }) };
    const census = (sev) => ({ observable: true, entries: [{ file: 'src/same.ts', severity: sev }] });
    assert.equal(computeVerdict({ matrix: m, mapA, mapB: mapA, census: census('risk'), debt: cleanDebt, parity: allPass(m) }).verdict, 'reject');
    assert.equal(computeVerdict({ matrix: m, mapA, mapB: mapA, census: census('legacy'), debt: cleanDebt, parity: allPass(m) }).verdict, 'conditional');
  });
});

describe('esecuzione completa da CLI-engine', () => {
  test('migration-verify: artefatti validi, registro dichiarato e assente = errore d\'ingresso', async () => {
    const factory = path.join(tmp, 'factory');
    fs.mkdirSync(factory);
    const r = await runAll({ oracleRepo: oracle, targetRepo: target, factoryRoot: factory, fork, slugA: 'orc', slugB: 'tgt' });
    assert.equal(r.verdict.verdict, 'conditional');
    for (const w of r.written.filter((f) => f.endsWith('.json'))) assert.deepEqual(validateArtifact(JSON.parse(fs.readFileSync(w, 'utf-8'))), [], w);
    assert.ok(fs.readFileSync(path.join(factory, 'migration', 'tgt', 'verdict.md'), 'utf-8').includes('migration-divergent'));
    const guard = createGuard({ factoryRoot: factory });
    assert.throws(() => buildVerdict({ guard, oracle: 'orc', target: 'tgt', debtFile: path.join(factory, 'manca.md') }), /dichiarato ma assente/);
    assert.throws(() => buildMatrix({ guard, oracle: 'orc', target: 'tgt', fork }), /--oracle-repo/);
  });
});
