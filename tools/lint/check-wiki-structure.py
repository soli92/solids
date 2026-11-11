#!/usr/bin/env python3
"""check-wiki-structure.py — Check 1 (orphan + wikilink), Check 4 (wiki ↔ kanban), Check 4ag (staleness).

Implementa le regole di `.claude/skills/lint-checks-wiki-structure.md` cosi' come sono scritte,
su tutta la popolazione (full-scan, mai campione).

Check 1
  popolazione  wiki/**/*.md esclusi log.md (e gli archivi wiki/log-*.md), index.md, wiki/query/, wiki/lint/
  orphan       pagina non linkata da wiki/index.md ([[slug]] o link markdown)   → WARNING
  broken-link  [[target]] senza un file wiki con slug (nome file) o path corrispondente → ERROR
               (si leggono le pagine della popolazione e wiki/index.md; `|alias` e `#ancora` ignorati;
               codice fra backtick e blocchi ``` non analizzati)
               heal-eligible se esiste uno slug con similarita' >= 0.90 (heal-protocol)
Check 4
  story-missing  ID di US nella sezione «## Storie collegate» senza file nel kanban → ERROR
  (la verifica «ogni US referenzia una pagina wiki esistente» e' broken-wiki-page del Check 3)
Check 4ag (always-on)
  popolazione  wiki/**/*.md esclusi log.md (e archivi), index.md, wiki/lint/, wiki/sources/
  data         `updated:`, o `created:` se `updated:` manca
  > 365 giorni → WARNING STALE · > 180 → INFO · nessuna data leggibile → WARNING MISSING-DATE

USO:
  python3 tools/lint/check-wiki-structure.py [--root <factory>] [--json] [--out <file>] [--strict]
                                             [--oggi YYYY-MM-DD]

Solo stdlib. Read-only (scrive solo --out). Exit 0 sempre; con --strict exit 1 se c'e' un ERROR.
"""
from __future__ import annotations

import datetime as dt
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_comune as lc  # noqa: E402
from lint_comune import kanban_ids  # noqa: E402

WIKILINK = re.compile(r'\[\[([^\]]+)\]\]')


def senza_codice(testo):
    """Il codice non contiene wikilink: blocchi ``` e codice fra backtick tolti prima dell'analisi
    (`new Map([['k', 'v']])` in un esempio JS e la sintassi `[[name]]` citata non sono link)."""
    testo = re.sub(r'```.*?```', '', testo, flags=re.S)
    return re.sub(r'`[^`\n]*`', '', testo)
MDLINK = re.compile(r'\]\(([^)\s#]+?\.md)(?:#[^)]*)?\)')
SOGLIA_HEAL = 0.90


def _wiki(radice):
    base = os.path.join(radice, 'wiki')
    files = []
    for d, dirnames, fs in os.walk(base):
        dirnames.sort()
        for f in sorted(fs):
            if f.endswith('.md'):
                files.append(os.path.relpath(os.path.join(d, f), radice).replace(os.sep, '/'))
    return files


def _in(p, escluse_dir):
    # wiki/log.md e i suoi archivi di rotazione (wiki/log-AAAA-MM-GG.md, log-AAAA-QN.md): append-only
    base = os.path.basename(p)
    archivio = p.count('/') == 1 and re.match(r'^log-[\w-]+\.md$', base)
    return base not in ('log.md', 'index.md') and not archivio and not any(
        p.startswith('wiki/%s/' % d) for d in escluse_dir)


def _data(fm, campi=('updated', 'created')):
    """Default (master): `updated`, o `created` se manca. Con piu' campi dichiarati in
    lint.wiki.date_fields vale la data piu' recente fra quelli leggibili."""
    if tuple(campi) == ('updated', 'created'):
        for k in campi:
            v = lc.testo_di((fm or {}).get(k)).strip()
            if v:
                m = re.match(r'^(\d{4}-\d{2}-\d{2})', v)
                if not m:
                    return None
                try:
                    return dt.date.fromisoformat(m.group(1))
                except ValueError:
                    return None
        return None
    date = []
    for k in campi:
        v = (fm or {}).get(k)
        for x in (v if isinstance(v, list) else [v]):  # `rotated_at: [2026-09-25, 2026-10-07]`
            m = re.match(r'^(\d{4}-\d{2}-\d{2})', lc.testo_di(x).strip())
            if m:
                try:
                    date.append(dt.date.fromisoformat(m.group(1)))
                except ValueError:
                    pass
    return max(date) if date else None


def check(radice, oggi):
    files = _wiki(radice)
    testo = {p: lc.leggi(os.path.join(radice, p)) for p in files}
    per_rel = {p[len('wiki/'):-3].lower(): p for p in files}
    per_slug = {}
    for p in files:
        per_slug.setdefault(os.path.basename(p)[:-3].lower(), p)

    def risolvi(grezzo):
        t = grezzo.split('|')[0].split('#')[0].strip().lower()
        if not t:
            return ''
        if t.startswith('wiki/'):
            t = t[len('wiki/'):]
        if t.endswith('.md'):
            t = t[:-3]
        return per_rel.get(t) or per_slug.get(os.path.basename(t))

    findings, diag = [], []
    regole = lc.regole_lint(radice)['wiki']
    pop1 = [p for p in files if _in(p, ('query', 'lint'))]

    # Check 1 — orphan: linkata da wiki/index.md
    linkate = set()
    if 'wiki/index.md' in testo:
        idx = testo['wiki/index.md']
        for m in WIKILINK.finditer(senza_codice(idx)):
            r = risolvi(m.group(1))
            if r:
                linkate.add(r)
        for m in MDLINK.finditer(idx):
            linkate.add(os.path.normpath(os.path.join('wiki', m.group(1))).replace(os.sep, '/'))
    else:
        diag.append('[1] wiki/index.md assente: ogni pagina risulta orphan')
    if regole['orphan'] == 'reachability' and 'wiki/index.md' in testo:
        # raggiungibile da wiki/index.md seguendo wikilink e link markdown: i sotto-indici contano
        visti, coda = set(linkate), list(linkate)
        while coda:
            q = coda.pop()
            if q not in testo:
                continue
            for m in WIKILINK.finditer(senza_codice(testo[q])):
                r = risolvi(m.group(1))
                if r and r not in visti:
                    visti.add(r)
                    coda.append(r)
            for m in MDLINK.finditer(testo[q]):
                r = os.path.normpath(os.path.join(os.path.dirname(q), m.group(1))).replace(os.sep, '/')
                if r not in visti:
                    visti.add(r)
                    coda.append(r)
        linkate = visti
        nota_orfana = 'non raggiungibile da wiki/index.md'
    else:
        nota_orfana = 'non linkata da wiki/index.md'
    orfane = [p for p in pop1 if p not in linkate]
    for p in orfane:
        findings.append(lc.finding('WARNING', 'orphan', '1', '%s — %s' % (p, nota_orfana), path=p))

    # Check 1 — broken-link
    rotti = 0
    slugs = sorted(per_slug)
    for p in pop1 + (['wiki/index.md'] if 'wiki/index.md' in testo else []):
        for m in WIKILINK.finditer(senza_codice(testo[p])):
            if risolvi(m.group(1)) is not None:
                continue
            rotti += 1
            bersaglio = os.path.basename(m.group(1).split('|')[0].split('#')[0].strip().lower())
            vicino = difflib.get_close_matches(bersaglio, slugs, n=1, cutoff=SOGLIA_HEAL)
            heal = bool(vicino)
            nota = ' (heal-eligible: -> [[%s]], %.2f)' % (
                vicino[0], difflib.SequenceMatcher(None, bersaglio, vicino[0]).ratio()) if heal else ''
            append_only = p == 'wiki/gaps.md' and regole['append_only_links'] == 'info'
            findings.append(lc.finding('INFO' if append_only else 'ERROR', 'broken-link', '1',
                                       '%s — [[%s]] non risolve%s%s' % (p, m.group(1), nota,
                                                                         ' (append-only: non si corregge)' if append_only else ''),
                                       path=p, heal_eligible=heal and not append_only))
    diag.append('Check 1 completato su %d file — %d orphan rilevati, %d broken-link rilevati'
                % (len(pop1), len(orfane), rotti))

    # Check 4 — «## Storie collegate» con sole storie esistenti
    arts_k = lc.raccogli_kanban(radice)
    us_ids = {a.id for a in arts_k if a.tipo == 'US'}
    solo_prefissati = lc.id_con_prefisso_obbligatorio(arts_k)
    sezioni = 0
    for p in pop1:
        sec = re.search(r'^## Storie collegate[ \t]*\n(.*?)(?=^## |\Z)', testo[p], re.S | re.M)
        if not sec:
            continue
        sezioni += 1
        citate = {i for i in kanban_ids.ID_IN_TESTO.findall(sec.group(1)) if kanban_ids.tipo_di(i) == 'US'
                  and not (solo_prefissati and not kanban_ids.prefisso_di(i))}  # senza prefisso = locale
        for us in sorted(citate - us_ids):
            findings.append(lc.finding('ERROR', 'story-missing', '4',
                                       '%s — %s in «## Storie collegate» senza file kanban' % (p, us), path=p))
    diag.append('Check 4 completato su %d sezioni «Storie collegate»' % sezioni)

    # Check 4ag — staleness
    pop4 = [p for p in files if _in(p, ('lint', 'sources'))]
    conta = {'STALE': 0, 'INFO': 0, 'MISSING-DATE': 0}
    for p in pop4:
        d = _data(lc.frontmatter_da_testo(testo[p]), tuple(regole['date_fields']))
        if d is None:
            conta['MISSING-DATE'] += 1
            findings.append(lc.finding('WARNING', 'staleness', '4ag', 'MISSING-DATE: %s' % p, path=p))
            continue
        eta = (oggi - d).days
        if eta > 365:
            conta['STALE'] += 1
            findings.append(lc.finding('WARNING', 'staleness', '4ag', 'STALE: %s — ultimo aggiornamento %d giorni fa '
                                       '(soglia: 365)' % (p, eta), path=p))
        elif eta > 180:
            conta['INFO'] += 1
            findings.append(lc.finding('INFO', 'staleness', '4ag', 'INFO: %s — non aggiornata da %d giorni (soglia: 180)'
                                       % (p, eta), path=p))
    diag.append('Check 4ag completato su %d file (oggi=%s) — %d MISSING-DATE, %d STALE, %d INFO'
                % (len(pop4), oggi.isoformat(), conta['MISSING-DATE'], conta['STALE'], conta['INFO']))
    stats = {'check1_file': len(pop1), 'orphan': len(orfane), 'broken_link': rotti,
             'check4_sezioni': sezioni, 'check4ag_file': len(pop4), 'check4ag': conta, 'oggi': oggi.isoformat()}
    return findings, diag, stats


def main(argv=None):
    ap = lc.parser(__doc__)
    ap.add_argument('--oggi', help='data di riferimento per 4ag (YYYY-MM-DD, default: oggi)')
    args = ap.parse_args(argv)
    oggi = dt.date.fromisoformat(args.oggi) if args.oggi else dt.date.today()
    findings, diag, stats = check(args.root, oggi)
    return lc.emetti(args, '1, 4, 4ag', findings, diag, stats)


if __name__ == '__main__':
    sys.exit(main())
