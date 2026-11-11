"""
Test di tools/lint/check-config-schema-coverage.py (TSK-729).

Fixture:
  - config con chiavi coperte dallo schema → 0 undeclared, exit 0
  - config con chiave sconosciuta → 1 undeclared, exit 1
  - config vuota → 0 undeclared
  - schema assente → 0 chiavi schema, qualsiasi config ha tutte chiavi undeclared
  - sul repo reale → 0 undeclared (AC di chiusura TSK-729)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "tools" / "lint" / "check-config-schema-coverage.py"

_spec = importlib.util.spec_from_file_location("csc", _SCRIPT)
csc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(csc)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_factory(tmp_path: Path, config_text: str, schema_props: dict | None = None) -> Path:
    root = tmp_path / "factory"
    root.mkdir()
    (root / "factory.config.yaml").write_text(config_text, encoding="utf-8")
    if schema_props is not None:
        (root / "schemas").mkdir()
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": schema_props,
        }
        (root / "schemas" / "factory.config.schema.json").write_text(
            json.dumps(schema), encoding="utf-8"
        )
    return root


# ---------------------------------------------------------------------------
# test: chiavi coperte
# ---------------------------------------------------------------------------

def test_all_covered_no_undeclared(tmp_path):
    root = _make_factory(
        tmp_path,
        "pattern_version: '2.43'\nmodels:\n  routing: {}\n",
        {"pattern_version": {"type": "string"}, "models": {"type": "object"}},
    )
    result = csc.run(root)
    assert result["undeclared"] == []


def test_unknown_key_is_undeclared(tmp_path):
    root = _make_factory(
        tmp_path,
        "pattern_version: '2.43'\nunknown_capability:\n  enabled: false\n",
        {"pattern_version": {"type": "string"}},
    )
    result = csc.run(root)
    assert "unknown_capability" in result["undeclared"]


def test_empty_config_no_undeclared(tmp_path):
    root = _make_factory(tmp_path, "# empty config\n", {"pattern_version": {"type": "string"}})
    result = csc.run(root)
    assert result["undeclared"] == []


def test_schema_absent_all_config_keys_are_undeclared(tmp_path):
    root = tmp_path / "nf"
    root.mkdir()
    (root / "factory.config.yaml").write_text("pattern_version: '2.43'\n")
    # nessun schemas/
    result = csc.run(root)
    # schema_keys e' vuoto → config_key pattern_version e' undeclared
    assert "pattern_version" in result["undeclared"]


def test_schema_only_keys_are_info_not_error(tmp_path):
    root = _make_factory(
        tmp_path,
        "pattern_version: '2.43'\n",
        {
            "pattern_version": {"type": "string"},
            "models":          {"type": "object"},
            "extra_schema":    {"type": "object"},
        },
    )
    result = csc.run(root)
    assert result["undeclared"] == []
    assert "models" in result["schema_only"]
    assert "extra_schema" in result["schema_only"]


def test_comments_not_parsed_as_keys(tmp_path):
    root = _make_factory(
        tmp_path,
        "# not_a_key: value\npattern_version: '2.43'\n",
        {"pattern_version": {"type": "string"}},
    )
    result = csc.run(root)
    assert "not_a_key" not in result["config_keys"]
    assert result["undeclared"] == []


def test_json_output(tmp_path):
    root = _make_factory(
        tmp_path,
        "pattern_version: '2.43'\nextra_key:\n  x: 1\n",
        {"pattern_version": {"type": "string"}},
    )
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(root), "--json"],
        capture_output=True, text=True,
    )
    data = json.loads(r.stdout)
    assert "extra_key" in data["undeclared"]
    assert data["exit_code"] == 1
    assert r.returncode == 1


def test_exit_0_when_no_undeclared(tmp_path):
    root = _make_factory(
        tmp_path,
        "pattern_version: '2.43'\n",
        {"pattern_version": {"type": "string"}},
    )
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(root)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "OK" in r.stdout


# ---------------------------------------------------------------------------
# test sul repo reale — AC di chiusura TSK-729
# ---------------------------------------------------------------------------

def test_repo_real_zero_undeclared():
    """Il repo reale non ha chiavi undeclared nello schema."""
    result = csc.run(_REPO_ROOT)
    assert result["undeclared"] == [], (
        f"Chiavi non dichiarate nello schema: {result['undeclared']}"
    )


def test_chiavi_locali_dichiarate_sono_info(tmp_path):
    """EP-072: una chiave propria della factory elencata in schema_local_keys non e' ERROR."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ccsc_local", Path(__file__).resolve().parents[1] / "lint" / "check-config-schema-coverage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "factory.config.schema.json").write_text('{"properties": {"a": {}, "schema_local_keys": {}}}')
    for testo in ("a: 1\nmia: 2\naltra: 3\nschema_local_keys: [mia]\n",
                  "a: 1\nmia: 2\naltra: 3\nschema_local_keys:\n  - mia   # verticale\n"):
        (tmp_path / "factory.config.yaml").write_text(testo)
        r = mod.run(tmp_path)
        assert r["declared_local"] == ["mia"] and r["undeclared"] == ["altra"]
