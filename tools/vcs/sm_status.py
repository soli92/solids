#!/usr/bin/env python3
"""
sm_status.py -- stato di factory + submodule dichiarati in factory.config.yaml.

Porta cross-platform generalizzata (US-311 EP-069): nessuna costante verticale
(nessun nome factory cablato, nessun prefisso directory). Read-only: nessuna
mutazione.

USO:
  python3 tools/vcs/sm_status.py [--target <nome>]
  (default: mostra tutti i submodule dichiarati in config)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smlib import (
    default_targets,
    color,
    factory_name,
    factory_root,
    is_archived,
    list_submodule_paths,
    resolve_submodule,
)
from smlib.factory_config import list_submodule_code_paths
from smlib.gitutil import count, current_branch, git_out, rev_parse


def _pointer_sha(root: Path, sm_key: str) -> str:
    """SHA del puntatore TRACCIATO dal padre (gitlink in HEAD)."""
    return git_out(["rev-parse", f"HEAD:{sm_key}"], cwd=root, default="")


def show_submodule(root: Path, sm_key: str) -> None:
    sm_path = root / sm_key
    archived = is_archived(root, sm_key)
    label = " " + color.yellow("[archiviato (read-only)]") if archived else ""
    print(color.cyan(f"=== Submodule: {sm_key} ===" + label))

    git_marker = sm_path / ".git"
    if not git_marker.exists():
        if archived:
            print("  Clone non presente (archiviato: nessuna azione richiesta).")
        else:
            print(
                "  "
                + color.yellow("Non inizializzato.")
                + f' Esegui: git submodule update --init "{sm_key}"'
            )
        return

    branch = current_branch(sm_path) or "(detached HEAD)"
    commit = rev_parse("HEAD", cwd=sm_path, short=True)
    staged = count(["diff", "--cached", "--name-only"], cwd=sm_path)
    modified = count(["diff", "--name-only"], cwd=sm_path)
    untracked = count(["ls-files", "--others", "--exclude-standard"], cwd=sm_path)

    print("  Branch   : " + color.yellow(branch))
    print(f"  Commit   : {commit}")
    print(f"  Staged   : {staged} file")
    print(f"  Modified : {modified} file")
    print(f"  Untracked: {untracked} file")

    if staged or modified or untracked:
        print("  " + color.yellow("-> Modifiche non committate nel submodule"))

    # Per i submodule archiviati la divergenza dal puntatore factory non e' un problema:
    # il repo e' read-only e non puo' ricevere push; non si segnala drift.
    if archived:
        return

    factory_ptr = _pointer_sha(root, sm_key)
    actual = rev_parse("HEAD", cwd=sm_path)

    if factory_ptr and factory_ptr == actual:
        print("  " + color.green("Puntatore in sync") + f" -- {factory_ptr[:9]}")
    else:
        name = Path(sm_key).name
        print(
            "  "
            + color.yellow("Puntatore out of sync")
            + f" -- factory: {factory_ptr[:9]} | HEAD: {actual[:9]}"
        )
        print(f"  -> python3 tools/vcs/sm_commit.py --pointer-only --target {name}")


def _config_sm_paths(root: Path) -> list:
    """Target senza --target: vcs_tooling.submodule_scope (smlib.default_targets)."""
    return default_targets(root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Stato factory + submodule (read-only).",
    )
    parser.add_argument("--target", default="",
                        help="Mostra solo il submodule indicato.")
    args = parser.parse_args(argv)

    root = factory_root()
    name = factory_name(root)

    print(color.cyan(f"=== Factory: {name} ==="))
    print("  Branch   : " + color.yellow(current_branch(root) or "(detached)"))
    print(f"  Staged   : {count(['diff', '--cached', '--name-only'], cwd=root)} file")
    print(f"  Modified : {count(['diff', '--name-only'], cwd=root)} file")
    print(
        f"  Untracked: "
        f"{count(['ls-files', '--others', '--exclude-standard'], cwd=root)} file"
    )
    print()

    if args.target:
        sm_key = resolve_submodule(root, args.target)
        if not sm_key:
            print(color.red(f"Target non trovato in .gitmodules: '{args.target}'"))
            print("Submodule disponibili:")
            for value in list_submodule_paths(root):
                print(f"  {value}")
            return 1
        show_submodule(root, sm_key)
    else:
        targets = _config_sm_paths(root)
        if not targets:
            print(color.cyan(
                "Nessun submodule dichiarato in factory.config.yaml "
                "(code_paths[] con vcs.mode: submodule)."))
            return 0
        for value in targets:
            show_submodule(root, value)
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
