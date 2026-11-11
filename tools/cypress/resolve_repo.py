#!/usr/bin/env python3
"""resolve_repo.py — path effettivi di un repo di test Cypress e del suo sorgente.

    python3 tools/cypress/resolve_repo.py <name>
    python3 tools/cypress/resolve_repo.py --list

Legge il registro `cypress_pipeline:` di factory.config.yaml (parsing riga per riga,
senza PyYAML, come tools/vcs/smlib/factory_config.py) e restituisce in JSON, per il
repo di test e per il repo sorgente dell'applicazione testata:

- il path effettivo: il submodule della factory, oppure il clone personale dichiarato
  dall'operatore in `tools/vcs/.env.local-repos` (gitignored) o nell'ambiente, con le
  stesse chiavi `LOCAL_REPO_<NOME>` di `sm_update --from-local`;
- la fonte usata (`submodule` | `override`), cosi' chi legge sa sempre dove si lavora;
- il remote del path effettivo confrontato con quello del submodule in .gitmodules.

Sola lettura: nessuna scrittura, nessun comando git che modifica lo stato.

Esiti (campo `status`, exit code):
  ok        0  path risolti; eventuali avvisi in `warnings` (es. remote diverso)
  disabled  0  `cypress_pipeline.enabled` e' false: nessuna risoluzione
  error     1  submodule non inizializzato, override inesistente, registro illeggibile
  usage     2  argomenti non validi o repo non presente nel registro
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "tools" / "vcs"))

from smlib.factory_config import load_env_file  # noqa: E402  (tools/vcs/smlib, del master)

ENV_FILE = Path("tools") / "vcs" / ".env.local-repos"
GIT_TIMEOUT = 15  # secondi: sono tutte letture locali, oltre c'e' un problema del repo


class GitError(RuntimeError):
    """git non eseguibile o in timeout: il risultato sarebbe incompleto."""


def git_out(args: List[str], cwd: Path) -> str:
    """stdout di git (strip); "" se git esce con errore (es. remote assente).

    Timeout o git mancante sollevano GitError: in quel caso la risoluzione e'
    incompleta e non deve uscire come successo.
    """
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), text=True,
                              capture_output=True, timeout=GIT_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {' '.join(args)} in {cwd}: timeout dopo {GIT_TIMEOUT}s") from exc
    except OSError as exc:
        raise GitError(f"git {' '.join(args)} in {cwd}: {exc}") from exc
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()
REPO_FIELDS = (
    "name", "test_path", "layout", "source", "source_path", "source_branch",
    "conventions_ref", "conventions_status", "reporter",
)
DEFAULT_REPORTER = "generic"


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

def _value(raw: str) -> str:
    """Valore scalare: senza commento inline e senza virgolette."""
    value = raw.strip()
    if value[:1] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end > 0 else value[1:]
    return value.split("#", 1)[0].strip()


def load_registry(root: Path) -> Optional[dict]:
    """Blocco `cypress_pipeline:` come {enabled, reporter, repos[]}; None se il blocco manca."""
    try:
        text = (root / "factory.config.yaml").read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"(?m)^cypress_pipeline:[ \t]*\n((?:[ \t]+[^\n]*\n?|[ \t]*\n)*)", text)
    if not m:
        return None

    enabled = False
    reporter = DEFAULT_REPORTER
    repos: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        en = re.match(r"^  enabled:\s*(.*)$", line)
        if en:
            enabled = _value(en.group(1)).lower() == "true"
            continue
        rep = re.match(r"^  reporter:\s*(.*)$", line)
        if rep:
            reporter = _value(rep.group(1)) or DEFAULT_REPORTER
            continue
        item = re.match(r"^    -\s+(\w+):\s*(.*)$", line)
        if item:
            current = {}
            repos.append(current)
            current[item.group(1)] = _value(item.group(2))
            continue
        field = re.match(r"^      (\w+):\s*(.*)$", line)
        if field and current is not None:
            current[field.group(1)] = _value(field.group(2))
    return {"enabled": enabled, "reporter": reporter, "repos": [r for r in repos if r.get("name")]}


# ---------------------------------------------------------------------------
# Risoluzione
# ---------------------------------------------------------------------------

def env_key(name: str) -> str:
    return "LOCAL_REPO_" + re.sub(r"[^A-Za-z0-9]", "_", name).upper()


def _normalize_remote(url: str) -> str:
    """Remote confrontabile: senza credenziali, senza .git finale, minuscolo."""
    url = url.strip().rstrip("/")
    url = re.sub(r"^(https?://)[^/@]+@", r"\1", url)
    if url.endswith(".git"):
        url = url[:-4]
    return url.lower()


@functools.lru_cache(maxsize=None)
def _gitmodules_urls(root: Path) -> Dict[str, str]:
    """{path: url} da .gitmodules, letto una volta per processo."""
    out = git_out(["config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.(path|url)$"],
                  cwd=root)
    paths: Dict[str, str] = {}
    urls: Dict[str, str] = {}
    for entry in out.splitlines():
        key, _, value = entry.partition(" ")
        section, _, kind = key.rpartition(".")
        (paths if kind == "path" else urls)[section] = value.strip()
    return {p: urls.get(s, "") for s, p in paths.items()}


def _expected_remote(root: Path, rel_path: str) -> str:
    """URL del submodule in .gitmodules per il path dato ("" se non c'e')."""
    return _gitmodules_urls(root).get(rel_path, "")


def _is_repo_root(path: Path) -> bool:
    """True se `path` e' la radice di un repo git proprio (non la cartella di un submodule vuoto)."""
    if not (path / ".git").exists():
        return False
    top = git_out(["rev-parse", "--show-toplevel"], cwd=path)
    return bool(top) and Path(top).resolve() == path.resolve()


def resolve_one(root: Path, name: str, rel_path: str, overrides: Dict[str, str]) -> dict:
    """Path effettivo di un repo (test o sorgente) e fonte usata."""
    key = env_key(name)
    override = overrides.get(key) or os.environ.get(key, "")
    out = {
        "name": name,
        "registered_path": rel_path,
        "override_key": key,
        "source": "override" if override else "submodule",
        "path": None,
        "branch": None,
        "commit": None,
        "remote": None,
        "expected_remote": _expected_remote(root, rel_path) or None,
        "remote_match": None,
        "errors": [],
        "warnings": [],
    }

    if override:
        path = Path(override).expanduser()
        if not path.is_dir():
            out["errors"].append(f"override {key} punta a un path inesistente: {override}")
            return out
        if not _is_repo_root(path):
            out["errors"].append(f"override {key} non e' la radice di un repo git: {override}")
            return out
    else:
        path = root / rel_path
        if not _is_repo_root(path):
            target = rel_path[len("code_repos/"):] if rel_path.startswith("code_repos/") else rel_path
            out["errors"].append(
                f"submodule {rel_path} non inizializzato: "
                f"python3 tools/vcs/sm_doctor.py --target {target} "
                f"(oppure dichiarare un clone personale in {ENV_FILE.as_posix()} con {key})")
            return out

    out["path"] = path.resolve().as_posix()
    # un submodule sta di norma in detached HEAD sul commit del puntatore: branch None, commit valorizzato
    branch = git_out(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    out["branch"] = branch if branch and branch != "HEAD" else None
    out["commit"] = git_out(["rev-parse", "--short", "HEAD"], cwd=path) or None
    remote = git_out(["remote", "get-url", "origin"], cwd=path)
    out["remote"] = remote or None
    if remote and out["expected_remote"]:
        out["remote_match"] = _normalize_remote(remote) == _normalize_remote(out["expected_remote"])
        if not out["remote_match"]:
            out["warnings"].append(
                f"remote di {out['path']} ({_normalize_remote(remote)}) diverso dal submodule "
                f"registrato ({_normalize_remote(out['expected_remote'])})")
    return out


def resolve(root: Path, name: str) -> tuple[dict, int]:
    registry = load_registry(root)
    # capability opt-in: blocco assente = spenta (come enabled: false), non un errore
    if registry is None or not registry["enabled"]:
        return {"status": "disabled", "repo": name,
                "message": "cypress_pipeline.enabled e' false: nessuna risoluzione"}, 0
    entry = next((r for r in registry["repos"] if r.get("name") == name), None)
    if entry is None:
        names = ", ".join(r["name"] for r in registry["repos"])
        return {"status": "usage", "errors": [f"repo '{name}' non nel registro; disponibili: {names}"],
                "warnings": []}, 2
    missing = [f for f in ("test_path", "source", "source_path") if not entry.get(f)]
    if missing:
        return {"status": "error", "repo": name,
                "errors": [f"voce del registro incompleta, mancano: {', '.join(missing)}"]}, 1

    overrides = load_env_file(root / ENV_FILE)
    test = resolve_one(root, entry["name"], entry["test_path"], overrides)
    source = resolve_one(root, entry["source"], entry["source_path"], overrides)
    errors = test["errors"] + source["errors"]
    warnings = test["warnings"] + source["warnings"]
    expected_branch = entry.get("source_branch", "")
    if (expected_branch and expected_branch != "da_confermare"
            and source["branch"] and source["branch"] != expected_branch):
        warnings.append(f"sorgente su {source['branch']}, registro indica {expected_branch}: "
                        "i selettori si verificano su un branch diverso da quello registrato")
    result = {
        "status": "error" if errors else "ok",
        "repo": name,
        "layout": entry.get("layout"),
        "conventions_status": entry.get("conventions_status"),
        "conventions_ref": entry.get("conventions_ref") or None,
        "source_branch": entry.get("source_branch"),
        "reporter": entry.get("reporter") or registry.get("reporter") or DEFAULT_REPORTER,
        "test": test,
        "source": source,
        "errors": errors,
        "warnings": warnings,
    }
    return result, 1 if errors else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Path effettivi di un repo di test Cypress.")
    parser.add_argument("name", nargs="?", help="name del repo nel registro cypress_pipeline.repos")
    parser.add_argument("--list", action="store_true", help="elenca i repo registrati")
    parser.add_argument("--root", default=str(_ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(args.root)

    if args.list:
        registry = load_registry(root) or {"enabled": False, "repos": []}
        print(json.dumps({"status": "ok", "enabled": registry["enabled"],
                          "repos": [{f: r.get(f) for f in REPO_FIELDS} for r in registry["repos"]]},
                         ensure_ascii=False, indent=2))
        return 0
    if not args.name:
        parser.print_usage(sys.stderr)
        return 2

    try:
        result, code = resolve(root.resolve(), args.name)
    except GitError as exc:
        result, code = {"status": "error", "repo": args.name, "errors": [str(exc)]}, 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
