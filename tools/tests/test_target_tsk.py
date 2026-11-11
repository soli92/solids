"""Check 4j: TSK aperti degli agenti senza un repository risolvibile (tools/lint/check_target_tsk.py).

Ogni test costruisce una radice minima in tmp_path; il check gira come sottoprocesso con --json.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LINT = Path(__file__).resolve().parents[1] / "lint"

CFG = """routing:
  be: agent
  fe: agent
  qa: agent
  db: human

code_paths:
  - name: app
    path: code_repos/app
    kind: code_path
  - name: svc-a
    path: code_repos/be/svc-a
    layers: [be]
  - name: svc-b
    path: code_repos/be/svc-b
    layers: [be]
  - name: unico-qa
    path: code_repos/test-repo
    layers: [qa]

lint:
  kanban:
    tsk_target: warning
    tsk_target_gitmodules: true
"""
GITMODULES = """[submodule "code_repos/app"]
\tpath = code_repos/app
[submodule "code_repos/servizi/altro"]
\tpath = code_repos/servizi/altro
"""


def _root(tmp_path, cfg=CFG):
    (tmp_path / "factory.config.yaml").write_text(cfg)
    (tmp_path / ".gitmodules").write_text(GITMODULES)
    return tmp_path


def _tsk(root: Path, tid="XX-TSK-001", **fm) -> None:
    d = root / "management" / "kanban" / "XX-EP-001" / "XX-US-001"
    d.mkdir(parents=True, exist_ok=True)
    base = dict(layer="fe", consumer="agent", status="todo", priority="P1")
    base.update(fm)
    righe = "".join(f"{k}: {v}\n" for k, v in base.items())
    (d / f"{tid}.md").write_text(f"---\nid: {tid}\n{righe}---\n\n# {tid}\n")


def _run(root: Path, *args: str):
    r = subprocess.run([sys.executable, str(LINT / "check_target_tsk.py"), "--root", str(root), "--json", *args],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    return json.loads(r.stdout)


def _codici(root):
    return [f["codice"] for f in _run(root)["findings"]]


def test_code_path_su_submodule_risolve_senza_target(tmp_path):
    root = _root(tmp_path)
    _tsk(root, code_path="code_repos/servizi/altro", layer="be")
    _tsk(root, "XX-TSK-002", code_path='"code_repos/app/src/lib"')
    out = _run(root)
    assert out["findings"] == []
    assert out["stats"]["risolti"] == 2


def test_code_path_della_factory_risolve(tmp_path):
    root = _root(tmp_path)
    _tsk(root, code_path=".", layer="qa")
    _tsk(root, "XX-TSK-002", code_path="tests/e2e/specs", layer="qa")
    assert _codici(root) == []


def test_code_path_su_voce_di_code_paths_risolve(tmp_path):
    root = _root(tmp_path)
    _tsk(root, code_path="code_repos/be/svc-a/", layer="be")
    assert _codici(root) == []


def test_code_path_sotto_code_repos_non_dichiarato(tmp_path):
    root = _root(tmp_path)
    _tsk(root, code_path="code_repos/inesistente", layer="be")
    assert _codici(root) == ["code-path-senza-repo"]


def test_code_path_assoluto(tmp_path):
    root = _root(tmp_path)
    _tsk(root, code_path="/Users/qualcuno/repo/tests", layer="qa")
    assert _codici(root) == ["code-path-assoluto"]


def test_senza_campi_con_due_voci_per_il_layer_e_ambiguo(tmp_path):
    root = _root(tmp_path)
    _tsk(root, layer="be")
    f = _run(root)["findings"]
    assert [x["codice"] for x in f] == ["target-ambiguo"]
    assert "svc-a" in f[0]["messaggio"] and "svc-b" in f[0]["messaggio"]
    assert f[0]["sev"] == "WARNING"


def test_senza_campi_con_una_voce_per_il_layer_risolve(tmp_path):
    root = _root(tmp_path)
    _tsk(root, layer="qa")
    assert _codici(root) == []


def test_senza_campi_e_senza_voci_per_il_layer(tmp_path):
    root = _root(tmp_path)
    _tsk(root, layer="fe")
    assert _codici(root) == ["senza-repo"]


def test_target_valido_e_target_sconosciuto(tmp_path):
    root = _root(tmp_path)
    _tsk(root, layer="be", target="svc-b")
    _tsk(root, "XX-TSK-002", layer="be", target="svc-z")
    assert _codici(root) == ["target-sconosciuto"]


def test_target_su_voce_senza_layers_risolve_e_con_layers_diversi_no(tmp_path):
    root = _root(tmp_path)
    _tsk(root, layer="fe", target="app")
    _tsk(root, "XX-TSK-002", layer="fe", target="svc-a")
    assert _codici(root) == ["target-layer"]


def test_target_prevale_su_code_path(tmp_path):
    root = _root(tmp_path)
    _tsk(root, layer="be", target="svc-a", code_path="/assoluto/ignorato")
    assert _codici(root) == []


def test_esclusi_chiusi_umani_e_layer_non_agent(tmp_path):
    root = _root(tmp_path)
    _tsk(root, "XX-TSK-001", layer="fe", status="done")
    _tsk(root, "XX-TSK-002", layer="fe", status="deferred")
    _tsk(root, "XX-TSK-003", layer="fe", consumer="human")
    _tsk(root, "XX-TSK-004", layer="db")
    _tsk(root, "XX-TSK-005", layer="tooling")
    out = _run(root)
    assert out["findings"] == []
    assert out["stats"]["soggetti"] == 0


def test_layer_con_segmento(tmp_path):
    root = _root(tmp_path)
    _tsk(root, layer="fe/a11y")
    assert _codici(root) == ["senza-repo"]


def test_regola_spenta_per_default(tmp_path):
    root = _root(tmp_path, CFG.replace("    tsk_target: warning\n", ""))
    _tsk(root, layer="fe")
    out = _run(root)
    assert out["findings"] == []
    assert out["stats"]["attivo"] is False
    assert _run(root, "--severita", "error")["findings"][0]["sev"] == "ERROR"


def test_strict_esce_1_con_error(tmp_path):
    root = _root(tmp_path, CFG.replace("tsk_target: warning", "tsk_target: error"))
    _tsk(root, layer="fe")
    r = subprocess.run([sys.executable, str(LINT / "check_target_tsk.py"), "--root", str(root), "--strict"],
                       capture_output=True, text=True)
    assert r.returncode == 1


def test_gitmodules_opzionale_per_default(tmp_path):
    """Senza tsk_target_gitmodules un code_path sotto code_repos/ non richiede .gitmodules."""
    root = _root(tmp_path, CFG.replace("    tsk_target_gitmodules: true\n", ""))
    _tsk(root, code_path="code_repos/inesistente", layer="be")
    assert _codici(root) == []
