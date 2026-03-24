import { Button } from "@/components/ui/button";

const meta = {
  title: "SoliDS/shadcn/Button",
  component: Button,
  parameters: {
    layout: "centered",
  },
  tags: ["autodocs"],
  argTypes: {
    variant: {
      control: "select",
      options: ["default", "destructive", "outline", "secondary", "ghost", "link"],
    },
    size: {
      control: "select",
      options: ["default", "sm", "lg", "icon"],
    },
  },
};

export default meta;

export const Default = {
  args: {
    children: "Button",
  },
};

export const Destructive = {
  args: {
    variant: "destructive",
    children: "Elimina",
  },
};

export const Outline = {
  args: {
    variant: "outline",
    children: "Outline",
  },
};
