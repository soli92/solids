import * as React from "react";
import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Button Group", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Affiancati: StoryObj = {
  render: () => (
    <ButtonGroup>
      <Button variant="outline">Sinistra</Button>
      <Button variant="outline">Centro</Button>
      <Button variant="outline">Destra</Button>
    </ButtonGroup>
  ),
};
