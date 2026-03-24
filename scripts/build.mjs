/**
 * SoliDS Build Script
 * --------------------
 * Generates the `dist/` folder from `src/` sources.
 *
 * Output:
 *   dist/tokens/tokens.json          — merged token tree (base + semantic + all themes)
 *   dist/css/variables.css           — :root CSS vars from semantic (light defaults)
 *   dist/css/themes.css              — [data-theme="…"] overrides + OS dark fallback
 *   dist/css/shadcn.css              — shadcn/ui variable mapping layer
 *   dist/css/base.css                — base resets / global styles
 *   dist/css/utilities.css           — utility classes
 *   dist/css/index.css               — entrypoint that @imports all of the above
 */

import {
  mkdirSync,
  readFileSync,
  readdirSync,
  writeFileSync,
  cpSync,
  rmSync,
} from "node:fs";
import { basename, join } from "node:path";

const SRC = "src";
const DIST = "dist";

/* ── helpers ─────────────────────────────────────────────── */

const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));
const ensureDir = (p) => mkdirSync(p, { recursive: true });
const cleanDist = () => rmSync(DIST, { recursive: true, force: true });

const filterMetaVars = (pairs) => pairs.filter(([k]) => !k.startsWith("--sd-_"));

/** Segmenti JSON tipo "0.5" → "0-5" così il nome `--sd-space-0-5` è valido per i parser CSS (es. Turbopack). */
const cssVarKeySegment = (k) => String(k).replace(/\./g, "-");

/**
 * Recursively flatten a nested token object into CSS variable pairs.
 * { color: { text: { primary: "#111" } } }
 *  → [["--sd-color-text-primary", "#111"]]
 */
const flattenToCssVars = (obj, prefix = []) => {
  const out = [];
  for (const [k, v] of Object.entries(obj)) {
    if (k.startsWith("_")) continue; // skip _comment, _schema, etc.
    const path = [...prefix, k];
    if (v && typeof v === "object" && !Array.isArray(v)) {
      out.push(...flattenToCssVars(v, path));
    } else {
      const name = path.map(cssVarKeySegment).join("-");
      out.push([`--sd-${name}`, String(v)]);
    }
  }
  return out;
};

/** Render a CSS block: selector { --var: value; } */
const toBlock = (selector, pairs) =>
  `${selector} {\n${pairs.map(([n, v]) => `  ${n}: ${v};`).join("\n")}\n}\n`;

/* ── main ────────────────────────────────────────────────── */

const main = () => {
  cleanDist();
  ensureDir(join(DIST, "css"));
  ensureDir(join(DIST, "tokens"));
  ensureDir(join(DIST, "tailwind"));

  /* 1 – Read sources */
  const base = readJson(join(SRC, "tokens", "base.json"));
  const semantic = readJson(join(SRC, "tokens", "semantic.json"));

  const themesDir = join(SRC, "tokens", "themes");
  const themeFileNames = readdirSync(themesDir)
    .filter((f) => f.endsWith(".json"))
    .sort();

  /** @type {Record<string, object>} */
  const themes = {};
  for (const f of themeFileNames) {
    const name = basename(f, ".json");
    themes[name] = readJson(join(themesDir, f));
  }

  if (!themes.light || !themes.dark) {
    throw new Error("SoliDS build: themes/light.json and themes/dark.json are required.");
  }

  const light = themes.light;
  const dark = themes.dark;

  /* 2 – Merged token JSON for consumers (style-dictionary compatible) */
  const tokens = {
    $schema: "https://solids.design/tokens.schema.json",
    base,
    semantic,
    themes,
  };
  writeFileSync(
    join(DIST, "tokens", "tokens.json"),
    JSON.stringify(tokens, null, 2),
    "utf8"
  );

  /* 3 – CSS variables
   *   :root      = base tokens + semantic defaults (= light theme)
   *   :root also gets [data-theme="light"] so it can be toggled explicitly
   *   [data-theme="<name>"] = per-theme overrides (all JSON files except light, which is baked into :root)
   *   @media prefers-color-scheme: dark on :root:not([data-theme]) only — avoids clobbering fantasy/cyberpunk, etc.
   */
  const baseVars = flattenToCssVars(base);
  const semanticVars = flattenToCssVars(semantic);
  const lightVars = filterMetaVars(flattenToCssVars(light));

  const rootVars = filterMetaVars([...baseVars, ...semanticVars, ...lightVars]);

  const variablesCss =
    `/* SoliDS — CSS Variables (auto-generated, do not edit) */\n\n` +
    toBlock(":root", rootVars) +
    `\n` +
    toBlock('[data-theme="light"]', lightVars);

  let themesCss = `/* SoliDS — Theme overrides (auto-generated, do not edit) */\n\n`;
  themesCss += toBlock('[data-theme="dark"]', filterMetaVars(flattenToCssVars(dark)));

  for (const name of Object.keys(themes)) {
    if (name === "light" || name === "dark") continue;
    themesCss += `\n${toBlock(
      `[data-theme="${name}"]`,
      filterMetaVars(flattenToCssVars(themes[name]))
    )}`;
  }

  const darkFlat = filterMetaVars(flattenToCssVars(dark));
  themesCss +=
    `\n@media (prefers-color-scheme: dark) {\n` +
    `  :root:not([data-theme]) {\n` +
    darkFlat.map(([n, v]) => `    ${n}: ${v};`).join("\n") +
    `\n  }\n}\n`;

  /* 4 – index.css entrypoint */
  const indexCss =
    `/* SoliDS — Entrypoint (auto-generated, do not edit) */\n` +
    `@import "./variables.css";\n` +
    `@import "./themes.css";\n` +
    `@import "./shadcn.css";\n` +
    `@import "./base.css";\n` +
    `@import "./utilities.css";\n`;

  /* 5 – Write generated CSS */
  writeFileSync(join(DIST, "css", "variables.css"), variablesCss, "utf8");
  writeFileSync(join(DIST, "css", "themes.css"), themesCss, "utf8");
  writeFileSync(join(DIST, "css", "index.css"), indexCss, "utf8");

  /* 6 – Copy static sources */
  cpSync(join(SRC, "css", "shadcn.css"), join(DIST, "css", "shadcn.css"));
  cpSync(join(SRC, "css", "base.css"), join(DIST, "css", "base.css"));
  cpSync(join(SRC, "css", "utilities.css"), join(DIST, "css", "utilities.css"));

  cpSync(join(SRC, "tailwind", "preset.cjs"), join(DIST, "tailwind", "preset.cjs"));

  console.log("✅ SoliDS build complete!");
  console.log(`   dist/tokens/tokens.json`);
  console.log(`   dist/css/index.css (variables → themes → shadcn → base → utilities)`);
  console.log(`   dist/tailwind/preset.cjs`);
};

main();
