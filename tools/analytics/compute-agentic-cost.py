#!/usr/bin/env python3
"""
compute-agentic-cost.py — tool deterministico compute_agentic_cost (EP-009, US-034, TSK-061)
Cross-platform replacement per compute-agentic-cost.sh (macOS / Linux / Windows).

READER agnostico dello store analytics/events/ scritto da record_task_event e di
analytics/pricing.yaml (single-writer umano, ADR-022). Filtra gli eventi
actor_type=agent, risolve il pricing per ogni evento e applica la formula del
costo agentico. L'output è JSON puro; l'interpretazione è scope della skill
(US-036) e dell'agente (US-038).

PATTERN.md §3 — operazione canonica opzionale «Cost Computation» (Agentic Cost).
ADR-022 — schema pricing_table (§B), resolution model_id (§D),
           valid_from semi-aperto (§E), determinismo retrospettivo (§F).
ADR-023 §A — contratto minimo tool analytics: --config opzionale,
              stdout=JSON / stderr=log, exit code semantico, stateless.

INVARIANTE — mai hardcodare prezzi: i prezzi provengono SEMPRE da
  analytics/pricing.yaml. Modello sconosciuto → fail-loud (ADR-022 §D).

INVARIANTE — determinismo retrospettivo (ADR-022 §F): il costo di un evento al
  timestamp e.ts è calcolato con il pricing valido a e.ts, MAI con il pricing
  corrente. Stesso input + stesso pricing snapshot → stesso output.

FORMULA (verbatim concept §2.1, applicata sui soli eventi actor_type=agent):
  costo = Σ_modello [ input·p_in + output·p_out + cache_read·p_cr
                     + (cache_write − cache_write_1h)·p_cw + cache_write_1h·p_cw1h ]
        + Σ_tool    [ qty · price_per_unit ]
  Prezzi token espressi per 1M token in pricing.yaml → divisione per 1e6.

CONTRATTO INPUT (CLI):
  --task-id <id>         filtro su task_id.
  --filter '<JSON>'      filtro aggiuntivo. Shape:
                         {project_id?, period?:{from,to}, actor_id?, task_type?}.
  --pricing <path>       path alla pricing table.
  --pricing-as-of YYYY-MM-DD  what-if (ADR-022 §F).
  --config <path>        default "factory.config.yaml".

  --task-id e --filter sono combinabili (AND).

CONTRATTO OUTPUT (stdout, JSON puro) — schema US-034 / TSK-061:
  {
    "cost": float, "currency": "EUR",
    "breakdown": {
      "per_model": {"<model_id>": float},
      "agentic_by_token_kind": {"input":f,"output":f,"cache_read":f,"cache_write":f},
      "per_tool": {"<tool_name>": float}
    },
    "events_considered": int,
    "pricing_table_version": str
  }

EXIT CODES:
  0  costo calcolato OR no-op (analytics.measurement.enabled assente/false)
  >0 errore (prerequisito mancante, pricing assente, model_id sconosciuto, ecc.)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
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
# Helper: lettura config YAML (regex, stdlib-only)
# ---------------------------------------------------------------------------

def _yaml_nested(config_path: str, section: str, key: str) -> str:
    """Estrae <key> dal blocco analytics.<section>. Ritorna "" se assente."""
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
# Helper: pricing_table_version — git hash o mtime date
# ---------------------------------------------------------------------------

def _pricing_version(pricing_path: Path) -> str:
    """Ritorna l'hash git del file pricing o la data di mtime come fallback."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "-1", "--format=%H", "--", str(pricing_path)],
            capture_output=True,
            text=True,
            timeout=120,  # git sotto carico: lo .sh non ha timeout, un fallback silenzioso cambierebbe l'output
        )
        ver = result.stdout.strip()
        if ver:
            return ver
    except Exception:
        pass
    try:
        mtime = pricing_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Helper: parser pricing.yaml — regex puro (no PyYAML)
# ---------------------------------------------------------------------------

def _parse_pricing_yaml(path: Path) -> dict:
    """
    Parsa analytics/pricing.yaml (schema ADR-022 §B) senza PyYAML.
    Ritorna dict strutturato:
      { "currency": str, "models": [...], "tools": [...] }
    Ogni model entry:
      { "id": str, "aliases": [str, ...], "pricing": [{valid_from, input_per_1m_tokens,
        output_per_1m_tokens, cache_read_per_1m_tokens, cache_write_per_1m_tokens}] }
    Ogni tool entry:
      { "name": str, "aliases": [str, ...], "pricing": [{valid_from, price_per_unit}] }
    Prezzi assenti → 0.0 (ADR-022 §B: cache_* omessi = 0).
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise FileNotFoundError(f"pricing file non leggibile: {path}") from exc

    result: dict = {"currency": "EUR", "models": [], "tools": []}
    section = None          # "models" | "tools" | None
    current_entry: dict | None = None
    current_price: dict | None = None
    in_aliases = False
    in_pricing_block = False

    def _flush_price() -> None:
        nonlocal current_price
        if current_price is not None and current_entry is not None:
            # defaults per campi omessi
            current_price.setdefault("input_per_1m_tokens", 0.0)
            current_price.setdefault("output_per_1m_tokens", 0.0)
            current_price.setdefault("cache_read_per_1m_tokens", 0.0)
            current_price.setdefault("cache_write_per_1m_tokens", 0.0)
            current_price.setdefault("price_per_unit", 0.0)
            current_entry["pricing"].append(current_price)
            current_price = None

    def _flush_entry() -> None:
        nonlocal current_entry, in_aliases, in_pricing_block, current_price
        _flush_price()
        if current_entry is not None:
            if section == "models":
                result["models"].append(current_entry)
            elif section == "tools":
                result["tools"].append(current_entry)
            current_entry = None
        in_aliases = False
        in_pricing_block = False

    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def _strip_comment(line: str) -> str:
        # rimuovi commenti inline (semplice, non gestisce stringhe quoted con #)
        pos = line.find(" #")
        if pos != -1:
            return line[:pos]
        if line.lstrip().startswith("#"):
            return ""
        return line

    def _unquote(s: str) -> str:
        s = s.strip()
        if (s.startswith('"') and s.endswith('"')) or \
           (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s

    def _to_float(s: str) -> float:
        try:
            return float(s.strip())
        except (ValueError, AttributeError):
            return 0.0

    for raw_line in raw.splitlines():
        line = _strip_comment(raw_line)
        if not line.strip():
            continue
        ind = _indent(line)
        stripped = line.strip()

        # top-level currency
        if ind == 0 and re.match(r"^currency\s*:", stripped):
            v = re.sub(r"^currency\s*:\s*", "", stripped)
            result["currency"] = _unquote(v)
            continue

        # section headers (top-level)
        if ind == 0 and re.match(r"^models\s*:", stripped):
            _flush_entry()
            section = "models"
            continue
        if ind == 0 and re.match(r"^tools\s*:", stripped):
            _flush_entry()
            section = "tools"
            continue

        if section is None:
            continue

        # new entry: "- id: ..." or "- name: ..."
        m_id = re.match(r"^-\s+id\s*:\s*(.+)$", stripped)
        m_name = re.match(r"^-\s+name\s*:\s*(.+)$", stripped)
        if m_id or m_name:
            _flush_entry()
            val = _unquote((m_id or m_name).group(1))  # type: ignore[union-attr]
            current_entry = {
                "id" if m_id else "name": val,
                "aliases": [],
                "pricing": [],
            }
            if m_name and section == "tools":
                current_entry["name"] = val
            in_aliases = True
            in_pricing_block = False
            continue

        if current_entry is None:
            continue

        # aliases block header
        if re.match(r"^aliases\s*:", stripped):
            in_aliases = True
            in_pricing_block = False
            continue

        # pricing/rates block header
        if re.match(r"^(pricing|rates)\s*:", stripped):
            in_aliases = False
            in_pricing_block = True
            continue

        # alias list item: "- <value>" (not a new entry marker)
        if in_aliases and re.match(r"^-\s+", stripped):
            if not re.match(r"^-\s+(id|name|valid_from)\s*:", stripped):
                val = re.sub(r"^-\s+", "", stripped)
                current_entry["aliases"].append(_unquote(val))
                continue

        # new price entry: "- valid_from: ..."
        if in_pricing_block and re.match(r"^-\s+valid_from\s*:", stripped):
            _flush_price()
            v = re.sub(r"^-\s+valid_from\s*:\s*", "", stripped)
            current_price = {"valid_from": _unquote(v)}
            continue

        # price sub-fields
        if current_price is not None:
            for field, key in [
                (r"^input_per_1m_tokens\s*:", "input_per_1m_tokens"),
                (r"^output_per_1m_tokens\s*:", "output_per_1m_tokens"),
                (r"^cache_read_per_1m_tokens\s*:", "cache_read_per_1m_tokens"),
                (r"^cache_write_per_1m_tokens\s*:", "cache_write_per_1m_tokens"),
                (r"^cache_write_1h_per_1m_tokens\s*:", "cache_write_1h_per_1m_tokens"),
                (r"^price_per_unit\s*:", "price_per_unit"),
            ]:
                if re.match(field, stripped):
                    v = re.sub(field, "", stripped)
                    current_price[key] = _to_float(v)
                    break

    _flush_entry()
    return result


# ---------------------------------------------------------------------------
# Helper: filtraggio eventi (condiviso tra JSONL e SQLite)
# ---------------------------------------------------------------------------

def _matches_filter(ev: dict, filt: dict, task_id: str) -> bool:
    """Filtra per actor_type=agent + task_id + filter dict."""
    if ev.get("actor_type") != "agent":
        return False
    if task_id and ev.get("task_id") != task_id:
        return False

    pid = filt.get("project_id")
    tt  = filt.get("task_type")
    aid = filt.get("actor_id")
    period = filt.get("period") or {}
    pfrom = period.get("from")
    pto   = period.get("to")

    if pid is not None and ev.get("project_id") != pid:
        return False
    if tt is not None and ev.get("task_type") != tt:
        return False
    if aid is not None and ev.get("actor_id") != aid:
        return False
    ts = ev.get("ts", "")
    if pfrom is not None and ts < pfrom:
        return False
    if pto is not None and ts >= pto:
        return False
    return True


def _safe_json(s: str | None, default):
    if not s:
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


# ---------------------------------------------------------------------------
# load_events: legge JSONL o SQLite, ritorna lista di eventi filtrati
# ---------------------------------------------------------------------------

def _load_jsonl(events_dir: Path, filt: dict, task_id: str) -> list[dict]:
    if not events_dir.is_dir():
        print(
            f"compute_agentic_cost: event store assente ({events_dir}). "
            "Nessun evento da valutare (R.P3).",
            file=sys.stderr,
        )
        return []
    files = sorted(events_dir.glob("*.jsonl"))
    if not files:
        print(
            f"compute_agentic_cost: nessun file evento in {events_dir} (R.P3).",
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


def _load_sqlite(db_path: Path, filt: dict, task_id: str) -> list[dict]:
    if not db_path.exists():
        print(
            f"compute_agentic_cost: event store SQLite assente ({db_path}). "
            "Nessun evento da valutare (R.P3).",
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
                "cache_write_1h": (row["tokens_cache_write_1h"]
                                   if "tokens_cache_write_1h" in row.keys() else 0),
            },
            "tool_calls": _safe_json(row["tool_calls"], []),
            "extras":     _safe_json(row["extras"], None),
        }
        if _matches_filter(ev, filt, task_id):
            events.append(ev)
    return events


def load_events(store: str, filt: dict, task_id: str) -> list[dict]:
    events_dir = REPO_ROOT / "analytics" / "events"
    db_path    = REPO_ROOT / "analytics" / "events.db"
    if store == "sqlite":
        return _load_sqlite(db_path, filt, task_id)
    return _load_jsonl(events_dir, filt, task_id)


# ---------------------------------------------------------------------------
# Validazione model_id (ADR-022 §D)
# ---------------------------------------------------------------------------

def _canon_model(raw: str, pricing: dict) -> dict | None:
    """Risolve raw model → dict entry da pricing. None se non trovato.

    Ordine: id o alias (dopo dots→dashes), alias grezzo; poi, solo se nulla combacia, lo
    stesso nome senza il suffisso finale fra parentesi quadre (`claude-opus-5[1m]` →
    `claude-opus-5`): una variante di contesto nuova non diventa «modello sconosciuto» perche'
    manca il suo alias (backport dalla derivata, EP-072). Un nome davvero ignoto resta None.
    """
    norm = raw.lower().replace(".", "-")
    for m in pricing.get("models", []):
        aliases = m.get("aliases", [])
        if m.get("id") == norm or norm in aliases or raw in aliases:
            return m
    stripped = re.sub(r"\[[^\]]*\]$", "", norm).rstrip("-")
    if stripped and stripped != norm:
        for m in pricing.get("models", []):
            if m.get("id") == stripped or stripped in m.get("aliases", []):
                return m
    return None


def _validate_models(events: list[dict], pricing: dict) -> int:
    """
    Verifica che ogni evento agent con token > 0 abbia un model risolvibile.
    Ritorna 0 se ok, 1 se errore (ha già stampato su stderr e stdout).
    """
    for ev in events:
        raw = ev.get("model") or ""
        tokens = ev.get("tokens") or {}
        tok_sum = (
            (tokens.get("input") or 0)
            + (tokens.get("output") or 0)
            + (tokens.get("cache_read") or 0)
            + (tokens.get("cache_write") or 0)
        )
        ev_task = ev.get("task_id") or "?"
        ev_ts   = ev.get("ts") or "?"

        if not raw or raw == "null":
            if tok_sum != 0:
                print(
                    f"ERRORE: evento {ev_task} ({ev_ts}) ha token agentici ma campo "
                    "'model' assente. Impossibile risolvere il pricing. Vedi ADR-022 §D.",
                    file=sys.stderr,
                )
                print(json.dumps({"status": "error", "error": f"missing model in event {ev_task}"}))
                return 1
            continue

        if tok_sum == 0:
            continue

        if _canon_model(raw, pricing) is None:
            print(
                f"ERRORE: Unknown model_id `{raw}` in event {ev_task}: "
                "add entry in analytics/pricing.yaml (vedi ADR-022).",
                file=sys.stderr,
            )
            print(json.dumps({"status": "error", "error": f"unknown model_id {raw} in event {ev_task}"}))
            return 1
    return 0


# ---------------------------------------------------------------------------
# Calcolo costo — formula §2.1 verbatim
# ---------------------------------------------------------------------------

def _pick_pricing(entries: list[dict], date_str: str) -> dict | None:
    """
    Seleziona la pricing entry valida alla data date_str (YYYY-MM-DD).
    entry valida = valid_from <= date_str; sceglie la massima valid_from.
    """
    candidates = [e for e in entries if e.get("valid_from", "") <= date_str]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e.get("valid_from", ""))


def _res_date(ts: str, pricing_as_of: str) -> str:
    """Data di resolution: pricing_as_of se fornito, altrimenti ts[:10]."""
    if pricing_as_of:
        return pricing_as_of
    return ts[:10] if ts else ""


def _round6(x: float) -> float:
    return _jq_round(x * 1_000_000) / 1_000_000


def compute_cost(events: list[dict], pricing: dict, pricing_as_of: str) -> dict:
    """
    Applica la formula §2.1 a tutti gli eventi. Ritorna il dict risultato
    (schema US-034 / TSK-061) senza pricing_table_version (aggiunto dal chiamante).
    Fail-loud se nessuna pricing entry copre la data dell'evento.
    """
    currency = pricing.get("currency", "EUR")
    total_cost = 0.0
    per_model: dict[str, float] = {}
    by_kind: dict[str, float] = {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}
    per_tool: dict[str, float] = {}
    tool_calls_forma_storica = [0]

    tools_index: dict[str, dict] = {t["name"]: t for t in pricing.get("tools", []) if "name" in t}

    for ev in events:
        raw = ev.get("model") or ""
        ts  = ev.get("ts") or ""
        ev_task = ev.get("task_id") or "?"
        d = _res_date(ts, pricing_as_of)
        tokens = ev.get("tokens") or {}

        # costo token modello
        if raw and raw != "null":
            m_entry = _canon_model(raw, pricing)
            if m_entry is not None:
                mid = m_entry["id"]
                pr = _pick_pricing(m_entry.get("pricing", []), d)
                if pr is None:
                    print(
                        f"ERRORE: No valid pricing for model '{mid}' at {d} in event {ev_task} "
                        "(vedi ADR-022 §D).",
                        file=sys.stderr,
                    )
                    print(json.dumps({
                        "status": "error",
                        "error": f"no valid pricing for model {mid} at {d} in event {ev_task}",
                    }))
                    sys.exit(1)

                t_in  = (tokens.get("input")       or 0) / 1_000_000 * (pr.get("input_per_1m_tokens")       or 0.0)
                t_out = (tokens.get("output")       or 0) / 1_000_000 * (pr.get("output_per_1m_tokens")      or 0.0)
                t_cr  = (tokens.get("cache_read")   or 0) / 1_000_000 * (pr.get("cache_read_per_1m_tokens")  or 0.0)
                # cache_write e' il totale; cache_write_1h la parte a TTL 1h (assente negli
                # eventi storici = tutto a 5m). Senza prezzo 1h nel listino vale quello a 5m.
                p_cw   = pr.get("cache_write_per_1m_tokens") or 0.0
                p_cw1h = pr.get("cache_write_1h_per_1m_tokens") or p_cw
                cw_all = tokens.get("cache_write") or 0
                cw_1h  = min(tokens.get("cache_write_1h") or 0, cw_all)
                t_cw  = ((cw_all - cw_1h) * p_cw + cw_1h * p_cw1h) / 1_000_000
                c_model = t_in + t_out + t_cr + t_cw

                total_cost += c_model
                per_model[mid] = per_model.get(mid, 0.0) + c_model
                by_kind["input"]       += t_in
                by_kind["output"]      += t_out
                by_kind["cache_read"]  += t_cr
                by_kind["cache_write"] += t_cw

        # costo tool calls
        for tc in ev.get("tool_calls") or []:
            if isinstance(tc, str):
                # forma storica: lista di nomi senza quantita' (fuori schema `{name, qty}`).
                # Senza qty il costo e' 0, ma il tool resta visibile in per_tool; la forma si
                # conta e si dichiara su stderr, non si scarta in silenzio.
                tool_calls_forma_storica[0] += 1
                tc = {"name": tc}
            elif not isinstance(tc, dict):
                tool_calls_forma_storica[0] += 1
                continue
            tname = tc.get("name") or ""
            if not tname:
                continue
            # parita' con lo .sh: un tool senza voce di prezzo conta 0 ma compare in per_tool
            tdef = tools_index.get(tname)
            if tdef is None:
                c_tool = 0
            else:
                td = _res_date(ts, pricing_as_of)
                tpr = _pick_pricing(tdef.get("pricing", []), td) or {}
                qty = tc.get("qty") or 0
                c_tool = qty * (tpr.get("price_per_unit") or 0)
            total_cost += c_tool
            per_tool[tname] = per_tool.get(tname, 0.0) + c_tool

    if tool_calls_forma_storica[0]:
        print(f"compute_agentic_cost: {tool_calls_forma_storica[0]} tool_calls in forma storica "
              "(nome senza qty, fuori schema {name, qty}): costo 0, tool elencato in per_tool.",
              file=sys.stderr)
    return {
        "cost": _round6(total_cost),
        "currency": currency,
        "breakdown": {
            "per_model": {k: _round6(v) for k, v in per_model.items()},
            "agentic_by_token_kind": {k: _round6(v) for k, v in by_kind.items()},
            "per_tool": {k: _round6(v) for k, v in per_tool.items()},
        },
        "events_considered": len(events),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = ContractArgumentParser(
        description="compute_agentic_cost — EP-009 US-034 ADR-022.",
        add_help=True,
    )
    parser.add_argument("--task-id",        default="",              dest="task_id",
                        help="Filtra sul singolo task_id.")
    parser.add_argument("--filter",         default="{}",
                        help="Filtro JSON aggiuntivo (default {}).")
    parser.add_argument("--pricing",        default="",
                        help="Path alla pricing table.")
    parser.add_argument("--pricing-as-of",  default="",              dest="pricing_as_of",
                        help="What-if: forza resolution a questa data (YYYY-MM-DD).")
    parser.add_argument("--config",         default="factory.config.yaml",
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

    # Valida --pricing-as-of se presente
    if args.pricing_as_of and not re.match(r"^\d{4}-\d{2}-\d{2}$", args.pricing_as_of):
        print(
            f"ERRORE: --pricing-as-of deve essere YYYY-MM-DD (trovato: '{args.pricing_as_of}').",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"invalid --pricing-as-of: {args.pricing_as_of}"}))
        return 1

    # §4 — Master switch
    enabled = _yaml_nested(config_path, "measurement", "enabled")
    if enabled != "true":
        print(
            "compute_agentic_cost: analytics.measurement.enabled non è true (no-op, R.P3).",
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

    # §5 — Risoluzione path pricing.yaml
    pricing_path_str = args.pricing
    if not pricing_path_str:
        pricing_path_str = _yaml_nested(config_path, "measurement", "pricing_table_path")
    if not pricing_path_str:
        pricing_path_str = "analytics/pricing.yaml"

    pricing_path = (
        Path(pricing_path_str)
        if Path(pricing_path_str).is_absolute()
        else (REPO_ROOT / pricing_path_str).resolve()
    )

    if not pricing_path.exists():
        rel = pricing_path_str
        print(
            f"ERRORE: pricing table mancante ({rel}). La capability è attiva ma il file "
            "di pricing non esiste. Crealo copiando analytics/pricing.yaml.template. "
            "Vedi ADR-022 §B/§G.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"missing pricing table: {rel}"}))
        return 1

    # §6 — pricing_table_version
    ptv = _pricing_version(pricing_path)

    # §7 — Parse pricing.yaml
    try:
        pricing = _parse_pricing_yaml(pricing_path)
    except Exception as exc:
        print(
            f"ERRORE: parsing di pricing.yaml fallito o schema non riconosciuto "
            f"({pricing_path}). Verifica lo schema ADR-022 §B. Dettaglio: {exc}",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": "pricing parse failed"}))
        return 1

    # §8 — Caricamento eventi
    events = load_events(store, filt, args.task_id)

    # §9 — Validazione model_id (fail-loud)
    if events:
        rc = _validate_models(events, pricing)
        if rc != 0:
            return rc

    # §10 — Calcolo costo
    result = compute_cost(events, pricing, args.pricing_as_of)
    result["pricing_table_version"] = ptv

    # §11 — Output
    print(
        f"compute_agentic_cost: {result['events_considered']} eventi agent valutati "
        f"con pricing {pricing_path} (version {ptv}).",
        file=sys.stderr,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
