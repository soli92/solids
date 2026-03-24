import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Dialog", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Interattivo: StoryObj = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">Apri dialog</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Modale</DialogTitle>
          <DialogDescription>
            Chiudi con Esc, clic sull&apos;overlay o il pulsante di chiusura.
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  ),
};
