#!/usr/bin/env python3
"""
show-session-tokens.py — display real-time token usage from the current session.
Called by the Stop hook to show cumulative costs after each Claude response.
Complements harvest-session-tokens.py (which logs to SessionEnd in the JSONL store).

Reads the Claude Code JSONL transcript from the current CWD (plus its subagents/) and
aggregates the tokens (input + output + cache), one API response per message.id.

USE:
  # from hook Stop (stdin = JSON payload):
  echo '<hook-json>' | show-session-tokens.py --from-hook [--full]
  # from CLI (manual debug/query):
  show-session-tokens.py [--full] [--transcript <path>]


"""
import sys
import json
import pathlib
import os
import re
import argparse
from typing import Optional, Set, Dict, Tuple


# ---------------------------------------------------------------------------
# Transcript discovery
# ---------------------------------------------------------------------------

def find_transcript(cwd: Optional[str] = None) -> Optional[str]:
    """Find the most recent JSONL transcript for the current cwd."""
    base = cwd or os.getcwd()
    # Claude Code mangling: replaces both '/' and '.' with '-' in the path
    mangled = base.replace("/", "-").replace(".", "-")
    pdir = os.path.expanduser(f"~/.claude/projects/{mangled}")
    try:
        cand = sorted(
            pathlib.Path(pdir).glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return str(cand[0]) if cand else None
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Parsing transcript
# ---------------------------------------------------------------------------

def _harvest():
    """harvest-session-tokens.py (stessa cartella): regola di conteggio per message.id e
    fan-in dei subagents/, condivisa con l'event store e con cost_alert.py."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "harvest_session_tokens", pathlib.Path(__file__).resolve().parent / "harvest-session-tokens.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def parse_session(path: str):
    """
    Aggregate token usage of the session: main transcript + subagents/agent-*.jsonl,
    one API response per message.id (a response spans one line per content block).
    Returns (totals_dict, models_seen_set, per_model): per_model holds the 5 token kinds
    per model, used to price each model with its own rates.
    """
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cache_write_1h": 0}
    per_model: Dict = {}
    models_seen: Set[str] = set()
    try:
        harvest = _harvest()
        for fpath, force_scope in harvest.collect_jsonl_files(path):
            try:
                responses = harvest.parse_responses(str(fpath), force_scope)
            except (OSError, UnicodeDecodeError):
                continue
            for model, _scope, vals, _ts in responses:
                models_seen.add(model)
                pm = per_model.setdefault(model, [0, 0, 0, 0, 0])
                for i, key in enumerate(("input", "output", "cache_read", "cache_write",
                                         "cache_write_1h")):
                    totals[key] += vals[i]
                    pm[i] += vals[i]
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return totals, models_seen, per_model


def parse_tokens(path: str) -> Tuple[Dict, Set]:
    """(totals, models_seen) of the session: see parse_session."""
    totals, models_seen, _ = parse_session(path)
    return totals, models_seen


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

_FALLBACK_PRICING = {
    # Sonnet 4.6 as a reasonable fallback (USD/1M)
    "in":  3.0,
    "out": 15.0,
    "cr":  0.3,    # cache read
    "cw":  3.75,   # cache write, TTL 5m
    "cw1h": 6.0,   # cache write, TTL 1h
}

_MODEL_FALLBACKS: Dict[str, Dict] = {
    "claude-opus":   {"in": 5.0,  "out": 25.0, "cr": 0.5,  "cw": 6.25, "cw1h": 10.0},
    "claude-sonnet": {"in": 3.0,  "out": 15.0, "cr": 0.3,  "cw": 3.75, "cw1h": 6.0},
    "claude-haiku":  {"in": 1.0,  "out": 5.0,  "cr": 0.1,  "cw": 1.25, "cw1h": 2.0},
    "claude-fable":  {"in": 10.0, "out": 50.0, "cr": 1.0,  "cw": 12.5, "cw1h": 20.0},
    "claude-mythos": {"in": 10.0, "out": 50.0, "cr": 1.0,  "cw": 12.5, "cw1h": 20.0},
}


def normalize_model(raw: str) -> str:
    """claude-sonnet-4-6[1m] → claude-sonnet-4-6"""
    return re.sub(r"\[.*?\]$", "", raw.strip().lower())


def load_pricing(project_dir: str) -> Dict[str, Dict]:
    """Read analytics/pricing.yaml → dict {model_id_or_alias: pricing_entry}."""
    result: Dict[str, Dict] = {}
    pricing_path = pathlib.Path(project_dir) / "analytics" / "pricing.yaml"
    if not pricing_path.exists():
        return result
    try:
        import yaml  # type: ignore
        with open(pricing_path) as f:
            data = yaml.safe_load(f)
        for m in data.get("models", []):
            mid = m.get("id", "")
            p_list = m.get("pricing", [])
            if not p_list:
                continue
            p = p_list[-1]
            entry = {
                "in":  float(p.get("input_per_1m_tokens", 0) or 0),
                "out": float(p.get("output_per_1m_tokens", 0) or 0),
                "cr":  float(p.get("cache_read_per_1m_tokens", 0) or 0),
                "cw":  float(p.get("cache_write_per_1m_tokens", 0) or 0),
                # TTL 1h: senza il campo nel listino vale il prezzo della scrittura a 5m
                "cw1h": float(p.get("cache_write_1h_per_1m_tokens")
                              or p.get("cache_write_per_1m_tokens", 0) or 0),
            }
            result[mid] = entry
            for alias in m.get("aliases", []):
                result[normalize_model(alias)] = entry
    except (ImportError, Exception):
        pass
    return result


def get_pricing(models_seen: Set[str], pricing: Dict) -> Dict:
    """Resolve pricing for the session model(s)."""
    for raw in models_seen:
        norm = normalize_model(raw)
        if norm in pricing:
            return pricing[norm]
        # fallback prefix-based
        for prefix, p in _MODEL_FALLBACKS.items():
            if norm.startswith(prefix):
                return p
    return _FALLBACK_PRICING


def tokens_cost(p, i: int, o: int, cr: int, cw: int, cw1h: int = 0) -> float:
    """Costo in USD. cw e' il totale scritto in cache, cw1h la parte a TTL 1h: il resto
    (cw - cw1h) si paga al prezzo della scrittura a 5m."""
    return (i * p["in"] + o * p["out"] + cr * p["cr"]
            + (cw - cw1h) * p["cw"] + cw1h * p.get("cw1h", p["cw"])) / 1_000_000


def calc_cost(totals: Dict, models_seen: Set, pricing: Dict, per_model=None) -> float:
    if per_model:
        return sum(tokens_cost(get_pricing({model}, pricing), *vals)
                   for model, vals in per_model.items())
    p = get_pricing(models_seen, pricing)
    return tokens_cost(p, totals["input"], totals["output"], totals["cache_read"],
                       totals["cache_write"], totals.get("cache_write_1h", 0))


def cache_savings(totals: Dict, models_seen: Set, pricing: Dict, per_model=None) -> float:
    """Savings vs. paying for all tokens as normal input (no cache)."""
    if totals["cache_read"] == 0:
        return 0.0
    if per_model:
        saved = 0.0
        for model, vals in per_model.items():
            cr = vals[2]
            p = get_pricing({model}, pricing)
            saved += cr / 1_000_000 * max(p["in"] - p["cr"], 0)
        return saved
    p = get_pricing(models_seen, pricing)
    delta = p["in"] - p["cr"]
    return totals["cache_read"] / 1_000_000 * max(delta, 0)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def fmt_k(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


# ---------------------------------------------------------------------------
# Ponytail gain (EP-057) — riga opzionale, letta dall'ultimo ponytail-audit report
# ---------------------------------------------------------------------------

def ponytail_gain(project_dir: str) -> Optional[str]:
    """Riga /ponytail-gain: aggregato dell'ultimo report ponytail-audit.

    Mostrata solo se ponytail.enabled:true in factory.config.yaml E esiste almeno un
    report code_quality/reports/ponytail-audit-*.md. Fail-open: qualsiasi errore → None.
    """
    try:
        cfg = os.path.join(project_dir, "factory.config.yaml")
        if not os.path.exists(cfg):
            return None
        with open(cfg, encoding="utf-8") as f:
            cfg_text = f.read()
        # ponytail: ... enabled: true (blocco top-level, indentazione a 2 spazi)
        block = re.search(r"(?m)^ponytail:\s*$(.*?)(?=^\S|\Z)", cfg_text, re.DOTALL)
        if not block or not re.search(r"(?m)^\s+enabled:\s*true\b", block.group(1)):
            return None

        reports_dir = os.path.join(project_dir, "code_quality", "reports")
        if not os.path.isdir(reports_dir):
            return None
        audits = sorted(
            f for f in os.listdir(reports_dir)
            if f.startswith("ponytail-audit-") and f.endswith(".md")
        )
        if not audits:
            return None

        with open(os.path.join(reports_dir, audits[-1]), encoding="utf-8") as f:
            report = f.read()
        files = re.search(r"(?m)^files_scanned:\s*(\d+)", report)
        cand = re.search(r"(?m)^candidates:\s*(\d+)", report)
        saving = re.search(r"(?m)^estimated_saving_lines:\s*(\d+)", report)
        if not (files and cand):
            return None
        saving_str = f"  saving stimato: ~{saving.group(1)} righe" if saving else ""
        return (
            f"◉ PONYTAIL  audit: {files.group(1)} file  "
            f"candidati: {cand.group(1)}{saving_str}"
        )
    except Exception:
        return None  # fail-open: mai rompere il token ledger


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def display_compact(totals: Dict, cost: float, savings: float) -> None:
    cache_note = f"  💾 -{savings:.4f}$" if savings > 0.0001 else ""
    print(
        f"◉ TOKENS  "
        f"in:{fmt_k(totals['input'])}  "
        f"out:{fmt_k(totals['output'])}"
        f"{cache_note}"
        f"  │  sessione: ~${cost:.4f}"
    )


def display_full(totals: Dict, cost: float, savings: float, models_seen: Set) -> None:
    model_str = ", ".join(sorted(normalize_model(m) for m in models_seen)) or "unknown"
    border = "─" * 52
    print(f"\n╭{border}╮")
    print(f"│  TOKEN LEDGER — sessione corrente              │")
    print(f"│  Modelli: {model_str[:40]:<40}│")
    print(f"├{border}┤")
    print(f"│  Input:       {fmt_k(totals['input']):>10}  tokens                  │")
    print(f"│  Output:      {fmt_k(totals['output']):>10}  tokens                  │")
    if totals["cache_read"] > 0:
        print(f"│  Cache read:  {fmt_k(totals['cache_read']):>10}  tokens                  │")
        print(f"│  Risparmio:   ${savings:>10.4f}                         │")
    if totals["cache_write"] > 0:
        print(f"│  Cache write: {fmt_k(totals['cache_write']):>10}  tokens                  │")
        if totals.get("cache_write_1h", 0) > 0:
            print(f"│    di cui 1h: {fmt_k(totals['cache_write_1h']):>10}  tokens                  │")
    print(f"├{border}┤")
    print(f"│  Costo sessione:  ~${cost:>8.4f}                    │")
    print(f"╰{border}╯")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Mostra token usage real-time dalla sessione Claude Code."
    )
    ap.add_argument("--from-hook", action="store_true",
                    help="Leggi hook JSON da stdin (Stop/SessionEnd hook mode)")
    ap.add_argument("--full", action="store_true",
                    help="Display box completo (default: one-liner compatto)")
    ap.add_argument("--transcript", default=None,
                    help="Path esplicito al transcript JSONL (override auto-discovery)")
    # `statusline-ledger.py --json` NON e' un sostituto: legge il contesto di sessione da
    # stdin (protocollo statusline), quindi un chiamante che non e' la statusline — un
    # servizio, un test, la plancia — deve chiudergli stdin per non restare appeso, e
    # allora risponde `null` su tutto. Qui il transcript si trova da solo, quindi la
    # risposta e' un numero anche fuori sessione.
    ap.add_argument("--json", action="store_true",
                    help="Uscita macchina su stdout invece del display (per servizi e test)")
    args = ap.parse_args()

    transcript: Optional[str] = args.transcript

    if args.from_hook:
        try:
            raw = sys.stdin.read()
            hook = json.loads(raw) if raw.strip() else {}
            transcript = transcript or hook.get("transcript_path")
        except Exception:
            pass

    if not transcript or not os.path.exists(transcript):
        transcript = find_transcript()

    if not transcript or not os.path.exists(transcript):
        if args.json:
            print(json.dumps({"disponibile": False, "ragione": "nessun transcript trovato"}))
        return 0  # fail-open: no transcript found

    totals, models_seen, per_model = parse_session(transcript)
    if totals["input"] == 0 and totals["output"] == 0:
        if args.json:
            print(json.dumps({"disponibile": False,
                              "ragione": "transcript senza token contabilizzati"}))
        return 0  # no data yet

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    pricing = load_pricing(project_dir)
    cost = calc_cost(totals, models_seen, pricing, per_model)
    savings = cache_savings(totals, models_seen, pricing, per_model)

    if args.json:
        # `disponibile` esplicito: chi legge non deve dedurre l'assenza da un campo a
        # `null`. Un buco dichiarato e un buco silenzioso si distinguono qui, non a valle.
        print(json.dumps({
            "disponibile": True,
            "input": totals["input"],
            "output": totals["output"],
            "cost_usd": round(cost, 4),
            "cache_savings_usd": round(savings, 4),
            "modelli": sorted(models_seen),
            "transcript": transcript,
        }))
        return 0

    if args.full:
        display_full(totals, cost, savings, models_seen)
    else:
        display_compact(totals, cost, savings)

    # /ponytail-gain (EP-057) — riga opzionale, omessa se non applicabile
    gain = ponytail_gain(project_dir)
    if gain:
        print(gain)

    return 0


if __name__ == "__main__":
    sys.exit(main())
