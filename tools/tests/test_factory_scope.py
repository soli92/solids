"""tools/factory_scope.py: perimetro unico di installer e upgrade.

Prima l'installer aveva una lista propria (ferma alla v2.21) e copiava `/factory-bootstrap`,
`/factory-upgrade`, `/release` e il CLAUDE.md del master, senza CAPABILITIES.md (fonte di
`/help`), `visual/` e `schemas/`. Questi test fissano le regole comuni.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import factory_scope as fs  # noqa: E402


@pytest.mark.parametrize("rel", [
    ".claude/commands/factory-bootstrap.md",
    ".claude/commands/factory-upgrade.md",
    ".claude/commands/release.md",
    ".claude/commands/references/factory-bootstrap/versions-recent.md",
    ".claude/agents/pattern-b-testbed.md",
    "tools/factory-upgrade-apply.py",
    "tools/tests/test_factory_upgrade_version.py",
    "tools/tests/test_installer.py",
])
def test_unita_del_meta_framework(rel):
    assert fs.is_meta_only(rel)


@pytest.mark.parametrize("rel", [
    ".claude/commands/release-artifact.md",
    ".claude/commands/help.md",
    "tools/factory_scope.py",
    "tools/tests/test_factory_scope.py",
])
def test_unita_della_derivata(rel):
    assert not fs.is_meta_only(rel)


def test_stacca_solo_i_link_locali_pendenti():
    testo = "[a](esiste.md) [b](manca.md#x) [c](https://x.y) [d](#ancora) [e](manca/)"
    out, n = fs.stacca_link_pendenti(testo, lambda p: p == "esiste.md")
    assert out == "[a](esiste.md) b [c](https://x.y) [d](#ancora) e"
    assert n == 2


def test_capabilities_per_derivata():
    master = "\n".join([
        "# Capability",
        "",
        "| Capability | Comando | Doc |",
        "|---|---|---|",
        "| Release gate | `/release` | — |",
        "| Release artefatti | `/release-artifact <t>` | [r](.claude/commands/release-artifact.md) |",
        "| Bootstrap | `/factory-bootstrap [args]` | [q](wiki/getting-started/q.md) |",
        "| Quick start | leggi `QUICKSTART.md` | [QUICKSTART.md](QUICKSTART.md) |",
        "| Help | `/help` | [runbook](wiki/runbooks/help.md) |",
    ])
    out = fs.capabilities_per_derivata(master, lambda p: p.startswith(".claude/"))
    assert "`/release` |" not in out
    assert "/factory-bootstrap" not in out and "QUICKSTART" not in out
    assert "| Release artefatti | `/release-artifact <t>` | [r](.claude/commands/release-artifact.md) |" in out
    assert "| Help | `/help` | runbook |" in out          # link pendente reso come testo
    assert out.startswith("# Capability\n\n> Copia per factory derivata")


def test_capabilities_del_master_senza_link_pendenti_in_derivata(tmp_path):
    """Sul CAPABILITIES.md reale: nessun link verso file che una factory vuota non ha."""
    master = (TOOLS.parent / "CAPABILITIES.md")
    if not master.is_file():
        pytest.skip("CAPABILITIES.md esiste solo nel meta-framework o in una derivata che l'ha")
    out = fs.capabilities_per_derivata(master.read_text(encoding="utf-8"), fs.esiste_in(tmp_path))
    _, residui = fs.stacca_link_pendenti(out, fs.esiste_in(tmp_path))
    assert residui == 0


def _upgrade_module():
    p = TOOLS / "factory-upgrade-apply.py"
    if not p.is_file():
        pytest.skip("factory-upgrade-apply.py esiste solo nel meta-framework")
    pytest.importorskip("yaml")
    spec = importlib.util.spec_from_file_location("fua_scope", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _coppia(tmp: Path) -> tuple[Path, Path]:
    m = tmp / "master"
    (m / "tools").mkdir(parents=True)
    (m / "factory.config.yaml").write_text('pattern_version: "2.45"\n')
    (m / "PATTERN.md").write_text("# P\n\n## §0 — x\nriga\n")
    (m / "CAPABILITIES.md").write_text("# Cap\n\n| a | `/release` |\n| b | `/help` | [w](wiki/x.md) |\n")
    _git(m, "init", "-q")
    _git(m, "add", "-A")
    _git(m, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "m")
    t = tmp / "target"
    t.mkdir()
    (t / "factory.config.yaml").write_text('pattern_version: "2.45"\n')
    (t / "PATTERN.md").write_text("# P\n\n## §0 — x\nriga\n")
    return m, t


def test_upgrade_aggiunge_capabilities_se_manca(tmp_path):
    fua = _upgrade_module()
    m, t = _coppia(tmp_path)
    piano = fua.upgrade_factory(t, m, dry_run=True)
    assert "CAPABILITIES.md" in piano["copy_paths"] and not (t / "CAPABILITIES.md").exists()
    fua.upgrade_factory(t, m, dry_run=False)
    testo = (t / "CAPABILITIES.md").read_text()
    assert "`/release`" not in testo and "| b | `/help` | w |" in testo


def test_upgrade_non_tocca_capabilities_della_derivata(tmp_path):
    fua = _upgrade_module()
    m, t = _coppia(tmp_path)
    (t / "CAPABILITIES.md").write_text("# mia\n")
    st = fua.upgrade_factory(t, m, dry_run=False)
    assert (t / "CAPABILITIES.md").read_text() == "# mia\n"
    assert "CAPABILITIES.md" not in st.get("copy_paths", [])


def _meta_only_in_target(m: Path, t: Path) -> None:
    """Una derivata nata dall'installer fino a v2.46.1: unita' del master copiate, una modificata."""
    for rel, testo in ((".claude/commands/release.md", "# release\n"),
                       ("tools/tests/test_installer.py", "x = 1\n"),
                       (".claude/commands/factory-upgrade.md", "# upgrade\n")):
        for root in (m, t):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(testo)
    (t / ".claude/commands/factory-upgrade.md").write_text("# upgrade, adattato dalla factory\n")


def test_upgrade_riporta_meta_only_senza_toccarle(tmp_path):
    fua = _upgrade_module()
    m, t = _coppia(tmp_path)
    _meta_only_in_target(m, t)
    st = fua.upgrade_factory(t, m, dry_run=False)
    assert st["meta_only_identical"] == [".claude/commands/release.md", "tools/tests/test_installer.py"]
    assert st["meta_only_modified"] == [".claude/commands/factory-upgrade.md"]
    assert st["meta_only_removed"] == [] and (t / ".claude/commands/release.md").is_file()


def test_prune_meta_only_rimuove_solo_le_identiche_con_backup(tmp_path):
    fua = _upgrade_module()
    m, t = _coppia(tmp_path)
    _meta_only_in_target(m, t)
    piano = fua.upgrade_factory(t, m, dry_run=True, prune_meta_only=True)
    assert len(piano["meta_only_removed"]) == 2 and (t / "tools/tests/test_installer.py").is_file()
    st = fua.upgrade_factory(t, m, dry_run=False, prune_meta_only=True)
    assert not (t / ".claude/commands/release.md").exists()
    assert not (t / "tools/tests").exists()  # cartella rimasta vuota: tolta
    assert (t / ".claude/commands/factory-upgrade.md").read_text().startswith("# upgrade, adattato")
    assert (Path(st["backup_path"]) / "meta-only/.claude/commands/release.md").read_text() == "# release\n"


def test_upgrade_aggiunge_gitattributes_se_manca(tmp_path):
    fua = _upgrade_module()
    m, t = _coppia(tmp_path)
    (m / ".gitattributes").write_text("wiki/log.md merge=factory-log-union\n")
    assert ".gitattributes" in fua.upgrade_factory(t, m, dry_run=True)["copy_paths"]
    fua.upgrade_factory(t, m, dry_run=False)
    assert (t / ".gitattributes").read_text() == "wiki/log.md merge=factory-log-union\n"
    (t / ".gitattributes").write_text("# mio\n")
    st = fua.upgrade_factory(t, m, dry_run=False)
    assert (t / ".gitattributes").read_text() == "# mio\n" and ".gitattributes" not in st["copy_paths"]


def test_upgrade_idempotente_sui_file_singoli(tmp_path):
    """I file singoli di SYNC_PATHS (analytics/*.yaml) gia' identici non sono COPY al giro dopo."""
    fua = _upgrade_module()
    m, t = _coppia(tmp_path)
    (m / "analytics").mkdir()
    (m / "analytics/pricing.yaml").write_text("x: 1\n")
    assert "analytics/pricing.yaml" in fua.upgrade_factory(t, m, dry_run=False)["copy_paths"]
    st = fua.upgrade_factory(t, m, dry_run=True)
    assert st["copy"] == 0 and st["conflict"] == 0, st["copy_paths"]
