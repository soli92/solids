#!/usr/bin/env python3
"""estimate-project.py — orchestratore composito estimate_project
                         (EP-010, US-041, TSK-075)

Parte della capability Task Analytics & Cost/Time Estimation — faccia
PREVISIONALE (EP-010), istanza del pattern thin-agents-fat-skills-refactor:
questo e' il TOOL (orchestrazione deterministica di calcolo numerico, no
ragionamento LLM). E' l'ORCHESTRATORE COMPOSITO della suite di stima: per
ogni voce dello scope costruisce la REFERENCE CLASS (build-reference-class.py,
TSK-074), poi esegue i metodi applicabili — RCF (outside view), PERT
three-point (run-pert.py, TSK-072), Monte Carlo throughput (run-monte-carlo.py,
TSK-073) — e combina i risultati col MASSIMO CONSERVATIVO (regola difensiva
anti-bias di ottimismo, ADR-025 §C). Emette il sub-blocco `estimate` con i 6
campi obbligatori (ADR-024 §E) e persiste in analytics/reports/estimates/
(ADR-027).

PATTERN.md §3 — operazione canonica opzionale «Project Estimation».
ADR-024 §E — sub-schema `estimate` (6 campi obbligatori).
ADR-025 §C — mapping confidence → metodo primario + contingency raccomandata.
ADR-025 §D — fallback N=0/very_low: PERT forzato + contingency >=30.
ADR-027 §A/§B — storage stime in analytics/reports/estimates/.

CONTRATTO INPUT (CLI)
  --scope '<JSON>'           lista JSON delle voci {name, O, M, P, ...}. Required.
  --force-method <m>         rcf | pert | monte-carlo | hybrid. Opzionale.
  --contingency-pct <n>      contingency base (>=0). Opzionale.
  --similarity <lvl>         high | medium | low (default medium).
  --unit <days|hours>        unit di default (default days).
  --throughput-samples '<JSON>'  distribuzione storica throughput (task/sett).
  --backlog <int>            numero task per Monte Carlo (default = len(scope)).
  --seed <int>               seed Monte Carlo.
  --slug <slug>              override slug di storage (kebab-case).
  --no-store                 non scrivere su disco.
  --config <path>            default factory.config.yaml.

CONTRATTO OUTPUT
  stdout : JSON puro del sub-blocco `estimate` (ADR-024 §E) + warnings[].
  file   : analytics/reports/estimates/<YYYY-MM-DD>-<slug>.{json,md}.
  stderr : log human-readable.

EXIT CODES
  0  stima prodotta OR no-op (analytics.estimation.enabled assente/false)
  >0 errore
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # tools/analytics/ → root factory (2 livelli)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytics_cli import ContractArgumentParser, jq_numbers  # noqa: E402 — contratto CLI comune (US-327)


def _jq_round(x: float) -> float:
    """`round` di jq (C round: la meta' va lontano da zero), non l'arrotondamento bancario di Python.

    Parita' con gli .sh: `round(0.125 * 100)` vale 13 in jq e 12 in Python.
    """
    import math as _m
    return float(_m.copysign(_m.floor(abs(x) + 0.5), x))


# ---------------------------------------------------------------------------
# §3 Helper YAML — regex pura, no PyYAML.
# ---------------------------------------------------------------------------

def _yaml_nested(config_path: str, section: str, key: str) -> str:
    """Estrae analytics.<section>.<key> da un file YAML via regex pura.

    Cerca il blocco analytics: -> <section>: -> <key>: e ritorna il valore
    stringa scalare (senza virgolette). Ritorna stringa vuota se assente.
    """
    p = Path(config_path)
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_analytics = False
    in_section = False
    analytics_indent = -1
    section_indent = -1

    for raw in lines:
        stripped = raw.rstrip()
        # Rimuovi commenti inline
        no_comment = re.sub(r'\s+#.*$', '', stripped)
        if not no_comment.strip():
            continue
        indent = len(no_comment) - len(no_comment.lstrip())
        content = no_comment.strip()

        if re.match(r'^analytics\s*:', content):
            in_analytics = True
            analytics_indent = indent
            in_section = False
            continue

        if in_analytics:
            if indent <= analytics_indent and not re.match(r'^analytics\s*:', content):
                in_analytics = False
                in_section = False
                continue
            if re.match(rf'^{re.escape(section)}\s*:', content):
                in_section = True
                section_indent = indent
                continue

        if in_section:
            if indent <= section_indent:
                in_section = False
                continue
            m = re.match(rf'^{re.escape(key)}\s*:\s*(.*)', content)
            if m:
                val = m.group(1).strip().strip('"').strip("'")
                return val
    return ""


# ---------------------------------------------------------------------------
# §0 Helpers generici
# ---------------------------------------------------------------------------

def _kebab(s: str) -> str:
    """Converte stringa in kebab-case."""
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s or "estimate"


CONF_RANK: dict[str, int] = {
    "very_low": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


def _rank(conf: str) -> int:
    return CONF_RANK.get(conf, 0)


def _err(msg: str, payload: dict | None = None) -> None:
    print(msg, file=sys.stderr)
    if payload:
        print(json.dumps(payload), flush=True)


def _round2(v: float | None) -> float | None:
    if v is None:
        return None
    return _jq_round(v * 100) / 100


def _max_not_none(*args: float | None) -> float | None:
    vals = [v for v in args if v is not None]
    return max(vals) if vals else None


# ---------------------------------------------------------------------------
# §1 Parsing CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = ContractArgumentParser(
        description="estimate-project — orchestratore composito stima progetto",
        add_help=True,
    )
    p.add_argument("--scope", required=False, default=None,
                   help="Array JSON delle voci {name, O, M, P, ...}. Required.")
    p.add_argument("--force-method", dest="force_method", default=None,
                   help="Override del mode aggregato (ADR-025 §E).")
    p.add_argument("--contingency-pct", dest="contingency_pct", default=None,
                   help="Contingency base (>=0).")
    p.add_argument("--similarity", default="medium",
                   help="Livello similarity per reference class (default medium).")
    p.add_argument("--unit", default="days",
                   help="Unit di default (default days).")
    p.add_argument("--throughput-samples", dest="throughput_samples", default=None,
                   help="Array JSON distribuzione storica throughput (task/sett).")
    p.add_argument("--backlog", default=None, type=int,
                   help="Numero task per Monte Carlo (default = len(scope)).")
    p.add_argument("--seed", default=None, type=int,
                   help="Seed Monte Carlo.")
    p.add_argument("--slug", default=None,
                   help="Override slug di storage (kebab-case).")
    p.add_argument("--no-store", dest="no_store", action="store_true",
                   help="Non scrivere su disco.")
    p.add_argument("--config", default="factory.config.yaml",
                   help="Percorso factory.config.yaml (default factory.config.yaml).")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:  # noqa: C901 — complessità ciclomatica accettabile per orchestratore
    args = _parse_args()

    # Normalizza CONFIG a path assoluto
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = str(REPO_ROOT / config_path)

    # Validazione argomenti prima del gate, nello stesso ordine dello .sh (US-327).
    if args.unit not in ("days", "hours"):
        _err(f"ERRORE: --unit deve essere 'days' o 'hours' (trovato: '{args.unit}').",
             {"status": "error", "error": f"invalid --unit: {args.unit}"})
        return 1
    if args.similarity not in ("high", "medium", "low"):
        _err(f"ERRORE: --similarity '{args.similarity}' non valido (ammessi: high|medium|low).",
             {"status": "error", "error": f"invalid --similarity: {args.similarity}"})
        return 1
    if args.force_method and args.force_method not in ("rcf", "pert", "monte-carlo", "hybrid"):
        _err(f"ERRORE: --force-method '{args.force_method}' non valido "
             "(ammessi: rcf|pert|monte-carlo|hybrid).",
             {"status": "error", "error": f"invalid --force-method: {args.force_method}"})
        return 1
    if args.contingency_pct not in (None, ""):
        if not re.fullmatch(r"[0-9]+(\.[0-9]+)?", str(args.contingency_pct)):
            _err(f"ERRORE: --contingency-pct deve essere un numero >=0 (trovato: '{args.contingency_pct}').",
                 {"status": "error", "error": f"invalid --contingency-pct: {args.contingency_pct}"})
            return 1
        args.contingency_pct = float(args.contingency_pct)
    else:
        args.contingency_pct = None

    # ---------------------------------------------------------------------------
    # §4 Master switch EP-010 — no-op se la capability previsionale e' spenta.
    # ---------------------------------------------------------------------------
    enabled = _yaml_nested(config_path, "estimation", "enabled")
    if enabled != "true":
        print("estimate_project: analytics.estimation.enabled non e' true (no-op, R.P3).",
              file=sys.stderr)
        return 0

    # default_contingency_pct base (ADR-025 §A), fallback 15.
    raw_default_cont = _yaml_nested(config_path, "estimation", "default_contingency_pct")
    try:
        default_contingency: float = float(raw_default_cont) if raw_default_cont else 15.0
    except ValueError:
        default_contingency = 15.0

    # Valida --contingency-pct
    if args.contingency_pct is not None and args.contingency_pct < 0:
        _err("ERRORE: --contingency-pct deve essere >=0.",
             {"status": "error", "error": "invalid --contingency-pct: must be >= 0"})
        return 1

    # ---------------------------------------------------------------------------
    # §5 Validazione scope — fail-loud (R.P3).
    # ---------------------------------------------------------------------------
    if args.scope is None:
        _err(
            "ERRORE: --scope mancante. estimate_project richiede una lista di voci "
            "{name,task_type,O,M,P}. Vedi US-041 §Tool estimate_project / ADR-025 §E.",
            {"status": "error", "error": "missing --scope"},
        )
        return 1

    try:
        scope: list = json.loads(args.scope)
    except json.JSONDecodeError as exc:
        _err(f"ERRORE: --scope non e' JSON valido: {exc}",
             {"status": "error", "error": "scope is not valid JSON"})
        return 1

    if not isinstance(scope, list) or len(scope) == 0:
        _err("ERRORE: --scope deve essere un array JSON non vuoto di voci.",
             {"status": "error", "error": "scope must be a non-empty array"})
        return 1

    for i, voice in enumerate(scope):
        o_val = voice.get("O")
        m_val = voice.get("M")
        p_val = voice.get("P")
        if not (isinstance(o_val, (int, float)) and
                isinstance(m_val, (int, float)) and
                isinstance(p_val, (int, float))):
            _err(
                f"ERRORE: voce #{i} manca di O/M/P numerici. "
                "Ogni voce dello scope deve avere O/M/P numerici per il dispatch PERT.",
                {"status": "error", "error": "scope voices must carry numeric O/M/P"},
            )
            return 1

    n_voices = len(scope)

    # ---------------------------------------------------------------------------
    # §6 Loop voci scope → invoca build-reference-class.py via subprocess.
    # ---------------------------------------------------------------------------
    rcf_items: list[dict] = []
    worst_conf = "high"
    worst_conf_rank = 3
    total_n = 0
    ep009_missing = False
    similarity = args.similarity

    build_rcf_script = HERE / "build-reference-class.py"
    # Fallback: se esiste solo la versione .sh, il loop usa fallback direttamente
    build_rcf_available = build_rcf_script.exists()

    for voice in scope:
        task_type = voice.get("task_type", "")
        layer = voice.get("layer", "")

        rcf_filter: dict = {}
        if task_type:
            rcf_filter["task_type"] = task_type
        if layer:
            rcf_filter["layer"] = layer

        rcf_out: dict | None = None
        if build_rcf_available:
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(build_rcf_script),
                        "--filter", json.dumps(rcf_filter),
                        "--similarity", similarity,
                        "--config", config_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
                if result.returncode == 0 and result.stdout.strip():
                    candidate = json.loads(result.stdout)
                    if "N" in candidate:
                        rcf_out = candidate
            except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
                rcf_out = None

        if rcf_out is None:
            # EP-009 assente o errore reference class → fallback N=0 (ADR-025 §D)
            ep009_missing = True
            rcf_out = {
                "filter": rcf_filter,
                "N": 0,
                "confidence": "very_low",
                "mode_recommended": "pert",
                "similarity": "n/a",
                "distribution": {
                    "duration_days": {
                        "p10": None, "p50": None, "p85": None,
                        "p90": None, "p95": None,
                    }
                },
                "reference_class_unavailable": True,
            }

        v_n: int = rcf_out.get("N", 0)
        v_conf: str = rcf_out.get("confidence", "very_low")
        total_n += v_n

        v_rank = _rank(v_conf)
        if v_rank < worst_conf_rank:
            worst_conf_rank = v_rank
            worst_conf = v_conf

        rcf_items.append(rcf_out)

    # Mode aggregato worst-case (ADR-025 §C)
    agg_mode_map = {
        "high": "rcf",
        "medium": "hybrid",
        "low": "pert",
        "very_low": "pert",
    }
    agg_mode = agg_mode_map.get(worst_conf, "pert")

    # ---------------------------------------------------------------------------
    # §7 Mode finale: --force-method se dato, altrimenti AGG_MODE.
    # ---------------------------------------------------------------------------
    if args.force_method:
        final_mode = args.force_method
        mode_source = "force-method"
    else:
        final_mode = agg_mode
        mode_source = "aggregato worst-case"

    # ---------------------------------------------------------------------------
    # §8 Enforce very_low (ADR-025 §C/§D).
    # ---------------------------------------------------------------------------
    very_low_enforced = False
    if worst_conf == "very_low" and final_mode != "pert":
        final_mode = "pert"
        very_low_enforced = True

    # Flag metodi applicabili
    run_rcf = final_mode in ("rcf", "hybrid")
    run_pert = final_mode in ("pert", "hybrid", "monte-carlo")
    run_mc = final_mode == "monte-carlo"

    # RCF applicabile solo se N>0
    if run_rcf and total_n == 0:
        run_rcf = False

    # PERT e' il fallback garantito
    if not run_rcf and not run_pert and not run_mc:
        run_pert = True

    # ---------------------------------------------------------------------------
    # §9 PERT (run-pert.py) — fail-loud se non produce .total.
    # ---------------------------------------------------------------------------
    pert_json: dict | None = None
    run_pert_script = HERE / "run-pert.py"

    if run_pert:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(run_pert_script),
                    "--voices", json.dumps(scope),
                    "--unit", args.unit,
                    "--config", config_path,
                ],
                capture_output=True,
                text=True,
                timeout=900,
            )
            if result.returncode != 0 or not result.stdout.strip():
                raise RuntimeError(
                    f"run-pert.py exit {result.returncode}: {result.stderr.strip()}"
                )
            candidate = json.loads(result.stdout)
            if "total" not in candidate:
                raise RuntimeError("run-pert.py non ha prodotto .total nel JSON.")
            pert_json = candidate
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError, RuntimeError) as exc:
            _err(
                f"ERRORE: run-pert.py non ha prodotto un output valido: {exc}. "
                "estimate_project non può procedere senza il metodo numerico base.",
                {"status": "error", "error": "run-pert failed"},
            )
            return 1

    # ---------------------------------------------------------------------------
    # §10 RCF aggregato — somma percentili durata dai distribution delle voci.
    # ---------------------------------------------------------------------------
    rcf_duration: dict | None = None
    if run_rcf and rcf_items:
        p50_sum = 0.0
        p85_sum = 0.0
        p95_sum = 0.0
        all_zero = True
        for item in rcf_items:
            dd = item.get("distribution", {}).get("duration_days", {})
            p50_sum += dd.get("p50") or 0.0
            p85_sum += dd.get("p85") or 0.0
            p95_val = dd.get("p95") or dd.get("p85") or 0.0
            p95_sum += p95_val
        if p50_sum != 0 or p85_sum != 0 or p95_sum != 0:
            all_zero = False
        if not all_zero:
            rcf_duration = {
                "p50": _round2(p50_sum),
                "p85": _round2(p85_sum),
                "p95": _round2(p95_sum),
            }

    # ---------------------------------------------------------------------------
    # §11 Monte Carlo (run-monte-carlo.py) — fail-soft.
    # ---------------------------------------------------------------------------
    mc_json: dict | None = None
    mc_skip_reason = ""
    throughput_samples = args.throughput_samples
    backlog = args.backlog if args.backlog is not None else n_voices

    # Messaggi identici allo .sh: finiscono in warnings[] dello stdout (US-327).
    _SHORT = "throughput storico < 8 settimane (US-041: Monte Carlo richiede >= 8 campioni)"
    if run_mc or throughput_samples:
        try:
            ts_list = json.loads(throughput_samples) if throughput_samples else None
        except json.JSONDecodeError:
            ts_list = None
        run_mc_script = HERE / "run-monte-carlo.py"
        if not throughput_samples:
            mc_skip_reason = "throughput-samples assente"
        elif not isinstance(ts_list, list) or len(ts_list) < 8:
            mc_skip_reason = _SHORT
        elif not run_mc_script.exists():
            mc_skip_reason = ("run-monte-carlo.py o python3 non disponibili "
                              "(Monte Carlo opzionale, fail-soft)")
        else:
            mc_args = [
                sys.executable, str(run_mc_script),
                "--throughput-samples", throughput_samples,
                "--backlog", str(backlog),
                "--config", config_path,
            ]
            if args.seed is not None:
                mc_args += ["--seed", str(args.seed)]
            rc = None
            try:
                mc_result = subprocess.run(mc_args, capture_output=True, text=True, timeout=900)
                rc = mc_result.returncode
                mc_candidate = json.loads(mc_result.stdout) if mc_result.stdout.strip() else None
                if (rc == 0 and isinstance(mc_candidate, dict)
                        and isinstance(mc_candidate.get("percentiles"), dict)
                        and mc_candidate["percentiles"].get("duration_weeks") not in (None, False)):
                    mc_json = mc_candidate
            except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
                pass
            if mc_json is None:
                mc_skip_reason = (
                    f"run-monte-carlo.py non ha prodotto output valido (rc={rc}; numpy mancante "
                    "o no-op) — Monte Carlo opzionale, fail-soft"
                )

    # ---------------------------------------------------------------------------
    # §12 Combinazione — massimo conservativo (ADR-025 §C).
    # ---------------------------------------------------------------------------
    pert_total = pert_json.get("total") if pert_json else None
    pert_p50: float | None = pert_total.get("p50_approx") if pert_total else None
    pert_p85: float | None = pert_total.get("p85_approx") if pert_total else None
    pert_p95: float | None = pert_total.get("p95_approx") if pert_total else None

    rcf_p50: float | None = rcf_duration.get("p50") if rcf_duration else None
    rcf_p85: float | None = rcf_duration.get("p85") if rcf_duration else None
    rcf_p95: float | None = rcf_duration.get("p95") if rcf_duration else None

    f50 = _round2(_max_not_none(pert_p50, rcf_p50))
    f85 = _round2(_max_not_none(pert_p85, rcf_p85))
    f95 = _round2(_max_not_none(pert_p95, rcf_p95))

    # Invariante monotonicita' (ADR-024 §E)
    if f50 is not None and f85 is not None:
        f85 = max(f85, f50)
    if f85 is not None and f95 is not None:
        f95 = max(f95, f85)

    collapsed = (f50 is not None and f50 == f85 == f95)

    if f50 is None:
        _err(
            "ERRORE: nessun metodo applicabile ha prodotto un intervallo di durata. "
            "estimate_project non può emettere una stima vuota.",
            {"status": "error", "error": "no applicable method produced an interval"},
        )
        return 1

    # MC duration weeks (informativo, unit non omogenea)
    mc_duration_weeks: dict | None = None
    if mc_json and isinstance(mc_json.get("percentiles"), dict):
        mc_duration_weeks = mc_json["percentiles"].get("duration_weeks")

    # ---------------------------------------------------------------------------
    # §13 Confidence finale + contingency (ADR-024 §E + ADR-025 §C/§D).
    # ---------------------------------------------------------------------------
    final_conf = worst_conf
    if collapsed and final_conf != "very_low":
        final_conf = "very_low"

    bucket_map = {
        "high": 15.0,
        "medium": 20.0,
        "low": 30.0,
        "very_low": 35.0,
    }
    bucket_contingency = bucket_map.get(final_conf, default_contingency)

    if args.contingency_pct is not None:
        eff_contingency = args.contingency_pct
    else:
        eff_contingency = bucket_contingency

    contingency_raised = False
    if final_conf == "very_low":
        final_mode = "pert"
        very_low_enforced = True
        if eff_contingency < 30.0:
            eff_contingency = 30.0
            contingency_raised = True

    # ---------------------------------------------------------------------------
    # §14 methods_used + etichetta method
    # ---------------------------------------------------------------------------
    methods_used: list[str] = []
    if run_pert and pert_json is not None:
        methods_used.append("PERT")
    if run_rcf and rcf_duration is not None:
        methods_used.append("RCF")
    if mc_json is not None:
        methods_used.append(
            "Monte Carlo (durata in settimane, metodo informativo separato)"
        )

    num_methods = len(methods_used)
    if final_conf == "very_low":
        eff_method_label = "PERT"
    elif num_methods > 1:
        eff_method_label = "combined"
    elif run_rcf and rcf_duration is not None and not run_pert:
        eff_method_label = "RCF"
    elif mc_json is not None and num_methods == 1:
        eff_method_label = "monte-carlo"
    else:
        eff_method_label = "PERT"

    # ---------------------------------------------------------------------------
    # §15 Assembla estimate dict — 6 campi obbligatori ADR-024 §E.
    # ---------------------------------------------------------------------------
    unit = args.unit

    # ---- OBBLIGATORIO #4: assumptions[] (non-vuota, fail-loud se vuota) ----
    assumptions: list[str] = [
        (
            "Combinazione P50/P85/P95 = massimo conservativo tra i metodi applicabili ("
            + ", ".join(methods_used or ["PERT"])
            + "); mai una media (regola anti-bias di ottimismo, ADR-025 §C)."
        ),
        f"Mode primario: {final_mode} (sorgente: {mode_source}).",
        (
            f"Reference class aggregata: N={total_n} campioni, "
            f"similarity={similarity}, confidence={final_conf}."
        ),
        (
            f"Durata in unit {unit} (PERT/RCF sommano voci indipendenti; "
            "ore-persona != tempo calendario — vedi run-pert §Limiti)."
        ),
        (
            "Costo (intervals.cost) non calcolato dal tool: richiede pricing per voce; "
            "la skill/agente lo deriva (ADR-024 §B). intervals.duration è il payload "
            "numerico reale."
        ),
    ]
    if collapsed:
        assumptions.append(
            "Distribuzione collassata (p50=p85=p95): applicare contingency manuale al "
            "rialzo; confidence forzata very_low (invariante mai numero puntuale, "
            "ADR-024 §E)."
        )
    if very_low_enforced:
        assumptions.append(
            "Confidence very_low → method forzato a PERT (ADR-025 §C/§D enforce)."
        )
    if contingency_raised:
        assumptions.append(
            "contingency_pct auto-alzata a 30 "
            "(very_low richiede >=30, ADR-025 §D)."
        )
    if ep009_missing:
        assumptions.append(
            "EP-009 (measurement) non disponibile: reference class vuota (N=0) "
            "→ fallback PERT-only (ADR-025 §D)."
        )
    if mc_json is not None:
        assumptions.append(
            "Monte Carlo throughput eseguito: durata in settimane riportata come "
            "metodo informativo separato (unit non omogenea con la durata principale)."
        )
    elif mc_skip_reason:
        assumptions.append(f"Monte Carlo non eseguito: {mc_skip_reason}.")

    # Validation fail-loud (ADR-024 §E)
    if len(assumptions) < 1:
        _err(
            "ERRORE: assumptions[] vuoto. ADR-024 §E richiede len>=1.",
            {"status": "error", "error": "assumptions must be non-empty (ADR-024 E)"},
        )
        return 1

    # ---- OBBLIGATORIO #6: sensitivity_drivers[] (non-vuota, fail-loud se vuota) ----
    sensitivity_drivers: list[dict] = [
        {"variable": "scope_count",       "impact_on_p85_pct": 25.0, "direction": "direct"},
        {"variable": "reference_class_N", "impact_on_p85_pct": 30.0, "direction": "inverse"},
    ]
    if final_conf == "very_low":
        sensitivity_drivers.extend([
            {"variable": "scope_completeness", "impact_on_p85_pct": 50.0, "direction": "inverse"},
            {"variable": "team_familiarity",   "impact_on_p85_pct": 40.0, "direction": "inverse"},
        ])

    if len(sensitivity_drivers) < 1:
        _err(
            "ERRORE: sensitivity_drivers[] vuoto. ADR-024 §E richiede len>=1.",
            {"status": "error",
             "error": "sensitivity_drivers must be non-empty (ADR-024 E)"},
        )
        return 1

    # ---- OBBLIGATORIO #2: intervals ----
    duration_block: dict = {
        "unit": unit,
        "per_method": {
            "pert": {
                "p50": pert_p50,
                "p85": pert_p85,
                "p95": pert_p95,
            },
            "rcf": {
                "p50": rcf_p50,
                "p85": rcf_p85,
                "p95": rcf_p95,
            },
        },
        "mc_duration_weeks": mc_duration_weeks,
    }
    if unit == "days":
        duration_block.update({
            "p50_days": f50,
            "p85_days": f85,
            "p95_days": f95,
        })
    else:
        duration_block.update({
            "p50_hours": f50,
            "p85_hours": f85,
            "p95_hours": f95,
            "effort_note": "Effort in ore, non calendar time.",
        })

    intervals: dict = {
        "cost": {
            "p50": None,
            "p85": None,
            "p95": None,
            "currency": None,
            "note": (
                "Costo non calcolato dal tool numerico (manca pricing per voce). "
                "Derivato dalla skill/agente, ADR-024 §B."
            ),
        },
        "duration": duration_block,
    }

    # ---- OBBLIGATORIO #3: split umano/agentico (placeholder conservativo) ----
    split_human_agentic: dict = {
        "human_pct": 100.0,
        "agentic_pct": 0.0,
        "human_cost_p50": None,
        "agentic_cost_p50": None,
        "note": (
            "Split costo derivato dalla skill/agente (pricing + reference class). "
            "Default conservativo human-only finché non arricchito."
        ),
    }

    # ---- OBBLIGATORIO #7 (effetto): qualita' reference class ----
    reference_class_quality: dict = {
        "N": total_n,
        "similarity": similarity,
        "confidence": final_conf,
    }
    if total_n == 0:
        reference_class_quality["mode"] = "PERT-only"

    estimate: dict = {
        "method": eff_method_label,
        "intervals": intervals,
        "split_human_agentic": split_human_agentic,
        "assumptions": assumptions,
        "contingency_pct": eff_contingency,
        "contingency_note": (
            "Buffer di rischio dichiarato separatamente, "
            "NON incluso nel P50 (ADR-024 §G)."
        ),
        "sensitivity_drivers": sensitivity_drivers,
        "reference_class_quality": reference_class_quality,
    }

    # warnings[] (ADR-025 §D)
    warnings: list[str] = []
    if final_conf == "very_low":
        warnings.append(
            "Confidence very_low: stima fragile. method=PERT forzato, contingency "
            ">=30 enforced. Bias di ottimismo non mitigato (Kahneman/Flyvbjerg). "
            "Vedi ADR-025 §C/§D."
        )
    if ep009_missing:
        warnings.append(
            "Nessun dato storico disponibile (EP-009 measurement assente o reference "
            "class vuota): stima PERT-only basata su elicitation. Calibrare "
            "contingency al rialzo."
        )
    if collapsed:
        warnings.append(
            "Distribuzione collassata: p50=p85=p95. "
            "Applicare contingency manuale al rialzo."
        )

    final_output: dict = {
        "estimate": estimate,
        "warnings": warnings,
    }

    # ---------------------------------------------------------------------------
    # §16 Persistenza (salvo --no-store).
    # ---------------------------------------------------------------------------
    if not args.no_store:
        if args.slug:
            slug = _kebab(args.slug)
        else:
            first_name = scope[0].get("name", "") if scope else ""
            slug = _kebab(first_name) if first_name else "estimate"

        date_stamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        est_dir = REPO_ROOT / "analytics" / "reports" / "estimates"
        os.makedirs(est_dir, exist_ok=True)

        out_json = est_dir / f"{date_stamp}-{slug}.json"
        out_md = est_dir / f"{date_stamp}-{slug}.md"

        out_json.write_text(
            json.dumps(final_output, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # MD human-readable (ADR-027 §A)
        md_lines: list[str] = [
            f"# Stima — {slug} ({date_stamp})",
            "",
            "> Sub-blocco `estimate` ADR-024 §E. estimate_id assegnato dalla skill/agente (ADR-027 §B).",
            "> Generato da estimate-project.py (EP-010, US-041, TSK-075). Immutabile (ADR-027 §A).",
            "",
            f"- **Metodo**: {eff_method_label} (mode finale: {final_mode}, sorgente: {mode_source})",
            f"- **Confidence**: {final_conf} (reference class N={total_n}, similarity={similarity})",
            (
                f"- **Durata** (unit={unit}): "
                f"p50={jq_numbers(f50)} · p85={jq_numbers(f85)} · p95={jq_numbers(f95)} "
                "— massimo conservativo tra metodi"
            ),
            f"- **Contingency**: {jq_numbers(eff_contingency)}% (separata dal P50, ADR-024 §G)",
            "- **Costo**: non calcolato dal tool numerico (derivato dalla skill/agente, ADR-024 §B)",
            "",
            "## Assumptions",
        ]
        for a in assumptions:
            md_lines.append(f"- {a}")
        md_lines.append("")
        md_lines.append("## Sensitivity drivers")
        for sd in sensitivity_drivers:
            md_lines.append(
                f"- {sd['variable']}: impact_on_p85={sd['impact_on_p85_pct']}% "
                f"({sd['direction']})"
            )
        if warnings:
            md_lines.append("")
            md_lines.append("## Warnings")
            for w in warnings:
                md_lines.append(f"- {w}")
        md_lines.append("")

        out_md.write_text("\n".join(md_lines), encoding="utf-8")

        rel_json = out_json.relative_to(REPO_ROOT)
        rel_md = out_md.relative_to(REPO_ROOT)
        print(
            f"estimate_project: stima scritta in {rel_json} + {rel_md} "
            "(estimate_id da assegnare, ADR-027 §B).",
            file=sys.stderr,
        )

    # ---------------------------------------------------------------------------
    # §17 Output finale JSON su stdout.
    # ---------------------------------------------------------------------------
    print(
        f"estimate_project: {n_voices} voci, mode={final_mode}, "
        f"confidence={final_conf}, contingency={eff_contingency}%.",
        file=sys.stderr,
    )
    print(json.dumps(final_output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
