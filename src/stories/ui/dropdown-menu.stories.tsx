import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Dropdown Menu", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Menu: StoryObj = {
  render: () => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">Apri menu</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56">
        <DropdownMenuLabel>Il mio account</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem>Profilo</DropdownMenuItem>
        <DropdownMenuItem>Impostazioni</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem>Esci</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  ),
};
