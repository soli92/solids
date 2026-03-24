/**
 * After `storybook build`, insert <base> immediately after <head> so relative manager
 * assets resolve under GitHub Pages project URLs even when opened as /repo (no trailing slash).
 * No-op unless SB_BASE is set (e.g. SB_BASE=/solids/ in CI).
 */
import fs from "node:fs";
import path from "node:path";

const raw = process.env.SB_BASE?.trim();
if (!raw) process.exit(0);

const href = raw.endsWith("/") ? raw : `${raw}/`;
const indexPath = path.resolve(process.cwd(), "storybook-static/index.html");
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
