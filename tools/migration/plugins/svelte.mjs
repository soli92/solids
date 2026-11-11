// plugins/svelte.mjs — Plugin Svelte/Astro.
//
// Grafo: import dai blocchi <script> dei .svelte e dal frontmatter/script dei .astro
// (estrazione condivisa con js-ts). Alias da tsconfig; `$lib` -> `src/lib` come default
// se il repo ha `src/lib` e nessun alias lo ridefinisce.
//
// Asse C (modeAudit): censimento legacy | runes per componente .svelte. L'AUTORITA' e'
// il compilatore installato NEL REPO ANALIZZATO (`svelte/compiler`, risolto con
// createRequire dal suo package.json). Se non e' risolvibile l'asse e' dichiarato
// «non osservabile» con la ragione: mai zero, mai un default. Se il compilatore non
// espone `metadata.runes` (Svelte 4) la classificazione e' euristica e l'artefatto lo
// dichiara (`authority: heuristic`).
//
// Nota: caricare il compilatore del repo analizzato significa eseguire codice di quel
// repo (il suo `node_modules`). E' lo stesso compromesso dell'originale: l'autorita'
// sulla modalita' e' la versione di Svelte che quel repo usa davvero.
//
// Entry point opzionali: `astro-pages` (src/pages/**/*.astro) e `storybook-stories`
// (file *.stories.* sotto stories/ o src/).

import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { extractSpecifiers, resolveSpecifiers } from './js-ts.mjs';
import { walkSources, readSource, relKey } from '../lib/walk.mjs';

/** Codice JS di un .svelte (blocchi <script>) o di un .astro (frontmatter + <script>). */
export function scriptContent(file, src) {
  const parts = [];
  if (file.endsWith('.astro')) {
    const fm = /^\s*---\r?\n([\s\S]*?)\r?\n---/.exec(src);
    if (fm) parts.push(fm[1]);
  }
  for (const m of src.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/gi)) parts.push(m[1]);
  return parts.join('\n');
}

// ---------------------------------------------------------------- asse C ---
// Classificazione portata dall'originale della derivata (stati e marcatori invariati),
// con la mappatura sulle severita' normalizzate di schema.mjs.

const STATUS_SEVERITY = {
  'NON-COMPILA': 'error',
  'runes-RISCHIOSO': 'risk',
  'runes-sporco': 'dirty',
  legacy: 'legacy',
  'runes-pulito': 'clean',
};

const RISK_WARNINGS = new Set(['non_reactive_update', 'state_referenced_locally', 'reactive_declaration_invalid_placement']);
const DEPRECATION_WARNINGS = new Set([
  'event_directive_deprecated',
  'slot_element_deprecated',
  'svelte_self_deprecated',
  'svelte_component_deprecated',
  'component_name_lowercase',
]);
const LEGACY_MARKERS = [
  ['export let', /(^|\n)\s*export\s+let\s/],
  ['$: reattivo', /(^|\n)\s*\$:\s/],
  ['createEventDispatcher', /createEventDispatcher/],
  ['on: direttiva', /\son:[\w-]+[=\s/>]/],
  ['<slot>', /<slot[\s/>]/],
  ['$$slots/$$props', /\$\$(slots|props|restProps)\b/],
  ['svelte/legacy run()', /from\s+['"]svelte\/legacy['"]/],
];
const RUNES_MARKERS = [/\$props\s*\(/, /\$state[.(]/, /\$derived[.(]/, /\$effect[.(]/, /\$bindable\s*\(/];

const blank = (c) => (c === '\n' ? '\n' : ' ');

function stripCodeSpans(src, lineComment) {
  let out = '';
  let state = 0;
  let quote = '';
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    const c2 = src[i + 1] ?? '';
    if (state === 1) {
      if (c === '\n') {
        state = 0;
        out += '\n';
      } else out += ' ';
      continue;
    }
    if (state === 2) {
      if (c === '*' && c2 === '/') {
        out += '  ';
        i++;
        state = 0;
      } else out += blank(c);
      continue;
    }
    if (state === 3) {
      if (c === '\\') {
        out += ' ';
        if (i + 1 < src.length) {
          out += blank(c2);
          i++;
        }
        continue;
      }
      if (c === quote) {
        out += ' ';
        state = 0;
      } else out += blank(c);
      continue;
    }
    if (lineComment && c === '/' && c2 === '/') {
      state = 1;
      out += '  ';
      i++;
      continue;
    }
    if (c === '/' && c2 === '*') {
      state = 2;
      out += '  ';
      i++;
      continue;
    }
    if (c === "'" || c === '"' || c === '`') {
      state = 3;
      quote = c;
      out += ' ';
      continue;
    }
    out += c;
  }
  return out;
}

function stripMarkupSpans(src) {
  let out = '';
  let inTag = false;
  let sub = 0;
  let quote = '';
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (sub === 1) {
      if (c === '-' && src[i + 1] === '-' && src[i + 2] === '>') {
        out += '   ';
        i += 2;
        sub = 0;
      } else out += blank(c);
      continue;
    }
    if (sub === 2) {
      if (c === quote) {
        out += ' ';
        sub = 0;
      } else out += blank(c);
      continue;
    }
    if (!inTag && c === '<' && src.startsWith('!--', i + 1)) {
      out += '    ';
      i += 3;
      sub = 1;
      continue;
    }
    if (!inTag && c === '<' && /[A-Za-z/]/.test(src[i + 1] ?? '')) {
      inTag = true;
      out += c;
      continue;
    }
    if (inTag) {
      if (c === '"' || c === "'") {
        quote = c;
        sub = 2;
        out += ' ';
        continue;
      }
      if (c === '>') inTag = false;
    }
    out += c;
  }
  return out;
}

/** Sorgente con commenti e stringhe azzerati, per i soli marcatori testuali. */
export function stripCommentsAndStrings(src) {
  let s = src.replace(/(<script\b[^>]*>)([\s\S]*?)(<\/script\s*>)/gi, (_, o, b, c) => o + stripCodeSpans(b, true) + c);
  s = s.replace(/(<style\b[^>]*>)([\s\S]*?)(<\/style\s*>)/gi, (_, o, b, c) => o + stripCodeSpans(b, false) + c);
  return stripMarkupSpans(s);
}

/** Classifica un componente. `compiler` = module.exports di svelte/compiler del repo. */
export function classify(absFile, repoRoot, compiler) {
  const source = readSource(absFile);
  const scan = stripCommentsAndStrings(source);
  const legacy = LEGACY_MARKERS.filter(([, re]) => re.test(scan)).map(([l]) => l);
  const runesHeuristic = RUNES_MARKERS.some((re) => re.test(scan));
  let runes = null;
  let warnings = [];
  let error = null;
  try {
    const res = compiler.compile(source, { filename: absFile, generate: false });
    warnings = (res.warnings ?? []).map((w) => w.code ?? w.name ?? 'unknown');
    const md = res.metadata?.runes;
    runes = typeof md === 'boolean' ? md : null;
  } catch (e) {
    error = String(e?.message ?? e).split('\n')[0];
  }
  const runesEffective = runes ?? runesHeuristic;
  const risk = [...new Set(warnings.filter((w) => RISK_WARNINGS.has(w)))];
  const deprecated = [...new Set(warnings.filter((w) => DEPRECATION_WARNINGS.has(w)))];
  let status;
  if (error) status = 'NON-COMPILA';
  else if (!runesEffective) status = 'legacy';
  else if (risk.length) status = 'runes-RISCHIOSO';
  else if (legacy.length || deprecated.length) status = 'runes-sporco';
  else status = 'runes-pulito';
  return {
    file: relKey(absFile, repoRoot),
    status,
    severity: STATUS_SEVERITY[status],
    runes,
    markers: legacy,
    risk,
    deprecated,
    error,
  };
}

/** Il compilatore del repo analizzato, o la ragione per cui non c'e'. */
export function resolveCompiler(repoRoot) {
  const nodeMajor = Number(process.versions.node.split('.')[0]);
  if (nodeMajor < 18) {
    return { compiler: null, reason: `Node ${process.versions.node} < 18: il compilatore Svelte 5 fallirebbe su ogni file (falsi NON-COMPILA)` };
  }
  try {
    const root = path.resolve(repoRoot);
    const req = createRequire(pathToFileURL(path.join(root, 'package.json')));
    // La risoluzione di Node risale le directory: un svelte trovato SOPRA il repo non e'
    // il compilatore di quel repo. Fail-closed: non osservabile, con il path trovato.
    const where = fs.realpathSync(req.resolve('svelte/compiler'));
    const rel = path.relative(fs.realpathSync(root), where);
    if (rel.startsWith('..') || path.isAbsolute(rel)) {
      return { compiler: null, reason: `svelte/compiler risolto fuori dal repo analizzato (${where}): non e' il suo compilatore (dipendenze hoisted in un monorepo: analizzare il package che le dichiara)` };
    }
    const compiler = req('svelte/compiler'); // CJS: compile su module.exports, non su .default
    if (typeof compiler?.compile !== 'function') return { compiler: null, reason: 'svelte/compiler risolto ma senza compile()' };
    return { compiler, version: compiler.VERSION ?? null };
  } catch (e) {
    return {
      compiler: null,
      reason: `svelte/compiler non risolvibile dal repo analizzato (${String(e.code ?? e.message).split('\n')[0]}): installare le dipendenze nel repo oppure accettare l'asse C non osservato`,
    };
  }
}

function probeRunesMetadata(compiler) {
  try {
    const res = compiler.compile('<script>let { x } = $props();</script>{x}', { filename: 'Probe.svelte', generate: false });
    return typeof res?.metadata?.runes === 'boolean';
  } catch {
    return false;
  }
}

export default {
  name: 'svelte',
  extensions: ['.svelte', '.astro'],

  prepare(repoRoot) {
    const extra = {};
    if (fs.existsSync(path.join(repoRoot, 'src', 'lib'))) extra['$lib/*'] = ['./src/lib/*'];
    if (fs.existsSync(path.join(repoRoot, 'src', 'lib'))) extra.$lib = ['./src/lib'];
    return { extraAliases: extra };
  },

  resolveImports(file, src, ctx) {
    return resolveSpecifiers(extractSpecifiers(scriptContent(file, src)), file, ctx);
  },

  entryPoints(repoRoot, kind) {
    if (kind === 'astro-pages') {
      return walkSources(path.join(repoRoot, 'src', 'pages'), { accept: (f) => f.endsWith('.astro') });
    }
    if (kind === 'storybook-stories') {
      const dirs = ['stories', 'src'].map((d) => path.join(repoRoot, d)).filter((d) => fs.existsSync(d));
      return dirs.flatMap((d) => walkSources(d, { accept: (f) => /\.(stories|story)\.(svelte|js|ts|mjs|jsx|tsx)$/i.test(f) }));
    }
    throw new Error(`entry kind non supportato dal plugin svelte: ${kind} (attesi astro-pages | storybook-stories)`);
  },

  modeAudit(files, repoRoot) {
    const components = files.filter((f) => f.endsWith('.svelte') && !/\.(stories|story)\.svelte$/i.test(f));
    const rt = resolveCompiler(repoRoot);
    if (!rt.compiler) return { observable: false, reason: rt.reason, entries: [], total: components.length };
    const hasRunes = probeRunesMetadata(rt.compiler);
    const entries = components.map((f) => classify(f, repoRoot, rt.compiler));
    return {
      observable: true,
      authority: hasRunes ? 'compiler' : 'heuristic',
      compilerVersion: rt.version ?? null,
      ...(hasRunes ? {} : { reason: 'il compilatore non espone metadata.runes (Svelte 4): classificazione euristica, da verificare prima di fidarsi dei numeri' }),
      entries,
      total: components.length,
    };
  },

  /** Asse B: slot/snippet a livello di file (v4 `slot="x"`, v5 `{#snippet x}`). */
  usageExtras(src) {
    const slots = new Set();
    for (const s of src.matchAll(/slot=["']([^"']+)["']/g)) slots.add(s[1]);
    for (const s of src.matchAll(/\{#snippet\s+([A-Za-z_$][\w$]*)/g)) slots.add(s[1]);
    return { slots: [...slots].sort() };
  },
};
