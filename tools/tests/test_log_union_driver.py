"""Merge driver `factory-log-union` per wiki/log.md e sua registrazione da install_factory_hooks.py."""
from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[2]
TOOLS = RADICE / "tools"
PY = sys.executable


def _carica(nome: str, percorso: Path):
    spec = importlib.util.spec_from_file_location(nome, percorso)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(percorso.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(percorso.parent))
    return mod


installer = _carica("install_factory_hooks_t", TOOLS / "vcs" / "install_factory_hooks.py")
log_driver = _carica("log_union_driver_t", TOOLS / "wiki" / "log_union_driver.py")


@pytest.fixture(autouse=True)
def git_isolato(monkeypatch, tmp_path_factory):
    vuoto = tmp_path_factory.mktemp("gitcfg") / "config"
    vuoto.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(vuoto))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(vuoto))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(f"git {' '.join(args)}: {r.stdout}{r.stderr}")
    return r


TESTA_LOG = (
    "---\ntype: wiki-log\nappend_only: true\n---\n\n# Wiki Log\n\n"
    "---\ndate: 2026-11-01\ntype: develop\ncontext: voce di partenza\n---\n"
)


def voce(data: str, contesto: str) -> str:
    return f"\n---\ndate: {data}\ntype: develop\ncontext: {contesto}\n---\n"


def crea_repo(tmp_path: Path, con_driver: bool) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "checkout", "-q", "-b", "main")
    git(repo, "config", "user.email", "prova@example.invalid")
    git(repo, "config", "user.name", "prova")
    (repo / ".gitattributes").write_text("wiki/log.md merge=factory-log-union\n")
    (repo / "wiki").mkdir()
    (repo / "wiki" / "log.md").write_text(TESTA_LOG)
    (repo / "tools" / "wiki").mkdir(parents=True)
    shutil.copy2(TOOLS / "wiki" / "log_union_driver.py", repo / "tools" / "wiki")
    git(repo, "add", "--", ".")
    git(repo, "commit", "-q", "-m", "base")
    if con_driver:
        assert set(installer.ensure_merge_drivers(repo).values()) == {"installed"}
    return repo


def ramo_log(repo: Path, nome: str, data: str, contesto: str) -> None:
    git(repo, "checkout", "-q", "-b", nome, "main")
    with open(repo / "wiki" / "log.md", "a") as fh:
        fh.write(voce(data, contesto))
    git(repo, "commit", "-q", "-am", f"log {nome}")


def conflitti(repo: Path):
    return git(repo, "diff", "--name-only", "--diff-filter=U").stdout.split()


def test_gitattributes_dichiara_il_driver_del_log():
    righe = [l.split() for l in (RADICE / ".gitattributes").read_text().splitlines() if "merge=" in l]
    assert ["wiki/log.md", "merge=factory-log-union"] in righe


def test_merge_log_con_driver_senza_conflitti(tmp_path):
    repo = crea_repo(tmp_path, con_driver=True)
    ramo_log(repo, "ramo-a", "2026-11-09", "voce ramo A")
    ramo_log(repo, "ramo-b", "2026-11-09", "voce ramo B")
    git(repo, "checkout", "-q", "ramo-a")
    r = git(repo, "merge", "-q", "ramo-b", "-m", "merge log", check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    assert conflitti(repo) == []
    log = (repo / "wiki" / "log.md").read_text()
    assert "<<<<<<<" not in log and ">>>>>>>" not in log
    assert log.count("voce ramo A") == 1 and log.count("voce ramo B") == 1
    assert log.count("voce di partenza") == 1
    assert log.index("voce ramo A") < log.index("voce ramo B")
    assert len(re.findall(r"^---\ndate: [^\n]*\ntype: develop\ncontext: [^\n]*\n---\n", log, re.M)) == 3


def test_merge_log_senza_driver_conflitto_come_prima(tmp_path):
    repo = crea_repo(tmp_path, con_driver=False)
    ramo_log(repo, "ramo-a", "2026-11-09", "voce ramo A")
    ramo_log(repo, "ramo-b", "2026-11-09", "voce ramo B")
    git(repo, "checkout", "-q", "ramo-a")
    r = git(repo, "merge", "-q", "ramo-b", "-m", "merge log", check=False)
    assert r.returncode != 0
    assert conflitti(repo) == ["wiki/log.md"]
    git(repo, "merge", "--abort")


def test_merge_log_voci_simili_restano_blocchi_separati(tmp_path):
    repo = crea_repo(tmp_path, con_driver=True)
    for nome, sid in (("ramo-a", "aaaa1111"), ("ramo-b", "bbbb2222")):
        git(repo, "checkout", "-q", "-b", nome, "main")
        with open(repo / "wiki" / "log.md", "a") as fh:
            fh.write(f"\n---\ndate: 2026-11-09\ntype: session-start\nsession_id: {sid}\nscope: all\n"
                     f"context: \"chat {sid}\"\n---\n")
        git(repo, "commit", "-q", "-am", nome)
    git(repo, "checkout", "-q", "ramo-a")
    git(repo, "merge", "-q", "ramo-b", "-m", "merge log")
    log = (repo / "wiki" / "log.md").read_text()
    assert log.count("session_id: ") == 2 and log.count("\ncontext: ") == 3
    assert len(re.findall(r"^---\ndate: [^\n]*\ntype: session-start\nsession_id: \w+\nscope: all\n"
                          r"context: [^\n]*\n---\n", log, re.M)) == 2


def test_log_union_driver_estende_la_base_con_le_code_dei_due_lati():
    base = b"testa\nbase\n"
    assert log_driver.merge(base, base + b"A\n", base + b"B\n") == base + b"A\nB\n"
    assert log_driver.merge(base, base, base + b"B\n") == base + b"B\n"
    assert log_driver.merge(base, base + b"A\n", base) == base + b"A\n"
    assert log_driver.merge(base, base + b"X\n", base + b"X\n") == base + b"X\n"


def test_log_union_driver_senza_base_prefisso_ricade_su_merge_file_union(tmp_path):
    paths = []
    for nome, testo in (("base", "t1\nbase\n"), ("ours", "T1\nbase\n"), ("theirs", "t1\nbase\nB\n")):
        p = tmp_path / nome
        p.write_text(testo)
        paths.append(str(p))
    base, ours, theirs = paths
    assert log_driver.merge(Path(base).read_bytes(), Path(ours).read_bytes(),
                            Path(theirs).read_bytes()) is None
    assert log_driver.driver(base, ours, theirs) == 0
    fuso = Path(ours).read_text()
    assert "<<<<<<<" not in fuso and "T1" in fuso and "B\n" in fuso


def test_log_union_driver_senza_argomenti_esce_con_2():
    assert log_driver.main([]) == 2


# --- registrazione del driver -------------------------------------------------

def _config_locale(repo: Path) -> str:
    return git(repo, "config", "--local", "--list").stdout


def test_installer_registra_e_resta_idempotente(tmp_path):
    repo = crea_repo(tmp_path, con_driver=False)
    assert "merge.factory" not in _config_locale(repo)
    assert set(installer.ensure_merge_drivers(repo).values()) == {"installed"}
    dopo1 = _config_locale(repo)
    assert "merge.factory-log-union.driver=python3 tools/wiki/log_union_driver.py %O %A %B" in dopo1
    assert set(installer.ensure_merge_drivers(repo).values()) == {"ok"}
    assert set(installer.ensure_merge_drivers(repo, overwrite=True).values()) == {"ok"}
    assert _config_locale(repo) == dopo1


def test_installer_non_sovrascrive_un_driver_diverso_senza_overwrite(tmp_path):
    repo = crea_repo(tmp_path, con_driver=False)
    git(repo, "config", "--local", "merge.factory-log-union.driver", "echo personalizzato")
    assert installer.ensure_merge_drivers(repo)["factory-log-union"] == "conflict"
    assert git(repo, "config", "--local", "--get",
               "merge.factory-log-union.driver").stdout.strip() == "echo personalizzato"
    assert installer.ensure_merge_drivers(repo, overwrite=True)["factory-log-union"] == "updated"
    assert "echo personalizzato" not in _config_locale(repo)


def test_installer_dry_run_non_scrive(tmp_path):
    repo = crea_repo(tmp_path, con_driver=False)
    prima = _config_locale(repo)
    assert set(installer.ensure_merge_drivers(repo, dry_run=True).values()) == {"installed"}
    assert _config_locale(repo) == prima


# --- cartella hook da worktree e opzione --only --------------------------------

def test_cartella_hook_da_worktree_e_quella_comune(tmp_path):
    repo = crea_repo(tmp_path, con_driver=False)
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "wt-b", str(wt))
    atteso = (repo / ".git" / "hooks").resolve()
    assert installer._factory_hooks_dir(wt).resolve() == atteso
    assert installer._factory_hooks_dir(repo).resolve() == atteso


def test_only_installa_un_solo_hook_senza_driver(tmp_path):
    repo = crea_repo(tmp_path, con_driver=False)
    r = subprocess.run([PY, str(TOOLS / "vcs" / "install_factory_hooks.py"),
                        "--root", str(repo), "--only", "post-merge"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    hooks = {p.name for p in (repo / ".git" / "hooks").iterdir() if not p.name.endswith(".sample")}
    assert hooks == {"post-merge"}
    assert "merge.factory" not in _config_locale(repo)
