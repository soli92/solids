import * as React from "react";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Carousel", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Scorrevole: StoryObj = {
  render: () => (
    <Carousel className="w-full max-w-xs">
      <CarouselContent>
        {[1, 2, 3].map((i) => (
          <CarouselItem key={i}>
            <div className="flex aspect-square items-center justify-center rounded-md border bg-muted p-6 text-2xl font-semibold">
              {i}
            </div>
          </CarouselItem>
        ))}
      </CarouselContent>
      <CarouselPrevious />
      <CarouselNext />
    </Carousel>
  ),
};
