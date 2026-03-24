import * as React from "react";
import { Button } from "@/components/ui/button";
import { Toast, ToastAction, ToastDescription, ToastTitle } from "@/components/ui/toast";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Toast", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Statico: StoryObj = {
  render: () => (
    <div className="w-[380px] space-y-4">
      <Toast>
        <div className="grid gap-1">
          <ToastTitle>Notifica</ToastTitle>
          <ToastDescription>Messaggio di esempio (il Toaster gestisce lo stack in app).</ToastDescription>
        </div>
        <ToastAction altText="Ok">Ok</ToastAction>
      </Toast>
      <p className="text-xs text-muted-foreground">Vedi anche la story Toaster per il flusso con hook.</p>
    </div>
  ),
};
