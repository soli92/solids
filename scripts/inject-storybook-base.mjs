/**
 * After `storybook build`, when SB_BASE is set (GitHub Pages under a subpath):
 * - Insert <base href="..."> so the manager resolves assets under /repo/.
 * - Write storybook-static/.nojekyll so Pages does not run Jekyll on the static output.
 *
 * Manual deploy: SB_BASE=/solids/ npm run build-storybook, then publish the whole storybook-static/.
 */
import fs from "node:fs";
import path from "node:path";

const raw = process.env.SB_BASE?.trim();
if (!raw) process.exit(0);

const staticDir = path.resolve(process.cwd(), "storybook-static");
fs.writeFileSync(path.join(staticDir, ".nojekyll"), "");

const href = raw.endsWith("/") ? raw : `${raw}/`;
const indexPath = path.join(staticDir, "index.html");
let html = fs.readFileSync(indexPath, "utf8");

const needle = `<base href="${href}"`;
if (html.includes(needle)) process.exit(0);

const headTag = "<head>";
const i = html.indexOf(headTag);
if (i === -1) {
  console.error("inject-storybook-base: no <head> in storybook-static/index.html");
  process.exit(1);
}

html =
  html.slice(0, i + headTag.length) +
  `\n    ${needle} />` +
  html.slice(i + headTag.length);

fs.writeFileSync(indexPath, html);
