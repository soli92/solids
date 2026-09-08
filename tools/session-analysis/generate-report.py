#!/usr/bin/env python3
"""
generate-report.py — EP-061/US-246/TSK-556 + TSK-558
Dual format report generation (MD + JSON) from session analysis pipeline output.

Reads:
  anomalies-json  Output of detect-anomalies.py  (AnomaliesEnvelope)
  metrics-json    Output of fleet-metrics.py      (session_totals + dispatch_efficiency)
  parsed-json     Output of parse-transcript.py   (meta + records)

Produces:
  <output-dir>/YYYY-MM-DD-session-analysis-<id-8char>.md
  <output-dir>/YYYY-MM-DD-session-analysis-<id-8char>.json

CLI:
  python3 generate-report.py <anomalies-json> <metrics-json> <parsed-json>
          [--output-dir raw/]
          [--session-id-short <id>]
          [--depth quick|full]
          [--span <descriptor>]
          [--dry-run]

Invariants enforced:
  R-SAA-5: ingest_eligible: false — hardcoded, non-bypassable
  R-SAA-3: redaction applied before any write (absolute paths, emails, credentials)
  R-SAA-7: provenance field preserved and cited in ## Fix Proposti
  R-SAA-2: writes ONLY to <output-dir>/ — no network, no git, no .claude/ mutations

stdlib-only: json, re, pathlib, sys, argparse, datetime, os
"""

import sys
import json
import re
import pathlib
import argparse
import datetime
import os

# ── Constants ──────────────────────────────────────────────────────────────────

SCHEMA_VERSION = 1
TTL_DAYS = 90
WIKI_INGEST_POLICY = "incidents-only"

# Severity ordering for worst_severity derivation.
SEVERITY_ORDER = ["critical", "warning", "info"]

# Fleet-relevant categories that produce fleet_recommendations.
FLEET_CATEGORIES = {"FLEET", "DISPATCH", "BUDGET"}

# Priority mapping from severity.
SEVERITY_TO_PRIORITY = {
    "critical": "high",
    "warning": "medium",
    "info": "low",
}

# Skill slug lookup: keyword patterns in evidence_excerpt / attribution_agent.
# Maps regex pattern → skill slug.
_SKILL_SLUG_PATTERNS = [
    (re.compile(r"parallel.schedul", re.I), "parallel-scheduling"),
    (re.compile(r"dispatch.polic", re.I), "dispatch-policy"),
    (re.compile(r"dev.protocol", re.I), "dev-protocol"),
    (re.compile(r"dev.handoff", re.I), "dev-handoff"),
    (re.compile(r"wiki.keeper", re.I), "session-analysis-protocol"),
    (re.compile(r"fleet.metric", re.I), "session-analysis-protocol"),
    (re.compile(r"detect.anomal", re.I), "session-analysis-protocol"),
    (re.compile(r"budget", re.I), "parallel-scheduling"),
]

# R-SAA-3 redaction regexes.
_PATH_RE = re.compile(r"/Users/[^/\s\"'<>]+/")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_CRED_RE = re.compile(
    r"(sk-[A-Za-z0-9\-]+|Bearer [A-Za-z0-9._\-]+|[A-Z_]{4,}_TOKEN=[^\s\"']+)"
)


# ── Redaction helpers ──────────────────────────────────────────────────────────

def _redact_str(s: str) -> str:
    """Apply R-SAA-3 redaction to a single string."""
    if not isinstance(s, str):
        return s
    s = _PATH_RE.sub("/Users/USER/", s)
    s = _EMAIL_RE.sub("user@example.com", s)
    s = _CRED_RE.sub("[REDACTED_CREDENTIAL]", s)
    return s


def _redact_value(v):
    """Recursively redact string values in any JSON-compatible structure."""
    if isinstance(v, str):
        return _redact_str(v)
    if isinstance(v, dict):
        return {k: _redact_value(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_redact_value(item) for item in v]
    return v


def _cap_evidence(excerpt: str, max_chars: int = 200) -> str:
    """Ensure evidence_excerpt is at most max_chars (R-SAA-3 invariant)."""
    if len(excerpt) > max_chars:
        return excerpt[:max_chars - len("[TRUNCATED]")] + "[TRUNCATED]"
    return excerpt


# ── Factory version reader ─────────────────────────────────────────────────────

def _read_factory_version() -> str:
    """
    Read pattern_version from factory.config.yaml by walking up from this script.
    Returns '2.41' as fallback if not found (fail-open, no crash).
    """
    here = pathlib.Path(__file__).resolve().parent
    for candidate in (here, here.parent, here.parent.parent, here.parent.parent.parent):
        cfg = candidate / "factory.config.yaml"
        if cfg.exists():
            text = cfg.read_text(encoding="utf-8")
            m = re.search(r'^pattern_version:\s*["\']?([0-9.]+)["\']?', text, re.MULTILINE)
            if m:
                return m.group(1)
    return "2.41"  # documented fallback


# ── Worst severity derivation ──────────────────────────────────────────────────

def _worst_severity(anomalies: list) -> str:
    """Return the highest severity across all anomalies, or 'none' if empty."""
    for sev in SEVERITY_ORDER:
        if any(a.get("severity") == sev for a in anomalies):
            return sev
    return "none"


# ── Skill slug inference (fleet_recommendations) ───────────────────────────────

def _infer_skill_affected(anomaly: dict) -> "str | None":
    """
    Infer skill slug from evidence_excerpt or attribution_agent using regex lookup.
    Returns None if no match found (fleet_doctor_command will remain null per v1 spec).
    """
    candidates = [
        anomaly.get("evidence_excerpt") or "",
        anomaly.get("attribution_agent") or "",
        anomaly.get("fix_suggestion") or "",
    ]
    for text in candidates:
        for pattern, slug in _SKILL_SLUG_PATTERNS:
            if pattern.search(text):
                return slug
    return None


# ── Fleet doctor command derivation (TSK-558) ─────────────────────────────────

def _build_fleet_doctor_command(
    anomaly: dict,
    skill: "str | None",
) -> "str | None":
    """
    Derive the advisory fleet_doctor_command string for a given anomaly.

    Format: /fleet-doctor analyze <target> --context=<anomaly_id>
    Note: /fleet-doctor is roadmap (no .claude/commands/fleet-doctor.md yet).
    The field is advisory-only — NEVER auto-invoked (R-SAA-6).

    Per-subtype mapping:
      FLEET / SKILL_NOT_FOUND:         /fleet-doctor analyze <skill_slug> --context=<id>
      DISPATCH / DISPATCH_REDUNDANT:   /fleet-doctor analyze <attribution_agent> --context=<id>
      DISPATCH / SERIAL_WHEN_PARALLEL: null  (text recommendation only, no fleet-doctor action)
      BUDGET / TIER_MISMATCH:          /fleet-doctor analyze <attribution_agent> --context=<id>
      Others (BUDGET_OVERFLOW etc.):   null
    """
    category = anomaly.get("category", "")
    subtype = anomaly.get("subtype", "")
    anomaly_id = anomaly.get("id", "unknown")
    attribution_agent = anomaly.get("attribution_agent") or ""

    if category == "FLEET" and subtype == "SKILL_NOT_FOUND":
        target = skill or attribution_agent or "unknown-skill"
        return f"/fleet-doctor analyze {target} --context={anomaly_id}"

    if category == "DISPATCH" and subtype == "DISPATCH_REDUNDANT":
        if attribution_agent:
            return f"/fleet-doctor analyze {attribution_agent} --context={anomaly_id}"
        return None  # no target to analyze without attribution_agent

    if category == "DISPATCH" and subtype == "SERIAL_WHEN_PARALLEL":
        return None  # session-level metric, no per-agent fleet-doctor action

    if category == "BUDGET" and subtype == "TIER_MISMATCH":
        if attribution_agent:
            return f"/fleet-doctor analyze {attribution_agent} --context={anomaly_id}"
        return None  # no target to analyze without attribution_agent

    return None  # all other subtypes: text recommendation only


# ── Fleet recommendations derivation ──────────────────────────────────────────

def _build_fleet_recommendations(anomalies: list) -> list:
    """
    Derive fleet_recommendations from anomalies with FLEET/DISPATCH/BUDGET category.
    fleet_doctor_command populated by TSK-558 per-subtype logic.
    Advisory only — never auto-invoked (R-SAA-6).
    """
    recs = []
    for ano in anomalies:
        if ano.get("category") not in FLEET_CATEGORIES:
            continue
        skill = _infer_skill_affected(ano)
        priority = SEVERITY_TO_PRIORITY.get(ano.get("severity", "info"), "low")
        fleet_cmd = _build_fleet_doctor_command(ano, skill)
        rec = {
            "anomaly_id": ano["id"],
            "skill_affected": skill,
            "recommendation": ano.get("fix_suggestion", ""),
            "priority": priority,
            "fleet_doctor_command": fleet_cmd,
        }
        recs.append(rec)
    return recs


# ── Session metrics mirror ─────────────────────────────────────────────────────

def _build_session_metrics(metrics_data: dict) -> dict:
    """
    Build SessionMetrics from fleet-metrics.py output.
    Only includes fields defined in schema-anomaly.json#SessionMetrics.
    """
    totals = metrics_data.get("session_totals") or {}
    eff = metrics_data.get("dispatch_efficiency") or {}

    result = {
        "total_cost_approx": totals.get("total_cost_approx") or 0.0,
        "agent_count": totals.get("agent_count") or 0,
    }

    # Optional fields — include if present.
    for field in (
        "total_token_in", "total_token_out",
        "total_cache_read", "total_cache_write",
        "session_duration_ms",
    ):
        v = totals.get(field)
        if v is not None:
            result[field] = v

    wave_count = totals.get("wave_count")
    if wave_count is not None:
        result["wave_count"] = wave_count

    # dispatch_efficiency_score from dispatch_efficiency.score.
    score = eff.get("score")
    if score is not None:
        result["dispatch_efficiency_score"] = score

    return result


# ── Markdown generation ────────────────────────────────────────────────────────

def _build_frontmatter(
    session_id: str,
    depth: str,
    span: str,
    generated_at: str,
    factory_version: str,
    anomaly_count: int,
    worst_severity: str,
    schema_degraded: bool,
) -> str:
    lines = [
        "---",
        "type: session-analysis-report",
        f"session_id: {session_id}",
        f"depth: {depth}",
        f"span: {span}",
        f"generated_at: {generated_at}",
        f"factory_version: {factory_version}",
        f"anomaly_count: {anomaly_count}",
        f"worst_severity: {worst_severity}",
        "ingest_eligible: false",
        f"wiki_ingest_policy: {WIKI_INGEST_POLICY}",
        f"ttl_days: {TTL_DAYS}",
        f"schema_version: {SCHEMA_VERSION}",
        f"schema_degraded: {str(schema_degraded).lower()}",
        "---",
    ]
    return "\n".join(lines)


def _section_executive_summary(
    anomaly_summary: dict,
    session_metrics: dict,
    anomalies: list,
    metrics_data: dict,
) -> str:
    totals = metrics_data.get("session_totals") or {}
    eff = metrics_data.get("dispatch_efficiency") or {}

    wave_count = totals.get("wave_count", 0)
    record_count = totals.get("record_count", 0)
    cost_approx = totals.get("total_cost_approx")
    cost_str = f"${cost_approx:.6f}" if cost_approx is not None else "n/a"
    eff_score = eff.get("score")
    eff_str = f"{eff_score:.4f}" if eff_score is not None else "n/a"

    by_sev = anomaly_summary.get("by_severity", {})
    critical_n = by_sev.get("critical", 0)
    warning_n = by_sev.get("warning", 0)
    info_n = by_sev.get("info", 0)
    total_n = anomaly_summary.get("total", 0)

    lines = [
        "## Executive Summary",
        "",
        f"| Metrica | Valore |",
        f"|---|---|",
        f"| Wave analizzate | {wave_count} |",
        f"| Record (tool_call/assistant) | {record_count} |",
        f"| Anomalie totali | {total_n} |",
        f"| — critical | {critical_n} |",
        f"| — warning | {warning_n} |",
        f"| — info | {info_n} |",
        f"| Costo sessione (USD approx) | {cost_str} |",
        f"| Dispatch efficiency score | {eff_str} |",
        "",
        f"Fonte metriche: `fleet-metrics.py` (session_totals + dispatch_efficiency). "
        f"Fonte anomalie: `detect-anomalies.py`.",
    ]
    return "\n".join(lines)


def _section_anomalie(anomalies: list) -> str:
    header = (
        "## Anomalie Rilevate\n\n"
        "| ID | Categoria | Subtype | Severity | Wave | Agent | Descrizione |"
        " Fix | Evidence Count | Pattern Eligible |\n"
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    if not anomalies:
        return header + "\n\n_Nessuna anomalia rilevata in questa sessione._"

    rows = []
    for ano in anomalies:
        wave = ano.get("wave_id") or "—"
        agent = ano.get("attribution_agent") or "—"
        desc = (ano.get("description") or "").replace("|", "\\|")[:120]
        fix = (ano.get("fix_suggestion") or "").replace("|", "\\|")[:100]
        pe = "si" if ano.get("pattern_eligible") else "no"
        ec = ano.get("evidence_count", 1)
        subtype = ano.get("subtype", "—")
        row = (
            f"| {ano['id']} | {ano.get('category','?')} | {subtype} |"
            f" {ano.get('severity','?')} | {wave} | {agent} |"
            f" {desc} | {fix} | {ec} | {pe} |"
        )
        rows.append(row)

    return header + "\n" + "\n".join(rows)


def _section_metriche(metrics_data: dict, parsed_meta: dict) -> str:
    totals = metrics_data.get("session_totals") or {}
    eff = metrics_data.get("dispatch_efficiency") or {}
    per_model = metrics_data.get("per_model") or []

    tok_in = totals.get("total_token_in", 0)
    tok_out = totals.get("total_token_out", 0)
    cache_r = totals.get("total_cache_read", 0)
    cache_w = totals.get("total_cache_write", 0)
    cost = totals.get("total_cost_approx")
    cost_str = f"${cost:.6f}" if cost is not None else "n/a"
    dur_ms = totals.get("session_duration_ms")
    dur_str = f"{dur_ms}ms" if dur_ms is not None else "n/a"
    eff_score = eff.get("score")
    eff_str = f"{eff_score:.4f}" if eff_score is not None else "n/a"
    waves_analyzed = eff.get("waves_analyzed", 0)
    agent_count = totals.get("agent_count", 0)

    models_str = ", ".join(
        m["model"] for m in per_model[:5]
    ) if per_model else "n/a"

    lines = [
        "## Metriche Sessione",
        "",
        "_Fonte: `fleet-metrics.py` (session_totals, dispatch_efficiency, per_model). "
        "Fonte provenance: R-SAA-7._",
        "",
        "| Metrica | Valore | Provenance |",
        "|---|---|---|",
        f"| Token input (totale) | {tok_in:,} | `session_totals.total_token_in` (metrics) |",
        f"| Token output (totale) | {tok_out:,} | `session_totals.total_token_out` (metrics) |",
        f"| Cache read | {cache_r:,} | `session_totals.total_cache_read` (metrics) |",
        f"| Cache write | {cache_w:,} | `session_totals.total_cache_write` (metrics) |",
        f"| Costo approx USD | {cost_str} | `session_totals.total_cost_approx` (metrics) |",
        f"| Durata sessione | {dur_str} | `session_totals.session_duration_ms` (metrics) |",
        f"| Agenti distinti | {agent_count} | `session_totals.agent_count` (metrics) |",
        f"| Dispatch efficiency | {eff_str} | `dispatch_efficiency.score` (metrics) |",
        f"| Wave analizzate (efficiency) | {waves_analyzed} | `dispatch_efficiency.waves_analyzed` (metrics) |",
        f"| Modelli usati (top 5) | {models_str} | `per_model[].model_id` (metrics) |",
    ]

    schema_deg = parsed_meta.get("schema_degraded", False)
    if schema_deg:
        lines += [
            "",
            "> **WARNING**: schema_degraded = true nel metadata parsed. "
            "Claude Code version non nel set SUPPORTED_CC_VERSIONS. "
            "Metriche potrebbero essere incomplete (R-SAA-9).",
        ]

    return "\n".join(lines)


def _section_fix_proposti(anomalies: list) -> str:
    lines = ["## Fix Proposti", ""]

    if not anomalies:
        lines.append("_Nessuna anomalia rilevata — nessun fix proposto._")
        return "\n".join(lines)

    lines.append(
        "_Lista ordinata per severity (critical → warning → info). "
        "R-SAA-6: nessun fix auto-applicato — ogni azione è umana o delegata a fleet-doctor._"
    )
    lines.append("")

    # Sort by severity order.
    sev_rank = {s: i for i, s in enumerate(SEVERITY_ORDER)}
    sorted_anos = sorted(
        anomalies,
        key=lambda a: sev_rank.get(a.get("severity", "info"), 99),
    )

    for ano in sorted_anos:
        sev = ano.get("severity", "?")
        ano_id = ano.get("id", "?")
        fix = ano.get("fix_suggestion", "—")
        prov = ano.get("provenance") or {}
        src_field = prov.get("source_field", "—")
        src_file = prov.get("source_file", "—")
        lines.append(
            f"- **{ano_id}** (`{sev}`): {fix}  \n"
            f"  Provenance: `{src_field}` (source_file: {src_file})"
        )

    return "\n".join(lines)


def _section_punti_aperti(anomalies: list, anomaly_meta: dict) -> str:
    lines = ["## Punti Aperti", ""]

    # LLM advisory is permitted only here; v1 uses static content from
    # notes[] or anomalies without deterministic fix.
    # Identify anomalies not fully classified (pattern_eligible=False and
    # no fix_suggestion pointing to a specific file).
    non_det = [
        a for a in anomalies
        if not a.get("pattern_eligible")
        and not re.search(r"\.(py|yaml|json|md)\b", a.get("fix_suggestion", ""))
    ]

    if not non_det:
        lines.append(
            "Nessun punto aperto — tutte le anomalie hanno regole deterministiche "
            "con fix_suggestion riferita a un file specifico."
        )
    else:
        lines.append(
            "Le seguenti anomalie non hanno una classificazione completamente deterministica "
            "o il fix_suggestion non indica un file specifico. Richiedono giudizio umano:"
        )
        lines.append("")
        for a in non_det:
            lines.append(f"- **{a['id']}** ({a.get('severity','?')}): {a.get('description','—')}")

    # Propagate warnings from detect-anomalies meta.
    warnings = anomaly_meta.get("meta", {}).get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("**Warning emessi da detect-anomalies.py**:")
        for w in warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)


def _section_perimetro(parsed_meta: dict, anomaly_meta: dict, metrics_meta: dict) -> str:
    session_id = parsed_meta.get("session_id", "—")
    subagent_count = parsed_meta.get("subagent_files_found", 0)
    record_count = parsed_meta.get("records_total", 0)
    schema_deg = parsed_meta.get("schema_degraded", False)

    cats_enabled = anomaly_meta.get("meta", {}).get("categories_enabled") or []
    cats_disabled = anomaly_meta.get("meta", {}).get("categories_disabled_reason") or {}
    all_categories = {"ERROR", "BUDGET", "DISPATCH", "LATENCY", "FLEET", "GOVERNANCE"}
    cats_not_enabled = all_categories - set(cats_enabled)

    lines = [
        "## Perimetro analizzato",
        "",
        "**Incluso:**",
        "",
        f"- session_id: `{session_id}`",
        f"- Transcript principale (main JSONL) + {subagent_count} file sub-agente",
        f"- Totale record normalizzati: {record_count}",
        f"- Categorie anomalie attive: {', '.join(sorted(cats_enabled)) or 'nessuna'}",
        "",
        "**Non incluso:**",
        "",
    ]

    if cats_not_enabled:
        for cat in sorted(cats_not_enabled):
            reason = cats_disabled.get(cat, "non abilitata in questa esecuzione (flag off o roadmap v2)")
            lines.append(f"- Categoria `{cat}`: {reason}")
    else:
        lines.append("- Tutte le categorie v1 erano abilitate.")

    lines += [
        "- Correlazione `analytics/events/` (opt-in disabilitato per default)",
        "- Correlazione `memory/episodic/` (opt-in disabilitato per default)",
        "- Correlazione `code_quality/reports/` (opt-in disabilitato per default)",
        "- Valutazione semantica del contenuto tool_result (mai inclusa — R-SAA-3)",
    ]

    if schema_deg:
        lines += [
            "",
            "> **CAVEAT**: schema_degraded = true. Il walker EP-062 ha parsato la sessione "
            "in modalità best-effort (versione Claude Code ignota). "
            "Alcuni record potrebbero essere omessi (dipendenza EP-062 walker riparato).",
        ]

    return "\n".join(lines)


def _section_provenienza_limiti(
    anomaly_meta: dict,
    parsed_meta: dict,
    factory_version: str,
) -> str:
    cats_enabled = anomaly_meta.get("meta", {}).get("categories_enabled") or []
    cats_disabled = anomaly_meta.get("meta", {}).get("categories_disabled_reason") or {}
    schema_deg = parsed_meta.get("schema_degraded", False)
    pricing_source = ""

    lines = [
        "## Provenienza & limiti",
        "",
        "**Sezione anti-compiacenza obbligatoria (R-SAA-Critic dal blackboard TR). "
        "Questo report è deterministico nelle sue misurazioni, ma ha limiti espliciti "
        "che il lettore deve conoscere.**",
        "",
        "### Categorie non abilitate e motivazione",
        "",
    ]

    all_cats = {"ERROR", "BUDGET", "DISPATCH", "LATENCY", "FLEET", "GOVERNANCE"}
    not_enabled = all_cats - set(cats_enabled)
    if not_enabled:
        for cat in sorted(not_enabled):
            reason = cats_disabled.get(
                cat,
                "non abilitata — flag --enable-* richiesto o categoria roadmap v2 "
                "(calibrazione signal/noise ratio in attesa di dati reali)",
            )
            lines.append(f"- `{cat}`: {reason}")
    else:
        lines.append("- Tutte le categorie v1 erano abilitate in questa esecuzione.")

    lines += [
        "",
        "### Limiti di rilevazione",
        "",
        "- **SAA-E (ERROR_LOOP)** è ancorata a `stop_reason` testuale via regex "
        "`(?i)error|failed|fatal`, non al flag `is_error` (sempre 0 nei record Claude Code). "
        "Falso positivo possibile se un agente logga stringhe contenenti 'error' "
        "senza fallire davvero.",
        "- **SAA-B (BUDGET_OVERFLOW)** dipende da `total_cost_approx` calcolato con "
        "pricing hardcoded/YAML. Se la sessione usa modelli non in pricing table, "
        "il costo è 0.0 (undercount silenzioso — WARNING emesso da fleet-metrics.py).",
        "- **SAA-D (DISPATCH_REDUNDANT)** usa euristiche su sequence di agent_hash. "
        "Non detecta ridondanza semantica (due agenti che fanno la stessa cosa "
        "con tool diversi).",
        "- **LATENCY** e **FLEET** (se abilitate): basate su elapsed_ms stimato "
        "da timestamp; dipendente dalla qualità dei timestamp nel JSONL.",
        "",
        "### Cosa questo report NON può dire",
        "",
        "- Non valuta il merito semantico delle decisioni degli agenti.",
        "- Non sostituisce una code review (usa `/review <TSK-id>` + CQRL).",
        "- Non rileva side-effect su sistemi esterni (rete, database, file fuori da raw/).",
        "- Non correla con risultati funzionali del progetto (usa functional-oracle-protocol).",
        "- Non sostituisce un'analisi architettuale (usa Tavola Rotonda o lead-architect).",
        "",
        "### Dipendenze e rischi noti",
        "",
        f"- Factory version al momento del report: `{factory_version}`.",
    ]

    if schema_deg:
        lines.append(
            "- **CRITICO**: `schema_degraded: true` — il walker EP-062 ha operato "
            "in modalità best-effort. Dipendenza EP-062 walker riparato: TSK-549 DONE, "
            "ma la versione Claude Code della sessione analizzata non era nel set "
            "SUPPORTED_CC_VERSIONS. Risultati possibilmente incompleti."
        )
    else:
        lines.append(
            "- Walker EP-062 ha operato in modalità normale (schema non degradato)."
        )

    lines += [
        "- `evidence_excerpt` cappato a 200 char (R-SAA-3). I valori numerici chiave "
        "sono preservati ma il contesto narrativo può essere troncato.",
        "- `fleet_recommendations.fleet_doctor_command` valorizzato per FLEET/SKILL_NOT_FOUND, "
        "DISPATCH/DISPATCH_REDUNDANT, BUDGET/TIER_MISMATCH (TSK-558). "
        "Null per SERIAL_WHEN_PARALLEL e altri subtypes — raccomandazione solo testuale. "
        "Il comando è advisory-only, mai auto-invocato (R-SAA-6). "
        "Nota: /fleet-doctor è roadmap (nessun .claude/commands/fleet-doctor.md ancora presente).",
    ]

    return "\n".join(lines)


def _build_markdown(
    session_id: str,
    depth: str,
    span: str,
    generated_at: str,
    factory_version: str,
    anomalies: list,
    anomaly_meta: dict,
    metrics_data: dict,
    parsed_data: dict,
) -> str:
    parsed_meta = parsed_data.get("meta") or {}
    anomaly_summary = anomaly_meta.get("summary") or {"total": 0, "by_severity": {}, "by_category": {}}
    anomaly_count = len(anomalies)
    worst_sev = _worst_severity(anomalies)
    schema_deg = parsed_meta.get("schema_degraded", False)

    session_metrics = _build_session_metrics(metrics_data)
    metrics_meta = metrics_data.get("meta") or {}

    parts = [
        _build_frontmatter(
            session_id, depth, span, generated_at,
            factory_version, anomaly_count, worst_sev, schema_deg,
        ),
        "",
        f"# Session Analysis Report — {session_id}",
        "",
        f"_Generato da `generate-report.py` (EP-061/TSK-556) il {generated_at}. "
        f"Profondità: `{depth}`. Factory: v{factory_version}._",
        "",
        _section_executive_summary(anomaly_summary, session_metrics, anomalies, metrics_data),
        "",
        _section_anomalie(anomalies),
        "",
        _section_metriche(metrics_data, parsed_meta),
        "",
        _section_fix_proposti(anomalies),
        "",
        _section_punti_aperti(anomalies, anomaly_meta),
        "",
        _section_perimetro(parsed_meta, anomaly_meta, metrics_meta),
        "",
        _section_provenienza_limiti(anomaly_meta, parsed_meta, factory_version),
        "",
    ]
    return "\n".join(parts)


# ── JSON report ────────────────────────────────────────────────────────────────

def _build_json_report(
    session_id: str,
    depth: str,
    span: str,
    generated_at: str,
    factory_version: str,
    anomalies: list,
    fleet_recs: list,
    session_metrics: dict,
) -> dict:
    """
    Build SessionAnalysisReport conforming to schema-anomaly.json#SessionAnalysisReport.
    Note: schema has additionalProperties: false; only include defined properties.
    """
    anomaly_count = len(anomalies)
    worst_sev = _worst_severity(anomalies)

    report = {
        "type": "session-analysis-report",
        "session_id": session_id,
        "depth": depth,
        "generated_at": generated_at,
        "factory_version": factory_version,
        "anomaly_count": anomaly_count,
        "worst_severity": worst_sev,
        "ingest_eligible": False,   # R-SAA-5: hardcoded, non-bypassable
        "wiki_ingest_policy": WIKI_INGEST_POLICY,
        "anomalies": anomalies,
        "fleet_recommendations": fleet_recs,
    }

    # Optional fields defined in schema.
    if span:
        report["span"] = span
    report["ttl_days"] = TTL_DAYS
    if session_metrics:
        report["session_metrics"] = session_metrics

    return report


# ── Validation (optional jsonschema) ──────────────────────────────────────────

def _validate_json_report(report: dict, schema_path: "pathlib.Path | None") -> list:
    """
    Validate report against schema-anomaly.json using jsonschema if available.
    Returns list of validation warning strings (empty = ok).
    Non-blocking: if jsonschema not installed, returns an informational message.
    """
    if schema_path is None:
        # Auto-discover schema-anomaly.json.
        here = pathlib.Path(__file__).resolve().parent
        candidate = here / "schema-anomaly.json"
        if candidate.exists():
            schema_path = candidate

    if schema_path is None or not schema_path.exists():
        return ["WARN: schema-anomaly.json not found — JSON validation skipped"]

    try:
        import importlib.util
        if importlib.util.find_spec("jsonschema") is None:
            return ["INFO: jsonschema not installed — JSON validation skipped (install with: pip install jsonschema)"]

        import jsonschema  # type: ignore

        with open(schema_path, encoding="utf-8") as f:
            full_schema = json.load(f)

        # Extract SessionAnalysisReport sub-schema.
        sa_schema = full_schema.get("$defs", {}).get("SessionAnalysisReport")
        if sa_schema is None:
            return ["WARN: SessionAnalysisReport not found in schema — validation skipped"]

        # Resolve $refs within the full schema context.
        resolver = jsonschema.RefResolver.from_schema(full_schema)
        validator = jsonschema.Draft202012Validator(sa_schema, resolver=resolver)
        errors = list(validator.iter_errors(report))
        if errors:
            return [f"SCHEMA_ERROR: {e.message} (path: {list(e.path)})" for e in errors]
        return []  # valid

    except Exception as exc:
        return [f"WARN: JSON schema validation error: {exc}"]


# ── Filename builder ───────────────────────────────────────────────────────────

def _build_filename_base(date_str: str, session_id_short: str) -> str:
    """Build the base filename without extension."""
    return f"{date_str}-session-analysis-{session_id_short}"


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "generate-report.py — EP-061/US-246/TSK-556. "
            "Generate dual MD+JSON session analysis report. stdlib-only."
        )
    )
    ap.add_argument(
        "anomalies_json",
        help="JSON file produced by detect-anomalies.py (AnomaliesEnvelope)",
    )
    ap.add_argument(
        "metrics_json",
        help="JSON file produced by fleet-metrics.py",
    )
    ap.add_argument(
        "parsed_json",
        help="JSON file produced by parse-transcript.py",
    )
    ap.add_argument(
        "--output-dir",
        default="raw/",
        help="Output directory for generated reports (default: raw/)",
    )
    ap.add_argument(
        "--session-id-short",
        default=None,
        help="8-char session ID override (default: first 8 chars of session_id from parsed meta)",
    )
    ap.add_argument(
        "--depth",
        choices=["quick", "full"],
        default="quick",
        help="Analysis depth: quick (ERROR/BUDGET/DISPATCH) or full (all categories)",
    )
    ap.add_argument(
        "--span",
        default=None,
        help="Textual descriptor of the session span (default: session-<id>)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print files to stdout instead of writing to disk",
    )
    ap.add_argument(
        "--schema",
        default=None,
        help="Path to schema-anomaly.json for JSON validation (auto-discovered if omitted)",
    )

    args = ap.parse_args()

    # ── Load inputs ────────────────────────────────────────────────────────────
    try:
        anomaly_data = json.loads(pathlib.Path(args.anomalies_json).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read anomalies-json: {exc}", file=sys.stderr)
        return 1

    try:
        metrics_data = json.loads(pathlib.Path(args.metrics_json).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read metrics-json: {exc}", file=sys.stderr)
        return 1

    try:
        parsed_data = json.loads(pathlib.Path(args.parsed_json).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read parsed-json: {exc}", file=sys.stderr)
        return 1

    # ── Resolve session_id ─────────────────────────────────────────────────────
    parsed_meta = parsed_data.get("meta") or {}
    raw_session_id = parsed_meta.get("session_id") or "unknown"

    if args.session_id_short:
        session_id_short = args.session_id_short[:8]
    else:
        # Use first 8 chars of session_id (strip non-alnum for safety).
        clean = re.sub(r"[^a-zA-Z0-9]", "", raw_session_id)
        session_id_short = clean[:8] if clean else "00000000"

    session_id = raw_session_id

    # ── Resolve span ────────────────────────────────────────────────────────────
    span = args.span or f"session-{session_id_short}"

    # ── Factory version ─────────────────────────────────────────────────────────
    factory_version = _read_factory_version()

    # ── Timestamp ───────────────────────────────────────────────────────────────
    now = datetime.datetime.now(datetime.timezone.utc)
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_str = now.strftime("%Y-%m-%d")

    # ── Redact anomalies (R-SAA-3) ──────────────────────────────────────────────
    raw_anomalies = anomaly_data.get("anomalies") or []
    anomalies = []
    for ano in raw_anomalies:
        redacted = _redact_value(dict(ano))
        # Enforce evidence_excerpt cap (R-SAA-3 invariant).
        if "evidence_excerpt" in redacted and isinstance(redacted["evidence_excerpt"], str):
            redacted["evidence_excerpt"] = _cap_evidence(redacted["evidence_excerpt"], 200)
        anomalies.append(redacted)

    # ── Fleet recommendations ────────────────────────────────────────────────────
    fleet_recs = _build_fleet_recommendations(anomalies)
    # Redact recommendations too.
    fleet_recs = _redact_value(fleet_recs)

    # ── Session metrics ──────────────────────────────────────────────────────────
    session_metrics = _build_session_metrics(metrics_data)

    # ── Build JSON report ────────────────────────────────────────────────────────
    json_report = _build_json_report(
        session_id=session_id,
        depth=args.depth,
        span=span,
        generated_at=generated_at,
        factory_version=factory_version,
        anomalies=anomalies,
        fleet_recs=fleet_recs,
        session_metrics=session_metrics,
    )
    # Redact JSON report string fields.
    json_report = _redact_value(json_report)

    # ── Validate JSON (R-SAA-7) ──────────────────────────────────────────────────
    schema_path = pathlib.Path(args.schema) if args.schema else None
    validation_warnings = _validate_json_report(json_report, schema_path)
    if validation_warnings:
        for w in validation_warnings:
            print(w, file=sys.stderr)

    # ── Build markdown report ────────────────────────────────────────────────────
    md_content = _build_markdown(
        session_id=session_id,
        depth=args.depth,
        span=span,
        generated_at=generated_at,
        factory_version=factory_version,
        anomalies=anomalies,
        anomaly_meta=anomaly_data,
        metrics_data=metrics_data,
        parsed_data=parsed_data,
    )
    # Redact markdown too (belt-and-suspenders after section builders).
    md_content = _redact_str(md_content)

    # ── R-SAA-3 final check ──────────────────────────────────────────────────────
    # Verify no personal paths or credentials survived redaction.
    _STOP_PATTERNS = [
        re.compile(r"/Users/(?!USER/)"),
        re.compile(r"sk-[A-Za-z0-9\-]{10,}"),
        re.compile(r"Bearer [A-Za-z0-9._\-]{10,}"),
    ]
    combined_check = md_content + json.dumps(json_report, ensure_ascii=False)
    for pat in _STOP_PATTERNS:
        if pat.search(combined_check):
            print(
                f"STOP (R-SAA-3): redaction incomplete — pattern {pat.pattern!r} "
                "found in output. Report NOT written.",
                file=sys.stderr,
            )
            return 2

    # ── Build filenames ───────────────────────────────────────────────────────────
    base = _build_filename_base(date_str, session_id_short)
    md_filename = f"{base}.md"
    json_filename = f"{base}.json"

    json_str = json.dumps(json_report, indent=2, ensure_ascii=False)

    # ── Write or dry-run ─────────────────────────────────────────────────────────
    if args.dry_run:
        print(f"=== DRY-RUN: {md_filename} ===", flush=True)
        print(md_content, flush=True)
        print(f"\n=== DRY-RUN: {json_filename} ===", flush=True)
        print(json_str, flush=True)
    else:
        # R-SAA-2: write only to output_dir.
        out_dir = pathlib.Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        md_path = out_dir / md_filename
        json_path = out_dir / json_filename

        md_path.write_text(md_content, encoding="utf-8")
        json_path.write_text(json_str, encoding="utf-8")

        print(f"MD  written: {md_path}", file=sys.stderr)
        print(f"JSON written: {json_path}", file=sys.stderr)
        print(f"Anomalie: {len(anomalies)} | Worst severity: {_worst_severity(anomalies)}", file=sys.stderr)
        if fleet_recs:
            print(f"Fleet recommendations: {len(fleet_recs)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
