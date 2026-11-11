#!/usr/bin/env bash
# Shim: backward-compat wrapper — delegates to utc-now.py (cross-platform).
# Chiamanti storici (ADR-030 §A, EP-011, EP-013) continuano a funzionare invariati.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/utc-now.py" "$@"
