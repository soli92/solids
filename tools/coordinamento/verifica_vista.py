#!/usr/bin/env python3
"""Controllo anti-regressione della pagina: ricava dalla misura tutto ciò che la vista deve mostrare e verifica che ci sia.
Le attese vengono dalla misura stessa (nessuna pagina di riferimento da tenere allineata): se una modifica alla vista perde un dato,
il controllo esce con 1 e il report non si consegna. I prompt «Chiedi una verifica» non contano: si cerca nel contenuto visibile.

    python verifica_vista.py --misura misura.json --html vista-pm.html
"""
import argparse
import datetime
import html
import json
import re
import sys


def testo_visibile(h):
    h = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', h, flags=re.S)
    h = re.sub(r'<pre class="prompt">.*?</pre>', ' ', h, flags=re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h)))


# etichette dei sottoperimetri come le scrive la vista: la regola di visibilita' resta qui, senza importare la vista
ETICHETTE_SP = {'sviluppo': 'Sviluppo', 'configurazione': 'Infra · rilascio', 'test': 'Test', 'non_indicato': 'Non indicato'}


def it(iso):
    return datetime.date.fromisoformat(iso).strftime('%d/%m/%Y')


def attese(m):
    """[(categoria, testo atteso)] dalla misura."""
    out = []
    for o in m['obiettivi']:
        out.append(('obiettivo', o['nome']))
        amb = o.get('ambiente_rilascio') or 'test'
        for k, c in (o.get('per_sottoperimetro') or {}).items():
            out.append(('avanzamento per sottoperimetro', '%s %d/%d fatti · %s' % (
                ETICHETTE_SP.get(k, k), c['fatto'], c['base_calcolo'], ('%d%%' % c['pct']) if c['pct'] is not None else 'n/d')))
        for ep in o['epiche']:
            out += [('epica', ep['id']), ('conteggi epica', '%d/%d fatti' % (ep['conteggi']['fatto'], ep['conteggi']['base_calcolo']))]
        for s in o['sezioni']:
            out.append(('sezione', s['nome']))
            if s.get('sottoperimetro'):
                out.append(('sottoperimetro della sezione', '%s %s' % (s['nome'], ETICHETTE_SP.get(s['sottoperimetro'], s['sottoperimetro']))))
            out += [('US di sezione', u['id']) for u in s['us']]
            out += [('TSK di sezione', t['tsk']) for t in s['tsk']]
            cal, r = s['calendario'], s.get('rilascio') or {}
            if cal['pianificata_il']:
                out.append(('pianificata il', 'pianificata il %s' % it(cal['pianificata_il'])))
            for k in ('avvio', 'pronta_entro'):
                if cal[k]:
                    out.append((k, it(cal[k])))
            if r.get('data'):
                out.append(('rilascio', 'rilascio in %s %s' % (amb, it(r['data']))))
            for pz in s.get('piano', []):
                out += [('piano %s' % k, str(v)) for k, v in pz.items() if k != 'us' and v not in (None, '', [])]
        out += [('US fuori sezione', g['us']) for g in o['non_legati_a_sezione']]
        out += [('TSK aperto', v['tsk']) for v in o.get('tsk_aperti', [])]
        out += [('avviso', a['testo']) for a in o.get('avvisi', [])]
        out += [('persona', p['nome']) for p in (o.get('persone') or {}).get('per_persona', [])]
        out += [('bloccante', b['tsk']) for b in o.get('bloccanti', [])]
    for f in m['qualita_dato']:
        out += [('anomalia', f['entita']), ('evidenza', f['evidenza'])]
    out.append(('tabella', 'Vista tabella · conteggi per stato'))
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--misura', required=True)
    ap.add_argument('--html', required=True)
    a = ap.parse_args(argv)
    m = json.load(open(a.misura, encoding='utf-8'))
    t = testo_visibile(open(a.html, encoding='utf-8').read())
    att = attese(m)
    mancanti = [(c, x) for c, x in att if re.sub(r'\s+', ' ', x) not in t]
    if mancanti:
        print('VERIFICA VISTA: FALLITA (%d elementi della misura non visibili nella pagina)' % len(mancanti))
        for c, x in mancanti[:40]:
            print('  - %s: %s' % (c, x[:140]))
        return 1
    print('VERIFICA VISTA: OK (%d elementi della misura visibili nella pagina)' % len(att))
    return 0


if __name__ == '__main__':
    sys.exit(main())
