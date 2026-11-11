import * as React from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemSeparator,
  ItemTitle,
} from "@/components/ui/item";
import { MODALITA, dati, type DatiModalita, type Membro } from "./lista-membri.fixtures";

/**
 * Lista membri = Item + Avatar + Badge, composti come farebbe un consumatore del DS.
 * Il toggle Demo / Caso peggiore / Vuoto / Uno / 1.000 righe e' SOLO dev: l'arg `dati`
 * (pannello Controls, oppure URL `&args=dati:peggiore`). Il componente non lo conosce:
 * la fixture si sceglie qui, al confine dei dati.
 */
type Props = { dati: DatiModalita };

function iniziali(nome: string): string {
  // Implementazione volutamente ingenua, tipica di un consumatore.
  return nome.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();
}

function Riga({ m }: { m: Membro }) {
  return (
    <Item variant="outline" size="sm" data-testid="riga-membro">
      <ItemMedia>
        <Avatar>
          {m.avatarUrl ? <AvatarImage src={m.avatarUrl} alt="" /> : null}
          <AvatarFallback>{m.nome ? iniziali(m.nome) : "?"}</AvatarFallback>
        </Avatar>
      </ItemMedia>
      <ItemContent>
        <ItemTitle>{m.nome}</ItemTitle>
        <ItemDescription>{m.email}</ItemDescription>
        {m.ruolo ? <ItemDescription>{m.ruolo}</ItemDescription> : null}
      </ItemContent>
      <ItemActions>
        <Badge variant={m.stato === "scaduto" || m.stato === "sospeso" ? "destructive" : m.stato === "invitato" ? "secondary" : "default"}>
          {m.stato === "scaduto" && m.ultimoAccessoGiorni ? `Invito scaduto da ${m.ultimoAccessoGiorni} giorni` : m.stato}
        </Badge>
      </ItemActions>
    </Item>
  );
}

function ListaMembri({ dati: modalita }: Props) {
  const righe = dati(modalita);
  return (
    <div data-testid="lista-membri" data-modalita={modalita} className="w-full max-w-[480px]">
      <h3 className="mb-2 text-sm font-semibold" data-testid="intestazione">
        {righe.length} membri
      </h3>
      {righe.length === 0 ? (
        <p data-testid="vuoto" className="text-sm text-muted-foreground">Nessun membro.</p>
      ) : (
        <ItemGroup>
          {righe.map((m, i) => (
            <React.Fragment key={m.id}>
              {i > 0 ? <ItemSeparator /> : null}
              <Riga m={m} />
            </React.Fragment>
          ))}
        </ItemGroup>
      )}
    </div>
  );
}

const meta = {
  title: "SoliDS/Esempi/Lista membri (caso peggiore)",
  component: ListaMembri,
  parameters: { layout: "padded", viewMode: "story" },
  args: { dati: "demo" },
  argTypes: {
    dati: {
      description: "Solo dev: fixture dei dati (demo / peggiore / vuoto / uno / mille).",
      control: { type: "inline-radio" },
      options: MODALITA,
    },
  },
} satisfies Meta<typeof ListaMembri>;
export default meta;

type S = StoryObj<typeof meta>;
export const Lista: S = {};
