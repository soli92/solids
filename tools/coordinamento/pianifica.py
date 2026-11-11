#!/usr/bin/env python3
"""Pianificazione deterministica del perimetro: classifica di priorita' dei TSK e proposta di owner.

    python tools/coordinamento/pianifica.py \\
        --config analytics/coordinamento/config-<operatore>.json \\
        --oggi YYYY-MM-DD [--ref HEAD] [--out pianificazione.json] [--operatore <id>]

- Legge il kanban SEMPRE dal commit (git cat-file su --ref, default HEAD): stesso commit +
  stessa config + stesso --oggi => stessi byte. Nessun orologio implicito, nessun timestamp.
- NON scrive mai in management/kanban/. Le proposte hanno la stessa forma di quelle di
  proponi_kanban.py e vanno al tpm dopo conferma umana (single-writer di owner: = tpm).
- Richiede il blocco `pianificazione` nella config: senza, esce con codice 2 (nessun default
  implicito sui pesi).

Classifica (TSK del perimetro in stato da_fare o bloccato):
  punteggio = (punti_priorita + punti_urgenza + punti_sblocco) / giorni_dimensione
  - punti_priorita  da `priority` (P0..P3) secondo pianificazione.punti_priorita
  - punti_urgenza   giorni lavorativi da --oggi alla scadenza (pronta_entro della sezione che
                    elenca il TSK in `tsk`, altrimenti della sezione che contiene la US e non lo
                    esclude, altrimenti data_target dell'obiettivo che contiene l'epica),
                    valutati sulle fasce pianificazione.fasce_urgenza; scadenza passata = 0 giorni
  - punti_sblocco   TSK aperti che dipendono da questo (depends_on/blocked_by/dependencies degli
                    altri + `blocks` di questo) x pianificazione.punti_sblocco_per_tsk
  - giorni          estimated_days, altrimenti estimate/size/estimated_size mappati dalla tabella
                    taglia->giorni (pianificazione.dimensioni_giorni oppure, con
                    pianificazione.velocity_config e senza dimensioni_giorni, la tabella `giorni`
                    di /velocity: una sola fonte), altrimenti dimensione_predefinita (avviso);
                    nel denominatore mai sotto pianificazione.dimensione_minima_giorni (default:
                    la taglia piu' piccola di dimensioni_giorni), cosi' una stima di 0.1 gg non
                    domina la classifica
  Un TSK e' «non pronto» se ha dipendenze TSK/US ancora aperte, un blocked_by esterno o stato
  bloccato: resta in classifica ma non riceve proposte.

Proposte di owner (solo TSK da_fare, pronti, senza owner persona; contano come senza owner anche
i TSK delle persone in pianificazione.persone_da_riassegnare):
  ordine di classifica, assegnazione greedy fra pianificazione.persone_assegnabili:
  1. competenze dichiarate (team[].competenze.layer): se presenti filtrano sul layer radice
  2. capacita' residua >= giorni del TSK, con
     capacita' = (giorni lavorativi dell'orizzonte - assenze) * impegno_pct/100 - carico nell'orizzonte
     carico nell'orizzonte = giorni dei TSK della persona (su TUTTO il kanban) in corso, oppure da
     fare/bloccati con scadenza entro la fine dell'orizzonte; il resto del backlog della persona e'
     riportato come carico_oltre_orizzonte e non riduce la capacita'
  3. fra i capienti: affinita' storica (TSK chiusi dalla persona sullo stesso layer radice +
     sulla stessa epica), poi capacita' residua, poi id
  Nessuno capiente => voce in non_assegnabili, nessuna proposta forzata.
  TSK bloccati senza owner => proposta verso pianificazione.referente_bloccanti (se dichiarato).

Esclusi sempre (TSK in revisione o in lavorazione): review/approved, in_progress, sospesi, chiusi.

Velocity misurata (con pianificazione.velocity_config e velocity_misurata non false): per ogni
persona l'output riporta punti e TSK chiusi a settimana (tools/analytics/team-velocity.py, con
--oggi come data), il carico nell'orizzonte in punti e le settimane che servono al ritmo misurato.
E' un dato di confronto: le proposte restano calcolate sulla capacita' nominale. La velocity legge
il kanban del working tree e la storia git corrente (non --ref): e' l'unica parte dell'output che
non dipende solo da ref + config + oggi, ed e' dichiarata in provenienza.velocity_misurata.
Senza velocity_config nulla cambia (stessi byte).

L'output contiene una `legenda` con le regole di calcolo.

Ultima riga su stdout: RIEPILOGO seguito da JSON.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kanban_ids import CAMPI_EP, CAMPI_US, da_frontmatter, da_path, nel_perimetro  # noqa: E402
from percorsi import MESSAGGIO_SPENTA, operatore_da_config, pm_report_abilitato, risolvi_factory_root  # noqa: E402
from proponi_kanban import (  # noqa: E402
    ID_RE, STATI_IN_LAVORAZIONE, frontmatter, git_rev_parse, normalizza_stato, scrivi_atomico, yaml,
)
from aggrega import gruppo_owner  # noqa: E402

RIF_RE = re.compile(r'\b((?:[A-Z]{2,4}-)?(?:TSK|US)-\d+)\b')  # prefisso di namespace opzionale
CHIAVI_DIPENDENZE = ('depends_on', 'blocked_by', 'dependencies')
CHIAVI_DIMENSIONE = ('estimate', 'size', 'estimated_size')
ORDINE_PRIORITA = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
STATI_APERTI = {'da_fare', 'in_corso', 'bloccato'}
STATI_R7 = {'review', 'approved'}

OBBLIGATORI = ('persone_assegnabili', 'orizzonte_giorni_lavorativi',
               'dimensione_predefinita', 'punti_priorita', 'fasce_urgenza', 'punti_sblocco_per_tsk')


# — Lettura del kanban dal commit —

def leggi_kanban(root, ref, kanban):
    """{path: testo} di tutti i .md sotto kanban al commit ref, con un solo git cat-file --batch."""
    r = subprocess.run(['git', '-C', root, 'ls-tree', '-r', '--name-only', ref, '--', kanban],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    paths = sorted(p for p in r.stdout.splitlines() if p.endswith('.md')) if r.returncode == 0 else []
    if not paths:
        return {}
    richiesta = ''.join('%s:%s\n' % (ref, p) for p in paths).encode('utf-8')
    out = subprocess.run(['git', '-C', root, 'cat-file', '--batch'], input=richiesta,
                         capture_output=True).stdout
    testi, pos = {}, 0
    for p in paths:
        fine_header = out.index(b'\n', pos)
        header = out[pos:fine_header].split()
        pos = fine_header + 1
        if len(header) < 3 or header[1] == b'missing':
            continue
        n = int(header[2])
        testi[p] = out[pos:pos + n].decode('utf-8', errors='replace')
        pos += n + 1
    return testi


def riferimenti(valore):
    """(id TSK/US citati, voci testuali senza id) da un campo dipendenze (lista, stringa o mappa)."""
    if valore in (None, '', [], {}):
        return [], []
    voci = valore if isinstance(valore, list) else [valore]
    ids, testi = [], []
    for v in voci:
        s = ' '.join(str(x) for x in v.values()) if isinstance(v, dict) else str(v)
        trovati = RIF_RE.findall(s)
        if trovati:
            ids.extend(trovati)
        elif s.strip():
            testi.append(s.strip())
    return sorted(set(ids)), sorted(set(testi))


def entita_kanban(testi, kanban, stati):
    """{id: entita} per US e TSK, con i campi usati dalla pianificazione."""
    out = {}
    prefisso = kanban.rstrip('/') + '/'
    for path, testo in testi.items():
        nome = path.rsplit('/', 1)[-1][:-3]
        m = ID_RE.match(nome)
        if not m or m.group(2) not in ('US', 'TSK'):
            continue
        dati, errore = frontmatter(testo)
        if errore:
            continue
        dentro = path[len(prefisso):].split('/') if path.startswith(prefisso) else []
        dip_ids, dip_testi, esterni = [], [], []
        for k in CHIAVI_DIPENDENZE:
            ids, tt = riferimenti(dati.get(k))
            dip_ids.extend(ids)
            (esterni if k == 'blocked_by' else dip_testi).extend(tt)
        blocks, _ = riferimenti(dati.get('blocks'))
        out[nome] = {
            'id': nome,
            'tipo': m.group(2),
            'file': path,
            # appartenenza: frontmatter, in mancanza le cartelle (nome uguale all'ID o «ID-slug»)
            'epic': da_frontmatter(dati, CAMPI_EP, 'EP') or da_path(dentro, 'EP') or '',
            'us': da_frontmatter(dati, CAMPI_US, 'US') or da_path(dentro, 'US') or '',
            'titolo': str(dati.get('title') or '').strip(),
            'stato_raw': str(dati.get('status') or '').strip(),
            'stato_norm': normalizza_stato(dati.get('status'), stati),
            'owner': str(dati.get('owner') or '').strip(),
            'priority': str(dati.get('priority') or '').strip().upper(),
            'layer': str(dati.get('layer') or '').strip(),
            'aggiornato': str(dati.get('updated') or '').strip()[:10] or None,
            'estimated_days': dati.get('estimated_days'),
            'dimensioni': {k: str(dati.get(k)).strip().upper() for k in CHIAVI_DIMENSIONE if dati.get(k)},
            'dipendenze': sorted(set(dip_ids)),
            'dipendenze_testo': sorted(set(dip_testi)),
            'bloccanti_esterni': sorted(set(esterni)),
            'blocks': blocks,
        }
    return out


# — Calendario —

def giorni_orizzonte(oggi, n, festivi):
    """I primi n giorni lavorativi a partire da oggi (incluso, se lavorativo)."""
    out, d = [], oggi
    while len(out) < n:
        if d.weekday() < 5 and d.isoformat() not in festivi:
            out.append(d)
        d += datetime.timedelta(days=1)
    return out


def giorni_lavorativi(oggi, target, festivi):
    """Giorni lavorativi in (oggi, target]; 0 se target <= oggi."""
    g, d = 0, oggi
    while d < target:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in festivi:
            g += 1
    return g


def giorni_assenza(persona, orizzonte):
    giorni = set()
    for a in persona.get('assenze') or []:
        try:
            dal = datetime.date.fromisoformat(str(a['dal']))
            al = datetime.date.fromisoformat(str(a.get('al') or a['dal']))
        except (KeyError, ValueError):
            continue
        giorni.update(d for d in orizzonte if dal <= d <= al)
    return len(giorni)


# — Config —

def valida_config(cfg):
    """Lista di errori del blocco pianificazione (vuota se valido)."""
    p = cfg.get('pianificazione')
    if not isinstance(p, dict):
        return ['blocco "pianificazione" assente nella config']
    errori = ['pianificazione.%s mancante' % k for k in OBBLIGATORI if k not in p]
    if not isinstance(p.get('dimensioni_giorni'), dict):
        errori.append('pianificazione.dimensioni_giorni mancante (o velocity_config senza tabella `giorni`)')
    if errori:
        return errori
    team = {t['id'] for t in cfg.get('team', [])}
    if not p['persone_assegnabili']:
        errori.append('pianificazione.persone_assegnabili vuoto')
    errori += ['pianificazione.persone_assegnabili: «%s» non e\' nel team' % x
               for x in p['persone_assegnabili'] if x not in team]
    errori += ['pianificazione.persone_da_riassegnare: «%s» non e\' nel team' % x
               for x in p.get('persone_da_riassegnare') or [] if x not in team]
    errori += ['pianificazione.persone_da_riassegnare: «%s» e\' anche fra le assegnabili' % x
               for x in p.get('persone_da_riassegnare') or [] if x in p['persone_assegnabili']]
    m = p.get('dimensione_minima_giorni')
    if m is not None and (not isinstance(m, (int, float)) or m <= 0):
        errori.append('pianificazione.dimensione_minima_giorni deve essere un numero > 0')
    ref = p.get('referente_bloccanti')
    if ref and ref not in team:
        errori.append('pianificazione.referente_bloccanti: «%s» non e\' nel team' % ref)
    if not isinstance(p['orizzonte_giorni_lavorativi'], int) or p['orizzonte_giorni_lavorativi'] <= 0:
        errori.append('pianificazione.orizzonte_giorni_lavorativi deve essere un intero > 0')
    if p['dimensione_predefinita'] not in p['dimensioni_giorni']:
        errori.append('pianificazione.dimensione_predefinita non e\' fra le chiavi di dimensioni_giorni')
    if any(not isinstance(v, (int, float)) or v <= 0 for v in p['dimensioni_giorni'].values()):
        errori.append('pianificazione.dimensioni_giorni: i valori devono essere numeri > 0')
    for f in p['fasce_urgenza']:
        if not isinstance(f, dict) or 'entro_giorni' not in f or 'punti' not in f:
            errori.append('pianificazione.fasce_urgenza: ogni fascia vuole entro_giorni e punti')
            break
    return errori


def perimetro_epiche(cfg):
    escluse = set(cfg.get('epiche_escluse') or [])
    return sorted({e for o in cfg.get('obiettivi', []) for p in o.get('perimetro', [])
                   for e in p.get('selettore', {}).get('epiche', [])} - escluse)


def scadenze(cfg):
    """(tsk -> [(data, fonte)], us -> [(data, fonte, obiettivo)], epic -> [(data, fonte)], {(obiettivo, tsk)})
    da sezioni e obiettivi della config. Stessa appartenenza dello snapshot: una sezione con `tsk` contiene
    solo i TSK elencati, le altre i TSK delle loro US tranne quelli elencati altrove nello stesso obiettivo."""
    per_tsk, per_us, per_epic, espliciti = {}, {}, {}, set()
    for o in cfg.get('obiettivi', []):
        for s in o.get('sezioni', []):
            pronta = (s.get('calendario') or {}).get('pronta_entro')
            if 'tsk' in s:
                for t in s['tsk']:
                    espliciti.add((o['id'], t))
                    if pronta:
                        per_tsk.setdefault(t, []).append((str(pronta), 'sezione:%s' % s['id']))
                continue
            if pronta:
                for us in s.get('us', []):
                    per_us.setdefault(us, []).append((str(pronta), 'sezione:%s' % s['id'], o['id']))
        if o.get('data_target'):
            for p in o.get('perimetro', []):
                for e in p.get('selettore', {}).get('epiche', []):
                    per_epic.setdefault(e, []).append((str(o['data_target']), 'obiettivo:%s' % o['id']))
    return per_tsk, per_us, per_epic, espliciti


# — Velocity (tools/analytics/team-velocity.py) —

def risolvi_velocity(root, pc, oggi):
    """Con pianificazione.velocity_config: tabella taglia->giorni dalla config di /velocity (se il blocco
    non ne dichiara una propria) e, salvo velocity_misurata: false, velocity misurata per persona.
    Modifica pc in place; ritorna il dizionario velocity per calcola() (None senza velocity_config)."""
    rel = pc.get('velocity_config')
    if not rel:
        return None
    path = os.path.join(root, rel)
    with open(path, 'rb') as fh:
        grezzo = fh.read()
    vcfg = json.loads(grezzo.decode('utf-8'))
    if 'dimensioni_giorni' not in pc and isinstance(vcfg.get('giorni'), dict):
        pc['dimensioni_giorni'] = dict(vcfg['giorni'])
        pc['_fonte_dimensioni'] = rel
    vel = {'config': rel, 'config_sha256': hashlib.sha256(grezzo).hexdigest(),
           'punti': vcfg.get('punti') or {}, 'misurata': False}
    if pc.get('velocity_misurata', True) is False:
        return vel
    script = os.path.join(root, 'tools', 'analytics', 'team-velocity.py')
    spec = importlib.util.spec_from_file_location('team_velocity', script)
    tv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tv)
    radice = pathlib.Path(root)
    r = tv.compute(tv.load_config(rel, radice), radice, today=oggi, per_persona=True)
    n_sett = len(r['finestra_settimane'])
    vel.update({
        'misurata': True,
        'epiche': [e['id'] for e in r['epiche']],
        'finestra_settimane': r['finestra_settimane'],
        # chiave: id della persona nel team di /velocity (o il nome grezzo dell'owner se non e' nel team)
        'per_persona': {k: {'punti_sett': p['punti_sett'],
                            'tsk_sett': round(p['tsk_finestra'] / n_sett, 1) if n_sett else 0.0}
                        for k, p in r['persone'].items()},
        'legenda': r['legenda'],
    })
    return vel


def legenda(pc, velocity, orizzonte_gg):
    """Righe della legenda della pianificazione, dai parametri effettivi."""
    tab = ' · '.join('%s %s' % kv for kv in pc['dimensioni_giorni'].items())
    righe = [
        'Punteggio di priorita\' = (punti priorita\' + punti urgenza + punti sblocco) / giorni del TSK. '
        'Priorita\': %s. Urgenza: giorni lavorativi alla scadenza della sezione del TSK (o dell\'obiettivo) sulle '
        'fasce %s. Sblocco: %s punti per ogni TSK aperto che dipende da questo.' % (
            ' · '.join('%s %s' % kv for kv in pc['punti_priorita'].items()),
            ', '.join('<= %s gg: %s' % (f['entro_giorni'], f['punti']) for f in pc['fasce_urgenza']),
            pc['punti_sblocco_per_tsk']),
        'Giorni di un TSK: estimated_days, altrimenti la taglia (estimate/size/estimated_size) con la tabella '
        '%s%s, altrimenti la taglia %s; nel denominatore mai meno di %s gg.' % (
            tab, ' (fonte: %s)' % pc['_fonte_dimensioni'] if pc.get('_fonte_dimensioni') else '',
            pc['dimensione_predefinita'],
            pc.get('dimensione_minima_giorni') or min(pc['dimensioni_giorni'].values())),
        'Non pronto: dipendenze TSK/US ancora aperte, blocked_by esterno o stato bloccato. Resta in classifica, '
        'non riceve proposte.',
        'Capacita\' nominale = (%d giorni lavorativi dell\'orizzonte - assenze) x impegno_pct - carico '
        'nell\'orizzonte (TSK della persona in corso, o da fare/bloccati con scadenza entro l\'orizzonte, su '
        'tutto il kanban). Il resto del backlog e\' riportato a parte.' % orizzonte_gg,
        'Proposta di owner: fra le persone assegnabili con competenze compatibili e capacita\' residua '
        'sufficiente, prima chi ha chiuso piu\' TSK sullo stesso layer e sulla stessa epica, poi chi ha piu\' '
        'capacita\' residua. Nessuno capiente: non assegnabile.',
    ]
    if velocity and velocity.get('misurata'):
        righe.append(
            'Velocity misurata (solo confronto, non entra nelle proposte; letta dal kanban e dalla storia git '
            'correnti, non da --ref): punti e TSK chiusi a settimana dalla persona sulle epiche %s, settimane %s. '
            'Carico in punti: taglie dei TSK nell\'orizzonte con la scala di /velocity. Settimane al ritmo '
            'misurato = carico in punti / punti a settimana.' % (
                ', '.join(velocity['epiche']), ', '.join(velocity['finestra_settimane']) or 'nessuna'))
        righe += ['/velocity — %s' % r for r in velocity['legenda']]
    return righe


# — Calcolo (funzione pura) —

def dimensione(t, pc):
    """(giorni, fonte, stimata) del TSK."""
    v = t.get('estimated_days')
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
        return float(v), 'estimated_days', True
    for k in CHIAVI_DIMENSIONE:
        taglia = t['dimensioni'].get(k)
        if taglia in pc['dimensioni_giorni']:
            return float(pc['dimensioni_giorni'][taglia]), '%s:%s' % (k, taglia), True
    d = pc['dimensione_predefinita']
    return float(pc['dimensioni_giorni'][d]), 'predefinita:%s' % d, False


def punti_urgenza(giorni, fasce):
    if giorni is None:
        return 0
    for f in sorted(fasce, key=lambda f: f['entro_giorni']):
        if giorni <= f['entro_giorni']:
            return f['punti']
    return 0


def layer_radice(layer):
    return layer.split('/')[0].strip().lower()


def calcola(entita, cfg, oggi, velocity=None):
    """Classifica, proposte, non assegnabili, carico per persona e avvisi.

    Funzione pura: nessun accesso a git o al disco. `oggi` e' un datetime.date.
    `velocity` e' il dizionario di risolvi_velocity() (opzionale): aggiunge i dati misurati per persona.
    """
    pc = cfg['pianificazione']
    festivi = {str(x) for x in pc.get('festivi') or []}
    includi_agente = bool(pc.get('includi_owner_agente'))
    epiche = set(perimetro_epiche(cfg))
    sc_tsk, sc_us, sc_epic, sc_espliciti = scadenze(cfg)
    team = {t['id']: t for t in cfg.get('team', [])}
    minimo = float(pc.get('dimensione_minima_giorni') or min(pc['dimensioni_giorni'].values()))
    da_riassegnare = set(pc.get('persone_da_riassegnare') or [])
    orizzonte = giorni_orizzonte(oggi, pc['orizzonte_giorni_lavorativi'], festivi)
    fine_orizzonte = orizzonte[-1].isoformat()
    avvisi = []

    def scadenza_di(t):
        date = (sc_tsk.get(t['id'])
                or [(d, f) for d, f, ob in sc_us.get(t['us'], []) if (ob, t['id']) not in sc_espliciti]
                or sc_epic.get(t['epic']) or [])
        return min(date) if date else (None, None)

    tsk = {k: v for k, v in entita.items() if v['tipo'] == 'TSK'}
    for t in tsk.values():
        t['giorni'], t['dimensione_fonte'], t['stimata'] = dimensione(t, pc)
        t['gruppo'], t['persona'], _ = gruppo_owner(t['owner'], cfg)

    def aperto(eid):
        e = entita.get(eid)
        return e is not None and e['stato_norm'] in STATI_APERTI | {'sospeso', 'sconosciuto'}

    # Dipendenti aperti di ciascun TSK (chi aspetta lui)
    dipendenti = {k: set() for k in tsk}
    for t in tsk.values():
        if t['stato_norm'] not in STATI_APERTI:
            continue
        for d in t['dipendenze']:
            if d in dipendenti:
                dipendenti[d].add(t['id'])
    for t in tsk.values():
        for b in t['blocks']:
            if b in tsk and tsk[b]['stato_norm'] in STATI_APERTI:
                dipendenti[t['id']].add(b)

    # Carico e affinita' su tutto il kanban
    carico = {pid: {'giorni': 0.0, 'n': 0, 'oltre': 0.0, 'n_oltre': 0, 'punti': 0} for pid in team}
    scala_punti = (velocity or {}).get('punti') or {}
    affinita_layer, affinita_epic = {}, {}
    for t in tsk.values():
        pid = t['persona']
        if t['gruppo'] != 'persona' or pid not in team:
            continue
        if t['stato_norm'] in STATI_APERTI:
            scad, _ = scadenza_di(t)
            if t['stato_norm'] == 'in_corso' or (scad and scad <= fine_orizzonte):
                carico[pid]['giorni'] += t['giorni']
                carico[pid]['n'] += 1
                taglia = next((t['dimensioni'][k] for k in CHIAVI_DIMENSIONE[:2] if t['dimensioni'].get(k)), None)
                carico[pid]['punti'] += scala_punti.get(taglia, 0)
            else:
                carico[pid]['oltre'] += t['giorni']
                carico[pid]['n_oltre'] += 1
        elif t['stato_norm'] == 'fatto':
            kl = (pid, layer_radice(t['layer']))
            ke = (pid, t['epic'])
            affinita_layer[kl] = affinita_layer.get(kl, 0) + 1
            affinita_epic[ke] = affinita_epic.get(ke, 0) + 1

    # Classifica
    classifica = []
    for t in sorted(tsk.values(), key=lambda x: x['id']):
        # con selettore.us in classifica solo i TSK delle US elencate; il carico resta su tutto il lavoro della persona
        if t['epic'] not in epiche or t['stato_norm'] not in ('da_fare', 'bloccato') \
                or not any(nel_perimetro(t['epic'], t.get('us'), o) for o in cfg.get('obiettivi', [])):
            continue
        if t['stato_raw'].lower() in STATI_R7 | STATI_IN_LAVORAZIONE:
            continue
        if not t['stimata']:
            avvisi.append({'tsk_id': t['id'], 'tipo': 'dimensione_non_stimata',
                           'dettaglio': 'nessun estimated_days/size/estimate riconosciuto: usata %s' % t['dimensione_fonte']})
        scadenza, fonte_scadenza = scadenza_di(t)
        giorni_scad = None
        if scadenza:
            try:
                giorni_scad = giorni_lavorativi(oggi, datetime.date.fromisoformat(scadenza), festivi)
            except ValueError:
                avvisi.append({'tsk_id': t['id'], 'tipo': 'scadenza_non_valida', 'dettaglio': scadenza})
                scadenza = fonte_scadenza = None
        pp = pc['punti_priorita'].get(t['priority'], 0)
        if t['priority'] not in pc['punti_priorita']:
            avvisi.append({'tsk_id': t['id'], 'tipo': 'priorita_non_riconosciuta',
                           'dettaglio': t['priority'] or '(vuota)'})
        pu = punti_urgenza(giorni_scad, pc['fasce_urgenza'])
        n_sbl = len(dipendenti[t['id']])
        ps = n_sbl * pc['punti_sblocco_per_tsk']
        punteggio = round((pp + pu + ps) / max(t['giorni'], minimo), 3)

        motivi = []
        if t['stato_norm'] == 'bloccato':
            motivi.append('stato %s' % t['stato_raw'])
        aperte = [d for d in t['dipendenze'] if aperto(d)]
        if aperte:
            motivi.append('dipendenze aperte: %s' % ', '.join(aperte))
        if t['bloccanti_esterni']:
            motivi.append('blocked_by esterno: %s' % '; '.join(t['bloccanti_esterni']))
        for d in t['dipendenze']:
            if d not in entita:
                avvisi.append({'tsk_id': t['id'], 'tipo': 'dipendenza_non_trovata', 'dettaglio': d})
        for d in t['dipendenze_testo']:
            avvisi.append({'tsk_id': t['id'], 'tipo': 'dipendenza_non_riconosciuta', 'dettaglio': d})

        giorni_agg = None
        if t['aggiornato']:
            try:
                giorni_agg = (oggi - datetime.date.fromisoformat(t['aggiornato'])).days
            except ValueError:
                pass
        classifica.append({
            'tsk_id': t['id'], 'titolo': t['titolo'], 'epic': t['epic'], 'us': t['us'], 'file': t['file'],
            'stato': t['stato_raw'], 'owner': t['owner'], 'priority': t['priority'], 'layer': t['layer'],
            'giorni': t['giorni'], 'dimensione_fonte': t['dimensione_fonte'],
            'scadenza': scadenza, 'fonte_scadenza': fonte_scadenza, 'giorni_alla_scadenza': giorni_scad,
            'punti': {'priorita': pp, 'urgenza': pu, 'sblocco': ps},
            'sbloccati': sorted(dipendenti[t['id']]),
            'punteggio': punteggio,
            'pronto': not motivi, 'motivo_non_pronto': '; '.join(motivi) or None,
            'aggiornato': t['aggiornato'], 'giorni_da_aggiornamento': giorni_agg,
        })
    classifica.sort(key=lambda v: (-v['punteggio'], ORDINE_PRIORITA.get(v['priority'], 9),
                                   v['scadenza'] or '9999-12-31', v['tsk_id']))
    for i, v in enumerate(classifica, 1):
        v['rank'] = i

    # Capacita' delle persone assegnabili
    persone = {}
    for pid in pc['persone_assegnabili']:
        p = team[pid]
        impegno = p.get('impegno_pct', 100)
        assenze = giorni_assenza(p, orizzonte)
        iniziale = round((len(orizzonte) - assenze) * impegno / 100.0, 2)
        persone[pid] = {
            'id': pid, 'nome': p['nome'], 'impegno_pct': impegno, 'giorni_assenza_orizzonte': assenze,
            'capacita_iniziale': iniziale, 'carico_orizzonte_giorni': round(carico[pid]['giorni'], 2),
            'n_tsk_orizzonte': carico[pid]['n'],
            'carico_oltre_orizzonte_giorni': round(carico[pid]['oltre'], 2), 'n_tsk_oltre_orizzonte': carico[pid]['n_oltre'],
            'capacita_residua_prima': round(iniziale - carico[pid]['giorni'], 2),
            'competenze_layer': sorted({c.lower() for c in (p.get('competenze') or {}).get('layer', [])}),
            'giorni_proposti': 0.0, 'n_proposti': 0,
        }
        if not persone[pid]['competenze_layer']:
            avvisi.append({'tsk_id': None, 'tipo': 'competenze_non_dichiarate',
                           'dettaglio': '%s: nessun filtro per layer, conta solo l\'affinita\' storica' % pid})
        if velocity and velocity.get('misurata'):
            misura = (velocity['per_persona'].get(pid) or velocity['per_persona'].get(p['nome'])
                      or {'punti_sett': 0.0, 'tsk_sett': 0.0})
            persone[pid].update({
                'velocity_punti_sett': misura['punti_sett'], 'velocity_tsk_sett': misura['tsk_sett'],
                'carico_orizzonte_punti': carico[pid]['punti'],
                'settimane_al_ritmo_misurato': (round(carico[pid]['punti'] / misura['punti_sett'], 1)
                                                if misura['punti_sett'] else None),
            })
    residua = {pid: v['capacita_residua_prima'] for pid, v in persone.items()}

    # Proposte
    proposte, non_assegnabili = [], []
    referente = pc.get('referente_bloccanti')
    for v in classifica:
        t = tsk[v['tsk_id']]
        senza_owner = (t['gruppo'] == 'da_designare' or (includi_agente and t['gruppo'] == 'agente')
                       or (t['gruppo'] == 'persona' and t['persona'] in da_riassegnare))
        if not senza_owner:
            if t['gruppo'] == 'sconosciuto':
                avvisi.append({'tsk_id': t['id'], 'tipo': 'owner_non_riconosciuto', 'dettaglio': t['owner']})
            continue
        base = {'file_target': t['file'], 'campo': 'owner', 'valore_attuale': t['owner'],
                'tipo_valore': 'suggested_owner', 'fonte': 'pianificazione', 'tsk_id': t['id'],
                'rank': v['rank'], 'punteggio': v['punteggio']}
        if t['stato_norm'] == 'bloccato':
            if referente:
                proposte.append(dict(base, tipo='owner_bloccante', valore_proposto=team[referente]['nome'],
                                     confidenza='media', motivazione=(
                                         'proposta automatica — verifica prima di applicare: TSK bloccato '
                                         'senza owner, va al referente dei bloccanti (%s)' % v['motivo_non_pronto'])))
            continue
        if not v['pronto']:
            continue
        lr = layer_radice(t['layer'])
        idonei = [pid for pid, p in persone.items() if not p['competenze_layer'] or lr in p['competenze_layer']]
        if not idonei:
            non_assegnabili.append({'tsk_id': t['id'], 'rank': v['rank'], 'giorni': t['giorni'],
                                    'motivo': 'nessuna persona assegnabile con competenze dichiarate sul layer «%s»' % lr})
            continue
        capienti = [pid for pid in idonei if residua[pid] >= t['giorni']]
        if not capienti:
            massima = max(residua[pid] for pid in idonei)
            non_assegnabili.append({'tsk_id': t['id'], 'rank': v['rank'], 'giorni': t['giorni'],
                                    'motivo': 'capacita\' residua insufficiente nell\'orizzonte (massima %.2f gg, '
                                              'servono %.2f gg)' % (massima, t['giorni'])})
            continue

        def chiave(pid):
            aff = affinita_layer.get((pid, lr), 0) + affinita_epic.get((pid, t['epic']), 0)
            return (-aff, -residua[pid], pid)
        scelto = sorted(capienti, key=chiave)[0]
        aff_l = affinita_layer.get((scelto, lr), 0)
        aff_e = affinita_epic.get((scelto, t['epic']), 0)
        prima = residua[scelto]
        residua[scelto] = round(prima - t['giorni'], 2)
        persone[scelto]['giorni_proposti'] += t['giorni']
        persone[scelto]['n_proposti'] += 1
        p = v['punti']
        proposte.append(dict(base, tipo='owner_proposto', valore_proposto=persone[scelto]['nome'],
                             confidenza='media' if aff_l + aff_e else 'bassa',
                             affinita={'layer': aff_l, 'epica': aff_e},
                             capacita_residua_prima=prima, motivazione=(
                                 'proposta automatica — verifica prima di applicare: rank %d, punteggio %.3f = '
                                 '(%s priorita\' + %s urgenza + %s sblocco) / %.2f gg; scadenza %s; affinita\' '
                                 '%d TSK chiusi sul layer «%s» e %d sull\'epica %s; capacita\' residua %.2f gg '
                                 'su %d giorni lavorativi'
                                 % (v['rank'], v['punteggio'], p['priorita'], p['urgenza'], p['sblocco'],
                                    t['giorni'], v['scadenza'] or 'n.d.', aff_l, lr, aff_e, t['epic'], prima,
                                    len(orizzonte)))))

    for pid, p in persone.items():
        p['giorni_proposti'] = round(p['giorni_proposti'], 2)
        p['capacita_residua_dopo'] = residua[pid]
        if p['capacita_residua_prima'] < 0:
            avvisi.append({'tsk_id': None, 'tipo': 'sovraccarico',
                           'dettaglio': '%s: carico nell\'orizzonte %.2f gg oltre una capacita\' di %.2f gg'
                                        % (pid, p['carico_orizzonte_giorni'], p['capacita_iniziale'])})
    avvisi.sort(key=lambda a: (a['tipo'], a['tsk_id'] or '', a['dettaglio']))
    return {
        'classifica': classifica,
        'proposte': proposte,
        'non_assegnabili': non_assegnabili,
        'persone': [persone[pid] for pid in pc['persone_assegnabili']],
        'orizzonte': {'giorni_lavorativi': len(orizzonte),
                      'dal': orizzonte[0].isoformat(), 'al': orizzonte[-1].isoformat()},
        'avvisi': avvisi,
    }


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True, help='Config operatore (JSON) con il blocco pianificazione')
    ap.add_argument('--oggi', required=True, help='Data di riferimento YYYY-MM-DD (niente orologio implicito)')
    ap.add_argument('--ref', default='HEAD', help='Commit da cui leggere il kanban (default HEAD)')
    ap.add_argument('--out', default=None, help='File JSON di output (default: stdout)')
    ap.add_argument('--operatore', default=None, help='ID operatore (default: dal nome della config)')
    a = ap.parse_args(argv)

    if yaml is None:
        print('ERRORE: PyYAML non disponibile — installare con pip install pyyaml', file=sys.stderr)
        return 1
    try:
        oggi = datetime.date.fromisoformat(a.oggi)
    except ValueError:
        print('ERRORE: --oggi non valido: %s (atteso YYYY-MM-DD)' % a.oggi, file=sys.stderr)
        return 2

    cfg = json.load(open(a.config, encoding='utf-8'))
    root = risolvi_factory_root(cfg, a.config)
    if pm_report_abilitato(root) is False:
        print(MESSAGGIO_SPENTA)
        return 0
    velocity = None
    if isinstance(cfg.get('pianificazione'), dict) and cfg['pianificazione'].get('velocity_config'):
        try:
            velocity = risolvi_velocity(root, cfg['pianificazione'], oggi)
        except (OSError, ValueError, KeyError) as exc:
            print('ERRORE: velocity non leggibile da %s: %s' % (cfg['pianificazione']['velocity_config'], exc),
                  file=sys.stderr)
            return 2
    errori = valida_config(cfg)
    if errori:
        print('ERRORE: configurazione di pianificazione non valida in %s:' % a.config, file=sys.stderr)
        for e in errori:
            print('  - %s' % e, file=sys.stderr)
        return 2

    kanban = cfg.get('kanban_root', 'management/kanban')
    ref_sha = git_rev_parse(root, a.ref)
    testi = leggi_kanban(root, ref_sha, kanban)
    if not testi:
        print('ERRORE: nessun file kanban letto da %s al commit %s' % (kanban, ref_sha), file=sys.stderr)
        return 1
    entita = entita_kanban(testi, kanban, cfg['stati'])
    ris = calcola(entita, cfg, oggi, velocity)
    ris['legenda'] = legenda(cfg['pianificazione'], velocity, ris['orizzonte']['giorni_lavorativi'])

    config_sha256 = hashlib.sha256(open(a.config, 'rb').read()).hexdigest()
    operatore = a.operatore or operatore_da_config(a.config)
    out_dati = dict(ris, **{
        'versione_schema': '1.0',
        'operatore': operatore,
        'dry_run': True,
        'note': ('Proposte da confermare con l\'utente prima dell\'applicazione, delegata al tpm '
                 '(single-writer di owner:). Prima di applicare, verificare che owner e status del TSK '
                 'al commit corrente coincidano con quelli di provenienza.ref_sha.'),
        'provenienza': dict({'config_sha256': config_sha256, 'oggi': a.oggi, 'ref_sha': ref_sha}, **(
            {'velocity_config': velocity['config'], 'velocity_config_sha256': velocity['config_sha256'],
             'velocity_misurata': velocity['misurata']} if velocity else {})),
        'conteggio': {
            'classifica': len(ris['classifica']),
            'pronti': sum(1 for v in ris['classifica'] if v['pronto']),
            'proposte': len(ris['proposte']),
            'non_assegnabili': len(ris['non_assegnabili']),
            'avvisi': len(ris['avvisi']),
        },
    })

    print('pianifica: %d TSK in classifica (%d pronti), %d proposte, %d non assegnabili (ref %s, operatore %s, '
          'orizzonte %d gg lavorativi)' % (
              out_dati['conteggio']['classifica'], out_dati['conteggio']['pronti'], len(ris['proposte']),
              len(ris['non_assegnabili']), ref_sha[:8], operatore, ris['orizzonte']['giorni_lavorativi']))
    print('\nPrime 15 della classifica:')
    for v in ris['classifica'][:15]:
        print('  %2d. %-13s %-3s %5.3f  scad %-10s  %s%s' % (
            v['rank'], v['tsk_id'], v['priority'], v['punteggio'], v['scadenza'] or 'n.d.',
            v['owner'] or '(senza owner)', '' if v['pronto'] else '  [non pronto: %s]' % v['motivo_non_pronto']))
    if ris['proposte']:
        print('\nProposte di owner:')
        for p in ris['proposte']:
            print('  #%d %s -> %s (%s, confidenza %s)' % (p['rank'], p['tsk_id'], p['valore_proposto'],
                                                         p['tipo'], p['confidenza']))
    if ris['non_assegnabili']:
        print('\nNon assegnabili:')
        for n in ris['non_assegnabili']:
            print('  #%d %s — %s' % (n['rank'], n['tsk_id'], n['motivo']))
    print('\nCapacita\' nell\'orizzonte %s..%s:' % (ris['orizzonte']['dal'], ris['orizzonte']['al']))
    for p in ris['persone']:
        print('  %-10s capacita\' %5.2f  carico %5.2f (%d TSK)  residua %6.2f -> %6.2f  (+%d proposti)  '
              'oltre orizzonte %5.2f (%d TSK)' % (
                  p['id'], p['capacita_iniziale'], p['carico_orizzonte_giorni'], p['n_tsk_orizzonte'],
                  p['capacita_residua_prima'], p['capacita_residua_dopo'], p['n_proposti'],
                  p['carico_oltre_orizzonte_giorni'], p['n_tsk_oltre_orizzonte']))
        if 'velocity_punti_sett' in p:
            sett = p['settimane_al_ritmo_misurato']
            print('             velocity misurata %4.1f pt/sett (%.1f TSK/sett)  carico %d pt  -> %s' % (
                p['velocity_punti_sett'], p['velocity_tsk_sett'], p['carico_orizzonte_punti'],
                '%.1f settimane al ritmo misurato' % sett if sett is not None else 'nessuna velocity misurata'))
    print('\nLegenda:')
    for riga in ris['legenda']:
        print('  - %s' % riga)

    if a.out:
        scrivi_atomico(a.out, out_dati)
        print('\npianificazione scritta in %s' % a.out)
    else:
        json.dump(out_dati, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
        sys.stdout.write('\n')
    print('RIEPILOGO ' + json.dumps(dict(out_dati['conteggio'], ref_sha=ref_sha, operatore=operatore,
                                         out=a.out), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
