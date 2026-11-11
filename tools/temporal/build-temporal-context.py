#!/usr/bin/env python3
"""
build-temporal-context.py — Temporal Context Injection per system prompt degli agenti.
Cross-platform replacement per build-temporal-context.sh (macOS / Linux / Windows).

PATTERN §3 (Temporal Context Injection) + ADR-030 §A §E + ADR-031 §B.
Wiki: [[temporal-awareness-multiagent-patterns]] §Pattern 1
      [[temporal-awareness-llm]] §Knowledge cutoff

No-op (exit 0, nessun output) quando i flag temporal sono disabilitati (R.P3).

CONTRATTO INPUT (CLI):
  --config <path>              default "factory.config.yaml"
  --task-started-at <UTC-ts>   obbligatorio; formato YYYY-MM-DDTHH:MM:SS[.sss]Z
  --session-id <uuid4>         obbligatorio; formato UUID v4

OUTPUT (stdout, solo se temporal.context_injection.enabled=true):
  # Temporal Context (UTC ISO-8601)
  current_datetime: <YYYY-MM-DDTHH:MM:SSZ>
  task_started_at: <input>
  session_id: <input>

EXIT CODES:
  0  contesto emesso OR no-op (flag spento)
  1  argomento obbligatorio mancante o formato invalido
"""
import sys
import re
import argparse
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helper: lettura flag YAML senza PyYAML (solo stdlib + regex)
# ---------------------------------------------------------------------------

def _read_flag(config_path: str, pattern: str, default: str = "false") -> str:
    """Estrae un valore scalare booleano da YAML con regex. Stdlib-only."""
    try:
        content = Path(config_path).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return default
    m = re.search(pattern, content, re.MULTILINE)
    return m.group(1) if m else default


# ---------------------------------------------------------------------------
# Helper: timestamp UTC corrente
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    """Timestamp UTC nel formato ADR-030 §A (secondi)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Validazione formati (ADR-030 §A, ADR-031 §B)
# ---------------------------------------------------------------------------

_ISO8601_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$"
)
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _is_iso8601_utc(ts: str) -> bool:
    return bool(_ISO8601_UTC_RE.match(ts))


def _is_uuid4(s: str) -> bool:
    return bool(_UUID4_RE.match(s))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Temporal Context Injection — ADR-030 §A §E + ADR-031 §B.",
        add_help=True,
    )
    parser.add_argument("--config", default="factory.config.yaml",
                        help="Path a factory.config.yaml (default: factory.config.yaml).")
    parser.add_argument("--task-started-at", default="",
                        dest="task_started_at",
                        help="Timestamp UTC ISO-8601 Z di inizio task (obbligatorio).")
    parser.add_argument("--session-id", default="",
                        dest="session_id",
                        help="UUID v4 della sessione corrente (obbligatorio).")
    args = parser.parse_args()

    # --- Gate 1: temporal.enabled ---
    temporal_enabled = _read_flag(
        args.config,
        r"^temporal:\s*\n(?:[ \t]+[^\n]*\n|[ \t]*\n)*?[ \t]+enabled:\s*(true|false)",
    )
    if temporal_enabled != "true":
        return 0  # no-op silenzioso (R.P3)

    # --- Gate 2: temporal.context_injection.enabled ---
    ci_enabled = _read_flag(
        args.config,
        r"context_injection:\s*\n(?:[ \t]+[^\n]*\n|[ \t]*\n)*?[ \t]+enabled:\s*(true|false)",
    )
    if ci_enabled != "true":
        return 0  # no-op silenzioso (R.P3)

    # --- Validazione --task-started-at ---
    if not args.task_started_at:
        print(
            "build-temporal-context.sh: --task-started-at is required.",
            file=sys.stderr,
        )
        return 1
    if not _is_iso8601_utc(args.task_started_at):
        print(
            "build-temporal-context.sh: task_started_at non in formato UTC ISO-8601 con Z. "
            "Vedi ADR-030 §A.",
            file=sys.stderr,
        )
        return 1

    # --- Validazione --session-id ---
    if not args.session_id:
        print(
            "build-temporal-context.sh: --session-id is required.",
            file=sys.stderr,
        )
        return 1
    if not _is_uuid4(args.session_id):
        print(
            "build-temporal-context.sh: session-id non in formato UUID v4. "
            "Atteso: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.",
            file=sys.stderr,
        )
        return 1

    # --- Emissione del blocco context (ADR-030 §A) ---
    current_datetime = _utc_now()
    print("# Temporal Context (UTC ISO-8601)")
    print(f"current_datetime: {current_datetime}")
    print(f"task_started_at: {args.task_started_at}")
    print(f"session_id: {args.session_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
