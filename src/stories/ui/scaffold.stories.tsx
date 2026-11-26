import * as React from "react";
import {
  Pane,
  PaneHandle,
  Scaffold,
  ScaffoldBar,
  ScaffoldPanes,
  ScaffoldRail,
} from "@/components/ui/scaffold";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Scaffold", parameters: { layout: "fullscreen" } } satisfies Meta;
export default meta;

const box = "rounded-[var(--sd-corner-large)] border border-[var(--sd-color-border-default)] bg-[var(--sd-color-bg-surface)] p-4 text-sm";

export const ListaDettaglio: StoryObj = {
  render: () => {
    const lista = React.useRef<HTMLElement>(null);
    return (
      <Scaffold style={{ minHeight: 420 }}>
        <ScaffoldBar className="p-4 sd-type-title-large">Posta</ScaffoldBar>
        <ScaffoldRail hideBelow="medium" className="p-4 sd-type-label-large">Rail</ScaffoldRail>
        <ScaffoldPanes reflow="below-medium">
          <Pane ref={lista} variant="resizable" scroll className={box}>Lista (trascina la maniglia; frecce, Home, End, Enter)</Pane>
          <PaneHandle pane={lista} storageKey="storybook:scaffold-lista" className="sd-hide-below-expanded" />
          <Pane hideBelow="expanded" className={box}>Dettaglio: compare da expanded (840px)</Pane>
          <Pane variant="fixed" hideBelow="extra-large" as="aside" className={box}>Side sheet: da extra-large (1600px)</Pane>
        </ScaffoldPanes>
        <ScaffoldBar position="bottom" hideFrom="medium" className="p-4 sd-type-label-large">Navigation bar (solo compact)</ScaffoldBar>
      </Scaffold>
    );
  },
};
