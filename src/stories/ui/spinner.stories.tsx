import * as React from "react";
import { Spinner } from "@/components/ui/spinner";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Spinner",
  component: Spinner,
  parameters: { layout: "centered" },
  argTypes: {},
} satisfies Meta<typeof Spinner>;

export default meta;

type Story = StoryObj<typeof Spinner>;

export const Playground: Story = {
  args: {},
  render: () => <Spinner className="size-8" />,
};
