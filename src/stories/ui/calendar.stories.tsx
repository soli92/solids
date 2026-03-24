import * as React from "react";
import { Calendar } from "@/components/ui/calendar";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Calendar", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Mese: StoryObj = {
  render: function R() {
    const [d, setD] = React.useState<Date | undefined>(new Date());
    return <Calendar mode="single" selected={d} onSelect={setD} className="rounded-md border" />;
  },
};
