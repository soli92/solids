"""Parita' misurata fra gli strumenti di analytics bash e il loro porting Python (US-327, TSK-743).

Il riferimento di COMPORTAMENTO e' l'implementazione bash di questa factory al commit
``REF_COMMIT`` (l'ultimo prima che i ``.sh`` diventassero rimandi al ``.py``): il test la
estrae con ``git show``, cosi' resta confrontabile anche dopo la migrazione.

Per ogni caso si costruisce una factory di prova in una cartella temporanea (config, prezzi,
tariffe ed eventi di fixture, repo git con un commit), si esegue la versione bash e quella
Python con gli stessi argomenti e si confrontano:

* exit code;
* stdout come JSON, normalizzato (campi di tempo d'esecuzione, path assoluti della fixture);
* gli artefatti scritti su disco (eventi, report, stime, database), normalizzati allo stesso modo.

Layout della fixture: i ``.sh`` storici risolvono la root a tre livelli sopra
(``.claude/tools/analytics/``), ``record-event.sh`` a due (``tools/analytics/``). Il test li mette
dove la root risolta coincide con la fixture; i ``.py`` stanno in ``tools/analytics/``.

Di default gira un caso per script (``SMOKE``); la matrice completa con ``ANALYTICS_PARITY=full``.

Salta (non fallisce) se mancano bash, jq, git o il commit di riferimento: su Windows senza
Git Bash il test non ha un termine di paragone, e i test del ``.py`` da solo
(``test_analytics_py.py``) restano comunque eseguiti.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ANALYTICS = ROOT / "tools" / "analytics"
REF_COMMIT = "9ebc4e239ebb670b8f1307eac37256c358458022"

SCRIPTS = [
    "analyze-timeline", "build-reference-class", "compute-agentic-cost",
    "compute-human-cost", "estimate-project", "generate-report",
    "migrate-jsonl-to-sqlite", "record-event", "run-pert",
]


# --------------------------------------------------------------------------- prerequisiti

def _ref_available() -> bool:
    if os.name == "nt" or not shutil.which("bash") or not shutil.which("jq") or not shutil.which("git"):
        return False
    r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{REF_COMMIT}^{{commit}}"],
                       capture_output=True)
    return r.returncode == 0


pytestmark = pytest.mark.skipif(
    not _ref_available(),
    reason="riferimento bash non disponibile (bash/jq/git assenti o commit di riferimento mancante)",
)


def _ref_source(name: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{REF_COMMIT}:tools/analytics/{name}"],
                          capture_output=True, text=True, check=True).stdout


def _patch_ref_compute_agentic_cost_sh(text: str) -> str:
    """Allinea lo step 9 al jq gia' corretto dello step 10 (canon) nello stesso script.

    La select del preflight usa `or (.aliases // []) as $a | index(...)` che su alcune
    versioni jq puo' fallire con «Cannot index boolean with string <model>» quando
    `.id == $norm` e' vero (precedenza `or`/`as`). Il calcolo costi usa gia' la forma
    con parentesi esplicite; il test di parita' deve poter eseguire il riferimento bash.
    """
    buggy = (
        "[ .models[] | select(.id == $norm or (.aliases // []) as $a | "
        "($a | index($norm)) != null or ($a | index($raw)) != null) | .id ] | first // \"\""
    )
    fixed = (
        "[ .models[] | select(.id == $norm or ((.aliases // []) | index($norm)) != null "
        "or ((.aliases // []) | index($raw)) != null) | .id ] | first // \"\""
    )
    if buggy not in text:
        return text
    return text.replace(buggy, fixed, 1)


# --------------------------------------------------------------------------- fixture

CONFIG_ON = """\
analytics:
  measurement:
    enabled: {measurement}
    store: jsonl
    pricing_table_path: analytics/pricing.yaml
    rate_card_path: analytics/rates.yaml
    rate_basis: fully-loaded
    min_aggregation_n: 5
    operational_show_actor_id: false
    actors_map:
      mario.rossi: senior-engineer
      anna.bianchi: senior-engineer
  estimation:
    enabled: {estimation}
    rcf_min_samples: 3
    rcf_low_confidence_threshold: 1
    rcf_medium_confidence_threshold: 3
    rcf_high_confidence_threshold: 6
    similarity_factor:
      high: 1.0
      medium: 0.7
      low: 0.4
    default_contingency_pct: 15
    monte_carlo:
      runtime: python
      iterations: 2000
      seed: 42
temporal:
  enabled: false
"""

PRICING = """\
currency: EUR
models:
  - id: claude-opus-4-7
    provider: anthropic
    display_name: "Claude Opus 4.7"
    aliases:
      - claude-opus-4.7
      - claude-opus-4-7[1m]
    pricing:
      - valid_from: 2026-01-01
        input_per_1m_tokens: 15.0
        output_per_1m_tokens: 75.0
        cache_read_per_1m_tokens: 1.5
        cache_write_per_1m_tokens: 18.75
      - valid_from: 2026-07-01
        input_per_1m_tokens: 5.0
        output_per_1m_tokens: 25.0
        cache_read_per_1m_tokens: 0.5
        cache_write_per_1m_tokens: 6.25
  - id: claude-sonnet-4-6
    provider: anthropic
    display_name: "Claude Sonnet 4.6"
    aliases:
      - claude-sonnet-4.6
    pricing:
      - valid_from: 2026-01-01
        input_per_1m_tokens: 3.0
        output_per_1m_tokens: 15.0
        cache_read_per_1m_tokens: 0.3
        cache_write_per_1m_tokens: 3.75
tools:
  - id: deterministic-script
    cost_per_call: 0.0
"""

RATES = """\
currency: EUR
rate_basis: fully-loaded
roles:
  - id: senior-engineer
    display_name: "Senior Software Engineer"
    aliases:
      - senior-eng
    rates:
      - valid_from: 2026-01-01
        hourly_rate: 80.0
      - valid_from: 2026-08-01
        hourly_rate: 90.0
"""

_LAYERS = ["be", "fe", "db", "qa", "docs"]
_MODELS = ["claude-opus-4-7", "claude-sonnet-4-6", "claude-opus-4.7", "claude-opus-4-7[1m]"]


def _events() -> list[dict]:
    """Eventi deterministici: 8 TSK agentici su 5 layer (uno bloccato), 6 TSK umani."""
    ev: list[dict] = []

    def add(**kw):
        base = {"project_id": "fixture", "tool_calls": [],
                "tokens": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}}
        base.update(kw)
        ev.append(base)

    for i in range(8):
        layer = _LAYERS[i % len(_LAYERS)]
        month = "06" if i < 3 else "09"
        day = 2 + i
        tid = f"TSK-{900 + i}"
        model = _MODELS[i % len(_MODELS)]
        add(task_id=tid, actor_type="agent", actor_id=f"{layer}-dev", task_type=layer,
            state="started", ts=f"2026-{month}-{day:02d}T09:00:00Z", model=model)
        if i == 6:
            add(task_id=tid, actor_type="agent", actor_id=f"{layer}-dev", task_type=layer,
                state="blocked", ts=f"2026-{month}-{day:02d}T10:00:00Z", model=model,
                blocked_reason="dipendenza mancante")
        hours = 1 + (i * 7) % 11
        add(task_id=tid, actor_type="agent", actor_id=f"{layer}-dev", task_type=layer,
            state="finished", ts=f"2026-{month}-{day:02d}T{9 + hours:02d}:30:00Z", model=model,
            elapsed_ms=hours * 3_600_000 + 1_800_000,
            tokens={"input": 1000 * (i + 1), "output": 500 * (i + 2),
                    "cache_read": 20000 * i, "cache_write": 3000 + 10 * i},
            tool_calls=[{"name": "Bash", "count": i + 1}])
    for j in range(6):
        actor = ["mario.rossi", "anna.bianchi", "luca.verdi"][j % 3]
        tid = f"TSK-{950 + j}"
        add(task_id=tid, actor_type="human", actor_id=actor, task_type=_LAYERS[j % 5],
            state="started", ts=f"2026-09-{10 + j:02d}T08:00:00Z")
        add(task_id=tid, actor_type="human", actor_id=actor, task_type=_LAYERS[j % 5],
            state="finished", ts=f"2026-09-{10 + j:02d}T{10 + j:02d}:00:00Z",
            elapsed_ms=(2 + j) * 3_600_000)
    return ev


UNKNOWN_MODEL_EVENT = {
    # modello assente dalla tabella prezzi: fail-loud, mai costo zero silenzioso
    "task_id": "TSK-990", "project_id": "fixture", "actor_type": "agent", "actor_id": "be-dev",
    "task_type": "be", "state": "finished", "ts": "2026-09-20T12:00:00Z", "model": "modello-ignoto-1",
    "elapsed_ms": 600000, "tool_calls": [],
    "tokens": {"input": 10, "output": 10, "cache_read": 0, "cache_write": 0},
}


def _write_events(root: Path, events: list[dict]) -> None:
    by_month: dict[str, list[str]] = {}
    for e in events:
        by_month.setdefault(e["ts"][:7], []).append(json.dumps(e, separators=(",", ":")))
    d = root / "analytics" / "events"
    d.mkdir(parents=True, exist_ok=True)
    for month, lines in by_month.items():
        (d / f"{month}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_factory(base: Path, *, measurement: bool = True, estimation: bool = True,
                  events: bool = True, extra_events: list[dict] | None = None) -> Path:
    root = base
    (root / "analytics").mkdir(parents=True, exist_ok=True)
    (root / "factory.config.yaml").write_text(
        CONFIG_ON.format(measurement=str(measurement).lower(), estimation=str(estimation).lower()),
        encoding="utf-8")
    (root / "analytics" / "pricing.yaml").write_text(PRICING, encoding="utf-8")
    (root / "analytics" / "rates.yaml").write_text(RATES, encoding="utf-8")
    if events:
        _write_events(root, _events() + list(extra_events or []))
    # implementazione bash di riferimento
    sh3 = root / ".claude" / "tools" / "analytics"
    sh3.mkdir(parents=True, exist_ok=True)
    for name in SCRIPTS:
        if name == "record-event":
            continue
        src = _ref_source(f"{name}.sh")
        if name == "compute-agentic-cost":
            src = _patch_ref_compute_agentic_cost_sh(src)
        (sh3 / f"{name}.sh").write_text(src, encoding="utf-8")
        (sh3 / f"{name}.sh").chmod(0o755)
    shutil.copy2(ANALYTICS / "run-monte-carlo.py", sh3 / "run-monte-carlo.py")
    py = root / "tools" / "analytics"
    py.mkdir(parents=True, exist_ok=True)
    (py / "record-event.sh").write_text(_ref_source("record-event.sh"), encoding="utf-8")
    (py / "record-event.sh").chmod(0o755)
    for name in SCRIPTS:
        shutil.copy2(ANALYTICS / f"{name}.py", py / f"{name}.py")
    shutil.copy2(ANALYTICS / "analytics_cli.py", py / "analytics_cli.py")
    shutil.copy2(ANALYTICS / "run-monte-carlo.py", py / "run-monte-carlo.py")
    shutil.copytree(ROOT / "tools" / "temporal", root / "tools" / "temporal",
                    ignore=shutil.ignore_patterns("__pycache__"))
    git = ["git", "-C", str(root), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
           "-c", "commit.gpgsign=false"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "fixture", "--date", "2026-09-01T00:00:00Z"],
                   check=True, env={**os.environ, "GIT_COMMITTER_DATE": "2026-09-01T00:00:00Z"})
    return root


# --------------------------------------------------------------------------- esecuzione

def run_sh(root: Path, name: str, args: list[str]) -> subprocess.CompletedProcess:
    path = (root / "tools" / "analytics" / "record-event.sh") if name == "record-event" \
        else (root / ".claude" / "tools" / "analytics" / f"{name}.sh")
    return subprocess.run(["bash", str(path), *args], cwd=root, capture_output=True, text=True,
                          timeout=900)


def run_py(root: Path, name: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "tools" / "analytics" / f"{name}.py"), *args],
                          cwd=root, capture_output=True, text=True, timeout=900)


# campi che dipendono dall'istante d'esecuzione, non dal dato
_VOLATILE_KEYS = {"generated_at", "computed_at", "run_at", "created_at", "timestamp", "now",
                  "as_of_run", "elapsed_ms_tool", "duration_ms"}
_ISO_NOW = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z")
# I report nominano l'implementazione che li ha generati («generate-report.sh (tool …)»,
# «Generato da estimate-project.sh (EP-010 …)» → «….py»): differenza dichiarata, l'unica
# normalizzata oltre a tempi d'esecuzione e path della fixture.
_GENERATED_BY = re.compile(r"\b(generate-report|estimate-project)\.(?:sh|py)( \((?:tool|EP-0))")


def _norm(obj, roots: tuple[str, ...]):
    if isinstance(obj, dict):
        return {k: ("<volatile>" if k in _VOLATILE_KEYS else _norm(v, roots)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_norm(v, roots) for v in obj]
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, str):
        for r in roots:
            obj = obj.replace(r, "<ROOT>")
        return _GENERATED_BY.sub(r"\1.<impl>\2", obj)
    return obj


def _parse_stdout(text: str, roots: tuple[str, ...]):
    text = text.strip()
    if not text:
        return None
    try:
        return _norm(json.loads(text), roots)
    except json.JSONDecodeError:
        # piu' righe JSON o testo: confronto riga per riga
        out = []
        for line in text.splitlines():
            try:
                out.append(_norm(json.loads(line), roots))
            except json.JSONDecodeError:
                out.append(_norm(line, roots))
        return out


def _snapshot(root: Path, rel_dirs: list[str]) -> dict:
    """Artefatti scritti dallo script, normalizzati (contenuto JSON/JSONL/MD/DB)."""
    roots = (str(root), str(root.resolve()))
    snap: dict = {}
    for rel in rel_dirs:
        base = root / rel
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.name == ".lock":
                continue
            key = str(p.relative_to(root))
            key = re.sub(r"\d{4}-\d{2}-\d{2}([T-]\d{2}-?\d{2}(-?\d{2})?Z?)?", "<DATE>", key)
            if p.suffix == ".db":
                con = sqlite3.connect(p)
                try:
                    rows = con.execute("SELECT * FROM events ORDER BY ts, task_id, state").fetchall()
                    cols = [c[1] for c in con.execute("PRAGMA table_info(events)")]
                finally:
                    con.close()
                snap[key] = {"cols": cols, "rows": [list(r[1:]) for r in rows]}
            elif p.suffix == ".json":
                snap[key] = _norm(json.loads(p.read_text(encoding="utf-8")), roots)
            elif p.suffix == ".jsonl":
                # byte per byte: il formato della riga e' parte del contratto (dedup per grep)
                snap[key] = p.read_text(encoding="utf-8").splitlines()
            else:
                txt = p.read_text(encoding="utf-8", errors="replace")
                for r in roots:
                    txt = txt.replace(r, "<ROOT>")
                snap[key] = _GENERATED_BY.sub(r"\1.<impl>\2", _ISO_NOW.sub("<TS>", txt))
    return snap


def compare(tmp_path: Path, name: str, args: list[str], *, measurement=True, estimation=True,
            events=True, extra_events=None, artifacts: list[str] | None = None, pre=None) -> dict:
    """Esegue bash e Python su due fixture identiche e ritorna gli esiti normalizzati."""
    res = {}
    # una sola fixture, copiata: stesso commit, quindi stessa versione della tabella prezzi
    build_factory(tmp_path / "sh", measurement=measurement, estimation=estimation,
                  events=events, extra_events=extra_events)
    shutil.copytree(tmp_path / "sh", tmp_path / "py", symlinks=True)
    for impl, runner in (("sh", run_sh), ("py", run_py)):
        root = tmp_path / impl
        if pre:
            pre(root, impl)
        cp = runner(root, name, args)
        roots = (str(root), str(root.resolve()))
        res[impl] = {
            "exit": cp.returncode,
            "stdout": _parse_stdout(cp.stdout, roots),
            "artifacts": _snapshot(root, artifacts or []),
            "_stderr": cp.stderr,
        }
    return res


# Divergenze DICHIARATE, non tollerate in silenzio: ognuna e' un difetto del riferimento bash
# che il porting corregge, con la motivazione. Il test le verifica esattamente (sh e py).
#
# record-event.sh installa `trap _temporal_sm_hook_v218 EXIT` (riga 356) ma definisce la
# funzione a fine file (riga 508), dopo gli `exit 0` del dispatch: a ogni registrazione riuscita
# (o idempotente) il trap non trova la funzione e lo script esce con 127, contro il proprio
# contratto («0 evento registrato»). Conseguenza osservabile: harvest-session-tokens.py segna
# `recorded: false` eventi che sono stati scritti. Il .py esce 0.
RECORD_EVENT_TRAP_BUG = {"sh": 127, "py": 0}


def assert_parity(res: dict, exit_divergence: dict | None = None) -> None:
    sh, py = res["sh"], res["py"]
    msg = f"\n--- stderr sh ---\n{sh['_stderr'][-1500:]}\n--- stderr py ---\n{py['_stderr'][-1500:]}"
    if exit_divergence:
        assert (sh["exit"], py["exit"]) == (exit_divergence["sh"], exit_divergence["py"]), \
            f"divergenza dichiarata cambiata: sh={sh['exit']} py={py['exit']}{msg}"
    else:
        assert sh["exit"] == py["exit"], f"exit sh={sh['exit']} py={py['exit']}{msg}"
    assert sh["stdout"] == py["stdout"], msg
    assert sh["artifacts"] == py["artifacts"], msg


# --------------------------------------------------------------------------- casi

VOICES = json.dumps([
    {"id": "be-api", "O": 1, "M": 3, "P": 8},
    {"id": "fe-form", "O": 2, "M": 4, "P": 10},
    {"id": "db-mig", "O": 0.5, "M": 1, "P": 2},
])

SCOPE = json.dumps([
    {"name": "be-api", "task_type": "be", "O": 1, "M": 3, "P": 8},
    {"name": "fe-form", "task_type": "fe", "O": 2, "M": 4, "P": 10},
])
THROUGHPUT = "[1,2,3,2,4,3,2,5]"

EVENT_OK = json.dumps({
    "task_id": "TSK-777", "project_id": "fixture", "actor_type": "agent", "actor_id": "be-dev",
    "task_type": "be", "state": "finished", "ts": "2026-09-30T10:00:00Z",
    "tokens": {"input": 1, "output": 2, "cache_read": 3, "cache_write": 4},
    "model": "claude-opus-4-7", "tool_calls": [], "elapsed_ms": 1000,
})

CASES: list[tuple[str, str, list[str], dict]] = [
    # compute-agentic-cost
    ("cac-default", "compute-agentic-cost", [], {}),
    ("cac-task", "compute-agentic-cost", ["--task-id", "TSK-901"], {}),
    ("cac-filter", "compute-agentic-cost", ["--filter", '{"task_type":"be"}'], {}),
    ("cac-as-of", "compute-agentic-cost", ["--pricing-as-of", "2026-03-01"], {}),
    ("cac-gate-off", "compute-agentic-cost", [], {"measurement": False}),
    ("cac-no-events", "compute-agentic-cost", [], {"events": False}),
    ("cac-unknown-model", "compute-agentic-cost", [], {"extra_events": [UNKNOWN_MODEL_EVENT]}),
    ("cac-bad-arg", "compute-agentic-cost", ["--nope"], {}),
    ("cac-missing-pricing", "compute-agentic-cost", ["--pricing", "analytics/manca.yaml"], {}),
    # compute-human-cost
    ("chc-default", "compute-human-cost", [], {}),
    ("chc-executive", "compute-human-cost", ["--audience", "executive"], {}),
    ("chc-project", "compute-human-cost", ["--audience", "project"], {}),
    ("chc-operativa", "compute-human-cost", ["--audience", "operativa"], {}),
    ("chc-task", "compute-human-cost", ["--task-id", "TSK-950"], {}),
    ("chc-rate-as-of", "compute-human-cost", ["--rate-as-of", "2026-03-01"], {}),
    ("chc-gate-off", "compute-human-cost", [], {"measurement": False}),
    ("chc-bad-arg", "compute-human-cost", ["--nope"], {}),
    # analyze-timeline
    ("at-default", "analyze-timeline", [], {}),
    ("at-layer", "analyze-timeline", ["--group-by", "layer"], {}),
    ("at-actor-type", "analyze-timeline", ["--group-by", "actor_type"], {}),
    ("at-state", "analyze-timeline", ["--group-by", "state"], {}),
    ("at-filter", "analyze-timeline", ["--filter", '{"task_type":"fe"}'], {}),
    ("at-bad-group", "analyze-timeline", ["--group-by", "colore"], {}),
    ("at-gate-off", "analyze-timeline", [], {"measurement": False}),
    ("at-no-events", "analyze-timeline", [], {"events": False}),
    # build-reference-class
    ("brc-be", "build-reference-class", ["--filter", '{"task_type":"be"}'], {}),
    ("brc-high", "build-reference-class", ["--filter", '{"task_type":"fe"}', "--similarity", "high"], {}),
    ("brc-low", "build-reference-class", ["--similarity", "low"], {}),
    ("brc-empty", "build-reference-class", ["--filter", '{"task_type":"zzz"}'], {}),
    ("brc-gate-off", "build-reference-class", [], {"estimation": False}),
    ("brc-bad-arg", "build-reference-class", ["--nope"], {}),
    # run-pert
    ("pert-days", "run-pert", ["--voices", VOICES], {}),
    ("pert-hours", "run-pert", ["--voices", VOICES, "--unit", "hours"], {}),
    ("pert-invalid", "run-pert", ["--voices", '[{"id":"x","O":5,"M":2,"P":1}]'], {}),
    ("pert-not-json", "run-pert", ["--voices", "nope"], {}),
    ("pert-missing", "run-pert", [], {}),
    ("pert-gate-off", "run-pert", ["--voices", VOICES], {"estimation": False}),
    # estimate-project
    ("est-no-store", "estimate-project", ["--scope", SCOPE, "--no-store", "--seed", "7"], {}),
    ("est-pert", "estimate-project", ["--scope", SCOPE, "--force-method", "pert", "--no-store"], {}),
    ("est-rcf", "estimate-project", ["--scope", SCOPE, "--force-method", "rcf", "--no-store"], {}),
    ("est-mc", "estimate-project", ["--scope", SCOPE, "--throughput-samples", THROUGHPUT, "--seed", "7",
                                    "--no-store"], {}),
    ("est-mc-short", "estimate-project", ["--scope", SCOPE, "--throughput-samples", "[1,2,3]",
                                          "--no-store"], {}),
    ("est-bad-method", "estimate-project", ["--scope", SCOPE, "--force-method", "oracolo"], {}),
    ("est-bad-contingency", "estimate-project", ["--scope", SCOPE, "--contingency-pct", "tanto"], {}),
    ("est-store", "estimate-project", ["--scope", SCOPE, "--slug", "fixture", "--seed", "7"],
     {"artifacts": ["analytics/reports"]}),
    ("est-missing-scope", "estimate-project", [], {}),
    ("est-gate-off", "estimate-project", ["--scope", SCOPE, "--no-store"], {"estimation": False}),
    # generate-report
    ("rep-operativa", "generate-report", ["--audience", "operativa", "--slug", "fx", "--format", "md+json"],
     {"artifacts": ["analytics/reports"]}),
    ("rep-progetto", "generate-report", ["--audience", "progetto", "--slug", "fx", "--format", "json"],
     {"artifacts": ["analytics/reports"]}),
    ("rep-executive", "generate-report", ["--audience", "executive", "--slug", "fx"],
     {"artifacts": ["analytics/reports"]}),
    ("rep-unknown-model", "generate-report", ["--audience", "operativa", "--slug", "fx"],
     {"extra_events": [UNKNOWN_MODEL_EVENT], "artifacts": ["analytics/reports"]}),
    ("rep-bad-audience", "generate-report", ["--audience", "nessuno"], {}),
    ("rep-gate-off", "generate-report", ["--audience", "operativa"], {"measurement": False}),
    # migrate-jsonl-to-sqlite
    ("mig-default", "migrate-jsonl-to-sqlite", [], {"artifacts": ["analytics/events.db"]}),
    ("mig-no-events", "migrate-jsonl-to-sqlite", [], {"events": False}),
    ("mig-bad-arg", "migrate-jsonl-to-sqlite", ["--nope"], {}),
    # record-event
    ("rec-ok", "record-event", ["--event", EVENT_OK],
     {"artifacts": ["analytics/events"], "exit_divergence": RECORD_EVENT_TRAP_BUG}),
    ("rec-missing", "record-event", [], {}),
    ("rec-bad-json", "record-event", ["--event", "{nope"], {}),
    ("rec-bad-state", "record-event", ["--event", EVENT_OK.replace('"finished"', '"volato"')], {}),
    ("rec-pii-key", "record-event", ["--event", EVENT_OK[:-1] + ', "email": "a@b.it"}'], {}),
    ("rec-pii-text", "record-event", ["--event", EVENT_OK[:-1] + ', "blocked_reason": "' + "x" * 201 + '"}'], {}),
    ("rec-gate-off", "record-event", ["--event", EVENT_OK],
     {"measurement": False, "artifacts": ["analytics/events"]}),
]


# Il riferimento bash e' lento (compute-agentic-cost.sh invoca jq per evento: ~3 minuti a caso).
# Di default gira un caso rappresentativo per script; la matrice completa con
# ANALYTICS_PARITY=full (misurata cosi' per US-327: vedi TSK-743).
SMOKE = {"cac-default", "chc-operativa", "at-layer", "brc-be", "pert-days", "est-no-store",
         "rep-operativa", "mig-default", "rec-ok", "rec-pii-key", "cac-bad-arg"}
_FULL = os.environ.get("ANALYTICS_PARITY", "").lower() == "full"
_SELECTED = [c for c in CASES if _FULL or c[0] in SMOKE]


@pytest.mark.parametrize("case_id,name,args,kw", _SELECTED, ids=[c[0] for c in _SELECTED])
def test_parity(tmp_path, case_id, name, args, kw):
    kw = dict(kw)
    divergence = kw.pop("exit_divergence", None)
    assert_parity(compare(tmp_path, name, args, **kw), divergence)


@pytest.mark.skipif(not _FULL, reason="matrice completa: ANALYTICS_PARITY=full")
def test_record_event_idempotent_parity(tmp_path):
    """Lo stesso evento registrato due volte produce una sola riga, in entrambe le versioni."""
    def twice(root: Path, impl: str):
        runner = run_sh if impl == "sh" else run_py
        runner(root, "record-event", ["--event", EVENT_OK])
    assert_parity(compare(tmp_path, "record-event", ["--event", EVENT_OK],
                          artifacts=["analytics/events"], pre=twice), RECORD_EVENT_TRAP_BUG)


def _deep_diff(a, b, path="$", out=None):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: sh={a.get(k, '<assente>')!r:.200} py={b.get(k, '<assente>')!r:.200}")
            else:
                _deep_diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _deep_diff(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append(f"{path}: sh={a!r:.300} py={b!r:.300}")
    return out


if __name__ == "__main__":  # diagnostica: stampa le divergenze caso per caso
    import tempfile
    only = set(sys.argv[1:])
    for cid, name, args, kw in CASES:
        if only and cid not in only and name not in only:
            continue
        with tempfile.TemporaryDirectory() as td:
            kw = dict(kw)
            div = kw.pop("exit_divergence", None)
            r = compare(Path(td), name, args, **kw)
            ok = all(r["sh"][k] == r["py"][k] for k in ("stdout", "artifacts")) and (
                (r["sh"]["exit"], r["py"]["exit"]) == ((div["sh"], div["py"]) if div
                                                     else (r["py"]["exit"], r["py"]["exit"])))
            print(("OK   " if ok else "DIFF ") + cid, flush=True)
            if not ok:
                for k in ("exit", "stdout", "artifacts"):
                    if r["sh"][k] != r["py"][k]:
                        for line in _deep_diff(r["sh"][k], r["py"][k])[:40]:
                            print(f"  [{k}] {line}")
                print("  sh-err:", r["sh"]["_stderr"][-600:].replace("\n", " | "))
                print("  py-err:", r["py"]["_stderr"][-600:].replace("\n", " | "))
