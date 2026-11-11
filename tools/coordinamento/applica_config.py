#!/usr/bin/env python3
"""Applica alla configurazione le proposte di allineamento confermate dall'utente. Deterministico, con backup.

    python tools/coordinamento/applica_config.py --config analytics/coordinamento/config-<operatore>.json --snapshot snapshot.json --proposte proposte.json --valida
    python tools/coordinamento/applica_config.py --config analytics/coordinamento/config-<operatore>.json --snapshot snapshot.json --proposte proposte.json --scelte 1,3,4
    python tools/coordinamento/applica_config.py ... --scelte tutte

proposte.json (dal subagente di allineamento):
  {"proposte": [{"azione": "...", "parametri": {...}, "motivazione": "...", "fonte": "...", "confidenza": "alta|media|bassa"}]}
Azioni ammesse:
  aggiungi_a_sezione {us, sezione}         nuova_sezione {us, sezione, nome, stato, ondata?, progetto_id?}
  attribuisci_sezione {sezione, progetto_id}  (la sezione diventa sotto-obiettivo di quel progetto del perimetro)
  imposta_rilascio {sezione, data AAAA-MM-GG, tsk?}  (data pianificata e TSK di rilascio della sezione)
  imposta_calendario {sezione, avvio?, pronta_entro?}  (date AAAA-MM-GG lette dalla window della US)
  mappa_owner {valore, persona_id} oppure {valore, non_persona: true}  (valore del campo owner dei TSK)
  us_fuori_sezione {us}                    us_ricetta {us}
  rimuovi_us {us}                          sostituisci_us {vecchia, nuova}
  mappa_stato {valore, categoria}          aggiungi_epica {epica, progetto_id}
  escludi_epica {epica}                    ignora {}
  aggiungi_tsk {tsk, sezione}              rimuovi_tsk {tsk, sezione}  (sotto-perimetri: sezioni con elenco `tsk`)
Ogni ID viene controllato sullo snapshot (US) o sul kanban al commit (epiche). Con --valida non scrive nulla.
Prima di scrivere salva una copia in analytics/coordinamento/storico/<operatore>/. Le azioni su sezioni e US gia' in config
valgono per l'obiettivo che le contiene, come i candidati di controlla_config.py; us_fuori_sezione e us_ricetta vanno
nell'obiettivo il cui perimetro contiene l'epica della US (se e' uno solo); nuove sezioni ed epiche, e i casi ambigui,
nell'obiettivo predefinito della vista.
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

from kanban_ids import cartella_e_di, nel_perimetro
from percorsi import operatore_da_config, risolvi_factory_root

STATI_VALIDI = {'attiva', 'anticipabile', 'congelata'}


def errore(msg):
    print('ERRORE: ' + msg)
    return msg


def _operatore(config_path):
    return operatore_da_config(config_path)


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True)
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--proposte', required=True)
    ap.add_argument('--scelte', help='numeri (1-based) separati da virgola, oppure tutte')
    ap.add_argument('--valida', action='store_true')
    ap.add_argument('--ref', help='commit su cui verificare le epiche (default: quello misurato dallo snapshot)')
    a = ap.parse_args(argv)

    cfg = json.load(open(a.config, encoding='utf-8'))
    snap = json.load(open(a.snapshot, encoding='utf-8'))
    a.ref = a.ref or snap['provenienza'].get('ref_sha') or snap['provenienza']['factory_head']
    prop = json.load(open(a.proposte, encoding='utf-8')).get('proposte', [])
    us_kanban = {e['id'] for e in snap['entita'] if e['tipo'] == 'US'}
    epica_us = {e['id']: e.get('epica') for e in snap['entita'] if e['tipo'] == 'US'}
    tsk_kanban = {e['id'] for e in snap['entita'] if e['tipo'] == 'TSK'}
    ob = next(o for o in cfg['obiettivi'] if o['id'] == cfg['vista_pm']['obiettivo_predefinito_id'])
    ob.setdefault('sezioni', [])
    # controlla_config.py genera candidati su tutti gli obiettivi: una sezione si cerca ovunque,
    # altrimenti rimuovi_us su una sezione fuori dall'obiettivo predefinito non toglie nulla
    sezioni, obiettivo_di = {}, {}
    for o in cfg['obiettivi']:
        for s in o.get('sezioni', []):
            sezioni[s['id']] = s
            obiettivo_di[s['id']] = o
    categorie = set(cfg['stati'])
    root, kanban = risolvi_factory_root(cfg, a.config), cfg.get('kanban_root', 'management/kanban')

    progetti = {p['progetto_id']: p for p in ob.get('perimetro', [])}

    def progetti_di(sezione):
        o = obiettivo_di.get(sezione, ob)
        return {p['progetto_id']: p for p in o.get('perimetro', [])}

    def attribuisci(sezione, progetto_id):
        """La sezione diventa sotto-obiettivo di un solo progetto del perimetro del suo obiettivo."""
        for p in obiettivo_di.get(sezione, ob).get('perimetro', []):
            so = p.get('sotto_obiettivi')
            if so:
                so['sezioni'] = [x for x in so.get('sezioni', []) if x != sezione]
        so = progetti_di(sezione)[progetto_id].setdefault('sotto_obiettivi', {'etichetta': None, 'sezioni': []})
        so['sezioni'] = so.get('sezioni', []) + [sezione]

    def obiettivo_della_us(u):
        """L'obiettivo il cui perimetro contiene l'epica della US; il predefinito se nessuno o piu' di uno."""
        trovati = [o for o in cfg['obiettivi'] if nel_perimetro(epica_us.get(u), u, o)]
        return trovati[0] if len(trovati) == 1 else ob

    def epica_esiste(ep):
        """Il file <kanban>/<cartella dell'epica>/<epica>.md esiste al commit; la cartella puo' avere uno slug."""
        r = subprocess.run(['git', '-C', root, 'ls-tree', '-r', '--name-only', a.ref, '--', kanban + '/'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        base = len(kanban.rstrip('/').split('/'))
        for p in r.stdout.splitlines():
            parti = p.split('/')
            if len(parti) == base + 2 and parti[-1] == ep + '.md' and cartella_e_di(parti[base], ep):
                return True
        return False

    if a.scelte in (None, '') and not a.valida:
        print('ERRORE: indica --scelte (es. 1,3 oppure tutte) o --valida')
        return 2
    scelte = range(1, len(prop) + 1) if a.valida or a.scelte == 'tutte' else [int(x) for x in a.scelte.split(',') if x.strip()]

    errori, fatte = [], []
    for n in scelte:
        if not 1 <= n <= len(prop):
            errori.append(errore('proposta %d inesistente' % n))
            continue
        p = prop[n - 1]
        az, par = p.get('azione'), p.get('parametri', {}) or {}
        us = par.get('us')
        if us and az not in ('rimuovi_us',) and us not in us_kanban:
            errori.append(errore('proposta %d: US %s non esiste nel kanban' % (n, us)))
            continue
        if az == 'aggiungi_a_sezione':
            if par.get('sezione') not in sezioni:
                errori.append(errore('proposta %d: sezione %r inesistente' % (n, par.get('sezione'))))
                continue
            if not a.valida:
                sezioni[par['sezione']]['us'] = sorted(set(sezioni[par['sezione']]['us']) | {us})
        elif az == 'nuova_sezione':
            if not par.get('sezione') or par['sezione'] in sezioni or par.get('stato') not in STATI_VALIDI or not par.get('nome'):
                errori.append(errore('proposta %d: nuova sezione non valida (id nuovo, nome e stato %s richiesti)' % (n, sorted(STATI_VALIDI))))
                continue
            if par.get('progetto_id') and par['progetto_id'] not in progetti:
                errori.append(errore('proposta %d: progetto %r fuori dal perimetro' % (n, par['progetto_id'])))
                continue
            if not a.valida:
                s = {'id': par['sezione'], 'nome': par['nome'], 'us': [us], 'stato': par['stato']}
                if par.get('ondata') not in (None, ''):
                    s['ondata'] = str(par['ondata'])  # l'ondata e' opzionale: solo se il kanban la indica
                ob['sezioni'].append(s)
                obiettivo_di[s['id']] = ob
                sezioni[s['id']] = s
                if par.get('progetto_id'):
                    attribuisci(s['id'], par['progetto_id'])
        elif az == 'imposta_rilascio':
            tsk_ok = not par.get('tsk') or par['tsk'] in {e['id'] for e in snap['entita'] if e['tipo'] == 'TSK'}
            try:
                datetime.date.fromisoformat(str(par.get('data')))
                data_ok = True
            except ValueError:
                data_ok = False
            if par.get('sezione') not in sezioni or not tsk_ok or not data_ok:
                errori.append(errore('proposta %d: sezione %r, data %r (AAAA-MM-GG) o TSK %r non validi' % (n, par.get('sezione'), par.get('data'), par.get('tsk'))))
                continue
            if not a.valida:
                sezioni[par['sezione']]['rilascio'] = {'data': str(par['data']), 'tsk': par.get('tsk')}
        elif az == 'imposta_calendario':
            valide = True
            for k in ('avvio', 'pronta_entro'):
                if par.get(k):
                    try:
                        datetime.date.fromisoformat(str(par[k]))
                    except ValueError:
                        valide = False
            if par.get('sezione') not in sezioni or not valide or not (par.get('avvio') or par.get('pronta_entro')):
                errori.append(errore('proposta %d: sezione %r o date (AAAA-MM-GG) non valide' % (n, par.get('sezione'))))
                continue
            if not a.valida:
                sezioni[par['sezione']]['calendario'] = {'avvio': par.get('avvio'), 'pronta_entro': par.get('pronta_entro')}
        elif az == 'mappa_owner':
            persone = {p['id']: p for p in cfg.get('team', [])}
            valore = str(par.get('valore') or '').strip()
            if not valore or (not par.get('non_persona') and par.get('persona_id') not in persone):
                errori.append(errore('proposta %d: valore owner vuoto o persona %r non nel team' % (n, par.get('persona_id'))))
                continue
            if not a.valida:
                if par.get('non_persona'):
                    cfg['owner_non_persona'] = sorted(set(cfg.get('owner_non_persona', [])) | {valore})
                else:
                    p_ = persone[par['persona_id']]
                    p_['alias'] = sorted(set(p_.get('alias', [])) | {valore})
        elif az == 'attribuisci_sezione':
            if par.get('sezione') not in sezioni or par.get('progetto_id') not in progetti_di(par.get('sezione')):
                errori.append(errore('proposta %d: sezione %r o progetto %r inesistenti nell\'obiettivo' % (n, par.get('sezione'), par.get('progetto_id'))))
                continue
            if not a.valida:
                attribuisci(par['sezione'], par['progetto_id'])
        elif az in ('us_fuori_sezione', 'us_ricetta'):
            if not a.valida:
                o = obiettivo_della_us(us)
                o[az] = sorted(set(o.get(az, [])) | {us})
        elif az == 'rimuovi_us':
            if not a.valida:
                for o in cfg['obiettivi']:
                    for s in o.get('sezioni', []):
                        s['us'] = [u for u in s['us'] if u != us]
                    for k in ('us_ricetta', 'us_fuori_sezione'):
                        if k in o:
                            o[k] = [u for u in o[k] if u != us]
        elif az == 'sostituisci_us':
            if par.get('nuova') not in us_kanban:
                errori.append(errore('proposta %d: US sostitutiva %r non esiste' % (n, par.get('nuova'))))
                continue
            if not a.valida:
                for o in cfg['obiettivi']:
                    for s in o.get('sezioni', []):
                        s['us'] = [par['nuova'] if u == par.get('vecchia') else u for u in s['us']]
        elif az == 'mappa_stato':
            if par.get('categoria') not in categorie or not par.get('valore'):
                errori.append(errore('proposta %d: categoria %r non valida (ammesse: %s)' % (n, par.get('categoria'), sorted(categorie))))
                continue
            gia = [c for c, vs in cfg['stati'].items() if str(par['valore']).strip().lower() in {v.lower() for v in vs}]
            if gia:
                errori.append(errore('proposta %d: il valore %r e\' gia\' mappato in %s (confronto senza maiuscole/minuscole)' % (n, par['valore'], gia)))
                continue
            if not a.valida:
                cfg['stati'][par['categoria']] = sorted(set(cfg['stati'][par['categoria']]) | {par['valore']})
        elif az == 'aggiungi_epica':
            ep = par.get('epica')
            perim = next((x for x in ob['perimetro'] if x['progetto_id'] == par.get('progetto_id')), None)
            if not ep or not epica_esiste(ep) or perim is None:
                errori.append(errore('proposta %d: epica %r inesistente o progetto %r fuori dal perimetro' % (n, ep, par.get('progetto_id'))))
                continue
            if not a.valida:
                perim['selettore']['epiche'] = sorted(set(perim['selettore']['epiche']) | {ep})
        elif az == 'escludi_epica':
            if not par.get('epica') or not epica_esiste(par['epica']):
                errori.append(errore('proposta %d: epica %r inesistente' % (n, par.get('epica'))))
                continue
            if not a.valida:
                cfg['epiche_escluse'] = sorted(set(cfg.get('epiche_escluse', [])) | {par['epica']})
        elif az in ('aggiungi_tsk', 'rimuovi_tsk'):
            s_ = sezioni.get(par.get('sezione'))
            if s_ is None or 'tsk' not in s_:
                errori.append(errore('proposta %d: %r non e\' un sotto-perimetro (sezione con elenco tsk)' % (n, par.get('sezione'))))
                continue
            if az == 'aggiungi_tsk' and par.get('tsk') not in tsk_kanban:
                errori.append(errore('proposta %d: TSK %r non esiste nel kanban' % (n, par.get('tsk'))))
                continue
            if not a.valida:
                s_['tsk'] = [x for x in s_['tsk'] if x != par['tsk']] + ([par['tsk']] if az == 'aggiungi_tsk' else [])
        elif az == 'ignora':
            pass
        else:
            errori.append(errore('proposta %d: azione %r non ammessa' % (n, az)))
            continue
        fatte.append('%d. %s %s' % (n, az, json.dumps(par, ensure_ascii=False)))

    if errori:
        print('%d proposte non valide: nessuna modifica scritta.' % len(errori))
        return 1
    if a.valida:
        print('VALIDE: %d proposte' % len(fatte))
        for f in fatte:
            print('  ' + f)
        return 0

    # storico in analytics/coordinamento/storico/<operatore>/
    operatore = _operatore(a.config)
    storico = os.path.join(os.path.dirname(os.path.abspath(a.config)), 'storico', operatore)
    os.makedirs(storico, exist_ok=True)
    ora = datetime.datetime.now(datetime.timezone.utc)
    copia = os.path.join(storico, 'config-%s.json' % ora.strftime('%Y%m%dT%H%M%SZ'))
    shutil.copy2(a.config, copia)
    cfg['aggiornato'] = ora.strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(a.config, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)
    print('APPLICATE: %d proposte (copia precedente: %s)' % (len(fatte), copia))
    for f in fatte:
        print('  ' + f)
    return 0


if __name__ == '__main__':
    sys.exit(main())
