import type { StorybookConfig } from "@storybook/react-vite";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { mergeConfig } from "vite";

const storybookDir = path.dirname(fileURLToPath(import.meta.url));

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
    /** GitHub Pages project site: set SB_BASE=/solids/ in CI */
    const base =
      process.env.SB_BASE && process.env.SB_BASE.length > 0
        ? process.env.SB_BASE
        : "/";
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
