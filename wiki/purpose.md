---
type: purpose
domain: "Meta-framework agent-agnostic per generare e governare factory multi-agente AI (pipeline wiki+kanban+codice, multi-adapter, compression layer opt-in)."
priority_entity_types: [pattern, capability, invariante, adapter, agente, skill, comando, ADR]
tone: technical-prescriptive
exclusions: [gossip-organizzativo, roadmap-commerciale, dati-personali-non-tecnici, credenziali]
---

# Purpose

Questa wiki documenta il **meta-framework** `soli-multi-agents-factory`: il pattern
(`PATTERN.md`), le sue capability opt-in, gli adapter (Claude Code, Cursor, Aider, …) e le
factory derivate. Non è la wiki di un prodotto applicativo — è la knowledge base del sistema
che *costruisce* prodotti.

## Cosa privilegiare nell'ingest

In ordine di priorità semantica:

1. **Pattern** — regole architetturali riutilizzabili (thin-orchestrator, CQRL, compression
   a due assi, cooperative locking, …). Sono l'unità di conoscenza centrale.
2. **Capability** — funzionalità derivabili e opt-in (functional oracle, wiki-search ibrida,
   code intelligence stack, tavola rotonda, …).
3. **Invarianti** — vincoli non-overridabili (§7 del PATTERN, R.C1, R.CI1, INV-TR-*, …).
   Vanno documentati come contratti, non come suggerimenti.
4. **Adapter / agente / skill / comando** — i componenti concreti del runtime.
5. **ADR** — decisioni architetturali con contesto e trade-off.

## Tono

**Technical-prescriptive**: normativo e imperativo. La documentazione dice *cosa deve valere*
(invarianti, gate, precondizioni), non racconta una storia. Preferire tabelle, contratti,
pseudo-DAG e riferimenti incrociati `[[wikilink]]` alla prosa discorsiva. Ogni claim non
banale cita la fonte (`[^src: ...]`, PATTERN §6).

## Esclusioni

Fuori scope semantico: dinamiche organizzative/di team, roadmap commerciale o di vendita,
dati personali non tecnici, e qualsiasi credenziale o segreto. Se emergono da una sorgente
raw, non entrano in `wiki/` (semmai in `wiki/gaps.md` come nota, se rilevanti al pattern).

## Note per gli agenti

- La distinzione **meta-framework vs factory derivata** è centrale: molti concetti hanno una
  faccia "nel meta" e una "nella factory generata". Esplicitare sempre quale.
- Le versioni del PATTERN (`v2.x`) sono entità di prima classe: i delta tra versioni sono
  conoscenza, non solo changelog.
- `factory.config.yaml` è la config **tecnica**; questo file è la dimensione **semantica**.
  Non duplicarli.

[^src: PATTERN.md §34 (Semantic Purpose Layer, EP-055) + §1-§7 (architettura e invarianti)]
