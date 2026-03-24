import * as React from "react";
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarSeparator,
  MenubarTrigger,
} from "@/components/ui/menubar";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Menubar", parameters: { layout: "padded" } } satisfies Meta;
export default meta;

export const Barra: StoryObj = {
  render: () => (
    <Menubar>
      <MenubarMenu>
        <MenubarTrigger>File</MenubarTrigger>
        <MenubarContent>
          <MenubarItem>Nuovo</MenubarItem>
          <MenubarSeparator />
          <MenubarItem>Esci</MenubarItem>
        </MenubarContent>
      </MenubarMenu>
      <MenubarMenu>
        <MenubarTrigger>Modifica</MenubarTrigger>
        <MenubarContent>
          <MenubarItem>Taglia</MenubarItem>
          <MenubarItem>Copia</MenubarItem>
        </MenubarContent>
      </MenubarMenu>
    </Menubar>
  ),
};
