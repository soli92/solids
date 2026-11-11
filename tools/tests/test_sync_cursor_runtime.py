"""sync-cursor-runtime.py — COPY / SKIP / CONFLICT / overwrite."""
from __future__ import annotations

import filecmp
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "tools/adapters/sync-cursor-runtime.py"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SYNC), *args],
        capture_output=True,
        text=True,
        cwd=cwd or ROOT,
    )


@pytest.fixture
def mini_factory(tmp_path: Path) -> Path:
    f = tmp_path / "wise"
    f.mkdir()
    (f / "factory.config.yaml").write_text(
        'pattern_version: "2.32"\nadapters:\n  - name: claude\n    folder: .claude\n    maturity: full\n',
        encoding="utf-8",
    )
    return f


def test_copies_missing_cursor_files(mini_factory: Path):
    r = _run(str(mini_factory), "--meta-source", str(ROOT), "--ensure-adapter")
    assert r.returncode == 0, r.stderr + r.stdout
    assert (mini_factory / ".cursor/commands/run.md").is_file()
    cfg = (mini_factory / "factory.config.yaml").read_text()
    assert "name: cursor" in cfg


def test_conflict_on_customized_file(mini_factory: Path):
    _run(str(mini_factory), "--meta-source", str(ROOT))
    custom = mini_factory / ".cursor/commands/run.md"
    custom.write_text("# customized\n", encoding="utf-8")
    r = _run(str(mini_factory), "--meta-source", str(ROOT))
    assert r.returncode == 2
    assert "CONFLICT" in r.stdout
    assert custom.read_text(encoding="utf-8").startswith("# customized")


def test_overwrite_changed_refreshes(mini_factory: Path):
    _run(str(mini_factory), "--meta-source", str(ROOT))
    custom = mini_factory / ".cursor/commands/run.md"
    custom.write_text("# customized\n", encoding="utf-8")
    canon = ROOT / "adapters/cursor/templates/commands/run.md"
    r = _run(str(mini_factory), "--meta-source", str(ROOT), "--overwrite-changed")
    assert r.returncode == 0, r.stderr
    assert filecmp.cmp(custom, canon, shallow=False)
