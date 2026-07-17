---
id: index
type: index
title: SoliDS — Design System Wiki
status: approved
created: 2026-06-15
updated: 2026-07-17
sources: [README.md, AGENTS.md, src/tokens/, AI_LOG.md, docs/foundations/, docs/principles.mdx, docs/roadmap.mdx, docs/registry-model-1.md, docs/shadcn-integration.md]
---

# SoliDS Wiki

Design system personale @soli92/solids — token semantici (light/dark), shadcn/ui compat, Storybook su GitHub Pages.

## Concepts

| Pagina | Stato | Descrizione |
|--------|-------|-------------|
| [Design System Overview](concepts/design-system-overview.md) | stable | Scopo, architettura, consumer |
| [Token Architecture](concepts/token-architecture.md) | stable | Base/semantici/temi, naming, CSS output |
| [Component Inventory](concepts/component-inventory.md) | stable | 56 componenti categorizati |
| [Design Principles](concepts/design-principles.md) | draft | 6 principi fondanti (Token-first, SSOT, A11y, ecc.) |
| [Icon System](concepts/icon-system.md) | draft | SolidsIcon wrapper, glyphs, tematiche, bridge @/lib/icons |
| [Brand Assets](concepts/brand-assets.md) | draft | soli-icons, soli-category-icons, workspace-icons normalizzati |
| [Struttura docs/ e pipeline factory](concepts/docs-structure.md) | draft | Anatomy docs/, foundations MDX, docs/raw/ pipeline |
| [Development History](concepts/development-history.md) | draft | 5 fasi sviluppo AI-assisted, decisioni architetturali, commit notevoli |
| [Registry Model 1](concepts/registry-model-1.md) | draft | Flusso consumer, namespace @solids, blocchi shadcn, workflow manutentori |
| [Shadcn Integration](concepts/shadcn-integration.md) | draft | Setup rapido, temi, token CSS, mapping shadcn vars |
| [Roadmap](concepts/roadmap.md) | draft | Stato attuale completato, prossimi step, visione |

### Concepts — Foundations

| Pagina | Stato | Descrizione |
|--------|-------|-------------|
| [Typography](concepts/foundations/typography.md) | draft | Font stack per tema, token --sd-font-*, scale dimensioni e pesi |
| [Spacing](concepts/foundations/spacing.md) | draft | Scala numerica --sd-space-*, alias semantici, regole fondamentali |
| [Colors](concepts/foundations/colors.md) | draft | Catalogo token colore semantico (text, bg, border, intent, icon) |
| [Border Radius](concepts/foundations/radius.md) | draft | Token --sd-radius-*, valori per tema, utility CSS |
| [Tokens (pipeline)](concepts/foundations/tokens.md) | draft | Struttura JSON pubblicato, pipeline CSS, token motion (easing/duration) |
| [Themes](concepts/foundations/themes.md) | draft | 12 temi, token chiave per tema, attivazione data-theme |
| [Accessibility and Motion](concepts/foundations/accessibility-and-motion.md) | draft | WCAG 2.2, MD3, Apple HIG, token touch-target, utility motion |

## Entities

| Pagina | Stato | Descrizione |
|--------|-------|-------------|
| [soli-frames](entities/soli-frames.md) | stable | Piattaforma hosting artefatti HTML (EP-048 §32) |

## Runbooks

| Pagina | Stato | Descrizione |
|--------|-------|-------------|
| [Content Share Setup](runbooks/content-share-setup.md) | current | Setup capability `/share` + PAT + secret (EP-048) |

## Decisions (ADR)

| Pagina | Stato | Descrizione |
|--------|-------|-------------|
| [DA-001 — Icon source of truth](decisions/da-001-icon-source-of-truth.md) | accepted | Conservare `glyphs-themed.tsx` vs segnaposto in `glyphs.tsx` |
| [DA-002 — Icons bridge pattern](decisions/da-002-icons-bridge-pattern.md) | accepted | Bridge `src/lib/icons/index.ts` per compatibilita' registry shadcn |
| [DA-003 — .gitignore root-anchored](decisions/da-003-gitignore-root-anchored.md) | accepted | Pattern `/solids/` con slash iniziale per non ignorare `registry/solids/` |
| [DA-004 — .claude/worktrees/ gitignored](decisions/da-004-claude-worktrees-gitignored.md) | accepted | Checkout isolati Claude Code esclusi dal tracking git |

## Incidents

| Pagina | Stato | Descrizione |
|--------|-------|-------------|
| [Bonifica 2026-07-17](incidents/bonifica-2026-07-17.md) | closed | Icone duplicate, import path rotto, git corrotto, adapter Claude Code assente |

## Artefatti design

| Artefatto | Stato | Descrizione |
|-----------|-------|-------------|
| [Token Naming Convention](design/token-naming-convention.md) | stable | Standard R.N1..R.N4 |
| [A11y Token Audit](design/a11y-token-audit.md) | stable | WCAG AA coppie colore |
| [EP-019 Critic Report](design/ep019-critic-report-solids.md) | done | Critic run C v2.21.0 |
| [Theme Spec: Brutalist](design/theme-spec-brutalist.md) | draft | Spec tema brutalist |
