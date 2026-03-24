import * as React from "react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Sidebar", parameters: { layout: "fullscreen" } } satisfies Meta;
export default meta;

export const Layout: StoryObj = {
  render: () => (
    <SidebarProvider>
      <div className="flex min-h-[320px] w-full">
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>Menu</SidebarGroupLabel>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton>Home</SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton>Impostazioni</SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
        <main className="flex flex-1 flex-col gap-2 p-4">
          <SidebarTrigger />
          <p className="text-sm text-muted-foreground">Contenuto principale accanto alla sidebar.</p>
        </main>
      </div>
    </SidebarProvider>
  ),
};
