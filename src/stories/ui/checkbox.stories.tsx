import * as React from "react";
import { Checkbox } from "@/components/ui/checkbox";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Checkbox",
  component: Checkbox,
  parameters: { layout: "centered" },
  argTypes: { disabled: { control: "boolean" } },
} satisfies Meta<typeof Checkbox>;

export default meta;

type Story = StoryObj<typeof Checkbox>;

export const Playground: Story = {
  args: { disabled: false },
  render: function R(args: Record<string, unknown>) {
    const [c, setC] = React.useState(false);
    return (
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={c} onCheckedChange={(v) => setC(v === true)} {...args} />
        Accetto i termini
      </label>
    );
  },
};
