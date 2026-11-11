"""
Tests for chunk_ast_aware (ADR-C, TSK-504, EP-042 Phase 2).

AC4 — code fence not split:
    chunk_ast_aware must never create a chunk boundary inside a ``` or ~~~ fence.
    An H2 heading that appears inside a code fence must NOT become a section split.

AC5 — silent fallback when tree-sitter unavailable:
    If tree-sitter / tree_sitter_languages cannot be imported, chunk_ast_aware
    silently falls back to chunk_h2 for .py/.ts/.go/.rs files (R.WS1).
    No exception must propagate to the caller.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the parent directory is on sys.path so indexer is importable
# regardless of cwd.
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from indexer import chunk_ast_aware, chunk_document, chunk_h2  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_page(raw_body: str, path: str = "wiki/test.md") -> dict:
    """Build a minimal page dict for testing."""
    return {
        "path": path,
        "title": "Test Page",
        "type": "concept",
        "status": "draft",
        "tags_json": "[]",
        "raw_body": raw_body,
    }


# ---------------------------------------------------------------------------
# AC4 — code fence not split
# ---------------------------------------------------------------------------

class TestCodeFenceNotSplit:
    """AC4: H2 headings inside code fences must not become section boundaries."""

    def test_h2_inside_backtick_fence_not_split(self):
        """
        An H2 that appears inside a triple-backtick fence must be ignored as a
        split point. The resulting chunks must NOT contain a section named after
        the fenced heading.
        """
        raw_body = (
            "Intro paragraph.\n\n"
            "```python\n"
            "## This is inside a fence — must NOT split\n"
            "print('hello')\n"
            "```\n\n"
            "## Real Section\n\n"
            "Content after the real heading.\n"
        )
        page = _make_page(raw_body)
        chunks = chunk_ast_aware(page)

        section_labels = [c["section"] for c in chunks]

        # The fenced pseudo-heading must NOT appear as a section
        assert "This is inside a fence — must NOT split" not in section_labels, (
            f"Fenced H2 incorrectly became a section boundary. Sections: {section_labels}"
        )

        # The real H2 must appear as a section
        assert "Real Section" in section_labels, (
            f"Real H2 heading not found as section. Sections: {section_labels}"
        )

    def test_h2_inside_tilde_fence_not_split(self):
        """Same check but with ~~~ (tilde) fences."""
        raw_body = (
            "Intro.\n\n"
            "~~~bash\n"
            "## Fake H2 inside tilde fence\n"
            "echo test\n"
            "~~~\n\n"
            "## After Fence\n\n"
            "Content.\n"
        )
        page = _make_page(raw_body)
        chunks = chunk_ast_aware(page)

        section_labels = [c["section"] for c in chunks]

        assert "Fake H2 inside tilde fence" not in section_labels
        assert "After Fence" in section_labels

    def test_fence_content_stays_in_same_chunk(self):
        """
        The fence body and its surrounding section content must end up in the
        same chunk, not split across two chunks.
        """
        raw_body = (
            "## Before Fence\n\n"
            "Some text.\n\n"
            "```\n"
            "## Not a real heading\n"
            "code line\n"
            "```\n\n"
            "More text after fence.\n"
        )
        page = _make_page(raw_body)
        chunks = chunk_ast_aware(page)

        # Only one section: "Before Fence"
        section_labels = [c["section"] for c in chunks]
        assert "Before Fence" in section_labels
        assert "Not a real heading" not in section_labels

        # The chunk for "Before Fence" must include the fence content
        before_fence_chunk = next(c for c in chunks if c["section"] == "Before Fence")
        assert "```" in before_fence_chunk["content"], (
            "Code fence delimiters missing from chunk content"
        )
        assert "code line" in before_fence_chunk["content"], (
            "Code fence body missing from chunk content"
        )

    def test_nested_fence_close_not_confused(self):
        """
        A line that starts with backticks but is NOT a closing fence (e.g. fewer
        backticks than the opener) must not prematurely close the fence.
        """
        # 4-backtick fence containing a 3-backtick block (nested)
        raw_body = (
            "````markdown\n"
            "## Heading inside outer fence\n"
            "```inner\n"
            "code\n"
            "```\n"
            "````\n\n"
            "## Outer Section\n\n"
            "Real content.\n"
        )
        page = _make_page(raw_body)
        chunks = chunk_ast_aware(page)

        section_labels = [c["section"] for c in chunks]
        assert "Heading inside outer fence" not in section_labels
        assert "Outer Section" in section_labels

    def test_chunk_document_dispatcher_ast_aware_respects_fence(self):
        """
        chunk_document with strategy="ast_aware" must behave identically to
        calling chunk_ast_aware directly.
        """
        raw_body = (
            "```\n"
            "## Inside fence\n"
            "```\n\n"
            "## Outside fence\n\n"
            "Content.\n"
        )
        page = _make_page(raw_body)

        direct = chunk_ast_aware(page)
        via_dispatcher = chunk_document(page, strategy="ast_aware")

        assert direct == via_dispatcher

    def test_chunk_document_default_strategy_is_h2_section(self):
        """
        chunk_document with no strategy arg (default "h2_section") must behave
        identically to chunk_h2 — backward compat (R.WS2).
        """
        raw_body = "## Section A\n\nBody A.\n\n## Section B\n\nBody B.\n"
        page = _make_page(raw_body)

        from_default = chunk_document(page)
        from_h2 = chunk_h2(page)

        assert from_default == from_h2

    def test_no_chunks_lost_when_fence_spans_end_of_body(self):
        """
        An unclosed fence (edge case: fence opened but file ends) must not
        cause an exception and must not lose the preceding section content.
        """
        raw_body = (
            "## Real Section\n\n"
            "Content before fence.\n\n"
            "```\n"
            "## Inside unclosed fence\n"
            "code\n"
            # Note: fence is intentionally not closed
        )
        page = _make_page(raw_body)

        # Must not raise
        chunks = chunk_ast_aware(page)

        assert isinstance(chunks, list)
        section_labels = [c["section"] for c in chunks]
        # The unclosed fence content must not have become a separate section
        assert "Inside unclosed fence" not in section_labels


# ---------------------------------------------------------------------------
# AC5 — silent fallback when tree-sitter unavailable
# ---------------------------------------------------------------------------

class TestFallbackWhenTreeSitterUnavailable:
    """AC5: chunk_ast_aware falls back silently to chunk_h2 for code files
    when tree-sitter dependencies cannot be imported (R.WS1)."""

    def _inject_missing_module(self, module_name: str):
        """
        Insert None into sys.modules to simulate an uninstallable package.
        Python's import machinery raises ImportError when it finds None.
        """
        sys.modules[module_name] = None  # type: ignore[assignment]

    _SENTINEL = object()

    def _restore_module(self, module_name: str, original):
        if original is self._SENTINEL:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original

    def test_fallback_no_exception_for_py_file(self):
        """
        For a .py file, if tree_sitter_languages is not importable,
        chunk_ast_aware must return a non-empty list (fallback) without raising.
        """
        orig_tsl = sys.modules.get("tree_sitter_languages", self._SENTINEL)
        orig_ts = sys.modules.get("tree_sitter", self._SENTINEL)

        try:
            self._inject_missing_module("tree_sitter_languages")
            self._inject_missing_module("tree_sitter")

            page = _make_page(
                "def hello():\n    return 'world'\n\ndef bye():\n    pass\n",
                path="src/module.py",
            )

            # Must not raise
            try:
                chunks = chunk_ast_aware(page)
            except Exception as exc:
                assert False, (
                    f"chunk_ast_aware raised {type(exc).__name__} instead of "
                    f"falling back silently: {exc}"
                )

            # Must return a list (may be empty or contain a fallback _root chunk)
            assert isinstance(chunks, list), "chunk_ast_aware must return a list"

        finally:
            self._restore_module("tree_sitter_languages", orig_tsl)
            self._restore_module("tree_sitter", orig_ts)

    def test_fallback_result_matches_chunk_h2(self):
        """
        When tree-sitter is unavailable for a .py file, the fallback result
        must be identical to chunk_h2(page) (same data, same structure).
        """
        orig_tsl = sys.modules.get("tree_sitter_languages", self._SENTINEL)
        orig_ts = sys.modules.get("tree_sitter", self._SENTINEL)

        try:
            self._inject_missing_module("tree_sitter_languages")
            self._inject_missing_module("tree_sitter")

            page = _make_page(
                "def hello():\n    return 'world'\n",
                path="src/utils.py",
            )

            chunks_fallback = chunk_ast_aware(page)
            chunks_h2 = chunk_h2(page)

            assert chunks_fallback == chunks_h2, (
                "Fallback result differs from chunk_h2 output:\n"
                f"  fallback: {chunks_fallback}\n"
                f"  chunk_h2: {chunks_h2}"
            )

        finally:
            self._restore_module("tree_sitter_languages", orig_tsl)
            self._restore_module("tree_sitter", orig_ts)

    def test_md_files_unaffected_by_missing_treesitter(self):
        """
        .md files use the fence-aware regex path (no tree-sitter dep).
        Missing tree-sitter must not affect MD chunking at all.
        """
        orig_tsl = sys.modules.get("tree_sitter_languages", self._SENTINEL)

        try:
            self._inject_missing_module("tree_sitter_languages")

            raw_body = (
                "## Section A\n\nBody A.\n\n"
                "```\n## Inside fence\n```\n\n"
                "## Section B\n\nBody B.\n"
            )
            page = _make_page(raw_body)
            chunks = chunk_ast_aware(page)

            section_labels = [c["section"] for c in chunks]
            assert "Section A" in section_labels
            assert "Section B" in section_labels
            assert "Inside fence" not in section_labels

        finally:
            self._restore_module("tree_sitter_languages", orig_tsl)

    def test_chunk_document_ast_aware_fallback_no_exception(self):
        """
        chunk_document with strategy="ast_aware" must also fall back silently
        when tree-sitter is missing (end-to-end through dispatcher).
        """
        orig_tsl = sys.modules.get("tree_sitter_languages", self._SENTINEL)
        orig_ts = sys.modules.get("tree_sitter", self._SENTINEL)

        try:
            self._inject_missing_module("tree_sitter_languages")
            self._inject_missing_module("tree_sitter")

            page = _make_page(
                "class MyClass:\n    pass\n",
                path="app/models.py",
            )

            try:
                chunks = chunk_document(page, strategy="ast_aware")
            except Exception as exc:
                assert False, (
                    f"chunk_document(strategy='ast_aware') raised {type(exc).__name__}: {exc}"
                )

            assert isinstance(chunks, list)

        finally:
            self._restore_module("tree_sitter_languages", orig_tsl)
            self._restore_module("tree_sitter", orig_ts)
