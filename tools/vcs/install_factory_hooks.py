#!/usr/bin/env python3
"""
install_factory_hooks.py -- installa gli hook del REPO PADRE (factory) che
allineano i submodule dopo ogni pull/checkout, chiamando sm_doctor.py in
modalita' non distruttiva (--align --quiet).

Complementare a install_submodule_hooks.py (che installa gli hook §ai_policy
DENTRO i submodule). Qui gli hook stanno in <factory>/.git/hooks e rendono
l'allineamento automatico e sicuro: dopo `git pull` / `git checkout <branch>`
i submodule seguono automaticamente il commit tracciato dalla factory, senza
mai toccare un working tree con modifiche non committate (niente --force).

HOOK INSTALLATI:
  - post-merge     -> dopo pull/merge sul repo padre
  - post-checkout  -> dopo checkout/switch di branch (non su checkout di file)
  - pre-commit     -> SOLO con `wiki_lint.log_append_guard.hook: true` in factory.config.yaml
                      (default false): se wiki/log.md e' in stage lancia
                      tools/wiki/log_append_guard.py e rifiuta il commit se una riga sparisce
                      senza archivio wiki/log-*.md. Opt-in, perche' e' l'unico hook che blocca.

MERGE DRIVER (git config locale, non versionata: va registrata in ogni clone):
  - factory-log-union -> wiki/log.md: voci aggiunte in coda da due branch si fondono senza
                         conflitto (tools/wiki/log_union_driver.py). Associato a .gitattributes.
  Senza driver registrato git ignora il nome del driver e usa il merge standard: nessun danno,
  solo i conflitti di prima. La cartella hook e' quella che git legge davvero
  (`git rev-parse --git-path hooks`), quindi l'installer funziona anche da un worktree.

USO:
  python3 tools/vcs/install_factory_hooks.py [--dry-run] [--force]
  python3 tools/vcs/install_factory_hooks.py --only post-merge [--dry-run] [--force]

--only <hook> installa SOLO quell'hook (niente altri hook, niente merge driver). Un hook diverso
gia' presente non si sovrascrive senza --force.

Esegui prima con --dry-run. Idempotente (checksum sha256). stdlib-only.

Riferimenti: tools/vcs/sm_doctor.py, tools/vcs/install_submodule_hooks.py
             tools/vcs/README-submodule.md
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

# Rende importabile smlib da qualsiasi CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))

from smlib import color, factory_root

# ---------------------------------------------------------------------------
# Contenuto hook -- bash (Git for Windows li invoca via shebang).
# Non distruttivi: exit 0 sempre (|| true) per non bloccare mai un'operazione git.
# Il path dello script fa riferimento a tools/vcs/sm_doctor.py.
# ---------------------------------------------------------------------------
_COMMON = r'''# --- factory submodule auto-align (sm_doctor, non distruttivo) ---
# Allinea i submodule al commit tracciato dalla factory. Salta i tree con
# modifiche non committate (mai --force). Errori non bloccano l'operazione git.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
PY="$(command -v python3 || command -v python || command -v py || true)"
[ -z "$PY" ] && exit 0
[ -f "$ROOT/tools/vcs/sm_doctor.py" ] || exit 0
"$PY" "$ROOT/tools/vcs/sm_doctor.py" --align --quiet || true
exit 0
'''

POST_MERGE_HOOK = (
    "#!/usr/bin/env bash\n"
    "# post-merge hook -- factory (auto-generato, install_factory_hooks.py)\n"
    "set -uo pipefail\n"
    + _COMMON
)

# post-checkout riceve: $1=prev-HEAD $2=new-HEAD $3=flag (1=branch checkout).
# Esegue il doctor solo sul checkout di branch, non sul checkout di singoli file.
POST_CHECKOUT_HOOK = (
    "#!/usr/bin/env bash\n"
    "# post-checkout hook -- factory (auto-generato, install_factory_hooks.py)\n"
    "set -uo pipefail\n"
    'if [ "${3:-0}" != "1" ]; then exit 0; fi\n'
    + _COMMON
)

# pre-commit: blocca (exit 1) solo se la guardia lo chiede. Senza python o senza lo script esce 0:
# un ambiente incompleto non deve impedire i commit.
PRE_COMMIT_HOOK = (
    "#!/usr/bin/env bash\n"
    "# pre-commit hook -- factory (auto-generato, install_factory_hooks.py)\n"
    "set -uo pipefail\n"
    "# --- wiki/log.md append-only (log_append_guard) ---\n"
    'ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0\n'
    'PY="$(command -v python3 || command -v python || command -v py || true)"\n'
    '[ -z "$PY" ] && exit 0\n'
    '[ -f "$ROOT/tools/wiki/log_append_guard.py" ] || exit 0\n'
    'git diff --cached --name-only | grep -qx "wiki/log.md" || exit 0\n'
    'exec "$PY" "$ROOT/tools/wiki/log_append_guard.py"\n'
)

HOOKS = {
    "post-merge": POST_MERGE_HOOK,
    "post-checkout": POST_CHECKOUT_HOOK,
}


# Merge driver: nome -> (descrizione, comando). Il comando gira con cwd = radice del working tree.
MERGE_DRIVERS = {
    "factory-log-union": (
        "wiki/log.md: union delle voci aggiunte in coda",
        "python3 tools/wiki/log_union_driver.py %O %A %B",
    ),
}


def _git_config(root: Path, *args: str):
    return subprocess.run(["git", "-C", str(root), "config", "--local", *args],
                          capture_output=True, text=True)


def ensure_merge_drivers(root: Path, dry_run: bool = False, overwrite: bool = False,
                         quiet: bool = True) -> dict:
    """Registra i merge driver nella config locale. Idempotente: se il valore c'e' gia' non scrive.

    Con overwrite=False un driver con comando diverso non viene toccato. Ritorna
    {nome: 'ok' | 'installed' | 'updated' | 'conflict'}. Con dry_run non scrive.
    """
    esiti = {}
    for nome, (descrizione, comando) in MERGE_DRIVERS.items():
        chiave = f"merge.{nome}.driver"
        attuale = _git_config(root, "--get", chiave).stdout.strip()
        if attuale == comando:
            esiti[nome] = "ok"
        elif attuale and not overwrite:
            esiti[nome] = "conflict"
        else:
            esiti[nome] = "updated" if attuale else "installed"
            if not dry_run:
                _git_config(root, chiave, comando)
                _git_config(root, f"merge.{nome}.name", descrizione)
        if not quiet:
            print("  " + {
                "ok": color.green(f"OK -- driver {nome} gia' registrato."),
                "conflict": color.yellow(f"ATTENZIONE -- driver {nome} diverso ({attuale}); "
                                         "riesegui senza --only per riallinearlo."),
                "installed": color.cyan(f"{'[dry-run] Registrerebbe' if dry_run else 'Registrato'} driver {nome}."),
                "updated": color.cyan(f"{'[dry-run] Aggiornerebbe' if dry_run else 'Aggiornato'} driver {nome}."),
            }[esiti[nome]])
    return esiti


def log_guard_enabled(root: Path) -> bool:
    """`wiki_lint.log_append_guard.hook: true` in factory.config.yaml (lettura per indentazione,
    senza YAML: stdlib-only). Assente, illeggibile o diverso da true -> False."""
    cfg = root / "factory.config.yaml"
    if not cfg.is_file():
        return False
    path = ["wiki_lint", "log_append_guard"]
    depth = 0
    for raw in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key = line.strip()
        if depth < len(path):
            if indent == 2 * depth and key == path[depth] + ":":
                depth += 1
            elif indent == 0 and depth:
                depth = 0
                if key == path[0] + ":":
                    depth = 1
            continue
        if indent < 2 * depth:
            return False
        m = re.match(r"hook:\s*(\S+)$", key)
        if indent == 2 * depth and m:
            return m.group(1).strip("\"'").lower() == "true"
    return False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _prompt(msg: str) -> str:
    try:
        with open("/dev/tty", "r") as tty:
            sys.stdout.write(msg)
            sys.stdout.flush()
            return tty.readline().strip()
    except OSError:
        return input(msg).strip()


def _factory_hooks_dir(root: Path) -> Path:
    """Directory hooks letta da git (comune a tutti i worktree, rispetta core.hooksPath).

    Da un worktree il file .git punta a .git/worktrees/<nome>, la cui cartella hooks git non
    legge: per questo si chiede a git. Il calcolo dal file .git resta come riserva.
    """
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute",
                            "--git-path", "hooks"], capture_output=True, text=True)
    except OSError:
        r = None
    if r is not None and r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip())
    git_marker = root / ".git"
    if git_marker.is_file():
        raw = git_marker.read_text(encoding="utf-8").strip()
        gitdir = raw.split("gitdir:", 1)[1].strip() if "gitdir:" in raw else raw
        gitdir_path = Path(gitdir)
        if not gitdir_path.is_absolute():
            gitdir_path = (root / gitdir_path).resolve()
        return gitdir_path / "hooks"
    return git_marker / "hooks"


def _install(name: str, content: str, hooks_dir: Path,
             dry_run: bool, force: bool) -> str:
    """Ritorna 'installed' | 'skipped' | 'conflict'."""
    hook_path = hooks_dir / name
    expected = _sha256(content.encode("utf-8"))

    if hook_path.exists():
        existing = _sha256(hook_path.read_bytes())
        if existing == expected:
            print("  " + color.green(f"OK -- {name} gia' aggiornato (checksum identico)."))
            return "skipped"
        print("  " + color.yellow(f"ATTENZIONE -- esiste un {name} diverso: {hook_path}"))
        if dry_run:
            print("  " + color.yellow("[dry-run] Sovrascrittura richiesta -- esegui senza --dry-run."))
            return "conflict"
        if not force:
            if _prompt(f"  Sovrascrivere il hook {name} esistente? [y/N] ") not in ("y", "Y"):
                print("  " + color.yellow(f"SKIP -- {name} non sovrascritto."))
                return "skipped"
        else:
            print("  " + color.yellow(f"--force: sovrascrittura di {name}."))

    if dry_run:
        print("  " + color.cyan(f"[dry-run] Installerebbe {name} in: {hook_path}"))
        return "skipped"

    hook_path.write_text(content, encoding="utf-8")
    hook_path.chmod(0o755)
    print("  " + color.green(f"Installato: {hook_path}"))
    return "installed"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Installa gli hook del repo padre (auto-align submodule).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra cosa verrebbe installato.")
    parser.add_argument("--force", action="store_true",
                        help="Sovrascrive senza prompt.")
    parser.add_argument("--only", choices=sorted(set(HOOKS) | {"pre-commit"}),
                        help="Installa solo questo hook (niente altri hook ne' merge driver).")
    parser.add_argument("--root", help=argparse.SUPPRESS)  # test
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else factory_root()
    if args.only:
        hooks_dir = _factory_hooks_dir(root)
        if not args.dry_run:
            hooks_dir.mkdir(parents=True, exist_ok=True)
        print(color.cyan(args.only) + ":")
        content = PRE_COMMIT_HOOK if args.only == "pre-commit" else HOOKS[args.only]
        esito = _install(args.only, content, hooks_dir, args.dry_run, args.force)
        return 1 if esito == "conflict" else 0
    hooks_dir = _factory_hooks_dir(root)
    if not hooks_dir.is_dir():
        if args.dry_run:
            print(color.yellow(f"[dry-run] Creerebbe directory: {hooks_dir}"))
        else:
            hooks_dir.mkdir(parents=True, exist_ok=True)

    print(color.cyan(f"Repo padre: {root}"))
    print(color.cyan(f"Hooks dir : {hooks_dir}"))
    print()

    hooks = dict(HOOKS)
    if log_guard_enabled(root):
        hooks["pre-commit"] = PRE_COMMIT_HOOK
    else:
        print(color.cyan("pre-commit:") + " non richiesto (wiki_lint.log_append_guard.hook: false)")
        print()

    installed = skipped = conflicts = 0
    for name, content in hooks.items():
        print(color.cyan(name) + ":")
        outcome = _install(name, content, hooks_dir, args.dry_run, args.force)
        installed += outcome == "installed"
        skipped += outcome == "skipped"
        conflicts += outcome == "conflict"

    print(color.cyan("merge driver (git config locale):"))
    ensure_merge_drivers(root, dry_run=args.dry_run, overwrite=True, quiet=False)
    print()
    if args.dry_run:
        print(color.cyan(
            f"[dry-run] Riepilogo: {installed} da installare, {skipped} skip, "
            f"{conflicts} conflitti."))
        print(color.yellow("Esegui senza --dry-run per procedere."))
    else:
        print(color.green(f"Riepilogo: {installed} hook installati, {skipped} skip."))
        if installed:
            print(color.yellow(
                "Gli hook sono locali (.git/hooks non e' versionato): ogni collaboratore "
                "deve eseguire questo installer una volta."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
