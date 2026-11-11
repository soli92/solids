#!/usr/bin/env python3
"""Verifica L0 della misura, prima di impaginarla: ricalcola i numeri dallo snapshot con un'implementazione
indipendente da aggrega.py e li confronta. Esce con 1 al primo scostamento.

    python verifica_l0.py --snapshot snapshot.json --misura misura.json [--config config-base.json]

Controlli, per ogni obiettivo:
- per ogni epica, sezione e gruppo: conteggi per stato ricalcolati = conteggi dichiarati; pct coerente;
- per ogni blocco: gli elenchi di ID dietro le voci da verificare coincidono con quelli ricalcolati;
- ogni TSK del perimetro è contato una e una sola volta fra «in sezioni» e «non legati»;
- riepilogo delle sezioni (per stato, avviate, senza TSK) e giorni lavorativi ricalcolati;
- avanzamento per sottoperimetro: per ogni sottoperimetro dichiarato dalle sezioni, conteggi sull'unione dei TSK delle sue sezioni.
In generale: la misura dichiara lo sha256 dello snapshot; ogni ID citato esiste nello snapshot.
Con --config: tabella stati disgiunta, status ri-normalizzati in modo indipendente, e obiettivi, perimetri, sezioni
e dipendenze fra obiettivi identici a quelli della config; progetto di ogni sezione dai `sotto_obiettivi` della config;
piano delle sezioni identico ai campi `vista_pm.piano` del frontmatter delle US; sottoperimetro delle sezioni e ambiente
di rilascio dell'obiettivo identici alla config.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from collections import Counter

CAT = ['fatto', 'in_corso', 'da_fare', 'bloccato', 'sospeso', 'sconosciuto', 'chiuso_senza_esito']
CAT_ELENCO = ['chiuso_senza_esito', 'sospeso', 'bloccato', 'sconosciuto']


def atteso(tsk_ids, cat_di):
    c = Counter(cat_di[i] for i in tsk_ids)
    r = {k: c.get(k, 0) for k in CAT}
    r['totale'] = len(tsk_ids)
    r['base_calcolo'] = r['totale'] - r['chiuso_senza_esito']
    r['pct'] = round(100 * r['fatto'] / r['base_calcolo']) if r['base_calcolo'] else None
    return r


def elenchi_attesi(tsk_ids, cat_di):
    return {cat: sorted(i for i in tsk_ids if cat_di[i] == cat) for cat in CAT_ELENCO}


def sottoperimetri_attesi(sezioni, membri_di, cat_di):
    """Conteggi per sottoperimetro dall'unione dei membri delle sezioni: implementazione indipendente da aggrega.py."""
    etichetta = {s['id']: s.get('sottoperimetro') or 'non_indicato' for s in sezioni}
    if set(etichetta.values()) <= {'non_indicato'}:
        return None
    unione = {}
    for sid, k in etichetta.items():
        unione[k] = unione.get(k, frozenset()) | frozenset(membri_di[sid])
    return {k: atteso(sorted(ids), cat_di) for k, ids in unione.items()}


def feriali(da, a):
    """Giorni lun-ven in (da, a]: implementazione diversa da quella di aggrega.py (settimane intere + resto)."""
    n = (a - da).days
    if n <= 0:
        return 0
    settimane, resto = divmod(n, 7)
    return settimane * 5 + sum(1 for k in range(1, resto + 1) if (da.weekday() + k) % 7 < 5)


RANK = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
# Forma dell'ID scritta qui, non importata: prefisso di namespace opzionale (XX-TSK-541 o TSK-635).
# Implementazione separata da kanban_ids.py per costruzione (test statico di indipendenza).
TSK_ID = re.compile(r'^(?:[A-Z]{2,4}-)?TSK-[0-9]+$')


def nel_p(e, p):
    """TSK dentro una voce `perimetro` della misura: epica fra le `epiche` e, se la voce elenca `us`, US fra quelle.
    Riscritta qui, non importata: L0 non usa il codice della misura."""
    return e['epica'] in p['epiche'] and (p.get('us') is None or e.get('us') in p['us'])


def aperta(c):
    return c not in ('fatto', 'chiuso_senza_esito')


def gruppo_di(owner, cfg):
    """(gruppo, persona_id, nota) con espressioni regolari: implementazione indipendente da aggrega.gruppo_owner."""
    v = str(owner if owner is not None else '').strip()
    if not v or v.lower() in {x.strip().lower() for x in cfg.get('owner_non_persona', [])}:
        return 'da_designare', None, None
    if v.lower() in {x.strip().lower() for x in cfg.get('owner_agente', [])}:
        return 'agente', None, None
    for p in cfg.get('team', []):
        for al in [p['nome']] + p.get('alias', []):
            m = re.match(r'^%s(?:$|(?=\W|_)(.*))' % re.escape(al.lower()), v.lower(), re.S)
            if m:
                resto = v[len(v) - len(m.group(1)):] if m.group(1) is not None else ''
                return 'persona', p['id'], resto.strip(' ()[],;:-') or None
    return 'sconosciuto', None, None


def dm(iso):
    return datetime.date.fromisoformat(iso).strftime('%d/%m')


def gg_lav_da(da_str, oggi):
    """Giorni lavorativi (lun-ven) in [da, oggi): implementazione indipendente da aggrega.py."""
    try:
        da = datetime.date.fromisoformat(str(da_str)[:10])
    except (ValueError, TypeError):
        return None
    n = (oggi - da).days
    if n <= 0:
        return 0
    return sum(1 for k in range(n) if (da + datetime.timedelta(days=k)).weekday() < 5)


def _mediana_intera(lista):
    """Mediana intera (arrotondamento verso zero per lista pari)."""
    vv = sorted(v for v in lista if v is not None)
    if not vv:
        return None
    n = len(vv)
    return vv[n // 2] if n % 2 else (vv[n // 2 - 1] + vv[n // 2]) // 2


# Avvisi di permanenza senza owner: dipendono dallo store da_assegnare, li ricalcola il blocco
# dello store in main() (con o senza store), non verifica_avvisi.
_CODICI_SLA = frozenset({'staleness', 'p0-staleness'})


def scadenza(s):
    return (s['calendario'] or {}).get('pronta_entro') or (s.get('rilascio') or {}).get('data')


def verifica_tsk_sezioni(o, ob, cfg, tsk, cat_di, sez_di):
    errori, nomi = [], {p['id']: p['nome'] for p in cfg.get('team', [])}
    for s in ob['sezioni']:
        atteso = []
        for i in sorted(i for i in tsk if s['id'] in sez_di[i]):
            e = tsk[i]
            g, pid, nota = gruppo_di(e.get('owner'), cfg)
            atteso.append({'tsk': i, 'titolo': e['titolo'], 'categoria': cat_di[i], 'stato': e['stato']['dichiarato'], 'priorita': e.get('priority'),
                           'gruppo': g, 'persona': pid, 'persona_nome': nomi.get(pid), 'nota_owner': nota, 'owner': e.get('owner'),
                           'non_assegnato': aperta(cat_di[i]) and g in ('da_designare', 'sconosciuto'),
                           'attende': [d for d in e.get('depends_on', []) if TSK_ID.match(d) and cat_di.get(d) != 'fatto'] if aperta(cat_di[i]) else []})
        atteso.sort(key=lambda v: (RANK.get(v['priorita'], 9), v['tsk']))
        if s['tsk'] != atteso:
            errori.append('%s · sezione %s: elenco dei TSK (stato, owner, prerequisiti) diverso da quello ricalcolato' % (o, s['id']))
    for gr in ob['non_legati_a_sezione']:
        us = None if gr['us'] == '(senza US)' else gr['us']
        na = sorted(i for i, e in tsk.items() if e['epica'] == gr['epica'] and e['us'] == us and not sez_di[i]
                    and aperta(cat_di[i]) and gruppo_di(e.get('owner'), cfg)[0] in ('da_designare', 'sconosciuto'))
        if gr['non_assegnati'] != na:
            errori.append('%s · gruppo %s: TSK non assegnati diversi da quelli ricalcolati' % (o, gr['us']))
    return errori


def ricalcola_aperti(ob, cfg, tsk, cat_di, sez_di, nel_perimetro):
    """Elenco dei TSK aperti del perimetro ricalcolato dallo snapshot (fonte per persone, piano operativo e avvisi)."""
    nomi = {p['id']: p['nome'] for p in cfg.get('team', [])}
    scad = {s['id']: scadenza(s) for s in ob['sezioni']}
    ids = sorted(i for i in nel_perimetro if aperta(cat_di[i]))
    out = []
    for i in ids:
        e = tsk[i]
        g, pid, nota = gruppo_di(e.get('owner'), cfg)
        ds = sorted(scad[z] for z in sez_di.get(i, []) if scad.get(z))
        att = [d for d in e.get('depends_on', []) if TSK_ID.match(d) and cat_di.get(d) != 'fatto']
        out.append({'tsk': i, 'titolo': e['titolo'], 'stato': e['stato']['dichiarato'], 'categoria': cat_di[i], 'priorita': e.get('priority'),
                    'gruppo': g, 'persona': pid, 'persona_nome': nomi.get(pid), 'nota_owner': nota, 'owner': e.get('owner'),
                    'non_assegnato': g in ('da_designare', 'sconosciuto'), 'sezioni': sez_di.get(i, []), 'us': e['us'], 'epica': e['epica'],
                    'scadenza_sezione': ds[0] if ds else None, 'attende': att,
                    'attesi_da': sorted(j for j in ids if i in tsk[j].get('depends_on', [])),
                    'pronto': cat_di[i] == 'da_fare' and not att})
    out.sort(key=lambda v: (RANK.get(v['priorita'], 9), v['scadenza_sezione'] or '9999-12-31', v['tsk']))
    return out


def verifica_bloccanti(o, ob, aperti, oggi):
    """Ricalcolo indipendente dei bloccanti prioritari dall'elenco ricalcolato dei TSK aperti."""
    per = {v['tsk']: v for v in aperti}
    sez = {s['id']: s for s in ob['sezioni']}
    att = []
    for v in aperti:
        chi = sorted(j for j in per if v['tsk'] in per[j]['attende'] or v['tsk'] in tsk_dep(per[j]))
        chi = [j for j in chi if j in v['attesi_da']]
        if not chi:
            continue
        sz = sorted(set(z for j in chi for z in per[j]['sezioni']))
        avvii, scad, serve = [], [], []
        for z in sz:
            if z not in sez:
                continue
            c = sez[z]['calendario']
            if c.get('avvio'):
                avvii.append(c['avvio'])
            if scadenza(sez[z]):
                scad.append(scadenza(sez[z]))
            if c.get('avvio') or scadenza(sez[z]):
                serve.append(c.get('avvio') or scadenza(sez[z]))
        pr = min(serve) if serve else None
        att.append({'tsk': v['tsk'], 'titolo': v['titolo'], 'priorita': v['priorita'], 'stato': v['stato'], 'categoria': v['categoria'],
                    'gruppo': v['gruppo'], 'persona_nome': v['persona_nome'], 'owner': v['owner'], 'non_assegnato': v['non_assegnato'],
                    'sezioni': v['sezioni'], 'scadenza_sezione': v['scadenza_sezione'], 'attende': v['attende'], 'attesi_da': chi,
                    'sezioni_attese': sz, 'primo_avvio_atteso': min(avvii) if avvii else None, 'prima_scadenza_attesa': min(scad) if scad else None,
                    'serve_entro': pr, 'serve_entro_da': None if pr is None else ['scadenza', 'avvio'][pr in avvii],
                    'giorni_a_serve_entro': feriali(oggi, datetime.date.fromisoformat(pr)) if pr else None,
                    'gia_necessario': pr is not None and datetime.date.fromisoformat(pr) <= oggi,
                    'serve_prima_della_sua_sezione': pr is not None and (v['scadenza_sezione'] is None or pr < v['scadenza_sezione'])})
    att.sort(key=lambda b: (b['serve_entro'] or '9999-12-31', -len(b['sezioni_attese']), RANK.get(b['priorita'], 9), -len(b['attesi_da']), b['tsk']))
    return [] if ob.get('bloccanti') == att else ['%s · bloccanti prioritari diversi da quelli ricalcolati' % o]


def tsk_dep(v):
    return v['attende']


def verifica_persone(o, ob, cfg, aperti):
    k = lambda v: (RANK.get(v['priorita'], 9), v['scadenza_sezione'] or '9999-12-31', v['tsk'])
    campi = ('tsk', 'titolo', 'priorita', 'stato', 'epica', 'us', 'sezioni', 'scadenza_sezione', 'owner')

    def voce(v, persona):
        x = {c: v[c] for c in campi}
        x['nota_owner'] = v['nota_owner'] if persona else None
        x['attesi_da'] = v['attesi_da']
        return x

    def gruppi(vv):
        ps, fu = {}, {}
        for v in vv:
            for z in v['sezioni']:
                ps[z] = sorted(ps.get(z, []) + [v['tsk']])
            if not v['sezioni']:
                fu[v['us'] or v['epica']] = sorted(fu.get(v['us'] or v['epica'], []) + [v['tsk']])
        return {'per_sezione': ps, 'fuori_sezioni': fu}
    senza = []
    for v in aperti:
        if v['gruppo'] in ('da_designare', 'sconosciuto'):
            x = voce(v, False)
            x['owner_non_riconosciuto'] = v['gruppo'] == 'sconosciuto'
            senza.append(x)
    agenti = [voce(v, False) for v in aperti if v['gruppo'] == 'agente']
    atteso = {'senza_owner': sorted(senza, key=k), 'senza_owner_raggruppati': gruppi(senza),
              'agenti': sorted(agenti, key=k), 'agenti_raggruppati': gruppi(agenti), 'per_persona': []}
    for p in cfg.get('team', []):
        vv = sorted((voce(v, True) for v in aperti if v['persona'] == p['id']), key=k)
        pr = {}
        for v in vv:
            pr[v['priorita'] or '-'] = pr.get(v['priorita'] or '-', 0) + 1
        ds = [v['scadenza_sezione'] for v in vv if v['scadenza_sezione']]
        atteso['per_persona'].append({'id': p['id'], 'nome': p['nome'], 'impegno_pct': p.get('impegno_pct'), 'nota': p.get('nota'), 'tsk': vv,
                                      'per_priorita': pr, 'prossima_scadenza': min(ds) if ds else None, **gruppi(vv)})
    persone_confronto = {k: v for k, v in ob['persone'].items() if k != 'senza_owner_bucket'}
    if persone_confronto != atteso:
        return ['%s · assegnazioni per persona / da designare / agenti diverse da quelle ricalcolate dal campo owner' % o]
    return []


def verifica_avvisi(o, ob, cfg, aperti, obiettivi_cfg):
    """Ricalcolo indipendente dei punti di attenzione: stesse regole dichiarate, scritte come filtri su insiemi."""
    vp = cfg.get('vista_pm', {})
    soglia_c, soglia_g = vp.get('soglia_collo_sezioni', 3), vp.get('soglia_giorni_scadenza', 3)
    nomi = {s['id']: s['nome'] for s in ob['sezioni']}
    per_id = {v['tsk']: v for v in aperti}
    sc = {s['id']: scadenza(s) for s in ob['sezioni']}
    att = []
    for v in aperti:
        sez_att = sorted(set().union(*[set(per_id[w]['sezioni']) for w in v['attesi_da'] if w in per_id]) if v['attesi_da'] else set())
        if len(sez_att) < soglia_c:
            continue
        prime = sorted(sc[z] for z in sez_att if sc.get(z))
        tardi = len(prime) > 0 and (v['scadenza_sezione'] is None or prime[0] < v['scadenza_sezione'])
        t = '%s (%s) è atteso da %d TSK di %d sezioni: %s' % (v['tsk'], v['titolo'], len(v['attesi_da']), len(sez_att),
                                                         ', '.join(nomi.get(z, z) for z in sez_att))
        if tardi:
            t += '; la prima che lo attende è pronta entro il %s, la sua %s' % (dm(prime[0]), 'entro il %s' % dm(v['scadenza_sezione']) if v['scadenza_sezione'] else 'non ha date')
        att.append({'codice': 'collo-di-bottiglia', 'livello': ['medio', 'alto'][tardi], 'testo': t, 'ids': [v['tsk']] + v['attesi_da'],
                    'sezioni': sorted(set(v['sezioni']).union(sez_att)),
                    'regola': 'TSK aperto atteso da TSK di almeno %d sezioni' % soglia_c})
    p0 = [v for v in aperti if v['priorita'] == 'P0' and v['non_assegnato']]
    if p0:
        att.append({'codice': 'p0-da-designare', 'livello': 'alto', 'ids': [v['tsk'] for v in p0],
                    'sezioni': sorted(set().union(*[v['sezioni'] for v in p0])),
                    'testo': '%d TSK P0 aperti senza owner: %s' % (len(p0), '; '.join('%s (%s)' % (v['tsk'], v['titolo']) for v in p0)),
                    'regola': 'priorità P0, owner vuoto o da designare'})
    for s in ob['sezioni']:
        mie = [v for v in aperti if s['id'] in v['sezioni']]
        cal = s['calendario']
        pe = cal['pronta_entro']
        n_mie = len(mie)
        n_senza = sum(1 for v in mie if v['non_assegnato'])
        if mie and n_senza == n_mie:
            att.append({'codice': 'sezione-da-designare', 'livello': 'medio', 'ids': [v['tsk'] for v in mie], 'sezioni': [s['id']],
                        'testo': '%s: tutti i %d TSK aperti sono senza owner%s' % (s['nome'], len(mie), ' (pronta entro il %s)' % dm(pe) if pe else ''),
                        'regola': 'sezione con TSK aperti tutti da designare'})
        elif mie and 2 * n_senza > n_mie:
            att.append({'codice': 'sezione-da-designare-parziale', 'livello': 'medio',
                        'ids': [v['tsk'] for v in mie if v['non_assegnato']], 'sezioni': [s['id']],
                        'n_tsk': n_senza, 'n_p0_p1': len([v for v in mie if v['non_assegnato'] and v.get('priorita') in ('P0', 'P1')]),
                        'testo': '%s: %d/%d TSK aperti senza owner%s' % (s['nome'], n_senza, n_mie, ' (pronta entro il %s)' % dm(pe) if pe else ''),
                        'regola': 'sezione con più della metà dei TSK aperti senza owner'})
        if mie and pe and not cal['pronta_scaduta_non_completata'] and cal['giorni_a_pronta'] <= soglia_g and s['avanzamento'] == 'non_avviata':
            att.append({'codice': 'scadenza-vicina-non-avviata', 'livello': 'alto', 'ids': [v['tsk'] for v in mie], 'sezioni': [s['id']],
                        'testo': '%s: %d TSK da completare entro il %s (%d %s), nessuno avviato' % (
                            s['nome'], len(mie), dm(pe), cal['giorni_a_pronta'], ['giorni lavorativi', 'giorno lavorativo'][cal['giorni_a_pronta'] == 1]),
                        'regola': '«pronta entro» a %d giorni lavorativi o meno, nessun TSK fatto o in corso' % soglia_g})
        if cal['pronta_scaduta_non_completata']:
            f = 'data «pronta entro» passata, sezione non completata'
            att.append({'codice': 'scadenza-passata', 'livello': 'alto', 'ids': [v['tsk'] for v in mie], 'sezioni': [s['id']],
                        'testo': '%s: %s' % (s['nome'], f), 'regola': f})
        if cal['avvio_passato_non_avviata']:
            f = 'avvio previsto passato, nessun TSK fatto o in corso'
            att.append({'codice': 'avvio-passato', 'livello': 'alto', 'ids': [v['tsk'] for v in mie], 'sezioni': [s['id']],
                        'testo': '%s: %s' % (s['nome'], f), 'regola': f})
        fa = [x for x in obiettivi_cfg if x['id'] == s.get('fino_a')]
        if fa and fa[0]['data_target'] > ob['data_target']:
            att.append({'codice': 'oltre-il-target', 'livello': 'info', 'ids': [u['id'] for u in s['us']], 'sezioni': [s['id']],
                        'testo': '%s attende «%s» (%s), oltre la data obiettivo %s: fuori da questo obiettivo per costruzione' % (
                            s['nome'], fa[0]['nome'], dm(fa[0]['data_target']), dm(ob['data_target'])),
                        'regola': 'sezione congelata fino a un obiettivo con data successiva'})
    for p in ob['perimetro']:
        mie = [v for v in aperti if nel_p(v, p)]
        if mie and not [s for s in ob['sezioni'] if s['progetto_id'] == p['progetto_id'] and scadenza(s)]:
            att.append({'codice': 'progetto-senza-date', 'livello': 'medio', 'ids': [v['tsk'] for v in mie], 'sezioni': [], 'progetto': p['progetto_id'],
                        'testo': '%s: %d TSK aperti, nessuna data nel piano (nessun sotto-obiettivo con date)' % (p.get('nome') or p['progetto_id'], len(mie)),
                        'regola': 'progetto del perimetro con TSK aperti e senza sotto-obiettivi datati'})
    att.sort(key=lambda x: ({'alto': 0, 'medio': 1, 'info': 2}[x['livello']], x['codice'], x['testo']))
    avvisi_dichiarati = [x for x in ob['avvisi'] if x['codice'] not in _CODICI_SLA]
    return [] if avvisi_dichiarati == att else ['%s · punti di attenzione diversi da quelli ricalcolati con le regole dichiarate' % o]


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--misura', required=True)
    ap.add_argument('--config', help='config della skill: controlla la tabella stati, ri-normalizza gli status e confronta gli obiettivi')
    ap.add_argument('--store', help='percorso di da_assegnare.yaml per la verifica A7 (opzionale)')
    ap.add_argument('--stale-alert-days', type=int, default=7, dest='stale_alert_days')
    ap.add_argument('--escalation-days', type=int, default=14, dest='escalation_days')
    a = ap.parse_args(argv)

    sb = open(a.snapshot, 'rb').read()
    snap = json.loads(sb)
    mis = json.load(open(a.misura, encoding='utf-8'))
    errori = []

    if mis['provenienza']['snapshot_sha256'] != hashlib.sha256(sb).hexdigest():
        errori.append('la misura non viene da questo snapshot (sha256 diverso)')

    tsk = {e['id']: e for e in snap['entita'] if e['tipo'] == 'TSK' and 'stato' in e}
    cfg, cfg_ob = None, {}
    if a.config:
        cfg = json.load(open(a.config, encoding='utf-8'))
        visti = {}
        for cat, valori in cfg['stati'].items():
            for v in valori:
                visti.setdefault(v.strip().lower(), set()).add(cat)
        doppi = {v: sorted(c) for v, c in visti.items() if len(c) > 1}
        if doppi:
            errori.append('tabella stati della config non disgiunta: %s' % doppi)
        # ri-normalizzazione indipendente dal codice di snapshot.py, a partire dallo status dichiarato nel file
        for i, e in tsk.items():
            cats = sorted(visti.get(str(e['stato']['dichiarato'] or '').strip().lower(), {'sconosciuto'}))
            atteso_cat = cats[0] if len(cats) == 1 else 'ambiguo'
            if atteso_cat != e['stato']['normalizzato']:
                errori.append('%s: status %r normalizzato in %s, atteso %s' % (i, e['stato']['dichiarato'], e['stato']['normalizzato'], atteso_cat))
        cfg_ob = {o['id']: o for o in cfg['obiettivi']}
        if sorted(cfg_ob) != sorted(o['id'] for o in mis['obiettivi']):
            errori.append('obiettivi della misura diversi da quelli della config')
        for ob in mis['obiettivi']:
            c = cfg_ob.get(ob['id'])
            if not c:
                continue
            ep_cfg = [ep for p in c.get('perimetro', []) for ep in p.get('selettore', {}).get('epiche', [])]
            if [e['id'] for e in ob['epiche']] != ep_cfg:
                errori.append('obiettivo %s: epiche del perimetro diverse dalla config' % ob['id'])
            if [(p['progetto_id'], p.get('selettore', {}).get('us')) for p in c.get('perimetro', [])] != \
                    [(p['progetto_id'], p.get('us')) for p in ob['perimetro']]:
                errori.append('obiettivo %s: US del selettore diverse dalla config' % ob['id'])
            if [(s['id'], s.get('stato'), s['us']) for s in c.get('sezioni', [])] != \
                    [(s['id'], s['stato_config'], [u['id'] for u in s['us']]) for s in ob['sezioni']]:
                errori.append('obiettivo %s: sezioni diverse dalla config' % ob['id'])
            dip = sorted((o['id'], s['id']) for o in cfg['obiettivi'] for s in o.get('sezioni', [])
                         if (s.get('fino_a') or {}).get('obiettivo') == ob['id'])
            if dip != sorted((d['obiettivo'], d['sezione']) for d in ob['dipendenti']):
                errori.append('obiettivo %s: sezioni dipendenti diverse dalla config' % ob['id'])
            if c['data_target'] != ob['data_target']:
                errori.append('obiettivo %s: data target diversa dalla config' % ob['id'])
            if [x.get('sottoperimetro') for x in c.get('sezioni', [])] != [x.get('sottoperimetro', '<assente>') for x in ob['sezioni']]:
                errori.append('obiettivo %s: sottoperimetro delle sezioni diverso dalla config' % ob['id'])
            if ob.get('ambiente_rilascio') != (c.get('ambiente_rilascio') or 'test'):
                errori.append('obiettivo %s: ambiente di rilascio diverso dalla config (default test)' % ob['id'])
    cat_di = {i: e['stato']['normalizzato'] for i, e in tsk.items()}
    us_di = {e['id']: e for e in snap['entita'] if e['tipo'] == 'US'}
    ids = {e['id'] for e in snap['entita']}
    oggi = datetime.date.fromisoformat(mis['oggi'])

    def confronta(nome, blocco, membri):
        exp = atteso(membri, cat_di)
        if blocco['conteggi'] != exp:
            errori.append('%s: dichiarato %s, ricalcolato %s' % (nome, blocco['conteggi'], exp))
        el = {k: sorted(x['id'] for x in v) for k, v in blocco.get('elenchi', {}).items()}
        if el != elenchi_attesi(membri, cat_di):
            errori.append('%s: elenchi degli ID diversi da quelli ricalcolati' % nome)

    riassunto = []
    for ob in mis['obiettivi']:
        o = ob['id']
        sez_di = {i: sorted({s['sezione'] for s in e.get('sezioni', []) if s['obiettivo'] == o}) for i, e in tsk.items()}
        for ep in ob['epiche']:
            pp = [p for p in ob['perimetro'] if p['progetto_id'] == ep['progetto_id'] and ep['id'] in p['epiche']]
            confronta('%s · epica %s' % (o, ep['id']), ep, [i for i, e in tsk.items() if e['epica'] == ep['id'] and any(nel_p(e, p) for p in pp)])
        for s in ob['sezioni']:
            membri = [i for i in tsk if s['id'] in sez_di[i]]
            confronta('%s · sezione %s' % (o, s['id']), s, membri)
            if cfg is not None and o in cfg_ob:
                pr = [p['progetto_id'] for p in cfg_ob[o].get('perimetro', []) if s['id'] in (p.get('sotto_obiettivi') or {}).get('sezioni', [])]
                if s['progetto_id'] != (pr[0] if len(pr) == 1 else None):
                    errori.append('%s · sezione %s: progetto %r diverso dai sotto_obiettivi della config %s' % (o, s['id'], s['progetto_id'], pr))
            r = s.get('rilascio')
            if cfg is not None and o in cfg_ob:
                rc = next((x.get('rilascio') for x in cfg_ob[o].get('sezioni', []) if x['id'] == s['id']), None) or None
                if (rc is None) != (r is None) or (rc and (rc.get('data'), rc.get('tsk')) != (r['data'], r['tsk'])):
                    errori.append('%s · sezione %s: rilascio diverso dalla config' % (o, s['id']))
            if r:
                t = tsk.get(r['tsk']) if r['tsk'] else None
                d = datetime.date.fromisoformat(r['data']) if r['data'] else None
                atteso_r = {'data': r['data'], 'giorni_lavorativi_rimasti': feriali(oggi, d) if d else None, 'data_passata': bool(d) and d < oggi,
                            'tsk': r['tsk'], 'tsk_trovato': t is not None, 'tsk_titolo': t['titolo'] if t else None,
                            'tsk_stato': t['stato']['dichiarato'] if t else None, 'tsk_categoria': cat_di[r['tsk']] if t else None,
                            'fatto': bool(t) and cat_di[r['tsk']] == 'fatto'}
                if r != atteso_r:
                    errori.append('%s · sezione %s: rilascio dichiarato %s, ricalcolato %s' % (o, s['id'], r, atteso_r))
            aperti = sorted(i for i in membri if cat_di[i] not in ('fatto', 'chiuso_senza_esito'))
            sub, att = [], []
            for i in aperti:
                pre = [d for d in tsk[i].get('depends_on', []) if TSK_ID.match(d) and cat_di.get(d) != 'fatto']
                if pre:
                    att.append({'tsk': i, 'titolo': tsk[i]['titolo'], 'prerequisiti': [
                        {'tsk': d, 'titolo': tsk[d]['titolo'] if d in tsk else None, 'stato': tsk[d]['stato']['dichiarato'] if d in tsk else None,
                         'sezioni': sez_di.get(d, []), 'stessa_sezione': s['id'] in sez_di.get(d, [])} for d in pre]})
                else:
                    sub.append(i)
            if s['partenza'] != {'subito': sub, 'in_attesa': att}:
                errori.append('%s · sezione %s: partenza diversa da quella ricalcolata dalle dipendenze' % (o, s['id']))
            cal = s['calendario']
            if cfg is not None and o in cfg_ob:
                cc = next((x.get('calendario') or {} for x in cfg_ob[o].get('sezioni', []) if x['id'] == s['id']), {})
                if (cc.get('avvio'), cc.get('pronta_entro')) != (cal['avvio'], cal['pronta_entro']):
                    errori.append('%s · sezione %s: calendario diverso dalla config' % (o, s['id']))
            create = [str(us_di[u['id']].get('creata'))[:10] for u in s['us'] if u['id'] in us_di and us_di[u['id']].get('creata')]
            avviata_r = any(cat_di[i] in ('fatto', 'in_corso') for i in membri)
            base_r = [cat_di[i] for i in membri if cat_di[i] != 'chiuso_senza_esito']
            compl_r = bool(base_r) and all(c == 'fatto' for c in base_r)
            av_d = datetime.date.fromisoformat(cal['avvio']) if cal['avvio'] else None
            pr_d = datetime.date.fromisoformat(cal['pronta_entro']) if cal['pronta_entro'] else None
            atteso_cal = {'pianificata_il': min(create) if create else None, 'avvio': cal['avvio'], 'pronta_entro': cal['pronta_entro'],
                          'giorni_a_pronta': feriali(oggi, pr_d) if pr_d else None,
                          'avvio_passato_non_avviata': bool(av_d) and av_d < oggi and not avviata_r,
                          'pronta_scaduta_non_completata': bool(pr_d) and pr_d < oggi and not compl_r}
            if cal != atteso_cal:
                errori.append('%s · sezione %s: calendario dichiarato %s, ricalcolato %s' % (o, s['id'], cal, atteso_cal))
            cats = [cat_di[i] for i in membri]
            base = [c for c in cats if c != 'chiuso_senza_esito']
            av = ('senza_tsk' if not cats else 'solo_chiusi_senza_esito' if not base else 'completata' if all(c == 'fatto' for c in base)
                  else 'in_lavorazione' if any(c in ('fatto', 'in_corso') for c in base) else 'non_avviata')
            if s['avanzamento'] != av:
                errori.append('%s · sezione %s: avanzamento %s, ricalcolato %s' % (o, s['id'], s['avanzamento'], av))
            campi = [p['campo'] for p in cfg.get('vista_pm', {}).get('piano', [])] if cfg is not None else \
                sorted({k for x in s['piano'] for k in x if k != 'us'})
            piano = [{'us': u['id'], **{k: (us_di.get(u['id'], {}).get('piano') or {}).get(k) for k in campi}} for u in s['us']]
            if s['piano'] != piano:
                errori.append('%s · sezione %s: piano diverso dal frontmatter delle US' % (o, s['id']))
        membri_di = {s['id']: [i for i in tsk if s['id'] in sez_di[i]] for s in ob['sezioni']}
        sp_atteso = sottoperimetri_attesi(ob['sezioni'], membri_di, cat_di)
        if ob.get('per_sottoperimetro') != sp_atteso:
            errori.append('%s · avanzamento per sottoperimetro dichiarato %s, ricalcolato %s' % (o, ob.get('per_sottoperimetro'), sp_atteso))
        for g in ob['non_legati_a_sezione']:
            us = None if g['us'] == '(senza US)' else g['us']
            confronta('%s · gruppo %s/%s' % (o, g['epica'], g['us']), g,
                      [i for i, e in tsk.items() if e['epica'] == g['epica'] and e['us'] == us and not sez_di[i]])

        epiche = {ep['id'] for ep in ob['epiche']}
        nel_perimetro = {i for i, e in tsk.items() if any(nel_p(e, p) for p in ob['perimetro'])}
        in_sez = {i for i in nel_perimetro if sez_di[i]}
        non_leg = sum(g['conteggi']['totale'] for g in ob['non_legati_a_sezione'])
        if len(in_sez) + non_leg != len(nel_perimetro):
            errori.append('%s · copertura: %d in sezioni + %d non legati != %d TSK nel perimetro' % (o, len(in_sez), non_leg, len(nel_perimetro)))
        cov_base = {'tsk_perimetro': len(nel_perimetro), 'tsk_in_sezioni': len(in_sez), 'tsk_non_legati': non_leg}
        cov_dichiarata = {k: v for k, v in ob.get('copertura', {}).items() if k != 'avanzamento_con_owner'}
        if cov_dichiarata != cov_base:
            errori.append('%s · copertura dichiarata diversa da quella ricalcolata' % o)

        for p in ob['perimetro']:
            if p.get('conteggi') != atteso(sorted(i for i in nel_perimetro if nel_p(tsk[i], p)), cat_di):
                errori.append('%s · avanzamento del progetto %s diverso da quello ricalcolato' % (o, p['progetto_id']))
        if ob['conteggi'] != atteso(sorted(nel_perimetro), cat_di):
            errori.append('%s · avanzamento complessivo dell\'obiettivo diverso da quello ricalcolato' % o)
        if sorted({x['fino_a'] for x in ob['sezioni'] if x.get('fino_a')}) != ob['attende_obiettivi']:
            errori.append('%s · obiettivi attesi diversi da quelli delle sezioni congelate' % o)
        if cfg is not None:
            c_o = cfg_ob.get(o, {})
            create = sorted(str(e.get('creata'))[:10] for e in snap['entita'] if e['tipo'] == 'EP' and e['id'] in epiche and e.get('creata'))
            if (ob['owner'], ob['inizio']) != (c_o.get('owner'), c_o.get('data_inizio') or (create[0] if create else None)):
                errori.append('%s · owner o data di inizio diversi dalla config o dalla creazione delle epiche' % o)
            aperti = ricalcola_aperti(ob, cfg, tsk, cat_di, sez_di, nel_perimetro)
            if ob['tsk_aperti'] != aperti:
                errori.append('%s · elenco dei TSK aperti (owner, prerequisiti, pronti) diverso da quello ricalcolato' % o)
            errori += verifica_persone(o, ob, cfg, aperti)
            errori += verifica_tsk_sezioni(o, ob, cfg, tsk, cat_di, sez_di)
            errori += verifica_avvisi(o, ob, cfg, aperti, cfg['obiettivi'])
            errori += verifica_bloccanti(o, ob, aperti, oggi)
        r = ob['riepilogo_sezioni']
        per_stato = Counter(s['stato_config'] or 'non indicato' for s in ob['sezioni'])
        if any(r['per_stato'].get(k, 0) != per_stato.get(k, 0) for k in set(per_stato) | set(r['per_stato'])) \
                or r['avviate'] != len([s for s in ob['sezioni'] if any(cat_di[i] in ('fatto', 'in_corso') for i in tsk if s['id'] in sez_di[i])]) \
                or r['senza_tsk'] != len([s for s in ob['sezioni'] if not any(s['id'] in sez_di[i] for i in tsk)]):
            errori.append('%s · riepilogo delle sezioni diverso da quello ricalcolato' % o)
        if ob['giorni_lavorativi_rimasti'] != feriali(oggi, datetime.date.fromisoformat(ob['data_target'])):
            errori.append('%s · giorni lavorativi diversi da quelli ricalcolati' % o)
        riassunto.append('%s: %d nel perimetro, %d in sezioni, %d non legati' % (o, len(nel_perimetro), len(in_sez), non_leg))

    # --- verifica A1: avanzamento_con_owner
    if cfg is not None:
        for ob in mis['obiettivi']:
            o = ob['id']
            nel = {i for i, e in tsk.items() if any(nel_p(e, p) for p in ob['perimetro'])}
            with_owner = [i for i in nel if gruppo_di(tsk[i].get('owner'), cfg)[0] == 'persona']
            cov = ob.get('copertura', {}).get('avanzamento_con_owner')
            if not with_owner:
                if cov is not None:
                    errori.append('%s · avanzamento_con_owner: atteso None, dichiarato %s' % (o, cov))
            else:
                aco_fatto = sum(1 for i in with_owner if cat_di[i] == 'fatto')
                aco_chiuso = sum(1 for i in with_owner if cat_di[i] == 'chiuso_senza_esito')
                aco_base = len(with_owner) - aco_chiuso
                aco_pct = round(100 * aco_fatto / aco_base) if aco_base else None
                aco_exp = {'fatto': aco_fatto, 'totale_con_owner': len(with_owner), 'chiuso_senza_esito': aco_chiuso,
                           'base_calcolo': aco_base, 'pct': aco_pct}
                if cov != aco_exp:
                    errori.append('%s · avanzamento_con_owner dichiarato %s, ricalcolato %s' % (o, cov, aco_exp))

    # --- verifica A2: senza_owner_summary
    if cfg is not None:
        summary = mis.get('senza_owner_summary')
        if summary is None:
            errori.append('senza_owner_summary assente dalla misura')
        else:
            tutti_senza = {}
            for ob in mis['obiettivi']:
                for v in ob.get('persone', {}).get('senza_owner', []):
                    if v['tsk'] not in tutti_senza:
                        tutti_senza[v['tsk']] = v
            senza_list = list(tutti_senza.values())
            exp_n = len(senza_list)
            exp_p0p1 = sum(1 for v in senza_list if v.get('priorita') in ('P0', 'P1'))
            exp_sez = sorted({z for v in senza_list for z in v.get('sezioni', [])})
            if summary.get('n_totali') != exp_n:
                errori.append('senza_owner_summary.n_totali dichiarato %s, ricalcolato %s' % (summary.get('n_totali'), exp_n))
            if summary.get('n_p0_p1') != exp_p0p1:
                errori.append('senza_owner_summary.n_p0_p1 dichiarato %s, ricalcolato %s' % (summary.get('n_p0_p1'), exp_p0p1))
            if summary.get('sezioni') != exp_sez:
                errori.append('senza_owner_summary.sezioni dichiarate %s, ricalcolate %s' % (summary.get('sezioni'), exp_sez))

    # --- verifica A7: eta_mediana_giorni nel senza_owner_bucket (se store presente)
    if a.store and os.path.exists(a.store):
        try:
            import yaml as _yaml_l0
            raw_store = open(a.store, 'rb').read()
            store_sha_exp = hashlib.sha256(raw_store).hexdigest()
            dati_store = _yaml_l0.safe_load(raw_store.decode('utf-8')) or {}
            voci_store = (dati_store.get('da_assegnare') or []) if isinstance(dati_store, dict) else dati_store
            eta_di = {}
            for item in voci_store:
                pv = item.get('prima_vista')
                if pv:
                    eta_di[item.get('tsk_id')] = gg_lav_da(pv, oggi)
            prov_sha = mis.get('provenienza', {}).get('da_assegnare_sha256')
            if prov_sha != store_sha_exp:
                errori.append('provenienza.da_assegnare_sha256 dichiarato %s, atteso %s' % (prov_sha, store_sha_exp))
            for ob in mis['obiettivi']:
                for bkt in ob.get('persone', {}).get('senza_owner_bucket', []):
                    sez = bkt.get('sezione')
                    senza_ob = ob.get('persone', {}).get('senza_owner', [])
                    tsk_sez = [v for v in senza_ob if sez in v['sezioni']] if sez else [v for v in senza_ob if not v['sezioni']]
                    eta_list = [eta_di.get(v['tsk']) for v in tsk_sez]
                    med = _mediana_intera(eta_list)
                    if bkt.get('eta_mediana_giorni') != med:
                        errori.append('%s · senza_owner_bucket sezione %s: eta_mediana_giorni dichiarato %s, ricalcolato %s' % (
                            ob['id'], sez, bkt.get('eta_mediana_giorni'), med))
            for ob in mis['obiettivi']:
                sla_attesi = {}
                oltre_esc = sorted(t for t, g in eta_di.items() if g is not None and g > a.escalation_days)
                oltre_stale = sorted(t for t, g in eta_di.items() if g is not None and g > a.stale_alert_days)
                if oltre_esc:
                    sla_attesi['p0-staleness'] = ('alto', oltre_esc)
                elif oltre_stale:
                    sla_attesi['staleness'] = ('medio', oltre_stale)
                dich = {x['codice']: (x['livello'], sorted(x['ids'])) for x in ob['avvisi'] if x['codice'] in _CODICI_SLA}
                if dich != sla_attesi:
                    errori.append('%s · avvisi di permanenza senza owner dichiarati %s, ricalcolati %s' % (ob['id'], dich, sla_attesi))
        except Exception as exc:
            errori.append('verifica A7 store: %s' % str(exc)[:200])
    else:
        for ob in mis['obiettivi']:
            if any(x['codice'] in _CODICI_SLA for x in ob['avvisi']):
                errori.append('%s · avvisi di permanenza senza owner presenti senza store' % ob['id'])

    citati = set(mis.get('titoli', {}))
    for ob in mis['obiettivi']:
        for b in ob['epiche'] + ob['sezioni'] + ob['non_legati_a_sezione']:
            for lista in b['prerequisiti'].values():
                citati.update(x['tsk'] for x in lista)
            for lista in b.get('elenchi', {}).values():
                citati.update(x['id'] for x in lista)
        for s in ob['sezioni']:
            citati.update(u['id'] for u in s['us'] if u['id'] not in s['us_assenti'])
    mancanti = sorted(citati - ids)
    if mancanti:
        errori.append('ID citati nella misura ma assenti dallo snapshot: %s' % ', '.join(mancanti))

    if errori:
        print('VERIFICA L0: FALLITA')
        for e in errori:
            print('  - ' + e)
        return 1
    print('VERIFICA L0: OK (%s)' % '; '.join(riassunto))
    return 0


if __name__ == '__main__':
    sys.exit(main())
