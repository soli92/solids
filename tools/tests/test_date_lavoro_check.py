"""Check 4be: date di lavoro obbligatorie sui TSK, su repo git temporaneo."""
import json
import os
import subprocess
import sys

import pytest

QUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(QUI, '..', 'lint', 'check-date-lavoro.py'))
CFG = 'kanban_dates:\n  required_from: "2026-10-19"\n'


def git(cwd, *a, data=None):
    env = dict(os.environ)
    if data:
        env.update(GIT_AUTHOR_DATE=data + 'T12:00:00', GIT_COMMITTER_DATE=data + 'T12:00:00')
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, env=env, check=True)


def tsk(stato, extra=''):
    return '---\ntype: task\nid: TSK-1\nstatus: %s\n%s---\n\n# TSK-1\n' % (stato, extra)


@pytest.fixture
def repo(tmp_path):
    for c in (('init', '-q'), ('config', 'user.email', 't@t'), ('config', 'user.name', 't')):
        git(tmp_path, *c)
    (tmp_path / 'factory.config.yaml').write_text(CFG)
    d = tmp_path / 'management' / 'kanban' / 'EP-1-a' / 'US-1-b'
    d.mkdir(parents=True)
    f = d / 'TSK-1-slug.md'
    f.write_text(tsk('todo'))
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'base', data='2026-10-01')
    return tmp_path, f


def esegui(root):
    r = subprocess.run([sys.executable, SCRIPT, '--json', '--root', str(root)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)['findings']


def commit(root, f, testo, data):
    f.write_text(testo)
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'stato', data=data)


def test_cambio_prima_dell_adozione_esente(repo):
    root, f = repo
    commit(root, f, tsk('done'), '2026-10-10')
    assert esegui(root) == []


def test_cambio_dopo_adozione_senza_date_error(repo):
    root, f = repo
    commit(root, f, tsk('done'), '2026-10-20')
    v = esegui(root)
    assert len(v) == 1 and v[0]['mancanti'] == ['started_at', 'closed_at']


def test_in_progress_richiede_solo_started_at(repo):
    root, f = repo
    commit(root, f, tsk('in-progress'), '2026-10-20')
    assert esegui(root)[0]['mancanti'] == ['started_at']
    commit(root, f, tsk('in-progress', 'started_at: 2026-10-20\n'), '2026-10-20')
    assert esegui(root) == []


def test_done_con_date_ok(repo):
    root, f = repo
    commit(root, f, tsk('done', 'started_at: 2026-10-20\nclosed_at: 2026-10-20\n'), '2026-10-21')
    assert esegui(root) == []


def test_stato_non_committato(repo):
    root, f = repo
    f.write_text(tsk('in-progress'))
    assert esegui(root)[0]['mancanti'] == ['started_at']
    f.write_text(tsk('in-progress', 'started_at: 2026-10-18\n'))
    assert esegui(root) == []


def test_date_invertite(repo):
    root, f = repo
    commit(root, f, tsk('done', 'started_at: 2026-10-22\nclosed_at: 2026-10-20\n'), '2026-10-22')
    v = esegui(root)
    assert len(v) == 1 and 'precede' in v[0]['incoerenze'][0]


def test_formato_errato(repo):
    root, f = repo
    commit(root, f, tsk('done', 'started_at: 20/10/2026\nclosed_at: 2026-10-20\n'), '2026-10-22')
    v = esegui(root)
    assert len(v) == 1 and 'formato' in v[0]['incoerenze'][0]


def test_chiave_assente_nessun_finding(repo):
    root, f = repo
    (root / 'factory.config.yaml').write_text('altro: 1\n')
    commit(root, f, tsk('done'), '2026-10-20')
    assert esegui(root) == []
    f.write_text(tsk('done') + 'x\n')
    assert esegui(root) == []


def test_archivio_escluso(repo):
    root, _ = repo
    a = root / 'management' / 'kanban' / 'archive'
    a.mkdir()
    (a / 'TSK-9.md').write_text(tsk('done'))
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'arch', data='2026-10-20')
    assert esegui(root) == []


def test_strict_esce_con_1(repo):
    root, f = repo
    commit(root, f, tsk('done'), '2026-10-20')
    r = subprocess.run([sys.executable, SCRIPT, '--strict', '--root', str(root)], capture_output=True, text=True)
    assert r.returncode == 1 and '[ERROR][date-lavoro][4be]' in r.stdout


def _senza_commit(tmp_path, stato_extra):
    (tmp_path / 'factory.config.yaml').write_text(CFG)
    d = tmp_path / 'management' / 'kanban' / 'EP-1-a' / 'US-1-b'
    d.mkdir(parents=True)
    (d / 'TSK-1-slug.md').write_text(tsk(*stato_extra))
    return tmp_path


def test_repo_senza_commit_non_va_in_crash(tmp_path):
    """EP-082: una factory appena installata ha `git init` e nessun commit; git log usciva con 128."""
    git(tmp_path, 'init', '-q')
    assert esegui(_senza_commit(tmp_path, ('todo',))) == []


def test_repo_senza_commit_vede_un_done_senza_date(tmp_path):
    git(tmp_path, 'init', '-q')
    findings = esegui(_senza_commit(tmp_path, ('done',)))
    assert len(findings) == 1


def test_fuori_da_git_non_va_in_crash(tmp_path):
    assert esegui(_senza_commit(tmp_path, ('todo',))) == []
