import * as React from "react";
import { Kbd } from "@/components/ui/kbd";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Kbd",
  component: Kbd,
  parameters: { layout: "centered" },
  argTypes: {},
} satisfies Meta<typeof Kbd>;

export default meta;

type Story = StoryObj<typeof Kbd>;

export const Playground: Story = {
  args: {},
  render: () => (
    <p className="text-sm">
      Premi <Kbd className="pointer-events-none">⌘</Kbd> + <Kbd className="pointer-events-none">K</Kbd>
    </p>
  ),
};
