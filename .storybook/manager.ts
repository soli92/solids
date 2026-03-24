import { addons } from "@storybook/manager-api";
import { themes } from "@storybook/theming";

const STORAGE_KEY = "solids:sb:theme";

function readStoredTheme(): "light" | "dark" {
  try {
    const t = localStorage.getItem(STORAGE_KEY);
    if (t === "dark" || t === "cyberpunk") return "dark";
    return "light";
  } catch {
    return "light";
  }
}

const theme = readStoredTheme() === "dark" ? themes.dark : themes.light;

addons.setConfig({
  theme
});
