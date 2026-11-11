#!/usr/bin/env python3
# =============================================================================
# run-monte-carlo.py — deterministic tool run_monte_carlo (EP-010, US-041, TSK-073)
# =============================================================================
#
# Part of the Task Analytics & Cost/Time Estimation (EP-010) capability, instance
# of the pattern [[thin-agents-fat-skills-refactor]]: this is the TOOL (deterministic
# numerical logic, no LLM reasoning). Runs the Monte Carlo throughput forecast
# (§Method 3): for `iterations` runs it samples weekly throughput from the
# historical distribution until the backlog is covered, collects `weeks_needed`, and
# emits the p50/p85/p95 duration percentiles. The tool does NOT choose the
# methodology: the skill (US-040) / agent (US-043) or `force_method` decide
# whether/when to invoke it; here we only perform the calculation.
#
# PATTERN.md §3 — optional canonical operation «Monte Carlo Throughput».
# Wiki: wiki/concepts/task-analytics-cost-estimation-capability.md
#       [[task-analytics-cost-estimation-capability]] §Enterprise estimate (forecast
#       face), §Mandatory output of every estimate.
#       wiki/syntheses/task-analytics-estimation-methods.md §Method 3.
# ADR-026 — Monte Carlo runtime: Python + numpy as DEFAULT (performance:
#           10k vectorized simulations in <1s). §A runtime, §B fail-loud on
#           missing numpy/python with exact install command, §F `--seed` for
#           reproducibility (metadata.seed always present), §G backward compat.
#
# INVARIANT «never a point estimate»: output ALWAYS exposes p50/p85/p95 percentiles
# (never a single expected value as primary, never `mean`/`average`/`media`). Durations
# are long-tail distributions: the mean misleads.
#
# FAIL-LOUD (ADR-026 §B): if `import numpy` fails → exit 2 + canonical verbatim
# message on stderr with exact `pip install`. No silent fallback.
#
# OPT-IN / R.P3: tool is no-op when capability is off. File presence/absence
# does not produce lint ERROR; invocation without required input fails loud.
#
# -----------------------------------------------------------------------------
# INPUT CONTRACT (CLI)
#   --throughput-samples '<JSON list>'  historical throughput distribution (tasks/week),
#                                       e.g. '[1,2,3,2,4]'. Required.
#   --backlog <int>                     number of tasks to complete. Required, >0.
#   --iterations <int>                  default 10000.
#   --week-count-cap <int>              anti-infinite-loop guard, default 520 (10 years).
#   --seed <int>                        optional; if absent → random from os.urandom.
#                                       Same seed + same input → byte-identical output.
#   --config <path>                     default "factory.config.yaml" (for no-op check).
#
# OUTPUT CONTRACT (stdout, pure JSON) — schema ADR-026 §A / TSK-073:
#   { iterations, backlog,
#     percentiles: { duration_weeks: {p50, p85, p95} },
#     distribution: { histogram: [{week, count}], bins: [...] },
#     metadata: { runtime, numpy, duration_ms, seed } }
#
# EXIT CODES: 0 ok | 1 invalid input / no-op gate | 2 missing dependency (numpy).
# =============================================================================

import sys
import os
import json
import time
import argparse

# --- Fail-loud numpy (ADR-026 §B) — first effective runtime line --------
try:
    import numpy as np
except ImportError:
    sys.stderr.write(
        "ERROR: numpy non installato. Monte Carlo runtime richiede numpy >=1.24.\n"
        "\n"
        "Install:\n"
        "  pip install 'numpy>=1.24'        # globale (sconsigliato per factory)\n"
        "  # OPPURE (raccomandato — venv dedicato):\n"
        "  python3 -m venv .factory-venv/analytics\n"
        "  source .factory-venv/analytics/bin/activate\n"
        "  pip install 'numpy>=1.24'\n"
        "\n"
        "Vedi ADR-026 §B per dettaglio.\n"
    )
    sys.exit(2)


def _die(msg, code=1):
    sys.stderr.write(msg.rstrip("\n") + "\n")
    sys.exit(code)


def _check_no_op(config_path):
    """R.P3 / ADR-026 §G: no-op when capability is off.

    If factory.config.yaml is present and analytics.estimation.enabled is
    explicitly false, the tool is no-op (does not simulate). Minimal tolerant
    parsing: if the file/block is missing or unreadable, we do NOT block
    (explicit invocation = explicit intent; the real gate lives in the skill).
    """
    if not config_path or not os.path.isfile(config_path):
        return  # no config → cannot prove disabled state; proceed
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return
    enabled = None
    in_analytics = in_estimation = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 0:
            in_analytics = stripped.startswith("analytics:")
            in_estimation = False
            continue
        if in_analytics and stripped.startswith("estimation:"):
            in_estimation = True
            continue
        if in_analytics and in_estimation and stripped.startswith("enabled:"):
            val = stripped.split(":", 1)[1].strip().lower()
            enabled = val in ("true", "yes", "on", "1")
            break
        # left estimation block when encountering a key at indent <= estimation level
        if in_estimation and indent <= 2 and not stripped.startswith("enabled:"):
            in_estimation = False
    if enabled is False:
        _die(
            "Monte Carlo no-op: analytics.estimation.enabled=false in "
            f"{config_path}. Attivare la capability (analytics.estimation.enabled: true) "
            "o invocare con un config diverso. Vedi ADR-026 §G / R.P3.",
            code=1,
        )


def simulate(throughput_samples, backlog, iterations, week_count_cap, rng):
    """Vectorized Monte Carlo throughput forecast (synthesis §Method 3).

    For each of the `iterations` runs, sample week-by-week throughput from the
    historical distribution until `tasks_completed >= backlog`, collecting
    `weeks_needed`. Vectorized in week blocks.
    """
    samples = np.asarray(throughput_samples, dtype=np.float64)
    completed = np.zeros(iterations, dtype=np.float64)
    weeks_needed = np.zeros(iterations, dtype=np.int64)
    done = np.zeros(iterations, dtype=bool)

    week = 0
    while not done.all() and week < week_count_cap:
        week += 1
        draws = rng.choice(samples, size=iterations)
        completed = np.where(done, completed, completed + draws)
        newly_done = (~done) & (completed >= backlog)
        weeks_needed = np.where(newly_done, week, weeks_needed)
        done = done | newly_done

    # Iterations that did not reach backlog within cap: assign cap
    # (signals insufficient throughput; realistic right tail, never underestimate).
    weeks_needed = np.where(done, weeks_needed, week_count_cap)
    return weeks_needed


def main():
    parser = argparse.ArgumentParser(
        prog="run-monte-carlo.py",
        description="Monte Carlo throughput forecast (EP-010, US-041, ADR-026). "
                    "Output JSON su stdout. Invariante: sempre percentili, mai puntuale.",
    )
    parser.add_argument("--throughput-samples", required=True,
                        help="Distribuzione storica throughput come JSON list, es. '[1,2,3,2,4]'.")
    parser.add_argument("--backlog", required=True, type=int,
                        help="Numero di task da completare (>0).")
    parser.add_argument("--iterations", type=int, default=10000,
                        help="Numero di simulazioni (default 10000).")
    parser.add_argument("--week-count-cap", type=int, default=520,
                        help="Guardia anti-loop: settimane massime per run (default 520).")
    parser.add_argument("--seed", type=int, default=None,
                        help="Seed per riproducibilità; default random da os.urandom.")
    parser.add_argument("--config", default="factory.config.yaml",
                        help="Path config per no-op check (default factory.config.yaml).")
    args = parser.parse_args()

    # No-op gate (R.P3 / ADR-026 §G) before any calculation.
    _check_no_op(args.config)

    # --- Input validation (fail-loud) -------------------------------------
    try:
        throughput = json.loads(args.throughput_samples)
    except json.JSONDecodeError as exc:
        _die(f"ERROR: --throughput-samples non è JSON valido: {exc}. "
             "Atteso una lista, es. '[1,2,3,2,4]'.")
    if not isinstance(throughput, list) or not throughput:
        _die("ERROR: --throughput-samples deve essere una lista non vuota di numeri, "
             "es. '[1,2,3,2,4]'.")
    try:
        throughput = [float(x) for x in throughput]
    except (TypeError, ValueError):
        _die("ERROR: --throughput-samples deve contenere solo numeri.")
    if any(x < 0 for x in throughput):
        _die("ERROR: --throughput-samples non può contenere valori negativi.")
    if all(x == 0 for x in throughput):
        _die("ERROR: --throughput-samples tutto a zero: throughput nullo, backlog mai "
             "completabile. Fornire una distribuzione storica con almeno un valore > 0.")
    if args.backlog <= 0:
        _die("ERROR: --backlog deve essere un intero positivo (> 0).")
    if args.iterations <= 0:
        _die("ERROR: --iterations deve essere un intero positivo (> 0).")
    if args.week_count_cap <= 0:
        _die("ERROR: --week-count-cap deve essere un intero positivo (> 0).")

    # --- Seed: sempre presente in metadata (ADR-026 §F) --------------------
    if args.seed is None:
        seed = int.from_bytes(os.urandom(4), "big")
    else:
        seed = int(args.seed)
    rng = np.random.default_rng(seed)

    # --- Simulation -------------------------------------------------------
    start = time.perf_counter()
    weeks_needed = simulate(throughput, args.backlog, args.iterations,
                            args.week_count_cap, rng)
    duration_ms = int(round((time.perf_counter() - start) * 1000))

    # --- Percentiles (invariant: p50/p85/p95, never mean) --------------------
    p50, p85, p95 = (int(round(v)) for v in
                     np.percentile(weeks_needed, [50, 85, 95], method="linear"))

    # --- Histogram (week → count) ---------------------------------
    max_week = int(weeks_needed.max())
    counts = np.bincount(weeks_needed, minlength=max_week + 1)
    histogram = [{"week": int(w), "count": int(counts[w])}
                 for w in range(1, max_week + 1) if counts[w] > 0]
    bins = [h["week"] for h in histogram]

    result = {
        "iterations": args.iterations,
        "backlog": args.backlog,
        "percentiles": {
            "duration_weeks": {"p50": p50, "p85": p85, "p95": p95}
        },
        "distribution": {
            "histogram": histogram,
            "bins": bins,
        },
        "metadata": {
            "runtime": "python-%d.%d.%d" % sys.version_info[:3],
            "numpy": np.__version__,
            "duration_ms": duration_ms,
            "seed": seed,
        },
    }

    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
