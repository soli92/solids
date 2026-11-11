"""Check 4ax — `ignore = dirty` su ogni submodule (EP-072, backport dalla derivata)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "lint" / "check-submodule-ignore.py"
_spec = importlib.util.spec_from_file_location("csi", _SCRIPT)
csi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(csi)

_GM = """\
[submodule "repos/a"]
\tpath = repos/a
\turl = https://example.invalid/a
\tignore = dirty
[submodule "repos/b"]
\tpath = repos/b
\turl = https://example.invalid/b
; commento
[submodule "repos/c"]
\tpath = repos/c
\tignore = untracked
"""


def test_segnala_solo_i_submodule_senza_ignore_accettato(tmp_path):
    (tmp_path / ".gitmodules").write_text(_GM)
    assert csi.scan(tmp_path) == [
        {"submodule": "repos/b", "ignore": None},
        {"submodule": "repos/c", "ignore": "untracked"},
    ]


def test_senza_gitmodules_nessun_finding(tmp_path):
    assert csi.scan(tmp_path) == []


def test_exit_zero_salvo_strict(tmp_path):
    (tmp_path / ".gitmodules").write_text(_GM)
    run = lambda *a: subprocess.run([sys.executable, str(_SCRIPT), str(tmp_path), *a], capture_output=True, text=True)
    r = run()
    assert r.returncode == 0 and "[WARNING][submodule-ignore-missing][4ax]" in r.stdout
    assert run("--strict").returncode == 1


def test_il_master_rispetta_il_check():
    radice = Path(__file__).resolve().parents[2]
    assert csi.scan(radice) == []
