/**
 * SoliDS — Tailwind preset (shadcn/ui + token bridge).
 * Install: tailwindcss, tailwindcss-animate, @soli92/solids.
 * In tailwind.config: presets: [require("@soli92/solids/tailwind-preset")].
 * In globals.css: import SoliDS index.css, then Tailwind layers.
 */
const { fontFamily } = require("tailwindcss/defaultTheme");

/** @type {import("tailwindcss").Config} */
module.exports = {
  darkMode: ["class", '[data-theme="dark"]', '[data-theme="cyberpunk"]'],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        chart: {
          1: "var(--chart-1)",
          2: "var(--chart-2)",
          3: "var(--chart-3)",
          4: "var(--chart-4)",
          5: "var(--chart-5)",
        },
        sidebar: {
          DEFAULT: "var(--sidebar)",
          foreground: "var(--sidebar-foreground)",
          primary: "var(--sidebar-primary)",
          "primary-foreground": "var(--sidebar-primary-foreground)",
          accent: "var(--sidebar-accent)",
          "accent-foreground": "var(--sidebar-accent-foreground)",
          border: "var(--sidebar-border)",
          ring: "var(--sidebar-ring)",
        },
        "sd-primary": "var(--sd-color-primary-default)",
        "sd-success": "var(--sd-color-intent-success)",
        "sd-warning": "var(--sd-color-intent-warning)",
        "sd-danger": "var(--sd-color-intent-danger)",
        "sd-info": "var(--sd-color-intent-info)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--sd-font-body)", ...fontFamily.sans],
        mono: ["var(--sd-font-mono)", ...fontFamily.mono],
      },
      boxShadow: {
        sm: "var(--sd-shadow-sm)",
        md: "var(--sd-shadow-md)",
        lg: "var(--sd-shadow-lg)",
        xl: "var(--sd-shadow-xl)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
