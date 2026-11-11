"""kanban_history.frontmatter legge anche le liste YAML a blocco."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analytics"))
import kanban_history as kh  # noqa: E402


def test_lista_a_blocco_non_e_piu_vuota():
    fm = kh.frontmatter("---\nid: TSK-1\ndone_by:\n  - ann\n  - \"bob\"  # nota\nstatus: done\n---\n")
    assert fm["done_by"] == "ann, bob"
    assert fm["status"] == "done"


def test_inline_e_scalare_invariati():
    fm = kh.frontmatter("---\ndone_by: [ann, bob]\nstatus: done\nempty:\n---\n")
    assert fm["done_by"] == "[ann, bob]"
    assert fm["empty"] == ""
