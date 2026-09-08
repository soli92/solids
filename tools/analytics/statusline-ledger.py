#!/usr/bin/env python3
"""
statusline-ledger.py — token ledger come Claude Code statusLine.

Rimpiazza l'hook Stop (EP-022) nel runtime estensione VS Code / Agent SDK, dove gli
hook shell di .claude/settings.json NON vengono eseguiti (gap CLI↔estensione, verificato
2026-09-01: log hook vuoto dopo un turno completo). La statusLine invece è eseguita
dall'estensione, si aggiorna dopo ogni risposta e riceve il costo di sessione da Claude
Code stesso su stdin (campo cost.total_cost_usd — numero autorevole, non stimato).

INPUT: JSON su stdin fornito da Claude Code. Campi usati (fail-open se assenti):
  cost.total_cost_usd            costo cumulativo sessione USD (reset a /clear)
  model.display_name             nome modello
  context_window.used_percentage % finestra di contesto occupata
  context_window.total_input_tokens / total_output_tokens  token in contesto

OUTPUT:
  senza flag  → una riga su stdout (la statusLine mostra la prima riga):
                ◉ TOKENS  ctx {in}↓/{out}↑  ({pct}%)  │  sessione: ~${cost:.4f}  ·  {model}
  --json      → oggetto JSON machine-readable con le stesse metriche

INTEGRAZIONE (aggiungere in .claude/settings.json):
  "statusLine": "python3 tools/analytics/statusline-ledger.py"
  (path relativo al root del progetto soli-multi-agents-factory)

Complementarietà con show-session-tokens.py:
  - statusline-ledger.py : costo autorevole da Claude Code runtime (stdin), per statusbar VS Code
  - show-session-tokens.py : costo stimato da transcript JSONL, per display in-chat (EP-022)
  I due tool coesistono e non si sovrappongono (canali distinti).

DIPENDENZE: solo stdlib Python 3 — sys, json, os, argparse.
VINCOLI: nessun subprocess, nessuna scrittura file, sempre exit 0.
"""
import sys
import json
import os
import argparse


def fmt_k(n) -> str:
    """Formatta un intero in formato compatto (k/M)."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "?"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def parse_stdin() -> dict:
    """Legge JSON da stdin. Fail-open: stdin vuoto o JSON non valido → {}."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def extract_metrics(data: dict) -> dict:
    """Estrae le metriche rilevanti dal payload JSON di Claude Code."""
    cost = (data.get("cost") or {}).get("total_cost_usd")
    ctx = data.get("context_window") or {}
    return {
        "cost": cost,
        "used_pct": ctx.get("used_percentage"),
        "ctx_in": ctx.get("total_input_tokens"),
        "ctx_out": ctx.get("total_output_tokens"),
        "model": (data.get("model") or {}).get("display_name"),
    }


def format_line(m: dict) -> str:
    """Produce la riga statusline a partire dalle metriche estratte."""
    parts = ["◉ TOKENS"]

    if m["ctx_in"] is not None or m["ctx_out"] is not None:
        in_fmt = fmt_k(m["ctx_in"] or 0)
        out_fmt = fmt_k(m["ctx_out"] or 0)
        parts.append(f"ctx {in_fmt}↓/{out_fmt}↑")

    if isinstance(m["used_pct"], (int, float)):
        parts.append(f"({m['used_pct']:.0f}%)")

    cost_str = f"~${m['cost']:.4f}" if isinstance(m["cost"], (int, float)) else "~$?"
    tail = f"│  sessione: {cost_str}"
    if m["model"]:
        tail += f"  ·  {m['model']}"

    return f"{'  '.join(parts)}  {tail}"


def format_json(m: dict) -> str:
    """Produce output JSON machine-readable con le stesse metriche."""
    out = {
        "cost_usd": m["cost"],
        "context_window": {
            "input_tokens": m["ctx_in"],
            "output_tokens": m["ctx_out"],
            "used_percentage": m["used_pct"],
        },
        "model": m["model"],
    }
    return json.dumps(out, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Token ledger statusline — legge metriche da stdin (Claude Code runtime)."
    )
    ap.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output machine-readable JSON invece della riga statusline plain text.",
    )
    args = ap.parse_args()

    data = parse_stdin()
    metrics = extract_metrics(data)

    if args.output_json:
        print(format_json(metrics))
    else:
        print(format_line(metrics))

    return 0


if __name__ == "__main__":
    sys.exit(main())
