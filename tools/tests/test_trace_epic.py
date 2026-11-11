"""Test di tools/docs/trace-epic.py (EP-080 US-352): la traccia si ricava da kanban e git."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("trace_epic", _ROOT / "tools" / "docs" / "trace-epic.py")
te = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(te)


def test_esiti_conta_le_righe_della_tabella_di_chiusura():
    tabella = ("| AC | Esito | Evidenza |\n|---|---|---|\n| a | SI | x |\n| b | DEROGA | y |\n"
               "| c | SI: online | z |\n")
    assert te.esiti(tabella) == {"SI": 2, "DEROGA": 1}


def test_frontmatter_legge_liste():
    fm, corpo = te.frontmatter_testo('---\nid: EP-1\nsource:\n  - "a"\n  - b\n---\n# x\n')
    assert fm["id"] == "EP-1" and fm["source"] == ["a", "b"] and corpo.startswith("# x")


def test_traccia_di_ep_079_ha_le_quattro_sezioni():
    if not list((_ROOT / "management" / "kanban").glob("EP-079-*")):
        pytest.skip("EP-079 esiste solo nel meta-framework")
    testo = te.traccia("EP-079", "HEAD")
    for titolo in ("## 1. Why", "## 2. What", "## 3. How", "## 4. Record"):
        assert titolo in testo
    assert "#### TSK-832 — closure, verbatim" in testo and "Deroga ritirata" in testo
