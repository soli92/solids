"""Test degli strumenti di analytics Python da soli (US-327, TSK-743): girano anche senza bash.

Coprono il contratto «stdout JSON / stderr log / exit code», il gate R.P3, i prezzi solo da
analytics/pricing.yaml, il fail-loud sul modello ignoto, il determinismo retrospettivo
(``--pricing-as-of``), la scrittura single-writer e idempotente di record-event e i rimandi
``.sh`` / shim. I valori attesi sono quelli misurati sull'implementazione bash
(test_analytics_parity.py), qui fissati come costanti.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_analytics_parity import (  # noqa: E402 — dati di fixture condivisi
    CONFIG_ON, EVENT_OK, PRICING, RATES, SCOPE, SCRIPTS, UNKNOWN_MODEL_EVENT, VOICES,
    _events, _write_events,
)

ROOT = Path(__file__).resolve().parents[2]
ANALYTICS = ROOT / "tools" / "analytics"


def _factory(base: Path, *, measurement=True, estimation=True, events=True, extra=None) -> Path:
    (base / "analytics").mkdir(parents=True)
    (base / "factory.config.yaml").write_text(
        CONFIG_ON.format(measurement=str(measurement).lower(), estimation=str(estimation).lower()),
        encoding="utf-8")
    (base / "analytics" / "pricing.yaml").write_text(PRICING, encoding="utf-8")
    (base / "analytics" / "rates.yaml").write_text(RATES, encoding="utf-8")
    if events:
        _write_events(base, _events() + list(extra or []))
    dst = base / "tools" / "analytics"
    dst.mkdir(parents=True)
    for name in SCRIPTS:
        shutil.copy2(ANALYTICS / f"{name}.py", dst / f"{name}.py")
    for extra_file in ("analytics_cli.py", "run-monte-carlo.py"):
        shutil.copy2(ANALYTICS / extra_file, dst / extra_file)
    shutil.copytree(ROOT / "tools" / "temporal", base / "tools" / "temporal",
                    ignore=shutil.ignore_patterns("__pycache__"))
    return base


def _run(root: Path, name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "tools" / "analytics" / f"{name}.py"), *args],
                          cwd=root, capture_output=True, text=True, timeout=300)


def _json(cp: subprocess.CompletedProcess):
    return json.loads(cp.stdout)


# --------------------------------------------------------------------------- contratto CLI

@pytest.mark.parametrize("name", SCRIPTS)
def test_help_exit_zero(name):
    cp = subprocess.run([sys.executable, str(ANALYTICS / f"{name}.py"), "--help"],
                        capture_output=True, text=True, timeout=60)
    assert cp.returncode == 0, cp.stderr
    assert "usage" in cp.stdout.lower()


@pytest.mark.parametrize("name", SCRIPTS)
def test_unknown_argument_is_json_exit_1(tmp_path, name):
    root = _factory(tmp_path)
    cp = _run(root, name, "--nope")
    assert cp.returncode == 1
    assert _json(cp) == {"status": "error", "error": "unknown argument: --nope"}
    assert cp.stderr.strip(), "il motivo va su stderr"


@pytest.mark.parametrize("name,args,flag", [
    ("compute-agentic-cost", [], "measurement"),
    ("compute-human-cost", [], "measurement"),
    ("analyze-timeline", [], "measurement"),
    ("generate-report", ["--audience", "operativa"], "measurement"),
    ("record-event", ["--event", EVENT_OK], "measurement"),
    ("build-reference-class", [], "estimation"),
    ("run-pert", ["--voices", VOICES], "estimation"),
    ("estimate-project", ["--scope", SCOPE, "--no-store"], "estimation"),
])
def test_gate_off_is_silent_noop(tmp_path, name, args, flag):
    root = _factory(tmp_path, **{flag: False})
    before = sorted(p.relative_to(root) for p in root.rglob("*") if "analytics" in p.parts)
    cp = _run(root, name, *args)
    assert cp.returncode == 0
    assert cp.stdout.strip() == ""
    assert "R.P3" in cp.stderr
    after = sorted(p.relative_to(root) for p in root.rglob("*") if "analytics" in p.parts
                   and "__pycache__" not in p.parts)
    assert [p for p in after if p not in before] == [], "a gate spento nessun file scritto"


# --------------------------------------------------------------------------- costi

def test_agentic_cost_values_match_bash_reference(tmp_path):
    out = _json(_run(_factory(tmp_path), "compute-agentic-cost"))
    assert out["cost"] == pytest.approx(1.36185)
    assert out["breakdown"]["per_model"] == pytest.approx(
        {"claude-opus-4-7": 1.204125, "claude-sonnet-4-6": 0.157725})
    assert out["events_considered"] == 17
    assert out["currency"] == "EUR"
    assert out["breakdown"]["per_tool"] == {"Bash": 0}  # tool senza prezzo: 0, ma elencato


def test_prices_only_from_pricing_table(tmp_path):
    root = _factory(tmp_path)
    base = _json(_run(root, "compute-agentic-cost"))["cost"]
    p = root / "analytics" / "pricing.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("output_per_1m_tokens: 25.0",
                                                       "output_per_1m_tokens: 50.0"), encoding="utf-8")
    assert _json(_run(root, "compute-agentic-cost"))["cost"] > base


def test_pricing_as_of_is_retrospectively_deterministic(tmp_path):
    root = _factory(tmp_path)
    first = _json(_run(root, "compute-agentic-cost", "--pricing-as-of", "2026-03-01"))
    # una nuova voce di prezzo successiva non cambia il costo calcolato «as of» il passato
    p = root / "analytics" / "pricing.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "  - id: claude-sonnet-4-6",
        "      - valid_from: 2026-10-01\n        input_per_1m_tokens: 99.0\n"
        "        output_per_1m_tokens: 99.0\n        cache_read_per_1m_tokens: 9.9\n"
        "        cache_write_per_1m_tokens: 9.9\n  - id: claude-sonnet-4-6"), encoding="utf-8")
    second = _json(_run(root, "compute-agentic-cost", "--pricing-as-of", "2026-03-01"))
    assert first["cost"] == second["cost"]


def test_cache_write_1h_priced_separately(tmp_path):
    # 1M scritti in cache, tutti a TTL 1h, su Sonnet 4.6 (5m: 3.75, 1h: 6.0 per 1M)
    event = {"task_id": "TSK-991", "project_id": "fixture", "actor_type": "agent",
             "actor_id": "be-dev", "task_type": "be", "state": "finished",
             "ts": "2026-09-21T12:00:00Z", "model": "claude-sonnet-4-6", "tool_calls": [],
             "tokens": {"input": 0, "output": 0, "cache_read": 0,
                        "cache_write": 1_000_000, "cache_write_1h": 1_000_000}}
    root = _factory(tmp_path, extra=[event])
    base = _json(_run(_factory(tmp_path / "base"), "compute-agentic-cost"))["cost"]
    # senza prezzo 1h nel listino: vale quello a 5m
    assert _json(_run(root, "compute-agentic-cost"))["cost"] == pytest.approx(base + 3.75)
    p = root / "analytics" / "pricing.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "        cache_write_per_1m_tokens: 3.75\n",
        "        cache_write_per_1m_tokens: 3.75\n        cache_write_1h_per_1m_tokens: 6.0\n"),
        encoding="utf-8")
    assert _json(_run(root, "compute-agentic-cost"))["cost"] == pytest.approx(base + 6.0)


def test_unknown_model_fails_loud_never_zero_cost(tmp_path):
    cp = _run(_factory(tmp_path, extra=[UNKNOWN_MODEL_EVENT]), "compute-agentic-cost")
    assert cp.returncode == 1
    assert _json(cp)["status"] == "error"
    assert "modello-ignoto-1" in cp.stderr


def test_human_cost_privacy_threshold(tmp_path):
    out = _json(_run(_factory(tmp_path), "compute-human-cost", "--audience", "executive"))
    assert out["cost"] == pytest.approx(1440)
    assert "per_actor" not in out["breakdown"]  # N=3 < min_aggregation_n=5


# --------------------------------------------------------------------------- stima

def test_run_pert_formula(tmp_path):
    out = _json(_run(_factory(tmp_path), "run-pert", "--voices", VOICES))
    exp = sum((o + 4 * m + p) / 6 for o, m, p in ((1, 3, 8), (2, 4, 10), (0.5, 1, 2)))
    assert out["total"]["expected"] == pytest.approx(round(exp, 2), abs=0.01)


def test_run_pert_rejects_inverted_voice(tmp_path):
    cp = _run(_factory(tmp_path), "run-pert", "--voices", '[{"id":"x","O":5,"M":2,"P":1}]')
    assert cp.returncode == 1 and "violates O<=M<=P" in _json(cp)["error"]


def test_estimate_project_no_store_writes_nothing(tmp_path):
    root = _factory(tmp_path)
    cp = _run(root, "estimate-project", "--scope", SCOPE, "--no-store", "--seed", "7")
    assert cp.returncode == 0, cp.stderr
    assert not (root / "analytics" / "reports").exists()
    est = _json(cp)["estimate"]
    assert est["assumptions"] and est["sensitivity_drivers"]  # ADR-024 §E: mai vuoti


# --------------------------------------------------------------------------- record-event

def test_record_event_writes_once_and_is_idempotent(tmp_path):
    root = _factory(tmp_path, events=False)
    first = _run(root, "record-event", "--event", EVENT_OK)
    second = _run(root, "record-event", "--event", EVENT_OK)
    assert first.returncode == 0 and second.returncode == 0
    lines = (root / "analytics" / "events" / "2026-09.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["hash"]


@pytest.mark.parametrize("payload,needle", [
    (EVENT_OK[:-1] + ', "email": "a@b.it"}', "PII boundary violation"),
    (EVENT_OK.replace('"finished"', '"volato"'), "state"),
    ("{nope", "JSON"),
])
def test_record_event_rejects_bad_payload(tmp_path, payload, needle):
    root = _factory(tmp_path, events=False)
    cp = _run(root, "record-event", "--event", payload)
    assert cp.returncode == 1
    assert needle.lower() in json.dumps(_json(cp)).lower()
    assert not (root / "analytics" / "events").exists() or not any(
        (root / "analytics" / "events").glob("*.jsonl"))


def test_migrate_jsonl_to_sqlite(tmp_path):
    root = _factory(tmp_path)
    cp = _run(root, "migrate-jsonl-to-sqlite")
    assert cp.returncode == 0, cp.stderr
    con = sqlite3.connect(root / "analytics" / "events.db")
    try:
        n = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    finally:
        con.close()
    assert n == len(_events())


# --------------------------------------------------------------------------- rimandi

@pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="bash assente")
@pytest.mark.parametrize("rel", [f"tools/analytics/{n}.sh" for n in SCRIPTS]
                         + [f".claude/tools/analytics/{n}.sh" for n in SCRIPTS])
def test_sh_redirect_forwards_args_and_exit(rel):
    """Il rimando .sh (e lo shim) passa gli argomenti al .py e ne restituisce l'exit code."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    name = Path(rel).stem
    assert len(text) < 1500 and f"{name}.py" in text and "exec " in text, "non e' un rimando"
    cp = subprocess.run(["bash", str(ROOT / rel), "--nope"], capture_output=True, text=True,
                        timeout=120)
    assert cp.returncode == 1
    assert json.loads(cp.stdout) == {"status": "error", "error": "unknown argument: --nope"}


def test_compute_agentic_cost_regge_tool_calls_in_forma_storica(tmp_path):
    """Eventi reali con `tool_calls: ["Read", "Edit"]` (fuori schema {name, qty}) facevano cadere
    il calcolo con AttributeError: ora contano 0, restano in per_tool e sono dichiarati su stderr."""
    storico = json.loads(EVENT_OK)
    storico["task_id"] = "TSK-STORICO"
    storico["tool_calls"] = ["Read", "Edit"]
    root = _factory(tmp_path, extra=[storico])
    cp = _run(root, "compute-agentic-cost")
    assert cp.returncode == 0, cp.stderr
    d = _json(cp)
    assert "forma storica" in cp.stderr
    assert {"Read", "Edit"} <= set(d["breakdown"].get("per_tool", {}))


def test_canon_model_suffisso_fra_quadre_senza_alias():
    """EP-072: `claude-x[2m]` si risolve su `claude-x` anche senza alias esplicito."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cac_canon", Path(__file__).resolve().parents[1] / "analytics" / "compute-agentic-cost.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pricing = {"models": [{"id": "claude-x", "aliases": []}]}
    assert mod._canon_model("claude-x[2m]", pricing)["id"] == "claude-x"
    assert mod._canon_model("claude.x", pricing)["id"] == "claude-x"
    assert mod._canon_model("claude-y[1m]", pricing) is None
