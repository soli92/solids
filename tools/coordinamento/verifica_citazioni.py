#!/usr/bin/env python3
"""Verifica la narrativa PM («lettura assistita») contro la misura: ogni frase cita i campi della misura su cui si basa e non
contiene numeri, ID o date che i campi citati non contengono. Esce con 1 alla prima violazione: la narrativa non entra nel report.

    python verifica_citazioni.py --misura misura.json --narrativa narrativa.md [--out narrativa_verificata.json]

Citazione: [F:percorso] con percorso nella misura, es. [F:obiettivi[id=<obiettivo>].conteggi.pct],
[F:obiettivi[0].sezioni[id=<sezione>].calendario], [F:obiettivi[0].avvisi[2]]. Segmenti separati da punto; [n] = indice, [k=v] = elemento
con chiave k uguale a v. Una frase = una riga di testo (titoli markdown esclusi) o un elemento di elenco.
Regole: (1) almeno una citazione per frase; (2) ogni percorso esiste; (3) ogni ID (EP/US/TSK), ogni data (gg/mm o gg/mm/aaaa) e ogni
numero della frase, tolte le citazioni, compare nei valori citati (i numeri anche come parte di un valore, es. 29 in «29/88»).
"""
import argparse
import datetime
import json
import re
import sys

CIT = re.compile(r'\[F:((?:[^\[\]]|\[[^\]]*\])+)\]')
ID = re.compile(r'\b(?:[A-Z]{2,4}-)?(?:EP|US|TSK)-\d+\b')  # prefisso di namespace opzionale
DATA = re.compile(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b')
NUM = re.compile(r'(?<![\w/.-])\d+(?:[.,]\d+)?(?![\w/])')
SEG = re.compile(r'^([\w-]+)((?:\[[^\]]+\])*)$')


def risolvi(m, percorso):
    cur = m
    for seg in percorso.split('.'):
        g = SEG.match(seg)
        if not g:
            raise KeyError(seg)
        nome, filtri = g.group(1), g.group(2)
        cur = cur[nome]
        for f in re.findall(r'\[([^\]]+)\]', filtri):
            if '=' in f:
                k, v = f.split('=', 1)
                cur = next(x for x in cur if str(x.get(k)) == v)
            else:
                cur = cur[int(f)]
    return cur


def frasi(testo):
    out = []
    for riga in testo.splitlines():
        r = riga.strip()
        if not r or r.startswith('#') or r.startswith('>') and not CIT.search(r):
            continue
        r = re.sub(r'^[-*]\s+|^\d+\.\s+', '', r)
        out.append(r)
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--misura', required=True)
    ap.add_argument('--narrativa', required=True)
    ap.add_argument('--out', help='JSON con le frasi verificate (per la vista)')
    a = ap.parse_args(argv)
    m = json.load(open(a.misura, encoding='utf-8'))
    errori, verificate = [], []
    for n, f in enumerate(frasi(open(a.narrativa, encoding='utf-8').read()), 1):
        cit = CIT.findall(f)
        if not cit:
            errori.append('frase %d senza citazione: %s' % (n, f[:120]))
            continue
        valori = []
        for c in cit:
            try:
                valori.append(json.dumps(risolvi(m, c.strip()), ensure_ascii=False))
            except (KeyError, IndexError, StopIteration, ValueError, TypeError):
                errori.append('frase %d: percorso inesistente nella misura [F:%s]' % (n, c))
        if len(valori) != len(cit):
            continue
        dump = ' '.join(valori)
        corpo = CIT.sub(' ', f)
        for i in ID.findall(corpo):
            if i not in dump:
                errori.append('frase %d: %s non compare nei campi citati' % (n, i))
        senza_id = ID.sub(' ', corpo)
        for g in DATA.finditer(senza_id):
            gg, mm, aa = int(g.group(1)), int(g.group(2)), g.group(3)
            iso = '-%02d-%02d' % (mm, gg) if not aa else '%s-%02d-%02d' % (aa, mm, gg)
            if iso not in dump and '%02d/%02d' % (gg, mm) not in dump:
                errori.append('frase %d: data %s non compare nei campi citati' % (n, g.group(0)))
        senza_date = DATA.sub(' ', senza_id)
        numeri_citati = set(re.findall(r'\d+(?:\.\d+)?', dump))
        for x in NUM.findall(senza_date):
            if x.replace(',', '.') not in numeri_citati:
                errori.append('frase %d: numero %s non compare nei campi citati' % (n, x))
        verificate.append({'frase': CIT.sub('', f).strip(), 'citazioni': [c.strip() for c in cit]})
    if errori:
        print('VERIFICA CITAZIONI: FALLITA')
        for x in errori:
            print('  - ' + x)
        return 1
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump({'verificata_il': datetime.datetime.now().isoformat(timespec='minutes'), 'frasi': verificate}, fh, ensure_ascii=False, indent=1)
    print('VERIFICA CITAZIONI: OK (%d frasi, tutte con citazioni verificate)' % len(verificate))
    return 0


if __name__ == '__main__':
    sys.exit(main())
