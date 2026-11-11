#!/usr/bin/env bash
# Shim: backward-compat wrapper — delegates to build-temporal-context.py (cross-platform).
# Chiamanti storici (PATTERN §3, ADR-030 §A §E, ADR-031 §B) continuano a funzionare invariati.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/build-temporal-context.py" "$@"
