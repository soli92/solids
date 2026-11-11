#!/usr/bin/env python3
"""
llm-advisory.py — optional LLM advisory for the session analysis report (depth full).

Reads the base report JSON written by generate-report.py (deterministic pipeline
already completed), builds a compact digest of its redacted aggregates (anomalies +
session metrics), checks it for leaks, bounds it to session_analysis.max_token_budget
and asks a model for an interpretive note via the Claude Code CLI in headless mode
(`claude -p`, the user's own authentication; no API key needed).

The output JSON is consumed by `generate-report.py --advisory <file>`, which puts the
text only in ## Punti Aperti (marked "LLM advisory") and the real token usage in
## Metriche Sessione. This script never writes the report itself.

CLI:
  python3 llm-advisory.py <base-report-json> --depth full --output <advisory.json>
          [--model <id>]                 (default: session_analysis.advisory_model, else
                                          models.routing.tier_fast of the config)
          [--config factory.config.yaml]
          [--claude-bin <path>]          (or env SESSION_ANALYSIS_CLAUDE_BIN)
          [--timeout 120] [--max-budget-usd 0.05]
          [--dry-run]                    (print payload and estimate, no call)

Exit codes:
  0  advisory written to --output
  1  usage / I/O error
  2  STOP (R-SAA-3): leak pattern in the payload or in the model output — no call
     (payload) or nothing written (output)
  3  STOP gate: depth != full, session_analysis.enabled not true, or the input is not
     a base report of the deterministic pipeline — no call
  4  SKIP with WARNING: budget too small, nothing to interpret, CLI unavailable or
     failed — no advisory written, the deterministic report stays unchanged

Budget: max_token_budget is split into an output cap (a quarter, at least 64) and an
input cap (the rest). The input estimate is ceil(chars / 4) of the system prompt plus
the user prompt. Over the cap, the lowest-severity anomalies are dropped and the
truncation is declared; if even the metrics alone do not fit, SKIP. The output cap is
both an instruction in the prompt and a hard truncation of the returned text. Real
tokens come from the CLI JSON response and are reported as they are (they include the
CLI's own fixed overhead, which this script cannot bound).

stdlib-only: json, math, os, pathlib, re, shutil, subprocess, sys, tempfile, argparse
"""

import argparse
import datetime
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from redaction import find_leaks, redact_str  # noqa: E402

ADVISORY_TYPE = "session-analysis-llm-advisory"
ADVISORY_MARKER = "LLM advisory"
# Last-resort fallback, used only when the config has neither
# session_analysis.advisory_model nor models.routing.tier_fast.
FALLBACK_MODEL = "claude-haiku-5-5"
DEFAULT_BUDGET = 1000
SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}
FIELD_CAP = 160  # chars per free-text field in the digest

EXIT_OK, EXIT_USAGE, EXIT_LEAK, EXIT_GATE, EXIT_SKIP = 0, 1, 2, 3, 4


# ── Config (stdlib line parser, same approach as generate-report.py) ───────────

def _find_factory_config() -> "pathlib.Path | None":
    here = pathlib.Path(__file__).resolve().parent
    for candidate in (here, here.parent, here.parent.parent, here.parent.parent.parent):
        cfg = candidate / "factory.config.yaml"
        if cfg.exists():
            return cfg
    return None


def _read_session_analysis(cfg: "pathlib.Path | None") -> dict:
    """Scalar keys directly under the top-level `session_analysis:` block."""
    if cfg is None or not cfg.exists():
        return {}
    lines = cfg.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if re.match(r"^session_analysis:\s*(#.*)?$", l))
    except StopIteration:
        return {}
    out = {}
    indent = None
    for line in lines[start + 1:]:
        if line.strip() and not line.lstrip().startswith("#") and not line[0].isspace():
            break  # next top-level key
        m = re.match(r"^(\s+)([A-Za-z_][A-Za-z0-9_]*):(.*)$", line)
        if not m:
            continue
        if indent is None:
            indent = len(m.group(1))
        if len(m.group(1)) != indent:
            continue  # nested key
        value = re.sub(r"\s+#.*$", "", m.group(3)).strip().strip("\"'")
        out[m.group(2)] = value
    return out


def _read_registry_tier_fast(cfg: "pathlib.Path | None") -> str:
    """models.routing.tier_fast from the Model Registry ('' if not readable)."""
    if cfg is None or not cfg.exists():
        return ""
    in_models = in_routing = False
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if re.match(r"^models:\s*(#.*)?$", line):
            in_models, in_routing = True, False
            continue
        if in_models and line.strip() and not line.lstrip().startswith("#") and not line[0].isspace():
            break
        if in_models and re.match(r"^\s+routing:\s*(#.*)?$", line):
            in_routing = True
            continue
        if in_routing:
            m = re.match(r"^\s+tier_fast:\s*([^\s#]+)", line)
            if m:
                return m.group(1).strip("\"'")
    return ""


def _resolve_model(explicit: "str | None", cfg: dict, cfg_path: "pathlib.Path | None") -> str:
    """--model, then session_analysis.advisory_model, then the registry's tier_fast."""
    return (explicit or cfg.get("advisory_model") or _read_registry_tier_fast(cfg_path)
            or FALLBACK_MODEL)


# ── Input: base report of the deterministic pipeline ───────────────────────────

def _check_base_report(report) -> str:
    """Return an error message if report is not a base report, else ''."""
    if not isinstance(report, dict) or report.get("type") != "session-analysis-report":
        return "l'input non è un report di generate-report.py (type != session-analysis-report)"
    if report.get("ingest_eligible") is not False:
        return "report senza ingest_eligible: false"
    if not isinstance(report.get("anomalies"), list):
        return "report senza lista anomalies"
    if "llm_advisory" in report:
        return "il report contiene già un llm_advisory: serve il report base deterministico"
    if report.get("depth") != "full":
        return "il report base va generato con --depth full"
    return ""


def _cap(value, n=FIELD_CAP):
    if not isinstance(value, str):
        return value
    return value if len(value) <= n else value[: n - 1] + "…"


def _digest_anomaly(a: dict) -> dict:
    keys = ("id", "category", "subtype", "severity", "wave_id", "attribution_agent",
            "evidence_count", "pattern_eligible")
    d = {k: a.get(k) for k in keys if a.get(k) is not None}
    d["description"] = _cap(a.get("description") or "")
    d["fix_suggestion"] = _cap(a.get("fix_suggestion") or "")
    return d


def _build_digest(report: dict, anomalies: list) -> dict:
    return {
        "session_id": report.get("session_id"),
        "anomaly_count": report.get("anomaly_count"),
        "worst_severity": report.get("worst_severity"),
        "session_metrics": report.get("session_metrics") or {},
        "report_warnings": [_cap(w, 120) for w in (report.get("warnings") or [])],
        "anomalies": anomalies,
    }


# ── Prompt ─────────────────────────────────────────────────────────────────────

def _system_prompt(max_words: int) -> str:
    return (
        "Sei un revisore advisory di un report di session-analysis. Ricevi solo aggregati "
        "redatti (anomalie e metriche) prodotti da strumenti deterministici. Interpreta le "
        "anomalie che richiedono giudizio umano: cause plausibili, correlazioni tra anomalie, "
        "cosa verificare. Regole: usa solo i dati forniti e cita gli ID anomalia; non "
        "inventare numeri; non scrivere comandi, codice, patch o fix applicabili in automatico; "
        "ogni azione suggerita inizia con 'Da valutare dall'operatore:'. "
        f"Rispondi in italiano, elenco puntato, al massimo {max_words} parole."
    )


def _user_prompt(digest: dict, dropped: int) -> str:
    note = ""
    if dropped:
        note = (f"\nNota: per limite di budget sono escluse {dropped} anomalie a severity "
                "più bassa.")
    return ("Aggregati redatti della sessione (JSON):\n"
            + json.dumps(digest, ensure_ascii=False, separators=(",", ":")) + note)


def _estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


def _fit_budget(report: dict, input_cap: int, max_words: int):
    """
    Drop lowest-severity anomalies until the payload fits input_cap.
    Returns (system, user, estimate, included, total) or None if nothing fits.
    """
    ordered = sorted(
        (_digest_anomaly(a) for a in report.get("anomalies") or []),
        key=lambda a: SEVERITY_RANK.get(a.get("severity"), 9),
    )
    system = _system_prompt(max_words)
    total = len(ordered)
    for n in range(total, -1, -1):
        user = _user_prompt(_build_digest(report, ordered[:n]), total - n)
        est = _estimate_tokens(system + user)
        if est <= input_cap and n > 0:
            return system, user, est, n, total
    return None


# ── Output filtering (R-SAA-6: no auto-applicable actions) ─────────────────────

_FENCE_RE = re.compile(r"```.*?(```|$)", re.S)
_CMD_WORDS = (r"sudo|rm|git|python3?|pip3?|npm|npx|node|curl|wget|bash|sh|zsh|chmod|chown|"
              r"mv|cp|sed|awk|make|docker|kubectl|claude|cat|echo")
_CMD_LINE_RE = re.compile(rf"^\s*(?:[-*]\s+)?(?:\$\s*|#\s+)?(?:{_CMD_WORDS})\s+\S")
_SLASH_CMD_LINE_RE = re.compile(r"^\s*(?:[-*]\s+)?`?/[a-z][a-z0-9-]+(?:\s|`|$)")
_INLINE_CMD_RE = re.compile(rf"`\s*(?:\$\s*)?(?:(?:{_CMD_WORDS})\s+[^`]*|/[a-z][a-z0-9-]+[^`]*)`")
REMOVED = "[comando rimosso: azione da valutare dall'operatore]"


def _filter_commands(text: str) -> "tuple[str, int]":
    removed = 0

    def _count(_m):
        nonlocal removed
        removed += 1
        return REMOVED

    text = _FENCE_RE.sub(_count, text)
    text = _INLINE_CMD_RE.sub(_count, text)
    lines = []
    for line in text.splitlines():
        if _CMD_LINE_RE.match(line) or _SLASH_CMD_LINE_RE.match(line):
            removed += 1
            lines.append(REMOVED)
        else:
            lines.append(line)
    return "\n".join(lines).strip(), removed


def _truncate_output(text: str, output_cap: int) -> "tuple[str, bool]":
    max_chars = output_cap * 4
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip() + " [TRONCATO al limite di budget]", True


# ── CLI invocation ─────────────────────────────────────────────────────────────

def _resolve_claude_bin(explicit: "str | None") -> "str | None":
    candidates = [
        explicit,
        os.environ.get("SESSION_ANALYSIS_CLAUDE_BIN"),
        shutil.which("claude"),
        str(pathlib.Path.home() / ".local" / "bin" / "claude"),
        os.environ.get("CLAUDE_CODE_EXECPATH"),
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def _child_env(output_cap: int) -> dict:
    """Environment for the child CLI without the parent session's variables."""
    env = dict(os.environ)
    for k in list(env):
        if k == "CLAUDECODE" or (k.startswith("CLAUDE_") and k != "CLAUDE_CONFIG_DIR"):
            env.pop(k)
    # The CLI has no flag for the generation limit: without this variable the
    # model is free to generate past the budget and only the report text is cut.
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(output_cap)
    # Extended thinking counts against the same output limit: an advisory of
    # a few sentences does not need it.
    env["MAX_THINKING_TOKENS"] = "0"
    return env


def _call_claude(bin_path, model, system, user, timeout, max_budget_usd, output_cap):
    """Run `claude -p` once, no tools, no session persistence. Returns (data, error)."""
    cmd = [
        bin_path, "-p",
        "--output-format", "json",
        "--model", model,
        "--system-prompt", system,
        "--tools", "",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--max-budget-usd", str(max_budget_usd),
    ]
    with tempfile.TemporaryDirectory(prefix="sa-advisory-") as cwd:
        # Empty cwd: no project CLAUDE.md or settings are picked up by the child.
        try:
            proc = subprocess.run(
                cmd, input=user, capture_output=True, text=True,
                timeout=timeout, cwd=cwd, env=_child_env(output_cap),
            )
        except subprocess.TimeoutExpired:
            return None, f"timeout dopo {timeout}s"
        except OSError as exc:
            return None, f"esecuzione fallita: {exc}"
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        tail = (proc.stderr or proc.stdout or "").strip()[-300:]
        return None, f"risposta non JSON (exit {proc.returncode}): {redact_str(tail)}"
    if proc.returncode != 0 or data.get("is_error") or data.get("subtype") not in (None, "success"):
        detail = data.get("result") or data.get("subtype") or proc.stderr.strip()[-200:]
        return None, f"CLI in errore (exit {proc.returncode}): {redact_str(str(detail))[:300]}"
    if not isinstance(data.get("result"), str):
        return None, "risposta JSON senza campo result"
    return data, ""


def _usage(data: dict) -> dict:
    u = data.get("usage") or {}
    keys = ("input_tokens", "output_tokens", "cache_read_input_tokens",
            "cache_creation_input_tokens")
    return {k: int(u.get(k) or 0) for k in keys}


# ── Main ───────────────────────────────────────────────────────────────────────

def _inside(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM advisory for session analysis (depth full).")
    ap.add_argument("report_json", help="base report JSON written by generate-report.py --depth full")
    ap.add_argument("--depth", choices=["quick", "full"], default="quick",
                    help="the advisory runs only with full (default quick = no call)")
    ap.add_argument("--output", help="advisory JSON to write (outside raw/ and wiki/)")
    ap.add_argument("--model", default=None,
                    help="model id (default: session_analysis.advisory_model, else "
                         "models.routing.tier_fast of factory.config.yaml)")
    ap.add_argument("--config", default=None, help="factory.config.yaml (auto-discovered)")
    ap.add_argument("--claude-bin", default=None,
                    help="claude executable (default: env SESSION_ANALYSIS_CLAUDE_BIN, PATH, "
                         "~/.local/bin/claude)")
    ap.add_argument("--timeout", type=int, default=120, help="CLI timeout in seconds")
    ap.add_argument("--max-budget-usd", type=float, default=0.05,
                    help="cost cap passed to the CLI (--max-budget-usd)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the payload and the estimate, do not call the model")
    args = ap.parse_args()

    # Gate: explicit activation only.
    if args.depth != "full":
        print("STOP: LLM advisory solo con --depth full (depth quick: nessuna chiamata LLM).",
              file=sys.stderr)
        return EXIT_GATE

    cfg_path = pathlib.Path(args.config) if args.config else _find_factory_config()
    cfg = _read_session_analysis(cfg_path)
    if cfg.get("enabled", "").lower() != "true":
        print("STOP (R-SAA-5): session_analysis.enabled non è true — nessuna chiamata LLM.",
              file=sys.stderr)
        return EXIT_GATE

    model = _resolve_model(args.model, cfg, cfg_path)

    budget_raw = cfg.get("max_token_budget", "")
    if re.fullmatch(r"\d+", budget_raw or "") and int(budget_raw) > 0:
        budget = int(budget_raw)
    else:
        budget = DEFAULT_BUDGET
        print(f"WARNING: session_analysis.max_token_budget assente o non valido — "
              f"default {DEFAULT_BUDGET}.", file=sys.stderr)
    if budget < 500:
        print(f"WARNING: max_token_budget = {budget} (< 500).", file=sys.stderr)

    if not args.dry_run:
        if not args.output:
            print("ERROR: --output obbligatorio (salvo --dry-run).", file=sys.stderr)
            return EXIT_USAGE
        factory_root = cfg_path.parent if cfg_path else None
        out = pathlib.Path(args.output)
        if factory_root and any(_inside(out, factory_root / d) for d in ("raw", "wiki", "code_repos")):
            print("ERROR: --output non può stare in raw/, wiki/ o code_repos/: l'advisory è un "
                  "file intermedio, il report lo scrive generate-report.py.", file=sys.stderr)
            return EXIT_USAGE

    # Prerequisite: the deterministic pipeline produced the base report.
    try:
        report = json.loads(pathlib.Path(args.report_json).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"STOP: report base non leggibile ({exc}) — eseguire prima la pipeline "
              "deterministica e generate-report.py --depth full.", file=sys.stderr)
        return EXIT_GATE
    err = _check_base_report(report)
    if err:
        print(f"STOP: {err}.", file=sys.stderr)
        return EXIT_GATE

    if not report["anomalies"]:
        print("WARNING: nessuna anomalia da interpretare — advisory saltato, report invariato.",
              file=sys.stderr)
        return EXIT_SKIP

    output_cap = max(64, budget // 4)
    input_cap = budget - output_cap
    max_words = max(30, int(output_cap * 0.6))
    fitted = _fit_budget(report, input_cap, max_words)
    if fitted is None:
        minimal = _estimate_tokens(_system_prompt(max_words)
                                   + _user_prompt(_build_digest(report, report["anomalies"][:1]), 0))
        print(f"WARNING: budget insufficiente — stima input minima {minimal} token "
              f"(ceil(caratteri/4)) > cap input {input_cap} su max_token_budget {budget}. "
              "Advisory saltato, report deterministico invariato.", file=sys.stderr)
        return EXIT_SKIP
    system, user, estimate, included, total = fitted

    # R-SAA-3 pre-scan on exactly what would be sent.
    leaks = find_leaks(system + "\n" + user, strict=True)
    if leaks:
        print(f"STOP (R-SAA-3): pattern sensibili nell'input LLM ({', '.join(leaks)}) — "
              "nessuna chiamata.", file=sys.stderr)
        return EXIT_LEAK

    print(f"INFO: stima input {estimate} token (ceil(caratteri/4)), cap input {input_cap}, "
          f"cap output {output_cap}, anomalie {included}/{total}.", file=sys.stderr)
    if included < total:
        print(f"WARNING: input troncato per budget — escluse {total - included} anomalie.",
              file=sys.stderr)

    if args.dry_run:
        print("=== SYSTEM ===\n" + system + "\n=== USER ===\n" + user)
        return EXIT_OK

    bin_path = _resolve_claude_bin(args.claude_bin)
    if bin_path is None:
        print("WARNING: CLI claude non trovata — advisory saltato, report invariato.",
              file=sys.stderr)
        return EXIT_SKIP

    data, call_err = _call_claude(bin_path, model, system, user,
                                  args.timeout, args.max_budget_usd, output_cap)
    if data is None:
        print(f"WARNING: chiamata LLM fallita — {call_err}. Advisory saltato, report invariato.",
              file=sys.stderr)
        return EXIT_SKIP

    text, removed = _filter_commands(redact_str(data["result"]))
    text, out_truncated = _truncate_output(text, output_cap)
    if not text.strip():
        print("WARNING: risposta vuota dopo il filtro — advisory saltato.", file=sys.stderr)
        return EXIT_SKIP
    out_leaks = find_leaks(text, strict=True)
    if out_leaks:
        print(f"STOP (R-SAA-3): pattern sensibili nell'output del modello "
              f"({', '.join(out_leaks)}) — advisory non scritto.", file=sys.stderr)
        return EXIT_LEAK

    usage = _usage(data)
    cost = data.get("total_cost_usd")
    advisory = {
        "type": ADVISORY_TYPE,
        "marker": ADVISORY_MARKER,
        "deterministic": False,
        "session_id": report.get("session_id"),
        "model": model,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "text": text,
        "usage": usage,
        "total_cost_usd": cost if isinstance(cost, (int, float)) else None,
        "budget": {
            "max_token_budget": budget,
            "input_cap_tokens": input_cap,
            "output_cap_tokens": output_cap,
            "input_estimate_tokens": estimate,
            "estimate_method": "ceil(caratteri/4) di system prompt + user prompt",
        },
        "truncation": {
            "anomalies_included": included,
            "anomalies_total": total,
            "input_truncated": included < total,
            "output_truncated": out_truncated,
        },
        "commands_removed": removed,
    }
    pathlib.Path(args.output).write_text(json.dumps(advisory, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    print(f"Advisory written: {args.output} | token in={usage['input_tokens']} "
          f"out={usage['output_tokens']} cache_read={usage['cache_read_input_tokens']} "
          f"cache_write={usage['cache_creation_input_tokens']}", file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
