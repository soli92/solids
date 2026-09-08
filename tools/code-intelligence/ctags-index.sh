#!/usr/bin/env bash
# ctags-index.sh — Genera/aggiorna indice universal-ctags nel side-channel .ctags-state/
# Usage: ctags-index.sh <repo_path> <slug> [--update]
# EP-054 L1 Symbol Resolver, PATTERN §33.2

set -euo pipefail

REPO_PATH="${1:-}"
SLUG="${2:-}"
MODE="${3:-}"

if [[ -z "$REPO_PATH" || -z "$SLUG" ]]; then
  echo "Usage: ctags-index.sh <repo_path> <slug> [--update]" >&2
  exit 1
fi

if [[ ! -d "$REPO_PATH" ]]; then
  echo "[L1-ERROR] repo_path not found: $REPO_PATH" >&2
  exit 1
fi

# R.CI2: prerequisite check — SKIP non STOP se ctags non disponibile
if ! command -v ctags &>/dev/null; then
  echo "[L1-SKIP] universal-ctags not installed — brew install universal-ctags (macOS) or apt-get install universal-ctags (Linux)"
  exit 0
fi

# Verifica Universal Ctags (non Exuberant Ctags)
if ! ctags --version 2>&1 | grep -qi "universal ctags"; then
  echo "[L1-SKIP] found incompatible ctags (need Universal Ctags, not Exuberant) — brew install universal-ctags"
  exit 0
fi

SIDE_CHANNEL=".ctags-state/${SLUG}"
TAGS_FILE="${SIDE_CHANNEL}/tags"
META_FILE="${SIDE_CHANNEL}/meta.json"

mkdir -p "$SIDE_CHANNEL"

# Linguaggi da indicizzare
LANGUAGES="Python,TypeScript,JavaScript,Java,Go,Rust,C,C++"

CTAGS_OPTS=(
  "--recurse=yes"
  "--languages=${LANGUAGES}"
  "--kinds-all=*"
  "--fields=+n+S+l"
  "--extras=+q"
  "--sort=yes"
  "--output-format=u-ctags"
  "--tag-relative=yes"
  "--exclude=node_modules"
  "--exclude=__pycache__"
  "--exclude=vendor"
  "--exclude=.git"
  "--exclude=*.min.js"
  "--exclude=dist"
  "--exclude=build"
  "--exclude=.claude/worktrees"
  "--exclude=.code-search"
  "--exclude=.ctags-state"
  "--exclude=.wiki-search"
  "--exclude=.graphify-state"
)

if [[ "$MODE" == "--update" && -f "$TAGS_FILE" ]]; then
  echo "[L1] Updating ctags index for slug: ${SLUG}"
  # Trova file modificati nell'ultimo minuto (approssimazione incrementale)
  # Per update preciso usare git diff --name-only e passare i file esplicitamente
  CHANGED_FILES=$(cd "$REPO_PATH" && git diff --name-only HEAD 2>/dev/null || true)
  if [[ -n "$CHANGED_FILES" ]]; then
    # Rimuovi entry vecchie per i file cambiati
    while IFS= read -r f; do
      if [[ -f "$TAGS_FILE" ]]; then
        sed -i.bak "/$(echo "$f" | sed 's/[\/&]/\\&/g')/d" "$TAGS_FILE" 2>/dev/null || true
      fi
    done <<< "$CHANGED_FILES"
    rm -f "${TAGS_FILE}.bak"
    # Appendi entry nuove per i file cambiati
    while IFS= read -r f; do
      FULL_PATH="${REPO_PATH}/${f}"
      if [[ -f "$FULL_PATH" ]]; then
        ctags "${CTAGS_OPTS[@]}" --append -f "$TAGS_FILE" "$FULL_PATH" 2>/dev/null || true
      fi
    done <<< "$CHANGED_FILES"
  else
    echo "[L1] No changed files detected, index up to date"
  fi
else
  echo "[L1] Generating ctags index for slug: ${SLUG} at ${REPO_PATH}"
  ctags "${CTAGS_OPTS[@]}" -f "$TAGS_FILE" "$REPO_PATH"
fi

# Conta simboli e genera meta.json
SYMBOL_COUNT=0
if [[ -f "$TAGS_FILE" ]]; then
  SYMBOL_COUNT=$(grep -v "^!" "$TAGS_FILE" | wc -l | tr -d ' ')
fi

GENERATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > "$META_FILE" <<EOF
{
  "generated": "${GENERATED_AT}",
  "symbols": ${SYMBOL_COUNT},
  "slug": "${SLUG}",
  "repo": "${REPO_PATH}",
  "mode": "${MODE:-generate}"
}
EOF

echo "[L1] Index ready: ${TAGS_FILE} (${SYMBOL_COUNT} symbols)"
echo "[L1] Meta: ${META_FILE}"
