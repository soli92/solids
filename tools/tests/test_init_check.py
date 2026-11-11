"""init_check: perimetro per segmenti, FAIL senza PyYAML, stdout UTF-8 (ritorno dalla derivata)."""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path
from unittest import mock

_P = Path(__file__).resolve().parents[1] / "env" / "init_check.py"
_spec = importlib.util.spec_from_file_location("init_check", str(_P))
ic = importlib.util.module_from_spec(_spec)
sys.modules["init_check"] = ic
_spec.loader.exec_module(ic)


def test_same_or_nested_non_confonde_prefissi():
    assert ic._same_or_nested("code_repos/app", "code_repos/app")
    assert ic._same_or_nested("code_repos/app/sub", "code_repos/app")
    assert ic._same_or_nested("code_repos/app", "code_repos/app/sub/")
    assert not ic._same_or_nested("code_repos/app-test", "code_repos/app")
    assert not ic._same_or_nested("code_repos/app", "code_repos/app-test")


def test_senza_pyyaml_il_blocco_environment_e_fail(tmp_path, capsys):
    (tmp_path / "factory.config.yaml").write_text("environment:\n  env_files: [.env]\n")
    with mock.patch.object(ic, "_has_pyyaml", return_value=False), \
            mock.patch.object(ic, "_load_yaml_simple", return_value={"environment": {"env_files": [".env"]}}):
        ic.main(["--root", str(tmp_path), "--json"])
    out = capsys.readouterr().out
    assert "environment (config)" in out and "PyYAML" in out and '"FAIL"' in out


def test_main_riconfigura_lo_stream_in_utf8(tmp_path):
    class Fake(io.StringIO):
        reconfigured = None

        def reconfigure(self, **kw):
            Fake.reconfigured = kw

    f = Fake()
    with mock.patch.object(sys, "stdout", f):
        ic.main(["--root", str(tmp_path), "--json"])
    assert Fake.reconfigured == {"encoding": "utf-8", "errors": "replace"}
