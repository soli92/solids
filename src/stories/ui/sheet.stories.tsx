import * as React from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Sheet", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Laterale: StoryObj = {
  render: () => (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline">Apri sheet</Button>
      </SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Pannello</SheetTitle>
          <SheetDescription>Scorre dal bordo dello schermo.</SheetDescription>
        </SheetHeader>
      </SheetContent>
    </Sheet>
  ),
};
