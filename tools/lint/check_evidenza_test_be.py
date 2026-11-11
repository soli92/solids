#!/usr/bin/env python3
"""Check 4bh — TSK `layer: be` chiusi senza evidenza di test automatici.

Un TSK di sviluppo BE `done` ha evidenza quando esiste un TSK `layer: qa` `done` che lo ha in
`depends_on` e la cui sezione «## Esito» riporta, in forma verificabile da macchina:
  - il comando eseguito (testo fra apici inversi);
  - il codice di uscita («codice di uscita 0», «exit 0»);
  - i test saltati a zero («0 saltati», «saltati: 0», «0 skipped»);
  - il percorso del report («report»);
  - almeno uno SHA (7-40 cifre esadecimali).

Non sono soggetti al check: i TSK non `done` (quindi anche `cancelled` e `superseded`), i TSK
chiusi prima della data di adozione, i TSK il cui `consumer` non e' fra quelli soggetti, e i TSK
che dichiarano `be_test_evidence: na` (nessun codice da provare) con un motivo non vuoto in
`be_test_evidence_reason`. Senza motivo l'esenzione non vale: il TSK resta soggetto e si aggiunge il
finding `be-na-senza-motivo`. La chiave e' dedicata: `test_evidence` ha un altro significato
(prova dell'esecuzione del caso) e non esenta dal check.

Regole (blocco `lint.kanban` di factory.config.yaml; default = spento):
  be_test_evidence            off | warning | error   severita' dei finding (default off)
  be_test_evidence_consumers  lista di consumer soggetti (default [agent]; [agent, human] per
                              estenderlo ai TSK BE umani)
  be_test_evidence_since      data AAAA-MM-GG: i TSK chiusi prima non sono soggetti
                              (data di chiusura = closed_at, in mancanza updated)

Uso:
    python3 tools/lint/check_evidenza_test_be.py [--root R] [--json] [--strict] [--severita S]
Exit code: 0 anche con finding; con --strict 1 se c'e' almeno un ERROR.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_comune as lc  # noqa: E402

CHECK = '4bh'
SEZIONE_ESITO = re.compile(r'^##\s+Esito\s*$(.*?)(?=^##\s|\Z)', re.M | re.S)
ELEMENTI = [
    ('comando', re.compile(r'`[^`\n]+`')),
    ('codice di uscita', re.compile(r'(?:codice di uscita|exit(?: code)?|uscita)\s*[:=]?\s*`?-?\d', re.I)),
    ('test saltati a zero', re.compile(r'(?:\b0\s+(?:test\s+)?(?:saltat\w*|skipped)|(?:saltat\w*|skipped)\s*[:=]?\s*0\b)', re.I)),
    ('report', re.compile(r'report', re.I)),
    ('SHA', re.compile(r'\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b')),
]
DEFAULT = {'be_test_evidence': 'off', 'be_test_evidence_consumers': ['agent'], 'be_test_evidence_since': ''}


def impostazioni(radice):
    cfg = lc.regole_lint(radice)['kanban']
    return {k: cfg.get(k, v) for k, v in DEFAULT.items()}


def _lista(v):
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)] if v else []


def _layer(a):
    return lc.testo_di(a.fm.get('layer')).split('/')[0].strip()


def data_chiusura(a):
    return lc.testo_di(a.fm.get('closed_at') or a.fm.get('updated')).strip()


def elementi_mancanti(testo):
    m = SEZIONE_ESITO.search(testo)
    if not m:
        return ['sezione «## Esito»']
    sez = m.group(1)
    return [nome for nome, rx in ELEMENTI if not rx.search(sez)]


def verifica(radice, severita=None, impost=None):
    """(finding, stats). `severita` sovrascrive be_test_evidence se dato (warning|error)."""
    cfg = impost or impostazioni(radice)
    sev = severita or lc.testo_di(cfg['be_test_evidence']).lower()
    if sev not in ('warning', 'error'):
        return [], {'attivo': False}
    sev = sev.upper()
    consumer = set(_lista(cfg['be_test_evidence_consumers']))
    dal = lc.testo_di(cfg['be_test_evidence_since']).strip()
    tsk = [a for a in lc.raccogli_kanban(radice) if a.tipo == 'TSK']
    qa_per_dipendenza = {}
    for a in tsk:
        if _layer(a) == 'qa':
            for dip in _lista(a.fm.get('depends_on')):
                qa_per_dipendenza.setdefault(dip.strip(), []).append(a)
    findings, stats = [], {'attivo': True, 'be_done': 0, 'soggetti': 0, 'con_evidenza': 0, 'esenti_data': 0,
                           'esenti_consumer': 0, 'esenti_na': 0}
    for a in tsk:
        if _layer(a) != 'be' or lc.testo_di(a.fm.get('status')) != 'done':
            continue
        stats['be_done'] += 1
        na = lc.testo_di(a.fm.get('be_test_evidence')).strip().lower() == 'na'
        motivo = lc.testo_di(a.fm.get('be_test_evidence_reason')).strip()
        if na and motivo:
            stats['esenti_na'] += 1
            continue
        if lc.testo_di(a.fm.get('consumer')) not in consumer:
            stats['esenti_consumer'] += 1
            continue
        chiuso = data_chiusura(a)
        if dal and (not chiuso or chiuso < dal):
            stats['esenti_data'] += 1
            continue
        stats['soggetti'] += 1
        if na:
            findings.append(lc.finding(sev, 'be-na-senza-motivo', CHECK,
                '%s (layer be, done): be_test_evidence: na richiede un motivo in be_test_evidence_reason; '
                'senza motivo l\'esenzione non vale.' % a.id, path=a.rel))
        qa = qa_per_dipendenza.get(a.id, [])
        chiusi = [q for q in qa if lc.testo_di(q.fm.get('status')) == 'done']
        if not qa:
            findings.append(lc.finding(sev, 'be-senza-tsk-qa', CHECK,
                '%s (layer be, done) non ha un TSK qa che lo abbia in depends_on.' % a.id, path=a.rel))
        elif not chiusi:
            findings.append(lc.finding(sev, 'be-tsk-qa-aperto', CHECK,
                '%s (layer be, done): il TSK qa %s non e\' done.' % (a.id, ', '.join(q.id for q in qa)),
                path=a.rel))
        else:
            mancanti = [elementi_mancanti(q.testo) for q in chiusi]
            if any(not m for m in mancanti):
                stats['con_evidenza'] += 1
            else:
                best = min(zip(mancanti, chiusi), key=lambda x: len(x[0]))
                findings.append(lc.finding(sev, 'be-evidenza-incompleta', CHECK,
                    '%s (layer be, done): l\'Esito di %s non riporta: %s.' % (a.id, best[1].id, ', '.join(best[0])),
                    path=best[1].rel))
    return findings, stats


def main(argv=None):
    ap = lc.parser(__doc__)
    ap.add_argument('--severita', choices=['warning', 'error'],
                    help='sovrascrive be_test_evidence (utile per misurare a regola spenta)')
    args = ap.parse_args(argv)
    args.root = os.path.abspath(args.root)
    findings, stats = verifica(args.root, args.severita)
    diag = []
    if not stats['attivo']:
        diag.append('[%s] regola spenta (lint.kanban.be_test_evidence: off)' % CHECK)
    elif not findings:
        diag.append('[%s] OK — %d TSK BE soggetti, tutti con evidenza' % (CHECK, stats['soggetti']))
    return lc.emetti(args, CHECK, findings, diag, stats)


if __name__ == '__main__':
    sys.exit(main())
