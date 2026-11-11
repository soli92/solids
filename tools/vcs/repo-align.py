#!/usr/bin/env python3
"""
tools/vcs/repo-align.py — verifica allineamento repo senza mutazione del working tree.

Risponde a: «il mio lavoro locale e' gia' sul remote?»

Supporta tutti i vcs.mode di PATTERN §15:
  monorepo  — git rev-parse HEAD vs git ls-remote origin refs/heads/<branch>
  submodule — gitlink-SHA nel parent vs ls-remote nel submodule remote
  sibling   — come monorepo, nel working tree del sibling (path separato)
  external  — unverified, reason opaque_topology (la factory non ne conosce la topologia)
  none      — escluso dal set: non e' un target (non unverified)

Operazione con effetti remoti: SOLO git ls-remote (zero mutazione locale).
MAI: fetch, pull, checkout, reset, submodule update.

Verdetti: aligned | diverged | unverified
Reason enum per unverified:
  unreachable | auth_failure | no_remote | detached_head |
  not_a_git_repo | opaque_topology | base_branch_undeclared |
  base_branch_misplaced | archived | auth_missing

auth_missing: il remote ha rifiutato e il token dichiarato in auth_domains[] non si
risolve (ne' in ambiente ne' in repo_align.env_file). Senza token dichiarato lo stesso
rifiuto resta auth_failure.

Uso:
  python3 tools/vcs/repo-align.py [--repos=<n1,n2>] [--json] [--config=<path>]

Argomenti:
  --repos=n1,n2   Override esplicito: verifica solo questi target (per nome)
  --json          Output machine-readable JSON
  --config=<p>    Percorso factory.config.yaml (default: auto-detect)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Tipi
# ---------------------------------------------------------------------------

Verdict = str  # "aligned" | "diverged" | "unverified"
Reason = str   # enum chiuso (vedi docstring sopra)

# ---------------------------------------------------------------------------
# Factory config — parsing regex (stdlib-only, niente PyYAML)
# ---------------------------------------------------------------------------

def _find_factory_root(start: str) -> Optional[Path]:
    """Risale l'albero da start finche' trova factory.config.yaml."""
    p = Path(start).resolve()
    for candidate in [p] + list(p.parents):
        if (candidate / "factory.config.yaml").exists():
            return candidate
    return None


def _scalar(text: str, key: str) -> Optional[str]:
    """Estrae uno scalare di primo livello: `key: value`."""
    m = re.search(
        rf'(?m)^{re.escape(key)}:\s*["\']?([^"\'\n#][^\n#]*?)["\']?\s*(?:#.*)?$',
        text,
    )
    if not m:
        # Prova con valore vuoto fra virgolette: `key: ""`
        m2 = re.search(rf'(?m)^{re.escape(key)}:\s*["\']["\']', text)
        if m2:
            return ""
        return None
    return m.group(1).strip().strip("\"'")


def _top_level_block(text: str, key: str) -> str:
    """Restituisce il contenuto indentato sotto `key:` (primo livello)."""
    m = re.search(
        rf'(?m)^{re.escape(key)}:\s*\n((?:[ \t]+[^\n]*\n?|[ \t]*\n)*)',
        text,
    )
    return m.group(1) if m else ""


def _block_scalar(block: str, key: str) -> Optional[str]:
    """Estrae `key: value` da un blocco indentato."""
    m = re.search(
        rf'(?m)^\s+{re.escape(key)}:\s*["\']?([^"\'\n#][^\n#]*?)["\']?\s*(?:#.*)?$',
        block,
    )
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def _parse_code_paths(text: str) -> list[dict]:
    """
    Parsa code_paths[] da factory.config.yaml con parsing riga per riga.
    Restituisce lista di dict con campi:
      name, path, vcs_mode, submodule_path, base_branch, remote_url
    """
    lines = text.splitlines()
    in_block = False
    in_vcs = False
    in_ba = False
    items: list[dict] = []
    current: Optional[dict] = None

    for line in lines:
        raw = line.rstrip()
        stripped = raw.lstrip()

        # Salta commenti e righe vuote
        if not stripped or stripped.startswith("#"):
            continue

        leading = len(raw) - len(stripped)

        # Inizio blocco code_paths:
        if re.match(r'^code_paths:\s*$', raw):
            in_block = True
            continue

        # Fine blocco (tasto top-level non indentato, non lista)
        if in_block and leading == 0 and not stripped.startswith("-"):
            in_block = False
            if current is not None:
                items.append(current)
                current = None
            continue

        if not in_block:
            continue

        # Nuovo item: `  - ...`
        if re.match(r'^\s{0,4}-\s', raw):
            if current is not None:
                items.append(current)
            current = {
                "name": None, "path": None, "vcs_mode": None,
                "submodule_path": None, "base_branch": None, "remote_url": None,
                "misplaced_base_branch": None,
            }
            in_vcs = False
            in_ba = False
            # Inline `  - name: foo`
            m = re.match(r'^\s*-\s+(\w[\w_-]*):\s*(.*)', raw)
            if m:
                k, v = m.group(1), m.group(2).strip().strip("\"'").split("#")[0].strip()
                if k == "name":
                    current["name"] = v
            continue

        if current is None:
            continue

        # Campi a 4 spazi (item-level)
        if leading == 4:
            in_vcs = False
            in_ba = False
            m = re.match(r'^\s{4}(\w[\w_-]*):\s*(.*)', raw)
            if not m:
                continue
            k, v = m.group(1), m.group(2).strip().strip("\"'").split("#")[0].strip()
            if k == "name":
                current["name"] = v
            elif k == "path":
                current["path"] = v
            elif k == "vcs":
                in_vcs = True
            continue

        # base_branch dentro branch_awareness: fuori dallo schema PATTERN §15, che lo
        # vuole fratello del blocco. Nessun consumatore EP-034 lo legge li': lo si
        # registra per nominarlo, non per usarlo.
        if leading == 8 and in_ba:
            m = re.match(r'^\s{8}base_branch:\s*(.*)', raw)
            if m:
                current["misplaced_base_branch"] = m.group(1).strip().strip("\"'").split("#")[0].strip()
            continue

        # Sotto-campi vcs a 6 spazi
        if leading == 6 and in_vcs:
            m = re.match(r'^\s{6}(\w[\w_-]*):\s*(.*)', raw)
            if not m:
                continue
            k, v = m.group(1), m.group(2).strip().strip("\"'").split("#")[0].strip()
            in_ba = k == "branch_awareness"
            if k == "mode":
                current["vcs_mode"] = v
            elif k == "submodule_path":
                current["submodule_path"] = v
            elif k == "base_branch":
                current["base_branch"] = v
            elif k == "remote_url":
                current["remote_url"] = v
            continue

    # Fine file con blocco ancora aperto
    if in_block and current is not None:
        items.append(current)

    return [i for i in items if i.get("name")]


def _parse_auth_domains(text: str) -> list[dict]:
    """
    Parsa il blocco repo_align.auth_domains[] se presente.
    Campo opzionale — assente → lista vuota (si usano credenziali d'ambiente).
    """
    block = _top_level_block(text, "repo_align")
    if not block:
        return []
    # Trova il sotto-blocco auth_domains:
    m = re.search(r'(?m)^\s+auth_domains:\s*\n((?:\s{4,}[^\n]*\n?)*)', block)
    if not m:
        return []
    ad_block = m.group(1)
    # Splitta per item: ogni item inizia con 4+ spazi + "- "
    # Usa finditer sulle righe che iniziano con `    - ` per trovare i punti di split
    lines = ad_block.split("\n")
    items: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if re.match(r'^\s{4}-\s', line):
            if current:
                items.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        items.append(current)

    domains = []
    for item_lines in items:
        item_text = "\n".join(item_lines)
        d: dict = {}
        for key in ("name", "path", "remote", "branch", "token_env", "token_env_var", "auth_type"):
            # Il primo campo puo' essere sulla stessa riga del `- `: `    - name: val`
            # oppure su una riga indentata: `      name: val`
            mv = re.search(
                rf'(?m)^[\s\-]*{re.escape(key)}:\s*["\']?([^"\'\n#][^\n#]*?)["\']?\s*(?:#.*)?$',
                item_text,
            )
            if mv:
                d[key] = mv.group(1).strip().strip("\"'")
        if d:
            # `token_env_var` e' la forma documentata nel blocco di config: sinonimo
            if "token_env" not in d and "token_env_var" in d:
                d["token_env"] = d["token_env_var"]
            domains.append(d)
    return domains


def load_config(config_path: Path) -> dict:
    """Carica e parsa i campi rilevanti di factory.config.yaml."""
    text = config_path.read_text(encoding="utf-8")
    cfg: dict = {}

    # code_paths[]
    cfg["code_paths"] = _parse_code_paths(text)

    # Legacy single-repo
    cp = _scalar(text, "code_path")
    cfg["legacy_code_path"] = cp

    # Legacy top-level vcs: block
    vcs_block = _top_level_block(text, "vcs")
    cfg["legacy_vcs_mode"] = _block_scalar(vcs_block, "mode")
    cfg["legacy_base_branch"] = _block_scalar(vcs_block, "base_branch")

    # auth_domains (opzionale)
    cfg["auth_domains"] = _parse_auth_domains(text)
    # file KEY=VALUE da cui leggere i token assenti dall'ambiente (opzionale)
    cfg["env_file"] = _block_scalar(_top_level_block(text, "repo_align"), "env_file")

    return cfg

# ---------------------------------------------------------------------------
# Risoluzione token di autenticazione
# ---------------------------------------------------------------------------

def _resolve_token(token_env: Optional[str], env_file: Optional[Path] = None) -> Optional[str]:
    """
    Risolve un token: prima la variabile d'ambiente, poi `env_file` (righe KEY=VALUE).
    Il file si legge riga per riga e non si esegue mai: valori con caratteri speciali
    (password) non passano per la shell. Restituisce None se non trovato.
    """
    if not token_env:
        return None
    key = token_env.strip()
    if os.environ.get(key):
        return os.environ[key]
    if env_file and env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            k, sep, v = line.strip().removeprefix("export ").partition("=")
            if sep and k.strip() == key:
                return v.strip().strip("\"'") or None
    return None


def _git_env_for_auth(auth_entry: Optional[dict]) -> dict:
    """Costruisce env vars per git con auth opzionale."""
    env = os.environ.copy()
    if auth_entry and auth_entry.get("token_env"):
        token = _resolve_token(auth_entry["token_env"])
        if token:
            # GIT_ASKPASS non-interattivo: inietta credenziali via env
            # Usiamo http.extraHeader tramite GIT_CONFIG_COUNT
            env["GIT_CONFIG_COUNT"] = "1"
            import base64
            encoded = base64.b64encode(f":{token}".encode()).decode()
            env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
            env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {encoded}"
    return env

# ---------------------------------------------------------------------------
# Primitiva zero-mutation: git ls-remote
# ---------------------------------------------------------------------------

def _ls_remote(repo_path: str, branch: str, auth_env: Optional[dict] = None) -> tuple[Optional[str], str]:
    """
    Chiama git ls-remote origin refs/heads/<branch> nel path dato.
    Restituisce (sha, reason_se_fallisce).
    sha = None significa fallimento; reason e' nell'enum chiuso.
    Zero mutazione sul working tree.
    """
    env = dict(os.environ)
    if auth_env:
        env.update(auth_env)

    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "ls-remote", "origin",
             f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except FileNotFoundError:
        return None, "not_a_git_repo"
    except subprocess.TimeoutExpired:
        return None, "unreachable"

    if result.returncode != 0:
        stderr = result.stderr.lower()
        if any(kw in stderr for kw in ("authentication", "403", "401", "permission denied", "could not read")):
            return None, "auth_failure"
        if "does not appear to be a git repository" in stderr:
            return None, "no_remote"
        return None, "unreachable"

    out = result.stdout.strip()
    if not out:
        # Branch non esiste sul remote
        return None, "unreachable"

    sha = out.split()[0]
    return sha, ""


def _current_head(repo_path: str) -> tuple[Optional[str], str]:
    """
    Restituisce (sha, reason). reason non vuoto = problema.
    Non controlla .git esplicitamente: lascia a git di risalire l'albero
    (necessario per path che sono sottodirectory di un monorepo).
    """
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        return None, "not_a_git_repo"
    except subprocess.TimeoutExpired:
        return None, "unreachable"

    if r.returncode != 0:
        return None, "not_a_git_repo"

    sha = r.stdout.strip()
    return sha, ""


def _current_branch(repo_path: str) -> Optional[str]:
    """Restituisce il nome del branch corrente, None se detached."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            b = r.stdout.strip()
            return None if b == "HEAD" else b
    except Exception:
        pass
    return None


def _has_remote(repo_path: str) -> bool:
    """Verifica se esiste un remote 'origin'."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "remote"],
            capture_output=True, text=True, timeout=10,
        )
        return "origin" in r.stdout.split()
    except Exception:
        return False


def _determine_direction(
    repo_path: str, local_sha: str, remote_sha: str
) -> dict:
    """
    Determina la direzione della divergenza senza fetch.
    Tenta di usare rev-list se il remote SHA e' nel local object store.
    Restituisce dict con chiavi: avanti, indietro, note.
    """
    # Controlla se il remote SHA e' presente localmente
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "cat-file", "-e", f"{remote_sha}^{{commit}}"],
            capture_output=True, timeout=10,
        )
        remote_known = (r.returncode == 0)
    except Exception:
        remote_known = False

    if not remote_known:
        return {
            "avanti": None,
            "indietro": None,
            "note": "distanza non calcolabile (remote SHA non in object store locale; eseguire git fetch per la distanza)",
        }

    # Commit in locale ma non nel remote (locale e' avanti)
    try:
        r1 = subprocess.run(
            ["git", "-C", repo_path, "rev-list", "--count", f"{remote_sha}..{local_sha}"],
            capture_output=True, text=True, timeout=10,
        )
        ahead = int(r1.stdout.strip()) if r1.returncode == 0 else 0
    except Exception:
        ahead = 0

    # Commit nel remote ma non in locale (remote e' avanti)
    try:
        r2 = subprocess.run(
            ["git", "-C", repo_path, "rev-list", "--count", f"{local_sha}..{remote_sha}"],
            capture_output=True, text=True, timeout=10,
        )
        behind = int(r2.stdout.strip()) if r2.returncode == 0 else 0
    except Exception:
        behind = 0

    note = ""
    if ahead > 0 and behind == 0:
        note = f"avanti di {ahead} commit (commit locali non presenti sul remote)"
    elif behind > 0 and ahead == 0:
        note = f"indietro di {behind} commit (commit sul remote non presenti localmente)"
    elif ahead > 0 and behind > 0:
        note = f"biforcato: +{ahead} locale, +{behind} remote"
    else:
        note = "distanza calcolata zero ma SHA diversi (anomalia)"

    return {"avanti": ahead, "indietro": behind, "note": note}


# ---------------------------------------------------------------------------
# Verifica per vcs.mode
# ---------------------------------------------------------------------------

def _check_monorepo(
    name: str, repo_path: str, base_branch: Optional[str],
    auth_env: Optional[dict] = None,
) -> dict:
    """
    monorepo: git rev-parse HEAD vs git ls-remote origin refs/heads/<branch>
    Il path e' nel factory repo (path relativo o assoluto).
    """
    result = {
        "name": name, "mode": "monorepo", "path": repo_path,
        "verdict": None, "branch": base_branch,
        "local_sha": None, "remote_sha": None,
        "direction": None, "reason": None, "note": "",
    }

    if not _has_remote(repo_path):
        result["verdict"] = "unverified"
        result["reason"] = "no_remote"
        return result

    # Risolvi branch se non dichiarato
    branch = base_branch
    if not branch:
        branch = _current_branch(repo_path)
    if not branch:
        result["verdict"] = "unverified"
        result["reason"] = "detached_head"
        return result
    if not base_branch:
        result["branch"] = branch
        result["note"] = "branch rilevato da HEAD (non dichiarato in config)"

    local_sha, err = _current_head(repo_path)
    if err:
        result["verdict"] = "unverified"
        result["reason"] = err
        return result
    result["local_sha"] = local_sha

    remote_sha, reason = _ls_remote(repo_path, branch, auth_env)
    if remote_sha is None:
        result["verdict"] = "unverified"
        result["reason"] = reason or "unreachable"
        return result
    result["remote_sha"] = remote_sha

    if local_sha == remote_sha:
        result["verdict"] = "aligned"
    else:
        result["verdict"] = "diverged"
        result["direction"] = _determine_direction(repo_path, local_sha, remote_sha)

    return result



def _is_archived_submodule(factory_root: str, submodule_path: str) -> bool:
    """True se il submodule ha `archived = true` in .gitmodules.

    Usa solo subprocess (stdlib), coerente con il design standalone di repo-align.
    Risolve il nome di sezione dal path prima di leggere la chiave archived.
    """
    gitmodules = os.path.join(factory_root, ".gitmodules")
    if not os.path.isfile(gitmodules):
        return False
    try:
        r = subprocess.run(
            ["git", "config", "-f", gitmodules, "--get-regexp",
             r"submodule\..*\.path"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return False
    section_name: Optional[str] = None
    for line in (r.stdout or "").splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[1].strip() == submodule_path:
            key = parts[0]
            inner = key[len("submodule."):]
            section_name = inner[: -len(".path")] if inner.endswith(".path") else inner
            break
    if not section_name:
        return False
    try:
        ra = subprocess.run(
            ["git", "config", "-f", gitmodules, "--get",
             f"submodule.{section_name}.archived"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return False
    return ra.returncode == 0 and ra.stdout.strip().lower() == "true"


def _check_submodule(
    name: str, factory_root: str, submodule_path: str, base_branch: Optional[str],
    auth_env: Optional[dict] = None, misplaced_base_branch: Optional[str] = None,
) -> dict:
    """
    submodule: gitlink-SHA nel parent vs ls-remote nel submodule.
    Il confronto e' sempre gitlink-parent vs remoto — mai HEAD locale del submodule.
    Nota semantica: detached HEAD del submodule NON e' segnale di divergenza.
    """
    result = {
        "name": name, "mode": "submodule", "path": submodule_path,
        "verdict": None, "branch": base_branch,
        "gitlink_sha": None, "remote_sha": None,
        "direction": None, "reason": None, "note": "",
    }

    if not base_branch and misplaced_base_branch:
        result["verdict"] = "unverified"
        result["reason"] = "base_branch_misplaced"
        result["note"] = (
            f"base_branch: {misplaced_base_branch} e' dentro vcs.branch_awareness; "
            "lo schema (PATTERN §15) lo vuole in vcs.base_branch, dove lo leggono "
            "anche branch-resolver e dispatch gate"
        )
        return result

    if not base_branch:
        result["verdict"] = "unverified"
        result["reason"] = "base_branch_undeclared"
        result["note"] = "submodule richiede base_branch dichiarato in config"
        return result

    # Gitlink SHA: SHA registrata nel parent (NON l'HEAD del checkout locale)
    # Usa git ls-files -s <path> nel parent repo
    submod_rel = submodule_path.rstrip("/")
    try:
        r = subprocess.run(
            ["git", "-C", factory_root, "ls-files", "-s", submod_rel],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        result["verdict"] = "unverified"
        result["reason"] = "not_a_git_repo"
        return result

    if r.returncode != 0 or not r.stdout.strip():
        result["verdict"] = "unverified"
        result["reason"] = "not_a_git_repo"
        result["note"] = f"git ls-files -s {submod_rel!r} non ha restituito output"
        return result

    # Formato: <mode> <sha> <stage>\t<path>
    parts = r.stdout.strip().split()
    if len(parts) < 2:
        result["verdict"] = "unverified"
        result["reason"] = "not_a_git_repo"
        result["note"] = "output git ls-files -s inatteso"
        return result

    gitlink_sha = parts[1]
    result["gitlink_sha"] = gitlink_sha

    # Path fisico del submodule per ls-remote
    submod_abs = os.path.join(factory_root, submod_rel)
    if not os.path.isdir(submod_abs):
        result["verdict"] = "unverified"
        result["reason"] = "not_a_git_repo"
        result["note"] = f"directory submodule non trovata: {submod_abs}"
        return result

    remote_sha, reason = _ls_remote(submod_abs, base_branch, auth_env)
    if remote_sha is None:
        result["verdict"] = "unverified"
        result["reason"] = reason or "unreachable"
        return result
    result["remote_sha"] = remote_sha

    if gitlink_sha == remote_sha:
        result["verdict"] = "aligned"
    else:
        result["verdict"] = "diverged"
        # Per submodule la direzione e' semplificata:
        # gitlink < remote = parent e' indietro (parent punta a vecchio commit)
        # gitlink > remote (insolito) = parent e' avanti
        result["direction"] = {
            "avanti": None,
            "indietro": None,
            "note": (
                f"gitlink nel parent ({gitlink_sha[:7]}) != tip del remote ({remote_sha[:7]}) "
                f"— aggiornare il gitlink con git add {submod_rel} && git commit"
            ),
        }

    return result


def _check_sibling(
    name: str, sibling_path: str, base_branch: Optional[str],
    auth_env: Optional[dict] = None,
) -> dict:
    """
    sibling: come monorepo, nel working tree del sibling.
    """
    result = _check_monorepo(name, sibling_path, base_branch, auth_env)
    result["mode"] = "sibling"
    return result


def _check_external(name: str, path: str) -> dict:
    """
    external: unverified, reason opaque_topology.
    La factory non ne conosce la topologia VCS (PATTERN §15).
    """
    return {
        "name": name, "mode": "external", "path": path,
        "verdict": "unverified",
        "reason": "opaque_topology",
        "note": "vcs.mode=external: la factory non gestisce git per questo path (PATTERN §15)",
        "branch": None, "local_sha": None, "remote_sha": None,
        "direction": None,
    }

# ---------------------------------------------------------------------------
# Risoluzione target
# ---------------------------------------------------------------------------

def _resolve_targets(
    cfg: dict,
    factory_root: Path,
    repos_filter: Optional[list[str]],
) -> list[dict]:
    """
    Costruisce la lista di target da verificare.
    Ordine di precedenza: --repos= > code_paths[] > legacy code_path.
    mode=none → escluso. mode=external → incluso come unverified.
    """
    # indicizzati per nome e per path: la forma documentata in config usa `path`
    auth_map: dict[str, dict] = {}
    for d in cfg.get("auth_domains", []):
        for k in (d.get("name"), d.get("path")):
            if k:
                auth_map.setdefault(k.rstrip("/"), d)
    env_file = cfg.get("env_file")
    env_path = (factory_root / env_file) if env_file and not os.path.isabs(env_file) else (
        Path(env_file) if env_file else None)

    targets = []

    # Aggiunge entry da code_paths[]
    for entry in cfg.get("code_paths", []):
        mode = (entry.get("vcs_mode") or "").strip()
        if mode == "none":
            continue  # escluso dal set, non unverified

        name = entry.get("name") or "unnamed"
        raw_path = (entry.get("path") or "").strip()

        # Risolvi path assoluto
        if raw_path and not os.path.isabs(raw_path):
            abs_path = str(factory_root / raw_path)
        else:
            abs_path = raw_path or str(factory_root)

        auth_entry = auth_map.get(name) or auth_map.get(raw_path.rstrip("/"))
        auth_env_extra: dict = {}
        auth_missing = None
        if auth_entry and auth_entry.get("token_env"):
            token = _resolve_token(auth_entry["token_env"], env_path)
            if not token:
                auth_missing = auth_entry["token_env"]
            if token:
                import base64
                encoded = base64.b64encode(f":{token}".encode()).decode()
                auth_env_extra["GIT_CONFIG_COUNT"] = "1"
                auth_env_extra["GIT_CONFIG_KEY_0"] = "http.extraHeader"
                auth_env_extra["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {encoded}"

        branch = entry.get("base_branch") or (auth_entry or {}).get("branch")

        targets.append({
            "name": name,
            "mode": mode,
            "path": abs_path,
            "raw_path": raw_path,
            "branch": branch,
            "submodule_path": entry.get("submodule_path") or raw_path,
            "auth_env": auth_env_extra if auth_env_extra else None,
            "auth_missing": auth_missing,
            "misplaced_base_branch": entry.get("misplaced_base_branch"),
        })

    # Legacy single-repo: aggiunge il repo della factory stessa
    legacy_cp = cfg.get("legacy_code_path")
    legacy_mode = cfg.get("legacy_vcs_mode")
    legacy_branch = cfg.get("legacy_base_branch")

    if legacy_cp is not None and legacy_mode and legacy_mode != "none":
        # Evita duplicati se gia' presente in code_paths[]
        factory_root_str = str(factory_root)
        if legacy_cp in (".", ""):
            abs_legacy = factory_root_str
        else:
            abs_legacy = str(factory_root / legacy_cp)

        already = any(t["path"] == abs_legacy for t in targets)
        if not already:
            targets.append({
                "name": "factory",
                "mode": legacy_mode,
                "path": abs_legacy,
                "raw_path": legacy_cp,
                "branch": legacy_branch,
                "submodule_path": legacy_cp,
                "auth_env": None,
            })

    # Applica filtro --repos=
    if repos_filter:
        targets = [t for t in targets if t["name"] in repos_filter]

    return targets


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_check(target: dict, factory_root: Path) -> dict:
    """Esegue il check per un singolo target; un rifiuto con token non risolto e' auth_missing."""
    result = _run_check_mode(target, factory_root)
    missing = target.get("auth_missing")
    if missing and result.get("reason") == "auth_failure":
        result["reason"] = "auth_missing"
        result["note"] = (f"token {missing} dichiarato in auth_domains ma non risolto "
                          "(ambiente o repo_align.env_file)")
    return result


def _run_check_mode(target: dict, factory_root: Path) -> dict:
    """Esegue il check per un singolo target. Failure isolation."""
    mode = target["mode"]
    name = target["name"]
    path = target["path"]
    branch = target.get("branch")
    auth_env = target.get("auth_env")
    submodule_path = target.get("submodule_path") or path

    try:
        if mode == "monorepo":
            return _check_monorepo(name, path, branch, auth_env)
        elif mode == "submodule":
            # Submodule archiviati: read-only sull'host remoto.
            # Si riporta `unverified: archived` e non `diverged`: un archiviato non riceve push,
            # quindi una divergenza non e' un problema operativo; distinguerlo dagli errori
            # reali tiene visibile il submodule senza far scattare allarmi.
            if _is_archived_submodule(str(factory_root), submodule_path):
                return {
                    "name": name, "mode": "submodule", "path": submodule_path,
                    "verdict": "unverified", "branch": branch,
                    "gitlink_sha": None, "remote_sha": None,
                    "direction": None, "reason": "archived",
                    "note": "submodule archiviato (read-only) — nessuna azione richiesta",
                }
            return _check_submodule(
                name, str(factory_root), submodule_path, branch, auth_env,
                target.get("misplaced_base_branch"),
            )
        elif mode == "sibling":
            return _check_sibling(name, path, branch, auth_env)
        elif mode == "external":
            return _check_external(name, path)
        else:
            return {
                "name": name, "mode": mode, "path": path,
                "verdict": "unverified",
                "reason": "opaque_topology",
                "note": f"vcs.mode={mode!r} non riconosciuto",
                "branch": branch, "local_sha": None, "remote_sha": None,
                "direction": None,
            }
    except Exception as exc:  # failure isolation per target
        return {
            "name": name, "mode": mode, "path": path,
            "verdict": "unverified",
            "reason": "unreachable",
            "note": f"errore non atteso: {exc}",
            "branch": branch, "local_sha": None, "remote_sha": None,
            "direction": None,
        }

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _sha7(sha: Optional[str]) -> str:
    if not sha:
        return "(none)"
    return sha[:7]


def _render_text(results: list[dict], timestamp: str) -> str:
    aligned = [r for r in results if r["verdict"] == "aligned"]
    diverged = [r for r in results if r["verdict"] == "diverged"]
    unverified = [r for r in results if r["verdict"] == "unverified"]

    lines = [
        f"[repo-align — snapshot @{timestamp}]",
        "=" * 53,
        "Primitiva: git ls-remote --heads (zero mutazione su working tree e refs/remotes/)",
        "",
    ]

    if aligned:
        lines.append(f"ALIGNED ({len(aligned)}):")
        for r in aligned:
            local = _sha7(r.get("local_sha") or r.get("gitlink_sha"))
            remote = _sha7(r.get("remote_sha"))
            branch = r.get("branch") or "(rilevato)"
            lines.append(f"  {r['name']:<20} mode={r['mode']:<10} branch={branch}")
            lines.append(f"    local={local} == remote={remote}")
    else:
        lines.append("ALIGNED (0): (nessuno)")

    lines.append("")

    if diverged:
        lines.append(f"DIVERGED ({len(diverged)}):")
        for r in diverged:
            local = _sha7(r.get("local_sha") or r.get("gitlink_sha"))
            remote = _sha7(r.get("remote_sha"))
            branch = r.get("branch") or "(rilevato)"
            lines.append(f"  {r['name']:<20} mode={r['mode']:<10} branch={branch}")
            lines.append(f"    local={local} != remote={remote}")
            d = r.get("direction") or {}
            note = d.get("note") or ""
            if note:
                lines.append(f"    -> {note}")
    else:
        lines.append("DIVERGED (0): (nessuno)")

    lines.append("")

    if unverified:
        lines.append(f"UNVERIFIED ({len(unverified)}):")
        for r in unverified:
            reason = r.get("reason") or "unknown"
            note = r.get("note") or ""
            lines.append(f"  {r['name']:<20} mode={r['mode']:<10} reason={reason}")
            if note:
                lines.append(f"    nota: {note}")
    else:
        lines.append("UNVERIFIED (0): (nessuno)")

    lines += [
        "",
        "-" * 53,
        "Nota: distanza numerica disponibile solo se remote SHA e' nel local object store.",
        "Per distanza: git fetch origin <branch> && git rev-list --count HEAD..origin/<branch>",
        "Nessuna azione automatica eseguita (R.14, R.B8).",
    ]
    return "\n".join(lines)


def _render_json(results: list[dict], timestamp: str) -> str:
    payload = {
        "timestamp": timestamp,
        "primitive": "git ls-remote (zero mutation)",
        "repos": {
            "aligned": [r for r in results if r["verdict"] == "aligned"],
            "diverged": [r for r in results if r["verdict"] == "diverged"],
            "unverified": [r for r in results if r["verdict"] == "unverified"],
        },
    }
    return json.dumps(payload, indent=2, default=str)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verifica allineamento repo senza mutazione del working tree."
    )
    parser.add_argument("--repos", default="",
                        help="Override: lista nomi target separati da virgola")
    parser.add_argument("--json", action="store_true",
                        help="Output machine-readable JSON")
    parser.add_argument("--config", default="",
                        help="Percorso factory.config.yaml (default: auto-detect)")
    args = parser.parse_args()

    # Trova factory root
    if args.config:
        config_path = Path(args.config).resolve()
        factory_root = config_path.parent
    else:
        factory_root = _find_factory_root(os.getcwd())
        if factory_root is None:
            print("[repo-align] ERRORE: factory.config.yaml non trovato. "
                  "Eseguire dalla factory root o passare --config=<path>.",
                  file=sys.stderr)
            sys.exit(1)
        config_path = factory_root / "factory.config.yaml"

    # Carica config
    try:
        cfg = load_config(config_path)
    except Exception as exc:
        print(f"[repo-align] ERRORE lettura config: {exc}", file=sys.stderr)
        sys.exit(1)

    # Filtro --repos=
    repos_filter = [n.strip() for n in args.repos.split(",") if n.strip()] or None

    # Risolvi target
    targets = _resolve_targets(cfg, factory_root, repos_filter)

    if not targets:
        msg = "[repo-align] Nessun target trovato."
        if repos_filter:
            msg += f" Filtro: {repos_filter}. Nomi disponibili: " + \
                   ", ".join(e.get("name", "?") for e in cfg.get("code_paths", []))
        print(msg)
        return

    # Esegui check
    results = [_run_check(t, factory_root) for t in targets]

    # Timestamp
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Output
    if args.json:
        print(_render_json(results, ts))
    else:
        print(_render_text(results, ts))


if __name__ == "__main__":
    main()
