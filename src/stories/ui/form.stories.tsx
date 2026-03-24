import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import type { Meta, StoryObj } from "@storybook/react";

const schema = z.object({ username: z.string().min(2, "Almeno 2 caratteri") });
type Values = z.infer<typeof schema>;

function DemoForm() {
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { username: "" } });
  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(() => undefined)}
        className="w-[280px] space-y-4"
      >
        <FormField
          control={form.control}
          name="username"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Username</FormLabel>
              <FormControl>
                <Input placeholder="shadcn" {...field} />
              </FormControl>
              <FormDescription>Nome pubblico.</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit">Invia</Button>
      </form>
    </Form>
  );
}

const meta = { title: "SoliDS/UI/Form", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const ReactHookForm: StoryObj = {
  render: () => <DemoForm />,
};
