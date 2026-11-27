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
if (base.layout?.["touch-target-min"] !== "48px") {
  fail(`base.layout.touch-target-min atteso "48px" (M3, da 3.0.0), trovato ${JSON.stringify(base.layout)}`);
}
ok('base.layout["touch-target-min"] === "48px"');

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
ok('base.layout["touch-target-material"] === "48px" (alias del default)');

/* ── 3.0.0: default allineati a M3 (EP-002 US-003) ───────── */
if (semantic.radius["2xl"] !== "28px" || semantic.radius["3xl"] !== "32px") fail("semantic.radius 2xl/3xl attesi 28px/32px (M3)");
if (base.radius["2xl"] !== "28px" || base.radius["3xl"] !== "32px") fail("base.radius 2xl/3xl attesi 28px/32px (M3)");
for (const [name, theme] of Object.entries(themes)) {
  if (theme.radius?.["2xl"] !== theme.corner["extra-large"] || theme.radius?.["3xl"] !== theme.corner["extra-large-increased"]) {
    fail(`themes.${name}: radius 2xl/3xl devono coincidere con corner extra-large/extra-large-increased`);
  }
}
ok("radius 2xl/3xl = corner M3 extra-large/extra-large-increased su semantic e su ogni tema (28/32 su light/dark)");

const utilCss = readFileSync(join(root, "dist", "css", "utilities.css"), "utf8");
// Regola a selettore singolo (esclude i gruppi `a,\nb {` che portano solo la shorthand).
const ruleOf = (sel) => {
  const m = new RegExp(`(?<!,\\s*)(^|\\n)[ \\t]*${sel.replace(".", "\\.")}\\s*\\{([^}]*)\\}`).exec(utilCss);
  if (!m) fail(`utilities.css: manca la regola ${sel}`);
  return m[2];
};
for (const [sel, speed] of [[".sd-transition", "default"], [".sd-transition-fast", "fast"]]) {
  const r = ruleOf(sel);
  if (!r.includes(`--sd-motion-spring-${speed}-spatial-easing`) || !r.includes(`--sd-motion-spring-${speed}-effects-easing`)) fail(`${sel}: non usa le molle M3 ${speed}`);
}
const emph = ruleOf(".sd-transition-emphasized");
if (!emph.includes("--sd-motion-spring-slow-spatial-easing") || emph.includes("--sd-duration-")) fail(".sd-transition-emphasized: non usa le molle M3 slow");
if (/\.sd-(transition|link)[^{]*\{[^}]*--sd-(duration|easing)-/.test(utilCss)) fail("utilities.css: .sd-transition*/.sd-link usano ancora --sd-duration-*/--sd-easing-*");
ok(".sd-transition / -fast / -emphasized e .sd-link sulle molle M3");

const baseCss = readFileSync(join(root, "dist", "css", "base.css"), "utf8");
const reduce = baseCss.slice(baseCss.indexOf("prefers-reduced-motion: reduce"));
if (!/transition-timing-function:\s*var\(--sd-motion-spring-fast-effects-easing[^;]*!important/.test(reduce)) {
  fail("base.css: con reduced motion manca la curva unica senza overshoot");
}
ok("reduced motion: una sola curva effects, nessun overshoot sulle proprieta' rimaste");

/* ── EP-003: scala tipografica M3, scaffold, overlay ────────
 * Valori: TypeScaleTokens.kt di Compose Material 3 (token generati da Material).
 * [font, size sp, line-height sp, tracking sp, weight, weight emphasized]
 */
const m3Type = {
  "display-large": ["brand", 57, 64, -0.25, 400, 500], "display-medium": ["brand", 45, 52, 0, 400, 500],
  "display-small": ["brand", 36, 44, 0, 400, 500], "headline-large": ["brand", 32, 40, 0, 400, 500],
  "headline-medium": ["brand", 28, 36, 0, 400, 500], "headline-small": ["brand", 24, 32, 0, 400, 500],
  "title-large": ["brand", 22, 28, 0, 400, 500], "title-medium": ["plain", 16, 24, 0.15, 500, 700],
  "title-small": ["plain", 14, 20, 0.1, 500, 700], "body-large": ["plain", 16, 24, 0.5, 400, 500],
  "body-medium": ["plain", 14, 20, 0.25, 400, 500], "body-small": ["plain", 12, 16, 0.4, 400, 500],
  "label-large": ["plain", 14, 20, 0.1, 500, 700], "label-medium": ["plain", 12, 16, 0.5, 500, 700],
  "label-small": ["plain", 11, 16, 0.5, 500, 700],
};
const remOf = (v) => parseFloat(v) * 16;
const fontOf = { brand: "var(--sd-font-heading)", plain: "var(--sd-font-body)" };
for (const [name, [font, size, lh, tr, w, we]] of Object.entries(m3Type)) {
  for (const [label, t, weight] of [[name, base.typescale?.[name], w], [`emphasized.${name}`, base.typescale?.emphasized?.[name], we]]) {
    if (!t) fail(`base.typescale.${label} mancante`);
    if (t.font !== fontOf[font]) fail(`typescale.${label}.font atteso ${fontOf[font]}`);
    if (remOf(t.size) !== size || remOf(t["line-height"]) !== lh || Math.abs(remOf(t.tracking) - tr) > 1e-9 || t.weight !== String(weight)) {
      fail(`typescale.${label} diverso da M3 (${size}/${lh}/${tr}/${weight})`);
    }
    const cls = `.sd-type-${name}${label.startsWith("emphasized") ? "-emphasized" : ""}`;
    const rule = ruleOf(cls);
    if (!rule.includes(`font-family: ${fontOf[font]}`)) fail(`${cls}: font-family deve leggere ${fontOf[font]} (i temi annidati devono cambiare font)`);
  }
}
if (Object.keys(m3Type).length !== Object.keys(base.typescale).filter((k) => !k.startsWith("_") && k !== "emphasized").length) {
  fail("base.typescale: stili in piu' o in meno rispetto a M3");
}
ok("scala tipografica M3: 15 baseline + 15 emphasized con valori ufficiali e 30 utility .sd-type-*");

for (const sel of [".sd-scaffold", ".sd-scaffold-bar-top", ".sd-scaffold-bar-bottom", ".sd-scaffold-rail-start",
  ".sd-scaffold-rail-end", ".sd-scaffold-panes", ".sd-pane", ".sd-pane-fixed"]) ruleOf(sel);
const utilFlat = utilCss.replace(/\s+/g, " ");
for (const [k, v] of Object.entries(m3Breakpoints)) {
  if (k === "compact") continue;
  if (!utilFlat.includes(`@media (width < ${v}) { .sd-hide-below-${k} `)) fail(`utilities.css: .sd-hide-below-${k} non usa ${v}`);
  if (!utilFlat.includes(`@media (width >= ${v}) { .sd-hide-from-${k} `)) fail(`utilities.css: .sd-hide-from-${k} non usa ${v}`);
}
ok("scaffold M3: bars, rails, panes e visibilita' per breakpoint allineata a base.breakpoint");

const overlay = twCss.slice(twCss.indexOf("Overlay motion"));
if (/--sd-easing-|--sd-duration-/.test(overlay)) fail("tailwind.css: gli overlay usano ancora --sd-easing-*/--sd-duration-*");
if (!/\[class\*="animate-in"\] \{[^}]*--tw-ease: var\(--sd-motion-spring-fast-spatial-easing\)/.test(overlay)) fail("tailwind.css: animate-in non usa la molla spatial fast");
if (!/animate-out"\] \{[^}]*--tw-ease: var\(--sd-motion-spring-fast-effects-easing\)/.test(overlay)) fail("tailwind.css: animate-out non usa la molla effects fast");
if (!/--animate-accordion-down: accordion-down[^;]*--sd-motion-standard-fast-spatial/.test(twCss)) fail("tailwind.css: accordion non usa la molla standard");
if (!/--tw-ease:\s*var\(--sd-motion-spring-fast-effects-easing[^;]*!important/.test(reduce)) fail("base.css: con reduced motion le animazioni non hanno la curva senza overshoot");
ok("overlay: entrata spatial, uscita effects, accordion standard, reduced motion senza overshoot");

/* ── EP-004 (GAP-012): language height, drag handle, levitate, reflow ── */
// Interlinee M3 per categoria di scrittura [small, medium, large, extra-large] in pt,
// dal database token di Material (m3.material.io, _dsm/data/dsdb-m3 2026-11-19, TYPOGRAPHY).
const m3LangLH = {
  "display-large": [64, 73, 89, 120],
  "display-medium": [52, 56, 71, 99],
  "display-small": [44, 47, 57, 80],
  "headline-large": [40, 42, 50, 75],
  "headline-medium": [36, 38, 45, 66],
  "headline-small": [32, 35, 41, 59],
  "title-large": [28, 31, 36, 53],
  "title-medium": [24, 27, 31, 42],
  "title-small": [20, 23, 26, 36],
  "body-large": [24, 27, 31, 41],
  "body-medium": [20, 23, 26, 35],
  "body-small": [16, 18, 21, 30],
  "label-large": [20, 23, 26, 36],
  "label-medium": [16, 18, 21, 30],
  "label-small": [16, 18, 21, 29],
};
const cats = ["medium", "large", "extra-large"];
for (const [st, [sm, ...rest]] of Object.entries(m3LangLH)) {
  if (remOf(base.typescale[st]["line-height"]) !== sm) fail(`typescale.${st}.line-height diverso da small M3 (${sm})`);
  cats.forEach((c, i) => {
    if (remOf(base["typescale-language"]?.[c]?.[st] ?? "x") !== rest[i]) fail(`typescale-language.${c}.${st} atteso ${rest[i]}pt`);
  });
  for (const [cls, tok] of [[`.sd-type-${st}`, `--sd-typescale-${st}-line-height`], [`.sd-type-${st}-emphasized`, `--sd-typescale-emphasized-${st}-line-height`]]) {
    if (!ruleOf(cls).includes(`line-height: var(--_sd-lh-${st}, var(${tok}))`)) fail(`${cls}: line-height non legge --_sd-lh-${st}`);
  }
}
const langBlock = (sel) => { const i = utilFlat.indexOf(sel); return i < 0 ? "" : utilFlat.slice(i, utilFlat.indexOf("}", i)); };
for (const [sel, cat] of [[":lang(ja)", "medium"], [":lang(ar)", "medium"], [":lang(te)", "large"], [":lang(ur) {", "extra-large"],
  ['[data-language-height="medium"]', "medium"], ['[data-language-height="extra-large"]', "extra-large"]]) {
  const b = langBlock(sel);
  if (Object.keys(m3LangLH).some((st) => !b.includes(`--_sd-lh-${st}: var(--sd-typescale-language-${cat}-${st});`))) fail(`language height: ${sel} non mappa i 15 stili su ${cat}`);
}
if (Object.keys(m3LangLH).some((st) => !langBlock('[data-language-height="small"]').includes(`--_sd-lh-${st}: initial;`))) fail("language height: small non ripristina i valori di base");
ok("language height M3: interlinee ufficiali per 15 stili x 4 categorie, da :lang() o data-language-height");

for (const sel of [".sd-pane-handle", ".sd-pane-resizable", ".sd-pane-floating", ".sd-pane-docked"]) ruleOf(sel);
for (const [bp, v] of [["medium", "600px"], ["expanded", "840px"], ["large", "1200px"]]) {
  if (!utilFlat.includes(`@media (width < ${v}) { .sd-panes-reflow-below-${bp} { flex-direction: column; } }`)) fail(`reflow below-${bp} non usa ${v}`);
}
if (!utilFlat.includes("@media (width < 600px) { .sd-pane-adaptive") || !utilFlat.includes("@media (600px <= width < 1200px) { .sd-pane-adaptive") || !utilFlat.includes("@media (width >= 1200px) { .sd-pane-adaptive")) {
  fail(".sd-pane-adaptive: docked < 600, floating 600-1199, co-planar >= 1200");
}
for (const r of ["below-medium", "below-expanded", "below-large", "portrait"]) {
  if (!utilFlat.includes(`.sd-panes-reflow-${r} > :is(.sd-pane-fixed, .sd-pane-resizable) { flex-basis: auto; }`)) {
    fail(`reflow ${r}: in colonna i pannelli fissi e ridimensionabili devono perdere la base (diventerebbe un'altezza)`);
  }
}
const scaffoldJs = join(root, "dist", "scaffold", "index.js");
if (!existsSync(scaffoldJs) || !existsSync(join(root, "dist", "scaffold", "index.d.ts"))) fail("dist/scaffold: manca index.js o index.d.ts");
ok("scaffold: drag handle (dist/scaffold con tipi), pannelli floating/docked/adaptive, reflow ai breakpoint");

/* ── Contrasto (WCAG 2.2): intent-*-text come testo, border-strong come componente ── */
const lin = (x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);
const lumOf = (hex) => {
  let h = hex.replace("#", "");
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  const [r, g, b] = [0, 2, 4].map((i) => lin(parseInt(h.slice(i, i + 2), 16) / 255));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => { const [x, y] = [lumOf(a), lumOf(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
for (const [name, theme] of Object.entries(themes)) {
  const c = (grp, key) => theme.color?.[grp]?.[key] ?? semantic.color[grp][key];
  const bgs = ["canvas", "surface", "elevated"].map((k) => c("bg", k));
  for (const it of ["success", "warning", "danger", "info"]) {
    const v = c("intent", `${it}-text`);
    if (!v) fail(`themes.${name}: manca color.intent.${it}-text`);
    const w = Math.min(...bgs.map((b) => contrast(v, b)));
    if (w < 4.5) fail(`themes.${name}: intent.${it}-text ${v} a ${w.toFixed(2)}:1 (< 4.5:1 su un fondo)`);
  }
  const bs = Math.min(...bgs.map((b) => contrast(c("border", "strong"), b)));
  if (bs < 3) fail(`themes.${name}: border.strong a ${bs.toFixed(2)}:1 (< 3:1, WCAG 1.4.11)`);
}
ok(`contrasto: intent-*-text >= 4.5:1 e border-strong >= 3:1 su canvas/surface/elevated in ${Object.keys(themes).length} temi`);

/* ── Spessori di bordo e focus (richiesta della plancia, 3.4.0) ── */
const bw = { none: "0px", thin: "1px", medium: "2px", thick: "3px" };
for (const [k, v] of Object.entries(bw)) if (base["border-width"]?.[k] !== v) fail(`base.border-width.${k} atteso ${v}`);
if (base["focus-indicator"]?.thickness !== "3px" || base["focus-indicator"]?.["outer-offset"] !== "2px") fail("base.focus-indicator: thickness/outer-offset attesi 3px/2px (M3)");
for (const [file, css] of [["utilities.css", utilCss], ["base.css", baseCss]]) {
  if (/(border(-top|-bottom)?|outline):\s*\d+px\s+solid/.test(css) || /outline-offset:\s*-?\d+px/.test(css)) fail(`${file}: spessore di bordo o di focus scritto a mano invece del token`);
}
if (!baseCss.includes("outline: var(--sd-focus-indicator-thickness) solid") || !baseCss.includes("outline-offset: var(--sd-focus-indicator-outer-offset)")) fail("base.css: il focus ring non usa --sd-focus-indicator-*");
for (const w of ["thin", "medium", "thick"]) ruleOf(`.sd-border-w-${w}`);
ok("border-width 0/1/2/3px e focus-indicator M3 3px/2px usati dal CSS; nessuno spessore scritto a mano");

const license = readFileSync(join(root, "LICENSE"), "utf8");
if (!license.startsWith("MIT License") || !/Copyright \(c\) \d{4} \S+/.test(license)) fail("LICENSE: testo MIT con anno e titolare mancante");
ok("LICENSE: testo MIT con anno e titolare");

console.log("tokens-sanity: tutte le verifiche passate.");
