#!/usr/bin/env python3
"""ai-policy-scan.py — Check detective §ai_policy Layer-2 (factory-native).

Verifica che i repo cliente con ``suppress_ai_traces: true`` non contengano
attribution AI ne' ID kanban factory nella loro history git.

DUE modalita':
  default  — advisory, exit 0 sempre (non blocca il workflow).
  --strict — gate bloccante, exit 1 se ci sono violazioni. Da usare al pre-push
             o in dev-handoff. NON usare in contesti non bloccanti come session-close.

Importa i pattern da ``tools/vcs/ai_policy.py`` (TSK-697) — zero duplicazione.

Semantica scan, per ogni repo target:
  - Finestra ``@{u}..HEAD`` (commit locali avanti sull'upstream).
    Fallback: ultimi 20 commit se upstream non configurato (ragione dichiarata nel report).
  - Diff staged corrente (git diff --cached).
  Per ogni commit: messaggio e righe aggiunte del diff.

Output partition: {clean, violations, unscanned}.
  clean      — nessuna traccia trovata.
  violations — [{repo, commit_short, where: "message"|"diff", matched}]
  unscanned  — [{repo, reason}]  (errore per-repo, non crash)

Target repos (precedenza):
  1. Flag --repos=a,b  (path assoluti o relativi alla factory root)
  2. Scope dichiarato in ai_policy_check.scope[].path in factory.config.yaml

GUARDIA DI SCOPE (AC4):
  Il repo della factory stessa non viene MAI scansionato, nemmeno se passato
  esplicitamente con ``--repos``. Qui l'attribution AI nei commit del framework e'
  DOVUTA (e' il sistema che la richiede), non vietata. Uno scan indiscriminato
  segnalerebbe ogni commit e il check verrebbe spento. Il tentativo produce un
  RIFIUTO ESPLICITO, non uno skip silenzioso.

Stdlib-only. Nessun nome di cliente nel codice o nei commenti.
Riferimento: PATTERN §ai_policy, CLAUDE.md §ai_policy, ADR-074.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Factory root e import ai_policy (fonte unica dei pattern)
# File location: <factory_root>/tools/vcs/ai-policy-scan.py
#   parents[0] = <factory_root>/tools/vcs/
#   parents[1] = <factory_root>/tools/
#   parents[2] = <factory_root>/             ← factory root
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_ROOT = _SCRIPT_DIR.parents[1]

sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from ai_policy import (  # type: ignore[import]
        AI_SUBSTRINGS,
        find_factory_ids,
        is_ai_attribution,
    )
except ImportError as _e:
    print(
        f"[ai-policy] ERRORE: impossibile importare ai_policy da {_SCRIPT_DIR}. "
        f"Dettaglio: {_e}. Assicurarsi che tools/vcs/ai_policy.py esista.",
        file=sys.stderr,
    )
    sys.exit(0)  # advisory: exit 0 sempre


# ---------------------------------------------------------------------------
# Guardia di scope — il repo della factory non viene mai scansionato
# ---------------------------------------------------------------------------

class _ToplevelNonVerificabile(Exception):
    """git non ha risposto (timeout, eseguibile assente): il toplevel non e' noto."""


def _git_toplevel(path: Path) -> Optional[Path]:
    """Toplevel del repo git che contiene path; None se path non esiste o non e' in un repo.

    Solleva _ToplevelNonVerificabile se git non risponde: «non lo so» non e' «non e' un repo».
    """
    if not path.exists():
        return None
    try:
        r = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise _ToplevelNonVerificabile(str(exc)) from exc
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 else None


def _is_factory_root(path: Path, factory_roots: List[Path]) -> bool:
    """True se path appartiene allo stesso repo git di una delle factory.

    Si confronta il toplevel git, non il path: un submodule in code_repos/ sta
    dentro la cartella della factory ma e' un altro repo — ed e' proprio il repo
    cliente che il layer-2 deve scansionare. Un path inesistente non e' la factory:
    lo scan lo riporta come repo_not_found.

    La guardia e' un'invariante, quindi FALLISCE CHIUSA: se git non risponde (timeout
    sotto carico, prima era 10 s) il path si rifiuta. Rinunciare a scansionare un repo
    cliente si recupera rilanciando; scansionare la factory no.
    """
    try:
        risolto = path.resolve()
        if any(risolto == f.resolve() for f in factory_roots):
            return True
        top = _git_toplevel(path)
        if top is None:
            return False
        return any(top == _git_toplevel(f) for f in factory_roots)
    except _ToplevelNonVerificabile as exc:
        print(f"[ai-policy] guardia di scope non verificabile per '{path}' ({exc}): "
              "rifiutato per sicurezza, rilanciare.", file=sys.stderr)
        return True


def _main_checkout(root: Path) -> Path:
    """Checkout principale della factory, anche se lo script gira da un worktree.

    La parent di `git rev-parse --git-common-dir` e' il checkout principale, dove i
    submodule in code_repos/ sono inizializzati. Se git non risponde resta root
    (fail-open voluto: lo scan e' advisory e la guardia di scope resta attiva).
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute",
             "--git-common-dir"],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return root
    common = r.stdout.strip()
    if r.returncode != 0 or not common:
        return root
    main = Path(common).resolve().parent
    return main if (main / "factory.config.yaml").exists() else root


def _reject_factory_root(path: Path) -> str:
    """Messaggio di rifiuto esplicito per il factory root."""
    return (
        f"[ai-policy] RIFIUTO: '{path}' risolve al repo della factory stessa. "
        "Su questa factory l'attribution AI nei commit del framework e' DOVUTA, non vietata. "
        "Aggiungere solo i repo cliente a ai_policy_check.scope[] in factory.config.yaml. "
        "(guardia AC4 — non e' uno skip silenzioso)"
    )


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git(args: List[str], cwd: Path, timeout: int = 30) -> Tuple[int, str, str]:
    """Esegue un comando git; ritorna (returncode, stdout, stderr). Failure-isolated."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"
    except Exception as exc:
        return 1, "", str(exc)


# ---------------------------------------------------------------------------
# Config parsing (stdlib-only, no PyYAML)
# ---------------------------------------------------------------------------

def _parse_config_scope(factory_root: Path) -> List[str]:
    """Estrae ai_policy_check.scope[].path da factory.config.yaml via regex."""
    config_path = factory_root / "factory.config.yaml"
    if not config_path.exists():
        return []
    try:
        text = config_path.read_text(encoding="utf-8")
    except Exception:
        return []

    # Localizza il blocco ai_policy_check: (dalla chiave alla successiva chiave top-level o EOF)
    block_match = re.search(
        r"^ai_policy_check:\s*\n((?:(?:[ \t][^\n]*)?\n)*)",
        text,
        re.MULTILINE,
    )
    if not block_match:
        return []

    block = block_match.group(1)
    # Filtra le righe commentate prima di cercare path: — il blocco puo' contenere
    # righe esempio commentate come "# - path: ..." che non sono scope reali.
    active_lines = "\n".join(
        line for line in block.splitlines()
        if not line.lstrip().startswith("#")
    )
    paths = re.findall(r"path:\s*(\S+)", active_lines)
    return paths


# ---------------------------------------------------------------------------
# Scan logic
# ---------------------------------------------------------------------------

def _get_commits_to_scan(repo_path: Path) -> Tuple[List[str], Optional[str]]:
    """Ritorna (sha_list, fallback_reason).

    Primaria: git log @{u}..HEAD (commit locali avanti sull'upstream).
    Fallback: ultimi 20 commit se upstream non configurato (ragione dichiarata).
    """
    rc, out, err = _git(["log", "@{u}..HEAD", "--format=%H"], repo_path)
    if rc == 0:
        shas = [s for s in out.splitlines() if s.strip()]
        return shas, None

    # Upstream non configurato o altro errore → fallback
    rc2, out2, _ = _git(["log", "-n", "20", "--format=%H"], repo_path)
    if rc2 == 0:
        shas = [s for s in out2.splitlines() if s.strip()]
        return shas, "no_upstream_tracking (ultimi 20 commit scansionati)"

    return [], f"git_log_failed: {err}"


def _check_commit(sha: str, repo_path: Path) -> List[Dict]:
    """Controlla messaggio e righe aggiunte di un singolo commit.

    Ritorna lista di violation dict. Failure-isolated per commit.
    """
    violations: List[Dict] = []

    # 1. Check messaggio commit
    rc_msg, msg, _ = _git(["log", "-1", "--format=%B", sha], repo_path)
    if rc_msg == 0:
        for line in msg.splitlines():
            if is_ai_attribution(line):
                violations.append({
                    "commit_short": sha[:7],
                    "where": "message",
                    "matched": line.strip(),
                })
                break  # una segnalazione per messaggio

        # 1b. Guardia ID kanban factory nel messaggio
        factory_ids = find_factory_ids(msg)
        if factory_ids:
            uniq_ids = sorted(set(factory_ids))
            violations.append({
                "commit_short": sha[:7],
                "where": "message",
                "matched": "ID kanban factory: " + ", ".join(uniq_ids[:5]),
            })

    # 2. Check righe aggiunte nel diff del commit
    rc_diff, diff, _ = _git(
        ["show", "--format=", "--diff-filter=AM", "-U0", sha],
        repo_path,
    )
    if rc_diff == 0:
        for line in diff.splitlines():
            # Righe aggiunte: iniziano con "+" ma non con "+++" (intestazione)
            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                if is_ai_attribution(content):
                    violations.append({
                        "commit_short": sha[:7],
                        "where": "diff",
                        "matched": content.strip(),
                    })
                    break  # una segnalazione per diff commit

    return violations


def _check_staged(repo_path: Path) -> List[Dict]:
    """Controlla il diff staged (git diff --cached) per attribution AI."""
    violations: List[Dict] = []
    rc, diff, _ = _git(
        ["diff", "--cached", "--diff-filter=AM", "-U0"],
        repo_path,
    )
    if rc == 0 and diff.strip():
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                if is_ai_attribution(content):
                    violations.append({
                        "commit_short": "STAGED",
                        "where": "diff",
                        "matched": content.strip(),
                    })
                    break  # una segnalazione per staged diff
    return violations


def scan_repo(repo_path: Path) -> Dict:
    """Scansiona un singolo repo. Ritorna dict con status in {clean, violations, unscanned}.

    Failure-isolated: ogni errore per-repo → unscanned, non crash.
    """
    if not repo_path.exists():
        return {"status": "unscanned", "reason": "repo_not_found"}

    # Verifica che sia un repo git con toplevel proprio: la cartella di un submodule non
    # inizializzato e' vuota e git risalirebbe al repo padre (la factory).
    rc, top, _ = _git(["rev-parse", "--show-toplevel"], repo_path)
    if rc != 0:
        return {"status": "unscanned", "reason": "not_a_git_repo"}
    if Path(top.strip()).resolve() != repo_path.resolve():
        return {"status": "unscanned",
                "reason": "repo_not_initialized (cartella senza repo proprio)"}

    all_violations: List[Dict] = []

    # Commit da scansionare
    try:
        shas, fallback_reason = _get_commits_to_scan(repo_path)
    except Exception as exc:
        return {"status": "unscanned", "reason": f"git_error: {exc}"}

    # Check ogni commit (failure-isolated per commit)
    for sha in shas:
        try:
            v = _check_commit(sha, repo_path)
            all_violations.extend(v)
        except Exception:
            pass

    # Check staged diff (failure-isolated)
    try:
        staged_v = _check_staged(repo_path)
        all_violations.extend(staged_v)
    except Exception:
        pass

    if all_violations:
        return {
            "status": "violations",
            "violations": all_violations,
            "fallback_reason": fallback_reason,
            "commits_checked": len(shas),
        }

    return {
        "status": "clean",
        "fallback_reason": fallback_reason,
        "commits_checked": len(shas),
    }


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _format_compact(results: Dict[str, Dict]) -> str:
    """Output compatto per contesto --from-hook."""
    violation_repos = [r for r, d in results.items() if d.get("status") == "violations"]
    unscanned_repos = [r for r, d in results.items() if d.get("status") == "unscanned"]

    if violation_repos:
        lines = [f"[ai-policy] VIOLATIONS rilevate in: {', '.join(violation_repos)}"]
        for repo in violation_repos:
            for v in results[repo].get("violations", []):
                lines.append(
                    f"  {repo}@{v['commit_short']} [{v['where']}]: {v['matched'][:80]}"
                )
        return "\n".join(lines)

    if unscanned_repos:
        return f"[ai-policy] clean (attenzione: {len(unscanned_repos)} repo non scansionato/i)"

    return "[ai-policy] clean — nessuna attribution AI trovata."


def _format_full(results: Dict[str, Dict], timestamp: str, strict: bool = False) -> str:
    """Output integrale in chat (R.18 — mai compresso verso utente)."""
    clean = {r: d for r, d in results.items() if d.get("status") == "clean"}
    violations = {r: d for r, d in results.items() if d.get("status") == "violations"}
    unscanned = {r: d for r, d in results.items() if d.get("status") == "unscanned"}

    sep = "=" * 50
    thin = "-" * 50

    lines = [
        f"[ai-policy — snapshot @{timestamp}]",
        sep,
        "Primitiva: git log @{u}..HEAD + git diff --cached (zero push/fetch)",
        "",
        f"OK clean ({len(clean)}):",
    ]

    if clean:
        for repo, data in clean.items():
            n = data.get("commits_checked", 0)
            fb = (
                f"  [fallback: {data['fallback_reason']}]"
                if data.get("fallback_reason")
                else ""
            )
            lines.append(f"  {repo}    commits_checked: {n}{fb}")
    else:
        lines.append("  (nessuno)")

    lines.append("")
    lines.append(f"!! violations ({len(violations)}):")

    if violations:
        for repo, data in violations.items():
            n = data.get("commits_checked", 0)
            fb = (
                f"  [fallback: {data['fallback_reason']}]"
                if data.get("fallback_reason")
                else ""
            )
            lines.append(f"  {repo}    commits_checked: {n}{fb}")
            for v in data.get("violations", []):
                lines.append(
                    f"    [{v['commit_short']}] [{v['where']}] -> {v['matched'][:100]}"
                )
    else:
        lines.append("  (nessuna)")

    lines.append("")
    lines.append(f"? unscanned ({len(unscanned)}):")

    if unscanned:
        for repo, data in unscanned.items():
            lines.append(f"  {repo}    reason: {data.get('reason', 'unknown')}")
    else:
        lines.append("  (nessuno)")

    lines.append("")
    lines.append(thin)

    if violations:
        lines.append(
            "[ai-policy] ATTENZIONE: attribution AI o ID kanban factory trovati nel repo cliente. "
            "Rimuovere le tracce prima del push. Detective-only: nessuna auto-fix. (§ai_policy)"
        )
        lines.append(thin)

    if strict:
        if violations:
            lines.append("Modalita' --strict: GATE BLOCCANTE — exit 1 (violazioni presenti).")
        else:
            lines.append("Modalita' --strict: nessuna violazione — exit 0.")
    else:
        lines.append("Nessuna azione automatica eseguita. Check advisory — exit 0 sempre.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "§ai_policy audit check — detective scan attribution AI "
            "nei commit dei repo cliente (Layer-2 factory-native, advisory)."
        )
    )
    parser.add_argument(
        "--repos",
        type=str,
        default="",
        help=(
            "Repo da scansionare, separati da virgola, relativi alla factory root "
            "o path assoluti. Es: --repos=../client-repo,/abs/path/other-repo. "
            "Il repo della factory stessa e' rifiutato esplicitamente (guardia AC4)."
        ),
    )
    parser.add_argument(
        "--root",
        type=str,
        default="",
        help=(
            "Factory su cui operare (default: quella che contiene lo script). "
            "Base dei path relativi e fonte di ai_policy_check.scope[]. La guardia "
            "di scope rifiuta sia questa factory sia quella che contiene lo script."
        ),
    )
    parser.add_argument(
        "--from-hook",
        action="store_true",
        help="Output compatto (per contesto hook o embed in altri tool).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Gate bloccante: exit 1 se ci sono violazioni. Default: advisory (exit 0). "
            "Da usare al pre-push o in dev-handoff. NON usare in session-close o "
            "contesti non bloccanti."
        ),
    )
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Senza --root, da un worktree si usa il checkout principale: nel worktree le
    # cartelle dei submodule sono vuote e la guardia rifiuterebbe ogni target.
    root = Path(args.root).resolve() if args.root else _main_checkout(FACTORY_ROOT)
    factory_roots = [FACTORY_ROOT, root]

    # -----------------------------------------------------------------------
    # Determina repo da scansionare (precedenza: --repos > config scope)
    # -----------------------------------------------------------------------
    raw_paths: List[str] = []

    if args.repos:
        raw_paths = [r.strip() for r in args.repos.split(",") if r.strip()]

    if not raw_paths:
        raw_paths = _parse_config_scope(root)

    if not raw_paths:
        print(
            "[ai-policy] Nessun repo da scansionare "
            "(nessun --repos fornito, scope vuoto in ai_policy_check.scope[]). "
            "Configurare ai_policy_check.scope[] in factory.config.yaml con i path "
            "dei repo cliente da monitorare. Exit 0."
        )
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Risolvi i path e applica la guardia di scope (AC4)
    # -----------------------------------------------------------------------
    repo_paths: List[str] = []
    rejected: List[str] = []

    for raw in raw_paths:
        p = Path(raw)
        if not p.is_absolute():
            p = root / p

        if _is_factory_root(p, factory_roots):
            rejected.append(raw)
            print(_reject_factory_root(p), file=sys.stderr)
        else:
            repo_paths.append(raw)

    # Se tutti i target erano il factory root, usciamo prima del scan
    if not repo_paths and rejected:
        print(
            "[ai-policy] Tutti i target forniti sono stati rifiutati (guardia di scope). "
            "Aggiungere solo repo cliente a ai_policy_check.scope[]. Exit 0.",
            file=sys.stderr,
        )
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Scan (failure-isolated per repo)
    # -----------------------------------------------------------------------
    results: Dict[str, Dict] = {}

    for repo_rel in repo_paths:
        p = Path(repo_rel)
        repo_abs = p if p.is_absolute() else root / p
        try:
            results[repo_rel] = scan_repo(repo_abs)
        except Exception as exc:
            results[repo_rel] = {
                "status": "unscanned",
                "reason": f"unexpected_error: {exc}",
            }

    # -----------------------------------------------------------------------
    # Output
    # -----------------------------------------------------------------------
    if args.from_hook:
        print(_format_compact(results))
    else:
        print(_format_full(results, timestamp, strict=args.strict))

    # --strict: gate bloccante. Default: advisory.
    if args.strict:
        has_violations = any(d.get("status") == "violations" for d in results.values())
        sys.exit(1 if has_violations else 0)

    sys.exit(0)  # ADVISORY (default): exit 0 sempre, mai blocca il workflow


if __name__ == "__main__":
    main()
