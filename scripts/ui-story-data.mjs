/**
 * Dati per generate-ui-stories.mjs: story composte (stringa = file CSF intero)
 * e preset Playground (args / argTypes / render) per componenti semplici.
 */

export const compoundStories = {
  card: `import * as React from "react";
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
`,

  dialog: `import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Dialog", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Interattivo: StoryObj = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">Apri dialog</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Modale</DialogTitle>
          <DialogDescription>
            Chiudi con Esc, clic sull&apos;overlay o il pulsante di chiusura.
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  ),
};
`,

  "alert-dialog": `import * as React from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Alert Dialog", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Conferma: StoryObj = {
  render: () => (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive">Elimina</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Sei sicuro?</AlertDialogTitle>
          <AlertDialogDescription>Questa azione non è reversibile.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Annulla</AlertDialogCancel>
          <AlertDialogAction>Continua</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  ),
};
`,

  sheet: `import * as React from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Sheet", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Laterale: StoryObj = {
  render: () => (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline">Apri sheet</Button>
      </SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Pannello</SheetTitle>
          <SheetDescription>Scorre dal bordo dello schermo.</SheetDescription>
        </SheetHeader>
      </SheetContent>
    </Sheet>
  ),
};
`,

  drawer: `import * as React from "react";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Drawer", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Mobile: StoryObj = {
  render: () => (
    <Drawer>
      <DrawerTrigger asChild>
        <Button variant="outline">Apri drawer</Button>
      </DrawerTrigger>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>Drawer</DrawerTitle>
          <DrawerDescription>Tipico pattern mobile / vaul.</DrawerDescription>
        </DrawerHeader>
        <DrawerFooter>
          <DrawerClose asChild>
            <Button variant="outline">Chiudi</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  ),
};
`,

  select: `import * as React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Select", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Scelta: StoryObj = {
  render: () => (
    <Select defaultValue="b">
      <SelectTrigger className="w-[220px]">
        <SelectValue placeholder="Scegli" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="a">Opzione A</SelectItem>
        <SelectItem value="b">Opzione B</SelectItem>
        <SelectItem value="c">Opzione C</SelectItem>
      </SelectContent>
    </Select>
  ),
};
`,

  tabs: `import * as React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Tabs", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Pannelli: StoryObj = {
  render: () => (
    <Tabs defaultValue="1" className="w-[400px]">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="1">Uno</TabsTrigger>
        <TabsTrigger value="2">Due</TabsTrigger>
        <TabsTrigger value="3">Tre</TabsTrigger>
      </TabsList>
      <TabsContent value="1" className="rounded-md border p-4 text-sm">Contenuto tab 1</TabsContent>
      <TabsContent value="2" className="rounded-md border p-4 text-sm">Contenuto tab 2</TabsContent>
      <TabsContent value="3" className="rounded-md border p-4 text-sm">Contenuto tab 3</TabsContent>
    </Tabs>
  ),
};
`,

  accordion: `import * as React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Accordion", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Espandibile: StoryObj = {
  render: () => (
    <Accordion type="single" collapsible className="w-[400px]">
      <AccordionItem value="a">
        <AccordionTrigger>Prima sezione</AccordionTrigger>
        <AccordionContent>Testo nascosto fino all&apos;apertura.</AccordionContent>
      </AccordionItem>
      <AccordionItem value="b">
        <AccordionTrigger>Seconda sezione</AccordionTrigger>
        <AccordionContent>Altro contenuto.</AccordionContent>
      </AccordionItem>
    </Accordion>
  ),
};
`,

  collapsible: `import * as React from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Collapsible", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const ConTrigger: StoryObj = {
  render: () => (
    <Collapsible className="w-[320px] space-y-2">
      <CollapsibleTrigger asChild>
        <Button variant="outline">Mostra / nascondi</Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="rounded-md border p-3 text-sm">
        Contenuto collassabile.
      </CollapsibleContent>
    </Collapsible>
  ),
};
`,

  "dropdown-menu": `import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Dropdown Menu", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Menu: StoryObj = {
  render: () => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">Apri menu</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56">
        <DropdownMenuLabel>Il mio account</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem>Profilo</DropdownMenuItem>
        <DropdownMenuItem>Impostazioni</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem>Esci</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  ),
};
`,

  "context-menu": `import * as React from "react";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Context Menu", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const TastoDestro: StoryObj = {
  render: () => (
    <ContextMenu>
      <ContextMenuTrigger className="flex h-32 w-[280px] items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
        Click destro qui
      </ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem>Copia</ContextMenuItem>
        <ContextMenuItem>Incolla</ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  ),
};
`,

  popover: `import * as React from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Popover", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Contenuto: StoryObj = {
  render: () => (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline">Apri popover</Button>
      </PopoverTrigger>
      <PopoverContent className="w-64">
        <p className="text-sm">Contenuto flottante con focus trap.</p>
      </PopoverContent>
    </Popover>
  ),
};
`,

  tooltip: `import * as React from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Tooltip", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const AlPassaggio: StoryObj = {
  render: () => (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="outline">Passa il mouse</Button>
      </TooltipTrigger>
      <TooltipContent>
        <p>Suggerimento breve</p>
      </TooltipContent>
    </Tooltip>
  ),
};
`,

  "hover-card": `import * as React from "react";
import { Button } from "@/components/ui/button";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Hover Card", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Anteprima: StoryObj = {
  render: () => (
    <HoverCard>
      <HoverCardTrigger asChild>
        <Button variant="link">@soli92</Button>
      </HoverCardTrigger>
      <HoverCardContent className="w-80">
        <p className="text-sm">Card ricca al hover con ritardo.</p>
      </HoverCardContent>
    </HoverCard>
  ),
};
`,

  table: `import * as React from "react";
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
`,

  breadcrumb: `import * as React from "react";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Breadcrumb", parameters: { layout: "padded" } } satisfies Meta;
export default meta;

export const Percorso: StoryObj = {
  render: () => (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink href="#">Home</BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem>
          <BreadcrumbLink href="#">Sezione</BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem>
          <BreadcrumbPage>Pagina</BreadcrumbPage>
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  ),
};
`,

  pagination: `import * as React from "react";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Pagination", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Pagine: StoryObj = {
  render: () => (
    <Pagination>
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious href="#" />
        </PaginationItem>
        <PaginationItem>
          <PaginationLink href="#" isActive>1</PaginationLink>
        </PaginationItem>
        <PaginationItem>
          <PaginationLink href="#">2</PaginationLink>
        </PaginationItem>
        <PaginationItem>
          <PaginationNext href="#" />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  ),
};
`,

  menubar: `import * as React from "react";
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarSeparator,
  MenubarTrigger,
} from "@/components/ui/menubar";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Menubar", parameters: { layout: "padded" } } satisfies Meta;
export default meta;

export const Barra: StoryObj = {
  render: () => (
    <Menubar>
      <MenubarMenu>
        <MenubarTrigger>File</MenubarTrigger>
        <MenubarContent>
          <MenubarItem>Nuovo</MenubarItem>
          <MenubarSeparator />
          <MenubarItem>Esci</MenubarItem>
        </MenubarContent>
      </MenubarMenu>
      <MenubarMenu>
        <MenubarTrigger>Modifica</MenubarTrigger>
        <MenubarContent>
          <MenubarItem>Taglia</MenubarItem>
          <MenubarItem>Copia</MenubarItem>
        </MenubarContent>
      </MenubarMenu>
    </Menubar>
  ),
};
`,

  "navigation-menu": `import * as React from "react";
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
`,

  command: `import * as React from "react";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Command", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Ricerca: StoryObj = {
  render: () => (
    <Command className="rounded-lg border shadow-md w-[320px]">
      <CommandInput placeholder="Cerca…" />
      <CommandList>
        <CommandEmpty>Nessun risultato.</CommandEmpty>
        <CommandGroup heading="Suggerimenti">
          <CommandItem>Calendario</CommandItem>
          <CommandItem>Impostazioni</CommandItem>
          <CommandItem>Profilo</CommandItem>
        </CommandGroup>
      </CommandList>
    </Command>
  ),
};
`,

  calendar: `import * as React from "react";
import { Calendar } from "@/components/ui/calendar";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Calendar", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Mese: StoryObj = {
  render: function R() {
    const [d, setD] = React.useState<Date | undefined>(new Date());
    return <Calendar mode="single" selected={d} onSelect={setD} className="rounded-md border" />;
  },
};
`,

  "toggle-group": `import * as React from "react";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Toggle Group", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Gruppo: StoryObj = {
  render: () => (
    <ToggleGroup type="multiple" variant="outline">
      <ToggleGroupItem value="b">B</ToggleGroupItem>
      <ToggleGroupItem value="i">I</ToggleGroupItem>
      <ToggleGroupItem value="u">U</ToggleGroupItem>
    </ToggleGroup>
  ),
};
`,

  avatar: `import * as React from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Avatar", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const ConFallback: StoryObj = {
  render: () => (
    <div className="flex gap-4">
      <Avatar>
        <AvatarImage src="https://github.com/shadcn.png" alt="Utente" />
        <AvatarFallback>CN</AvatarFallback>
      </Avatar>
      <Avatar>
        <AvatarFallback>SO</AvatarFallback>
      </Avatar>
    </div>
  ),
};
`,

  toast: `import * as React from "react";
import { Button } from "@/components/ui/button";
import { Toast, ToastAction, ToastDescription, ToastTitle } from "@/components/ui/toast";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Toast", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Statico: StoryObj = {
  render: () => (
    <div className="w-[380px] space-y-4">
      <Toast>
        <div className="grid gap-1">
          <ToastTitle>Notifica</ToastTitle>
          <ToastDescription>Messaggio di esempio (il Toaster gestisce lo stack in app).</ToastDescription>
        </div>
        <ToastAction altText="Ok">Ok</ToastAction>
      </Toast>
      <p className="text-xs text-muted-foreground">Vedi anche la story Toaster per il flusso con hook.</p>
    </div>
  ),
};
`,

  toaster: `import * as React from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import type { Meta, StoryObj } from "@storybook/react";

function Demo() {
  const { toast } = useToast();
  return (
    <div className="flex flex-col gap-2">
      <Button
        onClick={() =>
          toast({ title: "Salvato", description: "Le modifiche sono state applicate." })
        }
      >
        Mostra toast
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          toast({
            title: "Azione richiesta",
            description: "Conferma o annulla.",
            action: <Button size="sm">Undo</Button>,
          })
        }
      >
        Toast con azione
      </Button>
    </div>
  );
}

const meta = { title: "SoliDS/UI/Toaster", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const ConHook: StoryObj = {
  render: () => <Demo />,
};
`,

  sonner: `import * as React from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Sonner", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Messaggi: StoryObj = {
  render: () => (
    <div className="flex gap-2">
      <Button onClick={() => toast.success("Operazione riuscita")}>Success</Button>
      <Button variant="destructive" onClick={() => toast.error("Qualcosa è andato storto")}>
        Error
      </Button>
    </div>
  ),
};
`,

  "input-otp": `import * as React from "react";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSeparator,
  InputOTPSlot,
} from "@/components/ui/input-otp";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Input Otp", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Codice: StoryObj = {
  render: () => (
    <InputOTP maxLength={6}>
      <InputOTPGroup>
        <InputOTPSlot index={0} />
        <InputOTPSlot index={1} />
        <InputOTPSlot index={2} />
      </InputOTPGroup>
      <InputOTPSeparator />
      <InputOTPGroup>
        <InputOTPSlot index={3} />
        <InputOTPSlot index={4} />
        <InputOTPSlot index={5} />
      </InputOTPGroup>
    </InputOTP>
  ),
};
`,

  "input-group": `import * as React from "react";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
  InputGroupText,
} from "@/components/ui/input-group";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Input Group", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Combinato: StoryObj = {
  render: () => (
    <InputGroup className="max-w-md">
      <InputGroupAddon>
        <InputGroupText>@</InputGroupText>
      </InputGroupAddon>
      <InputGroupInput placeholder="username" />
      <InputGroupAddon align="inline-end">
        <InputGroupButton type="button">Go</InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  ),
};
`,

  "button-group": `import * as React from "react";
import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Button Group", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Affiancati: StoryObj = {
  render: () => (
    <ButtonGroup>
      <Button variant="outline">Sinistra</Button>
      <Button variant="outline">Centro</Button>
      <Button variant="outline">Destra</Button>
    </ButtonGroup>
  ),
};
`,

  "scroll-area": `import * as React from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Scroll Area", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Lista: StoryObj = {
  render: () => (
    <ScrollArea className="h-48 w-64 rounded-md border p-4">
      {Array.from({ length: 24 }, (_, i) => (
        <div key={i} className="py-1 text-sm">Riga {i + 1}</div>
      ))}
    </ScrollArea>
  ),
};
`,

  resizable: `import * as React from "react";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Resizable", parameters: { layout: "padded" } } satisfies Meta;
export default meta;

export const Pannelli: StoryObj = {
  render: () => (
    <ResizablePanelGroup orientation="horizontal" className="max-w-md rounded-lg border min-h-[120px]">
      <ResizablePanel defaultSize={50}>
        <div className="flex h-full items-center justify-center p-4 text-sm">A</div>
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={50}>
        <div className="flex h-full items-center justify-center p-4 text-sm">B</div>
      </ResizablePanel>
    </ResizablePanelGroup>
  ),
};
`,

  carousel: `import * as React from "react";
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
`,

  chart: `import * as React from "react";
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
`,

  sidebar: `import * as React from "react";
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
`,

  empty: `import * as React from "react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Empty", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const StatoVuoto: StoryObj = {
  render: () => (
    <Empty className="w-[360px] border">
      <EmptyHeader>
        <EmptyTitle>Nessun elemento</EmptyTitle>
        <EmptyDescription>Crea il primo record per iniziare.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button size="sm">Nuovo</Button>
      </EmptyContent>
    </Empty>
  ),
};
`,

  item: `import * as React from "react";
import { Item, ItemContent, ItemDescription, ItemTitle } from "@/components/ui/item";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Item", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const Riga: StoryObj = {
  render: () => (
    <Item className="w-[320px]">
      <ItemContent>
        <ItemTitle>Titolo riga</ItemTitle>
        <ItemDescription>Descrizione secondaria.</ItemDescription>
      </ItemContent>
    </Item>
  ),
};
`,

  field: `import * as React from "react";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { Meta, StoryObj } from "@storybook/react";

const meta = { title: "SoliDS/UI/Field", parameters: { layout: "centered" } } satisfies Meta;
export default meta;

export const ConInput: StoryObj = {
  render: () => (
    <Field className="w-[280px]">
      <FieldLabel htmlFor="f-email">Email</FieldLabel>
      <Input id="f-email" type="email" placeholder="tu@esempio.it" />
      <FieldDescription>Useremo solo per accesso.</FieldDescription>
    </Field>
  ),
};
`,

  form: `import * as React from "react";
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
`,
};

/** Preset Playground: component, args (stringa oggetto), argTypes (stringa oggetto), render (stringa fn) */
export const playgroundPresets = {
  button: {
    component: "Button",
    args: `{ children: "Pulsante", variant: "default", size: "default", disabled: false }`,
    argTypes: `{
    children: { control: "text" },
    variant: { control: "select", options: ["default", "destructive", "outline", "secondary", "ghost", "link"] },
    size: { control: "select", options: ["default", "sm", "lg", "icon"] },
    disabled: { control: "boolean" },
  }`,
    render: `(args: { children?: React.ReactNode } & Record<string, unknown>) => <Button {...args}>{args.children}</Button>`,
  },
  input: {
    component: "Input",
    args: `{ type: "text", placeholder: "Scrivi qui…", disabled: false }`,
    argTypes: `{
    type: { control: "select", options: ["text", "email", "password", "search", "url"] },
    placeholder: { control: "text" },
    disabled: { control: "boolean" },
  }`,
    render: `(args) => <Input {...args} />`,
  },
  textarea: {
    component: "Textarea",
    args: `{ placeholder: "Messaggio…", rows: 4, disabled: false }`,
    argTypes: `{ placeholder: { control: "text" }, rows: { control: "number" }, disabled: { control: "boolean" } }`,
    render: `(args) => <Textarea {...args} />`,
  },
  label: {
    component: "Label",
    args: `{ children: "Etichetta campo" }`,
    argTypes: `{ children: { control: "text" } }`,
    render: `(args: { children?: React.ReactNode } & Record<string, unknown>) => <Label {...args}>{args.children}</Label>`,
  },
  checkbox: {
    component: "Checkbox",
    args: `{ disabled: false }`,
    argTypes: `{ disabled: { control: "boolean" } }`,
    render: `function R(args: Record<string, unknown>) {
    const [c, setC] = React.useState(false);
    return (
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={c} onCheckedChange={(v) => setC(v === true)} {...args} />
        Accetto i termini
      </label>
    );
  }`,
  },
  switch: {
    component: "Switch",
    args: `{ disabled: false }`,
    argTypes: `{ disabled: { control: "boolean" } }`,
    render: `function R(args: Record<string, unknown>) {
    const [on, setOn] = React.useState(false);
    return (
      <div className="flex items-center gap-2">
        <Switch checked={on} onCheckedChange={setOn} {...args} />
        <span className="text-sm text-muted-foreground">{on ? "On" : "Off"}</span>
      </div>
    );
  }`,
  },
  slider: {
    component: "Slider",
    args: `{ defaultValue: [50], max: 100, step: 1, disabled: false }`,
    argTypes: `{ disabled: { control: "boolean" } }`,
    render: `(args) => <Slider className="w-[220px]" {...args} />`,
  },
  progress: {
    component: "Progress",
    args: `{ value: 60 }`,
    argTypes: `{ value: { control: { type: "range", min: 0, max: 100 } } }`,
    render: `(args) => <Progress className="w-[240px]" {...args} />`,
  },
  skeleton: {
    component: "Skeleton",
    args: `{}`,
    argTypes: `{}`,
    render: `() => (
    <div className="flex items-center space-x-4">
      <Skeleton className="h-12 w-12 rounded-full" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-[250px]" />
        <Skeleton className="h-4 w-[200px]" />
      </div>
    </div>
  )`,
  },
  separator: {
    component: "Separator",
    args: `{ orientation: "horizontal" as const }`,
    argTypes: `{ orientation: { control: "select", options: ["horizontal", "vertical"] } }`,
    render: `(args) => (
    <div>
      <div className="space-y-1">
        <h4 className="text-sm font-medium leading-none">Sezione</h4>
        <p className="text-sm text-muted-foreground">Testo sopra il separatore.</p>
      </div>
      <Separator className="my-4" {...args} />
      <p className="text-sm text-muted-foreground">Sotto.</p>
    </div>
  )`,
  },
  kbd: {
    component: "Kbd",
    args: `{}`,
    argTypes: `{}`,
    render: `() => (
    <p className="text-sm">
      Premi <Kbd className="pointer-events-none">⌘</Kbd> + <Kbd className="pointer-events-none">K</Kbd>
    </p>
  )`,
  },
  spinner: {
    component: "Spinner",
    args: `{}`,
    argTypes: `{}`,
    render: `() => <Spinner className="size-8" />`,
  },
  "logo-loader": {
    component: "LogoLoader",
    imports: `import { LogoLoader } from "@/components/ui/logo-loader";
import logoPng from "../../../docs/brand-assets/soli-category-icons/soli-icon-logo.png";
import logoSvg from "../../../docs/brand-assets/soli-category-icons/soli-icon-logo.svg";
import symbolSvg from "../../../docs/brand-assets/soli-category-icons/soli-icon-symbol.svg";`,
    args: `{
    src: undefined,
    size: 120,
    animation: "spin" as const,
    durationMs: 1400,
    alt: "Loading"
  }`,
    argTypes: `{
    src: {
      control: "select",
      options: ["__default__", "logo-svg", "logo-png", "symbol-svg"],
      mapping: {
        __default__: undefined,
        "logo-svg": logoSvg,
        "logo-png": logoPng,
        "symbol-svg": symbolSvg
      }
    },
    size: { control: { type: "range", min: 48, max: 220, step: 4 } },
    animation: { control: "inline-radio", options: ["spin", "pulse", "none"] },
    durationMs: { control: { type: "range", min: 400, max: 4000, step: 100 } },
    alt: { control: "text" }
  }`,
    render: `(args) => <LogoLoader {...args} />`,
  },
  badge: {
    component: "Badge",
    args: `{ children: "Badge", variant: "default" }`,
    argTypes: `{
    children: { control: "text" },
    variant: { control: "select", options: ["default", "secondary", "destructive", "outline"] },
  }`,
    render: `(args: { children?: React.ReactNode } & Record<string, unknown>) => <Badge {...args}>{args.children}</Badge>`,
  },
  alert: {
    component: "Alert",
    imports: `import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";`,
    args: `{ variant: "default" as const }`,
    argTypes: `{ variant: { control: "select", options: ["default", "destructive"] } }`,
    render: `(args) => (
    <Alert className="max-w-md" {...args}>
      <AlertTitle>Attenzione</AlertTitle>
      <AlertDescription>Messaggio descrittivo dell&apos;alert.</AlertDescription>
    </Alert>
  )`,
  },
  toggle: {
    component: "Toggle",
    args: `{ defaultPressed: false, variant: "default", size: "default", disabled: false }`,
    argTypes: `{
    variant: { control: "select", options: ["default", "outline"] },
    size: { control: "select", options: ["default", "sm", "lg"] },
    disabled: { control: "boolean" },
  }`,
    render: `(args) => <Toggle {...args}>Grassetto</Toggle>`,
  },
  "radio-group": {
    component: "RadioGroup",
    imports: `import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";`,
    args: `{}`,
    argTypes: `{}`,
    render: `() => (
    <RadioGroup defaultValue="a" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <RadioGroupItem value="a" id="rg-a" />
        <Label htmlFor="rg-a">Opzione A</Label>
      </div>
      <div className="flex items-center gap-2">
        <RadioGroupItem value="b" id="rg-b" />
        <Label htmlFor="rg-b">Opzione B</Label>
      </div>
    </RadioGroup>
  )`,
  },
  "aspect-ratio": {
    component: "AspectRatio",
    args: `{ ratio: 16 / 9 }`,
    argTypes: `{}`,
    render: `(args) => (
    <div className="w-[280px] overflow-hidden rounded-md border">
      <AspectRatio {...args}>
        <div className="flex h-full items-center justify-center bg-muted text-sm">16:9</div>
      </AspectRatio>
    </div>
  )`,
  },
};
