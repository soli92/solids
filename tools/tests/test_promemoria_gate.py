"""
Gate di conferma del push di tools/promemoria/promemoria.py, config e Day 0, senza rete:
il remote e' un repo bare locale in una cartella temporanea.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PM = _REPO_ROOT / "tools" / "promemoria" / "promemoria.py"
_DAY0 = _REPO_ROOT / "tools" / "onboarding" / "day0.py"
_VERIFICA = _REPO_ROOT / "tools" / "onboarding" / "verifica_day0.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pm = _load("promemoria_gate", _PM)
day0 = _load("day0_gate", _DAY0)
verifica = _load("verifica_gate", _VERIFICA)

CONFIG_ACCESA = """promemoria_operatori:
  enabled: true
  remote: origin
  branch: trunk
onboarding_day0:
  enabled: true
  roles:
    dev: Sviluppo
    qa: Collaudo
"""


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


@pytest.fixture
def factory(tmp_path, monkeypatch):
    """Clone con remote bare locale, ramo 'trunk', config accesa e un operatore in anagrafica."""
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "trunk", str(bare)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "-b", "trunk", str(work)], check=True)
    _git(work, "config", "user.name", "Anna Bianchi")
    _git(work, "config", "user.email", "anna.bianchi@example.com")
    (work / "factory.config.yaml").write_text(CONFIG_ACCESA, encoding="utf-8")
    riferimenti = work / ".claude/skills/references/onboarding"
    riferimenti.mkdir(parents=True)
    (riferimenti / "day0-per-ruolo.md").write_text(
        "## dev\n\n1. Uno\n\n## qa\n\n1. Due\n\n## generico\n\n1. Tre\n", encoding="utf-8")
    ops = work / "memory/promemoria/operatori"
    ops.mkdir(parents=True)
    (ops / "anna-bianchi.yaml").write_text(
        "nome: Anna Bianchi\nemail:\n  - anna.bianchi@example.com\nruolo: dev\n", encoding="utf-8")
    (ops / "mario-rossi.yaml").write_text(
        "nome: Mario Rossi\nemail:\n  - mario.rossi@example.com\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "-q", "origin", "trunk")
    monkeypatch.chdir(work)
    assert pm.configure(work) is True
    yield work, bare
    pm.configure(tmp_path)  # config assente: ripristina i default del modulo


def _args(**kw):
    base = dict(a="mario-rossi", testo="Controlla il rilascio", decorrenza=None, titolo=None,
                trailer=None, push=True, yes=False)
    base.update(kw)
    return argparse.Namespace(**base)


def _remote_head(bare: Path) -> str:
    return _git(bare, "rev-parse", "trunk")


def test_config_ramo_ruoli_e_enabled(factory):
    work, _ = factory
    assert pm.BRANCH == "trunk" and pm.REF == "refs/promemoria/trunk"
    assert pm.RUOLI == {"dev": "Sviluppo", "qa": "Collaudo"}


def test_default_a_config_assente_e_spento(tmp_path):
    assert pm.configure(tmp_path) is False
    assert pm.BRANCH == "main" and pm.REMOTE == "origin"
    assert "sviluppo" in pm.RUOLI


def test_config_branch_non_valido_rifiutato(tmp_path):
    (tmp_path / "factory.config.yaml").write_text("promemoria_operatori:\n  enabled: true\n  branch: \"--upload-pack=x\"\n",
                                                  encoding="utf-8")
    with pytest.raises(pm.Errore):
        pm.configure(tmp_path)
    pm.configure(tmp_path / "vuota")


def test_push_senza_yes_e_senza_terminale_rifiutato(factory, monkeypatch, capsys):
    work, bare = factory
    prima = _remote_head(bare)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert pm.fetch(work)
    with pytest.raises(pm.Errore, match="conferma richiesta"):
        pm.cmd_invia(_args(), work)
    assert _remote_head(bare) == prima
    assert "PUSH DA CONFERMARE" in capsys.readouterr().out


def test_push_con_yes_pubblica_sul_ramo_configurato(factory, monkeypatch, capsys):
    work, bare = factory
    prima = _remote_head(bare)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert pm.cmd_invia(_args(yes=True), work) == 0
    assert _remote_head(bare) != prima
    files = _git(bare, "ls-tree", "-r", "--name-only", "trunk").splitlines()
    assert any(f.startswith("memory/promemoria/mario-rossi/") and f.endswith(".md") for f in files)
    assert "main" not in _git(bare, "branch", "--format=%(refname:short)").split()
    assert "Conferma data con --yes" in capsys.readouterr().out


def test_push_interattivo_risposta_no_annulla(factory, monkeypatch):
    work, bare = factory
    prima = _remote_head(bare)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    with pytest.raises(pm.Errore, match="annullato"):
        pm.cmd_invia(_args(), work)
    assert _remote_head(bare) == prima


def test_push_interattivo_risposta_si_pubblica(factory, monkeypatch):
    work, bare = factory
    prima = _remote_head(bare)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "s")
    assert pm.cmd_invia(_args(), work) == 0
    assert _remote_head(bare) != prima


def test_anteprima_senza_push_non_chiede_ne_pubblica(factory, capsys):
    work, bare = factory
    prima = _remote_head(bare)
    assert pm.cmd_invia(_args(push=False), work) == 0
    assert _remote_head(bare) == prima
    assert "ANTEPRIMA" in capsys.readouterr().out


def test_mask_url_nasconde_le_credenziali():
    assert pm.mask_url("https://utente:segreto@host/repo.git") == "https://***@host/repo.git"
    assert pm.mask_url("/tmp/remote.git") == "/tmp/remote.git"


def test_capability_spenta_esce_con_3_e_la_consegna_tace(tmp_path, monkeypatch, capsys):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "factory.config.yaml").write_text("promemoria_operatori:\n  enabled: false\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert pm.main(["operatori", "--no-fetch"]) == 3
    assert "capability spenta" in capsys.readouterr().err
    assert pm.main(["consegna", "--no-fetch"]) == 0
    assert capsys.readouterr().out == ""


def test_senza_python_yaml_il_blocco_minimo_legge_enabled():
    testo = "promemoria:\n  enabled: true  # acceso\n  branch: trunk\naltro:\n  enabled: false\n"
    assert pm._blocco_minimo(testo, "promemoria") == {"enabled": "true", "branch": "trunk"}


# ----------------------------------------------------------------------- Day 0


def test_day0_ruolo_da_anagrafica_con_promemoria_acceso(factory, capsys):
    work, _ = factory
    code, payload = day0.run(["--root", str(work), "--ruolo", "dev"])
    assert code == 0 and payload["ruolo"] == "dev" and payload["etichetta"] == "Sviluppo"


def test_day0_ruolo_sconosciuto_exit_2(factory):
    work, _ = factory
    code, payload = day0.run(["--root", str(work), "--ruolo", "sviluppo-fe"])
    assert code == 2 and "dev" in payload["ruoli"] and "salta" in payload["ruoli"]


def test_day0_senza_promemoria_funziona_con_generico(tmp_path):
    (tmp_path / "factory.config.yaml").write_text("promemoria_operatori:\n  enabled: false\n", encoding="utf-8")
    ref = tmp_path / ".claude/skills/references/onboarding"
    ref.mkdir(parents=True)
    (ref / "day0-per-ruolo.md").write_text("## generico\n\n1. Prima\n", encoding="utf-8")
    code, payload = day0.run(["--root", str(tmp_path)])
    assert code == 0 and payload["ruolo"] == "generico"
    assert payload["promemoria_acceso"] is False and payload["nota_ruolo"] is None
    assert payload["onboarding_enabled"] is False
    assert "1. Prima" in day0.render(payload)


def test_day0_sezione_mancante_exit_1(factory):
    work, _ = factory
    (work / ".claude/skills/references/onboarding/day0-per-ruolo.md").write_text(
        "## generico\n\n1. Prima\n", encoding="utf-8")
    code, payload = day0.run(["--root", str(work), "--ruolo", "qa"])
    assert code == 1 and "manca la sezione" in payload["errore"]


def test_day0_file_di_riferimento_del_master_ha_una_sezione_per_ruolo_di_default():
    testi = day0.sections((_REPO_ROOT / day0.DAY0).read_text(encoding="utf-8"))
    pm.configure(_REPO_ROOT / "inesistente")
    assert set(pm.RUOLI) | {"generico"} <= set(testi)
    for corpo in testi.values():
        assert len([r for r in corpo.splitlines() if r[:2].strip().rstrip(".").isdigit()]) <= 3


def test_verifica_day0_spenta_senza_promemoria(tmp_path):
    (tmp_path / "factory.config.yaml").write_text("promemoria_operatori:\n  enabled: false\n", encoding="utf-8")
    code, r = verifica.run(["--dal", "2026-01-01", "--root", str(tmp_path)])
    assert code == 1 and "promemoria" in r["errore"]


def test_verifica_day0_registrati_e_primo_tsk(factory):
    work, _ = factory
    kanban = work / "management/kanban/EP-001"
    kanban.mkdir(parents=True)
    (kanban / "TSK-001.md").write_text(
        "---\nid: TSK-001\nstatus: done\nclosed_at: 2099-01-02\ndone_by:\n  - Anna Bianchi\n---\n",
        encoding="utf-8")
    code, r = verifica.run(["--dal", "2000-01-01", "--root", str(work), "--ref", "HEAD"])
    assert code == 0
    anna = next(p for p in r["persone"] if p["slug"] == "anna-bianchi")
    assert anna["ruolo"] == "dev" and anna["primo_tsk_chiuso"]["tsk"] == "TSK-001"
    mario = next(p for p in r["persone"] if p["slug"] == "mario-rossi")
    assert mario["primo_tsk_chiuso"] is None
    json.dumps(r)
