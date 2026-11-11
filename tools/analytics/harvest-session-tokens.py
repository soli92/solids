#!/usr/bin/env python3
"""
harvest-session-tokens.py — collects REAL token-usage from a Claude Code transcript
(JSONL) and records it to the event store via record-event.sh. It's the "missing piece" that
makes token capture operational (EP-009/EP-013): the payload hook does NOT contain the tokens,
but the JSONL transcript does (message.usage field).

USE:
  # from CLI (backfill):
  harvest-session-tokens.py <transcript.jsonl> [--project <id>] [--dry-run]
  # from hook Claude Code (Stop/SessionEnd): reads the hook JSON from stdin and extracts transcript_path
  echo '<hook-json>' | harvest-session-tokens.py --from-hook [--dry-run]

WHAT IT DOES (deterministic, no LLM):
  - JSONL parse; type=assistant lines with message.usage are grouped by message.id (one API
    response spans several lines, one per content block: see parse_transcript), then the 4
    token-kinds are added aggregating by (model, scope). Scope attribution (TSK-545 walker fan-in):
      * file location takes priority over isSidechain (CC 2.1.258+ compat)
      * main JSONL → scope determined by isSidechain (backward compat fallback)
      * subagents/agent-*.jsonl → scope "subagent" always (file-location wins)
  - WALKER FAN-IN (CC 2.1.258+): sub-agents write to a separate directory
    <session-uuid>/subagents/agent-<hash>.jsonl (isSidechain is always False in the
    main transcript). collect_jsonl_files() discovers those files automatically.
    Backward compat: if subagents/ is absent → fail-open, output identical to pre-TSK-545.
  - emit ONE event for (model, scope) via record-event.sh --event '<json>' (single-writer R.G5).
  - idempotent: ts = timestamp of last message of the group; stable task_id = session+scope+model
    → re-run does not duplicate (record-event.sh dedup on sha256(task_id|state|ts)).

LIMITS (honest):
  - the transcript exposes the tokens per MESSAGE, not per TSK: the aggregation is per session/scope,
    not for kanban task_id. Per-TSK granularity would require correlating develop markers.
  - the cost is calculated with compute-agentic-cost.sh ONLY if the `model` is in analytics/pricing.yaml.
  - subagents/ output_tokens is a lower bound when a response has only its streaming lines
    (no final line with stop_reason): the transcript then holds the message_start count
    (a few tokens). Input and cache fields are exact. Rare up to 2.1.281 (~1-2% of subagent
    responses), the norm on 2.1.289 (~80%): that is why 2.1.289 stays out of the supported set.


"""
import sys, json, subprocess, os, datetime, argparse, pathlib

HERE = pathlib.Path(__file__).resolve().parent
RECORD = HERE / "record-event.sh"

# --- Schema-version guard (TSK-546) -------------------------------------------
# Known-good Claude Code versions whose JSONL schema has been empirically verified.
# When a new CC release changes the JSONL format: verify compatibility, then add the
# version string here. Do NOT add blindly — parsing correctness must be confirmed first.
SUPPORTED_CC_VERSIONS = {
    "2.1.263",  # empirically verified in TSK-545/TSK-546 (2026-09-08) — current session
    "2.1.258",  # empirically verified in TR-c4e8f1b2 (2026-09-08)
    "2.1.257",  # structurally identical to 2.1.258, no format change observed
    "2.1.256",  # structurally identical to 2.1.258, no format change observed
    # Verified 2026-10-07 on one real transcript per version (main + subagents/): totals per
    # (scope, model) equal to an independent count keeping the last line per message.id.
    # 2.1.258 and 2.1.263 re-checked the same way after the per-message.id dedup.
    "2.1.266",  # verified 2026-10-07, independent per-message.id count (52 subagent files)
    "2.1.270",  # verified 2026-10-07, independent per-message.id count (80 subagent files)
    "2.1.274",  # verified 2026-10-07, independent per-message.id count (17 subagent files)
    "2.1.278",  # verified 2026-10-07, independent per-message.id count (45 subagent files)
    "2.1.280",  # verified 2026-10-07, independent per-message.id count (1 subagent file)
    "2.1.281",  # verified 2026-10-07, independent per-message.id count (21 subagent files)
    # 2.1.289 not added: parsing matches the independent count, but most subagent responses
    # lack their final line, so subagent output_tokens is undercounted (see LIMITS).
}


def detect_cc_version(transcript_path):
    """Return the Claude Code version string from the first JSONL line that contains
    a top-level 'version' field, or None if the field is absent in the whole file.

    Reads only until the first hit (cheap) — does NOT parse the whole transcript.
    Fail-open: returns None on any OSError or malformed JSON.
    """
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                v = d.get("version")
                if v is not None:
                    return str(v)
    except OSError:
        pass
    return None
# ------------------------------------------------------------------------------

def parse_responses(path, force_scope=None):
    """Ritorna la lista delle risposte API del transcript, una per message.id:
    [model, scope, (input, output, cache_read, cache_write, cache_write_1h), last_ts].

    cache_write e' il totale scritto in cache; cache_write_1h la parte scritta con TTL di
    un'ora (usage.cache_creation.ephemeral_1h_input_tokens), che costa 2x l'input invece
    di 1.25x. Il resto (cache_write - cache_write_1h) e' a TTL 5 minuti.

    force_scope: se None, determina scope via isSidechain (backward compat per old CC).
                 se "main" o "subagent", forza lo scope per tutte le righe (file-location wins,
                 TSK-545). isSidechain diventa fallback, NON fonte primaria.
    """
    # Claude Code writes one JSONL line per content block (thinking/text/tool_use) of the
    # same API response, each carrying message.usage. In the main transcript the usage is
    # repeated identical on every line; in subagents/ the earlier lines are streaming
    # partials whose output_tokens grows up to the final value (input and cache fields are
    # fixed from message_start). Summing every line counted each response 2-3 times.
    # One response = one message.id: keep, per id, the max of each field (= final value).
    # Lines without message.id are counted one by one, as before.
    per_msg = {}
    anon = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            # solo le righe con la chiave "usage" possono contare: le altre (tool_result,
            # prompt, metadati) sono la maggioranza e decodificarle era il costo principale
            if '"usage"' not in line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "assistant":
                continue
            msg = d.get("message") or {}
            usage = msg.get("usage") or {}
            if not usage:
                continue
            model = msg.get("model") or "unknown"
            # file-location wins (force_scope); isSidechain as retro-schema fallback only
            if force_scope is not None:
                scope = force_scope
            else:
                scope = "subagent" if d.get("isSidechain") else "main"
            ts = d.get("timestamp") or ""
            creation = usage.get("cache_creation") or {}
            vals = (int(usage.get("input_tokens", 0) or 0),
                    int(usage.get("output_tokens", 0) or 0),
                    int(usage.get("cache_read_input_tokens", 0) or 0),
                    int(usage.get("cache_creation_input_tokens", 0) or 0),
                    int(creation.get("ephemeral_1h_input_tokens", 0) or 0))
            mid = msg.get("id")
            if not mid:
                mid = ("anon", anon)
                anon += 1
            prev = per_msg.get(mid)
            if prev is None:
                per_msg[mid] = [model, scope, vals, ts]
            else:
                prev[2] = tuple(max(x, y) for x, y in zip(prev[2], vals))
                if ts > prev[3]:
                    prev[3] = ts
    return list(per_msg.values())


def parse_transcript(path, force_scope=None):
    """Ritorna dict: (model, scope) -> {input,output,cache_read,cache_write,cache_write_1h,
    msgs, last_ts}.

    force_scope: vedi parse_responses.
    """
    agg = {}
    for model, scope, vals, ts in parse_responses(path, force_scope):
        a = agg.setdefault((model, scope), {"input": 0, "output": 0, "cache_read": 0,
                                            "cache_write": 0, "cache_write_1h": 0,
                                            "msgs": 0, "last_ts": ""})
        a["input"]       += vals[0]
        a["output"]      += vals[1]
        a["cache_read"]  += vals[2]
        a["cache_write"] += vals[3]
        a["cache_write_1h"] += vals[4]
        a["msgs"]        += 1
        if ts > a["last_ts"]:
            a["last_ts"] = ts
    return agg


def collect_jsonl_files(transcript):
    """Ritorna lista di (pathlib.Path, force_scope) per il fan-in.

    Struttura directory CC 2.1.258+:
      ~/.claude/projects/<mangled-cwd>/<session-uuid>.jsonl         ← main
      ~/.claude/projects/<mangled-cwd>/<session-uuid>/subagents/agent-<hash>.jsonl  ← sub

    - JSONL principale: force_scope=None → isSidechain come fallback (backward compat)
    - File in subagents/: force_scope="subagent" → file-location vince su isSidechain
    - Se subagents/ non esiste → fail-open, solo main (sessioni pre-2.1.258 o adapter non CC)
    """
    main_path = pathlib.Path(transcript)
    files = [(main_path, None)]  # None = backward compat via isSidechain

    # La directory della sessione ha lo stesso nome del JSONL (senza estensione)
    session_dir = main_path.parent / main_path.stem
    subagents_dir = session_dir / "subagents"

    if subagents_dir.exists():
        for p in sorted(subagents_dir.glob("agent-*.jsonl")):
            files.append((p, "subagent"))

    return files


def fan_in_parse(transcript):
    """Fan-in: parse JSONL principale + tutti i subagents/agent-*.jsonl.

    Ritorna agg dict (stessa forma di parse_transcript) con scope attribuito
    per file-location (TSK-545). Deduplica per session: tutti i file appartengono
    alla stessa sessione e vengono aggregati per (model, scope).
    Fail-open su file mancanti o illeggibili.
    """
    merged = {}
    for (fpath, force_scope) in collect_jsonl_files(transcript):
        try:
            partial = parse_transcript(str(fpath), force_scope=force_scope)
        except OSError:
            continue  # fail-open: file mancante o permesso negato
        for (model, scope), data in partial.items():
            k = (model, scope)
            if k not in merged:
                merged[k] = dict(data)
            else:
                for field in ("input", "output", "cache_read", "cache_write", "cache_write_1h", "msgs"):
                    merged[k][field] += data[field]
                if data["last_ts"] > merged[k]["last_ts"]:
                    merged[k]["last_ts"] = data["last_ts"]
    return merged


def to_iso_z(ts):
    """Normalizza a ISO-8601 UTC con Z (lo schema lo richiede)."""
    if not ts:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        t = ts.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(t).astimezone(datetime.timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return ts

def build_event(session_id, model, scope, a, project_id):
    return {
        "task_id": f"session:{session_id[:8]}:{scope}:{model}",
        "project_id": project_id,
        "actor_type": "agent",
        "actor_id": f"claude-code:{scope}",
        "task_type": "session-aggregate",
        "state": "finished",
        "ts": to_iso_z(a["last_ts"]),
        "tokens": {
            "input": a["input"], "output": a["output"],
            "cache_read": a["cache_read"], "cache_write": a["cache_write"],
            "cache_write_1h": a["cache_write_1h"],
        },
        "model": model,
        "tool_calls": [],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", nargs="?", help="path al transcript JSONL")
    ap.add_argument("--from-hook", action="store_true", help="leggi hook-json da stdin, estrai transcript_path")
    ap.add_argument("--project", default=None, help="project_id (default: nome cwd)")
    ap.add_argument("--dry-run", action="store_true", help="stampa eventi, non li registra")
    args = ap.parse_args()

    transcript = args.transcript
    if args.from_hook:
        try:
            hook = json.load(sys.stdin)
            transcript = hook.get("transcript_path") or transcript
        except (json.JSONDecodeError, ValueError):
            transcript = None  # fail-open: try fallback below
        # Fallback: Some hooks (e.g. SessionEnd) may not expose transcript_path
        # → locates the most recent transcript for the current cwd.
        if not transcript or not os.path.exists(transcript):
            mangled = os.getcwd().replace("/", "-").replace(".", "-")
            pdir = os.path.expanduser(f"~/.claude/projects/{mangled}")
            try:
                cand = sorted(pathlib.Path(pdir).glob("*.jsonl"),
                              key=lambda p: p.stat().st_mtime, reverse=True)
                transcript = str(cand[0]) if cand else transcript
            except OSError:
                pass
    if not transcript or not os.path.exists(transcript):
        print(json.dumps({"status": "skip", "reason": f"transcript non trovato: {transcript}"}))
        return 0

    project_id = args.project or os.path.basename(os.getcwd())
    session_id = pathlib.Path(transcript).stem

    # --- Schema-version guard (TSK-546) ---
    # Detect Claude Code version from the transcript; warn and mark degraded if unknown.
    cc_version = detect_cc_version(transcript)
    schema_degraded = False
    if cc_version is None:
        print(
            "WARNING: Claude Code version not found in transcript; "
            "parsing in degraded mode (may miss data)",
            file=sys.stderr,
        )
        schema_degraded = True
    elif cc_version not in SUPPORTED_CC_VERSIONS:
        print(
            f"WARNING: Claude Code version {cc_version} not in supported set; "
            "parsing in degraded mode (may miss data)",
            file=sys.stderr,
        )
        schema_degraded = True
    # -------------------------------------

    # Fan-in: main JSONL + subagents/agent-*.jsonl (TSK-545)
    all_files = collect_jsonl_files(transcript)
    n_subagent_files = sum(1 for (_, s) in all_files if s == "subagent")
    agg = fan_in_parse(transcript)

    if not agg:
        print(json.dumps({"status": "skip", "reason": "nessun record usage nel transcript"}))
        return 0

    results = []
    for (model, scope), a in sorted(agg.items()):
        ev = build_event(session_id, model, scope, a, project_id)
        if args.dry_run:
            results.append({"event": ev, "recorded": False})
            continue
        try:
            p = subprocess.run([str(RECORD), "--event", json.dumps(ev)],
                               capture_output=True, text=True, timeout=30)
            ok = p.returncode == 0
            results.append({"task_id": ev["task_id"], "tokens": ev["tokens"],
                            "model": model, "recorded": ok,
                            "stdout": p.stdout.strip()[:200]})
        except Exception as e:  # noqa: BLE001 — fail-open osservatore
            results.append({"task_id": ev["task_id"], "recorded": False, "error": str(e)})

    print(json.dumps({"status": "ok", "transcript": transcript,
                      "subagent_files": n_subagent_files,
                      "schema_degraded": schema_degraded,
                      "groups": len(agg), "results": results}, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
