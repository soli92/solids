#!/usr/bin/env python3
"""Verifica oggettiva che una Tavola Rotonda abbia lanciato davvero i partecipanti.

    python3 tools/tavola-rotonda/verifica-lanci.py --registro <registro .md> --sessione <id>
    python3 tools/tavola-rotonda/verifica-lanci.py --agent-id <id del moderatore> [--sessione <id>]
    python3 tools/tavola-rotonda/verifica-lanci.py --trascrizione <file .jsonl>

--registro (flusso ADR-EP073-001, partecipanti lanciati dalla sessione principale): legge la lista
`lanci` ({agente, fase, round, agent_id}) dal frontmatter del registro e, per ogni voce, cerca la
trascrizione ~/.claude/projects/<progetto>/<sessione>/subagents/agent-<agent_id>.jsonl e il
tipo di agente nel .meta.json accanto. Esito `multi-agente` solo con almeno due agenti distinti,
tutti i lanci con trascrizione e tipo coincidente; altrimenti `non valido`.

--agent-id / --trascrizione (sessioni precedenti ad ADR-EP073-001, moderatore che lanciava da solo):
conta nella trascrizione del moderatore i tool_use con cui ha lanciato altri agenti (`Agent` o
`Task`). Esito `multi-agente` con almeno un lancio, altrimenti `simulato`.

In entrambi i casi la verifica non dipende da cio' che il registro dichiara sul proprio conto.
Uscita: JSON su stdout. Codice 0 = multi-agente, 1 = simulato / non valido, 2 = trascrizione o
registro non trovati o non leggibili.
"""
import argparse
import collections
import glob
import json
import os
import sys

STRUMENTI_LANCIO = {'Agent', 'Task'}


def trova_trascrizione(agent_id, sessione=None, radice=None):
    radice = radice or os.path.expanduser('~/.claude/projects')
    schema = os.path.join(radice, '*', sessione or '*', 'subagents', 'agent-%s.jsonl' % agent_id)
    trovate = sorted(glob.glob(schema))
    return trovate[0] if len(trovate) == 1 else (None if not trovate else trovate)


def frontmatter(path):
    testo = open(path, encoding='utf-8', errors='replace').read()
    if not testo.startswith('---'):
        return None
    fine = testo.find('\n---', 3)
    if fine < 0:
        return None
    import yaml  # usato solo in modalita' --registro
    dati = yaml.safe_load(testo[3:fine]) or {}
    return dati if isinstance(dati, dict) else None


def verifica_registro(lanci, trova):
    """Esito della verifica dei lanci dichiarati nel registro. `trova(agent_id)` restituisce
    (path trascrizione o None, tipo di agente dal .meta.json o None). Funzione pura."""
    verificati, mancanti, tipo_diverso = [], [], []
    for voce in lanci or []:
        aid = str((voce or {}).get('agent_id') or '').strip()
        agente = str((voce or {}).get('agente') or '').strip()
        if not aid:
            mancanti.append({'agente': agente, 'agent_id': None, 'motivo': 'agent_id assente'})
            continue
        path, tipo = trova(aid)
        if not path:
            mancanti.append({'agente': agente, 'agent_id': aid, 'motivo': 'trascrizione non trovata'})
        elif tipo != agente:
            tipo_diverso.append({'agente': agente, 'agent_id': aid, 'tipo_trascrizione': tipo})
        else:
            verificati.append({'agente': agente, 'agent_id': aid, 'fase': voce.get('fase'), 'round': voce.get('round')})
    distinti = sorted({v['agente'] for v in verificati})
    valido = len(distinti) >= 2 and not mancanti and not tipo_diverso
    return {'dichiarati': len(lanci or []), 'verificati': len(verificati), 'agenti_distinti': distinti,
            'mancanti': mancanti, 'tipo_diverso': tipo_diverso,
            'verdetto': 'multi-agente' if valido else 'non valido'}


def trova_per_sessione(sessione, radice=None):
    radice = radice or os.path.expanduser('~/.claude/projects')

    def trova(agent_id):
        trovate = sorted(glob.glob(os.path.join(radice, '*', sessione, 'subagents', 'agent-%s.jsonl' % agent_id)))
        if len(trovate) != 1:
            return None, None
        meta = trovate[0][:-len('.jsonl')] + '.meta.json'
        tipo = None
        if os.path.exists(meta):
            try:
                tipo = json.load(open(meta, encoding='utf-8')).get('agentType')
            except ValueError:
                tipo = None
        return trovate[0], tipo
    return trova


def conta(righe):
    """Conteggio dei tool_use del moderatore e dettaglio dei lanci (funzione pura su righe jsonl)."""
    strumenti = collections.Counter()
    lanci = []
    for riga in righe:
        try:
            evento = json.loads(riga)
        except ValueError:
            continue
        messaggio = evento.get('message') or {}
        if messaggio.get('role') != 'assistant':
            continue
        for blocco in messaggio.get('content') or []:
            if not isinstance(blocco, dict) or blocco.get('type') != 'tool_use':
                continue
            strumenti[blocco.get('name')] += 1
            if blocco.get('name') in STRUMENTI_LANCIO:
                ingresso = blocco.get('input') or {}
                lanci.append({'subagent_type': ingresso.get('subagent_type'),
                              'descrizione': (ingresso.get('description') or '')[:80]})
    return {'strumenti': dict(sorted(strumenti.items())), 'lanci': len(lanci), 'dettaglio_lanci': lanci}


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--registro', help='registro wiki/decisions/tavola-rotonda-*.md con la lista `lanci` (ADR-EP073-001)')
    g.add_argument('--agent-id', help='id del subagente moderatore (restituito dal lancio)')
    g.add_argument('--trascrizione', help='percorso esplicito del file .jsonl')
    ap.add_argument('--sessione', help='id della sessione principale (restringe la ricerca)')
    ap.add_argument('--radice', help='cartella dei progetti Claude Code (default ~/.claude/projects)')
    a = ap.parse_args(argv)

    if a.registro:
        if not a.sessione:
            print(json.dumps({'errore': '--registro richiede --sessione (id della sessione principale)'}))
            return 2
        try:
            fm = frontmatter(a.registro)
        except (OSError, ImportError, ValueError) as exc:
            print(json.dumps({'errore': 'registro non leggibile: %s' % exc}, ensure_ascii=False))
            return 2
        if fm is None:
            print(json.dumps({'errore': 'registro senza frontmatter', 'registro': a.registro}, ensure_ascii=False))
            return 2
        esito = verifica_registro(fm.get('lanci'), trova_per_sessione(a.sessione, a.radice))
        esito['registro'] = a.registro
        esito['partecipanti_lanciati_dichiarati'] = fm.get('partecipanti_lanciati')
        print(json.dumps(esito, ensure_ascii=False, indent=1))
        return 0 if esito['verdetto'] == 'multi-agente' else 1

    path = a.trascrizione or trova_trascrizione(a.agent_id, a.sessione, a.radice)
    if isinstance(path, list):
        print(json.dumps({'errore': 'piu\' trascrizioni per lo stesso agent-id: passare --sessione',
                          'trovate': path}, ensure_ascii=False))
        return 2
    if not path or not os.path.exists(path):
        print(json.dumps({'errore': 'trascrizione non trovata', 'agent_id': a.agent_id}, ensure_ascii=False))
        return 2
    with open(path, encoding='utf-8', errors='replace') as fh:
        esito = conta(fh)
    esito['trascrizione'] = path
    esito['verdetto'] = 'multi-agente' if esito['lanci'] else 'simulato'
    print(json.dumps(esito, ensure_ascii=False, indent=1))
    return 0 if esito['lanci'] else 1


if __name__ == '__main__':
    sys.exit(main())
