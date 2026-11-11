"""Test per pianifica.py.

Esegui con:
    python tools/coordinamento/tests/test_pianifica.py

I test unitari costruiscono le entita' da testi markdown in memoria (entita_kanban) e chiamano
calcola() direttamente (funzione pura); i test end-to-end creano un repository git temporaneo,
lanciano lo script e verificano determinismo, fail-loud e assenza di scritture. Esce con 0 se
tutti i test passano, con 1 altrimenti.
"""
import copy
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
STRUMENTI = os.path.normpath(os.path.join(QUI, '..'))
sys.path.insert(0, STRUMENTI)

import pianifica as pf  # noqa: E402

OGGI = datetime.date(2026, 10, 7)  # mercoledi'
K = 'management/kanban'

STATI = {
    'fatto': ['done'],
    'chiuso_senza_esito': ['superseded', 'cancelled'],
    'in_corso': ['in_progress', 'in-progress', 'review', 'approved'],
    'da_fare': ['todo'],
    'sospeso': ['on_hold'],
    'bloccato': ['blocked'],
}

CFG = {
    'factory_root': '.',
    'kanban_root': K,
    'stati': STATI,
    'owner_non_persona': ['da designare'],
    'team': [
        {'id': 'a', 'nome': 'Anna Rossi', 'alias': ['Rossi']},
        {'id': 'b', 'nome': 'Bruno Bianchi', 'alias': []},
        {'id': 'c', 'nome': 'Carla Verdi', 'alias': [], 'impegno_pct': 50},
        {'id': 'z', 'nome': 'Zeno Neri', 'alias': []},
    ],
    'obiettivi': [{
        'id': 'ob',
        'data_target': '2026-12-31',
        'perimetro': [{'selettore': {'epiche': ['XX-EP-001']}}],
        'sezioni': [{'id': 's1', 'us': ['XX-US-001'], 'calendario': {'pronta_entro': '2026-10-09'}}],
    }],
    'pianificazione': {
        'persone_assegnabili': ['a', 'b', 'c'],
        'referente_bloccanti': 'a',
        'orizzonte_giorni_lavorativi': 10,
        'dimensioni_giorni': {'XS': 0.5, 'S': 1, 'M': 2, 'L': 4, 'XL': 8},
        'dimensione_predefinita': 'M',
        'punti_priorita': {'P0': 8, 'P1': 5, 'P2': 3, 'P3': 1},
        'fasce_urgenza': [{'entro_giorni': 3, 'punti': 4}, {'entro_giorni': 10, 'punti': 2}],
        'punti_sblocco_per_tsk': 1,
    },
}


def esegui(nome, fn):
    try:
        ok = fn()
    except Exception as exc:  # noqa: BLE001
        print('KO  %s: eccezione: %s' % (nome, exc))
        return False
    print('%s  %s' % ('OK' if ok else 'KO', nome))
    return bool(ok)


def md(id_, us='XX-US-001', epic='XX-EP-001', **campi):
    """(path, testo) di un TSK con frontmatter YAML."""
    fm = {'id': id_, 'status': 'todo', 'priority': 'P2', 'layer': 'fe', 'size': 'S'}
    fm.update(campi)
    righe = ['---'] + ['%s: %s' % (k, json.dumps(v, ensure_ascii=False)) for k, v in fm.items()] + ['---', '']
    return '%s/%s/%s/%s.md' % (K, epic, us, id_), '\n'.join(righe)


def calcola(*tsk, cfg=None):
    testi = dict(tsk)
    return pf.calcola(pf.entita_kanban(testi, K, STATI), cfg or CFG, OGGI)


def voce(ris, tsk_id):
    return next(v for v in ris['classifica'] if v['tsk_id'] == tsk_id)


def persona(ris, pid):
    return next(p for p in ris['persone'] if p['id'] == pid)


# ---------------------------------------------------------------------------
# Test unitari
# ---------------------------------------------------------------------------

def caso_punteggio_e_componenti():
    """(5 priorita' + 4 urgenza + 1 sblocco) / 1 gg = 10; scadenza dalla sezione della US."""
    r = calcola(md('XX-TSK-001', priority='P1', owner='Anna Rossi'),
                md('XX-TSK-002', depends_on=['XX-TSK-001'], owner='Anna Rossi'))
    v = voce(r, 'XX-TSK-001')
    return (v['punti'] == {'priorita': 5, 'urgenza': 4, 'sblocco': 1}
            and v['punteggio'] == 10.0 and v['scadenza'] == '2026-10-09'
            and v['fonte_scadenza'] == 'sezione:s1' and v['giorni_alla_scadenza'] == 2
            and v['sbloccati'] == ['XX-TSK-002'] and v['rank'] == 1)


def caso_scadenza_da_obiettivo_e_dimensione_minima():
    """US fuori sezione -> data_target dell'obiettivo; estimated_days 0.1 non scende sotto la taglia minima."""
    r = calcola(md('XX-TSK-001', us='XX-US-002', estimated_days=0.1, priority='P1', owner='Anna Rossi'))
    v = voce(r, 'XX-TSK-001')
    return (v['fonte_scadenza'] == 'obiettivo:ob' and v['punti']['urgenza'] == 0
            and v['giorni'] == 0.1 and v['punteggio'] == 10.0)  # 5 / max(0.1, 0.5)


def caso_scadenza_da_sezione_che_elenca_il_tsk():
    """Sezione con `tsk`: il TSK elencato prende la sua data; gli altri TSK della US restano alla sezione
    della US; un TSK elencato in una sezione senza data non eredita la sezione della US ma l'obiettivo."""
    cfg = json.loads(json.dumps(CFG))
    cfg['obiettivi'][0]['sezioni'] += [
        {'id': 'rilascio', 'us': ['XX-US-001'], 'tsk': ['XX-TSK-002'], 'calendario': {'pronta_entro': '2026-10-14'}},
        {'id': 'senza-data', 'us': ['XX-US-001'], 'tsk': ['XX-TSK-003']},
    ]
    r = calcola(md('XX-TSK-001', owner='Anna Rossi'), md('XX-TSK-002', owner='Anna Rossi'),
                md('XX-TSK-003', owner='Anna Rossi'), cfg=cfg)
    v1, v2, v3 = voce(r, 'XX-TSK-001'), voce(r, 'XX-TSK-002'), voce(r, 'XX-TSK-003')
    return (v1['scadenza'] == '2026-10-09' and v1['fonte_scadenza'] == 'sezione:s1'
            and v2['scadenza'] == '2026-10-14' and v2['fonte_scadenza'] == 'sezione:rilascio'
            and v3['fonte_scadenza'] == 'obiettivo:ob')


def caso_dimensione_predefinita_con_avviso():
    r = calcola(md('XX-TSK-001', size=None, owner='Anna Rossi'))
    v = voce(r, 'XX-TSK-001')
    return (v['dimensione_fonte'] == 'predefinita:M' and v['giorni'] == 2.0
            and any(a['tipo'] == 'dimensione_non_stimata' and a['tsk_id'] == 'XX-TSK-001' for a in r['avvisi']))


def caso_esclusi_r7_lavorazione_sospesi_chiusi():
    r = calcola(md('XX-TSK-001', status='review', owner='da designare'),
                md('XX-TSK-002', status='approved', owner='da designare'),
                md('XX-TSK-003', status='in_progress', owner='da designare'),
                md('XX-TSK-004', status='on_hold', owner='da designare'),
                md('XX-TSK-005', status='done', owner='da designare'),
                md('XX-TSK-006', owner='da designare'))
    return [v['tsk_id'] for v in r['classifica']] == ['XX-TSK-006'] and \
        [p['tsk_id'] for p in r['proposte']] == ['XX-TSK-006']


def caso_non_pronti_senza_proposta():
    """Dipendenza aperta o blocked_by esterno: in classifica, non pronti, nessuna proposta."""
    r = calcola(md('XX-TSK-001', owner='Bruno Bianchi'),
                md('XX-TSK-002', owner='da designare', depends_on=['XX-TSK-001']),
                md('XX-TSK-003', owner='da designare', blocked_by=['risposta del cliente sul tracciato']),
                md('XX-TSK-004', owner='da designare', depends_on=['XX-TSK-005']),
                md('XX-TSK-005', status='done', owner='Bruno Bianchi'))
    v2, v3, v4 = voce(r, 'XX-TSK-002'), voce(r, 'XX-TSK-003'), voce(r, 'XX-TSK-004')
    return (not v2['pronto'] and 'XX-TSK-001' in v2['motivo_non_pronto']
            and not v3['pronto'] and 'esterno' in v3['motivo_non_pronto']
            and v4['pronto']
            and [p['tsk_id'] for p in r['proposte']] == ['XX-TSK-004'])


def caso_affinita_e_competenze():
    """Anna ha storico sul layer fe; Bruno dichiara solo qa e non e' idoneo su fe."""
    cfg = copy.deepcopy(CFG)
    cfg['team'][1]['competenze'] = {'layer': ['qa']}
    r = calcola(md('XX-TSK-001', status='done', owner='Anna Rossi', layer='fe/i18n'),
                md('XX-TSK-002', status='done', owner='Rossi', layer='fe'),
                md('XX-TSK-003', owner='da designare', layer='fe'),
                md('XX-TSK-004', owner='da designare', layer='qa'), cfg=cfg)
    per_tsk = {p['tsk_id']: p for p in r['proposte']}
    return (per_tsk['XX-TSK-003']['valore_proposto'] == 'Anna Rossi'
            and per_tsk['XX-TSK-003']['affinita'] == {'layer': 2, 'epica': 2}
            and per_tsk['XX-TSK-003']['confidenza'] == 'media'
            and per_tsk['XX-TSK-004']['tipo'] == 'owner_proposto'
            and per_tsk['XX-TSK-004']['campo'] == 'owner'
            and per_tsk['XX-TSK-004']['fonte'] == 'pianificazione')


def caso_capacita_insufficiente():
    """Carichi in corso che saturano l'orizzonte: il TSK L va in non_assegnabili, nessuna proposta forzata."""
    r = calcola(md('XX-TSK-001', status='in_progress', owner='Anna Rossi', size='XL'),
                md('XX-TSK-002', status='in_progress', owner='Bruno Bianchi', size='XL'),
                md('XX-TSK-003', status='in_progress', owner='Carla Verdi', size='XL'),
                md('XX-TSK-004', owner='da designare', size='L'))
    na = r['non_assegnabili']
    return (r['proposte'] == [] and [n['tsk_id'] for n in na] == ['XX-TSK-004']
            and 'capacita' in na[0]['motivo']
            and persona(r, 'a')['capacita_residua_prima'] == 2.0
            and persona(r, 'c')['capacita_residua_prima'] == -3.0
            and any(a['tipo'] == 'sovraccarico' and a['dettaglio'].startswith('c:') for a in r['avvisi']))


def caso_greedy_scala_la_capacita():
    """Senza affinita' vince la capacita' residua piu' alta; ogni proposta la riduce."""
    r = calcola(md('XX-TSK-001', owner='da designare', size='L', priority='P0'),
                md('XX-TSK-002', owner='da designare', size='L', priority='P1'),
                md('XX-TSK-003', owner='da designare', size='L', priority='P2'))
    chi = [(p['tsk_id'], p['valore_proposto']) for p in r['proposte']]
    return chi == [('XX-TSK-001', 'Anna Rossi'), ('XX-TSK-002', 'Bruno Bianchi'), ('XX-TSK-003', 'Anna Rossi')] \
        and persona(r, 'a')['capacita_residua_dopo'] == 2.0


def caso_carico_oltre_orizzonte():
    """Un todo con scadenza oltre l'orizzonte non riduce la capacita'; un in_corso si'."""
    r = calcola(md('XX-TSK-001', us='XX-US-002', owner='Anna Rossi', size='L'),
                md('XX-TSK-002', owner='Anna Rossi', size='M'),
                md('XX-TSK-003', status='in_progress', us='XX-US-002', owner='Anna Rossi', size='S'))
    p = persona(r, 'a')
    return (p['carico_orizzonte_giorni'] == 3.0 and p['n_tsk_orizzonte'] == 2
            and p['carico_oltre_orizzonte_giorni'] == 4.0 and p['capacita_residua_prima'] == 7.0)


def caso_assenze_e_impegno():
    """Carla al 50% e assente 2 giorni lavorativi: (10 - 2) * 0.5 = 4."""
    cfg = copy.deepcopy(CFG)
    cfg['team'][2]['assenze'] = [{'dal': '2026-10-08', 'al': '2026-10-09'}, {'dal': '2026-10-10', 'al': '2026-10-11'}]
    r = calcola(md('XX-TSK-001', owner='Anna Rossi'), cfg=cfg)
    p = persona(r, 'c')
    return p['giorni_assenza_orizzonte'] == 2 and p['capacita_iniziale'] == 4.0


def caso_bloccato_al_referente_e_da_riassegnare():
    cfg = copy.deepcopy(CFG)
    cfg['pianificazione']['persone_da_riassegnare'] = ['z']
    r = calcola(md('XX-TSK-001', status='blocked', owner='da designare'),
                md('XX-TSK-002', owner='Zeno Neri'),
                md('XX-TSK-003', owner='Bruno Bianchi'), cfg=cfg)
    per_tsk = {p['tsk_id']: p for p in r['proposte']}
    return (per_tsk['XX-TSK-001']['tipo'] == 'owner_bloccante'
            and per_tsk['XX-TSK-001']['valore_proposto'] == 'Anna Rossi'
            and per_tsk['XX-TSK-002']['valore_attuale'] == 'Zeno Neri'
            and 'XX-TSK-003' not in per_tsk)


def caso_appartenenza_con_cartelle_slug():
    """Kanban senza prefissi e con slug nelle cartelle: epica e US dal path, o dal frontmatter se presente."""
    testi = {
        '%s/EP-001-prova/US-001-prima/TSK-001.md' % K: md('TSK-001', us=None)[1],
        '%s/EP-001-prova/US-001-prima/TSK-002.md' % K: '---\nid: TSK-002\nstatus: todo\nstory: US-009\nepic: EP-002\n---\n',
    }
    e = pf.entita_kanban(testi, K, STATI)
    return (e['TSK-001']['epic'] == 'EP-001' and e['TSK-001']['us'] == 'US-001'
            and e['TSK-002']['epic'] == 'EP-002' and e['TSK-002']['us'] == 'US-009')


def caso_valida_config():
    senza = {k: v for k, v in CFG.items() if k != 'pianificazione'}
    rotta = copy.deepcopy(CFG)
    rotta['pianificazione']['persone_assegnabili'] = ['a', 'ignoto']
    rotta['pianificazione']['dimensione_predefinita'] = 'XXL'
    del rotta['pianificazione']['fasce_urgenza']
    e2 = pf.valida_config(rotta)
    rotta2 = copy.deepcopy(CFG)
    rotta2['pianificazione']['persone_assegnabili'] = ['a', 'ignoto']
    rotta2['pianificazione']['dimensione_predefinita'] = 'XXL'
    e3 = pf.valida_config(rotta2)
    return (pf.valida_config(CFG) == []
            and pf.valida_config(senza) == ['blocco "pianificazione" assente nella config']
            and e2 == ['pianificazione.fasce_urgenza mancante']
            and any('ignoto' in e for e in e3) and any('dimensione_predefinita' in e for e in e3))


def caso_riferimenti():
    return (pf.riferimenti(['XX-TSK-001', 'vedi XX-US-002', 'Q-UP-001 aperta']) == (['XX-TSK-001', 'XX-US-002'], ['Q-UP-001 aperta'])
            and pf.riferimenti('XX-TSK-003, XX-TSK-001') == (['XX-TSK-001', 'XX-TSK-003'], [])
            and pf.riferimenti(['TSK-5', 'vedi US-12 e TSK-7']) == (['TSK-5', 'TSK-7', 'US-12'], [])  # kanban senza prefisso
            and pf.riferimenti(None) == ([], []))


def caso_legenda():
    senza = pf.legenda(copy.deepcopy(CFG['pianificazione']), None, 10)
    return (any(r.startswith('Punteggio di priorita') and 'P0 8' in r for r in senza)
            and any('XS 0.5' in r and 'pianificazione.dimensioni_giorni' not in r for r in senza)
            and not any('elocity' in r for r in senza))


def caso_tabella_giorni_obbligatoria():
    cfg = copy.deepcopy(CFG)
    del cfg['pianificazione']['dimensioni_giorni']
    return any('dimensioni_giorni' in e for e in pf.valida_config(cfg))


def caso_legenda_con_velocity():
    pc = copy.deepcopy(CFG['pianificazione'])
    vel = {'misurata': True, 'epiche': ['XX-EP-001'], 'finestra_settimane': ['2026-W40'], 'legenda': ['regola']}
    righe = pf.legenda(pc, vel, 10)
    return (any(r.startswith('Velocity misurata') and 'non da --ref' in r for r in righe)
            and '/velocity — regola' in righe)


def caso_tabella_da_velocity_config():
    """Senza dimensioni_giorni la tabella viene da `giorni` della config di /velocity (nessuna misura)."""
    root = tempfile.mkdtemp(prefix='pianifica-vel-')
    try:
        _scrivi(root, 'v.json', json.dumps({'giorni': {'S': 1, 'M': 3}, 'punti': {'S': 2, 'M': 3}}))
        pc = {'velocity_config': 'v.json', 'velocity_misurata': False}
        vel = pf.risolvi_velocity(root, pc, OGGI)
        propria = {'velocity_config': 'v.json', 'velocity_misurata': False, 'dimensioni_giorni': {'S': 9}}
        pf.risolvi_velocity(root, propria, OGGI)
        return (pc['dimensioni_giorni'] == {'S': 1, 'M': 3} and vel['misurata'] is False
                and vel['config_sha256'] and propria['dimensioni_giorni'] == {'S': 9}
                and pf.risolvi_velocity(root, {}, OGGI) is None)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test end-to-end
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


def _repo(cfg):
    root = tempfile.mkdtemp(prefix='pianifica-')
    _git(root, 'init', '-q')
    for rel, testo in (md('XX-TSK-001', status='done', owner='Anna Rossi'),
                       md('XX-TSK-002', owner='da designare', priority='P1'),
                       md('XX-TSK-003', owner='Bruno Bianchi', depends_on=['XX-TSK-002'])):
        _scrivi(root, rel, testo)
    config = _scrivi(root, 'analytics/coordinamento/config-test.json', json.dumps(cfg, indent=1))
    _git(root, 'add', '-A')
    _git(root, 'commit', '-q', '-m', 'kanban di prova')
    return root, config


def _lancia(config, *extra):
    return subprocess.run([sys.executable, os.path.join(STRUMENTI, 'pianifica.py'), '--config', config, *extra],
                          capture_output=True, text=True, encoding='utf-8')


def caso_end_to_end_deterministico_e_senza_scritture():
    root, config = _repo(CFG)
    try:
        uscite = []
        for n in (1, 2):
            out = os.path.join(tempfile.gettempdir(), 'pianifica-%d-%s.json' % (n, os.path.basename(root)))
            r = _lancia(config, '--oggi', '2026-10-07', '--out', out)
            if r.returncode != 0:
                return False
            uscite.append(out)
        stato = _git(root, 'status', '--porcelain', '--untracked-files=all')
        b1, b2 = (open(u, 'rb').read() for u in uscite)
        for u in uscite:
            os.remove(u)
        dati = json.loads(b1)
        return (b1 == b2 and stato == ''
                and [p['tsk_id'] for p in dati['proposte']] == ['XX-TSK-002']
                and dati['proposte'][0]['valore_proposto'] == 'Anna Rossi'
                and dati['classifica'][0]['sbloccati'] == ['XX-TSK-003']
                and dati['provenienza']['oggi'] == '2026-10-07'
                and r.stdout.strip().splitlines()[-1].startswith('RIEPILOGO '))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _repo_velocity(cfg):
    """Repo temporaneo con kanban, config di /velocity e tools/analytics copiato dal master."""
    root, config = _repo(cfg)
    analytics = os.path.join(root, 'tools', 'analytics')
    os.makedirs(analytics)
    for f in ('team-velocity.py', 'kanban_history.py'):
        shutil.copy(os.path.join(STRUMENTI, '..', 'analytics', f), analytics)
    vcfg = {'epiche': ['XX-EP-001'], 'team': [{'id': 'a', 'nome': 'Anna Rossi', 'alias': []}],
            'punti': {'XS': 1, 'S': 2, 'M': 3, 'L': 5, 'XL': 8},
            'giorni': {'XS': 0.5, 'S': 1, 'M': 2, 'L': 4, 'XL': 8}}
    _scrivi(root, 'analytics/velocity/config.json', json.dumps(vcfg))
    _git(root, 'add', '-A')
    _git(root, 'commit', '-q', '-m', 'velocity')
    return root, config


def caso_end_to_end_con_velocity_config():
    """Con velocity_config: tabella da /velocity, velocity per persona, provenienza dichiarata, byte stabili;
    senza: output identico a quello senza le chiavi (nessuna chiave velocity)."""
    cfg = copy.deepcopy(CFG)
    senza_tabella = copy.deepcopy(cfg)
    senza_tabella['pianificazione'].pop('dimensioni_giorni')
    senza_tabella['pianificazione']['velocity_config'] = 'analytics/velocity/config.json'
    root, config = _repo_velocity(senza_tabella)
    try:
        uscite = []
        # --oggi non precedente ai commit del repo di prova: la velocity non regge chiusure «nel futuro»
        oggi = datetime.date.today().isoformat()
        for n in (1, 2):
            out = os.path.join(tempfile.gettempdir(), 'pianifica-v%d-%s.json' % (n, os.path.basename(root)))
            r = _lancia(config, '--oggi', oggi, '--out', out)
            if r.returncode != 0:
                return False
            uscite.append(out)
        b1, b2 = (open(u, 'rb').read() for u in uscite)
        for u in uscite:
            os.remove(u)
        d = json.loads(b1)
        anna = next(p for p in d['persone'] if p['id'] == 'a')
        return (b1 == b2
                and d['provenienza']['velocity_misurata'] is True
                and d['provenienza']['velocity_config'] == 'analytics/velocity/config.json'
                and len(d['provenienza']['velocity_config_sha256']) == 64
                and 'velocity_punti_sett' in anna and 'settimane_al_ritmo_misurato' in anna
                and any(r.startswith('Velocity misurata') for r in d['legenda'])
                and any('fonte: analytics/velocity/config.json' in r for r in d['legenda'])
                and [p['tsk_id'] for p in d['proposte']] == ['XX-TSK-002'])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def caso_output_identico_senza_velocity_config():
    """Aggiungere il solo codice velocity non cambia i byte: nessuna chiave velocity senza velocity_config."""
    root, config = _repo(CFG)
    try:
        out = os.path.join(tempfile.gettempdir(), 'pianifica-s-%s.json' % os.path.basename(root))
        r = _lancia(config, '--oggi', '2026-10-07', '--out', out)
        testo = open(out, encoding='utf-8').read()
        os.remove(out)
        return (r.returncode == 0 and 'velocity' not in testo.lower() and 'velocity' not in r.stdout.lower())
    finally:
        shutil.rmtree(root, ignore_errors=True)


def caso_end_to_end_fail_loud():
    """Senza blocco pianificazione: exit 2 e nessun output; senza --oggi: errore di argparse."""
    senza = {k: v for k, v in CFG.items() if k != 'pianificazione'}
    root, config = _repo(senza)
    try:
        out = os.path.join(root, 'non-deve-esistere.json')
        r1 = _lancia(config, '--oggi', '2026-10-07', '--out', out)
        r2 = _lancia(config)
        return (r1.returncode == 2 and 'pianificazione' in r1.stderr and not os.path.exists(out)
                and r2.returncode == 2 and '--oggi' in r2.stderr)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# Ogni `caso_*` restituisce True/False per il runner da script (`main`); per pytest se ne genera un
# `test_*` che asserisce l'esito (un test che restituisce False sarebbe verde per pytest).
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
    test = [(n[len('caso_'):].replace('_', ' '), f) for n, f in globals().items()
            if n.startswith('caso_') and callable(f)]
    esiti = [esegui(n, f) for n, f in test]
    print('\n%d OK, %d KO' % (sum(esiti), len(esiti) - sum(esiti)))
    return 0 if all(esiti) else 1


if __name__ == '__main__':
    sys.exit(main())
