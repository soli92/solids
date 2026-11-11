#!/usr/bin/env python3
"""Rilevamento deterministico delle discrepanze config→kanban e produzione di proposte JSON per il TPM.

    python tools/coordinamento/proponi_kanban.py \\
        --config analytics/coordinamento/config-<operatore>.json \\
        [--dry-run] [--ref HEAD] [--out proposte.json]
        [--aggiorna-store] [--oggi YYYY-MM-DD] [--operatore <id>]

- Legge il kanban SEMPRE dal commit (git show su --ref, default HEAD): il risultato
  e' riproducibile byte per byte per la stessa coppia (commit, config).
- NON scrive mai in management/kanban/. Le proposte vanno su --out (default stdout);
  nessun altro file viene scritto senza --aggiorna-store. Senza timestamp nel contenuto:
  stesso commit + config + store + --oggi => stessi byte.
- Il gate AskUserQuestion (conferma umana prima dell'applicazione) NON e' in questo
  script: va applicato dall'agente/skill che invoca proponi_kanban.py. L'applicazione
  effettiva e' delegata al tpm dopo conferma esplicita dell'operatore.

Gate: `pm_report.enabled: false` in factory.config.yaml della factory_root -> STOP, exit 0, nessuna
uscita. File o chiave assenti = non governato (si procede).

Stato fra esecuzioni: analytics/coordinamento/<operatore>/da_assegnare.yaml
(per-operatore, committabile), forma {da_assegnare: [...]}. Single-writer = sessione
dell'operatore (ADR-090 D5 della derivata). Si legge anche la lista nuda delle versioni precedenti.
Lo store viene LETTO sempre (se esiste, per preservare prima_vista) e SCRITTO solo
con --aggiorna-store. Il sha256 del file letto va in provenienza.da_assegnare_sha256.
Determinismo: stesso commit + stessa config + stesso store (stesso sha256) + stesso
--oggi -> stessi byte nell'output e nello store riscritto (ADR-090 D6).

Proposte generate (scope chiuso: nessun altro tipo):
  window_mancante       US di sezione senza campo `window` nel frontmatter
  window_non_allineata  US di sezione con `window` che non contiene la data
                        pronta_entro della sezione in formato gg/mm
  owner_suggerito       TSK con owner in owner_non_persona E epic_owner_default valido
                        (approved_by + valid_until futuro), tipo_valore: suggested_owner

Artefatto da_assegnare (mai in proposte, mai in coda di apply):
  TSK con owner in owner_non_persona (o vuoto) senza epic_owner_default valido.
  Per ogni voce: tsk_id, epic, us, priority, file, owner, prima_vista (ISO8601).

Appartenenza (epic, us): dal frontmatter, e solo in mancanza dal path (kanban_ids.py).

Esclusioni (nessuna proposta su lavoro in revisione o in corso):
  review/approved       TSK/US con status review o approved: esclusi
  in lavorazione        US/TSK con status in_progress/in-progress o nella categoria in_corso: esclusi
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    yaml = None

from kanban_ids import CAMPI_EP, CAMPI_US, ID_RE, da_frontmatter, da_path, epiche_nel_path, nel_perimetro
from percorsi import MESSAGGIO_SPENTA, operatore_da_config, pm_report_abilitato, risolvi_factory_root
from snapshot import leggi_blob

# Stato raw che esclude dalle proposte il lavoro in revisione, indipendentemente dall'owner
STATI_REVISIONE = {'review', 'approved'}

# Stato raw che attiva l'esclusione "in lavorazione"
STATI_IN_LAVORAZIONE = {'in_progress', 'in-progress'}

# Categorie della tabella `stati` della config che chiudono un'entita'
STATI_CHIUSI = {'fatto', 'chiuso_senza_esito'}


def git_ls(root, ref, *prefissi):
    r = subprocess.run(
        ['git', '-C', root, 'ls-tree', '-r', '--name-only', ref, '--', *prefissi],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
    )
    return r.stdout.splitlines() if r.returncode == 0 else []


def git_rev_parse(root, ref='HEAD'):
    r = subprocess.run(
        ['git', '-C', root, 'rev-parse', ref],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
    )
    return r.stdout.strip() if r.returncode == 0 else ref


def frontmatter(testo):
    if not testo or not testo.startswith('---'):
        return None, 'frontmatter assente'
    fine = testo.find('\n---', 3)
    if fine < 0:
        return None, 'frontmatter non chiuso'
    if yaml is None:
        return None, 'PyYAML non disponibile'
    try:
        dati = yaml.safe_load(testo[3:fine]) or {}
    except Exception as exc:  # noqa: BLE001
        return None, 'YAML non valido: %s' % str(exc).splitlines()[0][:120]
    if not isinstance(dati, dict):
        return None, 'frontmatter non e\' una mappa'
    return dati, None


def normalizza_stato(valore, stati):
    s = str(valore or '').strip().lower()
    for categoria, valori in stati.items():
        if s in [x.lower() for x in valori]:
            return categoria
    return 'sconosciuto'


def data_gg_mm(data_iso):
    """'2026-10-07' -> '07/10'. None se il formato non e' riconosciuto."""
    m = re.match(r'\d{4}-(\d{2})-(\d{2})', str(data_iso or ''))
    if not m:
        return None
    return '%s/%s' % (m.group(2), m.group(1))


def scrivi_atomico(path, dati):
    """Scrive il JSON in modo atomico (tmp + rename). newline=LF, indent=1, sort_keys=True."""
    tmp = path + '.tmp'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(dati, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write('\n')
    os.replace(tmp, path)


def calcola(entita, us_sezione, sezioni_cfg, owner_non_persona,
            store_precedente=None, oggi=None, epic_owner_map=None):
    """Proposte, esclusi e da_assegnare per le entita' lette dal kanban.

    Funzione pura: nessun accesso a git o al disco.

    Stato fra esecuzioni: da_assegnare.yaml (per-operatore, committato).
    Single-writer = sessione dell'operatore (ADR-090 D5).

    Parametri:
      store_precedente  dict tsk_id -> prima_vista del ciclo precedente (opzionale).
      oggi              data ISO8601 YYYY-MM-DD usata come prima_vista per voci nuove
                        (opzionale; obbligatoria con --aggiorna-store e se
                        epic_owner_map e' non vuoto; senza di essa le voci nuove
                        ottengono prima_vista=None).
      epic_owner_map    dict epic_id -> entry (approved_by, valid_until, owner).
                        Mapping valido + oggi presente -> proposta in proposte.
                        Mapping scaduto/incompleto/oggi assente -> da_assegnare.

    Ritorna: (proposte, esclusi, da_assegnare).
    """
    store_prec = store_precedente or {}
    epic_owner_map = epic_owner_map or {}
    proposte = []
    esclusi = []
    da_assegnare = []

    for nome, e in sorted(entita.items()):
        raw = e['stato_raw'].lower()
        # Chiusi (fatti o chiusi senza esito): niente da proporre né da assegnare
        if e['stato_norm'] in STATI_CHIUSI:
            continue
        # review/approved esclusi sempre (anche da da_assegnare)
        if raw in STATI_REVISIONE:
            esclusi.append({'id': nome, 'tipo': e['tipo'], 'stato': e['stato_raw'],
                            'motivo': 'review/approved — nessuna proposta su lavoro in revisione',
                            'file': e['file']})
            continue
        owner_l = e['owner'].strip().lower()
        # In lavorazione: escluso (anche da da_assegnare)
        if raw in STATI_IN_LAVORAZIONE or e['stato_norm'] == 'in_corso':
            esclusi.append({'id': nome, 'tipo': e['tipo'], 'stato': e['stato_raw'],
                            'owner': e['owner'],
                            'motivo': 'in lavorazione (%s) — escluso dalle proposte' % (e['owner'] or 'owner non indicato'),
                            'file': e['file']})
            continue

        if e['tipo'] == 'TSK':
            if owner_l in owner_non_persona or (not owner_l and 'da designare' in owner_non_persona):
                # Controlla epic_owner_default: mapping valido -> proposta, altrimenti da_assegnare
                epic = e.get('epic', '')
                entry = epic_owner_map.get(epic) if epic else None
                proposta_suggerita = None
                if entry:
                    approved_by = entry.get('approved_by')
                    valid_until_str = str(entry.get('valid_until') or '')
                    owner_default = entry.get('owner')
                    # Tutti e 3 i campi obbligatori presenti + oggi disponibile per valutare scadenza
                    if approved_by and valid_until_str and owner_default and oggi:
                        if valid_until_str >= oggi:
                            proposta_suggerita = {
                                'tipo': 'owner_suggerito',
                                'file_target': e['file'],
                                'campo': 'owner',
                                'valore_attuale': e['owner'] or '',
                                'valore_proposto': owner_default,
                                'tipo_valore': 'suggested_owner',
                                'fonte': 'config/owner_defaults',
                                'approved_by': approved_by,
                                'motivazione': (
                                    'suggerimento automatico — verifica prima di applicare: '
                                    'epic_owner_default per epica «%s» suggerisce «%s» '
                                    '(approved_by: %s, valido fino al %s)'
                                    % (epic, owner_default, approved_by, valid_until_str)
                                ),
                                'confidenza': 'media',
                            }
                if proposta_suggerita:
                    proposte.append(proposta_suggerita)
                else:
                    # Nessun mapping valido: va in da_assegnare (mai in coda di apply)
                    prima_vista = store_prec.get(nome, oggi)
                    da_assegnare.append({
                        'epic': e.get('epic', ''),
                        'file': e['file'],
                        'owner': e['owner'],
                        'prima_vista': prima_vista,
                        'priority': e.get('priority', ''),
                        'tsk_id': nome,
                        'us': e.get('us', ''),
                    })
                continue  # TSK gestito: salta il controllo window (per US)

        # Controllo window su US di sezione
        if e['tipo'] == 'US':
            sezioni_us = us_sezione.get(nome, [])
            for sid in sezioni_us:
                sc = sezioni_cfg.get(sid, {})
                cal = sc.get('calendario') or {}
                pronta_entro_iso = cal.get('pronta_entro')
                if not pronta_entro_iso:
                    continue
                gg_mm = data_gg_mm(pronta_entro_iso)
                if not gg_mm:
                    continue
                window = e['window']
                if not window:
                    proposte.append({
                        'tipo': 'window_mancante',
                        'file_target': e['file'],
                        'campo': 'window',
                        'valore_attuale': None,
                        'valore_proposto': 'entro %s' % gg_mm,
                        'motivazione': 'proposta automatica — verifica prima di applicare: la sezione «%s» ha pronta_entro %s ma la US non ha il campo window' % (sid, pronta_entro_iso),
                        'confidenza': 'media',
                    })
                elif gg_mm not in window:
                    proposte.append({
                        'tipo': 'window_non_allineata',
                        'file_target': e['file'],
                        'campo': 'window',
                        'valore_attuale': window,
                        'valore_proposto': window + ' [pronta_entro %s]' % gg_mm,
                        'motivazione': 'proposta automatica — verifica prima di applicare: la sezione «%s» ha pronta_entro %s (%s) che non compare nel campo window della US' % (sid, pronta_entro_iso, gg_mm),
                        'confidenza': 'bassa',
                    })

    # Ordinamento stabile
    proposte.sort(key=lambda p: (p['tipo'], p['file_target'], p['campo']))
    esclusi.sort(key=lambda ex: ex['id'])
    da_assegnare.sort(key=lambda d: d['tsk_id'])
    return proposte, esclusi, da_assegnare


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True, help='Percorso del file di config operatore (JSON)')
    ap.add_argument('--dry-run', action='store_true',
                    help='Modalita\' esplicita read-only (default sempre): non scrive in management/kanban/')
    ap.add_argument('--ref', default='HEAD', help='Commit git da cui leggere il kanban (default: HEAD)')
    ap.add_argument('--out', default=None, help='File di output JSON proposte (default: stdout)')
    ap.add_argument('--operatore', default=None,
                    help='ID operatore (default: derivato dal nome del file config)')
    ap.add_argument('--aggiorna-store', action='store_true',
                    help='Scrive analytics/coordinamento/<operatore>/da_assegnare.yaml (richiede --oggi)')
    ap.add_argument('--oggi', default=None,
                    help='Data corrente ISO8601 YYYY-MM-DD — obbligatoria con --aggiorna-store '
                         'e se epic_owner_default e\' configurato (niente orologio implicito)')
    a = ap.parse_args(argv)

    if yaml is None:
        print('ERRORE: PyYAML non disponibile — installare con pip install pyyaml', file=sys.stderr)
        return 1

    cfg = json.load(open(a.config, encoding='utf-8'))
    root = risolvi_factory_root(cfg, a.config)
    if pm_report_abilitato(root) is False:
        print(MESSAGGIO_SPENTA)
        return 0
    kanban = cfg.get('kanban_root', 'management/kanban')
    stati = cfg['stati']
    operatore = a.operatore or operatore_da_config(a.config)
    ref_sha = git_rev_parse(root, a.ref)
    owner_non_persona = {v.strip().lower() for v in cfg.get('owner_non_persona', [])}

    # epic_owner_default: mappa epic_id -> entry (ADR-090 D7)
    epic_owner_list = cfg.get('epic_owner_default') or []
    epic_owner_map = {
        str(entry.get('epic_id', '')): entry
        for entry in epic_owner_list
        if entry.get('epic_id')
    }

    # STOP: epic_owner_default configurato richiede --oggi per valutare valid_until
    if epic_owner_map and not a.oggi:
        print('ERRORE: --oggi e\' obbligatorio quando epic_owner_default e\' configurato '
              '(ADR-090 D7 — niente orologio implicito)', file=sys.stderr)
        return 1

    # STOP: --aggiorna-store richiede --oggi per riproducibilita'
    if a.aggiorna_store and not a.oggi:
        print('ERRORE: --oggi e\' obbligatorio con --aggiorna-store '
              '(niente orologio implicito, per riproducibilita\')', file=sys.stderr)
        return 1

    # Legge store del ciclo precedente (se esiste) — ADR-090 D5/D6
    store_path = os.path.join(root, 'analytics', 'coordinamento', operatore, 'da_assegnare.yaml')
    store_sha256 = None
    store_precedente = {}
    if os.path.exists(store_path):
        raw_bytes = open(store_path, 'rb').read()
        store_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        if yaml is not None:
            try:
                loaded = yaml.safe_load(raw_bytes.decode('utf-8', errors='replace')) or []
                if isinstance(loaded, dict):
                    loaded = loaded.get('da_assegnare') or []
                if isinstance(loaded, list):
                    for item in loaded:
                        if isinstance(item, dict) and 'tsk_id' in item and 'prima_vista' in item:
                            store_precedente[str(item['tsk_id'])] = str(item['prima_vista'])
            except Exception:  # noqa: BLE001
                pass  # store corrotto: si riparte senza prima_vista

    # Mappa US -> lista sezioni dalla config
    us_sezione = {}
    sezioni_cfg = {}
    obiettivo_id = cfg.get('vista_pm', {}).get('obiettivo_predefinito_id')
    ob = next((o for o in cfg.get('obiettivi', []) if o['id'] == obiettivo_id), None) if obiettivo_id else None
    if ob:
        for s in ob.get('sezioni', []):
            sezioni_cfg[s['id']] = s
            for us in s.get('us', []):
                us_sezione.setdefault(us, []).append(s['id'])

    # Epiche nel perimetro
    epiche = sorted({e for o in cfg.get('obiettivi', [])
                     for p in o.get('perimetro', [])
                     for e in p.get('selettore', {}).get('epiche', [])})

    # Legge entita' dal kanban al commit (un solo git cat-file --batch per tutti i file del perimetro)
    base = len(kanban.rstrip('/').split('/'))
    nomi = sorted(p for p in epiche_nel_path(git_ls(root, ref_sha, kanban), kanban, epiche)
                  if ID_RE.match(p.split('/')[-1][:-3]) and ID_RE.match(p.split('/')[-1][:-3]).group(2) in ('US', 'TSK'))
    testi = leggi_blob(root, ref_sha, nomi) if nomi else {}
    letti = []
    for path in nomi:
        nome = path.split('/')[-1][:-3]
        tipo = ID_RE.match(nome).group(2)
        dati, errore = frontmatter(testi.get(path))
        if errore or not isinstance(dati, dict):
            continue
        letti.append((nome, tipo, path, path.split('/')[base:], dati))
    epica_us = {}
    for nome, tipo, path, dentro, dati in letti:
        if tipo == 'US':
            epica_us[nome] = da_frontmatter(dati, CAMPI_EP, 'EP') or da_path(dentro, 'EP') or ''
    con_selettore_us = any('us' in p.get('selettore', {}) for o in cfg.get('obiettivi', []) for p in o.get('perimetro', []))
    entita = {}
    for nome, tipo, path, dentro, dati in letti:
        us_nome = (da_frontmatter(dati, CAMPI_US, 'US') or da_path(dentro, 'US') or '') if tipo == 'TSK' else ''
        epic_nome = da_frontmatter(dati, CAMPI_EP, 'EP') or epica_us.get(us_nome) or da_path(dentro, 'EP') or ''
        # con selettore.us restano solo le US elencate e i loro TSK; senza, l'epica intera come prima
        # (l'epica del filtro e' quella del path, come la selezione dei file; il frontmatter puo' dichiararne un'altra)
        if con_selettore_us and not any(nel_perimetro(da_path(dentro, 'EP') or epic_nome, nome if tipo == 'US' else us_nome, o)
                                        for o in cfg.get('obiettivi', [])):
            continue
        entita[nome] = {
            'tipo': tipo,
            'id': nome,
            'stato_raw': str(dati.get('status') or '').strip(),
            'stato_norm': normalizza_stato(dati.get('status'), stati),
            'owner': str(dati.get('owner') or '').strip(),
            'window': str(dati.get('window') or '').strip() or None,
            'file': path,
            'epic': epic_nome,
            'us': us_nome,
            'priority': str(dati.get('priority') or '').strip(),
        }

    proposte, esclusi, da_assegnare = calcola(
        entita, us_sezione, sezioni_cfg, owner_non_persona,
        store_precedente=store_precedente,
        oggi=a.oggi,
        epic_owner_map=epic_owner_map,
    )

    # Scrive store (solo con --aggiorna-store) — ADR-090 D5
    if a.aggiorna_store:
        tmp = store_path + '.tmp'
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
            yaml.safe_dump({'da_assegnare': da_assegnare}, fh, sort_keys=True, allow_unicode=True,
                           default_flow_style=False, indent=2)
        os.replace(tmp, store_path)
        print('store scritto in %s' % store_path, file=sys.stderr)

    config_sha256 = hashlib.sha256(open(a.config, 'rb').read()).hexdigest()

    out_dati = {
        'versione_schema': '1.0',
        'ref_sha': ref_sha,
        'config_sha256': config_sha256,
        'operatore': operatore,
        'dry_run': True,
        'note': ('Il gate AskUserQuestion (conferma umana) e\' obbligatorio prima di applicare '
                 'qualsiasi proposta. L\'applicazione e\' delegata al tpm.'),
        'provenienza': {
            'config_sha256': config_sha256,
            'da_assegnare_sha256': store_sha256,
            'oggi': a.oggi,
            'ref_sha': ref_sha,
        },
        'proposte': proposte,
        'da_assegnare': da_assegnare,
        'esclusi': esclusi,
        'conteggio': {
            'da_assegnare': len(da_assegnare),
            'esclusi': len(esclusi),
            'proposte': len(proposte),
        },
    }

    # Riepilogo su stdout
    print('proponi_kanban: %d proposte, %d da_assegnare, %d esclusi (ref %s, operatore %s)' % (
        len(proposte), len(da_assegnare), len(esclusi), ref_sha[:8], operatore))
    for i, p in enumerate(proposte, 1):
        print('\n[%d] %s — %s' % (i, p['tipo'], p['file_target']))
        print('     campo:           %s' % p['campo'])
        print('     valore_attuale:  %r' % p['valore_attuale'])
        print('     valore_proposto: %r' % p['valore_proposto'])
        print('     confidenza:      %s' % p['confidenza'])
    if da_assegnare:
        print('\nDa assegnare (%d TSK senza owner):' % len(da_assegnare))
        for d in da_assegnare:
            print('  %s [%s] prima_vista=%s' % (
                d['tsk_id'], d.get('priority') or '?', d.get('prima_vista') or 'N/A'))
    if esclusi:
        print('\nEsclusi (%d):' % len(esclusi))
        for ex in esclusi:
            print('  %s [%s] — %s' % (ex['id'], ex['stato'], ex['motivo']))

    # Output JSON
    if a.out:
        scrivi_atomico(a.out, out_dati)
        print('\nproposte scritte in %s' % a.out)
    else:
        json.dump(out_dati, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
        sys.stdout.write('\n')

    return 0


if __name__ == '__main__':
    sys.exit(main())
