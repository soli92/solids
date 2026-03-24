import * as React from "react";
import { Separator } from "@/components/ui/separator";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Separator",
  component: Separator,
  parameters: { layout: "centered" },
  argTypes: { orientation: { control: "select", options: ["horizontal", "vertical"] } },
} satisfies Meta<typeof Separator>;

export default meta;

type Story = StoryObj<typeof Separator>;

export const Playground: Story = {
  args: { orientation: "horizontal" as const },
  render: (args) => (
    <div>
      <div className="space-y-1">
        <h4 className="text-sm font-medium leading-none">Sezione</h4>
        <p className="text-sm text-muted-foreground">Testo sopra il separatore.</p>
      </div>
      <Separator className="my-4" {...args} />
      <p className="text-sm text-muted-foreground">Sotto.</p>
    </div>
  ),
};
