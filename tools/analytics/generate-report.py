"""
generate-report.py — tool deterministico generate_report (EP-009, US-037, TSK-065)

Parte della capability Task Analytics & Cost/Time Estimation (EP-009), istanza
del pattern thin-agents-fat-skills-refactor: questo è il TOOL (logica deterministica,
no LLM). Materializza il documento "Analytics Report" (sub-tipo cost_time_report)
nello schema canonico ADR-024 §A, differenziando contenuto e mascheramento privacy
per audience. È un AGGREGATORE: invoca i tre reader deterministici —
compute-agentic-cost.py, compute-human-cost.py, analyze-timeline.py — e assembla
i loro JSON nello schema standard.

PATTERN.md §3 — operazione canonica opzionale «Cost/Time Report».
Wiki: wiki/concepts/task-analytics-cost-estimation-capability.md §6.
ADR-024 §A — schema_version v1, type discriminator, blocchi additivi opzionali.
ADR-023 §C — privacy per audience. §E — rate_basis obbligatorio se human > 0.
ADR-027 §A/§E — storage scope in analytics/reports/<slug>/<periodo> vs adhoc.

EXIT CODES
  0  report prodotto OR no-op (analytics.measurement.enabled assente/false, R.P3)
  >0 errore (audience invalida, rate_basis mancante, sub-tool fallito, ecc.)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # tools/analytics/ → root factory (2 livelli)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytics_cli import ContractArgumentParser, jq_numbers  # noqa: E402 — contratto CLI comune (US-327)


def _jq_round(x: float) -> float:
    """`round` di jq (C round: la meta' va lontano da zero), non l'arrotondamento bancario di Python.

    Parita' con gli .sh: `round(0.125 * 100)` vale 13 in jq e 12 in Python.
    """
    import math as _m
    return float(_m.copysign(_m.floor(abs(x) + 0.5), x))


AGENTIC_DEFAULT: dict = {
    "cost": 0,
    "currency": "EUR",
    "breakdown": {
        "per_model": {},
        "agentic_by_token_kind": {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
        },
        "per_tool": {},
    },
    "events_considered": 0,
    "pricing_table_version": "",
}

HUMAN_DEFAULT: dict = {
    "cost": 0,
    "currency": "EUR",
    "breakdown": {"per_role": {}},
    "events_considered": 0,
    "rate_card_version": "",
    "notes": [],
}

TIMELINE_DEFAULT: dict = {
    "lead":  {"p50": 0, "p85": 0, "p95": 0, "unit": "days"},
    "cycle": {"p50": 0, "p85": 0, "p95": 0, "unit": "days"},
    "effort": {"p50": 0, "p85": 0, "p95": 0, "unit": "hours"},
    "wait":  {"p50": 0, "p85": 0, "p95": 0, "unit": "days"},
    "bottlenecks": [],
    "operational": {"throughput_per_week": 0, "wip_avg": 0, "wip_max": 0},
    "n_samples": 0,
    "events_considered": 0,
}

_UNUSED = math.floor  # stdlib math imported per contratto


def _yaml_nested(config_path: str, section: str, key: str) -> str:
    """Extract analytics.<section>.<key> from a YAML file using pure regex.

    Navigates the nested structure without an external YAML parser.
    Returns the value string, or "" if not found.
    """
    path = Path(config_path)
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")

    in_analytics = False
    in_section = False
    analytics_indent = -1
    section_indent = -1

    for raw_line in text.splitlines():
        stripped = re.sub(r'\s+#.*$', '', raw_line)
        content = stripped.rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip())
        bare = content.strip()

        if not in_analytics:
            if re.match(r'^analytics\s*:', content):
                in_analytics = True
                analytics_indent = indent
            continue

        if indent <= analytics_indent and not re.match(r'^analytics\s*:', content):
            in_analytics = False
            in_section = False
            continue

        if not in_section:
            if re.match(rf'^{re.escape(section)}\s*:', bare):
                in_section = True
                section_indent = indent
            continue

        if indent <= section_indent:
            in_section = False
            continue

        m = re.match(rf'^{re.escape(key)}\s*:\s*(.*)', bare)
        if m:
            val = m.group(1).strip().strip('"').strip("'")
            return val

    return ""


def _kebab(s: str) -> str:
    """Normalise a string to kebab-case."""
    return re.sub(r'-+$', '', re.sub(r'^-+', '', re.sub(r'[^a-z0-9]+', '-', s.lower())))


def _run_subtool(
    tool_path: Path,
    extra_args: list[str],
    timeout: int = 900,
) -> tuple[str, int]:
    """Run a Python sub-tool. Return (stdout, returncode)."""
    if not tool_path.is_file():
        print(
            f"ERRORE: sub-tool non trovato: {tool_path}. "
            "La capability è attiva ma il tool dipendente manca.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"missing sub-tool: {tool_path.name}"}))
        sys.exit(1)
    result = subprocess.run(
        [sys.executable, str(tool_path)] + extra_args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout, result.returncode


def _round2(v: float) -> float:
    return _jq_round(v * 100) / 100


def _render_md(report: dict, storage_kind: str) -> str:
    """Render human-readable Markdown from an assembled report dict."""
    c = report["cost"]
    sp = report["split"]
    tm = report["time"]
    lines: list[str] = []

    lines.append(f"# Analytics Report — {report['type']} ({report['audience']})")
    lines.append("")
    lines.append(f"- schema_version: `{report['schema_version']}`")
    lines.append(f"- generated_at: `{report['generated_at']}`")
    lines.append(f"- generated_by: `{report['generated_by']}`")
    lines.append(f"- scope: `{json.dumps(report['scope'])}`")
    lines.append("")

    cur = c.get("currency", "EUR")
    lines.append(f"## Cost ({cur})")
    lines.append("")
    lines.append("| Voce | Valore |")
    lines.append("|---|---|")
    lines.append(f"| agentic | {c.get('agentic', 0)} |")
    lines.append(f"| human | {c.get('human', 0)} |")
    lines.append(f"| total | {c.get('total', 0)} |")
    if c.get("rate_basis"):
        lines.append(f"| rate_basis | {c['rate_basis']} |")
    if c.get("agentic_cache_savings_pct") is not None:
        lines.append(f"| cache_savings_pct | {c['agentic_cache_savings_pct']}% |")
    lines.append("")

    lines.append("## Split umano / agentico")
    lines.append("")
    lines.append(f"- agentic: {sp.get('agentic_pct', 0)}%")
    lines.append(f"- human: {sp.get('human_pct', 0)}%")
    if sp.get("cache_savings_pct") is not None:
        lines.append(f"- cache_savings: {sp['cache_savings_pct']}%")
    lines.append("")

    lines.append("## Time (percentili — mai medie)")
    lines.append("")
    lines.append("| Metrica | p50 | p85 | p95 |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| lead (days) | {tm.get('lead_p50_days', 0)} | "
        f"{tm.get('lead_p85_days', 0)} | {tm.get('lead_p95_days', 0)} |"
    )
    lines.append(
        f"| cycle (days) | {tm.get('cycle_p50_days', 0)} | "
        f"{tm.get('cycle_p85_days', 0)} | {tm.get('cycle_p95_days', 0)} |"
    )
    lines.append(
        f"| effort (hours) | {tm.get('effort_p50_hours', 0)} | "
        f"{tm.get('effort_p85_hours', 0)} | — |"
    )
    lines.append(
        f"| wait (days) | {tm.get('wait_p50_days', 0)} | "
        f"{tm.get('wait_p85_days', 0)} | — |"
    )
    lines.append("")
    lines.append(f"- bottleneck: `{tm.get('bottleneck', 'n/a')}`")
    lines.append(f"- n_samples: {tm.get('n_samples', 0)}")
    lines.append("")

    if report.get("operational") is not None:
        op = report["operational"]
        lines.append("## Operational")
        lines.append("")
        lines.append(f"- throughput_per_week: {op.get('throughput_per_week', 0)}")
        lines.append(f"- wip_avg: {op.get('wip_avg', 0)}")
        lines.append(f"- cost_per_task: {op.get('cost_per_task', 0)}")
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    notes = report.get("notes", [])
    if not notes:
        lines.append("- (nessuna nota)")
    else:
        for n in notes:
            lines.append(f"- {n}")
    lines.append("")
    lines.append("---")
    lines.append(
        f"_Report {storage_kind} generato da generate-report.py (EP-009, US-037). "
        "Schema ADR-024 §A; storage ADR-027 §A. "
        "Capability [[task-analytics-cost-estimation-capability]] §6._"
    )
    return "\n".join(lines)


def main() -> None:  # noqa: C901
    parser = ContractArgumentParser(
        description="generate_report — EP-009, US-037, TSK-065",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--scope",
        default="{}",
        help="filtro analitico JSON. Shape: {project_id?, period?, name?, type?}. Default {}.",
    )
    parser.add_argument(
        "--audience",
        help="operativa | progetto | executive (REQUIRED).",
    )
    parser.add_argument(
        "--format",
        dest="fmt",
        default="md+json",
        help="md | json | md+json | pdf | html. Default md+json.",
    )
    parser.add_argument(
        "--type",
        dest="rtype",
        default="cost_time_report",
        help="sub-tipo report. Default cost_time_report.",
    )
    parser.add_argument(
        "--slug",
        default="",
        help="override slug storage (kebab-case).",
    )
    parser.add_argument(
        "--pricing",
        default="",
        help="path pricing YAML, forwarded a compute-agentic-cost.py.",
    )
    parser.add_argument(
        "--rates",
        default="",
        help="path rates YAML, forwarded a compute-human-cost.py.",
    )
    parser.add_argument(
        "--config",
        default="factory.config.yaml",
        help="path config YAML. Default factory.config.yaml.",
    )
    args = parser.parse_args()

    # §1 — Normalise config to absolute path (relative → repo root)
    config_path = (
        args.config if os.path.isabs(args.config) else str(REPO_ROOT / args.config)
    )

    # §2 — Input validation
    try:
        scope: dict = json.loads(args.scope)
    except json.JSONDecodeError as exc:
        print(f"ERRORE: --scope non è JSON valido: '{args.scope}'. {exc}", file=sys.stderr)
        print(json.dumps({"status": "error", "error": "invalid --scope JSON"}))
        sys.exit(1)

    # --audience obbligatorio e a dominio chiuso (parita' con lo .sh, US-327)
    if not args.audience:
        print("ERRORE: --audience è obbligatorio (operativa|progetto|executive). "
              "Vedi US-037 §Business Rules / ADR-023 §C.", file=sys.stderr)
        print(json.dumps({"status": "error", "error": "missing required --audience"}))
        sys.exit(1)
    if args.audience not in ("operativa", "progetto", "executive"):
        print(f"ERRORE: --audience '{args.audience}' non valido (ammessi: operativa|progetto|executive).",
              file=sys.stderr)
        print(json.dumps({"status": "error", "error": f"invalid --audience: {args.audience}"}))
        sys.exit(1)

    if args.rtype != "cost_time_report":
        print(
            f"ERRORE: --type '{args.rtype}' non supportato in EP-009 (solo 'cost_time_report'). "
            "I tipi 'project_estimate'/'combined'/'accuracy_retrospective' arrivano con EP-010. "
            "Vedi ADR-024 §A.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"unsupported type: {args.rtype}"}))
        sys.exit(1)

    if args.fmt not in ("md", "json", "md+json", "pdf", "html"):
        print(f"ERRORE: --format '{args.fmt}' non valido (ammessi: md|json|md+json|pdf|html).",
              file=sys.stderr)
        print(json.dumps({"status": "error", "error": f"invalid --format: {args.fmt}"}))
        sys.exit(1)

    if args.fmt in ("pdf", "html"):
        if not shutil.which("pandoc"):
            print(
                f"ERRORE: formato '{args.fmt}' richiede un motore documentale esterno "
                "(pandoc) non disponibile. Installalo o usa --format md+json (default). "
                "Vedi US-037 §Business Rules / ADR-024.",
                file=sys.stderr,
            )
            print(
                json.dumps({
                    "status": "error",
                    "error": f"format {args.fmt} requires external document engine (pandoc)",
                })
            )
            sys.exit(1)
        print(
            f"WARNING generate_report: formato '{args.fmt}' richiesto; "
            "md+json sono comunque prodotti come baseline di audit. "
            f"Il rendering {args.fmt} è additivo.",
            file=sys.stderr,
        )

    # §3 — Master switch (R.P3, ADR-021 §F)
    enabled = _yaml_nested(config_path, "measurement", "enabled")
    if enabled != "true":
        print(
            "generate_report: analytics.measurement.enabled non è true (no-op, R.P3).",
            file=sys.stderr,
        )
        sys.exit(0)

    # §4 — Optional config flags
    report_cache = (
        _yaml_nested(config_path, "measurement", "report_compression_savings") == "true"
    )
    price_drift_days_raw = _yaml_nested(config_path, "measurement", "pricing_drift_warn_days")
    price_drift_days = int(price_drift_days_raw) if price_drift_days_raw else 90

    # §5 — Audience mapping for sub-tools
    tool_audience = "project" if args.audience == "progetto" else args.audience

    # §6 — Build --filter from scope
    filt: dict = {}
    if scope.get("project_id"):
        filt["project_id"] = scope["project_id"]
    if scope.get("task_type"):
        filt["task_type"] = scope["task_type"]
    period = scope.get("period")
    if isinstance(period, dict):
        filt["period"] = period
    filt_json = json.dumps(filt)

    # §7 — Invoke sub-tools
    agentic_args = ["--filter", filt_json, "--config", config_path]
    if args.pricing:
        agentic_args += ["--pricing", args.pricing]

    human_args = [
        "--filter", filt_json,
        "--audience", tool_audience,
        "--config", config_path,
    ]
    if args.rates:
        human_args += ["--rates", args.rates]

    timeline_args = ["--filter", filt_json, "--config", config_path]

    sub_tools: list[tuple[str, Path, list[str]]] = [
        ("compute-agentic-cost", HERE / "compute-agentic-cost.py", agentic_args),
        ("compute-human-cost",   HERE / "compute-human-cost.py",   human_args),
        ("analyze-timeline",     HERE / "analyze-timeline.py",     timeline_args),
    ]

    raw_outputs: dict[str, str] = {}
    for name, tool_path, tool_args in sub_tools:
        stdout, rc = _run_subtool(tool_path, tool_args)
        if rc != 0:
            print(
                f"ERRORE: sub-tool {name} è uscito con codice {rc}. "
                "Report non producibile. Rilancia il tool isolato per il dettaglio dell'errore.",
                file=sys.stderr,
            )
            print(
                json.dumps({
                    "status": "error",
                    "error": f"sub-tool {name} failed with exit {rc}",
                })
            )
            sys.exit(1)
        raw_outputs[name] = stdout.strip()

    defaults_map: dict[str, dict] = {
        "compute-agentic-cost": AGENTIC_DEFAULT,
        "compute-human-cost":   HUMAN_DEFAULT,
        "analyze-timeline":     TIMELINE_DEFAULT,
    }
    parsed: dict[str, dict] = {}
    for name, raw in raw_outputs.items():
        if not raw:
            parsed[name] = defaults_map[name]
        else:
            try:
                parsed[name] = json.loads(raw)
            except json.JSONDecodeError:
                print(
                    f"ERRORE: output del sub-tool '{name}' non è JSON valido. "
                    "Report non producibile.",
                    file=sys.stderr,
                )
                print(
                    json.dumps({
                        "status": "error",
                        "error": f"sub-tool {name} emitted invalid JSON",
                    })
                )
                sys.exit(1)

    agentic_json  = parsed["compute-agentic-cost"]
    human_json    = parsed["compute-human-cost"]
    timeline_json = parsed["analyze-timeline"]

    # §8 — rate_basis (ADR-023 §E)
    rate_basis: str = human_json.get("rate_basis", "")

    # §9 — Pricing drift
    pricing_version: str = agentic_json.get("pricing_table_version", "")
    pricing_as_of_date = ""
    price_drift_note = ""

    if pricing_version:
        if re.match(r'^\d{4}-\d{2}-\d{2}$', pricing_version):
            pricing_as_of_date = pricing_version
        else:
            try:
                git_result = subprocess.run(
                    [
                        "git", "-C", str(REPO_ROOT),
                        "show", "-s", "--format=%cd", "--date=format:%Y-%m-%d",
                        pricing_version,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,  # git sotto carico: lo .sh non ha timeout, un fallback silenzioso cambierebbe l'output
                )
                if git_result.returncode == 0:
                    pricing_as_of_date = git_result.stdout.strip()
            except Exception:
                pass

    if pricing_as_of_date and re.match(r'^\d{4}-\d{2}-\d{2}$', pricing_as_of_date):
        try:
            then_dt = datetime.strptime(pricing_as_of_date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            now_dt = datetime.now(tz=timezone.utc)
            age_days = (now_dt - then_dt).days
            if age_days > price_drift_days:
                price_drift_note = (
                    f"WARNING drift prezzi: pricing_table non aggiornata da {age_days} giorni "
                    f"(ultimo aggiornamento {pricing_as_of_date}, soglia {price_drift_days}gg). "
                    "I costi potrebbero non riflettere le tariffe correnti. Vedi ADR-022 §F."
                )
        except ValueError:
            pass

    # §10 — Slug + periodo + storage routing (ADR-027 §A/§E)
    scope_id: str = scope.get("project_id") or scope.get("name", "")
    raw_period = scope.get("period", "")
    if isinstance(raw_period, str):
        scope_period = raw_period
    elif isinstance(raw_period, dict):
        p_from = raw_period.get("from", "")
        p_to = raw_period.get("to", "")
        scope_period = f"{p_from}_{p_to}"
    else:
        scope_period = str(raw_period) if raw_period else ""
    scope_period = re.sub(r'[^A-Za-z0-9._-]+', '-', scope_period).strip('-')

    slug = args.slug
    if not slug:
        slug = _kebab(scope_id) if scope_id else "adhoc"
    if not slug:
        slug = "adhoc"

    now_utc = datetime.now(tz=timezone.utc)
    generated_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = now_utc.strftime("%Y-%m-%d-%H-%M")

    reports_root = REPO_ROOT / "analytics" / "reports"
    if scope_id and scope_period:
        out_dir = reports_root / slug
        out_base = scope_period
        storage_kind = "scope"
    else:
        out_dir = reports_root / "_adhoc"
        out_base = f"{stamp}-{slug}"
        storage_kind = "adhoc"

    out_json = out_dir / f"{out_base}.json"
    out_md   = out_dir / f"{out_base}.md"

    # §11 — Report assembly (ADR-024 §A)
    agentic_cost: float = agentic_json.get("cost", 0) or 0
    human_cost:   float = human_json.get("cost", 0) or 0
    total_cost:   float = _jq_round((agentic_cost + human_cost) * 1_000_000) / 1_000_000
    currency: str = (
        agentic_json.get("currency") or human_json.get("currency") or "EUR"
    )

    # Split (ADR-024 §D) — derived, never hand-coded
    agentic_pct = _round2(agentic_cost / total_cost * 100) if total_cost > 0 else 0.0
    human_pct   = _round2(human_cost   / total_cost * 100) if total_cost > 0 else 0.0

    # cache_savings_pct (compression telemetry v2.14)
    bk = agentic_json.get("breakdown", {}).get("agentic_by_token_kind", {})
    cache_read:  float = bk.get("cache_read", 0) or 0
    cache_denom: float = (
        (bk.get("input", 0) or 0) + (bk.get("output", 0) or 0) + cache_read
    )
    cache_savings: float | None = (
        _round2(cache_read / cache_denom * 100)
        if (report_cache and cache_read > 0 and cache_denom > 0)
        else None
    )

    # Cost block (ADR-024 §B)
    cost_base: dict = {
        "agentic":  _round2(agentic_cost),
        "human":    _round2(human_cost),
        "total":    _round2(total_cost),
        "currency": currency,
    }
    if human_cost > 0:
        cost_base["rate_basis"] = rate_basis
    if cache_savings is not None:
        cost_base["agentic_cache_savings_pct"] = cache_savings

    # Breakdown audience-based (ADR-023 §C)
    per_actor = human_json.get("breakdown", {}).get("per_actor")
    actor_obj: dict = {"human_by_actor": per_actor} if per_actor is not None else {}

    if args.audience == "operativa":
        bd: dict = {
            "agentic_by_model":      agentic_json.get("breakdown", {}).get("per_model", {}),
            "agentic_by_token_kind": bk,
            "agentic_by_tool":       agentic_json.get("breakdown", {}).get("per_tool", {}),
            "human_by_role":         human_json.get("breakdown", {}).get("per_role", {}),
        }
        bd.update(actor_obj)
        cost_block: dict = dict(cost_base, breakdown=bd)
    elif args.audience == "progetto":
        bd = {"human_by_role": human_json.get("breakdown", {}).get("per_role", {})}
        bd.update(actor_obj)
        cost_block = dict(cost_base, breakdown=bd)
    else:
        cost_block = cost_base  # executive: no breakdown per-persona

    # Split block (ADR-024 §D)
    split_block: dict = {
        "agentic_pct":          agentic_pct,
        "human_pct":            human_pct,
        "agentic_share_of_cost": agentic_pct,
    }
    if cache_savings is not None:
        split_block["cache_savings_pct"] = cache_savings

    # Time block (ADR-024 §C) — pass-through percentiles, never means
    tl = timeline_json
    bottleneck_state: str | None = next(
        (b["state"] for b in tl.get("bottlenecks", []) if b.get("bottleneck")),
        None,
    )
    n_samples: int = tl.get("n_samples", 0)
    time_block: dict = {
        "lead_p50_days":     tl.get("lead", {}).get("p50", 0),
        "lead_p85_days":     tl.get("lead", {}).get("p85", 0),
        "lead_p95_days":     tl.get("lead", {}).get("p95", 0),
        "cycle_p50_days":    tl.get("cycle", {}).get("p50", 0),
        "cycle_p85_days":    tl.get("cycle", {}).get("p85", 0),
        "cycle_p95_days":    tl.get("cycle", {}).get("p95", 0),
        "effort_p50_hours":  tl.get("effort", {}).get("p50", 0),
        "effort_p85_hours":  tl.get("effort", {}).get("p85", 0),
        "wait_p50_days":     tl.get("wait", {}).get("p50", 0),
        "wait_p85_days":     tl.get("wait", {}).get("p85", 0),
        "bottleneck":        bottleneck_state if bottleneck_state is not None else "n/a",
        "bottleneck_state":  bottleneck_state,
        "n_samples":         n_samples,
    }

    # Operational block (only audience=operativa, US-037 §Business Rules)
    operational_block: dict | None = None
    if args.audience == "operativa":
        operational_block = dict(tl.get("operational", {}))
        operational_block["cost_per_task"] = (
            _round2(total_cost / n_samples) if n_samples > 0 else 0
        )

    # Notes (mandatory list, ADR-024 §A)
    notes: list[str] = []
    if pricing_version:
        note_ver = f"Pricing table version: {pricing_version}"
        if pricing_as_of_date:
            note_ver += f" (as-of {pricing_as_of_date})"
        notes.append(note_ver)
    notes.extend(human_json.get("notes", []))
    if price_drift_note:
        notes.append(price_drift_note)
    if n_samples < 10:
        notes.append(
            f"Time stats based on N={n_samples} samples; "
            "treat percentiles cautiously (ADR-024 §C)."
        )

    # Assemble full report (ADR-024 §A)
    report: dict = {
        "schema_version": "v1",
        "scope":          scope,
        "type":           args.rtype,
        "audience":       args.audience,
        "generated_at":   generated_at,
        "generated_by":   "generate-report.py (tool EP-009 US-037)",
        "cost":           cost_block,
        "time":           time_block,
        "split":          split_block,
    }
    if operational_block is not None:
        report["operational"] = operational_block
    report["notes"] = notes

    # §12 — Hard validations (fail-loud before write)

    # 12a. rate_basis obbligatorio se cost.human > 0 (ADR-023 §E)
    if (report["cost"].get("human") or 0) > 0 and not report["cost"].get("rate_basis"):
        print(
            "ERRORE: cost.human > 0 ma cost.rate_basis assente. "
            "Invariante ADR-023 §E violata: nessun costo umano senza base tariffaria esplicita. "
            "Verifica analytics/rates.yaml.rate_basis.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": "missing rate_basis with human cost > 0"}))
        sys.exit(1)

    # 12b. total = agentic + human (±0.01, ADR-024 §B)
    a_check = report["cost"].get("agentic", 0) or 0
    h_check = report["cost"].get("human", 0) or 0
    t_check = report["cost"].get("total", 0) or 0
    if abs(t_check - (a_check + h_check)) > 0.01:
        print(
            "ERRORE: cost.total != cost.agentic + cost.human (oltre tolleranza ±0.01). "
            "Invariante ADR-024 §B violata.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": "cost.total mismatch"}))
        sys.exit(1)

    # 12c. executive non deve esporre human_by_actor (ADR-023 §C)
    if args.audience == "executive":
        if report["cost"].get("breakdown", {}).get("human_by_actor") is not None:
            print(
                "ERRORE: audience executive non può esporre human_by_actor (actor_id raw). "
                "Invariante ADR-023 §C violata.",
                file=sys.stderr,
            )
            print(
                json.dumps({
                    "status": "error",
                    "error": "executive report exposes raw actor_id",
                })
            )
            sys.exit(1)

    # 12d. notes deve essere un array (ADR-024 §A)
    if not isinstance(report["notes"], list):
        print(
            "ERRORE: notes[] deve essere un array (anche vuoto). "
            "Invariante ADR-024 §A violata.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": "notes must be an array"}))
        sys.exit(1)

    # §13 — MD rendering is handled by _render_md()

    # §14 — Persist (ADR-027 §A single-writer logico)
    os.makedirs(out_dir, exist_ok=True)
    out_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    out_md.write_text(_render_md(jq_numbers(report), storage_kind) + "\n", encoding="utf-8")

    try:
        rel_json = str(out_json.relative_to(REPO_ROOT))
        rel_md   = str(out_md.relative_to(REPO_ROOT))
    except ValueError:
        rel_json = str(out_json)
        rel_md   = str(out_md)

    print(
        f"generate_report: report '{storage_kind}' (audience={args.audience}) "
        f"scritto in {rel_json} + {rel_md}.",
        file=sys.stderr,
    )

    # pdf/html: additivo best-effort via pandoc
    if args.fmt in ("pdf", "html"):
        if shutil.which("pandoc"):
            out_doc = out_dir / f"{out_base}.{args.fmt}"
            proc = subprocess.run(
                ["pandoc", str(out_md), "-o", str(out_doc)],
                capture_output=True,
            )
            if proc.returncode == 0:
                try:
                    rel_doc = str(out_doc.relative_to(REPO_ROOT))
                except ValueError:
                    rel_doc = str(out_doc)
                print(
                    f"generate_report: rendering additivo {args.fmt} prodotto in "
                    f"{rel_doc} (via pandoc).",
                    file=sys.stderr,
                )
            else:
                print(
                    f"WARNING generate_report: rendering {args.fmt} via pandoc fallito; "
                    "md+json restano l'output autoritativo.",
                    file=sys.stderr,
                )

    # §15 — Emit JSON report on stdout
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
