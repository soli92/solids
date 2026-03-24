import * as React from "react";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
  InputGroupText,
} from "@/components/ui/input-group";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Input Group", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Combinato: StoryObj = {
  render: () => (
    <InputGroup className="max-w-md">
      <InputGroupAddon>
        <InputGroupText>@</InputGroupText>
      </InputGroupAddon>
      <InputGroupInput placeholder="username" />
      <InputGroupAddon align="inline-end">
        <InputGroupButton type="button">Go</InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  ),
};
