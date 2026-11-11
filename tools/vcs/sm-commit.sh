#!/usr/bin/env bash
# Shim — delega a tools/vcs/sm_commit.py (TSK-700).
# Commit senza footer AI — per code_path con ai_attribution_policy.suppress_ai_traces: true
# Uso: ./tools/vcs/sm-commit.sh "messaggio commit" [path]
#
# Il messaggio viene filtrato da strip_ai_attribution e strip_factory_ids
# (tools/vcs/ai_policy.py, fonte unica §ai_policy ADR-074) prima del commit.
# Avvisa di cio' che rimuove invece di scartarlo in silenzio.
#
# Se <path> e' specificato, il commit viene eseguito nella directory indicata;
# altrimenti viene eseguito nella directory corrente.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# python3, poi python, poi py: su Windows (Git Bash) spesso c'e' solo il launcher `py`.
PY="$(command -v python3 || command -v python || command -v py || true)"
if [[ -z "$PY" ]]; then echo "Python non trovato (python3/python/py). Vedi tools/README-windows.md" >&2; exit 1; fi
exec "$PY" "$SCRIPT_DIR/sm_commit.py" "$@"
