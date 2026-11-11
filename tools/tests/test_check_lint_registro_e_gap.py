"""Check 4bb (log append-only), 4bc (chiusure dei gap verificate) e 4bd (gaps.md append-only): advisory, mai bloccanti."""
import os
import shutil
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
LINT = os.path.normpath(os.path.join(QUI, '..', 'lint'))
TESTA = b'---\ntype: wiki-log\n---\n\n'
E1 = b'## 2026-10-01 10:00 \xe2\x80\x94 prima\n\ntesto uno\n\n'
E2 = b'## 2026-10-02 10:00 \xe2\x80\x94 seconda\n\ntesto due\n\n'


def run(cwd, *a):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def test_4bb_segnala_riga_tolta_ma_non_blocca():
    r = tempfile.mkdtemp(prefix='4bb-')
    try:
        os.makedirs(os.path.join(r, 'wiki'))
        log = os.path.join(r, 'wiki', 'log.md')
        for c in (('init', '-q'), ('config', 'user.email', 't@t'), ('config', 'user.name', 't')):
            run(r, 'git', *c)
        open(log, 'wb').write(TESTA + E1 + E2)
        run(r, 'git', 'add', '.')
        run(r, 'git', 'commit', '-qm', 'base')
        script = os.path.join(LINT, 'check-log-append-guard.py')
        open(log, 'wb').write(TESTA + E2)
        run(r, 'git', 'commit', '-qam', 'tronca')
        out = run(r, sys.executable, script, r)
        assert out.returncode == 0 and '[WARNING][log-righe-rimosse][4bb]' in out.stdout
        assert run(r, sys.executable, script, '--strict', r).returncode == 1
        open(log, 'wb').write(TESTA + E2 + E1)
        run(r, 'git', 'commit', '-qam', 'coda')
        assert '[4bb] OK' in run(r, sys.executable, script, r).stdout
    finally:
        shutil.rmtree(r, ignore_errors=True)


def test_4bc_chiusura_a_parole_e_ok_con_fonte():
    r = tempfile.mkdtemp(prefix='4bc-')
    try:
        os.makedirs(os.path.join(r, 'wiki'))
        os.makedirs(os.path.join(r, 'raw'))
        open(os.path.join(r, 'raw', 'f.md'), 'w').write('f\n')
        open(os.path.join(r, 'wiki', 'p.md'), 'w').write('testo [^src: raw/f.md]\n')
        open(os.path.join(r, 'wiki', 'gaps.md'), 'w').write(
            "- [x] **G-A-1** chiuso\n  **Risolto:** 2026-10-15 — [[p]]\n"
            "- [x] **G-A-2** chiuso a parole\n  **Risolto:** 2026-10-15 — fatto\n")
        script = os.path.join(LINT, 'check-gap-closures.py')
        out = run(r, sys.executable, script, r)
        assert out.returncode == 0 and '[WARNING][gap-chiuso-non-verificato][4bc]' in out.stdout
        assert 'G-A-2' in out.stdout and 'G-A-1' not in out.stdout
        assert run(r, sys.executable, script, '--strict', r).returncode == 1
    finally:
        shutil.rmtree(r, ignore_errors=True)


def test_4bd_segnala_riga_gap_tolta_ma_non_blocca():
    r = tempfile.mkdtemp(prefix='4bd-')
    try:
        os.makedirs(os.path.join(r, 'wiki'))
        gaps = os.path.join(r, 'wiki', 'gaps.md')
        for c in (('init', '-q'), ('config', 'user.email', 't@t'), ('config', 'user.name', 't')):
            run(r, 'git', *c)
        base = b'# Gaps\n\n## 2026-10-01\n\n- [ ] **G-1** - primo\n- [ ] **G-2** - secondo\n'
        open(gaps, 'wb').write(base)
        run(r, 'git', 'add', '.')
        run(r, 'git', 'commit', '-qm', 'base')
        script = os.path.join(LINT, 'check-gaps-append-guard.py')
        open(gaps, 'wb').write(base.replace(b'- [ ] **G-1** - primo\n', b''))
        run(r, 'git', 'commit', '-qam', 'tronca')
        out = run(r, sys.executable, script, r)
        assert out.returncode == 0 and '[WARNING][gaps-righe-rimosse][4bd]' in out.stdout
        assert run(r, sys.executable, script, '--strict', r).returncode == 1
        open(gaps, 'wb').write(base.replace(b'- [ ] **G-1** - primo\n', b'') + b'- [ ] **G-3** - terzo\n')
        run(r, 'git', 'commit', '-qam', 'coda')
        assert '[4bd] OK' in run(r, sys.executable, script, r).stdout
    finally:
        shutil.rmtree(r, ignore_errors=True)
