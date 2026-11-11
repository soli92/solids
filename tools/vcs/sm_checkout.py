#!/usr/bin/env python3
"""
sm_checkout.py -- checkout di un branch nel submodule + allineamento fetch.

Porta cross-platform generalizzata (US-311 EP-069): nessuna costante verticale.
Il target e' richiesto se ci sono piu' submodule dichiarati in config; se ne
e' dichiarato uno solo, viene usato di default.

USO:
  python3 tools/vcs/sm_checkout.py <branch> [--target <nome-repo>] [--no-pull]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smlib import (
    default_targets,
    color,
    factory_root,
    is_archived,
    list_submodule_paths,
    resolve_submodule,
)
from smlib.factory_config import default_target, list_submodule_code_paths
from smlib.gitutil import GitError, current_branch, git_lines, git_run, rev_parse


def _config_sm_paths(root: Path) -> list:
    """Target senza --target: vcs_tooling.submodule_scope (smlib.default_targets)."""
    return default_targets(root)


def _print_targets(root: Path) -> None:
    print("Submodule disponibili:")
    for value in list_submodule_paths(root):
        print(f"  {value}")


def _resolve_target(root: Path, target: str):
    """Risolve il target: esplicito o auto-select se uno solo in config."""
    target = target or default_target(root) or ""   # vcs_tooling.default_target
    if target:
        return resolve_submodule(root, target)

    sm_paths = _config_sm_paths(root)
    if len(sm_paths) == 1:
        return sm_paths[0]
    elif len(sm_paths) > 1:
        names = ", ".join(Path(p).name for p in sm_paths)
        print(color.red(
            f"Piu' submodule dichiarati in config ({names}): "
            f"specifica --target <nome>."))
        return None
    else:
        print(color.yellow(
            "Nessun submodule dichiarato in factory.config.yaml "
            "(code_paths[] con vcs.mode: submodule)."))
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Checkout di un branch nel submodule.",
    )
    parser.add_argument("branch", nargs="?", default="",
                        help="Branch da fare checkout.")
    parser.add_argument("--target", default="",
                        help="Nome del submodule (obbligatorio se piu' di uno).")
    parser.add_argument("--no-pull", action="store_true",
                        help="Non fare pull dopo il checkout.")
    args = parser.parse_args(argv)

    root = factory_root()
    sm_key = _resolve_target(root, args.target)
    if not sm_key:
        _print_targets(root)
        return 1

    if is_archived(root, sm_key):
        target_name = Path(sm_key).name
        print(color.red(
            f"[{target_name}] Submodule archiviato (read-only): checkout non consentito."))
        print("  Il repo e' archiviato: fetch e push sarebbero rifiutati dall'host remoto.")
        print("  Nessuna operazione eseguita.")
        return 1

    target_name = Path(sm_key).name
    sm_path = root / sm_key
    initialized = (sm_path / ".git").exists()

    if not args.branch:
        print(color.red(
            f"Uso: sm_checkout.py <branch> [--target {target_name}] [--no-pull]"))
        print()
        if initialized:
            print("Branch disponibili in " + color.cyan(target_name) + ":")
            for line in git_lines(["branch", "-r"], cwd=sm_path):
                name = line.strip()
                if name.startswith("origin/"):
                    name = name[len("origin/"):]
                if name.startswith("HEAD"):
                    continue
                print(f"  {name}")
        else:
            print(color.yellow(f"Submodule non ancora inizializzato: {sm_key}"))
        return 1

    if not initialized:
        print(color.yellow("Submodule non inizializzato. Inizializzo..."))
        git_run(["submodule", "update", "--init", sm_key], cwd=root)

    current = current_branch(sm_path) or "detached"
    if current == args.branch:
        print(color.cyan(f"Gia' su branch '{args.branch}'."))
    else:
        print(color.yellow("Fetch remote..."))
        git_run(["fetch", "origin"], cwd=sm_path)

        print(color.yellow(f"Checkout '{args.branch}'..."))
        try:
            git_run(["checkout", args.branch], cwd=sm_path)
        except GitError:
            git_run(["checkout", "-b", args.branch, f"origin/{args.branch}"], cwd=sm_path)

    if not args.no_pull:
        print(color.yellow(f"Pull origin/{args.branch}..."))
        git_run(["pull", "origin", args.branch], cwd=sm_path)

    commit = rev_parse("HEAD", cwd=sm_path, short=True)
    print(color.green(f"[{target_name}] branch '{args.branch}' @ {commit}"))
    print()
    print("Puntatore factory " + color.yellow("out of sync") + ".")
    print(
        "Esegui: "
        + color.cyan(
            f"python3 tools/vcs/sm_commit.py --pointer-only --target {target_name}")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
