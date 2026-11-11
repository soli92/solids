"""build-reference-class — tool deterministico build_reference_class

(EP-010, US-041, TSK-074)

Costruisce la REFERENCE CLASS per un tipo di lavoro: filtra lo storico via
analyze-timeline.py, conta i campioni N, estrae la distribuzione di durata e
costo, e arricchisce N + similarity con la Reference Class Sufficiency Policy
(ADR-025 §A-B-C-D) per produrre `confidence` + `mode_recommended`.

PATTERN.md §3 — operazione canonica opzionale «Reference Class».
ADR-025 §A — soglie N→confidence (configurable via analytics.estimation.*).
ADR-025 §B — similarity factor: downgrade del bucket calcolato da N.
ADR-025 §C — mapping confidence → mode_recommended.
ADR-025 §D — fallback N=0: very_low + PERT-only + warning esplicito.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
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
# §3  Config helper — regex pura, no PyYAML
# ---------------------------------------------------------------------------

def _yaml_nested(config_path: str, section: str, key: str) -> str | None:
    """Legge una chiave scalare sotto analytics.<section>.<key>.

    Usa espressioni regolari senza dipendenze esterne. Restituisce None se la
    chiave non è trovata o il file non esiste.
    """
    p = Path(config_path)
    if not p.is_file():
        return None

    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_analytics = False
    analytics_indent = -1
    in_section = False
    section_indent = -1

    for raw_line in lines:
        # Rimuovi commenti inline
        stripped_comment = re.sub(r"\s+#.*$", "", raw_line)
        if not stripped_comment.strip():
            continue

        indent = len(stripped_comment) - len(stripped_comment.lstrip())
        content = stripped_comment.strip()

        if re.match(r"^analytics\s*:", content):
            in_analytics = True
            analytics_indent = indent
            in_section = False
            continue

        if in_analytics:
            if indent <= analytics_indent and not re.match(r"^analytics\s*:", content):
                in_analytics = False
                in_section = False
                continue

            if re.match(rf"^{re.escape(section)}\s*:", content):
                in_section = True
                section_indent = indent
                continue

            if in_section:
                if indent <= section_indent:
                    in_section = False
                    continue
                m = re.match(rf"^{re.escape(key)}\s*:\s*(.*)", content)
                if m:
                    value = m.group(1).strip().strip("'\"")
                    return value if value else None

    return None


# ---------------------------------------------------------------------------
# §6  Soglie sufficiency — ADR-025 §A
# ---------------------------------------------------------------------------

def _load_thresholds(config_path: str) -> tuple[int, int, int]:
    """Carica e valida le soglie rcf_*_confidence_threshold dal config.

    Applica default 1/10/30 e fail-loud su mis-configurazione.
    """
    raw_low    = _yaml_nested(config_path, "estimation", "rcf_low_confidence_threshold")
    raw_medium = _yaml_nested(config_path, "estimation", "rcf_medium_confidence_threshold")
    raw_high   = _yaml_nested(config_path, "estimation", "rcf_high_confidence_threshold")

    low    = raw_low    if raw_low    is not None else "1"
    medium = raw_medium if raw_medium is not None else "10"
    high   = raw_high   if raw_high   is not None else "30"

    if not all(re.fullmatch(r"[0-9]+", v) for v in (low, medium, high)):
        _fail(
            f"soglie rcf_*_confidence_threshold devono essere interi "
            f"(trovati: low={low} medium={medium} high={high}). Vedi ADR-025 §A.",
            "non-integer rcf thresholds",
        )

    rcf_low, rcf_medium, rcf_high = int(low), int(medium), int(high)

    if not (rcf_low >= 1 and rcf_low < rcf_medium < rcf_high):
        _fail(
            f"soglie sufficiency mis-configurate. Richiesto 1 <= rcf_low < rcf_medium < rcf_high "
            f"(trovati: low={rcf_low} medium={rcf_medium} high={rcf_high}). Vedi ADR-025 §A 'Validation'.",
            "invalid rcf threshold ordering",
        )

    return rcf_low, rcf_medium, rcf_high


# ---------------------------------------------------------------------------
# Utilitari
# ---------------------------------------------------------------------------

def _fail(message: str, error_key: str) -> None:
    print(f"ERRORE: {message}", file=sys.stderr)
    print(json.dumps({"status": "error", "error": error_key}))
    sys.exit(1)


def _round2(value: float) -> float:
    return _jq_round(value * 100) / 100


# ---------------------------------------------------------------------------
# §8  Sufficiency policy — ADR-025 §A-B-C-D
# ---------------------------------------------------------------------------

def _bucket_index(n: int, rcf_low: int, rcf_medium: int, rcf_high: int) -> int:
    if n >= rcf_high:
        return 3
    if n >= rcf_medium:
        return 2
    if n >= rcf_low:
        return 1
    return 0


def _similarity_downgrade(similarity: str) -> int:
    if similarity == "high":
        return 0
    if similarity == "medium":
        return 1
    return 2  # low


def _idx_to_confidence(i: int) -> str:
    if i >= 3:
        return "high"
    if i == 2:
        return "medium"
    if i == 1:
        return "low"
    return "very_low"


def _mode_for(confidence: str) -> str:
    if confidence == "high":
        return "rcf"
    if confidence == "medium":
        return "hybrid"
    return "pert"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # -----------------------------------------------------------------------
    # §1  Parsing argomenti CLI
    # -----------------------------------------------------------------------
    parser = ContractArgumentParser(
        description="Costruisce la reference class per un tipo di lavoro (US-041, ADR-025).",
        add_help=True,
    )
    parser.add_argument("--filter", dest="filter", default="{}", metavar="JSON")
    parser.add_argument(
        "--similarity",
        dest="similarity",
        default="medium",
    )
    parser.add_argument("--config", dest="config", default="factory.config.yaml", metavar="PATH")

    # Intercetta similarity non valido prima che argparse stampi messaggi in inglese.
    raw_args = sys.argv[1:]
    for i, arg in enumerate(raw_args):
        if arg == "--similarity" and i + 1 < len(raw_args):
            sim_val = raw_args[i + 1]
            if sim_val not in ("high", "medium", "low"):
                print(
                    f"ERRORE: --similarity '{sim_val}' non valido (ammessi: high|medium|low). "
                    "Default = medium (ADR-025 §B 'safe by default').",
                    file=sys.stderr,
                )
                print(json.dumps({"status": "error", "error": f"invalid --similarity: {sim_val}"}))
                sys.exit(1)

    args = parser.parse_args()

    filter_str: str = args.filter
    similarity: str = args.similarity
    config_raw: str = args.config

    # Normalizza config a path assoluto
    config_path_obj = Path(config_raw)
    if not config_path_obj.is_absolute():
        config_path_obj = REPO_ROOT / config_raw
    config_path = str(config_path_obj)

    # -----------------------------------------------------------------------
    # Valida --filter JSON
    # -----------------------------------------------------------------------
    try:
        filter_obj = json.loads(filter_str)
    except json.JSONDecodeError:
        _fail(f"--filter non è JSON valido: '{filter_str}'.", "invalid --filter JSON")
        return  # unreachable; aiuta mypy

    # -----------------------------------------------------------------------
    # §4  Master switch — no-op se analytics.estimation.enabled != "true"
    # -----------------------------------------------------------------------
    est_enabled = _yaml_nested(config_path, "estimation", "enabled")
    if est_enabled != "true":
        print(
            "build_reference_class: analytics.estimation.enabled non è true (no-op, R.P3).",
            file=sys.stderr,
        )
        sys.exit(0)

    # -----------------------------------------------------------------------
    # §5  Fail-loud se EP-009 (measurement) non attiva — ADR-025 §D + US-041
    # -----------------------------------------------------------------------
    meas_enabled = _yaml_nested(config_path, "measurement", "enabled")
    if meas_enabled != "true":
        print(
            "EP-009 (measurement) richiesta per build_reference_class. "
            "Attivare `analytics.measurement.enabled: true` o usare run_pert standalone.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": "EP-009 measurement not enabled"}))
        sys.exit(1)

    # -----------------------------------------------------------------------
    # §6  Soglie sufficiency
    # -----------------------------------------------------------------------
    rcf_low, rcf_medium, rcf_high = _load_thresholds(config_path)

    # -----------------------------------------------------------------------
    # §7  Invoca analyze-timeline.py via subprocess
    # -----------------------------------------------------------------------
    analyze_script = HERE / "analyze-timeline.py"

    timeline_data: dict = {"n_samples": 0, "lead": {}, "operational": {}}

    try:
        result = subprocess.run(
            [sys.executable, str(analyze_script), "--filter", filter_str, "--config", config_path],
            capture_output=True,
            text=True,
            timeout=900,
        )
        stdout = result.stdout.strip()
        if stdout:
            parsed = json.loads(stdout)
            timeline_data = parsed
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError):
        # ADR-025 §D: tratta come N=0, non errore
        pass

    # Propaga errore strutturato da analyze-timeline (fail-loud)
    if isinstance(timeline_data, dict) and timeline_data.get("status") == "error":
        print(
            "ERRORE: analyze_timeline ha riportato un errore durante il sampling della reference class:",
            file=sys.stderr,
        )
        print(timeline_data.get("error", "unknown"), file=sys.stderr)
        print(json.dumps(timeline_data))
        sys.exit(1)

    # -----------------------------------------------------------------------
    # §8  Assembla output con Sufficiency Policy
    # -----------------------------------------------------------------------
    tl = timeline_data if isinstance(timeline_data, dict) else {}
    n_samples: int = int(tl.get("n_samples", 0))
    lead: dict = tl.get("lead", {}) or {}
    op: dict = tl.get("operational", {}) or {}

    d10 = lead.get("p10")
    d50 = lead.get("p50")
    d85 = lead.get("p85")
    d95 = lead.get("p95")
    d90 = _round2((d85 + d95) / 2) if (d85 is not None and d95 is not None) else None

    period_from = op.get("period_from")
    period_to = op.get("period_to")

    bucket = _bucket_index(n_samples, rcf_low, rcf_medium, rcf_high)
    i_raw = bucket - _similarity_downgrade(similarity)
    i = max(0, i_raw)
    confidence = _idx_to_confidence(i)
    mode = _mode_for(confidence)

    output: dict = {
        "filter": filter_obj,
        "N": n_samples,
        "period_covered": {
            "from": period_from,
            "to": period_to,
        },
        "distribution": {
            "duration_days": {
                "p10": d10,
                "p50": d50,
                "p85": d85,
                "p90": d90,
                "p95": d95,
            },
            "cost_total": {
                "p10": None,
                "p50": None,
                "p85": None,
                "p90": None,
                "p95": None,
            },
            "split_human_pct_p50": op.get("split_human_pct"),
            "split_agent_pct_p50": op.get("split_agent_pct"),
        },
        "similarity": similarity,
        "confidence": confidence,
        "mode_recommended": mode,
        "thresholds": {
            "rcf_low": rcf_low,
            "rcf_medium": rcf_medium,
            "rcf_high": rcf_high,
        },
    }

    # ADR-025 §D — fallback N=0
    if n_samples == 0:
        output["warnings"] = [
            "Nessun dato storico disponibile (N=0): reference class vuota. "
            "Stima possibile solo PERT-only basata su elicitation. "
            "Bias di ottimismo non mitigato (Kahneman/Flyvbjerg). "
            "Calibrare contingency al rialzo (raccomandato >=30%). Vedi ADR-025 §D."
        ]

    # -----------------------------------------------------------------------
    # §9  Emissione output
    # -----------------------------------------------------------------------
    if n_samples == 0:
        print(
            "WARNING build_reference_class: reference class vuota (N=0) per il filtro dato. "
            "confidence=very_low, mode_recommended=pert (PERT-only). Vedi ADR-025 §D.",
            file=sys.stderr,
        )

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
