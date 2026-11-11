"""Risoluzione dei percorsi, operatore e gate della capability, condivisi dagli script del report."""

import os
import subprocess


def risolvi_factory_root(cfg, config_path):
    """factory_root assoluto resta com'e'; se relativo (default ".") si risolve rispetto alla root
    del repository git che contiene il file di config, cosi' la config puo' stare in qualunque
    sottocartella della factory. Fuori da un repository git si ripiega sulla cartella della config."""
    fr = cfg.get('factory_root', '.')
    if os.path.isabs(fr):
        return fr
    cartella = os.path.dirname(os.path.abspath(config_path))
    r = subprocess.run(['git', '-C', cartella, 'rev-parse', '--show-toplevel'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    base = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else cartella
    return os.path.normpath(os.path.join(base, fr))


def operatore_da_config(config_path):
    """Operatore dal nome del file di config: config-<operatore>.json (altrimenti il nome senza estensione)."""
    nome = os.path.basename(config_path)
    if nome.startswith('config-') and nome.endswith('.json'):
        return nome[len('config-'):-len('.json')]
    return os.path.splitext(nome)[0]


def leggi_factory_config(factory_root):
    """Contenuto di factory.config.yaml come dict; None se il file manca o non e' leggibile."""
    percorso = os.path.join(factory_root, 'factory.config.yaml')
    if not os.path.exists(percorso):
        return None
    try:
        import yaml
        with open(percorso, encoding='utf-8') as fh:
            dati = yaml.safe_load(fh.read())
    except Exception:  # noqa: BLE001 - config illeggibile = non governato, come un file assente
        return None
    return dati if isinstance(dati, dict) else None


def pm_report_abilitato(factory_root):
    """True/False se `pm_report.enabled` e' dichiarato, None se il file o la chiave mancano (non governato)."""
    fc = leggi_factory_config(factory_root)
    if fc is None:
        return None
    valore = (fc.get('pm_report') or {}).get('enabled')
    return valore if isinstance(valore, bool) else None


MESSAGGIO_SPENTA = ("STOP: pm_report.enabled e' false in factory.config.yaml: capability spenta, "
                    "nessuna uscita prodotta. Accenderla e' una modifica di factory.config.yaml, fuori da questi script.")
