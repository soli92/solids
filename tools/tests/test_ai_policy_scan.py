"""
Test della guardia di scope e della risoluzione dei path di tools/vcs/ai-policy-scan.py.

La fixture riproduce la forma di una factory derivata: il repo cliente e' un repo git
annidato dentro la cartella della factory (code_repos/<nome>), come un submodule.
Prima di questa suite la guardia confrontava i path, e rifiutava il repo cliente
perche' «sottodirectory della factory» — cioe' il caso d'uso principale del layer-2.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "tools" / "vcs" / "ai-policy-scan.py"


def _git(*args, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _make_repo(path: Path, message: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "t@example.com", cwd=path)
    _git("config", "user.name", "t", cwd=path)
    (path / "f.txt").write_text(message)
    _git("add", ".", cwd=path)
    _git("commit", "-q", "-m", message, cwd=path)
    return path


def _scan(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        cwd=str(cwd), capture_output=True, text=True,
    )


@pytest.fixture
def derived_factory(tmp_path):
    """Factory con un repo cliente annidato e una sottocartella non-repo."""
    factory = _make_repo(tmp_path / "derived-factory", "chore: init factory")
    _make_repo(factory / "code_repos" / "client", "feat: dettaglio (XX-TSK-123)")
    (factory / "wiki").mkdir()
    return factory


def test_nested_client_repo_is_scanned_not_rejected(derived_factory):
    r = _scan("--root", str(derived_factory), "--repos=code_repos/client", cwd=derived_factory)
    assert "RIFIUTO" not in r.stderr
    assert "XX-TSK-123" in r.stdout


def test_relative_paths_resolve_against_root_not_script_factory(derived_factory):
    """Lanciato dalla madre con --root, il path relativo e' della derivata."""
    r = _scan("--root", str(derived_factory), "--repos=code_repos/client", cwd=_REPO_ROOT)
    assert str(derived_factory / "code_repos" / "client") in r.stdout or "code_repos/client" in r.stdout
    assert "repo_not_found" not in r.stdout


def test_root_factory_itself_is_rejected(derived_factory):
    r = _scan("--root", str(derived_factory), "--repos=.", cwd=derived_factory)
    assert "RIFIUTO" in r.stderr
    assert r.returncode == 0


def test_plain_subdirectory_of_factory_is_rejected(derived_factory):
    """wiki/ non e' un repo: appartiene al repo della factory."""
    r = _scan("--root", str(derived_factory), "--repos=wiki", cwd=derived_factory)
    assert "RIFIUTO" in r.stderr


def test_script_factory_is_rejected_even_with_other_root(derived_factory):
    r = _scan("--root", str(derived_factory), f"--repos={_REPO_ROOT}", cwd=derived_factory)
    assert "RIFIUTO" in r.stderr


def test_missing_path_is_unscanned_not_rejected(derived_factory):
    r = _scan("--root", str(derived_factory), "--repos=code_repos/assente", cwd=derived_factory)
    assert "RIFIUTO" not in r.stderr
    assert "repo_not_found" in r.stdout


def test_guardia_fallisce_chiusa_se_git_non_risponde(tmp_path, monkeypatch):
    """Sotto carico `git rev-parse` andava in timeout (10 s), il toplevel risultava None e la
    factory non veniva riconosciuta: la guardia falliva APERTA. Ora un git che non risponde
    rifiuta il path."""
    import importlib.util
    import subprocess
    from pathlib import Path as _P

    spec = importlib.util.spec_from_file_location(
        "ai_policy_scan_mod", _P(__file__).resolve().parents[2] / "tools" / "vcs" / "ai-policy-scan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cliente = tmp_path / "cliente"
    cliente.mkdir()
    factory = tmp_path / "factory"
    factory.mkdir()

    def lento(*a, **k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=60)

    monkeypatch.setattr(mod.subprocess, "run", lento)
    assert mod._is_factory_root(cliente, [factory]) is True
    # il path identico alla factory si rifiuta senza nemmeno chiamare git
    assert mod._is_factory_root(factory, [factory]) is True


# ---------------------------------------------------------------------------
# Lancio da un worktree della factory: i submodule del worktree sono cartelle vuote,
# git li' risale al repo della factory. Lo scan deve leggere i repo cliente del
# checkout principale, non i commit della factory.
# ---------------------------------------------------------------------------

_SCRIPTS = ("tools/vcs/ai-policy-scan.py",)


@pytest.fixture
def factory_with_worktree(tmp_path):
    import shutil

    main = tmp_path / "factory"
    main.mkdir()
    for rel in _SCRIPTS + ("tools/vcs/ai_policy.py",):
        (main / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_REPO_ROOT / rel, main / rel)
    shutil.copytree(_REPO_ROOT / "tools" / "vcs" / "smlib", main / "tools" / "vcs" / "smlib",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (main / "factory.config.yaml").write_text(
        "ai_policy_check:\n  enabled: true\n  scope:\n    - path: code_repos/client\n",
        encoding="utf-8")
    (main / ".gitignore").write_text("code_repos/\n__pycache__/\n", encoding="utf-8")
    _git("init", "-q", cwd=main)
    _git("config", "user.email", "t@example.com", cwd=main)
    _git("config", "user.name", "t", cwd=main)
    _git("add", ".", cwd=main)
    _git("commit", "-q", "-m", "chore: init factory (XX-TSK-999)", cwd=main)
    _make_repo(main / "code_repos" / "client", "feat: dettaglio (XX-TSK-123)")
    wt = tmp_path / "wt"
    _git("worktree", "add", "-q", str(wt), cwd=main)
    (wt / "code_repos" / "client").mkdir(parents=True)  # submodule non inizializzato
    return main, wt


@pytest.mark.parametrize("script", _SCRIPTS)
def test_worktree_scans_client_repo_of_main_checkout(factory_with_worktree, script):
    _main, wt = factory_with_worktree
    r = subprocess.run([sys.executable, str(wt / script)], cwd=str(wt),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0
    assert "XX-TSK-123" in r.stdout          # commit del repo cliente
    assert "XX-TSK-999" not in r.stdout      # mai i commit della factory
    assert "RIFIUTO" not in r.stderr


def test_uninitialized_submodule_dir_is_unscanned_not_factory(factory_with_worktree):
    """Cartella vuota dentro il worktree passata esplicitamente: non diventa la factory."""
    import importlib.util

    _main, wt = factory_with_worktree
    spec = importlib.util.spec_from_file_location(
        "ai_policy_scan_vcs", wt / "tools" / "vcs" / "ai-policy-scan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = mod.scan_repo(wt / "code_repos" / "client")
    assert res["status"] == "unscanned"
    assert res["reason"].startswith("repo_not_initialized")
