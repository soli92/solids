import * as React from "react";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Aspect Ratio",
  component: AspectRatio,
  parameters: { layout: "centered" },
  argTypes: {},
} satisfies Meta<typeof AspectRatio>;

export default meta;

type Story = StoryObj<typeof AspectRatio>;

export const Playground: Story = {
  args: { ratio: 16 / 9 },
  render: (args) => (
    <div className="w-[280px] overflow-hidden rounded-md border">
      <AspectRatio {...args}>
        <div className="flex h-full items-center justify-center bg-muted text-sm">16:9</div>
      </AspectRatio>
    </div>
  ),
};
