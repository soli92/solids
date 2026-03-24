import * as React from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Scroll Area", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Lista: StoryObj = {
  render: () => (
    <ScrollArea className="h-48 w-64 rounded-md border p-4">
      {Array.from({ length: 24 }, (_, i) => (
        <div key={i} className="py-1 text-sm">Riga {i + 1}</div>
      ))}
    </ScrollArea>
  ),
};
