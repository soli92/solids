---
id: icon-system
type: concept
title: "SoliDS — Icon System"
status: draft
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/raw/analisi-repository-2026-07-17.txt §2.2 Sistema icone (post-bonifica)"
  - "docs/raw/analisi-repository-2026-07-17.txt §1.2 docs/foundations/ — Storybook MDX"
  - "docs/raw/bonifica-repo-2026-07-17.txt §Sezione 1 — Design System: icone duplicate"
  - "docs/raw/bonifica-repo-2026-07-17.txt §Sezione 2 — Design System: import path rotto"
  - "docs/foundations/icons.mdx §Utilizzo base"
  - "docs/foundations/icons.mdx §Prop variant"
  - "docs/foundations/icons.mdx §Prop size"
  - "docs/foundations/icons.mdx §Gallery icone base"
  - "docs/foundations/icons.mdx §Soli Brand Icon Pack (image set #2)"
  - "docs/foundations/icons.mdx §Aggiungere icone personalizzate"
---

# SoliDS — Icon System

Sistema di icone SVG React del design system, nella struttura consolidata dalla bonifica del 2026-07-17.[^src: docs/raw/analisi-repository-2026-07-17.txt §2.2 Sistema icone (post-bonifica)]

## Struttura sorgente (post-bonifica)

```
src/icons/
├── glyphs.tsx          — icone base universali (~246 righe, senza duplicati tematici)
├── glyphs-themed.tsx   — icone tematiche (Fantasy x3, Cyberpunk x3, Party x3)
├── solids-icon.tsx     — wrapper SolidsIcon con token CSS automatici
└── index.ts            — re-export di tutti e tre

src/lib/icons/
└── index.ts            — bridge: re-export da @/icons (compat. consumer registry shadcn)
```

## SolidsIcon — il wrapper principale

`SolidsIcon` e' il componente di rendering delle icone. Applica automaticamente i token CSS `--sd-color-icon-*`.[^src: docs/raw/analisi-repository-2026-07-17.txt §1.2 docs/foundations/ — Storybook MDX]

### Utilizzo base

```tsx
import { IconHome, IconStar, IconAlertCircle } from "@soli92/solids/icons";

<IconHome size="md" variant="default" />
<IconStar size="lg" variant="primary" />
<IconAlertCircle size="sm" variant="muted" />
```

[^src: docs/foundations/icons.mdx §Utilizzo base]

### Prop `variant`

| Variant | Token CSS | Uso consigliato |
|---------|-----------|-----------------|
| `default` | `--sd-color-icon-default` | Icone standard su sfondo canvas/surface |
| `muted` | `--sd-color-icon-muted` | Icone secondarie, placeholder, decorative |
| `primary` | `--sd-color-icon-primary` | Icone in evidenza, azioni principali |
| `on-primary` | `--sd-color-icon-on-primary` | Icone su sfondo primary (es. button filled) |

Tutti i temi definiscono `color.icon.*` — il colore si adatta automaticamente al `data-theme` attivo.[^src: docs/foundations/icons.mdx §Prop variant]

### Prop `size`

| Size | Dimensione |
|------|-----------|
| `sm` | 16px |
| `md` | 20px |
| `lg` | 24px |
| `xl` | 32px |
| `number` | Valore custom (es. `size={48}`) |

[^src: docs/foundations/icons.mdx §Prop size]

## Icone base (glyphs.tsx)

Icone universali. Il file conta circa 246 righe post-bonifica — le 9 versioni semplificate delle icone tematiche che erano presenti come segnaposto sono state rimosse nella bonifica 2026-07-17.[^src: docs/raw/bonifica-repo-2026-07-17.txt §Sezione 1 — Design System: icone duplicate]

Gallery (estratto): `Home` · `Search` · `User` · `Settings` · `Menu` · `X` · `Check` · `ChevronDown` · `ChevronRight` · `Plus` · `Minus` · `Trash` · `Pencil` · `Copy` · `ExternalLink` · `AlertCircle` · `Info` · `Star` · `Heart` · `Sun` · `Moon` · `Mail` · `Calendar` · `Folder`[^src: docs/foundations/icons.mdx §Gallery icone base]

## Icone tematiche (glyphs-themed.tsx)

9 icone tematiche in 3 set, con SVG path elaborati corrispondenti al design definitivo:[^src: docs/raw/analisi-repository-2026-07-17.txt §2.2 Sistema icone (post-bonifica)]

| Set | Icone esportate |
|-----|-----------------|
| Fantasy | `IconFantasyScroll`, `IconFantasySword`, `IconFantasyGem` |
| Cyberpunk | `IconCyberpunkChip`, `IconCyberpunkEye`, `IconCyberpunkSignal` |
| Party | `IconPartyBolt`, `IconPartyDiamond`, `IconPartyStar` |

Prima della bonifica queste icone erano inaccessibili: `glyphs-themed.tsx` esisteva con il design corretto ma non era esportato da `src/icons/index.ts`. La versione corretta e' quella in `glyphs-themed.tsx` — le versioni in `glyphs.tsx` erano segnaposto (vedi [[da-001-icon-source-of-truth]]).

## Bridge pattern (@/lib/icons)

Il file `src/lib/icons/index.ts` e' un bridge introdotto nella bonifica 2026-07-17.[^src: docs/raw/bonifica-repo-2026-07-17.txt §Sezione 2 — Design System: import path rotto]

**Problema risolto**: `logo-loader.tsx` importava da `@/icons`, path che funziona in locale (dove `@/` → `src/`) ma non per i consumer del registry shadcn — questi ricevono i file in `lib/`, dove `@/icons` non esiste. Il path corretto per il consumer e' `@/lib/icons`.

**Soluzione**: aggiungere `src/lib/icons/index.ts` che fa solo re-export. Questo evita il refactoring di tutto il codebase.

```typescript
// src/lib/icons/index.ts — bridge
export * from "@/icons"
```

In locale dev, `@/lib/icons` risolve via bridge → `@/icons` → `src/icons/`. Per i consumer del registry, `@/lib/icons` risolve a `lib/icons/` (dove il file viene installato direttamente). Vedi [[da-002-icons-bridge-pattern]].

## Icone tema-specifiche

9 icone tematiche disegnate per rispecchiare l'identita' visiva dei temi fantasy, cyberpunk e 90s-party. Usano `--sd-color-icon-*` come tutte le altre, ma danno il meglio abbinate al tema corrispondente.

```tsx
// Fantasy
import { IconFantasyScroll, IconFantasySword, IconFantasyGem } from "@soli92/solids/icons";
<div data-theme="fantasy">
  <IconFantasyScroll size="lg" variant="primary" />
</div>

// Cyberpunk
import { IconCyberpunkChip, IconCyberpunkEye, IconCyberpunkSignal } from "@soli92/solids/icons";
<div data-theme="cyberpunk">
  <IconCyberpunkEye size="xl" variant="primary" />
</div>

// 90s Party
import { IconPartyBolt, IconPartyDiamond, IconPartyStar } from "@soli92/solids/icons";
<div data-theme="90s-party">
  <IconPartyStar size="lg" variant="muted" />
</div>
```

[^src: docs/foundations/icons.mdx §Icone tema-specifiche]

## Icone brand (soli-icons)

Le brand icon di soli92 vivono in `docs/brand-assets/soli-icons/` (16 file). Includono varianti theme-aware che si adattano al `data-theme` attivo tramite token CSS. Sono esportate come componenti React da `@soli92/solids/icons`. Per la struttura completa degli asset, vedi [[brand-assets]].

### Componenti esportati (v1.13.1+)

**Varianti mono:**
`IconSoli1x1WithTextMono` · `IconSoli4x3WithTextMono` · `IconSoli1x1SymbolOnlyMono` · `IconSoli4x3SymbolOnlyMono`

**Varianti gold:**
`IconSoli1x1WithTextGold` · `IconSoli4x3WithTextGold` · `IconSoli1x1SymbolOnlyGold` · `IconSoli4x3SymbolOnlyGold`

**Varianti theme-aware** (si adattano automaticamente al tema attivo):
`IconSoli1x1WithTextTheme` · `IconSoli4x3WithTextTheme` · `IconSoli1x1SymbolOnlyTheme` · `IconSoli4x3SymbolOnlyTheme`

```tsx
import {
  IconSoli1x1WithTextTheme,
  IconSoli4x3WithTextTheme,
} from "@soli92/solids/icons";

<section data-theme="steampunk">
  <IconSoli4x3WithTextTheme size={160} />
</section>
```

**Import asset statici diretti:**

```tsx
import soliIconMonoSvg from "@soli92/solids/brand-assets/soli-icons/soli-icon-1x1-with-text-mono.svg";
import soliIconGoldPng from "@soli92/solids/brand-assets/soli-icons/soli-icon-4x3-with-text-gold.png";
```

[^src: docs/foundations/icons.mdx §Soli Brand Icon Pack (image set #2)]

## Aggiungere icone personalizzate

```tsx
import * as React from "react";
import { SolidsIcon, type SolidsIconProps } from "@soli92/solids/icons";

type IconProps = Omit<SolidsIconProps, "children">;

const IconMyCustom = React.forwardRef<SVGSVGElement, IconProps>(
  function IconMyCustom(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        {/* viewBox="0 0 24 24", stroke="currentColor" gia' impostati */}
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </SolidsIcon>
    );
  }
);
```

[^src: docs/foundations/icons.mdx §Aggiungere icone personalizzate]

## Export npm

```typescript
// Entry point: @soli92/solids/icons
import { SolidsIcon } from "@soli92/solids/icons"        // wrapper
import { IconHome, IconSearch } from "@soli92/solids/icons" // icone base
import { IconFantasyScroll } from "@soli92/solids/icons"   // icone tematiche
```

## Registry shadcn

Il registry shadcn gestisce le icone tematiche con un item dedicato:[^src: docs/raw/analisi-repository-2026-07-17.txt §2.3 Registry shadcn (Model 1)]

| File | Contenuto |
|------|-----------|
| `registry/r/solids-icons.json` | Item registry icone tematiche (nuovo dalla bonifica) |
| `registry/r/solids-ui.json` | Kit principale — dichiara `registryDependencies: ["solids-icons"]` |
| `scripts/sync-registry.mjs` | Script che rigenera i JSON — modifiche manuali vengono sovrascritte ad ogni run |

> Attenzione: `sync-registry.mjs` sovrascrive `registry.json` ad ogni run. Le modifiche al registry vanno sempre fatte nello script, non nei JSON generati.

## Pagine correlate

- [[da-001-icon-source-of-truth]] — decisione: `glyphs-themed.tsx` come source of truth
- [[da-002-icons-bridge-pattern]] — decisione: bridge `src/lib/icons/index.ts`
- [[bonifica-2026-07-17]] — incident: icone duplicate + import path rotto
- [[brand-assets]] — brand icon pack (soli-icons, workspace-icons)
- [[design-system-overview]] — panoramica export e distribuzione
