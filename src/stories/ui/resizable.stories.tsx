import * as React from "react";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Resizable", parameters: { layout: "padded" } } satisfies Meta;
export default meta;

export const Pannelli: StoryObj = {
  render: () => (
    <ResizablePanelGroup direction="horizontal" className="max-w-md rounded-lg border min-h-[120px]">
      <ResizablePanel defaultSize={50}>
        <div className="flex h-full items-center justify-center p-4 text-sm">A</div>
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={50}>
        <div className="flex h-full items-center justify-center p-4 text-sm">B</div>
      </ResizablePanel>
    </ResizablePanelGroup>
  ),
};
