import * as React from "react";
import { Label } from "@/components/ui/label";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Label",
  component: Label,
  parameters: { layout: "centered" },
  argTypes: { children: { control: "text" } },
} satisfies Meta<typeof Label>;

export default meta;

type Story = StoryObj<typeof Label>;

export const Playground: Story = {
  args: { children: "Etichetta campo" },
  render: (args: { children?: React.ReactNode } & Record<string, unknown>) => <Label {...args}>{args.children}</Label>,
};
