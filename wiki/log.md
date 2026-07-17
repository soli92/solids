---
id: log
type: log
title: Wiki Log
status: draft
created: 2026-06-15
updated: 2026-07-17
---

# Wiki Log

`YYYY-MM-DD HH:MM | <agent> | <operazione> | <target> | <note>`

## Entries

2026-06-15 | docs-dev | bootstrap | solids | Factory minimale v2.21 scaffoldata per EP-019 design intelligence run v2.21.0.
2026-06-15 | docs-dev | TSK-001 done | wiki/concepts/design-system-overview.md | Overview scopo + architettura token + theming + consumer.
2026-06-15 | docs-dev | TSK-002 done | wiki/concepts/token-architecture.md | Struttura directory, naming base/semantici, come creare tema, CSS output.
2026-06-15 | docs-dev | TSK-003 done | wiki/concepts/component-inventory.md | Inventario 56 componenti categorizati per tipo.
2026-06-15 | docs-dev | TSK-004 done | design_&_architecture/token-naming-convention.md | Standard naming + critic pass 4 finding (R.N1..R.N4).
2026-06-15 | docs-dev | TSK-005 done | design_&_architecture/a11y-token-audit.md | WCAG AA audit coppie colore: 2 finding a rischio.
2026-06-15 | docs-dev | TSK-006 done | design_&_architecture/ep019-critic-report-solids.md | Critic report globale EP-019 sprint solids.
2026-06-15 | docs-dev | TSK-007 done | design_&_architecture/theme-spec-brutalist.md | Theme spec brutalist: zero radius, zero shadow, max contrast.
2026-07-17 | wiki-keeper | ingest | docs/raw/bonifica-repo-2026-07-17.txt | Bonifica repository 2026-07-17: 4 problemi critici risolti (icone duplicate, import path rotto, git corrotto, adapter Claude Code assente). Commit 87818cc. Pattern factory v2.33 post-bonifica.
2026-07-17 | wiki-keeper | create | wiki/incidents/bonifica-2026-07-17.md | Incident report bonifica: 4 incidenti, 18 artefatti prodotti, rischi residui. Status: closed.
2026-07-17 | wiki-keeper | create | wiki/decisions/da-001-icon-source-of-truth.md | DA-001: conservare glyphs-themed.tsx come source of truth icone tematiche.
2026-07-17 | wiki-keeper | create | wiki/decisions/da-002-icons-bridge-pattern.md | DA-002: bridge src/lib/icons/index.ts per compatibilita' registry shadcn.
2026-07-17 | wiki-keeper | create | wiki/decisions/da-003-gitignore-root-anchored.md | DA-003: pattern /solids/ root-anchored per non ignorare registry/solids/.
2026-07-17 | wiki-keeper | create | wiki/decisions/da-004-claude-worktrees-gitignored.md | DA-004: .claude/worktrees/ gitignored (checkout isolati Claude Code).
2026-07-17 | wiki-keeper | update | wiki/entities/soli-frames.md | Arricchita con frontmatter completo, descrizione piattaforma, flusso dispatch, invarianti R.CS1..R.CS4, stato factory solids.
2026-07-17 | wiki-keeper | update | wiki/index.md | Aggiunte sezioni Entities, Runbooks, Decisions, Incidents con tutti i riferimenti.
2026-07-17 | wiki-keeper | update | wiki/log.md | Aggiornato updated date + aggiunte entry ingest 2026-07-17.
2026-07-17 | wiki-keeper | ingest | docs/raw/analisi-repository-2026-07-17.txt | Analisi repository 2026-07-17: struttura docs/, 8 finding consistency check factory, mappa conoscenza emersa. Nuove pagine concept + gaps aperti.
2026-07-17 | wiki-keeper | create | wiki/concepts/design-principles.md | 6 principi SoliDS da principles.mdx (Token-first, Semantic over visual, Framework agnostic, SSOT, Progressive adoption, A11y by default). Status: draft.
2026-07-17 | wiki-keeper | create | wiki/concepts/icon-system.md | Sistema icone post-bonifica: SolidsIcon wrapper, glyphs/glyphs-themed, bridge @/lib/icons, icone tematiche, registry shadcn. Status: draft.
2026-07-17 | wiki-keeper | create | wiki/concepts/brand-assets.md | Brand assets docs/brand-assets/: soli-icons, soli-category-icons, workspace-icons, workspace-icons-normalized. Status: draft.
2026-07-17 | wiki-keeper | create | wiki/concepts/docs-structure.md | Anatomia docs/: foundations MDX (8 file), pipeline raw/inbox, roadmap stato corrente, doc root-level. Status: draft.
2026-07-17 | wiki-keeper | create | wiki/gaps.md | 5 gap aperti da analisi-repository-2026-07-17 (design_&_architecture/ misplaced, AI_LOG.md, AGENTS.md, MDX non ingested, registry/shadcn docs). 2 finding gia' risolti documentati.
2026-07-17 | wiki-keeper | update | wiki/index.md | Aggiunte 4 nuove pagine concepts (design-principles, icon-system, brand-assets, docs-structure).
2026-07-17 | wiki-keeper | ingest | AI_LOG.md | Storico 58 commit sviluppo AI-assisted: 5 fasi, decisioni architetturali, problemi risolti, pattern ricorrenti, integrazione soli-prof.
2026-07-17 | wiki-keeper | create | wiki/concepts/development-history.md | Storico sviluppo SoliDS: 5 fasi (token/shadcn bridge, registry/Storybook, kit UI/temi, Turbopack/steampunk, a11y/font/test), debiti tecnici, commit notevoli. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/registry-model-1.md | Architettura registry Model 1: flusso consumer, namespace @solids, blocchi shadcn CLI, workflow manutentori, alternative senza namespace.
2026-07-17 | wiki-keeper | create | wiki/concepts/registry-model-1.md | Registry Model 1: setup CSS/Tailwind/shadcn, blocchi @solids/solids-ui, build registry, sync-registry.mjs. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/shadcn-integration.md | Guida integrazione shadcn/ui: compatibility layer shadcn.css, setup Next.js, temi data-theme, token CSS variables, mapping shadcn vars, utility sd-*.
2026-07-17 | wiki-keeper | create | wiki/concepts/shadcn-integration.md | Integrazione shadcn/ui: setup rapido, 12 temi, solo-variables mode, mapping shadcn→SoliDS, classi utility. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/roadmap.mdx | Roadmap: stato attuale (token, test, CSS pipeline, Storybook, registry), prossimi step, visione DS.
2026-07-17 | wiki-keeper | create | wiki/concepts/roadmap.md | Roadmap SoliDS: completato (token, pipeline CSS, Storybook, registry shadcn), prossimi step a11y/framework/stories. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/typography.mdx | Tipografia: famiglie semantiche --sd-font-*, font per tutti i 12 temi, scale dimensioni/pesi, utility CSS.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/typography.md | Typography foundations: token --sd-font-*, font per tema (Inter/DM Sans/JetBrains default, Source Serif 4/Cinzel fantasy, ecc.), CDN Google Fonts. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/spacing.mdx | Spacing: scala numerica --sd-space-0..64, alias semantici, regole fondamentali.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/spacing.md | Spacing foundations: scala --sd-space-1 (4px) ... --sd-space-6 (24px), alias semantici, regole anti-arbitrary. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/colors.mdx | Colors: catalogo token semantico completo (text, bg, border, intent, icon, brand).
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/colors.md | Colors foundations: catalogo token semantico per gruppo (text, background, border, intent, icon, componenti). Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/radius.mdx | Radius: token --sd-radius-none..full, valori per tema, utility CSS, linee guida.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/radius.md | Border Radius foundations: token --sd-radius-*, valori --sd-radius-md per tema (4px cyberpunk/sasuke → 12px light/dark), utility. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/tokens.mdx | Tokens pipeline: struttura JSON (base/semantic/themes), ordine import CSS (variables→themes→shadcn→base→utilities), token motion MD3.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/tokens.md | Tokens pipeline: struttura dist/tokens/tokens.json, pipeline CSS 5-step, token easing/duration MD3. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/themes.mdx | Themes: 12 temi, token chiave per ciascuno (text/bg/primary/font/radius), attivazione data-theme, Tailwind dark:, CDN font.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/themes.md | Themes foundations: 12 temi con token chiave esatti, attivazione data-theme, comportamento prefers-color-scheme, CDN font. Status: draft.
2026-07-17 | wiki-keeper | ingest | docs/foundations/accessibility-and-motion.mdx | A11y e motion: WCAG 2.2/MD3/HIG, focus visibile, reduced-motion, touch target 44px, utility .sd-min-touch-target/.sd-link/.sd-transition-emphasized.
2026-07-17 | wiki-keeper | create | wiki/concepts/foundations/accessibility-and-motion.md | A11y e Motion foundations: token layout.touch-target-min, utility motion, tabella riferimenti repo. Status: draft.
2026-07-17 | wiki-keeper | integrate | wiki/concepts/icon-system.md | Integrati docs/foundations/icons.mdx: px esatti size (16/20/24/32), gallery 24 icone base, tutti i componenti brand pack (mono/gold/theme-aware), custom icon pattern, esempi themed icons.
2026-07-17 | wiki-keeper | integrate | wiki/concepts/design-principles.md | Integrati docs/principles.mdx: testo autoritativo diretto per tutti e 6 i principi, riferimento a WCAG/MD3/HIG per principio A11y.
2026-07-17 | wiki-keeper | update | wiki/index.md | Aggiunte 4 nuove pagine concepts (development-history, registry-model-1, shadcn-integration, roadmap) + sezione Concepts/Foundations con 7 pagine. Aggiornata lista sources frontmatter.
2026-07-17 | wiki-keeper | close-gap | wiki/gaps.md | Chiusi: GAP-002 (AI_LOG.md ingested → development-history.md), GAP-004 (MDX foundations ingested), GAP-005 (registry-model-1.md + shadcn-integration.md ingested).
