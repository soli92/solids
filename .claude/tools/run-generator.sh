#!/usr/bin/env bash
# Shim: backward-compat wrapper → delegates to tools/visual/run-generator.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FACTORY_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
exec "$FACTORY_ROOT/tools/visual/run-generator.sh" "$@"
