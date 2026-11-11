#!/usr/bin/env bash
# Shim: backward-compat wrapper — delegates to rebuild-state-from-events.py (cross-platform).
# Chiamanti storici (ADR-028 §A §B.2 §E, record-event.sh) continuano a funzionare invariati.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/rebuild-state-from-events.py" "$@"
