"""Roll-up delle US: i TSK dichiarati in tsk_ids/tsk_range contano anche se stanno in un'altra cartella.

Prima il controllo «us-non-aggiornata» guardava solo i TSK della US per frontmatter/path: una US
che elenca TSK di altre US (es. «XX-TSK-267, XX-TSK-541..547») risultava incoerente a torto.
"""
import os
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))
from kanban_ids import tsk_dichiarati  # noqa: E402
from snapshot import controlli_qualita  # noqa: E402


def _stato(norm):
    return {'dichiarato': norm, 'normalizzato': norm}


def _repo():
    root = tempfile.mkdtemp(prefix='coord-rollup-')
    os.makedirs(os.path.join(root, 'management', 'kanban'))
    open(os.path.join(root, 'management', 'kanban', 'README.md'), 'w').write('x\n')
    for args in (['init', '-q'], ['add', '-A'],
                 ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '-m', 'init']):
        subprocess.run(['git', '-C', root] + args, check=True, capture_output=True)
    return root


def _entita(dichiarati):
    us = {'id': 'XX-US-001', 'tipo': 'US', 'stato': _stato('fatto'), 'fonte': {'path': 'us1.md'}}
    if dichiarati is not None:
        us['tsk_dichiarati'] = sorted(dichiarati)
    return [
        us,
        # il TSK della cartella di US-001 e' chiuso
        {'id': 'XX-TSK-001', 'tipo': 'TSK', 'us': 'XX-US-001', 'epica': None, 'stato': _stato('fatto'), 'fonte': {'path': 't1.md'}},
        # un TSK di un'altra US, dichiarato da US-001, e' ancora aperto
        {'id': 'XX-TSK-541', 'tipo': 'TSK', 'us': 'XX-US-009', 'epica': None, 'stato': _stato('in_corso'), 'fonte': {'path': 't2.md'}},
    ]


def _rollup(root, entita):
    return [f for f in controlli_qualita(root, 'management/kanban', 'HEAD', [], entita)
            if f['codice'] == 'us-non-aggiornata' and f['entita'] == 'XX-US-001']


def test_parser_tsk_range_e_tsk_ids():
    assert tsk_dichiarati({'tsk_range': 'XX-TSK-267, XX-TSK-541, XX-TSK-561..563'}) == {
        'XX-TSK-267', 'XX-TSK-541', 'XX-TSK-561', 'XX-TSK-562', 'XX-TSK-563'}
    assert tsk_dichiarati({'tsk_range': 'TSK-708..TSK-710'}) == {'TSK-708', 'TSK-709', 'TSK-710'}
    assert tsk_dichiarati({'tsk_ids': ['XX-TSK-001'], 'tsk_range': 'XX-TSK-009'}) == {'XX-TSK-001'}
    for illeggibile in ('', 'da assegnare dal tpm', 'TSK-9..TSK-1', 'TSK-1..TSK-9999', None):
        assert tsk_dichiarati({'tsk_range': illeggibile}) is None


def test_us_chiusa_con_tsk_dichiarato_aperto_e_segnalata():
    root = _repo()
    # dichiarato: la US e' «fatto» ma un suo TSK dichiarato e' aperto → avviso
    assert _rollup(root, _entita({'XX-TSK-001', 'XX-TSK-541'}))
    # senza dichiarazione conta solo il TSK della cartella, chiuso → nessun avviso (comportamento invariato)
    assert not _rollup(root, _entita(None))
