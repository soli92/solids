import type { StorybookConfig } from "@storybook/react-vite";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { mergeConfig } from "vite";

const storybookDir = path.dirname(fileURLToPath(import.meta.url));

/** GitHub Pages project site: set SB_BASE=/solids/ in CI */
function storybookBase(): string | null {
  const raw = process.env.SB_BASE?.trim();
  if (!raw) return null;
  return raw.endsWith("/") ? raw : `${raw}/`;
}

const sbBase = storybookBase();

const config: StorybookConfig = {
  framework: "@storybook/react-vite",

  stories: ["../docs/**/*.mdx", "../src/**/*.stories.@(js|jsx|ts|tsx|mdx)"],

  addons: ["@storybook/addon-docs", "@storybook/addon-essentials"],

  typescript: {
    reactDocgen: false,
  },

  docs: {
    autodocs: false,
  },

  async viteFinal(config) {
    const rootDir = path.resolve(storybookDir, "..");
    const base = sbBase ?? "/";
    return mergeConfig(config, {
      base,
      resolve: {
        alias: {
          "@": path.resolve(rootDir, "src"),
        },
      },
    });
  },
};

export default config;
