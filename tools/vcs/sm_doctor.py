#!/usr/bin/env python3
"""
sm_doctor.py -- diagnosi + auto-heal NON distruttivo dei submodule dichiarati
in factory.config.yaml (code_paths[] con vcs.mode: submodule).

Porta cross-platform generalizzata (US-311 EP-069): nessuna costante verticale
(nessun prefisso di directory, nessun nome di repo cablato). I target sono
letti dalla config, non da un filtro hardcoded.

SENZA ENTRY SUBMODULE IN CONFIG: esce 0 con messaggio esplicito.

CASI AUTO-RIPARATI (non distruttivi):
  - submodule non inizializzato          -> git submodule update --init
  - puntatore out of sync + tree pulito  -> allinea al commit tracciato
  - hook §ai_policy mancanti/obsoleti   -> reinstalla (solo se suppress_ai_traces: true)

CASI SOLO SEGNALATI (richiedono decisione umana -- R.14 gate VCS):
  - modifiche non committate nel submodule  -> stash/commit poi ri-esegui
  - detached HEAD out of sync con modifiche -> risolvi a mano

USO:
  python3 tools/vcs/sm_doctor.py [--target <nome>] [--align] [--dry-run] [--quiet]

  --target    Solo il submodule indicato (nome o path).
  --align     Allinea al puntatore anche i submodule su branch (clean).
  --dry-run   Diagnosi senza modifiche.
  --quiet     Output minimale (per uso da git hook post-merge/post-checkout).

EXIT: 0 = tutto verde o auto-riparato; 1 = resta un'azione umana da fare.

Riferimenti: tools/vcs/install_submodule_hooks.py, tools/vcs/sm_status.py
             tools/vcs/README-submodule.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Rende importabile smlib da qualsiasi CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))

from smlib import (
    default_targets,
    color,
    factory_root,
    is_archived,
    list_submodule_paths,
    resolve_submodule,
    suppress_ai_traces,
)
from smlib.factory_config import list_submodule_code_paths
from smlib.gitutil import (
    GitError,
    count,
    current_branch,
    git_lines,
    git_out,
    git_run,
    rev_parse,
)

# Riuso del contenuto hook e degli helper (single source of truth).
from install_submodule_hooks import get_hooks, resolve_hooks_dir, sha256 as _sha256


# ---------------------------------------------------------------------------
# Diagnosi
# ---------------------------------------------------------------------------
class Diagnosis:
    """Stato diagnostico di un singolo submodule."""

    def __init__(self, sm_key: str) -> None:
        self.sm_key = sm_key
        self.name = Path(sm_key).name
        self.initialized = False
        self.archived = False       # True = repo archiviato read-only sull'host remoto
        self.branch = ""            # '' = detached HEAD
        self.head = ""              # SHA HEAD reale del submodule
        self.pointer = ""           # SHA tracciato dalla factory
        self.staged = 0
        self.modified = 0
        self.untracked = 0
        self.hooks_missing: list = []   # nomi hook da (re)installare

    @property
    def dirty(self) -> bool:
        return (self.staged + self.modified + self.untracked) > 0

    @property
    def in_sync(self) -> bool:
        return bool(self.pointer) and self.pointer == self.head

    @property
    def detached(self) -> bool:
        return self.initialized and not self.branch


def _pointer_sha(root: Path, sm_key: str) -> str:
    """SHA del puntatore TRACCIATO (gitlink in HEAD) -- NON il commit checked-out."""
    return git_out(["rev-parse", f"HEAD:{sm_key}"], cwd=root, default="")


def batch_pointers(root: Path) -> dict:
    """Un solo `git ls-files -s` -> {path: pointer_sha} per i gitlink (mode 160000)."""
    result: dict = {}
    for line in git_lines(["ls-files", "-s"], cwd=root):
        if not line.startswith("160000"):
            continue
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) >= 2 and path:
            result[path.strip()] = parts[1]
    return result


def _read_head_sha(gitdir: Path) -> str:
    """SHA di HEAD del submodule letto dal filesystem (niente subprocess)."""
    head_file = gitdir / "HEAD"
    try:
        head = head_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not head.startswith("ref:"):
        return head  # detached: sha diretto
    ref = head.split(":", 1)[1].strip()
    loose = gitdir / ref
    try:
        return loose.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    packed = gitdir / "packed-refs"
    try:
        for line in packed.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "^")):
                continue
            sha, _, name = line.partition(" ")
            if name == ref:
                return sha
    except OSError:
        pass
    return ""


def batch_dirty_submodules(root: Path) -> set:
    """Un solo `git status --porcelain` sul padre -> set dei submodule 'sporchi'.

    Con `ignore = dirty` in `.gitmodules` (lint 4ax) il `git status` ordinario non scende
    nei submodule; qui il contenuto dei worktree serve davvero, quindi
    `--ignore-submodules=none` ripristina la scansione completa.
    """
    dirty: set = set()
    for line in git_lines(["status", "--porcelain", "--ignore-submodules=none"], cwd=root):
        path = line[3:].strip() if len(line) > 3 else ""
        if path:
            dirty.add(path.rstrip("/"))
    return dirty


def _expected_hooks(sm_path: Path, hooks: dict) -> list:
    """Nomi degli hook §ai_policy assenti o con checksum diverso."""
    hooks_dir = resolve_hooks_dir(sm_path)
    missing = []
    for name, content in hooks.items():
        hook_path = hooks_dir / name
        expected = _sha256(content.encode("utf-8"))
        if not hook_path.exists() or _sha256(hook_path.read_bytes()) != expected:
            missing.append(name)
    return missing


def diagnose(root: Path, sm_key: str,
             pointers: dict = None, dirty_set: set = None,
             check_hooks: bool = False) -> Diagnosis:
    """Diagnosi di un submodule."""
    d = Diagnosis(sm_key)
    sm_path = root / sm_key
    d.archived = is_archived(root, sm_key)
    d.pointer = (pointers.get(sm_key, "") if pointers is not None
                 else _pointer_sha(root, sm_key))

    if not (sm_path / ".git").exists():
        d.initialized = False
        return d

    d.initialized = True
    if check_hooks:
        hooks = get_hooks()
        d.hooks_missing = _expected_hooks(sm_path, hooks)

    gitdir = resolve_hooks_dir(sm_path).parent
    d.head = (_read_head_sha(gitdir) if pointers is not None
              else rev_parse("HEAD", cwd=sm_path))

    if d.head and d.pointer and d.head == d.pointer:
        if dirty_set is not None and sm_key in dirty_set:
            d.modified = 1
        return d

    d.branch = current_branch(sm_path)
    d.head = rev_parse("HEAD", cwd=sm_path)
    if not d.pointer:
        d.pointer = _pointer_sha(root, sm_key)
    d.staged = count(["diff", "--cached", "--name-only"], cwd=sm_path)
    d.modified = count(["diff", "--name-only"], cwd=sm_path)
    d.untracked = count(["ls-files", "--others", "--exclude-standard"], cwd=sm_path)
    return d


# ---------------------------------------------------------------------------
# Rimedi non distruttivi
# ---------------------------------------------------------------------------
def _align_to_pointer(root: Path, sm_key: str, dry_run: bool) -> bool:
    if dry_run:
        return True
    try:
        git_run(
            ["-c", "protocol.file.allow=always",
             "submodule", "update", "--init", sm_key],
            cwd=root,
        )
        return True
    except GitError as exc:
        print("  " + color.red(f"Allineamento fallito: {exc}"))
        return False


def _reinstall_hooks(root: Path, sm_key: str, names: list, dry_run: bool) -> bool:
    if dry_run:
        return True
    sm_path = root / sm_key
    hooks_dir = resolve_hooks_dir(sm_path)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hooks = get_hooks()
    for name in names:
        hook_path = hooks_dir / name
        hook_path.write_text(hooks[name], encoding="utf-8")
        hook_path.chmod(0o755)
    return True


# ---------------------------------------------------------------------------
# Trattamento per submodule
# ---------------------------------------------------------------------------
class Result:
    def __init__(self) -> None:
        self.healed = []
        self.needs_human = []


def treat(root: Path, d: Diagnosis, align: bool, dry_run: bool,
          quiet: bool, result: Result, check_hooks: bool = False) -> None:
    tag = "[dry-run] " if dry_run else ""

    def say(msg: str) -> None:
        if not quiet:
            print(msg)

    say(color.cyan(f"=== {d.sm_key} ==="))

    # 0) Archiviato -> solo informativo, nessuna azione automatica
    if d.archived:
        say("  " + color.yellow("[archiviato (read-only)]")
            + " — nessuna azione automatica (solo lettura).")
        return

    # 1) Non inizializzato -> init
    if not d.initialized:
        say("  " + color.yellow("Non inizializzato")
            + f" -> {tag}init" + (" + reinstall hook" if check_hooks else ""))
        if _align_to_pointer(root, d.sm_key, dry_run):
            if check_hooks:
                _reinstall_hooks(root, d.sm_key, list(get_hooks().keys()), dry_run)
                result.healed.append(f"{d.name}: init + hook")
            else:
                result.healed.append(f"{d.name}: init")
        else:
            result.needs_human.append(
                (d.name, "init fallito",
                 f'git submodule update --init "{d.sm_key}"'))
        return

    # 2) Modifiche non committate -> MAI toccare (R.14). Segnala.
    if d.dirty:
        detail = f"staged={d.staged} modified={d.modified} untracked={d.untracked}"
        if d.in_sync:
            say("  " + color.yellow(f"Modifiche locali ({detail})")
                + " -- puntatore in sync, nessun rischio (lavoro in corso).")
            if check_hooks:
                _heal_hooks_if_needed(root, d, dry_run, quiet, result, say, tag)
        else:
            say("  " + color.red(f"Out of sync CON modifiche locali ({detail})"))
            say("  " + "Il doctor non tocca un tree con modifiche non committate.")
            cmd = (f'git -C "{d.sm_key}" stash\n'
                   f'      python3 tools/vcs/sm_doctor.py --target {d.name} --align')
            result.needs_human.append(
                (d.name, "out of sync con modifiche non committate", cmd))
        return

    # 3) Tree pulito, puntatore in sync -> OK
    if d.in_sync:
        say("  " + color.green("In sync") + f" -- {d.pointer[:9]}")
        if check_hooks:
            _heal_hooks_if_needed(root, d, dry_run, quiet, result, say, tag)
        return

    # 4) Tree pulito ma out of sync
    where = "detached" if d.detached else f"branch '{d.branch}'"
    say("  " + color.yellow("Out of sync")
        + f" -- factory: {d.pointer[:9]} | HEAD: {d.head[:9]} ({where})")

    should_align = d.detached or align
    if should_align:
        say("  " + f"{tag}Allineo al commit tracciato dalla factory (non distruttivo)...")
        if _align_to_pointer(root, d.sm_key, dry_run):
            new_head = (d.pointer if dry_run
                        else rev_parse("HEAD", cwd=root / d.sm_key))
            say("  " + color.green(f"Allineato -> {new_head[:9]}"))
            if check_hooks:
                _reinstall_hooks(root, d.sm_key, list(get_hooks().keys()), dry_run)
            result.healed.append(f"{d.name}: allineato a puntatore")
        else:
            result.needs_human.append(
                (d.name, "allineamento fallito",
                 f'git submodule update --init "{d.sm_key}"'))
    else:
        say("  " + "Sei su un branch: potrebbe essere lavoro intenzionale.")
        result.needs_human.append(
            (d.name, f"out of sync su branch '{d.branch}' (clean)",
             f"python3 tools/vcs/sm_doctor.py --target {d.name} --align\n"
             f"      # oppure aggiorna il puntatore al tuo HEAD:\n"
             f"      python3 tools/vcs/sm_commit.py --pointer-only --target {d.name}"))


def _heal_hooks_if_needed(root: Path, d: Diagnosis, dry_run: bool, quiet: bool,
                           result: Result, say, tag: str) -> None:
    if not d.hooks_missing:
        return
    say("  " + color.yellow(
        f"Hook §ai_policy da (re)installare: {', '.join(d.hooks_missing)}")
        + f" -> {tag}reinstall")
    _reinstall_hooks(root, d.sm_key, d.hooks_missing, dry_run)
    result.healed.append(f"{d.name}: hook {', '.join(d.hooks_missing)}")


# ---------------------------------------------------------------------------
# Selezione target
# ---------------------------------------------------------------------------
def _config_sm_paths(root: Path) -> list:
    """Target senza --target: vcs_tooling.submodule_scope (smlib.default_targets)."""
    return default_targets(root)


def _targets(root: Path, target: str):
    # Target esplicito -> cerca in .gitmodules
    if target:
        resolved = resolve_submodule(root, target)
        if resolved:
            return [resolved]
        return []

    # Nessun target -> usa quelli dalla config
    return _config_sm_paths(root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnosi + auto-heal non distruttivo dei submodule.")
    parser.add_argument("--target", default="",
                        help="Solo il submodule indicato.")
    parser.add_argument("--align", action="store_true",
                        help="Allinea al puntatore anche i submodule su branch (clean).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Diagnosi senza modifiche.")
    parser.add_argument("--quiet", action="store_true",
                        help="Output minimale (uso da git hook).")
    args = parser.parse_args(argv)

    root = factory_root()
    submodules = _targets(root, args.target)

    if not submodules:
        if args.target:
            suffix = f" per target '{args.target}'"
            print(color.red(f"Nessun submodule trovato{suffix} in .gitmodules."))
            print("Submodule disponibili:")
            for value in list_submodule_paths(root):
                print(f"  {value}")
        else:
            print(color.cyan(
                "Nessun submodule dichiarato in factory.config.yaml "
                "(code_paths[] con vcs.mode: submodule)."))
            print("Per gestire un submodule con questo tool, aggiungi una entry:")
            print("  code_paths:")
            print("    - name: <nome>")
            print("      path: <path-relativo>")
            print("      vcs:")
            print("        mode: submodule")
            print("        base_branch: <branch>")
        return 0

    # Gli hook §ai_policy si reinstallano solo se la policy e' attiva
    check_hooks = suppress_ai_traces(root)

    pointers = batch_pointers(root)
    dirty_set = None if args.quiet else batch_dirty_submodules(root)

    result = Result()
    for sm_key in submodules:
        d = diagnose(root, sm_key, pointers=pointers, dirty_set=dirty_set,
                     check_hooks=check_hooks)
        treat(root, d, args.align, args.dry_run, args.quiet, result,
              check_hooks=check_hooks)

    if not args.quiet:
        print()
        if result.healed:
            prefix = "[dry-run] Riparerebbe" if args.dry_run else color.green("Riparato")
            print(f"{prefix}: {len(result.healed)} azione/i")
            for item in result.healed:
                print("  * " + item)
        if result.needs_human:
            print(color.yellow(f"Richiede intervento umano: {len(result.needs_human)}"))
            for name, reason, cmd in result.needs_human:
                print("  " + color.yellow(f"! {name}") + f" -- {reason}")
                print("      " + cmd)
        if not result.healed and not result.needs_human:
            print(color.green("Tutti i submodule sono in ordine."))

    return 1 if result.needs_human else 0


if __name__ == "__main__":
    sys.exit(main())
