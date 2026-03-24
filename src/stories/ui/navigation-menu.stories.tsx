import * as React from "react";
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from "@/components/ui/navigation-menu";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Navigation Menu", parameters: { layout: "padded" } } satisfies Meta;
export default meta;

export const Nav: StoryObj = {
  render: () => (
    <NavigationMenu>
      <NavigationMenuList>
        <NavigationMenuItem>
          <NavigationMenuTrigger>Voce</NavigationMenuTrigger>
          <NavigationMenuContent>
            <ul className="grid w-[200px] gap-2 p-2">
              <li>
                <NavigationMenuLink className="block rounded p-2 hover:bg-accent" href="#">
                  Link A
                </NavigationMenuLink>
              </li>
              <li>
                <NavigationMenuLink className="block rounded p-2 hover:bg-accent" href="#">
                  Link B
                </NavigationMenuLink>
              </li>
            </ul>
          </NavigationMenuContent>
        </NavigationMenuItem>
      </NavigationMenuList>
    </NavigationMenu>
  ),
};
