import * as React from "react";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Toggle Group", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Gruppo: StoryObj = {
  render: () => (
    <ToggleGroup type="multiple" variant="outline">
      <ToggleGroupItem value="b">B</ToggleGroupItem>
      <ToggleGroupItem value="i">I</ToggleGroupItem>
      <ToggleGroupItem value="u">U</ToggleGroupItem>
    </ToggleGroup>
  ),
};
