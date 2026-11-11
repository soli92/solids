"""Selezione del backend in HybridSearcher: con backend auto e indice .lance mancante si usa fts5."""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import searcher  # noqa: E402


def _cfg(tmp_path: Path, backend: str) -> Path:
    f = tmp_path / "factory.config.yaml"
    f.write_text("wiki_search:\n  enabled: true\n  backend: %s\n  index_path: %s\n"
                 % (backend, tmp_path / "assente.lance"), encoding="utf-8")
    return f


def test_auto_senza_indice_lance_ripiega_su_fts5(tmp_path, monkeypatch):
    monkeypatch.setattr(searcher, "_hybrid_deps_importable", lambda: True)
    s = searcher.HybridSearcher(str(_cfg(tmp_path, "auto")))
    assert s._backend == "fts5"
    assert s._fallback is False


def test_hybrid_esplicito_senza_indice_resta_hybrid_in_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(searcher, "_hybrid_deps_importable", lambda: True)
    s = searcher.HybridSearcher(str(_cfg(tmp_path, "hybrid")))
    assert s._backend == "hybrid" and s._fallback is True
