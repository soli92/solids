import { addons } from "@storybook/manager-api";
import { themes } from "@storybook/theming";

const STORAGE_KEY = "solids:sb:theme";

/** Allineato a preview.tsx: temi che usano UI Storybook “dark”. */
const DARK_CHROME_THEMES = new Set([
  "dark",
  "cyberpunk",
  "90s-party",
  "steampunk",
  "captain-america",
  "ichigo",
  "inuyasha",
  "sasuke",
  "vegeta",
  "zoro",
]);

function readStoredTheme(): "light" | "dark" {
  try {
    const t = localStorage.getItem(STORAGE_KEY);
    if (t && DARK_CHROME_THEMES.has(t)) return "dark";
    return "light";
  } catch {
    return "light";
  }
}

const theme = readStoredTheme() === "dark" ? themes.dark : themes.light;

addons.setConfig({
  theme,
  brandTitle: "SoliDS",
  brandUrl: "https://github.com/soli92/solids",
});
