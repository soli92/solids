import * as React from "react";
import { Badge } from "@/components/ui/badge";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Badge",
  component: Badge,
  parameters: { layout: "centered" },
  argTypes: {
    children: { control: "text" },
    variant: { control: "select", options: ["default", "secondary", "destructive", "outline"] },
  },
} satisfies Meta<typeof Badge>;

export default meta;

type Story = StoryObj<typeof Badge>;

export const Playground: Story = {
  args: { children: "Badge", variant: "default" },
  render: (args: { children?: React.ReactNode } & Record<string, unknown>) => <Badge {...args}>{args.children}</Badge>,
};
