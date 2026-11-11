"""
test_close_collect.py - test pytest per tools/session/close_collect.py e tools/session/close_lock.py

Copertura:
  - schema della busta (campi, status/severity/gate/source per fonte, dimensione)
  - exit code (0 completa, 3 incompleta, 2 argomenti non validi)
  - timeout simulato di una fonte (nessun blocco, busta incompleta)
  - mutex: doppio acquire, doppio release, GC dell'orfano (lock.json vecchio o mancante)
  - claim idempotente e conflitti concorrenti (advisory, exit 0, `attention` valorizzato)
  - coerenza tra i campi della busta e la tabella dei gate della skill

Ogni test lavora su una root temporanea (git init locale, copia dei tool di sessione):
nessuna scrittura nel clone reale, nessuna rete. I gate opt-in (repo-align, ai-policy)
restano spenti perche' la config temporanea non li abilita; cost-alert e' sostituito da
uno stub che esce con un JSON vuoto.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
from tools.session import close_collect as cc  # noqa: E402

SKILL = REPO / ".claude" / "skills" / "session-close-protocol.md"
SESSION_UUID = "aaaaaaaa-1111-4111-8111-111111111111"
OTHER_UUID = "bbbbbbbb"
ENVELOPE_FIELDS = {"schema", "generated_at", "root", "complete", "incomplete_sources",
                   "unavailable", "attention", "sources"}
SOURCE_FIELDS = {"status", "severity", "gate", "source", "data"}
STATUSES = {"ok", "fail", "attention", "skipped", "deferred", "error", "timeout"}
SEVERITIES = {"stop", "advisory", "info"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=30)


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Factory temporanea: repo git pulito, config con session_close attivo, tool copiati."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION_UUID)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.invalid")
    (tmp_path / "factory.config.yaml").write_text("session_close:\n  enabled: true\n", encoding="utf-8")
    (tmp_path / "wiki").mkdir()
    (tmp_path / "management").mkdir()
    (tmp_path / "wiki" / ".keep").write_text("", encoding="utf-8")
    (tmp_path / "management" / ".keep").write_text("", encoding="utf-8")
    shutil.copytree(REPO / "tools" / "session", tmp_path / "tools" / "session",
                    ignore=shutil.ignore_patterns("__pycache__"))
    stub = tmp_path / "tools" / "analytics"
    stub.mkdir(parents=True)
    (stub / "cost_alert.py").write_text(
        "import json\nprint(json.dumps({'enabled': False, 'results': [], 'escalations': []}))\n",
        encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _collect(root: Path, *extra: str, timeout: float = 120):
    cp = subprocess.run([sys.executable, str(REPO / "tools/session/close_collect.py"),
                         "--root", str(root), *extra],
                        capture_output=True, text=True, timeout=timeout, cwd=str(root),
                        env=os.environ.copy())
    env = json.loads(cp.stdout) if cp.stdout.strip() else None
    return cp, env


def _lock(root: Path, *args: str):
    cp = subprocess.run([sys.executable, str(root / "tools/session/close_lock.py"), *args,
                         "--root", str(root)],
                        capture_output=True, text=True, timeout=60, cwd=str(root))
    return cp


def _lock_json(cp) -> dict:
    return json.loads(cp.stdout)


def _sessions(root: Path, *args: str):
    return subprocess.run([sys.executable, str(root / "tools/session/active_sessions.py"), *args,
                           "--root", str(root), "--json"],
                          capture_output=True, text=True, timeout=60, cwd=str(root))


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def gate_table(text: str) -> dict[str, str]:
    """{nome gate: campo busta} dalla tabella dei gate della skill."""
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*`((?:STOP|ADV)-[A-Z-]+)`\s*\|.*\|\s*`([a-z_]+)`\s*\|\s*$", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def gate_mismatches(table: dict[str, str], sources: dict) -> list[str]:
    """Differenze tra tabella dei gate e campi `sources` della busta (entrambe le direzioni)."""
    problems = []
    for gate, field in table.items():
        if field not in sources:
            problems.append(f"{gate}: campo `{field}` assente dalla busta")
        elif sources[field].get("gate") != gate:
            problems.append(f"{gate}: il campo `{field}` riporta gate {sources[field].get('gate')!r}")
    in_table = set(table.values())
    for field, rec in sources.items():
        if rec.get("gate") and field not in in_table:
            problems.append(f"campo `{field}` ({rec['gate']}) non presente nella tabella")
    return problems


# ---------------------------------------------------------------------------
# 1. Schema della busta
# ---------------------------------------------------------------------------

def test_envelope_schema(root):
    cp, env = _collect(root)
    assert cp.returncode == 0, cp.stderr
    assert set(env) == ENVELOPE_FIELDS
    assert env["schema"] == "close_collect/1"
    assert env["complete"] is True and env["incomplete_sources"] == []
    assert isinstance(env["attention"], list)
    assert set(env["sources"]) == set(cc.GATES)
    for name, rec in env["sources"].items():
        assert SOURCE_FIELDS <= set(rec), name
        assert rec["status"] in STATUSES, name
        assert rec["severity"] in SEVERITIES, name
        assert isinstance(rec["source"], list) and rec["source"], name
        assert all("#" in s for s in rec["source"]), name
    assert len(cp.stdout.encode("utf-8")) <= 32 * 1024


def test_envelope_statuses_on_clean_root(root):
    _, env = _collect(root)
    s = env["sources"]
    assert s["config"]["status"] == "ok"
    assert s["dirty"]["status"] == "ok"
    assert s["lock"]["status"] == "ok"
    assert s["conflicts"]["status"] == "ok"
    assert s["repo_align"]["status"] == "skipped"
    assert s["ai_policy"]["status"] == "skipped"
    assert s["schema"]["status"] == "deferred" and s["sync_error"]["status"] == "deferred"
    assert s["session"]["data"]["session_id"] == SESSION_UUID
    assert s["session"]["data"]["short"] == SESSION_UUID[:8]


def test_dirty_wiki_is_stop_not_incomplete(root):
    (root / "wiki" / "nuova.md").write_text("x\n", encoding="utf-8")
    cp, env = _collect(root)
    assert cp.returncode == 0
    assert env["sources"]["dirty"]["status"] == "fail"
    assert env["sources"]["dirty"]["data"]["count"] == 1


def test_config_disabled_is_fail(root):
    (root / "factory.config.yaml").write_text("session_close:\n  enabled: false\n", encoding="utf-8")
    _, env = _collect(root)
    assert env["sources"]["config"]["status"] == "fail"


def test_live_lock_reported_as_fail(root):
    assert _lock(root, "acquire", "--operator", "x", "--session-label", "L").returncode == 0
    _, env = _collect(root)
    assert env["sources"]["lock"]["status"] == "fail"


def test_envelope_size_cap(root):
    for i in range(400):
        (root / "wiki" / f"{'x' * 60}-{i}.md").write_text("x\n", encoding="utf-8")
    cp, env = _collect(root)
    assert len(cp.stdout.encode("utf-8")) <= 32 * 1024
    assert env["sources"]["dirty"]["data"]["count"] == 400
    assert env["sources"]["dirty"]["data"]["truncated"] is True


# ---------------------------------------------------------------------------
# 2. Exit code
# ---------------------------------------------------------------------------

def test_exit_incomplete_when_config_missing(root):
    (root / "factory.config.yaml").unlink()
    cp, env = _collect(root)
    assert cp.returncode == 3
    assert env["complete"] is False
    assert "config" in env["incomplete_sources"]
    assert env["sources"]["config"]["status"] == "error"
    assert "complete:false" in cp.stderr


def test_exit_incomplete_when_not_a_git_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION_UUID)
    (tmp_path / "factory.config.yaml").write_text("session_close:\n  enabled: true\n", encoding="utf-8")
    cp, env = _collect(tmp_path)
    assert cp.returncode == 3
    assert env["complete"] is False and "dirty" in env["incomplete_sources"]


def test_exit_2_on_invalid_arguments(root):
    for args in (["--timeout", "0"], ["--timeout", "-3"], ["--timeout", "abc"], ["--nope"]):
        cp = subprocess.run([sys.executable, str(REPO / "tools/session/close_collect.py"),
                             "--root", str(root), *args], capture_output=True, text=True, timeout=60)
        assert cp.returncode == 2, args
        assert cp.stdout == ""


def test_lock_exit_2_on_invalid_arguments(root):
    assert _lock(root, "acquire", "--now", "non-una-data").returncode == 2
    assert _lock(root, "bogus").returncode == 2


def test_unavailable_advisory_source_does_not_make_envelope_incomplete(root):
    (root / "tools" / "analytics" / "cost_alert.py").write_text("raise SystemExit(5)\n", encoding="utf-8")
    cp, env = _collect(root)
    assert cp.returncode == 0
    assert env["complete"] is True
    assert env["sources"]["cost_alert"]["status"] == "error"
    assert env["unavailable"] == ["cost_alert"]


# ---------------------------------------------------------------------------
# 3. Timeout simulato
# ---------------------------------------------------------------------------

def test_timeout_of_required_source_is_incomplete_and_nonzero(root):
    (root / "tools" / "session" / "close_lock.py").write_text(
        "import time\ntime.sleep(30)\n", encoding="utf-8")
    cp, env = _collect(root, "--timeout", "1", timeout=25)
    assert cp.returncode == 3
    assert env["complete"] is False
    assert env["sources"]["lock"]["status"] == "timeout"
    assert env["sources"]["lock"]["timeout"] is True
    assert "lock" in env["incomplete_sources"]


def test_timeout_of_advisory_source_is_unavailable(root):
    (root / "tools" / "analytics" / "cost_alert.py").write_text(
        "import time\ntime.sleep(30)\n", encoding="utf-8")
    cp, env = _collect(root, "--timeout", "1", timeout=25)
    assert cp.returncode == 0
    assert env["sources"]["cost_alert"]["status"] == "timeout"
    assert env["unavailable"] == ["cost_alert"]


def test_run_maps_timeout_without_blocking(tmp_path):
    res = cc._run([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, 0.5)
    assert res["timeout"] is True and res["rc"] is None
    assert res["elapsed"] < 10
    bad = cc._failure("lock", res, 0.5)
    assert bad["status"] == "timeout"


# ---------------------------------------------------------------------------
# 4. Idempotenza di lock e claim
# ---------------------------------------------------------------------------

def test_double_acquire_fails_without_corrupting(root):
    first = _lock(root, "acquire", "--operator", "op1", "--session-label", "first", "--json")
    assert first.returncode == 0
    second = _lock(root, "acquire", "--operator", "op2", "--session-label", "second", "--json")
    assert second.returncode == 1
    out = _lock_json(second)
    assert out["gate"] == "STOP-LOCK" and out["reason"] == "live"
    stored = json.loads((root / ".session-close.lock" / "lock.json").read_text(encoding="utf-8"))
    assert stored["session_label"] == "first" and stored["operator"] == "op1"


def test_double_release_is_not_an_error(root):
    assert _lock(root, "acquire", "--operator", "o", "--session-label", "L").returncode == 0
    assert _lock(root, "release", "--json").returncode == 0
    again = _lock(root, "release", "--json")
    assert again.returncode == 0
    assert _lock_json(again)["released"] is False
    assert not (root / ".session-close.lock").exists()


def test_release_without_any_lock_is_ok(root):
    assert _lock(root, "release").returncode == 0


def test_acquire_after_release(root):
    assert _lock(root, "acquire", "--operator", "o", "--session-label", "L").returncode == 0
    _lock(root, "release")
    assert _lock(root, "acquire", "--operator", "o", "--session-label", "L2").returncode == 0


def test_double_claim_same_session_does_not_duplicate(root):
    args = ("claim", "--agent", "session-close", "--domain", "raw/sessions", "--kind", "session",
            "--uuid", SESSION_UUID[:8], "--operator", "tester")
    first = _sessions(root, *args)
    second = _sessions(root, *args)
    assert first.returncode == 0 and second.returncode == 0
    assert json.loads(first.stdout)["action"] == "aggiunto"
    assert json.loads(second.stdout)["action"] == "rinnovato"
    text = (root / "memory" / "active-sessions.yaml").read_text(encoding="utf-8")
    assert len(re.findall(rf"uuid:\s*{SESSION_UUID[:8]}", text)) == 1


def test_claim_release_roundtrip_is_idempotent(root):
    _sessions(root, "claim", "--agent", "a", "--domain", "raw/sessions", "--uuid", "cccccccc",
              "--operator", "tester")
    assert json.loads(_sessions(root, "release", "--domain", "raw/sessions",
                                "--uuid", "cccccccc").stdout)["removed"] == 1
    again = _sessions(root, "release", "--domain", "raw/sessions", "--uuid", "cccccccc")
    assert again.returncode == 0 and json.loads(again.stdout)["removed"] == 0


# ---------------------------------------------------------------------------
# 5. GC dell'orfano e lock vivo
# ---------------------------------------------------------------------------

def _write_lock(root: Path, minutes_ago: float, with_json: bool = True) -> Path:
    lock = root / ".session-close.lock"
    lock.mkdir()
    old = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    if with_json:
        (lock / "lock.json").write_text(json.dumps(
            {"locked_at": _iso(old), "operator": "old", "session_label": "old-label"}), encoding="utf-8")
    ts = old.timestamp()
    os.utime(lock, (ts, ts))
    return lock


def test_orphan_lock_with_json_is_garbage_collected(root):
    _write_lock(root, 30)
    cp = _lock(root, "acquire", "--operator", "new", "--session-label", "fresh", "--json")
    assert cp.returncode == 0
    out = _lock_json(cp)
    assert out["gc"]["session_label"] == "old-label"
    assert "orphan" in cp.stderr.lower()
    stored = json.loads((root / ".session-close.lock" / "lock.json").read_text(encoding="utf-8"))
    assert stored["session_label"] == "fresh"


def test_orphan_lock_without_json_uses_mtime(root):
    _write_lock(root, 30, with_json=False)
    status = _lock_json(_lock(root, "status", "--json"))["lock"]
    assert status["locked_at_source"] == "mtime" and status["orphan"] is True
    assert _lock(root, "acquire", "--operator", "n", "--session-label", "fresh").returncode == 0


def test_live_lock_within_ttl_is_not_collected(root):
    lock = _write_lock(root, 2)
    cp = _lock(root, "acquire", "--operator", "n", "--session-label", "fresh", "--json")
    assert cp.returncode == 1
    assert _lock_json(cp)["gate"] == "STOP-LOCK"
    assert lock.is_dir()
    assert json.loads((lock / "lock.json").read_text(encoding="utf-8"))["session_label"] == "old-label"


def test_live_lock_without_json_within_ttl_is_not_collected(root):
    _write_lock(root, 1, with_json=False)
    assert _lock(root, "acquire", "--operator", "n", "--session-label", "x").returncode == 1


def test_ttl_boundary_with_injected_clock(root):
    locked = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
    assert _lock(root, "acquire", "--operator", "o", "--session-label", "L",
                 "--now", _iso(locked)).returncode == 0
    live = _lock(root, "status", "--json", "--now", _iso(locked + timedelta(minutes=9)))
    dead = _lock(root, "status", "--json", "--now", _iso(locked + timedelta(minutes=11)))
    assert _lock_json(live)["lock"]["orphan"] is False
    assert _lock_json(dead)["lock"]["orphan"] is True


def test_collect_does_not_treat_orphan_lock_as_stop(root):
    _write_lock(root, 30)
    _, env = _collect(root)
    assert env["sources"]["lock"]["status"] == "ok"


def test_collect_is_read_only(root):
    _write_lock(root, 30)
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if ".git" not in p.parts
                    and "__pycache__" not in p.parts)
    _collect(root)
    after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if ".git" not in p.parts
                   and "__pycache__" not in p.parts)
    assert before == after


# ---------------------------------------------------------------------------
# 6. Claim concorrenti
# ---------------------------------------------------------------------------

def test_concurrent_claims_produce_attention(root):
    _sessions(root, "claim", "--agent", "session-close", "--domain", "raw/sessions", "--kind", "session",
              "--uuid", OTHER_UUID, "--operator", "altra-persona")
    cp, env = _collect(root)
    assert cp.returncode == 0  # advisory: mai un exit non-zero per un conflitto
    conflicts = env["sources"]["conflicts"]
    assert conflicts["status"] == "attention"
    assert conflicts["data"]["conflicts"]
    assert env["attention"]
    assert OTHER_UUID in env["attention"][0]
    assert env["complete"] is True


def test_no_conflict_means_empty_attention(root):
    _, env = _collect(root)
    assert env["attention"] == []
    assert env["sources"]["conflicts"]["data"]["conflicts"] == []


def test_own_claim_is_not_a_conflict(root):
    _sessions(root, "claim", "--agent", "session-close", "--domain", "raw/sessions", "--kind", "session",
              "--uuid", SESSION_UUID[:8], "--operator", "tester")
    _, env = _collect(root)
    assert env["sources"]["conflicts"]["status"] == "ok" and env["attention"] == []


def test_second_claim_reports_the_first_as_conflict(root):
    _sessions(root, "claim", "--agent", "a", "--domain", "raw/sessions", "--uuid", "dddddddd",
              "--operator", "uno")
    cp = _sessions(root, "claim", "--agent", "a", "--domain", "raw/sessions", "--uuid", "eeeeeeee",
                   "--operator", "due")
    assert cp.returncode == 0
    assert json.loads(cp.stdout)["conflicts"]


# ---------------------------------------------------------------------------
# 7. Coerenza busta / tabella dei gate
# ---------------------------------------------------------------------------

def test_gate_table_is_readable_and_covers_all_gates():
    table = gate_table(SKILL.read_text(encoding="utf-8"))
    assert {g.split("-")[0] for g in table} == {"STOP", "ADV"}
    for gate in ("STOP-CONFIG", "STOP-DIRTY", "STOP-LOCK", "STOP-SCHEMA", "STOP-SYNC-ERROR"):
        assert gate in table
    assert len(table) >= 9


def test_envelope_matches_gate_table(root):
    table = gate_table(SKILL.read_text(encoding="utf-8"))
    _, env = _collect(root)
    assert gate_mismatches(table, env["sources"]) == []


def test_gate_table_check_detects_removed_stop_field(root):
    table = gate_table(SKILL.read_text(encoding="utf-8"))
    _, env = _collect(root)
    for gate, field in table.items():
        broken = {k: v for k, v in env["sources"].items() if k != field}
        problems = gate_mismatches(table, broken)
        assert any(gate in p for p in problems), gate


def test_gate_table_check_detects_extra_field_in_envelope(root):
    table = gate_table(SKILL.read_text(encoding="utf-8"))
    _, env = _collect(root)
    extra = dict(env["sources"])
    extra["nuovo"] = {"gate": "STOP-NUOVO", "status": "ok"}
    assert gate_mismatches(table, extra)


def test_gate_table_check_fails_if_tool_drops_a_stop(monkeypatch):
    table = gate_table(SKILL.read_text(encoding="utf-8"))
    monkeypatch.setitem(cc.GATES, "lock", (None, "info"))
    sources = {k: {"gate": g} for k, (g, _) in cc.GATES.items()}
    assert any("STOP-LOCK" in p for p in gate_mismatches(table, sources))
