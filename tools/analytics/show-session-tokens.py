#!/usr/bin/env python3
"""
show-session-tokens.py — display real-time token usage from the current session.
Called by the Stop hook to show cumulative costs after each Claude response.
Complements harvest-session-tokens.py (which logs to SessionEnd in the JSONL store).

Reads the Claude Code JSONL transcript from the current CWD and aggregates the tokens
(input + output + cache) from all assistant messages in the session.

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

def parse_tokens(path: str) -> Tuple[Dict, Set]:
    """
    Aggregate token usage from all assistant messages in the transcript.
    Returns (totals_dict, models_seen_set).
    """
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    models_seen: Set[str] = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
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
                models_seen.add(model)
                totals["input"]       += int(usage.get("input_tokens", 0) or 0)
                totals["output"]      += int(usage.get("output_tokens", 0) or 0)
                totals["cache_read"]  += int(usage.get("cache_read_input_tokens", 0) or 0)
                totals["cache_write"] += int(usage.get("cache_creation_input_tokens", 0) or 0)
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return totals, models_seen


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

_FALLBACK_PRICING = {
    # Sonnet 4.6 as a reasonable fallback (USD/1M)
    "in":  3.0,
    "out": 15.0,
    "cr":  0.3,    # cache read
    "cw":  3.75,   # cache write
}

_MODEL_FALLBACKS: Dict[str, Dict] = {
    "claude-opus":   {"in": 5.0,  "out": 25.0, "cr": 0.5,  "cw": 6.25},
    "claude-sonnet": {"in": 3.0,  "out": 15.0, "cr": 0.3,  "cw": 3.75},
    "claude-haiku":  {"in": 1.0,  "out": 5.0,  "cr": 0.1,  "cw": 1.25},
    "claude-fable":  {"in": 3.0,  "out": 15.0, "cr": 0.3,  "cw": 3.75},
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


def calc_cost(totals: Dict, models_seen: Set, pricing: Dict) -> float:
    p = get_pricing(models_seen, pricing)
    return (
        totals["input"]       / 1_000_000 * p["in"]
        + totals["output"]    / 1_000_000 * p["out"]
        + totals["cache_read"] / 1_000_000 * p["cr"]
        + totals["cache_write"]/ 1_000_000 * p["cw"]
    )


def cache_savings(totals: Dict, models_seen: Set, pricing: Dict) -> float:
    """Savings vs. paying for all tokens as normal input (no cache)."""
    if totals["cache_read"] == 0:
        return 0.0
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
        return 0  # fail-open: no transcript found

    totals, models_seen = parse_tokens(transcript)
    if totals["input"] == 0 and totals["output"] == 0:
        return 0  # no data yet

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    pricing = load_pricing(project_dir)
    cost = calc_cost(totals, models_seen, pricing)
    savings = cache_savings(totals, models_seen, pricing)

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
