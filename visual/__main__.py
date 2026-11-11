"""`python3 -m visual` — avvio della plancia (US-279).

A capability non configurata esce con codice **0** e spiega come abilitarla: un
fallback esplicito, non un errore. E' la stessa convenzione di `/kanban-status`.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from visual.config import load, project_root
from visual.server import PortBusy, serve

HINT = """La plancia e' opt-in ed e' spenta.

Per abilitarla, in factory.config.yaml:

    visual_channel:
      enabled: true

Oppure, senza toccare la configurazione, solo per questa esecuzione:

    python3 -m visual --force
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m visual",
                                     description="Plancia locale sull'attivita' della factory (EP-067, sola lettura).")
    parser.add_argument("--port", type=int, help="porta (default dal blocco visual_channel)")
    parser.add_argument("--host", help="interfaccia di ascolto (default 127.0.0.1)")
    parser.add_argument("--force", action="store_true", help="avvia anche a gate spento")
    parser.add_argument("--check", action="store_true", help="stampa la configurazione risolta ed esce")
    parser.add_argument("--root", type=Path,
                        help="radice della factory da osservare (default: quella che contiene "
                             "questo pacchetto). Serve per puntare la plancia a una factory "
                             "derivata, ed e' cio' che rende il gate verificabile da un test "
                             "senza dipendere dalla configurazione del repo corrente.")
    args = parser.parse_args(argv)

    root = (args.root or project_root()).resolve()
    config = load(root)
    if args.port:
        config = replace(config, port=args.port)
    if args.host:
        config = replace(config, host=args.host)

    if args.check:
        print(f"radice            : {root}")
        print(f"visual_channel    : {'attivo' if config.enabled else 'spento (opt-in)'}")
        print(f"indirizzo         : {config.address}")
        print(f"pattern_version   : {config.pattern_version or 'non dichiarata'}")
        print(f"soglia stantio    : {config.stale_after_seconds}s")
        return 0

    if not config.enabled and not args.force:
        print(HINT)
        return 0                      # fallback esplicito, non un errore

    try:
        serve(root, config)
    except PortBusy as busy:
        print(f"  {busy}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
