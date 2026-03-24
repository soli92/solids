import * as React from "react";
import { Button } from "@/components/ui/button";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Hover Card", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Anteprima: StoryObj = {
  render: () => (
    <HoverCard>
      <HoverCardTrigger asChild>
        <Button variant="link">@soli92</Button>
      </HoverCardTrigger>
      <HoverCardContent className="w-80">
        <p className="text-sm">Card ricca al hover con ritardo.</p>
      </HoverCardContent>
    </HoverCard>
  ),
};
