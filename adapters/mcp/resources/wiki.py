"""
Resource handler wiki:// — Factory-as-MCP-Server (EP-058, v2.39)
Espone wiki/concepts/ e wiki/syntheses/ come risorse MCP read-only.

URI scheme:
  wiki://concepts/{slug}   → wiki/concepts/{slug}.md
  wiki://syntheses/{slug}  → wiki/syntheses/{slug}.md
  wiki://list/concepts     → elenco slug in wiki/concepts/
  wiki://list/syntheses    → elenco slug in wiki/syntheses/

R.MCP1 (ADR-MCP-002): nessuna operazione di write su factory state.

Flock-advisory (ADR-039 §A): se wiki_search.enabled: true e
.wiki-search/index.lance esiste, acquisisce flock-advisory in lettura
prima di ogni accesso a wiki/. Degrada gracefully (no flock) altrimenti.
"""
import fcntl
import os
from contextlib import contextmanager
from pathlib import Path

import yaml


def _load_wiki_search_enabled(factory_root: Path) -> bool:
    """Legge factory.config.yaml e restituisce wiki_search.enabled (default False)."""
    config_path = factory_root / "factory.config.yaml"
    if not config_path.exists():
        return False
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return bool(cfg.get("wiki_search", {}).get("enabled", False))
    except Exception:
        return False


@contextmanager
def _advisory_read_lock(factory_root: Path):
    """
    Acquisisce un flock-advisory condiviso (LOCK_SH) sul file
    .wiki-search/index.lance/lock se wiki_search è abilitato e
    il file esiste. Degrada gracefully (no-op) altrimenti.
    """
    lock_path = factory_root / ".wiki-search" / "index.lance" / "lock"
    if _load_wiki_search_enabled(factory_root) and lock_path.exists():
        try:
            with open(lock_path, "rb") as lf:
                fcntl.flock(lf, fcntl.LOCK_SH)
                try:
                    yield
                finally:
                    fcntl.flock(lf, fcntl.LOCK_UN)
        except OSError:
            # Flock non disponibile sul filesystem (es. NFS) — degrada senza bloccare
            yield
    else:
        yield


def register_wiki_resources(mcp, factory_root: Path) -> None:
    """Registra list_resources e read_resource per wiki/concepts/ e wiki/syntheses/."""

    concepts_dir = factory_root / "wiki" / "concepts"
    syntheses_dir = factory_root / "wiki" / "syntheses"

    @mcp.resource("wiki://concepts/{slug}")
    def read_wiki_concept(slug: str) -> str:
        """Legge una pagina wiki/concepts/{slug}.md e ne restituisce il contenuto markdown."""
        with _advisory_read_lock(factory_root):
            target = concepts_dir / f"{slug}.md"
            if not target.exists():
                available = [f.stem for f in sorted(concepts_dir.glob("*.md"))] if concepts_dir.exists() else []
                raise FileNotFoundError(
                    f"Concetto wiki non trovato: '{slug}'. "
                    f"Disponibili: {available}"
                )
            return target.read_text(encoding="utf-8")

    @mcp.resource("wiki://syntheses/{slug}")
    def read_wiki_synthesis(slug: str) -> str:
        """Legge una pagina wiki/syntheses/{slug}.md e ne restituisce il contenuto markdown."""
        with _advisory_read_lock(factory_root):
            target = syntheses_dir / f"{slug}.md"
            if not target.exists():
                available = [f.stem for f in sorted(syntheses_dir.glob("*.md"))] if syntheses_dir.exists() else []
                raise FileNotFoundError(
                    f"Sintesi wiki non trovata: '{slug}'. "
                    f"Disponibili: {available}"
                )
            return target.read_text(encoding="utf-8")

    @mcp.resource("wiki://list/concepts")
    def list_wiki_concepts() -> str:
        """Elenca tutti gli slug disponibili in wiki/concepts/ (uno per riga)."""
        with _advisory_read_lock(factory_root):
            if not concepts_dir.exists():
                return "(nessun concetto wiki trovato)"
            slugs = sorted(f.stem for f in concepts_dir.glob("*.md"))
            return "\n".join(slugs) if slugs else "(nessun concetto wiki trovato)"

    @mcp.resource("wiki://list/syntheses")
    def list_wiki_syntheses() -> str:
        """Elenca tutti gli slug disponibili in wiki/syntheses/ (uno per riga)."""
        with _advisory_read_lock(factory_root):
            if not syntheses_dir.exists():
                return "(nessuna sintesi wiki trovata)"
            slugs = sorted(f.stem for f in syntheses_dir.glob("*.md"))
            return "\n".join(slugs) if slugs else "(nessuna sintesi wiki trovata)"
