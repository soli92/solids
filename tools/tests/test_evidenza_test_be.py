"""Check 4bh: TSK layer be chiusi senza evidenza di test (tools/lint/check_evidenza_test_be.py).

Ogni test costruisce un kanban minimo in tmp_path; il check gira come sottoprocesso con --json.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

LINT = Path(__file__).resolve().parents[1] / "lint"
RADICE = Path(__file__).resolve().parents[2]

ESITO_OK = """## Esito

Comando `pytest tests/be -q`, codice di uscita 0. 12 passati, 0 falliti, 0 saltati.
Report: reports/be-run.json. SHA dei test 1a2b3c4d5e, SHA del servizio 9f8e7d6c5b.
"""
CFG = """routing:
  be: agent
  qa: agent
  fe: agent
lint:
  kanban:
    scope: open
    be_test_evidence: warning
    be_test_evidence_consumers: [agent]
    be_test_evidence_since: 2026-11-09
"""


def _tsk(root: Path, tid: str, corpo: str = "", **fm) -> None:
    d = root / "management" / "kanban" / "XX-EP-001" / "XX-US-001"
    d.mkdir(parents=True, exist_ok=True)
    fm.setdefault("priority", "P1")
    righe = "".join(f"{k}: {v}\n" for k, v in fm.items())
    (d / f"{tid}.md").write_text(f"---\nid: {tid}\n{righe}---\n\n# {tid}\n\n{corpo}")


def _be(root, tid="XX-TSK-001", **extra):
    base = dict(layer="be", consumer="agent", status="done", closed_at="2026-11-10", updated="2026-11-10")
    base.update(extra)
    _tsk(root, tid, **base)


def _qa(root, tid="XX-TSK-002", dep="XX-TSK-001", corpo=ESITO_OK, **extra):
    base = dict(layer="qa", consumer="agent", status="done", depends_on=f"[{dep}]")
    base.update(extra)
    _tsk(root, tid, corpo, **base)


def _run(root: Path, *args: str):
    r = subprocess.run([sys.executable, str(LINT / "check_evidenza_test_be.py"), "--root", str(root),
                        "--json", *args], capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    return json.loads(r.stdout)


def _root(tmp_path, cfg=CFG):
    (tmp_path / "factory.config.yaml").write_text(cfg)
    return tmp_path


def test_segnala_be_done_senza_tsk_qa(tmp_path):
    root = _root(tmp_path)
    _be(root)
    out = _run(root)
    assert [f["codice"] for f in out["findings"]] == ["be-senza-tsk-qa"]
    assert out["findings"][0]["sev"] == "WARNING"


def test_non_segnala_be_con_evidenza_completa(tmp_path):
    root = _root(tmp_path)
    _be(root)
    _qa(root)
    out = _run(root)
    assert out["findings"] == []
    assert out["stats"]["con_evidenza"] == 1


def test_non_segnala_layer_fe(tmp_path):
    root = _root(tmp_path)
    _tsk(root, "XX-TSK-001", layer="fe", consumer="agent", status="done", closed_at="2026-11-10")
    assert _run(root)["findings"] == []


def test_tsk_qa_non_chiuso(tmp_path):
    root = _root(tmp_path)
    _be(root)
    _qa(root, status="todo")
    assert [f["codice"] for f in _run(root)["findings"]] == ["be-tsk-qa-aperto"]


def test_esito_incompleto_elenca_cio_che_manca(tmp_path):
    root = _root(tmp_path)
    _be(root)
    _qa(root, corpo="## Esito\n\nHo eseguito `pytest`, tutto verde.\n")
    f = _run(root)["findings"]
    assert [x["codice"] for x in f] == ["be-evidenza-incompleta"]
    for voce in ("codice di uscita", "test saltati a zero", "report", "SHA"):
        assert voce in f[0]["messaggio"]
    assert "comando" not in f[0]["messaggio"].split("non riporta:")[1]


def test_senza_sezione_esito(tmp_path):
    root = _root(tmp_path)
    _be(root)
    _qa(root, corpo="Nessun esito.\n")
    assert "sezione" in _run(root)["findings"][0]["messaggio"]


def test_saltati_diversi_da_zero_non_valgono(tmp_path):
    root = _root(tmp_path)
    _be(root)
    corpo = ESITO_OK.replace("0 saltati", "5 saltati")
    _qa(root, corpo=corpo)
    assert "test saltati a zero" in _run(root)["findings"][0]["messaggio"]


def test_eccezioni(tmp_path):
    root = _root(tmp_path)
    _be(root, "XX-TSK-010", status="cancelled")
    _be(root, "XX-TSK-011", status="superseded")
    _be(root, "XX-TSK-012", be_test_evidence="na", be_test_evidence_reason="solo documentazione")
    _be(root, "XX-TSK-014", test_evidence="na")
    _be(root, "XX-TSK-013", closed_at="2026-11-08", updated="2026-11-08")
    out = _run(root)
    # test_evidence (prova dell'esecuzione del caso) non esenta: XX-TSK-014 resta soggetto
    assert [f["codice"] for f in out["findings"]] == ["be-senza-tsk-qa"]
    assert "XX-TSK-014" in out["findings"][0]["messaggio"]
    assert out["stats"]["esenti_na"] == 1 and out["stats"]["esenti_data"] == 1


def test_na_senza_motivo_non_esenta(tmp_path):
    root = _root(tmp_path)
    _be(root, be_test_evidence="na")
    _be(root, "XX-TSK-003", be_test_evidence="na", be_test_evidence_reason="''")
    out = _run(root)
    codici = sorted(f["codice"] for f in out["findings"])
    assert codici == ["be-na-senza-motivo", "be-na-senza-motivo", "be-senza-tsk-qa", "be-senza-tsk-qa"]
    assert out["stats"]["esenti_na"] == 0


def test_tsk_umano_esente_di_default_e_soggetto_se_configurato(tmp_path):
    root = _root(tmp_path)
    _be(root, consumer="human")
    assert _run(root)["findings"] == []
    (root / "factory.config.yaml").write_text(CFG.replace("[agent]", "[agent, human]"))
    assert [f["codice"] for f in _run(root)["findings"]] == ["be-senza-tsk-qa"]


def test_severita_error_e_strict(tmp_path):
    root = _root(tmp_path, CFG.replace("be_test_evidence: warning", "be_test_evidence: error"))
    _be(root)
    assert _run(root)["findings"][0]["sev"] == "ERROR"
    r = subprocess.run([sys.executable, str(LINT / "check_evidenza_test_be.py"), "--root", str(root),
                        "--strict"], capture_output=True, text=True)
    assert r.returncode == 1


def test_spento_di_default(tmp_path):
    root = _root(tmp_path, "routing:\n  be: agent\n")
    _be(root)
    out = _run(root)
    assert out["findings"] == [] and out["stats"]["attivo"] is False


def test_registrato_nel_runner_deterministico():
    spec = importlib.util.spec_from_file_location("run_det_t", LINT / "run-deterministic.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert any("4bh" in ids for ids, *_ in mod.CHECKS)
    # sul kanban reale (storico incluso) la configurazione di default non segnala nulla
    out = _run(RADICE)
    assert out["findings"] == []
