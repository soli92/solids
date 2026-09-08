"""
MCP Tool: get_task — legge frontmatter strutturato di un TSK (EP-058).
Cerca management/kanban/**/{tsk_id}.md e restituisce campi chiave.
R.MCP1 (ADR-MCP-002): read-only. Nessuna operazione di write.
"""
from pathlib import Path
from typing import Any


def register_get_task_tool(mcp, factory_root: Path) -> None:
    """Registra il tool get_task nel server FastMCP."""

    kanban_dir = factory_root / "management" / "kanban"

    @mcp.tool()
    def get_task(tsk_id: str) -> dict[str, Any]:
        """Legge il frontmatter strutturato del TSK specificato.

        Args:
            tsk_id: ID del task (es. 'TSK-481' oppure '481').

        Returns:
            Dict con campi: id, title, status, layer, consumer, priority,
            estimate, sprint, depends_on, blocked_by, us, ep.
            Oppure {"error": "..."} se non trovato.

        R.MCP1: read-only.
        """
        # Normalizza: '481' → 'TSK-481'
        normalized = tsk_id.strip().upper()
        if not normalized.startswith("TSK-"):
            normalized = f"TSK-{normalized}"

        matches = sorted(kanban_dir.glob(f"**/{normalized}.md"))
        if not matches:
            return {
                "error": (
                    f"Task non trovato: {tsk_id}. "
                    f"Verifica l'ID (es. 'TSK-481') o usa kanban://list/tasks per elencarli."
                )
            }

        content = matches[0].read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)

        # Restituisce solo i campi utili (esclude campi lunghi come code_path)
        keys = [
            "id", "title", "status", "layer", "consumer", "priority",
            "estimate", "sprint", "depends_on", "blocked_by", "us", "ep",
        ]
        return {k: fm[k] for k in keys if k in fm}


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Estrae e parsa il frontmatter YAML da un file Markdown.

    Parsing minimale line-by-line senza dipendenze esterne.
    R.MCP1: solo lettura.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    fm_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm_lines.append(line)

    result: dict[str, Any] = {}
    for line in fm_lines:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Gestisce liste YAML inline: [a, b, c]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            result[key] = [
                v.strip().strip('"').strip("'")
                for v in inner.split(",")
                if v.strip()
            ]
        else:
            result[key] = value
    return result
