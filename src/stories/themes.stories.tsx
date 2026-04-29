import type { Meta, StoryObj } from "@storybook/react";

const themes = [
  "light", "dark", "fantasy", "cyberpunk", "90s-party",
  "steampunk", "ichigo", "vegeta", "zoro",
  "captain-america", "sasuke", "inuyasha",
] as const;

type Theme = (typeof themes)[number];

const themeDescriptions: Record<Theme, string> = {
  "light":           "Superfici tonali chiare, blu primario shadcn, raggio generoso MD3.",
  "dark":            "Superfici M3 elevation su sfondo profondo, blu primary adattato al buio.",
  "fantasy":         "Pergamena e inchiostro medievale. Font serif Cinzel/Source Serif 4, oro ottone.",
  "cyberpunk":       "Neon cyan/magenta su buio cosmico. Font Orbitron/Space Grotesk, angoli taglienti.",
  "90s-party":       "Rave MTV Memphis. Magenta + teal + lime-acid su viola profondo. Font Russo One/VT323.",
  "steampunk":       "Laboratorio vittoriano. Ottone e rame, cuoio e vapore. Font Cinzel/Libre Baskerville.",
  "ichigo":          "Bleach: nero profondo, arancio/rosso Bankai, bianco ossa. Font Bebas Neue.",
  "vegeta":          "Dragon Ball: blu royal armatura, oro saiyan, bianco ghiaccio. Font Rajdhani.",
  "zoro":            "One Piece: verde profondo katana, acciaio freddo, erba feudale. Font Merriweather.",
  "captain-america": "Marvel: blu notte scudo, rosso patriottico, argento. Font Oswald.",
  "sasuke":          "Naruto: nero/blu notte, viola Chidori, freddo metallico. Font Rajdhani.",
  "inuyasha":        "Feudal Japan: rosso haori, argento lunare, terra e legno. Font Crimson Text.",
};

// ── Card compatta per showcase ──────────────────────────────────────────────────

const ThemeCard = ({ theme }: { theme: Theme }) => (
  <div
    data-theme={theme}
    style={{
      background: "var(--sd-color-bg-canvas)",
      border: "1px solid var(--sd-color-border-default)",
      borderRadius: "var(--sd-radius-lg)",
      padding: "var(--sd-space-lg)",
      minWidth: 220,
      maxWidth: 280,
    }}
  >
    <div style={{ marginBottom: "var(--sd-space-xs)" }}>
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
      lineHeight: 1.5,
    }}>
      {themeDescriptions[theme]}
    </p>

    {/* Color swatches */}
    <div style={{ display: "flex", gap: 6, marginBottom: "var(--sd-space-sm)" }}>
      {[
        "var(--sd-color-primary-default)",
        "var(--sd-color-bg-surface)",
        "var(--sd-color-bg-elevated)",
        "var(--sd-color-border-default)",
        "var(--sd-color-intent-success)",
        "var(--sd-color-intent-danger)",
      ].map((c, i) => (
        <span
          key={i}
          title={c}
          style={{
            width: 20,
            height: 20,
            borderRadius: "var(--sd-radius-sm)",
            background: c,
            border: "1px solid var(--sd-color-border-muted)",
            flexShrink: 0,
          }}
        />
      ))}
    </div>

    {/* Badges intent */}
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
      }}>Success</span>
      <span style={{
        background: "var(--sd-color-intent-warning-bg)",
        color: "var(--sd-color-intent-warning)",
        border: "1px solid var(--sd-color-intent-warning-border)",
        borderRadius: "var(--sd-radius-sm)",
        padding: "2px 10px",
        fontSize: "var(--sd-font-size-xs)",
      }}>Warning</span>
      <span style={{
        background: "var(--sd-color-intent-danger-bg)",
        color: "var(--sd-color-intent-danger)",
        border: "1px solid var(--sd-color-intent-danger-border)",
        borderRadius: "var(--sd-radius-sm)",
        padding: "2px 10px",
        fontSize: "var(--sd-font-size-xs)",
      }}>Danger</span>
    </div>
  </div>
);

// ── Token detail per tema ──────────────────────────────────────────────────────

const ThemeTokenDetail = ({ theme }: { theme: Theme }) => {
  const tokenRows: Array<{ label: string; var: string }> = [
    { label: "text.primary",       var: "--sd-color-text-primary" },
    { label: "text.secondary",     var: "--sd-color-text-secondary" },
    { label: "text.tertiary",      var: "--sd-color-text-tertiary" },
    { label: "text.link",          var: "--sd-color-text-link" },
    { label: "bg.canvas",          var: "--sd-color-bg-canvas" },
    { label: "bg.surface",         var: "--sd-color-bg-surface" },
    { label: "bg.elevated",        var: "--sd-color-bg-elevated" },
    { label: "border.default",     var: "--sd-color-border-default" },
    { label: "border.strong",      var: "--sd-color-border-strong" },
    { label: "primary.default",    var: "--sd-color-primary-default" },
    { label: "primary.foreground", var: "--sd-color-primary-foreground" },
    { label: "icon.default",       var: "--sd-color-icon-default" },
    { label: "icon.primary",       var: "--sd-color-icon-primary" },
    { label: "intent.success",     var: "--sd-color-intent-success" },
    { label: "intent.warning",     var: "--sd-color-intent-warning" },
    { label: "intent.danger",      var: "--sd-color-intent-danger" },
    { label: "intent.info",        var: "--sd-color-intent-info" },
  ];

  return (
    <div
      data-theme={theme}
      style={{
        background: "var(--sd-color-bg-canvas)",
        border: "1px solid var(--sd-color-border-default)",
        borderRadius: "var(--sd-radius-lg)",
        padding: "var(--sd-space-lg)",
        fontFamily: "var(--sd-font-mono)",
        fontSize: "var(--sd-font-size-xs)",
      }}
    >
      <h4 style={{
        color: "var(--sd-color-text-primary)",
        fontFamily: "var(--sd-font-heading)",
        fontSize: "var(--sd-font-size-md)",
        marginBottom: "var(--sd-space-md)",
      }}>
        {theme} — Token
      </h4>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {tokenRows.map(({ label, var: cssVar }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: "var(--sd-space-sm)" }}>
            <span
              style={{
                width: 24,
                height: 24,
                borderRadius: "var(--sd-radius-sm)",
                background: `var(${cssVar})`,
                border: "1px solid var(--sd-color-border-muted)",
                flexShrink: 0,
              }}
            />
            <span style={{ color: "var(--sd-color-text-secondary)", minWidth: 180 }}>{label}</span>
            <code style={{ color: "var(--sd-color-text-tertiary)" }}>{cssVar}</code>
          </div>
        ))}
      </div>

      {/* Font preview */}
      <div style={{ marginTop: "var(--sd-space-lg)", borderTop: "1px solid var(--sd-color-border-muted)", paddingTop: "var(--sd-space-md)" }}>
        <p style={{ color: "var(--sd-color-text-tertiary)", marginBottom: 6 }}>font.heading</p>
        <p style={{ fontFamily: "var(--sd-font-heading)", fontSize: "var(--sd-font-size-xl)", color: "var(--sd-color-text-primary)", margin: 0 }}>
          The quick brown fox
        </p>
        <p style={{ color: "var(--sd-color-text-tertiary)", marginTop: "var(--sd-space-sm)", marginBottom: 6 }}>font.body</p>
        <p style={{ fontFamily: "var(--sd-font-body)", fontSize: "var(--sd-font-size-sm)", color: "var(--sd-color-text-secondary)", margin: 0 }}>
          Jumps over the lazy dog — 0123456789
        </p>
        <p style={{ color: "var(--sd-color-text-tertiary)", marginTop: "var(--sd-space-sm)", marginBottom: 6 }}>font.mono</p>
        <code style={{ fontFamily: "var(--sd-font-mono)", fontSize: "var(--sd-font-size-sm)", color: "var(--sd-color-text-tertiary)" }}>
          const ds = &apos;@soli92/solids&apos;;
        </code>
      </div>

      {/* Shadow preview */}
      <div style={{ marginTop: "var(--sd-space-lg)", borderTop: "1px solid var(--sd-color-border-muted)", paddingTop: "var(--sd-space-md)" }}>
        <p style={{ color: "var(--sd-color-text-tertiary)", marginBottom: "var(--sd-space-sm)" }}>shadow</p>
        <div style={{ display: "flex", gap: "var(--sd-space-md)", flexWrap: "wrap" }}>
          {(["sm", "md", "lg", "xl"] as const).map((s) => (
            <div
              key={s}
              style={{
                width: 48,
                height: 48,
                borderRadius: "var(--sd-radius-md)",
                background: "var(--sd-color-bg-elevated)",
                boxShadow: `var(--sd-shadow-${s})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--sd-color-text-tertiary)",
                fontSize: 10,
              }}
            >
              {s}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ── Meta ────────────────────────────────────────────────────────────────────────

const meta: Meta = {
  title: "Foundations / Themes",
  parameters: { layout: "padded" },
};

export default meta;

// ── Stories ──────────────────────────────────────────────────────────────────────

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

export const TokenDetail: StoryObj = {
  name: "Token Detail — per tema",
  argTypes: {
    theme: {
      control: "select",
      options: themes,
    },
  },
  args: { theme: "light" },
  render: ({ theme }) => <ThemeTokenDetail theme={theme as Theme} />,
};

export const AllTokenDetails: StoryObj = {
  name: "All Token Details",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sd-space-xl)" }}>
      {themes.map((theme) => (
        <ThemeTokenDetail key={theme} theme={theme} />
      ))}
    </div>
  ),
};
