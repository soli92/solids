#!/usr/bin/env python3
"""
fleet-metrics.py — EP-061/US-244/TSK-553
Aggregation rollup from parse-transcript.py JSON output.

Produces per_agent, per_model, per_wave, session_totals, dispatch_efficiency.
Used as substrate for anomaly detection (TSK-554) and reporting (TSK-556).

CLI:
  python3 fleet-metrics.py <parsed-json-file> [--output <file>] [--pricing <file>]

  <parsed-json-file>  Path to JSON produced by parse-transcript.py, or "-" for stdin.
  --output FILE       Write JSON to FILE instead of stdout.
  --pricing FILE      Path to analytics/pricing.yaml (auto-discovery when omitted).

Pricing resolution order:
  1. --pricing FILE (explicit)
  2. Auto-discovery: <repo-root>/analytics/pricing.yaml
  3. Hardcoded fallback (documented below)

stdlib-only: json, argparse, sys, pathlib, collections, statistics, os, datetime, re
"""

import sys
import json
import argparse
import pathlib
import collections
import statistics
import os
import datetime
import re

# ── Hardcoded pricing fallback ─────────────────────────────────────────────────
# Fallback prices as of 2026-09; update via analytics/pricing.yaml
# Units: USD per 1M tokens.
# Source: Anthropic public pricing page 2026-09.

_FALLBACK_EXACT = {
    # model_id (or alias) → (input_per_1m, output_per_1m, cache_read_per_1m)
    "claude-sonnet-4-6":         (3.0,  15.0,  0.30),
    "claude-haiku-4-5":          (0.80,  4.0,  0.08),
    "claude-haiku-4-5-20251001": (0.80,  4.0,  0.08),
}

_FALLBACK_PREFIX = [
    # Prefix matching (longest-first order matters for specificity):
    ("claude-opus",   (15.0, 75.0, 1.50)),
    ("claude-sonnet", (3.0,  15.0, 0.30)),
    ("claude-haiku",  (0.80,  4.0, 0.08)),
]


# ── Repo root discovery ────────────────────────────────────────────────────────

def _find_repo_root():
    """Walk up from this script's directory to the factory repo root.

    Identified by the presence of factory.config.yaml. Returns the nearest
    ancestor that satisfies the condition. Falls back to grandparent of this
    script if no root is found.
    """
    here = pathlib.Path(__file__).resolve().parent
    for candidate in (here, here.parent, here.parent.parent, here.parent.parent.parent):
        if (candidate / "factory.config.yaml").exists():
            return candidate
    return here.parent.parent  # last-resort fallback


# ── Pricing YAML loader ────────────────────────────────────────────────────────

def _parse_pricing_yaml_regex(path):
    """
    Minimal regex-based parser for analytics/pricing.yaml.

    Handles the specific structure used in this factory:
      models:
        - id: <model_id>
          aliases:
            - <alias1>
          pricing:
            - valid_from: YYYY-MM-DD
              input_per_1m_tokens: F
              output_per_1m_tokens: F
              cache_read_per_1m_tokens: F

    Returns dict: (model_id or alias) → (input_per_1m, output_per_1m, cache_read_per_1m).
    Raises on IO errors; returns empty dict if structure not recognized.
    """
    text = pathlib.Path(path).read_text(encoding="utf-8")

    # Split on top-level model entries: "  - id: <something>"
    # Each chunk starts right after the split token.
    chunks = re.split(r"\n  - id:\s*", text)
    if len(chunks) < 2:
        return {}

    pricing = {}

    for chunk in chunks[1:]:  # first chunk is the file header
        lines = chunk.split("\n")
        # First line of chunk is the model id value
        mid_raw = lines[0].strip().strip('"').strip("'")
        if not mid_raw:
            continue

        block_text = "\n".join(lines[1:])

        # ── Extract aliases ────────────────────────────────────────────────────
        # aliases block: "    aliases:\n      - <alias>\n      - <alias>"
        aliases = []
        alias_block_m = re.search(
            r"aliases:\s*\n((?:\s{6,}-[^\n]*\n?)*)",
            block_text,
        )
        if alias_block_m:
            for line in alias_block_m.group(1).splitlines():
                m = re.match(r"\s+-\s+(.*)", line)
                if m:
                    aliases.append(m.group(1).strip().strip('"').strip("'"))

        # ── Extract pricing: use last entry (most recent valid_from) ───────────
        # Find all input/output/cache_read values in the pricing block.
        # Multiple valid_from entries possible; last wins (list sorted asc).
        inp_vals = re.findall(r"input_per_1m_tokens:\s*([\d.]+)", block_text)
        out_vals = re.findall(r"output_per_1m_tokens:\s*([\d.]+)", block_text)
        cr_vals  = re.findall(r"cache_read_per_1m_tokens:\s*([\d.]+)", block_text)

        inp = float(inp_vals[-1]) if inp_vals else 0.0
        out = float(out_vals[-1]) if out_vals else 0.0
        cr  = float(cr_vals[-1])  if cr_vals  else 0.0

        for key in [mid_raw] + aliases:
            pricing[key] = (inp, out, cr)

    return pricing


def _load_pricing(path, warnings):
    """
    Load pricing table from YAML file.

    Resolution:
      1. Try regex-based parser (stdlib-only, no PyYAML required).
      2. Return (dict, "analytics/pricing.yaml") on success.
      3. Return (None, "hardcoded-fallback") + warning on any failure.

    Returns: (pricing_dict | None, source_label)
    """
    if path is None:
        warnings.append(
            "pricing.yaml not found at auto-discovery path; using hardcoded fallback"
        )
        return None, "hardcoded-fallback"

    fpath = pathlib.Path(path)
    if not fpath.exists():
        warnings.append(f"pricing.yaml not found: {path}; using hardcoded fallback")
        return None, "hardcoded-fallback"

    try:
        pricing = _parse_pricing_yaml_regex(fpath)
        if not pricing:
            warnings.append(
                f"pricing.yaml parsed but no model entries found ({path}); "
                "using hardcoded fallback"
            )
            return None, "hardcoded-fallback"
        return pricing, str(fpath)
    except Exception as e:
        warnings.append(
            f"pricing.yaml parse error ({path}): {e}; using hardcoded fallback"
        )
        return None, "hardcoded-fallback"


# ── Model pricing lookup ───────────────────────────────────────────────────────

def _normalize_model_id(model_id):
    """Strip Claude Code bracket suffix (e.g., 'claude-sonnet-4-6[1m]' → 'claude-sonnet-4-6')."""
    if not model_id:
        return model_id
    return re.sub(r"\[.*?\]$", "", model_id)


def _get_prices(model_id, pricing_dict):
    """
    Return (input_per_1m, output_per_1m, cache_read_per_1m) for model_id.
    Returns None if model is unknown (both from pricing_dict and fallback).
    """
    if not model_id:
        return None

    norm = _normalize_model_id(model_id)

    # 1. Pricing dict (from YAML)
    if pricing_dict:
        for key in (model_id, norm):
            if key in pricing_dict:
                return pricing_dict[key]

    # 2. Hardcoded exact match
    for key in (model_id, norm):
        if key in _FALLBACK_EXACT:
            return _FALLBACK_EXACT[key]

    # 3. Hardcoded prefix match (longest-first order is already correct in _FALLBACK_PREFIX)
    norm_lower = (norm or "").lower()
    for prefix, prices in _FALLBACK_PREFIX:
        if norm_lower.startswith(prefix):
            return prices

    return None


def _cost_usd(usage, model_id, pricing_dict):
    """
    Compute approximate cost in USD for a single usage record.
    Returns None if model pricing is unknown.
    """
    prices = _get_prices(model_id, pricing_dict)
    if prices is None:
        return None
    inp_rate, out_rate, cr_rate = prices
    cost = (
        (usage.get("input",       0) or 0) * inp_rate / 1_000_000
        + (usage.get("output",    0) or 0) * out_rate / 1_000_000
        + (usage.get("cache_read",0) or 0) * cr_rate  / 1_000_000
    )
    return cost


# ── Timestamp helper ───────────────────────────────────────────────────────────

def _ts_ms(ts):
    """Parse ISO8601 timestamp to epoch milliseconds. Returns None on failure."""
    if not ts:
        return None
    try:
        t = ts.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(t)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError, AttributeError):
        return None


# ── P85 percentile (stdlib) ────────────────────────────────────────────────────

def _p85(values):
    """Return the 85th-percentile of a non-empty list. Returns None for empty."""
    if not values:
        return None
    sorted_v = sorted(values)
    idx = max(0, min(int(len(sorted_v) * 0.85), len(sorted_v) - 1))
    return sorted_v[idx]


# ── Wave detection ─────────────────────────────────────────────────────────────

def _detect_waves(records):
    """
    Heuristic wave detection.

    A wave starts when a main-attribution record has at least one tool_call
    with name == "Agent" (Claude Code sub-agent dispatch primitive). All
    subagent records following that dispatch — up to the next dispatch or EOF
    — belong to that wave.

    Returns: list of (wave_id: str, wave_records: list[dict])
             Empty list if no Agent dispatches are found.
    """
    # Sort by timestamp; records without timestamp maintain relative order at end.
    sorted_recs = sorted(
        records,
        key=lambda r: (r.get("timestamp") or "\xff" * 30),
    )

    waves = []
    current_wave_id = None
    current_wave_recs = []
    wave_counter = 0

    for rec in sorted_recs:
        if rec.get("attribution") == "main":
            has_dispatch = any(
                (tc.get("name") or "") in ("Agent", "Task", "SubAgent")
                for tc in (rec.get("tool_calls") or [])
            )
            if has_dispatch:
                # Flush previous wave if any.
                if current_wave_id is not None and current_wave_recs:
                    waves.append((current_wave_id, current_wave_recs))
                current_wave_id = f"wave-{wave_counter}"
                wave_counter += 1
                current_wave_recs = []
        else:
            # Subagent record — accumulate into open wave.
            if current_wave_id is not None:
                current_wave_recs.append(rec)

    # Flush last wave.
    if current_wave_id is not None and current_wave_recs:
        waves.append((current_wave_id, current_wave_recs))

    return waves


# ── Core aggregation ───────────────────────────────────────────────────────────

def _aggregate(data, pricing_dict, source_file, pricing_source):
    """
    Build all metric sections from the parse-transcript.py data dict.

    Args:
        data:           dict with "meta" and "records" keys.
        pricing_dict:   dict from _load_pricing, or None (use fallback only).
        source_file:    original file path string (for meta).
        pricing_source: label string for meta.

    Returns: (output_dict, warnings_list)
    """
    records = data.get("records") or []
    warnings = []

    # ── per_agent ──────────────────────────────────────────────────────────────
    # Key: (attribution, effective_agent_hash)
    # For main records agent_hash is null → normalise to the string "main".

    AgentBucket = lambda: {
        "attribution_agent": None,
        "tool_call_count": 0,
        "token_in": 0,
        "token_out": 0,
        "cache_read": 0,
        "cache_write": 0,
        "_cost_accum": 0.0,
        "_cost_null": False,
        "_elapsed_list": [],
        "models_used": set(),
        "stop_reason_distribution": collections.Counter(),
    }

    agent_buckets = collections.defaultdict(AgentBucket)

    for rec in records:
        attribution = rec.get("attribution") or "main"
        agent_hash  = rec.get("agent_hash") or "main"
        key = (attribution, agent_hash)

        usage = rec.get("usage")
        if not isinstance(usage, dict):
            warnings.append(
                f"record skipped: missing/invalid 'usage' "
                f"(attribution={attribution}, agent_hash={agent_hash})"
            )
            continue

        b = agent_buckets[key]

        # attribution_agent: capture first non-null value
        if b["attribution_agent"] is None and rec.get("attribution_agent"):
            b["attribution_agent"] = rec["attribution_agent"]

        b["tool_call_count"] += len(rec.get("tool_calls") or [])
        b["token_in"]        += int(usage.get("input",       0) or 0)
        b["token_out"]       += int(usage.get("output",      0) or 0)
        b["cache_read"]      += int(usage.get("cache_read",  0) or 0)
        b["cache_write"]     += int(usage.get("cache_write", 0) or 0)

        model = rec.get("model")
        if model:
            b["models_used"].add(model)

        cost = _cost_usd(usage, model, pricing_dict)
        if cost is None:
            b["_cost_null"] = True
        elif not b["_cost_null"]:
            b["_cost_accum"] += cost

        if rec.get("elapsed_ms") is not None:
            b["_elapsed_list"].append(rec["elapsed_ms"])

        if rec.get("stop_reason"):
            b["stop_reason_distribution"][rec["stop_reason"]] += 1

    # Track unknown models for session-level warnings
    unknown_models = set()
    for rec in records:
        model = rec.get("model")
        if model and _get_prices(model, pricing_dict) is None:
            unknown_models.add(model)
    for m in sorted(unknown_models):
        warnings.append(f"unknown model: {m}")

    per_agent = []
    for (attribution, agent_hash), b in agent_buckets.items():
        el = b["_elapsed_list"]
        per_agent.append({
            "attribution":              attribution,
            "agent_hash":               agent_hash,
            "attribution_agent":        b["attribution_agent"],
            "tool_call_count":          b["tool_call_count"],
            "token_in":                 b["token_in"],
            "token_out":                b["token_out"],
            "cache_read":               b["cache_read"],
            "cache_write":              b["cache_write"],
            "cost_usd_approx":          None if b["_cost_null"] else round(b["_cost_accum"], 6),
            "avg_elapsed_ms":           round(statistics.mean(el), 2) if el else None,
            "p85_elapsed_ms":           _p85(el),
            "models_used":              sorted(b["models_used"]),
            "stop_reason_distribution": dict(b["stop_reason_distribution"]),
        })

    # Sort: main first, then subagents by agent_hash.
    per_agent.sort(key=lambda a: (0 if a["attribution"] == "main" else 1, a["agent_hash"] or ""))

    # ── per_model ──────────────────────────────────────────────────────────────

    ModelBucket = lambda: {
        "call_count": 0,
        "token_in_total": 0,
        "token_out_total": 0,
        "_cost_accum": 0.0,
        "_cost_null": False,
    }

    model_buckets = collections.defaultdict(ModelBucket)

    for rec in records:
        model = rec.get("model")
        if not model:
            continue
        usage = rec.get("usage") or {}
        b = model_buckets[model]
        b["call_count"]      += 1
        b["token_in_total"]  += int(usage.get("input",  0) or 0)
        b["token_out_total"] += int(usage.get("output", 0) or 0)
        cost = _cost_usd(usage, model, pricing_dict)
        if cost is None:
            b["_cost_null"] = True
        elif not b["_cost_null"]:
            b["_cost_accum"] += cost

    per_model = []
    for model_id, b in model_buckets.items():
        per_model.append({
            "model":           model_id,
            "call_count":      b["call_count"],
            "token_in_total":  b["token_in_total"],
            "token_out_total": b["token_out_total"],
            "cost_usd_approx": None if b["_cost_null"] else round(b["_cost_accum"], 6),
        })
    per_model.sort(key=lambda m: m["call_count"], reverse=True)

    # ── per_wave ───────────────────────────────────────────────────────────────

    waves = _detect_waves(records)
    per_wave = []
    wave_efficiency_scores = []

    for wave_id, wave_recs in waves:
        # Group elapsed_ms by agent_hash to compute per-agent totals.
        elapsed_by_agent = collections.defaultdict(list)
        token_total = 0

        for rec in wave_recs:
            ah = rec.get("agent_hash") or "unknown"
            usage = rec.get("usage") or {}
            token_total += (
                int(usage.get("input",       0) or 0)
                + int(usage.get("output",    0) or 0)
                + int(usage.get("cache_read",0) or 0)
                + int(usage.get("cache_write",0) or 0)
            )
            if rec.get("elapsed_ms") is not None:
                elapsed_by_agent[ah].append(rec["elapsed_ms"])

        agent_count = len(elapsed_by_agent)
        # total_elapsed_ms: sum of all elapsed records in wave (proxy for wall time)
        all_elapsed = [v for vlist in elapsed_by_agent.values() for v in vlist]
        total_elapsed_ms = sum(all_elapsed)

        # parallel_factor: count of distinct agents dispatched (per spec)
        parallel_factor = float(agent_count)

        # Wave efficiency score (0..1, 1 = full parallelism):
        # Compute per-agent total elapsed, then:
        #   score = max_agent_elapsed / mean_agent_elapsed, capped at 1.0
        # Rationale: when agents take similar total time (parallel), max ≈ mean → score ≈ 1.
        # When one agent dominates (serial-like), max >> mean → score > 1 → capped at 1.
        # When agents differ widely (uneven load), score < 1.
        if agent_count > 0:
            agent_totals = [sum(vlist) for vlist in elapsed_by_agent.values()]
            max_et = max(agent_totals)
            mean_et = statistics.mean(agent_totals)
            if mean_et > 0:
                wave_score = min(1.0, max_et / mean_et)
            else:
                wave_score = 1.0
        else:
            wave_score = 1.0

        wave_efficiency_scores.append(wave_score)

        per_wave.append({
            "wave_id":          wave_id,
            "agent_count":      agent_count,
            "parallel_factor":  parallel_factor,
            "total_elapsed_ms": total_elapsed_ms,
            "token_total":      token_total,
        })

    # ── session_totals ─────────────────────────────────────────────────────────

    total_in = total_out = total_cr = total_cw = 0
    total_cost = 0.0
    cost_null = False
    ts_ms_list = []

    for rec in records:
        usage = rec.get("usage") or {}
        total_in  += int(usage.get("input",       0) or 0)
        total_out += int(usage.get("output",      0) or 0)
        total_cr  += int(usage.get("cache_read",  0) or 0)
        total_cw  += int(usage.get("cache_write", 0) or 0)

        model = rec.get("model")
        cost = _cost_usd(usage, model, pricing_dict)
        if cost is None:
            cost_null = True
        else:
            total_cost += cost

        ts = _ts_ms(rec.get("timestamp"))
        if ts is not None:
            ts_ms_list.append(ts)

    session_duration_ms = (max(ts_ms_list) - min(ts_ms_list)) if len(ts_ms_list) >= 2 else 0

    distinct_agents = len(set(
        (r.get("attribution") or "main", r.get("agent_hash") or "main")
        for r in records
    ))

    session_totals = {
        "total_token_in":    total_in,
        "total_token_out":   total_out,
        "total_cache_read":  total_cr,
        "total_cache_write": total_cw,
        "total_cost_approx": None if cost_null else round(total_cost, 6),
        "session_duration_ms": session_duration_ms,
        "agent_count":       distinct_agents,
        "record_count":      len(records),
        "wave_count":        len(per_wave),
    }

    # ── dispatch_efficiency ────────────────────────────────────────────────────
    # Aggregate score = mean of per-wave scores.
    # Score of 0.0 when no waves detected (cannot evaluate).

    if wave_efficiency_scores:
        overall_score = statistics.mean(wave_efficiency_scores)
    else:
        overall_score = 0.0

    dispatch_efficiency = {
        "score": round(overall_score, 4),
        "waves_analyzed": len(wave_efficiency_scores),
        "notes": [
            (
                "heuristic: wave = cluster of subagent records following a main-record "
                "Agent tool_call; score = mean(max_agent_elapsed / mean_agent_elapsed) "
                "per wave, capped at 1.0; 1.0 = agents took equal time (full parallelism), "
                "<1.0 = uneven load (partial serialization)"
            )
        ],
    }

    return {
        "per_agent":           per_agent,
        "per_model":           per_model,
        "per_wave":            per_wave,
        "session_totals":      session_totals,
        "dispatch_efficiency": dispatch_efficiency,
    }, warnings


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=(
            "fleet-metrics.py — EP-061/US-244/TSK-553. "
            "Aggregation rollup (per_agent / per_model / per_wave / "
            "session_totals / dispatch_efficiency) from parse-transcript.py output."
        ),
    )
    ap.add_argument(
        "parsed_json_file",
        help=(
            "JSON file produced by parse-transcript.py (format: {meta, records}). "
            "Use '-' to read from stdin."
        ),
    )
    ap.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Write JSON output to FILE instead of stdout.",
    )
    ap.add_argument(
        "--pricing",
        default=None,
        metavar="FILE",
        help=(
            "Path to analytics/pricing.yaml. "
            "Auto-discovery at <repo-root>/analytics/pricing.yaml when omitted. "
            "Falls back to hardcoded prices if file not found or unparseable."
        ),
    )
    args = ap.parse_args()

    # ── Load input JSON ─────────────────────────────────────────────────────────
    src = args.parsed_json_file
    try:
        if src == "-":
            raw = sys.stdin.read()
        else:
            raw = pathlib.Path(src).read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR: cannot read input file: {e}", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: malformed JSON input: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict) or "records" not in data:
        print(
            "ERROR: input JSON must have a top-level 'records' key "
            "(expected parse-transcript.py output format: {meta, records})",
            file=sys.stderr,
        )
        return 1

    # ── Resolve pricing path ────────────────────────────────────────────────────
    pricing_path = args.pricing
    if pricing_path is None:
        repo_root = _find_repo_root()
        candidate = repo_root / "analytics" / "pricing.yaml"
        if candidate.exists():
            pricing_path = str(candidate)

    # ── Load pricing ────────────────────────────────────────────────────────────
    load_warnings = []
    pricing_dict, pricing_source = _load_pricing(pricing_path, load_warnings)

    # ── Aggregate ───────────────────────────────────────────────────────────────
    result, agg_warnings = _aggregate(data, pricing_dict, src, pricing_source)
    all_warnings = load_warnings + agg_warnings

    # ── Build output ────────────────────────────────────────────────────────────
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = {
        "meta": {
            "source_file":    src,
            "generated_at":   now_iso,
            "pricing_source": pricing_source,
            "warnings":       all_warnings,
        },
        **result,
    }

    json_str = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        out_path = pathlib.Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_str, encoding="utf-8")
        print(f"Output written to: {out_path}", file=sys.stderr)
    else:
        print(json_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
