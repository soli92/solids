"""Test di tools/lint/fact_loss.py (EP-076 TSK-807)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("fact_loss", _REPO_ROOT / "tools" / "lint" / "fact_loss.py")
fl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fl)

FATTI = [
    {"id": "F1", "testo": "Il limite è 20 parole", "ancore": ["20"]},
    {"id": "F2", "testo": "Lo standard è l'Issue 9", "ancore": ["Issue 9"]},
    {"id": "F3", "testo": "Lo usa l'industria ferroviaria", "ancore": []},
    {"id": "F4", "testo": "Nato nel 1979", "ancore": ["1979"]},
]

RISCRITTURA = """La frase ha al massimo 20 parole.

## Omesso

- L'anno di nascita, 1979.
"""


def scrivi(tmp_path, verdetti, testo=RISCRITTURA):
    (tmp_path / "facts.json").write_text(json.dumps({"fatti": FATTI}), encoding="utf-8")
    (tmp_path / "a.md").write_text(testo, encoding="utf-8")
    (tmp_path / "verdicts.json").write_text(
        json.dumps({"varianti": {"A": {"file": "a.md", "verdetti": verdetti}}}), encoding="utf-8")
    return str(tmp_path / "facts.json"), str(tmp_path / "verdicts.json")


def test_ritenzione_conflitti_e_omissioni(tmp_path):
    f, v = scrivi(tmp_path, {"F1": "presente", "F2": "presente", "F3": "parziale", "F4": "assente"})
    e = fl.misura(f, v, 0.10)["A"]
    assert e["ritenzione"] == 0.625            # (1 + 1 + 0.5 + 0) / 4
    assert e["perdita"] == 0.375
    assert e["entro_soglia"] is False
    assert e["conflitti"] == [{"id": "F2", "ancore_mancanti": ["Issue 9"]}]
    assert e["omissioni"] == {"dichiarata": 1, "silenziosa": 0, "non determinabile": 1}
    assert e["ancore_complete"] == 0.333       # F1 si, F2 no, F4 solo in Omesso: non conta


def test_ancora_solo_in_omesso_non_vale_come_presente(tmp_path):
    f, v = scrivi(tmp_path, {"F1": "presente", "F2": "assente", "F3": "presente", "F4": "presente"})
    e = fl.misura(f, v, 0.5)["A"]
    assert {"id": "F4", "ancore_mancanti": ["1979"]} in e["conflitti"]
    assert e["omissioni"]["silenziosa"] == 1   # F2: ha ancore, nessuna in Omesso


def test_senza_sezione_omesso(tmp_path):
    f, v = scrivi(tmp_path, dict.fromkeys(["F1", "F2", "F3", "F4"], "presente"),
                  testo="20 parole, Issue 9, 1979.")
    e = fl.misura(f, v, 0.10)["A"]
    assert e["sezione_omesso"] is False
    assert e["perdita"] == 0.0 and e["conflitti"] == []


def test_verdetti_mancanti_o_non_ammessi(tmp_path):
    f, v = scrivi(tmp_path, {"F1": "presente"})
    with pytest.raises(fl.InputNonValido, match="mancanti: F2, F3, F4"):
        fl.misura(f, v, 0.1)
    f, v = scrivi(tmp_path, dict.fromkeys(["F1", "F2", "F3", "F4"], "forse"))
    with pytest.raises(fl.InputNonValido, match="non ammessi: forse"):
        fl.misura(f, v, 0.1)


def test_ancora_con_simboli_riscritti_in_parole():
    corpo = fl.normalizza("RAG o LSP fanno il retrieval. Meno di 20 file.")
    assert fl.contiene(corpo, "RAG / LSP")
    assert fl.contiene(corpo, "<20 file")
    assert not fl.contiene(corpo, "Issue 9")
    assert not fl.contiene(corpo, "20 righe")


def test_dividi_omesso_fino_al_titolo_successivo():
    corpo, omesso = fl.dividi("A\n## Omesso\n- x\n## Altro\nB\n")
    assert "x" in omesso and "B" not in omesso
    assert "B" in corpo and "x" not in corpo


def test_cli_strict_e_input_errato(tmp_path, capsys):
    f, v = scrivi(tmp_path, {"F1": "presente", "F2": "presente", "F3": "parziale", "F4": "assente"})
    assert fl.main(["--facts", f, "--verdicts", v, "--root", str(tmp_path)]) == 0
    assert "SOPRA SOGLIA" in capsys.readouterr().out
    assert fl.main(["--facts", f, "--verdicts", v, "--strict", "--root", str(tmp_path)]) == 1
    assert fl.main(["--facts", f, "--verdicts", v, "--strict", "--soglia", "0.5",
                    "--root", str(tmp_path)]) == 0
    assert fl.main(["--facts", str(tmp_path / "manca.json"), "--verdicts", v]) == 2


def test_soglia_dalla_config_del_repo():
    assert fl.soglia_config(str(_REPO_ROOT)) == 0.10
