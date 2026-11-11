#!/usr/bin/env python3
"""
compute-human-cost.py — tool deterministico compute_human_cost (EP-009, US-034, TSK-062)
Cross-platform replacement per compute-human-cost.sh (macOS / Linux / Windows).

READER agnostico dello store analytics/events/ (actor_type: human) + READER
della rate card versionata analytics/rates.yaml. Filtra eventi umani, risolve
actor_id → role_id, applica la formula costo umano, fa enforcement privacy N>=5
ed emette JSON puro. L'interpretazione narrativa è scope della skill, mai di
questo tool.

PATTERN.md §3 — operazione canonica opzionale «Cost Computation» (Human Cost):
  - aggregazione minima N>=5 sui dati personali (ADR-023 §C).
  - rate_basis esplicito in ogni output che usa la rate card (ADR-023 §E).

FORMULA verbatim (concept §2.2):
    costo_umano(task) = ore_sforzo · tariffa_ruolo    # da rate_card
  ore_sforzo: da effort_hours (extras evento, override esplicito) oppure
    auto-derivato da ts(finished) - ts(started).
  tariffa_ruolo: da analytics/rates.yaml, selezionata per valid_from valido
    al timestamp dell'effort. MAI hardcodata nel codice.

ADR-022 — schema rate_card (analytics/rates.yaml): YAML versionato git con
  valid_from semi-aperto a destra (§E), canonical role id + aliases (§C),
  rate_basis a livello file obbligatorio (§C), resolution role/valid_from (§D).
ADR-023 — contratto tool analytics (§A stateless, stdout=JSON, stderr=log):
  §C — aggregazione minima N>=5.
  §D — actor_id → role_id cascade.
  §E — rate_basis esplicito + fail-loud su mismatch config vs file.

CONTRATTO INPUT (CLI):
  --task-id <id>        analizza un singolo task (mutuamente escl. con --filter).
  --filter '<JSON>'     filtro su event store, default {} (aggregato globale).
                        Shape: {project_id?, task_type?, period?:{from,to}}.
  --rates <path>        rate card, default analytics/rates.yaml.
  --audience <lvl>      executive | project | operativa (default operativa).
  --rate-as-of <date>   proiezione what-if: forza resolution valid_from a una
                        data ISO-8601 specifica (ADR-022 §F).
  --config <path>       default factory.config.yaml (ADR-023 §A).

CONTRATTO OUTPUT (stdout, JSON puro) — schema US-034 / ADR-023 §E:
  {
    "cost": float, "currency": "EUR",
    "rate_basis": "fully-loaded|bill-rate",
    "breakdown": { "per_role": {...}, "per_actor": {...} },
    "events_considered": int,
    "rate_card_version": str,
    "notes": [...]
  }

EXIT CODES:
  0  costo calcolato OR no-op (analytics.measurement.enabled non true, R.P3).
  >0 errore (prerequisito mancante, rate card assente/illeggibile, mismatch
     rate_basis, argomenti invalidi).
"""
from __future__ import annotations

import sys
import json
import re
import sqlite3
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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
# §3 Helper: lettura config YAML (regex pura, stdlib-only)
# ---------------------------------------------------------------------------

def _yaml_nested(config_path: str, section: str, key: str) -> str:
    """Estrae <key> dal blocco analytics.<section>. Ritorna '' se assente."""
    try:
        content = Path(config_path).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return ""
    idx = content.find("analytics:")
    if idx == -1:
        return ""
    snippet = content[idx + len("analytics:"):]
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
# Helper: epoch UTC (parse ISO-8601) — stessa logica di analyze-timeline.py
# ---------------------------------------------------------------------------

def _to_epoch(ts: str) -> float | None:
    """Converte ISO-8601 in epoch seconds UTC. Ritorna None se non parsabile."""
    if not ts:
        return None
    ts2 = re.sub(r"\.\d+", "", ts)
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


def _round2(x: float) -> float:
    return _jq_round(x * 100) / 100


# ---------------------------------------------------------------------------
# §5 Rate card parser (regex pura, no PyYAML)
# ---------------------------------------------------------------------------

def _parse_rates_yaml(path: Path) -> dict:
    """
    Parsa analytics/rates.yaml con parser regex puro. Ritorna:
    {
      "currency": str,
      "rate_basis": str,
      "roles": [
        {
          "id": str,
          "display_name": str,
          "aliases": [str],
          "rates": [{"valid_from": str, "hourly_rate": float}]
        }
      ]
    }
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"ERRORE: impossibile leggere rate card '{path}': {exc}", file=sys.stderr)
        print(json.dumps({"status": "error", "error": f"cannot read rate card: {exc}"}))
        sys.exit(1)

    def _strip_comment(s: str) -> str:
        idx = s.find("#")
        return s[:idx] if idx != -1 else s

    def _unq(s: str) -> str:
        return s.strip().strip("\"'")

    currency = "EUR"
    rate_basis = ""
    roles: list[dict] = []

    state = "top"
    cur_role: dict | None = None
    cur_rate_entry: dict | None = None
    in_aliases = False
    in_rates = False

    for raw_line in lines:
        raw = _strip_comment(raw_line)
        line = raw.strip()
        if not line:
            continue

        if state == "top":
            if line.startswith("currency:"):
                currency = _unq(line[len("currency:"):])
            elif line.startswith("rate_basis:"):
                rate_basis = _unq(line[len("rate_basis:"):])
            elif line.startswith("roles:"):
                state = "roles"
            continue

        # state == "roles"
        m_id = re.match(r"^-\s*id:\s*(.+)$", line)
        if m_id:
            if cur_role is not None:
                if cur_rate_entry is not None:
                    cur_role["rates"].append(cur_rate_entry)
                    cur_rate_entry = None
                roles.append(cur_role)
            cur_role = {
                "id": _unq(m_id.group(1)),
                "display_name": "",
                "aliases": [],
                "rates": [],
            }
            in_aliases = False
            in_rates = False
            continue

        if cur_role is None:
            continue

        if line.startswith("display_name:"):
            cur_role["display_name"] = _unq(line[len("display_name:"):])
            in_aliases = False
            in_rates = False
            continue

        if line.startswith("aliases:"):
            in_aliases = True
            in_rates = False
            continue

        if line.startswith("rates:"):
            in_rates = True
            in_aliases = False
            continue

        if in_aliases and line.startswith("-"):
            val = _unq(line[1:].strip())
            if val:
                cur_role["aliases"].append(val)
            continue

        if in_rates:
            m_vf = re.match(r"^-\s*valid_from:\s*(.+)$", line)
            if m_vf:
                if cur_rate_entry is not None:
                    cur_role["rates"].append(cur_rate_entry)
                cur_rate_entry = {"valid_from": _unq(m_vf.group(1)), "hourly_rate": 0.0}
                continue
            if line.startswith("hourly_rate:") and cur_rate_entry is not None:
                try:
                    cur_rate_entry["hourly_rate"] = float(_unq(line[len("hourly_rate:"):]))
                except ValueError:
                    pass
                continue

    if cur_role is not None:
        if cur_rate_entry is not None:
            cur_role["rates"].append(cur_rate_entry)
        roles.append(cur_role)

    return {"currency": currency, "rate_basis": rate_basis, "roles": roles}


# ---------------------------------------------------------------------------
# §5.4 rate_card_version: git hash del file o mtime come fallback
# ---------------------------------------------------------------------------

def _rate_card_version(rates_path: Path) -> str:
    """Ritorna git hash short del file se disponibile, altrimenti mtime YYYY-MM-DD."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "-1", "--format=%h", "--", str(rates_path)],
            capture_output=True,
            text=True,
            timeout=120,  # git sotto carico: lo .sh non ha timeout, un fallback silenzioso cambierebbe l'output
        )
        gh = result.stdout.strip()
        if gh:
            return gh
    except Exception:
        pass
    try:
        mtime = rates_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return "unknown"


# ---------------------------------------------------------------------------
# §6 Actors map — cascade analytics/actors.yaml → config.actors_map (ADR-023 §D)
# ---------------------------------------------------------------------------

def _parse_actors_section(path: Path, container: str) -> dict[str, str]:
    """
    Estrae coppie key: value dalla sezione <container>: (prima occorrenza nel file).
    Funziona indipendentemente dall'indentazione del container.
    """
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return result

    def _strip_comment(s: str) -> str:
        idx = s.find("#")
        return s[:idx] if idx != -1 else s

    in_container = False
    container_indent = -1

    for raw_line in lines:
        raw = _strip_comment(raw_line)
        line = raw.strip()
        if not line:
            continue
        ind = len(raw) - len(raw.lstrip(" "))

        if not in_container:
            if line == f"{container}:":
                in_container = True
                container_indent = ind
            continue

        if ind <= container_indent:
            break

        m = re.match(r"^([A-Za-z0-9._-]+)\s*:\s*([A-Za-z0-9._-]+)\s*$", line)
        if m:
            result[m.group(1)] = m.group(2)

    return result


def _load_actors_map(config_path: str) -> dict[str, str]:
    """
    Cascade ADR-023 §D:
      Priorità 1: analytics/actors.yaml (sezione actors:)
      Priorità 2: factory.config.yaml (sezione actors_map:)
    File ha precedenza: cfg_map | file_map.
    """
    actors_file = REPO_ROOT / "analytics" / "actors.yaml"
    cfg_path = Path(config_path)

    cfg_map: dict[str, str] = {}
    if cfg_path.exists():
        cfg_map = _parse_actors_section(cfg_path, "actors_map")

    file_map: dict[str, str] = {}
    if actors_file.exists():
        file_map = _parse_actors_section(actors_file, "actors")

    return {**cfg_map, **file_map}


# ---------------------------------------------------------------------------
# §7 load_events — solo actor_type == "human" (ADR-021 §D)
# ---------------------------------------------------------------------------

def _safe_json(s: str | None, default):
    if not s:
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


def _matches_filter(ev: dict, filt: dict, task_id: str) -> bool:
    """Filtra evento: actor_type=human + task_id opzionale + filtro JSON."""
    if ev.get("actor_type") != "human":
        return False
    if task_id and ev.get("task_id") != task_id:
        return False
    pid = filt.get("project_id")
    tt = filt.get("task_type")
    period = filt.get("period") or {}
    pfrom = period.get("from")
    pto = period.get("to")
    if pid is not None and ev.get("project_id") != pid:
        return False
    if tt is not None and ev.get("task_type") != tt:
        return False
    ts = ev.get("ts", "")
    if pfrom is not None and ts < pfrom:
        return False
    if pto is not None and ts >= pto:
        return False
    return True


def _load_events_jsonl(events_dir: Path, filt: dict, task_id: str) -> list[dict]:
    if not events_dir.is_dir():
        print(
            f"compute_human_cost: event store assente ({events_dir}). "
            "Nessun evento (R.P3).",
            file=sys.stderr,
        )
        return []
    files = sorted(events_dir.glob("*.jsonl"))
    if not files:
        print(
            f"compute_human_cost: nessun file evento in {events_dir} (R.P3).",
            file=sys.stderr,
        )
        return []
    events: list[dict] = []
    for fpath in files:
        try:
            lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _matches_filter(ev, filt, task_id):
                events.append(ev)
    return events


def _load_events_sqlite(db_path: Path, filt: dict, task_id: str) -> list[dict]:
    if not db_path.exists():
        print(
            f"compute_human_cost: event store SQLite assente ({db_path}). "
            "Nessun evento (R.P3).",
            file=sys.stderr,
        )
        return []
    try:
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM events WHERE actor_type='human' ORDER BY ts"
        ).fetchall()
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
        if _matches_filter(ev, filt, task_id):
            events.append(ev)
    return events


def load_events(store: str, filt: dict, task_id: str) -> list[dict]:
    events_dir = REPO_ROOT / "analytics" / "events"
    db_path = REPO_ROOT / "analytics" / "events.db"
    if store == "jsonl":
        return _load_events_jsonl(events_dir, filt, task_id)
    return _load_events_sqlite(db_path, filt, task_id)


# ---------------------------------------------------------------------------
# §8 Calcolo costo umano per task (formula §2.2 verbatim)
# ---------------------------------------------------------------------------

def _pick_pricing(rates_entries: list[dict], as_of: str) -> dict | None:
    """Seleziona l'ultima entry con valid_from <= as_of (semi-aperto a destra, ADR-022 §E)."""
    sorted_entries = sorted(rates_entries, key=lambda r: r.get("valid_from", ""))
    pick = None
    for entry in sorted_entries:
        if entry.get("valid_from", "") <= as_of:
            pick = entry
    return pick


def _resolve_rate(rates: dict, role_id: str, as_of: str) -> dict:
    """
    Cerca role_id (id canonico o alias) nelle roles, poi applica valid_from.
    Ritorna {"rate": float, "found": bool, "reason": str, "canonical_role": str}.
    Non fail-loud: rate=0 + found=False su miss (ADR-023 §D).
    """
    matched = None
    for r in rates.get("roles", []):
        if r["id"] == role_id or role_id in r.get("aliases", []):
            matched = r
            break

    if matched is None:
        return {
            "rate": 0.0,
            "found": False,
            "reason": "role-not-found",
            "canonical_role": role_id,
        }

    pick = _pick_pricing(matched.get("rates", []), as_of)
    if pick is None:
        return {
            "rate": 0.0,
            "found": False,
            "reason": "no-valid-from-before-asof",
            "canonical_role": matched["id"],
        }

    return {
        "rate": float(pick.get("hourly_rate", 0.0)),
        "found": True,
        "reason": "ok",
        "canonical_role": matched["id"],
    }


def _compute_costs(
    events: list[dict],
    rates: dict,
    actors_map: dict[str, str],
    rate_as_of: str,
) -> dict:
    """
    Calcola costi per task raggruppando per task_id.
    Ritorna aggregazioni + warning collectors.
    """
    # Raggruppa per task_id
    by_task: dict[str, list[dict]] = {}
    for ev in events:
        tid = ev.get("task_id", "")
        if tid not in by_task:
            by_task[tid] = []
        by_task[tid].append(ev)

    task_costs: list[dict] = []

    for task_id, evs in by_task.items():
        evs_sorted = sorted(evs, key=lambda e: e.get("ts", ""))

        actor_id = evs_sorted[0].get("actor_id", "") if evs_sorted else ""
        role_id = actors_map.get(actor_id, "unknown")

        # effort_hours: override = ultimo non-null tra gli eventi del task
        eff_override: float | None = None
        for e in evs_sorted:
            ex = e.get("extras") or {}
            if isinstance(ex, dict) and ex.get("effort_hours") is not None:
                try:
                    eff_override = float(ex["effort_hours"])
                except (TypeError, ValueError):
                    pass

        # ts del primo started e ultimo finished (derivazione effort + as_of)
        ts_starts = [e.get("ts") for e in evs_sorted if e.get("state") == "started" and e.get("ts")]
        ts_finishes = [e.get("ts") for e in evs_sorted if e.get("state") == "finished" and e.get("ts")]
        ts_start = ts_starts[0] if ts_starts else None
        ts_finish = ts_finishes[-1] if ts_finishes else None

        # effort derivato da delta ts
        eff_derived = 0.0
        if ts_start and ts_finish:
            e_s = _to_epoch(ts_start)
            e_f = _to_epoch(ts_finish)
            if e_s is not None and e_f is not None:
                eff_derived = (e_f - e_s) / 3600.0

        hours = eff_override if eff_override is not None else eff_derived

        # as_of per resolution tariffa: --rate-as-of (proiezione) o ts effort
        if rate_as_of:
            as_of = rate_as_of
        else:
            ref_ts = ts_finish or ts_start or (evs_sorted[0].get("ts") if evs_sorted else None)
            as_of = ref_ts[:10] if ref_ts else ""

        rr = _resolve_rate(rates, role_id, as_of)
        cost_task = _round2(hours * rr["rate"])

        task_costs.append({
            "task_id":     task_id,
            "actor_id":    actor_id,
            "role_id":     rr["canonical_role"],
            "hours":       _round2(hours),
            "rate":        rr["rate"],
            "rate_found":  rr["found"],
            "rate_reason": rr["reason"],
            "cost":        cost_task,
        })

    total = _round2(sum(t["cost"] for t in task_costs))
    distinct_actors = len({t["actor_id"] for t in task_costs if t["actor_id"]})

    per_role: dict[str, float] = {}
    per_actor: dict[str, float] = {}
    for t in task_costs:
        rid = t["role_id"]
        aid = t["actor_id"]
        per_role[rid] = _round2(per_role.get(rid, 0.0) + t["cost"])
        per_actor[aid] = _round2(per_actor.get(aid, 0.0) + t["cost"])

    # Warning collectors per §9
    unmapped_actors = sorted({
        t["actor_id"]
        for t in task_costs
        if t["role_id"] == "unknown" and t["actor_id"]
    })
    seen_misses: set[tuple[str, str]] = set()
    rate_misses: list[dict] = []
    for t in task_costs:
        if not t["rate_found"] and t["cost"] == 0.0 and t["hours"] > 0:
            key = (t["role_id"], t["rate_reason"])
            if key not in seen_misses:
                seen_misses.add(key)
                rate_misses.append({"role": t["role_id"], "reason": t["rate_reason"]})

    return {
        "total":            total,
        "distinct_actors":  distinct_actors,
        "per_role":         per_role,
        "per_actor":        per_actor,
        "events_considered": len(events),
        "unmapped_actors":  unmapped_actors,
        "rate_misses":      rate_misses,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_VALID_AUDIENCE = ("executive", "project", "operativa")


def main() -> int:
    parser = ContractArgumentParser(
        description="compute_human_cost — EP-009 US-034 ADR-022/023.",
        add_help=True,
    )
    parser.add_argument(
        "--task-id", default="", dest="task_id",
        help="Analizza un singolo task (esclusivo con --filter).",
    )
    parser.add_argument(
        "--filter", default="{}",
        help="Filtro JSON (default {}).",
    )
    parser.add_argument(
        "--rates", default="",
        help="Path rate card YAML (default analytics/rates.yaml).",
    )
    parser.add_argument(
        "--audience", default="operativa",
        help="executive | project | operativa (default operativa).",
    )
    parser.add_argument(
        "--rate-as-of", default="", dest="rate_as_of",
        help="Data ISO-8601 YYYY-MM-DD per proiezione tariffa (ADR-022 §F).",
    )
    parser.add_argument(
        "--config", default="factory.config.yaml",
        help="Path factory.config.yaml (default factory.config.yaml).",
    )
    args = parser.parse_args()

    # --task-id e --filter mutuamente esclusivi
    if args.task_id and args.filter != "{}":
        print("ERRORE: --task-id e --filter sono mutuamente esclusivi.", file=sys.stderr)
        print(json.dumps({"status": "error", "error": "--task-id and --filter are mutually exclusive"}))
        return 1

    # Valida audience (ADR-023 §C)
    if args.audience not in _VALID_AUDIENCE:
        print(
            f"ERRORE: --audience '{args.audience}' non valido "
            f"(ammessi: executive|project|operativa). Vedi ADR-023 §C.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"invalid --audience: {args.audience}"}))
        return 1

    # Valida --filter JSON (fail-loud)
    try:
        filt = json.loads(args.filter)
    except json.JSONDecodeError as exc:
        print(f"ERRORE: --filter non è JSON valido: {exc}", file=sys.stderr)
        print(json.dumps({"status": "error", "error": "invalid --filter JSON"}))
        return 1

    # Valida --rate-as-of se presente
    rate_as_of = args.rate_as_of.strip()
    if rate_as_of and not re.match(r"^\d{4}-\d{2}-\d{2}$", rate_as_of):
        print(
            f"ERRORE: --rate-as-of '{rate_as_of}' non è una data ISO-8601 (YYYY-MM-DD).",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"invalid --rate-as-of: {rate_as_of}"}))
        return 1

    # Normalizza config a path assoluto
    config_path = str(
        (REPO_ROOT / args.config).resolve()
        if not Path(args.config).is_absolute()
        else Path(args.config).resolve()
    )

    # §4 Master switch — no-op se capability spenta (R.P3, ADR-023 §I)
    enabled = _yaml_nested(config_path, "measurement", "enabled")
    if enabled != "true":
        print(
            "compute_human_cost: analytics.measurement.enabled non è true (no-op, R.P3).",
            file=sys.stderr,
        )
        return 0

    # §4b Config values (con default ADR-021/022/023)
    store = _yaml_nested(config_path, "measurement", "store") or "jsonl"
    if store not in ("jsonl", "sqlite"):
        print(
            f"ERRORE: analytics.measurement.store deve essere 'jsonl' o 'sqlite' "
            f"(trovato: '{store}'). Vedi ADR-021 §C.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"invalid store: {store}"}))
        return 1

    # rate_card_path: --rates ha precedenza, poi config, poi default
    rates_cli = args.rates.strip()
    if rates_cli:
        rates_path_raw = rates_cli
    else:
        rates_path_raw = (
            _yaml_nested(config_path, "measurement", "rate_card_path")
            or "analytics/rates.yaml"
        )
    rates_path = (
        Path(rates_path_raw)
        if Path(rates_path_raw).is_absolute()
        else REPO_ROOT / rates_path_raw
    )

    # min_aggregation_n: default 5, floor 1 (ADR-023 §C)
    min_n_raw = _yaml_nested(config_path, "measurement", "min_aggregation_n")
    try:
        min_n = int(min_n_raw) if min_n_raw else 5
        if min_n < 1:
            raise ValueError("floor 1")
    except ValueError:
        print(
            f"ERRORE: analytics.measurement.min_aggregation_n deve essere intero >= 1 "
            f"(trovato: '{min_n_raw}'). Vedi ADR-023 §C.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"invalid min_aggregation_n: {min_n_raw}"}))
        return 1

    # operational_show_actor_id: default false (safe, ADR-023 §C)
    op_show = _yaml_nested(config_path, "measurement", "operational_show_actor_id") or "false"

    # rate_basis da config per cross-file validation (ADR-023 §E)
    cfg_rate_basis = _yaml_nested(config_path, "measurement", "rate_basis")

    # §5 Rate card — fail-loud se assente a capability ON (ADR-022 §G)
    try:
        rel_rates = str(rates_path.relative_to(REPO_ROOT))
    except ValueError:
        rel_rates = str(rates_path)

    if not rates_path.exists():
        print(
            f"ERRORE: rate card '{rel_rates}' mancante ma analytics.measurement.enabled=true. "
            "Copia analytics/rates.yaml.template in analytics/rates.yaml e adatta. "
            "Vedi ADR-022 §B/§G.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"missing rate card: {rel_rates}"}))
        return 1

    if not rates_path.is_file():
        print(f"ERRORE: rate card '{rel_rates}' non leggibile.", file=sys.stderr)
        print(json.dumps({"status": "error", "error": f"unreadable rate card: {rel_rates}"}))
        return 1

    rates = _parse_rates_yaml(rates_path)

    # §5.2 rate_basis a livello file OBBLIGATORIO (ADR-022 §C, ADR-023 §E)
    file_rate_basis = rates.get("rate_basis", "")
    if not file_rate_basis:
        print(
            f"ERRORE: '{rel_rates}' privo di 'rate_basis' a livello file "
            "(obbligatorio: fully-loaded|bill-rate). Vedi ADR-022 §C, ADR-023 §E.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": "missing file-level rate_basis"}))
        return 1

    if file_rate_basis not in ("fully-loaded", "bill-rate"):
        print(
            f"ERRORE: rate_basis '{file_rate_basis}' non valido in '{rel_rates}' "
            "(ammessi: fully-loaded|bill-rate). Vedi ADR-022 §C.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"invalid rate_basis: {file_rate_basis}"}))
        return 1

    # §5.3 Validation cross-file (ADR-023 §E) — fail-loud su mismatch
    if cfg_rate_basis and cfg_rate_basis != file_rate_basis:
        print(
            f"ERRORE: mismatch rate_basis — factory.config.yaml dichiara '{cfg_rate_basis}' "
            f"ma '{rel_rates}' dichiara '{file_rate_basis}'. "
            "Allinea i due. Vedi ADR-023 §E.",
            file=sys.stderr,
        )
        print(json.dumps({
            "status": "error",
            "error": f"rate_basis mismatch: config={cfg_rate_basis} file={file_rate_basis}",
        }))
        return 1

    currency = rates.get("currency", "EUR")

    # §5.4 rate_card_version: git hash o mtime
    rate_card_version = _rate_card_version(rates_path)

    # §6 Actors map (cascade ADR-023 §D)
    actors_map = _load_actors_map(config_path)

    # §7 load_events — solo actor_type=human
    events = load_events(store, filt, args.task_id)

    # §8 Calcolo costi
    compute = _compute_costs(events, rates, actors_map, rate_as_of)

    # §9 Warning non bloccanti su stderr (ADR-023 §D)
    for actor_id in compute["unmapped_actors"]:
        print(
            f"WARNING compute_human_cost: actor_id '{actor_id}' non mappato a un role_id "
            "(cascade analytics/actors.yaml → factory.config.yaml.analytics.measurement.actors_map). "
            "Aggregato come role='unknown'. Vedi ADR-023 §D.",
            file=sys.stderr,
        )
    for miss in compute["rate_misses"]:
        print(
            f"WARNING compute_human_cost: nessuna tariffa risolta per role='{miss['role']}' "
            f"({miss['reason']}). Tariffa 0 applicata (ore>0). "
            f"Verifica '{rel_rates}' (id/alias + valid_from). Vedi ADR-022 §D.",
            file=sys.stderr,
        )

    # §10 Privacy masking N>=5 (ADR-023 §C) — INVARIANTE NON NEGOZIABILE
    distinct = compute["distinct_actors"]
    suppress_actor = False
    privacy_note = ""

    if distinct < min_n:
        if args.audience in ("executive", "project"):
            suppress_actor = True
            privacy_note = (
                f"aggregated below threshold (ADR-023 §C): N={distinct} < "
                f"min_aggregation_n={min_n}, per_actor omesso; aggregazione per ruolo. "
                f"Audience={args.audience}."
            )
        else:  # operativa
            if op_show == "true":
                suppress_actor = False
                privacy_note = (
                    f"WARNING: per_actor mostrato con N={distinct} < "
                    f"min_aggregation_n={min_n} (operational_show_actor_id=true). "
                    "Verificare diritto di accesso del lettore. Vedi ADR-023 §C."
                )
            else:
                suppress_actor = True
                privacy_note = (
                    f"aggregated below threshold (ADR-023 §C): N={distinct} < "
                    f"min_aggregation_n={min_n}, per_actor omesso "
                    f"(operational_show_actor_id=false). Audience={args.audience}."
                )

    threshold_note = (
        f"Privacy threshold applicata: min_aggregation_n={min_n}, "
        f"distinct actor_id={distinct}, audience={args.audience}."
    )
    rate_basis_note = f"Rate basis: {file_rate_basis}. Vedi ADR-022 §C, ADR-023 §E."

    # §11 Assembla output finale — schema US-034 / ADR-023 §E
    cost = compute["total"]

    breakdown: dict = {"per_role": compute["per_role"]}
    if not suppress_actor:
        breakdown["per_actor"] = compute["per_actor"]

    output: dict = {}
    output["cost"] = cost
    output["currency"] = currency
    if cost > 0:
        output["rate_basis"] = file_rate_basis
    output["breakdown"] = breakdown
    output["events_considered"] = compute["events_considered"]
    output["rate_card_version"] = rate_card_version

    notes: list[str] = []
    if privacy_note:
        notes.append(privacy_note)
    notes.append(threshold_note)
    if cost > 0:
        notes.append(rate_basis_note)
    output["notes"] = notes

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
