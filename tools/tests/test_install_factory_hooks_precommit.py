"""Hook pre-commit opt-in della guardia del log (EP-077): flag di config e blocco reale su repo temporaneo."""
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(QUI, '..'))
sys.path.insert(0, os.path.join(TOOLS, 'vcs'))
spec = importlib.util.spec_from_file_location('ifh', os.path.join(TOOLS, 'vcs', 'install_factory_hooks.py'))
ifh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ifh)

TESTA = b'---\ntype: wiki-log\nupdated: 2026-10-01\n---\n\n'
E1 = b'## 2026-10-01 10:00 \xe2\x80\x94 prima\n\ntesto uno\n\n'
E2 = b'## 2026-10-02 10:00 \xe2\x80\x94 seconda\n\ntesto due\n\n'


def cfg(tmp, corpo):
    p = pathlib.Path(tmp)
    (p / 'factory.config.yaml').write_text(corpo)
    return p


def test_flag_spento_di_default_e_acceso_solo_con_true():
    d = tempfile.mkdtemp()
    try:
        assert ifh.log_guard_enabled(pathlib.Path(d)) is False            # nessun file
        assert ifh.log_guard_enabled(cfg(d, 'wiki_lint:\n  log_append_guard:\n    hook: false\n')) is False
        assert ifh.log_guard_enabled(cfg(d, 'wiki_lint:\n  semantic_check:\n    enabled: true\n')) is False
        assert ifh.log_guard_enabled(cfg(d, 'altro:\n  log_append_guard:\n    hook: true\n')) is False
        assert ifh.log_guard_enabled(cfg(d, 'wiki_lint:\n  log_append_guard:\n    hook: true  # si\n')) is True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_install_idempotente():
    d = tempfile.mkdtemp()
    try:
        hooks = pathlib.Path(d)
        assert ifh._install('pre-commit', ifh.PRE_COMMIT_HOOK, hooks, False, False) == 'installed'
        assert ifh._install('pre-commit', ifh.PRE_COMMIT_HOOK, hooks, False, False) == 'skipped'
        assert ifh._install('pre-commit', ifh.PRE_COMMIT_HOOK, pathlib.Path(d) / 'x', True, False) in ('skipped', 'conflict')
    finally:
        shutil.rmtree(d, ignore_errors=True)


def run(cwd, *a):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def test_hook_blocca_riga_tolta_e_lascia_passare_append():
    r = tempfile.mkdtemp(prefix='hook-log-')
    try:
        os.makedirs(os.path.join(r, 'tools', 'wiki'))
        os.makedirs(os.path.join(r, 'wiki'))
        shutil.copy(os.path.join(TOOLS, 'wiki', 'log_append_guard.py'), os.path.join(r, 'tools', 'wiki'))
        log = os.path.join(r, 'wiki', 'log.md')
        for c in (('init', '-q'), ('config', 'user.email', 't@t'), ('config', 'user.name', 't')):
            run(r, 'git', *c)
        open(log, 'wb').write(TESTA + E1 + E2)
        run(r, 'git', 'add', '.')
        run(r, 'git', 'commit', '-qm', 'base')
        ifh._install('pre-commit', ifh.PRE_COMMIT_HOOK, pathlib.Path(r, '.git', 'hooks'), False, False)

        open(log, 'wb').write(TESTA + E2)
        run(r, 'git', 'add', 'wiki/log.md')
        assert run(r, 'git', 'commit', '-qm', 'tronca').returncode != 0
        run(r, 'git', 'reset', '-q', '--hard')

        open(log, 'wb').write(TESTA.replace(b'2026-10-01', b'2026-10-16') + E1 + E2 + b'## 2026-10-03 \xe2\x80\x94 t\n\nx\n')
        run(r, 'git', 'add', 'wiki/log.md')
        assert run(r, 'git', 'commit', '-qm', 'coda').returncode == 0
    finally:
        shutil.rmtree(r, ignore_errors=True)
