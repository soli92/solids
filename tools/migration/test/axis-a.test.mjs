// axis-a.test.mjs — Asse A (albero degli import) e plugin.

import { describe, test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { computeImportMap } from '../map-architecture.mjs';
import { computeModeCensus } from '../audit-mode.mjs';
import { computeLibraryUsage, extractLibraryImports } from '../map-library-usage.mjs';
import { loadPlugins, validatePlugin, validateArtifact, readYamlBlock } from '../lib/index.mjs';
import { extractSpecifiers } from '../plugins/js-ts.mjs';

const FX = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures');
let jsts;
let svelte;
before(async () => {
  jsts = await loadPlugins('js-ts');
  svelte = await loadPlugins('svelte,js-ts');
});

describe('asse A — plugin js-ts', () => {
  test('grafo dell\'oracolo: file, import relativi, alias tsconfig, .js -> .ts', () => {
    const m = computeImportMap({ repo: path.join(FX, 'repo-a'), plugins: jsts });
    assert.deepEqual(validateArtifact(m), []);
    assert.deepEqual(m.entries.map((e) => e.file).sort(), ['src/divergent.ts', 'src/index.ts', 'src/only-a.ts', 'src/same.ts', 'src/util/helper.ts']);
    const idx = m.entries.find((e) => e.file === 'src/index.ts');
    assert.deepEqual(idx.imports, ['src/divergent.ts', 'src/only-a.ts', 'src/same.ts', 'src/util/helper.ts']);
    assert.match(m.meta.aliasSource, /^tsconfig:/);
  });
  test('condivisi, radici, ordine bottom-up (foglie prima)', () => {
    const m = computeImportMap({ repo: path.join(FX, 'repo-a'), plugins: jsts });
    const same = m.entries.find((e) => e.file === 'src/same.ts');
    assert.equal(same.shared, true);
    assert.deepEqual(same.usedBy, ['src/index.ts', 'src/util/helper.ts']);
    assert.deepEqual(m.roots, ['src/index.ts']);
    assert.equal(m.bottomUpOrder.at(-1), 'src/index.ts');
    assert.ok(m.bottomUpOrder.indexOf('src/same.ts') < m.bottomUpOrder.indexOf('src/util/helper.ts'));
  });
  test('un import nei commenti non e\' un arco', () => {
    assert.deepEqual(extractSpecifiers("// import a from './x'\n/* import('./y') */\nimport b from './z'"), ['./z']);
  });
  test('un import relativo che non risolve e\' dichiarato, non taciuto', () => {
    const m = computeImportMap({ repo: path.join(FX, 'repo-b'), plugins: jsts });
    assert.equal(m.summary.unresolvedImports, 1);
    assert.deepEqual(m.entries.find((e) => e.file === 'src/index.ts').unresolved, ['./non-esiste']);
  });
  test('l\'hash ignora la fine riga (CRLF = LF)', () => {
    const t = fs.mkdtempSync(path.join(os.tmpdir(), 'mig-eol-'));
    try {
      fs.mkdirSync(path.join(t, 'x'));
      fs.mkdirSync(path.join(t, 'y'));
      fs.writeFileSync(path.join(t, 'x', 'a.ts'), 'export const a = 1;\n');
      fs.writeFileSync(path.join(t, 'y', 'a.ts'), 'export const a = 1;\r\n');
      const hx = computeImportMap({ repo: path.join(t, 'x'), plugins: jsts }).entries[0].hash;
      const hy = computeImportMap({ repo: path.join(t, 'y'), plugins: jsts }).entries[0].hash;
      assert.equal(hx, hy);
    } finally {
      fs.rmSync(t, { recursive: true, force: true });
    }
  });
  test('cicli e self-import rilevati senza ricorsione infinita', () => {
    const t = fs.mkdtempSync(path.join(os.tmpdir(), 'mig-cyc-'));
    try {
      fs.writeFileSync(path.join(t, 'a.ts'), "import './b';");
      fs.writeFileSync(path.join(t, 'b.ts'), "import './a';");
      fs.writeFileSync(path.join(t, 'c.ts'), "import './c'; import './a';");
      const m = computeImportMap({ repo: t, plugins: jsts });
      assert.deepEqual(validateArtifact(m), []);
      assert.ok(m.cycles.includes('c.ts'));
      assert.ok(m.cycles.includes('a.ts') || m.cycles.includes('b.ts'));
    } finally {
      fs.rmSync(t, { recursive: true, force: true });
    }
  });
});

describe('asse A — plugin svelte e composizione', () => {
  test('entry plugin:astro-pages, alias $lib, .svelte -> .ts con js-ts composto', () => {
    const m = computeImportMap({ repo: path.join(FX, 'svelte-app'), plugins: svelte, entry: 'plugin:astro-pages' });
    assert.deepEqual(m.entries.map((e) => e.file).sort(), ['src/lib/App.svelte', 'src/lib/Button.svelte', 'src/lib/store.ts', 'src/pages/index.astro']);
    assert.equal(m.entryPoint.count, 1);
  });
  test('senza js-ts il .ts importato esce dal grafo e viene contato', async () => {
    const m = computeImportMap({ repo: path.join(FX, 'svelte-app'), plugins: await loadPlugins('svelte') });
    assert.equal(m.summary.edgesOutsidePlugins, 1);
  });
  test('un entry che non trova nulla e\' un errore, non uno zero', () => {
    assert.throws(() => computeImportMap({ repo: path.join(FX, 'repo-a'), plugins: svelte, entry: 'plugin:astro-pages' }), /nessun entry point/);
  });
});

describe('asse C — non osservabile e\' dichiarato, mai zero', () => {
  test('svelte senza compilatore nel repo: observable false con la ragione', () => {
    const c = computeModeCensus({ repo: path.join(FX, 'svelte-app'), plugins: svelte });
    assert.deepEqual(validateArtifact(c), []);
    assert.equal(c.observable, false);
    assert.match(c.reason, /svelte\/compiler/);
    assert.equal(c.entries.length, 0);
  });
  test('plugin senza modeAudit: observable false', () => {
    const c = computeModeCensus({ repo: path.join(FX, 'repo-a'), plugins: jsts });
    assert.equal(c.observable, false);
    assert.equal(c.applicable, false);
    assert.match(c.reason, /audit di modalita/);
  });
});

describe('asse B, interfaccia dei plugin, config', () => {
  test('import da libreria: named, alias, default, namespace, subpath', () => {
    const m = extractLibraryImports("import X, { A, B as C } from 'ui-kit/sub';\nimport * as N from 'ui-kit';", 'ui-kit');
    assert.deepEqual(Object.fromEntries(m), { A: 'A', C: 'B', X: 'default', N: '*' });
  });
  test('superficie consumata con prop e consumatori', () => {
    const t = fs.mkdtempSync(path.join(os.tmpdir(), 'mig-lib-'));
    try {
      fs.writeFileSync(path.join(t, 'a.tsx'), "import { Button } from 'ui-kit';\nexport const A = () => <Button variant=\"x\" onClick={() => 1} />;");
      const u = computeLibraryUsage({ repo: t, plugins: jsts, library: 'ui-kit' });
      assert.deepEqual(validateArtifact(u), []);
      assert.deepEqual(u.components[0].props, ['onClick', 'variant']);
      assert.equal(u.components[0].tags, 1);
    } finally {
      fs.rmSync(t, { recursive: true, force: true });
    }
  });
  test('un plugin non conforme e\' rifiutato', () => {
    assert.ok(validatePlugin({ name: 'x', extensions: ['ts'] }).length >= 2);
    assert.deepEqual(validatePlugin(jsts[0]), []);
  });
  test('lettura del blocco code_migration (sottoinsieme YAML)', () => {
    const y = 'altro: 1\ncode_migration:\n  enabled: false   # commento\n  artifacts_home: migration/\n  parity_threshold: 0.9\n  nested:\n    k: "v"\nfine: 2\n';
    assert.deepEqual(readYamlBlock(y, 'code_migration'), { enabled: false, artifacts_home: 'migration/', parity_threshold: 0.9, nested: { k: 'v' } });
  });
});

after(() => {});
