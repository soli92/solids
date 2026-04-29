import * as React from "react";
import { LogoLoader } from "@/components/ui/logo-loader";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Logo Loader",
  component: LogoLoader,
  parameters: { layout: "centered" },
} satisfies Meta<typeof LogoLoader>;

export default meta;

type Story = StoryObj<typeof LogoLoader>;

export const Playground: Story = {
  args: {},
  render: (args) => <LogoLoader {...args} />,
};
