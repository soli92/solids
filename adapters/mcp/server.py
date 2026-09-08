#!/usr/bin/env python3
"""
Factory-as-MCP-Server (EP-058, v2.39)
Espone wiki/, kanban/ e factory.config.yaml come risorse MCP read-only via stdio.

Invariante R.MCP1 (ADR-MCP-002): nessun handler scrive su factory state.
Transport: stdio — avviato per-sessione dal client MCP (Cursor, Claude Desktop).
Config: env var FACTORY_ROOT obbligatoria (path assoluto della factory).

Avvio:
  FACTORY_ROOT=/path/to/factory python adapters/mcp/server.py

Configurazione client (claude_desktop_config.json o Cursor settings):
  {
    "mcp_servers": {
      "factory": {
        "command": "python",
        "args": ["/path/to/factory/adapters/mcp/server.py"],
        "env": {"FACTORY_ROOT": "/path/to/factory"}
      }
    }
  }
"""
import os
import sys
from pathlib import Path

# --- Validazione FACTORY_ROOT (fail fast, messaggio esplicito) ---
FACTORY_ROOT_STR = os.environ.get("FACTORY_ROOT")
if not FACTORY_ROOT_STR:
    print(
        "ERROR: variabile d'ambiente FACTORY_ROOT non impostata.\n"
        "Imposta FACTORY_ROOT al path assoluto della factory prima di avviare il server.\n"
        "Esempio: FACTORY_ROOT=/Users/me/my-factory python adapters/mcp/server.py",
        file=sys.stderr,
    )
    sys.exit(1)

FACTORY_ROOT = Path(FACTORY_ROOT_STR).resolve()
if not FACTORY_ROOT.is_dir():
    print(
        f"ERROR: FACTORY_ROOT='{FACTORY_ROOT_STR}' non è una directory valida.",
        file=sys.stderr,
    )
    sys.exit(1)

# --- Aggiunge adapters/mcp/ al PYTHONPATH per import relativi ---
# Necessario quando il server è avviato dal client MCP con CWD diverso.
_adapter_dir = Path(__file__).parent
if str(_adapter_dir) not in sys.path:
    sys.path.insert(0, str(_adapter_dir))

# --- MCP Server (FastMCP high-level API — mcp==1.3.0, spec 2025-03-26) ---
# R.MCP1: FastMCP usato solo per resource registration (read-only).
# Nessun @mcp.tool in questo file — i tool sono registrati dai moduli tools/ (TSK-494..496).
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("factory")

# --- Registrazione resource set (R.MCP1: tutti read-only) ---
# I moduli resources/ sono implementati in TSK-490 (wiki), TSK-491 (kanban), TSK-492 (config).
# Stub accettabile fino al completamento di quei TSK.
from resources.wiki import register_wiki_resources
from resources.kanban import register_kanban_resources
from resources.config_resource import register_config_resources

register_wiki_resources(mcp, FACTORY_ROOT)
register_kanban_resources(mcp, FACTORY_ROOT)
register_config_resources(mcp, FACTORY_ROOT)

# --- Registrazione tool set (R.MCP1: tutti read-only) ---
# TSK-494: query_wiki — ricerca semantica/FTS sulla wiki.
# TSK-495: get_task  — frontmatter strutturato di un TSK dato ID.
from tools.wiki_search_tool import register_wiki_search_tool
from tools.get_task_tool import register_get_task_tool
from tools.lint_status_tool import register_lint_status_tool

# Carica factory.config.yaml per passarlo a query_wiki (flag wiki_search.enabled)
try:
    import yaml  # type: ignore
    with open(FACTORY_ROOT / "factory.config.yaml", encoding="utf-8") as _f:
        _factory_config: dict = yaml.safe_load(_f) or {}
except Exception:
    _factory_config = {}

register_wiki_search_tool(mcp, FACTORY_ROOT, _factory_config)
register_get_task_tool(mcp, FACTORY_ROOT)
register_lint_status_tool(mcp, FACTORY_ROOT)

# --- Entry point stdio ---
if __name__ == "__main__":
    # mcp.run() usa stdio transport per default (ADR-MCP-001: no HTTP, no port).
    mcp.run()
