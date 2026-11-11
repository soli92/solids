#!/usr/bin/env bash
# Shim: backward-compat wrapper → delegates to tools/analytics/record-event.py (US-327)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FACTORY_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
exec python3 "$FACTORY_ROOT/tools/analytics/record-event.py" "$@"
