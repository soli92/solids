import * as React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Accordion", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Espandibile: StoryObj = {
  render: () => (
    <Accordion type="single" collapsible className="w-[400px]">
      <AccordionItem value="a">
        <AccordionTrigger>Prima sezione</AccordionTrigger>
        <AccordionContent>Testo nascosto fino all&apos;apertura.</AccordionContent>
      </AccordionItem>
      <AccordionItem value="b">
        <AccordionTrigger>Seconda sezione</AccordionTrigger>
        <AccordionContent>Altro contenuto.</AccordionContent>
      </AccordionItem>
    </Accordion>
  ),
};
