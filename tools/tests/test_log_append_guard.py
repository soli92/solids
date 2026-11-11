"""log_append_guard.py — wiki/log.md append-only: guardia, esenzione del frontmatter, hook (EP-077)."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

QUI = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(QUI, '..'))
spec = importlib.util.spec_from_file_location('log_append_guard', os.path.join(TOOLS, 'wiki', 'log_append_guard.py'))
lag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lag)

TESTA = b'---\ntype: wiki-log\n---\n\n# Wiki Log\n\n> **Archivi:** [log-2026-10-08](log-2026-10-08.md)\n\n'
E1 = b'## 2026-10-01 10:00 \xe2\x80\x94 prima\n\ntesto uno\n\n'
E2 = b'## 2026-10-02 10:00 \xe2\x80\x94 seconda\n\ntesto due\n\n'
E3 = b'## 2026-10-03 10:00 \xe2\x80\x94 terza\n\ntesto tre\n\n'


def test_append_in_coda_ok():
    assert lag.removed_without_archive(TESTA + E1, TESTA + E1 + E2, []) == []


def test_troncamento_bloccato():
    gone = lag.removed_without_archive(TESTA + E1 + E2, TESTA + E2, [])
    assert b'## 2026-10-01 10:00 \xe2\x80\x94 prima' in gone and b'testo uno' in gone


def test_riga_modificata_bloccata():
    gone = lag.removed_without_archive(TESTA + E1, TESTA + E1.replace(b'uno', b'UNO'), [])
    assert gone == [b'testo uno']


def test_rotazione_con_archivio_ok():
    nuova_testa = TESTA.replace(b'(log-2026-10-08.md)', b'(log-2026-10-08.md) [log-2026-10-15](log-2026-10-15.md)')
    assert lag.removed_without_archive(TESTA + E1 + E2 + E3, nuova_testa + E3, [E1 + E2]) == []


def test_archivio_parziale_bloccato():
    gone = lag.removed_without_archive(TESTA + E1 + E2, TESTA, [E1])
    assert b'testo due' in gone and b'testo uno' not in gone


def test_righe_vuote_esenti():
    assert lag.removed_without_archive(TESTA + E1, TESTA + E1.replace(b'\n\n', b'\n'), []) == []


TESTA_FM = TESTA.replace(b'type: wiki-log\n', b'type: wiki-log\nupdated: 2026-10-01\n')


def test_frontmatter_esente():
    nuovo = TESTA_FM.replace(b'2026-10-01', b'2026-10-16') + E1
    assert lag.removed_without_archive(TESTA_FM + E1, nuovo, []) == []


def test_corpo_modificato_con_frontmatter_bloccato():
    nuovo = TESTA_FM.replace(b'2026-10-01', b'2026-10-16') + E1.replace(b'uno', b'UNO')
    assert lag.removed_without_archive(TESTA_FM + E1, nuovo, []) == [b'testo uno']


def test_puntatore_agli_archivi_esente():
    nuovo = TESTA.replace(b'(log-2026-10-08.md)', b'(log-2026-10-08.md) \xc2\xb7 [r](r.md)') + E1
    assert lag.removed_without_archive(TESTA + E1, nuovo, []) == []


def test_log_che_inizia_con_blocco_di_entry_non_ha_frontmatter():
    entry = b'---\ndate: 2026-10-01\n---\ntesto\n'
    assert lag.frontmatter_end(entry.splitlines(keepends=True)) == 0
    assert lag.removed_without_archive(entry, b'', []) != []


def _ha_commit(sha):
    return subprocess.run(['git', 'cat-file', '-e', sha + '^{commit}'], cwd=TOOLS, capture_output=True).returncode == 0


@pytest.mark.skipif(not _ha_commit('228bb90'), reason='storia della factory non disponibile')
def test_commit_reale_con_entry_perse_segnalato():
    gone = lag.check_commit('228bb90')
    assert sum(1 for l in gone if l.startswith(b'## ')) == 5


@pytest.mark.skipif(not _ha_commit('2460163'), reason='storia della factory non disponibile')
def test_rotazione_reale_ok():
    assert lag.check_commit('2460163') == []


def _run(cwd, *args):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)


def test_stage_su_repo_temporaneo():
    r = tempfile.mkdtemp(prefix='log-guard-')
    vecchio = lag.ROOT
    try:
        os.makedirs(os.path.join(r, 'wiki'))
        log = os.path.join(r, 'wiki', 'log.md')
        _run(r, 'git', 'init', '-q')
        _run(r, 'git', 'config', 'user.email', 't@t')
        _run(r, 'git', 'config', 'user.name', 't')
        open(log, 'wb').write(TESTA + E1 + E2)
        _run(r, 'git', 'add', '.')
        _run(r, 'git', 'commit', '-qm', 'base')
        lag.ROOT = __import__('pathlib').Path(r)

        open(log, 'wb').write(TESTA + E2)
        _run(r, 'git', 'add', 'wiki/log.md')
        assert lag.main([]) == 1

        open(log, 'wb').write(TESTA + E1 + E2 + E3)
        _run(r, 'git', 'add', 'wiki/log.md')
        assert lag.main([]) == 0
    finally:
        lag.ROOT = vecchio
        shutil.rmtree(r, ignore_errors=True)
