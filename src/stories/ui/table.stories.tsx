import * as React from "react";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Table", parameters: { layout: "padded" } } satisfies Meta;
export default meta;

export const Dati: StoryObj = {
  render: () => (
    <Table>
      <TableCaption>Esempio tabella token-aware.</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Nome</TableHead>
          <TableHead>Ruolo</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>Ada</TableCell>
          <TableCell>Dev</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>Alan</TableCell>
          <TableCell>Design</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
};
