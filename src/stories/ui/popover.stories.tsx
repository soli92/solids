import * as React from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Popover", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Contenuto: StoryObj = {
  render: () => (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline">Apri popover</Button>
      </PopoverTrigger>
      <PopoverContent className="w-64">
        <p className="text-sm">Contenuto flottante con focus trap.</p>
      </PopoverContent>
    </Popover>
  ),
};
