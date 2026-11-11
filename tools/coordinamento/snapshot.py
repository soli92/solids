#!/usr/bin/env python3
"""Snapshot del kanban: una riga per entità (EP, US, TSK) con provenienza, senza giudizi.

    python snapshot.py --config config-base.json --out snapshot.json [--fonte worktree|commit] [--ref HEAD]

- fonte `worktree` (default): legge i file così come sono sul disco; per ognuno registra sha256 del contenuto
  e se è modificato o non tracciato rispetto al commit (riquadro «non committato» nella vista).
- fonte `commit`: legge i file dal commit `--ref` (git show), riproducibile al byte.

ID: prefisso di namespace opzionale (XX-TSK-541 oppure TSK-635), cartelle con o senza slug (kanban_ids.py).
Appartenenza TSK → US → EP: dal frontmatter (story:/us:, epic:/ep:); solo in mancanza dal path, riconoscendo
la cartella dall'ID con cui comincia. Frontmatter e path discordanti = finding, vince il frontmatter.
Sezione: SOLO dalla config; il resto è `non_classificato`.
- sezione con `tsk` (sotto-perimetro, es. sviluppo, configurazione e rilascio, test): contiene solo i TSK
  elencati; le sue `us` servono al piano e alle date, non all'appartenenza dei TSK;
- sezione senza `tsk`: i TSK delle sue US, tranne quelli elencati in una sezione con `tsk` dello stesso obiettivo.
Stato: normalizzato con la tabella `stati` della config; un valore non previsto diventa `sconosciuto` (mai indovinato).
Sola lettura: non scrive nulla nella factory.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:  # la skill gira sulla postazione del coordinatore, dove PyYAML c'e'; fallback esplicito
    yaml = None

from calendario import GIORNI, GIORNO_DATA
from kanban_ids import CAMPI_EP, CAMPI_US, ID_IN_TESTO, ID_RE, cartelle_epiche, da_frontmatter, da_path, epiche_nel_path, tsk_dichiarati
from percorsi import risolvi_factory_root


def git(root, *args, check=True):
    r = subprocess.run(['git', '-C', root, *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode != 0:
        raise RuntimeError('git %s: %s' % (' '.join(args), r.stderr.strip()))
    return r.stdout


def frontmatter(testo):
    if not testo.startswith('---'):
        return None, 'frontmatter assente'
    fine = testo.find('\n---', 3)
    if fine < 0:
        return None, 'frontmatter non chiuso'
    blocco = testo[3:fine]
    if yaml is None:
        return None, 'PyYAML non disponibile'
    try:
        dati = yaml.safe_load(blocco) or {}
    except Exception as exc:  # noqa: BLE001 - il messaggio va nel finding
        return None, 'YAML non valido: %s' % str(exc).splitlines()[0][:120]
    if not isinstance(dati, dict):
        return None, 'frontmatter non e\' una mappa'
    return dati, None


def come_lista(v):
    if v in (None, '', []):
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [s.strip() for s in re.split(r'[,\s]+', str(v)) if s.strip()]


def testo_json(v):
    """Valore del frontmatter serializzabile così com'è (YAML può dare date): testo, numeri, liste, o la sua forma testuale."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, list):
        return [testo_json(x) for x in v]
    return str(v)


def normalizza_stato(valore, stati):
    s = str(valore or '').strip().lower()
    for categoria, valori in stati.items():
        if s in [x.lower() for x in valori]:
            return categoria
    return 'sconosciuto'


def leggi_blob(root, ref, nomi):
    """{nome: contenuto} di piu' file di un commit con un solo `git cat-file --batch`.
    Un `git show` per file costa ~80 ms in questo repo (decine di submodule): su ~2500 file
    del kanban sono minuti, contro pochi secondi in batch. Il testo e' decodificato come
    farebbe `git show` letto da subprocess in modalita' testo (utf-8 con replace, a capo
    universali), cosi' lo snapshot resta identico al byte."""
    if not nomi:
        return {}
    r = subprocess.run(['git', '-C', root, 'cat-file', '--batch'], capture_output=True,
                       input=''.join(f'{ref}:{n}\n' for n in nomi).encode('utf-8'))
    if r.returncode != 0:
        raise RuntimeError('git cat-file --batch: %s' % r.stderr.decode('utf-8', 'replace').strip())
    out, buf, pos = {}, r.stdout, 0
    for n in nomi:
        fine = buf.index(b'\n', pos)
        testata = buf[pos:fine].split()
        if len(testata) < 3 or testata[1] != b'blob':
            raise RuntimeError("git cat-file --batch: %s:%s non e' un blob (%s)" % (ref, n, buf[pos:fine].decode('utf-8', 'replace')))
        size = int(testata[2])
        out[n] = buf[fine + 1:fine + 1 + size].decode('utf-8', 'replace').replace('\r\n', '\n').replace('\r', '\n')
        pos = fine + 1 + size + 1
    return out


def cartelle_del_perimetro(root, kanban, fonte, ref, epiche):
    """Percorsi (relativi alla factory) delle cartelle di primo livello del kanban che appartengono alle epiche:
    la cartella si riconosce dall'ID iniziale, con o senza slug («EP-064-…» oppure «XX-EP-020»)."""
    if fonte == 'commit':
        nomi = [n.split('/')[-1] for n in git(root, 'ls-tree', '--name-only', ref, '--', kanban + '/').splitlines()]
    else:
        base = os.path.join(root, kanban)
        nomi = [n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n))] if os.path.isdir(base) else []
    return ['%s/%s' % (kanban, c) for c in cartelle_epiche(nomi, epiche)]


def elenco_file(root, kanban, fonte, ref, epiche):
    """[(path relativo alla factory, contenuto)] dei file .md sotto le epiche richieste."""
    out = []
    cartelle = cartelle_del_perimetro(root, kanban, fonte, ref, epiche)
    if fonte == 'commit':
        nomi = sorted(epiche_nel_path(git(root, 'ls-tree', '-r', '--name-only', ref, '--', *cartelle).splitlines() if cartelle else [],
                                      kanban, epiche))
        testi = leggi_blob(root, ref, nomi)
        out.extend((n, testi[n]) for n in nomi)
    else:
        for c in cartelle:
            base = os.path.join(root, *c.split('/'))
            for d, _, fs in os.walk(base):
                for f in fs:
                    if f.endswith('.md'):
                        p = os.path.join(d, f)
                        rel = os.path.relpath(p, root).replace('\\', '/')
                        with open(p, encoding='utf-8', errors='replace') as fh:
                            out.append((rel, fh.read()))
    return sorted(out)


def non_pushati(root, ref):
    """Commit del ref misurato non ancora sul remoto (rispetto all'upstream del branch corrente, all'ultimo fetch: niente fetch qui).
    None se non c'è upstream."""
    up = subprocess.run(['git', '-C', root, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'],
                        capture_output=True, text=True, encoding='utf-8', errors='replace')
    if up.returncode != 0 or not up.stdout.strip():
        return None
    righe = git(root, 'log', '--format=%h %s', '%s..%s' % (up.stdout.strip(), ref), check=False).splitlines()
    return {'upstream': up.stdout.strip(), 'commit': righe}


def stato_git(root, kanban):
    """{path: 'M'|'??'|...} per i file del kanban diversi dal commit (porcelain v1)."""
    st = {}
    for riga in git(root, 'status', '--porcelain', '--untracked-files=all', '--', kanban).splitlines():
        codice, path = riga[:2].strip(), riga[3:].strip().strip('"')
        if ' -> ' in path:
            path = path.split(' -> ')[1]
        st[path] = codice
    return st


CHIUSI = ('fatto', 'chiuso_senza_esito')


def sostituti(v):
    """superseded_by: lista di ID validi + elementi non leggibili come ID (testo libero, 'DST-US-006/007/008')."""
    if v in (None, '', []):
        return {}
    elementi = [str(x).strip() for x in v] if isinstance(v, list) else [str(v).strip()]
    ids, non_validi = [], []
    for el in elementi:
        if ID_RE.match(el):
            ids.append(el)
        else:
            non_validi.append(el if len(el) <= 80 else el[:77] + '...')
            ids += [x for x in ID_IN_TESTO.findall(el) if ID_RE.match(x)]
    return {'id': sorted(set(ids)), 'non_validi': non_validi}


def controlli_qualita(root, kanban, ref, cartelle, entita):
    """Controlli deterministici sul dato, emersi dalle verifiche manuali del 04/10 (nessun giudizio, solo frontmatter e git):
    superseded_by non valido o inesistente; chiusura senza campi strutturati; `updated` più vecchio dell'ultimo commit del file;
    US/EP con stato incoerente con i propri TSK (roll-up)."""
    out = []
    tutti = {os.path.basename(p)[:-3] for p in git(root, 'ls-tree', '-r', '--name-only', ref, '--', kanban).splitlines() if p.endswith('.md')}
    ultimo, data = {}, None
    for riga in (git(root, 'log', '--format=\x01%cs', '--name-only', ref, '--', *cartelle).splitlines() if cartelle else []):
        if riga.startswith('\x01'):
            data = riga[1:]
        elif riga.strip() and riga not in ultimo:
            ultimo[riga] = data
    for e in entita:
        if 'stato' not in e:
            continue
        sb = e.get('superseded_by') or {}
        if sb.get('non_validi'):
            riconosciuti = (' (riconosciuti: %s)' % ', '.join(sb['id'])) if sb['id'] else ''
            out.append({'livello': 'AVVISO', 'codice': 'superseded-by-non-valido', 'entita': e['id'],
                        'evidenza': f"{e['fonte']['path']}: superseded_by contiene {', '.join(repr(x) for x in sb['non_validi'])}, "
                                    f"non leggibile come ID{riconosciuti}; per più sostituti serve una lista di ID"})
        for s in sb.get('id', []):
            if s not in tutti:
                out.append({'livello': 'AVVISO', 'codice': 'superseded-by-non-valido', 'entita': e['id'],
                            'evidenza': f"{e['fonte']['path']}: superseded_by {s} non esiste nel kanban"})
        ch = e.get('chiusura', {})
        if e['stato']['normalizzato'] == 'chiuso_senza_esito' and not (e.get('superseded_by') or {}).get('id') \
                and not (ch.get('superseded_at') or ch.get('closed_at')) and not (ch.get('superseded_reason') or ch.get('resolution')):
            out.append({'livello': 'INFO', 'codice': 'chiusura-senza-metadati', 'entita': e['id'],
                        'evidenza': f"{e['fonte']['path']}: status {e['stato']['dichiarato']} senza superseded_by, superseded_at/closed_at "
                                    f"né superseded_reason/resolution (il motivo, se c'è, è solo nel testo)"})
        agg, mod = (e.get('updated') or '')[:10], ultimo.get(e['fonte']['path'])
        # solo TSK/US/EP chiusi: è il caso di una transizione di status senza aggiornare `updated` (verifica del 04/10).
        # Sui file aperti lo scarto è quasi sempre una nota aggiunta e farebbe rumore (98 casi su 104 al commit 28356249).
        if agg and mod and agg < mod and e['stato']['normalizzato'] in CHIUSI:
            out.append({'livello': 'INFO', 'codice': 'updated-non-aggiornato', 'entita': e['id'],
                        'evidenza': f"{e['fonte']['path']}: updated {agg}, ultimo commit sul file {mod}"})
    tsk = [e for e in entita if e['tipo'] == 'TSK' and 'stato' in e]
    for e in entita:
        if e['tipo'] not in ('US', 'EP') or 'stato' not in e:
            continue
        if e['tipo'] == 'US':
            # i TSK della US per frontmatter/path, piu' quelli che la US dichiara in tsk_ids/tsk_range
            # anche se stanno in un'altra cartella (prima venivano ignorati: falso «us-non-aggiornata»)
            dichiarati = set(e.get('tsk_dichiarati') or ())
            figli = [t for t in tsk if t['us'] == e['id'] or t['id'] in dichiarati]
        else:
            figli = [t for t in tsk if t['epica'] == e['id']]
        if not figli:
            continue
        cat = e['stato']['normalizzato']
        avviati = [t['id'] for t in figli if t['stato']['normalizzato'] in ('in_corso', 'fatto')]
        aperti = [t['id'] for t in figli if t['stato']['normalizzato'] not in CHIUSI]
        codice = 'us-non-aggiornata' if e['tipo'] == 'US' else 'ep-non-aggiornata'
        if cat == 'da_fare' and avviati:
            msg = 'status %s ma %d TSK avviati o fatti (%s)' % (e['stato']['dichiarato'], len(avviati), ', '.join(sorted(avviati)[:6]))
        elif cat not in CHIUSI and not aperti:
            msg = 'tutti i %d TSK sono chiusi ma lo status è ancora %s' % (len(figli), e['stato']['dichiarato'])
        elif cat == 'fatto' and aperti:
            msg = 'status %s con %d TSK aperti (%s)' % (e['stato']['dichiarato'], len(aperti), ', '.join(sorted(aperti)[:6]))
        else:
            continue
        out.append({'livello': 'AVVISO', 'codice': codice, 'entita': e['id'], 'evidenza': f"{e['fonte']['path']}: {msg}"})
    return out


def giorni_incoerenti(nome, rel, testo, anno):
    """«mer 06/10» con il 06/10 che è martedì: la data o il giorno è sbagliato, e una data di piano diventa ambigua.
    Anno: quello scritto, altrimenti quello del campo created del file."""
    out = []
    for n, riga in enumerate(testo.split('\n'), 1):
        for m in GIORNO_DATA.finditer(riga):
            a = int(m.group(4)) if m.group(4) else anno
            if a is None:
                continue
            a = a + 2000 if a < 100 else a
            try:
                d = datetime.date(a, int(m.group(3)), int(m.group(2)))
            except ValueError:
                continue
            if GIORNI[d.weekday()] != m.group(1):
                out.append({'livello': 'AVVISO', 'codice': 'giorno-data-incoerente', 'entita': nome,
                            'evidenza': f"{rel}:{n}: «{m.group(0)}», ma il {d.strftime('%d/%m/%Y')} è {GIORNI[d.weekday()]}"})
    return out


ESITO_NEL_CORPO = re.compile(r'\b((?:[A-Z]{2,4}-)?TSK-\d+)\b[^\n→]{0,40}?(?:→|->)\s*[*`]*([a-z_-]+)')


def esiti_nel_corpo(corpi, entita, stati):
    """Esito di un TSK dichiarato nel corpo di US/EP («DST-TSK-004 → done») diverso dall'esito nel suo frontmatter.
    Conta solo l'ultima menzione per file (le note sono in coda) e solo esiti terminali opposti: fatto contro chiuso senza esito."""
    tsk = {e['id']: e for e in entita if e['tipo'] == 'TSK' and 'stato' in e}
    out = []
    for e_id, (path, testo) in sorted(corpi.items()):
        ultima = {}
        for n, riga in enumerate(testo.split('\n'), 1):
            for m in ESITO_NEL_CORPO.finditer(riga):
                ultima[m.group(1)] = (m.group(2), n)
        for t_id, (parola, n) in sorted(ultima.items()):
            nel_corpo = normalizza_stato(parola, stati)
            t = tsk.get(t_id)
            if t and nel_corpo in CHIUSI and t['stato']['normalizzato'] in CHIUSI and nel_corpo != t['stato']['normalizzato']:
                out.append({'livello': 'AVVISO', 'codice': 'esito-corpo-diverso', 'entita': e_id,
                            'evidenza': f"{path}:{n}: {t_id} → {parola} nel corpo, ma il frontmatter di {t_id} dice "
                                        f"status {t['stato']['dichiarato']}"})
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--fonte', choices=['worktree', 'commit'], default='worktree')
    ap.add_argument('--ref', default='HEAD')
    a = ap.parse_args(argv)

    with open(a.config, encoding='utf-8') as fh:
        cfg = json.load(fh)
    root = risolvi_factory_root(cfg, a.config)
    kanban = cfg.get('kanban_root', 'management/kanban')
    stati = cfg['stati']
    campi_piano = [p['campo'] for p in cfg.get('vista_pm', {}).get('piano', [])]
    epiche = sorted({e for o in cfg['obiettivi'] for p in o.get('perimetro', []) for e in p.get('selettore', {}).get('epiche', [])})
    us_sezione, tsk_sezione, tsk_espliciti = {}, {}, set()
    for o in cfg['obiettivi']:
        for s in o.get('sezioni', []):
            if 'tsk' in s:
                for t in s['tsk']:
                    tsk_sezione.setdefault(t, []).append({'obiettivo': o['id'], 'sezione': s['id']})
                    tsk_espliciti.add((o['id'], t))
                continue
            for us in s.get('us', []):
                us_sezione.setdefault(us, []).append({'obiettivo': o['id'], 'sezione': s['id']})

    head = git(root, 'rev-parse', 'HEAD').strip()
    ref_sha = git(root, 'rev-parse', a.ref).strip() if a.fonte == 'commit' else None
    sporchi = stato_git(root, kanban) if a.fonte == 'worktree' else {}

    entita, findings, corpi, appartenenza = [], [], {}, []
    cartelle = cartelle_del_perimetro(root, kanban, a.fonte, a.ref, epiche)
    for rel, testo in elenco_file(root, kanban, a.fonte, a.ref, epiche):
        parti = rel.split('/')
        nome = parti[-1][:-3]
        m = ID_RE.match(nome)
        if not m:
            continue  # file di supporto (note, tabelle): non sono entità del kanban
        prefisso, tipo, _ = m.groups()
        dati, errore = frontmatter(testo)
        if tipo in ('US', 'EP'):
            corpi[nome] = (rel, testo)
        anno = re.match(r'\d{4}', str((dati or {}).get('created') or ''))
        findings += giorni_incoerenti(nome, rel, testo, int(anno.group(0)) if anno else None)
        dentro = parti[len(kanban.split('/')):]
        appartenenza.append((nome, tipo, rel, dentro, dati or {}))
        riga = {
            'id': nome, 'tipo': tipo, 'prefisso': prefisso, 'epica': None, 'us': nome if tipo == 'US' else None,
            'fonte': {'path': rel, 'sha256': hashlib.sha256(testo.encode('utf-8')).hexdigest(),
                      'git': sporchi.get(rel, 'pulito') if a.fonte == 'worktree' else 'commit'},
        }
        if errore:
            riga['errore'] = errore
            findings.append({'livello': 'ERRORE', 'codice': 'frontmatter', 'entita': nome, 'evidenza': f'{rel}: {errore}'})
        else:
            dichiarato = dati.get('status')
            riga.update({
                'titolo': str(dati.get('title') or '').strip(),
                'stato': {'dichiarato': dichiarato, 'normalizzato': normalizza_stato(dichiarato, stati)},
                'owner': dati.get('owner'), 'assignee': dati.get('assignee'), 'consumer': dati.get('consumer'),
                'priority': dati.get('priority'), 'size': dati.get('size') or dati.get('estimate'),
                'depends_on': come_lista(dati.get('depends_on')), 'blocks': come_lista(dati.get('blocks')),
                'window': dati.get('window'), 'updated': str(dati.get('updated') or '') or None,
                'superseded_by': sostituti(dati.get('superseded_by')),
                'chiusura': {k: bool(dati.get(k)) for k in ('superseded_at', 'superseded_reason', 'closed_at', 'resolution')},
            })
            if tipo == 'US':
                riga['piano'] = {c: testo_json(dati.get(c)) for c in campi_piano}
                dichiarati = tsk_dichiarati(dati)
                if dichiarati:
                    riga['tsk_dichiarati'] = sorted(dichiarati)
            if tipo in ('US', 'EP'):
                riga['creata'] = testo_json(dati.get('created'))
            if riga['stato']['normalizzato'] == 'sconosciuto':
                findings.append({'livello': 'AVVISO', 'codice': 'stato-sconosciuto', 'entita': nome,
                                 'evidenza': f'{rel}: status={dichiarato!r} non e\' nella tabella stati della config'})
            if dati.get('id') and str(dati.get('id')) != nome:
                findings.append({'livello': 'AVVISO', 'codice': 'id-diverso-dal-nome', 'entita': nome,
                                 'evidenza': f'{rel}: id={dati.get("id")!r}'})
        entita.append(riga)

    # appartenenza: frontmatter prima, path solo in mancanza (seconda passata: il TSK senza epic: eredita quella della sua US)
    per_nome = {e['id']: e for e in entita}
    for nome, tipo, rel, dentro, dati in sorted(appartenenza, key=lambda x: ('EP', 'US', 'TSK').index(x[1])):
        riga = per_nome[nome]
        ep_path = da_path(dentro, 'EP')
        if tipo == 'EP':
            riga['epica'] = nome
            continue
        us_fm = da_frontmatter(dati, CAMPI_US, 'US') if tipo == 'TSK' else None
        us_path = da_path(dentro, 'US') if tipo == 'TSK' else None
        if tipo == 'TSK':
            riga['us'] = us_fm or us_path
        ep_fm = da_frontmatter(dati, CAMPI_EP, 'EP')
        ep_us = (per_nome.get(riga['us']) or {}).get('epica') if tipo == 'TSK' and riga['us'] else None
        riga['epica'] = ep_fm or ep_us or ep_path
        riga['appartenenza_da'] = 'frontmatter' if (ep_fm or us_fm) else 'path'
        for campo, fm, pth in (('us', us_fm, us_path), ('epica', ep_fm or ep_us, ep_path)):
            if fm and pth and fm != pth:
                findings.append({'livello': 'AVVISO', 'codice': 'appartenenza-discordante', 'entita': nome,
                                 'evidenza': f'{rel}: {campo} {fm} nel frontmatter, {pth} dal path (vale il frontmatter)'})
    for riga in entita:
        chiave_us = riga['us'] if riga['tipo'] in ('TSK', 'US') else None
        riga['sezioni'] = us_sezione.get(chiave_us, []) if chiave_us else []
        if riga['tipo'] == 'TSK':
            riga['sezioni'] = [x for x in riga['sezioni'] if (x['obiettivo'], riga['id']) not in tsk_espliciti] \
                + tsk_sezione.get(riga['id'], [])
        elif riga['tipo'] == 'US':
            riga['sezioni'] = riga['sezioni'] + [{'obiettivo': o['id'], 'sezione': z['id']} for o in cfg['obiettivi']
                                                 for z in o.get('sezioni', []) if 'tsk' in z and riga['id'] in z.get('us', [])]
        if riga['tipo'] == 'TSK' and not riga['sezioni']:
            riga['classificazione'] = 'non_classificato'

    ids = {e['id'] for e in entita}
    for e in entita:
        for d in e.get('depends_on', []):
            if ID_RE.match(d) and d not in ids:
                findings.append({'livello': 'AVVISO', 'codice': 'dipendenza-fuori-snapshot', 'entita': e['id'],
                                 'evidenza': f'depends_on {d}: non presente nelle epiche del perimetro (o inesistente)'})
    per_id = {e['id']: e for e in entita if e['tipo'] == 'TSK' and 'stato' in e}
    for e in sorted(per_id.values(), key=lambda r: r['id']):
        for d in e.get('depends_on', []):
            b = per_id.get(d)
            if b and b.get('blocks') and e['id'] not in b['blocks']:
                findings.append({'livello': 'AVVISO', 'codice': 'blocks-incompleto', 'entita': d,
                                 'evidenza': '%s: blocks %s non elenca %s, che lo ha in depends_on' % (b['fonte']['path'], ', '.join(b['blocks']), e['id'])})
        for c in e.get('blocks', []):
            t = per_id.get(c)
            if t and e['id'] not in t.get('depends_on', []):
                findings.append({'livello': 'AVVISO', 'codice': 'depends-on-incompleto', 'entita': c,
                                 'evidenza': '%s: depends_on non elenca %s, che lo ha in blocks' % (t['fonte']['path'], e['id'])})
    findings += controlli_qualita(root, kanban, a.ref if a.fonte == 'commit' else 'HEAD', cartelle, entita)
    findings += esiti_nel_corpo(corpi, entita, stati)

    out = {
        'versione_schema': '1.0',
        'provenienza': {
            'fonte': a.fonte, 'ref': a.ref if a.fonte == 'commit' else None, 'ref_sha': ref_sha,
            'factory_head': head, 'epiche': epiche,
            'kanban_non_committati': sorted(p for p in sporchi if any(p.startswith(c + '/') for c in cartelle)),
            'non_pushati': non_pushati(root, a.ref if a.fonte == 'commit' else 'HEAD'),
            'config_sha256': hashlib.sha256(open(a.config, 'rb').read()).hexdigest(),
        },
        'entita': sorted(entita, key=lambda r: r['id']),
        'findings': sorted(findings, key=lambda f: (f['livello'], f['codice'], f['entita'])),
    }
    with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
    n = {t: sum(1 for e in entita if e['tipo'] == t) for t in ('EP', 'US', 'TSK')}
    print(f"snapshot: {n} — fonte {a.fonte} — findings {len(findings)} — non committati {len(out['provenienza']['kanban_non_committati'])}")
    if not n['TSK']:
        # nessun TSK letto: root o kanban_root sbagliati, e una misura a zero passerebbe tutte le verifiche
        print('STOP: nessun TSK trovato in %s/%s: controlla factory_root e kanban_root della config' % (root, kanban))
        return 2


if __name__ == '__main__':
    sys.exit(main())
