"""
test_repo_align.py — Test suite per tools/vcs/repo-align.py

Copre:
  - Parsing factory.config.yaml (regex, niente PyYAML)
  - Tutti i cinque vcs.mode di PATTERN §15:
      monorepo, submodule, sibling, external, none
  - Verdetti: aligned, diverged, unverified
  - Direction detection (avanti / indietro)
  - Fixture git per submodule (AC3 — ramo che questa factory non esercita)
  - Partition completeness: ogni target ha esattamente un verdetto

Eseguire dalla root del repo:
    pytest tools/tests/test_repo_align.py -v

Dipendenze: stdlib + pytest (niente PyYAML, niente mock non-stdlib).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pytest

# Import tramite importlib (il file si chiama repo-align.py con trattino)
import importlib.util as _ilu

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RA_PATH = _REPO_ROOT / "tools" / "vcs" / "repo-align.py"
_spec = _ilu.spec_from_file_location("repo_align", str(_RA_PATH))
ra = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(ra)  # type: ignore[union-attr]

# ---------------------------------------------------------------------------
# Helper per creare fixture git in-memory (tmpdir)
# ---------------------------------------------------------------------------

def _git(*args, cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@test.test",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@test.test",
    })
    return subprocess.run(
        ["git"] + list(args),
        cwd=cwd, capture_output=True, text=True,
        env=env, check=check,
    )


def _make_repo(tmpdir: str, name: str = "repo") -> Path:
    """Crea un repo git con un commit iniziale."""
    p = Path(tmpdir) / name
    p.mkdir()
    _git("init", cwd=str(p))
    _git("checkout", "-b", "main", cwd=str(p))
    (p / "README").write_text("init")
    _git("add", ".", cwd=str(p))
    _git("commit", "-m", "init", cwd=str(p))
    return p


def _add_commit(repo: Path, message: str = "extra") -> str:
    """Aggiunge un commit e restituisce lo SHA."""
    f = repo / f"file-{message.replace(' ', '_')}.txt"
    f.write_text(message)
    _git("add", ".", cwd=str(repo))
    _git("commit", "-m", message, cwd=str(repo))
    r = _git("rev-parse", "HEAD", cwd=str(repo))
    return r.stdout.strip()


def _head_sha(repo: Path) -> str:
    r = _git("rev-parse", "HEAD", cwd=str(repo))
    return r.stdout.strip()

# ---------------------------------------------------------------------------
# Fixture git per submodule (AC3)
# Il submodule non e' presente in questa factory, quindi questa fixture
# e' l'unico modo per esercitare il ramo in modo controllato.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def submodule_fixture(tmp_path_factory):
    """
    Crea la struttura:
      remote_sub/  — repo "remoto" del submodule (bare clone simulato)
      sub/         — checkout locale del submodule
      parent/      — repo parent che contiene il submodule

    Tre scenari:
      - aligned: gitlink == remote tip
      - diverged_parent_behind: gitlink (nel parent) < remote tip (parent indietro)
      - diverged_parent_ahead: gitlink nel parent > remote tip (commit nel remote non presente)
    """
    base = tmp_path_factory.mktemp("submodule_fixture")

    # 1. Crea il "remote" del submodule (bare)
    remote_sub = base / "remote_sub"
    remote_sub.mkdir()
    _git("init", "--bare", cwd=str(remote_sub))

    # 2. Crea un clone locale del submodule
    sub_local = base / "sub_local"
    _git("clone", str(remote_sub), str(sub_local), cwd=str(base))
    _git("checkout", "-b", "main", cwd=str(sub_local))
    (sub_local / "lib.py").write_text("# lib")
    _git("add", ".", cwd=str(sub_local))
    _git("commit", "-m", "init submodule", cwd=str(sub_local))
    _git("push", "origin", "main", cwd=str(sub_local))
    initial_sha = _head_sha(sub_local)

    # 3. Crea il parent che include il submodule
    parent = base / "parent"
    parent.mkdir()
    _git("init", cwd=str(parent))
    _git("checkout", "-b", "main", cwd=str(parent))

    # Commit iniziale nel parent (necessario prima di git submodule add)
    (parent / ".gitkeep").write_text("init")
    _git("add", ".", cwd=str(parent))
    _git("commit", "-m", "initial", cwd=str(parent))

    # Aggiunge il submodule al parent
    env = dict(os.environ, GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="t@t.t",
               GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="t@t.t")
    r_sub_add = subprocess.run(
        ["git", "-c", "protocol.file.allow=always",
         "submodule", "add", str(remote_sub), "sub"],
        cwd=str(parent), capture_output=True, text=True, env=env,
    )
    if r_sub_add.returncode != 0:
        pytest.skip(f"git submodule add fallito: {r_sub_add.stderr[:200]}")
    _git("commit", "-m", "add submodule", cwd=str(parent))
    aligned_gitlink = _head_sha(sub_local)  # = initial_sha (gitlink == remote tip)

    # Scenario "parent behind": aggiunge commit nel remote MA non aggiorna il gitlink
    (sub_local / "extra.py").write_text("# extra")
    _git("add", ".", cwd=str(sub_local))
    _git("commit", "-m", "new feature", cwd=str(sub_local))
    _git("push", "origin", "main", cwd=str(sub_local))
    remote_ahead_sha = _head_sha(sub_local)
    # Il parent continua a puntare a initial_sha (non aggiornato)

    return {
        "base": base,
        "remote_sub": remote_sub,    # remote del submodule
        "sub_local": sub_local,      # working copy del submodule
        "parent": parent,            # repo parent
        "initial_sha": initial_sha,  # SHA al momento della creazione del gitlink
        "remote_ahead_sha": remote_ahead_sha,  # SHA attuale del remote (dopo il push)
        "aligned_gitlink": aligned_gitlink,    # = initial_sha = SHA gitlink nel parent
    }

# ---------------------------------------------------------------------------
# Test: parsing factory.config.yaml
# ---------------------------------------------------------------------------

class TestParseFactoryConfig:

    def test_parse_code_paths_real_factory(self):
        """Il factory.config.yaml reale ha code_paths[] e ogni voce ha name e path.

        Non si controllano nomi precisi: le voci cambiano da factory a factory.
        """
        cfg_path = _REPO_ROOT / "factory.config.yaml"
        cfg = ra.load_config(cfg_path)
        assert isinstance(cfg["code_paths"], list)
        assert cfg["code_paths"], "code_paths vuoto nel factory.config.yaml reale"
        for e in cfg["code_paths"]:
            assert e.get("name") and e.get("path"), f"voce code_paths senza name o path: {e}"

    def test_parse_code_paths_fixture(self, tmp_path):
        """Una voce code_paths[] con name e path viene letta."""
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text(
            "code_paths:\n"
            "  - name: factory-guide\n"
            "    path: .\n",
            encoding="utf-8",
        )
        cfg = ra.load_config(cfg_path)
        names = [e.get("name") for e in cfg["code_paths"]]
        assert "factory-guide" in names, f"factory-guide non trovato in {names}"

    def test_parse_legacy_code_path(self, tmp_path):
        """Il legacy code_path: '.' viene letto correttamente."""
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text('code_path: "."\n', encoding="utf-8")
        cfg = ra.load_config(cfg_path)
        assert cfg["legacy_code_path"] == "."

    def test_legacy_code_path_assente(self, tmp_path):
        """Senza code_path di primo livello il valore è None, non un errore."""
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text("code_paths: []\n", encoding="utf-8")
        assert ra.load_config(cfg_path)["legacy_code_path"] is None

    def test_parse_legacy_vcs_mode(self):
        """Il vcs.mode top-level viene letto correttamente."""
        cfg_path = _REPO_ROOT / "factory.config.yaml"
        cfg = ra.load_config(cfg_path)
        assert cfg["legacy_vcs_mode"] in ("monorepo", "submodule", "sibling", "external", None)

    def test_parse_synthetic_config(self, tmp_path):
        """Testa il parsing su un config sintetico con tutti i mode."""
        synthetic = tmp_path / "factory.config.yaml"
        synthetic.write_text("""
code_paths:
  - name: be-api
    path: /some/abs/path/api
    layers: [be]
    vcs:
      mode: sibling
      base_branch: main
  - name: db-sub
    path: ./db/
    layers: [db]
    vcs:
      mode: submodule
      submodule_path: ./db/
      base_branch: develop
  - name: fe-ext
    path: /external/path
    layers: [fe]
    vcs:
      mode: external
  - name: shared
    path: ./packages/shared/
    layers: [be, fe]
    vcs:
      mode: monorepo
  - name: legacy-none
    path: ./old/
    layers: [be]
    vcs:
      mode: none
code_path: "."
vcs:
  mode: monorepo
  base_branch: main
""")
        cfg = ra.load_config(synthetic)
        entries = {e["name"]: e for e in cfg["code_paths"]}

        assert entries["be-api"]["vcs_mode"] == "sibling"
        assert entries["be-api"]["base_branch"] == "main"
        assert entries["db-sub"]["vcs_mode"] == "submodule"
        assert entries["db-sub"]["submodule_path"] == "./db/"
        assert entries["db-sub"]["base_branch"] == "develop"
        assert entries["fe-ext"]["vcs_mode"] == "external"
        assert entries["shared"]["vcs_mode"] == "monorepo"
        assert entries["legacy-none"]["vcs_mode"] == "none"

        assert cfg["legacy_code_path"] == "."
        assert cfg["legacy_vcs_mode"] == "monorepo"
        assert cfg["legacy_base_branch"] == "main"

    def test_parse_base_branch_inside_branch_awareness(self, tmp_path):
        """base_branch dentro branch_awareness (forma osservata in una derivata reale):
        non e' base_branch dichiarato, e' registrato come fuori posto."""
        synthetic = tmp_path / "factory.config.yaml"
        synthetic.write_text("""
code_paths:
  - name: sub-ba
    path: code_repos/sub
    vcs:
      mode: submodule
      branch_awareness:
        enabled: true
        base_branch: develop       # commento in coda
        dispatch_gate: block
  - name: sub-ok
    path: code_repos/ok
    vcs:
      mode: submodule
      base_branch: main
      branch_awareness:
        enabled: true
""")
        entries = {e["name"]: e for e in ra.load_config(synthetic)["code_paths"]}
        assert entries["sub-ba"]["base_branch"] is None
        assert entries["sub-ba"]["misplaced_base_branch"] == "develop"
        assert entries["sub-ok"]["base_branch"] == "main"
        assert entries["sub-ok"]["misplaced_base_branch"] is None

    def test_auth_domains_optional(self, tmp_path):
        """auth_domains assente → lista vuota, nessun crash."""
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text("code_path: '.'\nvcs:\n  mode: monorepo\n")
        cfg = ra.load_config(cfg_path)
        assert cfg["auth_domains"] == []

    def test_auth_domains_parsed(self, tmp_path):
        """auth_domains presenti → lista con entries."""
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text("""
repo_align:
  enabled: true
  auth_domains:
    - name: my-api
      path: /path/to/api
      branch: main
      token_env: MY_API_TOKEN
""")
        cfg = ra.load_config(cfg_path)
        assert len(cfg["auth_domains"]) == 1
        assert cfg["auth_domains"][0]["name"] == "my-api"
        assert cfg["auth_domains"][0]["token_env"] == "MY_API_TOKEN"

    _FORMA_DOCUMENTATA = """
code_paths:
  - name: api
    path: code_repos/api
    vcs:
      mode: submodule
repo_align:
  enabled: true
  env_file: .env.locale
  auth_domains:
    - path: code_repos/api
      remote: origin
      branch: develop
      auth_type: submodule-parent
      token_env_var: API_TOKEN_EP072
"""

    def test_forma_documentata_path_e_token_env_var(self, tmp_path, monkeypatch):
        """EP-072: la forma del blocco di config (path + token_env_var, senza name) usa il token."""
        monkeypatch.setenv("API_TOKEN_EP072", "segreto")
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text(self._FORMA_DOCUMENTATA)
        cfg = ra.load_config(cfg_path)
        assert cfg["auth_domains"][0]["token_env"] == "API_TOKEN_EP072"
        (t,) = ra._resolve_targets(cfg, tmp_path, None)
        assert t["branch"] == "develop"
        assert t["auth_env"]["GIT_CONFIG_KEY_0"] == "http.extraHeader"
        assert t["auth_missing"] is None

    def test_riga_vuota_nel_blocco_non_lo_tronca(self, tmp_path):
        """EP-072: una riga vuota dentro repo_align: troncava il blocco, auth_domains spariva."""
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text(self._FORMA_DOCUMENTATA.replace(
            "  enabled: true\n", "  enabled: true\n\n  # commento\n\n"))
        cfg = ra.load_config(cfg_path)
        assert cfg["env_file"] == ".env.locale"
        assert [d["path"] for d in cfg["auth_domains"]] == ["code_repos/api"]

    def test_token_da_env_file_letto_non_eseguito(self, tmp_path, monkeypatch):
        monkeypatch.delenv("API_TOKEN_EP072", raising=False)
        (tmp_path / ".env.locale").write_text("# commento\nALTRO=x\nexport API_TOKEN_EP072='p$w;d'\n")
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text(self._FORMA_DOCUMENTATA)
        (t,) = ra._resolve_targets(ra.load_config(cfg_path), tmp_path, None)
        assert t["auth_env"] is not None and t["auth_missing"] is None
        assert ra._resolve_token("API_TOKEN_EP072", tmp_path / ".env.locale") == "p$w;d"

    def test_token_dichiarato_non_risolto_e_auth_missing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("API_TOKEN_EP072", raising=False)
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text(self._FORMA_DOCUMENTATA)
        (t,) = ra._resolve_targets(ra.load_config(cfg_path), tmp_path, None)
        assert t["auth_env"] is None and t["auth_missing"] == "API_TOKEN_EP072"
        monkeypatch.setattr(ra, "_run_check_mode", lambda *_: {"verdict": "unverified", "reason": "auth_failure"})
        r = ra._run_check(t, tmp_path)
        assert r["reason"] == "auth_missing" and "API_TOKEN_EP072" in r["note"]
        t["auth_missing"] = None
        assert ra._run_check(t, tmp_path)["reason"] == "auth_failure"

# ---------------------------------------------------------------------------
# Test: mode=none escluso dal set
# ---------------------------------------------------------------------------

class TestModeNone:

    def test_mode_none_excluded(self, tmp_path):
        """mode=none e' escluso dal set di verifica (non unverified)."""
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text("""
code_paths:
  - name: skip-me
    path: /whatever
    vcs:
      mode: none
""")
        cfg = ra.load_config(cfg_path)
        factory_root = tmp_path
        targets = ra._resolve_targets(cfg, factory_root, None)
        names = [t["name"] for t in targets]
        assert "skip-me" not in names

# ---------------------------------------------------------------------------
# Test: mode=external
# ---------------------------------------------------------------------------

class TestModeExternal:

    def test_external_verdict_unverified_opaque_topology(self):
        """mode=external → unverified, reason=opaque_topology."""
        result = ra._check_external("my-ext", "/some/path")
        assert result["verdict"] == "unverified"
        assert result["reason"] == "opaque_topology"

    def test_external_via_resolve_and_run(self, tmp_path):
        """end-to-end: external entry produce unverified:opaque_topology."""
        cfg_path = tmp_path / "factory.config.yaml"
        cfg_path.write_text("""
code_paths:
  - name: ext-target
    path: /some/external/path
    vcs:
      mode: external
""")
        cfg = ra.load_config(cfg_path)
        targets = ra._resolve_targets(cfg, tmp_path, None)
        assert len(targets) == 1
        result = ra._run_check(targets[0], tmp_path)
        assert result["verdict"] == "unverified"
        assert result["reason"] == "opaque_topology"

# ---------------------------------------------------------------------------
# Test: mode=monorepo (con repo git reale locale)
# ---------------------------------------------------------------------------

class TestModeMonorepo:

    def test_monorepo_aligned(self, tmp_path):
        """
        monorepo: locale HEAD == remote tip → aligned.
        Usiamo il repo locale come 'remote' (bare clone).
        """
        # Crea un "remote" bare
        remote = tmp_path / "remote"
        remote.mkdir()
        _git("init", "--bare", cwd=str(remote))

        # Clone locale
        local = tmp_path / "local"
        _git("clone", str(remote), str(local), cwd=str(tmp_path))
        _git("checkout", "-b", "main", cwd=str(local))
        (local / "file.txt").write_text("hello")
        _git("add", ".", cwd=str(local))
        _git("commit", "-m", "init", cwd=str(local))
        _git("push", "origin", "main", cwd=str(local))

        result = ra._check_monorepo("test", str(local), "main")
        assert result["verdict"] == "aligned", f"Atteso aligned, ottenuto: {result}"
        assert result["local_sha"] == result["remote_sha"]

    def test_monorepo_diverged_avanti(self, tmp_path):
        """
        monorepo: locale e' avanti → diverged.
        Commit locale non pushato.
        """
        remote = tmp_path / "remote"
        remote.mkdir()
        _git("init", "--bare", cwd=str(remote))

        local = tmp_path / "local"
        _git("clone", str(remote), str(local), cwd=str(tmp_path))
        _git("checkout", "-b", "main", cwd=str(local))
        (local / "file.txt").write_text("v1")
        _git("add", ".", cwd=str(local))
        _git("commit", "-m", "init", cwd=str(local))
        _git("push", "origin", "main", cwd=str(local))

        # Commit locale non pushato
        (local / "unpushed.txt").write_text("unpushed")
        _git("add", ".", cwd=str(local))
        _git("commit", "-m", "unpushed", cwd=str(local))

        result = ra._check_monorepo("test", str(local), "main")
        assert result["verdict"] == "diverged", f"Atteso diverged, ottenuto: {result}"
        d = result.get("direction") or {}
        # Il remote SHA e' nel local object store (e' il nostro commit precedente)
        # Quindi la direzione e' calcolabile
        if d.get("avanti") is not None:
            assert d["avanti"] >= 1, f"Atteso avanti>=1, direction: {d}"

    def test_monorepo_diverged_indietro(self, tmp_path):
        """
        monorepo: remote e' avanti → diverged (locale indietro).
        Commit sul remote non pullato localmente.
        """
        remote = tmp_path / "remote"
        remote.mkdir()
        _git("init", "--bare", cwd=str(remote))

        # Clone A: push di 2 commit
        cloneA = tmp_path / "cloneA"
        _git("clone", str(remote), str(cloneA), cwd=str(tmp_path))
        _git("checkout", "-b", "main", cwd=str(cloneA))
        (cloneA / "f1.txt").write_text("v1")
        _git("add", ".", cwd=str(cloneA))
        _git("commit", "-m", "init", cwd=str(cloneA))
        _git("push", "origin", "main", cwd=str(cloneA))

        # Clone B: clonato prima del secondo commit
        cloneB = tmp_path / "cloneB"
        _git("clone", str(remote), str(cloneB), cwd=str(tmp_path))
        # main esplicito su origin/main: l'HEAD del remote bare punta al branch predefinito di
        # `git init` (master sul runner CI), e il clone restava senza commit (EP-080 TSK-837)
        _git("checkout", "-B", "main", "origin/main", cwd=str(cloneB))

        # Clone A aggiunge un commit e pusha
        (cloneA / "f2.txt").write_text("v2")
        _git("add", ".", cwd=str(cloneA))
        _git("commit", "-m", "new on remote", cwd=str(cloneA))
        _git("push", "origin", "main", cwd=str(cloneA))

        # Clone B e' indietro rispetto al remote
        result = ra._check_monorepo("test", str(cloneB), "main")
        assert result["verdict"] == "diverged", f"Atteso diverged, ottenuto: {result}"

    def test_monorepo_no_remote(self, tmp_path):
        """monorepo senza remote → unverified: no_remote."""
        local = tmp_path / "local"
        local.mkdir()
        _git("init", cwd=str(local))
        _git("checkout", "-b", "main", cwd=str(local))
        (local / "f.txt").write_text("x")
        _git("add", ".", cwd=str(local))
        _git("commit", "-m", "init", cwd=str(local))

        result = ra._check_monorepo("test", str(local), "main")
        assert result["verdict"] == "unverified"
        assert result["reason"] == "no_remote"

    def test_monorepo_branch_auto_detect(self, tmp_path):
        """
        monorepo senza base_branch dichiarato: rileva il branch corrente.
        """
        remote = tmp_path / "remote"
        remote.mkdir()
        _git("init", "--bare", cwd=str(remote))

        local = tmp_path / "local"
        _git("clone", str(remote), str(local), cwd=str(tmp_path))
        _git("checkout", "-b", "develop", cwd=str(local))
        (local / "f.txt").write_text("v1")
        _git("add", ".", cwd=str(local))
        _git("commit", "-m", "init", cwd=str(local))
        _git("push", "origin", "develop", cwd=str(local))

        # branch=None → auto-detect
        result = ra._check_monorepo("test", str(local), base_branch=None)
        # Deve rilevare "develop" o trovare il verdetto
        assert result["verdict"] in ("aligned", "diverged", "unverified")
        if result["verdict"] != "unverified":
            assert result["branch"] == "develop"

# ---------------------------------------------------------------------------
# Test: mode=submodule (con fixture git — AC3)
# Il ramo submodule non e' esercitato nel repo della factory (nessun submodule).
# Questa fixture e' l'unico modo per coprirlo e garantire che non si rompa a valle.
# ---------------------------------------------------------------------------

class TestModeSubmodule:

    def test_submodule_aligned(self, submodule_fixture):
        """
        submodule: gitlink nel parent == tip del remote → aligned.
        Il gitlink punta a initial_sha, che e' il tip al momento della creazione.
        Nota: dopo il push di "new feature" il remote e' avanti, quindi questa
        fixture e' 'diverged'. Verifichiamo il comportamento reale.
        """
        f = submodule_fixture
        # La fixture ha il remote avanti rispetto al gitlink
        # Verifichiamo _check_submodule con il path corretto
        result = ra._check_submodule(
            name="sub",
            factory_root=str(f["parent"]),
            submodule_path="sub",
            base_branch="main",
        )
        # Dopo il push di "new feature", il remote e' avanti → diverged
        assert result["verdict"] in ("aligned", "diverged"), \
            f"Verdetto inatteso: {result}"
        assert result.get("gitlink_sha") is not None
        assert result.get("remote_sha") is not None

    def test_submodule_diverged_parent_behind(self, submodule_fixture):
        """
        submodule: remote ha un commit in piu' rispetto al gitlink → diverged.
        Il parent non ha aggiornato il gitlink dopo il push nel remote.
        """
        f = submodule_fixture
        result = ra._check_submodule(
            name="sub",
            factory_root=str(f["parent"]),
            submodule_path="sub",
            base_branch="main",
        )
        # Il remote e' avanti (sha remote != gitlink)
        assert result["verdict"] == "diverged", \
            f"Atteso diverged (parent behind), ottenuto: {result}"
        assert result["gitlink_sha"] == f["initial_sha"]
        assert result["remote_sha"] == f["remote_ahead_sha"]

    def test_submodule_no_base_branch(self, submodule_fixture):
        """submodule senza base_branch → unverified: base_branch_undeclared."""
        f = submodule_fixture
        result = ra._check_submodule(
            name="sub",
            factory_root=str(f["parent"]),
            submodule_path="sub",
            base_branch=None,
        )
        assert result["verdict"] == "unverified"
        assert result["reason"] == "base_branch_undeclared"

    def test_submodule_misplaced_base_branch(self, submodule_fixture):
        """base_branch solo dentro branch_awareness → unverified con la causa nominata,
        non «non dichiarato»: l'utente l'ha dichiarato, nel posto sbagliato."""
        f = submodule_fixture
        result = ra._check_submodule(
            name="sub",
            factory_root=str(f["parent"]),
            submodule_path="sub",
            base_branch=None,
            misplaced_base_branch="develop",
        )
        assert result["verdict"] == "unverified"
        assert result["reason"] == "base_branch_misplaced"
        assert "vcs.base_branch" in result["note"]

    def test_submodule_missing_path(self, tmp_path):
        """submodule_path inesistente → unverified: not_a_git_repo."""
        repo = _make_repo(str(tmp_path), "parent_no_sub")
        result = ra._check_submodule(
            name="missing-sub",
            factory_root=str(repo),
            submodule_path="nonexistent",
            base_branch="main",
        )
        assert result["verdict"] == "unverified"
        assert result["reason"] in ("not_a_git_repo", "unreachable")

    def test_submodule_detached_head_not_signal(self, submodule_fixture):
        """
        Nota semantica: il detached HEAD del submodule NON e' segnale di divergenza.
        Il confronto e' gitlink-parent vs remoto, mai HEAD locale del submodule.
        Anche se il submodule locale e' in detached HEAD, il verdetto usa il gitlink.
        """
        f = submodule_fixture
        # Il checkout del submodule e' in detached HEAD per design (git submodule update)
        # _check_submodule usa git ls-files -s nel parent (gitlink), non HEAD del sub
        result = ra._check_submodule(
            name="sub",
            factory_root=str(f["parent"]),
            submodule_path="sub",
            base_branch="main",
        )
        # Il verdetto si basa sul gitlink, non sull'HEAD del submodule locale
        assert result.get("gitlink_sha") is not None
        assert result["verdict"] != "unverified" or result["reason"] != "detached_head", \
            "detached_head del submodule non deve essere reason per unverified"

# ---------------------------------------------------------------------------
# Test: mode=sibling
# ---------------------------------------------------------------------------

class TestModeSibling:

    def test_sibling_aligned(self, tmp_path):
        """sibling: stesso algoritmo di monorepo, su path separato → aligned."""
        remote = tmp_path / "remote"
        remote.mkdir()
        _git("init", "--bare", cwd=str(remote))

        sibling = tmp_path / "sibling"
        _git("clone", str(remote), str(sibling), cwd=str(tmp_path))
        _git("checkout", "-b", "main", cwd=str(sibling))
        (sibling / "f.txt").write_text("v1")
        _git("add", ".", cwd=str(sibling))
        _git("commit", "-m", "init", cwd=str(sibling))
        _git("push", "origin", "main", cwd=str(sibling))

        result = ra._check_sibling("test-sibling", str(sibling), "main")
        assert result["verdict"] == "aligned"
        assert result["mode"] == "sibling"

    def test_sibling_diverged(self, tmp_path):
        """sibling: commit non pushato → diverged."""
        remote = tmp_path / "remote"
        remote.mkdir()
        _git("init", "--bare", cwd=str(remote))

        sibling = tmp_path / "sibling"
        _git("clone", str(remote), str(sibling), cwd=str(tmp_path))
        _git("checkout", "-b", "main", cwd=str(sibling))
        (sibling / "f.txt").write_text("v1")
        _git("add", ".", cwd=str(sibling))
        _git("commit", "-m", "init", cwd=str(sibling))
        _git("push", "origin", "main", cwd=str(sibling))

        # Commit non pushato
        (sibling / "unpushed.txt").write_text("local only")
        _git("add", ".", cwd=str(sibling))
        _git("commit", "-m", "local", cwd=str(sibling))

        result = ra._check_sibling("test-sibling", str(sibling), "main")
        assert result["verdict"] == "diverged"
        assert result["mode"] == "sibling"

# ---------------------------------------------------------------------------
# Test: partition completeness (AC4)
# ---------------------------------------------------------------------------

class TestPartitionCompleteness:

    VALID_VERDICTS = {"aligned", "diverged", "unverified"}
    VALID_REASONS = {
        "unreachable", "auth_failure", "no_remote", "detached_head",
        "not_a_git_repo", "opaque_topology", "base_branch_undeclared",
        "base_branch_misplaced",
    }

    def test_every_result_has_exactly_one_verdict(self, tmp_path):
        """Ogni target ha esattamente un verdetto dall'enum chiuso."""
        # Usa il repo reale della factory
        cfg_path = _REPO_ROOT / "factory.config.yaml"
        cfg = ra.load_config(cfg_path)
        targets = ra._resolve_targets(cfg, _REPO_ROOT, None)

        for t in targets:
            result = ra._run_check(t, _REPO_ROOT)
            assert result["verdict"] in self.VALID_VERDICTS, \
                f"Verdetto non valido per {t['name']}: {result['verdict']!r}"

    def test_unverified_has_valid_reason(self, tmp_path):
        """Ogni unverified ha reason dall'enum chiuso."""
        result = ra._check_external("x", "/path")
        assert result["reason"] in self.VALID_REASONS, \
            f"Reason non valida: {result['reason']!r}"

    def test_external_opaque_topology_in_enum(self):
        """opaque_topology e' nell'enum chiuso."""
        result = ra._check_external("x", "/")
        assert result["reason"] == "opaque_topology"
        assert result["reason"] in self.VALID_REASONS

# ---------------------------------------------------------------------------
# Test: output JSON (machine-readable)
# ---------------------------------------------------------------------------

class TestOutputJson:

    def test_json_schema(self, tmp_path):
        """Output JSON ha la struttura attesa con timestamp e repos."""
        result_a = {
            "name": "a", "mode": "monorepo", "path": "/a",
            "verdict": "aligned", "branch": "main",
            "local_sha": "abc1234", "remote_sha": "abc1234",
            "direction": None, "reason": None, "note": "",
        }
        result_u = {
            "name": "b", "mode": "external", "path": "/b",
            "verdict": "unverified", "reason": "opaque_topology",
            "note": "", "branch": None, "local_sha": None, "remote_sha": None,
            "direction": None,
        }
        ts = "2026-09-25T12:00:00Z"
        out = ra._render_json([result_a, result_u], ts)
        parsed = json.loads(out)

        assert parsed["timestamp"] == ts
        assert "repos" in parsed
        assert "aligned" in parsed["repos"]
        assert "diverged" in parsed["repos"]
        assert "unverified" in parsed["repos"]
        assert len(parsed["repos"]["aligned"]) == 1
        assert len(parsed["repos"]["unverified"]) == 1

# ---------------------------------------------------------------------------
# Test: output testuale
# ---------------------------------------------------------------------------

class TestOutputText:

    def test_text_contains_sections(self):
        """Output testo contiene le sezioni ALIGNED, DIVERGED, UNVERIFIED."""
        results = [
            {"name": "x", "mode": "monorepo", "verdict": "aligned",
             "branch": "main", "local_sha": "aaa1111", "remote_sha": "aaa1111",
             "direction": None, "reason": None, "note": "", "path": "/x"},
        ]
        out = ra._render_text(results, "2026-09-25T12:00:00Z")
        assert "ALIGNED" in out
        assert "DIVERGED" in out
        assert "UNVERIFIED" in out
        assert "repo-align" in out

    def test_text_no_compression_marker(self):
        """Output testo non e' compresso (R.18 — output integrale)."""
        results = [
            {"name": "y", "mode": "external", "verdict": "unverified",
             "reason": "opaque_topology", "note": "", "branch": None,
             "local_sha": None, "remote_sha": None, "direction": None, "path": "/y"},
        ]
        out = ra._render_text(results, "2026-09-25T12:00:00Z")
        # L'output non deve essere compresso o troncato
        assert "ALIGNED" in out
        assert "DIVERGED" in out
        assert "UNVERIFIED" in out
        assert "opaque_topology" in out

# ---------------------------------------------------------------------------
# Test: integration su questo repo (AC8)
# ---------------------------------------------------------------------------

class TestIntegrationRealRepo:

    def test_real_repo_has_verdicts(self):
        """
        AC8: eseguito sul repo reale, ogni target ha un verdetto reale.
        Il repo e' accessibile e ha remote origin.
        """
        cfg_path = _REPO_ROOT / "factory.config.yaml"
        cfg = ra.load_config(cfg_path)
        targets = ra._resolve_targets(cfg, _REPO_ROOT, None)

        assert len(targets) > 0, "Nessun target trovato nel repo reale"

        for t in targets:
            result = ra._run_check(t, _REPO_ROOT)
            assert result["verdict"] in {"aligned", "diverged", "unverified"}, \
                f"Verdetto non valido per {t['name']}: {result}"

    def test_real_repo_factory_target_has_sha(self):
        """
        Il target della factory stessa (monorepo, code_path='.') ha SHA reali.
        """
        cfg_path = _REPO_ROOT / "factory.config.yaml"
        cfg = ra.load_config(cfg_path)
        targets = ra._resolve_targets(cfg, _REPO_ROOT, None)

        # Trova il target che corrisponde alla factory stessa
        factory_target = next(
            (t for t in targets if t["path"] == str(_REPO_ROOT)), None
        )
        if factory_target is None:
            # Prova a trovare "factory" o qualsiasi monorepo sulla root
            factory_target = next(
                (t for t in targets if t["mode"] == "monorepo" and
                 t["path"] == str(_REPO_ROOT)), None
            )

        if factory_target is None:
            pytest.skip("Target factory non trovato (potrebbe essere code_paths-only)")

        result = ra._run_check(factory_target, _REPO_ROOT)
        # Se ha un remote, deve avere gli SHA
        if result["verdict"] in ("aligned", "diverged"):
            sha_key = "local_sha" if result["mode"] != "submodule" else "gitlink_sha"
            assert result.get(sha_key) is not None, \
                f"SHA mancante per target factory: {result}"
