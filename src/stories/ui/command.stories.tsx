import * as React from "react";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Command", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Ricerca: StoryObj = {
  render: () => (
    <Command className="rounded-lg border shadow-md w-[320px]">
      <CommandInput placeholder="Cerca…" />
      <CommandList>
        <CommandEmpty>Nessun risultato.</CommandEmpty>
        <CommandGroup heading="Suggerimenti">
          <CommandItem>Calendario</CommandItem>
          <CommandItem>Impostazioni</CommandItem>
          <CommandItem>Profilo</CommandItem>
        </CommandGroup>
      </CommandList>
    </Command>
  ),
};
