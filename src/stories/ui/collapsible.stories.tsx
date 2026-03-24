import * as React from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Collapsible", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const ConTrigger: StoryObj = {
  render: () => (
    <Collapsible className="w-[320px] space-y-2">
      <CollapsibleTrigger asChild>
        <Button variant="outline">Mostra / nascondi</Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="rounded-md border p-3 text-sm">
        Contenuto collassabile.
      </CollapsibleContent>
    </Collapsible>
  ),
};
