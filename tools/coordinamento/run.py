#!/usr/bin/env python3
"""Report PM su richiesta, in qualsiasi momento:
snapshot -> controllo configurazione -> misura -> verifica L0 -> vista HTML -> verifica della vista (anti-regressione) -> controllo HTML.

    python tools/coordinamento/run.py --config analytics/coordinamento/config-<operatore>.json [--uscite <cartella>] [--oggi AAAA-MM-GG] [--fonte commit|worktree] [--ref HEAD]
    python tools/coordinamento/run.py --config analytics/coordinamento/config-<operatore>.json --solo-controllo

Default: kanban letto dal commit HEAD della factory (riproducibile); i file modificati e non committati vengono solo segnalati.
Se la verifica L0 fallisce la vista NON viene generata ed esce con 1. Nessuna scrittura nel kanban.
Gate: `pm_report.enabled: false` in factory.config.yaml della factory_root -> STOP esplicito, exit 0, nessuna uscita;
file o chiave assenti = non governato (si procede). Lo store dei TSK senza owner lo scrive proponi_kanban.py, non questo script.

Uscite in deliverables/coordinamento/report-pm/<operatore>/<AAAA-MM-GG>/:
  snapshot_<sha8>.json, allineamento_<sha8>.json, misura_<sha8>.json   (stesso commit e config => stessi byte)
  vista-pm_<sha8>_<HHMM>.html                                          (l'ora di generazione e' solo nella pagina)
Ultima riga su stdout: RIEPILOGO (o CONTROLLO con --solo-controllo) seguito da JSON, per il riepilogo in chat.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
sys.path.insert(0, QUI)
from percorsi import MESSAGGIO_SPENTA, leggi_factory_config, operatore_da_config, pm_report_abilitato, risolvi_factory_root  # noqa: E402


def _risolvi_factory_root(cfg, config_path):
    return risolvi_factory_root(cfg, config_path)


def _pm_report_abilitato(factory_root):
    """True/False se `pm_report.enabled` e' dichiarato, None se il file o la chiave mancano."""
    return pm_report_abilitato(factory_root)


def _operatore(config_path):
    return operatore_da_config(config_path)


def passo(nome, args):
    r = subprocess.run([PY, os.path.join(QUI, nome), *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        print('STOP: %s ha restituito %d' % (nome, r.returncode))
        sys.exit(r.returncode or 1)
    return r.stdout


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True, help='file di config operatore (es. analytics/coordinamento/config-<operatore>.json)')
    ap.add_argument('--uscite')
    ap.add_argument('--oggi')
    ap.add_argument('--fonte', choices=['commit', 'worktree'], default='commit')
    ap.add_argument('--ref', default='HEAD')
    ap.add_argument('--solo-controllo', action='store_true')
    ap.add_argument('--narrativa', help='narrativa PM (markdown con citazioni [F:percorso]): verificata e inserita come lettura assistita')
    ap.add_argument('--store', help='percorso esplicito del file da_assegnare.yaml (sovrascrive il path derivato da factory_root/operatore)')
    a = ap.parse_args(argv)

    cfg = json.load(open(a.config, encoding='utf-8'))
    factory_root = _risolvi_factory_root(cfg, a.config)
    operatore = _operatore(a.config)
    print('CONFIG: %s | OPERATORE: %s' % (os.path.basename(a.config), operatore))

    # Gate della capability: `pm_report.enabled` in factory.config.yaml. Si ferma solo se il flag
    # e' dichiarato false; una factory senza il file (le fixture dei test) non e' governata.
    abilitata = _pm_report_abilitato(factory_root)
    if abilitata is False:
        print(MESSAGGIO_SPENTA)
        return 0

    uscite = a.uscite or os.path.expanduser(cfg.get('report', {}).get('cartella_uscite',
        os.path.join(factory_root, 'deliverables', 'coordinamento', 'report-pm', operatore)))
    oggi = a.oggi or datetime.date.today().isoformat()
    sha = subprocess.run(['git', '-C', factory_root, 'rev-parse', a.ref if a.fonte == 'commit' else 'HEAD'],
                         capture_output=True, text=True).stdout.strip()
    if not sha:
        print('STOP: impossibile leggere il commit della factory (%s)' % factory_root)
        return 1
    d = os.path.join(uscite, oggi)
    os.makedirs(d, exist_ok=True)
    s8 = sha[:8] + ('' if a.fonte == 'commit' else '-worktree')
    snap = os.path.join(d, 'snapshot_%s.json' % s8)
    allin = os.path.join(d, 'allineamento_%s.json' % s8)
    mis = os.path.join(d, 'misura_%s.json' % s8)
    html = os.path.join(d, 'vista-pm_%s_%s.html' % (s8, datetime.datetime.now().strftime('%H%M')))

    passo('snapshot.py', ['--config', a.config, '--out', snap, '--fonte', a.fonte, '--ref', a.ref])
    passo('controlla_config.py', ['--config', a.config, '--snapshot', snap, '--out', allin, '--ref', a.ref if a.fonte == 'commit' else 'HEAD'])
    al = json.load(open(allin, encoding='utf-8'))
    if a.solo_controllo:
        print('CONTROLLO ' + json.dumps({'allineamento': allin, 'snapshot': snap, 'kanban_commit': sha[:8],
                                         'candidati': al['conteggio'], 'per_tipo': al['per_tipo']}, ensure_ascii=False))
        return 0
    # Thresholds da_assegnare: letti da factory.config.yaml §pm_report.da_assegnare (default 7/14)
    da_assegnare_cfg = ((leggi_factory_config(factory_root) or {}).get('pm_report') or {}).get('da_assegnare') or {}
    stale_alert_days = str(da_assegnare_cfg.get('stale_alert_days', 7))
    escalation_days = str(da_assegnare_cfg.get('escalation_days', 14))
    store_path = a.store if a.store else os.path.join(factory_root, 'analytics', 'coordinamento', operatore, 'da_assegnare.yaml')
    store_args = ['--store', store_path] if os.path.exists(store_path) else []

    passo('aggrega.py', ['--config', a.config, '--snapshot', snap, '--out', mis, '--oggi', oggi,
                          '--stale-alert-days', stale_alert_days, '--escalation-days', escalation_days] + store_args)
    passo('verifica_l0.py', ['--snapshot', snap, '--misura', mis, '--config', a.config,
                               '--stale-alert-days', stale_alert_days, '--escalation-days', escalation_days] + store_args)
    fg = os.path.join(d, 'file_grandi.json')
    passo('file_grandi.py', ['--config', a.config, '--out', fg])
    extra = []
    if a.narrativa:
        nv = os.path.join(d, 'narrativa_%s.json' % s8)
        passo('verifica_citazioni.py', ['--misura', mis, '--narrativa', a.narrativa, '--out', nv])
        extra = ['--narrativa', nv]
    passo('vista_pm.py', ['--config', a.config, '--misura', mis, '--out', html, '--allineamento', allin, '--file-grandi', fg] + extra)
    passo('verifica_vista.py', ['--misura', mis, '--html', html])
    passo('html_check.py', [html])

    m = json.load(open(mis, encoding='utf-8'))
    riepilogo = {
        'html': html, 'misura': mis, 'kanban_commit': sha[:8], 'fonte': a.fonte,
        'non_committati': len(m['provenienza']['kanban_non_committati']),
        'non_pushati': len((m['provenienza'].get('non_pushati') or {}).get('commit') or []),
        'config_non_allineata': al['conteggio'], 'config_per_tipo': al['per_tipo'],
        'obiettivi': [{
            'id': o['id'], 'nome': o['nome'], 'tipo': o['tipo'], 'data_target': o['data_target'],
            'giorni_lavorativi_rimasti': o['giorni_lavorativi_rimasti'], 'misurato': bool(o['epiche']),
            'epiche': [{'id': e['id'], 'fatto': e['conteggi']['fatto'], 'base': e['conteggi']['base_calcolo'], 'pct': e['conteggi']['pct'],
                        'chiusi_senza_esito': e['conteggi']['chiuso_senza_esito'],
                        'in_attesa_prerequisito': len({x['tsk'] for x in e['prerequisiti']['in_attesa_prerequisito_aperto']})} for e in o['epiche']],
            'sezioni': [{'id': s['id'], 'fatto': s['conteggi']['fatto'], 'base': s['conteggi']['base_calcolo'], 'in_corso': s['conteggi']['in_corso'],
                         'stato_config': s['stato_config'], 'ondata': s['ondata']} for s in o['sezioni']],
            'riepilogo_sezioni': o['riepilogo_sezioni'],
            'dipendenti': ['%s (%s)' % (d['nome'], ', '.join(d['us'])) for d in o['dipendenti']],
            'copertura': o['copertura'], 'avanzamento_pct': o['conteggi']['pct'] if o['epiche'] else None,
            'avvisi': [{'livello': x['livello'], 'codice': x['codice'], 'testo': x['testo']} for x in o['avvisi']]} for o in m['obiettivi']],
        'tsk_illeggibili': len(m['copertura']['tsk_illeggibili']),
        'qualita_dato': len(m['qualita_dato']),
    }
    print('RIEPILOGO ' + json.dumps(riepilogo, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
