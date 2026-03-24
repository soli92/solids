import * as UI from "@/components/ui/resizable";
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "SoliDS/UI/Resizable",
  parameters: { layout: "centered" },
} satisfies Meta;

export default meta;

export const Esportazioni: StoryObj = {
  render: () => (
    <div className="max-w-md rounded-lg border border-border bg-card p-4 text-card-foreground shadow-sm">
      <p className="mb-2 font-mono text-xs text-muted-foreground">@/components/ui/resizable</p>
      <p className="text-sm text-muted-foreground">
        Esportazioni:{" "}
        <span className="font-medium text-foreground">
          {Object.keys(UI).join(", ")}
        </span>
      </p>
    </div>
  ),
};
