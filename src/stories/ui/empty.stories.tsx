import * as React from "react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Empty", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const StatoVuoto: StoryObj = {
  render: () => (
    <Empty className="w-[360px] border">
      <EmptyHeader>
        <EmptyTitle>Nessun elemento</EmptyTitle>
        <EmptyDescription>Crea il primo record per iniziare.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button size="sm">Nuovo</Button>
      </EmptyContent>
    </Empty>
  ),
};
