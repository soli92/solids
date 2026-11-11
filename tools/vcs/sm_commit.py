#!/usr/bin/env python3
"""Commit con strip attribution AI e ID factory -- §ai_policy (ADR-074).

Uso base (singolo repo, default -- comportamento invariato rispetto a pre-US-311):
    sm_commit.py "messaggio commit" [path]
    sm_commit.py --message "messaggio" --path /repo [--dry-run] [--yes]

Retro-compatibilita' posizionale con sm-commit.sh:
    sm_commit.py "messaggio" [path]

Modalita' coordinata (US-311 EP-069) -- submodule + puntatore factory:
    sm_commit.py --coordinated "<msg-submodule>" [--target <nome>]
                 [--no-pointer] [--push] ["<msg-factory>"]

  --coordinated  Attiva la modalita' coordinata: commit nel submodule
                 (FASE 1) poi aggiorna il puntatore factory (FASE 2).
                 La modalita' base (singolo repo) rimane il default.
  --target       Nome del submodule target (richiesto se piu' di uno in config).
  --no-pointer   Salta FASE 2 (bump puntatore). Usare su branch effimeri
                 non ancora mergiati nel factory repo.
  --push         Push del submodule dopo il commit (prima di aggiornare
                 il puntatore factory -- verifica che il commit sia sul remote
                 prima di esporlo come gitlink).

In modalita' base (senza --coordinated) il comportamento e' identico a prima
di US-311: commit nel repo indicato da --path (o ".") con filtri §ai_policy,
gate sul messaggio alterato, conferma interattiva o --yes per non-interattivo.

Importa strip_ai_attribution e strip_factory_ids da tools/vcs/ai_policy.py
(fonte unica, nessuna duplicazione). Avvisa l'utente di cio' che e' stato
rimosso invece di scartarlo in silenzio.

stdlib-only. Nessun nome di cliente.
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Import ai_policy (fonte unica)
# ---------------------------------------------------------------------------

def _import_ai_policy():
    """Importa ai_policy.py dalla stessa directory di questo script."""
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("ai_policy", here / "ai_policy.py")
    if spec is None or spec.loader is None:
        print("Errore: impossibile trovare tools/vcs/ai_policy.py.", file=sys.stderr)
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Modalita' base (singolo repo) -- API pubblica per i test
# ---------------------------------------------------------------------------

def apply_ai_filters(message: str, ai_policy):
    """Applica strip attribution AI e strip factory IDs. Ritorna (msg, attr_rm, ids_rm)."""
    msg_after_attr, attr_removed = ai_policy.strip_ai_attribution(message)
    msg_final, ids_removed = ai_policy.strip_factory_ids(msg_after_attr)
    return msg_final, attr_removed, ids_removed


def _gate_altered_message(msg_final: str, attr_removed: list, ids_removed: list,
                           yes: bool) -> bool:
    """Gate di conferma quando il messaggio viene alterato. True = procedi."""
    if not (attr_removed or ids_removed):
        return True
    print("--- messaggio che verrebbe committato ---", file=sys.stderr)
    print(msg_final, file=sys.stderr)
    print("-----------------------------------------", file=sys.stderr)
    if yes:
        return True
    if sys.stdin.isatty():
        try:
            risposta = input("Committare questo messaggio? [s/N] ").strip().lower()
        except EOFError:
            risposta = ""
        if risposta not in ("s", "si", "ì", "y", "yes"):
            print("[sm_commit] Annullato. Nessun commit eseguito.", file=sys.stderr)
            return False
        return True
    else:
        print(
            "[sm_commit] Il messaggio e' stato alterato dai filtri e non c'e' un "
            "terminale per confermare. Nessun commit eseguito.\n"
            "            Rilanciare con --yes per accettare il messaggio mostrato, "
            "oppure riscrivere il messaggio senza la traccia.",
            file=sys.stderr,
        )
        return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sm_commit.py",
        description=(
            "Commit senza attribution AI e senza ID factory interni. "
            "Modalita' base (default) o coordinata (--coordinated)."
        ),
    )
    # Argomenti posizionali (retro-compatibilita')
    p.add_argument(
        "message",
        nargs="?",
        help="Messaggio di commit (posizionale, retro-compatibile con lo .sh).",
    )
    p.add_argument(
        "--message", "-m",
        dest="message_flag",
        default=None,
        help="Messaggio di commit (flag alternativo).",
    )
    p.add_argument(
        "path_pos",
        nargs="?",
        default=None,
        help="Path del repo (posizionale, retro-compatibile con lo .sh).",
    )
    p.add_argument(
        "--path", "-C",
        dest="path_flag",
        default=None,
        help="Path del repo (flag alternativo, modalita' base).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Mostra messaggio originale, messaggio filtrato e righe rimosse senza committare.",
    )
    p.add_argument(
        "--yes", "-y",
        action="store_true",
        default=False,
        help=(
            "Conferma non interattiva quando il messaggio viene alterato dai filtri."
        ),
    )
    # Modalita' coordinata (US-311)
    p.add_argument(
        "--coordinated",
        action="store_true",
        default=False,
        help="Modalita' coordinata: commit submodule (FASE 1) + puntatore factory (FASE 2).",
    )
    p.add_argument(
        "--target",
        default="",
        help="Nome submodule target (modalita' coordinata; auto se uno solo in config).",
    )
    p.add_argument(
        "--no-pointer",
        action="store_true",
        default=False,
        help="Salta FASE 2 (bump puntatore factory). Usare su branch effimeri.",
    )
    p.add_argument(
        "--pointer-only",
        action="store_true",
        default=False,
        help="Solo FASE 2 (aggiorna puntatore factory senza commit nel submodule).",
    )
    p.add_argument(
        "--push",
        action="store_true",
        default=False,
        help="Push submodule + factory (modalita' coordinata).",
    )
    return p


# ---------------------------------------------------------------------------
# Modalita' coordinata (US-311)
# ---------------------------------------------------------------------------

def _coordinated_main(args, ai_policy) -> int:
    """Gestisce la modalita' --coordinated."""
    # Import smlib (stesso package, stesso PATH)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from smlib import (
            color,
            factory_root,
            is_archived,
            list_submodule_paths,
            resolve_submodule,
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
    except ImportError as exc:
        print(f"Errore import smlib: {exc}", file=sys.stderr)
        return 1

    root = factory_root()

    # Messaggi
    # In modalita' coordinata: args.message = msg-submodule; args.path_pos = msg-factory
    sm_msg = args.message_flag or args.message or ""
    factory_msg = args.path_pos or ""

    # Risolvi target
    sm_key = _resolve_coordinated_target(root, args.target, resolve_submodule,
                                         list_submodule_code_paths,
                                         list_submodule_paths, color)
    if not sm_key:
        return 1

    if is_archived(root, sm_key):
        target_name = Path(sm_key).name
        print(color.red(
            f"[{target_name}] Submodule archiviato (read-only): commit non consentito."))
        print("  Il repo e' archiviato sull'host remoto: il push verrebbe rifiutato.")
        print("  Nessun commit eseguito.")
        return 1

    target_name = Path(sm_key).name
    sm_path = root / sm_key

    # Identita' git
    name_git = git_out(["config", "user.name"])
    email_git = git_out(["config", "user.email"])
    if not name_git or not email_git:
        print(color.red(
            "git config user.name/user.email non trovato. "
            "Configura prima la tua identita' git globale."), file=sys.stderr)
        return 1

    if not (sm_path / ".git").exists():
        print(color.red("Submodule non inizializzato."))
        print(f"Esegui: git submodule update --init {sm_key}")
        return 1

    # FASE 1 -- commit nel submodule
    if not args.pointer_only:
        rc = _commit_submodule(
            root, sm_path, target_name, sm_msg, (name_git, email_git),
            args.push, ai_policy, color, count, current_branch,
            git_run, rev_parse, GitError,
        )
        if rc != 0:
            return rc

    # FASE 2 -- aggiorna puntatore factory
    if args.no_pointer:
        sm_actual = rev_parse("HEAD", cwd=sm_path, short=True)
        sm_branch_now = current_branch(sm_path) or "detached"
        print()
        print(color.yellow("[--no-pointer] Puntatore factory NON aggiornato."))
        print(f"   Submodule HEAD: {sm_actual} ({sm_branch_now})")
        print("   Quando il branch sara' mergiato, esegui:")
        print(color.cyan(
            f"   python3 tools/vcs/sm_commit.py --coordinated --pointer-only "
            f"--target {target_name}"))
    else:
        if _remote_gate(root, sm_path, target_name, color, current_branch,
                        git_lines, git_run, rev_parse) != 0:
            return 1
        print()

        needs_update = git_out(["status", "--porcelain", sm_key], cwd=root, default="")
        if not needs_update:
            print(color.cyan(
                "Puntatore factory gia' aggiornato -- nessun commit factory necessario."))
        else:
            sm_actual = rev_parse("HEAD", cwd=sm_path, short=True)
            sm_branch_now = current_branch(sm_path) or "detached"
            if not factory_msg:
                factory_msg = (f"chore(submodule): bump {target_name} "
                               f"-> {sm_actual} ({sm_branch_now})")

            print(color.yellow(f"Aggiornamento puntatore factory -> {sm_actual}"))
            git_run(["add", sm_key], cwd=root)
            git_run(["commit", "-m", factory_msg], cwd=root)
            print(color.green("Factory committata con puntatore aggiornato."))

            if args.push:
                factory_branch = current_branch(root)
                print(color.yellow(f"Push factory -> origin/{factory_branch}..."))
                git_run(["push", "origin", factory_branch], cwd=root)
                print(color.green("Push factory completato."))

    print()
    print(color.green("Done.") + " Verifica con "
          + color.cyan(f"python3 tools/vcs/sm_status.py --target {target_name}"))
    return 0


def _resolve_coordinated_target(root, target, resolve_submodule,
                                 list_submodule_code_paths, list_submodule_paths, color):
    from smlib.factory_config import default_target
    target = target or default_target(root) or ""   # vcs_tooling.default_target
    if target:
        sm_key = resolve_submodule(root, target)
        if not sm_key:
            print(color.red(f"Target non trovato in .gitmodules: '{target}'"))
            print("Submodule disponibili:")
            for value in list_submodule_paths(root):
                print(f"  {value}")
        return sm_key

    # Auto-select se un solo submodule in config
    config_entries = list_submodule_code_paths(root)
    all_paths = list_submodule_paths(root)
    if not config_entries:
        print(color.yellow(
            "Nessun submodule dichiarato in factory.config.yaml "
            "(code_paths[] con vcs.mode: submodule)."))
        return None
    config_names = {e.get("name", "").strip() for e in config_entries}
    config_paths = {e.get("path", "").strip() for e in config_entries}
    sm_paths = [p for p in all_paths
                if p in config_paths or Path(p).name in config_names]
    if len(sm_paths) == 1:
        return sm_paths[0]
    elif len(sm_paths) > 1:
        names = ", ".join(Path(p).name for p in sm_paths)
        print(color.red(
            f"Piu' submodule dichiarati ({names}): specifica --target <nome>."))
    else:
        print(color.yellow(
            "Nessun submodule abbinato in .gitmodules. "
            "Verifica che il path in code_paths[] corrisponda al path in .gitmodules."))
    return None


def _commit_submodule(root, sm_path, target_name, sm_msg, author, do_push,
                      ai_policy, color, count, current_branch,
                      git_run, rev_parse, GitError):
    """Commit nel submodule con filtri §ai_policy."""
    from smlib.gitutil import git_out

    branch = current_branch(sm_path)
    if not branch:
        print(color.red(f"[DETACHED HEAD] Il submodule '{target_name}' e' in detached HEAD."))
        print("   Risolvi il detached HEAD prima di committare:")
        print(f"   git -C {sm_path} checkout <branch>")
        return 1

    staged = count(["diff", "--cached", "--name-only"], cwd=sm_path)
    modified = count(["diff", "--name-only"], cwd=sm_path)
    untracked = count(["ls-files", "--others", "--exclude-standard"], cwd=sm_path)

    if staged == 0 and modified == 0 and untracked == 0:
        print(color.cyan(f"[{target_name}] Submodule clean -- nessun commit necessario."))
        return 0

    if not sm_msg:
        print(color.yellow(f"Stato {target_name}:"))
        git_run(["status", "--short"], cwd=sm_path)
        print()
        sm_msg = input("Messaggio commit submodule: ").strip()
        if not sm_msg:
            print(color.red("Messaggio obbligatorio."), file=sys.stderr)
            return 1

    if staged == 0:
        print(color.yellow(
            "Nessun file staged. Esegui 'git add' prima, "
            "oppure usa --pointer-only."))
        git_run(["status", "--short"], cwd=sm_path)
        return 1

    # Filtri §ai_policy
    sm_msg, attr_removed = ai_policy.strip_ai_attribution(sm_msg)
    if attr_removed:
        print(color.yellow("[§ai_policy] Righe rimosse dal messaggio (attribution AI):"),
              file=sys.stderr)
        for line in attr_removed:
            print(f"  - {line}", file=sys.stderr)

    sm_msg, factory_ids = ai_policy.strip_factory_ids(sm_msg)
    if factory_ids:
        print(color.yellow("[§ai_policy] ID kanban factory rimossi dal messaggio:"),
              file=sys.stderr)
        for fid in factory_ids:
            print(f"  - {fid}", file=sys.stderr)

    if not sm_msg.strip():
        print(color.red(
            "Messaggio vuoto dopo il filtro §ai_policy -- nessun commit eseguito."),
            file=sys.stderr)
        return 1

    name, email = author
    print(color.yellow(f"Commit [{target_name}]..."))
    print(f"  Autore: {name} <{email}>")
    git_run(
        ["-c", f"user.name={name}", "-c", f"user.email={email}",
         "commit", "-m", sm_msg],
        cwd=sm_path,
    )
    print(color.green(f"Committato su branch '{branch}'."))

    if do_push:
        print(color.yellow(f"Push {target_name} -> origin/{branch}..."))
        git_run(["push", "origin", branch], cwd=sm_path)
        print(color.green("Push completato."))
    return 0


def _remote_gate(root, sm_path, target_name, color, current_branch,
                 git_lines, git_run, rev_parse):
    """Verifica che HEAD del submodule sia su un branch remoto."""
    from smlib.gitutil import GitError

    sm_head = rev_parse("HEAD", cwd=sm_path)
    remote_branches = git_lines(["branch", "-r", "--contains", sm_head], cwd=sm_path)
    if remote_branches:
        return 0

    print()
    print(color.yellow(
        f"[!] GATE REMOTE: il commit {sm_head[:9]} del submodule '{target_name}'"))
    print(color.yellow(
        "   non e' presente su nessun branch remoto."))
    print("   Il puntatore factory puntera' a una ref non accessibile ad altri.")
    print("   Opzioni:")
    print("     " + color.cyan("push") + "   -- push submodule adesso")
    print("     " + color.cyan("skip") + "   -- aggiorna puntatore comunque (rischio)")
    print("     " + color.cyan("abort") + "  -- interrompi (default)")
    print()
    answer = (input("   Risposta [push/skip/abort]: ").strip() or "abort")
    if answer == "push":
        sm_branch = current_branch(sm_path)
        if not sm_branch:
            print(color.red("HEAD detached -- push automatico impossibile."), file=sys.stderr)
            return 1
        git_run(["push", "origin", sm_branch], cwd=sm_path)
        print(color.green(f"Push '{target_name}' -> origin/{sm_branch} completato."))
        return 0
    if answer == "skip":
        print(color.yellow("Gate saltato -- puntatore procede (ref potenzialmente dangling)."))
        return 0
    print(color.red("Abort."), file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# git_out helper (necessario in coordinata)
# ---------------------------------------------------------------------------
def git_out(args, cwd=None, default=""):
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd is not None else None,
        text=True, capture_output=True,
    )
    if result.returncode != 0:
        return default
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Modalita' coordinata. --dry-run vince su ogni modalita': non committa mai e passa
    # dal ramo base, che mostra solo il messaggio filtrato. Senza questa guardia
    # --coordinated --dry-run (o --pointer-only, --target) committava davvero.
    if not args.dry_run and (args.coordinated or args.pointer_only or (args.target and not args.path_flag)):
        if args.coordinated or args.pointer_only:
            ai_policy = _import_ai_policy()
            return _coordinated_main(args, ai_policy)

    # Modalita' base (comportamento invariato rispetto a pre-US-311)
    message = args.message_flag or args.message
    if not message:
        parser.print_usage(sys.stderr)
        print("Errore: messaggio commit obbligatorio.", file=sys.stderr)
        return 1

    repo_path = args.path_flag or args.path_pos or "."

    ai_policy = _import_ai_policy()
    msg_final, attr_removed, ids_removed = apply_ai_filters(message, ai_policy)

    if attr_removed:
        print(
            "[sm_commit] Attribution AI rimossa:\n"
            + "\n".join(f"  - {r}" for r in attr_removed),
            file=sys.stderr,
        )
    if ids_removed:
        print(
            "[sm_commit] ID factory rimossi: " + ", ".join(ids_removed),
            file=sys.stderr,
        )

    if args.dry_run:
        print("--- messaggio originale ---")
        print(message)
        print("--- messaggio filtrato ---")
        print(msg_final)
        if not attr_removed and not ids_removed:
            print("[sm_commit] Nessuna modifica: il messaggio passa invariato.")
        return 0

    if not msg_final.strip():
        print(
            "Errore: il messaggio e' vuoto dopo la rimozione delle tracce AI.",
            file=sys.stderr,
        )
        return 1

    if not _gate_altered_message(msg_final, attr_removed, ids_removed, args.yes):
        return 1

    result = subprocess.run(
        ["git", "-C", repo_path, "commit", "-m", msg_final],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
