"""Test di tools/analytics/team-velocity.py e kanban_history.py su un kanban sintetico in un repo git temporaneo."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ANALYTICS = Path(__file__).resolve().parents[1] / "analytics"
sys.path.insert(0, str(_ANALYTICS))
_spec = importlib.util.spec_from_file_location("team_velocity", _ANALYTICS / "team-velocity.py")
tv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tv)
import kanban_history as kh  # noqa: E402

TODAY = dt.date(2026, 10, 14)  # mercoledi' della settimana 2026-W42


def _git(repo, *args, date=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Dev Uno", GIT_AUTHOR_EMAIL="uno@example.com",
               GIT_COMMITTER_NAME="Dev Uno", GIT_COMMITTER_EMAIL="uno@example.com")
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00"
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def _tsk(repo, rel, status, extra=""):
    p = repo / "management/kanban" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{k}: {v}" for k, v in extra) if extra else ""
    p.write_text(f"---\nid: x\nstatus: {status}\n{body}\n---\n# t\n", encoding="utf-8")


def _commit(repo, msg, date):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg, date=date)


@pytest.fixture()
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    return tmp_path


def _run(repo, cfg=None, **kw):
    c = tv.load_config(None, repo)
    c.update(cfg or {})
    return tv.compute(c, repo, today=TODAY, **kw)


def test_chiusura_da_storia_git_e_inizio_da_git(repo):
    _tsk(repo, "EP-001-a/US-1/TSK-1.md", "todo", [("estimate", "M")])
    _commit(repo, "a", "2026-10-01")
    _tsk(repo, "EP-001-a/US-1/TSK-1.md", "in-progress", [("estimate", "M")])
    _commit(repo, "b", "2026-10-05")
    _tsk(repo, "EP-001-a/US-1/TSK-1.md", "done", [("estimate", "M")])
    _commit(repo, "c", "2026-10-07")
    r = _run(repo)
    assert r["serie"]["2026-W41"]["totale"] == {"tsk": 1, "punti": 3, "giorni": 1.0, "in_blocco": 0}
    q = r["qualita_dati"]
    assert q["done_con_data_git"] == 1 and q["done_con_inizio_da_git"] == 1
    assert r["attraversamento"]["M"]["mediana"] == 3  # lun-mer inclusi


def test_closed_at_prevale_sulla_storia(repo):
    ex = [("estimate", "S"), ("started_at", "2026-09-29T08:00:00Z"), ("closed_at", "2026-10-02")]
    _tsk(repo, "EP-001-a/US-1/TSK-2.md", "done", ex)
    _commit(repo, "tutto insieme", "2026-10-12")
    r = _run(repo)
    assert r["serie"]["2026-W40"]["totale"]["punti"] == 2
    assert r["serie"]["2026-W42"]["totale"]["tsk"] == 0
    q = r["qualita_dati"]
    assert q["done_con_closed_at"] == 1 and q["done_con_started_at"] == 1 and q["done_registrati_in_blocco"] == 0


def test_registrazione_in_blocco(repo):
    for i in range(1, 4):
        _tsk(repo, f"EP-001-a/US-1/TSK-{i}.md", "done", [("estimate", "XS")])
    _commit(repo, "riconciliazione", "2026-10-06")
    r = _run(repo, {"soglia_chiusura_in_blocco": 3})
    assert r["qualita_dati"]["done_registrati_in_blocco"] == 3
    assert r["serie"]["2026-W41"]["totale"]["in_blocco"] == 3
    r = _run(repo, {"soglia_chiusura_in_blocco": 4})
    assert r["qualita_dati"]["done_registrati_in_blocco"] == 0


def test_tsk_senza_taglia_vale_zero_punti(repo):
    _tsk(repo, "EP-001-a/US-1/TSK-3.md", "done")
    _tsk(repo, "EP-001-a/US-1/TSK-4.md", "todo")
    _commit(repo, "x", "2026-10-06")
    r = _run(repo)
    assert r["serie"]["2026-W41"]["totale"]["tsk"] == 1 and r["serie"]["2026-W41"]["totale"]["punti"] == 0
    assert r["qualita_dati"]["aperti_senza_stima"] == ["TSK-4"]
    assert r["proiezioni"]["totale"]["backlog_tsk"] == 1


def test_id_con_e_senza_prefisso_e_slug(repo):
    _tsk(repo, "EP-001-a/US-1/TSK-5.md", "done", [("size", "s")])
    _tsk(repo, "XX-EP-002-b/XX-US-1/XX-TSK-6-con-slug.md", "done", [("estimate", "L")])
    _commit(repo, "x", "2026-10-06")
    r = _run(repo)
    assert r["serie"]["2026-W41"]["totale"] == {"tsk": 2, "punti": 7, "giorni": 2.5, "in_blocco": 0}
    assert kh.TSK_RE.search("XX-TSK-6-con-slug.md").group(1) == "XX-TSK-6"
    assert kh.TSK_RE.search("TSK-5.md").group(1) == "TSK-5"


def test_epiche_da_config_e_filtro_e_archivio(repo):
    _tsk(repo, "EP-001-a/US-1/TSK-7.md", "done", [("estimate", "M")])
    _tsk(repo, "EP-002-b/US-1/TSK-8.md", "done", [("estimate", "S")])
    _tsk(repo, "archive/EP-003-c/US-1/TSK-9.md", "done", [("estimate", "XL")])
    _commit(repo, "x", "2026-10-06")
    assert _run(repo)["serie"]["2026-W41"]["totale"]["tsk"] == 2  # archivio escluso di default
    cfg = {"epiche": [{"id": "EP-001", "gruppo": "uno"}, {"id": "EP-002", "gruppo": "due"}]}
    s = _run(repo, cfg)["serie"]["2026-W41"]
    assert s["uno"]["punti"] == 3 and s["due"]["punti"] == 2
    assert _run(repo, cfg, epic_filter=["EP-002"])["serie"]["2026-W41"]["totale"]["tsk"] == 1
    cfg = {"kanban": "management/kanban", "includi_archivio": True, "epiche": ["EP-003"]}
    assert _run(repo, cfg) ["qualita_dati"]["archivio_incluso"] is True


def test_persona_solo_con_flag(repo):
    _tsk(repo, "EP-001-a/US-1/TSK-10.md", "done", [("estimate", "S"), ("owner", "dev-agent")])
    _commit(repo, "x", "2026-10-06")
    cfg = {"team": [{"id": "uno", "nome": "Dev Uno"}], "agenti": ["dev-agent"]}
    assert "persone" not in _run(repo, cfg)
    r = _run(repo, cfg, per_persona=True)
    assert list(r["persone"]) == ["uno"]  # agente -> autore del commit di chiusura
    assert "Per persona" not in tv.render(_run(repo, cfg)) and "Per persona" in tv.render(r)


def test_done_non_committato_senza_data(repo):
    _tsk(repo, "EP-001-a/US-1/TSK-11.md", "todo")
    _commit(repo, "x", "2026-10-06")
    _tsk(repo, "EP-001-a/US-1/TSK-11.md", "done")
    assert _run(repo)["qualita_dati"]["done_senza_data"] == ["TSK-11"]


def test_id_duplicato_in_due_file(repo):
    _tsk(repo, "EP-001-a/US-1/TSK-12.md", "done", [("estimate", "S")])
    _tsk(repo, "EP-002-b/US-1/TSK-12.md", "done", [("estimate", "S")])
    _commit(repo, "x", "2026-10-06")
    r = _run(repo)
    assert r["serie"]["2026-W41"]["totale"]["tsk"] == 2 and r["qualita_dati"]["id_duplicati"] == ["TSK-12"]


def test_cli_senza_config_e_kanban_vuoto(repo, capsys):
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init", date="2026-10-01")
    tv.main(["--root", str(repo), "--config", "assente.json"])
    assert "Qualità dei dati" in capsys.readouterr().out


def test_chiusura_dopo_la_data_di_riferimento_esclusa(repo):
    # regressione: con today nel passato rispetto alla chiusura, compute andava in KeyError
    _tsk(repo, "EP-001-a/US-1/TSK-7.md", "done", [("estimate", "S"), ("closed_at", "2026-10-20")])
    _tsk(repo, "EP-001-a/US-1/TSK-8.md", "done", [("estimate", "M"), ("closed_at", "2026-10-06")])
    _commit(repo, "chiusure", "2026-10-20")
    r = _run(repo)
    assert r["qualita_dati"]["done_dopo_riferimento"] == ["TSK-7"]
    assert sum(w["totale"]["tsk"] for w in r["serie"].values()) == 1


def test_transitions_by_id_chiave_id_e_rinomina(repo):
    _tsk(repo, "EP-001-a/US-1/AA-TSK-7-vecchio.md", "todo")
    _commit(repo, "a", "2026-10-01")
    _git(repo, "mv", "management/kanban/EP-001-a/US-1/AA-TSK-7-vecchio.md",
         "management/kanban/EP-001-a/US-1/AA-TSK-7-nuovo.md")
    _tsk(repo, "EP-001-a/US-1/AA-TSK-7-nuovo.md", "done")
    _commit(repo, "b", "2026-10-03")
    per_path = kh.transitions(["management/kanban"], root=repo)
    per_id = kh.transitions_by_id(["management/kanban"], root=repo)
    assert list(per_path) == ["management/kanban/EP-001-a/US-1/AA-TSK-7-nuovo.md"]
    assert list(per_id) == ["AA-TSK-7"]
    assert [e[0] for e in per_id["AA-TSK-7"]] == ["todo", "done"]
