/**
 * Verifiche leggere su dist/tokens/tokens.json dopo `npm run build`.
 * Non sostituisce build-storybook; evita regressioni su token/layout/font.
 */
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const tokensPath = join(root, "dist", "tokens", "tokens.json");
const variablesPath = join(root, "dist", "css", "variables.css");
const workspaceNormalizedManifestPath = join(
  root,
  "dist",
  "brand-assets",
  "workspace-icons-normalized",
  "manifest.json"
);
const workspaceNormalizedIndexPath = join(
  root,
  "dist",
  "brand-assets",
  "workspace-icons-normalized",
  "index.json"
);
const workspaceNormalizedIndexTsPath = join(
  root,
  "dist",
  "brand-assets",
  "workspace-icons-normalized",
  "index.d.ts"
);
const soliCategoryIconsIndexPath = join(
  root,
  "dist",
  "brand-assets",
  "soli-category-icons",
  "index.json"
);

function fail(msg) {
  console.error(`tokens-sanity: FAIL — ${msg}`);
  process.exit(1);
}

function ok(msg) {
  console.log(`tokens-sanity: OK — ${msg}`);
}

if (!existsSync(tokensPath)) fail(`manca ${tokensPath} — eseguire prima npm run build`);

const raw = readFileSync(tokensPath, "utf8");
let tokens;
try {
  tokens = JSON.parse(raw);
} catch {
  fail("tokens.json non è JSON valido");
}

const { base, semantic, themes } = tokens;
if (!base || !semantic || !themes) fail("struttura tokens: servono base, semantic, themes");

// Base: layout touch target + durata emphasized (a11y / motion)
if (base.layout?.["touch-target-min"] !== "44px") {
  fail(`base.layout.touch-target-min atteso "44px", trovato ${JSON.stringify(base.layout)}`);
}
ok('base.layout["touch-target-min"] === "44px"');

if (base.duration?.emphasized !== "350ms") {
  fail(`base.duration.emphasized atteso "350ms", trovato ${JSON.stringify(base.duration?.emphasized)}`);
}
ok('base.duration.emphasized === "350ms"');

// Semantic: font stack moderni
for (const key of ["body", "heading", "mono"]) {
  const v = semantic.font?.[key];
  if (typeof v !== "string" || v.length < 10) fail(`semantic.font.${key} mancante o troppo corto`);
}
if (!String(semantic.font.body).includes("Inter")) fail("semantic.font.body deve includere Inter");
if (!String(semantic.font.heading).includes("DM Sans")) fail("semantic.font.heading deve includere DM Sans");
if (!String(semantic.font.mono).includes("JetBrains Mono")) fail("semantic.font.mono deve includere JetBrains Mono");
ok("semantic.font body/heading/mono con Inter, DM Sans, JetBrains Mono");

// Temi nominati + font dove previsto
const requiredThemes = [
  "light",
  "dark",
  "fantasy",
  "cyberpunk",
  "90s-party",
  "steampunk",
  "captain-america",
  "ichigo",
  "inuyasha",
  "sasuke",
  "vegeta",
  "zoro",
];
for (const name of requiredThemes) {
  if (!themes[name]) fail(`manca themes.${name}`);
}
ok(`themes contiene tutti i ${requiredThemes.length} temi attesi`);

for (const t of ["light", "dark"]) {
  const f = themes[t].font;
  if (!f?.body?.includes("Inter")) fail(`themes.${t}.font.body deve includere Inter`);
}
ok("light/dark.theme.font.body include Inter");

if (!themes.fantasy.font?.body?.includes("Source Serif 4")) {
  fail("themes.fantasy.font.body deve includere Source Serif 4");
}
ok("fantasy.font.body include Source Serif 4");

if (!themes.cyberpunk.font?.body?.includes("Space Grotesk")) {
  fail("themes.cyberpunk.font.body deve includere Space Grotesk");
}
ok("cyberpunk.font.body include Space Grotesk");

// CSS generato: variabili chiave
if (!existsSync(variablesPath)) fail(`manca ${variablesPath}`);
const css = readFileSync(variablesPath, "utf8");
for (const needle of [
  "--sd-layout-touch-target-min:",
  "--sd-duration-emphasized:",
  "--sd-font-body:",
]) {
  if (!css.includes(needle)) fail(`variables.css non contiene ${needle}`);
}
ok("variables.css contiene touch-target-min, duration-emphasized, font-body");

// Brand assets centralizzati (workspace-icons-normalized)
if (!existsSync(workspaceNormalizedManifestPath)) {
  fail(`manca ${workspaceNormalizedManifestPath}`);
}
if (!existsSync(workspaceNormalizedIndexPath)) {
  fail(`manca ${workspaceNormalizedIndexPath}`);
}
if (!existsSync(workspaceNormalizedIndexTsPath)) {
  fail(`manca ${workspaceNormalizedIndexTsPath}`);
}
ok("workspace-icons-normalized: manifest/index/index.d.ts presenti");

let workspaceManifest;
let workspaceIndex;
try {
  workspaceManifest = JSON.parse(readFileSync(workspaceNormalizedManifestPath, "utf8"));
  workspaceIndex = JSON.parse(readFileSync(workspaceNormalizedIndexPath, "utf8"));
} catch {
  fail("workspace-icons-normalized manifest/index non sono JSON validi");
}

if (!Array.isArray(workspaceManifest.items) || workspaceManifest.items.length === 0) {
  fail("workspace-icons-normalized manifest.items deve contenere almeno un asset");
}
if (workspaceManifest.count !== workspaceManifest.items.length) {
  fail("workspace-icons-normalized manifest.count non coincide con items.length");
}
for (const item of workspaceManifest.items) {
  if (typeof item.normalized !== "string" || !item.normalized.startsWith("soli-icon-")) {
    fail(`nome normalizzato non valido: ${JSON.stringify(item)}`);
  }
}
ok("workspace-icons-normalized manifest coerente e naming soli-icon-* valido");

const expectedCategories = ["app-icon", "apple-touch", "favicon", "logo", "symbol"];
for (const category of expectedCategories) {
  if (!workspaceIndex.categories?.[category]) {
    fail(`workspace-icons-normalized index: categoria mancante "${category}"`);
  }
}
ok("workspace-icons-normalized index contiene tutte le categorie attese");

// Soli category icons (1 asset per categoria, svg+png)
if (!existsSync(soliCategoryIconsIndexPath)) {
  fail(`manca ${soliCategoryIconsIndexPath}`);
}
let soliCategoryIndex;
try {
  soliCategoryIndex = JSON.parse(readFileSync(soliCategoryIconsIndexPath, "utf8"));
} catch {
  fail("soli-category-icons index.json non è JSON valido");
}
const requiredSoliCategories = ["app-icon", "apple-touch", "favicon", "logo", "symbol"];
for (const category of requiredSoliCategories) {
  const entry = soliCategoryIndex.categories?.[category];
  if (!entry?.svg || !entry?.png) {
    fail(`soli-category-icons: entry mancante o incompleto per categoria "${category}"`);
  }
  if (!existsSync(join(root, "dist", "brand-assets", "soli-category-icons", entry.svg))) {
    fail(`soli-category-icons: file svg mancante per "${category}"`);
  }
  if (!existsSync(join(root, "dist", "brand-assets", "soli-category-icons", entry.png))) {
    fail(`soli-category-icons: file png mancante per "${category}"`);
  }
}
ok("soli-category-icons contiene svg+png per tutte le categorie attese");

/* ── Material 3 Expressive (EP-002) ─────────────────────────
 * Valori ufficiali da m3.material.io (stato 2026-11): spaziatura, breakpoint,
 * scala corner, conversione molle → curve per il web, target 48dp.
 */
const m3Space = { 0: 0, 25: 2, 50: 4, 75: 6, 100: 8, 125: 10, 150: 12, 175: 14, 200: 16, 250: 20,
  300: 24, 400: 32, 450: 36, 500: 40, 600: 48, 700: 56, 800: 64, 900: 72 };
for (const [n, v] of Object.entries(m3Space)) {
  if (base.measurement?.[`space${n}`] !== `${v}px`) fail(`base.measurement.space${n} atteso ${v}px`);
  if (v !== (8 * Number(n)) / 100) fail(`space${n}: il valore non e' 8dp x ${Number(n) / 100}`);
}
if (Object.keys(base.measurement).length !== Object.keys(m3Space).length) fail("base.measurement: token in piu' o in meno rispetto a M3");
ok("base.measurement: 18 token M3 space0..space900 (space100 = 8px)");

const m3Breakpoints = { compact: "0px", medium: "600px", expanded: "840px", large: "1200px", "extra-large": "1600px" };
for (const [k, v] of Object.entries(m3Breakpoints)) {
  if (base.breakpoint?.[k] !== v) fail(`base.breakpoint.${k} atteso ${v}`);
}
const twCss = readFileSync(join(root, "dist", "css", "tailwind.css"), "utf8");
for (const [k, v] of Object.entries(m3Breakpoints)) {
  if (k === "compact") continue;
  if (!twCss.includes(`--breakpoint-${k}: ${v};`)) fail(`tailwind.css: --breakpoint-${k} non allineato a base.breakpoint (${v})`);
}
ok("breakpoint M3 600/840/1200/1600 in base.json e varianti Tailwind v4 allineate");

const cornerSteps = ["none", "extra-small", "small", "medium", "large", "large-increased",
  "extra-large", "extra-large-increased", "extra-extra-large", "full"];
const m3Corner = ["0px", "4px", "8px", "12px", "16px", "20px", "28px", "32px", "48px", "9999px"];
const checkCorner = (label, corner, exact) => {
  if (!corner) fail(`${label}: manca il blocco corner`);
  const vals = cornerSteps.map((s) => {
    if (!(s in corner)) fail(`${label}: corner.${s} mancante`);
    return parseFloat(corner[s]);
  });
  for (let i = 1; i < vals.length; i++) {
    if (!(vals[i] > vals[i - 1])) fail(`${label}: corner non strettamente crescente a ${cornerSteps[i]}`);
  }
  if (exact && cornerSteps.some((s, i) => corner[s] !== m3Corner[i])) fail(`${label}: corner diverso dalla scala M3`);
};
checkCorner("semantic", semantic.corner, true);
for (const [name, theme] of Object.entries(themes)) {
  checkCorner(`themes.${name}`, theme.corner, name === "light" || name === "dark");
  const r = theme.radius ?? semantic.radius;
  for (const [step, key] of [["small", "sm"], ["medium", "md"], ["large", "lg"], ["large-increased", "xl"]]) {
    if (theme.corner[step] !== r[key]) fail(`themes.${name}: corner.${step} deve coincidere con radius.${key}`);
  }
}
ok(`corner M3 a 10 gradi: valori esatti su semantic/light/dark, monotono e coerente con radius su ${Object.keys(themes).length} temi`);

const m3Curves = {
  expressive: { fast: ["0.42, 1.67, 0.21, 0.90", 350, "0.31, 0.94, 0.34, 1.00", 150],
    default: ["0.38, 1.21, 0.22, 1.00", 500, "0.34, 0.80, 0.34, 1.00", 200],
    slow: ["0.39, 1.29, 0.35, 0.98", 650, "0.34, 0.88, 0.34, 1.00", 300] },
  standard: { fast: ["0.27, 1.06, 0.18, 1.00", 350, "0.31, 0.94, 0.34, 1.00", 150],
    default: ["0.27, 1.06, 0.18, 1.00", 500, "0.34, 0.80, 0.34, 1.00", 200],
    slow: ["0.27, 1.06, 0.18, 1.00", 750, "0.34, 0.88, 0.34, 1.00", 300] },
};
for (const [scheme, speeds] of Object.entries(m3Curves)) {
  for (const [speed, [se, sd, ee, ed]] of Object.entries(speeds)) {
    const m = base.motion?.[scheme]?.[speed];
    if (m?.spatial?.easing !== `cubic-bezier(${se})` || m?.spatial?.duration !== `${sd}ms`) fail(`base.motion.${scheme}.${speed}.spatial diverso da M3`);
    if (m?.effects?.easing !== `cubic-bezier(${ee})` || m?.effects?.duration !== `${ed}ms`) fail(`base.motion.${scheme}.${speed}.effects diverso da M3`);
    const alias = semantic.motion?.spring?.[speed];
    for (const kind of ["spatial", "effects"]) {
      for (const prop of ["easing", "duration"]) {
        const want = `var(--sd-motion-expressive-${speed}-${kind}-${prop})`;
        if (alias?.[kind]?.[prop] !== want) fail(`semantic.motion.spring.${speed}.${kind}.${prop} deve puntare allo schema expressive`);
      }
    }
  }
}
const themesCssText = readFileSync(join(root, "dist", "css", "themes.css"), "utf8");
if (!/\[data-motion="standard"\] \{[^}]*--sd-motion-spring-fast-spatial-easing: var\(--sd-motion-standard-fast-spatial-easing\)/.test(themesCssText)) {
  fail('themes.css: manca il blocco [data-motion="standard"]');
}
ok('motion M3: 12 curve ufficiali, alias spring su expressive, [data-motion="standard"] generato');

if (base.layout?.["touch-target-material"] !== "48px") fail("base.layout.touch-target-material atteso 48px");
ok('base.layout["touch-target-material"] === "48px" (default 44px invariato)');

console.log("tokens-sanity: tutte le verifiche passate.");
