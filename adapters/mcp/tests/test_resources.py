"""
test_resources.py — P1: test delle MCP resources via FastMCP.

Testa le risorse registrate con mcp.resource() usando l'API FastMCP:
  - read_resource(uri) → Iterable[ReadResourceContents]
  - list_resources() → list[Resource]
  - list_resource_templates() → list[ResourceTemplate]

Resources coperte:
  wiki://concepts/{slug}        (resources/wiki.py)
  wiki://syntheses/{slug}       (resources/wiki.py)
  wiki://list/concepts          (resources/wiki.py)
  wiki://list/syntheses         (resources/wiki.py)
  kanban://tasks/{tsk_id}       (resources/kanban.py)
  kanban://epics/{ep_id}        (resources/kanban.py)
  kanban://stories/{us_id}      (resources/kanban.py)
  kanban://list/tasks           (resources/kanban.py)
  kanban://list/epics           (resources/kanban.py)
  kanban://list/stories         (resources/kanban.py)
  factory://config              (resources/config_resource.py)
  factory://config/pattern-version  (resources/config_resource.py)

Tutti i test usano asyncio.run() poiché mcp.read_resource è una coroutine
(pytest-asyncio non è nel dev stack — scelta deliberata per minimalità).
"""
import asyncio
import sys
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ResourceError

_MCP_DIR = Path(__file__).parent.parent
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))

# FastMCP wraps handler exceptions differently based on resource type:
# - Template resources (with {params}): raises ValueError
# - Concrete resources (no params): raises ResourceError
# Both are caught together:
_RESOURCE_NOT_FOUND_ERRORS = (FileNotFoundError, ValueError, ResourceError)

from resources.wiki import register_wiki_resources
from resources.kanban import register_kanban_resources
from resources.config_resource import register_config_resources


# ---------------------------------------------------------------------------
# Helper per estrarre il testo da un risultato read_resource
# ---------------------------------------------------------------------------

def _read(mcp_inst, uri: str) -> str:
    """Chiama read_resource e restituisce il testo concatenato dei risultati."""
    items = asyncio.run(mcp_inst.read_resource(uri))
    return "".join(item.content for item in items)


# ===========================================================================
# Wiki resources
# ===========================================================================

class TestWikiResources:
    @pytest.fixture
    def wiki_mcp(self, mcp_instance, tmp_factory):
        register_wiki_resources(mcp_instance, tmp_factory)
        return mcp_instance

    @pytest.fixture
    def real_wiki_mcp(self, mcp_instance, factory_root):
        register_wiki_resources(mcp_instance, factory_root)
        return mcp_instance

    # --- list/concepts ---

    def test_list_concepts_returns_string(self, wiki_mcp) -> None:
        result = _read(wiki_mcp, "wiki://list/concepts")
        assert isinstance(result, str)

    def test_list_concepts_contains_test_concept(self, wiki_mcp) -> None:
        result = _read(wiki_mcp, "wiki://list/concepts")
        assert "test-concept" in result

    def test_list_concepts_real_not_empty(self, real_wiki_mcp) -> None:
        """La factory reale ha almeno un concetto wiki."""
        result = _read(real_wiki_mcp, "wiki://list/concepts")
        assert result.strip() != ""
        assert "(nessun concetto" not in result

    # --- list/syntheses ---

    def test_list_syntheses_returns_string(self, wiki_mcp) -> None:
        result = _read(wiki_mcp, "wiki://list/syntheses")
        assert isinstance(result, str)

    def test_list_syntheses_contains_test_synthesis(self, wiki_mcp) -> None:
        result = _read(wiki_mcp, "wiki://list/syntheses")
        assert "test-synthesis" in result

    # --- wiki://concepts/{slug} ---

    def test_read_concept_returns_content(self, wiki_mcp) -> None:
        result = _read(wiki_mcp, "wiki://concepts/test-concept")
        assert "Test Concept" in result

    def test_read_concept_not_found_raises(self, wiki_mcp) -> None:
        # FastMCP wraps handler exceptions in ValueError (mcp==1.3.0 behavior)
        with pytest.raises(_RESOURCE_NOT_FOUND_ERRORS):
            _read(wiki_mcp, "wiki://concepts/nonexistent-slug-xyz")

    def test_read_concept_real_agent_agnostic(self, real_wiki_mcp) -> None:
        """Legge un concetto reale dalla factory: agent-agnostic.md."""
        result = _read(real_wiki_mcp, "wiki://concepts/agent-agnostic")
        assert len(result) > 0

    # --- wiki://syntheses/{slug} ---

    def test_read_synthesis_returns_content(self, wiki_mcp) -> None:
        result = _read(wiki_mcp, "wiki://syntheses/test-synthesis")
        assert "Sintesi" in result

    def test_read_synthesis_not_found_raises(self, wiki_mcp) -> None:
        with pytest.raises(_RESOURCE_NOT_FOUND_ERRORS):
            _read(wiki_mcp, "wiki://syntheses/nonexistent-synthesis-xyz")

    # --- list_resource_templates verifica registrazione ---

    def test_wiki_resources_registered(self, wiki_mcp) -> None:
        """Le resource template sono registrate correttamente."""
        templates = asyncio.run(wiki_mcp.list_resource_templates())
        uris = [str(t.uriTemplate) for t in templates]
        assert any("wiki://concepts/" in u for u in uris)
        assert any("wiki://syntheses/" in u for u in uris)

    def test_wiki_list_resources_registered(self, wiki_mcp) -> None:
        """Le resource 'list' (non-template) sono presenti."""
        resources = asyncio.run(wiki_mcp.list_resources())
        uris = [str(r.uri) for r in resources]
        assert any("wiki://list/concepts" in u for u in uris)
        assert any("wiki://list/syntheses" in u for u in uris)


# ===========================================================================
# Kanban resources
# ===========================================================================

class TestKanbanResources:
    @pytest.fixture
    def kanban_mcp(self, mcp_instance, tmp_factory):
        register_kanban_resources(mcp_instance, tmp_factory)
        return mcp_instance

    @pytest.fixture
    def real_kanban_mcp(self, mcp_instance, factory_root):
        register_kanban_resources(mcp_instance, factory_root)
        return mcp_instance

    # --- kanban://list/tasks ---

    def test_list_tasks_returns_tsk_001(self, kanban_mcp) -> None:
        result = _read(kanban_mcp, "kanban://list/tasks")
        assert "TSK-001" in result

    def test_list_tasks_real_not_empty(self, real_kanban_mcp) -> None:
        result = _read(real_kanban_mcp, "kanban://list/tasks")
        assert "TSK-" in result

    # --- kanban://tasks/{tsk_id} ---

    def test_read_task_returns_frontmatter(self, kanban_mcp) -> None:
        result = _read(kanban_mcp, "kanban://tasks/TSK-001")
        assert "TSK-001" in result

    def test_read_task_normalized_id(self, kanban_mcp) -> None:
        """Anche ID senza prefisso 'TSK-' viene normalizzato."""
        result = _read(kanban_mcp, "kanban://tasks/001")
        assert "TSK-001" in result

    def test_read_task_not_found_raises(self, kanban_mcp) -> None:
        with pytest.raises(_RESOURCE_NOT_FOUND_ERRORS):
            _read(kanban_mcp, "kanban://tasks/TSK-99999")

    def test_read_task_real_tsk_481(self, real_kanban_mcp) -> None:
        """Legge TSK-481 dalla factory reale: deve contenere l'id nel frontmatter."""
        result = _read(real_kanban_mcp, "kanban://tasks/TSK-481")
        assert "TSK-481" in result

    def test_read_task_real_tsk_406(self, real_kanban_mcp) -> None:
        """Legge TSK-406 dalla factory reale."""
        result = _read(real_kanban_mcp, "kanban://tasks/TSK-406")
        assert "TSK-406" in result

    # --- kanban://list/epics ---

    def test_list_epics_real_not_empty(self, real_kanban_mcp) -> None:
        result = _read(real_kanban_mcp, "kanban://list/epics")
        assert "EP-" in result

    # --- kanban://epics/{ep_id} ---

    def test_read_epic_real_ep_058(self, real_kanban_mcp) -> None:
        """Legge EP-058 dalla factory reale."""
        result = _read(real_kanban_mcp, "kanban://epics/EP-058")
        assert "EP-058" in result

    def test_read_epic_not_found_raises(self, kanban_mcp) -> None:
        with pytest.raises(_RESOURCE_NOT_FOUND_ERRORS):
            _read(kanban_mcp, "kanban://epics/EP-99999")

    # --- kanban://list/stories ---

    def test_list_stories_real_not_empty(self, real_kanban_mcp) -> None:
        result = _read(real_kanban_mcp, "kanban://list/stories")
        assert "US-" in result

    # --- kanban://stories/{us_id} ---

    def test_read_story_real_us_213(self, real_kanban_mcp) -> None:
        """Legge US-213 dalla factory reale (EP-058)."""
        result = _read(real_kanban_mcp, "kanban://stories/US-213")
        assert "US-213" in result

    def test_read_story_not_found_raises(self, kanban_mcp) -> None:
        with pytest.raises(_RESOURCE_NOT_FOUND_ERRORS):
            _read(kanban_mcp, "kanban://stories/US-99999")

    # --- Verifica registrazione template ---

    def test_kanban_templates_registered(self, kanban_mcp) -> None:
        templates = asyncio.run(kanban_mcp.list_resource_templates())
        uris = [str(t.uriTemplate) for t in templates]
        assert any("kanban://tasks/" in u for u in uris)
        assert any("kanban://epics/" in u for u in uris)
        assert any("kanban://stories/" in u for u in uris)


# ===========================================================================
# Config resources
# ===========================================================================

class TestConfigResources:
    @pytest.fixture
    def config_mcp(self, mcp_instance, tmp_factory):
        register_config_resources(mcp_instance, tmp_factory)
        return mcp_instance

    @pytest.fixture
    def real_config_mcp(self, mcp_instance, factory_root):
        register_config_resources(mcp_instance, factory_root)
        return mcp_instance

    def test_read_factory_config_returns_yaml(self, config_mcp) -> None:
        """factory://config restituisce il contenuto YAML della config."""
        result = _read(config_mcp, "factory://config")
        assert "pattern_version" in result

    def test_read_factory_config_redacts_secret(self, config_mcp) -> None:
        """auth_env con valore $ è redatto in factory://config."""
        result = _read(config_mcp, "factory://config")
        # Il valore $MY_SECRET_TOKEN deve essere nascosto
        assert "$MY_SECRET_TOKEN" not in result
        assert "<REDACTED>" in result

    def test_read_factory_config_real(self, real_config_mcp) -> None:
        """La factory reale espone factory://config con pattern_version."""
        result = _read(real_config_mcp, "factory://config")
        assert "pattern_version" in result
        assert "2.38" in result

    def test_read_factory_config_real_redacts_auth_env(self, real_config_mcp) -> None:
        """auth_env nella factory reale è redatto."""
        result = _read(real_config_mcp, "factory://config")
        assert "auth_env:" in result
        assert "<REDACTED>" in result

    def test_read_pattern_version(self, config_mcp) -> None:
        """factory://config/pattern-version restituisce la versione corretta."""
        result = _read(config_mcp, "factory://config/pattern-version")
        assert "2.38" in result

    def test_read_pattern_version_real(self, real_config_mcp) -> None:
        """factory://config/pattern-version sulla factory reale."""
        result = _read(real_config_mcp, "factory://config/pattern-version")
        assert result.strip() != ""
        assert result.strip() != "(pattern_version non trovata)"

    def test_read_factory_config_missing_file_raises(self, mcp_instance, tmp_path) -> None:
        """factory.config.yaml assente → ResourceError (FastMCP concrete resource)."""
        empty = tmp_path / "empty_factory"
        empty.mkdir()
        register_config_resources(mcp_instance, empty)
        with pytest.raises(_RESOURCE_NOT_FOUND_ERRORS):
            _read(mcp_instance, "factory://config")

    def test_negative_no_write_in_config(self, tmp_factory: Path) -> None:
        """Verifica che il file config originale non sia modificato dopo la lettura."""
        config_path = tmp_factory / "factory.config.yaml"
        original_content = config_path.read_text(encoding="utf-8")
        # Registra e legge la risorsa
        from mcp.server.fastmcp import FastMCP
        inst = FastMCP("cfg-test")
        register_config_resources(inst, tmp_factory)
        _read(inst, "factory://config")
        # Il file originale deve essere invariato
        assert config_path.read_text(encoding="utf-8") == original_content
