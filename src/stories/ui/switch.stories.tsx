import * as React from "react";
import { Switch } from "@/components/ui/switch";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Switch",
  component: Switch,
  parameters: { layout: "centered" },
  argTypes: { disabled: { control: "boolean" } },
} satisfies Meta<typeof Switch>;

export default meta;

type Story = StoryObj<typeof Switch>;

export const Playground: Story = {
  args: { disabled: false },
  render: function R(args: Record<string, unknown>) {
    const [on, setOn] = React.useState(false);
    return (
      <div className="flex items-center gap-2">
        <Switch checked={on} onCheckedChange={setOn} {...args} />
        <span className="text-sm text-muted-foreground">{on ? "On" : "Off"}</span>
      </div>
    );
  },
};
