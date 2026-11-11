#!/usr/bin/env python3
"""Check 4j — TSK aperti degli agenti senza un repository risolvibile.

Il dev-agent risolve il repository su cui lavorare in quest'ordine (Step 2-bis del dev-protocol,
con la regola locale di factory.config.yaml, commento sopra `code_paths`):
  1. `target:` del TSK: nome di una voce di `code_paths`;
  2. `code_path:` del TSK: «.» o un percorso della factory, oppure il percorso di una voce di
     `code_paths`; con `tsk_target_gitmodules: true` un percorso sotto `code_repos/` deve inoltre
     essere un repository dichiarato in `.gitmodules` (o una sua sottocartella);
  3. senza nessuno dei due: le voci di `code_paths` che elencano il layer del TSK in `layers:`,
     valida solo se ce n'e' esattamente una.

Sono soggetti i TSK con `consumer: agent`, status fra quelli aperti (todo, in_progress, review,
blocked) e layer instradato ad `agent` in `routing:`. Il layer vale per il segmento prima di «/».

Codici:
  target-sconosciuto    `target:` non corrisponde a nessuna voce di `code_paths`
  target-layer          la voce di `target:` dichiara `layers:` e il layer del TSK non c'e'
  code-path-assoluto    `code_path:` assoluto (dipende dalla macchina di chi l'ha scritto)
  code-path-senza-repo  `code_path:` sotto code_repos/ che non e' un repository dichiarato
                        (solo con tsk_target_gitmodules: true)
  senza-repo            ne' `target:` ne' `code_path:`, e nessuna voce di `code_paths` per il layer
  target-ambiguo        ne' `target:` ne' `code_path:`, e piu' voci di `code_paths` per il layer

Regola (blocco `lint.kanban` di factory.config.yaml; default spento):
  tsk_target             off | warning | error   severita' dei finding
  tsk_target_gitmodules  true | false (default)   risoluzione via .gitmodules/code_repos/ (opzionale)

Uso:
    python3 tools/lint/check_target_tsk.py [--root R] [--json] [--strict] [--severita S]
Exit code: 0 anche con finding; con --strict 1 se c'e' almeno un ERROR.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_comune as lc  # noqa: E402

CHECK = '4j'
APERTI = ('todo', 'in_progress', 'review', 'blocked')
RADICE_REPO = 'code_repos/'


def _norm(percorso):
    p = lc.testo_di(percorso).strip().strip('"\'').strip()
    while p.startswith('./') and len(p) > 2:
        p = p[2:]
    return p.rstrip('/') or p


def _blocco(testo, chiave):
    m = re.search(r'^%s:[ \t]*\n((?:[ \t]+[^\n]*\n?|[ \t]*\n|#[^\n]*\n)*)' % chiave, testo, re.M)
    return m.group(1) if m else ''


def routing_agent(testo):
    """Layer di `routing:` instradati ad agent."""
    out = set()
    for riga in _blocco(testo, 'routing').splitlines():
        m = re.match(r'^[ \t]+([a-z][\w-]*):\s*([a-z]+)', riga)
        if m and m.group(2) == 'agent':
            out.add(m.group(1))
    return out


def voci_code_paths(testo):
    """[{name, path, layers|None}] dalle voci di `code_paths:` (indentazione a due spazi)."""
    voci = []
    for riga in _blocco(testo, 'code_paths').splitlines():
        if re.match(r'^\s*#', riga):
            continue
        m = re.match(r'^  - name:\s*(\S+)', riga)
        if m:
            voci.append({'name': m.group(1).strip('"\''), 'path': '', 'layers': None})
            continue
        if not voci:
            continue
        m = re.match(r'^    path:\s*(\S+)', riga)
        if m:
            voci[-1]['path'] = _norm(m.group(1))
            continue
        m = re.match(r'^    layers:\s*\[([^\]]*)\]', riga)
        if m:
            voci[-1]['layers'] = [x.strip().strip('"\'') for x in m.group(1).split(',') if x.strip()]
    return voci


def repo_dichiarati(radice):
    gm = os.path.join(radice, '.gitmodules')
    if not os.path.isfile(gm):
        return set()
    return {_norm(p) for p in re.findall(r'^\s*path\s*=\s*(.+?)\s*$', lc.leggi(gm), re.M)}


def _sotto(percorso, basi):
    return any(percorso == b or percorso.startswith(b + '/') for b in basi if b)


def impostazioni(radice):
    cfg = lc.regole_lint(radice)['kanban']
    return {'tsk_target': cfg.get('tsk_target', 'off'),
            'tsk_target_gitmodules': cfg.get('tsk_target_gitmodules', False) is True}


def risolvi(layer, target, code_path, voci, repo, gitmodules=False):
    """None se il repository si risolve, altrimenti (codice, messaggio)."""
    if target:
        voce = next((v for v in voci if v['name'] == target), None)
        if voce is None:
            return 'target-sconosciuto', 'target: %s non corrisponde a nessuna voce di code_paths' % target
        if voce['layers'] is not None and layer not in voce['layers']:
            return 'target-layer', 'la voce %s di code_paths non elenca il layer %s' % (target, layer)
        return None
    if code_path:
        if code_path.startswith('/'):
            return 'code-path-assoluto', 'code_path assoluto (%s): va scritto relativo alla radice' % code_path
        if not gitmodules or not code_path.startswith(RADICE_REPO):
            return None
        if _sotto(code_path, repo | {v['path'] for v in voci}):
            return None
        return 'code-path-senza-repo', 'code_path %s non e\' un repository dichiarato in .gitmodules' % code_path
    candidati = [v['name'] for v in voci if v['layers'] and layer in v['layers']]
    if len(candidati) == 1:
        return None
    if not candidati:
        return 'senza-repo', 'senza target: e code_path:, e nessuna voce di code_paths elenca %s' % layer
    return 'target-ambiguo', 'senza target: e code_path:, e %d voci di code_paths elencano %s (%s)' % (
        len(candidati), layer, ', '.join(candidati))


def verifica(radice, severita=None, impost=None):
    """(finding, stats). `severita` sovrascrive tsk_target se dato (warning|error)."""
    cfg = impost or impostazioni(radice)
    sev = severita or lc.testo_di(cfg['tsk_target']).lower()
    if sev not in ('warning', 'error'):
        return [], {'attivo': False}
    sev = sev.upper()
    percorso_cfg = os.path.join(radice, 'factory.config.yaml')
    testo = lc.leggi(percorso_cfg) if os.path.isfile(percorso_cfg) else ''
    layers, voci, repo = routing_agent(testo), voci_code_paths(testo), repo_dichiarati(radice)
    findings, stats = [], {'attivo': True, 'soggetti': 0, 'risolti': 0}
    for a in lc.raccogli_kanban(radice):
        if a.tipo != 'TSK' or lc.testo_di(a.fm.get('status')) not in APERTI:
            continue
        if lc.testo_di(a.fm.get('consumer')) != 'agent':
            continue
        layer = lc.testo_di(a.fm.get('layer')).split('/')[0].strip()
        if layer not in layers:
            continue
        stats['soggetti'] += 1
        esito = risolvi(layer, lc.testo_di(a.fm.get('target')).strip(), _norm(a.fm.get('code_path')), voci, repo,
                       cfg['tsk_target_gitmodules'])
        if esito is None:
            stats['risolti'] += 1
            continue
        findings.append(lc.finding(sev, esito[0], CHECK, '%s (layer %s): %s.' % (a.id, layer, esito[1]),
                                   path=a.rel))
    return findings, stats


def main(argv=None):
    ap = lc.parser(__doc__)
    ap.add_argument('--severita', choices=['warning', 'error'],
                    help='sovrascrive tsk_target (utile per misurare a regola spenta)')
    args = ap.parse_args(argv)
    args.root = os.path.abspath(args.root)
    findings, stats = verifica(args.root, args.severita)
    diag = []
    if not stats['attivo']:
        diag.append('[%s] regola spenta (lint.kanban.tsk_target: off)' % CHECK)
    elif not findings:
        diag.append('[%s] OK — %d TSK aperti degli agenti, tutti con un repository risolvibile' % (
            CHECK, stats['soggetti']))
    return lc.emetti(args, CHECK, findings, diag, stats)


if __name__ == '__main__':
    sys.exit(main())
