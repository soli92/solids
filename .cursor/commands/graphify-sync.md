---
description: Estrae knowledge graph da un code_path target via Graphify CLI (PATTERN §16 + §20.10, v2.14 Fase 2). Output raw/ + side-channel .graphify-state/. Sub-comandi sync/show/status/refresh.
argument-hint: <target> | show | status [<target>] | refresh [<target>]
allowed-tools: Read, Write, Edit, Bash, Glob
---

Sintassi:

```
/graphify-sync <target>            → estrazione standard 5 fasi (auto-detect full vs incremental)
/graphify-sync <target> --force    → forza full rebuild (override incremental)
/graphify-sync <target> --slug=X   → override naming slug
/graphify-sync show                → mostra ultime estrazioni dal manifest
/graphify-sync status [<target>]   → stato drift (last_full_rebuild + giorni delta)
/graphify-sync refresh [<target>]  → incremental update (no chat per cost gate)
/graphify-sync help                → help inline + esempi
```

## Comportamento per sub-comando

### `/graphify-sync <target>`

1. Read `factory.config.yaml`:
   - `compression.context.enabled: true` richiesto (altrimenti ABORT con messaggio:
     «Attiva `compression.context.enabled: true` via `/compression set
     context.enabled true` per usare Graphify»).
   - `code_paths[name == target]` deve esistere.
2. Invoca l'agente [graphify-sync](mdc:.cursor/rules/graphify-sync.mdc) passando:
   - `target: <name>`
   - `force: <true|false>` (default `false`; `--force` lo forza `true`)
   - `slug: <slug-or-auto>` (default `<target-name>`)
3. L'agent esegue la skill [graphify-extraction-protocol](mdc:.cursor/skills/graphify-extraction-protocol/SKILL.md) 5 fasi:
   - Fase 1 — Bootstrap (valida target, verifica `graphifyy`/`graphify-ts`, dedup manifest).
   - Fase 2 — Discovery + Cost estimation (auto-detect full vs incremental, STOP se cost > warn).
   - Fase 3 — Build Graph (Graphify CLI, output in `.graphify-state/code_paths/<slug>/`).
   - Fase 4 — Side-channel write + Summary (`raw/<data>-graph-<slug>.md` + manifest entry).
   - Fase 5 — Log (`wiki/log.md`).
4. Mostra in chat al termine: stats + path artefatti + next step.

### `/graphify-sync show`

Read-only su `raw/.extraction-manifest.json`, filtra entries con `source: graph`, mostra:

```
GRAPHIFY EXTRACTIONS (lista da raw/.extraction-manifest.json)
==============================================================
<key>                       <data>        <target>  <mode>       <files>  <nodes E/I/A>  <status>
<YYYY-MM-DD>-graph-<slug-1> 2026-...      backend   full          127     M/K/J         success
<YYYY-MM-DD>-graph-<slug-2> 2026-...      frontend  incremental   89      M/K/J         success
```

Nessuna scrittura.

### `/graphify-sync status [<target>]`

Mostra lo stato drift dei graph esistenti:

```
GRAPHIFY STATUS (drift monitoring)
==================================
Target     Last full rebuild       Days delta   Status
backend    2026-05-22 03:00:00     6            OK (< drift_alert_days)
frontend   2026-05-18 03:00:00     10           WARN (> drift_alert_days=7)
db         2026-05-28 12:00:00     0            FRESH
```

Se `<target>` specificato, mostra solo quello con dettagli aggiuntivi (path,
size graph.json, ghost_duplicates count).

### `/graphify-sync refresh [<target>]`

Forza un incremental update SENZA cost gate (zero token per AST-only update):

```bash
# Internal: invoca graphifyy update <code_path> --state=.graphify-state/code_paths/<slug>/
```

Se `<target>` omesso → refresh di TUTTI i target con `code_paths` non vuoto.
Utile come post-commit hook o session-start hook.

Mai full rebuild qui: per quello serve `/graphify-sync <target>` standard (con cost
gate Fase 2) o `--force`.

### `/graphify-sync help`

Stampa help testuale inline + 3 esempi:

```
ESEMPI

# Estrazione standard del code_path 'backend' (auto-detect full vs incremental)
/graphify-sync backend

# Force full rebuild per refresh semantico (cron weekly suggerito)
/graphify-sync backend --force

# Status drift di tutti i target
/graphify-sync status

# Incremental update (post-commit hook tipico, zero token)
/graphify-sync refresh backend

DOPO L'ESTRAZIONE
- Il side-channel .graphify-state/code_paths/<slug>/ è pronto.
- I dev-agent in modalità context-compression (compression.context.enabled: true)
  consumano automaticamente GRAPH_REPORT.md come context replacement dei file
  sorgente raw (riduzione 50-90% del context window per agent).
- Per ingest del summary L1→L2 nella wiki (opzionale):
    Agent(subagent_type=wiki-keeper, prompt="Ingest raw/<data>-graph-<slug>.md")
```

## Prerequisiti

- `factory.config.yaml.compression.context.enabled: true`
- `factory.config.yaml.compression.context.provider` ∈ `{graphify-cloud, graphify-ollama}`
- Graphify installato: `graphify --version` (binario singola-y, da `pip install graphifyy`) o `graphify-ts --version` (TS). Procedura completa: [[graphify-installation]]
- API key per pass semantico (se `graphify-cloud`): `ANTHROPIC_API_KEY` o
  `OPENAI_API_KEY` (mai committata)
- `code_paths[name == target]` definito in `factory.config.yaml`
- Read access su tutto `<code_path>`
- Agente [graphify-sync](mdc:.cursor/rules/graphify-sync.mdc) presente
- `raw/` esistente nella factory che invoca

## Output (artefatti L1 + side-channel)

- `raw/<YYYY-MM-DD>-graph-<slug>.md` — summary primario, umano-leggibile (5-15 KB)
- `.graphify-state/code_paths/<slug>/graph.json` — graph completo (machine-readable)
- `.graphify-state/code_paths/<slug>/GRAPH_REPORT.md` — report Graphify nativo
- `.graphify-state/code_paths/<slug>/last_full_rebuild.txt` — timestamp (solo se mode=full)
- `raw/.extraction-manifest.json` — entry appended con `source: graph`

## Idempotenza

Re-estrazione sullo stesso target con la stessa data → dedup automatico:
- Mode `incremental`: append delta sul graph esistente, no nuovo file `raw/`
- Mode `full`: chiede conferma; se confermato, sovrascrive
  `.graphify-state/code_paths/<slug>/` + nuovo file `raw/` (incrementa data se serve)

Re-estrazione con data diversa (giorno successivo) → nuovo file `<YYYY-MM-DD>-graph-<slug>.md`;
il vecchio resta per audit.

## CI strategy

`factory.config.yaml.compression.context.ci_strategy.mode`:
- `cache-with-fallback` (default): cache hit zero token (carica
  `.graphify-state/code_paths/<slug>/` da cache provider); stale > 7gg → fallback
  scansione filesystem (no rebuild in CI)
- `disabled`: graph mai utilizzato in CI; sempre fallback scansione filesystem
- `always-rebuild`: full rebuild ad ogni CI run (costoso, sconsigliato)

## Vincoli (PATTERN §7 r.17 + §16 + §20.11)

- **L1 read-only** per la factory (§7 r.1): solo `graphify-sync` scrive in
  `raw/*-graph-*.md` e `.graphify-state/**`.
- **Sync read-only verso la sorgente** (§7 r.17): mai modificare il `<code_path>`
  scansionato.
- **Side-channel write-restricted** (R.G5): solo `graphify-sync` scrive in
  `.graphify-state/**`.
- **`.graphify-state/` in `.gitignore`** (R.G6): mai versionato in git, sempre
  rebuildable.
- **Cost gate per full rebuild** (Fase 2 STOP): se costo stimato > `full_rebuild_cost_warn`
  (default 5$) → conferma esplicita.
- **API key solo da env var**: mai committata; nome var dichiarato implicitamente
  da provider (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / Ollama locale).

## Bootstrap integration (v2.14 Fase 2)

Il `factory-bootstrap` meta-prompt (v2.14+) chiede `compression_context_mode` come
opzione opt-in:
- `none` (default, deferred)
- `graphify-cloud` (richiede installazione + API key)
- `graphify-ollama` (richiede installazione + Ollama 16+ GB VRAM)

Se attivato, il bootstrap scaffolda `.graphify-state/` in `.gitignore` automaticamente.
La prima invocazione di `/graphify-sync <target>` esegue il primo full rebuild
(cost-gated).

Vedi la skill [graphify-extraction-protocol](mdc:.cursor/skills/graphify-extraction-protocol/SKILL.md) per la procedura completa, l'agente
[graphify-sync](mdc:.cursor/rules/graphify-sync.mdc) per il contratto, PATTERN §16 «Sync adapters» + §20.10 «Context
Compression Layer» per la cornice generale, [[factory-compression-layer]] per il
design rationale.
