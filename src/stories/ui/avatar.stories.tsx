import * as React from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Avatar", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const ConFallback: StoryObj = {
  render: () => (
    <div className="flex gap-4">
      <Avatar>
        <AvatarImage src="https://github.com/shadcn.png" alt="Utente" />
        <AvatarFallback>CN</AvatarFallback>
      </Avatar>
      <Avatar>
        <AvatarFallback>SO</AvatarFallback>
      </Avatar>
    </div>
  ),
};
