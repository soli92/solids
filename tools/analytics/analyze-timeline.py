#!/usr/bin/env python3
"""
analyze-timeline.py — tool deterministico analyze_timeline (EP-009, US-035, TSK-063)
Cross-platform replacement per analyze-timeline.sh (macOS / Linux / Windows).

READER agnostico dello store analytics/events/ scritto da record_task_event.
Filtra eventi, ricostruisce le timeline per task e calcola lead/cycle/wait/effort.

ADR-021 — store JSONL + SQLite (read path)
ADR-024 §C — sub-schema `time` standard (percentili p50/p85/p95)
INVARIANTE: mai campo mean/average/media nell'output — solo percentili.

CONTRATTO INPUT (CLI):
  --filter '<JSON>'      filtro opzionale, default {}
  --group-by <dim>       task_type | layer | actor_type | actor_id | state (opzionale)
  --config <path>        default "factory.config.yaml"

CONTRATTO OUTPUT (stdout, JSON puro) — schema US-035 / ADR-024 §C:
  { filter, group_by, lead{p50,p85,p95,unit}, cycle, effort, wait,
    bottlenecks[{state,p50_wait,share_of_lead,bottleneck}],
    operational{throughput_per_week,wip_avg,wip_max,split_human_pct,...},
    n_samples, events_considered }

EXIT CODES:
  0  analisi prodotta OR no-op (analytics.measurement.enabled non true)
  >0 errore (store invalido, filtro invalido, prerequisito)
"""
from __future__ import annotations

import sys
import json
import re
import math
import sqlite3
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent       # tools/analytics/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # tools/analytics/ → root factory (2 livelli)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytics_cli import ContractArgumentParser  # noqa: E402 — contratto CLI comune (US-327)


def _jq_round(x: float) -> float:
    """`round` di jq (C round: la meta' va lontano da zero), non l'arrotondamento bancario di Python.

    Parita' con gli .sh: `round(0.125 * 100)` vale 13 in jq e 12 in Python.
    """
    import math as _m
    return float(_m.copysign(_m.floor(abs(x) + 0.5), x))


# ---------------------------------------------------------------------------
# Helper: lettura config YAML (regex, stdlib-only)
# ---------------------------------------------------------------------------

def _yaml_nested(config_path: str, section: str, key: str) -> str:
    """Estrae <key> dal blocco analytics.<section>. Ritorna "" se assente."""
    try:
        content = Path(config_path).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return ""
    # Trova il blocco analytics:
    idx = content.find("analytics:")
    if idx == -1:
        return ""
    snippet = content[idx + len("analytics:"):]
    # Trova il sub-blocco section:
    sidx = snippet.find(f"{section}:")
    if sidx == -1:
        return ""
    sub = snippet[sidx + len(f"{section}:"):]
    for line in sub.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^[A-Za-z_]", line):
            break
        m = re.match(rf"\s+{re.escape(key)}\s*:\s*[\"']?([^\n\"'#\s]+)", line)
        if m:
            return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Helper: epoch UTC (parse ISO-8601)
# ---------------------------------------------------------------------------

def _to_epoch(ts: str) -> float | None:
    """Converte ISO-8601 in epoch seconds UTC. Ritorna None se non parsabile."""
    if not ts:
        return None
    # Strip frazioni di secondo
    ts2 = re.sub(r"\.\d+", "", ts)
    # Normalizza offset → UTC
    try:
        if ts2.endswith("Z"):
            dt = datetime.fromisoformat(ts2[:-1]).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(ts2)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return dt.timestamp()


# ---------------------------------------------------------------------------
# Helper: percentile nearest-rank (deterministico, NO media)
# ---------------------------------------------------------------------------

def _pct(values: list[float], p: float) -> float:
    """Nearest-rank percentile. $arr ordinato, p in (0,1]. Ritorna 0 se vuoto."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    r = math.ceil(p * n)
    r = max(1, min(r, n))
    return s[r - 1]


def _round2(x: float) -> float:
    return _jq_round(x * 100) / 100


# ---------------------------------------------------------------------------
# Filtering degli eventi
# ---------------------------------------------------------------------------

def _matches_filter(ev: dict, f: dict) -> bool:
    """Applica il filtro {project_id?, task_type?, actor_type?, layer?, period?}."""
    pid = f.get("project_id")
    tt  = f.get("task_type")
    at  = f.get("actor_type")
    ly  = f.get("layer")
    period = f.get("period", {}) or {}
    pfrom = period.get("from")
    pto   = period.get("to")

    if pid is not None and ev.get("project_id") != pid:
        return False
    if tt is not None and ev.get("task_type") != tt:
        return False
    if at is not None and ev.get("actor_type") != at:
        return False
    if ly is not None:
        ev_layer = ev.get("layer") or (ev.get("extras") or {}).get("layer")
        if ev_layer != ly:
            return False
    ts = ev.get("ts", "")
    if pfrom is not None and ts < pfrom:
        return False
    if pto is not None and ts >= pto:
        return False
    return True


# ---------------------------------------------------------------------------
# load_events: legge JSONL o SQLite e ritorna lista di eventi filtrati
# ---------------------------------------------------------------------------

def _load_jsonl(events_dir: Path, filt: dict, scan_warn: int) -> list[dict]:
    if not events_dir.is_dir():
        print(
            f"analyze_timeline: event store assente ({events_dir}). "
            "Nessun evento da analizzare (R.P3).",
            file=sys.stderr,
        )
        return []
    files = sorted(events_dir.glob("*.jsonl"))
    if not files:
        print(
            f"analyze_timeline: nessun file evento in {events_dir} (R.P3).",
            file=sys.stderr,
        )
        return []

    total_lines = 0
    events: list[dict] = []
    for fpath in files:
        try:
            lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        total_lines += len(lines)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _matches_filter(ev, filt):
                events.append(ev)

    if total_lines > scan_warn:
        print(
            f"WARNING analyze_timeline: volume alto rilevato ({total_lines} eventi "
            f"scansionati, soglia {scan_warn}). Considera 'store: sqlite' per "
            "ridurre la latenza. Vedi ADR-021 §D.",
            file=sys.stderr,
        )
    return events


def _load_sqlite(db_path: Path, filt: dict) -> list[dict]:
    if not db_path.exists():
        print(
            f"analyze_timeline: event store SQLite assente ({db_path}). "
            "Nessun evento da analizzare (R.P3).",
            file=sys.stderr,
        )
        return []
    try:
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM events ORDER BY ts").fetchall()
        con.close()
    except sqlite3.Error as exc:
        print(f"ERRORE: SQLite read error: {exc}", file=sys.stderr)
        print(json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)

    events: list[dict] = []
    for row in rows:
        ev: dict = {
            "task_id":    row["task_id"],
            "project_id": row["project_id"],
            "parent_id":  row["parent_id"],
            "actor_type": row["actor_type"],
            "actor_id":   row["actor_id"],
            "task_type":  row["task_type"],
            "state":      row["state"],
            "ts":         row["ts"],
            "model":      row["model"],
            "tokens": {
                "input":       row["tokens_input"],
                "output":      row["tokens_output"],
                "cache_read":  row["tokens_cache_read"],
                "cache_write": row["tokens_cache_write"],
            },
            "tool_calls": _safe_json(row["tool_calls"], []),
            "extras":     _safe_json(row["extras"], None),
        }
        if _matches_filter(ev, filt):
            events.append(ev)
    return events


def _safe_json(s: str | None, default):
    if not s:
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Calcolo metriche (traduzione diretta dall'algoritmo jq)
# ---------------------------------------------------------------------------

def _iso_week(epoch_s: float) -> str:
    """Ritorna la settimana ISO nel formato YYYY-Www (es. 2026-W35)."""
    dt = datetime.fromtimestamp(epoch_s, tz=timezone.utc)
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _compute_metrics(events: list[dict], group_by: str) -> dict:
    """Calcola lead/cycle/wait/effort/bottlenecks/operational. NO medie."""

    events_considered = len(events)

    # Raggruppa per task_id
    by_task: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        by_task[ev.get("task_id", "")].append(ev)

    tasks: list[dict] = []
    for task_id, evs in by_task.items():
        evs_sorted = sorted(evs, key=lambda e: e.get("ts", ""))
        ts_epochs = [_to_epoch(e.get("ts", "")) or 0.0 for e in evs_sorted]
        m = len(evs_sorted)
        t0 = ts_epochs[0] if ts_epochs else 0.0
        actor_type = evs_sorted[0].get("actor_type", "") if evs_sorted else ""

        # tf = ultimo ts dove state == 'finished'
        finished_ts = [
            _to_epoch(e.get("ts", "")) or 0.0
            for e in evs_sorted if e.get("state") == "finished"
        ]
        tf = finished_ts[-1] if finished_ts else None

        # Intervalli consecutivi
        intervals: list[dict] = []
        for i in range(m - 1):
            intervals.append({
                "from_state": evs_sorted[i].get("state", ""),
                "dur": ts_epochs[i + 1] - ts_epochs[i],
            })

        # cycle = intervalli partenti da 'started' [secondi]
        cycle_s = sum(iv["dur"] for iv in intervals if iv["from_state"] == "started")
        # wait intervals (tutto tranne 'started')
        wait_ints = [iv for iv in intervals if iv["from_state"] != "started"]

        lead_s = (tf - t0) if tf is not None else None
        wait_s = (lead_s - cycle_s) if lead_s is not None else None

        # Effort: human → extras.effort_hours (override) | agent → cycle ore
        eff_override = None
        for e in evs_sorted:
            ex = e.get("extras") or {}
            if isinstance(ex, dict) and "effort_hours" in ex:
                eff_override = float(ex["effort_hours"])
        if actor_type == "human":
            effort_h = eff_override if eff_override is not None else 0.0
        else:
            effort_h = cycle_s / 3600.0

        tasks.append({
            "task_id":     task_id,
            "actor_type":  actor_type,
            "lead_days":   (lead_s / 86400.0) if lead_s is not None else None,
            "cycle_days":  cycle_s / 86400.0,
            "wait_days":   (wait_s / 86400.0) if wait_s is not None else None,
            "effort_hours": effort_h,
            "finished":    tf is not None,
            "first_ts":    t0,
            "last_ts":     ts_epochs[-1] if ts_epochs else t0,
            "wait_by_state": [
                {"state": iv["from_state"], "dur_days": iv["dur"] / 86400.0}
                for iv in wait_ints
            ],
        })

    # Solo task completati → percentili
    done = [t for t in tasks if t["finished"] and t["lead_days"] is not None]

    lead_arr   = [_round2(t["lead_days"])   for t in done]
    cycle_arr  = [_round2(t["cycle_days"])  for t in done]
    wait_arr   = [_round2(t["wait_days"])   for t in done if t["wait_days"] is not None]
    effort_arr = [_round2(t["effort_hours"]) for t in done]

    # Bottlenecks: wait accumulato per stato
    state_wait: dict[str, list[float]] = defaultdict(list)
    for t in tasks:
        for wbs in t["wait_by_state"]:
            state_wait[wbs["state"]].append(wbs["dur_days"])

    total_lead = sum(t["lead_days"] for t in done) or 0.0
    bottlenecks_raw = []
    for state, waits in state_wait.items():
        p50w = _round2(_pct(waits, 0.5))
        sum_w = sum(waits)
        share = _round2(sum_w / total_lead) if total_lead > 0 else 0.0
        bottlenecks_raw.append({
            "state": state,
            "p50_wait": p50w,
            "share_of_lead": share,
        })
    bottlenecks_raw.sort(key=lambda x: -x["p50_wait"])
    bottlenecks = [
        {**b, "bottleneck": (i == 0)}
        for i, b in enumerate(bottlenecks_raw)
    ]

    # Operational: throughput/week, WIP
    if events:
        all_ts = [_to_epoch(e.get("ts", "")) or 0.0 for e in events]
        span_min, span_max = min(all_ts), max(all_ts)
        weeks_raw = (span_max - span_min) / 604800.0
        weeks = max(1.0, weeks_raw)
    else:
        weeks = 1.0

    throughput = _round2(len(done) / weeks)
    wip_now = len([t for t in tasks if not t["finished"]])
    worked_tasks = len([t for t in tasks if t["cycle_days"] > 0])
    wip_avg = _round2(worked_tasks / weeks)

    # Split human/agent
    human_lead = sum(t["lead_days"] for t in done if t["actor_type"] == "human" and t["lead_days"])
    agent_lead = sum(t["lead_days"] for t in done if t["actor_type"] == "agent" and t["lead_days"])
    tot_lead2 = human_lead + agent_lead
    human_pct = _round2(human_lead / tot_lead2 * 100) if tot_lead2 > 0 else 0.0
    agent_pct = _round2(agent_lead / tot_lead2 * 100) if tot_lead2 > 0 else 0.0

    # Trend settimanale lead_p50
    week_leads: dict[str, list[float]] = defaultdict(list)
    for t in done:
        w = _iso_week(t["first_ts"])
        week_leads[w].append(t["lead_days"])
    trend = [
        {"week": w, "lead_p50": _round2(_pct(leads, 0.5))}
        for w, leads in sorted(week_leads.items())
    ]

    return {
        "lead":  {"p50": _round2(_pct(lead_arr, 0.5)),  "p85": _round2(_pct(lead_arr, 0.85)),  "p95": _round2(_pct(lead_arr, 0.95)),  "unit": "days"},
        "cycle": {"p50": _round2(_pct(cycle_arr, 0.5)), "p85": _round2(_pct(cycle_arr, 0.85)), "p95": _round2(_pct(cycle_arr, 0.95)), "unit": "days"},
        "effort":{"p50": _round2(_pct(effort_arr, 0.5)),"p85": _round2(_pct(effort_arr, 0.85)),"p95": _round2(_pct(effort_arr, 0.95)),"unit": "hours"},
        "wait":  {"p50": _round2(_pct(wait_arr, 0.5)),  "p85": _round2(_pct(wait_arr, 0.85)),  "p95": _round2(_pct(wait_arr, 0.95)),  "unit": "days"},
        "bottlenecks": bottlenecks,
        "operational": {
            "throughput_per_week": throughput,
            "wip_avg": wip_avg,
            "wip_max": wip_now,
            "split_human_pct": human_pct,
            "split_agent_pct": agent_pct,
            "trend": trend,
        },
        "n_samples": len(done),
        "events_considered": events_considered,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_VALID_GROUP_BY = {"task_type", "layer", "actor_type", "actor_id", "state"}


def main() -> int:
    parser = ContractArgumentParser(
        description="analyze_timeline — EP-009 US-035 ADR-024 §C.",
        add_help=True,
    )
    parser.add_argument("--filter",   default="{}", help="Filtro JSON (default {}).")
    parser.add_argument("--group-by", default="",   dest="group_by",
                        help="Dimensione di raggruppamento opzionale.")
    parser.add_argument("--config",   default="factory.config.yaml",
                        help="Path factory.config.yaml.")
    args = parser.parse_args()

    # Normalizza config a path assoluto
    config_path = str(
        (REPO_ROOT / args.config).resolve()
        if not Path(args.config).is_absolute()
        else Path(args.config).resolve()
    )

    # Valida --filter
    try:
        filt = json.loads(args.filter)
    except json.JSONDecodeError as exc:
        print(f"ERRORE: --filter non è JSON valido: {exc}", file=sys.stderr)
        print(json.dumps({"status": "error", "error": "invalid --filter JSON"}))
        return 1

    # Valida --group-by
    group_by = args.group_by.strip()
    if group_by and group_by not in _VALID_GROUP_BY:
        valid = "|".join(sorted(_VALID_GROUP_BY))
        print(
            f"ERRORE: --group-by '{group_by}' non valido (ammessi: {valid}).",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"invalid --group-by: {group_by}"}))
        return 1

    # Master switch (R.P3)
    enabled = _yaml_nested(config_path, "measurement", "enabled")
    if enabled != "true":
        print(
            "analyze_timeline: analytics.measurement.enabled non è true (no-op, R.P3).",
            file=sys.stderr,
        )
        return 0

    store = _yaml_nested(config_path, "measurement", "store") or "jsonl"
    if store not in ("jsonl", "sqlite"):
        print(
            f"ERRORE: analytics.measurement.store deve essere 'jsonl' o 'sqlite' "
            f"(trovato: '{store}'). Vedi ADR-021 §C.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"invalid store: {store}"}))
        return 1

    scan_warn_raw = _yaml_nested(config_path, "measurement", "jsonl_scan_warn_lines")
    scan_warn = int(scan_warn_raw) if scan_warn_raw.isdigit() else 500000

    events_dir = REPO_ROOT / "analytics" / "events"
    db_path    = REPO_ROOT / "analytics" / "events.db"

    if store == "jsonl":
        events = _load_jsonl(events_dir, filt, scan_warn)
    else:
        events = _load_sqlite(db_path, filt)

    metrics = _compute_metrics(events, group_by)

    output = {
        "filter":   filt,
        "group_by": group_by or None,
        **metrics,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
