import * as React from "react";
import { LogoLoader } from "@/components/ui/logo-loader";
import logoPng from "../../../docs/brand-assets/soli-category-icons/soli-icon-logo.png";
import logoSvg from "../../../docs/brand-assets/soli-category-icons/soli-icon-logo.svg";
import symbolSvg from "../../../docs/brand-assets/soli-category-icons/soli-icon-symbol.svg";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Logo Loader",
  component: LogoLoader,
  parameters: { layout: "centered" },
  argTypes: {
    src: {
      control: "select",
      options: ["__default__", "logo-svg", "logo-png", "symbol-svg"],
      mapping: {
        __default__: undefined,
        "logo-svg": logoSvg,
        "logo-png": logoPng,
        "symbol-svg": symbolSvg
      }
    },
    size: { control: { type: "range", min: 48, max: 220, step: 4 } },
    animation: { control: "inline-radio", options: ["spin", "pulse", "none"] },
    durationMs: { control: { type: "range", min: 400, max: 4000, step: 100 } },
    alt: { control: "text" }
  },
} satisfies Meta<typeof LogoLoader>;

export default meta;

type Story = StoryObj<typeof LogoLoader>;

export const Playground: Story = {
  args: {
    src: undefined,
    size: 120,
    animation: "spin" as const,
    durationMs: 1400,
    alt: "Loading"
  },
  render: (args) => <LogoLoader {...args} />,
};
