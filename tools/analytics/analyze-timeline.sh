#!/usr/bin/env bash
# analyze-timeline.sh — rimando a analyze-timeline.py (US-327, EP-071): stessi argomenti, stesso exit code.
# L'implementazione e' Python, portabile anche su Windows senza bash; questo file resta per
# i chiamanti storici. Implementazione bash precedente: git show 9ebc4e2:tools/analytics/analyze-timeline.sh
# Parita' misurata: tools/tests/test_analytics_parity.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || command -v python || command -v py)"
if [[ -z "$PY" ]]; then
  echo "ERRORE: python3 non trovato: analyze-timeline richiede Python 3." >&2
  printf '{"status":"error","error":"missing prerequisite: python3"}\n'
  exit 1
fi
exec "$PY" "$SCRIPT_DIR/analyze-timeline.py" "$@"
