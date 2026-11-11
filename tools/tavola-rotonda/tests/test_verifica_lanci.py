"""Test per verifica-lanci.py. Esegui con: python3 tools/tavola-rotonda/tests/test_verifica_lanci.py (o pytest)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(QUI, '..', 'verifica-lanci.py'))
spec = importlib.util.spec_from_file_location('verifica_lanci', SCRIPT)
vl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vl)


def evento(*blocchi, ruolo='assistant'):
    return json.dumps({'type': ruolo, 'message': {'role': ruolo, 'content': list(blocchi)}})


def uso(nome, **ingresso):
    return {'type': 'tool_use', 'name': nome, 'input': ingresso}


SIMULATA = [evento({'type': 'text', 'text': 'avvio'}, ruolo='user'),
            evento(uso('Read', file_path='a'), uso('Read', file_path='b')),
            evento(uso('Glob', pattern='*')), evento(uso('Write', file_path='registro.md')), 'riga non json']
REALE = SIMULATA + [evento(uso('Agent', subagent_type='tpm', description='posizione tpm')),
                    evento(uso('Task', subagent_type='qa-dev', description='posizione qa'))]


def test_conta_simulata():
    r = vl.conta(SIMULATA)
    assert r['lanci'] == 0 and r['strumenti'] == {'Glob': 1, 'Read': 2, 'Write': 1}


def test_conta_reale():
    r = vl.conta(REALE)
    assert r['lanci'] == 2 and [x['subagent_type'] for x in r['dettaglio_lanci']] == ['tpm', 'qa-dev']


def _lancia(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, encoding='utf-8')


def test_end_to_end_codici_di_uscita():
    radice = tempfile.mkdtemp(prefix='verifica-lanci-')
    try:
        for agente, righe in (('sim', SIMULATA), ('ok', REALE)):
            d = os.path.join(radice, 'progetto', 'sessione-1', 'subagents')
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'agent-%s.jsonl' % agente), 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(righe) + '\n')
        r_sim = _lancia('--agent-id', 'sim', '--radice', radice)
        r_ok = _lancia('--agent-id', 'ok', '--radice', radice)
        r_no = _lancia('--agent-id', 'assente', '--radice', radice)
        assert r_sim.returncode == 1 and json.loads(r_sim.stdout)['verdetto'] == 'simulato'
        assert r_ok.returncode == 0 and json.loads(r_ok.stdout)['lanci'] == 2
        assert r_no.returncode == 2
    finally:
        shutil.rmtree(radice, ignore_errors=True)


def test_verifica_registro_pura():
    trascrizioni = {'a1': ('x.jsonl', 'tpm'), 'a2': ('y.jsonl', 'qa-dev'), 'a3': ('z.jsonl', 'fe-dev')}
    trova = lambda aid: trascrizioni.get(aid, (None, None))
    ok = vl.verifica_registro([{'agente': 'tpm', 'agent_id': 'a1', 'fase': 1},
                               {'agente': 'qa-dev', 'agent_id': 'a2', 'fase': 1}], trova)
    uno = vl.verifica_registro([{'agente': 'tpm', 'agent_id': 'a1'}], trova)
    manca = vl.verifica_registro([{'agente': 'tpm', 'agent_id': 'a1'}, {'agente': 'qa-dev', 'agent_id': 'zz'}], trova)
    tipo = vl.verifica_registro([{'agente': 'tpm', 'agent_id': 'a1'}, {'agente': 'qa-dev', 'agent_id': 'a3'}], trova)
    assert ok['verdetto'] == 'multi-agente' and ok['agenti_distinti'] == ['qa-dev', 'tpm']
    assert uno['verdetto'] == 'non valido'
    assert manca['verdetto'] == 'non valido' and manca['mancanti'][0]['agent_id'] == 'zz'
    assert tipo['verdetto'] == 'non valido' and tipo['tipo_diverso'][0]['tipo_trascrizione'] == 'fe-dev'
    assert vl.verifica_registro(None, trova)['verdetto'] == 'non valido'


def test_end_to_end_registro():
    radice = tempfile.mkdtemp(prefix='verifica-lanci-reg-')
    try:
        d = os.path.join(radice, 'progetto', 'sess-9', 'subagents')
        os.makedirs(d)
        for aid, tipo in (('p1', 'tpm'), ('p2', 'qa-dev')):
            open(os.path.join(d, 'agent-%s.jsonl' % aid), 'w').write(SIMULATA[1] + '\n')
            json.dump({'agentType': tipo}, open(os.path.join(d, 'agent-%s.meta.json' % aid), 'w'))
        reg_ok = os.path.join(radice, 'ok.md')
        open(reg_ok, 'w').write('---\nesecuzione: sessione-principale\npartecipanti_lanciati: 2\nlanci:\n'
                                '  - {agente: tpm, fase: 1, round: 0, agent_id: p1}\n'
                                '  - {agente: qa-dev, fase: 1, round: 0, agent_id: p2}\n---\n# registro\n')
        reg_ko = os.path.join(radice, 'ko.md')
        open(reg_ko, 'w').write('---\npartecipanti_lanciati: 0\n---\n# registro\n')
        r_ok = _lancia('--registro', reg_ok, '--sessione', 'sess-9', '--radice', radice)
        r_ko = _lancia('--registro', reg_ko, '--sessione', 'sess-9', '--radice', radice)
        r_senza = _lancia('--registro', reg_ok)
        assert r_ok.returncode == 0 and json.loads(r_ok.stdout)['verificati'] == 2
        assert r_ko.returncode == 1 and json.loads(r_ko.stdout)['verdetto'] == 'non valido'
        assert r_senza.returncode == 2
    finally:
        shutil.rmtree(radice, ignore_errors=True)


if __name__ == '__main__':
    esiti = []
    for nome, fn in sorted(globals().items()):
        if nome.startswith('test_') and callable(fn):
            try:
                fn(); print('OK  ' + nome); esiti.append(True)
            except AssertionError as exc:
                print('KO  %s: %s' % (nome, exc)); esiti.append(False)
    print('\n%d OK, %d KO' % (sum(esiti), len(esiti) - sum(esiti)))
    sys.exit(0 if all(esiti) else 1)
