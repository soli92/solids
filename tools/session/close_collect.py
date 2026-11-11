#!/usr/bin/env python3
"""
close_collect.py - raccolta iniziale di /session-close (Fase 0) in una busta JSON, in sola lettura.

Sostituisce i Bash separati con cui il modello raccoglie, all'inizio della chiusura, session id,
operatore, stato dirty di wiki/ e management/, stato del lock, conflicts su raw/sessions,
repo-align, ai-policy e cost-alert. Non scrive nulla: niente claim, niente lock acquire, niente
`gc`, niente harvest dei token, niente record di cost_alert. Quei passi restano nella skill.

La busta e' una proiezione delle regole scritte in `.claude/skills/session-close-protocol.md`
e nelle sue foglie: non decide, non ridefinisce soglie ne' testi di STOP. Ogni fonte riporta
`gate` (nome nella tabella dei gate della skill), `severity` (stop|advisory|info), `status`
e `source` (ancora sorgente). Per i gate di Fase 2/3 (`schema`, `sync_error`) lo status e'
`deferred`: non si raccolgono in Fase 0.

Uso:
  python3 tools/session/close_collect.py [--root <factory_root>] [--skip-dirty-check]
                                         [--timeout <secondi>]

  --root        radice della factory (default: CWD)
  --timeout     timeout di ogni subprocess in secondi (default: per fonte, 15-60)
  --skip-dirty-check  registra la richiesta di bypass in `dirty.data`; lo status non cambia

Status per fonte: ok | fail (condizione di STOP verificata) | attention (advisory da riportare)
| skipped (gate di config spento) | deferred | error | timeout.

Fonti richieste (se in `error`/`timeout` la busta e' incompleta): config, session, dirty, lock,
conflicts. Le fonti advisory opt-in (repo_align, ai_policy, cost_alert) in errore restano
`status: error` e sono elencate in `unavailable`, senza rendere la busta incompleta:
la skill dice per loro «non disponibile» e prosegue (MAI STOP).

`attention` e' sempre definito: lista, non vuota se `conflicts` ha elementi (advisory, da
riportare in chat).

Exit: 0 busta completa; 3 busta incompleta (`complete:false`, ERR-14, messaggio su stderr);
2 argomenti non validi. Risultato su stdout, diagnostica su stderr.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_id import resolve_session_id  # noqa: E402

SCHEMA = "close_collect/1"
MAX_BYTES = 32 * 1024
EXIT_OK = 0
EXIT_INCOMPLETE = 3

SKILL = ".claude/skills/session-close-protocol.md"
LEAF = ".claude/skills/references/session-close-protocol/"

# Sorgente per fonte: ancora `file#sezione` della skill o della foglia da cui il campo deriva.
# Ancore per titolo, non per numero di riga: non invecchiano quando la skill viene modificata.
SOURCES = {
    "config": [f"{SKILL}#Fase 0 passo 1"],
    "session": [f"{SKILL}#Fase 0 passo 2", f"{SKILL}#Fase 0 passo 4"],
    "dirty": [f"{SKILL}#Fase 0-bis A"],
    "lock": [f"{SKILL}#Fase 0-ter Passo A", f"{SKILL}#Fase 0-ter Passo B",
             f"{LEAF}fase-0ter-detail.md#Passo A"],
    "conflicts": [f"{SKILL}#Fase 0-ter Passo C", f"{LEAF}fase-0ter-detail.md#Passo C"],
    "repo_align": [f"{SKILL}#Fase 1-bis"],
    "ai_policy": [f"{SKILL}#Fase 1-ter"],
    "cost_alert": [f"{SKILL}#Fase 1 voce 1h"],
    "schema": [f"{SKILL}#Fase 2 gate schema"],
    "sync_error": [f"{SKILL}#Fase 3"],
}
GATES = {
    "config": ("STOP-CONFIG", "stop"),
    "session": (None, "info"),
    "dirty": ("STOP-DIRTY", "stop"),
    "lock": ("STOP-LOCK", "stop"),
    "schema": ("STOP-SCHEMA", "stop"),
    "sync_error": ("STOP-SYNC-ERROR", "stop"),
    "conflicts": ("ADV-CLAIM", "advisory"),
    "repo_align": ("ADV-REPO-ALIGN", "advisory"),
    "ai_policy": ("ADV-AI-POLICY", "advisory"),
    "cost_alert": ("ADV-COST-ALERT", "advisory"),
}
REQUIRED = ("config", "session", "dirty", "lock", "conflicts")
DEFAULT_TIMEOUT = {"repo_align": 60, "ai_policy": 30, "cost_alert": 30}
LOCAL_TIMEOUT = 15
LIST_CAP = 40
EXCERPT_CAP = 12


def _src(name: str, status: str, data=None, note: str | None = None, **extra) -> dict:
    gate, severity = GATES[name]
    rec = {"status": status, "severity": severity, "gate": gate, "source": SOURCES[name],
           "data": data if data is not None else {}}
    if note:
        rec["note"] = note
    rec.update(extra)
    return rec


def _run(cmd: list[str], cwd: Path, timeout: float) -> dict:
    """Esegue un comando in sola lettura. Ritorna {rc, out, err, timeout, error}: un timeout o un
    errore di avvio non sono mai un successo (il chiamante li rende `timeout`/`error`)."""
    started = time.monotonic()
    try:
        cp = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"rc": None, "out": "", "err": "", "timeout": True, "error": None,
                "cmd": cmd, "elapsed": time.monotonic() - started}
    except OSError as exc:
        return {"rc": None, "out": "", "err": "", "timeout": False, "error": str(exc),
                "cmd": cmd, "elapsed": time.monotonic() - started}
    return {"rc": cp.returncode, "out": cp.stdout, "err": cp.stderr, "timeout": False,
            "error": None, "cmd": cmd, "elapsed": time.monotonic() - started}


def _failure(name: str, res: dict, timeout: float) -> dict | None:
    """Record error/timeout se il comando non e' riuscito, altrimenti None."""
    cmd = " ".join("python3" if c == sys.executable else c for c in res["cmd"])[:120] or "?"
    if res["timeout"]:
        return _src(name, "timeout", note=f"timeout dopo {timeout:g}s: {cmd}",
                    timeout=True, timeout_s=timeout)
    if res["error"]:
        return _src(name, "error", note=f"{cmd}: {res['error']}")
    if res["rc"] != 0:
        tail = (res["err"] or res["out"]).strip().splitlines()[-1:] or [""]
        return _src(name, "error", note=f"{cmd}: exit {res['rc']}: {tail[0][:200]}")
    return None


def _json_out(name: str, res: dict) -> tuple[dict | None, dict | None]:
    try:
        data = json.loads(res["out"])
    except ValueError:
        return None, _src(name, "error", note=f"{name}: output non JSON")
    if not isinstance(data, dict):
        return None, _src(name, "error", note=f"{name}: JSON non oggetto")
    return data, None


# --- config (scanner di blocchi stdlib: PyYAML non e' garantito) -------------------------------

def _flag(text: str, block: str, key: str, sub: str | None = None):
    """Valore booleano di `block.[sub.]key` in un YAML a blocchi semplici; None se assente."""
    in_block = in_sub = False
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            in_block = line.startswith(block + ":")
            in_sub = False
            continue
        if not in_block:
            continue
        if sub and indent == 2:
            in_sub = line.strip().startswith(sub + ":")
            continue
        if (sub and in_sub and indent == 4) or (not sub and indent == 2):
            m = re.match(r"\s*" + re.escape(key) + r":\s*(\S+)", line)
            if m:
                return m.group(1).lower() == "true"
    return None


def _read_config(root: Path) -> tuple[str | None, str | None]:
    try:
        return (root / "factory.config.yaml").read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, f"factory.config.yaml illeggibile: {exc}"


def collect_config(text: str | None, err: str | None) -> dict:
    if text is None:
        return _src("config", "error", note=err)
    enabled = _flag(text, "session_close", "enabled")
    return _src("config", "ok" if enabled else "fail", {"session_close_enabled": bool(enabled)})


# --- fonti -------------------------------------------------------------------------------------

def collect_session(root: Path) -> dict:
    sid, source = resolve_session_id()
    res = _run(["git", "-C", str(root), "config", "user.name"], root, LOCAL_TIMEOUT)
    operator = (res["out"].strip() or "unknown") if res["rc"] == 0 else "unknown"
    now = datetime.now(timezone.utc)
    data = {"session_id": sid, "short": sid[:8], "id_source": source, "operator": operator,
            "date_hour_utc": now.strftime("%Y-%m-%d-%H"),
            "closed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    note = "session id generato: la chat non e' riconoscibile" if source == "generated" else None
    return _src("session", "ok", data, note)


def collect_dirty(root: Path, skip: bool, timeout: float) -> dict:
    res = _run(["git", "-C", str(root), "status", "--porcelain", "--", "wiki/", "management/"],
               root, timeout)
    bad = _failure("dirty", res, timeout)
    if bad:
        return bad
    files = [ln for ln in res["out"].splitlines() if ln.strip()]
    data = {"count": len(files), "files": files[:LIST_CAP], "truncated": len(files) > LIST_CAP,
            "skip_dirty_check_requested": skip}
    return _src("dirty", "fail" if files else "ok", data)


def collect_lock(root: Path, timeout: float) -> dict:
    res = _run([sys.executable, "tools/session/close_lock.py", "status", "--json",
                "--root", str(root)], root, timeout)
    bad = _failure("lock", res, timeout)
    if bad:
        return bad
    data, bad = _json_out("lock", res)
    if bad:
        return bad
    lock = data.get("lock") if isinstance(data.get("lock"), dict) else {}
    live = bool(lock.get("exists")) and not lock.get("orphan")
    return _src("lock", "fail" if live else "ok", lock,
                "istantanea precedente all'acquire: il gate resta close_lock.py acquire")


def collect_conflicts(root: Path, short: str, timeout: float) -> dict:
    res = _run([sys.executable, "tools/session/active_sessions.py", "conflicts", "--domain",
                "raw/sessions", "--uuid", short, "--json", "--root", str(root)], root, timeout)
    bad = _failure("conflicts", res, timeout)
    if bad:
        return bad
    data, bad = _json_out("conflicts", res)
    if bad:
        return bad
    found = data.get("conflicts")
    if not isinstance(found, list):
        return _src("conflicts", "error", note="conflicts: campo `conflicts` assente")
    return _src("conflicts", "attention" if found else "ok", {"conflicts": found})


def _gate_on(text: str | None, block: str) -> bool | None:
    if text is None:
        return None
    return bool(_flag(text, block, "enabled")) and bool(
        _flag(text, block, "on_session_close", "triggers"))


def collect_repo_align(root: Path, cfg: str | None, timeout: float) -> dict:
    if not _gate_on(cfg, "repo_align"):
        return _src("repo_align", "skipped", note="gate repo_align spento in factory.config.yaml")
    res = _run([sys.executable, "tools/vcs/repo-align.py", "--json"], root, timeout)
    bad = _failure("repo_align", res, timeout)
    if bad:
        return bad
    data, bad = _json_out("repo_align", res)
    if bad:
        return bad
    repos = data.get("repos") if isinstance(data.get("repos"), dict) else {}
    counts = {k: len(v) for k, v in repos.items() if isinstance(v, list)}
    detail = [{"name": r.get("name"), "verdict": r.get("verdict"), "reason": r.get("reason"),
               "direction": r.get("direction")}
              for k in ("diverged", "unverified") for r in repos.get(k, []) if isinstance(r, dict)]
    out = {"counts": counts, "not_aligned": detail[:LIST_CAP]}
    return _src("repo_align", "attention" if counts.get("diverged") else "ok", out)


def collect_ai_policy(root: Path, cfg: str | None, timeout: float) -> dict:
    if not _gate_on(cfg, "ai_policy_check"):
        return _src("ai_policy", "skipped", note="gate ai_policy_check spento in factory.config.yaml")
    res = _run([sys.executable, "tools/vcs/ai-policy-scan.py"], root, timeout)
    bad = _failure("ai_policy", res, timeout)
    if bad:
        return bad
    text = res["out"]
    m_v = re.search(r"violations \((\d+)\)", text)
    m_u = re.search(r"unscanned \((\d+)\)", text)
    if not (m_v and m_u):
        return _src("ai_policy", "error", note="ai-policy-scan: formato dell'output non riconosciuto")
    violations, unscanned = int(m_v.group(1)), int(m_u.group(1))
    excerpt = [ln.strip() for ln in text.splitlines()
               if re.match(r"\s+(\[|code_repos/)", ln) and "commits_checked" not in ln][:EXCERPT_CAP]
    data = {"violations": violations, "unscanned": unscanned, "excerpt": excerpt}
    return _src("ai_policy", "attention" if violations or unscanned else "ok", data)


def collect_cost_alert(root: Path, timeout: float) -> dict:
    # check senza --record: nessun record su disco; l'harvest dei token resta nella skill (1h).
    res = _run([sys.executable, "tools/analytics/cost_alert.py", "check", "--period", "all",
                "--json"], root, timeout)
    bad = _failure("cost_alert", res, timeout)
    if bad:
        return bad
    data, bad = _json_out("cost_alert", res)
    if bad:
        return bad
    results = [{k: r.get(k) for k in ("period", "action", "threshold_usd", "cost_usd", "breached")}
               for r in data.get("results", []) if isinstance(r, dict)]
    esc = data.get("escalations") if isinstance(data.get("escalations"), list) else []
    out = {"enabled": data.get("enabled"), "agent_enabled": data.get("agent_enabled"),
           "results": results, "escalations": len(esc), "notes": data.get("notes", [])}
    breached = any(r.get("breached") for r in results)
    return _src("cost_alert", "attention" if breached or esc else "ok", out)


# --- busta -------------------------------------------------------------------------------------

def _shrink(env: dict) -> None:
    """Riduce le liste della busta finche' non rientra nel limite (ordine: dal meno al piu' utile)."""
    s = env["sources"]
    for path in (("ai_policy", "excerpt"), ("dirty", "files"), ("repo_align", "not_aligned"),
                 ("conflicts", "conflicts")):
        items = s[path[0]]["data"].get(path[1])
        if isinstance(items, list) and len(items) > 3:
            s[path[0]]["data"][path[1]] = items[:3]
            s[path[0]]["data"]["truncated"] = True
        if len(_dump(env)) <= MAX_BYTES:
            return


def _dump(env: dict) -> str:
    return json.dumps(env, ensure_ascii=False, separators=(",", ":"))


def build(root: Path, skip_dirty: bool, timeout: float | None) -> dict:
    def tmo(name: str) -> float:
        return timeout if timeout is not None else DEFAULT_TIMEOUT.get(name, LOCAL_TIMEOUT)

    cfg_text, cfg_err = _read_config(root)
    sources: dict[str, dict] = {"config": collect_config(cfg_text, cfg_err)}
    sources["session"] = collect_session(root)
    short = sources["session"]["data"].get("short", "")
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {
            "dirty": pool.submit(collect_dirty, root, skip_dirty, tmo("dirty")),
            "lock": pool.submit(collect_lock, root, tmo("lock")),
            "conflicts": pool.submit(collect_conflicts, root, short, tmo("conflicts")),
            "repo_align": pool.submit(collect_repo_align, root, cfg_text, tmo("repo_align")),
            "ai_policy": pool.submit(collect_ai_policy, root, cfg_text, tmo("ai_policy")),
            "cost_alert": pool.submit(collect_cost_alert, root, tmo("cost_alert")),
        }
        for name, fut in futs.items():
            sources[name] = fut.result()
    sources["schema"] = _src("schema", "deferred", note="gate di Fase 2: non raccoglibile in Fase 0")
    sources["sync_error"] = _src("sync_error", "deferred",
                                 note="gate di Fase 3: non raccoglibile in Fase 0")
    ordered = {k: sources[k] for k in GATES}

    bad = [k for k in REQUIRED if ordered[k]["status"] in ("error", "timeout")]
    conflicts = ordered["conflicts"]["data"].get("conflicts") or []
    attention = [f"conflitto su raw/sessions: sessione {c.get('uuid')} ({c.get('operator')}, "
                 f"agent {c.get('agent')}): {c.get('reason')}" for c in conflicts]
    env = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": str(root),
        "complete": not bad,
        "incomplete_sources": bad,
        "unavailable": [k for k, v in ordered.items()
                        if k not in REQUIRED and v["status"] in ("error", "timeout")],
        "attention": attention,
        "sources": ordered,
    }
    if len(_dump(env)) > MAX_BYTES:
        _shrink(env)
    if len(_dump(env)) > MAX_BYTES:
        env["complete"] = False
        env["incomplete_sources"] = bad + ["size"]
    return env


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="close_collect.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--root", default=".")
    p.add_argument("--skip-dirty-check", action="store_true")
    p.add_argument("--timeout", type=float, default=None)
    args = p.parse_args(argv)
    if args.timeout is not None and args.timeout <= 0:
        p.error("--timeout deve essere > 0")
    root = Path(args.root).resolve()
    env = build(root, args.skip_dirty_check, args.timeout)
    sys.stdout.write(_dump(env) + "\n")
    if not env["complete"]:
        detail = [f"{k}={env['sources'][k]['status']}" + (f" ({env['sources'][k].get('note')})"
                  if k in env["sources"] and env["sources"][k].get("note") else "")
                  for k in env["incomplete_sources"] if k in env["sources"]]
        print("[close_collect] busta incompleta (complete:false): "
              + ("; ".join(detail) or ", ".join(env["incomplete_sources"]))
              + ". Fermarsi e riportare in chat.", file=sys.stderr)
        return EXIT_INCOMPLETE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
