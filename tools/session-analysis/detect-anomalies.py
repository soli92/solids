#!/usr/bin/env python3
"""
detect-anomalies.py — EP-061/US-244/TSK-554
Deterministic anomaly detection on parse-transcript.py + fleet-metrics.py output.

Decision on PA-R3-4 (scope tassonomia aperto):
  Implementa le 3 categorie core (ERROR, BUDGET, DISPATCH) enabled by default.
  LATENCY e FLEET sono opzionali (--enable-latency / --enable-fleet), documentate
  come roadmap v2 in attesa di dati reali per calibrazione signal/noise ratio
  (>3 anomalie azionabili per 20 sessioni, kill criterion EP-061).
  Le categorie SAA-V / SAA-C / SAA-G / SAA-O / SAA-S non sono implementate (roadmap v2).

Invarianti:
  R-SAA-7 (anti-fabbricazione): ogni anomalia DEVE avere `provenance` valorizzato
    con source_field e source_file. Se una regola non riesce a citare la fonte
    → skip anomalia (fail-loud su stderr, no anomalia fabbricata).
  R-SAA-3 (redazione): evidence_excerpt cap 200 caratteri con marker [TRUNCATED];
    path anonymization /Users/<name>/ → /Users/USER/; strip credenziali (sk-*, Bearer *).
  R-SAA-6 (no auto-fix): fix_suggestion è solo testo. Nessun campo auto_apply.

CLI:
  python3 detect-anomalies.py <parsed-json> <metrics-json>
          [--output <file>]
          [--schema <schema-path>]
          [--enable-latency]
          [--enable-fleet]
          [--budget-max-usd <F>]

Args:
  parsed-json      (obbligatorio): JSON prodotto da parse-transcript.py
  metrics-json     (obbligatorio): JSON prodotto da fleet-metrics.py
  --output         : file di output JSON (default: stdout)
  --schema         : path a schema-anomaly.json (validazione output, TSK-555 — TBD)
  --enable-latency : attiva rilevatore LATENCY (default off, roadmap v2)
  --enable-fleet   : attiva rilevatore FLEET (default off, roadmap v2)
  --budget-max-usd : override soglia BUDGET (default: auto-discovery factory.config.yaml
                     budget.max_cost_usd, fallback hardcoded 5.00)

stdlib-only: json, re, pathlib, sys, argparse, datetime, collections, statistics, os
"""

import sys
import json
import re
import pathlib
import argparse
import datetime
import collections
import statistics
import os

# ── Constants ─────────────────────────────────────────────────────────────────

_DEFAULT_BUDGET_MAX_USD = 5.0

# Tier-deep model prefix patterns (TIER_MISMATCH detector).
# Convention from factory.config.yaml: tier_deep = claude-opus-*
_TIER_DEEP_PREFIXES = ("claude-opus",)

# Token output threshold below which a tier_deep usage is suspicious.
_TIER_DEEP_MIN_TOKEN_OUT = 500

# ERROR_LOOP: minimum consecutive error stop_reasons to flag.
_ERROR_LOOP_MIN_CONSECUTIVE = 3

# Regex to detect error-style stop_reason text (NOT the is_error flag — always 0).
_ERROR_TEXT_RE = re.compile(r"(?i)error|failed|fatal")

# DISPATCH_REDUNDANT: same agent invoked > N times consecutively as fallback heuristic.
_DISPATCH_CONSECUTIVE_THRESHOLD = 3

# DISPATCH_REDUNDANT: same agent_hash invoked > N times in same wave for same resource.
_DISPATCH_WAVE_THRESHOLD = 2

# SERIAL_WHEN_PARALLEL: efficiency score below which serialization is flagged.
_SERIAL_SCORE_THRESHOLD = 0.5

# R-SAA-3 redaction patterns.
_PATH_RE = re.compile(r"/Users/[^/\s]+/")
_CRED_RE = re.compile(
    r"(sk-[A-Za-z0-9-]+|Bearer\s+[A-Za-z0-9._-]+|[A-Z_]{2,}_TOKEN=[^\s&\"']*|\.env(?=[\s/\"']|$))"
)

# Evidence excerpt max length (R-SAA-3).
_EVIDENCE_MAX_CHARS = 200


# ── Helpers ───────────────────────────────────────────────────────────────────

def _redact(s):
    """Apply R-SAA-3 redaction to a string (path anonymization + credential strip)."""
    if not isinstance(s, str):
        return str(s) if s is not None else ""
    s = _PATH_RE.sub("/Users/USER/", s)
    s = _CRED_RE.sub("[REDACTED]", s)
    return s


def _cap_evidence(s):
    """Cap evidence string at 200 chars with [TRUNCATED] marker (R-SAA-3)."""
    s = _redact(s)
    if len(s) > _EVIDENCE_MAX_CHARS:
        s = s[:_EVIDENCE_MAX_CHARS] + "[TRUNCATED]"
    return s


def _is_tier_deep(model_id):
    """Return True if model_id matches a tier_deep (opus) pattern."""
    if not model_id:
        return False
    norm = model_id.lower()
    # Strip bracket suffix (e.g. 'claude-opus-4-8[1m]' → 'claude-opus-4-8')
    norm = re.sub(r"\[.*?\]$", "", norm)
    return any(norm.startswith(p) for p in _TIER_DEEP_PREFIXES)


def _ano_id(counter):
    """Return formatted anomaly ID: ANO-NNN."""
    return f"ANO-{counter:03d}"


def _find_repo_root():
    """Walk up from this script to find factory repo root (factory.config.yaml)."""
    here = pathlib.Path(__file__).resolve().parent
    for candidate in (here, here.parent, here.parent.parent, here.parent.parent.parent):
        if (candidate / "factory.config.yaml").exists():
            return candidate
    return here.parent.parent


def _read_budget_from_config():
    """
    Try to read budget.max_cost_usd from factory.config.yaml using simple line scan.
    Returns float or None on failure.
    """
    repo_root = _find_repo_root()
    config_path = repo_root / "factory.config.yaml"
    if not config_path.exists():
        return None
    try:
        text = config_path.read_text(encoding="utf-8")
        # Look for top-level `budget:` block then `max_cost_usd:` within it.
        # Simple approach: find `max_cost_usd:` at any indentation level and take first numeric.
        for line in text.splitlines():
            m = re.match(r"\s*max_cost_usd:\s*([\d.]+)", line)
            if m:
                return float(m.group(1))
    except Exception:
        pass
    return None


def _detect_waves_from_records(records):
    """
    Re-implement heuristic wave detection (mirrors fleet-metrics.py logic).
    Returns list of (wave_id, wave_records).
    """
    sorted_recs = sorted(records, key=lambda r: (r.get("timestamp") or "\xff" * 30))
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
                if current_wave_id is not None and current_wave_recs:
                    waves.append((current_wave_id, current_wave_recs))
                current_wave_id = f"wave-{wave_counter}"
                wave_counter += 1
                current_wave_recs = []
        else:
            if current_wave_id is not None:
                current_wave_recs.append(rec)

    if current_wave_id is not None and current_wave_recs:
        waves.append((current_wave_id, current_wave_recs))

    return waves


# ── Anomaly detectors ─────────────────────────────────────────────────────────

def _detect_error_loop(records, source_parsed, warnings):
    """
    ERROR_LOOP: stop_reason matching error pattern repeated ≥3 times consecutive
    for same (attribution, agent_hash). Does NOT use is_error flag (always 0).

    Returns list of anomaly dicts (without id, filled later).
    """
    anomalies = []

    # Sort records by timestamp for sequential analysis.
    sorted_recs = sorted(records, key=lambda r: (r.get("timestamp") or "\xff" * 30))

    # Group by (attribution, agent_hash) and look for consecutive error stop_reasons.
    # We iterate over all records in time order and maintain per-agent run-length encoding.
    agent_streaks = collections.defaultdict(lambda: {"count": 0, "timestamps": [], "reasons": []})

    for rec in sorted_recs:
        attribution = rec.get("attribution") or "main"
        agent_hash = rec.get("agent_hash") or "main"
        key = (attribution, agent_hash)
        stop_reason = rec.get("stop_reason") or ""

        is_error_stop = bool(_ERROR_TEXT_RE.search(stop_reason))

        b = agent_streaks[key]
        if is_error_stop:
            b["count"] += 1
            b["timestamps"].append(rec.get("timestamp", ""))
            b["reasons"].append(stop_reason)
        else:
            # Flush streak: if reached threshold, emit anomaly.
            if b["count"] >= _ERROR_LOOP_MIN_CONSECUTIVE:
                ts_list = b["timestamps"][:_ERROR_LOOP_MIN_CONSECUTIVE]
                reason_sample = b["reasons"][0]
                evidence_raw = (
                    f"stop_reason='{reason_sample}' repeated {b['count']}x consecutive "
                    f"(timestamps: {ts_list})"
                )
                anomalies.append({
                    "category": "ERROR",
                    "subtype": "ERROR_LOOP",
                    "severity": "critical",
                    "wave_id": None,
                    "agent_hash": agent_hash if agent_hash != "main" else None,
                    "attribution_agent": rec.get("attribution_agent"),
                    "description": (
                        f"Error stop_reason repeated {b['count']} consecutive times "
                        f"for agent {agent_hash}"
                    ),
                    "evidence_excerpt": _cap_evidence(evidence_raw),
                    "evidence_count": b["count"],
                    "fix_suggestion": (
                        f"Investiga circuit breaker per agent {agent_hash}; "
                        "verifica se skill o tool sta fallendo ripetutamente"
                    ),
                    "pattern_eligible": True,
                    "provenance": {
                        "source_field": "records[].stop_reason (regex match error|failed|fatal)",
                        "source_file": "parsed",
                    },
                })
            # Reset streak.
            b["count"] = 0
            b["timestamps"] = []
            b["reasons"] = []

    # Final flush.
    for (attribution, agent_hash), b in agent_streaks.items():
        if b["count"] >= _ERROR_LOOP_MIN_CONSECUTIVE:
            ts_list = b["timestamps"][:_ERROR_LOOP_MIN_CONSECUTIVE]
            reason_sample = b["reasons"][0]
            evidence_raw = (
                f"stop_reason='{reason_sample}' repeated {b['count']}x consecutive "
                f"(timestamps: {ts_list})"
            )
            anomalies.append({
                "category": "ERROR",
                "subtype": "ERROR_LOOP",
                "severity": "critical",
                "wave_id": None,
                "agent_hash": agent_hash if agent_hash != "main" else None,
                "attribution_agent": None,
                "description": (
                    f"Error stop_reason repeated {b['count']} consecutive times "
                    f"for agent {agent_hash}"
                ),
                "evidence_excerpt": _cap_evidence(evidence_raw),
                "evidence_count": b["count"],
                "fix_suggestion": (
                    f"Investiga circuit breaker per agent {agent_hash}; "
                    "verifica se skill o tool sta fallendo ripetutamente"
                ),
                "pattern_eligible": True,
                "provenance": {
                    "source_field": "records[].stop_reason (regex match error|failed|fatal)",
                    "source_file": "parsed",
                },
            })

    return anomalies


def _detect_budget(session_totals, per_agent, budget_max_usd, warnings):
    """
    BUDGET_OVERFLOW: total_cost_approx >= budget_max_usd → CRITICAL.
    TIER_MISMATCH: agent on tier_deep model with token_out < 500 → WARNING.

    Returns list of anomaly dicts (without id, filled later).
    """
    anomalies = []

    # BUDGET_OVERFLOW
    total_cost = session_totals.get("total_cost_approx")
    if total_cost is None:
        warnings.append(
            "BUDGET check skipped: session_totals.total_cost_approx is null "
            "(unknown model pricing)"
        )
    else:
        # Provenance is clear: total_cost_approx field from session_totals.
        severity = "critical" if total_cost >= budget_max_usd else "warning"
        if total_cost >= budget_max_usd:
            evidence_raw = (
                f"total_cost_approx={total_cost:.6f} USD >= "
                f"budget_max_usd={budget_max_usd:.2f} USD"
            )
            anomalies.append({
                "category": "BUDGET",
                "subtype": "BUDGET_OVERFLOW",
                "severity": "critical",
                "wave_id": None,
                "agent_hash": None,
                "attribution_agent": None,
                "description": (
                    f"Session cost {total_cost:.4f} USD exceeds budget cap "
                    f"{budget_max_usd:.2f} USD"
                ),
                "evidence_excerpt": _cap_evidence(evidence_raw),
                "evidence_count": 1,
                "fix_suggestion": (
                    "Analizza la distribuzione costi per agente (metrics per_agent.cost_usd_approx); "
                    "considera di abbassare il tier o ridurre il numero di invocazioni"
                ),
                "pattern_eligible": True,
                "provenance": {
                    "source_field": f"session_totals.total_cost_approx: {total_cost:.6f} >= threshold {budget_max_usd:.2f}",
                    "source_file": "metrics",
                },
            })

    # TIER_MISMATCH: agente su modello tier_deep con token_out < 500 totale.
    for agent in per_agent:
        models_used = agent.get("models_used") or []
        token_out = agent.get("token_out") or 0
        agent_hash = agent.get("agent_hash")
        attribution_agent = agent.get("attribution_agent")

        tier_deep_models = [m for m in models_used if _is_tier_deep(m)]
        if tier_deep_models and token_out < _TIER_DEEP_MIN_TOKEN_OUT:
            model_list = ", ".join(tier_deep_models)
            evidence_raw = (
                f"agent_hash={agent_hash} attribution={attribution_agent} "
                f"models={model_list} token_out={token_out} < {_TIER_DEEP_MIN_TOKEN_OUT}"
            )
            anomalies.append({
                "category": "BUDGET",
                "subtype": "TIER_MISMATCH",
                "severity": "warning",
                "wave_id": None,
                "agent_hash": agent_hash,
                "attribution_agent": attribution_agent,
                "description": (
                    f"Agent {agent_hash or attribution_agent} uses tier_deep model "
                    f"({model_list}) but produced only {token_out} output tokens "
                    f"(< {_TIER_DEEP_MIN_TOKEN_OUT} threshold): possible tier overspend"
                ),
                "evidence_excerpt": _cap_evidence(evidence_raw),
                "evidence_count": 1,
                "fix_suggestion": (
                    f"Ridurre tier per agent {agent_hash}; "
                    "migrare a claude-haiku-4-5 per task piccoli con output ridotto"
                ),
                "pattern_eligible": True,
                "provenance": {
                    "source_field": (
                        f"per_agent[agent_hash={agent_hash}].models_used={tier_deep_models}, "
                        f"per_agent[agent_hash={agent_hash}].token_out={token_out}"
                    ),
                    "source_file": "metrics",
                },
            })

    return anomalies


def _detect_dispatch(records, per_wave, dispatch_efficiency, warnings):
    """
    DISPATCH_REDUNDANT: same attribution_agent dispatched redundantly.
      Primary: same attribution_agent dispatched >2 times as distinct agent_hash instances
               within the same wave (multiple concurrent spawns of same agent type in one wave).
      Fallback: same attribution_agent dispatched >3 times as distinct agent_hash instances
               across the whole session (repeated across waves — heuristic, may include
               legitimate sequential use; raises warning, not critical).
    SERIAL_WHEN_PARALLEL: dispatch_efficiency.score < 0.5 and >= 1 wave with agent_count >= 2.

    Note on record count vs dispatch count:
      Each subagent record = one tool_use turn of a running agent instance (same agent_hash).
      Dispatch redundancy = multiple distinct agent_hash instances of the same attribution_agent.
      Record count per agent_hash is NOT used for DISPATCH_REDUNDANT — only distinct hash count.

    Returns list of anomaly dicts (without id, filled later).
    """
    anomalies = []

    # Build waves from records (same logic as fleet-metrics.py).
    waves = _detect_waves_from_records(records)

    # DISPATCH_REDUNDANT — Primary heuristic:
    # Multiple distinct agent_hash instances of same attribution_agent within same wave.
    for wave_id, wave_recs in waves:
        # Map: attribution_agent → set of distinct agent_hash in this wave.
        ag_to_hashes = collections.defaultdict(set)
        for rec in wave_recs:
            ag = rec.get("attribution_agent")
            ah = rec.get("agent_hash")
            if ag and ah:
                ag_to_hashes[ag].add(ah)

        for ag_name, hashes in ag_to_hashes.items():
            if len(hashes) > _DISPATCH_WAVE_THRESHOLD:
                evidence_raw = (
                    f"wave_id={wave_id} attribution_agent={ag_name} "
                    f"distinct_dispatches={len(hashes)} hashes={sorted(hashes)}"
                )
                anomalies.append({
                    "category": "DISPATCH",
                    "subtype": "DISPATCH_REDUNDANT",
                    "severity": "warning",
                    "wave_id": wave_id,
                    "agent_hash": None,
                    "attribution_agent": ag_name,
                    "description": (
                        f"Agent '{ag_name}' dispatched {len(hashes)} distinct instances "
                        f"in {wave_id} (soglia: {_DISPATCH_WAVE_THRESHOLD}): "
                        "possibile ridondanza intra-wave"
                    ),
                    "evidence_excerpt": _cap_evidence(evidence_raw),
                    "evidence_count": len(hashes),
                    "fix_suggestion": (
                        "Verifica se questo dispatch è idempotente; "
                        "consolida invocazioni o parallelizza per ridurre ridondanza"
                    ),
                    "pattern_eligible": True,
                    "provenance": {
                        "source_field": (
                            f"records[wave={wave_id}].attribution_agent={ag_name} "
                            f"distinct agent_hash count={len(hashes)} "
                            f"(threshold={_DISPATCH_WAVE_THRESHOLD})"
                        ),
                        "source_file": "parsed",
                    },
                })

    # DISPATCH_REDUNDANT — Fallback: same attribution_agent dispatched > threshold times
    # as distinct agent_hash instances across whole session.
    agent_name_to_hashes = collections.defaultdict(set)
    for rec in records:
        if rec.get("attribution") == "subagent":
            ag = rec.get("attribution_agent")
            ah = rec.get("agent_hash")
            if ag and ah:
                agent_name_to_hashes[ag].add(ah)

    for ag_name, hashes in agent_name_to_hashes.items():
        if len(hashes) > _DISPATCH_CONSECUTIVE_THRESHOLD:
            evidence_raw = (
                f"attribution_agent={ag_name} dispatched as {len(hashes)} distinct "
                f"agent_hash instances across session: {sorted(hashes)}"
            )
            anomalies.append({
                "category": "DISPATCH",
                "subtype": "DISPATCH_REDUNDANT",
                "severity": "warning",
                "wave_id": None,
                "agent_hash": None,
                "attribution_agent": ag_name,
                "description": (
                    f"Agent '{ag_name}' dispatched {len(hashes)} distinct instances "
                    f"across the whole session (soglia: {_DISPATCH_CONSECUTIVE_THRESHOLD}): "
                    "pattern ripetuto, potenziale ridondanza"
                ),
                "evidence_excerpt": _cap_evidence(evidence_raw),
                "evidence_count": len(hashes),
                "fix_suggestion": (
                    "Verifica se le invocazioni successive possono essere consolidate; "
                    "considera se il task è divisibile in subtask indipendenti parallelizzabili"
                ),
                "pattern_eligible": True,
                "provenance": {
                    "source_field": (
                        f"records[].attribution_agent={ag_name} "
                        f"distinct agent_hash count={len(hashes)} "
                        f"(threshold={_DISPATCH_CONSECUTIVE_THRESHOLD})"
                    ),
                    "source_file": "parsed",
                },
            })

    # SERIAL_WHEN_PARALLEL: session-level score < 0.5 AND at least one wave with agent_count >= 2.
    eff_score = dispatch_efficiency.get("score")
    if eff_score is not None and eff_score < _SERIAL_SCORE_THRESHOLD:
        wave_with_multiple = [w for w in per_wave if w.get("agent_count", 0) >= 2]
        if wave_with_multiple:
            wave_ids = [w["wave_id"] for w in wave_with_multiple]
            evidence_raw = (
                f"dispatch_efficiency.score={eff_score:.4f} < {_SERIAL_SCORE_THRESHOLD} "
                f"(waves with agent_count>=2: {wave_ids})"
            )
            anomalies.append({
                "category": "DISPATCH",
                "subtype": "SERIAL_WHEN_PARALLEL",
                "severity": "warning",
                "wave_id": ", ".join(wave_ids),
                "agent_hash": None,
                "attribution_agent": None,
                "description": (
                    f"Bassa efficienza di dispatch (score={eff_score:.4f}) con "
                    f"{len(wave_with_multiple)} wave parallelizzabili: "
                    "agenti eseguiti serialmente nonostante indipendenza"
                ),
                "evidence_excerpt": _cap_evidence(evidence_raw),
                "evidence_count": len(wave_with_multiple),
                "fix_suggestion": (
                    "Verifica le dipendenze tra gli agenti nelle wave; "
                    "usa parallel scheduling (scheduler.enabled: true) "
                    "e assicurati che i TSK non abbiano code_path_conflict"
                ),
                "pattern_eligible": True,
                "provenance": {
                    "source_field": f"dispatch_efficiency.score={eff_score:.4f}",
                    "source_file": "metrics",
                },
            })

    return anomalies


def _detect_latency(per_agent, warnings):
    """
    STRAGGLER (LATENCY, opt-in): agent with p85_elapsed_ms > 2× median per attribution_agent type.

    Returns list of anomaly dicts.
    Roadmap v2: requires signal calibration with real fixtures.
    """
    anomalies = []

    # Group p85 values by attribution_agent.
    by_agent_type = collections.defaultdict(list)
    for agent in per_agent:
        ag_type = agent.get("attribution_agent") or agent.get("attribution") or "main"
        p85 = agent.get("p85_elapsed_ms")
        if p85 is not None and p85 > 0:
            by_agent_type[ag_type].append((agent, p85))

    for ag_type, entries in by_agent_type.items():
        if len(entries) < 2:
            continue  # Need at least 2 to compare.
        p85_values = [p85 for _, p85 in entries]
        median_p85 = statistics.median(p85_values)
        if median_p85 <= 0:
            continue
        threshold = 2.0 * median_p85
        for agent, p85 in entries:
            if p85 > threshold:
                ah = agent.get("agent_hash")
                evidence_raw = (
                    f"agent_hash={ah} attribution_agent={ag_type} "
                    f"p85_elapsed_ms={p85} > 2×median({median_p85:.0f}) = {threshold:.0f}"
                )
                anomalies.append({
                    "category": "LATENCY",
                    "subtype": "STRAGGLER",
                    "severity": "warning",
                    "wave_id": None,
                    "agent_hash": ah,
                    "attribution_agent": ag_type,
                    "description": (
                        f"Agent {ah} ({ag_type}) p85 elapsed {p85}ms > "
                        f"2× median {median_p85:.0f}ms ({threshold:.0f}ms): straggler"
                    ),
                    "evidence_excerpt": _cap_evidence(evidence_raw),
                    "evidence_count": 1,
                    "fix_suggestion": (
                        f"Analizza tool_call_count e token volume per agent {ah}; "
                        "verifica se il task è divisibile o se il tool ha alta latenza I/O"
                    ),
                    "pattern_eligible": True,
                    "provenance": {
                        "source_field": (
                            f"per_agent[agent_hash={ah}].p85_elapsed_ms={p85} vs "
                            f"median per {ag_type}={median_p85:.0f}"
                        ),
                        "source_file": "metrics",
                    },
                })

    return anomalies


def _detect_fleet(records, warnings):
    """
    SKILL_NOT_FOUND (FLEET, opt-in): skill referenced in Agent tool_call description
    not found in .claude/skills/<name>.md.

    Returns list of anomaly dicts.
    Roadmap v2: requires signal calibration with real fixtures.
    """
    anomalies = []

    # Find repo root and skills directory.
    repo_root = _find_repo_root()
    skills_dir = repo_root / ".claude" / "skills"

    if not skills_dir.is_dir():
        warnings.append(
            f"FLEET check: .claude/skills/ not found at {skills_dir}; "
            "SKILL_NOT_FOUND detector skipped"
        )
        return anomalies

    # Enumerate available skill names (stem of .md files).
    available_skills = {p.stem for p in skills_dir.glob("*.md")}

    # Regex to match skill-like identifiers in tool_call descriptions.
    # Pattern: kebab-case identifiers that look like skill names (e.g., session-analysis-protocol).
    _SKILL_REF_RE = re.compile(r"\b([a-z][a-z0-9-]{3,}(?:-protocol|-skill|-handoff|-checks))\b")

    seen_missing = set()

    for rec in records:
        for tc in rec.get("tool_calls") or []:
            if tc.get("name") not in ("Agent", "Task", "SubAgent"):
                continue
            description = tc.get("description") or ""
            if not description:
                continue
            for m in _SKILL_REF_RE.finditer(description):
                skill_name = m.group(1)
                if skill_name not in available_skills and skill_name not in seen_missing:
                    seen_missing.add(skill_name)
                    ah = rec.get("agent_hash")
                    attribution_agent = rec.get("attribution_agent")
                    evidence_raw = (
                        f"skill_ref='{skill_name}' cited in Agent tool_call "
                        f"by agent_hash={ah} ({attribution_agent}) — "
                        f"not found in .claude/skills/"
                    )
                    anomalies.append({
                        "category": "FLEET",
                        "subtype": "SKILL_NOT_FOUND",
                        "severity": "warning",
                        "wave_id": None,
                        "agent_hash": ah,
                        "attribution_agent": attribution_agent,
                        "description": (
                            f"Skill '{skill_name}' referenced in agent dispatch "
                            f"but not found in .claude/skills/{skill_name}.md"
                        ),
                        "evidence_excerpt": _cap_evidence(evidence_raw),
                        "evidence_count": 1,
                        "fix_suggestion": (
                            f"Verifica se la skill '{skill_name}' esiste nel percorso "
                            ".claude/skills/; crea il file skill o correggi il riferimento "
                            "nell'agent prompt"
                        ),
                        "pattern_eligible": True,
                        "provenance": {
                            "source_field": (
                                f"records[agent_hash={ah}].tool_calls[name=Agent].description "
                                f"(skill ref: '{skill_name}')"
                            ),
                            "source_file": "parsed",
                        },
                    })

    return anomalies


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_anomalies(anomalies, warnings):
    """
    R-SAA-7: ensure every anomaly has provenance. Remove violators with stderr warning.
    R-SAA-6: ensure no auto_apply field.
    """
    valid = []
    for ano in anomalies:
        prov = ano.get("provenance")
        if not prov or not prov.get("source_field") or not prov.get("source_file"):
            msg = (
                f"[WARN R-SAA-7] Anomaly skipped (missing provenance): "
                f"category={ano.get('category')} subtype={ano.get('subtype')}"
            )
            print(msg, file=sys.stderr)
            warnings.append(msg)
            continue
        # R-SAA-6: no auto-apply fields allowed.
        if "auto_apply" in ano:
            del ano["auto_apply"]
        # Ensure evidence_excerpt is capped (already done at generation, double-check).
        exc = ano.get("evidence_excerpt", "")
        if len(exc) > _EVIDENCE_MAX_CHARS + len("[TRUNCATED]"):
            ano["evidence_excerpt"] = exc[:_EVIDENCE_MAX_CHARS] + "[TRUNCATED]"
        valid.append(ano)
    return valid


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=(
            "detect-anomalies.py — EP-061/US-244/TSK-554. "
            "Deterministic anomaly detection (ERROR/BUDGET/DISPATCH core; "
            "LATENCY/FLEET opt-in roadmap v2) on parse-transcript.py + "
            "fleet-metrics.py output. stdlib-only, no LLM calls."
        )
    )
    ap.add_argument(
        "parsed_json",
        help="JSON file produced by parse-transcript.py ({meta, records}).",
    )
    ap.add_argument(
        "metrics_json",
        help="JSON file produced by fleet-metrics.py ({meta, per_agent, ...}).",
    )
    ap.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Write JSON output to FILE instead of stdout.",
    )
    ap.add_argument(
        "--schema",
        default=None,
        metavar="SCHEMA",
        help="Path to schema-anomaly.json for output validation (TSK-555, TBD; currently ignored).",
    )
    ap.add_argument(
        "--enable-latency",
        action="store_true",
        default=False,
        help=(
            "Activate LATENCY detector (STRAGGLER rule). "
            "Default off — roadmap v2, needs signal calibration "
            "(>3 actionable anomalies per 20 sessions, per EP-061 kill criterion)."
        ),
    )
    ap.add_argument(
        "--enable-fleet",
        action="store_true",
        default=False,
        help=(
            "Activate FLEET detector (SKILL_NOT_FOUND rule). "
            "Default off — roadmap v2, needs signal calibration."
        ),
    )
    ap.add_argument(
        "--budget-max-usd",
        type=float,
        default=None,
        metavar="F",
        help=(
            "Override BUDGET threshold in USD. "
            "Default: auto-discovery from factory.config.yaml budget.max_cost_usd, "
            f"fallback {_DEFAULT_BUDGET_MAX_USD:.2f}."
        ),
    )
    args = ap.parse_args()

    # ── Resolve budget threshold ────────────────────────────────────────────────
    if args.budget_max_usd is not None:
        budget_max_usd = args.budget_max_usd
        budget_source = f"--budget-max-usd CLI override"
    else:
        discovered = _read_budget_from_config()
        if discovered is not None:
            budget_max_usd = discovered
            budget_source = "factory.config.yaml (budget.max_cost_usd)"
        else:
            budget_max_usd = _DEFAULT_BUDGET_MAX_USD
            budget_source = f"hardcoded default {_DEFAULT_BUDGET_MAX_USD}"

    # ── Load inputs ─────────────────────────────────────────────────────────────
    errors = []
    try:
        parsed_raw = pathlib.Path(args.parsed_json).read_text(encoding="utf-8")
        parsed_data = json.loads(parsed_raw)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read/parse parsed-json: {e}", file=sys.stderr)
        return 1

    try:
        metrics_raw = pathlib.Path(args.metrics_json).read_text(encoding="utf-8")
        metrics_data = json.loads(metrics_raw)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read/parse metrics-json: {e}", file=sys.stderr)
        return 1

    if "records" not in parsed_data:
        print(
            "ERROR: parsed-json must have a 'records' key "
            "(expected parse-transcript.py output)",
            file=sys.stderr,
        )
        return 1

    records = parsed_data.get("records") or []
    session_totals = metrics_data.get("session_totals") or {}
    per_agent = metrics_data.get("per_agent") or []
    per_wave = metrics_data.get("per_wave") or []
    dispatch_efficiency = metrics_data.get("dispatch_efficiency") or {}

    # ── Run detectors ───────────────────────────────────────────────────────────
    run_warnings = []

    categories_enabled = ["ERROR", "BUDGET", "DISPATCH"]
    categories_disabled_reason = {
        "LATENCY": (
            "opt-in --enable-latency (roadmap v2: needs signal calibration "
            ">3 actionable anomalies per 20 sessions, per EP-061 kill criterion)"
        ),
        "FLEET": (
            "opt-in --enable-fleet (roadmap v2: needs signal calibration "
            ">3 actionable anomalies per 20 sessions, per EP-061 kill criterion)"
        ),
    }

    all_anomalies = []

    # ERROR
    all_anomalies.extend(_detect_error_loop(records, args.parsed_json, run_warnings))

    # BUDGET
    all_anomalies.extend(
        _detect_budget(session_totals, per_agent, budget_max_usd, run_warnings)
    )

    # DISPATCH
    all_anomalies.extend(
        _detect_dispatch(records, per_wave, dispatch_efficiency, run_warnings)
    )

    # LATENCY (opt-in)
    if args.enable_latency:
        categories_enabled.append("LATENCY")
        del categories_disabled_reason["LATENCY"]
        all_anomalies.extend(_detect_latency(per_agent, run_warnings))

    # FLEET (opt-in)
    if args.enable_fleet:
        categories_enabled.append("FLEET")
        del categories_disabled_reason["FLEET"]
        all_anomalies.extend(_detect_fleet(records, run_warnings))

    # ── R-SAA-7 validation: strip anomalies without provenance ─────────────────
    all_anomalies = _validate_anomalies(all_anomalies, run_warnings)

    # ── Assign IDs ──────────────────────────────────────────────────────────────
    for i, ano in enumerate(all_anomalies, start=1):
        ano["id"] = _ano_id(i)

    # Re-order fields to match spec output format.
    ordered_anomalies = []
    for ano in all_anomalies:
        ordered_anomalies.append({
            "id": ano.get("id"),
            "category": ano.get("category"),
            "subtype": ano.get("subtype"),
            "severity": ano.get("severity"),
            "wave_id": ano.get("wave_id"),
            "agent_hash": ano.get("agent_hash"),
            "attribution_agent": ano.get("attribution_agent"),
            "description": ano.get("description"),
            "evidence_excerpt": ano.get("evidence_excerpt"),
            "evidence_count": ano.get("evidence_count"),
            "fix_suggestion": ano.get("fix_suggestion"),
            "pattern_eligible": ano.get("pattern_eligible"),
            "provenance": ano.get("provenance"),
        })

    # ── Summary ─────────────────────────────────────────────────────────────────
    by_severity = collections.Counter(a["severity"] for a in ordered_anomalies)
    by_category = collections.Counter(a["category"] for a in ordered_anomalies)

    summary = {
        "total": len(ordered_anomalies),
        "by_severity": dict(by_severity),
        "by_category": dict(by_category),
    }

    # Invariant check: summary.total == len(anomalies)
    assert summary["total"] == len(ordered_anomalies), (
        f"BUG: summary.total={summary['total']} != len(anomalies)={len(ordered_anomalies)}"
    )

    # ── Build output ────────────────────────────────────────────────────────────
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    output = {
        "meta": {
            "generated_at": now_iso,
            "source_parsed": str(pathlib.Path(args.parsed_json).resolve()),
            "source_metrics": str(pathlib.Path(args.metrics_json).resolve()),
            "budget_max_usd": budget_max_usd,
            "budget_source": budget_source,
            "categories_enabled": categories_enabled,
            "categories_disabled_reason": categories_disabled_reason,
            "warnings": run_warnings,
        },
        "anomalies": ordered_anomalies,
        "summary": summary,
    }

    json_str = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        out_path = pathlib.Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_str, encoding="utf-8")
        print(f"Output written to: {out_path}", file=sys.stderr)
    else:
        print(json_str)

    # Print summary to stderr for human visibility.
    print(
        f"[detect-anomalies] {summary['total']} anomalies detected "
        f"(categories: {categories_enabled}) "
        f"| severity: {dict(by_severity)} "
        f"| budget_threshold: {budget_max_usd:.2f} USD ({budget_source})",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
