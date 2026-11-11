"""Test di tools/cypress/run_report.py: passi di merge e profili, senza Cypress.

Coprono il JUnit unito, la copia degli screenshot, esito.md, la scelta del profilo di
reporter (generic di default, profilo custom da modulo) e il rifiuto di una cartella di
report dentro il repo di test. Il lancio reale richiede il node_modules del repo di test e
si prova a mano.

Si eseguono con pytest oppure direttamente: python3 tools/tests/test_cypress_run_report.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

QUI = Path(__file__).resolve().parent
SCRIPT = QUI.parent / "cypress" / "run_report.py"
spec = importlib.util.spec_from_file_location("run_report", SCRIPT)
rr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rr)

JUNIT_A = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="Mocha Tests" time="1.5" tests="2" failures="1">
  <testsuite name="Root Suite" tests="0" file="cypress/e2e/A.cy.js" failures="0" time="0"/>
  <testsuite name="Area A" tests="2" failures="1" time="1.5">
    <testcase name="ok" time="0.5"/>
    <testcase name="ko" time="1.0"><failure message="atteso 1,   trovato 2">x</failure></testcase>
  </testsuite>
</testsuites>"""
JUNIT_B = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="Mocha Tests" time="0.25" tests="1" failures="0">
  <testsuite name="Area B" tests="1" failures="0" skipped="0" time="0.25">
    <testcase name="ok" time="0.25"/>
  </testsuite>
</testsuites>"""

CUSTOM = """
import sys
sys.path.insert(0, %r)
import run_report as rr

class P(rr.ReporterProfile):
    name = "custom-prova"
    def cypress_args(self, run_dir):
        return ["--reporter", "spec"]
    def finalize(self, test_path, run_dir, stamp, dry):
        return ["- Extra del profilo custom"]

PROFILE = P()
"""


def _run_dir(tmp: Path) -> Path:
    run = tmp / "run-20261110_120000"
    (run / "junit").mkdir(parents=True)
    (run / "junit" / "junit-report-a.xml").write_text(JUNIT_A, encoding="utf-8")
    (run / "junit" / "junit-report-b.xml").write_text(JUNIT_B, encoding="utf-8")
    return run


def test_merge_junit_somma_le_testsuite():
    with tempfile.TemporaryDirectory() as t:
        run = _run_dir(Path(t))
        out = rr.merge_junit(run)
        assert out == run / "html_report" / "junit-report.xml"
        root = ET.parse(out).getroot()
        assert root.tag == "testsuites"
        assert (root.get("tests"), root.get("failures"), root.get("time")) == ("3", "1", "1.750")
        assert [s.get("name") for s in root.findall("testsuite")] == ["Root Suite", "Area A", "Area B"]
        assert root.find("testsuite").get("file") == "cypress/e2e/A.cy.js"


def test_screenshot_ed_esito_generic():
    with tempfile.TemporaryDirectory() as t:
        run = _run_dir(Path(t))
        assert rr.copy_screenshots(run) == 0
        shot = run / "screenshots" / "A.cy.js" / "ko (failed).png"
        shot.parent.mkdir(parents=True)
        shot.write_bytes(b"png")
        assert rr.copy_screenshots(run) == 1
        assert (run / "html_report" / "screenshots" / "A.cy.js" / "ko (failed).png").exists()

        junit = rr.merge_junit(run)
        esito = rr.write_esito(run, "TSK-0001", ["a.cy.js"], junit, 1, 1,
                               rr.PROFILES["generic"], []).read_text(encoding="utf-8")
        assert "| 3 | 1 | 0 | 1.750 |" in esito
        assert "- Area A / ko: atteso 1, trovato 2" in esito
        assert "html_report/junit-report.xml" in esito
        assert "Profilo di reporter: `generic`" in esito


def test_profilo_generic_usa_il_reporter_integrato():
    args = rr.PROFILES["generic"].cypress_args(Path("/x/run"))
    assert args[:2] == ["--reporter", "junit"]
    assert "mochaFile=" in args[3] and "junit-report-[hash].xml" in args[3]
    assert rr.PROFILES["generic"].required_tools == ()


def test_profilo_default_e_sconosciuto():
    assert rr.choose_profile(None, None, None).name == "generic"
    r = subprocess.run([sys.executable, str(SCRIPT), "--tsk", "TSK-1", "--test-path", ".",
                        "--reporter", "inesistente", "--spec", "x"], capture_output=True, text=True)
    assert r.returncode == 2 and "inesistente" in r.stderr


def test_profilo_custom_da_modulo():
    with tempfile.TemporaryDirectory() as t:
        mod = Path(t) / "profilo.py"
        mod.write_text(CUSTOM % str(SCRIPT.parent), encoding="utf-8")
        profile = rr.choose_profile(None, str(mod), None)
        assert profile.name == "custom-prova"
        assert profile.cypress_args(Path("/x")) == ["--reporter", "spec"]
        assert profile.finalize(Path("/x"), Path("/y"), "s", True) == ["- Extra del profilo custom"]


def test_modulo_senza_profile_rifiutato():
    with tempfile.TemporaryDirectory() as t:
        mod = Path(t) / "vuoto.py"
        mod.write_text("X = 1\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPT), "--tsk", "TSK-1", "--test-path", t,
                            "--reporter-module", str(mod), "--spec", "x"], capture_output=True, text=True)
        assert r.returncode == 2 and "PROFILE" in r.stderr


def test_report_dentro_il_repo_di_test_rifiutato():
    with tempfile.TemporaryDirectory() as t:
        repo = Path(t) / "repo"
        repo.mkdir()
        (repo / "cypress.config.js").write_text("module.exports = {};")
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--tsk", "TSK-0001", "--test-path", str(repo),
             "--out-root", str(repo / "out"), "--spec", "x.cy.js", "--dry-run"],
            capture_output=True, text=True,
        )
        assert r.returncode == 2
        assert "repo di test" in r.stderr


def test_config_assente_e_tsk_non_valido():
    with tempfile.TemporaryDirectory() as t:
        r = subprocess.run([sys.executable, str(SCRIPT), "--tsk", "TSK-1", "--test-path", t, "--spec", "x"],
                           capture_output=True, text=True)
        assert r.returncode == 2 and "config di Cypress" in r.stderr
    r = subprocess.run([sys.executable, str(SCRIPT), "--tsk", "boh", "--spec", "x"],
                       capture_output=True, text=True)
    assert r.returncode == 2


def test_tsk_con_namespace_accettato():
    assert rr.TSK_RE.match("TSK-873") and rr.TSK_RE.match("XX-TSK-0268")
    assert not rr.TSK_RE.match("US-12")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
