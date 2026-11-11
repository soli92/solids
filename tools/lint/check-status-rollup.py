#!/usr/bin/env python3
"""check-status-rollup.py — Check 4au: roll-up di stato TSK -> US -> epica e coerenza con sprint.md.

Implementa la norma di `.claude/skills/lint-checks-agent-fleet.md` §Check 4au e i vincoli
V1/V2 con le generalizzazioni G1/G2/G3 (foglia `references/lint-checks-agent-fleet/check-4au.md`).
Tutti i sub-check sono WARNING, mai heal-eligible, mai auto-rollup (R.7).

  4au.1  US non terminale con tutti i TSK terminali
  4au.2  US terminale con almeno un TSK aperto
  4au.3  epica non terminale con tutte le US terminali
  4au.4  epica terminale con almeno una US aperta
  4au.5  status di una riga di sprint.md (l'ultima cella che e' uno stato, qualunque granularita') != frontmatter
  4au.6  US dichiarata nella tabella di un'epica senza file
  4au.7  US il cui `epic:` punta a un'epica che non la elenca (o a un'epica senza file)

Appartenenza (G1): ID con prefisso di namespace opzionale e cartelle con o senza slug, dal
modulo condiviso tools/coordinamento/kanban_ids.py. I TSK di una US sono quelli che la
dichiarano (`story:`/`us:`, in mancanza la cartella) piu' quelli in `tsk_ids`/`tsk_range`;
le US di un'epica quelle con `epic:`/`ep:` (in mancanza la cartella).
V1: frontmatter dai primi 64 KB del file; gli artefatti esclusi per questo sono elencati in una
riga diagnostica, non scompaiono in silenzio.
V2: `in-progress` = `in_progress`; marcatori `*` e `~` tolti dalle celle di sprint.md;
due stati entrambi terminali non sono un disallineamento (scenario 11).

USO:
  python3 tools/lint/check-status-rollup.py [--root <factory>] [--json] [--out <file>] [--strict]

Solo stdlib. Read-only (scrive solo --out). Exit 0 sempre (check WARNING-only).
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_comune as lc  # noqa: E402
from lint_comune import kanban_ids  # noqa: E402

LIMITE_V1 = 65536  # alzato da 4096: ora che il parser si ferma al --- di chiusura, 64 KB e' sufficiente per ogni frontmatter reale (US-264, 4319 byte, era escluso con 4096)
SPRINT = lc.KANBAN + '/sprint.md'
TERMINAL = {'done', 'completed', 'superseded', 'cancelled', 'renamed', 'wontfix'}
OPEN = {'todo', 'in_progress', 'blocked', 'review', 'deferred', 'on_hold'}
CODICE = 'status-rollup'
GRANA = {'EP': 0, 'US': 1, 'TSK': 2}
SUB = ('4au.1', '4au.2', '4au.3', '4au.4', '4au.5', '4au.6', '4au.7')


def norm(stato):
    """Normalizza uno stato: rimuove decorazioni markdown (~~x~~, **x**, `x`) e converte - in _."""
    s = lc.testo_di(stato).strip()
    # Rimuovi decorazioni markdown complete (ordine: strikethrough, bold, backtick)
    s = re.sub(r'~~(.+?)~~', r'\1', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
    s = re.sub(r'`(.+?)`', r'\1', s)
    return s.strip('*~ ').lower().replace('-', '_')


def terminale(stato):
    return norm(stato) in TERMINAL


def aperto(stato):
    return norm(stato) in OPEN


def stato(a):
    v = (a.fm or {}).get('status')
    return lc.testo_di(v).strip() or None


def _w(sub, path, note, extra=()):
    return lc.finding('WARNING', CODICE, sub, path, dettagli=[note] + list(extra), path=path)


def _rollup(padre, figli, sub_chiuso, sub_aperto, etichetta, nome_figli):
    st = stato(padre)
    coppie = [(f, stato(f)) for f in figli]
    coppie = [(f, s) for f, s in coppie if s]
    if st is None or not coppie:
        return []
    out = []
    if all(terminale(s) for _, s in coppie) and not terminale(st):
        out.append(_w(sub_chiuso, padre.rel,
                      '%s status=%s — tutti i %d %s sono terminali' % (etichetta, st, len(coppie), nome_figli)))
    aperti = [(f, s) for f, s in coppie if aperto(s)]
    if terminale(st) and aperti:
        out.append(_w(sub_aperto, padre.rel,
                      '%s status=%s — %d %s ancora aperti:' % (etichetta, st, len(aperti), nome_figli),
                      ['  %s (status=%s)' % (f.rel, s) for f, s in sorted(aperti, key=lambda x: x[0].rel)]))
    return out


def check(radice):
    arts = lc.raccogli_kanban(radice, LIMITE_V1)
    per_tipo = {'EP': [], 'US': [], 'TSK': []}
    per_id = {}
    for a in arts:
        per_tipo[a.tipo].append(a)
        per_id.setdefault(a.id, a)
    findings, diag = [], []

    esclusi = [a.rel for a in arts if a.fm is None and lc.frontmatter(a.path) is not None]
    diag.append('[Passo 1] Raccolti: %d EP, %d US, %d TSK' % tuple(len(per_tipo[t]) for t in ('EP', 'US', 'TSK')))
    if esclusi:
        diag.append('[4au] V1: %d artefatti con frontmatter oltre %d KB esclusi dal roll-up: %s'
                    % (len(esclusi), LIMITE_V1 // 1024, ', '.join(sorted(esclusi))))

    # Passo 2 — 4au.1 / 4au.2: US vs TSK
    tsk_di = {}
    for t in per_tipo['TSK']:
        if t.us:
            tsk_di.setdefault(t.us, set()).add(t.path)
    tsk_per_id = {}
    for t in per_tipo['TSK']:
        tsk_per_id.setdefault(t.id, t)
    per_path = {a.path: a for a in arts}
    for u in per_tipo['US']:
        figli = set(tsk_di.get(u.id, ()))
        for tid in kanban_ids.tsk_dichiarati(u.fm) or ():
            if tid in tsk_per_id:
                figli.add(tsk_per_id[tid].path)
        findings += _rollup(u, [per_path[p] for p in sorted(figli)], '4au.1', '4au.2', 'US', 'TSK')

    # Passo 3 — 4au.3 / 4au.4: epica vs US
    us_di = {}
    for u in per_tipo['US']:
        if u.ep:
            us_di.setdefault(u.ep, []).append(u)
    for e in per_tipo['EP']:
        findings += _rollup(e, sorted(us_di.get(e.id, []), key=lambda x: x.rel), '4au.3', '4au.4', 'Epica', 'US')

    # Passo 4 — 4au.5: sprint.md (G2: status nell'ultima colonna, qualunque granularita')
    sprint = os.path.join(radice, SPRINT)
    if os.path.isfile(sprint):
        dichiarati, forme = {}, {'EP': 0, 'US': 0, 'TSK': 0}
        for line in lc.leggi(sprint).splitlines():
            if not line.lstrip().startswith('|'):
                continue
            cs = [c for c in lc.celle(line) if c]
            if len(cs) < 2:
                continue
            # soggetto: l'ID piu' specifico fra le celle-ID iniziali («| US-1 | TSK-3 | ... | todo |»
            # descrive TSK-3, non US-1); un ID dopo la prima cella non-ID e' un riferimento
            iniziali = []
            for c in cs:
                i = lc.id_in_cella(c)
                if not i:
                    break
                iniziali.append(i)
            if not iniziali:
                continue
            ident = max(iniziali, key=lambda i: GRANA[kanban_ids.tipo_di(i)])
            # lo stato e' l'ultima cella che contiene uno stato riconosciuto (in alcune tabelle sta
            # prima del titolo: «| ID | ... | todo | titolo |»); se nessuna, l'ultima cella.
            # «~~in_progress~~ → done»: vale lo stato dopo la freccia
            celle_pulite = [(re.sub(r'~~.*?~~', '', c).split('→')[-1] if '→' in c and '~~' in c else c)
                            .strip('*~ ').strip() for c in cs[len(iniziali):]]
            stati_noti = TERMINAL | OPEN
            ultima = next((c for c in reversed(celle_pulite) if c and norm(c.split()[0]) in stati_noti),
                          celle_pulite[-1] if celle_pulite else '')
            if not ultima:
                continue
            dichiarati[ident] = ultima
            forme[kanban_ids.tipo_di(ident)] += 1
        letti = sum(forme.values())
        forma = ', '.join('%s-level=%d' % (k, v) for k, v in forme.items() if v) or 'nessuna'
        diag.append('[4au.5] sprint.md: %d righe lette (forma rilevata: %s — status in ultima colonna)' % (letti, forma))
        STATI_NOTI = TERMINAL | OPEN
        non_riconosciuti = []
        for ident in sorted(dichiarati):
            a = per_id.get(ident)
            if a is None or stato(a) is None:
                continue
            nel_sprint = dichiarati[ident]
            s_sprint = norm(nel_sprint.split()[0])
            # Celle con stato non riconosciuto → INFO (non confrontate, evitano rumore da label)
            if s_sprint not in STATI_NOTI:
                non_riconosciuti.append(ident)
                continue
            s_file = norm(stato(a))
            if s_sprint == s_file or (s_sprint in TERMINAL and s_file in TERMINAL):
                continue
            findings.append(_w('4au.5', SPRINT, '%s: sprint.md="%s" vs file="%s" — disallineamento'
                               % (ident, nel_sprint, stato(a))))
        if non_riconosciuti:
            # una riga sola: celle la cui ultima colonna non e' uno stato (note, label), non confrontate
            findings.append(lc.finding('INFO', CODICE, '4au.5', SPRINT, path=SPRINT,
                                       dettagli=['%d righe con ultima colonna che non e\' uno stato, non confrontate '
                                                 '(es. %s)' % (len(non_riconosciuti), ', '.join(non_riconosciuti[:5]))]))
    else:
        diag.append('[4au.5] sprint.md assente: sub-check non eseguito')

    # Passo 5 — 4au.6: US in tabella dell'epica senza file (G3: ID nudo o in link markdown)
    us_ids = {u.id for u in per_tipo['US']}
    solo_prefissati = lc.id_con_prefisso_obbligatorio(arts)
    locali = {}
    for e in per_tipo['EP']:
        for line in e.testo.splitlines():
            if not line.lstrip().startswith('|'):
                continue
            cs = lc.celle(line)
            ident = lc.id_in_cella(cs[0]) if cs else None
            if ident and kanban_ids.tipo_di(ident) == 'US' and ident not in us_ids:
                if solo_prefissati and not kanban_ids.prefisso_di(ident):
                    locali.setdefault(e.rel, []).append(ident)   # numerazione locale dell'epica
                    continue
                findings.append(_w('4au.6', e.rel, '%s dichiarata in tabella ma nessun file trovato in %s/'
                                   % (ident, lc.KANBAN)))
    for rel in sorted(locali):
        findings.append(lc.finding('INFO', CODICE, '4au.6', rel, path=rel,
                                   dettagli=['%d US con ID locale senza prefisso (es. %s): non confrontate con i file'
                                             % (len(locali[rel]), ', '.join(locali[rel][:3]))]))

    # Passo 6 — 4au.7: US con `epic:` che non la elenca
    ep_per_id = {}
    for e in per_tipo['EP']:
        ep_per_id.setdefault(e.id, e)
    for u in sorted(per_tipo['US'], key=lambda x: (x.id, x.rel)):
        rif = kanban_ids.da_frontmatter(u.fm, kanban_ids.CAMPI_EP, 'EP')
        if not rif:
            continue
        e = ep_per_id.get(rif)
        if e is None:
            findings.append(_w('4au.7', u.rel, 'epic: %s — file epica non trovato' % rif))
            continue
        if e.rel in locali:
            continue   # tabella con ID locali: appartenenza non verificabile (INFO per epica, sotto)
        corto = u.id if not kanban_ids.prefisso_di(u.id) else u.id.split('-', 1)[1]
        if any(re.search(r'(?<![\w-])%s(?![\w-])' % re.escape(x), e.testo) for x in {u.id, corto}):
            continue
        cercati = u.id if corto == u.id else "ne' %s ne' %s" % (u.id, corto)
        findings.append(_w('4au.7', u.rel, 'epic: %s — ID non trovato (%s) nella tabella epica '
                           '[potenziale falso positivo se tabella usa ID locali relativi]' % (rif, cercati)))

    for rel in sorted(locali):
        findings.append(lc.finding('INFO', CODICE, '4au.7', rel, path=rel,
                                   dettagli=['tabella US con ID locali (US-NNN): appartenenza delle US non verificabile']))

    conta = {s: 0 for s in SUB}
    for f in findings:
        conta[f['check']] += 1
    diag.append('Riepilogo 4au: ' + ', '.join('%s=%d' % (k, v) for k, v in conta.items()))
    return findings, diag, {'sub_check': conta, 'esclusi_v1': esclusi}


def main(argv=None):
    args = lc.parser(__doc__).parse_args(argv)
    findings, diag, stats = check(args.root)
    return lc.emetti(args, '4au', findings, diag, stats)


if __name__ == '__main__':
    sys.exit(main())
