import * as React from "react";
import type { Preview } from "@storybook/react";
import { themes } from "@storybook/theming";

import { Toaster } from "../src/components/ui/toaster";
import { TooltipProvider } from "../src/components/ui/tooltip";
import { Toaster as SonnerToaster } from "sonner";

import "../dist/css/index.css";
import "./preview-tw.built.css";

const STORAGE_KEY = "solids:sb:theme";

const DS_THEMES = ["light", "dark", "fantasy", "cyberpunk"] as const;
type DsTheme = (typeof DS_THEMES)[number];

function readStoredTheme(): DsTheme {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v && (DS_THEMES as readonly string[]).includes(v)) return v as DsTheme;
    return "light";
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
      description: "Tema SoliDS (token CSS)",
      toolbar: {
        title: "Tema DS",
        icon: "paintbrush",
        items: [
          { value: "light", title: "Light", icon: "circlehollow" },
          { value: "dark", title: "Dark", icon: "circle" },
          { value: "fantasy", title: "Fantasy", icon: "bookmark" },
          { value: "cyberpunk", title: "Cyberpunk", icon: "lightning" },
        ],
        dynamicTitle: true,
      },
    },
  },

  initialGlobals: {
    theme: initialTheme,
  },

  parameters: {
    viewMode: "docs",
    previewTabs: { canvas: { hidden: false } },
    options: { showPanel: true },
    controls: { expanded: true },
    docs: {
      theme: initialTheme === "dark" || initialTheme === "cyberpunk" ? themes.dark : themes.light,
    },
  },

  decorators: [
    (Story, context) => {
      const raw = context.globals.theme;
      const theme: DsTheme =
        raw && (DS_THEMES as readonly string[]).includes(raw) ? (raw as DsTheme) : "light";

      document.documentElement.setAttribute("data-theme", theme);
      const colorScheme = theme === "dark" || theme === "cyberpunk" ? "dark" : "light";
      document.documentElement.style.colorScheme = colorScheme;
      document.body.setAttribute("data-theme", theme);
      document.body.style.colorScheme = colorScheme;

      writeStoredTheme(theme);

      const sonnerTheme = theme === "dark" || theme === "cyberpunk" ? "dark" : "light";

      return (
        <TooltipProvider delayDuration={200}>
          <Toaster />
          <SonnerToaster theme={sonnerTheme} className="toaster group" />
          <Story />
        </TooltipProvider>
      );
    },
  ],
};

export default preview;
