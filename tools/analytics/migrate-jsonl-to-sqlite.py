#!/usr/bin/env python3
"""
migrate-jsonl-to-sqlite.py — promozione store JSONL → SQLite (EP-009, US-033, TSK-059)

Cross-platform Python rewrite of migrate-jsonl-to-sqlite.sh.
Stdlib-only: json, sqlite3, pathlib, argparse, sys.

CONTRATTO INPUT (CLI)
  --events-dir <path>     default "analytics/events" (relativo al repo root)
  --db <path>             default "analytics/events.db"

CONTRATTO OUTPUT (stdout, JSON puro)
  {"status":"ok","db":"analytics/events.db","inserted":N,"skipped":M,"files":K}
  {"status":"error","error":"<message>"}

EXIT CODES  0 success | >0 error (dir assente, ecc.)

Idempotente: dedup su (ts, task_id) — righe già presenti vengono saltate.

ADR-021 §B — schema SQLite tabella `events`.
ADR-023 §A — stdout=JSON / stderr=log, exit code semantico, stateless.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve repo root: script is at .claude/tools/analytics/migrate-jsonl-to-sqlite.py
# → parent.parent.parent.parent = repo root
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # tools/analytics/ → root factory (2 livelli)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytics_cli import ContractArgumentParser  # noqa: E402 — contratto CLI comune (US-327)


_DDL = """
CREATE TABLE IF NOT EXISTS events (
  rowid               INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id             TEXT    NOT NULL,
  project_id          TEXT    NOT NULL,
  parent_id           TEXT,
  actor_type          TEXT    NOT NULL,
  actor_id            TEXT    NOT NULL,
  task_type           TEXT    NOT NULL,
  state               TEXT    NOT NULL,
  ts                  TEXT    NOT NULL,
  model               TEXT,
  tokens_input        INTEGER DEFAULT 0,
  tokens_output       INTEGER DEFAULT 0,
  tokens_cache_read   INTEGER DEFAULT 0,
  tokens_cache_write  INTEGER DEFAULT 0,
  tokens_cache_write_1h INTEGER DEFAULT 0,
  tool_calls          TEXT,
  extras              TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_task         ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_project_ts   ON events(project_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_task_type_ts ON events(task_type, ts);
"""

_CHECK_SQL = "SELECT COUNT(*) FROM events WHERE ts = ? AND task_id = ?"

_INSERT_SQL = """
INSERT INTO events
  (task_id, project_id, parent_id, actor_type, actor_id, task_type, state, ts,
   model, tokens_input, tokens_output, tokens_cache_read, tokens_cache_write,
   tokens_cache_write_1h, tool_calls, extras)
VALUES
  (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _ensure_cache_write_1h(con: sqlite3.Connection) -> None:
    """DB creati prima della colonna tokens_cache_write_1h: la aggiunge (default 0)."""
    cols = {row[1] for row in con.execute("PRAGMA table_info(events)")}
    if "tokens_cache_write_1h" not in cols:
        con.execute("ALTER TABLE events ADD COLUMN tokens_cache_write_1h INTEGER DEFAULT 0")


def _err(msg: str) -> None:
    """Emit JSON error to stdout and log to stderr."""
    print(json.dumps({"status": "error", "error": msg}), flush=True)
    print(f"migrate-jsonl-to-sqlite: ERROR — {msg}", file=sys.stderr)


def _resolve(path_str: str) -> Path:
    """Resolve a path: if relative, root it at REPO_ROOT."""
    p = Path(path_str)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p


def _migrate(events_dir: Path, db_path: Path) -> None:
    if not events_dir.is_dir():
        _err("events dir not found")
        sys.exit(1)

    # Ensure parent directory for the DB exists.
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(_DDL)
        _ensure_cache_write_1h(con)
        con.commit()

        inserted = 0
        skipped = 0
        files = 0

        jsonl_files = sorted(events_dir.glob("*.jsonl"))
        for f in jsonl_files:
            files += 1
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError as exc:
                print(
                    f"migrate-jsonl-to-sqlite: WARN — cannot read {f}: {exc}",
                    file=sys.stderr,
                )
                continue

            for raw_line in lines:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue

                # Malformed JSON → skip defensively (no fail-loud on entire migration).
                try:
                    rec = json.loads(raw_line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue

                task_id = rec.get("task_id") or ""
                ts = rec.get("ts") or ""
                if not task_id or not ts:
                    skipped += 1
                    continue

                # Idempotent dedup by (ts, task_id).
                cur = con.execute(_CHECK_SQL, (ts, task_id))
                if (cur.fetchone()[0] or 0) > 0:
                    skipped += 1
                    continue

                tokens = rec.get("tokens") or {}
                tool_calls_raw = rec.get("tool_calls")
                extras_raw = rec.get("extras")

                con.execute(
                    _INSERT_SQL,
                    (
                        task_id,
                        rec.get("project_id") or "",
                        rec.get("parent_id") or None,
                        rec.get("actor_type") or "",
                        rec.get("actor_id") or "",
                        rec.get("task_type") or "",
                        rec.get("state") or "",
                        ts,
                        rec.get("model") or None,
                        int(tokens.get("input") or 0),
                        int(tokens.get("output") or 0),
                        int(tokens.get("cache_read") or 0),
                        int(tokens.get("cache_write") or 0),
                        int(tokens.get("cache_write_1h") or 0),
                        json.dumps(tool_calls_raw) if tool_calls_raw is not None else None,
                        json.dumps(extras_raw) if extras_raw is not None else None,
                    ),
                )
                inserted += 1

        con.commit()
    finally:
        con.close()

    # Relative DB path for the output JSON (mirrors the .sh behaviour).
    try:
        rel_db = str(db_path.relative_to(REPO_ROOT))
    except ValueError:
        rel_db = str(db_path)

    print(
        f"migrate-jsonl-to-sqlite: {inserted} inseriti, {skipped} saltati,"
        f" {files} file processati → {rel_db}.",
        file=sys.stderr,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "db": rel_db,
                "inserted": inserted,
                "skipped": skipped,
                "files": files,
            }
        ),
        flush=True,
    )


def main() -> None:
    parser = ContractArgumentParser(
        prog="migrate-jsonl-to-sqlite.py",
        description="Promote JSONL event store → SQLite (EP-009, ADR-021).",
    )
    parser.add_argument(
        "--events-dir",
        default="analytics/events",
        metavar="PATH",
        help='Source directory of *.jsonl files (default: "analytics/events").',
    )
    parser.add_argument(
        "--db",
        default="analytics/events.db",
        metavar="PATH",
        help='Destination SQLite database (default: "analytics/events.db").',
    )
    args = parser.parse_args()

    events_dir = _resolve(args.events_dir)
    db_path = _resolve(args.db)

    try:
        _migrate(events_dir, db_path)
    except Exception as exc:  # noqa: BLE001
        _err(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
