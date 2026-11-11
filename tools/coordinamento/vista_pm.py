#!/usr/bin/env python3
"""Impagina la misura del kanban (misura.json di aggrega.py) nel report a schede (design «Report Attività con tabbed design»):
Vista PM (portafoglio obiettivi, dettaglio nel tempo ad albero, punti di attenzione, persone e carico), Piano operativo (TSK aperti per
sezione, settimana, filtri per obiettivo e persona), Qualità dato (anomalie, voci da verificare con prompt, provenienza).

Solo presentazione: ogni numero, data, avviso e assegnazione arriva dalla misura, verificata da verifica_l0.py. Le date che il kanban
non ha restano vuote («senza date nel piano»). Nessun dato di esempio, nessun giudizio di rischio. Pagina autosufficiente: nessuna
libreria o font scaricati da internet; il JavaScript serve solo a schede, filtri, selezione e copia dei prompt.

    python vista_pm.py --config config-base.json --misura misura.json --out vista-pm.html
                       [--allineamento allineamento.json] [--file-grandi file_grandi.json] [--generato "04/10/2026 15:30"]
"""
import argparse
import datetime
import html
import json
import os
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
import prompt_verifica as pv  # noqa: E402
from calendario import GIORNI, MESI  # noqa: E402
from kanban_ids import nel_selettore, prefisso_di  # noqa: E402
from percorsi import operatore_da_config, risolvi_factory_root  # noqa: E402

ASSETS = os.path.join(QUI, 'assets')


def _risolvi_factory_root(cfg, config_path):
    return risolvi_factory_root(cfg, config_path)


def _operatore(config_path):
    return operatore_da_config(config_path)


D = datetime.date.fromisoformat
# Palette neutra: coppie (pieno, tinta). I nomi sono colori, non progetti; i progetti scelgono il proprio con
# `progetti[].tono` in config, e `vista_pm.palette` aggiunge o ridefinisce colori ({"nome": ["pieno", "tinta"]}).
# blu = in corso / primo progetto; verde = in linea / pronto; ambra = esterno, a rischio; rosso = critico.
TONI = {
    'blu': ('oklch(0.52 0.13 255)', 'oklch(0.94 0.03 255)'),
    'verde': ('oklch(0.52 0.13 165)', 'oklch(0.94 0.03 165)'),
    'ambra': ('oklch(0.55 0.13 60)', 'oklch(0.95 0.035 60)'),
    'ink': ('#1b1d21', '#ecece8'),
    'rosso': ('oklch(0.55 0.15 25)', 'oklch(0.95 0.03 25)'),
}
ORDINE_TONI = ['blu', 'verde', 'ambra']


def configura_palette(cfg):
    """Applica `vista_pm.palette` della config alla palette di default (nessun colore cablato per progetto)."""
    for nome, coppia in ((cfg.get('vista_pm') or {}).get('palette') or {}).items():
        if isinstance(coppia, (list, tuple)) and len(coppia) == 2:
            TONI[str(nome)] = (str(coppia[0]), str(coppia[1]))
LIV_COLORE = {'alto': TONI['rosso'][0], 'medio': TONI['ambra'][0], 'info': '#8a8d93'}
CAT_TESTO = (('chiuso_senza_esito', '%d chiusi senza esito o rinviati (esclusi dal calcolo)'), ('sospeso', '%d sospesi'),
             ('bloccato', '%d bloccati'), ('sconosciuto', '%d con stato non riconosciuto'))
PRE_TESTO = (('in_attesa_prerequisito_aperto', '%d in attesa di un prerequisito aperto'),
             ('prerequisito_da_riconciliare', '%d con un prerequisito annullato o superato (da riconciliare)'),
             ('prerequisito_fuori_perimetro', '%d con un prerequisito fuori perimetro'))
# etichette dei sottoperimetri della config: testo sempre presente (non solo colore); «Infra · rilascio» e' quella in evidenza
SOTTOPERIMETRI = {'sviluppo': 'Sviluppo', 'configurazione': 'Infra · rilascio', 'test': 'Test'}
ORDINE_SOTTOPERIMETRI = ['sviluppo', 'configurazione', 'test']
AVANZAMENTO = {'senza_tsk': '– senza TSK', 'solo_chiusi_senza_esito': '– solo chiusi senza esito', 'non_avviata': '○ non avviata',
               'in_lavorazione': '◔ in lavorazione', 'completata': '● completata'}


def e(x):
    return html.escape(str('' if x is None else x), quote=True)


def gm(iso):
    return '%s/%s' % (iso[8:10], iso[5:7]) if iso else '—'


def data_it(iso):
    return D(iso).strftime('%d/%m/%Y')


def corto(s, n):
    s = str(s or '')
    if len(s) <= n:
        return s
    t = s[:n].rsplit(' ', 1)[0]
    return (t or s[:n]).rstrip(' ,;:—-') + '…'


def cta(etichetta, prompt):
    return ('<details class="cta"><summary>Chiedi una verifica: %s</summary><div class="box"><pre class="prompt">%s</pre>'
            '<button type="button" class="copia">Copia prompt</button></div></details>' % (e(etichetta), e(prompt)))


def voci(blocco, voce, ctx, titoli):
    """[(testo, prompt)] delle voci da verificare di un blocco (epica, sezione, gruppo)."""
    c, p, el = blocco['conteggi'], blocco['prerequisiti'], blocco.get('elenchi', {})
    out = []
    for k, fmt in CAT_TESTO:
        if c[k]:
            out.append((fmt % c[k], pv.per_categoria(ctx, voce, k, el.get(k, []), titoli)))
    for k, fmt in PRE_TESTO:
        n = len({x['tsk'] for x in p[k]})
        if n:
            out.append((fmt % n, pv.per_categoria(ctx, voce, k, p[k], titoli)))
    return out


def scadenza(s):
    return (s['calendario'] or {}).get('pronta_entro') or (s.get('rilascio') or {}).get('data')


def milestone_sotto_obiettivo(cfg, ob_id, progetto_id):
    """Milestone del sotto-obiettivo dichiarate in config (`perimetro[].sotto_obiettivi.milestone`: [{data, etichetta, descrizione}]),
    in ordine di data; le voci senza una data AAAA-MM-GG valida sono ignorate. Lista vuota se il campo manca."""
    for ob in cfg.get('obiettivi', []):
        if ob.get('id') != ob_id:
            continue
        for p in ob.get('perimetro', []):
            if p.get('progetto_id') != progetto_id:
                continue
            out = []
            for m in (p.get('sotto_obiettivi') or {}).get('milestone') or []:
                try:
                    d = datetime.date.fromisoformat(str(m.get('data')))
                except ValueError:
                    continue
                out.append((str(d), str(m.get('etichetta') or ''), str(m.get('descrizione') or '')))
            return sorted(out)
    return []


def ambiente(o):
    """Ambiente in cui avviene il rilascio dell'obiettivo (config `ambiente_rilascio`, default test)."""
    return o.get('ambiente_rilascio') or 'test'


def etichetta_sp(sp):
    """Chip testuale del sottoperimetro di una sezione; vuoto se la config non lo indica."""
    if not sp:
        return ''
    cls = sp if sp in SOTTOPERIMETRI else 'altro'
    return '<span class="sp sp-%s" title="sottoperimetro della config: %s">%s</span>' % (cls, e(sp), e(SOTTOPERIMETRI.get(sp, sp)))


def sp_sezioni(o):
    """{id sezione: sottoperimetro} dell'obiettivo."""
    return {s['id']: s.get('sottoperimetro') for s in o['sezioni']}


def chip_infra(v, sp_di):
    """Chip «Infra · rilascio» per un TSK che appartiene ad almeno una sezione con sottoperimetro configurazione."""
    return etichetta_sp('configurazione') if any(sp_di.get(z) == 'configurazione' for z in v.get('sezioni') or []) else ''


def legenda_sp(sezioni):
    """Voce di legenda delle etichette di sottoperimetro, solo se qualche sezione le usa."""
    if not any(s.get('sottoperimetro') for s in sezioni):
        return ''
    return ('<span class="leg">%s%s%s<span>sottoperimetro della sezione, dalla config: «Infra · rilascio» = TSK di rilascio, ambiente, utenze '
            'e allineamento</span></span>' % (etichetta_sp('configurazione'), etichetta_sp('sviluppo'), etichetta_sp('test')))


def avanzamento_sp(o):
    """Avanzamento per sottoperimetro dell'obiettivo (fatti/base, %) dalla misura; vuoto se la config non classifica le sezioni."""
    sp = o.get('per_sottoperimetro') or {}
    if not sp:
        return ''
    chiavi = [k for k in ORDINE_SOTTOPERIMETRI if k in sp] + sorted(k for k in sp if k not in ORDINE_SOTTOPERIMETRI and k != 'non_indicato')
    chiavi += ['non_indicato'] if 'non_indicato' in sp else []
    voci_sp = []
    for k in chiavi:
        c = sp[k]
        voci_sp.append('<span>%s<span class="mono">%d/%d fatti · %s</span></span>' % (
            etichetta_sp(k) if k != 'non_indicato' else '<span class="sp">Non indicato</span>', c['fatto'], c['base_calcolo'],
            ('%d%%' % c['pct']) if c['pct'] is not None else 'n/d'))
    return '<div class="sps"><span class="mono s up">Per sottoperimetro</span>%s</div>' % ''.join(voci_sp)


def finestra(s, oggi):
    """(inizio, fine) della barra di una sezione: avvio (o oggi) → «pronta entro» (o rilascio). None se il piano non ha date."""
    cal, r = s['calendario'], s.get('rilascio') or {}
    fine = cal['pronta_entro'] or r.get('data')
    if not fine:
        return None
    inizio = cal['avvio'] or oggi
    return (inizio, fine) if inizio <= fine else None


def ondata(s, nomi_ob):
    st, o = s['stato_config'], str(s.get('ondata') if s.get('ondata') is not None else '')
    if st == 'attiva':
        return ('Ondata %s' % o) if o.isdigit() else ('Stream %s' % o) if o else 'Attiva'
    if st == 'congelata' and s.get('fino_a'):
        return 'Congelata fino a %s' % corto(nomi_ob.get(s['fino_a'], s['fino_a']), 30)
    return (st or '—').capitalize()


def chiave_sezione(s):
    st, o = s['stato_config'], str(s.get('ondata') if s.get('ondata') is not None else '')
    return ({'attiva': 0, 'anticipabile': 1, 'congelata': 2}.get(st, 3), (0, int(o)) if o.isdigit() else (1, 0), scadenza(s) or '9999')


def chi_owner(v):
    """(testo, classe) dell'owner di un TSK: persona, agente, da designare (⚠) o non riconosciuto (⚠)."""
    if v['gruppo'] == 'persona':
        return (v['persona_nome'] or v['owner']) + (' (%s)' % v['nota_owner'] if v.get('nota_owner') else ''), 'n'
    if v['gruppo'] == 'agente':
        return 'agente · %s' % v['owner'], 'a'
    if v['gruppo'] == 'sconosciuto':
        return '⚠ owner non riconosciuto: %s' % v['owner'], 'x'
    return '⚠ da designare', 'x'


def toni_progetti(cfg):
    """{progetto_id: nome del tono}: `progetti[].tono` se e' un colore della palette, altrimenti la palette in ordine."""
    return {p['id']: p['tono'] if p.get('tono') in TONI else ORDINE_TONI[i % len(ORDINE_TONI)]
            for i, p in enumerate(cfg.get('progetti', []))}


REGOLA_STATO = ('Stato calcolato dagli avvisi a regole, non una valutazione: ✖ Critico = almeno un avviso alto; '
                '▲ A rischio = solo avvisi medi; ✔ In linea = nessun avviso alto o medio.')


def stato_da_avvisi(avvisi, sezione=None):
    """(simbolo, etichetta, colore, codici) dagli avvisi che riguardano l'obiettivo (sezione None) o una sezione."""
    aa = [x for x in avvisi if x['livello'] in ('alto', 'medio') and (sezione is None or sezione in x.get('sezioni', []))]
    codici = sorted({x['codice'] for x in aa})
    if any(x['livello'] == 'alto' for x in aa):
        return '✖', 'Critico', TONI['rosso'][0], codici
    if aa:
        return '▲', 'A rischio', TONI['ambra'][0], codici
    return '✔', 'In linea', TONI['verde'][0], codici


def etichetta_stato(avvisi, sezione=None):
    sym, lab, col, cod = stato_da_avvisi(avvisi, sezione)
    return '<span class="stl" style="color:%s" title="%s">%s %s</span>' % (col, e(('avvisi: ' + ', '.join(cod)) if cod else 'nessun avviso'), sym, lab)


class Scala:
    """Asse temporale in percentuale fra due date (incluse)."""

    def __init__(self, inizio, fine):
        self.i, self.n = D(inizio), (D(fine) - D(inizio)).days + 1

    def x(self, iso, meta=False):
        return max(0.0, min(100.0, 100.0 * ((D(iso) - self.i).days + (0.5 if meta else 0)) / self.n))

    def w(self, a, b):
        return max(self.x(str(D(b) + datetime.timedelta(1))) - self.x(a), 0.8)


def cognome(nome):
    return str(nome or '').split(' ')[-1]


def progetto_di_tsk(o, cfg):
    """Funzione ID -> progetto_id (None se ignoto o ambiguo). Prima l'epica del TSK, se il TSK e' nel perimetro
    dell'obiettivo; poi il prefisso di namespace dell'ID, dai `prefissi_kanban` dei repository in config. Un kanban
    senza prefissi (ID come TSK-635) si risolve solo per epica: il prefisso non e' un'informazione che ha."""
    rep = {r['id']: r.get('prefissi_kanban', []) for r in cfg.get('repository', [])}
    pref = {}
    for p in o['perimetro']:
        prog = next((x for x in cfg.get('progetti', []) if x['id'] == p['progetto_id']), {})
        for rid in prog.get('repository_ids', []):
            for pr in rep.get(rid, []):
                pref.setdefault(pr, set()).add(p['progetto_id'])
    for ep in o['epiche']:
        if prefisso_di(ep['id']):
            pref.setdefault(prefisso_di(ep['id']), set()).add(ep['progetto_id'])
    per_prefisso = {k: next(iter(v)) for k, v in pref.items() if len(v) == 1}
    prog_ep = {ep['id']: ep['progetto_id'] for ep in o['epiche']}
    per_tsk = {v['tsk']: prog_ep.get(v['epica']) for v in o.get('tsk_aperti', [])}

    def di(ident):
        if per_tsk.get(ident):
            return per_tsk[ident]
        return per_prefisso.get(prefisso_di(ident))
    return di


TITOLO_AVVISO = {
    'collo-di-bottiglia': lambda a, n: '%s è atteso da TSK di %d sezioni' % (a['ids'][0], len(a['sezioni'])),
    'p0-da-designare': lambda a, n: 'TSK P0 senza owner: %s' % ', '.join(a['ids']),
    'scadenza-vicina-non-avviata': lambda a, n: '%s: scadenza vicina, nessun TSK avviato' % n,
    'sezione-da-designare': lambda a, n: '%s: TSK tutti «da designare»' % n,
    'scadenza-passata': lambda a, n: '%s: «pronta entro» passata' % n,
    'avvio-passato': lambda a, n: '%s: avvio passato senza TSK avviati' % n,
    'oltre-il-target': lambda a, n: '%s fuori dalla data obiettivo' % n,
}


def titolo_avviso(a, nomi_sez):
    n = nomi_sez.get((a.get('sezioni') or [''])[0], '')
    f = TITOLO_AVVISO.get(a['codice'])
    if f and (n or a['codice'] in ('collo-di-bottiglia', 'p0-da-designare')):
        return f(a, n)
    if a['codice'] == 'progetto-senza-date' and ':' in a['testo']:
        return a['testo'].split(':')[0] + ': nessuna data nel piano'
    return a['testo'].split(':')[0] if ':' in a['testo'] else a['codice']


def contesto_avviso(a, o, nomi_sez):
    """Fatti collegati all'avviso, presi dalla misura così come sono: owner del TSK e piano della US della sezione."""
    out = []
    ap = {v['tsk']: v for v in o['tsk_aperti']}
    if a['codice'] == 'collo-di-bottiglia' and a['ids'][0] in ap:
        v = ap[a['ids'][0]]
        out.append('owner %s · sezione %s' % (chi_owner(v)[0], ', '.join(nomi_sez.get(z, z) for z in v['sezioni']) or 'nessuna'))
    if a['codice'] in ('scadenza-vicina-non-avviata', 'sezione-da-designare', 'scadenza-passata', 'avvio-passato'):
        s = next((x for x in o['sezioni'] if x['id'] in (a.get('sezioni') or [])), None)
        for pz in (s or {}).get('piano', []):
            campi = ['%s «%s»' % (k, pz[k]) for k in ('window', 'assignee') if pz.get(k) not in (None, '', [])]
            if campi:
                out.append('piano della %s: %s' % (pz['us'], ' · '.join(campi)))
        dd = [x['tsk'] for x in (s or {}).get('tsk', []) if x['non_assegnato']]
        if dd and a['codice'] != 'sezione-da-designare':
            out.append('da designare: %s' % ', '.join(dd))
    return out


# ---------------------------------------------------------------- Vista PM
def portafoglio(m, oggi):
    obs = m['obiettivi']
    date = [oggi] + [o['data_target'] for o in obs] + [o['inizio'] for o in obs if o.get('inizio')]
    ini = D(min(date)) - datetime.timedelta(7)
    ini -= datetime.timedelta(ini.weekday())
    fin = D(max(date)) + datetime.timedelta(21)
    sc = Scala(str(ini), str(fin))
    ticks, t = [], datetime.date(ini.year, ini.month, 1)
    while True:
        t = datetime.date(t.year + (t.month == 12), t.month % 12 + 1, 1)
        if t > fin:
            break
        ticks.append((sc.x(str(t)), MESI[t.month - 1] + (" '%s" % str(t.year)[2:] if t.month == 1 else '')))
    codice = {o['id']: 'O%d' % (i + 1) for i, o in enumerate(obs)}
    blocca = {o['id']: [x['id'] for x in obs if o['id'] in x['attende_obiettivi']] for o in obs}
    righe = []
    for o in obs:
        c = o['conteggi']
        pct = c['pct'] if o['epiche'] and c['base_calcolo'] else None
        ext = o.get('tipo') == 'esterno'
        solid, tint = TONI['ambra' if ext else 'blu']
        alti = [x for x in o['avvisi'] if x['livello'] == 'alto']
        medi = [x for x in o['avvisi'] if x['livello'] == 'medio']
        sym, lab, col, cod = stato_da_avvisi(o['avvisi']) if o['epiche'] else ('–', 'non misurato', '#8a8d93', [])
        primo = (alti or medi or [None])[0]
        nota = titolo_avviso(primo, {s['id']: s['nome'] for s in o['sezioni']}) if primo else (
            'nessun avviso' if o['epiche'] else 'fuori dal kanban: nessuna misura')
        conta = ('%d alti · %d medi' % (len(alti), len(medi))) if (alti or medi) else ''
        deps = '   '.join(x for x in (
            ('← ' + ' '.join(codice[d] for d in o['attende_obiettivi'] if d in codice)) if o['attende_obiettivi'] else '',
            ('→ ' + ' '.join(codice[d] for d in blocca[o['id']])) if blocca[o['id']] else '') if x) or '—'
        barra = ''
        if o.get('inizio'):
            barra = ('<div class="pf-bar" title="%s → %s (inizio: %s) · %s" style="left:%.3f%%;width:%.3f%%;background:%s;border:1px %s %s">'
                     '<div style="width:%s%%;background:%s"></div></div>' % (
                         gm(o['inizio']), gm(o['data_target']), e(o['inizio_da']), ('%d%% completato' % pct) if pct is not None else 'n/d',
                         sc.x(o['inizio']), sc.w(o['inizio'], o['data_target']), tint, 'dashed' if ext else 'solid', solid, pct or 0, solid))
        righe.append(
            '<div class="pf-row" data-ob="%s" data-rel="%s" data-tipo="%s" data-alto="%d" data-gg30="%d">'
            '<div class="pf-c"><span class="code">%s</span></div>'
            '<div class="pf-n"><span class="t">%s</span><span class="mono s">%s · %s · %s</span></div>'
            '<div class="pf-t">%s<div class="oggi" style="left:%.3f%%"></div>%s<div class="ms" title="data obiettivo %s" style="left:%.3f%%"></div></div>'
            '<div class="pf-d"><span class="mono">%s</span><span class="s">%d gg lav.</span></div>'
            '<div class="pf-a"><span class="mono">%s</span><span class="s av" title="%s"><i style="background:%s"></i>'
            '<span><span class="sr" style="color:%s">%s %s%s · </span>%s</span></span></div></div>' % (
                e(o['id']), e(' '.join([o['id']] + o['attende_obiettivi'] + blocca[o['id']])), e(o.get('tipo') or ''), 1 if alti else 0,
                1 if o['giorni_lavorativi_rimasti'] <= 22 else 0, codice[o['id']], e(o['nome']), e(o.get('tipo') or '—'),
                e(cognome(o.get('owner')) if o.get('owner') and ' ' in o['owner'] and o['owner'][0].isupper() else (o.get('owner') or 'owner non indicato')),
                ('%d%%' % pct) if pct is not None else 'n/d',
                ''.join('<div class="tick" style="left:%.3f%%"></div>' % x for x, _ in ticks), sc.x(oggi, True), barra,
                gm(o['data_target']), sc.x(o['data_target'], True), gm(o['data_target']), o['giorni_lavorativi_rimasti'], e(deps),
                e(('avvisi: ' + ', '.join(cod)) if cod else REGOLA_STATO), col, col, sym, e(lab), (' · ' + e(conta)) if conta else '', e(nota)))
    n_crit = sum(1 for o in obs if o['epiche'] and any(x['livello'] == 'alto' for x in o['avvisi']))
    chips = [('tutti', 'Tutti', len(obs)), ('interno', 'Interni', sum(1 for o in obs if o.get('tipo') == 'interno')),
             ('esterno', 'Esterni', sum(1 for o in obs if o.get('tipo') == 'esterno')), ('alto', 'Critici', n_crit),
             ('gg30', 'Entro 30 gg lav.', sum(1 for o in obs if o['giorni_lavorativi_rimasti'] <= 22))]
    return (
        '<section class="card"><div class="card-h"><div><h2>Portafoglio obiettivi</h2><span class="s">%d obiettivi · %d interni · %d esterni · '
        '%d critici</span></div><div class="chips">%s</div></div>'
        '<div class="scroll"><div class="pf"><div class="pf-row pf-head"><span></span><span class="mono s">OBIETTIVO</span>'
        '<div class="pf-t pf-ticks">%s</div><span class="mono s pl">TARGET</span><span class="mono s pl">DIPENDENZE · STATO</span></div>%s</div></div>'
        '<div class="card-f"><span>Clic su una riga per aprirne il dettaglio e filtrare il piano operativo · passa sopra per isolare le dipendenze</span>'
        '<span class="mono">← dipende da · → blocca</span><span class="leg"><i class="ext"></i>obiettivo esterno</span>'
        '<span class="leg" title="%s"><b style="color:%s">✖</b> critico <b style="color:%s">▲</b> a rischio <b style="color:%s">✔</b> in linea: dagli avvisi a regole</span>'
        '</div></section>' % (
            len(obs), chips[1][2], chips[2][2], n_crit,
            ''.join('<button class="chip%s" data-f="%s">%s<span class="mono">%d</span></button>' % (' on' if k == 'tutti' else '', k, l, n)
                    for k, l, n in chips),
            ''.join('<span style="left:%.3f%%">%s</span>' % (x, l) for x, l in ticks), ''.join(righe), e(REGOLA_STATO),
            TONI['rosso'][0], TONI['ambra'][0], TONI['verde'][0]))


def schede_obiettivo(o, obs, codice, cfg):
    c = o['conteggi']
    pct = ('%d%%' % c['pct']) if o['epiche'] and c['base_calcolo'] else 'n/d'
    da_des = len(o['persone']['senza_owner']) if o.get('persone') else 0
    chips = ''.join(
        '<button class="dep" data-sel="%s"><span class="mono s">%s</span><span>%s · %s</span><span class="mono s">%s ›</span></button>' % (
            e(x['id']), d, codice[x['id']], e(x['nome']), gm(x['data_target']))
        for d, lst in (('Dipende da', [x for x in obs if x['id'] in o['attende_obiettivi']]),
                       ('Blocca', [x for x in obs if o['id'] in x['attende_obiettivi']])) for x in lst)
    tsk_txt = ('%d TSK · %d aperti · %d da designare' % (o['copertura']['tsk_perimetro'], len(o['tsk_aperti']), da_des)) if o['epiche'] \
        else 'nessun TSK nel perimetro'
    toni = toni_progetti(cfg)
    sub = []
    for p in o['perimetro']:
        cc = p.get('conteggi') or {}
        solid = TONI[toni.get(p['progetto_id'], 'blu')][0]
        datate = any(s['progetto_id'] == p['progetto_id'] and scadenza(s) for s in o['sezioni'])
        sub.append('<div class="sub"><div class="row-sb"><span class="t">%s</span><span class="big" style="color:%s">%s</span></div>'
                   '<div class="mini"><div style="width:%s%%;background:%s"></div></div><span class="mono s">%s · %d in corso%s</span></div>' % (
                       e(p['nome']), solid, ('%d%%' % cc['pct']) if cc.get('base_calcolo') else 'n/d', cc.get('pct') or 0, solid,
                       e(' · '.join('%s %d/%d fatti' % (ep['id'], ep['conteggi']['fatto'], ep['conteggi']['base_calcolo'])
                                    for ep in o['epiche'] if ep['progetto_id'] == p['progetto_id'])),
                       cc.get('in_corso', 0), '' if datate else ' · nessuna data'))
    sym, lab, col, cod = stato_da_avvisi(o['avvisi'])
    return (
        '<section class="duo"><div class="card pad"><div class="row-sb"><div class="col6"><span class="tipo"><span class="code inv">%s</span>'
        '<span class="mono up" style="color:%s">Obiettivo %s</span>%s</span><span class="h20">%s</span></div>'
        '<div class="gg"><div class="big28">%d</div><div class="s">gg lav. al %s</div></div></div><div class="s">%s</div>'
        '<div class="mono s meta">owner %s · avanzamento %s · %s</div>%s%s</div>'
        '<div class="card pad"><span class="mono s up">Sotto-obiettivi</span>%s</div></section>' % (
            codice[o['id']], TONI['ambra'][0] if o.get('tipo') == 'esterno' else '#5d6168', e(o.get('tipo') or ''),
            ('<span class="stl" style="color:%s" title="%s">%s %s</span>' % (col, e(('avvisi: ' + ', '.join(cod)) if cod else REGOLA_STATO), sym, e(lab)))
            if o['epiche'] else '', e(o['nome']), o['giorni_lavorativi_rimasti'], gm(o['data_target']), e(o.get('descrizione') or ''),
            e(o.get('owner') or 'non indicato'), pct, tsk_txt, avanzamento_sp(o), ('<div class="deps">%s</div>' % chips) if chips else '',
            ('<div class="subs">%s</div>' % ''.join(sub)) if sub else
            '<div class="vuoto">Nessun sotto-obiettivo nel perimetro misurato: l\'obiettivo è tracciato solo per i suoi effetti sugli altri.</div>'))


def blocco_bloccanti(o, n_vista=8):
    """Bloccanti prioritari (dalla misura): ordinati per la data in cui servono alle sezioni che li attendono."""
    bb = o.get('bloccanti') or []
    if not bb:
        return ''
    nomi_sez = {s['id']: s['nome'] for s in o['sezioni']}
    sp_di = sp_sezioni(o)
    righe = []
    for i, b in enumerate(bb):
        chi, cls = chi_owner(b)
        if b['serve_entro']:
            quando = '%s %s' % (GIORNI[D(b['serve_entro']).weekday()], gm(b['serve_entro']))
            nota = ('già necessario · ' if b['gia_necessario'] else 'tra %d gg lav. · ' % b['giorni_a_serve_entro']) + (
                'avvio della prima sezione in attesa' if b['serve_entro_da'] == 'avvio' else '«pronta entro» della prima sezione in attesa')
        else:
            quando, nota = '—', 'le sezioni in attesa non hanno date'
        attese = ', '.join(nomi_sez.get(z, z) for z in b['sezioni_attese']) or 'TSK fuori dalle sezioni'
        segnali = [x for x, c in (('⚠ da designare', b['non_assegnato']), ('non avviato', b['categoria'] == 'da_fare'),
                                  ('serve prima della sua sezione', b['serve_prima_della_sua_sezione']),
                                  ('attende a sua volta ' + ', '.join(b['attende']), bool(b['attende']))) if c]
        righe.append(
            '<div class="bl%s"%s><span class="mono s">%02d</span><span class="pr %s">%s</span><div class="bl-t"><span class="mono s ids">%s</span>'
            '<span>%s%s</span><span class="ow %s">%s · %s</span></div><div class="bl-a"><span class="t">%s%d %s</span><span class="s ids">%s</span>'
            '<span class="mono s ids">%s</span></div><div class="bl-d"><span class="mono%s">%s</span><span class="s">%s</span></div>'
            '<div class="bl-f s">%s</div></div>' % (
                ' alt' if b['gia_necessario'] else '', ' hidden data-extra="1"' if i >= n_vista else '', i + 1,
                e((b['priorita'] or 'nd').lower()), e(b['priorita'] or '—'), e(b['tsk']), e(b['titolo']), chip_infra(b, sp_di), cls, e(chi), e(b['stato']),
                ('%d %s · ' % (len(b['sezioni_attese']), 'sezione' if len(b['sezioni_attese']) == 1 else 'sezioni')) if b['sezioni_attese'] else '',
                len(b['attesi_da']),
                'TSK in attesa' if len(b['attesi_da']) == 1 else 'TSK in attesa', e(attese), e(', '.join(b['attesi_da'])),
                ' rosso' if b['gia_necessario'] else '', e(quando), e(nota), e(' · '.join(segnali))))
    altri = len(bb) - n_vista
    return ('<section class="card"><div class="card-h"><div><h2>Bloccanti prioritari</h2><span class="s">TSK aperti attesi da altri TSK aperti, '
            'in ordine di quando servono: avvio della prima sezione che li attende (o la sua «pronta entro» se l\'avvio non è indicato), '
            'poi numero di sezioni sbloccate e priorità.</span></div><span class="mono s">%d bloccanti</span></div>'
            '<div class="bls"><div class="bl head"><span></span><span class="mono s">PRIO</span><span class="mono s">TSK · OWNER</span>'
            '<span class="mono s">SBLOCCA</span><span class="mono s">SERVE ENTRO</span><span class="mono s">SEGNALI</span></div>%s</div>%s</section>' % (
                len(bb), ''.join(righe),
                ('<div class="card-f"><button class="tg altri-bl">Mostra gli altri %d</button></div>' % altri) if altri > 0 else ''))


def asse_dettaglio(o, obs, oggi):
    """Asse del dettaglio: da una settimana prima di oggi alla data più lontana fra target, piano e obiettivi collegati (lunedì → +8 giorni).
    Le barre che iniziano prima vengono tagliate a sinistra; le date esatte sono nel tooltip."""
    prereq = [x for x in obs if x['id'] in o['attende_obiettivi']]
    dip = [(x, s) for x in obs for s in x['sezioni'] if s.get('fino_a') == o['id']]
    date = [str(D(oggi) - datetime.timedelta(7)), o['data_target']] + [x['data_target'] for x in prereq] + [x['data_target'] for x, _ in dip]
    for s in o['sezioni'] + [s for _, s in dip]:
        f = finestra(s, oggi)
        date += list(f) if f else []
        if (s.get('rilascio') or {}).get('data'):
            date.append(s['rilascio']['data'])
    ini = D(min(date))
    ini -= datetime.timedelta(ini.weekday())
    return str(ini), str(D(max(date)) + datetime.timedelta(8)), prereq, dip


def legami_sezioni(o):
    """{(sezione che attende, sezione prerequisito): [TSK prerequisiti]} dai depends_on dei TSK aperti (prerequisiti non completati)."""
    sez_di = {}
    for s in o['sezioni']:
        for v in s['tsk']:
            sez_di.setdefault(v['tsk'], []).append(s['id'])
    out = {}
    for s in o['sezioni']:
        for v in s['tsk']:
            for d in v['attende']:
                for z in sez_di.get(d, []):
                    if z != s['id']:
                        out.setdefault((s['id'], z), set()).add(d)
    return {k: sorted(v) for k, v in out.items()}


def albero(o, obs, codice, cfg, oggi, nomi_ob):
    """1a · Gantt ad albero: obiettivo → sotto-obiettivo (progetto) → sezione, con finestre e rilasci; TSK apribili con un clic sulla sezione;
    US fuori sezione con TSK aperti; obiettivi collegati (← prerequisiti, → dipendenti)."""
    toni = toni_progetti(cfg)
    ini, fin, prereq, dip = asse_dettaglio(o, obs, oggi)
    sc = Scala(ini, fin)
    ticks, t = [], D(ini)
    while t <= D(fin):
        ticks.append((sc.x(str(t)), t.strftime('%d/%m')))
        t += datetime.timedelta(7)
    nomi_sez = {s['id']: s['nome'] for s in o['sezioni']}
    legami = legami_sezioni(o)
    pref = progetto_di_tsk(o, cfg)
    nomi_prog = {p['progetto_id']: p['nome'] for p in o['perimetro']}
    righe = []

    def riga(k, lvl, label, meta, deps, tono='blu', bar=None, fill=0, ms=None, dashed=False, undated='', rel='', warn=False, cls='',
             badge='', of='', tip=''):
        solid, tint = TONI[tono]
        b = ''
        if bar:
            b = ('<div class="gb" title="%s" style="left:%.3f%%;width:%.3f%%;height:%dpx;background:%s;border:1px %s %s">'
                 '<div style="width:%s%%;background:%s"></div></div>' % (
                     e(tip or '%s → %s' % (gm(bar[0]), gm(bar[1]))), sc.x(bar[0]), sc.w(bar[0], bar[1]),
                     12 if lvl >= 3 else 14 if lvl == 2 else 18, tint, 'dashed' if dashed else 'solid', solid, fill, solid))
        if undated:
            b += '<span class="und">%s</span>' % e(undated)
        for m in (ms if isinstance(ms, list) else [ms] if ms else []):
            col = solid if lvl == 0 else '#1b1d21'
            b += ('<div class="gms" style="left:%.3f%%"%s><i style="background:%s;box-shadow:0 0 0 1px %s"></i><span style="color:%s">%s</span></div>' % (
                sc.x(m[0], True), (' title="%s"' % e(m[2])) if len(m) > 2 and m[2] else '', col, col, col, e(m[1])))
        bordo = '3px solid %s' % solid if lvl == 0 else '2px solid %s' % solid if lvl == 1 else '2px solid transparent'
        righe.append(
            '<div class="ga-row l%d%s" data-k="%s" data-rel="%s"%s><div class="ga-n" style="padding-left:%dpx;border-left:%s"><span class="t">%s%s</span>'
            '<span class="mono s">%s</span></div><div class="ga-t" style="background-size:%.4f%% 100%%"><div class="oggi" style="left:%.3f%%"></div>'
            '<div class="tgt" style="left:%.3f%%"></div>%s</div><div class="ga-d%s">%s</div></div>' % (
                min(lvl, 3), cls, e(k), e(rel), (' data-of="%s"' % e(of)) if of else '', 12 + 18 * min(lvl, 3), bordo, e(label), badge, e(meta),
                700.0 / sc.n, sc.x(oggi, True), sc.x(o['data_target'], True), b, ' warn' if warn else '', e(deps)))

    def righe_tsk(vv, of, bar, tono, extra='', badge=''):
        for v in vv:
            if v['categoria'] == 'chiuso_senza_esito':
                # restano visibili come riga spenta: fuori dal calcolo, ma la verifica della vista li cerca nella pagina
                riga('t-' + v['tsk'], 3, '%s %s' % (v['tsk'], corto(v['titolo'], 46)), '%s · fuori dal calcolo (%s)' % (v['priorita'] or '—', v['stato']),
                     '', tono=tono, bar=bar, fill=0, undated='' if bar else 'senza date', rel=of, cls=' tsk%s chiuso' % extra, of=of, badge=badge)
                continue
            chi = chi_owner(v)[0] if v['categoria'] != 'fatto' else (v.get('persona_nome') or v.get('owner') or '—')
            stato = {'fatto': 'fatto', 'in_corso': 'in corso'}.get(v['categoria'], v['stato'])
            riga('t-' + v['tsk'], 3, '%s %s' % (v['tsk'], corto(v['titolo'], 46)), '%s · %s · %s' % (v['priorita'] or '—', chi, stato),
                 ('⧗ attende ' + ', '.join(v['attende'])) if v['attende'] else '', tono=tono, bar=bar,
                 fill=100 if v['categoria'] == 'fatto' else 50 if v['categoria'] == 'in_corso' else 0, undated='' if bar else 'senza date',
                 rel=of, warn=v['non_assegnato'], cls=' tsk%s%s' % (extra, ' alert' if v['non_assegnato'] else ''), of=of, badge=badge)

    c = o['conteggi']
    progetti = [p['nome'] for p in o['perimetro']]
    riga(o['id'], 0, o['nome'], 'Obiettivo %s · %d gg lavorativi' % (o.get('tipo') or '', o['giorni_lavorativi_rimasti']),
         ('Dipende da %d sotto-obiettivi: %s' % (len(progetti), ' + '.join(progetti))) if progetti else 'Nessun sotto-obiettivo nel kanban',
         tono='ambra' if o.get('tipo') == 'esterno' else 'ink', bar=(o['inizio'], o['data_target']) if o.get('inizio') else None,
         fill=(c['pct'] or 0) if o['epiche'] else 0, ms=(o['data_target'], 'target ' + gm(o['data_target'])), dashed=o.get('tipo') == 'esterno',
         rel=' '.join(['p-%s' % p['progetto_id'] for p in o['perimetro']] + ['o-' + x['id'] for x in prereq]),
         tip='%s → %s (inizio: %s)' % (gm(o.get('inizio')), gm(o['data_target']), o.get('inizio_da') or '—'))
    perimetro = list(o['perimetro'])
    if any(s['progetto_id'] is None for s in o['sezioni']):
        perimetro.append({'progetto_id': None, 'nome': 'Sezioni non attribuite a un progetto del perimetro', 'epiche': [], 'conteggi': {}})
    for p in perimetro:
        tono = toni.get(p['progetto_id'], 'blu')
        cc = p.get('conteggi') or {}
        mie = [v for v in o['tsk_aperti'] if nel_selettore(v['epica'], v['us'], p)]
        altri = [q for q in o['perimetro'] if q['progetto_id'] not in (None, p['progetto_id'])]
        legate = sorted({'%s → %s' % (v['tsk'], d) for v in mie for d in v['attende']
                         if pref(d) not in (None, p['progetto_id'])} |
                        {'%s → %s' % (v['tsk'], d) for v in o['tsk_aperti'] if not nel_selettore(v['epica'], v['us'], p) for d in v['attende']
                         if pref(d) == p['progetto_id']})
        deps = ('Dipendenze registrate con %s: %s' % (' + '.join(q['nome'] for q in altri), ', '.join(legate))) if legate else (
            'Nessuna dipendenza registrata con %s' % ' + '.join(q['nome'] for q in altri) if altri else
            '%d TSK aperti · %d da designare' % (len(mie), sum(1 for v in mie if v['non_assegnato'])))
        mil = milestone_sotto_obiettivo(cfg, o['id'], p['progetto_id']) if p['progetto_id'] else []
        bar_p = (o['inizio'], o['data_target']) if o.get('inizio') and p['progetto_id'] else None
        tip_p = 'finestra dell\'obiettivo: il sotto-obiettivo non ha date proprie'
        if mil:
            # con milestone in config la barra va dalla prima data delle sue sezioni (o dall'inizio dell'obiettivo) all'ultima milestone o scadenza
            mie_sez = [s for s in o['sezioni'] if s['progetto_id'] == p['progetto_id']]
            inizi = [s['calendario']['avvio'] for s in mie_sez if (s['calendario'] or {}).get('avvio')]
            fini = [x for x in [scadenza(s) for s in mie_sez] + [m[0] for m in mil] if x]
            a = min(inizi) if inizi else o.get('inizio') or min(fini)
            bar_p = (min(a, max(fini)), max(fini))
            tip_p = 'dalle date delle sezioni e delle milestone del sotto-obiettivo: %s' % '; '.join(
                '%s %s%s' % (m[1], gm(m[0]), (' — ' + m[2]) if m[2] else '') for m in mil)
        riga('p-%s' % p['progetto_id'], 1, p['nome'],
             'Sotto-obiettivo · %s%s%s' % (' + '.join(p['epiche']) + ((' · %d US' % len(p['us'])) if p.get('us') is not None else ''), (' · %d/%d' % (cc['fatto'], cc['base_calcolo'])) if cc else '',
                                           (' · milestone ' + ', '.join('%s %s' % (m[1], gm(m[0])) for m in mil)) if mil else ''),
             deps, tono=tono, bar=bar_p, fill=cc.get('pct') or 0,
             ms=[(m[0], '%s %s' % (m[1], gm(m[0])), m[2]) for m in mil] or None,
             dashed=not any(s['progetto_id'] == p['progetto_id'] and scadenza(s) for s in o['sezioni']), rel=o['id'], tip=tip_p)
        for s in sorted((s for s in o['sezioni'] if s['progetto_id'] == p['progetto_id']), key=chiave_sezione):
            f = finestra(s, oggi)
            r = s.get('rilascio') or {}
            cs = s['conteggi']
            persone = sorted({cognome(v['persona_nome']) for v in s['tsk'] if v.get('persona_nome') and v['categoria'] not in ('fatto', 'chiuso_senza_esito')})
            dd = sum(1 for v in s['tsk'] if v['non_assegnato'])
            attese = {z: ids for (a_, z), ids in legami.items() if a_ == s['id']}
            sblocca = {a_: ids for (a_, z), ids in legami.items() if z == s['id']}
            parti = []
            for x, k in (('avvio passato senza TSK avviati', 'avvio_passato_non_avviata'), ('«pronta entro» passata', 'pronta_scaduta_non_completata')):
                if s['calendario'][k]:
                    parti.append(x)
            if r.get('data_passata') and not r.get('fatto'):
                parti.append('rilascio passato, non completato')
            if s.get('fino_a'):
                xo = next((x for x in obs if x['id'] == s['fino_a']), None)
                parti.append('Attende l\'obiettivo %s %s (%s)%s' % (codice.get(s['fino_a'], ''), nomi_ob.get(s['fino_a'], s['fino_a']),
                                                                   gm(xo['data_target']) if xo else '—',
                                                                   ': oltre il target' if xo and xo['data_target'] > o['data_target'] else ''))
            if attese:
                parti.append('Attende ' + ' · '.join('%s (%s)' % (', '.join(ids), nomi_sez.get(z, z)) for z, ids in sorted(attese.items())))
            if sblocca:
                tutti = sorted({i for ids in sblocca.values() for i in ids})
                parti.append('Sblocca %s (%s)' % (', '.join(nomi_sez.get(z, z) for z in sorted(sblocca)), ', '.join(tutti)))
            sym, lab, col, cod = stato_da_avvisi(o['avvisi'], s['id'])
            n_tsk = sum(1 for v in s['tsk'] if v['categoria'] != 'chiuso_senza_esito')
            riga('s-' + s['id'], 2, s['nome'],
                 '%s · %s · %d/%d%s%s' % (ondata(s, nomi_ob), ', '.join(persone) or 'nessuno', cs['fatto'], cs['base_calcolo'],
                                          (' · %d senza owner' % dd) if dd else '', (' · ▸ %d TSK' % n_tsk) if n_tsk else ''),
                 ' · '.join(parti) or 'Nessuna dipendenza aperta', tono='ambra' if s['stato_config'] == 'congelata' else tono, bar=f, fill=cs['pct'] or 0,
                 ms=(r['data'], 'R ' + gm(r['data'])) if r.get('data') else None, dashed=not s['calendario']['avvio'],
                 undated='' if f else ('dopo il %s · senza date nel piano' % gm(next((x['data_target'] for x in obs if x['id'] == s.get('fino_a')), None))
                                       if s.get('fino_a') else 'senza date nel piano'),
                 rel=' '.join(['s-' + z for z in sorted(set(attese) | set(sblocca))] + ['p-%s' % p['progetto_id']] +
                              (['o-' + s['fino_a']] if s.get('fino_a') else [])),
                 warn=bool(attese or len(parti) > (1 if sblocca else 0) or s.get('fino_a')), cls=' sez' + (' apre' if n_tsk else ''),
                 badge='%s <span class="stg" style="color:%s" title="%s · %s">%s</span>' % (
                     etichetta_sp(s.get('sottoperimetro')), col, e(lab), e(('avvisi: ' + ', '.join(cod)) if cod else 'nessun avviso'), sym),
                 tip='%s → %s%s · %s' % (gm(f[0]), gm(f[1]), ' (avvio non indicato: da oggi)' if not s['calendario']['avvio'] else '',
                                         AVANZAMENTO.get(s['avanzamento'], '')) if f else '')
            righe_tsk(s['tsk'], 's-' + s['id'], f, tono, badge=etichetta_sp('configurazione') if s.get('sottoperimetro') == 'configurazione' else '')
        chiuse = []
        ha_sez = any(s['progetto_id'] == p['progetto_id'] for s in o['sezioni'])
        fz = ' fuori' if ha_sez else ''
        for g in [g for g in o['non_legati_a_sezione'] if nel_selettore(g['epica'], None if g['us'] == '(senza US)' else g['us'], p)]:
            vv = [v for v in o['tsk_aperti'] if v['us'] == g['us'] and not v['sezioni'] and v['epica'] == g['epica']]
            if not vv:
                chiuse.append(g['us'])
                continue
            cg, pre = g['conteggi'], g['prerequisiti']
            na = g.get('non_assegnati') or []
            deps = [('Prerequisito da riconciliare: ' + ', '.join('%s (%s)' % (x['prerequisito'], x.get('stato') or '') for x in pre['prerequisito_da_riconciliare']))
                    if pre['prerequisito_da_riconciliare'] else '',
                    ('Attende ' + ', '.join(sorted({x['prerequisito'] for x in pre['in_attesa_prerequisito_aperto']})))
                    if pre['in_attesa_prerequisito_aperto'] else '',
                    ('Prerequisito fuori perimetro: ' + ', '.join(x['prerequisito'] for x in pre['prerequisito_fuori_perimetro']))
                    if pre['prerequisito_fuori_perimetro'] else '', ('⚠ %d da designare' % len(na)) if na else '']
            riga('u-' + g['us'], 2, '%s · %s' % (g['us'], corto(g['titolo_us'], 48)),
                 'fuori sezione · %d/%d · %d aperti%s · ▸ %d TSK' % (cg['fatto'], cg['base_calcolo'], len(vv), ' · ricetta' if g['us_ricetta'] else '', len(vv)),
                 ' · '.join(x for x in deps if x) or 'Nessuna dipendenza aperta', tono=tono,
                 undated='non pianificata · %s' % (('%d%%' % cg['pct']) if cg['pct'] is not None else 'n/d'),
                 rel='p-%s' % p['progetto_id'], warn=any(deps), cls=fz + ' apre')
            righe_tsk(vv, 'u-' + g['us'], None, tono, fz)
        if chiuse:
            riga('c-%s' % p['progetto_id'], 2, 'Altre %d US fuori sezione' % len(chiuse), 'senza TSK aperti', ', '.join(chiuse), tono=tono,
                 undated='nessun TSK aperto', rel='p-%s' % p['progetto_id'], cls=fz)
    for x in prereq:
        cx = x['conteggi']
        fermi = [s['nome'] for s in o['sezioni'] if s.get('fino_a') == x['id']]
        tardi = x['data_target'] > o['data_target']
        riga('o-' + x['id'], 0, '← %s · %s' % (codice[x['id']], x['nome']),
             'Prerequisito · obiettivo %s · %s · %s' % (x.get('tipo') or '', x.get('owner') or 'owner non indicato',
                                                       ('%d%%' % cx['pct']) if x['epiche'] and cx['base_calcolo'] else 'n/d'),
             ('Blocca: %s' % ', '.join(fermi) if fermi else 'Prerequisito dichiarato') +
             ('; target %s dopo il target di questo obiettivo (%s)' % (gm(x['data_target']), gm(o['data_target'])) if tardi else ''),
             tono='ambra' if x.get('tipo') == 'esterno' else 'ink', bar=(x['inizio'], x['data_target']) if x.get('inizio') else None,
             fill=(cx['pct'] or 0) if x['epiche'] else 0, ms=(x['data_target'], gm(x['data_target'])), dashed=True,
             rel=' '.join([o['id']] + ['s-' + s['id'] for s in o['sezioni'] if s.get('fino_a') == x['id']]), warn=tardi,
             tip='%s → %s (inizio: %s)' % (gm(x.get('inizio')), gm(x['data_target']), x.get('inizio_da') or '—'))
    for x in [x for x in obs if any(s.get('fino_a') == o['id'] for s in x['sezioni'])]:
        cx = x['conteggi']
        ss = [s for s in x['sezioni'] if s.get('fino_a') == o['id']]
        riga('o-' + x['id'], 0, '→ %s · %s' % (codice[x['id']], x['nome']),
             'Dipendente · obiettivo %s · %s' % (x.get('tipo') or '', ('%d%%' % cx['pct']) if x['epiche'] and cx['base_calcolo'] else 'n/d'),
             'Attende questo obiettivo con la sezione %s' % ', '.join(s['nome'] for s in ss),
             tono='ambra' if x.get('tipo') == 'esterno' else 'ink', bar=(x['inizio'], x['data_target']) if x.get('inizio') else None,
             fill=(cx['pct'] or 0) if x['epiche'] else 0, ms=(x['data_target'], gm(x['data_target'])), dashed=True,
             rel=' '.join([o['id']] + ['d-' + s['id'] for s in ss]), warn=x['data_target'] < o['data_target'])
        for s in ss:
            riga('d-' + s['id'], 2, s['nome'], '%s · %s' % (ondata(s, nomi_ob), ', '.join(u['id'] for u in s['us'])),
                 'Riparte dopo il %s' % gm(o['data_target']), tono='ambra', undated='dopo il %s · senza date nel piano' % gm(o['data_target']),
                 rel='o-' + x['id'], warn=True, badge=etichetta_sp(s.get('sottoperimetro')))
    return ('<div class="var v-a"><div class="scroll"><div class="ga no-fuori"><div class="ga-row head"><span class="mono s">OBIETTIVO / SOTTO-OBIETTIVO / SEZIONE</span>'
            '<div class="ga-t ticks">%s</div><span class="mono s pl">DIPENDENZE</span></div>%s</div></div>'
            '<div class="card-f"><span class="leg"><i class="fill"></i>fatto</span><span class="leg"><i class="win"></i>finestra pianificata</span>'
            '<span class="leg"><i class="dash"></i>finestra senza avvio nel kanban (parte da oggi) o del solo obiettivo</span>'
            '<span class="leg"><i class="dia"></i>rilascio in %s / target</span><span class="leg"><i class="now"></i>oggi</span>%s'
            '<span>Clic su una sezione o US per aprirne i TSK (⚠ da designare · ⧗ attende) · passa sopra una riga per isolarne le dipendenze</span></div></div>' % (
                ''.join('<span style="left:%.3f%%">%s</span>' % (x, l) for x, l in ticks), ''.join(righe), e(ambiente(o)), legenda_sp(o['sezioni'])))


def rete(o, obs, codice, cfg, oggi, nomi_ob):
    """1b · Rete su asse temporale: sezioni come nodi sulla loro finestra, frecce fra sezioni i cui TSK si attendono (depends_on),
    obiettivi prerequisiti come nodi fino al loro target. Niente date dedotte: ciò che non ha date è elencato sotto."""
    toni = toni_progetti(cfg)
    ini, fin, prereq, _ = asse_dettaglio(o, obs, oggi)
    GUT, PX, MINW, H = 200, 34, 156, 42
    giorni = (D(fin) - D(ini)).days + 1
    X = lambda iso: GUT + max(0, (D(iso) - D(ini)).days) * PX
    LY = lambda i: 52 + i * 56
    nodi, gruppi, senza, lane = {}, [], [], 0
    ap_n = {}

    def piazza(lista, inizio_lane):
        corsie = []
        for k, a, b, extra in lista:
            x = X(a)
            w = max(X(b) + PX - x, MINW)
            c = next((i for i, r in enumerate(corsie) if r + 12 <= x), None)
            if c is None:
                corsie.append(x + w)
                c = len(corsie) - 1
            else:
                corsie[c] = x + w
            nodi[k] = dict(extra, x=x, w=w, y=LY(inizio_lane + c))
        return max(1, len(corsie))

    for p in o['perimetro']:
        tono = toni.get(p['progetto_id'], 'blu')
        lista = []
        for s in sorted((s for s in o['sezioni'] if s['progetto_id'] == p['progetto_id']), key=chiave_sezione):
            f = finestra(s, oggi)
            cs, r = s['conteggi'], s.get('rilascio') or {}
            persone = sorted({cognome(v['persona_nome']) for v in s['tsk'] if v.get('persona_nome') and v['categoria'] not in ('fatto', 'chiuso_senza_esito')})
            dd = sum(1 for v in s['tsk'] if v['non_assegnato'])
            meta = '%s · %d/%d%s%s' % (', '.join(persone) or 'nessuno', cs['fatto'], cs['base_calcolo'], (' · %d da designare' % dd) if dd else '',
                                       (' · R ' + gm(r['data'])) if r.get('data') else '')
            if f:
                lista.append(('s-' + s['id'], f[0], f[1], {'label': s['nome'], 'sp': s.get('sottoperimetro'), 'meta': meta, 'tono': tono,
                                                           'dashed': not s['calendario']['avvio'], 'fill': cs['pct'] or 0, 'title': '%s · %s → %s' % (s['nome'], gm(f[0]), gm(f[1]))}))
            elif s.get('fino_a') and any(x['id'] == s['fino_a'] for x in obs):
                dopo = str(D(next(x['data_target'] for x in obs if x['id'] == s['fino_a'])) + datetime.timedelta(1))
                lista.append(('s-' + s['id'], dopo, dopo, {'label': s['nome'], 'sp': s.get('sottoperimetro'),
                                                           'meta': 'dopo il %s · senza date nel piano' % gm(dopo), 'tono': 'ambra',
                                                           'dashed': True, 'fill': 0, 'title': '%s · riparte dopo il target di %s' % (s['nome'], codice[s['fino_a']])}))
            else:
                senza.append('%s (%s)' % (s['nome'], ondata(s, nomi_ob)))
        cc = p.get('conteggi') or {}
        if not lista:
            senza.append('%s (%d TSK aperti, nessun sotto-obiettivo datato)' % (p['nome'], sum(1 for v in o['tsk_aperti'] if nel_selettore(v['epica'], v['us'], p))))
            continue
        n = piazza(lista, lane)
        gruppi.append({'y': LY(lane), 'h': LY(lane + n - 1) - LY(lane) + 44, 'label': p['nome'],
                       'meta': 'sotto-obiettivo · %s' % (('%d%%' % cc['pct']) if cc.get('base_calcolo') else 'n/d'), 'solid': TONI[tono][0]})
        lane += n
    for x in prereq:
        cx = x['conteggi']
        a = max(x.get('inizio') or x['data_target'], ini)
        n = piazza([('o-' + x['id'], a, x['data_target'], {
            'label': x['nome'], 'meta': '%s · target %s · %s' % (x.get('owner') or 'obiettivo', gm(x['data_target']),
                                                                ('%d%%' % cx['pct']) if x['epiche'] and cx['base_calcolo'] else 'n/d'),
            'tono': 'ambra' if x.get('tipo') == 'esterno' else 'ink', 'dashed': False, 'fill': (cx['pct'] or 0) if x['epiche'] else 0,
            'title': '%s · %s → %s' % (x['nome'], gm(x.get('inizio')), gm(x['data_target']))})], lane)
        gruppi.append({'y': LY(lane), 'h': 44, 'label': '%s · %s' % (codice[x['id']], corto(x['nome'], 22)),
                       'meta': 'obiettivo %s' % (x.get('tipo') or ''), 'solid': TONI['ambra'][0] if x.get('tipo') == 'esterno' else '#1b1d21'})
        lane += n
    if not nodi:
        return ''
    caldi = {a['ids'][0] for a in o['avvisi'] if a['codice'] == 'collo-di-bottiglia'}
    archi = [('s-' + z, 's-' + a_, any(i in caldi for i in ids), ', '.join(ids)) for (a_, z), ids in sorted(legami_sezioni(o).items())]
    archi += [('o-' + s['fino_a'], 's-' + s['id'], False, 'congelata fino al target') for s in o['sezioni'] if s.get('fino_a')]
    svg = []
    for a_, b_, caldo, tit in archi:
        if a_ not in nodi or b_ not in nodi:
            continue
        s_, t_ = nodi[a_], nodi[b_]
        sr, tr = s_['x'] + s_['w'], t_['x'] + t_['w']
        y1, y2 = s_['y'] + 21, t_['y'] + 21
        if t_['x'] >= sr + 24:
            d = 'M%d %d C%d %d, %d %d, %d %d' % (sr, y1, sr + 50, y1, t_['x'] - 50, y2, t_['x'] - 2, y2)
        else:
            xv = min(max(sr + 10, t_['x'] + 10), tr - 10)
            giu = t_['y'] > s_['y']
            d = 'M%d %d H%d Q%d %d %d %d V%d' % (sr, y1, xv - 6, xv, y1, xv, y1 + (6 if giu else -6), t_['y'] - 2 if giu else t_['y'] + 44)
        svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" marker-end="url(#%s)"><title>%s</title></path>' % (
            d, TONI['rosso'][0] if caldo else '#1b1d21', 2 if caldo else 1.5, 'arwx' if caldo else 'arw', e(tit)))
    wB, hB = GUT + giorni * PX + 20, LY(lane) + 34
    ticks = ''.join('<div class="nb-tk" style="left:%dpx"></div><span class="nb-tl" style="left:%dpx">lun %s</span>' % (
        X(str(D(ini) + datetime.timedelta(i))), X(str(D(ini) + datetime.timedelta(i))), gm(str(D(ini) + datetime.timedelta(i))))
        for i in range(0, giorni, 7))
    rel = sorted({(s['rilascio']['data'], s['rilascio'].get('tsk') or '') for s in o['sezioni'] if (s.get('rilascio') or {}).get('data')})
    linee = ''.join('<div class="nb-ln" style="left:%dpx"></div><span class="nb-lb" style="left:%dpx;top:26px" title="%s">R %s</span>' % (
        X(d) + PX, X(d) + PX, e(t), gm(d)) for d, t in sorted({d: t for d, t in rel}.items()))
    linee += ('<div class="nb-ln tg" style="left:%dpx"></div><span class="nb-lb tg" style="left:%dpx;top:%dpx">Obiettivo %s</span>' % (
        X(o['data_target']) + PX, X(o['data_target']) + PX, LY(lane) + 6, gm(o['data_target'])))
    gr = ''.join('<div class="nb-gr" style="top:%dpx;height:%dpx;border-left-color:%s"><span class="t">%s</span><span class="mono s">%s</span></div>' % (
        g['y'], g['h'], g['solid'], e(g['label']), e(g['meta'])) for g in gruppi)
    nn = ''.join('<div class="nb-n" title="%s" style="left:%dpx;top:%dpx;width:%dpx;background:%s;border:1px %s %s"><div class="nb-f" style="width:%s%%;background:%s"></div>'
                 '<span class="t">%s%s</span><span class="mono">%s</span></div>' % (
                     e(n['title']), n['x'], n['y'], n['w'], TONI[n['tono']][1], 'dashed' if n['dashed'] else 'solid', TONI[n['tono']][0],
                     n['fill'], TONI[n['tono']][0], e(n['label']), etichetta_sp(n.get('sp')), e(n['meta'])) for n in nodi.values())
    return ('<div class="var v-b" hidden><div class="scroll"><div class="nb" style="width:%dpx;height:%dpx">%s%s%s%s'
            '<svg width="%d" height="%d"><defs><marker id="arw" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M0,0 L8,4 L0,8 z" fill="#1b1d21"></path></marker><marker id="arwx" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="%s"></path></marker></defs>%s</svg><div class="nb-oggi" style="left:%dpx"></div></div></div>'
            '<div class="card-f"><span class="leg"><i class="arr"></i>un TSK della sezione d\'arrivo attende un TSK di quella di partenza (depends_on)</span>'
            '<span class="leg"><i class="arr hot"></i>collo di bottiglia (TSK atteso da TSK di ≥ 3 sezioni)</span>'
            '<span class="leg"><i class="dash"></i>avvio non indicato o sezione congelata fino a un obiettivo</span>'
            '%s<span>R = rilasci in %s · scorri in orizzontale%s</span></div></div>' % (
                wB, hB, gr, ticks, linee, nn, wB, hB, TONI['rosso'][0], ''.join(svg), X(oggi) + PX // 2, legenda_sp(o['sezioni']), e(ambiente(o)),
                (' · senza date nel piano: ' + e('; '.join(senza))) if senza else ''))


def dettaglio_nel_tempo(o, obs, codice, cfg, oggi, nomi_ob):
    b = rete(o, obs, codice, cfg, oggi, nomi_ob) if o['sezioni'] else ''
    var = ('<div class="seg2"><button class="tg on" data-var="a"><span class="mono s">1a</span> Gantt ad albero</button>'
           '<button class="tg%s" data-var="b"%s><span class="mono s">1b</span> Rete su asse temporale%s</button></div>' % (
               '' if b else ' off', '' if b else ' disabled', '' if b else ' (serve un piano per sezioni)'))
    return ('<section class="card"><div class="card-h"><div><h2>Dettaglio nel tempo · %s e dipendenze</h2>'
            '<span class="s hint" data-hint-a="1a — gerarchia obiettivo → sotto-obiettivo → sezione, con finestre e rilasci sullo stesso asse." '
            'data-hint-b="1b — sezioni come nodi nel tempo, frecce fra le sezioni i cui TSK si attendono.">'
            '1a — gerarchia obiettivo → sotto-obiettivo → sezione, con finestre e rilasci sullo stesso asse.</span></div>'
            '<div class="row-g">%s<div class="seg2"><button class="tg" data-tg="tsk">Tutti i TSK</button><button class="tg" data-tg="fuori" title="US fuori dalle sezioni nei progetti che hanno sezioni">US fuori sezione</button></div>'
            '</div></div>%s%s</section>' % (codice[o['id']], var, albero(o, obs, codice, cfg, oggi, nomi_ob), b))


def attenzione_e_persone(o):
    nomi_sez = {s['id']: s['nome'] for s in o['sezioni']}
    av = ''.join('<div class="pa"><span class="mono" style="color:%s">%02d</span><div><span class="t">%s</span><span class="s b">%s%s</span>'
                 '<span class="s r">%s · regola: %s</span></div></div>' % (
                     LIV_COLORE[x['livello']], i + 1, e(titolo_avviso(x, nomi_sez)), e(x['testo']),
                     ''.join(' · ' + e(c) for c in contesto_avviso(x, o, nomi_sez)), e(x['livello']), e(x['regola']))
                 for i, x in enumerate(o['avvisi'])) or '<div class="vuoto">Nessun avviso dalle regole dichiarate.</div>'
    pers = o.get('persone') or {'per_persona': [], 'senza_owner': [], 'agenti': []}
    nomi_prog = {ep: p['nome'] for p in o['perimetro'] for ep in p['epiche']}
    con_sez = {p['progetto_id'] for p in o['perimetro'] if any(s['progetto_id'] == p['progetto_id'] for s in o['sezioni'])}
    prog_ep = {ep: p['progetto_id'] for p in o['perimetro'] for ep in p['epiche']}

    sp_di = sp_sezioni(o)

    def dove(v):
        if v['sezioni']:
            return [(nomi_sez.get(z, z), sp_di.get(z) == 'configurazione') for z in v['sezioni']]
        return [('%s · fuori sezione' % nomi_prog.get(v['epica'], v['epica']), False)] if prog_ep.get(v['epica']) in con_sez else \
            [(nomi_prog.get(v['epica'], v['epica']), False)]

    def riga(nome, nota, vv, colore='#1b1d21', peso=600):
        p0 = sum(1 for v in vv if v['priorita'] == 'P0')
        ds = sorted(v['scadenza_sezione'] for v in vv if v['scadenza_sezione'])
        secs = []
        for v in vv:
            for x in dove(v):
                if x not in secs:
                    secs.append(x)
        return ('<div class="pp"><span style="font-weight:%d;color:%s">%s</span><span class="s">%s</span></div><span class="mono">%d</span>'
                '<span class="mono" style="color:%s">%s</span><span class="mono">%s</span><span class="s"><span>%s</span></span>' % (
                    peso, colore, e(nome), e(nota or ''), len(vv), TONI['rosso'][0] if p0 else '#8a8d93', p0 or '—', gm(ds[0]) if ds else '—',
                    ', '.join(e(x) + (etichetta_sp('configurazione') if infra else '') for x, infra in secs) or '—'))
    con, senza = [], []
    for pp in pers['per_persona']:
        nota = ' · '.join(x for x in (('impegno ~%d%%' % pp['impegno_pct']) if pp.get('impegno_pct') else '', pp.get('nota') or '') if x)
        (con if pp['tsk'] else senza).append(riga(pp['nome'], nota, pp['tsk'], peso=600 if pp['tsk'] else 400,
                                                  colore='#1b1d21' if pp['tsk'] else '#5d6168'))
    righe = con + [riga('Da designare', 'senza owner umano', pers['senza_owner'], colore=TONI['rosso'][0]),
                   riga('Agenti', 'owner = tipo di agente', pers.get('agenti', []))] + senza
    return ('<section class="duo"><div class="card pad"><h2>Punti di attenzione</h2>%s'
            '<span class="s">Avvisi calcolati con regole dichiarate sui dati del kanban, non giudizi.</span></div>'
            '<div class="card pad"><div class="row-sb"><h2>Persone e carico</h2><span class="s">TSK aperti nel perimetro</span></div>'
            '<div class="ppl"><span class="mono s">PERSONA</span><span class="mono s">TSK</span><span class="mono s">P0</span><span class="mono s">SCADE</span>'
            '<span class="mono s">SEZIONI</span>%s</div></div></section>' % (av, ''.join(righe)))


def dettaglio_piano(s, etichette_piano, ambiente_rilascio='test'):
    """Piano e calendario di una sezione, come prima del template: US, pianificata il, avvio, pronta entro, rilascio con TSK e status,
    campi del frontmatter della US indicati in vista_pm.piano. Tutto dalla misura; le date assenti restano «non indicata»."""
    cal, r = s['calendario'], s.get('rilascio') or {}
    parti = ['US %s' % ', '.join(u['id'] for u in s['us']),
             'pianificata il %s' % (data_it(cal['pianificata_il']) if cal['pianificata_il'] else '—'),
             'avvio %s' % (data_it(cal['avvio']) if cal['avvio'] else 'non indicato'),
             'pronta entro %s' % (data_it(cal['pronta_entro']) if cal['pronta_entro'] else 'non indicata'),
             ('rilascio in %s %s%s' % (ambiente_rilascio, data_it(r['data']), (' (%s · status %s)' % (r['tsk'], r['tsk_stato']) if r.get('tsk_trovato')
                                                              else ' (%s non trovato nel kanban)' % r['tsk'] if r.get('tsk') else '')))
             if r.get('data') else 'rilascio: nessuna data in config']
    righe = ['<span class="mono s">%s</span>' % e(' · '.join(parti))]
    for pz in s.get('piano', []):
        for campo, etichetta in etichette_piano.items():
            if pz.get(campo) not in (None, '', []):
                righe.append('<span class="s"><b>%s</b> %s</span>' % (e(etichetta), e(pz[campo])))
    return '<div class="piano">%s</div>' % ''.join(righe)


# ---------------------------------------------------------------- Piano operativo
def piano_operativo(m, cfg, oggi):
    obs = m['obiettivi']
    codice = {o['id']: 'O%d' % (i + 1) for i, o in enumerate(obs)}
    nomi_ob = {o['id']: o['nome'] for o in obs}
    soglia = cfg.get('vista_pm', {}).get('soglia_giorni_scadenza', 3)
    toni = toni_progetti(cfg)
    etichette_piano = {x['campo']: x.get('etichetta') or x['campo'] for x in cfg.get('vista_pm', {}).get('piano', [])}
    gruppi, tutte = [], []
    for o in obs:
        ap = o['tsk_aperti']
        sp_di = sp_sezioni(o)
        progetto_di = {ep: p['progetto_id'] for p in o['perimetro'] for ep in p['epiche']}
        blocchi = [(ondata(s, nomi_ob) + ' · ' + s['nome'], s, [v for v in ap if s['id'] in v['sezioni']])
                   for s in sorted(o['sezioni'], key=chiave_sezione)]
        visti = {v['tsk'] for _, _, vv in blocchi for v in vv}
        altri = {}
        for v in ap:
            if v['tsk'] not in visti:
                altri.setdefault((v['epica'], v['us'] or '(senza US)'), []).append(v)
        titoli_us = {g['us']: g['titolo_us'] for g in o['non_legati_a_sezione']}
        blocchi += [('%s · %s' % (us, corto(titoli_us.get(us, ''), 60)), None, vv) for (ep, us), vv in sorted(altri.items())]
        for label, s, vv in blocchi:
            if not vv:
                # sezione senza TSK aperti: resta visibile con piano e calendario (date di pronta entro e rilascio),
                # altrimenti spariscono dalla pagina appena la sezione e' completata. Classe grp-fatta e non grp:
                # il filtro del piano nasconde i .grp senza TSK visibili; i .grp-fatta seguono obiettivo e persona in report-tab.js.
                if s and s['conteggi']['totale']:
                    ril = (s.get('rilascio') or {}).get('data')
                    gruppi.append(
                        '<section class="card grp-fatta" data-ob="%s"><div class="grp-h" style="border-left:3px solid %s"><div class="row-g">'
                        '<span class="t">%s%s</span><span class="mono s">%s%s · %s</span>%s</div><div class="row-g"><span class="s cnt">%d/%d fatti · nessun TSK aperto</span></div>'
                        '<details class="dett piano-d"><summary>Piano della US e calendario</summary>%s</details></div></section>' % (
                            e(o['id']), TONI['verde'][0], e(label), etichetta_sp(s.get('sottoperimetro')), e(AVANZAMENTO.get(s['avanzamento'], s['avanzamento'])),
                            (' · rilascio ' + gm(ril)) if ril else '', codice[o['id']], etichetta_stato(o['avvisi'], s['id']),
                            s['conteggi']['fatto'], s['conteggi']['base_calcolo'], dettaglio_piano(s, etichette_piano, ambiente(o))))
                continue
            tutte += vv
            persone = sorted({v['persona_nome'] for v in vv if v['persona_nome']})
            ril = (s.get('rilascio') or {}).get('data') if s else None
            sc_ = scadenza(s) if s else None
            gg = s['calendario']['giorni_a_pronta'] if s else None
            due = ('entro %s · %d g lav.' % (gm(sc_), gg) if gg is not None else 'entro %s' % gm(sc_)) if sc_ else 'senza data'
            tono = 'ambra' if s and s['stato_config'] == 'congelata' else toni.get(progetto_di.get(vv[0]['epica']), 'blu')
            righe = []
            for v in vv:
                chi, cls = chi_owner(v)
                if v['categoria'] == 'in_corso':
                    st, col = 'In corso', TONI['blu'][0]
                elif v['categoria'] in ('sospeso', 'bloccato'):
                    st, col = v['stato'], TONI['rosso'][0]
                elif v['pronto']:
                    st, col = 'Pronto da avviare', TONI['verde'][0]
                elif v['attende']:
                    st, col = 'In attesa', TONI['ambra'][0]
                else:
                    st, col = v['stato'], '#5d6168'
                link = ('attende ' + ', '.join(v['attende'])) if v['attende'] else ('sblocca %d TSK' % len(v['attesi_da'])) if v['attesi_da'] else (
                    ('scade ' + gm(v['scadenza_sezione'])) if v['scadenza_sezione'] else '')
                own = v['persona'] if v['gruppo'] == 'persona' else 'agente' if v['gruppo'] == 'agente' else 'da_designare'
                righe.append(
                    '<div class="tk" data-tsk="%s" data-ob="%s" data-own="%s" data-p0="%d" data-pronto="%d" data-attesa="%d"><span class="pr %s">%s</span>'
                    '<span class="mono s">%s</span><span>%s%s</span><span class="ow %s">%s</span><div class="st"><span style="color:%s"><i style="background:%s"></i>%s</span>'
                    '<span class="mono s">%s</span></div></div>' % (
                        e(v['tsk']), e(o['id']), e(own), v['priorita'] == 'P0', v['pronto'], bool(v['attende']), e((v['priorita'] or 'nd').lower()),
                        e(v['priorita'] or '—'), e(v['tsk']), e(v['titolo']), chip_infra(v, sp_di), cls, e(chi), col, col, e(st), e(link)))
            gruppi.append(
                '<section class="card grp" data-ob="%s"><div class="grp-h" style="border-left:3px solid %s"><div class="row-g"><span class="t">%s%s</span>'
                '<span class="mono s">%s%s · %s</span>%s</div><div class="row-g"><span class="s cnt">%d pronti · %d in attesa</span>'
                '<span class="due%s">%s</span></div>%s</div>%s</section>' % (
                    e(o['id']), TONI[tono][0], e(label), etichetta_sp(s.get('sottoperimetro')) if s else '', e(', '.join(persone) or 'nessuna persona'),
                    (' · rilascio ' + gm(ril)) if ril else '',
                    codice[o['id']], etichetta_stato(o['avvisi'], s['id']) if s else '', sum(1 for v in vv if v['pronto']), sum(1 for v in vv if v['attende']),
                    ' hot' if gg is not None and gg <= soglia else '', e(due),
                    ('<details class="dett piano-d"><summary>Piano della US e calendario</summary>%s</details>' % dettaglio_piano(s, etichette_piano, ambiente(o)))
                    if s else '',
                    ''.join(righe)))
    giorni, d = ([oggi] if D(oggi).weekday() < 5 else []), D(oggi)
    while len(giorni) < 6:
        d += datetime.timedelta(1)
        if d.weekday() < 5:
            giorni.append(str(d))
    sett = []
    for g in giorni:
        items = []
        for o in obs:
            nomi = {s['id']: s['nome'] for s in o['sezioni']}
            items += [('○', 'Avvio · %s' % s['nome']) for s in o['sezioni'] if s['calendario'].get('avvio') == g]
            for s in o['sezioni']:
                if (s.get('rilascio') or {}).get('data') == g:
                    items.append(('◆', 'Rilascio in %s · %s%s' % (ambiente(o), s['nome'], (' (%s)' % s['rilascio']['tsk']) if s['rilascio'].get('tsk') else '')))
            per_sez = {}
            for v in o['tsk_aperti']:
                if v['scadenza_sezione'] == g:
                    for z in v['sezioni']:
                        per_sez[z] = per_sez.get(z, 0) + 1
            items += [('●', '%s: %d TSK da chiudere' % (nomi.get(z, z), n)) for z, n in sorted(per_sez.items())]
        n = sum(1 for o in obs for v in o['tsk_aperti'] if v['scadenza_sezione'] == g)
        sett.append('<div class="day%s"><div class="row-sb"><span class="t">%s %s%s</span><span class="mono s">%s</span></div>%s</div>' % (
            ' hot' if items else '', GIORNI[D(g).weekday()].capitalize(), gm(g), ' · oggi' if g == oggi else '', ('%d TSK' % n) if n else '',
            ''.join('<div class="it"><span>%s</span><span>%s</span></div>' % (sym, e(t)) for sym, t in items)
            or '<div class="it muto"><span>·</span><span>Nessuna scadenza</span></div>'))
    kpi = [('kpi-n', len(tutte), 'TSK aperti', '#1b1d21'), ('kpi-p0', sum(1 for v in tutte if v['priorita'] == 'P0'), 'P0', TONI['rosso'][0]),
           ('kpi-pronti', sum(1 for v in tutte if v['pronto']), 'pronti da avviare', TONI['verde'][0]),
           ('kpi-attesa', sum(1 for v in tutte if v['attende']), 'in attesa di prerequisito', TONI['ambra'][0])]
    leg_sp = legenda_sp([s for o in obs for s in o['sezioni']])
    chip_ob = [('tutti', 'Tutti gli obiettivi', len(tutte), '')] + [(o['id'], codice[o['id']], len(o['tsk_aperti']), o['nome']) for o in obs]
    chip_p = [('tutti', 'Tutti', len(tutte))] + [(p['id'], p['nome'].split(' ')[-1], sum(1 for v in tutte if v['persona'] == p['id']))
                                                 for p in cfg.get('team', [])] + [
        ('da_designare', '⚠ Da designare', sum(1 for v in tutte if v['non_assegnato'])), ('agente', 'Agenti', sum(1 for v in tutte if v['gruppo'] == 'agente'))]
    return (
        '<div class="col16"><div class="chips"><span class="s lab">Obiettivo</span>%s</div><div class="chips"><span class="s lab">Mostra il lavoro di</span>%s</div>'
        '<section class="week">%s</section><span class="s">Settimana: tutte le persone · ○ avvio · ● scadenza («pronta entro» della sezione del TSK) · ◆ rilascio in %s</span>'
        '%s<section class="kpis">%s</section>%s<div class="vuoto nessuno" hidden>Nessun TSK aperto per questo filtro.</div></div>' % (
            ''.join('<button class="chip sq%s" data-fob="%s" title="%s">%s<span class="mono">%d</span></button>' % (
                ' on' if k == 'tutti' else '', e(k), e(t), e(l), n) for k, l, n, t in chip_ob),
            ''.join('<button class="chip%s" data-fown="%s">%s<span class="mono">%d</span></button>' % (' on' if k == 'tutti' else '', e(k), e(l), n)
                    for k, l, n in chip_p),
            ''.join(sett), e(' / '.join(dict.fromkeys(ambiente(o) for o in obs)) or 'test'),
            ('<div class="leg-sp s">%s</div>' % leg_sp) if leg_sp else '',
            ''.join('<div class="kpi" style="border-top-color:%s"><span class="v" id="%s">%d</span><span class="s">%s</span></div>' % (c, i, v, l)
                                   for i, v, l, c in kpi), ''.join(gruppi)))


def tabella_conteggi(m):
    """Conteggi per stato di ogni epica, sezione e gruppo di lavoro non legato (la «Vista tabella» di prima)."""
    righe = []
    for o in m['obiettivi']:
        blocchi = [('Epica', '%s · %s' % (ep['id'], ep['titolo']), ep['conteggi'], None) for ep in o['epiche']] + \
                  [('Sezione', s['nome'], s['conteggi'], s.get('sottoperimetro')) for s in o['sezioni']] + \
                  [('Non legato · %s' % g['epica'], '%s · %s' % (g['us'], g['titolo_us']), g['conteggi'], None) for g in o['non_legati_a_sezione']]
        for gruppo, voce, c, sp in blocchi:
            righe.append('<tr><td>%s</td><td>%s</td><td>%s%s</td>%s<td class="n">%s</td></tr>' % (
                e(corto(o['nome'], 30)), e(gruppo), e(voce), etichetta_sp(sp), ''.join('<td class="n">%d</td>' % c[k] for k in
                                                                     ('fatto', 'in_corso', 'da_fare', 'sospeso', 'bloccato', 'sconosciuto', 'chiuso_senza_esito')),
                '' if c['pct'] is None else '%d%%' % c['pct']))
    return ('<details class="dett"><summary>Vista tabella · conteggi per stato</summary><div class="scroll"><table class="tab-c"><thead><tr><th>Obiettivo</th>'
            '<th>Gruppo</th><th>Voce</th><th>Completate</th><th>In corso</th><th>Da fare</th><th>Sospese</th><th>Bloccate</th><th>Stato sconosciuto</th>'
            '<th>Chiuse senza esito</th><th>%%</th></tr></thead><tbody>%s</tbody></table></div></details>' % ''.join(righe))


# ---------------------------------------------------------------- Qualità dato
def qualita(m, cfg, ctx, titoli, al, kdata, sha, generato):
    gruppi_q = {}
    for f in m['qualita_dato']:
        gruppi_q.setdefault((f['livello'], f['codice']), []).append(f)
    gravi, info = [], []
    for (liv, cod), ff in sorted(gruppi_q.items(), key=lambda kv: (kv[0][0] != 'ERRORE', kv[0][0] != 'AVVISO', kv[0][1])):
        descr = pv.DESCR_QUALITA.get(cod, cod)
        ids = sorted({f['entita'] for f in ff})
        colore = TONI['rosso'][0] if liv == 'ERRORE' else TONI['ambra'][0] if liv == 'AVVISO' else '#8a8d93'
        if liv == 'INFO':
            info.append('<div class="q"><span class="mono" style="color:%s">%s</span><div><span class="t">%d × %s</span>%s%s</div></div>' % (
                colore, e(liv), len(ff), e(descr),
                ''.join('<span class="s">%s · %s</span>' % (e(f['entita']), e(f['evidenza'])) for f in ff[:12])
                + ('<details class="dett"><summary>altre %d</summary>%s</details>' % (len(ff) - 12, ''.join(
                    '<span class="s">%s · %s</span>' % (e(f['entita']), e(f['evidenza'])) for f in ff[12:])) if len(ff) > 12 else ''),
                cta('%s (%d: %s%s)' % (descr, len(ff), ', '.join(ids[:4]), '…' if len(ids) > 4 else ''), pv.qualita(ctx, ff))))
            continue
        for f in ff:
            gravi.append('<div class="q"><span class="mono" style="color:%s">%s</span><div><span class="t">%s · %s</span>'
                         '<span class="s">%s</span><span class="s">%s</span>%s</div></div>' % (
                             colore, e(liv), e(f['entita']), e(cod), e(descr), e(f['evidenza']), cta('%s · %s' % (f['entita'], cod), pv.qualita(ctx, [f]))))
    voci_html = []
    for o in m['obiettivi']:
        blocchi = [('%s (%s)' % (ep['id'], corto(ep['titolo'], 60)), ep) for ep in o['epiche']] + \
                  [('sezione %s' % s['nome'], s) for s in o['sezioni']] + \
                  [('%s (%s)' % (g['us'], corto(g['titolo_us'], 60)), g) for g in o['non_legati_a_sezione']]
        for voce, b in blocchi:
            vv = voci(b, voce, ctx, titoli)
            if vv:
                voci_html.append('<div class="q"><span class="mono s">voce</span><div><span class="t">%s</span><span class="s">%s</span>%s</div></div>' % (
                    e(voce), e(' · '.join(t for t, _ in vv)), ''.join(cta(t, pr) for t, pr in vv)))
        for s in o['sezioni']:
            if not s['conteggi']['totale']:
                voci_html.append('<div class="q"><span class="mono s">sezione</span><div><span class="t">%s: nessun TSK registrato</span>%s%s</div></div>' % (
                    e(s['nome']), dettaglio_piano(s, {x['campo']: x.get('etichetta') or x['campo'] for x in cfg.get('vista_pm', {}).get('piano', [])}, ambiente(o)),
                    cta('sezione senza TSK', pv.sezione_vuota(ctx, s['nome'], s['us']))))
    prov, cop = m['provenienza'], m['copertura']
    np_ = prov.get('non_pushati') or {}
    kv = [('ref', '%s · %s (%s)' % (prov.get('ref') or prov['fonte'], sha[:8], kdata)),
          ('TSK letti', '%d (%d illeggibili%s)' % (cop['tsk_totali'], len(cop['tsk_illeggibili']),
                                                 (': ' + ', '.join(cop['tsk_illeggibili'])) if cop['tsk_illeggibili'] else ''))]
    kv += [('perimetro %s' % corto(o['nome'], 22), '%d TSK · %d in sezioni · %d non legati' % (
        o['copertura']['tsk_perimetro'], o['copertura']['tsk_in_sezioni'], o['copertura']['tsk_non_legati'])) for o in m['obiettivi'] if o['epiche']]
    kv += [('generato', generato), ('allineamento', '%d candidati · config %s' % (al['conteggio'] if al else 0, cfg.get('aggiornato', '?'))),
           ('snapshot sha256', prov['snapshot_sha256'][:12]), ('config sha256', prov['config_sha256'][:12])]
    regole = ('Avanzamento = TSK completati sul totale, esclusi i chiusi senza esito e gli stati che la config mette fra loro (es. rinviati definitivamente), mostrati a parte; i sospesi restano nel calcolo. '
              'Sezione solo dalla mappa US→sezione della config; i TSK senza sezione restano con la loro US. Owner solo dal campo owner del TSK '
              '(team, owner_agente e owner_non_persona della config). Date: avvio, «pronta entro» e rilascio dalla config ancorata al kanban, '
              '«pianificata il» dal created della US; quelle assenti restano vuote. Avvisi = regole dichiarate, non giudizi. '
              'Nessun dato di questa pagina è prodotto da un modello di AI.')
    return (
        '<div class="duo top"><div class="col16">%s<section class="card pad"><h2>Da correggere nel kanban</h2>%s%s</section></div>'
        '<div class="col16"><section class="card pad"><h2>Provenienza</h2><div class="kv mono">%s</div>%s<span class="s">%s</span>%s</section>'
        '<section class="card pad"><h2>Voci da verificare</h2><span class="s">Prompt pronti da incollare in una sessione Claude nella factory '
        '(verifica in sola lettura, modifica solo dopo conferma).</span>%s</section></div></div>' % (
            allineamento(al, ctx), ''.join(gravi) or '<div class="vuoto">Nessun errore o avviso.</div>',
            ('<details class="dett"><summary>Informazioni minori (%d)</summary>%s</details>' % (
                sum(len(v) for (lv, _), v in gruppi_q.items() if lv == 'INFO'), ''.join(info))) if info else '',
            ''.join('<span class="k">%s</span><span>%s</span>' % (e(k), e(v)) for k, v in kv),
            ('<span class="s">%d commit locali non ancora su %s: il report riflette lo stato locale.</span>' % (len(np_['commit']), e(np_['upstream'])))
            if np_.get('commit') else '', e(regole), tabella_conteggi(m), ''.join(voci_html) or '<div class="vuoto">Nessuna voce da verificare.</div>'))


def allineamento(al, ctx):
    if not (al and al['conteggio']):
        return ''
    dettaglio = ', '.join('%s %d' % (k.replace('_', ' '), v) for k, v in al['per_tipo'].items())
    return ('<section class="card pad"><h2>Configurazione del report</h2><span class="s">La configurazione del report non è allineata al kanban: '
            '%d elementi da classificare (%s). Il raggruppamento per sezione può essere incompleto.</span>%s</section>' % (
                al['conteggio'], e(dettaglio), cta('allinea la configurazione', pv.allineamento_config(ctx, al['conteggio']))))


def lettura_assistita(path):
    """Narrativa PM già verificata da verifica_citazioni.py: riquadro separato, dichiarato non deterministico."""
    if not path:
        return ''
    n = json.load(open(path, encoding='utf-8'))
    return ('<section class="card pad narr"><div class="row-sb"><h2>Lettura assistita</h2><span class="mono s up" style="color:%s">non deterministica · '
            'citazioni verificate</span></div><ul>%s</ul><span class="s">Testo scritto da un modello sui campi della misura: ogni numero, ID e data è stato '
            'controllato contro i campi citati (verifica_citazioni.py, %s). Non sostituisce i dati: in caso di dubbio valgono le schede.</span></section>' % (
                TONI['ambra'][0], ''.join('<li>%s <span class="mono cit">%s</span></li>' % (e(f['frase']), e(' '.join('[F:%s]' % c for c in f['citazioni'])))
                                        for f in n['frasi']), e(n.get('verificata_il', ''))))


# ---------------------------------------------------------------- pagina
def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True)
    ap.add_argument('--misura', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--allineamento', help='JSON di controlla_config.py')
    ap.add_argument('--file-grandi', help='JSON di file_grandi.py (regole di lettura nei prompt)')
    ap.add_argument('--generato', help='testo dell\'ora di generazione (default: adesso)')
    ap.add_argument('--narrativa', help='JSON di verifica_citazioni.py --out (lettura assistita verificata)')
    a = ap.parse_args(argv)

    cfg = json.load(open(a.config, encoding='utf-8'))
    m = json.load(open(a.misura, encoding='utf-8'))
    vp = cfg.get('vista_pm', {})
    prov = m['provenienza']
    root = _risolvi_factory_root(cfg, a.config)
    operatore = _operatore(a.config)
    config_nome = os.path.basename(a.config)
    print('CONFIG: %s | OPERATORE: %s' % (config_nome, operatore))
    sha = prov.get('ref_sha') or prov['factory_head']
    try:
        kdata = subprocess.run(['git', '-C', root, 'show', '-s', '--format=%cd', '--date=format:%d/%m/%Y %H:%M', sha],
                               capture_output=True, text=True).stdout.strip() or 'data non disponibile'
    except OSError:
        kdata = 'data non disponibile'
    generato = a.generato or datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    titolo = vp.get('titolo', 'Avanzamento del kanban')
    oggi = m['oggi']
    configura_palette(cfg)
    pv.configura(cfg.get('prompt_verifica') or {})
    ctx = {'factory_root': root, 'commit': sha[:8], 'titolo': titolo, 'data': data_it(oggi), 'oggi': oggi, 'config': a.config,
           'file_grandi': json.load(open(a.file_grandi, encoding='utf-8')) if a.file_grandi else None}
    titoli = m.get('titoli', {})
    al = json.load(open(a.allineamento, encoding='utf-8')) if a.allineamento else None
    obs = m['obiettivi']
    codice = {o['id']: 'O%d' % (i + 1) for i, o in enumerate(obs)}
    nomi_ob = {o['id']: o['nome'] for o in obs}
    np_ = prov.get('non_pushati') or {}

    banner = []
    if prov['fonte'] != 'commit':
        banner.append(e('Misura letta dai file sul disco, non da un commit: non è riproducibile.'))
    if prov['kanban_non_committati']:
        banner.append(e('Il kanban ha %d file modificati e non ancora committati: non sono inclusi in questa misura.' % len(prov['kanban_non_committati'])))
    if prov.get('fonte') == 'commit' and 'non_pushati' in prov and prov['non_pushati'] is None:
        banner.append(e('Il branch della factory non ha un upstream configurato: non posso dire se il commit misurato è stato pushato.'))
    sel = next((o['id'] for o in obs if o.get('predefinito')), obs[0]['id'] if obs else '')
    dettagli = ''.join('<div class="obdet" data-obdet="%s"%s>%s%s%s</div>' % (
        e(o['id']), '' if o['id'] == sel else ' hidden', schede_obiettivo(o, obs, codice, cfg) + blocco_bloccanti(o), dettaglio_nel_tempo(o, obs, codice, cfg, oggi, nomi_ob),
        attenzione_e_persone(o) if o['epiche'] else '') for o in obs)
    n_err = sum(1 for f in m['qualita_dato'] if f['livello'] == 'ERRORE')
    n_avv = sum(1 for f in m['qualita_dato'] if f['livello'] == 'AVVISO')
    n_ap = sum(len(o['tsk_aperti']) for o in obs)
    meta = 'misura del kanban · oggi %s %s · %s %s%s%s' % (
        GIORNI[D(oggi).weekday()], data_it(oggi), 'HEAD' if prov['fonte'] == 'commit' and (prov.get('ref') or 'HEAD') == 'HEAD' else (prov.get('ref') or 'disco'),
        sha[:8], (' · %d commit non pushati' % len(np_['commit'])) if np_.get('commit') else '',
        (' · config: %d elementi da classificare' % al['conteggio']) if al and al['conteggio'] else '')
    tabs = (('pm', 'Vista PM', ''), ('ops', 'Piano operativo', str(n_ap)),
            ('q', 'Qualità dato', ('%d err' % n_err) if n_err else ('%d avvisi' % n_avv) if n_avv else ''))
    css = open(os.path.join(ASSETS, 'report-tab.css'), encoding='utf-8').read()
    js = open(os.path.join(ASSETS, 'report-tab.js'), encoding='utf-8').read() + '\n' + open(os.path.join(ASSETS, 'cta-prompt.js'), encoding='utf-8').read()
    pagina = (
        '<!DOCTYPE html>\n<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>%s — %s</title><style>%s</style></head><body><div class="wrap"><header><div class="hh"><div class="mono s">%s</div>'
        '<div class="mono s" style="color:#8a8d93">CONFIG: %s | OPERATORE: %s</div><h1>%s</h1></div>'
        '<nav>%s</nav></header>%s<div class="pane" data-pane="pm"><div class="col20">%s%s%s</div></div>'
        '<div class="pane" data-pane="ops" hidden>%s</div><div class="pane" data-pane="q" hidden>%s</div></div><script>%s</script></body></html>\n') % (
        e(titolo), e(data_it(oggi)), css, e(meta), e(config_nome), e(operatore), e(titolo),
        ''.join('<button class="tab%s" data-tab="%s">%s<span class="mono s">%s</span></button>' % (' on' if k == 'pm' else '', k, l, b) for k, l, b in tabs),
        ''.join('<div class="banner">%s</div>' % b for b in banner), lettura_assistita(a.narrativa), portafoglio(m, oggi), dettagli,
        piano_operativo(m, cfg, oggi), qualita(m, cfg, ctx, titoli, al, kdata, sha, generato), js)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(pagina)
    print('vista PM ->', a.out)


if __name__ == '__main__':
    sys.exit(main())
