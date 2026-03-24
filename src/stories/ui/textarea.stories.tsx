import * as React from "react";
import { Textarea } from "@/components/ui/textarea";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Textarea",
  component: Textarea,
  parameters: { layout: "centered" },
  argTypes: { placeholder: { control: "text" }, rows: { control: "number" }, disabled: { control: "boolean" } },
} satisfies Meta<typeof Textarea>;

export default meta;

type Story = StoryObj<typeof Textarea>;

export const Playground: Story = {
  args: { placeholder: "Messaggio…", rows: 4, disabled: false },
  render: (args) => <Textarea {...args} />,
};
