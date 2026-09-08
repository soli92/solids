"""
MCP Tool: query_wiki — ricerca semantica/FTS sulla wiki factory (EP-058).
Integra wiki-search-protocol (EP-042, LanceDB) se wiki_search.enabled: true.
Fallback FTS garantito (R.WS1): grep-like su wiki/**/*.md se disabilitato.
R.MCP1 (ADR-MCP-002): read-only. Nessuna operazione di write.
"""
from pathlib import Path
import re
from typing import Any


def register_wiki_search_tool(mcp, factory_root: Path, config: dict) -> None:
    """Registra il tool query_wiki nel server FastMCP."""

    wiki_dir = factory_root / "wiki"
    wiki_search_enabled = config.get("wiki_search", {}).get("enabled", False)

    @mcp.tool()
    def query_wiki(question: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Cerca nella wiki della factory per concetti, decisioni e runbook.

        Usa LanceDB (EP-042) se wiki_search.enabled: true in factory.config.yaml.
        Degrada su ricerca full-text (FTS) garantita se disabilitato (R.WS1).

        Args:
            question: Domanda o termine da cercare nella wiki.
            top_k: Numero massimo di risultati (default 5).

        Returns:
            Lista di dict {slug, path, snippet, score} ordinata per rilevanza.
        """
        if wiki_search_enabled:
            try:
                import sys
                tools_dir = str(factory_root / "tools")
                if tools_dir not in sys.path:
                    sys.path.insert(0, tools_dir)
                from wiki_search import search as lancedb_search  # type: ignore
                return lancedb_search(question, top_k=top_k, factory_root=str(factory_root))
            except (ImportError, Exception):
                pass  # Fallback a FTS

        # Fallback FTS garantito (R.WS1)
        return _fts_search(question, top_k, wiki_dir)


def _fts_search(question: str, top_k: int, wiki_dir: Path) -> list[dict]:
    """Ricerca full-text (grep-like) su wiki/**/*.md. Read-only (R.MCP1)."""
    terms = [t.lower() for t in question.split() if len(t) > 2]
    if not terms or not wiki_dir.exists():
        return []

    results = []
    for md_file in wiki_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        content_lower = content.lower()
        score = sum(content_lower.count(term) for term in terms)
        if score > 0:
            # Estrae snippet: prime 200 char della sezione che contiene il primo match
            first_term = terms[0]
            idx = content_lower.find(first_term)
            start = max(0, idx - 60)
            snippet = content[start : start + 200].replace("\n", " ").strip()
            results.append({
                "slug": md_file.stem,
                "path": str(md_file.relative_to(wiki_dir.parent)),
                "snippet": snippet,
                "score": score,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
