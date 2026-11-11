#!/usr/bin/env python3
"""Perdita di fatti di una riscrittura (EP-076 US-339).

Nessun numero dal modello: un giudice (agente distinto da chi riscrive) da' un verdetto per fatto,
`presente` | `parziale` | `assente`; i conti li fa questo script, e le **ancore** (numeri,
identificativi, nomi che un fatto deve portare con se') si verificano qui, sul testo.

Input:
  --facts     {"documento": "...", "fatti": [{"id": "F1", "testo": "...", "ancore": ["20"]}]}
  --verdicts  {"varianti": {"A": {"file": "riscrittura.md", "verdetti": {"F1": "presente"}}}}

Per ogni variante:
  ritenzione   (presente + 0,5 * parziale) / fatti;  perdita = 1 - ritenzione
  ancore       quota dei fatti con ancore che le hanno tutte nel corpo della riscrittura (alla
               lettera, o con tutti i token alfanumerici: i simboli diventano parole)
  conflitti    fatto giudicato `presente` con un'ancora che manca nel corpo: si mostra, non si
               risolve in silenzio
  omissioni    per i fatti `assente`/`parziale`: `dichiarata` se un'ancora compare nella sezione
               `## Omesso`, `silenziosa` se ha ancore e nessuna vi compare, `non determinabile`
               se il fatto non ha ancore

Soglia: `ste_lite.max_fact_loss` (default 0,10), o `--soglia`.
Exit: 0 · 1 con --strict se una variante supera la soglia · 2 input non valido o verdetti mancanti.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

RADICE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERDETTI = {'presente': 1.0, 'parziale': 0.5, 'assente': 0.0}
OMESSO = re.compile(r'^#{1,6}\s+Omesso\b.*$', re.M | re.I)


class InputNonValido(Exception):
    pass


def soglia_config(radice):
    try:
        import yaml
        with open(os.path.join(radice, 'factory.config.yaml'), encoding='utf-8') as fh:
            v = ((yaml.safe_load(fh) or {}).get('ste_lite') or {}).get('max_fact_loss')
    except (ImportError, OSError):
        return 0.10
    return float(v) if isinstance(v, (int, float)) else 0.10


def normalizza(testo):
    return re.sub(r'\s+', ' ', testo.replace('’', "'")).casefold()


def token(testo):
    return re.findall(r'[^\W_]+', normalizza(testo))


def contiene(testo_n, ancora):
    """Ancora presente alla lettera, o con tutti i suoi token alfanumerici come parole intere.

    La seconda forma serve perche' la scrittura controllata trasforma i simboli in parole
    («RAG / LSP» -> «RAG o LSP», «<20 file» -> «meno di 20 file»).
    """
    a = normalizza(str(ancora))
    if a in testo_n:
        return True
    parti = token(a)
    return bool(parti) and set(parti) <= set(token(testo_n))


def dividi(testo):
    """(corpo, omesso): la sezione `Omesso` va dal suo titolo al titolo successivo o alla fine."""
    m = OMESSO.search(testo)
    if not m:
        return testo, ''
    dopo = testo[m.end():]
    fine = re.search(r'^#{1,6}\s', dopo, re.M)
    omesso = dopo[:fine.start()] if fine else dopo
    return testo[:m.start()] + (dopo[fine.start():] if fine else ''), omesso


def valuta(fatti, variante, testo, soglia):
    verdetti = variante.get('verdetti') or {}
    mancanti = [f['id'] for f in fatti if f['id'] not in verdetti]
    if mancanti:
        raise InputNonValido('verdetti mancanti: ' + ', '.join(mancanti))
    ignoti = sorted({v for v in verdetti.values() if v not in VERDETTI})
    if ignoti:
        raise InputNonValido('verdetti non ammessi: ' + ', '.join(ignoti))

    corpo, omesso = dividi(testo)
    corpo_n, omesso_n = normalizza(corpo), normalizza(omesso)
    punti, conteggio, conflitti, omissioni = 0.0, {k: 0 for k in VERDETTI}, [], []
    con_ancore = complete = 0
    for f in fatti:
        v = verdetti[f['id']]
        punti += VERDETTI[v]
        conteggio[v] += 1
        ancore = [a for a in (f.get('ancore') or []) if str(a).strip()]
        assenti = [a for a in ancore if not contiene(corpo_n, a)]
        if ancore:
            con_ancore += 1
            complete += not assenti
        if v == 'presente' and assenti:
            conflitti.append({'id': f['id'], 'ancore_mancanti': assenti})
        if v != 'presente':
            if not ancore:
                tipo = 'non determinabile'
            elif any(contiene(omesso_n, a) for a in ancore):
                tipo = 'dichiarata'
            else:
                tipo = 'silenziosa'
            omissioni.append({'id': f['id'], 'verdetto': v, 'omissione': tipo})

    n = len(fatti)
    perdita = round(1 - punti / n, 3) if n else 0.0
    tipi = [o['omissione'] for o in omissioni]
    return {
        'file': variante.get('file'),
        'fatti': n,
        'verdetti': conteggio,
        'ritenzione': round(1 - perdita, 3),
        'perdita': perdita,
        'soglia': soglia,
        'entro_soglia': perdita <= soglia,
        'ancore_complete': round(complete / con_ancore, 3) if con_ancore else None,
        'conflitti': conflitti,
        'sezione_omesso': bool(OMESSO.search(testo)),
        'omissioni': {t: tipi.count(t) for t in ('dichiarata', 'silenziosa', 'non determinabile')},
        'dettaglio_omissioni': omissioni,
    }


def carica(percorso):
    try:
        with open(percorso, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        raise InputNonValido(f'{percorso}: {e}')


def misura(facts_path, verdicts_path, soglia):
    fatti = carica(facts_path).get('fatti') or []
    if not fatti or any('id' not in f for f in fatti):
        raise InputNonValido('fatti assenti o senza id')
    varianti = carica(verdicts_path).get('varianti') or {}
    if not varianti:
        raise InputNonValido('nessuna variante nei verdetti')
    base = os.path.dirname(os.path.abspath(verdicts_path))
    esiti = {}
    for nome, variante in sorted(varianti.items()):
        file = variante.get('file')
        if not file:
            raise InputNonValido(f'variante {nome}: campo file assente')
        percorso = file if os.path.isabs(file) else os.path.join(base, file)
        try:
            with open(percorso, encoding='utf-8') as fh:
                testo = fh.read()
        except OSError as e:
            raise InputNonValido(f'variante {nome}: {e}')
        esiti[nome] = valuta(fatti, variante, testo, soglia)
    return esiti


def stampa(esiti):
    for nome, e in esiti.items():
        stato = 'entro soglia' if e['entro_soglia'] else 'SOPRA SOGLIA'
        anc = '—' if e['ancore_complete'] is None else f'{e["ancore_complete"]:.0%}'
        o = e['omissioni']
        print(f'{nome}  {e["file"]}\n'
              f'  fatti: {e["fatti"]}  presenti: {e["verdetti"]["presente"]}  parziali: '
              f'{e["verdetti"]["parziale"]}  assenti: {e["verdetti"]["assente"]}\n'
              f'  perdita: {e["perdita"]:.1%} (soglia {e["soglia"]:.0%}, {stato})  ancore complete: {anc}\n'
              f'  omissioni: dichiarate {o["dichiarata"]}, silenziose {o["silenziosa"]}, '
              f'non determinabili {o["non determinabile"]}  sezione Omesso: '
              f'{"si" if e["sezione_omesso"] else "NO"}')
        for c in e['conflitti']:
            print(f'  conflitto {c["id"]}: giudicato presente, ancore mancanti {c["ancore_mancanti"]}')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Perdita di fatti di una riscrittura (EP-076).')
    ap.add_argument('--facts', required=True)
    ap.add_argument('--verdicts', required=True)
    ap.add_argument('--soglia', type=float)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--root', default=RADICE)
    a = ap.parse_args(argv)
    soglia = a.soglia if a.soglia is not None else soglia_config(a.root)
    try:
        esiti = misura(a.facts, a.verdicts, soglia)
    except InputNonValido as e:
        print(f'input non valido: {e}', file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(esiti, ensure_ascii=False, indent=2))
    else:
        stampa(esiti)
    return 1 if a.strict and not all(e['entro_soglia'] for e in esiti.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
