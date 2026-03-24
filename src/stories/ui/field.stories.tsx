import * as React from "react";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Field", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const ConInput: StoryObj = {
  render: () => (
    <Field className="w-[280px]">
      <FieldLabel htmlFor="f-email">Email</FieldLabel>
      <Input id="f-email" type="email" placeholder="tu@esempio.it" />
      <FieldDescription>Useremo solo per accesso.</FieldDescription>
    </Field>
  ),
};
