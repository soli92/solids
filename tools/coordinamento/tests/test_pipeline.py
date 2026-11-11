#!/usr/bin/env python3
"""Test di contratto della pipeline del report PM, su un kanban sintetico in un repo git temporaneo.

Esegui con:
    python tools/coordinamento/tests/test_pipeline.py
    python -m pytest tools/coordinamento/tests/test_pipeline.py

Esce con 0 se tutti i casi passano, con 1 se almeno uno fallisce.

Casi:
- regole di calcolo: chiusi senza esito fuori dal denominatore, sospesi dentro, alias di stato, stato non riconosciuto;
- classificazione solo da config;
- prerequisiti: soddisfatto, in attesa, da riconciliare, fuori perimetro;
- riproducibilita' al byte; lettura dal commit con i file sporchi segnalati ma non inclusi;
- verifica L0: blocca un numero manomesso e un elenco manomesso;
- anti-allucinazione: il testo libero dei TSK («bloccato», AC non spuntati) non cambia nessun numero;
- controllo della configurazione e applicazione delle proposte, con validazione e backup;
- riquadri «Chiedi una verifica» nella vista, con ID e commit nel prompt;
- indipendenza di verifica_l0.py dagli altri moduli del motore (test statico e regressione con bug sintetico);
- storico per operatore creato da applica_config.py nella directory della config;
- determinismo del rilevamento candidati: stessa (commit, config) => stessi candidati byte per byte;
- due forme di kanban: ID con prefisso e cartelle senza slug, ID senza prefisso e cartelle con slug;
  la misura della seconda e' quella della prima a meno del prefisso; appartenenza dal frontmatter, path solo in mancanza;
- obiettivo senza sezioni: misurato, verificato e impaginato, senza chiedere di classificare le US;
- store da_assegnare letto in entrambe le forme ({da_assegnare: [...]} e lista nuda);
- nessuna costante di dominio della factory derivata nel motore.
- avanzamento per sottoperimetro (TSK condiviso fra sezioni contato una volta), obiettivo senza sottoperimetri,
  ambiente di rilascio di default e valorizzato, etichetta «Infra · rilascio» nella vista, manomissioni bloccate da L0.
- selettore.us: perimetro limitato alle US elencate in misura, L0 (anche contro una manomissione), controllo della
  config e proposte.

Nessuna baseline sha256 dei file: nella sorgente proteggeva le copie esatte dalla derivata, qui i file
sono generalizzati e non sono copie. Il contratto e' quello dei casi sopra (vedi README, «Provenienza»).
"""
import ast
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(QUI, '..'))  # tools/coordinamento/
PY = sys.executable
ESITI = []


def ok(cond, nome):
    ESITI.append((bool(cond), nome))


def sha256_file(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def sh(*args, cwd=None, check=True):
    r = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    if check and r.returncode != 0:
        raise RuntimeError('%s: %s %s' % (' '.join(args), r.stdout, r.stderr))
    return r


def scrivi(path, testo):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(testo)


def tsk(root, us, n, status, extra='', corpo=''):
    p = os.path.join(root, 'management', 'kanban', 'XX-EP-001', us, 'XX-TSK-%03d.md' % n)
    scrivi(p, corpo_tsk(us, n, status, extra, corpo))


def corpo_tsk(us, n, status, extra='', corpo=''):
    return '---\nid: XX-TSK-%03d\ntitle: "Task %d"\nstatus: %s\nus: %s\n%s---\n%s\n' % (n, n, status, us, extra, corpo)


# Cartelle con slug della seconda forma (ID senza prefisso): il nome della cartella non e' l'ID
SLUG = {'XX-EP-001': 'EP-001-epica-di-prova', 'XX-EP-002': 'EP-002-epica-nuova', 'XX-EP-003': 'EP-003-epica-chiusa',
        'XX-EP-004': 'EP-004-epica-vecchia', 'XX-US-001': 'US-001-sezione-a', 'XX-US-002': 'US-002-lavoro-per-tipo',
        'XX-US-003': 'US-003-sezione-b-vuota', 'XX-US-004': 'US-004-us-nuova'}


def file_kanban():
    """{path relativo alla factory (forma con prefisso): contenuto} del kanban sintetico."""
    k = 'management/kanban'
    f = {}
    f[k + '/XX-EP-001/XX-EP-001.md'] = ('---\nid: XX-EP-001\ntitle: "Epica di prova"\nstatus: in_progress\n---\n'
           '## Note\n- 01/10: XX-TSK-005 → done (gate verde)\n- 01/10: XX-TSK-001 → done\n'
           '- 02/10: XX-TSK-010 → superseded\n- 03/10: XX-TSK-010 → **done** (rettifica)\n- 03/10: XX-TSK-004 → done\n')
    for us, t in (('XX-US-001', 'Sezione A'), ('XX-US-002', 'Lavoro per tipo'), ('XX-US-003', 'Sezione B vuota'), ('XX-US-004', 'US nuova')):
        piano = {'XX-US-001': 'window: "lun 05/10"\nassignee: "Dev A"\ncreated: 2026-10-01\n',
                 'XX-US-002': 'window: "entro mer 06/10"\ncreated: 2026-10-01\n'}.get(us, '')
        f['%s/XX-EP-001/%s/%s.md' % (k, us, us)] = '---\nid: %s\ntitle: "%s"\nstatus: todo\n%s---\n' % (us, t, piano)
    # epiche fuori perimetro: solo XX-EP-002 (aperta, dopo la data della config) e' candidata
    f[k + '/XX-EP-002/XX-EP-002.md'] = '---\nid: XX-EP-002\ntitle: "Epica nuova"\nstatus: todo\ncreated: 2026-10-05\n---\n'
    f[k + '/XX-EP-003/XX-EP-003.md'] = '---\nid: XX-EP-003\ntitle: "Epica chiusa"\nstatus: done\ncreated: 2026-10-05\n---\n'
    f[k + '/XX-EP-004/XX-EP-004.md'] = '---\nid: XX-EP-004\ntitle: "Epica vecchia"\nstatus: todo\ncreated: 2026-09-01\n---\n'
    # anti-allucinazione: AC non spuntati su un TSK done, la prosa dice «bloccato» su un TSK todo
    for us, n, st, extra, corpo in (
            ('XX-US-001', 1, 'done', 'blocks: [XX-TSK-010]' + chr(10), '## AC\n- [ ] verifica runtime non eseguita\n'),
            ('XX-US-001', 2, 'in_progress', 'depends_on:\n  - XX-TSK-001\nowner: Dev A\n', ''),
            ('XX-US-001', 3, 'todo', 'depends_on: [XX-TSK-004]\nowner: "Dev A (proposto)"\npriority: P0\n', ''),
            ('XX-US-002', 4, 'todo', 'updated: 2026-01-01\nowner: fe-dev-agent\n', 'Questo task e\' BLOCCATO dal backend, status: blocked\n'),
            ('XX-US-002', 5, 'superseded', 'superseded_by: XX-US-006/007' + chr(10) + 'updated: 2026-01-01' + chr(10), ''),
            ('XX-US-002', 6, 'on_hold', '', ''),
            ('XX-US-002', 7, 'wip', '', ''),
            ('XX-US-002', 8, 'todo', 'depends_on: [XX-TSK-005]\n', ''),
            ('XX-US-002', 9, 'todo', 'depends_on: [XX-TSK-999]\n', ''),
            ('XX-US-001', 10, 'completed', '', '')):
        f['%s/XX-EP-001/%s/XX-TSK-%03d.md' % (k, us, n)] = corpo_tsk(us, n, st, extra, corpo)
    return f


def forma_slug(rel, testo):
    """Seconda forma: ID senza prefisso, cartelle con slug; TSK 1-5 con `story:`/`epic:` nel frontmatter,
    TSK 6-10 senza campi di appartenenza (si ricavano dal path)."""
    parti = rel.split('/')
    rel = '/'.join([SLUG.get(c, c) for c in parti[:-1]] + [parti[-1]]).replace('XX-', '')
    testo = testo.replace('XX-', '')
    nome = parti[-1]
    if nome.startswith('XX-TSK-'):
        n = int(nome[7:10])
        riga_us = next(r for r in testo.split('\n') if r.startswith('us: '))
        nuova = ('story: %s\nepic: EP-001' % riga_us[4:]) if n <= 5 else None
        testo = testo.replace(riga_us + '\n', (nuova + '\n') if nuova else '')
    return rel, testo


def costruisci(root, forma='prefisso'):
    for rel, testo in sorted(file_kanban().items()):
        if forma == 'slug':
            rel, testo = forma_slug(rel, testo)
        scrivi(os.path.join(root, *rel.split('/')), testo)
    sh('git', 'init', '-q', cwd=root)
    sh('git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'add', '-A', cwd=root)
    sh('git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', 'kanban di prova', cwd=root)


def config(root, path):
    cfg = {
        'versione_schema': '1.1', 'factory_root': root.replace('\\', '/'), 'kanban_root': 'management/kanban',
        'progetti': [{'id': 'p', 'nome': 'Progetto di prova', 'repository_ids': ['r']}],
        'repository': [{'id': 'r', 'percorso': 'x', 'branch_base': 'main', 'prefissi_kanban': ['XX']}],
        'obiettivi': [{'id': 'ob', 'nome': 'Obiettivo di prova', 'data_target': '2026-10-23', 'tipo': 'interno',
                       'perimetro': [{'progetto_id': 'p', 'selettore': {'epiche': ['XX-EP-001']},
                                      'sotto_obiettivi': {'etichetta': 'Sezioni di prova', 'sezioni': ['a', 'b']}}],
                       'sezioni': [{'id': 'a', 'nome': 'Sezione A', 'us': ['XX-US-001'], 'stato': 'attiva', 'ondata': '1',
                                    'rilascio': {'data': '2026-10-05', 'tsk': 'XX-TSK-002'}, 'calendario': {'avvio': '2026-10-05'}},
                                   {'id': 'b', 'nome': 'Sezione B', 'us': ['XX-US-003'], 'stato': 'congelata', 'ondata': '-', 'fino_a': {'obiettivo': 'ob2'}}],
                       'us_ricetta': ['XX-US-002'], 'us_fuori_sezione': ['XX-US-099']},
                      {'id': 'ob2', 'nome': 'Obiettivo esterno', 'data_target': '2026-11-11', 'tipo': 'esterno', 'perimetro': []}],
        'stati': {'fatto': ['done', 'completed'], 'chiuso_senza_esito': ['superseded', 'cancelled', 'renamed', 'wontfix'],
                  'in_corso': ['in_progress', 'in-progress', 'review'], 'da_fare': ['todo', 'ready'],
                  'sospeso': ['on_hold', 'deferred'], 'bloccato': ['blocked']},
        'epiche_escluse': [],
        'team': [{'id': 'a', 'nome': 'Dev A', 'alias': []}, {'id': 'b', 'nome': 'Dev B', 'alias': [], 'impegno_pct': 50, 'nota': 'part time'}],
        'owner_non_persona': ['da designare'], 'owner_agente': ['fe-dev-agent'],
        'vista_pm': {'obiettivo_predefinito_id': 'ob', 'piano': [{'campo': 'window', 'etichetta': 'finestra'},
                                                                  {'campo': 'assignee', 'etichetta': 'assegnatari'},
                                                                  {'campo': 'owner', 'etichetta': 'owner'}]},
        'aggiornato': '2026-10-04T00:00:00Z',
    }
    json.dump(cfg, open(path, 'w', encoding='utf-8'))


def config_slug(root, path):
    """Config della seconda forma: stessi contenuti, ID senza prefisso, repository senza prefissi_kanban."""
    config(root, path)
    testo = open(path, encoding='utf-8').read().replace('XX-', '')
    cfg = json.loads(testo)
    for r in cfg['repository']:
        r['prefissi_kanban'] = []
    json.dump(cfg, open(path, 'w', encoding='utf-8'))


def run(script, *args, check=True):
    """Esegue uno script del motore come sottoprocesso."""
    return sh(PY, os.path.join(ROOT, script), *args, check=check)


def verifica_indipendenza_l0_statica():
    """Verifica che verifica_l0.py non importi moduli del motore (analisi statica AST).
    Regola di calcolo: Avanzamento = TSK fatti / (totali - chiusi senza esito).
    La verifica L0 reimplementa feriali() e gruppo_di() in modo diverso da aggrega.py:
    un bug nel motore non invalida il controllo.
    """
    src_path = os.path.join(ROOT, 'verifica_l0.py')
    moduli_vietati = {'aggrega', 'snapshot', 'controlla_config', 'applica_config', 'vista_pm', 'percorsi', '_comune'}
    try:
        src = open(src_path, encoding='utf-8').read()
        tree = ast.parse(src)
    except Exception as exc:
        ok(False, 'verifica_l0.py parsabile (AST): %s' % exc)
        return
    trovati = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in moduli_vietati:
                    trovati.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            modulo = (node.module or '').split('.')[0]
            if modulo in moduli_vietati:
                trovati.append(node.module)
    ok(not trovati, 'verifica_l0.py: nessun import di moduli del motore (trovati: %s)' % trovati)


def _misura(root, cfgp, tmp, tag, oggi='2026-10-04', store=None):
    """snapshot (dal commit) + misura; restituisce i path."""
    sp, mp = os.path.join(tmp, 'snap-%s.json' % tag), os.path.join(tmp, 'mis-%s.json' % tag)
    run('snapshot.py', '--config', cfgp, '--out', sp, '--fonte', 'commit', '--ref', 'HEAD')
    run('aggrega.py', '--config', cfgp, '--snapshot', sp, '--out', mp, '--oggi', oggi, *(['--store', store] if store else []))
    return sp, mp


def _senza_prefisso(dati):
    """Misura confrontabile fra le due forme: niente provenienza (sha e path), ID senza prefisso."""
    d = {k: v for k, v in dati.items() if k not in ('provenienza', 'qualita_dato')}
    return json.loads(json.dumps(d, sort_keys=True).replace('XX-', ''))


def verifica_forma_slug():
    """Seconda forma del kanban (ID senza prefisso, cartelle con slug, appartenenza dal frontmatter o dal path)."""
    tmp = tempfile.mkdtemp(prefix='coord-slug-')
    try:
        r1, r2 = os.path.join(tmp, 'prefisso'), os.path.join(tmp, 'slug')
        os.makedirs(r1)
        os.makedirs(r2)
        costruisci(r1, 'prefisso')
        costruisci(r2, 'slug')
        c1, c2 = os.path.join(tmp, 'config-p.json'), os.path.join(tmp, 'config-s.json')
        config(r1, c1)
        config_slug(r2, c2)
        s1, m1 = _misura(r1, c1, tmp, 'p')
        s2, m2 = _misura(r2, c2, tmp, 's')
        mp, ms = json.load(open(m1, encoding='utf-8')), json.load(open(m2, encoding='utf-8'))
        ok(ms['copertura']['tsk_totali'] == 10 and ms['obiettivi'][0]['epiche'][0]['id'] == 'EP-001',
           'forma slug: 10 TSK letti dalle cartelle «EP-001-epica-di-prova/US-00n-…», epica riconosciuta dall\'ID iniziale')
        ok(_senza_prefisso(mp) == _senza_prefisso(ms),
           'forma slug: la misura e\' identica a quella della forma con prefisso, a meno del prefisso')
        qp = sorted((f['livello'], f['codice'], f['entita'].replace('XX-', '')) for f in mp['qualita_dato'])
        qs = sorted((f['livello'], f['codice'], f['entita']) for f in ms['qualita_dato'])
        ok(qp == qs, 'forma slug: stesse anomalie di qualità del dato (%d)' % len(qs))
        sn = {e['id']: e for e in json.load(open(s2, encoding='utf-8'))['entita']}
        ok(all(sn['TSK-%03d' % n]['appartenenza_da'] == 'frontmatter' for n in range(1, 6))
           and all(sn['TSK-%03d' % n]['appartenenza_da'] == 'path' for n in range(6, 11))
           and sn['TSK-006']['us'] == 'US-002' and sn['TSK-006']['epica'] == 'EP-001',
           'forma slug: appartenenza dal frontmatter (story/epic) e, solo in mancanza, dal path')
        ok(run('verifica_l0.py', '--snapshot', s2, '--misura', m2, '--config', c2, check=False).returncode == 0,
           'forma slug: verifica L0 passa')
        a1, a2 = os.path.join(tmp, 'al-p.json'), os.path.join(tmp, 'al-s.json')
        run('controlla_config.py', '--config', c1, '--snapshot', s1, '--out', a1)
        run('controlla_config.py', '--config', c2, '--snapshot', s2, '--out', a2)
        k1 = sorted((x['tipo'], str(x.get('id') or x.get('valore')).replace('XX-', '')) for x in json.load(open(a1, encoding='utf-8'))['candidati'])
        k2 = sorted((x['tipo'], str(x.get('id') or x.get('valore'))) for x in json.load(open(a2, encoding='utf-8'))['candidati'])
        ok(k1 == k2 and ('epica_candidata', 'EP-002') in k2,
           'forma slug: stessi candidati di allineamento; epiche candidate anche senza prefissi_kanban')
        v2 = os.path.join(tmp, 'v-s.html')
        run('vista_pm.py', '--config', c2, '--misura', m2, '--out', v2, '--generato', 'test', '--allineamento', a2)
        ok(run('verifica_vista.py', '--misura', m2, '--html', v2, check=False).returncode == 0
           and sh(PY, os.path.join(ROOT, 'html_check.py'), v2, check=False).returncode == 0,
           'forma slug: vista completa (verifica_vista e html_check)')
        # applica_config riconosce un'epica la cui cartella ha uno slug
        prop = os.path.join(tmp, 'prop.json')
        json.dump({'proposte': [{'azione': 'escludi_epica', 'parametri': {'epica': 'EP-004'}}]}, open(prop, 'w', encoding='utf-8'))
        ok(run('applica_config.py', '--config', c2, '--snapshot', s2, '--proposte', prop, '--valida', check=False).returncode == 0,
           'forma slug: applica_config trova l\'epica nella cartella con slug')

        # frontmatter e path discordanti: vale il frontmatter, la discordanza e' un finding
        k = os.path.join(r2, 'management', 'kanban', 'EP-001-epica-di-prova')
        scrivi(os.path.join(k, 'US-001-sezione-a', 'TSK-011.md'), '---\nid: TSK-011\ntitle: "Task 11"\nstatus: todo\nstory: US-002\n---\n')
        scrivi(os.path.join(k, 'TSK-012.md'), '---\nid: TSK-012\ntitle: "Task 12"\nstatus: todo\n---\n')
        sh('git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'add', '-A', cwd=r2)
        sh('git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', 'discordanza', cwd=r2)
        s3, m3 = _misura(r2, c2, tmp, 'd')
        sn = {e['id']: e for e in json.load(open(s3, encoding='utf-8'))['entita']}
        q3 = {(f['codice'], f['entita']) for f in json.load(open(s3, encoding='utf-8'))['findings']}
        ok(sn['TSK-011']['us'] == 'US-002' and ('appartenenza-discordante', 'TSK-011') in q3,
           'appartenenza: story: nel frontmatter vince sulla cartella, la discordanza e\' segnalata')
        ok(sn['TSK-012']['us'] is None and sn['TSK-012']['epica'] == 'EP-001'
           and run('verifica_l0.py', '--snapshot', s3, '--misura', m3, '--config', c2, check=False).returncode == 0,
           'appartenenza: TSK direttamente sotto l\'epica (senza US) contato nell\'epica; L0 passa')

        # obiettivo senza sezioni (ne' ondate, ne' window): misurato, verificato, impaginato
        c4 = os.path.join(tmp, 'config-solo.json')
        cfg4 = json.load(open(c2, encoding='utf-8'))
        cfg4['obiettivi'] = [{'id': 'solo', 'nome': 'Obiettivo senza sezioni', 'data_target': '2026-10-23',
                              'perimetro': [{'progetto_id': 'p', 'selettore': {'epiche': ['EP-001']}}]}]
        cfg4['vista_pm'] = {'obiettivo_predefinito_id': 'solo'}
        json.dump(cfg4, open(c4, 'w', encoding='utf-8'))
        s4, m4 = _misura(r2, c4, tmp, 'solo')
        o4 = json.load(open(m4, encoding='utf-8'))['obiettivi'][0]
        a4 = os.path.join(tmp, 'al-solo.json')
        run('controlla_config.py', '--config', c4, '--snapshot', s4, '--out', a4)
        tipi4 = {x['tipo'] for x in json.load(open(a4, encoding='utf-8'))['candidati']}
        ok(o4['sezioni'] == [] and o4['conteggi']['totale'] == 12 and 'us_non_mappata' not in tipi4
           and run('verifica_l0.py', '--snapshot', s4, '--misura', m4, '--config', c4, check=False).returncode == 0,
           'obiettivo senza sezioni: tutti i TSK nel perimetro, nessuna US da classificare, L0 passa')
        u4 = os.path.join(tmp, 'uscite-solo')
        r = run('run.py', '--config', c4, '--uscite', u4, '--oggi', '2026-10-05', check=False)
        ok(r.returncode == 0 and 'VERIFICA L0: OK' in r.stdout and 'RIEPILOGO ' in r.stdout
           and glob.glob(os.path.join(u4, '2026-10-05', 'vista-pm_*.html')),
           'obiettivo senza sezioni: run.py completo (L0, vista, verifica della vista, html_check)')

        # store da_assegnare nella forma a lista (versioni precedenti di proponi_kanban): letto da aggrega e da L0
        st = os.path.join(tmp, 'store-lista.yaml')
        open(st, 'w', encoding='utf-8').write('- tsk_id: TSK-006\n  prima_vista: "2026-09-20"\n')
        s5, m5 = _misura(r2, c2, tmp, 'lista', oggi='2026-10-05', store=st)
        mm5 = json.load(open(m5, encoding='utf-8'))
        ok('da_assegnare_sha256' in mm5['provenienza']
           and any(x['codice'] in ('staleness', 'p0-staleness') for x in mm5['obiettivi'][0]['avvisi'])
           and run('verifica_l0.py', '--snapshot', s5, '--misura', m5, '--config', c2, '--store', st, check=False).returncode == 0,
           'store in forma di lista: eta calcolata, avviso di permanenza, L0 passa')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def verifica_senza_costanti_di_dominio():
    """Il motore non contiene nomi di persone, progetti, prefissi o handle di regola della factory derivata."""
    import re
    vietati = re.compile(r'musio|olivieri|portale|design.system|\bPS-|\bDS-|\bFAC-|\bADO\b|\bnpm\b|R\.(?:7|8|19|21)\b|code_repos|front-end',
                         re.I)
    trovati = []
    for f in sorted(glob.glob(os.path.join(ROOT, '*.py')) + glob.glob(os.path.join(ROOT, 'assets', '*'))):
        for n, riga in enumerate(open(f, encoding='utf-8'), 1):
            if vietati.search(riga):
                trovati.append('%s:%d' % (os.path.relpath(f, ROOT), n))
    ok(not trovati, 'nessuna costante di dominio della derivata nel motore (trovate: %s)' % trovati[:6])


def verifica_selettore_us(root, tmp):
    """selettore.us: dell'epica contano solo i TSK delle US elencate (misura, L0, controllo della config, proponi_kanban)."""
    cfgp = os.path.join(tmp, 'config-us.json')
    config(root, cfgp)
    cfg = json.load(open(cfgp, encoding='utf-8'))
    ob = cfg['obiettivi'][0]
    ob['perimetro'][0]['selettore']['us'] = ['XX-US-001', 'XX-US-003']
    ob['us_ricetta'] = []
    json.dump(cfg, open(cfgp, 'w', encoding='utf-8'))
    sp, mp = _misura(root, cfgp, tmp, 'us')
    o = json.load(open(mp, encoding='utf-8'))['obiettivi'][0]
    ok(o['conteggi']['totale'] == 4 and o['conteggi']['fatto'] == 2 and o['epiche'][0]['conteggi']['totale'] == 4
       and o['perimetro'][0]['conteggi']['totale'] == 4 and o['perimetro'][0]['us'] == ['XX-US-001', 'XX-US-003'],
       'selettore.us: obiettivo, epica e progetto contano solo i 4 TSK di XX-US-001 (non i 6 di XX-US-002)')
    ok(o['non_legati_a_sezione'] == [] and o['copertura']['tsk_perimetro'] == 4 and o['copertura']['tsk_non_legati'] == 0
       and sorted(v['tsk'] for v in o['tsk_aperti']) == ['XX-TSK-002', 'XX-TSK-003'],
       'selettore.us: niente lavoro non legato, copertura e TSK aperti solo delle US elencate')
    ok(run('verifica_l0.py', '--snapshot', sp, '--misura', mp, '--config', cfgp, check=False).returncode == 0,
       'selettore.us: L0 ricalcola con lo stesso filtro e passa')
    m = json.load(open(mp, encoding='utf-8'))
    m['obiettivi'][0]['perimetro'][0].pop('us')
    mt = os.path.join(tmp, 'mis-us-manomessa.json')
    json.dump(m, open(mt, 'w', encoding='utf-8'))
    ok(run('verifica_l0.py', '--snapshot', sp, '--misura', mt, '--config', cfgp, check=False).returncode == 1,
       'selettore.us: L0 blocca una misura senza le US del selettore')
    al = os.path.join(tmp, 'al-us.json')
    run('controlla_config.py', '--config', cfgp, '--snapshot', sp, '--out', al)
    nm = {c_['id'] for c_ in json.load(open(al, encoding='utf-8'))['candidati'] if c_['tipo'] == 'us_non_mappata'}
    ok('XX-US-002' not in nm and 'XX-US-004' not in nm, 'selettore.us: le US fuori dal selettore non sono da classificare')
    pk = os.path.join(tmp, 'prop-us.json')
    run('proponi_kanban.py', '--config', cfgp, '--ref', 'HEAD', '--oggi', '2026-10-04', '--out', pk)
    testo = open(pk, encoding='utf-8').read()
    ok('XX-TSK-006' not in testo and 'XX-TSK-009' not in testo, 'selettore.us: proponi_kanban ignora i TSK delle US fuori dal selettore')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    tmp = tempfile.mkdtemp(prefix='coord-test-')
    try:
        root = os.path.join(tmp, 'factory')
        os.makedirs(root)
        costruisci(root)
        sha8 = sh('git', 'rev-parse', 'HEAD', cwd=root).stdout.strip()[:8]
        cfgp = os.path.join(tmp, 'config.json')
        config(root, cfgp)
        s1, s2, m1, m2 = (os.path.join(tmp, n) for n in ('s1.json', 's2.json', 'm1.json', 'm2.json'))
        run('snapshot.py', '--config', cfgp, '--out', s1, '--fonte', 'commit', '--ref', 'HEAD')
        run('aggrega.py', '--config', cfgp, '--snapshot', s1, '--out', m1, '--oggi', '2026-10-04')
        m = json.load(open(m1, encoding='utf-8'))
        c = m['obiettivi'][0]['epiche'][0]['conteggi']

        # --- regole di calcolo e anti-allucinazione
        ok(c['totale'] == 10 and c['chiuso_senza_esito'] == 1 and c['base_calcolo'] == 9, 'chiusi senza esito fuori dal denominatore (9 su 10)')
        ok(c['fatto'] == 2, 'alias di stato: done e completed sono entrambi fatti')
        ok(c['sospeso'] == 1 and c['base_calcolo'] == 9, 'sospesi visibili e dentro il denominatore')
        ok(c['sconosciuto'] == 1, 'stato non previsto (wip) contato come non riconosciuto')
        ok(any(f['codice'] == 'stato-sconosciuto' and f['entita'] == 'XX-TSK-007' for f in m['qualita_dato']), 'stato non riconosciuto segnalato nella qualita\' del dato')
        ok(c['pct'] == 22, 'percentuale = 2/9 arrotondata (22)')
        ok(c['bloccato'] == 0 and c['da_fare'] == 4, 'anti-allucinazione: «BLOCCATO» nella prosa non cambia lo stato (da fare 4, bloccati 0)')
        ok(c['fatto'] == 2, 'anti-allucinazione: AC non spuntati non declassano un TSK done')
        el = m['obiettivi'][0]['epiche'][0]['elenchi']
        ok([x['id'] for x in el['chiuso_senza_esito']] == ['XX-TSK-005'] and [x['id'] for x in el['sospeso']] == ['XX-TSK-006']
           and [x['id'] for x in el['sconosciuto']] == ['XX-TSK-007'], 'elenchi degli ID dietro le voci da verificare')

        # --- classificazione
        sa = next(s for s in m['obiettivi'][0]['sezioni'] if s['id'] == 'a')['conteggi']
        sb = next(s for s in m['obiettivi'][0]['sezioni'] if s['id'] == 'b')['conteggi']
        ok(sa['totale'] == 4 and sa['fatto'] == 2 and sa['pct'] == 50, 'sezione A dalla mappa US→sezione (4 TSK, 50%)')
        ok(sb['totale'] == 0 and sb['pct'] is None, 'sezione senza TSK dichiarata vuota, nessuna percentuale inventata')
        nl = m['obiettivi'][0]['non_legati_a_sezione']
        ok(len(nl) == 1 and nl[0]['us'] == 'XX-US-002' and nl[0]['conteggi']['totale'] == 6 and nl[0]['us_ricetta'], 'TSK senza sezione mostrati con la loro US, non dedotti')
        ok(m['obiettivi'][0]['copertura']['tsk_in_sezioni'] + m['obiettivi'][0]['copertura']['tsk_non_legati'] == 10, 'ogni TSK contato una volta')

        # --- obiettivi
        o1, o2 = m['obiettivi']
        ok([o1['id'], o2['id']] == ['ob', 'ob2'], 'obiettivi in ordine di data target')
        ok(o1['giorni_lavorativi_rimasti'] == 15 and o2['giorni_lavorativi_rimasti'] == 28, 'giorni lavorativi per obiettivo (15 al 23/10, 28 all\'11/11)')
        ok(o1['riepilogo_sezioni'] == {'per_stato': {'attiva': 1, 'anticipabile': 0, 'congelata': 1}, 'avviate': 1, 'senza_tsk': 1},
           'riepilogo delle sezioni: 1 attiva e avviata, 1 congelata senza TSK')
        ok(o2['epiche'] == [] and o2['sezioni'] == [] and o2['copertura']['tsk_perimetro'] == 0, 'obiettivo senza perimetro: nessuna misura inventata')
        sez_a = next(x for x in o1['sezioni'] if x['id'] == 'a')
        sez_b = next(x for x in o1['sezioni'] if x['id'] == 'b')
        ok(sez_a['progetto_id'] == 'p' and sez_b['progetto_id'] == 'p', 'sotto-obiettivi: progetto della sezione dai sotto_obiettivi della config')
        ok(sez_a['avanzamento'] == 'in_lavorazione' and sez_b['avanzamento'] == 'senza_tsk', 'sotto-obiettivi: stato di avanzamento deterministico')
        ok(sez_a['rilascio'] == {'data': '2026-10-05', 'giorni_lavorativi_rimasti': 1, 'data_passata': False, 'tsk': 'XX-TSK-002',
                                 'tsk_trovato': True, 'tsk_titolo': 'Task 2', 'tsk_stato': 'in_progress', 'tsk_categoria': 'in_corso', 'fatto': False}
           and sez_b['rilascio'] is None, 'rilascio: data dalla config, stato del TSK di rilascio dal kanban, nessuna data inventata')
        ok(sez_a['calendario'] == {'pianificata_il': '2026-10-01', 'avvio': '2026-10-05', 'pronta_entro': None, 'giorni_a_pronta': None,
                                   'avvio_passato_non_avviata': False, 'pronta_scaduta_non_completata': False}
           and sez_b['calendario']['pianificata_il'] is None, 'calendario: pianificata il dal created della US, avvio dalla config, niente date dedotte')
        ok(sez_a['partenza'] == {'subito': ['XX-TSK-002'], 'in_attesa': [{'tsk': 'XX-TSK-003', 'titolo': 'Task 3', 'prerequisiti': [
               {'tsk': 'XX-TSK-004', 'titolo': 'Task 4', 'stato': 'todo', 'sezioni': [], 'stessa_sezione': False}]}]}
           and sez_b['partenza'] == {'subito': [], 'in_attesa': []},
           'partenza: subito i TSK aperti senza prerequisiti da completare, in attesa gli altri con il prerequisito; nessuna data dedotta')
        pa, pb = o1['persone']['per_persona']
        ok([v['tsk'] for v in pa['tsk']] == ['XX-TSK-003', 'XX-TSK-002'] and pa['tsk'][0]['nota_owner'] == 'proposto'
           and pa['per_priorita'] == {'P0': 1, '-': 1} and pa['prossima_scadenza'] == '2026-10-05' and pb['tsk'] == [] and pb['impegno_pct'] == 50,
           'persone: TSK per persona dal campo owner (con nota «proposto»), ordinati per priorità, prima scadenza della sezione')
        so = o1['persone']['senza_owner']
        ag = o1['persone']['agenti']
        ok([v['tsk'] for v in so] == ['XX-TSK-006', 'XX-TSK-007', 'XX-TSK-008', 'XX-TSK-009'] and [v['tsk'] for v in ag] == ['XX-TSK-004']
           and ag[0]['attesi_da'] == ['XX-TSK-003'] and not any(v['owner_non_riconosciuto'] for v in so),
           'persone: da designare = owner vuoto o generico; agenti a parte (owner tipo di agente), con i TSK che li attendono')
        ap = {v['tsk']: v for v in o1['tsk_aperti']}
        ok(sorted(ap) == ['XX-TSK-002', 'XX-TSK-003', 'XX-TSK-004', 'XX-TSK-006', 'XX-TSK-007', 'XX-TSK-008', 'XX-TSK-009']
           and ap['XX-TSK-003']['attende'] == ['XX-TSK-004'] and not ap['XX-TSK-003']['pronto'] and ap['XX-TSK-004']['pronto']
           and ap['XX-TSK-004']['gruppo'] == 'agente' and ap['XX-TSK-006']['non_assegnato'],
           'TSK aperti: owner per gruppo, prerequisiti non completati e «pronto» = da fare senza prerequisiti aperti')
        ok(o1['conteggi']['pct'] == 22 and o1['owner'] is None and o1['attende_obiettivi'] == ['ob2'] and o2['avvisi'] == [],
           'obiettivo: avanzamento complessivo, obiettivi attesi dalle sezioni congelate')
        ok([a_['codice'] for a_ in o1['avvisi']] == ['oltre-il-target'],
           'avvisi: solo le regole che scattano (sezione congelata oltre il target), nessun giudizio')
        ok([v['tsk'] for v in sez_a['tsk']] == ['XX-TSK-003', 'XX-TSK-001', 'XX-TSK-002', 'XX-TSK-010']
           and sez_a['tsk'][0]['persona_nome'] == 'Dev A' and sez_a['tsk'][0]['attende'] == ['XX-TSK-004']
           and not any(v['non_assegnato'] for v in sez_a['tsk']) and sez_b['tsk'] == [],
           'sezione: elenco completo dei TSK con persona e prerequisiti; i chiusi non sono «non assegnati»')
        ok(nl[0]['non_assegnati'] == ['XX-TSK-006', 'XX-TSK-007', 'XX-TSK-008', 'XX-TSK-009'],
           'lavoro non legato: TSK aperti non assegnati della US')
        bl = o1['bloccanti']
        ok([b['tsk'] for b in bl] == ['XX-TSK-004'] and bl[0]['attesi_da'] == ['XX-TSK-003'] and bl[0]['sezioni_attese'] == ['a']
           and bl[0]['serve_entro'] == '2026-10-05' and bl[0]['serve_entro_da'] == 'avvio' and bl[0]['serve_prima_della_sua_sezione'],
           'bloccanti: TSK aperto atteso da altri, «serve entro» = avvio della sezione in attesa; i prerequisiti chiusi non sono bloccanti')
        qq = {(f['codice'], f['entita']) for f in m['qualita_dato']}
        ok(('blocks-incompleto', 'XX-TSK-001') in qq and ('depends-on-incompleto', 'XX-TSK-010') in qq,
           'qualità: legami blocks/depends_on scritti da una parte sola segnalati in entrambe le direzioni')
        ok(sez_a['piano'] == [{'us': 'XX-US-001', 'window': 'lun 05/10', 'assignee': 'Dev A', 'owner': None}],
           'sotto-obiettivi: piano copiato dai campi del frontmatter indicati in config')
        ok([(d['obiettivo'], d['sezione']) for d in o2['dipendenti']] == [('ob', 'b')] and not o1['dipendenti'],
           'dipendenza fra obiettivi: la sezione B congelata attende l\'obiettivo esterno')
        ok('per_sottoperimetro' not in o1 and 'per_sottoperimetro' not in o2 and sez_a['sottoperimetro'] is None and sez_b['sottoperimetro'] is None,
           'sottoperimetri: senza il campo nelle sezioni nessun avanzamento per sottoperimetro, sottoperimetro della sezione null')
        ok(o1['ambiente_rilascio'] == 'test' and o2['ambiente_rilascio'] == 'test', 'ambiente di rilascio: default «test» se la config non lo indica')

        # --- A1: avanzamento_con_owner
        aco = o1['copertura'].get('avanzamento_con_owner')
        ok(aco is not None and 'fatto' in aco and 'totale_con_owner' in aco and 'base_calcolo' in aco and 'pct' in aco,
           'A1: copertura.avanzamento_con_owner presente con campi fatto/totale_con_owner/base_calcolo/pct')
        ok(aco['totale_con_owner'] == 2 and aco['fatto'] == 0 and aco['base_calcolo'] == 2 and aco['pct'] == 0,
           'A1: avanzamento_con_owner = 0 fatti su 2 TSK con owner (TSK-002 in_progress, TSK-003 todo); TSK-001 done non ha owner')
        ok(o1['copertura'].get('tsk_perimetro') == 10,
           'A1: denominatore avanzamento_totale non modificato (tsk_perimetro invariato)')
        ok(o2['copertura'].get('avanzamento_con_owner') is None,
           'A1: avanzamento_con_owner=None se nessun TSK con owner nel perimetro')

        # --- A2: senza_owner_summary e senza_owner_bucket
        summary = m.get('senza_owner_summary')
        ok(summary is not None and 'n_totali' in summary and 'n_p0_p1' in summary and 'sezioni' in summary,
           'A2: senza_owner_summary presente a livello misura con n_totali/n_p0_p1/sezioni')
        ok(summary['n_totali'] == 4 and isinstance(summary['sezioni'], list),
           'A2: senza_owner_summary.n_totali = 4 (TSK-006,007,008,009 senza owner)')
        bkt = o1['persone'].get('senza_owner_bucket')
        ok(bkt is not None and isinstance(bkt, list),
           'A2: persone.senza_owner_bucket presente come lista')
        ok(any(x.get('n_tsk', 0) > 0 for x in bkt) or len(bkt) > 0,
           'A2: senza_owner_bucket ha almeno un bucket con n_tsk')
        ok(all('priorita_max' in x and 'eta_mediana_giorni' in x for x in bkt),
           'A2: ogni bucket ha priorita_max e eta_mediana_giorni (None se no store)')

        # --- avvisi di sezione per TSK senza owner: tutti (invariato) e piu' della meta' (nuovo)
        m6a = os.path.join(tmp, 'm6a.json')
        cfg6a = json.load(open(cfgp, encoding='utf-8'))
        cfg6a['obiettivi'][0]['sezioni'] += [
            {'id': 'c', 'nome': 'Sezione C', 'us': ['XX-US-002'], 'stato': 'attiva'},
            {'id': 'd', 'nome': 'Sezione D', 'us': ['XX-US-001', 'XX-US-002'], 'stato': 'attiva'}]
        # fe-dev-agent come owner non persona: la sezione C resta senza nessun owner, la D oltre la metà
        cfg6a['owner_non_persona'] = sorted(set(cfg6a.get('owner_non_persona', [])) | {'fe-dev-agent'})
        cfgp6a = os.path.join(tmp, 'cfg6a.json')
        json.dump(cfg6a, open(cfgp6a, 'w', encoding='utf-8'))
        s6a = os.path.join(tmp, 's6a.json')
        run('snapshot.py', '--config', cfgp6a, '--out', s6a, '--fonte', 'commit', '--ref', 'HEAD')
        run('aggrega.py', '--config', cfgp6a, '--snapshot', s6a, '--out', m6a, '--oggi', '2026-10-04')
        ob6a = json.load(open(m6a, encoding='utf-8'))['obiettivi'][0]
        attesi6a = {}
        for sz in ob6a['sezioni']:
            ap_ = [v for v in ob6a['tsk_aperti'] if sz['id'] in v['sezioni']]
            ns_ = sum(1 for v in ap_ if v['non_assegnato'])
            if ap_ and ns_ == len(ap_):
                attesi6a[sz['id']] = 'sezione-da-designare'
            elif ap_ and 2 * ns_ > len(ap_):
                attesi6a[sz['id']] = 'sezione-da-designare-parziale'
        dich6a = {x['sezioni'][0]: x['codice'] for x in ob6a['avvisi']
                  if x['codice'] in ('sezione-da-designare', 'sezione-da-designare-parziale')}
        ok(dich6a == attesi6a and set(attesi6a.values()) == {'sezione-da-designare', 'sezione-da-designare-parziale'},
           "avvisi di sezione senza owner: tutti -> sezione-da-designare, oltre la metà -> parziale (%s)" % dich6a)
        piena = [x for x in ob6a['avvisi'] if x['codice'] == 'sezione-da-designare']
        ok(piena and all(x['livello'] == 'medio' and 'n_tsk' not in x for x in piena),
           'avviso con tutti i TSK senza owner invariato rispetto alla skill')
        parz = [x for x in ob6a['avvisi'] if x['codice'] == 'sezione-da-designare-parziale']
        ok(parz and all(x['livello'] == 'medio' and x['n_tsk'] == len(x['ids']) and 'n_p0_p1' in x for x in parz),
           'avviso parziale con n_tsk e n_p0_p1')
        ok(run('verifica_l0.py', '--snapshot', s6a, '--misura', m6a, '--config', cfgp6a, check=False).returncode == 0,
           'verifica L0 passa con gli avvisi di sezione senza owner')
        m6b = os.path.join(tmp, 'm6b.json')
        d6b = json.load(open(m6a, encoding='utf-8'))
        d6b['obiettivi'][0]['avvisi'] = [x for x in d6b['obiettivi'][0]['avvisi'] if x['codice'] != 'sezione-da-designare-parziale']
        json.dump(d6b, open(m6b, 'w', encoding='utf-8'))
        ok(run('verifica_l0.py', '--snapshot', s6a, '--misura', m6b, '--config', cfgp6a, check=False).returncode == 1,
           "verifica L0 fallisce se manca l'avviso parziale")

        # --- A7: store da_assegnare.yaml (fixture congelata e store assente)
        store_p = os.path.join(tmp, 'da_assegnare-test.yaml')
        open(store_p, 'w', encoding='utf-8').write(
            'da_assegnare:\n'
            '  - tsk_id: XX-TSK-006\n'
            '    prima_vista: "2026-09-20"\n'
            '  - tsk_id: XX-TSK-007\n'
            '    prima_vista: "2026-10-03"\n'
        )
        m_a7 = os.path.join(tmp, 'm_a7.json')
        run('aggrega.py', '--config', cfgp, '--snapshot', s1, '--out', m_a7, '--oggi', '2026-10-05',
            '--store', store_p, '--stale-alert-days', '7', '--escalation-days', '14')
        ma7 = json.load(open(m_a7, encoding='utf-8'))
        ok('da_assegnare_sha256' in ma7.get('provenienza', {}),
           'A7: provenienza.da_assegnare_sha256 presente quando store esiste')
        avvisi_a7 = [a_['codice'] for a_ in ma7['obiettivi'][0].get('avvisi', [])]
        ok('p0-staleness' in avvisi_a7 or 'staleness' in avvisi_a7,
           'A7: avviso SLA presente quando eta > soglia (TSK-006 prima_vista 2026-09-20 = ~11 gg lavorativi > 7)')
        bkt_a7 = ma7['obiettivi'][0]['persone'].get('senza_owner_bucket', [])
        ok(any(x.get('eta_mediana_giorni') is not None for x in bkt_a7),
           'A7: eta_mediana_giorni valorizzata nei bucket quando store presente')
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', m_a7, '--config', cfgp,
               '--store', store_p, check=False).returncode == 0,
           'A7: verifica L0 con store passa su misura corretta')
        m_a7_no = os.path.join(tmp, 'm_a7_no.json')
        run('aggrega.py', '--config', cfgp, '--snapshot', s1, '--out', m_a7_no, '--oggi', '2026-10-05')
        ma7no = json.load(open(m_a7_no, encoding='utf-8'))
        ok('da_assegnare_sha256' not in ma7no.get('provenienza', {}),
           'A7: provenienza.da_assegnare_sha256 assente quando store non esiste')
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', m_a7_no, check=False).returncode == 0,
           'A7: verifica L0 senza store passa correttamente (store opzionale)')
        # determinismo: stessa terna (commit, config, store, --oggi) -> stessi byte
        m_a7b = os.path.join(tmp, 'm_a7b.json')
        run('aggrega.py', '--config', cfgp, '--snapshot', s1, '--out', m_a7b, '--oggi', '2026-10-05',
            '--store', store_p, '--stale-alert-days', '7', '--escalation-days', '14')
        ok(open(m_a7, 'rb').read() == open(m_a7b, 'rb').read(),
           'A7: determinismo — stessa terna (commit + config + store) e --oggi -> stessi byte')
        # verifica_l0 fallisce se eta_mediana_giorni alterata
        ma7_man = json.load(open(m_a7, encoding='utf-8'))
        for bkt in ma7_man['obiettivi'][0]['persone'].get('senza_owner_bucket', []):
            if bkt.get('eta_mediana_giorni') is not None:
                bkt['eta_mediana_giorni'] = bkt['eta_mediana_giorni'] + 999
                break
        mm_a7 = os.path.join(tmp, 'mm_a7.json')
        json.dump(ma7_man, open(mm_a7, 'w', encoding='utf-8'))
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', mm_a7, '--config', cfgp,
               '--store', store_p, check=False).returncode == 1,
           'A7: verifica L0 fallisce con eta_mediana_giorni alterata')
        ma7_sla = json.load(open(m_a7, encoding='utf-8'))
        ma7_sla['obiettivi'][0]['avvisi'] = [x for x in ma7_sla['obiettivi'][0]['avvisi'] if x['codice'] not in ('staleness', 'p0-staleness')]
        ms_a7 = os.path.join(tmp, 'ms_a7.json')
        json.dump(ma7_sla, open(ms_a7, 'w', encoding='utf-8'))
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', ms_a7, '--config', cfgp,
               '--store', store_p, check=False).returncode == 1,
           "A7: verifica L0 fallisce se manca l'avviso di permanenza senza owner")
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', m_a7, '--config', cfgp, check=False).returncode == 1,
           'A7: verifica L0 fallisce se la misura ha avvisi di permanenza ma lo store non viene passato')

        # --- prerequisiti
        p = m['obiettivi'][0]['epiche'][0]['prerequisiti']
        ok([x['tsk'] for x in p['in_attesa_prerequisito_aperto']] == ['XX-TSK-003'], 'prerequisito aperto: XX-TSK-003 attende XX-TSK-004')
        ok([x['tsk'] for x in p['prerequisito_da_riconciliare']] == ['XX-TSK-008'], 'prerequisito annullato: da riconciliare, non soddisfatto')
        ok([x['tsk'] for x in p['prerequisito_fuori_perimetro']] == ['XX-TSK-009'], 'prerequisito inesistente: fuori perimetro (indeterminato)')
        ok(all(x['tsk'] != 'XX-TSK-002' for v in p.values() for x in v), 'prerequisito completato: nessuna attesa')

        # --- riproducibilita' e fonte
        run('snapshot.py', '--config', cfgp, '--out', s2, '--fonte', 'commit', '--ref', 'HEAD')
        run('aggrega.py', '--config', cfgp, '--snapshot', s2, '--out', m2, '--oggi', '2026-10-04')
        ok(open(s1, 'rb').read() == open(s2, 'rb').read() and open(m1, 'rb').read() == open(m2, 'rb').read(), 'riproducibile: stesso commit ⇒ stessi byte')

        # --- verifica L0
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', m1, check=False).returncode == 0, 'verifica L0 passa su una misura corretta')
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', m1, '--config', cfgp, check=False).returncode == 0,
           'verifica L0 con config: tabella stati disgiunta e ri-normalizzazione indipendente coerente')
        cfg_dop = json.load(open(cfgp, encoding='utf-8'))
        cfg_dop['stati']['in_corso'].append('Done')
        cfgd = os.path.join(tmp, 'config-doppia.json')
        json.dump(cfg_dop, open(cfgd, 'w', encoding='utf-8'))
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', m1, '--config', cfgd, check=False).returncode == 1,
           'verifica L0 blocca una tabella stati non disgiunta (Done in due categorie)')
        manom = json.load(open(m1, encoding='utf-8'))
        manom['obiettivi'][0]['epiche'][0]['conteggi']['fatto'] += 1
        mm = os.path.join(tmp, 'manomessa.json')
        json.dump(manom, open(mm, 'w', encoding='utf-8'))
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', mm, check=False).returncode == 1, 'verifica L0 blocca un numero manomesso')
        manom2 = json.load(open(m1, encoding='utf-8'))
        manom2['obiettivi'][0]['epiche'][0]['elenchi']['chiuso_senza_esito'] = []
        mm2 = os.path.join(tmp, 'manomessa2.json')
        json.dump(manom2, open(mm2, 'w', encoding='utf-8'))
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', mm2, check=False).returncode == 1, 'verifica L0 blocca un elenco di ID manomesso')
        for nome, ritocco in (('riepilogo delle sezioni', lambda x: x['obiettivi'][0]['riepilogo_sezioni'].update(avviate=0)),
                              ('giorni lavorativi', lambda x: x['obiettivi'][1].update(giorni_lavorativi_rimasti=27)),
                              ('dipendenze fra obiettivi', lambda x: x['obiettivi'][1].update(dipendenti=[])),
                              ('obiettivo mancante', lambda x: x['obiettivi'].pop()),
                              ('progetto della sezione', lambda x: x['obiettivi'][0]['sezioni'][0].update(progetto_id=None)),
                              ('avanzamento della sezione', lambda x: x['obiettivi'][0]['sezioni'][0].update(avanzamento='completata')),
                              ('piano della sezione', lambda x: x['obiettivi'][0]['sezioni'][0]['piano'][0].update(window='altro')),
                              ('rilascio della sezione', lambda x: x['obiettivi'][0]['sezioni'][0]['rilascio'].update(fatto=True)),
                              ('calendario della sezione', lambda x: x['obiettivi'][0]['sezioni'][0]['calendario'].update(pianificata_il='2026-09-01')),
                              ('partenza della sezione', lambda x: x['obiettivi'][0]['sezioni'][0]['partenza'].update(in_attesa=[])),
                              ('assegnazioni', lambda x: x['obiettivi'][0]['persone']['senza_owner'].pop()),
                              ('TSK della sezione', lambda x: x['obiettivi'][0]['sezioni'][0]['tsk'][0].update(non_assegnato=True)),
                              ('non assegnati della US', lambda x: x['obiettivi'][0]['non_legati_a_sezione'][0]['non_assegnati'].pop()),
                              ('punti di attenzione', lambda x: x['obiettivi'][0]['avvisi'].append(
                                  {'codice': 'inventato', 'livello': 'alto', 'testo': 'rischio alto', 'ids': [], 'regola': '-'})),
                              ('TSK aperti', lambda x: x['obiettivi'][0]['tsk_aperti'][0].update(pronto=not x['obiettivi'][0]['tsk_aperti'][0]['pronto'])),
                              ('avanzamento complessivo', lambda x: x['obiettivi'][0]['conteggi'].update(pct=47)),
                              ('bloccanti prioritari', lambda x: x['obiettivi'][0]['bloccanti'][0].update(serve_entro='2026-12-31')),
                              ('owner obiettivo', lambda x: x['obiettivi'][0].update(owner='Qualcuno')),
                              ('sottoperimetro della sezione', lambda x: x['obiettivi'][0]['sezioni'][0].update(sottoperimetro='test')),
                              ('ambiente di rilascio', lambda x: x['obiettivi'][0].update(ambiente_rilascio='preprod')),
                              ('avanzamento per sottoperimetro', lambda x: x['obiettivi'][0].update(
                                  per_sottoperimetro={'non_indicato': x['obiettivi'][0]['conteggi']}))):
            mx = json.load(open(m1, encoding='utf-8'))
            ritocco(mx)
            mmx = os.path.join(tmp, 'manomessa-x.json')
            json.dump(mx, open(mmx, 'w', encoding='utf-8'))
            ok(run('verifica_l0.py', '--snapshot', s1, '--misura', mmx, '--config', cfgp, check=False).returncode == 1,
               'verifica L0 blocca %s manomesso' % nome)

        # --- controllo della configurazione
        al = os.path.join(tmp, 'allineamento.json')
        run('controlla_config.py', '--config', cfgp, '--snapshot', s1, '--out', al)
        cand = json.load(open(al, encoding='utf-8'))['candidati']
        tipi = {(x['tipo'], x.get('id') or x.get('valore')) for x in cand}
        ok(('us_non_mappata', 'XX-US-004') in tipi, 'controllo config: US nuova non mappata segnalata')
        ok(('us_config_assente', 'XX-US-099') in tipi, 'controllo config: US citata in config ma assente dal kanban')
        ok(('stato_non_mappato', 'wip') in tipi, 'controllo config: valore di status non previsto')
        ok(('epica_candidata', 'XX-EP-002') in tipi and ('epica_candidata', 'XX-EP-004') in tipi and ('epica_candidata', 'XX-EP-003') not in tipi,
           'controllo config: tutte le epiche aperte non classificate sono candidate, anche quelle vecchie; le chiuse no')
        ok(len(cand) == 5, 'controllo config: nessun candidato in più')
        q = {(f['codice'], f['entita']) for f in m['qualita_dato']}
        ok(('superseded-by-non-valido', 'XX-TSK-005') in q, "qualità: superseded_by 'XX-US-006/007' segnalato come non leggibile")
        ok(('updated-non-aggiornato', 'XX-TSK-005') in q, "qualità: updated più vecchio dell'ultimo commit segnalato")
        ok(('updated-non-aggiornato', 'XX-TSK-004') not in q, 'qualità: updated vecchio su un TSK aperto non segnalato (solo i chiusi)')
        ok(('us-non-aggiornata', 'XX-US-001') in q and ('us-non-aggiornata', 'XX-US-002') not in q,
           'qualità: US todo con TSK avviati o fatti segnalata (XX-US-001), US senza TSK avviati no (XX-US-002)')
        ok(('chiusura-senza-metadati', 'XX-TSK-005') not in q, 'qualità: con superseded_by (anche malformato) non si chiede altro metadato')
        corpo = [f for f in m['qualita_dato'] if f['codice'] == 'esito-corpo-diverso']
        gd = [f for f in m['qualita_dato'] if f['codice'] == 'giorno-data-incoerente']
        ok(len(gd) == 1 and gd[0]['entita'] == 'XX-US-002' and '«mer 06/10»' in gd[0]['evidenza'] and 'è mar' in gd[0]['evidenza'],
           'qualità: giorno della settimana incoerente con la data segnalato (solo dove c\'è un anno: created del file)')
        ok(len(corpo) == 1 and corpo[0]['entita'] == 'XX-EP-001' and 'XX-TSK-005 → done' in corpo[0]['evidenza']
           and 'XX-EP-001.md:7:' in corpo[0]['evidenza'],
           'qualità: epica che dichiara done un TSK superseded segnalata con file e riga; ultima menzione rettificata e TSK aperto no')

        # --- vista con riquadri di verifica
        out = os.path.join(tmp, 'v.html')
        run('vista_pm.py', '--config', cfgp, '--misura', m1, '--out', out, '--generato', 'test', '--allineamento', al)
        h = open(out, encoding='utf-8').read()
        ok(all('data-pane="%s"' % t in h for t in ('pm', 'ops', 'q')) and 'Portafoglio obiettivi' in h and 'Piano operativo' in h
           and 'Qualità dato' in h and 'unpkg' not in h and 'googleapis' not in h,
           'vista: tre schede (Vista PM, Piano operativo, Qualità dato), nessuna risorsa scaricata da internet')
        ok('data-ob="ob"' in h and 'data-ob="ob2"' in h and '← O2' in h and '→ O1' in h and 'fuori dal kanban: nessuna misura' in h
           and 'esempio' not in h.lower().replace('es. «mer', ''),
           'vista: portafoglio con i soli obiettivi della config, dipendenze fra obiettivi, nessun obiettivo di esempio')
        ok('22%' in h and '2/9 fatti' in h and 'Dettaglio nel tempo · O1' in h and 'data-k="s-a"' in h and 'data-k="t-XX-TSK-003"' in h
           and '⧗ attende XX-TSK-004' in h and 'R 05/10' in h and 'senza date nel piano' in h and 'data-k="u-XX-US-002"' in h,
           'vista: dettaglio ad albero obiettivo → progetto → sezione → TSK, con rilascio, prerequisiti e US fuori dalle sezioni')
        ok('→ O1 · Obiettivo di prova' in h and 'Attende questo obiettivo con la sezione Sezione B' in h,
           'vista: nel dettaglio dell\'obiettivo esterno compaiono l\'obiettivo e le sezioni che lo attendono')
        ok('Bloccanti prioritari' in h and 'class="bl alt"' not in h.split('Bloccanti prioritari')[0], 'vista: riquadro dei bloccanti prioritari')
        ok('data-var="b"' in h and 'class="nb-n"' in h and '<path d=' in h and 'class="var v-a"' in h and 'Dettaglio nel tempo · O1 e dipendenze' in h,
           'vista: dettaglio nel tempo con le varianti 1a (albero) e 1b (rete con nodi e frecce), come nel template')
        ok('US XX-US-001 · pianificata il 01/10/2026 · avvio 05/10/2026 · pronta entro non indicata · rilascio in test 05/10/2026 (XX-TSK-002 · status in_progress)' in h
           and '<b>finestra</b> lun 05/10' in h and '<b>assegnatari</b> Dev A' in h,
           'vista: nessuna perdita rispetto alla vista precedente — piano e calendario della sezione con US, date in chiaro e TSK di rilascio')
        ok('Vista tabella · conteggi per stato' in h and '<th>Sospese</th>' in h and '<th>Chiuse senza esito</th>' in h,
           'vista: nessuna perdita — tabella dei conteggi per stato')
        ok('Persone e carico' in h and 'Dev A' in h and '~50% · part time' in h and '⚠ Da designare' in h and 'Agenti' in h
           and 'Punti di attenzione' in h and 'regola: sezione congelata fino a un obiettivo con data successiva' in h,
           'vista: persone e carico con i gruppi Da designare e Agenti; punti di attenzione con la regola dichiarata')
        ok(h.count('class="tk"') == 7 and 'Pronto da avviare' in h and 'In attesa' in h and 'attende XX-TSK-004' in h
           and 'agente · fe-dev-agent' in h and '⚠ da designare' in h and 'id="kpi-pronti"' in h,
           'vista: piano operativo con tutti i TSK aperti, owner (persona, agente, da designare) e stato pronto/in attesa')
        ok('Chiedi una verifica: 1 chiusi senza esito' in h and 'XX-TSK-005 (Task 5) — status: superseded' in h and sha8 in h,
           'vista: prompt di verifica dei chiusi senza esito con ID, sintesi e commit')
        ok('XX-TSK-003 (Task 3) → attende XX-TSK-004 (Task 4)' in h, 'vista: prompt dei prerequisiti in attesa con le coppie di ID')
        ok('la US di sezione non ha TSK registrati' in h, 'vista: prompt per la sezione senza TSK')
        ok('Strumento factory per la VERIFICA: git log -p sul file del TSK' in h and 'controllo a mano dei campi di chiusura' in h,
           'vista: per i chiusi senza esito la verifica è sul git log, sui successori e sui campi di chiusura')
        ok('cooperative locking (EP-053)' in h and 'active_sessions.py conflicts' in h and 'R.21' not in h,
           'vista: lo strumento di modifica controlla i claim advisory (cooperative locking), senza handle di regola della derivata')
        ok('NON VERIFICABILE: solo se la fonte è fuori dalla factory' in h and 'NON TROVATO' in h and 'VERIFICATO' in h,
           'vista: ogni prompt impone lo standard VERIFICATO / NON TROVATO / NON VERIFICABILE')
        ok('git log --oneline %s..HEAD -- management/kanban' % sha8 in h and 'verifica su HEAD' in h,
           'vista: il prompt confronta il commit con HEAD e, se il report è vecchio, verifica su HEAD')
        ok('NON TROVATO, non NON VERIFICABILE' in h and 'la US e l&#x27;epica padre riportano lo stesso esito' in h,
           'vista: assenza di traccia nei file = NON TROVATO; i chiusi senza esito chiedono la coerenza di US ed epica padre')
        ok('Check 4g «Coerenza scheduler/depends_on»' in h, 'vista: il prompt dei prerequisiti indica il Check 4g della factory')
        ok(h.count('Strumento factory per l&#x27;eventuale MODIFICA o RICONCILIAZIONE, solo dopo la mia conferma esplicita: agente `tpm`') >= 3,
           'vista: ogni prompt indica il tpm come strumento di modifica, dopo conferma')
        ok('id_registry_check.py' in h and 'per la taskificazione' in h, 'vista: il prompt della sezione vuota indica la taskificazione via tpm e registro ID')
        ok('non lanciare /session-start (nemmeno l&#x27;avvio automatico' in h and 'pull, fetch o sync' in h and 'sprint.md non è una fonte' in h,
           'vista: i prompt vietano session-start (anche automatico) e pull, e indicano il frontmatter come fonte degli stati')
        ok('check-4au.md' in h and 'US con uno status incoerente con i propri TSK' in h, 'vista: anomalie di roll-up con il proprio riquadro e il check 4au')
        ok('La configurazione del report non è allineata al kanban: 5 elementi' in h, 'vista: riquadro di configurazione non allineata')
        ok('✔ In linea' in h and 'Stato calcolato dagli avvisi a regole, non una valutazione' in h and '– non misurato' in h,
           'vista: stato In linea / A rischio / Critico calcolato dagli avvisi, con la regola in legenda; obiettivo non misurato dichiarato')
        ok(sh(PY, os.path.join(ROOT, 'html_check.py'), out, check=False).returncode == 0, 'vista: html_check OK (niente caratteri di controllo)')
        ok(run('verifica_vista.py', '--misura', m1, '--html', out, check=False).returncode == 0,
           'verifica della vista: tutti gli elementi della misura sono visibili nella pagina')
        nb = os.path.join(tmp, 'narr-buona.md')
        open(nb, 'w', encoding='utf-8').write("# Lettura\n- L'epica XX-EP-001 è al 22%, 2 TSK fatti su 9 nel calcolo [F:obiettivi[id=ob].epiche[0].conteggi] [F:obiettivi[0].epiche[0].id]\n"
                                              "- La sezione Sezione A ha il rilascio il 05/10 [F:obiettivi[0].sezioni[id=a].rilascio]\n")
        nj = os.path.join(tmp, 'narr.json')
        ok(run('verifica_citazioni.py', '--misura', m1, '--narrativa', nb, '--out', nj, check=False).returncode == 0,
           'narrativa: frasi con citazioni, numeri, ID e date presenti nei campi citati = verificata')
        for nome, testo in (('numero sbagliato', "- L'epica è al 30% [F:obiettivi[0].epiche[0].conteggi]\n"),
                            ('senza citazione', "- L'epica è al 22%\n"),
                            ('percorso inesistente', "- Al 22% [F:obiettivi[0].nonesiste]\n"),
                            ('ID non citato', "- XX-TSK-777 è fatto [F:obiettivi[0].epiche[0].conteggi]\n"),
                            ('data non citata', "- Rilascio il 09/10 [F:obiettivi[0].sezioni[id=a].rilascio]\n")):
            nx = os.path.join(tmp, 'narr-x.md')
            open(nx, 'w', encoding='utf-8').write(testo)
            ok(run('verifica_citazioni.py', '--misura', m1, '--narrativa', nx, check=False).returncode == 1, 'narrativa bloccata: %s' % nome)
        vn = os.path.join(tmp, 'v-narr.html')
        run('vista_pm.py', '--config', cfgp, '--misura', m1, '--out', vn, '--generato', 'test', '--narrativa', nj)
        hn = open(vn, encoding='utf-8').read()
        ok('Lettura assistita' in hn and 'non deterministica · citazioni verificate' in hn and 'al 22%, 2 TSK fatti su 9' in hn
           and run('verifica_vista.py', '--misura', m1, '--html', vn, check=False).returncode == 0,
           'vista: lettura assistita in un riquadro separato e dichiarato, senza perdere dati')
        hx = os.path.join(tmp, 'v-ridotta.html')
        open(hx, 'w', encoding='utf-8').write(h.replace('lun 05/10', '').replace('Sezione B', 'Sezione'))
        ok(run('verifica_vista.py', '--misura', m1, '--html', hx, check=False).returncode == 1,
           'verifica della vista: una pagina che perde un dato (finestra, nome di sezione) blocca la consegna')

        # --- applicazione delle proposte (su una copia della config)
        cfg2 = os.path.join(tmp, 'cfgdir', 'config.json')
        os.makedirs(os.path.dirname(cfg2))
        shutil.copy(cfgp, cfg2)
        prima = hashlib.sha256(open(cfg2, 'rb').read()).hexdigest()
        prop = os.path.join(tmp, 'proposte.json')
        json.dump({'proposte': [
            {'azione': 'aggiungi_a_sezione', 'parametri': {'us': 'XX-US-004', 'sezione': 'a'}, 'motivazione': 't', 'fonte': 't', 'confidenza': 'alta'},
            {'azione': 'rimuovi_us', 'parametri': {'us': 'XX-US-099'}, 'motivazione': 't', 'fonte': 't', 'confidenza': 'alta'},
            {'azione': 'mappa_stato', 'parametri': {'valore': 'wip', 'categoria': 'in_corso'}, 'motivazione': 't', 'fonte': 't', 'confidenza': 'media'},
            {'azione': 'aggiungi_epica', 'parametri': {'epica': 'XX-EP-002', 'progetto_id': 'p'}, 'motivazione': 't', 'fonte': 't', 'confidenza': 'alta'},
            {'azione': 'escludi_epica', 'parametri': {'epica': 'XX-EP-004'}, 'motivazione': 't', 'fonte': 't', 'confidenza': 'alta'},
        ]}, open(prop, 'w', encoding='utf-8'))
        r = run('applica_config.py', '--config', cfg2, '--snapshot', s1, '--proposte', prop, '--valida', check=False)
        ok(r.returncode == 0 and hashlib.sha256(open(cfg2, 'rb').read()).hexdigest() == prima, 'applica --valida: proposte valide, config non toccata')
        cattive = os.path.join(tmp, 'cattive.json')
        json.dump({'proposte': [{'azione': 'aggiungi_a_sezione', 'parametri': {'us': 'XX-US-777', 'sezione': 'a'}}]}, open(cattive, 'w', encoding='utf-8'))
        r = run('applica_config.py', '--config', cfg2, '--snapshot', s1, '--proposte', cattive, '--scelte', 'tutte', check=False)
        ok(r.returncode == 1 and hashlib.sha256(open(cfg2, 'rb').read()).hexdigest() == prima, 'applica: US inesistente rifiutata, config non toccata')
        doppia = os.path.join(tmp, 'doppia.json')
        json.dump({'proposte': [{'azione': 'mappa_stato', 'parametri': {'valore': 'Done', 'categoria': 'in_corso'}}]}, open(doppia, 'w', encoding='utf-8'))
        r = run('applica_config.py', '--config', cfg2, '--snapshot', s1, '--proposte', doppia, '--valida', check=False)
        ok(r.returncode == 1, 'applica: mappa_stato di un valore già mappato (Done ~ done) rifiutata')
        r = run('applica_config.py', '--config', cfg2, '--snapshot', s1, '--proposte', prop, '--scelte', 'tutte', check=False)
        # storico salvato in <dir_config>/storico/<operatore>/config-*.json
        # per 'config.json': operatore = 'config' (fallback: nome file senza estensione)
        storico_glob = os.path.join(os.path.dirname(cfg2), 'storico', '*', 'config-*.json')
        ok(r.returncode == 0 and bool(glob.glob(storico_glob)), 'applica: modifiche scritte con copia nello storico per operatore')
        s5, al5 = os.path.join(tmp, 's5.json'), os.path.join(tmp, 'al5.json')
        run('snapshot.py', '--config', cfg2, '--out', s5, '--fonte', 'commit', '--ref', 'HEAD')
        run('controlla_config.py', '--config', cfg2, '--snapshot', s5, '--out', al5)
        ok(json.load(open(al5, encoding='utf-8'))['conteggio'] == 0, 'dopo l\'applicazione: nessun candidato residuo')

        cfg7 = os.path.join(tmp, 'cfgdir7', 'config.json')
        os.makedirs(os.path.dirname(cfg7))
        c7 = json.load(open(cfgp, encoding='utf-8'))
        c7['obiettivi'].append({'id': 'altro', 'sezioni': [{'id': 'z', 'nome': 'Z', 'us': ['XX-US-099', 'XX-US-001'], 'stato': 'attiva', 'ondata': '-'}]})
        json.dump(c7, open(cfg7, 'w', encoding='utf-8'))
        rim = os.path.join(tmp, 'rim.json')
        json.dump({'proposte': [{'azione': 'rimuovi_us', 'parametri': {'us': 'XX-US-099'}}]}, open(rim, 'w', encoding='utf-8'))
        r = run('applica_config.py', '--config', cfg7, '--snapshot', s1, '--proposte', rim, '--scelte', 'tutte', check=False)
        z = next(o for o in json.load(open(cfg7, encoding='utf-8'))['obiettivi'] if o['id'] == 'altro')['sezioni'][0]
        ok(r.returncode == 0 and z['us'] == ['XX-US-001'], 'applica: rimuovi_us toglie la US anche da una sezione fuori dall\'obiettivo predefinito')
        c8 = json.load(open(cfgp, encoding='utf-8'))
        c8['obiettivi'][0]['perimetro'][0]['selettore']['epiche'] = ['XX-EP-004']
        c8['obiettivi'].append({'id': 'altro', 'perimetro': [{'progetto_id': 'q', 'selettore': {'epiche': ['XX-EP-001']}}], 'sezioni': []})
        json.dump(c8, open(cfg7, 'w', encoding='utf-8'))
        fuori = os.path.join(tmp, 'fuori.json')
        json.dump({'proposte': [{'azione': 'us_fuori_sezione', 'parametri': {'us': 'XX-US-004'}}]}, open(fuori, 'w', encoding='utf-8'))
        r = run('applica_config.py', '--config', cfg7, '--snapshot', s1, '--proposte', fuori, '--scelte', 'tutte', check=False)
        c8 = json.load(open(cfg7, encoding='utf-8'))
        ok(r.returncode == 0 and 'XX-US-004' in c8['obiettivi'][-1].get('us_fuori_sezione', [])
           and 'XX-US-004' not in c8['obiettivi'][0].get('us_fuori_sezione', []),
           'applica: us_fuori_sezione va nell\'obiettivo il cui perimetro contiene l\'epica della US')

        cfg3 = os.path.join(tmp, 'cfgdir3', 'config.json')
        os.makedirs(os.path.dirname(cfg3))
        c3 = json.load(open(cfgp, encoding='utf-8'))
        c3['obiettivi'][0]['perimetro'][0]['sotto_obiettivi']['sezioni'] = ['a']
        json.dump(c3, open(cfg3, 'w', encoding='utf-8'))
        al6, m6, v6 = (os.path.join(tmp, n) for n in ('al6.json', 'm6.json', 'v6.html'))
        run('controlla_config.py', '--config', cfg3, '--snapshot', s1, '--out', al6)
        ok(any(x['tipo'] == 'sezione_non_attribuita' and x['id'] == 'b' for x in json.load(open(al6, encoding='utf-8'))['candidati']),
           'controllo config: sezione che nessun progetto elenca nei sotto_obiettivi segnalata')
        run('aggrega.py', '--config', cfg3, '--snapshot', s1, '--out', m6, '--oggi', '2026-10-04')
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', m6, '--config', cfg3, check=False).returncode == 0,
           'sezione non attribuita: misura coerente con la config (progetto assente)')
        run('vista_pm.py', '--config', cfg3, '--misura', m6, '--out', v6, '--generato', 'test')
        ok('Sezioni non attribuite a un progetto del perimetro' in open(v6, encoding='utf-8').read(), 'vista: sezione non attribuita mostrata a parte, non dedotta')
        attr = os.path.join(tmp, 'attr.json')
        json.dump({'proposte': [{'azione': 'attribuisci_sezione', 'parametri': {'sezione': 'b', 'progetto_id': 'p'}}]}, open(attr, 'w', encoding='utf-8'))
        r = run('applica_config.py', '--config', cfg3, '--snapshot', s1, '--proposte', attr, '--scelte', 'tutte', check=False)
        run('controlla_config.py', '--config', cfg3, '--snapshot', s1, '--out', al6)
        ok(r.returncode == 0 and not any(x['tipo'] == 'sezione_non_attribuita' for x in json.load(open(al6, encoding='utf-8'))['candidati']),
           'applica: attribuisci_sezione rende la sezione sotto-obiettivo del progetto')
        c4 = json.load(open(cfg3, encoding='utf-8'))
        c4['obiettivi'][0]['sezioni'][0]['rilascio'] = {'data': '2026-10-09', 'tsk': 'XX-TSK-002'}
        json.dump(c4, open(cfg3, 'w', encoding='utf-8'))
        run('controlla_config.py', '--config', cfg3, '--snapshot', s1, '--out', al6)
        ok([x['id'] for x in json.load(open(al6, encoding='utf-8'))['candidati'] if x['tipo'] == 'rilascio_non_coerente'] == ['a'],
           'controllo config: data di rilascio che non compare né nel TSK né nella window della US segnalata')
        ril = os.path.join(tmp, 'ril.json')
        json.dump({'proposte': [{'azione': 'imposta_rilascio', 'parametri': {'sezione': 'a', 'data': '2026-10-05', 'tsk': 'XX-TSK-002'}}]},
                  open(ril, 'w', encoding='utf-8'))
        r = run('applica_config.py', '--config', cfg3, '--snapshot', s1, '--proposte', ril, '--scelte', 'tutte', check=False)
        run('controlla_config.py', '--config', cfg3, '--snapshot', s1, '--out', al6)
        ok(r.returncode == 0 and not any(x['tipo'] == 'rilascio_non_coerente' for x in json.load(open(al6, encoding='utf-8'))['candidati']),
           'applica: imposta_rilascio corregge la data, il controllo torna pulito')
        c5 = json.load(open(cfg3, encoding='utf-8'))
        c5['obiettivi'][0]['sezioni'][0]['calendario'] = {'avvio': '2026-10-05', 'pronta_entro': '2026-10-08'}
        json.dump(c5, open(cfg3, 'w', encoding='utf-8'))
        run('controlla_config.py', '--config', cfg3, '--snapshot', s1, '--out', al6)
        cc = [x for x in json.load(open(al6, encoding='utf-8'))['candidati'] if x['tipo'] == 'calendario_non_coerente']
        ok(len(cc) == 1 and 'pronta_entro 08/10 non compare' in cc[0]['motivo'] and '«pronta entro» dopo il rilascio' in cc[0]['motivo'],
           'controllo config: data di calendario assente dalla window e fuori ordine rispetto al rilascio segnalata')
        cal = os.path.join(tmp, 'cal.json')
        json.dump({'proposte': [{'azione': 'imposta_calendario', 'parametri': {'sezione': 'a', 'avvio': '2026-10-05', 'pronta_entro': '2026-10-05'}}]},
                  open(cal, 'w', encoding='utf-8'))
        r = run('applica_config.py', '--config', cfg3, '--snapshot', s1, '--proposte', cal, '--scelte', 'tutte', check=False)
        run('controlla_config.py', '--config', cfg3, '--snapshot', s1, '--out', al6)
        ok(r.returncode == 0 and not any(x['tipo'] == 'calendario_non_coerente' for x in json.load(open(al6, encoding='utf-8'))['candidati']),
           'applica: imposta_calendario corregge le date, il controllo torna pulito')
        c8 = json.load(open(cfg3, encoding='utf-8'))
        c8['team'] = [x for x in c8['team'] if x['id'] != 'a']
        json.dump(c8, open(cfg3, 'w', encoding='utf-8'))
        run('controlla_config.py', '--config', cfg3, '--snapshot', s1, '--out', al6)
        om = sorted(x['valore'] for x in json.load(open(al6, encoding='utf-8'))['candidati'] if x['tipo'] == 'owner_non_mappato')
        ok(om == ['Dev A', 'Dev A (proposto)'], 'controllo config: owner che non è né persona del team né non-persona segnalato')
        mo = os.path.join(tmp, 'mo.json')
        json.dump({'proposte': [{'azione': 'mappa_owner', 'parametri': {'valore': 'Dev A', 'persona_id': 'b'}}]}, open(mo, 'w', encoding='utf-8'))
        r = run('applica_config.py', '--config', cfg3, '--snapshot', s1, '--proposte', mo, '--scelte', 'tutte', check=False)
        run('controlla_config.py', '--config', cfg3, '--snapshot', s1, '--out', al6)
        ok(r.returncode == 0 and not any(x['tipo'] == 'owner_non_mappato' for x in json.load(open(al6, encoding='utf-8'))['candidati']),
           'applica: mappa_owner aggiunge l\'alias alla persona e risolve anche la variante «(proposto)»')
        m7, v7 = os.path.join(tmp, 'm7.json'), os.path.join(tmp, 'v7.html')
        run('aggrega.py', '--config', cfg3, '--snapshot', s1, '--out', m7, '--oggi', '2026-10-07')
        c7 = next(x for x in json.load(open(m7, encoding='utf-8'))['obiettivi'][0]['sezioni'] if x['id'] == 'a')
        ok(c7['calendario']['pronta_scaduta_non_completata'] and not c7['calendario']['avvio_passato_non_avviata'] and c7['rilascio']['data_passata'],
           'calendario: dopo la data, sezione non completata = fatto datato; avviata = nessun avviso sull\'avvio')
        ok(run('verifica_l0.py', '--snapshot', s1, '--misura', m7, '--config', cfg3, check=False).returncode == 0,
           'verifica L0 ricalcola il calendario con un oggi diverso')
        run('vista_pm.py', '--config', cfg3, '--misura', m7, '--out', v7, '--generato', 'test')
        h7 = open(v7, encoding='utf-8').read()
        ok('data «pronta entro» passata, sezione non completata' in h7 and 'rilascio passato, non completato' in h7,
           'vista: scadenze passate dette come fatti, senza giudizi')
        av7 = [a_['codice'] for a_ in json.load(open(m7, encoding='utf-8'))['obiettivi'][0]['avvisi']]
        ok('scadenza-passata' in av7, 'avvisi: «pronta entro» passata con sezione non completata = avviso alto')

        # --- file sporco dopo il commit (per ultimo: modifica il working tree)
        tsk(root, 'XX-US-002', 4, 'done')
        s3, m3, s4 = (os.path.join(tmp, n) for n in ('s3.json', 'm3.json', 's4.json'))
        run('snapshot.py', '--config', cfgp, '--out', s3, '--fonte', 'commit', '--ref', 'HEAD')
        run('aggrega.py', '--config', cfgp, '--snapshot', s3, '--out', m3, '--oggi', '2026-10-04')
        ok(json.load(open(m3, encoding='utf-8'))['obiettivi'][0]['epiche'][0]['conteggi'] == c, 'dal commit: una modifica non committata non entra nei numeri')
        run('snapshot.py', '--config', cfgp, '--out', s4, '--fonte', 'worktree')
        nc = json.load(open(s4, encoding='utf-8'))['provenienza']['kanban_non_committati']
        ok(nc == ['management/kanban/XX-EP-001/XX-US-002/XX-TSK-004.md'], 'dal disco: il file non committato e\' elencato')

        # --- determinismo del rilevamento candidati
        # due run di controlla_config.py sullo stesso (commit, config) producono JSON identici byte per byte
        al_det1 = os.path.join(tmp, 'al-det1.json')
        al_det2 = os.path.join(tmp, 'al-det2.json')
        run('controlla_config.py', '--config', cfgp, '--snapshot', s1, '--out', al_det1)
        run('controlla_config.py', '--config', cfgp, '--snapshot', s1, '--out', al_det2)
        ok(open(al_det1, 'rb').read() == open(al_det2, 'rb').read(),
           'determinismo: due run di controlla_config.py sullo stesso (commit, config) producono output identici byte per byte')

        # --- sotto-perimetri: sezioni con elenco esplicito di TSK
        cfg_sp = json.load(open(cfgp, encoding='utf-8'))
        o_sp = cfg_sp['obiettivi'][0]
        o_sp['sezioni'] += [{'id': 'a-test', 'nome': 'Sezione A · test', 'sottoperimetro': 'test', 'us': ['XX-US-001'], 'tsk': ['XX-TSK-003'],
                             'stato': 'attiva', 'ondata': '1', 'calendario': {}},
                            {'id': 'conf', 'nome': 'Configurazione', 'sottoperimetro': 'configurazione', 'us': ['XX-US-002'],
                             'tsk': ['XX-TSK-004', 'XX-TSK-998'], 'stato': 'attiva', 'ondata': '1', 'calendario': {}}]
        o_sp['perimetro'][0]['sotto_obiettivi']['sezioni'] += ['a-test', 'conf']
        cfgp_sp, s_sp, m_sp, al_sp = (os.path.join(tmp, n) for n in ('config-sp.json', 's-sp.json', 'm-sp.json', 'al-sp.json'))
        json.dump(cfg_sp, open(cfgp_sp, 'w', encoding='utf-8'))
        run('snapshot.py', '--config', cfgp_sp, '--out', s_sp, '--fonte', 'commit', '--ref', 'HEAD')
        run('aggrega.py', '--config', cfgp_sp, '--snapshot', s_sp, '--out', m_sp, '--oggi', '2026-10-04')
        o_m = json.load(open(m_sp, encoding='utf-8'))['obiettivi'][0]
        tot = {s['id']: s['conteggi']['totale'] for s in o_m['sezioni']}
        nl_sp = {g['us']: g['conteggi']['totale'] for g in o_m['non_legati_a_sezione']}
        ok(tot['a'] == 3 and tot['a-test'] == 1 and tot['conf'] == 1 and nl_sp == {'XX-US-002': 5},
           'sotto-perimetri: il TSK elencato esce dalla sezione della sua US ed entra solo nel sotto-perimetro')
        ok(o_m['copertura']['tsk_in_sezioni'] + o_m['copertura']['tsk_non_legati'] == 10, 'sotto-perimetri: ogni TSK contato una volta')
        r_sp = sh(PY, os.path.join(ROOT, 'verifica_l0.py'), '--snapshot', s_sp, '--misura', m_sp, '--config', cfgp_sp, check=False)
        ok(r_sp.returncode == 0, 'sotto-perimetri: la verifica L0 indipendente conferma la misura')
        run('controlla_config.py', '--config', cfgp_sp, '--snapshot', s_sp, '--out', al_sp, '--ref', 'HEAD')
        c_sp = json.load(open(al_sp, encoding='utf-8'))['candidati']
        ok([x['id'] for x in c_sp if x['tipo'] == 'tsk_config_assente'] == ['XX-TSK-998'], 'sotto-perimetri: TSK elencato e assente dal kanban segnalato')
        o_sp['sezioni'] = [s for s in o_sp['sezioni'] if s['id'] != 'a'] + [
            {'id': 'a-dev', 'nome': 'Sezione A · sviluppo', 'us': ['XX-US-001'], 'tsk': ['XX-TSK-003'], 'stato': 'attiva', 'ondata': '1', 'calendario': {}}]
        json.dump(cfg_sp, open(cfgp_sp, 'w', encoding='utf-8'))
        run('snapshot.py', '--config', cfgp_sp, '--out', s_sp, '--fonte', 'commit', '--ref', 'HEAD')
        run('controlla_config.py', '--config', cfgp_sp, '--snapshot', s_sp, '--out', al_sp, '--ref', 'HEAD')
        c_sp = json.load(open(al_sp, encoding='utf-8'))['candidati']
        ok([x['id'] for x in c_sp if x['tipo'] == 'tsk_fuori_sottoperimetro'] == ['XX-TSK-002', 'XX-TSK-006', 'XX-TSK-007', 'XX-TSK-008', 'XX-TSK-009']
           and [x['id'] for x in c_sp if x['tipo'] == 'tsk_in_piu_sottoperimetri'] == ['XX-TSK-003'],
           'sotto-perimetri: TSK aperti di US divise (solo in sezioni con tsk) e non elencati segnalati; TSK in due sotto-perimetri segnalato')

        # --- avanzamento per sottoperimetro e ambiente di rilascio
        cfg_k = json.load(open(cfgp, encoding='utf-8'))
        o_k = cfg_k['obiettivi'][0]
        o_k['ambiente_rilascio'] = 'preprod'
        o_k['sezioni'][0]['sottoperimetro'] = 'sviluppo'
        # d condivide i TSK della US-001 con a (stesso sottoperimetro), e quelli della US-002 con e (sottoperimetro diverso)
        o_k['sezioni'] += [{'id': 'd', 'nome': 'Sezione D', 'sottoperimetro': 'sviluppo', 'us': ['XX-US-001', 'XX-US-002'], 'stato': 'attiva'},
                           {'id': 'e', 'nome': 'Rilascio e utenze', 'sottoperimetro': 'configurazione', 'us': ['XX-US-002'], 'stato': 'attiva'}]
        o_k['perimetro'][0]['sotto_obiettivi']['sezioni'] += ['d', 'e']
        cfgp_k, s_k, m_k, m_k2, v_k = (os.path.join(tmp, n) for n in ('config-k.json', 's-k.json', 'm-k.json', 'm-k2.json', 'v-k.html'))
        json.dump(cfg_k, open(cfgp_k, 'w', encoding='utf-8'))
        run('snapshot.py', '--config', cfgp_k, '--out', s_k, '--fonte', 'commit', '--ref', 'HEAD')
        run('aggrega.py', '--config', cfgp_k, '--snapshot', s_k, '--out', m_k, '--oggi', '2026-10-04')
        run('aggrega.py', '--config', cfgp_k, '--snapshot', s_k, '--out', m_k2, '--oggi', '2026-10-04')
        mk = json.load(open(m_k, encoding='utf-8'))
        ok_, ok2 = mk['obiettivi']
        psp = ok_['per_sottoperimetro']
        ok(sorted(psp) == ['configurazione', 'non_indicato', 'sviluppo'] and psp['sviluppo']['totale'] == 10 and psp['sviluppo']['fatto'] == 2
           and psp['sviluppo']['base_calcolo'] == 9 and psp['sviluppo']['pct'] == 22,
           'per sottoperimetro: TSK condivisi fra due sezioni dello stesso sottoperimetro contati una volta (10, non 14)')
        ok(psp['configurazione']['totale'] == 6 and psp['configurazione']['fatto'] == 0 and psp['configurazione']['chiuso_senza_esito'] == 1,
           'per sottoperimetro: un TSK in sezioni di sottoperimetri diversi conta in ciascuno (US-002 in sviluppo e configurazione)')
        ok(psp['non_indicato']['totale'] == 0 and psp['non_indicato']['pct'] is None,
           'per sottoperimetro: le sezioni senza campo sotto non_indicato, nessuna percentuale inventata')
        ok([x['sottoperimetro'] for x in ok_['sezioni']] == ['sviluppo', None, 'sviluppo', 'configurazione'],
           'sottoperimetro della sezione copiato dalla config, null se assente')
        ok(ok_['ambiente_rilascio'] == 'preprod' and ok2['ambiente_rilascio'] == 'test' and 'per_sottoperimetro' not in ok2,
           'ambiente di rilascio dalla config; obiettivo senza sezioni senza avanzamento per sottoperimetro')
        ok(open(m_k, 'rb').read() == open(m_k2, 'rb').read(), 'per sottoperimetro: riproducibile al byte')
        ok(run('verifica_l0.py', '--snapshot', s_k, '--misura', m_k, '--config', cfgp_k, check=False).returncode == 0,
           'per sottoperimetro: la verifica L0 indipendente conferma la misura')
        for nome, ritocco in (('conteggio', lambda x: x['obiettivi'][0]['per_sottoperimetro']['sviluppo'].update(fatto=3)),
                              ('voce mancante', lambda x: x['obiettivi'][0]['per_sottoperimetro'].pop('configurazione')),
                              ('blocco assente', lambda x: x['obiettivi'][0].pop('per_sottoperimetro')),
                              ('sottoperimetro della sezione', lambda x: x['obiettivi'][0]['sezioni'][3].update(sottoperimetro='test'))):
            mx = json.load(open(m_k, encoding='utf-8'))
            ritocco(mx)
            mmx = os.path.join(tmp, 'manomessa-k.json')
            json.dump(mx, open(mmx, 'w', encoding='utf-8'))
            ok(run('verifica_l0.py', '--snapshot', s_k, '--misura', mmx, '--config', cfgp_k, check=False).returncode == 1,
               'verifica L0 blocca l\'avanzamento per sottoperimetro manomesso (%s)' % nome)
        mx = json.load(open(m_k, encoding='utf-8'))
        mx['obiettivi'][0]['per_sottoperimetro']['sviluppo']['fatto'] = 3
        mmx = os.path.join(tmp, 'manomessa-k.json')
        json.dump(mx, open(mmx, 'w', encoding='utf-8'))
        ok(run('verifica_l0.py', '--snapshot', s_k, '--misura', mmx, check=False).returncode == 1,
           'verifica L0 blocca l\'avanzamento per sottoperimetro manomesso anche senza config')
        run('vista_pm.py', '--config', cfgp_k, '--misura', m_k, '--out', v_k, '--generato', 'test')
        hk = open(v_k, encoding='utf-8').read()
        ok('class="sp sp-configurazione"' in hk and 'Rilascio e utenze<span class="sp sp-configurazione"' in hk
           and '>Infra · rilascio</span>' in hk and 'class="sp sp-sviluppo"' in hk,
           'vista: sezioni con sottoperimetro configurazione etichettate «Infra · rilascio» (testo e classe dedicata), le altre con la loro etichetta')
        ok('Per sottoperimetro' in hk and '2/9 fatti · 22%' in hk and '0/5 fatti · 0%' in hk
           and 'sottoperimetro della sezione, dalla config' in hk,
           'vista: avanzamento per sottoperimetro nel riepilogo dell\'obiettivo e voce in legenda')
        ok('rilascio in preprod 05/10/2026' in hk and 'Rilascio in preprod · Sezione A' in hk
           and 'rilascio in test 05/10' not in hk and 'Rilascio in test' not in hk and '◆ rilascio in preprod / test' in hk,
           'vista: «rilascio in <ambiente_rilascio>» al posto del testo fisso «rilascio in test»')
        ok(run('verifica_vista.py', '--misura', m_k, '--html', v_k, check=False).returncode == 0,
           'verifica della vista: sottoperimetri e avanzamento per sottoperimetro visibili')
        hk2 = os.path.join(tmp, 'v-k-ridotta.html')
        open(hk2, 'w', encoding='utf-8').write(hk.replace('>Infra · rilascio<', '><'))
        ok(run('verifica_vista.py', '--misura', m_k, '--html', hk2, check=False).returncode == 1,
           'verifica della vista: una pagina senza l\'etichetta «Infra · rilascio» blocca la consegna')

        # --- regressione L0: bug sintetico in aggrega.py rilevato da verifica_l0.py indipendente
        # copia il motore in una directory temporanea e altera aggrega.py con un bug sintetico
        bug_dir = os.path.join(tmp, 'bug-motore')
        shutil.copytree(ROOT, bug_dir)
        src_bug = os.path.join(bug_dir, 'aggrega.py')
        codice_orig = open(src_bug, encoding='utf-8').read()
        # bug sintetico: incrementa artificialmente il conteggio dei fatti di 99
        targa = "    c['base_calcolo'] = c['totale'] - c['chiuso_senza_esito']"
        sostituzione = "    c['fatto'] += 99\n    c['base_calcolo'] = c['totale'] - c['chiuso_senza_esito']"
        codice_bug = codice_orig.replace(targa, sostituzione)
        if codice_bug == codice_orig:
            ok(False, 'regressione L0: la stringa target non trovata in aggrega.py (test non eseguito)')
        else:
            open(src_bug, 'w', encoding='utf-8').write(codice_bug)
            m_bug = os.path.join(tmp, 'm-bug.json')
            r_bug = sh(PY, os.path.join(bug_dir, 'aggrega.py'),
                       '--config', cfgp, '--snapshot', s1, '--out', m_bug, '--oggi', '2026-10-04', check=False)
            if r_bug.returncode != 0:
                ok(False, 'regressione L0: aggrega.py con bug sintetico non eseguibile (%s)' % r_bug.stderr[:200])
            else:
                r_l0_bug = sh(PY, os.path.join(ROOT, 'verifica_l0.py'),
                              '--snapshot', s1, '--misura', m_bug, check=False)
                ok(r_l0_bug.returncode == 1, 'regressione L0: verifica_l0.py rileva il bug sintetico in aggrega.py (esce con 1)')
                output_l0 = r_l0_bug.stdout + r_l0_bug.stderr
                ok(any(kw in output_l0 for kw in ('atteso', 'dichiarato', 'calcolato', 'diverge', 'scostamento', 'fatto', 'STOP')),
                   'regressione L0: il messaggio riporta i valori in conflitto')

        verifica_selettore_us(root, tmp)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # verifica indipendenza statica di verifica_l0.py (nessun import del motore)
    verifica_indipendenza_l0_statica()

    # seconda forma del kanban, obiettivo senza sezioni, store in lista, nessuna costante di dominio
    verifica_forma_slug()
    verifica_senza_costanti_di_dominio()

    for esito, nome in ESITI:
        print(('OK    ' if esito else 'FALLITO ') + nome)
    passati = sum(1 for e, _ in ESITI if e)
    print('\n%d/%d casi passano' % (passati, len(ESITI)))
    return 0 if passati == len(ESITI) else 1


def test_main():
    """Entry point per pytest: esegue l'intera suite e verifica che tutti i casi passino."""
    ESITI.clear()
    esito = main()
    assert esito == 0, 'casi falliti: %s' % [n for e, n in ESITI if not e]


if __name__ == '__main__':
    sys.exit(main())
