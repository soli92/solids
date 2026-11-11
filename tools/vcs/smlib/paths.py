"""Risoluzione dei path base della factory, indipendente dalla CWD."""
from __future__ import annotations

from pathlib import Path


def factory_root() -> Path:
    """Root della factory.

    Questo file e' tools/vcs/smlib/paths.py. La root e' tre livelli sopra:
      parents[0] = smlib/
      parents[1] = vcs/
      parents[2] = tools/
      parents[3] = factory root

    Non dipende dalla directory corrente: gli script funzionano invocati
    da qualsiasi CWD.
    """
    return Path(__file__).resolve().parents[3]
