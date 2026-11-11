#!/usr/bin/env python3
"""run-pert.py — tool deterministico run_pert (EP-010, US-041, TSK-072)

Parte della capability Task Analytics & Cost/Time Estimation (EP-010, faccia
previsionale), istanza del pattern thin-agents-fat-skills-refactor: questo e' il TOOL
(logica deterministica, no LLM). Implementa il Metodo 2 — PERT three-point
estimation. Il tool NON ragiona sulla metodologia (quale metodo applicare, quale
similarity, quale contingency): quella scelta e' scope della skill `project-estimation`
(US-040) e dell'agente `estimation-analyst` (US-043). Questo tool riceve voci O/M/P
ed emette attesa + varianza + std + percentili approssimati. JSON puro su stdout.

PATTERN.md §3 — operazione canonica opzionale «Project Estimation» / «PERT».
Wiki: wiki/concepts/task-analytics-cost-estimation-capability.md
      wiki/syntheses/task-analytics-estimation-methods.md §Metodo 2 — PERT three-point.
ADR-025 §E — PERT scope ingestion: esplicito (default) + `--from-kanban` opt-in.
          §E punto 5: formula PERT verbatim attesa=(O+4M+P)/6, varianza=((P-O)/6)^2.
ADR-026 — runtime Monte Carlo separato (run-monte-carlo.py); qui solo i percentili
          approssimati da distribuzione normale (rinvio a Monte Carlo per precisione).

INVARIANTE «mai numero puntuale» (PATTERN §3, ADR-024/025): ogni stima e' un intervallo.
  Anche con una sola voce a std=0 il totale espone p50/p85/p95 (eventualmente uguali).
  Il tool NON emette MAI un campo `mean`/`average`/`media` come valore primario:
  `expected` e' l'attesa PERT (media pesata three-point), accompagnata SEMPRE da std e
  percentili — mai presentata come stima puntuale.

FORMULE VERBATIM (synthesis §Metodo 2 / ADR-025 §E punto 5):
  attesa   = (O + 4M + P) / 6
  varianza = ((P - O) / 6)^2
  std      = sqrt(varianza) = |P - O| / 6
Aggregazione progetto (somma di voci indipendenti):
  attesa_totale   = Σ attesa_i
  varianza_totale = Σ varianza_i
  std_totale      = sqrt(varianza_totale)
Percentili approssimati (distribuzione normale del totale, teorema del limite centrale):
  p50 ≈ attesa_totale
  p85 ≈ attesa_totale + 1.04  * std_totale
  p95 ≈ attesa_totale + 1.645 * std_totale

LIMITE DOCUMENTATO (concept §Limiti): il tool NON somma ore-persona come tempo di
  calendario. Se le voci sono in `unit: hours`, l'output resta in ore ed espone la
  nota "Effort, non calendar time". La conversione effort→calendario e' scope umano.

CONTRATTO INPUT (CLI)
  --voices '<JSON>'      lista JSON delle voci. Shape per voce:
                         {name, O: float, M: float, P: float, unit?: "days"|"hours"}.
                         `unit` opzionale per voce; default = --unit globale (days).
  --unit <days|hours>    unit di default per le voci senza campo `unit` (default days).
  --config <path>        default "factory.config.yaml" (ADR-023 §A contract).

CONTRATTO OUTPUT (stdout, JSON puro) — schema US-041 §Tool run_pert / TSK-072:
  {
    "voices": [{ "name", "expected", "variance", "std", "unit" }],
    "total": {
      "expected", "std", "variance",
      "p50_approx", "p85_approx", "p95_approx",
      "unit",
      "approximation_note"
    }
  }
  Se unit == hours, total.effort_note = "Effort, non calendar time".

STDERR
  log human-readable (fail-loud su errore; quiet su success).

EXIT CODES
  0  stima prodotta OR no-op (analytics.estimation.enabled assente/false, R.P3)
  >0 errore (voices mancante, O/M/P non numerici, O<=M<=P violato, unit invalida)

Dependency: solo stdlib Python (json, math, argparse, sys, re, pathlib).
"""
from __future__ import annotations

import sys
import json
import math
import re
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
# .claude/tools/analytics/ → repo root e' 3 livelli sopra
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
# z-score one-sided upper tail (identici allo .sh)
# ---------------------------------------------------------------------------
_Z85 = 1.04
_Z95 = 1.645

_APPROXIMATION_NOTE = (
    "Percentili derivati da media + std assumendo distribuzione normale "
    "(z85=1.04, z95=1.645); per stima rigorosa usare Monte Carlo su questi "
    "parametri (run-monte-carlo.py, TSK-073 / ADR-026)."
)

_EFFORT_NOTE = (
    "Effort, non calendar time. La conversione effort→calendario "
    "(capacità team, parallelismo) è scope umano, non del tool."
)

_UNIT_WARNING = (
    "Voci con unit eterogenee (days/hours): il totale aggrega quantità "
    "non omogenee. Normalizzare lo scope a una sola unit prima di sommare."
)

_VALID_UNITS = {"days", "hours"}


# ---------------------------------------------------------------------------
# Helpers aritmetici — arrotondamenti deterministici (no falsa precisione)
# ---------------------------------------------------------------------------

def _round2(x: float) -> float:
    """round2 di jq: round(x * 100) / 100"""
    return _jq_round(x * 100) / 100


def _round4(x: float) -> float:
    """round4 di jq: round(x * 10000) / 10000"""
    return _jq_round(x * 10000) / 10000


# ---------------------------------------------------------------------------
# Lettura config — estrae analytics.estimation.enabled senza PyYAML
# ---------------------------------------------------------------------------

def _read_estimation_enabled(config_path: str) -> bool:
    """Estrae analytics.estimation.enabled da factory.config.yaml via regex/parsing
    line-by-line. Nessuna dipendenza esterna. Default False se assente.

    Logica: scansiona linee cercando il blocco `analytics:` (indent 0), poi il
    sotto-blocco `estimation:`, poi la chiave `enabled:`. Valida solo `true`.
    """
    p = Path(config_path)
    if not p.is_file():
        return False

    try:
        content = p.read_text(encoding="utf-8")
    except OSError:
        return False

    in_analytics = False
    in_estimation = False
    analytics_indent: int | None = None
    estimation_indent: int | None = None

    for raw_line in content.splitlines():
        # Rimuovi commenti inline
        line = re.sub(r'\s+#.*$', '', raw_line)
        stripped = line.strip()
        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())

        if re.match(r'^analytics\s*:', stripped):
            in_analytics = True
            analytics_indent = indent
            in_estimation = False
            estimation_indent = None
            continue

        if in_analytics:
            # Uscita dal blocco analytics se troviamo una chiave allo stesso livello
            if analytics_indent is not None and indent <= analytics_indent and stripped:
                # Assicurati che non sia una riga vuota o commento
                if not stripped.startswith('#'):
                    in_analytics = False
                    in_estimation = False
                    continue

            if re.match(r'^estimation\s*:', stripped):
                in_estimation = True
                estimation_indent = indent
                continue

            if in_estimation:
                # Uscita dal blocco estimation se indent torna al livello estimation o sopra
                if estimation_indent is not None and indent <= estimation_indent and stripped:
                    if not stripped.startswith('#'):
                        in_estimation = False
                        continue

                m = re.match(r'^enabled\s*:\s*(.+)$', stripped)
                if m:
                    val = m.group(1).strip().strip('"\'')
                    return val == 'true'

    return False


# ---------------------------------------------------------------------------
# Calcolo PERT — formule verbatim ADR-025 §E punto 5
# ---------------------------------------------------------------------------

def _compute_pert_voices(voices: list[dict], default_unit: str) -> dict:
    """Calcola PERT per ogni voce e aggrega il totale.

    Formule verbatim:
      expected  = (O + 4M + P) / 6
      variance  = ((P - O) / 6)^2
      std       = sqrt(variance)
    Aggregazione:
      sum_expected = Σ expected_i  (calcolato su valori arrotondati, fedele allo .sh)
      sum_variance = Σ variance_i  (calcolato su valori arrotondati, fedele allo .sh)
      std_total    = sqrt(sum_variance)
    Percentili:
      p50 ≈ sum_expected
      p85 ≈ sum_expected + 1.04  * std_total
      p95 ≈ sum_expected + 1.645 * std_total
    """
    computed_voices: list[dict] = []

    for v in voices:
        o_val = float(v["O"])
        m_val = float(v["M"])
        p_val = float(v["P"])
        unit = v.get("unit", default_unit)

        expected = (o_val + 4.0 * m_val + p_val) / 6.0
        variance = ((p_val - o_val) / 6.0) ** 2
        std = math.sqrt(variance)

        computed_voices.append({
            "name": v.get("name", "(unnamed)"),
            "expected": _round2(expected),
            "variance": _round4(variance),
            "std": _round2(std),
            "unit": unit,
        })

    # Aggregazione sul totale: sum di valori già arrotondati (fedele al comportamento jq .sh)
    sum_expected = sum(cv["expected"] for cv in computed_voices)
    sum_variance = sum(cv["variance"] for cv in computed_voices)
    std_total = math.sqrt(sum_variance)

    # Unit del totale: coerente solo se tutte le voci condividono la stessa unit
    units_used = list({cv["unit"] for cv in computed_voices})
    total_unit = units_used[0] if len(units_used) == 1 else "mixed"

    total: dict = {
        "expected": _round2(sum_expected),
        "variance": _round4(sum_variance),
        "std": _round2(std_total),
        "p50_approx": _round2(sum_expected),
        "p85_approx": _round2(sum_expected + _Z85 * std_total),
        "p95_approx": _round2(sum_expected + _Z95 * std_total),
        "unit": total_unit,
        "approximation_note": _APPROXIMATION_NOTE,
    }

    # Limite documentato (concept §Limiti): ore-persona != calendario
    if total_unit == "hours":
        total["effort_note"] = _EFFORT_NOTE

    if total_unit == "mixed":
        total["unit_warning"] = _UNIT_WARNING

    return {"voices": computed_voices, "total": total}


# ---------------------------------------------------------------------------
# Validazione input voices
# ---------------------------------------------------------------------------

def _validate_voices(voices: list) -> None:
    """Valida la lista voci. Raise SystemExit con messaggio se invalida.

    Validazioni (fail-loud con indice voce offendente):
    1. Ogni voce ha O, M, P come numeri.
    2. O <= M <= P.
    """
    for i, v in enumerate(voices):
        # O/M/P devono essere presenti e numerici
        for field in ("O", "M", "P"):
            val = v.get(field)
            if val is None or not isinstance(val, (int, float)):
                print(
                    f"ERRORE: voce all'indice {i} ha {field} mancante o non numerico. "
                    "Ogni voce richiede O,M,P come numeri. Vedi US-041 §Tool run_pert.",
                    file=sys.stderr,
                )
                print(
                    json.dumps({"status": "error", "error": f"voice {i} has non-numeric or missing O/M/P"}),
                )
                sys.exit(1)

        o_val, m_val, p_val = float(v["O"]), float(v["M"]), float(v["P"])
        if o_val > m_val or m_val > p_val:
            detail = f"O={json.dumps(v['O'])},M={json.dumps(v['M'])},P={json.dumps(v['P'])}"  # numeri come li stampa jq
            print(
                f"ERRORE: voce all'indice {i} viola il vincolo O<=M<=P ({detail}). "
                "PERT richiede ottimistico<=probabile<=pessimistico.",
                file=sys.stderr,
            )
            print(
                json.dumps({"status": "error", "error": f"voice {i} violates O<=M<=P: {detail}"}),
            )
            sys.exit(1)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = ContractArgumentParser(
        prog="run-pert.py",
        description="PERT three-point estimation tool (EP-010, US-041, TSK-072).",
        add_help=True,
    )
    parser.add_argument(
        "--voices",
        metavar="JSON",
        default=None,
        help="lista JSON delle voci: [{\"name\":\"...\",\"O\":2,\"M\":4,\"P\":8}]",
    )
    parser.add_argument(
        "--unit",
        default="days",
        help="unit di default per le voci senza campo `unit` (default: days)",
    )
    parser.add_argument(
        "--config",
        default="factory.config.yaml",
        help="path al factory.config.yaml (default: factory.config.yaml relativo a repo root)",
    )

    args = parser.parse_args()

    # Normalizza config a path assoluto (relativo → rispetto al repo root)
    config_path = args.config
    if not Path(config_path).is_absolute():
        config_path = str(REPO_ROOT / config_path)

    # --unit gia' validato da argparse choices, ma verifica esplicita per coerenza con .sh
    if args.unit not in _VALID_UNITS:
        print(
            f"ERRORE: --unit deve essere 'days' o 'hours' (trovato: '{args.unit}').",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": f"invalid --unit: {args.unit}"}))
        sys.exit(1)

    # ---------------------------------------------------------------------------
    # Master switch — no-op se la capability e' spenta (R.P3, ADR-025 §G).
    # Assenza del file/blocco => disabilitato => exit 0 silenzioso, 0 output JSON.
    # Backward-compat totale: factory v2.17- senza il blocco estimation = no-op.
    # ---------------------------------------------------------------------------
    enabled = _read_estimation_enabled(config_path)
    if not enabled:
        print(
            "run_pert: analytics.estimation.enabled non e' true (no-op, R.P3).",
            file=sys.stderr,
        )
        sys.exit(0)

    # ---------------------------------------------------------------------------
    # Validazione input voices — fail-loud (R.P3: input mancante => fail-loud,
    # NON output fittizio). La capability e' attiva ma manca lo scope.
    # ---------------------------------------------------------------------------
    if not args.voices:
        print(
            "ERRORE: --voices mancante. run_pert richiede una lista di voci O/M/P. "
            "Vedi US-041 §Tool run_pert.",
            file=sys.stderr,
        )
        print(
            "Uso: run-pert.py --voices '<JSON>' [--unit days|hours] [--config <path>]",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": "missing --voices"}))
        sys.exit(1)

    # Parse JSON
    try:
        voices_raw = json.loads(args.voices)
    except json.JSONDecodeError as exc:
        print(
            f"ERRORE: --voices non e' JSON valido: '{args.voices}'. ({exc})",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": "invalid --voices JSON"}))
        sys.exit(1)

    # Deve essere un array non vuoto
    if not isinstance(voices_raw, list) or len(voices_raw) == 0:
        print(
            "ERRORE: --voices deve essere un array JSON non vuoto di voci {name,O,M,P}.",
            file=sys.stderr,
        )
        print(json.dumps({"status": "error", "error": "voices must be a non-empty array"}))
        sys.exit(1)

    # Validazione per-voce (O/M/P numerici + O<=M<=P)
    _validate_voices(voices_raw)

    # ---------------------------------------------------------------------------
    # Calcolo PERT — formule verbatim ADR-025 §E punto 5
    # ---------------------------------------------------------------------------
    result = _compute_pert_voices(voices_raw, args.unit)

    # ---------------------------------------------------------------------------
    # Emissione output finale — JSON puro su stdout.
    # Invariante «mai numero puntuale»: l'output espone sempre p50/p85/p95; con
    # una sola voce a std=0 i tre percentili coincidono (distribuzione collassata),
    # ma restano tre campi distinti (la skill US-040 marca confidence: very_low).
    # ---------------------------------------------------------------------------
    n_voices = len(voices_raw)
    print(
        f"run_pert: {n_voices} voci processate (unit default: {args.unit}).",
        file=sys.stderr,
    )

    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
