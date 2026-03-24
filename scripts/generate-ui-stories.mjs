/**
 * One CSF file per component in src/components/ui for Storybook navigation.
 */
import { mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const uiDir = join(ROOT, "src", "components", "ui");
const outDir = join(ROOT, "src", "stories", "ui");
mkdirSync(outDir, { recursive: true });

function titleFromBase(base) {
  return base
    .split("-")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");
}

for (const f of readdirSync(uiDir).filter((x) => x.endsWith(".tsx"))) {
  const base = basename(f, ".tsx");
  const title = titleFromBase(base);
  const mod = `@/components/ui/${base}`;
  const body = `import * as UI from "${mod}";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/${title}",
  parameters: { layout: "centered" },
} satisfies Meta;

export default meta;

export const Esportazioni: StoryObj = {
  render: () => (
    <div className="max-w-md rounded-lg border border-border bg-card p-4 text-card-foreground shadow-sm">
      <p className="mb-2 font-mono text-xs text-muted-foreground">${mod}</p>
      <p className="text-sm text-muted-foreground">
        Esportazioni:{" "}
        <span className="font-medium text-foreground">
          {Object.keys(UI).join(", ")}
        </span>
      </p>
    </div>
  ),
};
`;
  writeFileSync(join(outDir, `${base}.stories.tsx`), body, "utf8");
}

console.log("✅ UI stories generated in src/stories/ui/");
