import * as React from "react";
import { Item, ItemContent, ItemDescription, ItemTitle } from "@/components/ui/item";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Item", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Riga: StoryObj = {
  render: () => (
    <Item className="w-[320px]">
      <ItemContent>
        <ItemTitle>Titolo riga</ItemTitle>
        <ItemDescription>Descrizione secondaria.</ItemDescription>
      </ItemContent>
    </Item>
  ),
};
