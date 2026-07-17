---
id: gaps
type: gaps
title: Wiki Gaps
status: current
created: 2026-07-17
updated: 2026-07-17
---

# Wiki Gaps

Gap aperti nella knowledge base wiki — segnalati dall'analisi del repository (2026-07-17).

Formato entry: `GAP-NNN | YYYY-MM-DD | fonte | descrizione | priorita' | stato`

Per chiudere un gap: aggiungere `**Risolto:** <data> — <note>` alla entry corrispondente.

---

## GAP-001 — design_&_architecture/ fuori dalla wiki tree

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.5 FINDING MODERATO #4
**Priorita'**: P2 (Importante)

4 documenti referenziati da `wiki/index.md` si trovano fuori dalla wiki tree in `design_&_architecture/`:

- `a11y-token-audit.md`
- `ep019-critic-report-solids.md`
- `theme-spec-brutalist.md`
- `token-naming-convention.md`

Problema: il wiki-lint non li scansiona; il wiki-keeper non li aggiorna automaticamente; i path relativi `../design_&_architecture/` in `wiki/index.md` sono fragili (si rompono se wiki/ viene riorganizzata).

**Azione raccomandata**: spostare i 4 file in `wiki/design/` o `wiki/concepts/` e aggiornare i link in `wiki/index.md`.

**Stato**: APERTO

---

## GAP-002 — AI_LOG.md non ingested

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.6 FINDING MODERATO #5
**Priorita'**: P2 (Importante)

`AI_LOG.md` (root del repo) contiene storico prezioso attualmente non accessibile via wiki:

- 58 commit 2026-02-16 → 2026-04-08
- Decisioni architetturali per fase (token, registry, brand assets, ecc.)
- Integrazione soli-prof (webhook HMAC, re-ingest selettivo)
- Pattern e lezioni apprese

**Azione raccomandata**: copiare `AI_LOG.md` in `docs/raw/ai-log-<data>.txt` ed eseguire ingest con wiki-keeper.

**Stato**: CHIUSO

**Risolto:** 2026-07-17 — `AI_LOG.md` ingested direttamente. Creata `wiki/concepts/development-history.md` con 5 fasi di sviluppo, decisioni architetturali per fase, problemi tecnici risolti (con hash commit), pattern ricorrenti, debiti tecnici noti, integrazione soli-prof. Il file e' stato letto dalla root del repo senza copia in `docs/raw/`.

---

## GAP-003 — AGENTS.md root outdated (pre-factory)

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.4 FINDING MAGGIORE #3
**Priorita'**: P3 (Mantenibilita')

`AGENTS.md` root (aggiornato 2026-04-29) e' precedente alla factory scaffold (2026-07-17). Non contiene riferimenti a:

- Pattern factory v2.33
- Adapter `.claude/` e `.cursor/`
- Wiki in `wiki/` root (slash commands `/run`, `/query`, `/lint`, ecc.)
- Flusso wiki-keeper per ingest di `docs/raw/`

In topologia knowledge-only, `CLAUDE.md` e' il punto di ingresso principale — `AGENTS.md` root dovrebbe almeno rimandare a `CLAUDE.md`.

**Azione raccomandata**: aggiungere sezione "Factory / Agent Context" all'`AGENTS.md` root con rimando a `CLAUDE.md` e `wiki/`.

**Stato**: APERTO

---

## GAP-004 — docs MDX non ingested direttamente nella wiki

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.7 FINDING MODERATO #6
**Priorita'**: P4 (Nice to have)

`docs/principles.mdx` e `docs/roadmap.mdx` (e tutti i file in `docs/foundations/`) contengono conoscenza strutturata di produzione non ingested direttamente nella wiki factory. La wiki ha pagine derivate da analisi secondaria ma non dal MDX originale.

Conoscenza mancante (non ancora in wiki):
- Tipografia: font stack (Inter, DM Sans, JetBrains Mono), scale tipografica, token `--sd-font-*`
- Spacing: scala `--sd-spacing-*` con valori esatti
- Radius: scala `--sd-radius-*` con valori esatti
- Colori: dettaglio palette semantica light/dark con coppie di valori
- Motion: token `easing.standard`, `easing.emphasized`, `duration.*`

**Azione raccomandata**: ingestare `docs/principles.mdx`, `docs/roadmap.mdx` e selettivamente i file `docs/foundations/*.mdx` piu' rilevanti come raw sources.

**Stato**: CHIUSO

**Risolto:** 2026-07-17 — Ingested tutti i file MDX richiesti:
- `docs/principles.mdx` → integrato in `wiki/concepts/design-principles.md` (testo autoritativo diretto)
- `docs/roadmap.mdx` → `wiki/concepts/roadmap.md` (nuovo)
- `docs/foundations/typography.mdx` → `wiki/concepts/foundations/typography.md` (font stack per tutti i 12 temi)
- `docs/foundations/spacing.mdx` → `wiki/concepts/foundations/spacing.md` (scala numerica con valori px)
- `docs/foundations/colors.mdx` → `wiki/concepts/foundations/colors.md` (catalogo token semantico completo)
- `docs/foundations/radius.mdx` → `wiki/concepts/foundations/radius.md` (token e valori per tema)
- `docs/foundations/tokens.mdx` → `wiki/concepts/foundations/tokens.md` (pipeline CSS, token motion MD3)
- `docs/foundations/themes.mdx` → `wiki/concepts/foundations/themes.md` (token chiave per tutti i 12 temi)
- `docs/foundations/accessibility-and-motion.mdx` → `wiki/concepts/foundations/accessibility-and-motion.md`
- `docs/foundations/icons.mdx` → integrato in `wiki/concepts/icon-system.md`

---

## GAP-005 — docs/registry-model-1.md e docs/shadcn-integration.md non ingested

**Data**: 2026-07-17
**Fonte**: analisi-repository-2026-07-17 §3.9 FINDING MINORE #8
**Priorita'**: P4 (Nice to have)

Due documenti tecnici di valore non ingested nella wiki:

- `docs/registry-model-1.md` — architettura registry Model 1: struttura blocchi, `registryDependencies`, naming convention
- `docs/shadcn-integration.md` — guida completa integrazione shadcn/ui: theming, token bridge, `shadcn.css`

**Azione raccomandata**: ingestare come raw sources in una sessione successiva.

**Stato**: CHIUSO

**Risolto:** 2026-07-17 — Entrambi i documenti ingested direttamente:
- `docs/registry-model-1.md` → `wiki/concepts/registry-model-1.md` (flusso consumer, namespace @solids, blocchi CLI, workflow manutentori)
- `docs/shadcn-integration.md` → `wiki/concepts/shadcn-integration.md` (setup rapido, 12 temi, token CSS, mapping shadcn vars, utility sd-*)

---

## Findings gia' risolti (per riferimento storico)

### FINDING #1 — docs/wiki/ ghost schema con alwaysApply:true [RISOLTO]

**Data**: 2026-07-17
**Risolto**: 2026-07-17 — `docs/wiki/` eliminata integralmente (commit 87818cc o sessione contestuale). La Cursor rule `alwaysApply: true` che iniettava lo schema incompatibile e' rimossa.

### FINDING #2 — factory.config.yaml: description stale + content_share incompleto [RISOLTO]

**Data**: 2026-07-17
**Risolto**: 2026-07-17 — `factory.config.yaml` aggiornato: description → "SoliDS — Design system React (@soli92/solids)"; `source_repo_slug: "solids"`; `source_repo: "soli92/solids"`.
