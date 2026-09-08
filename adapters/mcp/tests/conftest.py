"""
conftest.py — Fixture condivise per la suite di test MCP EP-058.

Fixture:
  factory_root   — Path alla factory reale su disco (session scope)
  wiki_dir       — factory_root / "wiki"
  kanban_dir     — factory_root / "management" / "kanban"
  mcp_instance   — FastMCP fresco per ogni test (function scope)
  tmp_factory    — directory temporanea con struttura minima factory (function scope)
"""
import pytest
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------
FACTORY_ROOT = Path(
    "/Users/simone.olivieri/Documents/Personal/Repos/soli-multi-agents-factory"
)


# ---------------------------------------------------------------------------
# Fixture base — factory reale su disco
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def factory_root() -> Path:
    """Restituisce il path della factory reale. Fallisce se non esiste."""
    assert FACTORY_ROOT.is_dir(), (
        f"FACTORY_ROOT non trovato: {FACTORY_ROOT}. "
        "Esegui i test dalla macchina di sviluppo con il repo clonato."
    )
    return FACTORY_ROOT


@pytest.fixture(scope="session")
def wiki_dir(factory_root: Path) -> Path:
    return factory_root / "wiki"


@pytest.fixture(scope="session")
def kanban_dir(factory_root: Path) -> Path:
    return factory_root / "management" / "kanban"


# ---------------------------------------------------------------------------
# Fixture FastMCP — fresca per ogni test
# ---------------------------------------------------------------------------

@pytest.fixture
def mcp_instance():
    """Restituisce un'istanza FastMCP isolata per ogni test."""
    from mcp.server.fastmcp import FastMCP
    return FastMCP("factory-test")


# ---------------------------------------------------------------------------
# Fixture tmp_factory — directory temporanea con struttura minima
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_factory(tmp_path: Path) -> Path:
    """
    Crea una factory temporanea minimale con:
      - factory.config.yaml (con pattern_version e auth_env)
      - wiki/concepts/test-concept.md
      - wiki/syntheses/test-synthesis.md
      - wiki/lint/2026-01-01-lint-report.md
      - management/kanban/TSK-001.md (con frontmatter completo)
    """
    root = tmp_path / "factory"
    root.mkdir()

    # factory.config.yaml con segreto da redarre
    (root / "factory.config.yaml").write_text(
        textwrap.dedent("""\
            pattern_version: "2.38"
            project_name: test-factory
            kanban_publish:
              auth_env: $MY_SECRET_TOKEN
            wiki_search:
              enabled: false
        """),
        encoding="utf-8",
    )

    # wiki/concepts/
    concepts = root / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "test-concept.md").write_text(
        "# Test Concept\n\nQuesto è un concetto di test per FTS e risorse MCP.\n",
        encoding="utf-8",
    )

    # wiki/syntheses/
    syntheses = root / "wiki" / "syntheses"
    syntheses.mkdir(parents=True)
    (syntheses / "test-synthesis.md").write_text(
        "# Test Synthesis\n\nSintesi di prova.\n",
        encoding="utf-8",
    )

    # wiki/lint/ — report con pattern ERROR/WARNING/INFO
    lint_dir = root / "wiki" / "lint"
    lint_dir.mkdir(parents=True)
    (lint_dir / "2026-01-01-lint-report.md").write_text(
        textwrap.dedent("""\
            # Lint Report 2026-01-01
            - ERROR: campo mancante
            - ERROR: link non trovato
            - WARNING: campo deprecato
            - INFO: suggerimento
        """),
        encoding="utf-8",
    )

    # management/kanban/ — TSK con frontmatter completo
    kanban = root / "management" / "kanban"
    kanban.mkdir(parents=True)
    (kanban / "TSK-001.md").write_text(
        textwrap.dedent("""\
            ---
            id: TSK-001
            title: "Task di test"
            status: todo
            layer: be
            consumer: agent
            priority: P1
            estimate: S
            sprint: 1
            depends_on: []
            blocked_by: []
            us: US-001
            ep: EP-001
            ---

            # TSK-001

            Corpo del task.
        """),
        encoding="utf-8",
    )

    return root
