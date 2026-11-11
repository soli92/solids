// plugins/js-ts.mjs — Plugin di default: JavaScript e TypeScript.
//
// Interfaccia dei plugin (vedi tools/migration/README.md §Plugin):
//   name            string
//   extensions      string[]                       file di cui il plugin e' proprietario
//   accept?(abs)    boolean                        filtro fine (default: per estensione)
//   prepare?(root, ctx)                            contesto per repo (alias...)
//   resolveImports(file, src, ctx) -> { files[], unresolved[], externals[] }
//   entryPoints?(root, kind) -> string[]           opzionale
//   modeAudit?(files, root) -> { observable, reason?, authority?, entries[] }   opzionale
//
// Riconosce: import/export ... from, import side-effect, import() dinamico, require(),
// `import x = require()` (TS). Commenti rimossi prima del match (le stringhe restano).
// Limiti dichiarati: specifier calcolati (`import(name)`), campo `imports` (#alias) di
// package.json, alias definiti solo nel bundler (vite resolve.alias) non sono seguiti.

/** Azzera i commenti `//` e `/* *\/` preservando stringhe e template literal. */
export function stripJsComments(src) {
  let out = '';
  let state = 0; // 0 codice, 1 commento riga, 2 commento blocco, 3 stringa
  let quote = '';
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    const n = src[i + 1];
    if (state === 1) {
      if (c === '\n') {
        state = 0;
        out += '\n';
      } else out += ' ';
      continue;
    }
    if (state === 2) {
      if (c === '*' && n === '/') {
        out += '  ';
        i++;
        state = 0;
      } else out += c === '\n' ? '\n' : ' ';
      continue;
    }
    if (state === 3) {
      out += c;
      if (c === '\\' && i + 1 < src.length) {
        out += n;
        i++;
      } else if (c === quote) state = 0;
      continue;
    }
    if (c === '/' && n === '/') {
      state = 1;
      out += '  ';
      i++;
      continue;
    }
    if (c === '/' && n === '*') {
      state = 2;
      out += '  ';
      i++;
      continue;
    }
    if (c === "'" || c === '"' || c === '`') {
      state = 3;
      quote = c;
    }
    out += c;
  }
  return out;
}

const SPECIFIER_RES = [
  /\b(?:import|export)\s+(?:type\s+)?[^'"`;]*?\bfrom\s*['"]([^'"\n]+)['"]/g,
  /\bimport\s*['"]([^'"\n]+)['"]/g,
  /\bimport\s*\(\s*['"]([^'"\n]+)['"]\s*\)/g,
  /\brequire\s*\(\s*['"]([^'"\n]+)['"]\s*\)/g,
];

/** Specifier importati da un sorgente JS/TS (ordine di comparsa, senza duplicati). */
export function extractSpecifiers(src) {
  const code = stripJsComments(src);
  const found = [];
  const seen = new Set();
  for (const re of SPECIFIER_RES) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(code)) !== null) {
      if (!seen.has(m[1])) {
        seen.add(m[1]);
        found.push(m[1]);
      }
    }
  }
  return found;
}

/**
 * Risolve gli specifier con il resolver condiviso del repo (ctx.resolver).
 * @returns {{ files: string[], unresolved: string[], externals: string[] }}
 */
export function resolveSpecifiers(specs, file, ctx) {
  const files = new Set();
  const unresolved = [];
  const externals = new Set();
  for (const spec of specs) {
    const r = ctx.resolver.resolve(spec, file);
    if (r.kind === 'file') files.add(r.path);
    else if (r.kind === 'external') externals.add(r.pkg);
    else unresolved.push(spec);
  }
  return { files: [...files], unresolved, externals: [...externals] };
}

const EXTENSIONS = ['.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs'];

export default {
  name: 'js-ts',
  extensions: EXTENSIONS,
  /** I file di dichiarazione non sono codice da migrare. */
  accept(abs) {
    return !/\.d\.[cm]?ts$/.test(abs);
  },
  resolveImports(file, src, ctx) {
    return resolveSpecifiers(extractSpecifiers(src), file, ctx);
  },
};
