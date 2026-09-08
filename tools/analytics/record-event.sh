#!/usr/bin/env bash
# =============================================================================
# record-event.sh — deterministic tool record_task_event (EP-009, US-033, TSK-059)
# =============================================================================
#
# Part of the Task Analytics & Cost/Time Estimation (EP-009) capability, instance
# of the pattern [[thin-agents-fat-skills-refactor]]: this is the TOOL (deterministic logic,
# no LLM). It is the single-source WRITER of the `analytics/events/` side-channel
# ([[single-writer-per-file-pattern]]): orchestrator hooks, explicit skills and


# dev-agents invoke this file by NAME, never write to the file/DB directly.
# The tool does NOT reason: it validates the scheme, dispatches to the store and appends the event.
#
# PATTERN.md §3 — optional canonical operation «Task Analytics – Event Recording».
# Wiki: wiki/concepts/task-analytics-cost-estimation-capability.md
#       [[task-analytics-cost-estimation-capability]] §Event model (minimum)
# ADR-021 — `<<task_event_store>>`: JSONL append-only `analytics/events/<YYYY-MM>.jsonl`
#           
           default + SQLite opt-in `analytics/events.db` (schema §B). §A/§B/§C/§E/§F.

# 
 ADR-023 §A — analytics tool registration in `.claude/tools/analytics/*` (no MCP),

#           minimal contract: --config optional, stdout=JSON / stderr=log, exit code
#           
           semantic, stateless.

#
# ADR pending for binding to guest framework (see wiki/gaps.md 2026-06-04):
#   - ADR-022 `<<model_id>>` resolution (canonical `model` field).
#   - ADR-024 schema `analytics/reports/`.
#
# ESTENSIONE v2.19 (EP-013 US-052, TSK-104) — additiva, backward-compatible EP-009:
#   - ADR-042 §A §B §C — event extension schema: enum `state` extended to 7 values
#       canonici (started|finished|blocked|aborted|wave_started|wave_completed|
#       
       sub_agent_dispatched) + 11 optional extension fields (wave_id, wave_size,

#       wave_elapsed_ms, success_count, failure_count, candidates, aborted_reason,
#       blocked_reason, blocking_artifacts, dispatch_ts, completion_ts, hash).
#       
       Schema-permissive (non-mandatory extension fields), no breaking change.

#   
   - ADR-039 §A — flock(2) exclusive advisory lock on `analytics/events/.lock`

#       BEFORE writing JSONL (safety from parallel waves, scheduler v2.11
#       max_parallel:4). Timeout configurabile via ANALYTICS_LOCK_TIMEOUT_SECONDS
#       
       (default 5s). Cross-month shared lock. Self-release when closing fd 200.

#   - ADR-039 §B — single-writer enforced: this tool is the ONLY writer of
#       analytics/events/<YYYY-MM>.jsonl (no one writes to the file directly).
#   - ADR-039 §C §G — idempotency: hash compound sha256(task_id|state|ts)[0:16]
#       added to payload + check pre-write duplicates via grep. Same event
#       2× (same ts) → 1 entry only. Historical events without `hash` not deduplicated.
#   
   - ADR-039 §D — fail-open on workflow / fail-loud on tool: lock timeout or write

#       
       error → exit non-zero + WARNING stderr; the caller continues (observer

#       patterns). PII violation → exit 1 + ERROR stderr (caller bug).
#   - ADR-040 §C — enforcement PII boundary pre-write: allowlist top-level keys
#       
       (9 safe fields + extension), blocklist 7 categories (free-text >200 chars,

#       pattern secret/key/token/password/prompt/system/PEM/hex, email fuori da
#       actor_id). Fail-loud (exit 1) on violation. Performed AFTER scheme (§4),
#       BEFORE dispatch store (store-agnostic).
#
# -----------------------------------------------------------------------------
# INPUT CONTRACT (CLI)
#   --event '<JSON>' event to log (required). Diagram §E ADR-021
#                           
                           + ADR-042 extension (7 enum states + optional fields).

#   
   --config <path> default "factory.config.yaml" (agnostic-test, ADR-023 §A).

#
# OUTPUT CONTRACT (stdout, pure JSON)
#   success: {"status":"ok","path":"analytics/events/2026-06.jsonl","event_id":"<ts>-<task_id>"}
#   error:   {"status":"error","error":"<message>"}
#
# STDERR
#   human-readable log (fail-loud on error; quiet on success).
#
# EXIT CODES
#   0 event logged OR no-op (capability off R.P3 / idempotency hit /
#      
      lock timeout fail-open ADR-039 §D case B)

#   1 fail-loud error: invalid schema, invalid store, PII boundary violation
#      
      (ADR-040 §C — caller bug, NOT fail-open)

#   2 lock timeout (ADR-039 §D case B) — reserved for fail-loud-on-lock variants;
#      
      in v2.19 the default is fail-open (exit 0) consistent with observer pattern

#   3  write error (disk full / permission, ADR-039 §D caso C)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 
 0. Repo root resolution (the script can be invoked from any cwd)

# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# tools/analytics/ → repo root is 2 levels up (it was 3 when the path was .claude/tools/analytics/).
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# 
 Worktree-aware (TSK-408 Fix B): If the script runs in a secondary worktree,

# git --git-common-dir points to the .git of the main repo (absolute path), while
# --git-dir points to the .git of the worktree (.git/worktrees/<id>). In that case it is used
# dirname(--git-common-dir) as REPO_ROOT, so events end in
# analytics/events/ of the main repo (not in the possibly absent one of the worktree).
_GIT_COMMON="$(git -C "$SCRIPT_DIR" rev-parse --git-common-dir 2>/dev/null || true)"
_GIT_DIR="$(git -C "$SCRIPT_DIR" rev-parse --git-dir 2>/dev/null || true)"
if [[ -n "$_GIT_COMMON" && -n "$_GIT_DIR" && "$_GIT_COMMON" != "$_GIT_DIR" && "$_GIT_COMMON" = /* ]]; then
  # We are in a worktree: --git-common-dir is absolute and different from --git-dir
  REPO_ROOT="$(dirname "$_GIT_COMMON")"
fi
unset _GIT_COMMON _GIT_DIR

# ---------------------------------------------------------------------------
# 1. CLI argument parsing
# ---------------------------------------------------------------------------
EVENT=""
CONFIG="factory.config.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event)
      EVENT="${2:-}"; shift 2 ;;
    --config)
      CONFIG="${2:-factory.config.yaml}"; shift 2 ;;
    *)
      echo "ERRORE: argomento sconosciuto '$1'. Uso: record-event.sh --event '<JSON>' [--config <path>]" >&2
      printf '{"status":"error","error":"unknown argument: %s"}\n' "$1"
      exit 1 ;;
  esac
done

if [[ -z "$EVENT" ]]; then
  echo "ERRORE: --event è obbligatorio. Uso: record-event.sh --event '<JSON>' [--config <path>]" >&2
  printf '{"status":"error","error":"missing required argument: --event"}\n'
  exit 1
fi

# 
 Normalize CONFIG to absolute path (relative → with respect to the root repo).

if [[ "$CONFIG" != /* ]]; then
  CONFIG="$REPO_ROOT/$CONFIG"
fi

# ---------------------------------------------------------------------------
# 2. Check prerequisiti — fail-loud (ADR-023 §A contract)
# ---------------------------------------------------------------------------
if ! command -v jq >/dev/null 2>&1; then
  echo "Tool record_task_event richiede 'jq' per il parsing/validazione JSON. Installare jq (brew install jq / apt-get install jq)." >&2
  printf '{"status":"error","error":"missing prerequisite: jq"}\n'
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. Master switch — no-op if the capability is off (R.P3, ADR-021 §F)
#    Read analytics.measurement.enabled from CONFIG. Absence of the file or
#    lock => disabled => exit 0 silent, NO file written.
# ---------------------------------------------------------------------------
# Minimal helper: extracts a scalar value from a nested YAML block
# `analytics: > measurement: > <key>:` senza dipendenze esterne (no yq).
yaml_measurement_value() {
  # $1 = key under analytics.measurement
  local key="$1" file="$2"
  [[ -f "$file" ]] || return 0
  awk -v want="$key" '
    function indent(s,   n){ n=0; while (substr(s,n+1,1)==" ") n++; return n }
    {
      raw=$0
      # strip inline comment (simple: after " #")
      sub(/[[:space:]]+#.*$/, "", raw)
      ind=indent(raw)
      line=raw; gsub(/^[[:space:]]+/, "", line); gsub(/[[:space:]]+$/, "", line)
      if (line=="") next
      if (line ~ /^analytics:/)    { in_a=1; a_ind=ind; in_m=0; next }
      if (in_a && ind<=a_ind && line !~ /^analytics:/) { in_a=0; in_m=0 }
      if (in_a && line ~ /^measurement:/) { in_m=1; m_ind=ind; next }
      if (in_m && ind<=m_ind) { in_m=0 }
      if (in_m && line ~ ("^" want ":")) {
        v=line; sub(("^" want ":[[:space:]]*"), "", v)
        gsub(/^["'"'"']|["'"'"']$/, "", v)
        print v; exit
      }
    }
  ' "$file"
}

ENABLED="$(yaml_measurement_value "enabled" "$CONFIG")"
if [[ "$ENABLED" != "true" ]]; then
  # No-op: capability turned off or blocking absent. Total backward-compat (R.P3).
  echo "record_task_event: analytics.measurement.enabled non è true (no-op, R.P3)." >&2
  exit 0
fi

STORE="$(yaml_measurement_value "store" "$CONFIG")"
[[ -z "$STORE" ]] && STORE="jsonl"   # default ADR-021 §A
if [[ "$STORE" != "jsonl" && "$STORE" != "sqlite" ]]; then
  echo "ERRORE: analytics.measurement.store deve essere 'jsonl' o 'sqlite' (trovato: '$STORE'). Vedi ADR-021 §C." >&2
  printf '{"status":"error","error":"invalid store: %s"}\n' "$STORE"
  exit 1
fi

# ---------------------------------------------------------------------------
# 4. Event schema validation — fail-loud on stderr, JSON error on stdout
#    (US-033 §Business Rules + ADR-021 §E)
# ---------------------------------------------------------------------------
fail_schema() {
  # 
 $1 = human-readable message / error payload

  echo "ERRORE schema evento: $1" >&2
  printf '{"status":"error","error":"%s"}\n' "$1"
  exit 1
}

# 4.0 JSON well-formed?
if ! printf '%s' "$EVENT" | jq -e . >/dev/null 2>&1; then
  fail_schema "invalid JSON payload"
fi

# 4.1 Top-level mandatory fields present (US-033: 10 enforced fields + optional parent_id).
REQUIRED=(task_id project_id actor_type actor_id task_type state ts tokens model tool_calls)
for f in "${REQUIRED[@]}"; do
  if ! printf '%s' "$EVENT" | jq -e --arg k "$f" 'has($k)' >/dev/null 2>&1; then
    fail_schema "missing required field: $f"
  fi
done

# 
 4.2 non-empty task_id and project_id (critical rule US-033 §Business Rules).

for f in task_id project_id; do
  val="$(printf '%s' "$EVENT" | jq -r --arg k "$f" '.[$k] // ""')"
  if [[ -z "$val" || "$val" == "null" ]]; then
    fail_schema "missing required field: $f"
  fi
done

# 4.3 actor_type ∈ {agent,human}.
ACTOR_TYPE="$(printf '%s' "$EVENT" | jq -r '.actor_type // ""')"
if [[ "$ACTOR_TYPE" != "agent" && "$ACTOR_TYPE" != "human" ]]; then
  fail_schema "invalid actor_type: '$ACTOR_TYPE' (allowed: agent|human)"
fi

# 4.4 state ∈ enum canonico esteso v2.19 (ADR-042 §A §C).
#     7 values: 3 original EP-009 + aborted + wave_started + wave_completed
#     + sub_agent_dispatched (accepted by the tool; issued only if granularity:tool).
VALID_STATES=("started" "finished" "blocked" "aborted" "wave_started" "wave_completed" "sub_agent_dispatched")
STATE="$(printf '%s' "$EVENT" | jq -r '.state // ""')"
if [[ ! " ${VALID_STATES[*]} " == *" ${STATE} "* ]]; then
  fail_schema "invalid state: '$STATE' (allowed: started|finished|blocked|aborted|wave_started|wave_completed|sub_agent_dispatched)"
fi

# 4.5 ts ISO-8601 (YYYY-MM-DDThh:mm:ss[.fff][Z|±hh:mm]).
TS="$(printf '%s' "$EVENT" | jq -r '.ts // ""')"
if ! printf '%s' "$TS" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$'; then
  fail_schema "invalid ts (not ISO-8601): '$TS'"
fi

# 4.6 tokens is an object with 4 distinct (not added) sub-fields.
if ! printf '%s' "$EVENT" | jq -e '.tokens | type == "object"' >/dev/null 2>&1; then
  fail_schema "tokens must be an object with input/output/cache_read/cache_write"
fi
for sub in input output cache_read cache_write; do
  if ! printf '%s' "$EVENT" | jq -e --arg k "$sub" '.tokens | has($k)' >/dev/null 2>&1; then
    fail_schema "missing tokens sub-field: $sub"
  fi
done

# 
 4.7 tool_calls is array (can be empty).

if ! printf '%s' "$EVENT" | jq -e '.tool_calls | type == "array"' >/dev/null 2>&1; then
  fail_schema "tool_calls must be an array (may be empty)"
fi

# ---------------------------------------------------------------------------
# 4.8-4.11 Enforcement PII boundary pre-write (ADR-040 §C)
#   Performed AFTER schema validation (§4.1-4.7) and BEFORE the dispatch store
#   (§6) → store-agnostic (applies to jsonl and sqlite). Fail-loud (exit 1):
#   
   PII leak is a caller structural bug, NOT fail-open (ADR-039 §D case E,

#   
   ADR-040 §C). Never write non-compliant payloads.

# ---------------------------------------------------------------------------
fail_pii_violation() {
  # 
 $1 = human-readable message / error payload

  echo "ERRORE PII boundary: $1" >&2
  printf '{"status":"error","error":"PII boundary violation: %s"}\n' "$1"
  exit 1   # fail-loud (ADR-040 §C — not fail-open)
}

# 4.8 Allowlist check (ADR-040 §A): each top-level key of the payload must be
#     
     safe-listed. 9 canonical fields + optional extensions (ADR-038/039/042).

ALLOWED_KEYS=("ts" "state" "task_id" "project_id" "actor_id" "actor_type"
              "task_type" "elapsed_ms" "tokens" "model" "tool_calls" "parent_id"
              "extras" "wave_id" "wave_size" "wave_elapsed_ms" "success_count"
              "failure_count" "candidates" "aborted_reason" "blocked_reason"
              "blocking_artifacts" "hash" "dispatch_ts" "completion_ts")
while IFS= read -r KEY; do
  [[ -z "$KEY" ]] && continue
  if [[ ! " ${ALLOWED_KEYS[*]} " == *" ${KEY} "* ]]; then
    fail_pii_violation "key '$KEY' not in allowlist (ADR-040 §A)"
  fi
done < <(printf '%s' "$EVENT" | jq -r 'keys[]')

# 4.9 Blocklist category 7 — free-text >200 chars on fields that can have text.
TEXT_FIELDS=("aborted_reason" "blocked_reason")
for FIELD in "${TEXT_FIELDS[@]}"; do
  VAL="$(printf '%s' "$EVENT" | jq -r --arg k "$FIELD" '.[$k] // ""')"
  if [[ ${#VAL} -gt 200 ]]; then
    fail_pii_violation "field '$FIELD' length ${#VAL} > 200 char (ADR-040 §B cat 7 free-text)"
  fi
done

# 4.10 Blocklist pattern check (ADR-040 §B cat 1-5): secret/key/token/password/
#      prompt/system/PEM/long-hex. Conservativo (rischio falsi positivi accettato).
declare -a BLOCKED_PATTERNS=(
  '"[A-Z_]+_KEY"[[:space:]]*:[[:space:]]*"[^"]+"'     # API key fingerprint (cat 5)
  '"[A-Z_]+_TOKEN"[[:space:]]*:[[:space:]]*"[^"]+"'   # token fingerprint (cat 5)
  '"password"[[:space:]]*:[[:space:]]*"[^"]+"'        # password (cat 5)
  '"api_key"[[:space:]]*:[[:space:]]*"[^"]+"'         # api_key (cat 5)
  '"prompt"[[:space:]]*:[[:space:]]*"[^"]+"'          # prompt content (cat 2)
  '"system"[[:space:]]*:[[:space:]]*"[^"]+"'          # system prompt (cat 2)
  'BEGIN [A-Z ]+PRIVATE KEY'                          # PEM keys (cat 5)
  '[0-9a-fA-F]{32,}'                                  # potenziali hash di segreti (cat 5)
)
for PATTERN in "${BLOCKED_PATTERNS[@]}"; do
  if printf '%s' "$EVENT" | grep -Eq "$PATTERN"; then
    fail_pii_violation "pattern matches blocklist (ADR-040 §B): /${PATTERN}/"
  fi
done

# 4.11 Blocklist categoria 6 — email fuori da actor_id (eccezione documentata §B:
#      actor_id can be GitHub handle/email; email anywhere else = leak).
EMAIL_RE='[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
if printf '%s' "$EVENT" | grep -Eq "$EMAIL_RE"; then
  EMAIL_IN_ACTOR_ID="$(printf '%s' "$EVENT" | jq -r '.actor_id // ""' | grep -E '@' || true)"
  EMAIL_ANYWHERE="$(printf '%s' "$EVENT" | grep -coE "$EMAIL_RE")"
  if [[ -z "$EMAIL_IN_ACTOR_ID" || "$EMAIL_ANYWHERE" != "1" ]]; then
    fail_pii_violation "email pattern detected outside actor_id (ADR-040 §B cat 6)"
  fi
fi

# ---------------------------------------------------------------------------
# 5. Derivazioni comuni
# ---------------------------------------------------------------------------
TASK_ID="$(printf '%s' "$EVENT" | jq -r '.task_id')"
YYYY_MM="$(printf '%s' "$TS" | cut -c1-7)"   # da ts ISO-8601 → YYYY-MM (rotazione mensile)
EVENT_ID="${TS}-${TASK_ID}"
EVENTS_DIR="$REPO_ROOT/analytics/events"

# Temporal State Machine hook registration (opt-in v2.18+, ADR-028 §B.2).
# The _temporal_sm_hook_v218 function is defined at the end of the file (section 7).
# Runs via EXIT trap after every exit with code 0 (dispatch successful).
# 
 With flag off (default) → no-op: triple gate in the function itself (R.P3).

trap '_temporal_sm_hook_v218' EXIT

# ---------------------------------------------------------------------------
# 6. Dispatch store (ADR-021 §C: exclusive switch, never both)
# ---------------------------------------------------------------------------
if [[ "$STORE" == "jsonl" ]]; then
  # 
 6a. JSONL atomic append — one file per month (ADR-021 §A).
  mkdir -p "$EVENTS_DIR"
  TARGET="$EVENTS_DIR/${YYYY_MM}.jsonl"
  REL_TARGET="analytics/events/${YYYY_MM}.jsonl"

  # --- Idempotency hash compound (ADR-039 §C §G) ---
  # sha256(task_id|state|ts)[0:16]. 64 bit entropy, dedup for volumes <1M/month.
  # sha256sum (Linux) or `shasum -a 256` (macOS/BSD). Fallback fail-loud if absent.
  if command -v sha256sum >/dev/null 2>&1; then
    HASH="$(printf '%s' "${TASK_ID}|${STATE}|${TS}" | sha256sum | cut -c1-16)"
  elif command -v shasum >/dev/null 2>&1; then
    HASH="$(printf '%s' "${TASK_ID}|${STATE}|${TS}" | shasum -a 256 | cut -c1-16)"
  else
    echo "Tool record_task_event richiede 'sha256sum' o 'shasum' per l'idempotency hash (ADR-039 §C)." >&2
    printf '{"status":"error","error":"missing prerequisite: sha256sum/shasum"}\n'
    exit 1
  fi

  # 
 --- Lock advisory flock(2) exclusive (ADR-039 §A §E) ---

  # Lock condiviso cross-mese su analytics/events/.lock (auto-created, gitignored).
  # 
 Configurable timeout via ANALYTICS_LOCK_TIMEOUT_SECONDS (default 5s).

  # 
 The lock protects the atomic sequence check-idempotent + append (§C).

  LOCK_FILE="$EVENTS_DIR/.lock"
  LOCK_TIMEOUT="${ANALYTICS_LOCK_TIMEOUT_SECONDS:-5}"

  if command -v flock >/dev/null 2>&1; then
    touch "$LOCK_FILE" 2>/dev/null || true
    exec 200>"$LOCK_FILE"
    if ! flock -w "$LOCK_TIMEOUT" -x 200; then
      # 
 Case B (ADR-039 §D): lock not acquired → fail-open on the workflow.

      echo "[analytics-write-fail] flock timeout after ${LOCK_TIMEOUT}s — skipping event write (fail-open, ADR-039 §D)" >&2
      printf '{"status":"skipped","reason":"lock_timeout","event_id":"%s"}\n' "$EVENT_ID"
      exit 0   # fail-open: observer does not block the observed workflow
    fi
  else
    # flock absent (macOS without util-linux): graceful degradation, single-writer
    # advisory not available. Best-effort writing (no lock). Documented ADR-039 §A.
    echo "record_task_event: 'flock' non disponibile — append senza advisory lock (degradazione graceful, ADR-039 §A)." >&2
  fi

  # --- Idempotency check pre-write (under lock, ADR-039 §C) ---
  if grep -qF "\"hash\":\"${HASH}\"" "$TARGET" 2>/dev/null; then
    echo "record_task_event: evento ${HASH} già presente (idempotent, no-op, ADR-039 §C)." >&2
    command -v flock >/dev/null 2>&1 && flock -u 200 2>/dev/null || true
    printf '{"status":"ok","path":"%s","event_id":"%s","idempotent":true}\n' "$REL_TARGET" "$EVENT_ID"
    exit 0   # no-op silenzioso (ADR-039 §D caso D)
  fi

  # --- Append with embedded hash (ADR-039 §C) ---
  # Compact to one line (one-liner JSONL) + open-flush-close atomic append.
  ONELINE="$(printf '%s' "$EVENT" | jq -c --arg h "$HASH" '. + {hash: $h}')"
  if ! printf '%s\n' "$ONELINE" >> "$TARGET" 2>/dev/null; then
    # Caso C (ADR-039 §D): scrittura fallita (disk full / permission) → fail-loud tool.
    echo "[analytics-write-fail] write error su $REL_TARGET (disk full / permission?) — evento perso (ADR-039 §D caso C)" >&2
    command -v flock >/dev/null 2>&1 && flock -u 200 2>/dev/null || true
    printf '{"status":"error","error":"write error: %s"}\n' "$REL_TARGET"
    exit 3   # write error (fail-loud on tool; caller does fail-open)
  fi

  # --- Release lock (auto locking fd 200, explicit for clarity ADR-039 §A) ---
  command -v flock >/dev/null 2>&1 && flock -u 200 2>/dev/null || true

  echo "record_task_event: evento $EVENT_ID appeso a $REL_TARGET (store=jsonl, hash=$HASH)." >&2
  printf '{"status":"ok","path":"%s","event_id":"%s"}\n' "$REL_TARGET" "$EVENT_ID"
  exit 0
else
  # 6b. SQLite — DDL on-init + INSERT (ADR-021 §B).
  if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "Tool record_task_event con store=sqlite richiede 'sqlite3' CLI (≥3.35). Installare sqlite3 o usare store=jsonl (default). Vedi ADR-021 §B." >&2
    printf '{"status":"error","error":"missing prerequisite: sqlite3"}\n'
    exit 1
  fi
  mkdir -p "$EVENTS_DIR/.."   # garantisce analytics/
  DB="$REPO_ROOT/analytics/events.db"
  REL_DB="analytics/events.db"

  # DDL idempotente (schema §B ADR-021).
  sqlite3 "$DB" <<'SQL'
CREATE TABLE IF NOT EXISTS events (
  rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id     TEXT    NOT NULL,
  project_id  TEXT    NOT NULL,
  parent_id   TEXT,
  actor_type  TEXT    NOT NULL CHECK(actor_type IN ('agent', 'human')),
  actor_id    TEXT    NOT NULL,
  task_type   TEXT    NOT NULL,
  state       TEXT    NOT NULL CHECK(state IN ('started', 'finished', 'blocked')),
  ts          TEXT    NOT NULL,
  model       TEXT,
  tokens_input        INTEGER DEFAULT 0,
  tokens_output       INTEGER DEFAULT 0,
  tokens_cache_read   INTEGER DEFAULT 0,
  tokens_cache_write  INTEGER DEFAULT 0,
  tool_calls  TEXT,
  extras      TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_project_ts ON events(project_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_task_type_ts ON events(task_type, ts);
SQL

  # Field extraction (distinct sub-field tokens, NOT summed — ADR-021 §E).
  PROJECT_ID="$(printf '%s' "$EVENT" | jq -r '.project_id')"
  PARENT_ID="$(printf '%s' "$EVENT" | jq -r '.parent_id // ""')"
  ACTOR_ID="$(printf '%s' "$EVENT" | jq -r '.actor_id')"
  TASK_TYPE="$(printf '%s' "$EVENT" | jq -r '.task_type')"
  MODEL="$(printf '%s' "$EVENT" | jq -r '.model // ""')"
  TOK_IN="$(printf '%s' "$EVENT" | jq -r '.tokens.input // 0')"
  TOK_OUT="$(printf '%s' "$EVENT" | jq -r '.tokens.output // 0')"
  TOK_CR="$(printf '%s' "$EVENT" | jq -r '.tokens.cache_read // 0')"
  TOK_CW="$(printf '%s' "$EVENT" | jq -r '.tokens.cache_write // 0')"
  TOOL_CALLS="$(printf '%s' "$EVENT" | jq -c '.tool_calls')"
  EXTRAS="$(printf '%s' "$EVENT" | jq -c '.extras // null')"

  # Escape single quotes for SQL literals.
  sql_q() { printf '%s' "$1" | sed "s/'/''/g"; }

  sqlite3 "$DB" <<SQL
INSERT INTO events
  (task_id, project_id, parent_id, actor_type, actor_id, task_type, state, ts,
   model, tokens_input, tokens_output, tokens_cache_read, tokens_cache_write,
   tool_calls, extras)
VALUES
  ('$(sql_q "$TASK_ID")', '$(sql_q "$PROJECT_ID")', '$(sql_q "$PARENT_ID")',
   '$(sql_q "$ACTOR_TYPE")', '$(sql_q "$ACTOR_ID")', '$(sql_q "$TASK_TYPE")',
   '$(sql_q "$STATE")', '$(sql_q "$TS")', '$(sql_q "$MODEL")',
   $TOK_IN, $TOK_OUT, $TOK_CR, $TOK_CW,
   '$(sql_q "$TOOL_CALLS")', '$(sql_q "$EXTRAS")');
SQL

  echo "record_task_event: evento $EVENT_ID inserito in $REL_DB (store=sqlite)." >&2
  printf '{"status":"ok","path":"%s","event_id":"%s"}\n' "$REL_DB" "$EVENT_ID"
  exit 0
fi

# ---------------------------------------------------------------------------
# 7. Temporal State Machine hook (opt-in v2.18+, ADR-028 §B.2)
#    Function invoked via `trap EXIT` (section 5) after each successful dispatch.
#    Single-writer of the side-channel management/state/<task_id>.json mode
#    `source: events`. Delega all'algoritmo canonico rebuild-state-from-events.sh.
#    Backward compat absolute (R.P3): gate triple → no-op when flag off.
# ---------------------------------------------------------------------------
_temporal_sm_hook_v218() {
  local _exit_code=$?
  # Run only on successful dispatch (exit 0 from JSONL or SQLite path)
  [[ "$_exit_code" -ne 0 ]] && return 0

  # Gate 1: temporal.enabled
  local _tm_enabled
  _tm_enabled="$(python3 -c "
import re, sys
try:
    with open('${CONFIG}') as f: c = f.read()
    m = re.search(r'^\s*temporal:\s*\n\s+enabled:\s*(true|false)', c, re.M)
    print(m.group(1) if m else 'false')
except: print('false')
" 2>/dev/null)"
  [[ "$_tm_enabled" != "true" ]] && return 0

  # Gate 2: temporal.state_machine.enabled
  local _sm_enabled
  _sm_enabled="$(python3 -c "
import re
try:
    with open('${CONFIG}') as f: c = f.read()
    m = re.search(r'state_machine:\s*\n\s+enabled:\s*(true|false)', c)
    print(m.group(1) if m else 'false')
except: print('false')
" 2>/dev/null)"
  [[ "$_sm_enabled" != "true" ]] && return 0

  # Gate 3: temporal.state_machine.source == "events"
  local _sm_source
  _sm_source="$(python3 -c "
import re
try:
    with open('${CONFIG}') as f: c = f.read()
    m = re.search(r'state_machine:.*?source:\s*[\"']?(\w+)', c, re.S)
    print(m.group(1) if m else 'standalone')
except: print('standalone')
" 2>/dev/null)"
  [[ "$_sm_source" != "events" ]] && return 0

  # Validation cross-config (ADR-028 §G): source:events richiede analytics.measurement.enabled: true.
  # We are already on the success path, so measurement is enabled (section 3 checks this).

  # ADR-028 §B.2: eventi senza step_id → WARNING su stderr, no state update (no fail-loud)
  local _step_id
  _step_id="$(printf '%s' "$EVENT" | jq -r '.extras.step_id // ""' 2>/dev/null || echo '')"
  if [[ -z "$_step_id" ]]; then
    echo "WARNING: Evento per TSK temporal-aware ${TASK_ID} senza step_id in extras. State view non aggiornata. Vedi ADR-028 §B.2." >&2
    return 0
  fi

  # 
 Read state_file_path from config (default management/state)
  local _sm_path
  _sm_path="$(python3 -c "
import re
try:
    with open('${CONFIG}') as f: c = f.read()
    m = re.search(r'state_file_path:\s*[\"']?([^\n\"'#]+)', c)
    print(m.group(1).strip() if m else 'management/state')
except: print('management/state')
" 2>/dev/null)"

  # Delega all'algoritmo canonico rebuild-state-from-events.sh (ADR-028 §B.2 idempotente)
  local _rebuild="$SCRIPT_DIR/../temporal/rebuild-state-from-events.sh"
  if [[ -f "$_rebuild" ]]; then
    bash "$_rebuild" \
      --task-id "$TASK_ID" \
      --events-dir "$REPO_ROOT/analytics/events" \
      --output-dir "$REPO_ROOT/$_sm_path" \
      --config "$CONFIG" >&2 || true
  else
    echo "WARNING: rebuild-state-from-events.sh non trovato (${_rebuild}). State view non aggiornata. Vedi ADR-028 §B.2." >&2
  fi
  return 0
}
