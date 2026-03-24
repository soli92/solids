import * as React from "react";
import { Slider } from "@/components/ui/slider";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Slider",
  component: Slider,
  parameters: { layout: "centered" },
  argTypes: { disabled: { control: "boolean" } },
} satisfies Meta<typeof Slider>;

export default meta;

type Story = StoryObj<typeof Slider>;

export const Playground: Story = {
  args: { defaultValue: [50], max: 100, step: 1, disabled: false },
  render: (args) => <Slider className="w-[220px]" {...args} />,
};
