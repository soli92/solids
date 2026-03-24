import * as React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Select", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Scelta: StoryObj = {
  render: () => (
    <Select defaultValue="b">
      <SelectTrigger className="w-[220px]">
        <SelectValue placeholder="Scegli" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="a">Opzione A</SelectItem>
        <SelectItem value="b">Opzione B</SelectItem>
        <SelectItem value="c">Opzione C</SelectItem>
      </SelectContent>
    </Select>
  ),
};
