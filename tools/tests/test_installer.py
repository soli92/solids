"""Installer v2.45+ (EP-082 US-357): una factory installata dichiara la versione della sorgente,
ha il PATTERN completo e passa i check deterministici. Da repo e da zip.

Prima di EP-082 nessun test eseguiva l'installer: v2.40 e' rimasto indietro di cinque release.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INST = ROOT / "installers" / "v2.45"
GRUPPI = "1,3,4au,4am,4ar,4aq,4ax,4bb,4bc,4bd,4be"
OGGI = "2026-10-18"

pytestmark = pytest.mark.skipif(not INST.is_dir(), reason="gli installer esistono solo nel meta-framework")


def _versione_sorgente() -> str:
    return re.search(r"Pattern version:\s*\*\*([0-9.]+)\*\*", (ROOT / "PATTERN.md").read_text()).group(1)


def _verifica(factory: Path) -> None:
    cfg = (factory / "factory.config.yaml").read_text(encoding="utf-8")
    assert f'pattern_version: "{_versione_sorgente()}"' in cfg
    assert f'required_from: "{OGGI}"' in cfg
    moduli = re.findall(r"\]\((PATTERN-[A-Za-z0-9_-]+\.md)\)", (ROOT / "PATTERN.md").read_text())
    for m in set(moduli):
        assert (factory / m).is_file(), f"modulo {m} non copiato"
    r = subprocess.run([sys.executable, str(factory / "tools/lint/check-version-coherence.py"), "--json",
                        "--root", str(factory)], capture_output=True, text=True)
    assert json.loads(r.stdout)["findings"] == []
    r = subprocess.run([sys.executable, str(factory / "tools/lint/run-deterministic.py"), "--root", str(factory),
                        "--strict", "--solo", GRUPPI], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]


def test_installa_dal_repo(tmp_path):
    f = tmp_path / "factory"
    r = subprocess.run([sys.executable, str(INST / "install.py"), "--target", str(f), "--name", "t",
                        "--topology", "full-stack-agents", "--today", OGGI], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "  be: agent" in (f / "factory.config.yaml").read_text()
    _verifica(f)


def test_installa_dallo_zip(tmp_path):
    r = subprocess.run([sys.executable, str(INST / "build-dist.py"), "--output", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "Duplicate name" not in r.stderr
    zip_path = next(tmp_path.glob("factory-installer-v*.zip"))
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp_path / "x")
    setup = next((tmp_path / "x").glob("*/setup.py"))
    f = tmp_path / "factory"
    r = subprocess.run([sys.executable, str(setup), "--target", str(f), "--adapters", "claude", "cursor",
                        "--today", OGGI], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (f / ".cursor").is_dir()
    _verifica(f)


def test_starter_config_alla_versione_corrente():
    starter = (ROOT / "factory.starter.config.yaml").read_text(encoding="utf-8")
    assert f'pattern_version: "{_versione_sorgente()}"' in starter
