"""
Resource handler kanban:// — Factory-as-MCP-Server (EP-058, v2.39)
Espone frontmatter YAML di TSK/EP/US come risorse MCP read-only.

URI scheme:
  kanban://tasks/{tsk-id}      → management/kanban/**/TSK-{tsk-id}.md (frontmatter)
  kanban://epics/{ep-id}       → management/kanban/**/EP-{ep-id}.md (frontmatter)
  kanban://stories/{us-id}     → management/kanban/**/US-{us-id}.md (frontmatter)
  kanban://list/tasks          → lista ID di tutti i TSK
  kanban://list/epics          → lista ID di tutti gli EP
  kanban://list/stories        → lista ID di tutte le US

R.MCP1 (ADR-MCP-002): nessuna operazione di write su factory state.
"""
from pathlib import Path
import re


def _extract_frontmatter(content: str) -> str:
    """Estrae il blocco frontmatter YAML (tra --- e ---) da un file Markdown.
    Restituisce il testo tra i delimitatori. Se assente, restituisce stringa vuota."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return ""
    return "\n".join(lines[1:end])


def _find_file(kanban_dir: Path, pattern: str) -> Path | None:
    """Trova il primo file che matcha il glob pattern in kanban_dir (ordinato)."""
    matches = sorted(kanban_dir.glob(pattern))
    return matches[0] if matches else None


def register_kanban_resources(mcp, factory_root: Path) -> None:
    """Registra resources kanban:// per TSK, EP e US."""

    kanban_dir = factory_root / "management" / "kanban"

    @mcp.resource("kanban://tasks/{tsk_id}")
    def read_task(tsk_id: str) -> str:
        """Restituisce il frontmatter YAML del TSK richiesto."""
        # Normalizza: TSK-481 o 481 → TSK-481
        if not tsk_id.upper().startswith("TSK-"):
            tsk_id = f"TSK-{tsk_id}"
        tsk_id = tsk_id.upper()
        f = _find_file(kanban_dir, f"**/{tsk_id}.md")
        if not f:
            raise FileNotFoundError(f"Task non trovato: {tsk_id}")
        return _extract_frontmatter(f.read_text(encoding="utf-8")) or f.read_text(encoding="utf-8")

    @mcp.resource("kanban://epics/{ep_id}")
    def read_epic(ep_id: str) -> str:
        """Restituisce il frontmatter YAML dell'EP richiesto."""
        if not ep_id.upper().startswith("EP-"):
            ep_id = f"EP-{ep_id}"
        ep_id = ep_id.upper()
        f = _find_file(kanban_dir, f"**/{ep_id}.md")
        if not f:
            raise FileNotFoundError(f"Epica non trovata: {ep_id}")
        return _extract_frontmatter(f.read_text(encoding="utf-8")) or f.read_text(encoding="utf-8")

    @mcp.resource("kanban://stories/{us_id}")
    def read_story(us_id: str) -> str:
        """Restituisce il frontmatter YAML della US richiesta."""
        if not us_id.upper().startswith("US-"):
            us_id = f"US-{us_id}"
        us_id = us_id.upper()
        f = _find_file(kanban_dir, f"**/{us_id}.md")
        if not f:
            raise FileNotFoundError(f"User story non trovata: {us_id}")
        return _extract_frontmatter(f.read_text(encoding="utf-8")) or f.read_text(encoding="utf-8")

    @mcp.resource("kanban://list/tasks")
    def list_tasks() -> str:
        """Elenca tutti gli ID dei TSK nel kanban (uno per riga)."""
        ids = sorted(f.stem for f in kanban_dir.glob("**/TSK-*.md"))
        return "\n".join(ids) if ids else "(nessun task trovato)"

    @mcp.resource("kanban://list/epics")
    def list_epics() -> str:
        """Elenca tutti gli ID degli EP nel kanban (uno per riga)."""
        ids = sorted(set(f.stem for f in kanban_dir.glob("**/EP-*.md")))
        return "\n".join(ids) if ids else "(nessuna epica trovata)"

    @mcp.resource("kanban://list/stories")
    def list_stories() -> str:
        """Elenca tutti gli ID delle US nel kanban (uno per riga)."""
        ids = sorted(f.stem for f in kanban_dir.glob("**/US-*.md"))
        return "\n".join(ids) if ids else "(nessuna user story trovata)"
