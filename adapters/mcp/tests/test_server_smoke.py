"""
test_server_smoke.py — P2: smoke test di server.py.

Verifica:
  1. Importazione del modulo server.py con FACTORY_ROOT valida → nessuna eccezione.
  2. Avvio come subprocess senza FACTORY_ROOT → exit code != 0.
  3. Avvio come subprocess con FACTORY_ROOT invalida → exit code != 0.
  4. Il server espone i tool e le resource attesi dopo l'importazione.

NOTA: server.py valida FACTORY_ROOT a import time (fail fast).
Il test di importazione usa importlib con env var patchata.
"""
import importlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_FACTORY_ROOT = Path(
    "/Users/simone.olivieri/Documents/Personal/Repos/soli-multi-agents-factory"
)
_SERVER_PATH = Path(__file__).parent.parent / "server.py"
_PYTHON = "python3.12"


# ===========================================================================
# Subprocess smoke tests (non richiedono importazione del modulo)
# ===========================================================================

class TestServerSubprocess:
    def test_missing_factory_root_exits_nonzero(self) -> None:
        """Senza FACTORY_ROOT il server termina con exit code != 0."""
        env = {k: v for k, v in os.environ.items() if k != "FACTORY_ROOT"}
        result = subprocess.run(
            [_PYTHON, str(_SERVER_PATH)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode != 0, (
            "Il server avviato senza FACTORY_ROOT dovrebbe uscire con codice != 0. "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        )

    def test_missing_factory_root_prints_error(self) -> None:
        """Senza FACTORY_ROOT il server stampa un messaggio di errore su stderr."""
        env = {k: v for k, v in os.environ.items() if k != "FACTORY_ROOT"}
        result = subprocess.run(
            [_PYTHON, str(_SERVER_PATH)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert "FACTORY_ROOT" in result.stderr, (
            "Il messaggio di errore dovrebbe menzionare FACTORY_ROOT"
        )

    def test_invalid_factory_root_exits_nonzero(self) -> None:
        """FACTORY_ROOT che punta a un path non-directory → exit code != 0."""
        env = {**os.environ, "FACTORY_ROOT": "/nonexistent/path/xyz_12345"}
        result = subprocess.run(
            [_PYTHON, str(_SERVER_PATH)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode != 0

    def test_invalid_factory_root_prints_error(self) -> None:
        """FACTORY_ROOT invalida → messaggio di errore su stderr."""
        env = {**os.environ, "FACTORY_ROOT": "/nonexistent/path/xyz_12345"}
        result = subprocess.run(
            [_PYTHON, str(_SERVER_PATH)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert "ERROR" in result.stderr or "non è una directory" in result.stderr


# ===========================================================================
# Import-level smoke test (verifica che il modulo si carichi senza errori)
# ===========================================================================

class TestServerImport:
    """
    Verifica che server.py si importi correttamente con FACTORY_ROOT valida.

    Usa importlib per caricare il modulo in un namespace isolato, con
    FACTORY_ROOT patchato nell'ambiente prima dell'import.

    AVVERTENZA: server.py ha effetti collaterali a import time (registrazione
    resource e tool su `mcp`). Il modulo viene isolato dal resto della suite
    usando un nome univoco.
    """

    def test_server_imports_without_error(self, monkeypatch) -> None:
        """server.py si importa senza eccezioni con FACTORY_ROOT valida."""
        monkeypatch.setenv("FACTORY_ROOT", str(_FACTORY_ROOT))

        # Aggiungi adapters/mcp/ al path se necessario
        mcp_dir = str(_SERVER_PATH.parent)
        if mcp_dir not in sys.path:
            sys.path.insert(0, mcp_dir)

        spec = importlib.util.spec_from_file_location(
            "_server_smoke_test_module", _SERVER_PATH
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)

        # Esegue il modulo — nessuna eccezione attesa
        spec.loader.exec_module(module)  # type: ignore[union-attr]

    def test_server_module_has_mcp_instance(self, monkeypatch) -> None:
        """Dopo l'import, il modulo espone un'istanza FastMCP chiamata 'mcp'."""
        monkeypatch.setenv("FACTORY_ROOT", str(_FACTORY_ROOT))

        mcp_dir = str(_SERVER_PATH.parent)
        if mcp_dir not in sys.path:
            sys.path.insert(0, mcp_dir)

        spec = importlib.util.spec_from_file_location(
            "_server_mcp_check_module", _SERVER_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        from mcp.server.fastmcp import FastMCP
        assert hasattr(module, "mcp")
        assert isinstance(module.mcp, FastMCP)

    def test_server_tools_registered(self, monkeypatch) -> None:
        """Dopo l'import, i tool query_wiki, get_task, lint_status sono registrati."""
        import asyncio
        monkeypatch.setenv("FACTORY_ROOT", str(_FACTORY_ROOT))

        mcp_dir = str(_SERVER_PATH.parent)
        if mcp_dir not in sys.path:
            sys.path.insert(0, mcp_dir)

        spec = importlib.util.spec_from_file_location(
            "_server_tools_check_module", _SERVER_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        mcp = module.mcp
        tools = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tools}
        assert "query_wiki" in tool_names
        assert "get_task" in tool_names
        assert "lint_status" in tool_names

    def test_server_resources_registered(self, monkeypatch) -> None:
        """Dopo l'import, le resource wiki://, kanban://, factory:// sono registrate."""
        import asyncio
        monkeypatch.setenv("FACTORY_ROOT", str(_FACTORY_ROOT))

        mcp_dir = str(_SERVER_PATH.parent)
        if mcp_dir not in sys.path:
            sys.path.insert(0, mcp_dir)

        spec = importlib.util.spec_from_file_location(
            "_server_resources_check_module", _SERVER_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        mcp = module.mcp
        resources = asyncio.run(mcp.list_resources())
        templates = asyncio.run(mcp.list_resource_templates())

        all_uris = (
            [str(r.uri) for r in resources]
            + [str(t.uriTemplate) for t in templates]
        )
        # Deve esserci almeno un URI per ogni scheme
        assert any("wiki://" in u for u in all_uris), "Nessuna resource wiki://"
        assert any("kanban://" in u for u in all_uris), "Nessuna resource kanban://"
        assert any("factory://" in u for u in all_uris), "Nessuna resource factory://"

    def test_server_factory_root_resolved(self, monkeypatch) -> None:
        """FACTORY_ROOT nel modulo è un Path risolto e punta alla directory reale."""
        monkeypatch.setenv("FACTORY_ROOT", str(_FACTORY_ROOT))

        mcp_dir = str(_SERVER_PATH.parent)
        if mcp_dir not in sys.path:
            sys.path.insert(0, mcp_dir)

        spec = importlib.util.spec_from_file_location(
            "_server_root_check_module", _SERVER_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        assert hasattr(module, "FACTORY_ROOT")
        assert module.FACTORY_ROOT.is_dir()
        assert module.FACTORY_ROOT == _FACTORY_ROOT.resolve()
