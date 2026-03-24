/**
 * SoliDS Build Script
 * --------------------
 * Generates the `dist/` folder from `src/` sources.
 *
 * Output:
 *   dist/tokens/tokens.json          — merged token tree (base + semantic + themes)
 *   dist/css/variables.css           — :root CSS vars from semantic (light defaults)
 *   dist/css/themes.css              — [data-theme="dark"] overrides
 *   dist/css/shadcn.css              — shadcn/ui variable mapping layer
 *   dist/css/base.css                — base resets / global styles
 *   dist/css/utilities.css           — utility classes
 *   dist/css/index.css               — entrypoint that @imports all of the above
 */

import { mkdirSync, readFileSync, writeFileSync, cpSync, rmSync } from "node:fs";
import { join } from "node:path";

const SRC  = "src";
const DIST = "dist";

/* ── helpers ─────────────────────────────────────────────── */

const readJson  = (p)   => JSON.parse(readFileSync(p, "utf8"));
const ensureDir = (p)   => mkdirSync(p, { recursive: true });
const cleanDist = ()    => rmSync(DIST, { recursive: true, force: true });

/**
 * Recursively flatten a nested token object into CSS variable pairs.
 * { color: { text: { primary: "#111" } } }
 *  → [["--sd-color-text-primary", "#111"]]
 */
const flattenToCssVars = (obj, prefix = []) => {
  const out = [];
  for (const [k, v] of Object.entries(obj)) {
    if (k.startsWith("_")) continue;               // skip _comment, _schema, etc.
    const path = [...prefix, k];
    if (v && typeof v === "object" && !Array.isArray(v)) {
      out.push(...flattenToCssVars(v, path));
    } else {
      out.push([`--sd-${path.join("-")}`, String(v)]);
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

  /* 1 – Read sources */
  const base     = readJson(join(SRC, "tokens", "base.json"));
  const semantic = readJson(join(SRC, "tokens", "semantic.json"));
  const light    = readJson(join(SRC, "tokens", "themes", "light.json"));
  const dark     = readJson(join(SRC, "tokens", "themes",  "dark.json"));

  /* 2 – Merged token JSON for consumers (style-dictionary compatible) */
  const tokens = {
    $schema: "https://solids.design/tokens.schema.json",
    base,
    semantic,
    themes: { light, dark },
  };
  writeFileSync(
    join(DIST, "tokens", "tokens.json"),
    JSON.stringify(tokens, null, 2),
    "utf8"
  );

  /* 3 – CSS variables
   *   :root      = base tokens + semantic defaults (= light theme)
   *   :root also gets [data-theme="light"] so it can be toggled explicitly
   *   [data-theme="dark"] = dark overrides
   *   @media prefers-color-scheme: dark = same as data-theme="dark" for system-level
   */
  const baseVars     = flattenToCssVars(base);
  const semanticVars = flattenToCssVars(semantic);
  const lightVars    = flattenToCssVars(light);
  const darkVars     = flattenToCssVars(dark);

  // Combine: base → semantic → light for the default :root
  const rootVars = [...baseVars, ...semanticVars, ...lightVars].filter(
    ([k]) => !k.startsWith("--sd-_")  // strip comment keys
  );

  const variablesCss =
    `/* SoliDS — CSS Variables (auto-generated, do not edit) */\n\n` +
    toBlock(":root", rootVars) +
    `\n` +
    toBlock('[data-theme="light"]', lightVars.filter(([k]) => !k.startsWith("--sd-_")));

  const themesCss =
    `/* SoliDS — Dark Theme (auto-generated, do not edit) */\n\n` +
    toBlock('[data-theme="dark"]', darkVars.filter(([k]) => !k.startsWith("--sd-_"))) +
    `\n` +
    `@media (prefers-color-scheme: dark) {\n` +
    `  :root:not([data-theme="light"]) {\n` +
    darkVars.filter(([k]) => !k.startsWith("--sd-_")).map(([n, v]) => `    ${n}: ${v};`).join("\n") +
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
  writeFileSync(join(DIST, "css", "themes.css"),    themesCss,    "utf8");
  writeFileSync(join(DIST, "css", "index.css"),     indexCss,     "utf8");

  /* 6 – Copy static sources */
  cpSync(join(SRC, "css", "shadcn.css"),    join(DIST, "css", "shadcn.css"));
  cpSync(join(SRC, "css", "base.css"),      join(DIST, "css", "base.css"));
  cpSync(join(SRC, "css", "utilities.css"), join(DIST, "css", "utilities.css"));

  console.log("✅ SoliDS build complete!");
  console.log(`   dist/tokens/tokens.json`);
  console.log(`   dist/css/index.css (variables → themes → shadcn → base → utilities)`);
};

main();
