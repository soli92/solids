#!/usr/bin/env python3
"""
close_lock.py — mutex mkdir-lock di /session-close (Fase 0-ter, Passi A, B, D).

Sostituisce lo pseudocodice bash della foglia
`.claude/skills/references/session-close-protocol/fase-0ter-detail.md`: stessa
semantica, eseguita dal codice invece che dal modello.

Uso:
  python3 tools/session/close_lock.py acquire [--operator OP] [--session-label L] [--json]
  python3 tools/session/close_lock.py release [--json]
  python3 tools/session/close_lock.py status  [--json]

Opzioni comuni: --root <factory_root> (default: CWD), --now <ISO8601> (test).

Semantica:
  - LOCK_DIR = <root>/.session-close.lock, con lock.json {locked_at, operator,
    session_label}. TTL = 10 minuti.
  - acquire: se LOCK_DIR esiste e locked_at e' oltre il TTL, il lock e' orfano:
    GC (messaggio su stderr) e prosegue. Se e' vivo: exit 1 (STOP-LOCK). La
    primitiva atomica e' os.mkdir: se fallisce in race, exit 1 (STOP-LOCK).
    Se lock.json manca o e' illeggibile, l'eta' si misura dall'mtime di LOCK_DIR.
  - release: idempotente. Rilasciare un lock gia' rilasciato esce 0.
  - status: sola lettura, esce 0 con lo stato nel JSON.

Exit: 0 riuscito; 1 lock vivo o race (STOP-LOCK); 2 errore di I/O o argomenti.
Risultato su stdout (JSON con --json), diagnostica su stderr.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claims as C  # noqa: E402
from session_id import resolve_session_id  # noqa: E402

LOCK_NAME = ".session-close.lock"
LOCK_FILE_NAME = "lock.json"
TTL_MINUTES = 10

EXIT_OK = 0
EXIT_LOCKED = 1
EXIT_ERROR = 2


def _now(raw: str | None) -> datetime:
    return C.parse_ts(raw) if raw else datetime.now(timezone.utc)


def _operator(root: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "config", "user.name"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _default_label(now: datetime) -> str:
    session_id, _ = resolve_session_id()
    return f"session-{now.strftime('%Y-%m-%d-%H')}-{session_id[:8]}"


def _emit(args, payload: dict, line: str) -> None:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(line)


def _read_lock(lock_dir: Path) -> dict:
    """Legge lock.json; ritorna {} se manca o non e' un JSON oggetto (nessun fail-open
    silenzioso: il chiamante ripiega sull'mtime di LOCK_DIR, che resta una misura valida)."""
    try:
        data = json.loads((lock_dir / LOCK_FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _inspect(lock_dir: Path, now: datetime) -> dict:
    """Stato del lock: exists, locked_at, age_minutes, orphan, e i campi di lock.json."""
    if not lock_dir.is_dir():
        return {"exists": False}
    info = _read_lock(lock_dir)
    locked_at = C.parse_ts(info.get("locked_at"))
    source = "lock.json"
    if locked_at is None:
        locked_at = datetime.fromtimestamp(lock_dir.stat().st_mtime, tz=timezone.utc)
        source = "mtime"
    age = (now - locked_at).total_seconds() / 60.0
    return {
        "exists": True,
        "locked_at": C.fmt_ts(locked_at),
        "locked_at_source": source,
        "age_minutes": round(age, 2),
        "ttl_minutes": TTL_MINUTES,
        "orphan": age > TTL_MINUTES,
        "operator": info.get("operator"),
        "session_label": info.get("session_label"),
    }


def cmd_acquire(args, lock_dir: Path) -> int:
    now = _now(args.now)
    state = _inspect(lock_dir, now)
    gc = None
    if state["exists"]:
        if not state["orphan"]:
            msg = (f"[session-close] Operazione gia' in corso "
                   f"(session_id: {state['session_label']}, avviata: {state['locked_at']}). "
                   f"Riprova tra qualche minuto o verifica che la sessione precedente "
                   f"sia completata.")
            print(msg, file=sys.stderr)
            _emit(args, {"status": "locked", "gate": "STOP-LOCK", "reason": "live", "lock": state},
                  "STOP-LOCK: lock vivo")
            return EXIT_LOCKED
        print(f"[session-close] Lock orphan rilevato (TTL scaduto: {state['locked_at']}). "
              f"GC automatico: rimosso {lock_dir}.", file=sys.stderr)
        shutil.rmtree(lock_dir)
        gc = {"removed": str(lock_dir), "locked_at": state["locked_at"],
              "session_label": state["session_label"]}
    try:
        os.mkdir(lock_dir)
    except FileExistsError:
        print("[session-close] Race condition rilevata: un altro agente ha acquisito "
              "il lock nell'intervallo di controllo. Riprova.", file=sys.stderr)
        _emit(args, {"status": "locked", "gate": "STOP-LOCK", "reason": "race"},
              "STOP-LOCK: race")
        return EXIT_LOCKED
    lock = {"locked_at": C.fmt_ts(now),
            "operator": args.operator or _operator(lock_dir.parent),
            "session_label": args.session_label or _default_label(now)}
    try:
        (lock_dir / LOCK_FILE_NAME).write_text(json.dumps(lock, ensure_ascii=False) + "\n",
                                               encoding="utf-8")
    except OSError:
        shutil.rmtree(lock_dir, ignore_errors=True)  # lock senza lock.json: non lasciarlo
        raise
    _emit(args, {"status": "acquired", "lock_dir": str(lock_dir), "lock": lock, "gc": gc},
          f"lock acquisito: {lock['session_label']}")
    return EXIT_OK


def cmd_release(args, lock_dir: Path) -> int:
    if not lock_dir.exists():
        _emit(args, {"status": "absent", "released": False}, "lock gia' rilasciato")
        return EXIT_OK
    shutil.rmtree(lock_dir)
    _emit(args, {"status": "released", "released": True}, "lock rilasciato")
    return EXIT_OK


def cmd_status(args, lock_dir: Path) -> int:
    state = _inspect(lock_dir, _now(args.now))
    if state["exists"]:
        text = (f"lock {'orfano' if state['orphan'] else 'vivo'}: {state['session_label']} "
                f"da {state['locked_at']} ({state['age_minutes']} min)")
    else:
        text = "nessun lock"
    _emit(args, {"status": "status", "lock": state}, text)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="close_lock.py",
                                description="Mutex mkdir-lock di /session-close.")
    p.add_argument("--root", default=".")
    p.add_argument("--now", help=argparse.SUPPRESS)
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("acquire")
    s.add_argument("--operator"); s.add_argument("--session-label", dest="session_label")
    sub.add_parser("release")
    sub.add_parser("status")

    # --json / --root / --now accettati anche dopo il sottocomando
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        sp.add_argument("--root", default=argparse.SUPPRESS)
        sp.add_argument("--now", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    args = p.parse_args(argv)
    if args.now and C.parse_ts(args.now) is None:
        print(f"[close_lock] --now non e' ISO8601: {args.now}", file=sys.stderr)
        return EXIT_ERROR
    lock_dir = Path(args.root).resolve() / LOCK_NAME
    try:
        return {"acquire": cmd_acquire, "release": cmd_release,
                "status": cmd_status}[args.cmd](args, lock_dir)
    except OSError as exc:
        print(f"[close_lock] errore di I/O su {lock_dir}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
