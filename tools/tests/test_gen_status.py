"""Test di tools/docs/gen-status.py (EP-080 US-350): una sola fonte per la maturita' degli adapter."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "docs" / "gen-status.py"
_spec = importlib.util.spec_from_file_location("gen_status", _SCRIPT)
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)


def _factory(tmp_path: Path, riga_aider: str) -> Path:
    for nome, mat, ver in [("claude", "full", "2.44"), ("aider", "partial", "2.13")]:
        d = tmp_path / "adapters" / nome
        d.mkdir(parents=True)
        (d / "manifest.yaml").write_text(
            f"adapter_name: {nome}\nadapter_folder: .{nome}\nmaturity: {mat}\ncontract_version: {ver}\n")
    (tmp_path / "CLAUDE.md").write_text(
        "## Adapter registry (v2.44)\n\n| Adapter | Maturity |\n|---|---|\n"
        "| `.claude/` | full reference (contract 2.44) |\n" + riga_aider + "\n## Altro\n")
    (tmp_path / "docs").mkdir()
    for rel in gs.PAGINE:
        (tmp_path / rel).write_text(f"# x\n\n{gs.BEGIN}\n{gs.END}\n")
    return tmp_path


def test_claude_md_coerente_nessuna_deriva(tmp_path):
    root = _factory(tmp_path, "| `.aider/` | partial (contract 2.13) |")
    assert gs.deriva_claude_md(root, gs.manifest(root)) == []


def test_claude_md_con_maturita_scritta_a_mano_diversa_e_deriva(tmp_path):
    """Il caso misurato il 2026-10-18: README «full v2.13», manifest «partial»."""
    root = _factory(tmp_path, "| `.aider/` | full (contract 2.13) |")
    errori = gs.deriva_claude_md(root, gs.manifest(root))
    assert len(errori) == 1 and "partial" in errori[0]


def test_contratto_divergente_e_deriva(tmp_path):
    root = _factory(tmp_path, "| `.aider/` | partial (contract 2.12) |")
    errori = gs.deriva_claude_md(root, gs.manifest(root))
    assert len(errori) == 1 and "2.12" in errori[0]


def test_blocco_generato_ordina_per_maturita(tmp_path):
    root = _factory(tmp_path, "| `.aider/` | partial |")
    righe = gs.blocco(gs.manifest(root), gs.PAGINE["docs/STATUS.md"]).splitlines()
    assert righe[3].startswith("| claude ") and righe[4].startswith("| aider ")
