import * as React from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import type { Meta, StoryObj } from "@storybook/react";

function Demo() {
  const { toast } = useToast();
  return (
    <div className="flex flex-col gap-2">
      <Button
        onClick={() =>
          toast({ title: "Salvato", description: "Le modifiche sono state applicate." })
        }
      >
        Mostra toast
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          toast({
            title: "Azione richiesta",
            description: "Conferma o annulla.",
            action: <Button size="sm">Undo</Button>,
          })
        }
      >
        Toast con azione
      </Button>
    </div>
  );
}

const meta = { title: "SoliDS/UI/Toaster", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const ConHook: StoryObj = {
  render: () => <Demo />,
};
