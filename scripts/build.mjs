import { mkdirSync, readFileSync, writeFileSync, cpSync, rmSync } from "node:fs";
import { join } from "node:path";

const SRC = "src";
const DIST = "dist";

const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));

const ensureDir = (p) => mkdirSync(p, { recursive: true });

const cleanDist = () => rmSync(DIST, { recursive: true, force: true });

const flattenToCssVars = (obj, prefix = []) => {
  const out = [];
  for (const [k, v] of Object.entries(obj)) {
    const path = [...prefix, k];
    if (v && typeof v === "object" && !Array.isArray(v)) {
      out.push(...flattenToCssVars(v, path));
    } else {
      const name = `--sd-${path.join("-")}`;
      out.push([name, String(v)]);
    }
  }
  return out;
};

const main = () => {
  cleanDist();
  ensureDir(join(DIST, "css"));
  ensureDir(join(DIST, "tokens"));

  const base = readJson(join(SRC, "tokens", "base.json"));
  const semantic = readJson(join(SRC, "tokens", "semantic.json"));
  const light = readJson(join(SRC, "tokens", "themes", "light.json"));
  const dark = readJson(join(SRC, "tokens", "themes", "dark.json"));

  const tokens = {
    $schema: "https://example.com/solids-tokens.schema.json",
    base,
    semantic,
    themes: { light, dark }
  };

  writeFileSync(join(DIST, "tokens", "tokens.json"), JSON.stringify(tokens, null, 2), "utf8");

  // CSS variables: usiamo semantic + theme light come default
  const defaultVars = flattenToCssVars({ ...semantic, ...light });
  const darkVars = flattenToCssVars({ ...semantic, ...dark });

  const toBlock = (selector, pairs) =>
    `${selector}{\n${pairs.map(([n, val]) => `  ${n}: ${val};`).join("\n")}\n}\n`;

  const variablesCss =
    `/* SoliDS – generated */\n` +
    toBlock(":root", defaultVars);

  const themesCss =
    `/* SoliDS – generated themes */\n` +
    toBlock('[data-theme="dark"]', darkVars);

  // Entry-point CSS that imports everything in the correct order
  const indexCss =
    `/* SoliDS – entrypoint */\n` +
    `@import "./variables.css";\n` +
    `@import "./themes.css";\n` +
    `@import "./base.css";\n` +
    `@import "./utilities.css";\n`;

  writeFileSync(join(DIST, "css", "index.css"), indexCss, "utf8");

  writeFileSync(join(DIST, "css", "variables.css"), variablesCss, "utf8");
  writeFileSync(join(DIST, "css", "themes.css"), themesCss, "utf8");

  // Copy base + utilities
  cpSync(join(SRC, "css", "base.css"), join(DIST, "css", "base.css"));
  cpSync(join(SRC, "css", "utilities.css"), join(DIST, "css", "utilities.css"));
};

main();
