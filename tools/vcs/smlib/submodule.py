"""Risoluzione dei submodule da .gitmodules.

Match ESATTO o ancorato allo slash finale: il target `my-repo` risolve
`code_repos/my-repo` ma NON `code_repos/my-repo-extra` (elimina la
collisione di prefisso — ex BUG-2 della versione bash).

Nessun filtro di prefisso hardcoded: i path dei submodule sono determinati
dal .gitmodules del repo, non da una costante di directory (vedi factory_config
per la lista guidata dalla config).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .gitutil import git_lines


def list_submodule_paths(root: Path) -> List[str]:
    """Lista dei path dei submodule registrati in .gitmodules."""
    gitmodules = root / ".gitmodules"
    if not gitmodules.exists():
        return []
    lines = git_lines(
        ["config", "--file", str(gitmodules), "--get-regexp", r"submodule\..*\.path"],
        cwd=root,
    )
    paths: List[str] = []
    for line in lines:
        # Formato: "submodule.<name>.path <value>"
        parts = line.split(None, 1)
        if len(parts) == 2:
            paths.append(parts[1].strip())
    return paths


def resolve_submodule(root: Path, target: str) -> Optional[str]:
    """Path del submodule il cui nome corrisponde a `target`.

    Ritorna il path relativo (es. 'code_repos/portale-servizi') o None.
    """
    for value in list_submodule_paths(root):
        if value == target or value.endswith("/" + target):
            return value
    return None


def _section_name_for_path(root: Path, sm_path: str) -> Optional[str]:
    """Nome della sezione [submodule "name"] corrispondente al path dato.

    In .gitmodules il nome della sezione puo' differire dal path:
    [submodule "my-name"]
        path = code_repos/my-path
    Questa funzione risolve il mapping path -> nome sezione leggendo
    tutte le chiavi submodule.*.path da .gitmodules.
    """
    gitmodules = root / ".gitmodules"
    if not gitmodules.exists():
        return None
    lines = git_lines(
        ["config", "--file", str(gitmodules), "--get-regexp", r"submodule\..*\.path"],
        cwd=root,
    )
    for line in lines:
        # Formato: "submodule.<name>.path <value>"
        parts = line.split(None, 1)
        if len(parts) == 2:
            value = parts[1].strip()
            if value == sm_path:
                key = parts[0]  # "submodule.<name>.path"
                inner = key[len("submodule."):]
                name = inner[: -len(".path")] if inner.endswith(".path") else inner
                return name
    return None


def is_archived(root: Path, sm_path: str) -> bool:
    """True se il submodule e' marcato come archiviato in .gitmodules.

    Legge la chiave custom `archived = true` dalla sezione del submodule
    in .gitmodules tramite `git config -f .gitmodules --get`.
    Supporta sezioni dove il nome differisce dal path (risolve il mapping
    tramite _section_name_for_path). Valori accettati: true/false git-style.

    Fonte unica: .gitmodules (non factory.config.yaml). Due fonti
    richiederebbero una regola di precedenza dichiarata e raddoppierebbero
    il rischio di inconsistenza; .gitmodules e' il file che git stesso legge.
    """
    gitmodules = root / ".gitmodules"
    if not gitmodules.exists():
        return False
    section_name = _section_name_for_path(root, sm_path)
    if section_name is None:
        return False
    lines = git_lines(
        ["config", "--file", str(gitmodules), "--get",
         f"submodule.{section_name}.archived"],
        cwd=root,
    )
    return bool(lines) and lines[0].strip().lower() == "true"


def default_targets(root: Path) -> List[str]:
    """Submodule su cui lavorano sm_status/sm_doctor/sm_update/sm_checkout senza --target.

    Ordine di .gitmodules. Con `vcs_tooling.submodule_scope: gitmodules` tutti; altrimenti
    quelli dichiarati in code_paths[] (vcs.mode: submodule), abbinati per path o per nome.
    """
    from .factory_config import list_submodule_code_paths, submodule_scope
    all_paths = list_submodule_paths(root)
    if submodule_scope(root) == "gitmodules":
        return all_paths
    entries = list_submodule_code_paths(root)
    if not entries:
        return []
    names = {e.get("name", "").strip() for e in entries}
    paths = {e.get("path", "").strip() for e in entries}
    return [p for p in all_paths if p in paths or Path(p).name in names]
