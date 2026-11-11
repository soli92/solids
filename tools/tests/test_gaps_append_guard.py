"""gaps_append_guard.py — wiki/gaps.md append-only, solo avviso."""
import importlib.util
import os
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(QUI, '..'))
SCRIPT = os.path.join(TOOLS, 'wiki', 'gaps_append_guard.py')
spec = importlib.util.spec_from_file_location('gaps_append_guard', SCRIPT)
gag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gag)

TESTA = b'# Gaps\n\n> nota di testa\n\n## 2026-10-01\n\n'
A = b'- [ ] **G-1** - primo gap\n'
A_X = b'- [x] **G-1** - primo gap\n'
B = b'- [ ] **G-2** - secondo\n'
AGG = b'  **Aggiornamento 2026-10-02:** altro dato\n'
RIS = b'  **Risolto:** 2026-10-03 - evidenza\n'


def chk(old, new):
    return gag.check_texts(old, new)


def test_append_ok():
    assert chk(TESTA + A, TESTA + A + B) == []


def test_checkbox_ok():
    assert chk(TESTA + A, TESTA + A.replace(b'[ ]', b'[x]')) == []


def test_checkbox_con_risolto_ok():
    assert chk(TESTA + A + B, TESTA + A.replace(b'[ ]', b'[x]') + RIS + B) == []


def test_d1_sostituzione_ok():
    old = TESTA + A + AGG + B
    new = TESTA + A.replace(b'[ ]', b'[x]') + RIS + B
    assert chk(old, new) == []


def test_aggiornamento_senza_risolto_avviso():
    assert chk(TESTA + A + AGG + B, TESTA + A + B) == [AGG.rstrip(b'\n')]


def test_risolto_in_altro_blocco_avviso():
    old = TESTA + A + AGG + B
    new = TESTA + A + B + RIS
    assert chk(old, new) == [AGG.rstrip(b'\n')]


def test_riga_riscritta_avviso():
    assert chk(TESTA + A, TESTA + A.replace(b'primo', b'PRIMO')) == [A.replace(b'[ ]', b'[x]').rstrip(b'\n')]


def test_riga_di_testa_non_esente():
    assert chk(TESTA + A, TESTA.replace(b'nota di testa', b'altra') + A) == [b'> nota di testa']


def test_log_guard_invariato_su_testa():
    lag = gag.lag
    assert lag.removed_without_archive(TESTA + A, TESTA.replace(b'nota di testa', b'altra') + A, []) == []


def test_cli_exit_zero_e_strict():
    r = subprocess.run([sys.executable, SCRIPT, '--storia', '5'], cwd=TOOLS, capture_output=True, text=True)
    assert r.returncode == 0 and 'commit esaminati' in r.stdout
