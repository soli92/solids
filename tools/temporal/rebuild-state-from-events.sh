#!/usr/bin/env bash
# rebuild-state-from-events.sh — Temporal State Machine rebuild from analytics events
# Sources:
#   ADR-028 §A  — schema state file + storage contract
#   ADR-028 §B.2 — update_state_view_from_event algorithm
#   ADR-028 §E  — migration & conflict policy
#   ADR-030 §A  — UTC ISO-8601 Z timestamp format
#
# Usage:
#   bash .claude/tools/temporal/rebuild-state-from-events.sh \
#     --task-id TSK-XXX \
#     [--events-dir analytics/events] \
#     [--output-dir management/state] \
#     [--config factory.config.yaml]
#
# Schema state file (management/state/<TSK-id>.json) — ADR-028 §A:
# {
#   "task_id": "TSK-XXX",
#   "task_started_at": "YYYY-MM-DDTHH:MM:SSZ | null",
#   "current_state": "pending|in_progress|completed|blocked",
#   "history": [
#     {
#       "step_id": "<string>",
#       "name": "<string>",
#       "status": "pending|in_progress|completed|blocked",
#       "started_at": "<UTC ISO-8601 Z | null>",
#       "completed_at": "<UTC ISO-8601 Z | null>",
#       "agent": "<string>",
#       "notes": "<string | null>"
#     }
#   ]
# }

set -euo pipefail

TASK_ID=""
EVENTS_DIR="analytics/events"
OUTPUT_DIR="management/state"
CONFIG_FILE="factory.config.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id)    TASK_ID="$2";    shift 2 ;;
    --events-dir) EVENTS_DIR="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --config)     CONFIG_FILE="$2"; shift 2 ;;
    *) echo "Error: unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$TASK_ID" ]]; then
  echo "Error: --task-id is required. Usage: bash $0 --task-id TSK-XXX" >&2
  exit 1
fi

# --- Validate prerequisites (ADR-028 §B.2 + §G) ---
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Error: config file '$CONFIG_FILE' not found. Vedi ADR-028 §B.2." >&2
  exit 1
fi

SM_SOURCE=$(python3 - "$CONFIG_FILE" << 'PY'
import sys, re
config_file = sys.argv[1]
with open(config_file) as f:
    content = f.read()
m = re.search(r'state_machine:\s*\n\s+source:\s*["\']?(\w+)', content)
print(m.group(1) if m else "")
PY
)

ANALYTICS_ENABLED=$(python3 - "$CONFIG_FILE" << 'PY'
import sys, re
config_file = sys.argv[1]
with open(config_file) as f:
    content = f.read()
m = re.search(r'measurement:\s*\n\s+enabled:\s*(true|false)', content)
print(m.group(1) if m else "false")
PY
)

if [[ "$SM_SOURCE" != "events" ]]; then
  echo "Error: temporal.state_machine.source deve essere 'events' per usare rebuild-state-from-events.sh." >&2
  echo "  Attuale: '${SM_SOURCE:-non configurato}'. Vedi ADR-028 §B.2 e §G." >&2
  exit 1
fi

if [[ "$ANALYTICS_ENABLED" != "true" ]]; then
  echo "Error: analytics.measurement.enabled deve essere 'true' per usare rebuild-state-from-events.sh." >&2
  echo "  Attuale: '${ANALYTICS_ENABLED:-non configurato}'. Vedi ADR-028 §B.2 e §G." >&2
  exit 1
fi

# --- Rebuild state from events (ADR-028 §B.2 update_state_view_from_event) ---
export _RSE_TASK_ID="$TASK_ID"
export _RSE_OUTPUT_DIR="$OUTPUT_DIR"
export _RSE_EVENTS_DIR="$EVENTS_DIR"

python3 << 'PYTHON_EOF'
import sys, json, os, glob

task_id    = os.environ["_RSE_TASK_ID"]
output_dir = os.environ["_RSE_OUTPUT_DIR"]
events_dir = os.environ["_RSE_EVENTS_DIR"]

# Collect events from all JSONL files, filter by task_id
events = []
if os.path.isdir(events_dir):
    for jsonl_file in sorted(glob.glob(os.path.join(events_dir, "*.jsonl"))):
        try:
            with open(jsonl_file, encoding="utf-8") as f:
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

# Sort by timestamp (ADR-028 §B.2: process in chronological order)
events.sort(key=lambda e: e.get("timestamp", "") or "")

# Initialize state
state = {
    "task_id": task_id,
    "task_started_at": None,
    "current_state": "pending",
    "history": []
}
steps = {}  # step_id → step dict (idempotent: last-write-wins per field)

for ev in events:
    # Capture first timestamp as task_started_at
    if state["task_started_at"] is None and ev.get("timestamp"):
        state["task_started_at"] = ev["timestamp"]

    extras = ev.get("extras", {}) or {}
    step_id = extras.get("step_id")

    # ADR-028 §B.2: events without step_id → silently ignored
    if not step_id:
        continue

    ev_status       = extras.get("status") or "in_progress"
    ev_name         = extras.get("name") or extras.get("step_name") or ""
    ev_agent        = extras.get("agent") or ev.get("agent_id") or ""
    ev_notes        = extras.get("notes")
    ev_started_at   = extras.get("started_at") or (
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
        if ev_name:         s["name"]         = ev_name
        s["status"]                           = ev_status
        if ev_started_at:   s["started_at"]   = ev_started_at
        if ev_completed_at: s["completed_at"] = ev_completed_at
        if ev_agent:        s["agent"]        = ev_agent
        if ev_notes is not None: s["notes"]   = ev_notes

state["history"] = list(steps.values())

# Derive current_state from history (ADR-028 §B.2)
statuses = [s["status"] for s in state["history"]]
if "blocked" in statuses:
    state["current_state"] = "blocked"
elif "in_progress" in statuses:
    state["current_state"] = "in_progress"
elif statuses and all(s == "completed" for s in statuses):
    state["current_state"] = "completed"
else:
    state["current_state"] = "pending"

# Conflict detection (ADR-028 §E)
output_path = os.path.join(output_dir, f"{task_id}.json")
if os.path.exists(output_path):
    try:
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
        existing_ids   = {s["step_id"] for s in existing.get("history", [])}
        rebuilt_ids    = set(steps.keys())
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

# Atomic write: temp file + os.replace (ADR-028 §A idempotence guarantee)
os.makedirs(output_dir, exist_ok=True)
tmp_path = output_path + ".tmp"
with open(tmp_path, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
    f.write("\n")
os.replace(tmp_path, output_path)
print(f"State rebuilt: {output_path}")
PYTHON_EOF
