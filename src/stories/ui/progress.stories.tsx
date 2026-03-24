import * as React from "react";
import { Progress } from "@/components/ui/progress";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Progress",
  component: Progress,
  parameters: { layout: "centered" },
  argTypes: { value: { control: { type: "range", min: 0, max: 100 } } },
} satisfies Meta<typeof Progress>;

export default meta;

type Story = StoryObj<typeof Progress>;

export const Playground: Story = {
  args: { value: 60 },
  render: (args) => <Progress className="w-[240px]" {...args} />,
};
