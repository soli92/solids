# Factory MCP Server (EP-058)

Adapter `protocol-bridge` che espone la factory come server MCP (Model Context Protocol) in sola lettura via stdio.

> **R.MCP1 (ADR-MCP-002)**: questo server è read-only by design. Nessun tool modifica lo stato della factory.
> Le operazioni di write rimangono gatate tramite Claude Code con gate umano.

Per la guida completa (prerequisiti, test, troubleshooting): [`wiki/runbooks/mcp-server.md`](../../wiki/runbooks/mcp-server.md)

---

## Configurazione client rapida

### Claude Desktop

Percorso config:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "factory": {
      "command": "python",
      "args": ["/path/to/factory/adapters/mcp/server.py"],
      "env": {
        "FACTORY_ROOT": "/path/to/factory"
      }
    }
  }
}
```

### Cursor

Nel settings JSON di Cursor o in `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "factory": {
      "command": "python",
      "args": ["/path/to/factory/adapters/mcp/server.py"],
      "env": {
        "FACTORY_ROOT": "/path/to/factory"
      }
    }
  }
}
```

> Sostituisci `/path/to/factory` con il path assoluto della factory. Riavvia il client dopo la modifica.

---

## Resources esposti (read-only)

| URI | Descrizione |
|-----|-------------|
| `wiki://concepts/{slug}` | Pagina concetto wiki (es. `wiki://concepts/model-context-protocol`) |
| `wiki://syntheses/{slug}` | Sintesi e decisioni wiki |
| `wiki://list/concepts` | Lista di tutti gli slug in wiki/concepts/ |
| `wiki://list/syntheses` | Lista di tutti gli slug in wiki/syntheses/ |
| `kanban://tasks/{tsk-id}` | Frontmatter del TSK (es. `kanban://tasks/TSK-481`) |
| `kanban://epics/{ep-id}` | Frontmatter dell'EP (es. `kanban://epics/EP-058`) |
| `kanban://stories/{us-id}` | Frontmatter della US (es. `kanban://stories/US-213`) |
| `kanban://list/tasks` | Lista di tutti gli ID TSK nel kanban |
| `kanban://list/epics` | Lista di tutti gli ID EP nel kanban |
| `kanban://list/stories` | Lista di tutti gli ID US nel kanban |
| `factory://config` | `factory.config.yaml` filtrato (segreti redatti) |
| `factory://config/pattern-version` | Versione corrente del pattern (stringa) |

---

## Tools disponibili (read-only)

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `query_wiki` | `(question: str, top_k: int = 5)` | Ricerca semantica (EP-042) o FTS sulla wiki |
| `get_task` | `(tsk_id: str)` | Frontmatter strutturato di un TSK (es. `"TSK-481"`) |
| `lint_status` | `()` | Conteggio ERROR/WARNING/INFO dall'ultimo report /lint |

---

## Struttura adapter

```
adapters/mcp/
├── manifest.yaml          # Registrazione adapter (adapter_type: protocol-bridge)
├── requirements.txt       # mcp==1.3.0 (pin ADR-MCP-004)
├── server.py              # Entrypoint stdio (FastMCP, FACTORY_ROOT obbligatoria)
├── resources/
│   ├── __init__.py
│   ├── wiki.py            # handler wiki:// (concepts + syntheses)
│   ├── kanban.py          # handler kanban:// (tasks + epics + stories)
│   └── config_resource.py # handler factory://config (con secret redaction)
└── tools/
    ├── __init__.py
    ├── wiki_search_tool.py # tool query_wiki (FTS + LanceDB opt-in)
    ├── get_task_tool.py    # tool get_task
    └── lint_status_tool.py # tool lint_status
```

---

## Avvio manuale (debug)

```bash
FACTORY_ROOT=$(pwd) python adapters/mcp/server.py
```

Il server si avvia in modalità stdio e attende input dal client MCP. Usa MCP Inspector per il test interattivo:

```bash
FACTORY_ROOT=$(pwd) mcp dev adapters/mcp/server.py
```

---

## Note ADR

| ADR | Decisione |
|-----|-----------|
| [ADR-MCP-001](../../design_%26_architecture/decisions/ADR-MCP-001-factory-as-mcp-server.md) | GO factory-as-MCP-server read-only |
| [ADR-MCP-002](../../design_%26_architecture/decisions/ADR-MCP-002-rmcp1-no-write.md) | R.MCP1 no-write non-bypassabile |
| [ADR-MCP-003](../../design_%26_architecture/decisions/ADR-MCP-003-adapters-mcp-location.md) | adapters/mcp/ + adapter_type: protocol-bridge |
| [ADR-MCP-004](../../design_%26_architecture/decisions/ADR-MCP-004-spec-versioning.md) | Pin mcp==1.3.0 + upgrade gate umano |
