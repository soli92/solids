"""
MCP Tool: lint_status — health check read-only della factory (EP-058).
Legge il report lint più recente disponibile in wiki/lint/ o management/.
Non triggera un nuovo lint run (R.MCP1: read-only).
Restituisce {error_count, warning_count, info_count, report_path, timestamp}.
"""
from pathlib import Path
import re
from typing import Any


def register_lint_status_tool(mcp, factory_root: Path) -> None:
    """Registra il tool lint_status nel server FastMCP."""

    @mcp.tool()
    def lint_status() -> dict[str, Any]:
        """Legge il report lint più recente della factory.

        Restituisce il conteggio di ERROR, WARNING e INFO dall'ultimo report /lint.
        Non esegue un nuovo lint run — solo lettura del report esistente (R.MCP1).

        Returns:
            Dict con error_count, warning_count, info_count, report_path, timestamp.
            Se nessun report disponibile: {error_count: -1, message: "..."}.
        """
        report_path = _find_latest_lint_report(factory_root)
        if not report_path:
            return {
                "error_count": -1,
                "warning_count": -1,
                "info_count": -1,
                "message": "Nessun report lint disponibile. Esegui /lint per generarlo.",
            }
        return _parse_lint_report(report_path)


def _find_latest_lint_report(factory_root: Path) -> "Path | None":
    """Trova il report lint più recente per mtime. R.MCP1: solo lettura."""
    candidates: list[Path] = []
    # Cerca in wiki/lint/ (posizione standard da wiki-lint agent)
    wiki_lint_dir = factory_root / "wiki" / "lint"
    if wiki_lint_dir.exists():
        candidates.extend(p for p in wiki_lint_dir.glob("*lint*.md") if p.is_file())
        # Fallback: qualsiasi .md in wiki/lint/ (escluso .gitkeep)
        if not candidates:
            candidates.extend(p for p in wiki_lint_dir.glob("*.md") if p.is_file())
    # Cerca anche in management/kanban/ per report alternativi
    kanban_dir = factory_root / "management" / "kanban"
    if kanban_dir.exists():
        candidates.extend(
            p for p in kanban_dir.glob("lint-report*.md") if p.is_file()
        )

    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _parse_lint_report(report_path: Path) -> dict[str, Any]:
    """Parsa un report lint markdown e conta ERROR/WARNING/INFO. R.MCP1: solo lettura."""
    try:
        content = report_path.read_text(encoding="utf-8")
    except OSError:
        return {
            "error_count": -1,
            "warning_count": -1,
            "info_count": -1,
            "message": f"Impossibile leggere il report: {report_path}",
        }

    error_count = len(re.findall(r"\bERROR\b", content, re.IGNORECASE))
    warning_count = len(re.findall(r"\bWARNING\b", content, re.IGNORECASE))
    info_count = len(re.findall(r"\bINFO\b", content, re.IGNORECASE))

    # Estrae timestamp dal nome file (es. 2026-08-28-lint-report.md)
    timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2})", report_path.name)
    timestamp = timestamp_match.group(1) if timestamp_match else "unknown"

    return {
        "error_count": error_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "report_path": str(report_path),
        "timestamp": timestamp,
    }
