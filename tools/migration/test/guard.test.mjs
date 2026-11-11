// guard.test.mjs — NESSUNA scrittura del tooling puo' cadere dentro un repo analizzato.
//
// La suite «porting» riproduce uno per uno i 39 assert della guard della derivata
// (dove la radice vietata era la costante `code_repos/`), adattati alla guard generica
// (radici vietate = repo passati all'analisi). La suite «generalizzazione» copre cio'
// che la costante non poteva esprimere: configurazioni insicure rifiutate alla
// costruzione, symlink, e un'esecuzione completa che non tocca i repo.
//
//   node --test "tools/migration/**/*.test.mjs"

import { describe, test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import {
  createGuard,
  sanitizeSlug,
  ReadOnlyViolationError,
  FACTORY_ROOT,
  makeMeta,
  validateArtifact,
  isValidRelKey,
  ARTIFACT_FILES,
} from '../lib/index.mjs';
import { runAll } from '../migration-verify.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const blocked = (fn) => assert.throws(fn, ReadOnlyViolationError);

let tmp;
let guard;
let ORACLE;
let TARGET;
let LIBRARY;
let ART;

before(() => {
  tmp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'mig-guard-')));
  ORACLE = path.join(tmp, 'repos', 'oracle');
  TARGET = path.join(tmp, 'repos', 'target');
  LIBRARY = path.join(tmp, 'repos', 'library');
  for (const d of [ORACLE, TARGET, LIBRARY]) fs.mkdirSync(path.join(d, 'src'), { recursive: true });
  guard = createGuard({ factoryRoot: tmp, artifactsHome: 'migration', analyzedRoots: [ORACLE, TARGET, LIBRARY] });
  ART = guard.artifactsRoot;
});
after(() => fs.rmSync(tmp, { recursive: true, force: true }));

describe('porting dei 39 assert della guard', () => {
  const evil = () => [
    ['oracle/src/leak.json', path.join(ORACLE, 'src', 'leak.json')],
    ['target/import-map.json', path.join(TARGET, 'import-map.json')],
    ['library/tests/x.spec.ts', path.join(LIBRARY, 'tests', 'x.spec.ts')],
    ['traversal da artifacts verso target', path.join(ART, '..', 'repos', 'target', 'evil.json')],
    ['relativo alla root factory', 'repos/oracle/relative-leak.json'],
  ];
  // 1. 5 bersagli x 3 controlli = 15 assert
  for (let i = 0; i < 5; i++) {
    test(`assertNotInAnalyzed blocca #${i + 1}`, () => blocked(() => guard.assertNotInAnalyzed(evil()[i][1], { op: 'test' })));
    test(`guardedWriteFileSync blocca #${i + 1}`, () => blocked(() => guard.guardedWriteFileSync(evil()[i][1], 'x', { op: 'test' })));
    test(`isForbidden true #${i + 1}`, () => assert.equal(guard.isForbidden(evil()[i][1]), true));
  }
  // 2. output fuori da artifacts_home (2)
  test('assertWritableOutput blocca output fuori da artifacts_home', () => blocked(() => guard.assertWritableOutput(path.join(tmp, 'analytics', 'x.json'))));
  test('assertWritableOutput blocca la root factory', () => blocked(() => guard.assertWritableOutput(path.join(tmp, 'leak.json'))));
  // 3. sanitizeSlug (5 + 1)
  for (const bad of ['..', '.', 'a/b', 'a\\b', '../repos']) {
    test(`sanitizeSlug blocca "${bad}"`, () => blocked(() => sanitizeSlug(bad)));
  }
  test('sanitizeSlug accetta slug valido', () => assert.equal(sanitizeSlug('app-upgrade'), 'app-upgrade'));
  // 4. resolveOutputPath per i 4 assi (8)
  for (const axis of ['A', 'B', 'C', 'D']) {
    test(`resolveOutputPath ${axis} -> artifacts/<slug>/${ARTIFACT_FILES[axis]}`, () =>
      assert.equal(guard.resolveOutputPath('slug-x', axis), path.join(ART, 'slug-x', ARTIFACT_FILES[axis])));
    test(`resolveOutputPath ${axis} non e' in un repo analizzato`, () => assert.equal(guard.isForbidden(guard.resolveOutputPath('slug-x', axis)), false));
  }
  // 5. percorso positivo (4)
  test('validateArtifact su census valido', () => {
    const census = { meta: makeMeta({ kind: 'C', slug: 'selftest' }), observable: true, entries: [{ file: 'src/a.svelte', severity: 'clean' }], summary: {}, total: 1 };
    assert.deepEqual(validateArtifact(census), []);
  });
  test('writeArtifact scrive in artifacts_home (ammesso)', () => {
    const p = guard.writeArtifact('selftest', 'C', { meta: makeMeta({ kind: 'C', slug: 'selftest' }), observable: false, reason: 'test', entries: [] });
    assert.ok(fs.existsSync(p));
  });
  test('artefatto scritto dentro artifacts_home', () => assert.ok(guard.resolveOutputPath('selftest', 'C').startsWith(ART + path.sep)));
  test('artefatto NON dentro un repo analizzato', () => assert.equal(guard.isForbidden(guard.resolveOutputPath('selftest', 'C')), false));
  // 6. relKey (4)
  test('isValidRelKey accetta relKey POSIX', () => assert.ok(isValidRelKey('src/lib/Foo.tsx')));
  test('isValidRelKey rifiuta assoluto', () => assert.ok(!isValidRelKey('/abs/Foo.tsx')));
  test('isValidRelKey rifiuta backslash', () => assert.ok(!isValidRelKey('src\\lib\\Foo.tsx')));
  test('isValidRelKey rifiuta traversal', () => assert.ok(!isValidRelKey('../Foo.tsx')));
});

describe('generalizzazione della guard', () => {
  test('resolveOutputPath V (verdetto)', () => assert.equal(guard.resolveOutputPath('s', 'V'), path.join(ART, 's', 'verdict.json')));
  test('rifiuta artifacts_home dentro un repo analizzato', () =>
    blocked(() => createGuard({ factoryRoot: tmp, artifactsHome: 'repos/target/migration', analyzedRoots: [TARGET] })));
  test('rifiuta di analizzare la factory stessa con gli artefatti dentro', () =>
    blocked(() => createGuard({ factoryRoot: tmp, artifactsHome: 'migration', analyzedRoots: [tmp] })));
  test('rifiuta artifacts_home fuori dalla factory', () => blocked(() => createGuard({ factoryRoot: tmp, artifactsHome: '../altrove' })));
  test('un symlink in artifacts_home verso un repo analizzato non e\' una via di fuga', (t) => {
    fs.mkdirSync(ART, { recursive: true });
    try {
      fs.symlinkSync(TARGET, path.join(ART, 'link-al-target'), 'dir');
    } catch (e) {
      // Windows senza privilegi: lo skip e' dichiarato nel report del runner, non silenzioso.
      t.skip(`symlink non consentiti su questa piattaforma (${e.code})`);
      return;
    }
    blocked(() => guard.guardedWriteFileSync(path.join(ART, 'link-al-target', 'x.json'), 'x'));
    assert.equal(fs.existsSync(path.join(TARGET, 'x.json')), false);
  });
  test('la root di default e\' quella della factory che ospita il tool', () =>
    assert.ok(fs.existsSync(path.join(FACTORY_ROOT, 'tools', 'migration', 'lib', 'paths.mjs'))));

  test('un\'esecuzione completa non modifica nessun file dei repo analizzati', async () => {
    const snap = (dir) => {
      const out = {};
      const walk = (d) => {
        for (const e of fs.readdirSync(d, { withFileTypes: true })) {
          const p = path.join(d, e.name);
          if (e.isDirectory()) walk(p);
          else out[path.relative(dir, p)] = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
        }
      };
      walk(dir);
      return out;
    };
    const a = path.join(HERE, 'fixtures', 'repo-a');
    const b = path.join(HERE, 'fixtures', 'repo-b');
    const before = [snap(a), snap(b)];
    const r = await runAll({ oracleRepo: a, targetRepo: b, factoryRoot: tmp, artifactsHome: 'run-completo' });
    assert.deepEqual([snap(a), snap(b)], before);
    for (const w of r.written) assert.ok(w.startsWith(path.join(tmp, 'run-completo') + path.sep), w);
  });
});
