# Skill: Graphify Extraction Protocol

> Adapter Cursor della skill `graphify-extraction-protocol` definita in PATTERN.md.

Metadata skill (originale):
```yaml
name: graphify-extraction-protocol
description: Protocollo provider-agnostic per estrazione knowledge graph da code_path via Graphify (PATTERN §16 + §20.10, v2.14 Fase 2). 5 fasi (Bootstrap → Discovery → Build Graph → Side-channel write → Log). Output raw/ + .graphify-state/ side-channel.
```

Riferimenti: PATTERN §16 «Sync adapters» (4° adapter), §20.10 (Context Compression
Layer), §20.11 (R.G1–R.G6 invarianti), §7 r.17 (sync read-only verso la sorgente),
[[graphify]] (entity product), [[factory-compression-layer]] (design doc).

Questa skill è invocata dall'agent [graphify-sync](mdc:.cursor/rules/graphify-sync.mdc) (§2 + §16). Definisce le 5 fasi
che ogni estrazione di knowledge graph deve seguire. Provider-bound a [[graphify]]:
supporta sia la variante Python (`graphifyy` PyPI) sia la variante TypeScript
(`graphify-ts` npm). La selezione del binario avviene in Fase 1.

## Prerequisiti

- `factory.config.yaml.compression.context.provider` ∈ `{graphify-cloud, graphify-ollama}`
  (non `none`).
- Graphify installato: `graphify --version` (binario singola-y, da pacchetto PyPI
  `graphifyy` doppia-y) o `graphify-ts --version` (variante TS) ritorna OK.
  Vedi [[graphify-installation]] per la procedura completa.
- Target `<name>` corrispondente a una entry di `factory.config.yaml.code_paths[]`.
- `<code_path>` esiste sul filesystem e è leggibile.
- Variabile d'ambiente API key per il pass semantico (se `graphify-cloud`):
  - `ANTHROPIC_API_KEY` o `OPENAI_API_KEY` configurata (mai committata).
  - Se `graphify-ollama`: server Ollama locale attivo + modello (es. `llama3.1:8b`).

Se uno dei prerequisiti manca → ABORT in Fase 1 con messaggio chiaro.

## Fase 1 — Bootstrap

Input: `target: <name>` passato dall'utente o dal dispatcher.

1. Read `factory.config.yaml`:
   - `compression.context` block completo.
   - `code_paths[name == target]` → estrai `path`, `layers`, `gitignore_patterns`.
   - Se `target` non esiste → ABORT con messaggio: «Target `<name>` non trovato in
     `code_paths`. Disponibili: <list>».
2. Verifica Graphify installato (CLI binario è `graphify`, non `graphifyy`):
   ```bash
   graphify --version   # atteso: graphify 0.8.22 o superiore (da pip install graphifyy)
   # alternativa TS: graphify-ts --version
   ```
   Se non installato → ABORT con messaggio `install_command` da config + rimando
   a [[graphify-installation]].
3. Verifica `<code_path>` esiste e è leggibile.
4. Calcola slug:
   - Default: `<target-name-kebab>`. Es. `backend` → `backend`.
   - Override possibile via `--slug=<custom>` ma scoraggiato (consistenza).
5. Read `raw/.extraction-manifest.json`:
   - Se esiste entry `<YYYY-MM-DD>-graph-<slug>` per oggi → mode `incremental`,
     conferma con utente.
   - Altrimenti → procedi.
6. Read `.graphify-state/code_paths/<slug>/last_full_rebuild.txt` (se esiste):
   - Calcola delta giorni vs oggi.
   - Se `delta > drift_alert_days` (default 7) → suggerisci mode `full` in chat.

## Fase 2 — Discovery + Cost Estimation

1. Scansiona `<code_path>` (read-only):
   ```bash
   find <code_path> -type f \( -name "*.py" -o -name "*.ts" -o ... \) | wc -l
   du -sh <code_path>
   ```
2. Determina mode:
   - **`incremental`** (default se `.graphify-state/code_paths/<slug>/graph.json`
     esiste): solo AST update sui file modificati. Zero token, ~0.4s/1k file.
   - **`full`** (primo build o `--force` o stale > drift_alert_days):
     AST + semantic LLM pass. Costo stimato 2–20 $.
3. Cost estimation per mode `full`:
   ```bash
   # Heuristic: 1 token per ~4 char di codice + ~10% per docs/markdown
   estimated_tokens = (files * avg_lines * 4) / 4
   estimated_cost_usd = estimated_tokens * 0.000003  # Claude rate ~3$/M
   ```
4. Se `mode == full` AND `estimated_cost > compression.context.full_rebuild_cost_warn`
   (default 5$):
   - **STOP** (§7 r.15 analogo). Mostra in chat:
     ```
     PIANO ESTRAZIONE
     ================
     Target: <name>
     Path: <code_path>
     Mode: full
     Files: <N>
     Cost stimato: $<C>
     Tempo stimato: <T>
     Proseguire? (y/N)
     ```
   - Attendi conferma esplicita. ABORT su `N`.

## Fase 3 — Build Graph

Esegui Graphify (read-only verso `<code_path>`, scrive in `graphify-out/` default
o nel side-channel custom path):

```bash
# Mode incremental (default, zero-token AST update):
graphify update <code_path>
# Output: <code_path>/graphify-out/{graph.json, GRAPH_REPORT.md, graph.html}

# Mode full (con pass semantico LLM-driven, costoso):
graphify update <code_path> --force
# overwrite del graph esistente, include re-extraction concept semantica

# Mode cluster-only (rerun clustering su graph esistente):
graphify cluster-only <code_path>

# Post-rebuild check anti ghost-duplicates:
graphify diagnose multigraph --graph <code_path>/graphify-out/graph.json --json
```

Dopo l'esecuzione del CLI, **sposta** gli output da `<code_path>/graphify-out/` al
side-channel `.graphify-state/code_paths/<slug>/` per conformità all'invariante R.G5:

```bash
mkdir -p .graphify-state/code_paths/<slug>/
mv <code_path>/graphify-out/graph.json .graphify-state/code_paths/<slug>/
mv <code_path>/graphify-out/GRAPH_REPORT.md .graphify-state/code_paths/<slug>/
# graph.html opzionale, può restare in graphify-out/ per visualizzazione locale
rmdir <code_path>/graphify-out/ 2>/dev/null || true
```

**Nota terminologica**: il design doc usa `get_impact_radius(file)` come nome
concettuale del check di blast radius. Nel CLI reale il sub-comando equivalente è
`graphify affected "<symbol-or-file>"` (reverse traversal, vedi
[[graphify-installation]]).

Applica `gitignore_patterns` da config (`*.env`, `secrets/**`, ecc.) per
esclusione secret hygiene — implementato tramite copia preventiva del `<code_path>`
in dir temp escludendo i pattern, oppure usando `.graphifyignore` se supportato
dalla versione corrente di Graphify.

Cattura stdout per estrarre metriche:
- Files analyzed: N
- Nodes EXTRACTED / INFERRED / AMBIGUOUS
- Edges totali
- Communities detected
- Ghost duplicates
- Duration
- Tokens consumed (per full)

## Fase 4 — Side-channel write + Summary

1. Verifica file prodotti:
   - `.graphify-state/code_paths/<slug>/graph.json` esiste e non è vuoto
   - `.graphify-state/code_paths/<slug>/GRAPH_REPORT.md` esiste
2. Aggiorna `last_full_rebuild.txt` (solo se mode == full):
   ```bash
   date -u +%Y-%m-%dT%H:%M:%SZ > .graphify-state/code_paths/<slug>/last_full_rebuild.txt
   ```
3. **Genera summary `raw/<YYYY-MM-DD>-graph-<slug>.md`** umano-leggibile:
   - Read `GRAPH_REPORT.md` prodotto da Graphify
   - Estrai: top-10 god nodes, top-10 surprising connections, confidence breakdown,
     communities, ghost duplicates count
   - Componi documento con sezioni canoniche (vedi agent `graphify-sync` §Sezioni canoniche)
   - Lunghezza target: 5-15 KB (sampling, non dump del GRAPH_REPORT.md completo)
4. **Append a `raw/.extraction-manifest.json`**:
   ```json
   {
     "<YYYY-MM-DD>-graph-<slug>": {
       "source": "graph",
       "extracted_at": "<ISO-8601>",
       "primary_artifact": "raw/<YYYY-MM-DD>-graph-<slug>.md",
       "secondary_artifacts": [
         ".graphify-state/code_paths/<slug>/graph.json",
         ".graphify-state/code_paths/<slug>/GRAPH_REPORT.md"
       ],
       "extractor_version": "graphify-sync@2.14.0",
       "extraction_metadata": {
         "code_path_target": "<name>",
         "code_path_source": "<path>",
         "git_commit": "<hash>",
         "git_branch": "<branch>",
         "mode": "<full|incremental>",
         "files_analyzed": <N>,
         "nodes_extracted": <M>,
         "nodes_inferred": <K>,
         "nodes_ambiguous": <J>,
         "edges_total": <E>,
         "tokens_consumed": <T>,
         "cost_usd": <C>,
         "duration_seconds": <D>,
         "ghost_duplicates": <G>,
         "status": "success | partial | error"
       }
     }
   }
   ```

## Fase 5 — Log

Append a `wiki/log.md` (formato standard, `wiki-log-entry` skill):

```
[YYYY-MM-DD HH:MM] graphify-sync — target=<name>, mode=<full|incremental>,
  files=<N>, nodes=<EXTR>/<INFR>/<AMB>, edges=<E>, tokens=<T>,
  cost=$<C>, ghost_dup=<G> — files touched: 4
```

Mostra in chat al termine:
```
GRAPHIFY EXTRACTION COMPLETE
============================
Target: <name>
Mode: <full|incremental>
Summary: raw/<YYYY-MM-DD>-graph-<slug>.md
Side-channel: .graphify-state/code_paths/<slug>/{graph.json,GRAPH_REPORT.md}

Stats:
  Files analyzed: N
  Nodes EXTRACTED: M (deterministic)
  Nodes INFERRED: K (semantic)
  Nodes AMBIGUOUS: J
  Edges: E
  Tokens consumed: T (cost: $C)
  Duration: D seconds
  Ghost duplicates: G

Next step:
  - Invoca wiki-keeper per ingest summary L1→L2 (opzionale)
  - I dev-agent ora consumano GRAPH_REPORT.md come context (se compression.context.enabled)
  - /graphify-sync show per stats consolidate
```

## Drift handling (R.G4)

Se durante Fase 3 emergono ghost duplicates > soglia (default `ghost_duplicates_warn:
10`):
- Mode `full` → completa rebuild ma flag warning in chat
- Mode `incremental` → forza retry in mode `full`, conferma con utente

Cron weekly suggerito (`compression.context.full_rebuild_cron`):
```cron
0 0 * * 0 /usr/local/bin/graphifyy update <code_path> --force --state=.graphify-state/...
```

In CI con `ci_strategy.mode: cache-with-fallback`:
- Cache hit (95%+ runs) → graph caricato in <5s, zero token
- Cache miss o stale > `stale_threshold_hours` (default 168 = 7 giorni) → fallback
  automatico a scansione filesystem (comportamento v2.14 Fase 1 pre-Graphify),
  nessun rebuild in CI
- Full rebuild solo on-demand via `/graphify-sync <target> --force` (local dev o
  scheduled job dedicato)

## Vincoli (PATTERN §7 r.17 + §16 isolamento + §20.11 R.G1–R.G6)

- **L1 read-only** (§7 r.1): solo `graphify-sync` scrive in `raw/*-graph-*.md` e
  `.graphify-state/**`.
- **Sync read-only verso la sorgente** (§7 r.17): mai modificare il `<code_path>`
  scansionato. Mai aggiungere `factory.config.yaml`, `.cursor/`, o file
  infrastrutturali alla sorgente.
- **Side-channel write-restricted** (R.G5): nessun altro agent scrive in
  `.graphify-state/**`.
- **Filesystem single source of truth** (R.G1): graph è view derivata, mai authoritative.
- **Confidence preserved**: il graph mantiene i tag EXTRACTED/INFERRED/AMBIGUOUS;
  il filtering per ruolo agent (R.G2) avviene downstream nel [parallel-scheduling](mdc:.cursor/skills/parallel-scheduling/SKILL.md).
- **Mai chiamate network non documentate**: solo l'API LLM per il pass semantico
  (se `graphify-cloud`). Mai chiamate a Neo4j auto (richiede flag esplicito).
- **Secret hygiene**: applica `gitignore_patterns` da config. Secret rilevati
  durante extraction non vengono mai inclusi nel summary `.md` (redacted).
- **Cost gate**: full rebuild > `full_rebuild_cost_warn` (default 5$) richiede
  conferma esplicita.

## Output finale (sequenza esatta di file)

1. `raw/<YYYY-MM-DD>-graph-<slug>.md` — summary umano-leggibile (5-15 KB)
2. `.graphify-state/code_paths/<slug>/graph.json` — graph completo (Graphify nativo)
3. `.graphify-state/code_paths/<slug>/GRAPH_REPORT.md` — report Graphify nativo
4. `.graphify-state/code_paths/<slug>/last_full_rebuild.txt` — timestamp (solo se full)
5. `raw/.extraction-manifest.json` — entry appended
6. `wiki/log.md` — entry appended

Vedi [graphify-sync](mdc:.cursor/rules/graphify-sync.mdc) agent per il contratto completo, PATTERN §20.10 per il context
axis del Compression Layer, [[factory-compression-layer]] per il design rationale.
