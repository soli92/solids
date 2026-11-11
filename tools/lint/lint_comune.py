"""Parti comuni dei check deterministici di /lint (EP-071 US-324).

Un punto solo per: radice della factory, lettura del frontmatter, raccolta di EP/US/TSK,
appartenenza TSK -> US -> EP, formato delle righe del report e opzioni della riga di comando.

Forma degli ID: NON e' definita qui. Si importa `tools/coordinamento/kanban_ids.py`
(prefisso di namespace opzionale, cartella riconosciuta dall'ID iniziale, appartenenza dal
frontmatter e solo in mancanza dal path, `tsk_dichiarati`): e' la fonte gia' usata dal report PM
(EP-070), e una seconda regex per gli stessi ID divergerebbe alla prima factory nuova.

Solo stdlib. Nessuna scrittura, salvo il file indicato con --out.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

_QUI = os.path.dirname(os.path.abspath(__file__))
RADICE_DEFAULT = os.path.dirname(os.path.dirname(_QUI))
sys.path.insert(0, os.path.join(RADICE_DEFAULT, 'tools', 'coordinamento'))

import kanban_ids  # noqa: E402  (fonte unica della forma degli ID)

KANBAN = 'management/kanban'
SEVERITA = ('ERROR', 'WARNING', 'INFO')

# Insieme di layer validi se routing: manca in factory.config.yaml
LAYERS_DEFAULT = {'be', 'fe', 'db', 'qa', 'infra', 'docs'}


def leggi_routing_layers(radice):
    """Chiavi di routing: da factory.config.yaml; fallback LAYERS_DEFAULT.

    Legge la sezione top-level `routing:` (non indentata, non quella nidificata
    sotto `model:`) e ne ritorna le chiavi come insieme di stringhe. Se il file
    e' assente o la sezione manca, ritorna LAYERS_DEFAULT (che include gia' `docs`
    per compatibilita' con le factory v2.19+).
    """
    cfg = os.path.join(radice, 'factory.config.yaml')
    if not os.path.isfile(cfg):
        return LAYERS_DEFAULT
    testo = leggi(cfg)
    # Sezione top-level: riga non indentata `routing:` seguita da righe indentate
    m = re.search(r'^routing:\n((?:[ \t]+[^\n]*\n?|[ \t]*\n)*)', testo, re.M)
    if not m:
        return LAYERS_DEFAULT
    layers = set()
    for line in m.group(1).splitlines():
        km = re.match(r'^[ \t]+([a-z][a-z0-9_-]*):\s', line)
        if km:
            layers.add(km.group(1))
    return layers if layers else LAYERS_DEFAULT

# Regole parametriche del lint (blocco `lint:` di factory.config.yaml, EP-072). Il default e'
# il comportamento del master; una derivata con norme proprie le dichiara invece di tenere
# una copia degli script.
REGOLE_DEFAULT = {
    'kanban': {
        'scope': 'all',                 # all | open: Check 3 su tutti gli artefatti o sui soli aperti
        'required': {'EP': ['id', 'title', 'status', 'priority', 'confidence'],
                     'US': ['id', 'title', 'role', 'priority', 'status', 'wiki_page'],
                     'TSK': ['id', 'layer', 'consumer', 'priority', 'estimate', 'status']},
        'warning': {'EP': [], 'US': [], 'TSK': []},   # campi mancanti → WARNING invece di ERROR
        'layer_severity': 'error',      # error | warning per layer fuori da routing:
        'layer_segment': False,         # true: vale il segmento prima di «/» (fe/a11y → fe)
        'id_duplicate': True,           # false se l'unicita' e' presidiata altrove (es. id_registry_check)
        'equivalents': {},              # es. {estimate: [size]}: il campo vale presente se c'e' un equivalente
        'in_progress_needs_sprint': True,   # WARNING per TSK in_progress/review senza sprint:
        'be_test_evidence': 'off',      # 4bh: off | warning | error, TSK be done senza evidenza di test
        'be_test_evidence_consumers': ['agent'],   # consumer soggetti al 4bh
        'be_test_evidence_since': '',   # 4bh: i TSK chiusi prima di questa data non sono soggetti
        'tsk_target': 'off',            # 4j: off | warning | error, TSK aperti degli agenti senza repository
        'tsk_target_gitmodules': False,  # 4j: true = un code_path sotto code_repos/ deve essere in .gitmodules
    },
    'wiki': {
        'orphan': 'index',              # index: linkata da wiki/index.md | reachability: raggiungibile
        'append_only_links': 'error',   # error | info: link rotti in gaps.md, che non si correggono (R.5)
        'date_fields': ['updated', 'created'],   # 4ag: vale la data piu' recente fra questi campi
    },
}


def _mini_yaml(righe, base):
    """Sottoinsieme di YAML per il blocco lint: mappe annidate per indentazione, scalari,
    liste inline [a, b]. Stesso esito su ogni macchina (niente PyYAML)."""
    out = {}
    pila = [(base - 1, out)]
    for raw in righe:
        riga = raw.split(' #')[0].rstrip()
        if not riga.strip() or riga.strip().startswith('#'):
            continue
        ind = len(riga) - len(riga.lstrip())
        m = re.match(r'^\s*([A-Za-z_][\w-]*):\s*(.*)$', riga)
        if not m:
            continue
        while pila and ind <= pila[-1][0]:
            pila.pop()
        chiave, val = m.group(1), m.group(2).strip()
        corrente = pila[-1][1]
        if val == '':
            corrente[chiave] = {}
            pila.append((ind, corrente[chiave]))
        elif val.startswith('{'):
            raise ValueError("lint: mappa inline non supportata (%s): usare la forma a blocco" % chiave)
        elif val.startswith('[') and val.endswith(']'):
            corrente[chiave] = [x.strip().strip('"\'') for x in val[1:-1].split(',') if x.strip()]
        else:
            v = val.strip('"\'')
            corrente[chiave] = {'true': True, 'false': False}.get(v.lower(), v)
    return out


def regole_lint(radice):
    """REGOLE_DEFAULT sovrascritte dal blocco `lint:` di factory.config.yaml (chiave per chiave)."""
    import copy
    regole = copy.deepcopy(REGOLE_DEFAULT)
    cfg = os.path.join(radice, 'factory.config.yaml')
    if not os.path.isfile(cfg):
        return regole
    m = re.search(r'^lint:[ \t]*\n((?:[ \t]+[^\n]*\n?|[ \t]*\n)*)', leggi(cfg), re.M)
    if not m:
        return regole
    letto = _mini_yaml(m.group(1).splitlines(), 2)

    def fondi(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                fondi(dst[k], v)
            else:
                dst[k] = v
    fondi(regole, letto)
    return regole


_FM_RE = re.compile(r'^---\n(.*?)\n---\n', re.S)
_CHIAVE_RE = re.compile(r'^([A-Za-z_][\w-]*):\s*(.*)$')


# ---------------------------------------------------------------- frontmatter

def _valore(grezzo):
    v = grezzo.strip()
    if not v:
        return ''
    if v[0] in '"\'':
        chiusa = v.find(v[0], 1)
        return v[1:chiusa] if chiusa > 0 else v[1:]
    if v.startswith('['):
        interno = v[1:v.rfind(']')] if ']' in v else v[1:]
        return [x.strip().strip('"\'') for x in interno.split(',') if x.strip()]
    return v.split(' #', 1)[0].strip()


def frontmatter_da_testo(testo, limite=None):
    """Dict del frontmatter YAML in testa al testo; None se assente o non chiuso.

    `limite` (byte) riproduce il vincolo V1 del Check 4au: si guarda solo l'inizio del file.
    Parser a righe, senza PyYAML: lo stesso file da' lo stesso risultato su ogni macchina.
    Riconosce scalari (anche quotati), liste inline `[a, b]`, liste a blocco `- x` e
    scalari a blocco `|`/`>`. La prima occorrenza di una chiave vince.
    """
    if limite is not None:
        testo = testo[:limite]
    m = _FM_RE.match(testo)
    if not m:
        return None
    righe = m.group(1).splitlines()
    out = {}
    i = 0
    while i < len(righe):
        kv = _CHIAVE_RE.match(righe[i])
        i += 1
        if not kv:
            continue
        chiave, grezzo = kv.group(1), kv.group(2)
        valore = _valore(grezzo)
        if grezzo.strip()[:1] in ('|', '>'):
            pezzi = []
            while i < len(righe) and (righe[i].startswith((' ', '\t')) or not righe[i].strip()):
                pezzi.append(righe[i].strip())
                i += 1
            valore = ' '.join(p for p in pezzi if p)
        elif valore == '':
            voci = []
            while i < len(righe):
                im = re.match(r'^\s*-\s+(.*)$', righe[i])
                if not im:
                    break
                voci.append(_valore(im.group(1)))
                i += 1
            if voci:
                valore = voci
        if chiave not in out:
            out[chiave] = valore
    return out


def leggi(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read().replace('\r\n', '\n')


def frontmatter(path, limite=None):
    return frontmatter_da_testo(leggi(path), limite)


def testo_di(v):
    """Valore del frontmatter come stringa (le liste diventano «a, b»)."""
    if isinstance(v, list):
        return ', '.join(str(x) for x in v)
    return '' if v is None else str(v)


# ---------------------------------------------------------------- kanban

class Artefatto:
    __slots__ = ('id', 'tipo', 'path', 'rel', 'fm', 'testo', 'us', 'ep')

    def __init__(self, ident, tipo, path, rel, fm, testo, us, ep):
        self.id, self.tipo, self.path, self.rel = ident, tipo, path, rel
        self.fm, self.testo, self.us, self.ep = fm, testo, us, ep


def raccogli_kanban(radice, limite=None):
    """Lista di Artefatto per ogni file `<ID>.md` sotto management/kanban (archivio incluso).

    Tipo dal nome del file (kanban_ids.tipo_di); appartenenza a US/EP dal frontmatter
    (kanban_ids.CAMPI_US / CAMPI_EP) e solo in mancanza dal path (kanban_ids.da_path).
    `limite`: byte di testa da cui leggere il frontmatter (V1 del Check 4au); None = tutto.
    """
    base = os.path.join(radice, KANBAN)
    out = []
    for dirpath, dirnames, files in os.walk(base):
        dirnames.sort()
        for fn in sorted(files):
            if not fn.endswith('.md'):
                continue
            stem = fn[:-3]
            tipo = kanban_ids.tipo_di(stem)
            if not tipo:
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, radice).replace(os.sep, '/')
            testo = leggi(path)
            fm = frontmatter_da_testo(testo, limite)
            dentro = os.path.relpath(path, base).replace(os.sep, '/').split('/')
            us = ep = None
            if tipo == 'TSK':
                us = kanban_ids.da_frontmatter(fm, kanban_ids.CAMPI_US, 'US') or kanban_ids.da_path(dentro, 'US')
            if tipo in ('TSK', 'US'):
                ep = kanban_ids.da_frontmatter(fm, kanban_ids.CAMPI_EP, 'EP') or kanban_ids.da_path(dentro, 'EP')
            out.append(Artefatto(stem, tipo, path, rel, fm, testo, us, ep))
    return out


def id_in_cella(cella):
    """ID del kanban contenuto in una cella di tabella: nudo, in grassetto o in link markdown.

    Nessuna regex di ID qui: si tolgono i marcatori e si chiede a kanban_ids se cio' che
    resta e' un ID (G1 + G3 del Check 4au).
    """
    c = cella.strip().strip('*').strip()
    m = re.match(r'^\[([^\]]+)\]\([^)]*\)$', c)
    if m:
        c = m.group(1).strip().strip('*').strip()
    elif c.startswith('[') and c.endswith(']'):
        c = c[1:-1].strip()
    return c if kanban_ids.tipo_di(c) else None


def celle(riga):
    """Celle di una riga di tabella markdown, bordi esclusi."""
    parti = [c.strip() for c in riga.strip().split('|')]
    if parti and parti[0] == '':
        parti = parti[1:]
    if parti and parti[-1] == '':
        parti = parti[:-1]
    return parti


# ---------------------------------------------------------------- finding e output

def finding(sev, codice, check, messaggio, path=None, dettagli=None, **extra):
    f = {'sev': sev, 'codice': codice, 'check': check, 'messaggio': messaggio}
    if path:
        f['path'] = path
    if dettagli:
        f['dettagli'] = list(dettagli)
    f.update(extra)
    return f


_ORDINE = {s: i for i, s in enumerate(SEVERITA)}


def ordina(findings):
    return sorted(findings, key=lambda f: (_ORDINE[f['sev']], f['check'], f['codice'],
                                           f.get('path', ''), f['messaggio']))


def riga(f):
    testa = '- [%s][%s][%s] %s' % (f['sev'], f['codice'], f['check'], f['messaggio'])
    return '\n'.join([testa] + ['  ' + d for d in f.get('dettagli', [])])


def conteggi(findings):
    c = {s: 0 for s in SEVERITA}
    for f in findings:
        c[f['sev']] += 1
    return c


def parser(descrizione):
    ap = argparse.ArgumentParser(description=descrizione, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default=RADICE_DEFAULT, help='radice della factory (default: questa)')
    ap.add_argument('--json', action='store_true', help='output machine-readable')
    ap.add_argument('--out', help='scrive anche il report su questo file (relativo a --root se non assoluto)')
    ap.add_argument('--strict', action='store_true', help='exit 1 se almeno un ERROR (default: exit 0 sempre)')
    return ap


def scrivi_out(radice, out, testo):
    dest = out if os.path.isabs(out) else os.path.join(radice, out)
    os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
    with open(dest, 'w', encoding='utf-8') as fh:
        fh.write(testo if testo.endswith('\n') else testo + '\n')


def emetti(args, nome, findings, diagnostica, stats):
    """Stampa (testo o JSON), scrive --out, ritorna l'exit code (0, o 1 con --strict ed ERROR)."""
    findings = ordina(findings)
    if args.json:
        testo = json.dumps({'check': nome, 'conteggi': conteggi(findings), 'stats': stats,
                            'diagnostica': diagnostica, 'findings': findings},
                           indent=2, ensure_ascii=False, sort_keys=True)
    else:
        testo = '\n'.join([riga(f) for f in findings] + diagnostica)
    print(testo)
    if args.out:
        scrivi_out(args.root, args.out, testo)
    return 1 if args.strict and any(f['sev'] == 'ERROR' for f in findings) else 0


def id_con_prefisso_obbligatorio(arts):
    """True se ogni artefatto del kanban ha un ID con prefisso di namespace: allora un ID senza
    prefisso citato in un testo (`US-001` nella tabella di `XX-EP-001`) e' un numero locale,
    non il riferimento a un file."""
    return bool(arts) and all(kanban_ids.prefisso_di(a.id) for a in arts if a.id)
