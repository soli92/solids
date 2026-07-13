#!/usr/bin/env bash
# Temporal Context Injection — builds the context block for agent system prompts.
# PATTERN §3 (Temporal Context Injection) + ADR-030 §A §E + ADR-031 §B.
# Wiki: [[temporal-awareness-multiagent-patterns]] §Pattern 1
#       [[temporal-awareness-llm]] §Knowledge cutoff
#
# No-op (exit 0, no output) when temporal flags are disabled (R.P3).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG="factory.config.yaml"
TASK_STARTED_AT=""
SESSION_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config=*)          CONFIG="${1#--config=}"; shift ;;
    --config)            CONFIG="$2"; shift 2 ;;
    --task-started-at=*) TASK_STARTED_AT="${1#--task-started-at=}"; shift ;;
    --task-started-at)   TASK_STARTED_AT="$2"; shift 2 ;;
    --session-id=*)      SESSION_ID="${1#--session-id=}"; shift ;;
    --session-id)        SESSION_ID="$2"; shift 2 ;;
    *) echo "build-temporal-context.sh: unknown argument: $1" >&2; exit 1 ;;
  esac
done

# Read opt-in flags via python3 (R.P3: no-op when disabled)
TEMPORAL_ENABLED="$(python3 - "${CONFIG}" <<'PYEOF'
import sys, re

config_path = sys.argv[1] if len(sys.argv) > 1 else "factory.config.yaml"
try:
    with open(config_path) as f:
        content = f.read()
except (FileNotFoundError, IOError):
    print("false"); sys.exit(0)

# Extract temporal.enabled (simple regexp, avoids PyYAML dependency)
m = re.search(r'^temporal:\s*\n(?:[ \t]+[^\n]*\n)*?[ \t]+enabled:\s*(true|false)', content, re.MULTILINE)
print(m.group(1) if m else "false")
PYEOF
)"

if [[ "${TEMPORAL_ENABLED}" != "true" ]]; then
  exit 0
fi

CONTEXT_INJECTION_ENABLED="$(python3 - "${CONFIG}" <<'PYEOF'
import sys, re

config_path = sys.argv[1] if len(sys.argv) > 1 else "factory.config.yaml"
try:
    with open(config_path) as f:
        content = f.read()
except (FileNotFoundError, IOError):
    print("false"); sys.exit(0)

# Extract temporal.context_injection.enabled
m = re.search(r'context_injection:\s*\n(?:[ \t]+[^\n]*\n)*?[ \t]+enabled:\s*(true|false)', content, re.MULTILINE)
print(m.group(1) if m else "false")
PYEOF
)"

if [[ "${CONTEXT_INJECTION_ENABLED}" != "true" ]]; then
  exit 0
fi

# Validate --task-started-at (ADR-030 §A)
if [[ -z "${TASK_STARTED_AT}" ]]; then
  echo "build-temporal-context.sh: --task-started-at is required." >&2
  exit 1
fi
if ! echo "${TASK_STARTED_AT}" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,3})?Z$'; then
  echo "build-temporal-context.sh: task_started_at non in formato UTC ISO-8601 con Z. Vedi ADR-030 §A." >&2
  exit 1
fi

# Validate --session-id (UUID v4)
if [[ -z "${SESSION_ID}" ]]; then
  echo "build-temporal-context.sh: --session-id is required." >&2
  exit 1
fi
if ! echo "${SESSION_ID}" | grep -qE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
  echo "build-temporal-context.sh: session-id non in formato UUID v4. Atteso: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx." >&2
  exit 1
fi

# Generate current_datetime (recalculated at each invocation — ADR-030 §A)
CURRENT_DATETIME="$("${SCRIPT_DIR}/utc-now.sh")"

cat <<EOF
# Temporal Context (UTC ISO-8601)
current_datetime: ${CURRENT_DATETIME}
task_started_at: ${TASK_STARTED_AT}
session_id: ${SESSION_ID}
EOF
