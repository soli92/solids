import * as React from "react";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Button",
  component: Button,
  parameters: { layout: "centered" },
  argTypes: {
    children: { control: "text" },
    variant: { control: "select", options: ["default", "destructive", "outline", "secondary", "ghost", "link"] },
    size: { control: "select", options: ["default", "sm", "lg", "icon"] },
    disabled: { control: "boolean" },
  },
} satisfies Meta<typeof Button>;

export default meta;

type Story = StoryObj<typeof Button>;

export const Playground: Story = {
  args: { children: "Pulsante", variant: "default", size: "default", disabled: false },
  render: (args: { children?: React.ReactNode } & Record<string, unknown>) => <Button {...args}>{args.children}</Button>,
};
