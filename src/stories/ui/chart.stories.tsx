import * as React from "react";
import { Bar, BarChart, CartesianGrid, XAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import type { Meta, StoryObj } from "@storybook/react";

const data = [
  { m: "Gen", v: 120 },
  { m: "Feb", v: 200 },
  { m: "Mar", v: 150 },
];

const config = {
  v: { label: "Valore", color: "var(--chart-1)" },
} satisfies ChartConfig;

const meta = { title: "SoliDS/UI/Chart", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Barre: StoryObj = {
  render: () => (
    <ChartContainer config={config} className="h-[220px] w-[360px]">
      <BarChart accessibilityLayer data={data}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="m" tickLine={false} axisLine={false} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="v" fill="var(--color-v)" radius={4} />
      </BarChart>
    </ChartContainer>
  ),
};
