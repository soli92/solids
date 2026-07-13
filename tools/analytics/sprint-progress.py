#!/usr/bin/env python3
"""
sprint-progress.py — segnale burndown del sprint corrente.
Basato su event store EP-009 con fallback automatico a conteggio kanban.

USO:
  python3 tools/analytics/sprint-progress.py [sprint_id] [--json]

ARGOMENTI:
  sprint_id  (opzionale, int) — sprint da analizzare.
             Default: legge sprint_current: da management/kanban/sprint.md.
  --json     Output machine-readable JSON invece del formato rich text.

DIPENDENZE: solo stdlib Python (json, pathlib, datetime, statistics, re, sys, argparse).
PyYAML usato se disponibile per il parsing di factory.config.yaml, con fallback regex.
"""
import sys
import json
import pathlib
import datetime
import statistics
import re
import argparse
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

SEP = "━" * 43  # ━━━━...


# ---------------------------------------------------------------------------
# Project root discovery
# ---------------------------------------------------------------------------

def find_project_dir() -> pathlib.Path:
    """
    Risale dalla posizione dello script al root del progetto.
    tools/analytics/sprint-progress.py  →  root = ../../
    Se lo script viene eseguito da un path diverso, usa cwd come fallback.
    """
    try:
        here = pathlib.Path(__file__).resolve()
        candidate = here.parent.parent.parent
        if (candidate / "factory.config.yaml").exists():
            return candidate
    except Exception:
        pass
    return pathlib.Path.cwd()


# ---------------------------------------------------------------------------
# Lettura sprint_current
# ---------------------------------------------------------------------------

def read_sprint_current(project_dir: pathlib.Path) -> Optional[int]:
    """
    Legge sprint_current: da management/kanban/sprint.md via regex.
    Ritorna None se il file non esiste o il campo non è presente.
    """
    sprint_md = project_dir / "management" / "kanban" / "sprint.md"
    try:
        text = sprint_md.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"sprint_current:\s*(\d+)", text)
        if m:
            return int(m.group(1))
    except (OSError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# Lettura factory.config.yaml
# ---------------------------------------------------------------------------

def load_config(project_dir: pathlib.Path) -> Dict[str, Any]:
    """
    Legge factory.config.yaml per:
      - analytics.sprint_progress.velocity_rolling_days  (default 7)
      - temporal.estimate_protocol.enabled               (default False)
    Graceful fallback se PyYAML non installato o file non trovato / parse error.
    """
    cfg: Dict[str, Any] = {
        "velocity_rolling_days": 7,
        "estimate_protocol_enabled": False,
    }
    config_path = project_dir / "factory.config.yaml"
    if not config_path.exists():
        return cfg

    text = ""
    try:
        text = config_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return cfg

    # Tentativo con PyYAML
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            analytics = data.get("analytics") or {}
            sp = analytics.get("sprint_progress") or {}
            if "velocity_rolling_days" in sp:
                cfg["velocity_rolling_days"] = int(sp["velocity_rolling_days"])
            temporal = data.get("temporal") or {}
            ep = temporal.get("estimate_protocol") or {}
            if "enabled" in ep:
                cfg["estimate_protocol_enabled"] = bool(ep["enabled"])
        return cfg
    except (ImportError, Exception):
        pass

    # Fallback regex (best-effort)
    m_vrd = re.search(r"velocity_rolling_days\s*:\s*(\d+)", text)
    if m_vrd:
        try:
            cfg["velocity_rolling_days"] = int(m_vrd.group(1))
        except ValueError:
            pass
    # estimate_protocol.enabled in blocco annidato
    m_ep = re.search(
        r"estimate_protocol\s*:\s*\n(?:\s+\w[^:]+:\s*[^\n]+\n)*\s+enabled\s*:\s*(true|false)",
        text,
    )
    if m_ep:
        cfg["estimate_protocol_enabled"] = m_ep.group(1).lower() == "true"
    return cfg


# ---------------------------------------------------------------------------
# Parsing frontmatter YAML (stdlib only)
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)^---\s*\n", re.DOTALL | re.MULTILINE)


def parse_frontmatter(text: str) -> Dict[str, str]:
    """
    Estrae coppie key: value semplici dal blocco frontmatter YAML.
    Non gestisce strutture annidate o liste multi-riga: solo scalari flat.
    """
    m = _FRONTMATTER_RE.search(text)
    if not m:
        return {}
    result: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^([\w][\w_-]*):\s*(.*)$", line.strip())
        if kv:
            val = kv.group(2).strip()
            # Rimuovi virgolette semplici o doppie
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            result[kv.group(1)] = val
    return result


# ---------------------------------------------------------------------------
# Kanban scanning
# ---------------------------------------------------------------------------

def load_kanban_tasks(
    project_dir: pathlib.Path,
    sprint_id: int,
) -> List[Dict[str, str]]:
    """
    Scansiona management/kanban/EP-*/US-*/TSK-*.md.
    Ritorna la lista di task con sprint == sprint_id con campi:
      id, status, estimate, layer.
    Graceful: salta file non leggibili o senza sprint matching.
    """
    kanban_root = project_dir / "management" / "kanban"
    if not kanban_root.exists():
        return []

    tasks: List[Dict[str, str]] = []
    for tsk_path in sorted(kanban_root.glob("EP-*/US-*/TSK-*.md")):
        try:
            text = tsk_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = parse_frontmatter(text)
        try:
            tsk_sprint = int(fm.get("sprint", "-1"))
        except ValueError:
            continue
        if tsk_sprint != sprint_id:
            continue
        tasks.append({
            "id": fm.get("id", tsk_path.stem),
            "status": fm.get("status", "todo").lower(),
            "estimate": fm.get("estimate", "").upper(),
            "layer": fm.get("layer", ""),
        })
    return tasks


# ---------------------------------------------------------------------------
# Event store
# ---------------------------------------------------------------------------

def load_events(
    project_dir: pathlib.Path,
    sprint_id: int,
) -> Tuple[Dict[str, str], Optional[datetime.datetime]]:
    """
    Scansiona analytics/events/*.jsonl, filtra per campo sprint == sprint_id.
    Raggruppa per task_id → stato:
      'done'        se presente evento con state='finished'
      'in-progress' se presente evento state='started' senza 'finished'
    Ritorna (task_states: Dict[task_id, stato], first_event_ts: Optional[datetime]).

    Se la directory non esiste o nessun evento ha il campo sprint, ritorna ({}, None).
    """
    events_dir = project_dir / "analytics" / "events"
    if not events_dir.exists():
        return {}, None

    # {task_id: {"started": Optional[datetime], "finished": Optional[datetime]}}
    task_events: Dict[str, Dict[str, Optional[datetime.datetime]]] = {}
    first_ts: Optional[datetime.datetime] = None

    for jsonl_file in sorted(events_dir.glob("*.jsonl")):
        try:
            text = jsonl_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Filtra solo eventi con sprint field
            rec_sprint = rec.get("sprint")
            if rec_sprint is None:
                continue
            try:
                if int(rec_sprint) != sprint_id:
                    continue
            except (ValueError, TypeError):
                continue

            task_id: str = rec.get("task_id", "")
            state: str = rec.get("state", "")
            ts_str: str = rec.get("ts", "")

            ts: Optional[datetime.datetime] = None
            try:
                ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

            if task_id not in task_events:
                task_events[task_id] = {"started": None, "finished": None}

            if state == "started" and ts is not None:
                prev = task_events[task_id]["started"]
                if prev is None or ts < prev:
                    task_events[task_id]["started"] = ts
            elif state == "finished" and ts is not None:
                prev = task_events[task_id]["finished"]
                if prev is None or ts > prev:
                    task_events[task_id]["finished"] = ts

            if ts is not None and (first_ts is None or ts < first_ts):
                first_ts = ts

    if not task_events:
        return {}, None

    task_states: Dict[str, str] = {}
    for tid, ev in task_events.items():
        if ev["finished"] is not None:
            task_states[tid] = "done"
        elif ev["started"] is not None:
            task_states[tid] = "in-progress"

    return task_states, first_ts


# ---------------------------------------------------------------------------
# Velocity & projection (event store mode)
# ---------------------------------------------------------------------------

def compute_velocity_and_uncertainty(
    events_dir: pathlib.Path,
    sprint_id: int,
    done_task_ids: List[str],
    done_count: int,
    first_event_ts: datetime.datetime,
    rolling_days: int,
) -> Tuple[float, Optional[float]]:
    """
    Calcola:
      velocity = done_count / days_elapsed
      uncertainty = stdev delle done giornaliere negli ultimi rolling_days (se >= 2 giorni)

    Ritorna (velocity, uncertainty). velocity garantito > 0 (clamped a 0.5 giorni min).
    """
    today = datetime.datetime.now(tz=datetime.timezone.utc)
    days_elapsed = max(
        (today - first_event_ts).total_seconds() / 86400,
        0.5,  # minimo mezzo giorno per evitare divisione per zero
    )
    velocity = done_count / days_elapsed

    # Rolling variance: raccogli timestamps finished degli ultimi rolling_days
    cutoff = today - datetime.timedelta(days=rolling_days)
    daily_done: Dict[str, int] = {}

    for jsonl_file in sorted(events_dir.glob("*.jsonl")):
        try:
            text = jsonl_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                if int(rec.get("sprint", -1)) != sprint_id:
                    continue
            except (ValueError, TypeError):
                continue
            if rec.get("state") != "finished":
                continue
            if rec.get("task_id") not in done_task_ids:
                continue
            ts_str = rec.get("ts", "")
            try:
                ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if ts < cutoff:
                continue
            day_key = ts.strftime("%Y-%m-%d")
            daily_done[day_key] = daily_done.get(day_key, 0) + 1

    uncertainty: Optional[float] = None
    if len(daily_done) >= 2:
        try:
            uncertainty = statistics.stdev(daily_done.values())
        except statistics.StatisticsError:
            pass

    return velocity, uncertainty


def compute_projection(
    todo_count: int,
    velocity: float,
    uncertainty: Optional[float],
) -> Tuple[float, Optional[float]]:
    """
    Ritorna (projection_days, projection_uncertainty_days).
    Propaga l'incertezza con formula lineare: ± (todo / v_lo - todo / v_hi) / 2.
    """
    projection = todo_count / velocity
    proj_uncertainty: Optional[float] = None
    if uncertainty is not None and uncertainty > 0:
        v_lo = max(velocity - uncertainty, 0.01)
        v_hi = velocity + uncertainty
        proj_uncertainty = abs(todo_count / v_lo - todo_count / v_hi) / 2.0
    return projection, proj_uncertainty


# ---------------------------------------------------------------------------
# XL outliers
# ---------------------------------------------------------------------------

def check_xl_outliers(
    project_dir: pathlib.Path,
    sprint_id: int,
    estimate_protocol_enabled: bool,
) -> List[Dict[str, Any]]:
    """
    Trova TSK XL in-progress per lo sprint.
    Se estimate_protocol_enabled=False, ritorna lista vuota (sezione omessa).
    Se True, tenta di arricchire con elapsed_h dall'event store.
    """
    if not estimate_protocol_enabled:
        return []

    kanban_root = project_dir / "management" / "kanban"
    if not kanban_root.exists():
        return []

    events_dir = project_dir / "analytics" / "events"
    outliers: List[Dict[str, Any]] = []

    for tsk_path in sorted(kanban_root.glob("EP-*/US-*/TSK-*.md")):
        try:
            text = tsk_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = parse_frontmatter(text)
        try:
            tsk_sprint = int(fm.get("sprint", "-1"))
        except ValueError:
            continue
        if tsk_sprint != sprint_id:
            continue
        estimate = fm.get("estimate", "").upper()
        status = fm.get("status", "").lower()
        if estimate != "XL" or status != "in-progress":
            continue

        task_id = fm.get("id", tsk_path.stem)

        # Cerca timestamp 'started' nell'event store per calcolare elapsed
        elapsed_h: Optional[float] = None
        if events_dir.exists():
            for jsonl_file in sorted(events_dir.glob("*.jsonl")):
                try:
                    ev_text = jsonl_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for raw_line in ev_text.splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("task_id") != task_id:
                        continue
                    if rec.get("state") != "started":
                        continue
                    ts_str = rec.get("ts", "")
                    try:
                        started = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
                        elapsed_h = (now_utc - started).total_seconds() / 3600
                    except (ValueError, AttributeError):
                        pass

        # Baseline stima temporale XL: ~8h di effort
        xl_hours_baseline = 8.0
        time_ratio: Optional[float] = None
        confidence: float = 0.3

        if elapsed_h is not None:
            time_ratio = elapsed_h / xl_hours_baseline
            confidence = 0.6

        if time_ratio is not None and time_ratio > 1.5:
            recommendation = "Considera split o escalation — elapsed superiore alla stima XL"
        elif time_ratio is not None and time_ratio > 1.0:
            recommendation = "Monitora — elapsed vicino alla stima XL"
        else:
            recommendation = "In attesa di dati elapsed — monitora con state machine"

        outliers.append({
            "task_id": task_id,
            "elapsed_h": round(elapsed_h, 2) if elapsed_h is not None else None,
            "estimate": "XL",
            "recommendation": recommendation,
            "time_ratio": round(time_ratio, 2) if time_ratio is not None else None,
            "confidence": confidence,
        })

    return outliers


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _make_bar(done: int, total: int, width: int = 20) -> str:
    """Barra ASCII proporzionale done/total."""
    if total == 0:
        return "─" * width  # ────
    filled = round(done / total * width)
    return "█" * filled + "░" * (width - filled)  # █ / ░


def format_rich(data: Dict[str, Any]) -> str:
    """Formatta l'output rich text della CLI."""
    lines: List[str] = []
    ts = data["generated_at"]
    sprint = data["sprint"]
    lines.append(f"Sprint SP-{sprint} — Progress Signal ({ts})")
    lines.append(SEP)

    done = data["done"]
    in_prog = data["in_progress"]
    todo = data["todo"]
    total = data["total"]
    pct = data["completion_pct"]
    bar = _make_bar(done, total)

    lines.append(f"Done       : {done:>3} TSK  [{bar}]  {pct:.0f}%")
    lines.append(f"In-progress: {in_prog:>3} TSK")
    lines.append(f"Todo       : {todo:>3} TSK")
    lines.append(SEP)

    vel = data.get("velocity_per_day")
    rolling_days = data.get("_rolling_days", 7)

    if vel is not None:
        lines.append(f"Velocita'  : {vel:.2f} TSK/giorno (rolling {rolling_days}gg)")
    else:
        lines.append("Velocita'  : n/d — fallback kanban")  # n/d — fallback kanban

    proj = data.get("projection_days")
    proj_unc = data.get("projection_uncertainty_days")
    if proj is not None:
        unc_str = f" (± {proj_unc:.1f} giorni)" if proj_unc is not None else ""
        lines.append(f"Proiezione : ~{proj:.1f} giorni al completamento sprint{unc_str}")
    else:
        lines.append("Proiezione : n/d")
    lines.append(SEP)

    # Banner fallback kanban
    if data["source"] == "kanban_fallback":
        lines.append(
            "[Nota: velocita' non calcolabile — event store non disponibile. "
            "Uso conteggio kanban.]"
        )
        lines.append(SEP)

    # Sezione XL outliers (solo se estimate_protocol_enabled e outlier presenti)
    xl_outliers = data.get("xl_outliers") or []
    if xl_outliers:
        lines.append("TSK XL outlier (stima temporale):")
        for ol in xl_outliers:
            elapsed_str = (
                f"{ol['elapsed_h']}h" if ol.get("elapsed_h") is not None else "n/d"
            )
            tr = ol.get("time_ratio")
            conf = ol.get("confidence")
            tr_str = f"{tr:.2f}" if tr is not None else "n/d"
            conf_str = f"{conf:.2f}" if conf is not None else "n/d"
            lines.append(
                f"  {ol['task_id']} [in-progress, elapsed: {elapsed_str}, estimate: XL]"
            )
            lines.append(
                f"  → {ol['recommendation']} "
                f"(time_ratio: {tr_str}, confidence: {conf_str})"
            )
        lines.append(SEP)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Segnale burndown sprint corrente. "
            "Usa event store EP-009 con fallback automatico a conteggio kanban."
        ),
    )
    ap.add_argument(
        "sprint_id",
        nargs="?",
        type=int,
        default=None,
        help="Sprint ID (int). Default: legge sprint_current: da sprint.md",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON (tutti i campi del segnale burndown)",
    )
    args = ap.parse_args()

    project_dir = find_project_dir()

    # Risolvi sprint_id
    sprint_id: Optional[int] = args.sprint_id
    if sprint_id is None:
        sprint_id = read_sprint_current(project_dir)
    if sprint_id is None:
        print(
            "ERRORE: sprint_id non specificato e sprint_current non trovato "
            "in management/kanban/sprint.md",
            file=sys.stderr,
        )
        return 1

    # Carica configurazione (graceful fallback se file/PyYAML assenti)
    cfg = load_config(project_dir)
    rolling_days: int = cfg["velocity_rolling_days"]
    estimate_protocol_enabled: bool = cfg["estimate_protocol_enabled"]

    # --- Tenta event store ---
    task_states, first_event_ts = load_events(project_dir, sprint_id)

    # Carica sempre lista kanban per il totale TSK del sprint
    kanban_tasks = load_kanban_tasks(project_dir, sprint_id)

    source: str
    done_count: int
    in_progress_count: int
    todo_count: int
    velocity: Optional[float] = None
    proj_days: Optional[float] = None
    proj_unc: Optional[float] = None

    if task_states and first_event_ts is not None:
        # --- Modo event store ---
        source = "event_store"
        done_ids = [tid for tid, st in task_states.items() if st == "done"]
        in_progress_ids = [tid for tid, st in task_states.items() if st == "in-progress"]

        if kanban_tasks:
            # Combina: i task kanban sono la source-of-truth dell'elenco completo
            done_count = sum(
                1 for t in kanban_tasks
                if t["id"] in done_ids or t["status"] == "done"
            )
            in_progress_count = sum(
                1 for t in kanban_tasks
                if t["id"] in in_progress_ids and t["id"] not in done_ids
                and t["status"] != "done"
            )
        else:
            done_count = len(done_ids)
            in_progress_count = len(in_progress_ids)

        total = max(len(kanban_tasks), done_count + in_progress_count)
        todo_count = max(0, total - done_count - in_progress_count)

        # Velocity (solo se ci sono task done)
        if done_count > 0:
            events_dir = project_dir / "analytics" / "events"
            velocity, uncertainty = compute_velocity_and_uncertainty(
                events_dir=events_dir,
                sprint_id=sprint_id,
                done_task_ids=done_ids,
                done_count=done_count,
                first_event_ts=first_event_ts,
                rolling_days=rolling_days,
            )
            if velocity is not None and velocity > 0 and todo_count > 0:
                proj_days, proj_unc = compute_projection(todo_count, velocity, uncertainty)

    else:
        # --- Fallback kanban ---
        source = "kanban_fallback"
        done_count = 0
        in_progress_count = 0
        todo_count = 0
        for t in kanban_tasks:
            st = t["status"]
            if st == "done":
                done_count += 1
            elif st == "in-progress":
                in_progress_count += 1
            else:
                todo_count += 1

    total = done_count + in_progress_count + todo_count
    completion_pct: float = (done_count / total * 100.0) if total > 0 else 0.0

    # XL outliers (solo se estimate_protocol_enabled)
    xl_outliers = check_xl_outliers(project_dir, sprint_id, estimate_protocol_enabled)

    now_iso = (
        datetime.datetime.now(tz=datetime.timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    data: Dict[str, Any] = {
        "sprint": sprint_id,
        "generated_at": now_iso,
        "source": source,
        "done": done_count,
        "in_progress": in_progress_count,
        "todo": todo_count,
        "total": total,
        "completion_pct": round(completion_pct, 2),
        "velocity_per_day": round(velocity, 4) if velocity is not None else None,
        "projection_days": round(proj_days, 2) if proj_days is not None else None,
        "projection_uncertainty_days": (
            round(proj_unc, 2) if proj_unc is not None else None
        ),
        "xl_outliers": xl_outliers,
        # Campo interno, non incluso nel --json output
        "_rolling_days": rolling_days,
    }

    if args.json:
        out = {k: v for k, v in data.items() if not k.startswith("_")}
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(format_rich(data))

    return 0


if __name__ == "__main__":
    sys.exit(main())
