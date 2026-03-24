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

const meta: Meta = {
  title: "Foundations / Icons",
  parameters: { layout: "padded" },
};

export default meta;

export const Gallery: StoryObj = {
  render: () => (
    <div
      className="sd-grid sd-gap-lg"
      style={{
        gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
      }}
    >
      {allIcons.map(({ name, Icon }) => (
        <div
          key={name}
          className="sd-flex sd-flex-col sd-items-center sd-gap-sm sd-p-md sd-rounded-lg sd-border"
          style={{ background: "var(--sd-color-bg-surface)" }}
        >
          <Icon size="lg" />
          <span className="sd-text-xs sd-text-secondary">{name}</span>
        </div>
      ))}
    </div>
  ),
};

export const Variants: StoryObj = {
  render: () => (
    <div className="sd-flex sd-items-center sd-gap-xl sd-flex-wrap">
      <IconHome size="xl" variant="default" />
      <IconHome size="xl" variant="muted" />
      <IconHome size="xl" variant="primary" />
      <div
        className="sd-flex sd-items-center sd-justify-center sd-p-md sd-rounded-md"
        style={{ background: "var(--sd-color-primary-default)" }}
      >
        <IconHome size="xl" variant="on-primary" />
      </div>
    </div>
  ),
};

export const Sizes: StoryObj = {
  render: () => (
    <div className="sd-flex sd-items-end sd-gap-md">
      <IconStar size="sm" />
      <IconStar size="md" />
      <IconStar size="lg" />
      <IconStar size="xl" />
      <IconStar size={40} />
    </div>
  ),
};
