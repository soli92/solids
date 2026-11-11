"""
Test di tools/lint/check-version-coherence.py (Check 4am eseguibile).

La fixture `derived` riproduce una factory derivata reale: pattern_version annidata,
nessuno dei siti di framework, PATTERN.md presente. Prima del profilo, --root su una
derivata dava 5-7 version-site-missing e il segnale vero (PATTERN.md indietro) annegava.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "tools" / "lint" / "check-version-coherence.py"

_spec = importlib.util.spec_from_file_location("cvc", _SCRIPT)
cvc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cvc)


def _derived(tmp_path: Path, pattern_md: str = "2.42") -> Path:
    root = tmp_path / "derived"
    root.mkdir()
    (root / "factory.config.yaml").write_text(
        'project:\n  name: x\n  pattern_version: "2.42"\n'
    )
    (root / "PATTERN.md").write_text(f"# Pattern\n\nPattern version: **{pattern_md}**\n")
    return root


def test_meta_framework_declares_framework_profile():
    if not (_REPO_ROOT / "meta-prompts" / "README.md").is_file():
        pytest.skip("solo nel meta-framework: una derivata e' derived")
    assert cvc.read_profile(_REPO_ROOT) == "framework"


def test_profile_defaults_to_derived(tmp_path):
    assert cvc.read_profile(_derived(tmp_path)) == "derived"


def test_derived_missing_framework_sites_are_not_findings(tmp_path):
    root = _derived(tmp_path)
    findings, na = cvc.scan(root, "2.42", "derived")
    assert findings == []
    assert "meta-prompts/README.md" in na
    assert ".claude/commands/factory-bootstrap.md" in na


def test_derived_stale_pattern_md_is_still_a_finding(tmp_path):
    root = _derived(tmp_path, pattern_md="2.27")
    findings, _ = cvc.scan(root, "2.42", "derived")
    assert [f["file"] for f in findings] == ["PATTERN.md"]
    assert findings[0]["rule"] == "version-divergent"


def test_derived_present_and_divergent_framework_site_is_a_finding(tmp_path):
    root = _derived(tmp_path)
    cmd = root / ".claude" / "commands"
    cmd.mkdir(parents=True)
    (cmd / "factory-bootstrap.md").write_text("Dispatcher thin → v2.23 (corrente)\n")
    findings, na = cvc.scan(root, "2.42", "derived")
    assert [f["file"] for f in findings] == [".claude/commands/factory-bootstrap.md"]
    assert ".claude/commands/factory-bootstrap.md" not in na


def test_framework_profile_missing_site_is_a_finding(tmp_path):
    root = _derived(tmp_path)
    findings, na = cvc.scan(root, "2.42", "framework")
    assert na == []
    assert any(f["file"] == "meta-prompts/README.md" and f["rule"] == "version-site-missing"
               for f in findings)


def test_cli_declares_not_applicable_sites(tmp_path):
    root = _derived(tmp_path)
    r = subprocess.run([sys.executable, str(_SCRIPT), "--root", str(root)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "Profilo: derived" in r.stdout
    assert "Non applicabili al profilo derived" in r.stdout


def _split(root: Path, modules: dict[str, str]) -> None:
    """Indice con tabella §Moduli (US-319) + i moduli dati."""
    rows = "".join(f"| §x | y | [`{n}`]({n}) |\n" for n in modules)
    (root / "PATTERN.md").write_text(
        "# Pattern\n\nPattern version: **2.42**\n\n## Moduli — §12+\n\n" + rows
    )
    for n, body in modules.items():
        if body is not None:
            (root / n).write_text(body)


def test_split_pattern_complete_is_clean(tmp_path):
    root = _derived(tmp_path)
    _split(root, {"PATTERN-runtime.md": "> Modulo di PATTERN.md\n\n## §18 — x\n"})
    findings, _ = cvc.scan(root, "2.42", "derived")
    assert findings == []


def test_split_pattern_missing_module_is_a_finding(tmp_path):
    root = _derived(tmp_path)
    _split(root, {"PATTERN-runtime.md": "## §18\n", "PATTERN-governance.md": None})
    findings, _ = cvc.scan(root, "2.42", "derived")
    assert [(f["rule"], f["file"]) for f in findings] == [
        ("pattern-module-missing", "PATTERN-governance.md")
    ]


def test_split_pattern_module_with_divergent_version_is_a_finding(tmp_path):
    root = _derived(tmp_path)
    _split(root, {"PATTERN-runtime.md": "Pattern version: **2.27**\n"})
    findings, _ = cvc.scan(root, "2.42", "derived")
    assert [(f["rule"], f["file"]) for f in findings] == [("version-divergent", "PATTERN-runtime.md")]


def test_unindexed_pattern_file_is_not_a_module(tmp_path):
    """`PATTERN-historical.md` (archivio) non e' nella tabella: non e' contratto."""
    root = _derived(tmp_path)
    (root / "PATTERN-historical.md").write_text("Pattern version: **1.0**\n")
    findings, _ = cvc.scan(root, "2.42", "derived")
    assert findings == []


def test_siti_locali_della_factory(tmp_path):
    """version_sites_locali.py: un sito nuovo e un sito optional del master reso obbligatorio."""
    root = _derived(tmp_path)
    (root / "tools" / "lint").mkdir(parents=True)
    (root / "tools" / "lint" / "version_sites_locali.py").write_text(
        "SITES = [\n"
        "    ('QUICKSTART.md', 'riga vX.Y', r'Quickstart v([0-9]+\\.[0-9]+)', 'all'),\n"
        "    ('CAPABILITIES.md', 'link guida', r'factory-guide-v([0-9]+\\.[0-9]+)\\.html', 'all'),\n"
        "]\n")
    (root / "QUICKSTART.md").write_text("Quickstart v2.40\n")
    findings, _ = cvc.scan(root, "2.42", "derived")
    per_file = {f["file"]: f["rule"] for f in findings}
    assert per_file == {"QUICKSTART.md": "version-divergent", "CAPABILITIES.md": "version-site-missing"}
    assert sum(1 for x in cvc.sites(root) if x[0] == "CAPABILITIES.md") == 1  # sostituito, non duplicato


def test_versione_nel_nome_di_un_file(tmp_path):
    root = _derived(tmp_path)
    (root / "tools" / "lint").mkdir(parents=True)
    (root / "tools" / "lint" / "version_sites_locali.py").write_text(
        "GLOBS = [('guides/guida-v*.html', 'nome della guida', r'guida-v([0-9]+\\.[0-9]+)\\.html', True)]\n")
    findings, _ = cvc.scan(root, "2.42", "derived")
    assert [f["rule"] for f in findings] == ["version-site-missing"]
    (root / "guides").mkdir()
    (root / "guides" / "guida-v2.40.html").write_text("")
    findings, _ = cvc.scan(root, "2.42", "derived")
    assert [(f["rule"], f["file"]) for f in findings] == [("version-divergent", "guides/guida-v2.40.html")]


def test_versione_corrente_chiamata_candidate_e_un_finding(tmp_path):
    """EP-080 US-350: il dispatcher dichiarava v2.44 corrente alla riga 14 e «candidate» alla 5."""
    root = _derived(tmp_path)
    cmd = root / ".claude" / "commands"
    cmd.mkdir(parents=True)
    (cmd / "factory-bootstrap.md").write_text(
        "> **v2.42 candidate** (EP-x): non e' ancora la versione corrente.\n\n"
        "- Dispatcher thin → v2.42 (corrente)\n"
        "- v2.41 candidate, storia\n"
    )
    findings, _ = cvc.scan(root, "2.42", "derived")
    assert [(f["rule"], f["file"]) for f in findings] == [
        ("version-stale-candidate", ".claude/commands/factory-bootstrap.md:1")
    ]


def test_sprint_md_candidate_storico_non_e_un_finding(tmp_path):
    root = _derived(tmp_path)
    kb = root / "management" / "kanban"
    kb.mkdir(parents=True)
    (kb / "sprint.md").write_text(
        '---\npattern_version: "2.42"\n---\n## Sprint 9 — EP-1 (v2.42-candidate)\n'
    )
    findings, _ = cvc.scan(root, "2.42", "derived")
    assert findings == []
