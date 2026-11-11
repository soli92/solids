#!/usr/bin/env python3
"""
record-event.py — tool deterministico record_task_event (EP-009, US-033, TSK-059)
Cross-platform Python replacement per record-event.sh (macOS / Linux / Windows).

Invarianti di contratto identiche alla versione bash:
  - stesso CLI (--event, --config)
  - stesso formato stdout JSON
  - stessi exit code (0 ok/no-op, 1 schema/PII, 3 write error)
  - stessa idempotency (sha256 hash, ADR-039 §C)
  - advisory lock cross-platform (fcntl su Unix, best-effort su Windows)
  - nessuna dipendenza esterna (stdlib: json, hashlib, sqlite3, re, pathlib)

ADR-021 — store JSONL append-only + SQLite opt-in
ADR-039  — lock advisory, idempotency, fail-open/fail-loud
ADR-040  — PII boundary enforcement

EXIT CODES:
  0  evento registrato, no-op (capability spenta), idempotency hit, lock timeout
  1  schema invalido, PII violation, prerequisito mancante
  3  write error (disk full / permission)
"""
from __future__ import annotations  # union syntax (X | Y) su Python 3.9+
import sys
import json
import re
import os
import hashlib
import sqlite3
import argparse
import time
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Risoluzione root del repo (lo script è invocabile da qualunque cwd)
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent          # tools/analytics/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # tools/analytics/ → root factory (2 livelli)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytics_cli import ContractArgumentParser  # noqa: E402 — contratto CLI comune (US-327)



def _worktree_main_root(default: Path) -> Path:
    """Worktree-aware (TSK-408 Fix B, parita' con record-event.sh).

    In un worktree secondario `git --git-common-dir` punta (path assoluto) al .git del
    repo principale, mentre `--git-dir` punta a .git/worktrees/<id>. In quel caso la root
    e' dirname(--git-common-dir): gli eventi finiscono in analytics/events/ del repo
    principale, non in quella (eventualmente assente) del worktree.
    """
    import subprocess as _sp
    try:
        common = _sp.run(["git", "-C", str(HERE), "rev-parse", "--git-common-dir"],
                         capture_output=True, text=True, timeout=120).stdout.strip()
        gitdir = _sp.run(["git", "-C", str(HERE), "rev-parse", "--git-dir"],
                         capture_output=True, text=True, timeout=120).stdout.strip()
    except (OSError, _sp.SubprocessError):
        return default
    if common and gitdir and common != gitdir and os.path.isabs(common):
        return Path(os.path.dirname(common))
    return default


REPO_ROOT = _worktree_main_root(REPO_ROOT)

# ---------------------------------------------------------------------------
# Locking cross-platform
# ---------------------------------------------------------------------------

try:
    import fcntl as _fcntl
    _HAS_FCNTL = True
except ImportError:
    _fcntl = None  # type: ignore[assignment]
    _HAS_FCNTL = False  # Windows


class _FileLock:
    """Advisory file lock cross-platform.

    Unix (Linux + macOS): fcntl.flock() esclusivo non-bloccante + polling.
    Windows: creazione esclusiva con O_CREAT|O_EXCL + polling (best-effort).
    Fallback automatico se né fcntl né O_EXCL disponibili → lock gracefully degradato.
    """

    def __init__(self, lock_path: Path, timeout: float = 5.0) -> None:
        self._path = lock_path
        self._timeout = timeout
        self._fd: int | None = None
        self._spin_owned = False  # usato dal percorso Windows

    def acquire(self) -> bool:
        """Acquisisce il lock. Ritorna True se acquisito, False se timeout."""
        deadline = time.monotonic() + self._timeout

        if _HAS_FCNTL:
            # --- Unix: flock esclusivo non-bloccante + polling ---
            try:
                self._path.touch(exist_ok=True)
                self._fd = os.open(str(self._path), os.O_WRONLY)
                while True:
                    try:
                        _fcntl.flock(self._fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)  # type: ignore[attr-defined]
                        return True
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            os.close(self._fd)
                            self._fd = None
                            return False
                        time.sleep(0.05)
            except OSError:
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except OSError:
                        pass
                    self._fd = None
                # Degradazione graceful se flock fallisce (es. FS non supportato)
                return True
        else:
            # --- Windows: spin-lock con creazione esclusiva ---
            spin_file = self._path.with_suffix(".spin")
            while time.monotonic() < deadline:
                try:
                    fd = os.open(str(spin_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(fd, str(os.getpid()).encode())
                    os.close(fd)
                    self._spin_owned = True
                    return True
                except FileExistsError:
                    # Rimuovi lock stale (più vecchio di 2× timeout)
                    try:
                        if time.monotonic() - spin_file.stat().st_mtime > self._timeout * 2:
                            spin_file.unlink(missing_ok=True)
                            continue
                    except OSError:
                        pass
                    time.sleep(0.05)
            return False

    def release(self) -> None:
        """Rilascia il lock."""
        if _HAS_FCNTL and self._fd is not None:
            try:
                _fcntl.flock(self._fd, _fcntl.LOCK_UN)  # type: ignore[attr-defined]
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        elif self._spin_owned:
            spin_file = self._path.with_suffix(".spin")
            spin_file.unlink(missing_ok=True)
            self._spin_owned = False

    def __enter__(self) -> "_FileLock":
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


# ---------------------------------------------------------------------------
# Helper: lettura flag YAML (regex, stdlib-only)
# ---------------------------------------------------------------------------

def _yaml_block_value(config_path: str, block: str, key: str) -> str:
    """
    Estrae il valore di <key> dentro il blocco <block>: nel YAML, usando
    solo regex. Ritorna "" se assente o config non trovata.
    """
    try:
        content = Path(config_path).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return ""

    # Trova il blocco di primo livello
    idx = content.find(f"{block}:")
    if idx == -1:
        return ""

    snippet = content[idx + len(f"{block}:"):]
    for line in snippet.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Nuova chiave top-level → usciti dal blocco
        if re.match(r"^[A-Za-z_]", line):
            break
        m = re.match(rf"\s+{re.escape(key)}\s*:\s*[\"']?([^\n\"'#\s]+)", line)
        if m:
            return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Validazione schema evento (ADR-021 §E + ADR-042)
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = [
    "task_id", "project_id", "actor_type", "actor_id",
    "task_type", "state", "ts", "tokens", "model", "tool_calls",
]
_VALID_ACTOR_TYPES = {"agent", "human"}
_VALID_STATES = {
    "started", "finished", "blocked", "aborted",
    "wave_started", "wave_completed", "sub_agent_dispatched",
}
_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
_TOKEN_SUBFIELDS = ["input", "output", "cache_read", "cache_write"]


def _validate_schema(event: dict) -> str | None:
    """Valida l'evento contro lo schema. Ritorna messaggio di errore o None se ok."""
    # 4.1 Campi obbligatori
    for f in _REQUIRED_FIELDS:
        if f not in event:
            return f"missing required field: {f}"

    # 4.2 task_id e project_id non vuoti
    for f in ("task_id", "project_id"):
        v = event.get(f)
        if not v or v == "null":
            return f"missing required field: {f}"

    # 4.3 actor_type
    if event.get("actor_type") not in _VALID_ACTOR_TYPES:
        return f"invalid actor_type: '{event.get('actor_type')}' (allowed: agent|human)"

    # 4.4 state
    if event.get("state") not in _VALID_STATES:
        # ordine dello .sh, non alfabetico: il messaggio e' parte del contratto
        allowed = "started|finished|blocked|aborted|wave_started|wave_completed|sub_agent_dispatched"
        return f"invalid state: '{event.get('state')}' (allowed: {allowed})"

    # 4.5 ts ISO-8601
    ts = event.get("ts", "")
    if not _ISO8601_RE.match(str(ts)):
        return f"invalid ts (not ISO-8601): '{ts}'"

    # 4.6 tokens è oggetto con i 4 sub-campi
    tokens = event.get("tokens")
    if not isinstance(tokens, dict):
        return "tokens must be an object with input/output/cache_read/cache_write"
    for sub in _TOKEN_SUBFIELDS:
        if sub not in tokens:
            return f"missing tokens sub-field: {sub}"

    # 4.7 tool_calls è array
    if not isinstance(event.get("tool_calls"), list):
        return "tool_calls must be an array (may be empty)"

    return None  # OK


# ---------------------------------------------------------------------------
# PII boundary enforcement (ADR-040 §C)
# ---------------------------------------------------------------------------

_ALLOWED_KEYS = {
    "ts", "state", "task_id", "project_id", "actor_id", "actor_type",
    "task_type", "elapsed_ms", "tokens", "model", "tool_calls", "parent_id",
    "extras", "wave_id", "wave_size", "wave_elapsed_ms", "success_count",
    "failure_count", "candidates", "aborted_reason", "blocked_reason",
    "blocking_artifacts", "hash", "dispatch_ts", "completion_ts",
}
_TEXT_FIELDS = ("aborted_reason", "blocked_reason")
_BLOCKED_PATTERNS = [
    re.compile(r'"[A-Z_]+_KEY"\s*:\s*"[^"]+"'),         # API key fingerprint
    re.compile(r'"[A-Z_]+_TOKEN"\s*:\s*"[^"]+"'),        # token fingerprint
    re.compile(r'"password"\s*:\s*"[^"]+"'),              # password
    re.compile(r'"api_key"\s*:\s*"[^"]+"'),               # api_key
    re.compile(r'"prompt"\s*:\s*"[^"]+"'),                # prompt content
    re.compile(r'"system"\s*:\s*"[^"]+"'),                # system prompt
    re.compile(r"BEGIN [A-Z ]+PRIVATE KEY"),              # PEM keys
    re.compile(r"[0-9a-fA-F]{32,}"),                     # potenziali hash segreti
]
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _check_pii(event: dict) -> str | None:
    """Controlla i boundary PII. Ritorna messaggio di violazione o None se ok."""
    event_str = json.dumps(event)

    # 4.8 Allowlist chiavi top-level
    for key in event.keys():
        if key not in _ALLOWED_KEYS:
            return f"key '{key}' not in allowlist (ADR-040 §A)"

    # 4.9 Free-text >200 char
    for field in _TEXT_FIELDS:
        val = event.get(field, "") or ""
        if len(str(val)) > 200:
            return (
                f"field '{field}' length {len(str(val))} > 200 char "
                f"(ADR-040 §B cat 7 free-text)"
            )

    # 4.10 Pattern blocklist
    for pat in _BLOCKED_PATTERNS:
        if pat.search(event_str):
            return f"pattern matches blocklist (ADR-040 §B): /{pat.pattern}/"

    # 4.11 Email fuori da actor_id
    email_matches = _EMAIL_RE.findall(event_str)
    if email_matches:
        actor_id = str(event.get("actor_id", ""))
        actor_has_email = "@" in actor_id
        total_emails = len(email_matches)
        if not actor_has_email or total_emails != 1:
            return "email pattern detected outside actor_id (ADR-040 §B cat 6)"

    return None  # OK


# ---------------------------------------------------------------------------
# Idempotency hash (ADR-039 §C §G)
# ---------------------------------------------------------------------------

def _compute_hash(task_id: str, state: str, ts: str) -> str:
    """sha256(task_id|state|ts)[0:16] — 64 bit di entropia."""
    raw = f"{task_id}|{state}|{ts}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Dispatch JSONL (ADR-021 §A, ADR-039)
# ---------------------------------------------------------------------------

def _dispatch_jsonl(
    event: dict,
    repo_root: Path,
    lock_timeout: float,
) -> tuple[int, dict]:
    """
    Scrive l'evento nel file JSONL mensile con lock advisory e idempotency check.
    Ritorna (exit_code, output_dict).
    """
    ts = event.get("ts", "")
    yyyy_mm = ts[:7]  # YYYY-MM
    task_id = event.get("task_id", "")
    state = event.get("state", "")
    event_id = f"{ts}-{task_id}"

    events_dir = repo_root / "analytics" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    target = events_dir / f"{yyyy_mm}.jsonl"
    rel_target = f"analytics/events/{yyyy_mm}.jsonl"
    lock_file = events_dir / ".lock"

    # --- Idempotency hash ---
    hash_val = _compute_hash(task_id, state, ts)

    # --- Acquisisci lock advisory ---
    lock = _FileLock(lock_file, timeout=lock_timeout)
    acquired = lock.acquire()
    if not acquired:
        # fail-open (ADR-039 §D caso B): timeout lock → skip silenzioso
        print(
            f"[analytics-write-fail] lock timeout after {lock_timeout:.0f}s — "
            "skipping event write (fail-open, ADR-039 §D)",
            file=sys.stderr,
        )
        return 0, {
            "status": "skipped",
            "reason": "lock_timeout",
            "event_id": event_id,
        }

    with lock:
        # --- Idempotency check pre-write (sotto lock, ADR-039 §C) ---
        try:
            if target.exists() and f'"hash":"{hash_val}"' in target.read_text(encoding="utf-8", errors="replace"):
                print(
                    f"record_task_event: evento {hash_val} già presente "
                    "(idempotent, no-op, ADR-039 §C).",
                    file=sys.stderr,
                )
                return 0, {
                    "status": "ok",
                    "path": rel_target,
                    "event_id": event_id,
                    "idempotent": True,
                }
        except OSError:
            pass

        # --- Append con hash embedded (ADR-039 §C) ---
        payload = {**event, "hash": hash_val}
        # compatto come `jq -c`: il controllo d'idempotenza cerca `"hash":"<h>"` senza spazi
        oneline = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        try:
            with open(target, "a", encoding="utf-8") as f:
                f.write(oneline + "\n")
        except OSError as exc:
            print(
                f"[analytics-write-fail] write error su {rel_target} "
                f"(disk full / permission?): {exc} — evento perso (ADR-039 §D caso C)",
                file=sys.stderr,
            )
            return 3, {"status": "error", "error": f"write error: {rel_target}"}

    print(
        f"record_task_event: evento {event_id} appeso a {rel_target} "
        f"(store=jsonl, hash={hash_val}).",
        file=sys.stderr,
    )
    return 0, {"status": "ok", "path": rel_target, "event_id": event_id}


# ---------------------------------------------------------------------------
# Dispatch SQLite (ADR-021 §B)
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS events (
  rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id     TEXT    NOT NULL,
  project_id  TEXT    NOT NULL,
  parent_id   TEXT,
  actor_type  TEXT    NOT NULL CHECK(actor_type IN ('agent', 'human')),
  actor_id    TEXT    NOT NULL,
  task_type   TEXT    NOT NULL,
  state       TEXT    NOT NULL,
  ts          TEXT    NOT NULL,
  model       TEXT,
  tokens_input        INTEGER DEFAULT 0,
  tokens_output       INTEGER DEFAULT 0,
  tokens_cache_read   INTEGER DEFAULT 0,
  tokens_cache_write  INTEGER DEFAULT 0,
  tokens_cache_write_1h INTEGER DEFAULT 0,
  tool_calls  TEXT,
  extras      TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_project_ts ON events(project_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_task_type_ts ON events(task_type, ts);
"""


def _ensure_cache_write_1h(con: sqlite3.Connection) -> None:
    """DB creati prima della colonna tokens_cache_write_1h: la aggiunge (default 0)."""
    cols = {row[1] for row in con.execute("PRAGMA table_info(events)")}
    if "tokens_cache_write_1h" not in cols:
        con.execute("ALTER TABLE events ADD COLUMN tokens_cache_write_1h INTEGER DEFAULT 0")


def _dispatch_sqlite(event: dict, repo_root: Path) -> tuple[int, dict]:
    """Inserisce l'evento nel DB SQLite (ADR-021 §B)."""
    db_path = repo_root / "analytics" / "events.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rel_db = "analytics/events.db"

    ts = event.get("ts", "")
    task_id = event.get("task_id", "")
    event_id = f"{ts}-{task_id}"
    tokens: dict = event.get("tokens", {})

    try:
        con = sqlite3.connect(str(db_path))
        con.executescript(_DDL)
        _ensure_cache_write_1h(con)
        con.execute(
            """
            INSERT INTO events
              (task_id, project_id, parent_id, actor_type, actor_id, task_type,
               state, ts, model, tokens_input, tokens_output, tokens_cache_read,
               tokens_cache_write, tokens_cache_write_1h, tool_calls, extras)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                event.get("project_id", ""),
                event.get("parent_id") or "",
                event.get("actor_type", ""),
                event.get("actor_id", ""),
                event.get("task_type", ""),
                event.get("state", ""),
                ts,
                event.get("model") or "",
                int(tokens.get("input", 0) or 0),
                int(tokens.get("output", 0) or 0),
                int(tokens.get("cache_read", 0) or 0),
                int(tokens.get("cache_write", 0) or 0),
                int(tokens.get("cache_write_1h", 0) or 0),
                json.dumps(event.get("tool_calls", []), ensure_ascii=False),
                json.dumps(event.get("extras") or None, ensure_ascii=False),
            ),
        )
        con.commit()
        con.close()
    except sqlite3.Error as exc:
        print(
            f"[analytics-write-fail] SQLite error: {exc}",
            file=sys.stderr,
        )
        return 3, {"status": "error", "error": str(exc)}

    print(
        f"record_task_event: evento {event_id} inserito in {rel_db} (store=sqlite).",
        file=sys.stderr,
    )
    return 0, {"status": "ok", "path": rel_db, "event_id": event_id}


# ---------------------------------------------------------------------------
# Temporal State Machine hook (opt-in v2.18+, ADR-028 §B.2)
# ---------------------------------------------------------------------------

def _temporal_sm_hook(event: dict, config_path: str, repo_root: Path) -> None:
    """
    Invocato dopo ogni dispatch riuscito (exit 0).
    Gate triplo → no-op quando flag spento (R.P3).
    Delega a rebuild-state-from-events.py (ADR-028 §B.2 idempotente).
    """
    # Gate 1: temporal.enabled
    tm_enabled = _yaml_block_value(config_path, "temporal", "enabled")
    if tm_enabled != "true":
        return

    # Gate 2: temporal.state_machine.enabled
    sm_enabled = _yaml_block_value(config_path, "state_machine", "enabled")
    if sm_enabled != "true":
        return

    # Gate 3: temporal.state_machine.source == "events"
    sm_source = _yaml_block_value(config_path, "state_machine", "source")
    if sm_source != "events":
        return

    # Verifica step_id in extras (ADR-028 §B.2)
    task_id = event.get("task_id", "")
    extras = event.get("extras", {}) or {}
    step_id = extras.get("step_id", "")
    if not step_id:
        print(
            f"WARNING: Evento per TSK temporal-aware {task_id} senza step_id in extras. "
            "State view non aggiornata. Vedi ADR-028 §B.2.",
            file=sys.stderr,
        )
        return

    # Leggi state_file_path dalla config (default management/state)
    try:
        content = Path(config_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"state_file_path:\s*[\"']?([^\n\"'#]+)", content)
        sm_path = m.group(1).strip() if m else "management/state"
    except OSError:
        sm_path = "management/state"

    # Invoca rebuild-state-from-events.py nella stessa directory di questo script
    # oppure nella posizione mirror tools/temporal/
    import subprocess as _sp
    rebuild_candidates = [
        HERE.parent / "temporal" / "rebuild-state-from-events.py",  # da analytics/
        HERE / "rebuild-state-from-events.py",                       # se stesso percorso
    ]
    rebuild_script = next((p for p in rebuild_candidates if p.exists()), None)
    if rebuild_script is None:
        print(
            "WARNING: rebuild-state-from-events.py non trovato. "
            "State view non aggiornata. Vedi ADR-028 §B.2.",
            file=sys.stderr,
        )
        return

    try:
        _sp.run(
            [
                sys.executable, str(rebuild_script),
                "--task-id", task_id,
                "--events-dir", str(repo_root / "analytics" / "events"),
                "--output-dir", str(repo_root / sm_path),
                "--config", config_path,
            ],
            timeout=30,
        )
    except Exception as exc:
        print(
            f"WARNING: rebuild-state-from-events.py fallito: {exc}. "
            "Vedi ADR-028 §B.2.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = ContractArgumentParser(
        description="record_task_event — ADR-021, ADR-039, ADR-040.",
        add_help=True,
    )
    parser.add_argument(
        "--event",
        help="Evento JSON da registrare (schema ADR-021 §E + ADR-042).",
    )
    parser.add_argument(
        "--config",
        default="factory.config.yaml",
        help="Path a factory.config.yaml (default: factory.config.yaml).",
    )
    args = parser.parse_args()
    if args.event is None:
        print("ERRORE: --event è obbligatorio. Uso: record-event.py --event '<JSON>' [--config <path>]",
              file=sys.stderr)
        print(json.dumps({"status": "error", "error": "missing required argument: --event"}))
        sys.exit(1)

    # Normalizza config a path assoluto
    config_path = str(
        (REPO_ROOT / args.config).resolve()
        if not Path(args.config).is_absolute()
        else Path(args.config).resolve()
    )

    # ---------------------------------------------------------------------------
    # 3. Master switch — no-op se capability spenta (R.P3, ADR-021 §F)
    # ---------------------------------------------------------------------------
    measurement_enabled = _yaml_block_value(config_path, "analytics", "enabled")
    # Fallback: cerca measurement.enabled direttamente
    if measurement_enabled != "true":
        try:
            content = Path(config_path).read_text(encoding="utf-8", errors="replace")
            m = re.search(r"measurement:\s*\n\s+enabled:\s*(true|false)", content)
            if m:
                measurement_enabled = m.group(1)
        except OSError:
            pass
    if measurement_enabled != "true":
        print(
            "record_task_event: analytics.measurement.enabled non è true "
            "(no-op, R.P3).",
            file=sys.stderr,
        )
        return 0

    # ---------------------------------------------------------------------------
    # Store type
    # ---------------------------------------------------------------------------
    store = _yaml_block_value(config_path, "measurement", "store") or "jsonl"
    if store not in ("jsonl", "sqlite"):
        err = f"invalid store: {store}"
        print(f"ERRORE: analytics.measurement.store deve essere 'jsonl' o 'sqlite' "
              f"(trovato: '{store}'). Vedi ADR-021 §C.", file=sys.stderr)
        print(json.dumps({"status": "error", "error": err}))
        return 1

    # ---------------------------------------------------------------------------
    # 4. Parsing e validazione JSON evento
    # ---------------------------------------------------------------------------
    try:
        event = json.loads(args.event)
    except json.JSONDecodeError as exc:
        err = "invalid JSON payload"
        print(f"ERRORE schema evento: {err} ({exc})", file=sys.stderr)
        print(json.dumps({"status": "error", "error": err}))
        return 1

    schema_err = _validate_schema(event)
    if schema_err:
        print(f"ERRORE schema evento: {schema_err}", file=sys.stderr)
        print(json.dumps({"status": "error", "error": schema_err}))
        return 1

    # ---------------------------------------------------------------------------
    # 4.8-4.11 PII boundary enforcement (ADR-040 §C) — fail-loud
    # ---------------------------------------------------------------------------
    pii_err = _check_pii(event)
    if pii_err:
        print(f"ERRORE PII boundary: {pii_err}", file=sys.stderr)
        print(json.dumps({"status": "error", "error": f"PII boundary violation: {pii_err}"}))
        return 1

    # ---------------------------------------------------------------------------
    # 6. Dispatch store
    # ---------------------------------------------------------------------------
    lock_timeout = float(os.environ.get("ANALYTICS_LOCK_TIMEOUT_SECONDS", "5"))

    if store == "jsonl":
        exit_code, output = _dispatch_jsonl(event, REPO_ROOT, lock_timeout)
    else:
        exit_code, output = _dispatch_sqlite(event, REPO_ROOT)

    print(json.dumps(output))

    # ---------------------------------------------------------------------------
    # 7. Temporal SM hook (post-dispatch, solo se exit 0)
    # ---------------------------------------------------------------------------
    if exit_code == 0 and output.get("status") == "ok":
        _temporal_sm_hook(event, config_path, REPO_ROOT)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
