import type { Meta, StoryObj } from "@storybook/react";

import {
  IconAlertCircle,
  IconCalendar,
  IconCheck,
  IconChevronDown,
  IconChevronRight,
  IconCopy,
  IconExternalLink,
  IconFolder,
  IconHeart,
  IconHome,
  IconInfo,
  IconMail,
  IconMenu,
  IconMinus,
  IconMoon,
  IconPencil,
  IconPlus,
  IconSearch,
  IconSettings,
  IconStar,
  IconSun,
  IconTrash,
  IconUser,
  IconX,
  // Themed icons
  IconFantasyScroll,
  IconFantasySword,
  IconFantasyGem,
  IconCyberpunkChip,
  IconCyberpunkEye,
  IconCyberpunkSignal,
  IconPartyBolt,
  IconPartyDiamond,
  IconPartyStar,
  type SolidsIconVariant,
} from "@/icons";

const allIcons = [
  { name: "Home", Icon: IconHome },
  { name: "Search", Icon: IconSearch },
  { name: "User", Icon: IconUser },
  { name: "Settings", Icon: IconSettings },
  { name: "Menu", Icon: IconMenu },
  { name: "X", Icon: IconX },
  { name: "Check", Icon: IconCheck },
  { name: "ChevronDown", Icon: IconChevronDown },
  { name: "ChevronRight", Icon: IconChevronRight },
  { name: "Plus", Icon: IconPlus },
  { name: "Minus", Icon: IconMinus },
  { name: "Trash", Icon: IconTrash },
  { name: "Pencil", Icon: IconPencil },
  { name: "Copy", Icon: IconCopy },
  { name: "ExternalLink", Icon: IconExternalLink },
  { name: "AlertCircle", Icon: IconAlertCircle },
  { name: "Info", Icon: IconInfo },
  { name: "Star", Icon: IconStar },
  { name: "Heart", Icon: IconHeart },
  { name: "Sun", Icon: IconSun },
  { name: "Moon", Icon: IconMoon },
  { name: "Mail", Icon: IconMail },
  { name: "Calendar", Icon: IconCalendar },
  { name: "Folder", Icon: IconFolder },
] as const;

const themedIcons = [
  { name: "FantasyScroll", Icon: IconFantasyScroll, theme: "fantasy" },
  { name: "FantasySword",  Icon: IconFantasySword,  theme: "fantasy" },
  { name: "FantasyGem",   Icon: IconFantasyGem,    theme: "fantasy" },
  { name: "CyberpunkChip",   Icon: IconCyberpunkChip,   theme: "cyberpunk" },
  { name: "CyberpunkEye",    Icon: IconCyberpunkEye,    theme: "cyberpunk" },
  { name: "CyberpunkSignal", Icon: IconCyberpunkSignal, theme: "cyberpunk" },
  { name: "PartyBolt",    Icon: IconPartyBolt,    theme: "90s-party" },
  { name: "PartyDiamond", Icon: IconPartyDiamond, theme: "90s-party" },
  { name: "PartyStar",    Icon: IconPartyStar,    theme: "90s-party" },
] as const;

const themes = [
  "light", "dark", "fantasy", "cyberpunk", "90s-party",
  "steampunk", "ichigo", "vegeta", "zoro",
  "captain-america", "sasuke", "inuyasha",
] as const;

const meta: Meta = {
  title: "Foundations / Icons",
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component:
          'Import from `@soli92/solids/icons` to use token-driven SVG icons in app projects.',
      },
    },
  },
};

export default meta;

// ── Gallery base ────────────────────────────────────────────────────────────────

export const Gallery: StoryObj = {
  name: "Gallery — All Base Icons",
  render: () => (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
        gap: "var(--sd-space-lg)",
      }}
    >
      {allIcons.map(({ name, Icon }) => (
        <div
          key={name}
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "var(--sd-space-sm)",
            padding: "var(--sd-space-md)",
            borderRadius: "var(--sd-radius-lg)",
            border: "1px solid var(--sd-color-border-default)",
            background: "var(--sd-color-bg-surface)",
          }}
        >
          <Icon size="lg" />
          <span style={{
            fontSize: "var(--sd-font-size-xs)",
            color: "var(--sd-color-text-secondary)",
            fontFamily: "var(--sd-font-mono)",
            textAlign: "center",
          }}>{name}</span>
        </div>
      ))}
    </div>
  ),
};

// ── Themed icons gallery ────────────────────────────────────────────────────────

export const ThemedGallery: StoryObj = {
  name: "Gallery — Themed Icons",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sd-space-xl)" }}>
      {(["fantasy", "cyberpunk", "90s-party"] as const).map((themeName) => (
        <div key={themeName} data-theme={themeName}>
          <p style={{
            fontFamily: "var(--sd-font-mono)",
            fontSize: "var(--sd-font-size-xs)",
            color: "var(--sd-color-text-tertiary)",
            marginBottom: "var(--sd-space-sm)",
          }}>
            data-theme=&quot;{themeName}&quot;
          </p>
          <div
            style={{
              display: "flex",
              gap: "var(--sd-space-lg)",
              flexWrap: "wrap",
              padding: "var(--sd-space-lg)",
              borderRadius: "var(--sd-radius-lg)",
              background: "var(--sd-color-bg-canvas)",
              border: "1px solid var(--sd-color-border-default)",
            }}
          >
            {themedIcons
              .filter((i) => i.theme === themeName)
              .map(({ name, Icon }) => (
                <div
                  key={name}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "var(--sd-space-xs)",
                    minWidth: 80,
                  }}
                >
                  <Icon size="xl" />
                  <span style={{
                    fontSize: "var(--sd-font-size-xs)",
                    color: "var(--sd-color-text-secondary)",
                    fontFamily: "var(--sd-font-mono)",
                    textAlign: "center",
                  }}>{name}</span>
                </div>
              ))}
          </div>
        </div>
      ))}
    </div>
  ),
};

// ── Variants ────────────────────────────────────────────────────────────────────

export const Variants: StoryObj = {
  name: "Variants — default / muted / primary / on-primary",
  argTypes: {
    theme: { control: "select", options: themes },
  },
  args: { theme: "light" },
  render: ({ theme }) => (
    <div data-theme={theme} style={{ padding: "var(--sd-space-lg)", background: "var(--sd-color-bg-canvas)", borderRadius: "var(--sd-radius-lg)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--sd-space-xl)", flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sd-space-xs)" }}>
          <IconHome size="xl" variant="default" />
          <span style={{ fontSize: "var(--sd-font-size-xs)", color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>default</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sd-space-xs)" }}>
          <IconHome size="xl" variant="muted" />
          <span style={{ fontSize: "var(--sd-font-size-xs)", color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>muted</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sd-space-xs)" }}>
          <IconHome size="xl" variant="primary" />
          <span style={{ fontSize: "var(--sd-font-size-xs)", color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>primary</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sd-space-xs)" }}>
          <div style={{ background: "var(--sd-color-primary-default)", padding: "var(--sd-space-sm)", borderRadius: "var(--sd-radius-md)" }}>
            <IconHome size="xl" variant="on-primary" />
          </div>
          <span style={{ fontSize: "var(--sd-font-size-xs)", color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>on-primary</span>
        </div>
      </div>
    </div>
  ),
};

// ── Sizes ───────────────────────────────────────────────────────────────────────

export const Sizes: StoryObj = {
  name: "Sizes — sm / md / lg / xl / custom",
  render: () => (
    <div style={{ display: "flex", alignItems: "flex-end", gap: "var(--sd-space-md)" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sd-space-xs)" }}>
        <IconStar size="sm" />
        <span style={{ fontSize: "var(--sd-font-size-xs)", color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>sm (16)</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sd-space-xs)" }}>
        <IconStar size="md" />
        <span style={{ fontSize: "var(--sd-font-size-xs)", color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>md (20)</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sd-space-xs)" }}>
        <IconStar size="lg" />
        <span style={{ fontSize: "var(--sd-font-size-xs)", color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>lg (24)</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sd-space-xs)" }}>
        <IconStar size="xl" />
        <span style={{ fontSize: "var(--sd-font-size-xs)", color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>xl (32)</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sd-space-xs)" }}>
        <IconStar size={48} />
        <span style={{ fontSize: "var(--sd-font-size-xs)", color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>48px</span>
      </div>
    </div>
  ),
};

// ── Interactive ─────────────────────────────────────────────────────────────────

export const Interactive: StoryObj = {
  name: "Interactive — scegli tema e variant",
  argTypes: {
    theme: { control: "select", options: themes },
    variant: { control: "select", options: ["default", "muted", "primary", "on-primary"] },
    size: { control: "select", options: ["sm", "md", "lg", "xl"] },
  },
  args: { theme: "light", variant: "default", size: "lg" },
  render: ({ theme, variant, size }) => (
    <div
      data-theme={theme}
      style={{
        padding: "var(--sd-space-xl)",
        background: variant === "on-primary" ? "var(--sd-color-primary-default)" : "var(--sd-color-bg-canvas)",
        borderRadius: "var(--sd-radius-lg)",
        display: "flex",
        flexWrap: "wrap",
        gap: "var(--sd-space-lg)",
      }}
    >
      {allIcons.map(({ name, Icon }) => (
        <div key={name} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
          <Icon size={size as "sm" | "md" | "lg" | "xl"} variant={variant as SolidsIconVariant} />
          <span style={{ fontSize: 10, color: "var(--sd-color-text-tertiary)", fontFamily: "var(--sd-font-mono)" }}>{name}</span>
        </div>
      ))}
    </div>
  ),
};
