#!/usr/bin/env bash
# ADR-069 §B — deterministic Bash tool for LLM-Generator Separation (EP-019).

# Invoke the configured generator binary (plop|yeoman) from the CWD of the target package.

# Fail-loud on missing prerequisite; no MCP (ADR-008).

set -euo pipefail

GENERATOR=""
SPEC_PATH=""
TARGET_CWD=""

usage() {
  echo "Usage: $0 --generator <plop|yeoman> --spec <path-yaml> --cwd <path>" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --generator) GENERATOR="$2"; shift 2 ;;
    --spec)      SPEC_PATH="$2"; shift 2 ;;
    --cwd)       TARGET_CWD="$2"; shift 2 ;;
    *) echo "Argomento sconosciuto: $1" >&2; usage ;;
  esac
done

[[ -z "$GENERATOR" || -z "$SPEC_PATH" || -z "$TARGET_CWD" ]] && usage

# Check target CWD

if [[ ! -d "$TARGET_CWD" ]]; then
  echo "ERRORE: CWD target '$TARGET_CWD' non trovata." >&2
  exit 1
fi

# Check spec

if [[ ! -f "$SPEC_PATH" ]]; then
  echo "ERRORE: spec parametrica '$SPEC_PATH' non trovata." >&2
  exit 1
fi

resolve_binary() {
  local bin_name="$1"
  local local_bin="$TARGET_CWD/node_modules/.bin/$bin_name"
  if [[ -x "$local_bin" ]]; then
    echo "$local_bin"
  elif command -v "$bin_name" &>/dev/null; then
    command -v "$bin_name"
  else
    echo ""
  fi
}

case "$GENERATOR" in
  plop)
    BINARY=$(resolve_binary "plop")
    if [[ -z "$BINARY" ]]; then
      echo "ERRORE: generatore 'plop' non trovato nella CWD '$TARGET_CWD'; installare Plop.js (npm install --save-dev plop) nel package target prima di abilitare design_intelligence.generator_tool: plop." >&2
      exit 1
    fi
    # Check plopfile

    PLOPFILE=""
    for f in "$TARGET_CWD/plopfile.js" "$TARGET_CWD/plopfile.mjs" "$TARGET_CWD/plopfile.cjs"; do
      if [[ -f "$f" ]]; then PLOPFILE="$f"; break; fi
    done
    if [[ -z "$PLOPFILE" ]]; then
      echo "ERRORE: template 'plopfile.js|mjs|cjs' non trovato in '$TARGET_CWD'; verificare che il template sia versionato nel design system (ADR-069 §C)." >&2
      exit 1
    fi
    # Invoke plop passing the spec as input

    (cd "$TARGET_CWD" && "$BINARY" --plopfile "$PLOPFILE" -- --spec "$SPEC_PATH")
    ;;
  yeoman)
    BINARY=$(resolve_binary "yo")
    if [[ -z "$BINARY" ]]; then
      echo "ERRORE: generatore 'yo' (Yeoman) non trovato nella CWD '$TARGET_CWD'; installare Yeoman (npm install -g yo) e il generator package nel package target prima di abilitare design_intelligence.generator_tool: yeoman." >&2
      exit 1
    fi
    # Yeoman: Request generator name from package.json or config
    GENERATOR_NAME=""
    if [[ -f "$TARGET_CWD/package.json" ]]; then
      GENERATOR_NAME=$(cd "$TARGET_CWD" && node -e "try{const p=require('./package.json');const k=Object.keys(p.dependencies||{}).concat(Object.keys(p.devDependencies||{})).find(k=>k.startsWith('generator-'));console.log(k||'')}catch(e){console.log('')}" 2>/dev/null || true)
    fi
    if [[ -z "$GENERATOR_NAME" ]]; then
      echo "ERRORE: template Yeoman (generator-*) non trovato in '$TARGET_CWD/package.json'; verificare che il generator package sia versionato nel design system (ADR-069 §C)." >&2
      exit 1
    fi
    (cd "$TARGET_CWD" && "$BINARY" "$GENERATOR_NAME" --spec "$SPEC_PATH" --no-insight)
    ;;
  *)
    echo "ERRORE: generatore '$GENERATOR' non supportato. Valori validi: plop, yeoman." >&2
    exit 1
    ;;
esac
