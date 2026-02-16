import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  framework: "@storybook/react-vite",

  stories: [
    "../docs/**/*.mdx"
  ],

  addons: [
    "@storybook/addon-docs",
    "@storybook/addon-essentials"
  ],

  typescript: {
    reactDocgen: false
  },


  docs: {
    autodocs: false
  }
};

export default config;
