#!/usr/bin/env python3
"""Travaso di un albero di codice da un repo sorgente (a SHA immutabile) a un repo
target, senza trasferire history. Implementa la Fase G2→G3 di repo-handover-protocol.

Uso:
    python3 tools/vcs/repo_handover.py \\
        --source <path_sorgente> --sha <sha> \\
        --target <path_target> \\
        [--path <subdir_in_sorgente>] \\
        [--exclude <pattern>] \\
        [--dry-run]

Opzioni:
    --source PATH   Path assoluto al repo sorgente (read-only).
    --sha SHA       SHA del commit nel sorgente. Deve essere un commit esistente.
    --target PATH   Path assoluto al repo target.
    --path SUBDIR   Sottodirectory del sorgente da includere (default: tutto).
                    Ripetibile per includere piu' path.
    --exclude PAT   Pattern di esclusione (stile gitignore, relativo alla root
                    dell'albero estratto). Ripetibile.
    --dry-run       Elenca i file senza scrivere nel target.

Exit codes:
    0  Successo (o dry-run completato).
    1  Errore: parametri mancanti, SHA non trovato, target non pulito, ecc.

stdlib-only. Nessuna costante verticale. Nessuna dipendenza esterna.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers git
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def verify_sha(source_repo: str, sha: str) -> bool:
    """Verifica che SHA esista nel repo sorgente come commit."""
    r = _git(["cat-file", "-t", sha], cwd=source_repo, check=False)
    return r.returncode == 0 and r.stdout.strip() == "commit"


def is_working_tree_clean(repo: str) -> bool:
    """True se il working tree del repo non ha modifiche non committate."""
    r = _git(["status", "--porcelain"], cwd=repo, check=False)
    return r.returncode == 0 and r.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Export + filtraggio
# ---------------------------------------------------------------------------

def handover(
    source_repo: str,
    sha: str,
    target_repo: str,
    include_paths: list[str],
    exclude_patterns: list[str],
    dry_run: bool,
) -> list[str]:
    """Esegue il travaso (o dry-run). Restituisce la lista dei file trasferiti."""

    # --- Preflight G1 ---
    if not verify_sha(source_repo, sha):
        print(f"STOP G1: SHA '{sha}' non trovato nel repo sorgente '{source_repo}'.",
              file=sys.stderr)
        sys.exit(1)

    if not dry_run and not is_working_tree_clean(target_repo):
        print("STOP G1: il repo target ha modifiche non committate. "
              "Committale o stashale prima di procedere.", file=sys.stderr)
        sys.exit(1)

    # --- Costruisce il comando git archive ---
    archive_args = ["archive", "--format=tar", sha]
    if include_paths:
        archive_args += ["--"] + include_paths

    result = subprocess.run(
        ["git"] + archive_args,
        cwd=source_repo,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"STOP: git archive fallito (exit {result.returncode}):", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        sys.exit(1)

    archive_bytes = result.stdout

    # --- Estrai in tmp e applica exclude ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False, dir=tmp) as f:
            f.write(archive_bytes)
            tar_path = f.name

        tree = tmp_path / "tree"
        tree.mkdir()
        with tarfile.open(tar_path, "r") as tf:
            # filter="data" rifiuta path assoluti, `..` e link fuori albero (Python >= 3.12,
            # backport nelle patch recenti di 3.9-3.11).
            if hasattr(tarfile, "data_filter"):
                tf.extractall(tree, filter="data")
            else:
                tf.extractall(tree)

        # Raccogli e filtra
        def _excluded(rel_path: str) -> bool:
            parts = rel_path.split("/")
            for pat in exclude_patterns:
                if pat.endswith("/"):
                    # pattern di cartella: esclude ogni file sotto una cartella che lo matcha,
                    # a qualunque profondita' (`node_modules/` copre `a/node_modules/x.js`)
                    if any(fnmatch.fnmatch(seg, pat.rstrip("/")) for seg in parts[:-1]):
                        return True
                    continue
                if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(parts[-1], pat):
                    return True
            return False

        all_files: list[str] = []
        for p in tree.rglob("*"):
            if p.is_file():
                all_files.append(p.relative_to(tree).as_posix())

        selected = sorted(f for f in all_files if not _excluded(f))

        if dry_run:
            return selected

        # --- Copia nel target ---
        target_path = Path(target_repo)
        for rel in selected:
            src = tree / rel
            dst = target_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())

        return selected


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Travaso di un albero di codice da sorgente@SHA a target (senza history).",
    )
    p.add_argument("--source", required=True, metavar="PATH",
                   help="Path assoluto al repo sorgente (read-only).")
    p.add_argument("--sha", required=True, metavar="SHA",
                   help="SHA del commit nel sorgente.")
    p.add_argument("--target", required=True, metavar="PATH",
                   help="Path assoluto al repo target.")
    p.add_argument("--path", action="append", default=[], metavar="SUBDIR",
                   help="Sottodirectory del sorgente da includere. Ripetibile.")
    p.add_argument("--exclude", action="append", default=[], metavar="PAT",
                   help="Pattern di esclusione (stile fnmatch). Ripetibile.")
    p.add_argument("--dry-run", action="store_true",
                   help="Elenca i file senza scrivere nel target.")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    source = os.path.abspath(args.source)
    target = os.path.abspath(args.target)
    sha = args.sha
    include_paths = args.path
    exclude_patterns = args.exclude
    dry_run = args.dry_run

    if not Path(source).is_dir():
        print(f"STOP: repo sorgente non trovato: {source}", file=sys.stderr)
        sys.exit(1)
    if not Path(target).is_dir():
        print(f"STOP: repo target non trovato: {target}", file=sys.stderr)
        sys.exit(1)

    selected = handover(
        source_repo=source,
        sha=sha,
        target_repo=target,
        include_paths=include_paths,
        exclude_patterns=exclude_patterns,
        dry_run=dry_run,
    )

    if dry_run:
        print(f"[dry-run] {len(selected)} file da trasferire:")
        for f in selected:
            print(f"  {f}")
    else:
        print(f"[handover] {len(selected)} file trasferiti in {target}")
        for f in selected:
            print(f"  {f}")


if __name__ == "__main__":
    main()
