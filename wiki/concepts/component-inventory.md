---
id: component-inventory
type: concept
title: "SoliDS — Component Inventory"
status: stable
created: 2026-06-15
updated: 2026-06-15
---

# SoliDS — Component Inventory

56 componenti React in `src/components/ui/`. Tutti usano `cva` (class-variance-authority) per le varianti e `cn` (clsx + tailwind-merge) per classi.

## Componenti disponibili

### Layout & Contenitori

| Componente | File | Note |
|-----------|------|------|
| `Card` | card.tsx | Surface contenitore. Export: Card, CardHeader, CardContent, CardFooter, CardTitle, CardDescription |
| `Separator` | separator.tsx | Divisore orizzontale/verticale |
| `AspectRatio` | aspect-ratio.tsx | Contenitore con aspect ratio fisso (Radix) |
| `ResizablePanel` | resizable.tsx | Pannelli ridimensionabili (react-resizable-panels) |
| `ScrollArea` | scroll-area.tsx | Scroll area con scrollbar custom (Radix) |

### Form & Input

| Componente | File | Note |
|-----------|------|------|
| `Button` | button.tsx | Varianti: default, secondary, outline, ghost, destructive, link. Size: default, sm, lg, icon |
| `ButtonGroup` | button-group.tsx | Gruppo di button collegati |
| `Input` | input.tsx | Input testuale base |
| `InputGroup` | input-group.tsx | Input con addons prefix/suffix |
| `InputOTP` | input-otp.tsx | OTP 6-digit (input-otp lib) |
| `Textarea` | textarea.tsx | Area testo multi-riga |
| `Checkbox` | checkbox.tsx | Checkbox con stato checked/indeterminate (Radix) |
| `RadioGroup` | radio-group.tsx | Gruppo radio (Radix) |
| `Switch` | switch.tsx | Toggle on/off (Radix) |
| `Slider` | slider.tsx | Slider range (Radix) |
| `Select` | select.tsx | Dropdown select (Radix) |
| `Label` | label.tsx | Label accessibile (Radix) |
| `Field` | field.tsx | Wrapper label + input + error |
| `Form` | form.tsx | Form con react-hook-form + zod |
| `Calendar` | calendar.tsx | Date picker (react-day-picker) |
| `Toggle` | toggle.tsx | Toggle button (Radix) |
| `ToggleGroup` | toggle-group.tsx | Gruppo di toggle (Radix) |

### Overlay & Feedback

| Componente | File | Note |
|-----------|------|------|
| `Dialog` | dialog.tsx | Modal dialog (Radix) |
| `AlertDialog` | alert-dialog.tsx | Dialog di conferma/alert (Radix) |
| `Sheet` | sheet.tsx | Pannello slide-in (Radix) |
| `Drawer` | drawer.tsx | Drawer mobile (vaul) |
| `Popover` | popover.tsx | Popover floating (Radix) |
| `HoverCard` | hover-card.tsx | Card on hover (Radix) |
| `Tooltip` | tooltip.tsx | Tooltip breve (Radix) |
| `Alert` | alert.tsx | Alert inline. Varianti: default, destructive |
| `Toast` | toast.tsx | Toast notification (Radix) |
| `Toaster` | toaster.tsx | Container globale toast |
| `Sonner` | sonner.tsx | Toast alternativo (sonner lib) |
| `Skeleton` | skeleton.tsx | Placeholder loading |
| `Spinner` | spinner.tsx | Indicatore di caricamento |
| `Progress` | progress.tsx | Progress bar (Radix) |

### Navigation

| Componente | File | Note |
|-----------|------|------|
| `Tabs` | tabs.tsx | Tab navigation (Radix) |
| `Breadcrumb` | breadcrumb.tsx | Breadcrumb navigation |
| `NavigationMenu` | navigation-menu.tsx | Menu navigazione orizzontale (Radix) |
| `Menubar` | menubar.tsx | Menu bar stile desktop (Radix) |
| `Pagination` | pagination.tsx | Paginazione |
| `Sidebar` | sidebar.tsx | Sidebar layout con collasso |

### Data & Display

| Componente | File | Note |
|-----------|------|------|
| `Badge` | badge.tsx | Etichetta colorata. Varianti: default, secondary, outline, destructive |
| `Avatar` | avatar.tsx | Avatar immagine/iniziali (Radix) |
| `Table` | table.tsx | Tabella dati |
| `Chart` | chart.tsx | Chart wrapper (recharts) |
| `Carousel` | carousel.tsx | Carosello (embla-carousel) |
| `KBD` | kbd.tsx | Shortcut tastiera |
| `Item` | item.tsx | Item list generico |
| `Empty` | empty.tsx | Stato vuoto |
| `LogoLoader` | logo-loader.tsx | Loader animato con logo Soli |

### Interactive & Utility

| Componente | File | Note |
|-----------|------|------|
| `Command` | command.tsx | Command palette (cmdk) |
| `Accordion` | accordion.tsx | Accordion collassabile (Radix) |
| `Collapsible` | collapsible.tsx | Sezione collassabile (Radix) |
| `DropdownMenu` | dropdown-menu.tsx | Menu contestuale dropdown (Radix) |
| `ContextMenu` | context-menu.tsx | Menu contestuale tasto destro (Radix) |

## API comune

Tutti i componenti seguono il pattern shadcn/ui:
- Props `className` per customizzazione CSS
- Props `asChild` (Radix Slot) dove supportato
- `cva` per gestione varianti tipizzate
- Export named (non default export)
- Compatibili con `@soli92/solids` registry CLI: `shadcn add <component>`
