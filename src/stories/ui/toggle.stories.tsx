import * as React from "react";
import { Toggle } from "@/components/ui/toggle";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Toggle",
  component: Toggle,
  parameters: { layout: "centered" },
  argTypes: {
    variant: { control: "select", options: ["default", "outline"] },
    size: { control: "select", options: ["default", "sm", "lg"] },
    disabled: { control: "boolean" },
  },
} satisfies Meta<typeof Toggle>;

export default meta;

type Story = StoryObj<typeof Toggle>;

export const Playground: Story = {
  args: { defaultPressed: false, variant: "default", size: "default", disabled: false },
  render: (args) => <Toggle {...args}>Grassetto</Toggle>,
};
