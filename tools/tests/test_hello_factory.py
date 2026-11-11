"""examples/hello-factory (EP-081 US-354): la catena compilata resta verde, e un anello rotto si vede.

Solo check deterministici: nessun confronto con l'output di un modello.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ESEMPIO = ROOT / "examples" / "hello-factory"
RUNNER = ROOT / "tools" / "lint" / "run-deterministic.py"

# l'esempio esiste solo nel meta-framework: in una factory installata il test non si applica
pytestmark = pytest.mark.skipif(not ESEMPIO.is_dir(), reason="examples/hello-factory esiste solo nel meta-framework")


def _lint(radice: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(RUNNER), "--root", str(radice), "--strict",
                           "--solo", "1,3,4au"], capture_output=True, text=True)


def test_esempio_verde():
    r = _lint(ESEMPIO)
    assert r.returncode == 0, r.stdout
    assert "**Totale script**: 0 ERROR, 0 WARNING" in r.stdout


def test_ogni_citazione_punta_a_un_file_di_raw():
    for pagina in (ESEMPIO / "wiki").rglob("*.md"):
        for fonte in re.findall(r"\[\^src: ([^\s\]]+)", pagina.read_text(encoding="utf-8")):
            assert (ESEMPIO / fonte).is_file(), f"{pagina.name} cita {fonte}, che non esiste"


def test_il_task_chiuso_ha_date_e_tabella_di_chiusura():
    tsk = next(ESEMPIO.rglob("TSK-001.md")).read_text(encoding="utf-8")
    assert re.search(r"^status: done$", tsk, re.M)
    assert re.search(r"^started_at: \d{4}-\d{2}-\d{2}$", tsk, re.M)
    assert re.search(r"^closed_at: \d{4}-\d{2}-\d{2}$", tsk, re.M)
    assert "## Closure" in tsk and "| Evidence |" in tsk


def test_anello_rotto_trovato(tmp_path):
    """La storia punta a una pagina wiki che non c'e' piu': il check 3 lo segnala come ERROR."""
    copia = tmp_path / "hello-factory"
    shutil.copytree(ESEMPIO, copia)
    us = next(copia.rglob("US-001.md"))
    us.write_text(us.read_text(encoding="utf-8").replace(
        "wiki/concepts/loan-rules.md", "wiki/concepts/loan-rule.md"), encoding="utf-8")
    r = _lint(copia)
    assert r.returncode == 1
    assert "broken-wiki-page" in r.stdout
