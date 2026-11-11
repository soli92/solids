"""Strip attribution AI dai messaggi di commit -- §ai_policy (PATTERN §23.9).

Thin wrapper che delega a tools/vcs/ai_policy.py (fonte unica dei pattern
AI e degli ID kanban). Nessuna logica duplicata.

Esporta la stessa API di smlib.aipolicy di portale-servizi-factory per
compatibilita' dei test portati.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List, Tuple


def _import_ai_policy():
    """Importa ai_policy.py dalla directory tools/vcs/ (percorso assoluto)."""
    here = Path(__file__).resolve()
    # tools/vcs/smlib/aipolicy.py -> tools/vcs/ai_policy.py
    ai_policy_path = here.parent.parent / "ai_policy.py"
    if not ai_policy_path.exists():
        raise ImportError(f"tools/vcs/ai_policy.py non trovato: {ai_policy_path}")
    spec = importlib.util.spec_from_file_location("_vcs_ai_policy", ai_policy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossibile caricare: {ai_policy_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_mod = _import_ai_policy()

# Re-export dalla fonte unica
AI_SUBSTRINGS: Tuple[str, ...] = tuple(getattr(_mod, "AI_SUBSTRINGS", ()))
FACTORY_ID_RE = getattr(_mod, "FACTORY_ID_RE", None)


def is_ai_attribution(line: str) -> bool:
    return _mod.is_ai_attribution(line)


def strip_ai_attribution(message: str) -> Tuple[str, List[str]]:
    return _mod.strip_ai_attribution(message)


def find_factory_ids(text: str) -> List[str]:
    return _mod.find_factory_ids(text)


def strip_factory_ids(message: str) -> Tuple[str, List[str]]:
    return _mod.strip_factory_ids(message)
