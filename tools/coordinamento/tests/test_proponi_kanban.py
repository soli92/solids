"""Test per proponi_kanban.py.

Esegui con:
    python tools/coordinamento/tests/test_proponi_kanban.py

I test unitari chiamano calcola() direttamente (funzione pura); i test end-to-end
creano un repository git temporaneo, lanciano lo script e verificano output,
determinismo e assenza di scritture indesiderate. Esce con 0 se tutti i test
passano, con 1 altrimenti.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
STRUMENTI = os.path.normpath(os.path.join(QUI, '..'))
sys.path.insert(0, STRUMENTI)

import proponi_kanban as pk  # noqa: E402

STATI = {
    'fatto': ['done'],
    'chiuso_senza_esito': ['superseded', 'cancelled'],
    'in_corso': ['in_progress', 'in-progress', 'review', 'approved'],
    'da_fare': ['todo'],
}


def esegui(nome, fn):
    try:
        ok = fn()
    except Exception as exc:  # noqa: BLE001
        print('KO  %s: eccezione: %s' % (nome, exc))
        return False
    print('%s  %s' % ('OK' if ok else 'KO', nome))
    return bool(ok)


def entita(nome, tipo, stato, owner='', window=None, epic='XX-EP-001', us='XX-US-001', priority='P1'):
    """Crea un dict entita' per i test unitari."""
    return {
        'tipo': tipo,
        'id': nome,
        'stato_raw': stato,
        'stato_norm': pk.normalizza_stato(stato, STATI),
        'owner': owner,
        'window': window,
        'file': 'management/kanban/%s/%s/%s.md' % (epic, us, nome),
        'epic': epic,
        'us': us,
        'priority': priority,
    }


SEZIONE = {'id': 'sez', 'us': ['XX-US-001'], 'calendario': {'pronta_entro': '2026-10-16'}}


def calcola(ent, owner_non_persona=(), oggi=None, store_precedente=None, epic_owner_map=None):
    """Wrapper che chiama pk.calcola con sezione e us_sezione fisse per i test."""
    return pk.calcola(
        ent,
        {'XX-US-001': ['sez']},
        {'sez': SEZIONE},
        set(owner_non_persona),
        store_precedente=store_precedente,
        oggi=oggi,
        epic_owner_map=epic_owner_map,
    )


# ---------------------------------------------------------------------------
# Test unitari (funzione pura calcola)
# ---------------------------------------------------------------------------

def caso_in_lavorazione_esclusa_qualunque_owner():
    ent = {n: entita(n, 'TSK', s, o) for n, s, o in [
        ('XX-TSK-001', 'in_progress', 'dev-a'),
        ('XX-TSK-002', 'in-progress', 'Altro Dev'),
        ('XX-TSK-003', 'in_progress', ''),
    ]}
    proposte, esclusi, da_assegnare = calcola(ent, ['', 'da designare'])
    return (not proposte and not da_assegnare
            and [e['id'] for e in esclusi] == ['XX-TSK-001', 'XX-TSK-002', 'XX-TSK-003'])


def caso_review_approved_esclusi():
    ent = {
        'XX-US-001': entita('XX-US-001', 'US', 'review'),
        'XX-TSK-004': entita('XX-TSK-004', 'TSK', 'approved'),
    }
    proposte, esclusi, da_assegnare = calcola(ent, [''])
    return not proposte and not da_assegnare and {e['id'] for e in esclusi} == {'XX-US-001', 'XX-TSK-004'}


def caso_window_mancante_e_non_allineata():
    p1, _, _ = calcola({'XX-US-001': entita('XX-US-001', 'US', 'todo', window=None)})
    p2, _, _ = calcola({'XX-US-001': entita('XX-US-001', 'US', 'todo', window='entro 10/10')})
    p3, _, _ = calcola({'XX-US-001': entita('XX-US-001', 'US', 'todo', window='07/10 - 16/10')})
    return (
        [p['tipo'] for p in p1] == ['window_mancante']
        and p1[0]['valore_proposto'] == 'entro 16/10'
        and [p['tipo'] for p in p2] == ['window_non_allineata']
        and p3 == []
    )


def caso_owner_non_persona():
    """TSK con owner in owner_non_persona va in da_assegnare, NON in proposte.

    Verifica il blind spot: valore_proposto: null non deve comparire in proposte.
    """
    ent = {
        'XX-TSK-005': entita('XX-TSK-005', 'TSK', 'todo', 'da designare'),
        'XX-TSK-006': entita('XX-TSK-006', 'TSK', 'todo', 'dev-a'),
    }
    proposte, _, da_assegnare = calcola(ent, ['da designare'])
    # nessuna proposta con valore_proposto null
    if proposte:
        return False
    # XX-TSK-005 in da_assegnare con campi richiesti
    if len(da_assegnare) != 1:
        return False
    da = da_assegnare[0]
    return (da['tsk_id'] == 'XX-TSK-005'
            and 'epic' in da
            and 'us' in da
            and 'priority' in da
            and 'prima_vista' in da
            and 'file' in da)


def caso_ordine_stabile():
    """L'ordine di da_assegnare e' stabile indipendentemente dall'ordine del dict entita'."""
    ent = {n: entita(n, 'TSK', 'todo', 'da designare') for n in ('XX-TSK-009', 'XX-TSK-007', 'XX-TSK-008')}
    _, _, a = calcola(ent, ['da designare'])
    _, _, b = calcola(dict(reversed(list(ent.items()))), ['da designare'])
    return a == b and [d['tsk_id'] for d in a] == ['XX-TSK-007', 'XX-TSK-008', 'XX-TSK-009']


def caso_normalizza_stato():
    return (
        pk.normalizza_stato('In_Progress', STATI) == 'in_corso'
        and pk.normalizza_stato('done', STATI) == 'fatto'
        and pk.normalizza_stato('boh', STATI) == 'sconosciuto'
    )


def caso_data_gg_mm():
    return pk.data_gg_mm('2026-10-07') == '07/10' and pk.data_gg_mm('07/10') is None


def caso_epic_owner_default_guardrail():
    """Tre scenari A6: mapping valido, scaduto, senza approved_by."""
    ent_senza = {'XX-TSK-011': entita('XX-TSK-011', 'TSK', 'todo', 'da designare', epic='XX-EP-001')}

    # Scenario 1: mapping valido -> proposta in proposte con tipo_valore e fonte
    mappa_valida = {'XX-EP-001': {
        'epic_id': 'XX-EP-001', 'owner': 'Mario Rossi',
        'approved_by': 'Musio', 'valid_until': '2099-12-31',
    }}
    p1, _, da1 = calcola(ent_senza, ['da designare'], oggi='2026-10-05', epic_owner_map=mappa_valida)
    ok1 = (
        len(p1) == 1 and not da1
        and p1[0]['valore_proposto'] == 'Mario Rossi'
        and p1[0].get('tipo_valore') == 'suggested_owner'
        and p1[0].get('fonte') == 'config/owner_defaults'
        and p1[0].get('approved_by') == 'Musio'
    )

    # Scenario 2: mapping scaduto -> da_assegnare
    mappa_scaduta = {'XX-EP-001': {
        'epic_id': 'XX-EP-001', 'owner': 'Mario Rossi',
        'approved_by': 'Musio', 'valid_until': '2020-01-01',
    }}
    p2, _, da2 = calcola(ent_senza, ['da designare'], oggi='2026-10-05', epic_owner_map=mappa_scaduta)
    ok2 = not p2 and len(da2) == 1 and da2[0]['tsk_id'] == 'XX-TSK-011'

    # Scenario 3: mapping senza approved_by -> da_assegnare (guardrail obbligatorio)
    mappa_no_approved = {'XX-EP-001': {
        'epic_id': 'XX-EP-001', 'owner': 'Mario Rossi',
        'valid_until': '2099-12-31',
    }}
    p3, _, da3 = calcola(ent_senza, ['da designare'], oggi='2026-10-05', epic_owner_map=mappa_no_approved)
    ok3 = not p3 and len(da3) == 1 and da3[0]['tsk_id'] == 'XX-TSK-011'

    return ok1 and ok2 and ok3


def caso_prima_vista_idempotente():
    """A7: prima_vista preservata fra cicli, nuova voce con oggi, voce risolta esce."""
    ent_senza = {'XX-TSK-012': entita('XX-TSK-012', 'TSK', 'todo', 'da designare',
                                     epic='XX-EP-001', us='XX-US-001', priority='P1')}
    ent_con = {'XX-TSK-012': entita('XX-TSK-012', 'TSK', 'todo', 'dev-a',
                                   epic='XX-EP-001', us='XX-US-001', priority='P1')}
    ent_nuovo = {'XX-TSK-013': entita('XX-TSK-013', 'TSK', 'todo', 'da designare',
                                     epic='XX-EP-001', us='XX-US-001', priority='P2')}

    # Prima run (store vuoto): prima_vista = oggi
    _, _, da1 = calcola(ent_senza, ['da designare'], oggi='2026-10-01')
    if not da1 or da1[0]['prima_vista'] != '2026-10-01':
        return False

    # Seconda run (store con prima_vista del ciclo precedente): prima_vista conservata
    store_prec = {'XX-TSK-012': '2026-10-01'}
    _, _, da2 = calcola(ent_senza, ['da designare'], oggi='2026-10-05', store_precedente=store_prec)
    if not da2 or da2[0]['prima_vista'] != '2026-10-01':
        return False

    # TSK ha acquisito owner: esce da da_assegnare
    _, _, da3 = calcola(ent_con, ['da designare'], oggi='2026-10-05', store_precedente=store_prec)
    if any(d['tsk_id'] == 'XX-TSK-012' for d in da3):
        return False

    # Voce nuova (non nello store): prima_vista = oggi
    _, _, da4 = calcola(ent_nuovo, ['da designare'], oggi='2026-10-05', store_precedente=store_prec)
    if not da4 or da4[0]['prima_vista'] != '2026-10-05':
        return False

    return True


# ---------------------------------------------------------------------------
# Helpers per i test end-to-end
# ---------------------------------------------------------------------------

def _git(cwd, *args):
    return subprocess.run(
        ['git', '-c', 'user.name=test', '-c', 'user.email=test@example.invalid', '-C', cwd, *args],
        capture_output=True, text=True, encoding='utf-8', check=True,
    ).stdout


def _scrivi(root, rel, testo):
    path = os.path.join(root, *rel.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(testo)
    return path


def _repo_base(owner_non_persona=None):
    """Crea un repository git temporaneo con kanban minimo per i test."""
    root = tempfile.mkdtemp(prefix='proponi-kanban-')
    _git(root, 'init', '-q')
    k = 'management/kanban/XX-EP-001'
    _scrivi(root, k + '/XX-EP-001.md', '---\nid: XX-EP-001\nstatus: in_progress\n---\n')
    _scrivi(root, k + '/XX-US-001/XX-US-001.md',
            '---\nid: XX-US-001\nstatus: todo\nwindow: "entro 10/10"\n---\n')
    _scrivi(root, k + '/XX-US-001/XX-TSK-001.md',
            '---\nid: XX-TSK-001\nstatus: in_progress\nowner: dev-a\n---\n')
    _scrivi(root, k + '/XX-US-001/XX-TSK-002.md',
            '---\nid: XX-TSK-002\nstatus: todo\nowner: da designare\npriority: P1\n---\n')
    onp = owner_non_persona if owner_non_persona is not None else ['da designare']
    cfg = {
        'factory_root': '.',
        'kanban_root': 'management/kanban',
        'stati': STATI,
        'owner_non_persona': onp,
        'vista_pm': {'obiettivo_predefinito_id': 'ob'},
        'obiettivi': [{
            'id': 'ob',
            'perimetro': [{'selettore': {'epiche': ['XX-EP-001']}}],
            'sezioni': [SEZIONE],
        }],
    }
    config = _scrivi(root, 'analytics/coordinamento/config-test.json', json.dumps(cfg, indent=1))
    _git(root, 'add', '-A')
    _git(root, 'commit', '-q', '-m', 'kanban di prova')
    return root, config


# ---------------------------------------------------------------------------
# Test end-to-end
# ---------------------------------------------------------------------------

def caso_end_to_end_deterministico_e_senza_scritture():
    """Due esecuzioni senza --aggiorna-store: stessi byte, nessuna scrittura nel repo."""
    root, config = _repo_base()
    try:
        prima = _git(root, 'status', '--porcelain', '--untracked-files=all')
        uscite = []
        for n in (1, 2):
            out = os.path.join(tempfile.gettempdir(),
                               'proposte-%d-%s.json' % (n, os.path.basename(root)))
            subprocess.run(
                [sys.executable, os.path.join(STRUMENTI, 'proponi_kanban.py'),
                 '--config', config, '--out', out],
                capture_output=True, text=True, encoding='utf-8', check=True,
            )
            uscite.append(out)
        dopo = _git(root, 'status', '--porcelain', '--untracked-files=all')
        b1, b2 = (open(u, 'rb').read() for u in uscite)
        dati = json.loads(b1)
        for u in uscite:
            os.remove(u)
        return (
            b1 == b2
            and prima == dopo == ''
            # owner_non_persona -> da_assegnare, NON in proposte
            and sorted(p['tipo'] for p in dati['proposte']) == ['window_non_allineata']
            and [e['id'] for e in dati['esclusi']] == ['XX-TSK-001']
            and len(dati['da_assegnare']) == 1
            and dati['da_assegnare'][0]['tsk_id'] == 'XX-TSK-002'
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def caso_aggiorna_store():
    """--aggiorna-store: store scritto; idempotente; prima_vista preservata; senza flag nessuna scrittura."""
    root, config = _repo_base()
    try:
        store_path = os.path.join(root, 'analytics', 'coordinamento', 'test', 'da_assegnare.yaml')
        script = os.path.join(STRUMENTI, 'proponi_kanban.py')

        # Senza --aggiorna-store: store non viene creato
        subprocess.run(
            [sys.executable, script, '--config', config, '--operatore', 'test'],
            capture_output=True, text=True, encoding='utf-8', check=True,
        )
        if os.path.exists(store_path):
            return False

        # Prima run con --aggiorna-store --oggi: store creato
        subprocess.run(
            [sys.executable, script, '--config', config, '--operatore', 'test',
             '--aggiorna-store', '--oggi', '2026-10-01'],
            capture_output=True, text=True, encoding='utf-8', check=True,
        )
        if not os.path.exists(store_path):
            return False
        b_store1 = open(store_path, 'rb').read()

        # Seconda run identica: store byte-identico (idempotente)
        out1 = store_path + '.out1.json'
        subprocess.run(
            [sys.executable, script, '--config', config, '--operatore', 'test',
             '--aggiorna-store', '--oggi', '2026-10-01', '--out', out1],
            capture_output=True, text=True, encoding='utf-8', check=True,
        )
        b_store2 = open(store_path, 'rb').read()
        b_out1 = open(out1, 'rb').read()
        os.remove(out1)
        if b_store1 != b_store2:
            return False

        # Terza run identica: output JSON byte-identico alla seconda (stesso store in input)
        out2 = store_path + '.out2.json'
        subprocess.run(
            [sys.executable, script, '--config', config, '--operatore', 'test',
             '--aggiorna-store', '--oggi', '2026-10-01', '--out', out2],
            capture_output=True, text=True, encoding='utf-8', check=True,
        )
        b_out2 = open(out2, 'rb').read()
        os.remove(out2)
        if b_out1 != b_out2:
            return False

        # --oggi diverso ma TSK gia' nello store: prima_vista conservata -> store byte-identico
        subprocess.run(
            [sys.executable, script, '--config', config, '--operatore', 'test',
             '--aggiorna-store', '--oggi', '2026-10-05'],
            capture_output=True, text=True, encoding='utf-8', check=True,
        )
        b_store3 = open(store_path, 'rb').read()
        if b_store1 != b_store3:
            return False

        # sha256 dello store e' presente nella provenienza dell'output
        out3 = store_path + '.out3.json'
        subprocess.run(
            [sys.executable, script, '--config', config, '--operatore', 'test',
             '--aggiorna-store', '--oggi', '2026-10-01', '--out', out3],
            capture_output=True, text=True, encoding='utf-8', check=True,
        )
        dati = json.loads(open(out3, 'rb').read())
        os.remove(out3)
        sha_in_output = dati.get('provenienza', {}).get('da_assegnare_sha256')
        if not sha_in_output:
            return False

        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def caso_store_forma_mappa_letta_da_aggrega():
    """Lo store scritto e' {da_assegnare: [...]}: la forma che aggrega.py e verifica_l0.py leggono."""
    import yaml
    root, config = _repo_base()
    try:
        store_path = os.path.join(root, 'analytics', 'coordinamento', 'test', 'da_assegnare.yaml')
        subprocess.run([sys.executable, os.path.join(STRUMENTI, 'proponi_kanban.py'), '--config', config,
                        '--operatore', 'test', '--aggiorna-store', '--oggi', '2026-10-01'],
                       capture_output=True, text=True, encoding='utf-8', check=True)
        dati = yaml.safe_load(open(store_path, encoding='utf-8'))
        sys.path.insert(0, STRUMENTI)
        import aggrega
        import datetime
        voci, sha, avviso = aggrega._leggi_store(store_path, datetime.date(2026, 10, 5))
        return (isinstance(dati, dict) and [v['tsk_id'] for v in dati['da_assegnare']] == ['XX-TSK-002']
                and avviso is None and bool(sha) and [v['eta_giorni'] for v in voci] == [2])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def caso_kanban_senza_prefisso_con_slug():
    """ID senza prefisso e cartelle con slug: epic/us dal frontmatter, poi dal path; stesse proposte."""
    root = tempfile.mkdtemp(prefix='proponi-slug-')
    try:
        _git(root, 'init', '-q')
        k = 'management/kanban/EP-001-epica-di-prova'
        _scrivi(root, k + '/EP-001.md', '---\nid: EP-001\nstatus: in-progress\n---\n')
        _scrivi(root, k + '/US-001-sezione/US-001.md', '---\nid: US-001\nstatus: todo\nwindow: "entro 10/10"\n---\n')
        _scrivi(root, k + '/US-001-sezione/TSK-001.md', '---\nid: TSK-001\nstatus: in-progress\nowner: dev-a\n---\n')
        _scrivi(root, k + '/US-001-sezione/TSK-002.md', '---\nid: TSK-002\nstatus: todo\npriority: P1\n---\n')
        _scrivi(root, k + '/US-001-sezione/TSK-003.md', '---\nid: TSK-003\nstatus: todo\nstory: US-009\nepic: EP-009\n---\n')
        sez = {'id': 'sez', 'us': ['US-001'], 'calendario': {'pronta_entro': '2026-10-16'}}
        cfg = {'factory_root': '.', 'kanban_root': 'management/kanban', 'stati': STATI, 'owner_non_persona': ['da designare'],
               'vista_pm': {'obiettivo_predefinito_id': 'ob'},
               'obiettivi': [{'id': 'ob', 'perimetro': [{'selettore': {'epiche': ['EP-001']}}], 'sezioni': [sez]}]}
        config = _scrivi(root, 'analytics/coordinamento/config-test.json', json.dumps(cfg, indent=1))
        _git(root, 'add', '-A')
        _git(root, 'commit', '-q', '-m', 'kanban senza prefisso')
        out = os.path.join(root, 'proposte.json')
        subprocess.run([sys.executable, os.path.join(STRUMENTI, 'proponi_kanban.py'), '--config', config, '--out', out],
                       capture_output=True, text=True, encoding='utf-8', check=True)
        dati = json.load(open(out, encoding='utf-8'))
        da = {d['tsk_id']: d for d in dati['da_assegnare']}
        return (sorted(p['tipo'] for p in dati['proposte']) == ['window_non_allineata']
                and [e['id'] for e in dati['esclusi']] == ['TSK-001']
                and sorted(da) == ['TSK-002', 'TSK-003']
                and (da['TSK-002']['epic'], da['TSK-002']['us']) == ('EP-001', 'US-001')
                and (da['TSK-003']['epic'], da['TSK-003']['us']) == ('EP-009', 'US-009'))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def caso_gate_pm_report_spento():
    """pm_report.enabled: false nella factory_root: STOP esplicito, exit 0, nessuno store e nessuna uscita."""
    root, config = _repo_base()
    try:
        _scrivi(root, 'factory.config.yaml', 'pm_report:\n  enabled: false\n')
        out = os.path.join(root, 'proposte.json')
        r = subprocess.run([sys.executable, os.path.join(STRUMENTI, 'proponi_kanban.py'), '--config', config,
                            '--operatore', 'test', '--aggiorna-store', '--oggi', '2026-10-01', '--out', out],
                           capture_output=True, text=True, encoding='utf-8')
        store_path = os.path.join(root, 'analytics', 'coordinamento', 'test', 'da_assegnare.yaml')
        return (r.returncode == 0 and 'STOP' in r.stdout and 'pm_report.enabled' in r.stdout
                and not os.path.exists(out) and not os.path.exists(store_path))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def caso_chiusi_ignorati():
    ent = {'XX-TSK-010': entita('XX-TSK-010', 'TSK', 'done', 'da designare'),
           'XX-TSK-011': entita('XX-TSK-011', 'TSK', 'superseded', ''),
           'XX-TSK-012': entita('XX-TSK-012', 'TSK', 'todo', 'da designare')}
    r = calcola(ent, ['', 'da designare'])
    proposte, esclusi, da_assegnare = r[0], r[1], r[2]
    ids = [v.get('tsk_id') for v in da_assegnare]
    return not proposte and not esclusi and ids == ['XX-TSK-012']

# Ogni `caso_*` restituisce True/False per il runner da script (`main`). Per pytest se ne genera
# un `test_*` che ASSERISCE l'esito: un test che restituisce un bool e' verde per pytest anche
# quando restituisce False (PytestReturnNotNoneWarning), quindi senza questo wrapper la suite non
# verificava nulla.
def _come_test(caso):
    def test():
        assert caso() is True, '%s ha restituito un esito diverso da True' % caso.__name__
    test.__name__ = 'test_' + caso.__name__[len('caso_'):]
    return test


for _nome, _caso in list(globals().items()):
    if _nome.startswith('caso_') and callable(_caso):
        globals()['test_' + _nome[len('caso_'):]] = _come_test(_caso)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    test = [
        ('in lavorazione esclusa qualunque sia l\'owner (AC-4)', caso_in_lavorazione_esclusa_qualunque_owner),
        ('review e approved esclusi (AC-5)', caso_review_approved_esclusi),
        ('window mancante / non allineata / allineata', caso_window_mancante_e_non_allineata),
        ('owner_non_persona -> da_assegnare, nessun valore_proposto:null in proposte (A4+A5)',
         caso_owner_non_persona),
        ('ordine stabile di da_assegnare (A5)', caso_ordine_stabile),
        ('normalizza_stato', caso_normalizza_stato),
        ('data_gg_mm', caso_data_gg_mm),
        ('epic_owner_default: valido/scaduto/senza approved_by (A6)', caso_epic_owner_default_guardrail),
        ('prima_vista preservata, nuova voce con oggi, voce risolta esce (A7)', caso_prima_vista_idempotente),
        ('end-to-end: stessi byte su due esecuzioni, nessuna scrittura nel repository', caso_end_to_end_deterministico_e_senza_scritture),
        ('aggiorna-store: idempotente, senza flag nessuna scrittura, sha256 in provenienza (A7)',
         caso_aggiorna_store),
    ]
    test.append(('TSK chiusi ignorati (fatti e chiusi senza esito)', caso_chiusi_ignorati))
    test.append(('store in forma {da_assegnare: [...]}, letto da aggrega', caso_store_forma_mappa_letta_da_aggrega))
    test.append(('kanban senza prefisso, cartelle con slug, appartenenza dal frontmatter', caso_kanban_senza_prefisso_con_slug))
    test.append(('gate pm_report.enabled false: STOP, exit 0, nessuna scrittura', caso_gate_pm_report_spento))
    esiti = [esegui(n, f) for n, f in test]
    print('\n%d OK, %d KO' % (sum(esiti), len(esiti) - sum(esiti)))
    return 0 if all(esiti) else 1


if __name__ == '__main__':
    sys.exit(main())
