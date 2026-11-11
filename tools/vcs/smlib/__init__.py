"""
smlib -- libreria condivisa per gli script di gestione submodule della factory.

stdlib-only, cross-platform (macOS / Linux / Windows: cmd, PowerShell, Git Bash).
Derivata dalla versione di portale-servizi-factory (ADR-077), generalizzata per
la flotta: nessuna costante verticale (host, nome repo, prefisso directory).

Moduli:
  - paths          : factory_root()
  - ui             : colorazione TTY-aware (NO_COLOR rispettato)
  - gitutil        : wrapper subprocess su git
  - submodule      : risoluzione target da .gitmodules (match esatto)
  - factory_config : parse submodule code_paths da factory.config.yaml
  - aipolicy       : strip attribution AI §ai_policy (wrapper su ai_policy.py)
"""
from .paths import factory_root
from .ui import Color, color
from .aipolicy import (
    strip_ai_attribution,
    is_ai_attribution,
    AI_SUBSTRINGS,
    find_factory_ids,
    strip_factory_ids,
    FACTORY_ID_RE,
)
from .submodule import resolve_submodule, list_submodule_paths, is_archived, default_targets
from .factory_config import (
    resolve_base_branch,
    list_submodule_code_paths,
    suppress_ai_traces,
    submodule_scope,
    factory_name,
    load_env_file,
)

__all__ = [
    "factory_root",
    "Color",
    "color",
    "strip_ai_attribution",
    "is_ai_attribution",
    "AI_SUBSTRINGS",
    "find_factory_ids",
    "strip_factory_ids",
    "FACTORY_ID_RE",
    "resolve_submodule",
    "list_submodule_paths",
    "is_archived",
    "resolve_base_branch",
    "list_submodule_code_paths",
    "default_targets",
    "submodule_scope",
    "suppress_ai_traces",
    "factory_name",
    "load_env_file",
]
