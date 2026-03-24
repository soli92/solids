import * as React from "react";
import { Input } from "@/components/ui/input";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Input",
  component: Input,
  parameters: { layout: "centered" },
  argTypes: {
    type: { control: "select", options: ["text", "email", "password", "search", "url"] },
    placeholder: { control: "text" },
    disabled: { control: "boolean" },
  },
} satisfies Meta<typeof Input>;

export default meta;

type Story = StoryObj<typeof Input>;

export const Playground: Story = {
  args: { type: "text", placeholder: "Scrivi qui…", disabled: false },
  render: (args) => <Input {...args} />,
};
