#!/usr/bin/env python3
"""STE-lite: regole strutturali di ASD-STE100 sui testi che legge una persona (EP-076 US-337).

Controllo deterministico, nessun modello nel path del verdetto: i modelli sovrastimano quanto
rispettano i vincoli, quindi la conformita' dichiarata da chi scrive non e' una misura.

Regole (limiti da `ste_lite.limits` di factory.config.yaml):

  frase-procedurale     frase procedurale oltre `procedural_words` parole (default 20)
  frase-descrittiva     frase descrittiva oltre `descriptive_words` parole (default 25)
  paragrafo             paragrafo di prosa oltre `paragraph_sentences` frasi (default 6)
  punto-e-virgola       punto e virgola in una frase
  istruzioni-multiple   frase procedurale con un secondo imperativo dopo «e», «poi», «,»
  passivo-procedura     passivo in una frase procedurale
  contrazione           frecce o abbreviazioni da compressione (caveman) nella prosa
  glossario             sinonimo vietato da `ste_lite.glossary` (un termine, un significato)

Euristiche dichiarate: una frase e' procedurale se sta in un elenco numerato o comincia con un
imperativo dell'elenco della lingua; la lingua si riconosce dalle parole funzione. I gruppi
nominali (max 3 parole) non si controllano: senza analisi morfologica non sono contabili.

Esclusi dal conteggio: frontmatter, blocchi di codice, tabelle, titoli, commenti HTML; nel testo,
codice inline, URL e note `[^...]`. Le parole con apostrofo contano per due («l'agente»).

Uso:
  python3 tools/lint/ste_lite.py FILE [FILE ...] [--json] [--strict] [--lang it|en]
  python3 tools/lint/ste_lite.py --targets        # i file di ste_lite.targets

Exit: 0 (advisory, anche con violazioni) · 1 con --strict e almeno una violazione · 2 uso errato.
A `ste_lite.enabled: false` l'invocazione esplicita su file funziona: e' volonta' esplicita.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

RADICE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT = {
    'enabled': False,
    'targets': [],
    'limits': {'procedural_words': 20, 'descriptive_words': 25, 'paragraph_sentences': 6},
    'glossary': {},
}

IMPERATIVI = {
    'it': set('''esegui apri chiudi verifica controlla aggiungi rimuovi imposta scrivi leggi lancia
        avvia usa copia crea salva installa configura aggiorna sposta premi seleziona inserisci
        attendi rilancia cancella elimina ripeti assicurati accendi spegni collega passa
        committa pusha mergia sostituisci riavvia ferma annota registra segui indica
        riporta mostra calcola confronta prendi metti togli scarica carica cerca'''.split()),
    'en': set('''run open close check verify add remove set write read launch start use copy create
        save install configure update move press select enter wait delete repeat make do turn
        connect commit push merge replace restart stop record follow report show compute compare
        take put download upload find'''.split()),
}
FUNZIONE = {
    'it': set('il lo la gli le di che per non una un con del della dei delle nel nella è sono'.split()),
    'en': set('the of and to is that for with this are be it on not an by from'.split()),
}
PASSIVO = {
    'it': re.compile(r"\b(?:viene|vengono|venga|vengano|veniva|venivano|verrà|verranno|va|vanno|"
                     r"è\s+stat[oaie]|sono\s+stat[ie]|sia\s+stat[oa])\s+(?:\w+\s+)?"
                     r"\w+(?:at|ut|it|s|tt|st|rt|nt)[oaie]\b", re.I),
    'en': re.compile(r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b", re.I),
}
CONGIUNZIONI = {'it': r'(?:\be\b|\bpoi\b|,)', 'en': r'(?:\band\b|\bthen\b|,)'}
CONTRAZIONI = re.compile(r'(→|=>|⇒|\b(?:fn|ret|impl|cfg|w/o?|b/c)\b)')
ABBREVIAZIONI = re.compile(r'\b(?:es|ecc|cfr|pag|sez|art|n|p|vs|e\.g|i\.e|etc|ad|ca|Dr|Mr|Mrs)\.$',
                           re.I)

ELENCO = re.compile(r'^(\s*)(?:([-*+])|(\d+)[.)])\s+(.*)$')


def carica_config(radice):
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT.items()}
    percorso = os.path.join(radice, 'factory.config.yaml')
    try:
        import yaml
        with open(percorso, encoding='utf-8') as fh:
            blocco = (yaml.safe_load(fh) or {}).get('ste_lite') or {}
    except (ImportError, OSError):
        return cfg
    cfg['enabled'] = blocco.get('enabled') is True
    cfg['targets'] = list(blocco.get('targets') or [])
    cfg['limits'].update({k: v for k, v in (blocco.get('limits') or {}).items() if isinstance(v, int)})
    cfg['glossary'] = dict(blocco.get('glossary') or {})
    return cfg


# --- segmentazione ----------------------------------------------------------------------

def blocchi(testo):
    """Unita' di prosa: (riga, testo, tipo) con tipo in prosa | voce | voce-numerata."""
    righe = testo.splitlines()
    i = 0
    if righe and righe[0].strip() == '---':
        for j in range(1, len(righe)):
            if righe[j].strip() == '---':
                i = j + 1
                break
    fuori, corrente, recinto, in_commento = [], None, None, False

    def chiudi():
        nonlocal corrente
        if corrente and corrente[1].strip():
            fuori.append(tuple(corrente))
        corrente = None

    for n in range(i, len(righe)):
        riga, nr = righe[n], n + 1
        s = riga.strip()
        if recinto:
            if s.startswith(recinto):
                recinto = None
            continue
        if s.startswith('```') or s.startswith('~~~'):
            chiudi()
            recinto = s[:3]
            continue
        if in_commento or s.startswith('<!--'):
            chiudi()
            in_commento = '-->' not in s
            continue
        if not s or s.startswith('#') or s.startswith('|') or re.fullmatch(r'[-*_=]{3,}', s):
            chiudi()
            continue
        s = re.sub(r'^(?:>\s?)+', '', s)
        m = ELENCO.match(s)
        if m:
            chiudi()
            corrente = [nr, m.group(4), 'voce-numerata' if m.group(3) else 'voce']
        elif corrente:
            corrente[1] += ' ' + s
        else:
            corrente = [nr, s, 'prosa']
    chiudi()
    return fuori


def pulisci(testo):
    testo = re.sub(r'\[\^[^\]]*\]', '', testo)
    testo = re.sub(r'`[^`]*`', ' CODICE ', testo)
    testo = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', testo)
    testo = re.sub(r'https?://\S+', ' URL ', testo)
    testo = re.sub(r'(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1', r'\2', testo)
    return re.sub(r'\s+', ' ', testo).strip()


def frasi(testo):
    pezzi, inizio = [], 0
    for m in re.finditer(r'[.!?…]+["»”)\]]*(?=\s+|$)', testo):
        candidato = testo[inizio:m.end()]
        if ABBREVIAZIONI.search(candidato):
            continue
        pezzi.append(candidato.strip())
        inizio = m.end()
    resto = testo[inizio:].strip()
    if resto:
        pezzi.append(resto)
    return [p for p in pezzi if parole(p)]


def parole(frase):
    return re.findall(r"[^\W_]+(?:[-.][^\W_]+)*", frase.replace('’', "'").replace("'", ' '))


def lingua(testo):
    p = [w.lower() for w in parole(testo)]
    punti = {k: sum(w in v for w in p) for k, v in FUNZIONE.items()}
    return 'en' if punti['en'] > punti['it'] else 'it'


# --- regole -----------------------------------------------------------------------------

def analizza(testo, cfg, lang=None):
    lang = lang or lingua(pulisci(testo))
    lim = cfg['limits']
    imperativi = IMPERATIVI[lang]
    glossario = {s.lower(): t for t, sin in cfg['glossary'].items() for s in (sin or [])}
    trovati, n_frasi, n_parole, frasi_ko = [], 0, 0, 0

    for riga, grezzo, tipo in blocchi(testo):
        for c in CONTRAZIONI.finditer(re.sub(r'`[^`]*`', '', grezzo)):
            trovati.append(_f(riga, 'contrazione', c.group(1), None, grezzo))
        elenco = frasi(pulisci(grezzo))
        if tipo == 'prosa' and len(elenco) > lim['paragraph_sentences']:
            trovati.append(_f(riga, 'paragrafo', len(elenco), lim['paragraph_sentences'], grezzo))
        for frase in elenco:
            w = parole(frase)
            n_frasi += 1
            n_parole += len(w)
            prima = len(trovati)
            procedurale = tipo == 'voce-numerata' or w[0].lower() in imperativi
            limite = lim['procedural_words'] if procedurale else lim['descriptive_words']
            if len(w) > limite:
                regola = 'frase-procedurale' if procedurale else 'frase-descrittiva'
                trovati.append(_f(riga, regola, len(w), limite, frase))
            if ';' in frase:
                trovati.append(_f(riga, 'punto-e-virgola', frase.count(';'), 0, frase))
            if procedurale:
                dopo = re.finditer(CONGIUNZIONI[lang] + r'\s+(\w+)', frase, re.I)
                altri = [m.group(1) for m in dopo if m.group(1).lower() in imperativi]
                if altri:
                    trovati.append(_f(riga, 'istruzioni-multiple', 1 + len(altri), 1, frase))
                passivo = PASSIVO[lang].search(frase)
                if passivo:
                    trovati.append(_f(riga, 'passivo-procedura', passivo.group(0), None, frase))
            for parola in {x.lower() for x in w} & set(glossario):
                trovati.append(_f(riga, 'glossario', parola, glossario[parola], frase))
            if len(trovati) > prima:
                frasi_ko += 1

    per_regola = {}
    for t in trovati:
        per_regola[t['regola']] = per_regola.get(t['regola'], 0) + 1
    return {
        'lingua': lang,
        'frasi': n_frasi,
        'parole_medie': round(n_parole / n_frasi, 1) if n_frasi else 0,
        'frasi_conformi': round(1 - frasi_ko / n_frasi, 3) if n_frasi else 1.0,
        'per_regola': dict(sorted(per_regola.items())),
        'violazioni': trovati,
    }


def _f(riga, regola, misura, limite, testo):
    estratto = testo if len(testo) <= 90 else testo[:87] + '...'
    return {'riga': riga, 'regola': regola, 'misura': misura, 'limite': limite, 'testo': estratto}


# --- riga di comando --------------------------------------------------------------------

def stampa(percorso, esito):
    print(f'{percorso}  [{esito["lingua"]}]  frasi: {esito["frasi"]}  parole/frase: '
          f'{esito["parole_medie"]}  conformi: {esito["frasi_conformi"]:.0%}')
    for v in esito['violazioni']:
        lim = f' (limite {v["limite"]})' if v['limite'] not in (None, 0) else ''
        print(f'  r.{v["riga"]:<5} {v["regola"]:<20} {v["misura"]}{lim}  {v["testo"]}')
    if esito['per_regola']:
        print('  totale: ' + ', '.join(f'{k}={n}' for k, n in esito['per_regola'].items()))


def main(argv=None):
    ap = argparse.ArgumentParser(description='Linter STE-lite (EP-076).')
    ap.add_argument('file', nargs='*')
    ap.add_argument('--targets', action='store_true', help='usa i glob di ste_lite.targets')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--strict', action='store_true', help='exit 1 se ci sono violazioni')
    ap.add_argument('--lang', choices=('it', 'en'))
    ap.add_argument('--root', default=RADICE)
    a = ap.parse_args(argv)

    cfg = carica_config(a.root)
    file = list(a.file)
    if a.targets:
        if not cfg['enabled']:
            print('ste_lite.enabled: false — nessun target da controllare (exit 0).')
            return 0
        for g in cfg['targets']:
            file += sorted(glob.glob(os.path.join(a.root, g), recursive=True))
    if not file:
        ap.print_usage(sys.stderr)
        return 2

    esiti = {}
    for f in file:
        if not os.path.isfile(f):
            print(f'file assente: {f}', file=sys.stderr)
            return 2
        with open(f, encoding='utf-8') as fh:
            esiti[f] = analizza(fh.read(), cfg, a.lang)

    if a.json:
        print(json.dumps({'enabled': cfg['enabled'], 'limiti': cfg['limits'], 'file': esiti},
                         ensure_ascii=False, indent=2))
    else:
        if not cfg['enabled']:
            print('nota: ste_lite.enabled: false — invocazione esplicita, il controllo gira lo stesso.')
        for f, e in esiti.items():
            stampa(os.path.relpath(f, a.root) if os.path.isabs(f) else f, e)
    violazioni = sum(len(e['violazioni']) for e in esiti.values())
    return 1 if a.strict and violazioni else 0


if __name__ == '__main__':
    sys.exit(main())
