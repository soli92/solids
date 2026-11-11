#!/usr/bin/env python3
"""File di testo grandi della factory (oltre una soglia di righe), misurati a ogni report: finiscono nei prompt di verifica
e nel prompt del subagente, per evitare letture integrali che saturano il contesto.

    python file_grandi.py --config config-base.json --out file_grandi.json [--soglia 2000]

Conta le righe dei file tracciati da git (.md .yaml .yml .json .jsonl .txt). I submodule non sono file e restano fuori
per costruzione; altri prefissi da escludere stanno in config `file_grandi.escludi` (lista, default vuota). Sola lettura.
"""
import argparse
import json
import os
import subprocess
import sys

from percorsi import risolvi_factory_root


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--soglia', type=int, default=None, help='default: config file_grandi.soglia, altrimenti 2000')
    a = ap.parse_args(argv)
    cfg = json.load(open(a.config, encoding='utf-8'))
    root = risolvi_factory_root(cfg, a.config)
    fg_cfg = cfg.get('file_grandi') or {}
    a.soglia = a.soglia or int(fg_cfg.get('soglia', 2000))
    escludi = tuple(str(x).rstrip('/') + '/' for x in fg_cfg.get('escludi', []))
    nomi = subprocess.run(['git', '-C', root, 'ls-files', '--', '*.md', '*.yaml', '*.yml', '*.json', '*.jsonl', '*.txt'],
                          capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.splitlines()
    grandi = []
    for n in nomi:
        if escludi and n.startswith(escludi):
            continue
        if not os.path.isfile(os.path.join(root, n)):
            continue  # submodule (gitlink) o file assente dal disco
        try:
            with open(os.path.join(root, n), encoding='utf-8', errors='ignore') as fh:
                righe = sum(1 for _ in fh)
        except OSError:
            continue
        if righe > a.soglia:
            grandi.append({'path': n, 'righe': righe})
    grandi.sort(key=lambda x: (-x['righe'], x['path']))
    with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'soglia': a.soglia, 'file': grandi}, fh, ensure_ascii=False, indent=1)
    print('file grandi (> %d righe): %d -> %s' % (a.soglia, len(grandi), a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
