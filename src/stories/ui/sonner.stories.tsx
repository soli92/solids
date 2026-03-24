import * as React from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Sonner", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Messaggi: StoryObj = {
  render: () => (
    <div className="flex gap-2">
      <Button onClick={() => toast.success("Operazione riuscita")}>Success</Button>
      <Button variant="destructive" onClick={() => toast.error("Qualcosa è andato storto")}>
        Error
      </Button>
    </div>
  ),
};
