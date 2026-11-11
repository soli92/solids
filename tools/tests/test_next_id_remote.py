"""next-id.py: gli ID presenti su origin/main entrano nel calcolo; offline si dichiara.

Ogni test crea in una cartella temporanea un "remoto" bare e un clone, copia nel clone lo
script e lo lancia come processo: nessuna rete, nessun accesso al repo reale.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "kanban" / "next-id.py"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def git(cwd, *args):
    env = dict(os.environ, **GIT_ENV)
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=env)


def touch(repo, rel):
    p = repo / "management" / "kanban" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\n---\n")


def commit(repo, msg="c"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


@pytest.fixture
def env(tmp_path):
    """(locale, altro): `altro` pubblica su origin/main, `locale` non ha ancora scaricato."""
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    altro = tmp_path / "altro"
    git(tmp_path, "clone", "-q", str(bare), str(altro))
    git(altro, "switch", "-q", "-c", "main")
    touch(altro, "EP-001/US-001/TSK-010.md")
    for pre in ("PS", "UP", "PC", "PNS", "XY"):
        touch(altro, f"{pre}-EP-001/{pre}-US-001/{pre}-TSK-010.md")
    commit(altro)
    git(altro, "push", "-q", "origin", "main")
    locale = tmp_path / "locale"
    git(tmp_path, "clone", "-q", str(bare), str(locale))
    (locale / "tools" / "kanban").mkdir(parents=True)
    shutil.copy(SCRIPT, locale / "tools" / "kanban" / "next-id.py")
    return locale, altro


def run(repo, *args):
    r = subprocess.run([sys.executable, str(repo / "tools" / "kanban" / "next-id.py"), *args],
                       cwd=repo, capture_output=True, text=True)
    return r


def publish(altro, rel):
    touch(altro, rel)
    commit(altro)
    git(altro, "push", "-q", "origin", "main")


def test_id_solo_remoto_non_viene_restituito(env):
    locale, altro = env
    publish(altro, "EP-001/US-001/TSK-025.md")
    assert not (locale / "management/kanban/EP-001/US-001/TSK-025.md").exists()
    r = run(locale, "tsk")
    assert r.returncode == 0
    assert r.stdout.strip() == "TSK-026"
    assert "next-id-remote" not in r.stderr  # fetch riuscito: stderr invariato


def test_id_solo_locale(env):
    locale, _ = env
    touch(locale, "EP-001/US-001/TSK-040.md")  # non committato, non pubblicato
    r = run(locale, "tsk", "2")
    assert r.stdout.split() == ["TSK-041", "TSK-042"]


def test_us_ed_ep_remoti(env):
    locale, altro = env
    touch(altro, "EP-007/EP-007.md")
    touch(altro, "EP-007/US-033/US-033.md")
    publish(altro, "EP-007/US-033/TSK-011.md")
    assert run(locale, "us").stdout.strip() == "US-034"
    assert run(locale, "ep").stdout.strip() == "EP-008"


@pytest.mark.parametrize("pre", ["PS", "UP", "PC", "PNS", "XY"])
def test_prefissi_namespace(env, pre):
    locale, altro = env
    publish(altro, f"{pre}-EP-001/{pre}-US-001/{pre}-TSK-030.md")
    touch(locale, f"{pre}-EP-001/{pre}-US-001/{pre}-TSK-005.md")
    r = run(locale, "tsk", "--namespace", pre)
    assert r.returncode == 0
    assert r.stdout.strip() == f"{pre}-TSK-031"


def test_namespace_non_mescola_prefissi(env):
    locale, altro = env
    publish(altro, "UP-EP-001/UP-US-001/UP-TSK-099.md")
    assert run(locale, "tsk", "--namespace", "XY").stdout.strip() == "XY-TSK-011"


def test_offline_dichiarato(env):
    locale, altro = env
    git(locale, "remote", "set-url", "origin", str(locale.parent / "inesistente.git"))
    # ref locale di origin/main ancora vecchio: l'ID del remoto non e' noto
    r = run(locale, "tsk")
    assert r.returncode == 0
    assert r.stdout.strip() == "TSK-011"
    assert "AVVISO" in r.stderr
    assert "# next-id-remote: stale" in r.stderr


def test_offline_senza_ref_remoto(tmp_path):
    repo = tmp_path / "solo"
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    (repo / "tools" / "kanban").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "tools" / "kanban" / "next-id.py")
    touch(repo, "EP-001/US-001/TSK-020.md")
    r = run(repo, "tsk")
    assert r.returncode == 0
    assert r.stdout.strip() == "TSK-021"
    assert "AVVISO" in r.stderr and "# next-id-remote: unavailable" in r.stderr


def test_strict_esce_non_zero_offline(tmp_path):
    repo = tmp_path / "solo"
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    (repo / "tools" / "kanban").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "tools" / "kanban" / "next-id.py")
    assert run(repo, "tsk", "--strict").returncode == 3


def test_json(env):
    locale, altro = env
    publish(altro, "EP-001/US-001/TSK-025.md")
    d = json.loads(run(locale, "tsk", "--json").stdout)
    assert d == {"ids": ["TSK-026"], "remote": "ok", "detail": ""}


def test_no_fetch_legge_ref_locale(env):
    locale, altro = env
    publish(altro, "EP-001/US-001/TSK-025.md")
    r = run(locale, "tsk", "--no-fetch")
    assert r.stdout.strip() == "TSK-011"  # ref non aggiornato: il fetch non e' stato fatto
    git(locale, "fetch", "-q", "origin", "main")
    assert run(locale, "tsk", "--no-fetch").stdout.strip() == "TSK-026"


def test_regressione_formato_ed_exit_code(env):
    locale, _ = env
    r = run(locale, "tsk", "3")
    assert r.returncode == 0
    assert r.stdout.split() == ["TSK-011", "TSK-012", "TSK-013"]
    assert run(locale, "xx").returncode == 2
    assert run(locale).stdout.strip() == "TSK-011"


def test_no_remote_non_legge_il_remoto(env):
    locale, altro = env
    publish(altro, "EP-001/US-001/TSK-025.md")
    r = run(locale, "tsk", "--no-remote")
    assert r.returncode == 0 and r.stdout.strip() == "TSK-011"
    assert r.stderr == ""
    d = json.loads(run(locale, "tsk", "--no-remote", "--json", "--strict").stdout)
    assert d["remote"] == "disabled"


def test_env_next_id_offline(env, monkeypatch):
    locale, altro = env
    publish(altro, "EP-001/US-001/TSK-025.md")
    monkeypatch.setenv("NEXT_ID_OFFLINE", "1")
    assert run(locale, "tsk").stdout.strip() == "TSK-011"
    monkeypatch.delenv("NEXT_ID_OFFLINE")
    assert run(locale, "tsk").stdout.strip() == "TSK-026"


def test_remote_e_branch_configurabili(env):
    locale, altro = env
    git(altro, "switch", "-q", "-c", "sviluppo")
    touch(altro, "EP-001/US-001/TSK-070.md")
    commit(altro)
    git(altro, "push", "-q", "origin", "sviluppo")
    git(locale, "remote", "add", "up", str(locale.parent / "remote.git"))
    assert run(locale, "tsk").stdout.strip() == "TSK-011"          # default origin/main
    r = run(locale, "tsk", "--remote", "up", "--branch", "sviluppo", "--json")
    d = json.loads(r.stdout)
    assert d == {"ids": ["TSK-071"], "remote": "ok", "detail": ""}


def test_fetch_fallito_resta_fail_open_con_remote_errato(env):
    locale, _ = env
    r = run(locale, "tsk", "--remote", "inesistente")
    assert r.returncode == 0 and r.stdout.strip() == "TSK-011"
    assert "# next-id-remote: unavailable" in r.stderr
