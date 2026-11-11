"""rotate_log.py — rotazione a soglia di wiki/log.md (dalla derivata, EP-072 TSK-782)."""
import hashlib
import importlib.util
import os
import shutil
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('rotate_log', os.path.normpath(os.path.join(QUI, '..', 'wiki', 'rotate_log.py')))
rl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rl)

TESTA = ('---\ntype: wiki-log\n---\n\n# Wiki Log\n\n'
         '> **Storico ruotato.** Le entry fino al 2026-09-30 sono in log-2026-Q3.md.\n\n')


def log(*entry):
    return TESTA + ''.join(entry)


def entry(data, testo='x' * 40):
    return '## %s 10:00 — voce\n\n%s\n\n' % (data, testo)


def radice(contenuto):
    r = tempfile.mkdtemp(prefix='rotate-log-')
    os.makedirs(os.path.join(r, 'wiki'))
    with open(os.path.join(r, 'wiki', 'log.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(contenuto)
    return r


def leggi(r, nome):
    with open(os.path.join(r, 'wiki', nome), 'rb') as fh:
        return fh.read()


def lancia(r, *args):
    return rl.main(['--root', r, '--oggi', '2026-10-15', *args])


def test_sotto_soglia_non_fa_nulla():
    r = radice(log(entry('2026-10-10'), entry('2026-10-14')))
    try:
        prima = leggi(r, 'log.md')
        assert lancia(r, '--apply') == 0
        assert leggi(r, 'log.md') == prima and not os.path.exists(os.path.join(r, 'wiki', 'log-2026-10-15.md'))
    finally:
        shutil.rmtree(r)


def test_rotazione_a_soglia_byte_preserving():
    r = radice(log(entry('2026-10-10'), entry('2026-10-14'), entry('2026-10-15')))
    try:
        originale = leggi(r, 'log.md')
        assert lancia(r, '--apply', '--soglia', '100') == 0
        arc, nuovo = leggi(r, 'log-2026-10-15.md'), leggi(r, 'log.md')
        blocco = arc.split(b'# Wiki Log \xe2\x80\x94 archivio fino al 2026-10-15\n\n', 1)[1]
        assert originale.startswith(TESTA.encode()) and originale.endswith(blocco)
        assert TESTA.encode() + blocco == originale  # nessun byte perso o alterato
        assert b'> **Archivi:** [`log-2026-10-15.md`](log-2026-10-15.md)' in nuovo
        assert b'range: "dal 2026-10-10 al 2026-10-15"' in arc and b'soglia_bytes: 100' in arc
        assert nuovo.count(b'\n## ') == 0  # tutte le entry fino a oggi sono in archivio
    finally:
        shutil.rmtree(r)


def test_due_rotazioni_nello_stesso_mese_e_rifiuto_nello_stesso_giorno():
    r = radice(log(entry('2026-10-03'), entry('2026-10-05')))
    try:
        assert rl.main(['--root', r, '--oggi', '2026-10-05', '--apply', '--soglia', '100']) == 0
        with open(os.path.join(r, 'wiki', 'log.md'), 'a', encoding='utf-8') as fh:
            fh.write(entry('2026-10-09') + entry('2026-10-11'))
        assert rl.main(['--root', r, '--oggi', '2026-10-11', '--apply', '--soglia', '100']) == 0
        nuovo = leggi(r, 'log.md')
        assert os.path.exists(os.path.join(r, 'wiki', 'log-2026-10-05.md'))
        assert os.path.exists(os.path.join(r, 'wiki', 'log-2026-10-11.md'))
        assert b'[`log-2026-10-05.md`](log-2026-10-05.md) \xc2\xb7 [`log-2026-10-11.md`](log-2026-10-11.md)' in nuovo
        with open(os.path.join(r, 'wiki', 'log.md'), 'a', encoding='utf-8') as fh:
            fh.write(entry('2026-10-11', 'y' * 40))
        assert rl.main(['--root', r, '--oggi', '2026-10-11', '--apply', '--soglia', '100']) == 1
    finally:
        shutil.rmtree(r)


def test_entry_futura_e_successive_restano():
    r = radice(log(entry('2026-10-10'), entry('2026-10-20'), entry('2026-10-12')))
    try:
        assert lancia(r, '--apply', '--soglia', '100') == 0
        nuovo = leggi(r, 'log.md')
        assert b'## 2026-10-20' in nuovo and b'## 2026-10-12' in nuovo
        assert b'## 2026-10-10' in leggi(r, 'log-2026-10-15.md')
    finally:
        shutil.rmtree(r)


def test_dry_run_non_scrive_e_etichetta_legacy():
    contenuto = log(entry('2026-10-10')).replace('> **Storico',
                                                  '> **Archivi mensili:** [`log-2026-09.md`](log-2026-09.md)\n> **Storico')
    r = radice(contenuto)
    try:
        sha = hashlib.sha256(leggi(r, 'log.md')).hexdigest()
        assert lancia(r, '--forza') == 0
        assert hashlib.sha256(leggi(r, 'log.md')).hexdigest() == sha
        assert not os.path.exists(os.path.join(r, 'wiki', 'log-2026-10-15.md'))
        assert lancia(r, '--forza', '--apply') == 0
        riga = [l for l in leggi(r, 'log.md').split(b'\n') if l.startswith(b'> **Archivi mensili:**')][0]
        assert riga.endswith(b'[`log-2026-10-15.md`](log-2026-10-15.md)')
    finally:
        shutil.rmtree(r)


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
