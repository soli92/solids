"""Wrapper sottili su `git` via subprocess -- cross-platform.

Due modalita':
  - git_out / git_lines : catturano lo stdout (per rev-parse, status, ...).
  - git_run             : eredita lo stdio del processo (l'output di git e'
                          mostrato all'utente, es. commit / push / pull).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Union

PathLike = Union[str, Path, None]


class GitError(RuntimeError):
    """Errore di esecuzione di un comando git (returncode != 0)."""


def _cwd(cwd: PathLike) -> Optional[str]:
    return str(cwd) if cwd is not None else None


def git_out(args: Sequence[str], cwd: PathLike = None, default: str = "") -> str:
    """Esegue git e ritorna stdout strip()'d. Su errore ritorna `default`."""
    proc = subprocess.run(
        ["git", *args],
        cwd=_cwd(cwd),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return default
    return proc.stdout.strip()


def git_lines(args: Sequence[str], cwd: PathLike = None) -> List[str]:
    """Come git_out ma ritorna la lista delle righe non vuote."""
    out = git_out(args, cwd=cwd, default="")
    if not out:
        return []
    return [ln for ln in out.splitlines() if ln.strip() != ""]


def git_run(args: Sequence[str], cwd: PathLike = None, check: bool = True) -> int:
    """Esegue git ereditando lo stdio (output visibile). Ritorna il returncode.

    Se check=True e il comando fallisce, solleva GitError.
    """
    proc = subprocess.run(["git", *args], cwd=_cwd(cwd))
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} -> exit {proc.returncode}")
    return proc.returncode


def current_branch(cwd: PathLike = None) -> str:
    """Branch corrente, o '' se detached HEAD."""
    return git_out(["branch", "--show-current"], cwd=cwd, default="")


def rev_parse(ref: str = "HEAD", cwd: PathLike = None, short: bool = False) -> str:
    args = ["rev-parse"]
    if short:
        args.append("--short")
    args.append(ref)
    return git_out(args, cwd=cwd, default="")


def count(args: Sequence[str], cwd: PathLike = None) -> int:
    """Numero di righe non vuote nell'output di un comando git."""
    return len(git_lines(args, cwd=cwd))
