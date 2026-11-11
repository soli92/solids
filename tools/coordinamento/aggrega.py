#!/usr/bin/env python3
"""Aggrega uno snapshot del kanban nella misura per il report PM (proiezione deterministica, nessun giudizio).

    python aggrega.py --config config-base.json --snapshot snapshot.json --out misura.json [--oggi AAAA-MM-GG]

La misura è organizzata per obiettivo della config (in ordine di data target): ogni obiettivo ha le epiche del suo perimetro,
le sue sezioni, il lavoro non legato a una sezione e le sezioni di altri obiettivi congelate fino a lui (`fino_a`).
Un obiettivo senza perimetro nel kanban non ha numeri: si mostrano solo data, giorni e dipendenze.

Regole (dichiarate anche nel report):
- avanzamento = TSK fatti / (TSK totali - chiusi senza esito). I chiusi senza esito (superseded, cancelled, renamed,
  wontfix) si mostrano a parte e non entrano nel calcolo; i sospesi (on_hold, deferred) restano nel denominatore.
- un TSK si conta una sola volta nel totale dell'epica, anche se la sua US appartiene a piu' sezioni.
- sezione: solo dalla mappa US→sezione della config. I TSK delle epiche del perimetro senza sezione vanno nel gruppo
  della loro US ("lavoro non legato a una sezione"), mai dedotti dai path.
- prerequisiti (depends_on fra TSK): soddisfatto solo se il prerequisito e' «fatto». Annullato/superato = da riconciliare,
  non soddisfatto. Assente dallo snapshot = fuori perimetro o inesistente (indeterminato).
- giorni lavorativi: lun-ven da oggi (escluso) alla data target (inclusa); festivita' non considerate.
- sezione avviata: almeno un TSK fatto o in corso. Stato di avanzamento della sezione: senza TSK, non avviata, in lavorazione,
  completata (tutti i TSK nel calcolo fatti).
- progetto della sezione: quello che la elenca nei propri `sotto_obiettivi` (config, perimetro dell'obiettivo); nessuno o piu' d'uno = non attribuita.
- calendario della sezione: pianificata il = `created` più vecchio delle sue US; avvio e pronta entro dalla config
  (`sezioni[].calendario`); fatti: avvio passato senza TSK fatti o in corso, data «pronta entro» passata senza sezione completata.
- partenza della sezione: TSK aperti che possono partire subito (nessun prerequisito da completare) e TSK in attesa, con i
  prerequisiti non completati e la loro sezione. Nessuna data di partenza dedotta.
- avanzamento per progetto del perimetro (`perimetro[].conteggi`): stessa regola, sui TSK delle sue epiche.
- bloccanti prioritari: TSK aperti attesi da altri TSK aperti, ordinati per «serve entro» (avvio, o scadenza, delle sezioni in attesa).
- persone: TSK aperti del perimetro per persona del team (config `team`, riconosciuta dal campo owner del TSK) e senza owner
  (owner vuoto o fra `owner_non_persona`, es. tipi di agente); ordine: priorità, scadenza della sezione, ID. Nessuna assegnazione dedotta.
- rilascio della sezione: data e TSK di rilascio dalla config (`sezioni[].rilascio`), stato del TSK dal kanban; data passata = prima di oggi.
- piano della sezione: i campi del frontmatter delle sue US indicati in `vista_pm.piano` della config, copiati senza interpretarli.
- sottoperimetro della sezione: solo dalla config (`sezioni[].sottoperimetro`: sviluppo, configurazione = TSK di rilascio, ambiente,
  utenze e allineamento, test), null se non indicato; mai dedotto da titoli o path.
- avanzamento per sottoperimetro dell'obiettivo (`per_sottoperimetro`): stessa regola, sui TSK delle sezioni con quel sottoperimetro;
  un TSK in piu' sezioni dello stesso sottoperimetro si conta una volta, in sezioni di sottoperimetri diversi una volta in ciascuno.
  Chiavi nell'ordine sviluppo, configurazione, test, poi gli altri valori; le sezioni senza campo sotto `non_indicato`. Assente se
  nessuna sezione dell'obiettivo indica il sottoperimetro.
- ambiente di rilascio dell'obiettivo: dalla config (`obiettivi[].ambiente_rilascio`, es. preprod), default «test»; solo un'etichetta.
- per ogni blocco, gli elenchi degli ID dietro le voci da verificare (chiusi senza esito, sospesi, bloccati, stato non
  riconosciuto): servono ai prompt di verifica del report.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kanban_ids import TSK_RE, nel_perimetro as _nel_perimetro, nel_selettore  # noqa: E402

CATEGORIE = ['fatto', 'in_corso', 'da_fare', 'bloccato', 'sospeso', 'sconosciuto', 'chiuso_senza_esito']
APERTE = {'in_corso', 'da_fare', 'bloccato', 'sospeso', 'sconosciuto'}
CAT_ELENCO = ['chiuso_senza_esito', 'sospeso', 'bloccato', 'sconosciuto']
STATI_SEZIONE = ['attiva', 'anticipabile', 'congelata']
SOTTOPERIMETRI = ['sviluppo', 'configurazione', 'test']


def conteggi(tsk):
    c = {k: 0 for k in CATEGORIE}
    for t in tsk:
        c[t['categoria']] += 1
    c['totale'] = len(tsk)
    c['base_calcolo'] = c['totale'] - c['chiuso_senza_esito']
    c['pct'] = round(100 * c['fatto'] / c['base_calcolo']) if c['base_calcolo'] else None
    return c


def elenchi(tsk):
    return {cat: sorted(({'id': t['id'], 'stato': t['stato_dichiarato']} for t in tsk if t['categoria'] == cat), key=lambda x: x['id'])
            for cat in CAT_ELENCO}


def prerequisiti(tsk, indice):
    """Liste sui TSK aperti che dichiarano depends_on verso altri TSK."""
    out = {'in_attesa_prerequisito_aperto': [], 'prerequisito_da_riconciliare': [], 'prerequisito_fuori_perimetro': []}
    for t in tsk:
        if t['categoria'] not in APERTE:
            continue
        for d in t['depends_on']:
            if not TSK_RE.match(d):
                continue
            p = indice.get(d)
            if p is None:
                out['prerequisito_fuori_perimetro'].append({'tsk': t['id'], 'prerequisito': d})
            elif p['categoria'] == 'chiuso_senza_esito':
                out['prerequisito_da_riconciliare'].append({'tsk': t['id'], 'prerequisito': d, 'stato': p['stato_dichiarato']})
            elif p['categoria'] != 'fatto':
                out['in_attesa_prerequisito_aperto'].append({'tsk': t['id'], 'prerequisito': d, 'stato': p['stato_dichiarato']})
    for k in out:
        out[k] = sorted(out[k], key=lambda x: (x['tsk'], x['prerequisito']))
    return out


def blocco(tt, indice):
    return {'conteggi': conteggi(tt), 'prerequisiti': prerequisiti(tt, indice), 'elenchi': elenchi(tt)}


def per_sottoperimetro(sezioni_cfg, tsk, sez_di):
    """Conteggi dei TSK delle sezioni raggruppate per sottoperimetro della config; None se nessuna sezione lo indica."""
    if not any(s.get('sottoperimetro') for s in sezioni_cfg):
        return None
    gruppi = {}
    for s in sezioni_cfg:
        gruppi.setdefault(s.get('sottoperimetro') or 'non_indicato', set()).add(s['id'])
    chiavi = [k for k in SOTTOPERIMETRI if k in gruppi] + sorted(k for k in gruppi if k not in SOTTOPERIMETRI and k != 'non_indicato')
    chiavi += ['non_indicato'] if 'non_indicato' in gruppi else []
    return {k: conteggi([t for t in tsk if gruppi[k] & set(sez_di[t['id']])]) for k in chiavi}


def giorni_lavorativi(oggi, target):
    g, d = 0, oggi
    while d < target:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:
            g += 1
    return g


def scrivi_atomico(path, dati):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(dati, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def stato_avanzamento(c):
    """Etichetta deterministica dai conteggi (non è una valutazione: niente «in linea» o «a rischio»)."""
    if not c['totale']:
        return 'senza_tsk'
    if not c['base_calcolo']:
        return 'solo_chiusi_senza_esito'
    if c['fatto'] == c['base_calcolo']:
        return 'completata'
    if c['fatto'] + c['in_corso']:
        return 'in_lavorazione'
    return 'non_avviata'


def rilascio(r, indice, oggi):
    """Rilascio pianificato della sezione: data e TSK dalla config, stato del TSK dal kanban. Nessuna stima."""
    if not r:
        return None
    t = indice.get(r.get('tsk')) if r.get('tsk') else None
    data = r.get('data')
    fatto = bool(t and t['categoria'] == 'fatto')
    return {'data': data, 'giorni_lavorativi_rimasti': giorni_lavorativi(oggi, datetime.date.fromisoformat(data)) if data else None,
            'data_passata': bool(data) and datetime.date.fromisoformat(data) < oggi,
            'tsk': r.get('tsk'), 'tsk_trovato': bool(t), 'tsk_titolo': t['titolo'] if t else None,
            'tsk_stato': t['stato_dichiarato'] if t else None, 'tsk_categoria': t['categoria'] if t else None, 'fatto': fatto}


def calendario(s, us_creata, c, oggi):
    """Pianificata il = `created` più vecchio fra le US della sezione (frontmatter); avvio e pronta entro dalla config
    (`sezioni[].calendario`). I due fatti datati confrontano il piano con lo stato registrato: nessuna stima."""
    cal = s.get('calendario') or {}
    create = sorted(str(us_creata[u])[:10] for u in s['us'] if us_creata.get(u))
    avvio, pronta = cal.get('avvio'), cal.get('pronta_entro')
    avviata = c['fatto'] + c['in_corso'] > 0
    completata = bool(c['base_calcolo']) and c['fatto'] == c['base_calcolo']
    return {'pianificata_il': create[0] if create else None, 'avvio': avvio, 'pronta_entro': pronta,
            'giorni_a_pronta': giorni_lavorativi(oggi, datetime.date.fromisoformat(pronta)) if pronta else None,
            'avvio_passato_non_avviata': bool(avvio) and datetime.date.fromisoformat(avvio) < oggi and not avviata,
            'pronta_scaduta_non_completata': bool(pronta) and datetime.date.fromisoformat(pronta) < oggi and not completata}


def partenza(tt, indice, sez_di, sezione):
    """Quando può partire la sezione, dalle dipendenze fra TSK (depends_on): i TSK aperti senza prerequisiti da completare
    possono partire subito; gli altri attendono. Nessuna data: i TSK non ne hanno, e quella della sezione del prerequisito
    non vale per il singolo TSK."""
    subito, attesa = [], []
    for t in sorted((t for t in tt if t['categoria'] in APERTE), key=lambda t: t['id']):
        pre = []
        for d in t['depends_on']:
            if not TSK_RE.match(d):
                continue
            p = indice.get(d)
            if p is None or p['categoria'] != 'fatto':
                pre.append({'tsk': d, 'titolo': p['titolo'] if p else None, 'stato': p['stato_dichiarato'] if p else None,
                            'sezioni': sez_di.get(d, []), 'stessa_sezione': sezione in sez_di.get(d, [])})
        if pre:
            attesa.append({'tsk': t['id'], 'titolo': t['titolo'], 'prerequisiti': pre})
        else:
            subito.append(t['id'])
    return {'subito': subito, 'in_attesa': attesa}


ORDINE_PRIORITA = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}


def gruppo_owner(owner, cfg):
    """(gruppo, persona_id, nota) dal campo owner del TSK. gruppo: 'persona' (team della config, per nome o alias),
    'agente' (config owner_agente: tipi di agente), 'da_designare' (vuoto o config owner_non_persona), 'sconosciuto'."""
    v = str(owner if owner is not None else '').strip()
    if not v or v.lower() in {x.lower() for x in cfg.get('owner_non_persona', [])}:
        return 'da_designare', None, None
    if v.lower() in {x.lower() for x in cfg.get('owner_agente', [])}:
        return 'agente', None, None
    for persona in cfg.get('team', []):
        for alias in [persona['nome']] + persona.get('alias', []):
            a = alias.lower()
            if v.lower() == a:
                return 'persona', persona['id'], None
            if v.lower().startswith(a) and not v[len(a)].isalnum():
                return 'persona', persona['id'], v[len(a):].strip(' ()[],;:-') or None
    return 'sconosciuto', None, None


def chi_e(owner, cfg):
    """(persona_id, nota); None se non è una persona del team; 'sconosciuto' se la config non conosce il valore."""
    g, pid, nota = gruppo_owner(owner, cfg)
    return (pid, nota) if g == 'persona' else ('sconosciuto', None) if g == 'sconosciuto' else (None, None)


def non_assegnato(gruppo):
    """Avviso ⚠: TSK aperto senza persona e senza tipo di agente."""
    return gruppo in ('da_designare', 'sconosciuto')


def scadenza_sezione(s):
    """Prima data del piano della sezione: «pronta entro», altrimenti il rilascio."""
    return (s['calendario'] or {}).get('pronta_entro') or (s.get('rilascio') or {}).get('data')


def _senza_owner_bucket(senza_sorted):
    """Raggruppa i TSK senza owner per sezione: n_tsk, priorita_max, eta_mediana_giorni (None finché lo store non è disponibile)."""
    per_sez = {}
    fuori = []
    for v in senza_sorted:
        if v['sezioni']:
            for z in v['sezioni']:
                per_sez.setdefault(z, []).append(v)
        else:
            fuori.append(v)

    def _pmax(vv):
        rank = [ORDINE_PRIORITA.get(v['priorita'], 9) for v in vv]
        best = min(rank) if rank else 9
        return next((p for p, r in ORDINE_PRIORITA.items() if r == best), None)

    bucket = []
    for sezione, vv in sorted(per_sez.items()):
        bucket.append({'sezione': sezione, 'n_tsk': len(vv), 'priorita_max': _pmax(vv), 'eta_mediana_giorni': None})
    if fuori:
        bucket.append({'sezione': None, 'n_tsk': len(fuori), 'priorita_max': _pmax(fuori), 'eta_mediana_giorni': None})
    return bucket


def persone(cfg, tsk, nel_perimetro, sez_di, sezioni_out):
    """Assegnazioni dei TSK aperti del perimetro: per persona del team e senza owner (persona). Solo dal campo owner."""
    sez = {s['id']: s for s in sezioni_out}
    aperti = [t for t in tsk if id(t) in nel_perimetro and t['categoria'] in APERTE]
    attesi_da = {}
    for t in aperti:
        for d in t['depends_on']:
            attesi_da.setdefault(d, []).append(t['id'])

    def voce(t, nota=None):
        ss = sez_di.get(t['id'], [])
        date = sorted(x for x in (scadenza_sezione(sez[z]) for z in ss if z in sez) if x)
        return {'tsk': t['id'], 'titolo': t['titolo'], 'priorita': t['priorita'], 'stato': t['stato_dichiarato'], 'epica': t['epica'],
                'us': t['us'], 'sezioni': ss, 'scadenza_sezione': date[0] if date else None, 'owner': t['owner'], 'nota_owner': nota,
                'attesi_da': sorted(attesi_da.get(t['id'], []))}

    def chiave(v):
        return (ORDINE_PRIORITA.get(v['priorita'], 9), v['scadenza_sezione'] or '9999-12-31', v['tsk'])

    per, senza, agenti = {}, [], []
    for t in aperti:
        g, pid, nota = gruppo_owner(t['owner'], cfg)
        if g == 'persona':
            per.setdefault(pid, []).append(voce(t, nota))
        elif g == 'agente':
            agenti.append(voce(t))
        else:
            v = voce(t)
            v['owner_non_riconosciuto'] = g == 'sconosciuto'
            senza.append(v)
    def per_sezione(vv):
        ps, fuori = {}, {}
        for v in vv:
            for z in v['sezioni']:
                ps.setdefault(z, []).append(v['tsk'])
            if not v['sezioni']:
                fuori.setdefault(v['us'] or v['epica'], []).append(v['tsk'])
        return {'per_sezione': {k: sorted(x) for k, x in ps.items()}, 'fuori_sezioni': {k: sorted(x) for k, x in fuori.items()}}

    out = []
    for persona in cfg.get('team', []):
        vv = sorted(per.get(persona['id'], []), key=chiave)
        date = sorted(v['scadenza_sezione'] for v in vv if v['scadenza_sezione'])
        out.append({'id': persona['id'], 'nome': persona['nome'], 'impegno_pct': persona.get('impegno_pct'), 'nota': persona.get('nota'),
                    'tsk': vv, 'per_priorita': {k: sum(1 for v in vv if (v['priorita'] or '-') == k) for k in sorted({v['priorita'] or '-' for v in vv})},
                    'prossima_scadenza': date[0] if date else None, **per_sezione(vv)})
    senza_sorted = sorted(senza, key=chiave)
    bucket = _senza_owner_bucket(senza_sorted)
    return {'per_persona': out, 'senza_owner': senza_sorted, 'senza_owner_raggruppati': per_sezione(senza),
            'senza_owner_bucket': bucket,
            'agenti': sorted(agenti, key=chiave), 'agenti_raggruppati': per_sezione(agenti)}


def tsk_della_sezione(tt, indice, cfg):
    """Tutti i TSK della sezione (anche chiusi), per il diagramma: stato, priorità, persona dal campo owner, prerequisiti non completati."""
    nomi = {p['id']: p['nome'] for p in cfg.get('team', [])}
    out = []
    for t in tt:
        g, persona, nota = gruppo_owner(t['owner'], cfg)
        attende = [d for d in t['depends_on'] if TSK_RE.match(d) and (indice.get(d) is None or indice[d]['categoria'] != 'fatto')]
        out.append({'tsk': t['id'], 'titolo': t['titolo'], 'categoria': t['categoria'], 'stato': t['stato_dichiarato'],
                    'priorita': t['priorita'], 'gruppo': g, 'persona': persona, 'persona_nome': nomi.get(persona), 'nota_owner': nota,
                    'owner': t['owner'], 'non_assegnato': t['categoria'] in APERTE and non_assegnato(g),
                    'attende': attende if t['categoria'] in APERTE else []})
    return sorted(out, key=lambda v: (ORDINE_PRIORITA.get(v['priorita'], 9), v['tsk']))


def tsk_aperti(cfg, tsk, nel_perimetro, sez_di, sezioni_out, indice):
    """Tutti i TSK aperti del perimetro, una riga ciascuno: owner (gruppo), sezioni, scadenza della sezione, prerequisiti non
    completati, TSK aperti che li attendono, «pronto» = da fare e senza prerequisiti da completare."""
    nomi = {p['id']: p['nome'] for p in cfg.get('team', [])}
    sez = {s['id']: s for s in sezioni_out}
    aperti = [t for t in tsk if id(t) in nel_perimetro and t['categoria'] in APERTE]
    attesi_da = {}
    for t in aperti:
        for d in t['depends_on']:
            attesi_da.setdefault(d, []).append(t['id'])
    out = []
    for t in aperti:
        g, pid, nota = gruppo_owner(t['owner'], cfg)
        ss = sez_di.get(t['id'], [])
        date = sorted(x for x in (scadenza_sezione(sez[z]) for z in ss if z in sez) if x)
        attende = [d for d in t['depends_on'] if TSK_RE.match(d) and (indice.get(d) is None or indice[d]['categoria'] != 'fatto')]
        out.append({'tsk': t['id'], 'titolo': t['titolo'], 'stato': t['stato_dichiarato'], 'categoria': t['categoria'],
                    'priorita': t['priorita'], 'gruppo': g, 'persona': pid, 'persona_nome': nomi.get(pid), 'nota_owner': nota,
                    'owner': t['owner'], 'non_assegnato': non_assegnato(g), 'sezioni': ss, 'us': t['us'], 'epica': t['epica'],
                    'scadenza_sezione': date[0] if date else None, 'attende': attende, 'attesi_da': sorted(attesi_da.get(t['id'], [])),
                    'pronto': t['categoria'] == 'da_fare' and not attende})
    return sorted(out, key=lambda v: (ORDINE_PRIORITA.get(v['priorita'], 9), v['scadenza_sezione'] or '9999-12-31', v['tsk']))


LIVELLI = {'alto': 0, 'medio': 1, 'info': 2}


def gm(iso):
    return '%s/%s' % (iso[8:10], iso[5:7])


def giorni_lavorativi_da(data_str, oggi):
    """Giorni lavorativi (lun-ven) dalla data_str (ISO8601 date) a oggi, inclusi entrambi gli estremi."""
    try:
        da = datetime.date.fromisoformat(str(data_str)[:10])
    except (ValueError, TypeError):
        return None
    n = (oggi - da).days
    if n <= 0:
        return 0
    return sum(1 for k in range(n) if (da + datetime.timedelta(days=k)).weekday() < 5)


def eta_mediana(eta_list):
    """Mediana intera di una lista di interi (None se lista vuota)."""
    vv = sorted(v for v in eta_list if v is not None)
    if not vv:
        return None
    n = len(vv)
    return vv[n // 2] if n % 2 else (vv[n // 2 - 1] + vv[n // 2]) // 2


def avvisi(ob_out, cfg, oggi, obiettivi_cfg, sla_info=None):
    """Punti di attenzione con regole dichiarate (nessun giudizio): ogni avviso cita la regola, i fatti e gli ID."""
    vp = cfg.get('vista_pm', {})
    soglia_collo, soglia_gg = vp.get('soglia_collo_sezioni', 3), vp.get('soglia_giorni_scadenza', 3)
    nomi_sez = {s['id']: s['nome'] for s in ob_out['sezioni']}
    sez = {s['id']: s for s in ob_out['sezioni']}
    ap = {v['tsk']: v for v in ob_out['tsk_aperti']}
    out = []
    for v in ob_out['tsk_aperti']:
        attesa = sorted({z for w in v['attesi_da'] if w in ap for z in ap[w]['sezioni']})
        if len(attesa) >= soglia_collo:
            prime = sorted(x for x in (scadenza_sezione(sez[z]) for z in attesa if z in sez) if x)
            tardi = bool(prime) and (v['scadenza_sezione'] is None or v['scadenza_sezione'] > prime[0])
            testo = '%s (%s) è atteso da %d TSK di %d sezioni: %s' % (v['tsk'], v['titolo'], len(v['attesi_da']), len(attesa),
                                                                 ', '.join(nomi_sez.get(z, z) for z in attesa))
            if tardi:
                testo += '; la prima che lo attende è pronta entro il %s, la sua %s' % (
                    gm(prime[0]), ('entro il %s' % gm(v['scadenza_sezione'])) if v['scadenza_sezione'] else 'non ha date')
            out.append({'codice': 'collo-di-bottiglia', 'livello': 'alto' if tardi else 'medio', 'testo': testo,
                        'sezioni': sorted(set(v['sezioni']) | set(attesa)),
                        'ids': [v['tsk']] + v['attesi_da'], 'regola': 'TSK aperto atteso da TSK di almeno %d sezioni' % soglia_collo})
    p0 = [v for v in ob_out['tsk_aperti'] if v['priorita'] == 'P0' and v['non_assegnato']]
    if p0:
        out.append({'codice': 'p0-da-designare', 'livello': 'alto', 'ids': [v['tsk'] for v in p0],
                    'sezioni': sorted({z for v in p0 for z in v['sezioni']}),
                    'testo': '%d TSK P0 aperti senza owner: %s' % (len(p0), '; '.join('%s (%s)' % (v['tsk'], v['titolo']) for v in p0)),
                    'regola': 'priorità P0, owner vuoto o da designare'})
    for s in ob_out['sezioni']:
        aperti = [v for v in ob_out['tsk_aperti'] if s['id'] in v['sezioni']]
        cal = s['calendario']
        n_aperti = len(aperti)
        n_senza = sum(1 for v in aperti if v['non_assegnato'])
        if n_aperti > 0 and n_senza == n_aperti:
            out.append({'codice': 'sezione-da-designare', 'livello': 'medio', 'ids': [v['tsk'] for v in aperti], 'sezioni': [s['id']],
                        'testo': '%s: tutti i %d TSK aperti sono senza owner%s' % (
                            s['nome'], len(aperti), (' (pronta entro il %s)' % gm(cal['pronta_entro'])) if cal['pronta_entro'] else ''),
                        'regola': 'sezione con TSK aperti tutti da designare'})
        elif n_aperti > 0 and n_senza / n_aperti > 0.5:
            out.append({'codice': 'sezione-da-designare-parziale', 'livello': 'medio',
                        'ids': [v['tsk'] for v in aperti if v['non_assegnato']], 'sezioni': [s['id']],
                        'n_tsk': n_senza, 'n_p0_p1': sum(1 for v in aperti if v['non_assegnato'] and v.get('priorita') in ('P0', 'P1')),
                        'testo': '%s: %d/%d TSK aperti senza owner%s' % (
                            s['nome'], n_senza, n_aperti, (' (pronta entro il %s)' % gm(cal['pronta_entro'])) if cal['pronta_entro'] else ''),
                        'regola': 'sezione con più della metà dei TSK aperti senza owner'})
        if aperti and cal['pronta_entro'] and not cal['pronta_scaduta_non_completata'] and cal['giorni_a_pronta'] <= soglia_gg \
                and s['avanzamento'] == 'non_avviata':
            out.append({'codice': 'scadenza-vicina-non-avviata', 'livello': 'alto', 'ids': [v['tsk'] for v in aperti], 'sezioni': [s['id']],
                        'testo': '%s: %d TSK da completare entro il %s (%d %s), nessuno avviato' % (
                            s['nome'], len(aperti), gm(cal['pronta_entro']), cal['giorni_a_pronta'],
                            'giorno lavorativo' if cal['giorni_a_pronta'] == 1 else 'giorni lavorativi'),
                        'regola': '«pronta entro» a %d giorni lavorativi o meno, nessun TSK fatto o in corso' % soglia_gg})
        for chiave, cod, frase in (('pronta_scaduta_non_completata', 'scadenza-passata', 'data «pronta entro» passata, sezione non completata'),
                                   ('avvio_passato_non_avviata', 'avvio-passato', 'avvio previsto passato, nessun TSK fatto o in corso')):
            if cal[chiave]:
                out.append({'codice': cod, 'livello': 'alto', 'ids': [v['tsk'] for v in aperti], 'sezioni': [s['id']],
                            'testo': '%s: %s' % (s['nome'], frase),
                            'regola': frase})
        fa = next((o for o in obiettivi_cfg if o['id'] == s.get('fino_a')), None)
        if fa and fa['data_target'] > ob_out['data_target']:
            out.append({'codice': 'oltre-il-target', 'livello': 'info', 'ids': [u['id'] for u in s['us']], 'sezioni': [s['id']],
                        'testo': '%s attende «%s» (%s), oltre la data obiettivo %s: fuori da questo obiettivo per costruzione' % (
                            s['nome'], fa['nome'], gm(fa['data_target']), gm(ob_out['data_target'])),
                        'regola': 'sezione congelata fino a un obiettivo con data successiva'})
    for p in ob_out['perimetro']:
        datate = [s for s in ob_out['sezioni'] if s['progetto_id'] == p['progetto_id'] and scadenza_sezione(s)]
        aperti = [v for v in ob_out['tsk_aperti'] if nel_selettore(v['epica'], v['us'], p)]
        if aperti and not datate:
            out.append({'codice': 'progetto-senza-date', 'livello': 'medio', 'ids': [v['tsk'] for v in aperti], 'sezioni': [],
                        'progetto': p['progetto_id'],
                        'testo': '%s: %d TSK aperti, nessuna data nel piano (nessun sotto-obiettivo con date)' % (
                            p.get('nome') or p['progetto_id'], len(aperti)),
                        'regola': 'progetto del perimetro con TSK aperti e senza sotto-obiettivi datati'})
    if sla_info:
        stale = sla_info.get('stale_alert_days', 7)
        esc = sla_info.get('escalation_days', 14)
        stale_ids = [x['tsk_id'] for x in sla_info.get('voci', []) if (x.get('eta_giorni') or 0) > stale]
        esc_ids = [x['tsk_id'] for x in sla_info.get('voci', []) if (x.get('eta_giorni') or 0) > esc]
        if esc_ids:
            out.append({'codice': 'p0-staleness', 'livello': 'alto',
                        'ids': esc_ids, 'sezioni': [],
                        'testo': '%d TSK senza owner da oltre %d giorni lavorativi (escalation): %s' % (
                            len(esc_ids), esc, ', '.join(esc_ids)),
                        'regola': 'TSK in da_assegnare da oltre escalation_days=%d giorni lavorativi' % esc})
        elif stale_ids:
            out.append({'codice': 'staleness', 'livello': 'medio',
                        'ids': stale_ids, 'sezioni': [],
                        'testo': '%d TSK senza owner da oltre %d giorni lavorativi: %s' % (
                            len(stale_ids), stale, ', '.join(stale_ids)),
                        'regola': 'TSK in da_assegnare da oltre stale_alert_days=%d giorni lavorativi' % stale})
    return sorted(out, key=lambda x: (LIVELLI[x['livello']], x['codice'], x['testo']))


def bloccanti(ob_out, oggi):
    """Bloccanti prioritari: TSK aperti attesi da altri TSK aperti, ordinati per la data in cui servono alle sezioni che li attendono.
    «Serve entro» = per ogni sezione in attesa, il suo avvio (config) se indicato, altrimenti la sua «pronta entro» (o il rilascio);
    si prende la più vicina. Ordine: serve entro, numero di sezioni in attesa (decrescente), priorità, numero di TSK in attesa, ID."""
    sez = {s['id']: s for s in ob_out['sezioni']}
    ap = {v['tsk']: v for v in ob_out['tsk_aperti']}
    out = []
    for v in ob_out['tsk_aperti']:
        att = sorted(w for w in v['attesi_da'] if w in ap)
        if not att:
            continue
        sz = sorted({z for w in att for z in ap[w]['sezioni']})
        avvii = sorted(sez[z]['calendario']['avvio'] for z in sz if z in sez and sez[z]['calendario'].get('avvio'))
        scad = sorted(x for x in (scadenza_sezione(sez[z]) for z in sz if z in sez) if x)
        serve = sorted(x for x in ((sez[z]['calendario'].get('avvio') or scadenza_sezione(sez[z])) for z in sz if z in sez) if x)
        prima = serve[0] if serve else None
        out.append({'tsk': v['tsk'], 'titolo': v['titolo'], 'priorita': v['priorita'], 'stato': v['stato'], 'categoria': v['categoria'],
                    'gruppo': v['gruppo'], 'persona_nome': v['persona_nome'], 'owner': v['owner'], 'non_assegnato': v['non_assegnato'],
                    'sezioni': v['sezioni'], 'scadenza_sezione': v['scadenza_sezione'], 'attende': v['attende'],
                    'attesi_da': att, 'sezioni_attese': sz, 'primo_avvio_atteso': avvii[0] if avvii else None,
                    'prima_scadenza_attesa': scad[0] if scad else None, 'serve_entro': prima,
                    'serve_entro_da': None if not prima else ('avvio' if prima in avvii else 'scadenza'),
                    'giorni_a_serve_entro': giorni_lavorativi(oggi, datetime.date.fromisoformat(prima)) if prima else None,
                    'gia_necessario': bool(prima) and prima <= oggi.isoformat(),
                    'serve_prima_della_sua_sezione': bool(prima) and (v['scadenza_sezione'] is None or prima < v['scadenza_sezione'])})
    return sorted(out, key=lambda b: (b['serve_entro'] or '9999-12-31', -len(b['sezioni_attese']), ORDINE_PRIORITA.get(b['priorita'], 9),
                                      -len(b['attesi_da']), b['tsk']))


def _avanzamento_con_owner(tsk_lista, nel_perimetro, cfg):
    """Avanzamento calcolato solo sui TSK con owner dichiarato come persona del team (non vuoto, non in owner_non_persona)."""
    with_owner = [t for t in tsk_lista if id(t) in nel_perimetro and gruppo_owner(t['owner'], cfg)[0] == 'persona']
    if not with_owner:
        return None
    fatto = sum(1 for t in with_owner if t['categoria'] == 'fatto')
    chiuso = sum(1 for t in with_owner if t['categoria'] == 'chiuso_senza_esito')
    base = len(with_owner) - chiuso
    return {'fatto': fatto, 'totale_con_owner': len(with_owner), 'chiuso_senza_esito': chiuso,
            'base_calcolo': base, 'pct': round(100 * fatto / base) if base else None}


def misura_obiettivo(ob, cfg, tsk, indice, titoli_tutti, us_piano, us_creata, creata_ep, oggi):
    sez_di = {t['id']: sorted({s['sezione'] for s in t['sezioni_snap'] if s['obiettivo'] == ob['id']}) for t in tsk}
    epiche_perimetro = {ep for p in ob.get('perimetro', []) for ep in p.get('selettore', {}).get('epiche', [])}
    # TSK del perimetro (per identita' dell'oggetto: gli ID possono ripetersi nel kanban): epica fra le epiche del selettore e, se il selettore elenca `us`, US fra quelle
    nel_perimetro = {id(t) for t in tsk if _nel_perimetro(t['epica'], t['us'], ob)}

    epiche_out, perimetro_out = [], []
    for perim in ob.get('perimetro', []):
        sel = perim.get('selettore', {})
        eps = sel.get('epiche', [])
        so = perim.get('sotto_obiettivi') or {}
        perimetro_out.append({'progetto_id': perim['progetto_id'], 'epiche': eps, **({'us': sel['us']} if sel.get('us') is not None else {}),
                              'nome': next((x['nome'] for x in cfg.get('progetti', []) if x['id'] == perim['progetto_id']), perim['progetto_id']),
                              'repository': [{'id': r.get('repository_id'), 'branch_feature': r.get('branch_feature', [])}
                                             for r in perim.get('repository', [])],
                              'sotto_obiettivi': {'etichetta': so.get('etichetta'), 'sezioni': so.get('sezioni', [])},
                              'conteggi': conteggi([t for t in tsk if nel_selettore(t['epica'], t['us'], sel)])})
        for ep in eps:
            tt = [t for t in tsk if t['epica'] == ep and nel_selettore(t['epica'], t['us'], sel)]
            epiche_out.append({'id': ep, 'titolo': titoli_tutti.get(ep, ''), 'progetto_id': perim['progetto_id'], **blocco(tt, indice)})

    campi_piano = [p['campo'] for p in cfg.get('vista_pm', {}).get('piano', [])]
    sezioni_out = []
    for s in ob.get('sezioni', []):
        tt = [t for t in tsk if s['id'] in sez_di[t['id']]]
        progetti = [p['progetto_id'] for p in ob.get('perimetro', []) if s['id'] in (p.get('sotto_obiettivi') or {}).get('sezioni', [])]
        b = blocco(tt, indice)
        sezioni_out.append({'id': s['id'], 'nome': s['nome'], 'stato_config': s.get('stato'), 'ondata': s.get('ondata'),
                            'sottoperimetro': s.get('sottoperimetro'),
                            'fino_a': (s.get('fino_a') or {}).get('obiettivo'),
                            'progetto_id': progetti[0] if len(progetti) == 1 else None,
                            'avanzamento': stato_avanzamento(b['conteggi']),
                            'us': [{'id': u, 'titolo': titoli_tutti.get(u, '')} for u in s['us']],
                            'us_assenti': [u for u in s['us'] if u not in titoli_tutti],
                            'piano': [{'us': u, **{k: (us_piano.get(u) or {}).get(k) for k in campi_piano}} for u in s['us']],
                            'rilascio': rilascio(s.get('rilascio'), indice, oggi),
                            'calendario': calendario(s, us_creata, b['conteggi'], oggi),
                            'partenza': partenza(tt, indice, sez_di, s['id']),
                            'tsk': tsk_della_sezione(tt, indice, cfg), **b})

    ricetta = set(ob.get('us_ricetta', []))
    non_legati = {}
    for t in tsk:
        if id(t) in nel_perimetro and not sez_di[t['id']]:
            non_legati.setdefault((t['epica'], t['us'] or '(senza US)'), []).append(t)
    gruppi = [{'epica': ep, 'us': us, 'titolo_us': titoli_tutti.get(us, ''), 'us_ricetta': us in ricetta,
               'non_assegnati': sorted(t['id'] for t in tt if t['categoria'] in APERTE and non_assegnato(gruppo_owner(t['owner'], cfg)[0])),
               **blocco(tt, indice)}
              for (ep, us), tt in sorted(non_legati.items())]

    dipendenti = [{'obiettivo': o['id'], 'obiettivo_nome': o['nome'], 'sezione': s['id'], 'nome': s['nome'], 'us': s['us']}
                  for o in cfg['obiettivi'] for s in o.get('sezioni', []) if (s.get('fino_a') or {}).get('obiettivo') == ob['id']]

    per_stato = {k: 0 for k in STATI_SEZIONE}
    for s in sezioni_out:
        k = s['stato_config'] or 'non indicato'
        per_stato[k] = per_stato.get(k, 0) + 1
    riepilogo = {'per_stato': per_stato,
                 'avviate': sum(1 for s in sezioni_out if s['conteggi']['fatto'] + s['conteggi']['in_corso'] > 0),
                 'senza_tsk': sum(1 for s in sezioni_out if not s['conteggi']['totale'])}
    target = datetime.date.fromisoformat(ob['data_target'])
    out = {
        'id': ob['id'], 'nome': ob['nome'], 'descrizione': ob.get('descrizione', ''), 'tipo': ob.get('tipo'),
        'data_target': ob['data_target'], 'giorni_lavorativi_rimasti': giorni_lavorativi(oggi, target),
        'predefinito': ob['id'] == cfg.get('vista_pm', {}).get('obiettivo_predefinito_id'),
        'perimetro': perimetro_out, 'epiche': epiche_out, 'sezioni': sezioni_out, 'non_legati_a_sezione': gruppi,
        'riepilogo_sezioni': riepilogo, 'dipendenti': dipendenti,
        'persone': persone(cfg, tsk, nel_perimetro, sez_di, sezioni_out),
        'tsk_aperti': tsk_aperti(cfg, tsk, nel_perimetro, sez_di, sezioni_out, indice),
        'conteggi': conteggi([t for t in tsk if id(t) in nel_perimetro]),
        'owner': ob.get('owner'), 'inizio': ob.get('data_inizio') or (min(creata_ep[e] for e in epiche_perimetro if creata_ep.get(e))
                                                                     if any(creata_ep.get(e) for e in epiche_perimetro) else None),
        'inizio_da': 'config' if ob.get('data_inizio') else ('creazione epica' if any(creata_ep.get(e) for e in epiche_perimetro) else None),
        'attende_obiettivi': sorted({x['fino_a'] for x in sezioni_out if x.get('fino_a')}),
        'copertura': {'tsk_perimetro': len(nel_perimetro),
                      'tsk_in_sezioni': sum(1 for t in tsk if id(t) in nel_perimetro and sez_di[t['id']]),
                      'tsk_non_legati': sum(len(v) for v in non_legati.values()),
                      'avanzamento_con_owner': _avanzamento_con_owner(tsk, nel_perimetro, cfg)},
        'ambiente_rilascio': ob.get('ambiente_rilascio') or 'test',
    }
    sp = per_sottoperimetro(ob.get('sezioni', []), tsk, sez_di)
    if sp is not None:
        out['per_sottoperimetro'] = sp
    return out


def _leggi_store(store_path, oggi):
    """Legge da_assegnare.yaml e calcola eta_giorni per voce. Restituisce (voci, sha256, avviso) o ([], None, avviso)."""
    if not store_path or not os.path.exists(store_path):
        return [], None, 'store da_assegnare assente: nessun calcolo eta/SLA'
    try:
        import yaml as _yaml
        raw = open(store_path, 'rb').read()
        sha = hashlib.sha256(raw).hexdigest()
        dati = _yaml.safe_load(raw.decode('utf-8')) or {}
        # forma canonica {da_assegnare: [...]}; la lista nuda e' la forma scritta dalle versioni precedenti
        elenco = dati if isinstance(dati, list) else (dati.get('da_assegnare') or [])
        voci = []
        for item in elenco:
            pv = item.get('prima_vista')
            eta = giorni_lavorativi_da(pv, oggi) if pv else None
            voci.append({'tsk_id': item.get('tsk_id'), 'prima_vista': str(pv) if pv else None, 'eta_giorni': eta})
        return voci, sha, None
    except Exception as exc:
        return [], None, 'store da_assegnare non leggibile: %s' % str(exc)[:200]


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True)
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--oggi', help='AAAA-MM-GG (default: data locale di oggi)')
    ap.add_argument('--store', help='percorso di analytics/coordinamento/<operatore>/da_assegnare.yaml')
    ap.add_argument('--stale-alert-days', type=int, default=7, dest='stale_alert_days')
    ap.add_argument('--escalation-days', type=int, default=14, dest='escalation_days')
    a = ap.parse_args(argv)

    cfg = json.load(open(a.config, encoding='utf-8'))
    snap_bytes = open(a.snapshot, 'rb').read()
    snap = json.loads(snap_bytes)
    oggi = datetime.date.fromisoformat(a.oggi) if a.oggi else datetime.date.today()

    store_voci, store_sha, store_avviso = _leggi_store(a.store, oggi)
    sla_info = {'stale_alert_days': a.stale_alert_days, 'escalation_days': a.escalation_days,
                'voci': store_voci} if store_voci else None

    entita = snap['entita']
    titoli_tutti = {e['id']: e.get('titolo', '') for e in entita}
    tsk = []
    for e in entita:
        if e['tipo'] != 'TSK' or 'stato' not in e:
            continue
        tsk.append({'id': e['id'], 'epica': e['epica'], 'us': e['us'], 'titolo': e.get('titolo', ''),
                    'categoria': e['stato']['normalizzato'], 'stato_dichiarato': e['stato']['dichiarato'],
                    'depends_on': e.get('depends_on', []), 'sezioni_snap': e.get('sezioni', []),
                    'owner': e.get('owner'), 'priorita': e.get('priority')})
    indice = {t['id']: t for t in tsk}
    tsk_illeggibili = sorted(e['id'] for e in entita if e['tipo'] == 'TSK' and 'stato' not in e)

    ordine = {o['id']: i for i, o in enumerate(cfg['obiettivi'])}
    us_piano = {e['id']: e.get('piano') or {} for e in entita if e['tipo'] == 'US'}
    us_creata = {e['id']: e.get('creata') for e in entita if e['tipo'] == 'US'}
    creata_ep = {e['id']: (str(e['creata'])[:10] if e.get('creata') else None) for e in entita if e['tipo'] == 'EP'}
    obiettivi = [misura_obiettivo(o, cfg, tsk, indice, titoli_tutti, us_piano, us_creata, creata_ep, oggi)
                 for o in sorted(cfg['obiettivi'], key=lambda o: (o['data_target'], ordine[o['id']]))]

    citati = set()
    for ob in obiettivi:
        for b in ob['epiche'] + ob['sezioni'] + ob['non_legati_a_sezione']:
            for lista in b['prerequisiti'].values():
                for x in lista:
                    citati.update((x['tsk'], x['prerequisito']))
            for lista in b['elenchi'].values():
                citati.update(x['id'] for x in lista)

    if store_voci:
        eta_di = {v['tsk_id']: v['eta_giorni'] for v in store_voci}
        for ob in obiettivi:
            for bkt in ob['persone'].get('senza_owner_bucket', []):
                sez = bkt['sezione']
                tsk_senza = [v for v in ob['persone']['senza_owner'] if sez in v['sezioni']] if sez else \
                            [v for v in ob['persone']['senza_owner'] if not v['sezioni']]
                eta_list = [eta_di.get(v['tsk']) for v in tsk_senza]
                bkt['eta_mediana_giorni'] = eta_mediana(eta_list)

    for o in obiettivi:
        o['avvisi'] = avvisi(o, cfg, oggi, cfg['obiettivi'], sla_info)
        o['bloccanti'] = bloccanti(o, oggi)
    titoli = {i: titoli_tutti[i] for i in sorted(citati) if i in titoli_tutti}

    tutti_senza = {}
    for ob in obiettivi:
        for v in ob['persone'].get('senza_owner', []):
            if v['tsk'] not in tutti_senza:
                tutti_senza[v['tsk']] = v
    senza_list = list(tutti_senza.values())
    senza_owner_summary = {
        'n_totali': len(senza_list),
        'n_p0_p1': sum(1 for v in senza_list if v.get('priorita') in ('P0', 'P1')),
        'sezioni': sorted({z for v in senza_list for z in v.get('sezioni', [])}),
    }

    prov = {
        'snapshot_sha256': hashlib.sha256(snap_bytes).hexdigest(),
        'config_sha256': snap['provenienza']['config_sha256'],
        'fonte': snap['provenienza']['fonte'], 'ref': snap['provenienza'].get('ref'), 'ref_sha': snap['provenienza'].get('ref_sha'),
        'factory_head': snap['provenienza']['factory_head'],
        'kanban_non_committati': snap['provenienza']['kanban_non_committati'],
        'non_pushati': snap['provenienza'].get('non_pushati'),
    }
    if store_sha is not None:
        prov['da_assegnare_sha256'] = store_sha
        prov['da_assegnare_stale_alert_days'] = a.stale_alert_days
        prov['da_assegnare_escalation_days'] = a.escalation_days
    out = {
        'versione_schema': '1.2',
        'nome': 'misura del kanban',
        'oggi': oggi.isoformat(),
        'senza_owner_summary': senza_owner_summary,
        'provenienza': prov,
        'obiettivi': obiettivi,
        'titoli': titoli,
        'copertura': {'tsk_totali': len(tsk) + len(tsk_illeggibili), 'tsk_illeggibili': tsk_illeggibili},
        'qualita_dato': snap['findings'],
    }
    if store_avviso:
        print('NOTA store: %s' % store_avviso)
    scrivi_atomico(a.out, out)
    print('misura: %d TSK, %d illeggibili; %s -> %s' % (
        out['copertura']['tsk_totali'], len(tsk_illeggibili),
        '; '.join('%s: %d nel perimetro, %d in sezioni' % (o['id'], o['copertura']['tsk_perimetro'], o['copertura']['tsk_in_sezioni'])
                  for o in obiettivi), a.out))


if __name__ == '__main__':
    sys.exit(main())
