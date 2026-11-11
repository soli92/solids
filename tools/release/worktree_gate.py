#!/usr/bin/env python3
"""
worktree_gate.py — Gate locali su SHA immutabile tramite git worktree.

Crea un worktree detached su uno SHA specifico, esegue i comandi gate in
ordine, e garantisce il cleanup anche in caso di errore o interruzione.

Invarianti:
  R.WG1  worktree sempre --detach (nessun branch spostato)
  R.WG2  hooks git disabilitati: -c core.hooksPath=/dev/null
  R.WG3  cleanup garantito anche su errore (atexit + signal handler)
  R.WG4  exit code di ogni comando letto senza pipe
  R.WG5  worktree in directory temporanea, mai nel repo

Uso:
  python3 tools/release/worktree_gate.py \\
    --repo <path_repo> \\
    --sha <sha_commit> \\
    --cmd "npm run lint" \\
    --cmd "npm test" \\
    [--node-modules-symlink <path>] \\
    [--workdir <subdir_nel_wt>]

Exit 0  = tutti i comandi PASS
Exit 1  = almeno un comando FAIL (con output del comando fallito)
"""

import argparse
import atexit
import os
import shutil
import signal
import subprocess
import sys
import tempfile


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Gate locali su SHA immutabile tramite git worktree."
    )
    p.add_argument("--repo", required=True, help="Path assoluto al repo git")
    p.add_argument("--sha", required=True, help="SHA del commit su cui eseguire i gate")
    p.add_argument(
        "--cmd",
        dest="commands",
        action="append",
        default=[],
        metavar="CMD",
        help="Comando gate (ripetibile, eseguito in ordine)",
    )
    p.add_argument(
        "--node-modules-symlink",
        default="",
        help="Path assoluto da linkare come node_modules nel worktree",
    )
    p.add_argument(
        "--workdir",
        default="",
        help="Sottodirectory del worktree da usare come cwd (default: root worktree)",
    )
    return p.parse_args()


def run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Esegue un comando e restituisce il risultato con stdout+stderr combinati."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def create_worktree(repo: str, sha: str, wt_path: str) -> None:
    """Crea un worktree detached con hooks disabilitati (R.WG1, R.WG2)."""
    # Fetch best-effort (non bloccante se il remote non e' raggiungibile)
    run(["git", "-C", repo, "fetch", "--quiet", "origin"])

    result = run([
        "git", "-C", repo,
        "-c", "core.hooksPath=/dev/null",
        "worktree", "add", "--detach", wt_path, sha,
    ])
    if result.returncode != 0:
        print(f"[worktree-gate ERROR] git worktree add fallito:\n{result.stdout}", file=sys.stderr)
        sys.exit(1)


def remove_worktree(repo: str, wt_path: str) -> None:
    """Rimuove il worktree (R.WG3). Chiamata da atexit e signal handler."""
    if os.path.isdir(wt_path):
        run(["git", "-C", repo, "worktree", "remove", "--force", wt_path])


def setup_symlinks(wt_path: str, node_modules_symlink: str) -> None:
    """Crea il symlink node_modules se richiesto."""
    if not node_modules_symlink:
        return
    target = os.path.join(wt_path, "node_modules")
    if os.path.exists(target) or os.path.islink(target):
        return
    os.symlink(node_modules_symlink, target)
    print(f"[worktree-gate] symlink node_modules -> {node_modules_symlink}")


def run_gates(wt_path: str, commands: list[str], workdir: str) -> int:
    """
    Esegue i comandi gate in ordine.
    Exit code letto senza pipe (R.WG4).
    Restituisce 0 se tutti i comandi PASS, 1 al primo FAIL.
    """
    cwd = os.path.join(wt_path, workdir) if workdir else wt_path

    for cmd_str in commands:
        print(f"[worktree-gate] Esecuzione: {cmd_str}")
        # Esegue via shell=True per supportare comandi complessi (flag, pipe nei comandi
        # gate stessi sono leciti; e' la lettura dell'exit code *di questo wrapper*
        # che deve avvenire senza pipe — R.WG4).
        result = subprocess.run(
            cmd_str,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        # Mostra output sempre (non solo su errore) per trasparenza
        if result.stdout:
            print(result.stdout, end="")
        if result.returncode != 0:
            print(
                f"[worktree-gate FAIL] '{cmd_str}' ha restituito exit {result.returncode}.",
                file=sys.stderr,
            )
            return 1
        print(f"[worktree-gate PASS] '{cmd_str}'")

    return 0


def main() -> int:
    args = parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print(f"[worktree-gate ERROR] repo non trovato: {repo}", file=sys.stderr)
        return 1

    if not args.commands:
        print("[worktree-gate] Nessun comando gate dichiarato. PASS (lista vuota lecita).")
        return 0

    # Crea directory temporanea per il worktree (R.WG5)
    wt_parent = tempfile.mkdtemp(prefix="wt-gate-")
    wt_path = os.path.join(wt_parent, "wt")

    # Cleanup garantito (R.WG3)
    def cleanup() -> None:
        remove_worktree(repo, wt_path)
        if os.path.isdir(wt_parent):
            shutil.rmtree(wt_parent, ignore_errors=True)

    atexit.register(cleanup)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: sys.exit(1))

    create_worktree(repo, args.sha, wt_path)
    setup_symlinks(wt_path, args.node_modules_symlink)

    rc = run_gates(wt_path, args.commands, args.workdir)

    # cleanup viene eseguito da atexit
    return rc


if __name__ == "__main__":
    sys.exit(main())
