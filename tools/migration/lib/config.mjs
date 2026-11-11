// config.mjs — Lettura del blocco `code_migration:` di factory.config.yaml + parser CLI.
//
// Nessuna dipendenza npm: si legge un sottoinsieme di YAML sufficiente al blocco
// (mappe annidate per indentazione, scalari, liste inline `[a, b]`). Un blocco assente
// non e' un errore: valgono i default. La precedenza e' flag CLI > config > default.

import fs from 'node:fs';
import path from 'node:path';

export const DEFAULTS = Object.freeze({
  enabled: false,
  artifacts_home: 'migration',
  verdict_reject_gate: 'human',
  default_plugin: 'js-ts',
  join_by: 'path',
  library_package: null,
  parity_threshold: 0.95,
  debt_registry: null, // default per slug: <artifacts_home>/<slug-target>/debt-registry.md
});

function scalar(raw) {
  const v = raw.trim();
  if (v === '' || v === '~' || v === 'null') return null;
  if (v === 'true') return true;
  if (v === 'false') return false;
  if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
  if (/^\[.*\]$/.test(v)) {
    const inner = v.slice(1, -1).trim();
    return inner ? inner.split(',').map((s) => scalar(s)) : [];
  }
  const q = /^(['"])(.*)\1$/.exec(v);
  return q ? q[2] : v;
}

function stripComment(line) {
  let inS = false;
  let inD = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === "'" && !inD) inS = !inS;
    else if (c === '"' && !inS) inD = !inD;
    else if (c === '#' && !inS && !inD && (i === 0 || /\s/.test(line[i - 1]))) return line.slice(0, i);
  }
  return line;
}

/**
 * Estrae un blocco top-level da un testo YAML come oggetto (sottoinsieme).
 * @param {string} text
 * @param {string} key
 * @returns {object|null}
 */
export function readYamlBlock(text, key) {
  const lines = text.split(/\r?\n/);
  const start = lines.findIndex((l) => new RegExp(`^${key}:\\s*(#.*)?$`).test(l));
  if (start === -1) return null;
  const root = {};
  const stack = [{ indent: -1, obj: root }];
  for (let i = start + 1; i < lines.length; i++) {
    const line = stripComment(lines[i]);
    if (line.trim() === '') continue;
    const indent = line.length - line.trimStart().length;
    if (indent === 0) break; // fine del blocco
    const m = /^\s*([A-Za-z0-9_\-]+):\s*(.*)$/.exec(line);
    if (!m) continue; // liste a trattino e forme non supportate: ignorate
    while (stack.length > 1 && indent <= stack[stack.length - 1].indent) stack.pop();
    const parent = stack[stack.length - 1].obj;
    if (m[2].trim() === '') {
      parent[m[1]] = {};
      stack.push({ indent, obj: parent[m[1]] });
    } else {
      parent[m[1]] = scalar(m[2]);
    }
  }
  return root;
}

/**
 * Config risolta della capability.
 * @param {string} factoryRoot
 * @returns {{config: object, source: string}}
 */
export function loadMigrationConfig(factoryRoot) {
  const file = path.join(factoryRoot, 'factory.config.yaml');
  let block = null;
  try {
    block = readYamlBlock(fs.readFileSync(file, 'utf-8'), 'code_migration');
  } catch {
    block = null;
  }
  return {
    config: { ...DEFAULTS, ...(block ?? {}) },
    source: block ? 'factory.config.yaml#code_migration' : 'default (blocco code_migration assente)',
  };
}

/** Parser minimale: `--flag value`, `--flag=value`, booleani, posizionali. */
export function parseArgs(argv, booleans = []) {
  const flags = {};
  const positional = [];
  const bools = new Set(booleans);
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const eq = a.indexOf('=');
      if (eq !== -1) {
        flags[a.slice(2, eq)] = a.slice(eq + 1);
        continue;
      }
      const name = a.slice(2);
      const next = argv[i + 1];
      if (!bools.has(name) && next !== undefined && !next.startsWith('--')) {
        flags[name] = next;
        i++;
      } else {
        flags[name] = true;
      }
    } else if (a === '-h') {
      flags.help = true;
    } else {
      positional.push(a);
    }
  }
  return { flags, positional };
}

/** True se il modulo e' eseguito direttamente da riga di comando. */
export function isMain(metaUrl) {
  if (!process.argv[1]) return false;
  try {
    return fs.realpathSync(process.argv[1]) === fs.realpathSync(new URL(metaUrl));
  } catch {
    return false;
  }
}
