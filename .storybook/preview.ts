import type { Preview } from "@storybook/react";
import { themes } from "@storybook/theming";

import "../dist/css/index.css";

const STORAGE_KEY = "solids:sb:theme";

function readStoredTheme() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function writeStoredTheme(theme: string) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // ignore
  }
}

const initialTheme = readStoredTheme();

const preview: Preview = {
  globalTypes: {
    theme: {
      description: "Global theme for SoliDS docs",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: [
          { value: "light", title: "Light", icon: "circlehollow" },
          { value: "dark", title: "Dark", icon: "circle" }
        ],
        dynamicTitle: true
      }
    }
  },

  initialGlobals: {
    theme: initialTheme
  },

  parameters: {
    viewMode: "docs",
    previewTabs: { canvas: { hidden: true } },
    options: { showPanel: false },
    docs: {
      theme: initialTheme === "dark" ? themes.dark : themes.light
    }
  },

  decorators: [
    (Story, context) => {
      const raw = context.globals.theme;
      const theme = raw === "dark" ? "dark" : "light";

      // Applica tema a <html>
      document.documentElement.setAttribute("data-theme", theme);
      document.documentElement.style.colorScheme = theme;

      // ✅ Applica tema anche a <body> (necessario per Docs)
      document.body.setAttribute("data-theme", theme);
      document.body.style.colorScheme = theme;

      writeStoredTheme(theme);

      return Story();
    }
  ]
};

export default preview;
