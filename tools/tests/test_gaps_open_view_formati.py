"""gaps_open_view.py: due formati di wiki/gaps.md riconosciuti dal file (EP-073 TSK-790)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_P = Path(__file__).resolve().parents[1] / "wiki" / "gaps_open_view.py"
_s = importlib.util.spec_from_file_location("gov", _P)
gov = importlib.util.module_from_spec(_s)
_s.loader.exec_module(gov)


def test_formato_riconosciuto():
    assert gov.formato("## 2026-10-01 — gap\n**Risolto:** si\n") == "sezioni"
    assert gov.formato("## Sezione\n- [ ] aperto\n- [x] chiuso\n") == "voci"
    assert gov.formato("- [CONFIRMED OPEN] ancora aperto\n") == "voci"


def test_voci_aperte_e_chiuse(tmp_path, monkeypatch):
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "gaps.md").write_text(
        "# Gaps\n\n## 2026-10-01 — lotto\n\n- [ ] G-1 aperto\n- [x] G-2 chiuso\n- [CONFIRMED OPEN] G-3\n")
    monkeypatch.setattr(gov, "GAPS_PATH", tmp_path / "wiki" / "gaps.md")
    monkeypatch.setattr(gov, "OUTPUT_PATH", tmp_path / "memory" / "gaps-open.md")
    (tmp_path / "memory").mkdir()
    gov.main()
    vista = (tmp_path / "memory" / "gaps-open.md").read_text()
    assert "G-1 aperto" in vista and "G-3" in vista and "G-2 chiuso" not in vista
