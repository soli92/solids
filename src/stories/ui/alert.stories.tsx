import * as React from "react";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Alert",
  component: Alert,
  parameters: { layout: "centered" },
  argTypes: { variant: { control: "select", options: ["default", "destructive"] } },
} satisfies Meta<typeof Alert>;

export default meta;

type Story = StoryObj<typeof Alert>;

export const Playground: Story = {
  args: { variant: "default" as const },
  render: (args) => (
    <Alert className="max-w-md" {...args}>
      <AlertTitle>Attenzione</AlertTitle>
      <AlertDescription>Messaggio descrittivo dell&apos;alert.</AlertDescription>
    </Alert>
  ),
};
