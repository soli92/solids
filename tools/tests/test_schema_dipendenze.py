"""Schema config: le regole HARD DEP valgono solo se il sotto-blocco c'e' (EP-072).

`if: {properties: {voice_channel: {properties: {wake_word: ...}}}}` senza `required` e' vero a
vuoto quando `wake_word` manca: `{voice_channel: {enabled: false}}`, config spenta valida,
violava tre regole. Rilevato validando la config di una derivata.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "factory.config.schema.json").read_text(encoding="utf-8"))
V = jsonschema.Draft202012Validator(SCHEMA)


def _errori(cfg):
    return [e.message for e in V.iter_errors(cfg)]


@pytest.mark.parametrize("cfg", [
    {"voice_channel": {"enabled": False}},
    {"compression": {"context": {"enabled": False}}},
    {"compression": {"output": {"enabled": False}}},
    {"code_quality": {"enabled": False}},
])
def test_blocco_spento_senza_sotto_blocchi_e_valido(cfg):
    assert _errori(cfg) == []


def test_sotto_flag_acceso_con_master_spento_resta_errore():
    assert _errori({"voice_channel": {"enabled": False, "wake_word": {"enabled": True}}})


def test_ogni_regola_if_dichiara_le_chiavi_che_legge():
    def ok(node):
        props = node.get("properties")
        if not isinstance(props, dict):
            return True
        return set(props) <= set(node.get("required", [])) and all(
            ok(v) for v in props.values() if isinstance(v, dict))
    assert all(ok(r["if"]) for r in SCHEMA["allOf"] if "if" in r)


def test_variabili_come_oggetti_ammesse():
    cfg = {"environment": {"variables": {"optional": ["A", {"name": "B", "tied_to_capability": "x"}]}}}
    assert _errori(cfg) == []


def test_config_del_master_valida():
    assert _errori(yaml.safe_load((ROOT / "factory.config.yaml").read_text(encoding="utf-8"))) == []
