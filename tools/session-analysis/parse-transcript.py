#!/usr/bin/env python3
"""
parse-transcript.py — EP-061/US-243/TSK-551
Fan-in main+subagent JSONL transcripts, normalize each assistant record to
a structured JSON object for downstream anomaly analysis (fleet-metrics.py,
detect-anomalies.py).

CLI:
  python3 parse-transcript.py <session-path>
          [--subagents-path <dir>]
          [--output <file>]
          [--evidence-max-chars N]

Invariants:
  R-SAA-3 redaction:
    - Never include tool_result content (assistant records only; user msgs skipped)
    - Path anonymization: /Users/<name>/ → /Users/USER/ in all string values
    - Credential strip: sk-*, Bearer *, *_TOKEN=*, .env paths → [REDACTED]
    - Evidence cap: strings > evidence-max-chars truncated with [TRUNCATED]
  R-SAA-8 out-of-band gate:
    - sys.exit(2) if session_id == CLAUDE_SESSION_ID env var (euristica 1)
    - sys.exit(2) if main JSONL mtime < 60s ago (euristica 2)
  Fail-open:
    - Malformed JSONL lines: skip + aggregate warning counter
    - Missing subagent files: skip silently (backward compat)
  Deduplication: by record uuid (avoid double-count if record appears in both
    main and subagent files)
  stdlib-only: json, pathlib, sys, argparse, re, os, time, datetime, importlib.util

Output format:
  {
    "meta": { session_id, cc_version, schema_degraded, subagent_files_found,
              records_total, records_skipped_malformed, redaction_applied, generated_at },
    "records": [ { session_id, attribution, agent_hash, attribution_agent,
                   model, usage, elapsed_ms, stop_reason, tool_calls, timestamp,
                   schema_version } ]
  }
"""

import sys
import json
import argparse
import pathlib
import re
import os
import time
import datetime
import importlib.util

# ── Optional reuse of harvest-session-tokens.py ───────────────────────────────
# We import via importlib because the filename contains hyphens, which makes it
# invalid as a Python module identifier. Fail-open: if import fails, inline
# fallbacks below handle all needed functionality.
HERE = pathlib.Path(__file__).resolve().parent
_HARVEST_PATH = HERE.parent / "analytics" / "harvest-session-tokens.py"
_harvest_mod = None

if _HARVEST_PATH.exists():
    try:
        _spec = importlib.util.spec_from_file_location("_harvest_session_tokens", _HARVEST_PATH)
        _harvest_mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_harvest_mod)
    except Exception:
        pass  # fail-open — inline fallbacks will be used


# ── R-SAA-3 redaction ─────────────────────────────────────────────────────────
# Match /Users/<anything-not-slash-or-space>/ paths for anonymization.
_PATH_RE = re.compile(r"/Users/[^/\s]+/")

# Match known credential patterns for removal.
_CRED_RE = re.compile(
    r"(sk-[A-Za-z0-9-]+|Bearer\s+[A-Za-z0-9._-]+|[A-Z_]{2,}_TOKEN=[^\s&\"']*|\.env(?=[\s/\"']|$))"
)


def _redact_str(s, max_chars):
    """Apply R-SAA-3 redaction to a single string value.

    1. Anonymize absolute user paths.
    2. Remove credential-shaped tokens.
    3. Cap length at max_chars with [TRUNCATED] marker.
    """
    if not isinstance(s, str):
        return s
    s = _PATH_RE.sub("/Users/USER/", s)
    s = _CRED_RE.sub("[REDACTED]", s)
    if len(s) > max_chars:
        s = s[:max_chars] + "[TRUNCATED]"
    return s


def _redact_value(v, max_chars):
    """Recursively apply R-SAA-3 redaction to any JSON-compatible value."""
    if isinstance(v, str):
        return _redact_str(v, max_chars)
    if isinstance(v, dict):
        return {k: _redact_value(val, max_chars) for k, val in v.items()}
    if isinstance(v, list):
        return [_redact_value(item, max_chars) for item in v]
    return v  # int, float, bool, None — pass through unchanged


# ── CC version detection ──────────────────────────────────────────────────────

def _detect_cc_version(transcript_path):
    """Return CC version string from first JSONL record with a 'version' field.

    Delegates to harvest_mod when available; falls back to inline implementation.
    Returns None on any failure (fail-open).
    """
    if _harvest_mod is not None:
        try:
            return _harvest_mod.detect_cc_version(transcript_path)
        except Exception:
            pass  # fall through to inline

    # Inline fallback: read until first record with 'version' field.
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                v = d.get("version")
                if v is not None:
                    return str(v)
    except OSError:
        pass
    return None


# ── Fan-in file collection ────────────────────────────────────────────────────

def _collect_files(transcript, subagents_override):
    """Return list of (pathlib.Path, force_scope) for the fan-in.

    - transcript is the main JSONL pathlib.Path.
    - subagents_override: explicit subagents directory path (str or None).
    - force_scope == "subagent" for subagent files, None for the main file.

    Auto-discovery (when subagents_override is None):
      CC 2.1.258+ structure:
        <session-uuid>.jsonl              ← main
        <session-uuid>/subagents/agent-*.jsonl  ← sub

    Delegates to harvest_mod.collect_jsonl_files when available and no override
    is requested. Inline fallback mirrors harvest-session-tokens.py logic.

    Fail-open: absent subagents/ directory is silently ignored.
    """
    if subagents_override is None and _harvest_mod is not None:
        try:
            return _harvest_mod.collect_jsonl_files(str(transcript))
        except Exception:
            pass  # fall through to inline

    # Inline fallback / override path
    files = [(transcript, None)]  # main transcript

    if subagents_override is not None:
        sub_dir = pathlib.Path(subagents_override)
    else:
        # Auto-discovery: <parent>/<stem>/subagents/
        sub_dir = transcript.parent / transcript.stem / "subagents"

    if sub_dir.exists():
        for p in sorted(sub_dir.glob("agent-*.jsonl")):
            files.append((p, "subagent"))

    return files


# ── Timestamp helpers ─────────────────────────────────────────────────────────

def _ts_to_ms(ts):
    """Parse ISO8601 timestamp string to epoch milliseconds. Returns None on failure."""
    if not ts:
        return None
    try:
        t = ts.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(t)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError, AttributeError):
        return None


# ── R-SAA-8 out-of-band gate ──────────────────────────────────────────────────

def _check_session_open(transcript):
    """Return (is_open, mtime_delta_seconds).

    Euristica 1 (env var): session_id == CLAUDE_SESSION_ID.
    Euristica 2 (mtime): main JSONL mtime < 60 seconds ago.
    Either condition independently triggers is_open=True.
    """
    session_id = transcript.stem
    mtime_delta = None

    try:
        mtime_delta = time.time() - transcript.stat().st_mtime
    except OSError:
        pass

    # Euristica 1
    env_sid = os.environ.get("CLAUDE_SESSION_ID")
    if env_sid and env_sid == session_id:
        return True, mtime_delta

    # Euristica 2
    if mtime_delta is not None and mtime_delta < 60:
        return True, mtime_delta

    return False, mtime_delta


# ── Record normalization ──────────────────────────────────────────────────────

def _extract_tool_calls(content):
    """Extract tool_calls summary from message.content.

    R-SAA-3: only tool_use items are inspected; tool_result items are NEVER
    included in output (we skip all non-assistant records, so tool_result
    content in user messages is naturally excluded). The is_error field is set
    to None for tool_use items since the error state is only known from the
    subsequent user message (which we do not process).
    """
    calls = []
    if not isinstance(content, list):
        return calls
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "tool_use":
            calls.append({
                "name": item.get("name"),
                "is_error": None,  # unknown at assistant-message time
            })
    return calls


def _normalize_record(record, attribution, agent_hash, session_id,
                      schema_version, prev_ts_ms, max_chars):
    """Normalize one parsed JSONL dict into a structured record.

    Returns the normalized dict, or None if the record should be skipped.
    Only records of type 'assistant' are processed; all others are skipped silently.
    """
    if record.get("type") != "assistant":
        return None  # skip user, attachment, queue-operation, etc.

    msg = record.get("message") or {}
    if not msg:
        return None  # degenerate assistant record with no message

    # Usage tokens
    usage_raw = msg.get("usage") or {}
    usage = {
        "input":       int(usage_raw.get("input_tokens", 0) or 0),
        "output":      int(usage_raw.get("output_tokens", 0) or 0),
        "cache_read":  int(usage_raw.get("cache_read_input_tokens", 0) or 0),
        "cache_write": int(usage_raw.get("cache_creation_input_tokens", 0) or 0),
    }

    # Timestamp and elapsed
    ts = record.get("timestamp") or None
    ts_ms = _ts_to_ms(ts)
    elapsed_ms = (ts_ms - prev_ts_ms) if (ts_ms is not None and prev_ts_ms is not None) else None

    # Tool calls summary (R-SAA-3: content of tool_result never included)
    tool_calls = _extract_tool_calls(msg.get("content") or [])

    rec = {
        "session_id":        session_id,
        "attribution":       attribution,
        "agent_hash":        agent_hash,
        "attribution_agent": record.get("attributionAgent") or None,
        "model":             msg.get("model") or None,
        "usage":             usage,
        "elapsed_ms":        elapsed_ms,
        "stop_reason":       msg.get("stop_reason") or None,
        "tool_calls":        tool_calls,
        "timestamp":         ts,
        "schema_version":    schema_version,
    }

    # R-SAA-3: apply full redaction to all string values in the normalized record.
    return _redact_value(rec, max_chars)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=(
            "parse-transcript.py — fan-in Claude Code JSONL (main + subagents), "
            "normalize to structured JSON for anomaly analysis. "
            "EP-061/US-243/TSK-551."
        )
    )
    ap.add_argument(
        "session_path",
        help="Path to the main session JSONL file.",
    )
    ap.add_argument(
        "--subagents-path",
        default=None,
        metavar="DIR",
        help=(
            "Override the subagents/ directory for fan-in. "
            "Auto-discovery is used when omitted (mirrors harvest-session-tokens.py)."
        ),
    )
    ap.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Write JSON output to FILE instead of stdout.",
    )
    ap.add_argument(
        "--evidence-max-chars",
        type=int,
        default=200,
        metavar="N",
        help="Maximum characters for evidence string snippets before [TRUNCATED] (default: 200).",
    )
    args = ap.parse_args()

    transcript = pathlib.Path(args.session_path)
    if not transcript.exists():
        print(f"ERROR: session file not found: {args.session_path}", file=sys.stderr)
        return 1

    session_id = transcript.stem

    # ── R-SAA-8: gate — reject if session still open ──
    is_open, mtime_delta = _check_session_open(transcript)
    if is_open:
        delta_str = f"{mtime_delta:.1f}s" if mtime_delta is not None else "unknown"
        print(
            f"ERROR: session appears still open (R-SAA-8 violated). "
            f"Analyse closed sessions only. "
            f"Session id: {session_id}, mtime delta: {delta_str}",
            file=sys.stderr,
        )
        return 2

    # ── CC version detection (schema guard) ──
    schema_version = _detect_cc_version(str(transcript))
    schema_degraded = schema_version is None
    if schema_degraded:
        print(
            "WARNING: CC version not found in transcript; schema_degraded=true",
            file=sys.stderr,
        )

    # ── Fan-in: collect all JSONL files ──
    files = _collect_files(transcript, args.subagents_path)
    n_subagent_files = sum(1 for (_, scope) in files if scope == "subagent")

    # ── Parse and normalize records ──
    records = []
    seen_uuids = set()
    skipped_malformed = 0
    # Track last timestamp per attribution channel for elapsed_ms computation.
    prev_ts_ms_by_attr = {}  # attribution -> last ts_ms seen

    for (fpath, force_scope) in files:
        # Determine attribution and agent_hash from file position in the fan-in.
        if force_scope == "subagent":
            attribution = "subagent"
            # Extract hash from "agent-<hash>.jsonl"
            stem = fpath.stem
            agent_hash = stem[len("agent-"):] if stem.startswith("agent-") else stem
        else:
            # Main transcript file (force_scope == None)
            attribution = "main"
            agent_hash = None

        try:
            fh = open(fpath, encoding="utf-8")
        except OSError:
            # fail-open: subagent file missing or unreadable — skip silently.
            continue

        with fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue

                try:
                    d = json.loads(raw_line)
                except json.JSONDecodeError:
                    skipped_malformed += 1
                    continue

                # Deduplication by uuid
                uid = d.get("uuid")
                if uid:
                    if uid in seen_uuids:
                        continue
                    seen_uuids.add(uid)

                prev_ms = prev_ts_ms_by_attr.get(attribution)
                rec = _normalize_record(
                    d,
                    attribution,
                    agent_hash,
                    session_id,
                    schema_version,
                    prev_ms,
                    args.evidence_max_chars,
                )
                if rec is None:
                    continue  # non-assistant record — skip

                # Update elapsed tracking for next record of same attribution.
                ts_ms = _ts_to_ms(rec.get("timestamp"))
                if ts_ms is not None:
                    prev_ts_ms_by_attr[attribution] = ts_ms

                records.append(rec)

    # Aggregate malformed warning at end (fail-open pattern from EP-062).
    if skipped_malformed > 0:
        print(
            f"WARNING: {skipped_malformed} malformed JSONL line(s) skipped across all files.",
            file=sys.stderr,
        )

    # ── Build output ──
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = {
        "meta": {
            "session_id":               session_id,
            "cc_version":               schema_version,
            "schema_degraded":          schema_degraded,
            "subagent_files_found":     n_subagent_files,
            "records_total":            len(records),
            "records_skipped_malformed": skipped_malformed,
            "redaction_applied":        ["path", "credentials", "truncate"],
            "generated_at":             now_iso,
        },
        "records": records,
    }

    json_str = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        out_path = pathlib.Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"Output written to: {out_path}", file=sys.stderr)
    else:
        print(json_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
