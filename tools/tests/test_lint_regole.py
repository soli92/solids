"""Regole parametriche del lint deterministico (blocco `lint:`, EP-072).

Una derivata con norme proprie (Check 3 sui soli aperti, campi consigliati come WARNING, layer per
segmento, orphan per raggiungibilita', ID locali nelle epiche) dichiara le regole invece di tenere
una copia degli script. A regole di default il comportamento e' quello del master.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

LINT = Path(__file__).resolve().parents[1] / "lint"
sys.path.insert(0, str(LINT))
import lint_comune as lc  # noqa: E402

REGOLE_DERIVATA = """
lint:
  kanban:
    scope: open
    required:
      US: [id, title, priority, status]
      TSK: [id, layer, consumer, priority, status]
    warning:
      US: [role, wiki_page]
      TSK: [estimate]
    layer_severity: warning
    layer_segment: true
    id_duplicate: false
    equivalents:
      estimate: [size]
    in_progress_needs_sprint: false
  wiki:
    orphan: reachability
    append_only_links: info
    date_fields: [updated, created, closed_at]
"""


def _tsk(root: Path, ep: str, us: str, tid: str, **fm) -> None:
    d = root / "management" / "kanban" / ep / us
    d.mkdir(parents=True, exist_ok=True)
    (root / "management" / "kanban" / ep / f"{ep}.md").write_text(
        f"---\nid: {ep}\ntitle: e\nstatus: in_progress\npriority: P1\nconfidence: high\n---\n\n| US | T |\n|---|---|\n| US-001 | locale |\n")
    (d / f"{us}.md").write_text(f"---\nid: {us}\ntitle: u\nrole: r\npriority: P1\nstatus: in_progress\nwiki_page: \"\"\nepic: {ep}\n---\n")
    righe = "".join(f"{k}: {v}\n" for k, v in fm.items())
    (d / f"{tid}.md").write_text(f"---\nid: {tid}\n{righe}---\n")


def _run(script: str, root: Path) -> list[dict]:
    r = subprocess.run([sys.executable, str(LINT / script), "--root", str(root), "--json"],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    return json.loads(r.stdout).get("findings", [])


def _factory(tmp: Path, regole: str = "") -> Path:
    (tmp / "factory.config.yaml").write_text("routing:\n  fe: agent\n  docs: agent\n" + regole)
    _tsk(tmp, "XX-EP-001", "XX-US-001", "XX-TSK-001", layer="fe/a11y", consumer="agent", priority="P1",
         size="S", status="todo")
    _tsk(tmp, "XX-EP-001", "XX-US-001", "XX-TSK-002", layer="zz", consumer="docs-dev", status="done")
    return tmp


def test_default_e_il_master(tmp_path):
    r = lc.regole_lint(tmp_path)
    assert r == lc.REGOLE_DEFAULT


def test_mappa_inline_rifiutata(tmp_path):
    (tmp_path / "factory.config.yaml").write_text("lint:\n  kanban:\n    equivalents: {estimate: [size]}\n")
    with pytest.raises(ValueError):
        lc.regole_lint(tmp_path)


def test_regole_della_derivata_sul_check_3(tmp_path):
    f = _run("check-kanban-integrity.py", _factory(tmp_path, REGOLE_DERIVATA))
    codici = {(x["sev"], x["codice"]) for x in f}
    assert ("ERROR", "missing-field") not in codici          # estimate: c'e' size, equivalente
    assert ("ERROR", "invalid-layer") not in codici          # fe/a11y → fe; il chiuso non si guarda
    assert ("ERROR", "invalid-consumer") not in codici       # docs-dev sta su un TSK chiuso
    assert not any(x["codice"] == "in-progress-senza-sprint" for x in f)


def test_default_sullo_stesso_kanban(tmp_path):
    f = _run("check-kanban-integrity.py", _factory(tmp_path))
    codici = {(x["sev"], x["codice"]) for x in f}
    assert ("ERROR", "invalid-layer") in codici and ("ERROR", "invalid-consumer") in codici


def test_id_locali_nelle_epiche_sono_info(tmp_path):
    f = _run("check-status-rollup.py", _factory(tmp_path, REGOLE_DERIVATA))
    assert not any(x["check"] == "4au.6" and x["sev"] == "WARNING" for x in f)
    assert any(x["check"] == "4au.6" and x["sev"] == "INFO" for x in f)


def test_sprint_stato_non_in_ultima_colonna(tmp_path):
    root = _factory(tmp_path)
    (root / "management" / "kanban" / "sprint.md").write_text(
        "| ID | tipo | stato | titolo |\n|---|---|---|---|\n| XX-TSK-002 | task | todo | descrizione lunga |\n")
    f = _run("check-status-rollup.py", root)
    assert any(x["check"] == "4au.5" and x["sev"] == "WARNING" for x in f)


def test_orphan_per_raggiungibilita_e_link_append_only(tmp_path):
    root = _factory(tmp_path, REGOLE_DERIVATA)
    w = root / "wiki"
    (w / "concepts").mkdir(parents=True)
    (w / "index.md").write_text("# Indice\n\n- [[hub]]\n")
    (w / "concepts" / "hub.md").write_text("---\nupdated: 2026-10-01\n---\n[[foglia]]\n")
    (w / "concepts" / "foglia.md").write_text("---\ncreated: 2020-01-01\nclosed_at: 2026-10-01\n---\nx\n")
    (w / "gaps.md").write_text("---\nupdated: 2026-10-01\n---\n[[rotto]]\n")
    f = _run("check-wiki-structure.py", root)
    assert not any(x["codice"] == "orphan" and "foglia" in x.get("path", "") for x in f)
    assert {x["sev"] for x in f if x["codice"] == "broken-link"} == {"INFO"}
    assert not any(x["codice"] == "staleness" and "foglia" in x.get("path", "") for x in f)


def test_check_locali_della_factory(tmp_path):
    """tools/lint/checks_locali.py: check della sola derivata, nel runner senza toccarne il codice."""
    (tmp_path / "tools" / "lint").mkdir(parents=True)
    (tmp_path / "tools" / "x").mkdir()
    (tmp_path / "tools" / "x" / "conta.py").write_text("print('- [WARNING] uno')\nprint('- [WARNING] due')\n")
    (tmp_path / "tools" / "x" / "rotto.py").write_text("raise SystemExit(1)\n")
    (tmp_path / "tools" / "lint" / "checks_locali.py").write_text(
        "CHECKS = [(('L1',), 'conta', 'tools/x/conta.py', []),\n"
        "          (('L2',), 'rotto', 'tools/x/rotto.py', ['--check'])]\n")
    r = subprocess.run([sys.executable, str(LINT / "run-deterministic.py"), "--root", str(tmp_path),
                        "--json", "--solo", "L1,L2"], capture_output=True, text=True)
    risultati = {x["check"]: x for x in json.loads(r.stdout)["risultati"]}
    assert risultati["L1"]["conteggi"]["WARNING"] == 2
    assert risultati["L1"]["comando"] == "python3 tools/x/conta.py"
    assert risultati["L2"]["conteggi"]["ERROR"] == 1  # solo exit code: resta un errore
    assert risultati["L2"]["comando"] == "python3 tools/x/rotto.py --check"


def test_sprint_soggetto_della_riga_e_freccia(tmp_path):
    """La riga descrive l'ID piu' specifico fra le celle-ID iniziali; dopo «→» vale il nuovo stato."""
    root = _factory(tmp_path)
    (root / "management" / "kanban" / "sprint.md").write_text(
        "| US | TSK | titolo | stato |\n|---|---|---|---|\n"
        "| XX-US-001 | XX-TSK-002 | figlio chiuso | done |\n"          # US in_progress: non e' lei
        "| XX-US-001 | titolo | XX-TSK-002 | in_progress |\n"         # riferimento dopo il titolo
        "| XX-TSK-001 | titolo | ~~done~~ → todo |\n")
    f = _run("check-status-rollup.py", root)
    assert [x for x in f if x["check"] == "4au.5"] == []


def test_campo_data_a_lista_vale_la_piu_recente():
    sys.path.insert(0, str(LINT))
    import importlib.util
    spec = importlib.util.spec_from_file_location("cws", LINT / "check-wiki-structure.py")
    cws = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cws)
    import datetime as dt
    fm = {"rotated_at": ["2026-09-25", "2026-10-07"], "created": "2025-01-01"}
    assert cws._data(fm, ("updated", "created", "rotated_at")) == dt.date(2026, 10, 7)


def test_archivi_del_log_esclusi_come_il_log(tmp_path):
    root = _factory(tmp_path)
    w = root / "wiki"
    w.mkdir(exist_ok=True)
    (w / "index.md").write_text("---\nupdated: 2026-10-01\n---\n")
    (w / "log.md").write_text("---\nid: log\n---\n")
    (w / "log-2026-10-08.md").write_text("---\ntype: wiki-log-archive\n---\n[[link-storico-rotto]]\n")
    f = _run("check-wiki-structure.py", root)
    assert not [x for x in f if "log-2026-10-08" in json.dumps(x)]
