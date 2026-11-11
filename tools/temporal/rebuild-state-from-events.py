#!/usr/bin/env python3
"""
rebuild-state-from-events.py — Temporal State Machine rebuild da analytics events.
Cross-platform replacement per rebuild-state-from-events.sh (macOS / Linux / Windows).

Sources:
  ADR-028 §A  — schema state file + storage contract
  ADR-028 §B.2 — update_state_view_from_event algorithm
  ADR-028 §E  — migration & conflict policy
  ADR-030 §A  — UTC ISO-8601 Z timestamp format

CONTRATTO INPUT (CLI):
  --task-id <TSK-id>           obbligatorio
  --events-dir <path>          default "analytics/events"
  --output-dir <path>          default "management/state"
  --config <path>              default "factory.config.yaml"

Schema state file (management/state/<TSK-id>.json) — ADR-028 §A:
{
  "task_id": "TSK-XXX",
  "task_started_at": "YYYY-MM-DDTHH:MM:SSZ | null",
  "current_state": "pending|in_progress|completed|blocked",
  "history": [
    {
      "step_id": "<string>",
      "name": "<string>",
      "status": "pending|in_progress|completed|blocked",
      "started_at": "<UTC ISO-8601 Z | null>",
      "completed_at": "<UTC ISO-8601 Z | null>",
      "agent": "<string>",
      "notes": "<string | null>"
    }
  ]
}

EXIT CODES:
  0  rebuild completato
  1  --task-id mancante, config non trovata, o validazione prerequisiti fallita
"""
import sys
import json
import os
import glob
import re
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Helper: lettura flag YAML con regex (stdlib-only, senza PyYAML)
# ---------------------------------------------------------------------------

def _read_yaml_value(config_path: str, pattern: str, default: str = "") -> str:
    """Estrae un valore scalare da YAML con regex. Stdlib-only."""
    try:
        content = Path(config_path).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return default
    m = re.search(pattern, content, re.DOTALL)
    return m.group(1).strip() if m else default


# ---------------------------------------------------------------------------
# Rebuild core (ADR-028 §B.2 update_state_view_from_event)
# ---------------------------------------------------------------------------

def rebuild_state(task_id: str, events_dir: str, output_dir: str) -> None:
    """
    Legge tutti i file JSONL in events_dir, filtra per task_id,
    ricostruisce lo state file e lo scrive atomicamente in output_dir.
    Idempotente: run multipli producono lo stesso output (ADR-028 §B.2).
    """
    # --- Raccolta eventi da tutti i JSONL, filtrati per task_id ---
    events = []
    events_path = Path(events_dir)
    if events_path.is_dir():
        for jsonl_file in sorted(events_path.glob("*.jsonl")):
            try:
                with open(jsonl_file, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            ev = json.loads(line)
                            if ev.get("task_id") == task_id:
                                events.append(ev)
                        except json.JSONDecodeError:
                            pass
            except OSError:
                pass

    # --- Ordine cronologico (ADR-028 §B.2) ---
    events.sort(key=lambda e: e.get("timestamp", "") or "")

    # --- Inizializzazione state ---
    state = {
        "task_id": task_id,
        "task_started_at": None,
        "current_state": "pending",
        "history": [],
    }
    steps = {}  # step_id -> step dict (last-write-wins per field)

    for ev in events:
        # Primo timestamp diventa task_started_at
        if state["task_started_at"] is None and ev.get("timestamp"):
            state["task_started_at"] = ev["timestamp"]

        extras = ev.get("extras", {}) or {}
        step_id = extras.get("step_id")

        # ADR-028 §B.2: eventi senza step_id -> ignorati silenziosamente
        if not step_id:
            continue

        ev_status = extras.get("status") or "in_progress"
        ev_name = extras.get("name") or extras.get("step_name") or ""
        ev_agent = extras.get("agent") or ev.get("agent_id") or ""
        ev_notes = extras.get("notes")
        ev_started_at = extras.get("started_at") or (
            ev.get("timestamp") if ev_status == "in_progress" else None
        )
        ev_completed_at = extras.get("completed_at") or (
            ev.get("timestamp") if ev_status in ("completed", "blocked") else None
        )

        if step_id not in steps:
            steps[step_id] = {
                "step_id":      step_id,
                "name":         ev_name,
                "status":       ev_status,
                "started_at":   ev_started_at,
                "completed_at": ev_completed_at,
                "agent":        ev_agent,
                "notes":        ev_notes,
            }
        else:
            s = steps[step_id]
            if ev_name:
                s["name"] = ev_name
            s["status"] = ev_status
            if ev_started_at:
                s["started_at"] = ev_started_at
            if ev_completed_at:
                s["completed_at"] = ev_completed_at
            if ev_agent:
                s["agent"] = ev_agent
            if ev_notes is not None:
                s["notes"] = ev_notes

    state["history"] = list(steps.values())

    # --- Derivazione current_state da history (ADR-028 §B.2) ---
    statuses = [s["status"] for s in state["history"]]
    if "blocked" in statuses:
        state["current_state"] = "blocked"
    elif "in_progress" in statuses:
        state["current_state"] = "in_progress"
    elif statuses and all(s == "completed" for s in statuses):
        state["current_state"] = "completed"
    else:
        state["current_state"] = "pending"

    # --- Conflict detection (ADR-028 §E) ---
    output_path = Path(output_dir) / f"{task_id}.json"
    if output_path.exists():
        try:
            with open(output_path, encoding="utf-8") as f:
                existing = json.load(f)
            existing_ids = {s["step_id"] for s in existing.get("history", [])}
            rebuilt_ids = set(steps.keys())
            unreproducible = existing_ids - rebuilt_ids
            if unreproducible:
                print(
                    f"WARNING: State file esistente contiene transizioni non riproducibili da eventi "
                    f"per step(s): {sorted(unreproducible)}. "
                    f"Eseguire switch config prima del rebuild. Vedi ADR-028 §E.",
                    file=sys.stderr,
                )
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    # --- Scrittura atomica: tmp -> os.replace (ADR-028 §A, cross-platform) ---
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, output_path)
    print(f"State rebuilt: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Temporal State Machine rebuild da analytics events (ADR-028).",
        add_help=True,
    )
    parser.add_argument("--task-id", required=True, help="Task ID (es. TSK-XXX).")
    parser.add_argument("--events-dir", default="analytics/events",
                        help="Directory degli eventi JSONL (default: analytics/events).")
    parser.add_argument("--output-dir", default="management/state",
                        help="Directory output state JSON (default: management/state).")
    parser.add_argument("--config", default="factory.config.yaml",
                        help="Path a factory.config.yaml (default: factory.config.yaml).")
    args = parser.parse_args()

    # --- Prerequisiti: config esiste ---
    if not Path(args.config).exists():
        print(
            f"Error: config file '{args.config}' not found. Vedi ADR-028 §B.2.",
            file=sys.stderr,
        )
        return 1

    # --- Prerequisito: state_machine.source == "events" ---
    sm_source = _read_yaml_value(
        args.config,
        r"state_machine:\s*\n\s+source:\s*[\"']?(\w+)",
    )
    if sm_source != "events":
        print(
            "Error: temporal.state_machine.source deve essere 'events' per usare "
            "rebuild-state-from-events.sh.\n"
            f"  Attuale: '{sm_source or 'non configurato'}'. Vedi ADR-028 §B.2 e §G.",
            file=sys.stderr,
        )
        return 1

    # --- Prerequisito: analytics.measurement.enabled == "true" ---
    analytics_enabled = _read_yaml_value(
        args.config,
        r"measurement:\s*\n\s+enabled:\s*(true|false)",
        default="false",
    )
    if analytics_enabled != "true":
        print(
            "Error: analytics.measurement.enabled deve essere 'true' per usare "
            "rebuild-state-from-events.sh.\n"
            f"  Attuale: '{analytics_enabled or 'non configurato'}'. Vedi ADR-028 §B.2 e §G.",
            file=sys.stderr,
        )
        return 1

    # --- Rebuild ---
    rebuild_state(args.task_id, args.events_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
