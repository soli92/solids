import * as React from "react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Radio Group",
  component: RadioGroup,
  parameters: { layout: "centered" },
  argTypes: {},
} satisfies Meta<typeof RadioGroup>;

export default meta;

type Story = StoryObj<typeof RadioGroup>;

export const Playground: Story = {
  args: {},
  render: () => (
    <RadioGroup defaultValue="a" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <RadioGroupItem value="a" id="rg-a" />
        <Label htmlFor="rg-a">Opzione A</Label>
      </div>
      <div className="flex items-center gap-2">
        <RadioGroupItem value="b" id="rg-b" />
        <Label htmlFor="rg-b">Opzione B</Label>
      </div>
    </RadioGroup>
  ),
};
