import * as React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Card", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Esempio: StoryObj = {
  render: () => (
    <Card className="w-[380px]">
      <CardHeader>
        <CardTitle>Titolo</CardTitle>
        <CardDescription>Breve descrizione della card.</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">Contenuto principale.</p>
      </CardContent>
      <CardFooter className="gap-2">
        <Button size="sm">Azione</Button>
        <Button size="sm" variant="outline">Annulla</Button>
      </CardFooter>
    </Card>
  ),
};
