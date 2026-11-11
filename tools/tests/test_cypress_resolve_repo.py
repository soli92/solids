"""Test di tools/cypress/resolve_repo.py .

Ogni test costruisce una factory finta in una cartella temporanea: factory.config.yaml con il
blocco cypress_pipeline, .gitmodules e repo git minimi (un commit vuoto, remote origin). Nessuna
dipendenza dai submodule reali della macchina; le variabili LOCAL_REPO_* dell'ambiente sono
tolte prima di ogni esecuzione.

Si eseguono con pytest oppure direttamente: python3 tools/tests/test_cypress_resolve_repo.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
SCRIPT = QUI.parent / "cypress" / "resolve_repo.py"
_spec = importlib.util.spec_from_file_location("resolve_repo", SCRIPT)
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

TEST_URL = "https://git.example.invalid/org/cypress-test"
SOURCE_URL = "https://git.example.invalid/org/app"
ALTRO_URL = "https://git.example.invalid/altro/altro-repo"
TIMEOUT = 30


def _git(args, cwd):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", "-c", f"core.hooksPath={os.devnull}", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True, timeout=TIMEOUT)


def _repo(path: Path, url: str, branch: str = "main", detached: bool = False) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q", "-b", branch], path)
    _git(["commit", "-q", "--allow-empty", "-m", "init"], path)
    _git(["remote", "add", "origin", url], path)
    if detached:
        _git(["checkout", "-q", "--detach"], path)
    return path


def _config(enabled: bool = True, source_branch: str = "develop", extra_entry: str = "") -> str:
    return f"""project:
  name: finta

cypress_pipeline:
  enabled: {"true" if enabled else "false"}   # commento inline
  repos:
    - name: prova-cypress-test
      test_path: code_repos/prova/cypress-test
      layout: root
      source: app-prova
      source_path: code_repos/app-prova
      source_branch: {source_branch}
      conventions_ref: ""                 # commento inline
      conventions_status: presenti
{extra_entry}
lint:
  enabled: true
"""


def _gitmodules() -> str:
    return f"""[submodule "code_repos/prova/cypress-test"]
\tpath = code_repos/prova/cypress-test
\turl = {TEST_URL}
[submodule "code_repos/app-prova"]
\tpath = code_repos/app-prova
\turl = {SOURCE_URL}
"""


@contextlib.contextmanager
def factory(enabled=True, init_test=True, init_source=True, source_branch="develop",
            source_on="develop", source_detached=False, extra_entry=""):
    """Factory finta; restituisce (root, cartella esterna per i clone personali)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        root = base / "factory"
        root.mkdir()
        (root / "factory.config.yaml").write_text(
            _config(enabled, source_branch, extra_entry), encoding="utf-8")
        (root / ".gitmodules").write_text(_gitmodules(), encoding="utf-8")
        test_dir = root / "code_repos" / "prova" / "cypress-test"
        source_dir = root / "code_repos" / "app-prova"
        if init_test:
            _repo(test_dir, TEST_URL)
        else:
            test_dir.mkdir(parents=True)        # cartella del submodule non inizializzato
        if init_source:
            _repo(source_dir, SOURCE_URL, branch=source_on, detached=source_detached)
        else:
            source_dir.mkdir(parents=True)
        esterna = base / "clone"
        esterna.mkdir()
        yield root, esterna


def _env(extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("LOCAL_REPO_")}
    env.update(extra or {})
    return env


def run_cli(root, *args, env=None):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args, "--root", str(root)],
                          capture_output=True, text=True, timeout=TIMEOUT, env=_env(env))
    return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip() else None), proc


def _write_override(root, **values):
    (root / "tools" / "vcs").mkdir(parents=True, exist_ok=True)
    (root / "tools" / "vcs" / ".env.local-repos").write_text(
        "# clone personali\n" + "".join(f'{k}="{v}"\n' for k, v in values.items()),
        encoding="utf-8")


def _snapshot(root: Path):
    return sorted((p.relative_to(root).as_posix(), p.stat().st_size, p.stat().st_mtime_ns)
                  for p in root.rglob("*") if p.is_file())


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

def test_flag_spento_risponde_disabled_senza_risoluzione():
    with factory(enabled=False, init_test=False, init_source=False) as (root, _):
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 0
        assert out["status"] == "disabled"
        assert "test" not in out and "source" not in out


def test_list_legge_registro_e_commenti_inline():
    with factory(enabled=False) as (root, _):
        code, out, _ = run_cli(root, "--list")
        assert code == 0 and out["enabled"] is False
        voce = out["repos"][0]
        assert voce["name"] == "prova-cypress-test"
        assert voce["conventions_ref"] == "" and voce["source_branch"] == "develop"


def test_blocco_assente_equivale_a_spento():
    with factory() as (root, _):
        (root / "factory.config.yaml").write_text("project:\n  name: finta\n", encoding="utf-8")
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 0 and out["status"] == "disabled"
        code, out, _ = run_cli(root, "--list")
        assert code == 0 and out["enabled"] is False and out["repos"] == []


def test_nome_sconosciuto_exit_2():
    with factory() as (root, _):
        code, out, _ = run_cli(root, "non-esiste")
        assert code == 2 and out["status"] == "usage"
        assert "prova-cypress-test" in out["errors"][0]


def test_argomenti_mancanti_exit_2():
    with factory() as (root, _):
        code, out, proc = run_cli(root)
        assert code == 2 and out is None and "usage" in proc.stderr


def test_voce_incompleta_e_errore():
    voce = "    - name: monca\n      test_path: code_repos/monca\n"
    with factory(extra_entry=voce) as (root, _):
        code, out, _ = run_cli(root, "monca")
        assert code == 1 and out["status"] == "error"
        assert "source" in out["errors"][0]


# ---------------------------------------------------------------------------
# Submodule
# ---------------------------------------------------------------------------

def test_submodule_inizializzati_ok():
    with factory() as (root, _):
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 0 and out["status"] == "ok", out
        assert out["test"]["source"] == "submodule" and out["source"]["source"] == "submodule"
        assert out["test"]["path"].endswith("code_repos/prova/cypress-test")
        assert out["test"]["remote_match"] is True and out["source"]["remote_match"] is True
        assert out["warnings"] == []


def test_submodule_non_inizializzato_indica_sm_doctor():
    with factory(init_test=False) as (root, _):
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 1 and out["status"] == "error"
        assert out["test"]["path"] is None
        assert "sm_doctor.py --target prova/cypress-test" in out["errors"][0]
        assert "LOCAL_REPO_PROVA_CYPRESS_TEST" in out["errors"][0]


def test_sorgente_non_inizializzato_e_errore():
    with factory(init_source=False) as (root, _):
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 1 and "code_repos/app-prova" in out["errors"][0]


def test_detached_head_senza_avviso_sul_branch():
    with factory(source_detached=True) as (root, _):
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 0 and out["warnings"] == []
        assert out["source"]["branch"] is None and out["source"]["commit"]


def test_branch_con_nome_diverso_dal_registro_avvisa():
    with factory(source_on="feature/altro") as (root, _):
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 0 and out["status"] == "ok"
        assert any("feature/altro" in w for w in out["warnings"])


def test_branch_da_confermare_non_avvisa():
    with factory(source_branch="da_confermare", source_on="feature/altro") as (root, _):
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 0 and out["warnings"] == []


# ---------------------------------------------------------------------------
# Override per operatore
# ---------------------------------------------------------------------------

def test_override_da_file_valido():
    with factory(init_test=False) as (root, esterna):
        clone = _repo(esterna / "cypress-test", TEST_URL + ".git")
        _write_override(root, LOCAL_REPO_PROVA_CYPRESS_TEST=clone.as_posix())
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 0 and out["status"] == "ok", out
        assert out["test"]["source"] == "override"
        assert out["test"]["path"] == clone.resolve().as_posix()
        assert out["test"]["remote_match"] is True        # .git finale ignorato nel confronto


def test_override_con_credenziali_nel_remote_combacia():
    with factory(init_test=False) as (root, esterna):
        clone = _repo(esterna / "cypress-test", TEST_URL.replace("https://", "https://utente@"))
        _write_override(root, LOCAL_REPO_PROVA_CYPRESS_TEST=clone.as_posix())
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 0 and out["test"]["remote_match"] is True


def test_override_da_variabile_ambiente():
    with factory() as (root, esterna):
        clone = _repo(esterna / "app", SOURCE_URL, branch="develop")
        code, out, _ = run_cli(root, "prova-cypress-test",
                               env={"LOCAL_REPO_APP_PROVA": clone.as_posix()})
        assert code == 0 and out["source"]["source"] == "override"
        assert out["test"]["source"] == "submodule"


def test_override_inesistente_e_errore():
    with factory() as (root, esterna):
        _write_override(root, LOCAL_REPO_PROVA_CYPRESS_TEST=(esterna / "manca").as_posix())
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 1 and out["status"] == "error"
        assert "path inesistente" in out["errors"][0]


def test_override_non_radice_di_repo_e_errore():
    with factory() as (root, esterna):
        clone = _repo(esterna / "cypress-test", TEST_URL)
        (clone / "sotto").mkdir()
        _write_override(root, LOCAL_REPO_PROVA_CYPRESS_TEST=(clone / "sotto").as_posix())
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 1 and "radice di un repo git" in out["errors"][0]


def test_override_con_remote_diverso_avvisa():
    with factory() as (root, esterna):
        clone = _repo(esterna / "altro", ALTRO_URL)
        _write_override(root, LOCAL_REPO_PROVA_CYPRESS_TEST=clone.as_posix())
        code, out, _ = run_cli(root, "prova-cypress-test")
        assert code == 0 and out["status"] == "ok"
        assert out["test"]["remote_match"] is False
        assert any("diverso dal submodule" in w for w in out["warnings"])


# ---------------------------------------------------------------------------
# Robustezza
# ---------------------------------------------------------------------------

def test_git_in_timeout_esce_con_errore():
    with factory() as (root, _):
        originale = rr.subprocess.run

        def lento(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout"))

        rr.subprocess.run = lento
        rr._gitmodules_urls.cache_clear()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                code = rr.main(["prova-cypress-test", "--root", str(root)])
        finally:
            rr.subprocess.run = originale
            rr._gitmodules_urls.cache_clear()
        out = json.loads(buf.getvalue())
        assert code == 1 and out["status"] == "error"
        assert "timeout" in out["errors"][0]


def test_sola_lettura_e_output_stabile():
    with factory() as (root, esterna):
        clone = _repo(esterna / "cypress-test", TEST_URL)
        _write_override(root, LOCAL_REPO_PROVA_CYPRESS_TEST=clone.as_posix())
        prima = _snapshot(root)
        _, uno, _ = run_cli(root, "prova-cypress-test")
        _, due, _ = run_cli(root, "prova-cypress-test")
        assert _snapshot(root) == prima        # nessun file scritto o modificato
        assert uno == due


def test_env_key():
    assert rr.env_key("mio-cypress-test") == "LOCAL_REPO_MIO_CYPRESS_TEST"
    assert rr.env_key("app-demo") == "LOCAL_REPO_APP_DEMO"


def test_reporter_default_globale_e_per_repo():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        (root / "factory.config.yaml").write_text(_config(), encoding="utf-8")
        assert rr.load_registry(root)["reporter"] == "generic"
        testo = _config().replace("  enabled: true", "  enabled: true\n  reporter: custom-x", 1)
        testo = testo.replace("      conventions_status: presenti",
                              "      conventions_status: presenti\n      reporter: altro", 1)
        (root / "factory.config.yaml").write_text(testo, encoding="utf-8")
        reg = rr.load_registry(root)
        assert reg["reporter"] == "custom-x" and reg["repos"][0]["reporter"] == "altro"


if __name__ == "__main__":
    test_fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falliti = 0
    for nome, fn in test_fns:
        try:
            fn()
            print(f"ok    {nome}")
        except Exception as exc:  # il runner riporta ogni fallimento e prosegue
            falliti += 1
            print(f"FAIL  {nome}: {exc!r}")
    print(f"\n{len(test_fns) - falliti}/{len(test_fns)} passati")
    sys.exit(1 if falliti else 0)
