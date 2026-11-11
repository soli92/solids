#!/usr/bin/env python3
"""
sm_update.py -- aggiorna un submodule da origin o da un clone locale.

Porta cross-platform generalizzata (US-311 EP-069): nessuna costante verticale.
Il target e' richiesto se ci sono piu' submodule dichiarati in config; se ne
e' dichiarato uno solo, viene usato di default.

USO:
  python3 tools/vcs/sm_update.py [--merge | --rebase] [--target <nome-repo>]
  python3 tools/vcs/sm_update.py --from-local [<branch>] [--target <nome-repo>]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smlib import (
    default_targets,
    color,
    factory_root,
    is_archived,
    list_submodule_paths,
    load_env_file,
    resolve_submodule,
)
from smlib.factory_config import default_target, list_submodule_code_paths
from smlib.gitutil import current_branch, git_out, git_run, rev_parse


def _config_sm_paths(root: Path) -> list:
    """Target senza --target: vcs_tooling.submodule_scope (smlib.default_targets)."""
    return default_targets(root)


def _resolve_target(root: Path, target: str):
    target = target or default_target(root) or ""   # vcs_tooling.default_target
    if target:
        return resolve_submodule(root, target)

    sm_paths = _config_sm_paths(root)
    if len(sm_paths) == 1:
        return sm_paths[0]
    elif len(sm_paths) > 1:
        names = ", ".join(Path(p).name for p in sm_paths)
        print(color.red(
            f"Piu' submodule dichiarati ({names}): specifica --target <nome>."))
        return None
    else:
        print(color.yellow(
            "Nessun submodule dichiarato in factory.config.yaml "
            "(code_paths[] con vcs.mode: submodule)."))
        return None


def _local_repo_for(root: Path, target: str) -> str:
    """Path del clone locale per il target da .env.local-repos o env."""
    env_file = root / "tools" / "vcs" / ".env.local-repos"
    values = load_env_file(env_file) if env_file.exists() else {}
    key = "LOCAL_REPO_" + target.upper().replace("-", "_")
    return values.get(key) or os.environ.get(key, "")


def _pointer_sha(root: Path, sm_key: str) -> str:
    raw = git_out(["submodule", "status", sm_key], cwd=root, default="")
    parts = raw.split()
    return parts[0].lstrip("+-") if parts else ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Aggiorna un submodule.")
    parser.add_argument("branch", nargs="?", default="",
                        help="Branch (per --from-local).")
    parser.add_argument("--target", default="",
                        help="Nome del submodule (obbligatorio se piu' di uno).")
    parser.add_argument("--from-local", action="store_true",
                        help="Aggiorna da clone locale.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--merge", dest="mode", action="store_const", const="--merge")
    mode.add_argument("--rebase", dest="mode", action="store_const", const="--rebase")
    parser.set_defaults(mode="--merge")
    args = parser.parse_args(argv)

    root = factory_root()
    sm_key = _resolve_target(root, args.target)
    if not sm_key:
        print("Submodule disponibili:")
        for value in list_submodule_paths(root):
            print(f"  {value}")
        return 1

    if is_archived(root, sm_key):
        target_name = Path(sm_key).name
        print(color.red(
            f"[{target_name}] Submodule archiviato (read-only): aggiornamento non consentito."))
        print("  Il repo e' archiviato sull'host remoto e non accetta push.")
        print("  Nessun fetch eseguito.")
        return 1

    target_name = Path(sm_key).name
    sm_path = root / sm_key

    if not (sm_path / ".git").exists():
        print(color.yellow("Submodule non inizializzato. Inizializzo..."))
        git_run(
            ["-c", "protocol.file.allow=always", "submodule", "update", "--init", sm_key],
            cwd=root,
        )

    if args.from_local:
        branch = args.branch or current_branch(sm_path)
        if not branch:
            print(color.red(
                "Branch non determinabile (HEAD detached?). Specificalo esplicitamente."))
            print(f"Uso: sm_update.py --from-local <branch> --target {target_name}")
            return 1

        local_repo = _local_repo_for(root, target_name)
        if not local_repo:
            print(color.red(
                f"Nessun clone locale configurato per '{target_name}'."))
            print("Crea tools/vcs/.env.local-repos e imposta:")
            key = "LOCAL_REPO_" + target_name.upper().replace("-", "_")
            print(f"  {key}=/path/al/repo")
            return 1

        if not (Path(local_repo) / ".git").exists():
            print(color.red(f"Clone locale non trovato: {local_repo}"))
            return 1

        print(color.yellow("Fetch da clone locale (nessuna rete richiesta)..."))
        print(f"  Sorgente: {local_repo}")
        git_run(["-c", "protocol.file.allow=always", "-C", str(sm_path),
                 "fetch", "local"])

        print(color.yellow(f"Merge branch '{branch}' da local..."))
        git_run(["-C", str(sm_path), "merge", f"local/{branch}"])

        commit = rev_parse("HEAD", cwd=sm_path, short=True)
        print(color.green(f"[{target_name}] aggiornato da clone locale."))
        print(f"  Branch : {branch}")
        print(f"  Commit : {commit}")
    else:
        print(color.yellow(
            f"Aggiornamento [{target_name}] da origin ({args.mode})..."))
        git_run(["submodule", "update", "--remote", args.mode, sm_key], cwd=root)

        commit = rev_parse("HEAD", cwd=sm_path, short=True)
        branch = current_branch(sm_path) or "detached"
        print(color.green(f"[{target_name}] aggiornato da origin."))
        print(f"  Branch : {branch}")
        print(f"  Commit : {commit}")

    print()
    pointer = _pointer_sha(root, sm_key)
    full = rev_parse("HEAD", cwd=sm_path)
    if pointer != full:
        print(color.yellow("Puntatore factory cambiato -> aggiorna con:"))
        print(
            "  "
            + color.cyan(
                f"python3 tools/vcs/sm_commit.py --pointer-only --target {target_name}")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
