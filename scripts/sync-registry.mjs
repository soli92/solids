/**
 * Mirrors src/lib, src/hooks, src/components/ui → registry/solids/*
 * and writes registry.json (solids-utils, solids-button, solids-ui block).
 */
import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const REG = join(ROOT, "registry", "solids");

/* reset registry/solids (rebuild from src) */
rmSync(REG, { recursive: true, force: true });
mkdirSync(join(REG, "utils"), { recursive: true });

cpSync(join(ROOT, "src", "lib", "utils.ts"), join(REG, "utils", "utils.ts"));

const hooksSrc = join(ROOT, "src", "hooks");
const hooksDest = join(REG, "hooks");
const hookFiles = [];
if (existsSync(hooksSrc)) {
  mkdirSync(hooksDest, { recursive: true });
  for (const f of readdirSync(hooksSrc)) {
    cpSync(join(hooksSrc, f), join(hooksDest, f));
    hookFiles.push({ path: `registry/solids/hooks/${f}`, type: "registry:hook" });
  }
}

const uiSrc = join(ROOT, "src", "components", "ui");
for (const f of readdirSync(uiSrc).filter((x) => x.endsWith(".tsx"))) {
  const name = basename(f, ".tsx");
  const dir = join(REG, name);
  mkdirSync(dir, { recursive: true });
  cpSync(join(uiSrc, f), join(dir, f));
}

const uiNpm = JSON.parse(
  readFileSync(join(ROOT, "scripts", "solids-ui-npm-deps.json"), "utf8")
);
const deps = Object.entries(uiNpm).map(([name, range]) => `${name}@${range}`);

const uiFiles = readdirSync(uiSrc)
  .filter((x) => x.endsWith(".tsx"))
  .map((f) => ({
    path: `registry/solids/${basename(f, ".tsx")}/${f}`,
    type: "registry:ui",
  }));

const iconsSrc = join(ROOT, "src", "icons");
const iconFiles = [];
if (existsSync(iconsSrc)) {
  const iconsDest = join(REG, "icons");
  mkdirSync(iconsDest, { recursive: true });
  for (const f of readdirSync(iconsSrc)) {
    if (f.endsWith(".ts") || f.endsWith(".tsx")) {
      cpSync(join(iconsSrc, f), join(iconsDest, f));
      iconFiles.push({ path: `registry/solids/icons/${f}`, type: "registry:lib" });
    }
  }
}

const blockFiles = [...hookFiles, ...uiFiles];

const registry = {
  $schema: "https://ui.shadcn.com/schema/registry.json",
  name: "solids",
  homepage: "https://github.com/soli92/solids",
  items: [
    {
      name: "solids-utils",
      type: "registry:lib",
      title: "SoliDS utils",
      description: "Helper cn() (clsx + tailwind-merge).",
      dependencies: ["clsx", "tailwind-merge"],
      files: [{ path: "registry/solids/utils/utils.ts", type: "registry:lib" }],
    },
    {
      name: "solids-button",
      type: "registry:ui",
      title: "SoliDS Button",
      description: "Solo Button (Radix Slot + CVA).",
      dependencies: ["@radix-ui/react-slot", "class-variance-authority"],
      registryDependencies: ["@solids/solids-utils"],
      files: [{ path: "registry/solids/button/button.tsx", type: "registry:ui" }],
    },
    {
      name: "solids-icons",
      type: "registry:lib",
      title: "SoliDS — icone SVG",
      description:
        "Set di icone stroke allineate ai token `--sd-color-icon-*` (varianti default, muted, primary, on-primary). Richiede @solids/solids-utils.",
      registryDependencies: ["@solids/solids-utils"],
      dependencies: ["react"],
      files: iconFiles,
    },
    {
      name: "solids-ui",
      type: "registry:block",
      title: "SoliDS — kit shadcn/ui completo",
      description:
        "Tutti i componenti UI + hooks installabili in un colpo. Richiede @solids/solids-utils. Dipendenze npm come da package.json del DS.",
      registryDependencies: ["@solids/solids-utils"],
      dependencies: deps,
      files: blockFiles,
    },
  ],
};

writeFileSync(join(ROOT, "registry.json"), JSON.stringify(registry, null, 2), "utf8");

console.log("✅ registry/solids mirrored from src/ + registry.json written");
