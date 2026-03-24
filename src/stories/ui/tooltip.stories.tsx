import * as React from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Tooltip", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const AlPassaggio: StoryObj = {
  render: () => (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="outline">Passa il mouse</Button>
      </TooltipTrigger>
      <TooltipContent>
        <p>Suggerimento breve</p>
      </TooltipContent>
    </Tooltip>
  ),
};
