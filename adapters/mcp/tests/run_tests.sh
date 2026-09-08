#!/usr/bin/env bash
# Esegue la suite di test dell'adapter MCP EP-058
# Uso: bash adapters/mcp/tests/run_tests.sh [pytest-args]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FACTORY_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
export FACTORY_ROOT
export PYTHONPATH="$FACTORY_ROOT/adapters/mcp:${PYTHONPATH:-}"
cd "$FACTORY_ROOT"
echo "FACTORY_ROOT=$FACTORY_ROOT"
echo "PYTHONPATH=$PYTHONPATH"
python3.12 -m pytest adapters/mcp/tests/ -v "$@"
