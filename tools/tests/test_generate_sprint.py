"""generate_sprint.py — sprint.md come vista generata dal frontmatter (EP-073 TSK-789)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "kanban" / "generate_sprint.py"


def _tsk(root: Path, ep: str, cartella_us: str, tid: str, status: str, pri: str = "P1", **extra) -> None:
    d = root / "management" / "kanban" / ep / cartella_us
    d.mkdir(parents=True, exist_ok=True)
    (root / "management" / "kanban" / ep / f"{ep.split('-slug')[0]}.md").write_text(
        f"---\nid: {ep.split('-slug')[0]}\ntitle: Epica\nstatus: in_progress\n---\n")
    righe = "".join(f"{k}: {v}\n" for k, v in extra.items())
    (d / f"{tid}.md").write_text(f"---\nid: {tid}\ntitle: t {tid}\nstatus: {status}\npriority: {pri}\n{righe}---\n")


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI), "--root", str(root), *args], capture_output=True, text=True)


def test_id_con_e_senza_prefisso_e_stato_normalizzato(tmp_path):
    (tmp_path / "factory.config.yaml").write_text("project:\n  name: prova\n")
    _tsk(tmp_path, "EP-001-slug", "US-001-x", "TSK-001", "in-progress", story="US-001")
    _tsk(tmp_path, "XX-EP-002", "XX-US-002", "XX-TSK-002", "todo", "P3", us="XX-US-002")
    _tsk(tmp_path, "EP-001-slug", "US-001-x", "TSK-003", "done")
    out = _run(tmp_path, "--stdout").stdout
    assert "# Sprint view — prova" in out
    assert "[TSK-001]" in out and "| US-001 |" in out and "| in_progress |" in out
    assert "[XX-TSK-002]" in out and "TSK-003" not in out
    assert "Totale TSK aperti: 2 (sprint corrente 1, lookahead 1)." in out


def test_check_segnala_la_deriva(tmp_path):
    _tsk(tmp_path, "EP-001-slug", "US-001-x", "TSK-001", "todo")
    assert _run(tmp_path).returncode == 0
    assert _run(tmp_path, "--check").returncode == 0
    _tsk(tmp_path, "EP-001-slug", "US-001-x", "TSK-004", "todo")
    assert _run(tmp_path, "--check").returncode == 1
