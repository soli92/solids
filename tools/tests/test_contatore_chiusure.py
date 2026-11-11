"""contatore_chiusure.py — trigger on_tsk_closed_count (EP-072 TSK-779)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "vcs" / "contatore_chiusure.py"
CFG = """\
repo_align:
  enabled: true
  triggers:
    on_tsk_closed_count: 2   # ogni 2 TSK
    on_session_close: false
ai_policy_check:
  enabled: false
  triggers:
    on_tsk_closed_count: 1
altro: x
"""


def _run(root: Path, tsk: str) -> list[dict]:
    r = subprocess.run([sys.executable, str(CLI), "--root", str(root), "--tsk", tsk, "--json",
                        "--now", "2026-10-07T10:00:00Z"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_soglia_raggiunta_e_azzeramento(tmp_path):
    (tmp_path / "factory.config.yaml").write_text(CFG)
    assert _run(tmp_path, "TSK-1") == [{"capability": "repo-align", "count": 1, "soglia": 2, "esegui": None}]
    e = _run(tmp_path, "TSK-2")
    assert e[0]["esegui"] == "python3 tools/vcs/repo-align.py"
    assert "count: 0" in (tmp_path / "memory" / "repo-align-counter.yaml").read_text()
    assert not (tmp_path / "memory" / "ai-policy-counter.yaml").exists()  # capability spenta


def test_spento_o_senza_soglia_non_fa_nulla(tmp_path):
    (tmp_path / "factory.config.yaml").write_text(CFG.replace("on_tsk_closed_count: 2", "on_tsk_closed_count: 0"))
    assert _run(tmp_path, "TSK-1") == []
    assert not (tmp_path / "memory").exists()


def test_contatore_illeggibile_e_un_avviso(tmp_path):
    (tmp_path / "factory.config.yaml").write_text(CFG)
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "repo-align-counter.yaml").write_text("rotto\n")
    e = _run(tmp_path, "TSK-1")
    assert "errore" in e[0]


def test_intestazione_del_contatore_conservata(tmp_path):
    (tmp_path / "factory.config.yaml").write_text(CFG)
    (tmp_path / "memory").mkdir()
    c = tmp_path / "memory" / "repo-align-counter.yaml"
    c.write_text("# contatore della factory\ncount: 0\nlast_reset_at: null\nlast_tsk_id: null\nlast_seen_at: null\n")
    _run(tmp_path, "TSK-9")
    assert c.read_text() == ("# contatore della factory\ncount: 1\nlast_reset_at: null\n"
                             "last_tsk_id: TSK-9\nlast_seen_at: 2026-10-07T10:00:00Z\n")
