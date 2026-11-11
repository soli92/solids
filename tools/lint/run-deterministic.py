#!/usr/bin/env python3
"""run-deterministic.py — esegue in un colpo i check di /lint che hanno un'implementazione eseguibile.

Per questi check l'esecutore del lint (wiki-lint) riporta le righe prodotte, senza ricostruirle,
stimarle o campionarle. I check non elencati restano a lettura (2 citazioni, 4c-4f config,
4g scheduler, 4m risk, citation audit, ...).

  1, 4, 4ag   struttura wiki: orphan, broken-link, storie collegate, staleness  check-wiki-structure.py
  3, 4as, 4b  integrita' kanban, assignee, question                            check-kanban-integrity.py
  4au         roll-up di stato TSK -> US -> epica e sprint.md                  check-status-rollup.py
  4am         coerenza delle versioni dichiarate                               check-version-coherence.py
  4ar         annotazioni SUNSET scadute                                       check-expired-sunset.py
  4aq         path portabili su Windows (git ls-files della factory)           check-portable-paths.py
  4ax         ignore = dirty sui submodule (.gitmodules letto come testo)       check-submodule-ignore.py
  4bb         wiki/log.md append-only (detective, ultimo commit del log)       check-log-append-guard.py
  4bc         chiusure dei gap non verificate sulla wiki                        check-gap-closures.py
  4bd         wiki/gaps.md append-only (detective, ultimo commit dei gap)       check-gaps-append-guard.py
  4be         date di lavoro dei TSK (started_at/closed_at) dalla data di adozione  check-date-lavoro.py
  4bf, 4bg    ordine di wiki/log.md e contatore «## Sources (N)» dell'index    check_dati_derivati.py
  4bh         TSK be done senza evidenza di test (TSK qa con ## Esito), default off  check_evidenza_test_be.py
  4j          TSK aperti degli agenti senza repository risolvibile, default off      check_target_tsk.py
  (locali)    check della sola factory, dichiarati in tools/lint/checks_locali.py

USO:
  python3 tools/lint/run-deterministic.py                       # riepilogo + righe per check (markdown)
  python3 tools/lint/run-deterministic.py --json
  python3 tools/lint/run-deterministic.py --out wiki/lint/YYYY-MM-DD-deterministic.md
  python3 tools/lint/run-deterministic.py --root <factory> --solo 1,3,4au   # solo alcuni gruppi
  python3 tools/lint/run-deterministic.py --oggi YYYY-MM-DD     # data di riferimento di 4ag

Solo stdlib. Read-only: scrive solo il file di --out. Exit 0 sempre (il lint riporta, non
blocca); con --strict exit 1 se almeno un check segnala ERROR o termina con errore.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_comune as lc  # noqa: E402

QUI = os.path.dirname(os.path.abspath(__file__))

# (check coperti, descrizione, script, argomenti; {root} e {oggi} sostituiti a runtime)
CHECKS = [
    (('1', '4', '4ag'), 'Struttura wiki: orphan, broken-link, storie collegate, staleness',
     'check-wiki-structure.py', ['--root', '{root}', '--oggi', '{oggi}']),
    (('3', '4as', '4b'), "Integrita' kanban, assignee, question",
     'check-kanban-integrity.py', ['--root', '{root}']),
    (('4au',), 'Roll-up di stato TSK -> US -> epica e sprint.md',
     'check-status-rollup.py', ['--root', '{root}']),
    (('4am',), 'Coerenza delle versioni dichiarate',
     'check-version-coherence.py', ['--root', '{root}']),
    (('4ar',), 'Annotazioni SUNSET scadute',
     'check-expired-sunset.py', ['{root}']),
    (('4aq',), 'Path portabili su Windows',
     'check-portable-paths.py', []),
    (('4ax',), 'ignore = dirty sui submodule di .gitmodules',
     'check-submodule-ignore.py', ['{root}']),
    (('4bb',), 'wiki/log.md append-only (ultimo commit che lo tocca)',
     'check-log-append-guard.py', ['{root}']),
    (('4bc',), 'Chiusure dei gap verificate sulla wiki',
     'check-gap-closures.py', ['{root}']),
    (('4bd',), 'wiki/gaps.md append-only (ultimo commit che lo tocca)',
     'check-gaps-append-guard.py', ['{root}']),
    (('4be',), 'Date di lavoro dei TSK (started_at, closed_at) dalla data di adozione',
     'check-date-lavoro.py', ['{root}']),
    (('4bf', '4bg'), "Ordine delle voci di wiki/log.md e contatore Sources dell'index",
     'check_dati_derivati.py', ['{root}']),
    (('4bh',), 'Evidenza di test sui TSK layer be chiusi (regola lint.kanban.be_test_evidence)',
     'check_evidenza_test_be.py', ['--root', '{root}']),
    (('4j',), 'Repository risolvibile sui TSK aperti degli agenti (regola lint.kanban.tsk_target)',
     'check_target_tsk.py', ['--root', '{root}']),
]
SEV = re.compile(r'^\s*(?:-\s*)?\[?(ERROR|WARNING|INFO)[\]\s]')
LOCALI = 'tools/lint/checks_locali.py'


def checks_locali(radice):
    """Check della sola factory, in `tools/lint/checks_locali.py` (file che il master non ha, quindi
    mai in conflitto all'upgrade): una lista `CHECKS` nella stessa forma, con lo script relativo
    alla radice della factory. Un file illeggibile e' un errore esplicito, non un silenzio."""
    p = os.path.join(radice, LOCALI)
    if not os.path.isfile(p):
        return []
    ns = {}
    exec(compile(lc.leggi(p), p, 'exec'), ns)  # file della factory stessa, non input esterno
    return [(tuple(ids), nome, script, list(arg)) for ids, nome, script, arg in ns['CHECKS']]


def esegui(script, argomenti, radice, oggi):
    # script con un path (check locali) relativo alla radice della factory, altrimenti accanto al runner
    percorso = os.path.join(radice, script) if '/' in script else os.path.join(QUI, script)
    cmd = [sys.executable, percorso] + [a.format(root=radice, oggi=oggi) for a in argomenti]
    r = subprocess.run(cmd, cwd=radice, capture_output=True, text=True)
    righe = (r.stdout + r.stderr).rstrip().splitlines()
    conta = {s: 0 for s in lc.SEVERITA}
    for line in righe:
        m = SEV.match(line)
        if m:
            conta[m.group(1)] += 1
    # script che segnala solo con l'exit code: un errore resta un errore, non un silenzio
    if r.returncode != 0 and conta['ERROR'] == 0:
        conta['ERROR'] = 1
    mostrato = 'python3 %s %s' % (script if '/' in script else 'tools/lint/' + script,
                                  ' '.join(a.format(root='.', oggi=oggi) for a in argomenti))
    return {'exit': r.returncode, 'conteggi': conta, 'output': righe, 'comando': mostrato.strip()}


def main(argv=None):
    ap = lc.parser(__doc__)
    ap.add_argument('--solo', help='gruppi da eseguire, per ID di check (es. 1,3,4au)')
    ap.add_argument('--oggi', help='data di riferimento per 4ag (YYYY-MM-DD, default: oggi)')
    args = ap.parse_args(argv)
    oggi = args.oggi or dt.date.today().isoformat()
    radice = os.path.abspath(args.root)
    voluti = {x.strip() for x in args.solo.split(',')} if args.solo else None
    risultati = []
    for ids, nome, script, argomenti in CHECKS + checks_locali(radice):
        if voluti is not None and not (voluti & set(ids)):
            continue
        r = esegui(script, argomenti, radice, oggi)
        risultati.append(dict(check=', '.join(ids), nome=nome, **r))

    tot = {s: sum(r['conteggi'][s] for r in risultati) for s in lc.SEVERITA}
    if args.json:
        testo = json.dumps({'oggi': oggi, 'totale': tot, 'risultati': risultati}, indent=2, ensure_ascii=False)
    else:
        out = ['## Check eseguiti da script', '',
               'Data di riferimento: %s. Comando: `python3 tools/lint/run-deterministic.py`.' % oggi, '',
               '| Check | Cosa | ERROR | WARNING | INFO | Exit |', '|---|---|---|---|---|---|']
        for r in risultati:
            c = r['conteggi']
            out.append('| %s | %s | %d | %d | %d | %d |' % (r['check'], r['nome'], c['ERROR'], c['WARNING'],
                                                            c['INFO'], r['exit']))
        out += ['', '**Totale script**: %d ERROR, %d WARNING, %d INFO' % (tot['ERROR'], tot['WARNING'], tot['INFO']), '']
        for r in risultati:
            out += ['### %s — %s' % (r['check'], r['nome']), '', '`%s`' % r['comando'], '', '```']
            out += r['output'] or ['(nessun output)']
            out += ['```', '']
        testo = '\n'.join(out)
    print(testo)
    if args.out:
        lc.scrivi_out(radice, args.out, testo)
    return 1 if args.strict and tot['ERROR'] else 0


if __name__ == '__main__':
    sys.exit(main())
