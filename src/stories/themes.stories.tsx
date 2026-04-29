import type { Meta, StoryObj } from "@storybook/react";

const themes = [
  "light", "dark", "fantasy", "cyberpunk", "90s-party",
  "steampunk", "ichigo", "vegeta", "zoro",
  "captain-america", "sasuke", "inuyasha"
] as const;

type Theme = typeof themes[number];

const ThemeCard = ({ theme }: { theme: Theme }) => (
  <div
    data-theme={theme}
    style={{
      background: "var(--sd-color-bg-canvas)",
      border: "1px solid var(--sd-color-border-default)",
      borderRadius: "var(--sd-radius-lg)",
      padding: "var(--sd-space-lg)",
      minWidth: 220,
    }}
  >
    <div style={{ marginBottom: "var(--sd-space-sm)" }}>
      <span style={{
        fontSize: "var(--sd-font-size-xs)",
        color: "var(--sd-color-text-tertiary)",
        fontFamily: "var(--sd-font-mono)",
      }}>
        data-theme=&quot;{theme}&quot;
      </span>
    </div>
    <h3 style={{
      color: "var(--sd-color-text-primary)",
      fontFamily: "var(--sd-font-heading)",
      fontSize: "var(--sd-font-size-lg)",
      fontWeight: 700,
      margin: "0 0 var(--sd-space-xs)",
    }}>
      {theme.charAt(0).toUpperCase() + theme.slice(1).replace(/-/g, " ")}
    </h3>
    <p style={{
      color: "var(--sd-color-text-secondary)",
      fontFamily: "var(--sd-font-body)",
      fontSize: "var(--sd-font-size-sm)",
      margin: "0 0 var(--sd-space-md)",
    }}>
      Testo secondario di esempio per vedere la leggibilità del tema.
    </p>
    <div style={{ display: "flex", gap: "var(--sd-space-sm)", flexWrap: "wrap" }}>
      <span style={{
        background: "var(--sd-color-primary-default)",
        color: "var(--sd-color-primary-foreground)",
        borderRadius: "var(--sd-radius-sm)",
        padding: "2px 10px",
        fontSize: "var(--sd-font-size-xs)",
        fontFamily: "var(--sd-font-body)",
      }}>Primary</span>
      <span style={{
        background: "var(--sd-color-intent-success-bg)",
        color: "var(--sd-color-intent-success)",
        border: "1px solid var(--sd-color-intent-success-border)",
        borderRadius: "var(--sd-radius-sm)",
        padding: "2px 10px",
        fontSize: "var(--sd-font-size-xs)",
        fontFamily: "var(--sd-font-body)",
      }}>Success</span>
      <span style={{
        background: "var(--sd-color-intent-danger-bg)",
        color: "var(--sd-color-intent-danger)",
        border: "1px solid var(--sd-color-intent-danger-border)",
        borderRadius: "var(--sd-radius-sm)",
        padding: "2px 10px",
        fontSize: "var(--sd-font-size-xs)",
        fontFamily: "var(--sd-font-body)",
      }}>Danger</span>
    </div>
  </div>
);

const meta: Meta = {
  title: "Foundations / Themes",
  parameters: { layout: "padded" },
};

export default meta;

export const AllThemes: StoryObj = {
  name: "All Themes Showcase",
  render: () => (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sd-space-lg)" }}>
      {themes.map((theme) => (
        <ThemeCard key={theme} theme={theme} />
      ))}
    </div>
  ),
};

export const SingleTheme: StoryObj = {
  name: "Single Theme Preview",
  argTypes: {
    theme: {
      control: "select",
      options: themes,
    },
  },
  args: { theme: "light" },
  render: ({ theme }) => <ThemeCard theme={theme as Theme} />,
};
