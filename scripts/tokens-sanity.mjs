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

console.log("tokens-sanity: tutte le verifiche passate.");
