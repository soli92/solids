import * as React from "react";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Context Menu", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const TastoDestro: StoryObj = {
  render: () => (
    <ContextMenu>
      <ContextMenuTrigger className="flex h-32 w-[280px] items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
        Click destro qui
      </ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem>Copia</ContextMenuItem>
        <ContextMenuItem>Incolla</ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  ),
};
