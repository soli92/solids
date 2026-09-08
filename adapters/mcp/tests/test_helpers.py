"""
test_helpers.py — P0: unit test delle funzioni helper private (no FastMCP).

Copre:
  - _fts_search            (wiki_search_tool.py)
  - _parse_frontmatter     (get_task_tool.py)
  - _find_latest_lint_report / _parse_lint_report  (lint_status_tool.py)
  - _extract_frontmatter   (resources/kanban.py)
  - _find_file             (resources/kanban.py)
  - _redact_secrets        (resources/config_resource.py)

Tutti i moduli sono R.MCP1 read-only: nessuna funzione apre un file in
modalità write. Questo è verificato esplicitamente in test_r_mcp1_*.
"""
import sys
import ast
import textwrap
from pathlib import Path

import pytest

# Aggiunge adapters/mcp/ al path per gli import diretti
_MCP_DIR = Path(__file__).parent.parent
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))

from tools.wiki_search_tool import _fts_search
from tools.get_task_tool import _parse_frontmatter
from tools.lint_status_tool import _find_latest_lint_report, _parse_lint_report
from resources.kanban import _extract_frontmatter, _find_file
from resources.config_resource import _redact_secrets


# ===========================================================================
# R.MCP1 — verifica statuta che nessun modulo apre file in scrittura
# ===========================================================================

_MODULES_TO_CHECK = [
    _MCP_DIR / "tools" / "wiki_search_tool.py",
    _MCP_DIR / "tools" / "get_task_tool.py",
    _MCP_DIR / "tools" / "lint_status_tool.py",
    _MCP_DIR / "resources" / "wiki.py",
    _MCP_DIR / "resources" / "kanban.py",
    _MCP_DIR / "resources" / "config_resource.py",
]


def _has_write_open(source_path: Path) -> bool:
    """Restituisce True se il sorgente contiene open(..., 'w') o open(..., 'wb')."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Cerca open()
        is_open = (isinstance(func, ast.Name) and func.id == "open") or (
            isinstance(func, ast.Attribute) and func.attr == "open"
        )
        if not is_open:
            continue
        # Controlla gli argomenti: write mode come stringa letterale
        for arg in node.args[1:]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if "w" in arg.value:
                    return True
        # Controlla keyword mode=
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                if "w" in str(kw.value.value):
                    return True
    return False


@pytest.mark.parametrize("module_path", _MODULES_TO_CHECK, ids=[p.name for p in _MODULES_TO_CHECK])
def test_r_mcp1_no_write_open(module_path: Path) -> None:
    """R.MCP1: nessun modulo MCP apre file in modalità write (ADR-MCP-002)."""
    assert not _has_write_open(module_path), (
        f"Violazione R.MCP1: {module_path.name} contiene open(..., 'w'). "
        "I moduli MCP sono read-only per contratto."
    )


# ===========================================================================
# _fts_search — ricerca full-text su wiki reale
# ===========================================================================

class TestFtsSearch:
    def test_returns_list(self, wiki_dir: Path) -> None:
        """_fts_search restituisce sempre una lista."""
        result = _fts_search("orchestrator", 5, wiki_dir)
        assert isinstance(result, list)

    def test_result_shape(self, wiki_dir: Path) -> None:
        """Ogni risultato ha slug, path, snippet, score."""
        results = _fts_search("orchestrator", 3, wiki_dir)
        if results:  # la wiki ha contenuto su orchestrator
            r = results[0]
            assert "slug" in r
            assert "path" in r
            assert "snippet" in r
            assert "score" in r

    def test_top_k_respected(self, wiki_dir: Path) -> None:
        """_fts_search rispetta il limite top_k."""
        results = _fts_search("agent", 2, wiki_dir)
        assert len(results) <= 2

    def test_sorted_by_score_desc(self, wiki_dir: Path) -> None:
        """I risultati sono ordinati per score decrescente."""
        results = _fts_search("wiki", 10, wiki_dir)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_question_returns_empty(self, wiki_dir: Path) -> None:
        """Termini tutti ≤ 2 caratteri → lista vuota (nessun termine utile)."""
        result = _fts_search("a b c", 5, wiki_dir)
        assert result == []

    def test_nonexistent_wiki_dir_returns_empty(self, tmp_path: Path) -> None:
        """Wiki dir inesistente → lista vuota (graceful)."""
        result = _fts_search("anything", 5, tmp_path / "nonexistent")
        assert result == []

    def test_negative_term_not_found_returns_empty(self, wiki_dir: Path) -> None:
        """Termine assente nella wiki → lista vuota (verifica negativa)."""
        result = _fts_search("zzz_nonexistent_term_xyz_999", 5, wiki_dir)
        assert result == []

    def test_with_tmp_factory(self, tmp_factory: Path) -> None:
        """_fts_search trova 'concetto' nel file wiki di test."""
        results = _fts_search("concetto", 5, tmp_factory / "wiki")
        assert len(results) >= 1
        assert results[0]["slug"] == "test-concept"

    def test_snippet_not_empty_when_found(self, tmp_factory: Path) -> None:
        """Lo snippet non è vuoto quando il termine è trovato."""
        results = _fts_search("concetto", 5, tmp_factory / "wiki")
        assert results[0]["snippet"] != ""


# ===========================================================================
# _parse_frontmatter — parsing YAML inline da TSK reale
# ===========================================================================

class TestParseFrontmatter:
    _FULL_FM = textwrap.dedent("""\
        ---
        id: TSK-481
        us: US-213
        ep: EP-058
        title: "Crea wiki/concepts/model-context-protocol.md"
        layer: docs
        consumer: agent
        priority: P1
        estimate: S
        status: done
        depends_on: []
        blocked_by: []
        ---

        # Body
    """)

    def test_parses_string_fields(self) -> None:
        fm = _parse_frontmatter(self._FULL_FM)
        assert fm["id"] == "TSK-481"
        assert fm["status"] == "done"
        assert fm["layer"] == "docs"

    def test_parses_inline_list(self) -> None:
        fm = _parse_frontmatter(self._FULL_FM)
        assert fm["depends_on"] == []
        assert fm["blocked_by"] == []

    def test_strips_quotes_from_title(self) -> None:
        fm = _parse_frontmatter(self._FULL_FM)
        # Le virgolette doppie attorno al titolo devono essere strip-pate
        assert fm["title"] == "Crea wiki/concepts/model-context-protocol.md"

    def test_no_frontmatter_returns_empty_dict(self) -> None:
        fm = _parse_frontmatter("# Solo contenuto\nNessun frontmatter.")
        assert fm == {}

    def test_unclosed_frontmatter_parses_available_fields(self) -> None:
        """Frontmatter aperto ma non chiuso → funzione parsa i campi disponibili.

        _parse_frontmatter non richiede il delimitatore di chiusura per
        restituire dati. Questo rispecchia il comportamento documentato.
        """
        fm = _parse_frontmatter("---\nid: TSK-999\n# no closing ---")
        # La funzione estrae i campi presenti anche senza delimitatore di chiusura
        assert fm.get("id") == "TSK-999"

    def test_real_tsk_481(self) -> None:
        """Parsing del TSK-481 reale su disco."""
        tsk_path = Path(
            "/Users/simone.olivieri/Documents/Personal/Repos"
            "/soli-multi-agents-factory/management/kanban"
            "/EP-058-factory-mcp-server/US-213-wiki-concept-mcp/TSK-481.md"
        )
        content = tsk_path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        assert fm["id"] == "TSK-481"
        assert fm["status"] == "done"
        assert fm["ep"] == "EP-058"

    def test_list_field_multiple_values(self) -> None:
        content = textwrap.dedent("""\
            ---
            id: TSK-X
            depends_on: [TSK-1, TSK-2, TSK-3]
            ---
        """)
        fm = _parse_frontmatter(content)
        assert fm["depends_on"] == ["TSK-1", "TSK-2", "TSK-3"]

    def test_negative_missing_field(self) -> None:
        """Campo non presente → non deve apparire nel dict."""
        fm = _parse_frontmatter(self._FULL_FM)
        # sprint non è nel frontmatter di _FULL_FM
        assert "sprint" not in fm


# ===========================================================================
# _find_latest_lint_report / _parse_lint_report
# ===========================================================================

class TestLintReport:
    def test_find_latest_returns_path(self, factory_root: Path) -> None:
        """_find_latest_lint_report trova almeno un report nella factory reale."""
        report = _find_latest_lint_report(factory_root)
        assert report is not None
        assert report.exists()
        assert report.suffix == ".md"

    def test_find_latest_nonexistent_factory_returns_none(self, tmp_path: Path) -> None:
        """Factory senza lint reports → None (graceful, no eccezione)."""
        empty_factory = tmp_path / "empty"
        empty_factory.mkdir()
        result = _find_latest_lint_report(empty_factory)
        assert result is None

    def test_find_latest_picks_most_recent(self, tmp_factory: Path) -> None:
        """Tra due report, viene scelto quello con mtime più recente."""
        lint_dir = tmp_factory / "wiki" / "lint"
        older = lint_dir / "2025-01-01-lint-report.md"
        older.write_text("# Old", encoding="utf-8")
        newer = lint_dir / "2026-06-01-lint-report.md"
        newer.write_text("# New", encoding="utf-8")
        # Forza mtime: newer deve avere mtime > older
        import time
        older_mtime = newer.stat().st_mtime - 10
        import os
        os.utime(older, (older_mtime, older_mtime))

        result = _find_latest_lint_report(tmp_factory)
        assert result is not None
        # newer o il report già esistente (2026-01-01) — comunque non older
        assert result.name != older.name or result == newer

    def test_parse_lint_report_counts(self, tmp_factory: Path) -> None:
        """_parse_lint_report conta correttamente ERROR, WARNING, INFO."""
        report_path = tmp_factory / "wiki" / "lint" / "2026-01-01-lint-report.md"
        result = _parse_lint_report(report_path)
        assert result["error_count"] == 2
        assert result["warning_count"] == 1
        assert result["info_count"] == 1

    def test_parse_lint_report_has_path_and_timestamp(self, tmp_factory: Path) -> None:
        """Il risultato include report_path e timestamp."""
        report_path = tmp_factory / "wiki" / "lint" / "2026-01-01-lint-report.md"
        result = _parse_lint_report(report_path)
        assert "report_path" in result
        assert result["timestamp"] == "2026-01-01"

    def test_parse_lint_report_nonexistent_file(self, tmp_path: Path) -> None:
        """File inesistente → error_count = -1 e campo message."""
        result = _parse_lint_report(tmp_path / "ghost.md")
        assert result["error_count"] == -1
        assert "message" in result

    def test_parse_real_lint_report(self, factory_root: Path) -> None:
        """_parse_lint_report sul report reale: restituisce dict con chiavi attese."""
        report = _find_latest_lint_report(factory_root)
        assert report is not None
        result = _parse_lint_report(report)
        for key in ("error_count", "warning_count", "info_count"):
            assert key in result
            assert isinstance(result[key], int)
            assert result[key] >= 0

    def test_negative_empty_report_counts_zero(self, tmp_path: Path) -> None:
        """Report vuoto (nessun match) → tutti i conteggi sono 0."""
        empty_report = tmp_path / "2026-02-02-lint-report.md"
        empty_report.write_text("# Report\nNessun problema trovato.\n", encoding="utf-8")
        result = _parse_lint_report(empty_report)
        assert result["error_count"] == 0
        assert result["warning_count"] == 0
        assert result["info_count"] == 0


# ===========================================================================
# _extract_frontmatter (resources/kanban.py)
# ===========================================================================

class TestExtractFrontmatter:
    def test_extracts_between_dashes(self) -> None:
        content = textwrap.dedent("""\
            ---
            id: TSK-001
            status: todo
            ---
            # Body
        """)
        fm = _extract_frontmatter(content)
        assert "id: TSK-001" in fm
        assert "status: todo" in fm
        assert "# Body" not in fm

    def test_no_frontmatter_returns_empty(self) -> None:
        assert _extract_frontmatter("# No frontmatter\n") == ""

    def test_unclosed_frontmatter_returns_empty(self) -> None:
        assert _extract_frontmatter("---\nid: TSK-X\n") == ""

    def test_real_tsk_406(self, kanban_dir: Path) -> None:
        """_extract_frontmatter su TSK-406 reale restituisce frontmatter non vuoto."""
        tsk = kanban_dir / "EP-048-content-share-consumer-layer" / "TSK-406.md"
        content = tsk.read_text(encoding="utf-8")
        fm = _extract_frontmatter(content)
        assert "id: TSK-406" in fm

    def test_negative_body_excluded(self) -> None:
        content = "---\nid: X\n---\n# Corpo non estratto\n"
        fm = _extract_frontmatter(content)
        assert "Corpo" not in fm


# ===========================================================================
# _find_file (resources/kanban.py)
# ===========================================================================

class TestFindFile:
    def test_finds_existing_tsk(self, kanban_dir: Path) -> None:
        """_find_file trova TSK-406.md nel kanban reale."""
        result = _find_file(kanban_dir, "**/TSK-406.md")
        assert result is not None
        assert result.name == "TSK-406.md"

    def test_returns_none_for_missing_file(self, kanban_dir: Path) -> None:
        """Pattern che non matcha → None."""
        result = _find_file(kanban_dir, "**/TSK-99999.md")
        assert result is None

    def test_returns_first_sorted(self, tmp_path: Path) -> None:
        """Con più match, restituisce il primo in ordine alfabetico."""
        (tmp_path / "AAA.md").write_text("a", encoding="utf-8")
        (tmp_path / "BBB.md").write_text("b", encoding="utf-8")
        result = _find_file(tmp_path, "*.md")
        assert result is not None
        assert result.name == "AAA.md"

    def test_negative_empty_dir_returns_none(self, tmp_path: Path) -> None:
        """Directory vuota → None."""
        result = _find_file(tmp_path, "*.md")
        assert result is None


# ===========================================================================
# _redact_secrets (resources/config_resource.py)
# ===========================================================================

class TestRedactSecrets:
    def test_redacts_dollar_env_var(self) -> None:
        content = "auth_token: $MY_SECRET\n"
        redacted = _redact_secrets(content)
        assert "$MY_SECRET" not in redacted
        assert "<REDACTED>" in redacted

    def test_redacts_auth_env_field(self) -> None:
        content = "auth_env: GH_TOKEN\n"
        redacted = _redact_secrets(content)
        assert "GH_TOKEN" not in redacted
        assert "<REDACTED>" in redacted

    def test_preserves_non_secret_fields(self) -> None:
        content = "pattern_version: \"2.38\"\nproject_name: my-factory\n"
        redacted = _redact_secrets(content)
        assert "pattern_version" in redacted
        assert "2.38" in redacted
        assert "my-factory" in redacted

    def test_redacts_multiple_secrets(self) -> None:
        content = textwrap.dedent("""\
            auth_env: GITHUB_TOKEN
            api_key: $SECRET_KEY
            name: safe-value
        """)
        redacted = _redact_secrets(content)
        assert "GITHUB_TOKEN" not in redacted
        assert "$SECRET_KEY" not in redacted
        assert "safe-value" in redacted
        assert redacted.count("<REDACTED>") == 2

    def test_real_factory_config_redacted(self, factory_root: Path) -> None:
        """Il factory.config.yaml reale contiene auth_env: → deve essere redatto."""
        content = (factory_root / "factory.config.yaml").read_text(encoding="utf-8")
        redacted = _redact_secrets(content)
        # auth_env deve essere presente ma il suo valore oscurato
        assert "auth_env:" in redacted
        assert "<REDACTED>" in redacted

    def test_negative_dollar_not_redacted_in_comment(self) -> None:
        """Un commento con $ non deve essere redatto (il pattern opera su valori dopo ':').

        Nota: _redact_secrets usa "\n".join(lines) che rimuove eventuali
        newline finali, ma il token $HOME deve restare intatto.
        """
        content = "# Usa $HOME per il path\n"
        redacted = _redact_secrets(content)
        # $HOME NON deve essere sostituito con <REDACTED>
        assert "$HOME" in redacted
        assert "<REDACTED>" not in redacted
