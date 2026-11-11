"""Gate di `pm_report.enabled` in run.py: a flag false si ferma prima di ogni passo."""
import json
import os
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
RUN_PY = os.path.join(os.path.dirname(QUI), 'run.py')
sys.path.insert(0, os.path.dirname(QUI))
from run import _pm_report_abilitato  # noqa: E402


def _factory(contenuto_config):
    root = tempfile.mkdtemp(prefix='coord-gate-')
    if contenuto_config is not None:
        with open(os.path.join(root, 'factory.config.yaml'), 'w', encoding='utf-8') as fh:
            fh.write(contenuto_config)
    return root


def test_flag_letto_dichiarato_o_assente():
    assert _pm_report_abilitato(_factory('pm_report:\n  enabled: true\n')) is True
    assert _pm_report_abilitato(_factory('pm_report:\n  enabled: false\n')) is False
    assert _pm_report_abilitato(_factory('altro: 1\n')) is None
    assert _pm_report_abilitato(_factory(None)) is None


def test_flag_false_ferma_run_senza_scrivere():
    root = _factory('pm_report:\n  enabled: false\n')
    config = os.path.join(root, 'config-x.json')
    with open(config, 'w', encoding='utf-8') as fh:
        json.dump({'factory_root': '.'}, fh)
    uscite = os.path.join(root, 'uscite')
    r = subprocess.run([sys.executable, RUN_PY, '--config', config, '--uscite', uscite],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert 'pm_report.enabled' in r.stdout and 'STOP' in r.stdout
    assert not os.path.exists(uscite)
