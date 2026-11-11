#!/usr/bin/env python3
"""Allineamento configurazione ↔ kanban, prima del report: trova (senza giudicare) gli elementi del kanban che la
configurazione non conosce ancora o che ha superato.

    python controlla_config.py --config config-base.json --snapshot snapshot.json --out allineamento.json [--ref HEAD]

Candidati (tipo → significato):
- us_non_mappata       US nelle epiche del perimetro che la config non cita (non in sezioni, us_ricetta, us_fuori_sezione),
                       solo per gli obiettivi che classificano le US: con sezioni o liste us_*, oppure `classifica_us: true`.
                       Un obiettivo senza sezioni misura le sue epiche senza chiedere di classificarne le US
- us_config_assente    US citata dalla config che non esiste più nel kanban
- us_config_chiusa     US di sezione chiusa senza esito (superata, annullata): la sezione punta a una US morta
- sezione_non_attribuita  sezione dell'obiettivo che nessun progetto del perimetro elenca nei `sotto_obiettivi` (o più d'uno),
                       o attribuita a un progetto che non contiene l'epica delle sue US, o citata nei sotto_obiettivi ma non definita
- rilascio_non_coerente  `sezioni[].rilascio` con TSK inesistente, data non valida, o data (gg/mm) che non compare né nel titolo
                       del TSK di rilascio né nella `window` delle US della sezione (né, per un sotto-perimetro, nella window
                       o nel titolo dei suoi TSK)
- calendario_non_coerente  `sezioni[].calendario` (avvio, pronta_entro) con data non valida, assente dalle fonti delle date,
                       o fuori ordine (avvio > pronta entro, pronta entro > rilascio). Fonti: `window` delle US della sezione;
                       per un sotto-perimetro (sezione con `tsk`) anche window e titolo dei suoi TSK e titolo dei TSK di rilascio
                       dell'obiettivo (il test dell'ondata N va dal rilascio N al rilascio N+1)
- tsk_config_assente   TSK elencato in `sezioni[].tsk` che non esiste nel kanban o non è nelle epiche del perimetro dell'obiettivo
- tsk_in_piu_sottoperimetri  TSK elencato in più sotto-perimetri dello stesso obiettivo
- tsk_fuori_sottoperimetro  TSK aperto di una US divisa in sotto-perimetri (citata solo da sezioni con `tsk` dell'obiettivo)
                       che nessun sotto-perimetro elenca: finirebbe fra il lavoro non legato a una sezione
- owner_non_mappato    valore del campo owner di TSK aperti del perimetro che non è né una persona del `team` (nome o alias)
                       né fra gli `owner_non_persona`
- stato_non_mappato    valore di status presente nel perimetro e assente dalla tabella `stati` della config
- epica_candidata      epica aperta fuori da ogni perimetro e non esclusa; se i repository dichiarano `prefissi_kanban`,
                       solo le epiche con quei prefissi (kanban senza prefissi: lista vuota = tutte)
                       (qualunque data: una scelta non scritta in config resta un candidato, tavola rotonda c7f4a2e8)
Classificare i candidati e proporre le modifiche è il compito del subagente di allineamento (references/agente-allineamento-config.md);
applicarle, dopo conferma, è il compito di applica_config.py. Esce sempre con 0 (è una misura, non un gate).
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

try:
    import yaml
except ImportError:
    yaml = None

from percorsi import risolvi_factory_root
from kanban_ids import EP_RE, cartella_e_di
from snapshot import leggi_blob
from kanban_ids import nel_perimetro, nel_selettore


def git(root, *args):
    return subprocess.run(['git', '-C', root, *args], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout


def frontmatter(testo):
    if not testo.startswith('---') or yaml is None:
        return {}
    fine = testo.find('\n---', 3)
    try:
        d = yaml.safe_load(testo[3:fine]) if fine > 0 else {}
    except Exception:  # noqa: BLE001
        return {}
    return d if isinstance(d, dict) else {}


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True)
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--ref', default='HEAD')
    a = ap.parse_args(argv)

    cfg = json.load(open(a.config, encoding='utf-8'))
    snap = json.load(open(a.snapshot, encoding='utf-8'))
    root, kanban = risolvi_factory_root(cfg, a.config), cfg.get('kanban_root', 'management/kanban')
    stati_noti = {v.lower() for vs in cfg['stati'].values() for v in vs}
    chiusi = {v.lower() for v in cfg['stati'].get('chiuso_senza_esito', [])} | {v.lower() for v in cfg['stati'].get('fatto', [])}

    us_sezione, us_note = {}, set()
    perimetro_epiche, epiche_classificate = set(), set()
    for o in cfg['obiettivi']:
        ep_o = {e for p in o.get('perimetro', []) for e in p.get('selettore', {}).get('epiche', [])}
        perimetro_epiche.update(ep_o)
        classifica = o.get('classifica_us')
        if classifica is None:
            classifica = bool(o.get('sezioni') or o.get('us_ricetta') or o.get('us_fuori_sezione'))
        if classifica:
            epiche_classificate.update(ep_o)
        for s in o.get('sezioni', []):
            for u in s.get('us', []):
                us_sezione[u] = s['id']
        us_note.update(o.get('us_ricetta', []))
        us_note.update(o.get('us_fuori_sezione', []))
    citate = set(us_sezione) | us_note
    escluse = set(cfg.get('epiche_escluse', []))
    prefissi = {p for r in cfg.get('repository', []) for p in r.get('prefissi_kanban', [])}
    soglia = str(cfg.get('aggiornato', ''))[:10]

    entita = {e['id']: e for e in snap['entita']}
    us_kanban = {i: e for i, e in entita.items() if e['tipo'] == 'US'}
    cand = []
    # una US fuori dal selettore di ogni perimetro (selettore.us) non e' del perimetro: nessuna classificazione da chiedere
    for i, e in sorted(us_kanban.items()):
        if i not in citate and e.get('epica') in epiche_classificate and any(nel_perimetro(e['epica'], i, o) for o in cfg['obiettivi']):
            cand.append({'tipo': 'us_non_mappata', 'id': i, 'titolo': e.get('titolo', ''), 'epica': e['epica'],
                         'stato': (e.get('stato') or {}).get('dichiarato'), 'fonte': e['fonte']['path'],
                         'tsk': sorted(x['id'] for x in snap['entita'] if x['tipo'] == 'TSK' and x['us'] == i)})
    for u in sorted(citate):
        if u not in us_kanban:
            cand.append({'tipo': 'us_config_assente', 'id': u, 'dove': ('sezione ' + us_sezione[u]) if u in us_sezione else 'us_ricetta/us_fuori_sezione'})
        elif u in us_sezione and (us_kanban[u].get('stato') or {}).get('normalizzato') == 'chiuso_senza_esito':
            cand.append({'tipo': 'us_config_chiusa', 'id': u, 'sezione': us_sezione[u], 'stato': us_kanban[u]['stato']['dichiarato'],
                         'fonte': us_kanban[u]['fonte']['path']})
    for o in cfg['obiettivi']:
        perim = o.get('perimetro', [])
        for s in o.get('sezioni', []):
            progetti = [p['progetto_id'] for p in perim if s['id'] in (p.get('sotto_obiettivi') or {}).get('sezioni', [])]
            epiche_us = sorted({us_kanban[u]['epica'] for u in s.get('us', []) if u in us_kanban})
            if len(progetti) != 1:
                motivo = 'in nessun sotto_obiettivi del perimetro' if not progetti else 'in più progetti: %s' % ', '.join(progetti)
            else:
                sel_prog = next(p for p in perim if p['progetto_id'] == progetti[0]).get('selettore', {})
                fuori = [ep for ep in epiche_us if ep not in sel_prog.get('epiche', [])]
                fuori_us = [u for u in s.get('us', []) if u in us_kanban and us_kanban[u]['epica'] not in fuori
                            and not nel_selettore(us_kanban[u]['epica'], u, sel_prog)]
                if not fuori and not fuori_us:
                    continue
                motivo = ('attribuita a %s, ma le sue US stanno in %s, epiche fuori dal progetto' % (progetti[0], ', '.join(fuori)) if fuori
                          else 'attribuita a %s, ma %s fuori dalle US del selettore del progetto' % (progetti[0], ', '.join(fuori_us)))
            cand.append({'tipo': 'sezione_non_attribuita', 'id': s['id'], 'obiettivo': o['id'], 'motivo': motivo,
                         'epiche_delle_us': epiche_us, 'progetti_attuali': progetti})
    def testi_tsk(s):
        return [str(entita[t].get(k) or '') for t in s.get('tsk', []) if t in entita for k in ('titolo', 'window')]

    for o in cfg['obiettivi']:
        for s in o.get('sezioni', []):
            r = s.get('rilascio')
            if not r:
                continue
            problemi = []
            t = entita.get(r.get('tsk')) if r.get('tsk') else None
            if r.get('tsk') and (t is None or t['tipo'] != 'TSK'):
                problemi.append('TSK di rilascio %s assente dal kanban' % r['tsk'])
            try:
                d = datetime.date.fromisoformat(str(r.get('data')))
            except ValueError:
                d = None
                problemi.append('data %r non nel formato AAAA-MM-GG' % r.get('data'))
            if d:
                testi = [str((t or {}).get('titolo') or '')] + [str(us_kanban[u].get('window') or '') for u in s.get('us', []) if u in us_kanban] \
                    + testi_tsk(s)
                if not any(d.strftime('%d/%m') in x for x in testi):
                    problemi.append('la data %s non compare né nel titolo del TSK di rilascio né nella window delle US' % d.strftime('%d/%m'))
            if problemi:
                cand.append({'tipo': 'rilascio_non_coerente', 'id': s['id'], 'obiettivo': o['id'], 'rilascio': r, 'motivo': '; '.join(problemi),
                             'titolo_tsk': (t or {}).get('titolo'), 'window_us': {u: us_kanban[u].get('window') for u in s.get('us', []) if u in us_kanban}})
    for o in cfg['obiettivi']:
        rilasci_ob = [str((entita.get((z.get('rilascio') or {}).get('tsk')) or {}).get('titolo') or '') for z in o.get('sezioni', [])]
        for s in o.get('sezioni', []):
            cal = s.get('calendario') or {}
            if not cal:
                continue
            windows = [str(us_kanban[u].get('window') or '') for u in s.get('us', []) if u in us_kanban]
            if 'tsk' in s:
                windows += testi_tsk(s) + rilasci_ob
            problemi, date = [], {}
            for k in ('avvio', 'pronta_entro'):
                if not cal.get(k):
                    continue
                try:
                    date[k] = datetime.date.fromisoformat(str(cal[k]))
                except ValueError:
                    problemi.append('%s %r non nel formato AAAA-MM-GG' % (k, cal[k]))
                    continue
                if not any(date[k].strftime('%d/%m') in w for w in windows):
                    problemi.append('%s %s non compare nella window delle US%s' % (
                        k, date[k].strftime('%d/%m'), ' né nei TSK del sotto-perimetro o nei rilasci dell\'obiettivo' if 'tsk' in s else ''))
            ril = (s.get('rilascio') or {}).get('data')
            if 'avvio' in date and 'pronta_entro' in date and date['avvio'] > date['pronta_entro']:
                problemi.append('avvio dopo «pronta entro»')
            if 'pronta_entro' in date and ril and str(date['pronta_entro']) > str(ril):
                problemi.append('«pronta entro» dopo il rilascio %s' % ril)
            if problemi:
                cand.append({'tipo': 'calendario_non_coerente', 'id': s['id'], 'obiettivo': o['id'], 'calendario': cal, 'motivo': '; '.join(problemi),
                             'window_us': {u: us_kanban[u].get('window') for u in s.get('us', []) if u in us_kanban}})
    for s_id in sorted({x for o in cfg['obiettivi'] for p in o.get('perimetro', [])
                        for x in (p.get('sotto_obiettivi') or {}).get('sezioni', [])
                        if x not in {s['id'] for s in o.get('sezioni', [])}}):
        cand.append({'tipo': 'sezione_non_attribuita', 'id': s_id, 'motivo': 'citata nei sotto_obiettivi ma non definita fra le sezioni dell\'obiettivo',
                     'epiche_delle_us': [], 'progetti_attuali': []})
    for o in cfg['obiettivi']:
        con_tsk = [s for s in o.get('sezioni', []) if 'tsk' in s]
        dove = {}
        for s in con_tsk:
            for t in s['tsk']:
                dove.setdefault(t, []).append(s['id'])
                if t not in entita or entita[t]['tipo'] != 'TSK' or not nel_perimetro(entita[t].get('epica'), entita[t].get('us'), o):
                    cand.append({'tipo': 'tsk_config_assente', 'id': t, 'obiettivo': o['id'], 'sezione': s['id'],
                                 'motivo': 'assente dal kanban' if t not in entita else 'fuori dalle epiche del perimetro'})
        for t, zz in sorted(dove.items()):
            if len(zz) > 1:
                cand.append({'tipo': 'tsk_in_piu_sottoperimetri', 'id': t, 'obiettivo': o['id'], 'sezioni': zz})
        us_divise = {u for s in con_tsk for u in s.get('us', [])} - {u for s in o.get('sezioni', []) if 'tsk' not in s for u in s.get('us', [])}
        for e in snap['entita']:
            if e['tipo'] == 'TSK' and e.get('us') in us_divise and e['id'] not in dove \
                    and (e.get('stato') or {}).get('normalizzato') not in ('fatto', 'chiuso_senza_esito', None):
                cand.append({'tipo': 'tsk_fuori_sottoperimetro', 'id': e['id'], 'obiettivo': o['id'], 'us': e['us'],
                             'titolo': e.get('titolo', ''), 'stato': (e.get('stato') or {}).get('dichiarato')})
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from aggrega import chi_e  # stessa regola della misura: nessuna seconda interpretazione del campo owner
    owner_ignoti = {}
    for e in snap['entita']:
        if e['tipo'] == 'TSK' and any(nel_perimetro(e.get('epica'), e.get('us'), o) for o in cfg['obiettivi']) and (e.get('stato') or {}).get('normalizzato') not in ('fatto', 'chiuso_senza_esito', None):
            if chi_e(e.get('owner'), cfg)[0] == 'sconosciuto':
                owner_ignoti.setdefault(str(e.get('owner')).strip(), []).append(e['id'])
    for v, ids in sorted(owner_ignoti.items()):
        cand.append({'tipo': 'owner_non_mappato', 'valore': v, 'entita': sorted(ids)})
    valori = {}
    for e in snap['entita']:
        v = str((e.get('stato') or {}).get('dichiarato') or '').strip()
        if v and v.lower() not in stati_noti:
            valori.setdefault(v, []).append(e['id'])
    for v, ids in sorted(valori.items()):
        cand.append({'tipo': 'stato_non_mappato', 'valore': v, 'entita': sorted(ids)})

    epiche_file = []
    for path in git(root, 'ls-tree', '-r', '--name-only', a.ref, '--', kanban).splitlines():
        parti = path.split('/')
        nome = parti[-1][:-3] if parti[-1].endswith('.md') else ''
        m = EP_RE.match(nome)
        if not m or len(parti) != len(kanban.split('/')) + 2 or not cartella_e_di(parti[-2], nome) \
                or (prefissi and m.group(1) not in prefissi):
            continue
        if nome in perimetro_epiche or nome in escluse:
            continue
        epiche_file.append((path, nome))
    testi = leggi_blob(root, a.ref, [p for p, _ in epiche_file])
    for path, nome in epiche_file:
        d = frontmatter(testi[path])
        stato = str(d.get('status') or '').lower()
        date = [str(d.get(k))[:10] for k in ('created', 'updated') if d.get(k)]
        if stato in chiusi:
            continue
        cand.append({'tipo': 'epica_candidata', 'id': nome, 'titolo': str(d.get('title') or ''), 'stato': d.get('status'),
                     'date': sorted(date), 'fonte': path})

    out = {'versione_schema': '1.0', 'ref': a.ref, 'config_aggiornato': cfg.get('aggiornato'), 'candidati': cand,
           'conteggio': len(cand), 'per_tipo': {t: sum(1 for c in cand if c['tipo'] == t) for t in sorted({c['tipo'] for c in cand})}}
    with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print('allineamento config: %d candidati %s -> %s' % (len(cand), out['per_tipo'] or '', a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
