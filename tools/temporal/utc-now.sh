#!/usr/bin/env bash
# Canonical UTC ISO-8601 timestamp generator.
# ADR-030 §A: format YYYY-MM-DDTHH:MM:SSZ (seconds) or YYYY-MM-DDTHH:MM:SS.sssZ (milliseconds).
# Used by: build-temporal-context.sh; all EP-011 temporal patterns (US-045, US-046, US-047).
# Ref: [[temporal-awareness-multiagent-patterns]] §Pattern 1, [[temporal-awareness-llm]] §Knowledge cutoff

set -euo pipefail

PRECISION="seconds"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --precision=*) PRECISION="${1#--precision=}"; shift ;;
    --precision)   PRECISION="$2"; shift 2 ;;
    *) echo "utc-now.sh: unknown argument: $1" >&2; exit 1 ;;
  esac
done

case "${PRECISION}" in
  seconds)
    date -u +"%Y-%m-%dT%H:%M:%SZ"
    ;;
  milliseconds)
    python3 -c "
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
ms = now.microsecond // 1000
print(now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{ms:03d}Z')
"
    ;;
  *)
    echo "utc-now.sh: unknown --precision='${PRECISION}'. Valid: seconds (default), milliseconds." >&2
    exit 1
    ;;
esac
