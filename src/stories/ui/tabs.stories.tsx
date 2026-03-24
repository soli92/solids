import * as React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Tabs", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Pannelli: StoryObj = {
  render: () => (
    <Tabs defaultValue="1" className="w-[400px]">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="1">Uno</TabsTrigger>
        <TabsTrigger value="2">Due</TabsTrigger>
        <TabsTrigger value="3">Tre</TabsTrigger>
      </TabsList>
      <TabsContent value="1" className="rounded-md border p-4 text-sm">Contenuto tab 1</TabsContent>
      <TabsContent value="2" className="rounded-md border p-4 text-sm">Contenuto tab 2</TabsContent>
      <TabsContent value="3" className="rounded-md border p-4 text-sm">Contenuto tab 3</TabsContent>
    </Tabs>
  ),
};
