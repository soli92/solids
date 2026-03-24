/**
 * Copies canonical UI sources from src/ into registry/solids/ for `shadcn build`.
 * Single source of truth: src/lib + src/components/ui.
 */
import { cpSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const pairs = [
  ["src/lib/utils.ts", "registry/solids/utils/utils.ts"],
  ["src/components/ui/button.tsx", "registry/solids/button/button.tsx"],
];

for (const [fromRel, toRel] of pairs) {
  const toAbs = join(ROOT, toRel);
  mkdirSync(dirname(toAbs), { recursive: true });
  cpSync(join(ROOT, fromRel), toAbs);
}

console.log("✅ registry/solids synced from src/");
