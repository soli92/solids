# Comando: /graphify-sync

> Equivalente Cursor del comando Claude Code `/graphify-sync` (`.claude/commands/graphify-sync.md`).
> Procedura: vedi [graphify-extraction-protocol](mdc:.cursor/rules/skills/graphify-extraction-protocol.mdc).

**Sintassi**:
```
/graphify-sync <target>           → estrazione standard 5 fasi
/graphify-sync <target> --force   → forza full rebuild
/graphify-sync show               → ultime estrazioni dal manifest
/graphify-sync status [<target>]  → stato drift (last_full_rebuild)
/graphify-sync refresh [<target>] → incremental update senza cost gate
```

> **Gate**: `factory.config.yaml.compression.context.enabled: true`. Se `false` → ABORT.

## Comportamento

### `/graphify-sync <target>`

Esegue [graphify-extraction-protocol](mdc:.cursor/rules/skills/graphify-extraction-protocol.mdc) 5 fasi:
- Fase 1 — Bootstrap (valida target, verifica `graphifyy`, dedup manifest)
- Fase 2 — Discovery + Cost estimation (auto-detect full vs incremental; STOP se cost > warn)
- Fase 3 — Build Graph (`graphify update <code_path>` CLI)
- Fase 4 — Side-channel write + Summary (`raw/<data>-graph-<slug>.md`)
- Fase 5 — Log (`wiki/log.md`)

Output: `raw/<YYYY-MM-DD>-graph-<slug>.md` + `.graphify-state/code_paths/<slug>/` (graph.json + GRAPH_REPORT.md).

### `/graphify-sync status`

Mostra stato drift per tutti i target: `Last full rebuild`, `Days delta`, status `OK/WARN/FRESH`.

### `/graphify-sync refresh`

Incremental update `graphify update <path>` — zero token, nessun cost gate. Utile come post-commit hook.

## Vincoli

- **Read-only verso la sorgente** (§7 r.17).
- **`.graphify-state/` in `.gitignore`** (R.G6).
- **Cost gate per full rebuild** (STOP se costo > `full_rebuild_cost_warn`).
- API key solo da env var.

## Prerequisiti

- `graphify --version` disponibile (`pip install graphifyy` — doppia y).
- `compression.context.provider ∈ {graphify-cloud, graphify-ollama}`.

## Limitazioni Cursor

- Usare terminal Cursor per invocare il CLI `graphify`.
- Le 5 fasi vanno eseguite sequenzialmente.
