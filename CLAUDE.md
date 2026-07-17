# CLAUDE.md — SoliDS Design System

Questo repo segue il pattern definito in [`PATTERN.md`](PATTERN.md) (v2.33 = Content Share Consumer Layer EP-048 opt-in; backward compat totale v2.32).

**Progetto**: `@soli92/solids` — Design System React (componenti, token, icone, Storybook, registry shadcn).

## Adapter

| Adapter | Versione | Cartella |
|---|---|---|
| `.cursor/` | v2.32 (primario) | `.cursor/rules/`, `.cursor/commands/`, `.cursor/skills/` |
| `.claude/` | v2.33 (secondario) | `.claude/agents/`, `.claude/commands/`, `.claude/skills/` |

L'adapter primario è `.cursor/`. L'adapter `.claude/` è aggiunto a v2.33 con il Content Share Consumer Layer (EP-048) e porta in parità tutti gli agenti/comandi/skill con il pattern corrente.

## Pattern version: v2.33

- **v2.33**: Content Share Consumer Layer EP-048 opt-in — skill `content-share-protocol` + comando `/share` + invarianti R.CS1..R.CS4 + config `content_share:`; dispatch fire-and-forget verso soli-frames; gate umano R.CS3; backward compat totale v2.32
- **v2.32**: Capability Formativa EP-045 + Voice Hardening EP-046 (agente tutor MVP + Student Model SM-2 + retrieval practice + curriculum YAML; 7 contratti FSM voice hardening C1..C7)
- **v2.31**: Voice Handsfree Improvements EP-044 (debounce VAD, wake-word Levenshtein, FilePipeAdapter watchdog, PID lock)
- Vedi `PATTERN.md` per la storia completa

## Topologia

```
knowledge-only
```

Routing: `docs → agent`, `fe → agent`. No dev-agent attivi (topologia knowledge-only). Il parallel scheduler è abilitato (`scheduler.enabled: true`, `max_parallel: 20`).

## Quick start (adapter Claude Code)

- Dashboard di stato: `/run`
- Domanda al wiki: `/query <domanda>`
- Ricerca semantica wiki (opt-in): `/wiki-search <query>` (richiede `wiki_search.enabled: true`)
- Health check: `/lint`
- Heal errori meccanici: `/heal [<report-path>]`
- Promote pagina: `/promote <path> <new-status>`
- Topologia: `/topology [show|set <topology>]`
- Design review: `/ux-ui-review`
- Analisi accessibilità: `/a11y <target>`
- Nuovo documento raw → wiki: `/sync-docs`
- Estrazione Figma: `/figma-sync <url|file_key>`
- Stima costi/tempi: `/estimate <scope>`
- **Pubblica artefatto HTML su soli-frames**: `/share <html-path> [--slug=<slug>] [--dry-run]`
  - Richiede `content_share.enabled: true` in `factory.config.yaml` + secret configurati

## Agenti principali

| Agente | Ruolo | Trigger |
|---|---|---|
| `orchestrator` | Dashboard, /run, /promote, wave dispatch | `/run`, `/promote` |
| `wiki-keeper` | Ingest L1→L2, gestione wiki/ | Nuovo raw/ |
| `wiki-keeper-worker` | Sub-agent ingest parallelo | Via wiki-keeper |
| `wiki-query` | Ricerca e sintesi knowledge base | `/query` |
| `wiki-lint` | Health check wiki | `/lint` |
| `product-manager` | Gestione epic/user story | Documenti strategici |
| `lead-architect` | Decisioni tecniche, ADR | Q&A architettura |
| `tpm` | Pianificazione sprint, stima | `/estimate`, sprint review |
| `ui-designer` | Generazione spec design | Design tasks |
| `ux-ui-reviewer` | Review UX/UI | `/ux-ui-review` |
| `figma-sync` | Estrazione da Figma | `/figma-sync` |
| `sync-docs` | Ingest PDF/doc | `/sync-docs` |
| `repo-sync` | Estrazione da repo | `/repo-sync` |
| `graphify-sync` | Knowledge graph da code_path | `/graphify-sync` |
| `prototype-generator` | Generazione prototipi HTML | `/prototype` |
| `a11y-specialist` | Scan WCAG 2.2 AA | `/a11y` |
| `analytics-reporter` | Report costi/ROI (misurazione) | `/analytics` |
| `estimation-analyst` | Stima costi/tempi (previsionale) | `/estimate` |
| `tutor` | Tutoring adattivo (opt-in EP-045) | Richieste formative |
| `tavola-rotonda-moderatore` | Deliberazione multi-agente (opt-in) | `/tavola-rotonda` |

## Configurazione factory (`factory.config.yaml`)

- **Pattern version**: `2.33`
- **Topologia**: `knowledge-only`
- **Scheduler**: `enabled: true`, `max_parallel: 20`
- **Analytics dogfooding**: `enabled: true` (EP-013)
- **Content Share** (v2.33): `content_share.enabled: false` (opt-in — configura per attivare `/share`)
- **Modelli**: `tier_fast: claude-haiku-4-5-20251001`, `tier_default: claude-sonnet-4-6`, `tier_deep: claude-opus-4-8`
- Tutte le capability opt-in (prototype, tavola-rotonda, wiki-search, temporal, tutor) sono `enabled: false` di default (R.P3)

## Note progetto SoliDS

- **Non modificare** `src/`, `registry/` — sono la libreria del design system
- La wiki in `wiki/` documenta componenti, token design, ADR, decisioni di architettura
- Storybook a `src/stories/`; registry shadcn in `registry/`
- Design tokens in `src/tokens/`; icone in `registry/solids/icons/`
- Build: `npm run build`; Storybook: `npm run storybook`

## Cross-link

- [`PATTERN.md`](PATTERN.md) — pattern completo v2.33 (§32 = Content Share Consumer Layer)
- [`factory.config.yaml`](factory.config.yaml) — configurazione factory
- [`.cursor/rules/orchestrator.mdc`](.cursor/rules/orchestrator.mdc) — contesto orchestrator
- `wiki/` — knowledge base del progetto
- `wiki/runbooks/content-share-setup.md` — setup prerequisiti `/share`
- `wiki/entities/soli-frames.md` — piattaforma hosting artefatti
