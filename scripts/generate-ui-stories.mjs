/**
 * Genera story CSF per ogni file in src/components/ui:
 * - componenti composti → demo interattive (ui-story-data.compoundStories)
 * - preset Playground → args / Controlli Storybook (ui-story-data.playgroundPresets)
 * - fallback → componente principale dedotto dagli export
 */
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { compoundStories, playgroundPresets } from "./ui-story-data.mjs";

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

function parseExports(content) {
  const m = content.match(/export\s*\{([^}]+)\}/s);
  if (!m) return [];
  return m[1]
    .split(",")
    .map((s) => s.trim().split(/\s+as\s+/)[0].trim())
    .filter(Boolean);
}

function pascalFromBase(base) {
  return base
    .split("-")
    .map((s) => s[0].toUpperCase() + s.slice(1))
    .join("");
}

function pickPrimary(base, exports) {
  const want = pascalFromBase(base);
  if (exports.includes(want)) return want;
  return exports.find(
    (n) =>
      /^[A-Z][a-zA-Z0-9]*$/.test(n) &&
      !/Variants$|Props$|Schema$/.test(n)
  );
}

function buildPlaygroundStory(base, preset) {
  const title = titleFromBase(base);
  const { component, args, argTypes, render, imports } = preset;
  const mod = `@/components/ui/${base}`;
  const importBlock = imports ?? `import { ${component} } from "${mod}";`;

  return `import * as React from "react";
${importBlock}
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/${title}",
  component: ${component},
  parameters: { layout: "centered" },
  argTypes: ${argTypes},
} satisfies Meta<typeof ${component}>;

export default meta;

type Story = StoryObj<typeof ${component}>;

export const Playground: Story = {
  args: ${args},
  render: ${render},
};
`;
}

function buildFallbackStory(base, primary) {
  const mod = `@/components/ui/${base}`;
  const title = titleFromBase(base);
  return `import * as React from "react";
import { ${primary} } from "${mod}";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/${title}",
  component: ${primary},
  parameters: { layout: "centered" },
} satisfies Meta<typeof ${primary}>;

export default meta;

type Story = StoryObj<typeof ${primary}>;

export const Playground: Story = {
  args: {},
  render: (args) => <${primary} {...args} />,
};
`;
}

function buildExportOnlyPlaceholder(base) {
  const mod = `@/components/ui/${base}`;
  const title = titleFromBase(base);
  return `import * as UI from "${mod}";
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
}

for (const f of readdirSync(uiDir).filter((x) => x.endsWith(".tsx"))) {
  const base = basename(f, ".tsx");
  let body;

  if (compoundStories[base]) {
    body = compoundStories[base];
  } else if (playgroundPresets[base]) {
    body = buildPlaygroundStory(base, playgroundPresets[base]);
  } else {
    const src = readFileSync(join(uiDir, f), "utf8");
    const exports = parseExports(src);
    const primary = pickPrimary(base, exports);
    body = primary
      ? buildFallbackStory(base, primary)
      : buildExportOnlyPlaceholder(base);
  }

  writeFileSync(join(outDir, `${base}.stories.tsx`), body, "utf8");
}

console.log("✅ UI stories generated in src/stories/ui/");
