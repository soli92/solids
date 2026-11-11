"""
Test di tools/analytics/cost_alert.py.

Fixture: una factory di prova (config, pricing, regole) e una cartella di transcript in
tmp_path, nello stesso layout di ~/.claude/projects/<cwd>/ (sessione principale + subagents/).
Prezzi di prova: 1 USD per 1M token di input, 0 per il resto, così il costo atteso si legge
direttamente dal numero di token.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "tools" / "analytics" / "cost_alert.py"

_spec = importlib.util.spec_from_file_location("cost_alert", _SCRIPT)
ca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ca)

SID = "11111111-2222-3333-4444-555555555555"

PRICING = """currency: USD
models:
  - id: test-model
    pricing:
      - valid_from: 2026-01-01
        input_per_1m_tokens: 1.0
        output_per_1m_tokens: 0.0
        cache_read_per_1m_tokens: 0.0
        cache_write_per_1m_tokens: 0.0
"""


def _config(enabled=True, agent=True) -> str:
    return (f"analytics:\n  cost_alert:\n    enabled: {str(enabled).lower()}\n"
            f"    agent: {str(agent).lower()}\n")


def _rules(*rules) -> str:
    out = "version: 1\nrules:\n"
    for period, thr, action, *op in rules:
        out += f"  - period: {period}\n    threshold_usd: {thr}\n    action: {action}\n"
        if op:
            out += f"    operator: {op[0]}\n"
    return out


def _line(mid, tokens, ts, out_tokens=0):
    return json.dumps({"type": "assistant", "timestamp": ts, "message": {
        "id": mid, "model": "test-model",
        "usage": {"input_tokens": tokens, "output_tokens": out_tokens}}})


def _factory(tmp_path, config=None, rules=None, pricing=PRICING) -> Path:
    root = tmp_path / "factory"
    (root / "analytics").mkdir(parents=True)
    (root / "factory.config.yaml").write_text(config or _config(), encoding="utf-8")
    (root / "analytics" / "pricing.yaml").write_text(pricing, encoding="utf-8")
    (root / "analytics" / "alert-rules.yaml").write_text(
        rules or _rules(("session", 2.0, "warn")), encoding="utf-8")
    return root


def _transcripts(tmp_path, main_lines, sub_lines=()) -> Path:
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    (tdir / f"{SID}.jsonl").write_text("\n".join(main_lines) + "\n", encoding="utf-8")
    if sub_lines:
        sdir = tdir / SID / "subagents"
        sdir.mkdir(parents=True)
        (sdir / "agent-abc.jsonl").write_text("\n".join(sub_lines) + "\n", encoding="utf-8")
    return tdir


def _now_ts(delta_hours=0):
    t = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=delta_hours)
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _ctx(root, tdir):
    return {"root": root, "tdir": tdir, "pricer": ca.Pricer(root),
            "now": dt.datetime.now().astimezone(), "session_id": SID}


def test_stessa_risposta_su_piu_righe_contata_una_volta(tmp_path):
    root = _factory(tmp_path)
    ts = _now_ts()
    tdir = _transcripts(tmp_path, [_line("m1", 1_000_000, ts), _line("m1", 1_000_000, ts),
                                   _line("m2", 500_000, ts)])
    v = ca.evaluate(_ctx(root, tdir), ("session",))
    assert v["results"][0]["cost_usd"] == 1.5


def test_sessione_include_i_subagenti(tmp_path):
    root = _factory(tmp_path)
    ts = _now_ts()
    tdir = _transcripts(tmp_path, [_line("m1", 1_000_000, ts)], [_line("s1", 2_000_000, ts)])
    v = ca.evaluate(_ctx(root, tdir), ("session",))
    r = v["results"][0]
    assert r["cost_usd"] == 3.0 and r["breached"] and r["action"] == "warn"
    assert v["escalations"] == []


def test_finestra_giornaliera_esclude_i_giorni_precedenti(tmp_path):
    root = _factory(tmp_path, rules=_rules(("daily", 10.0, "warn")))
    now = dt.datetime.now().astimezone()
    yesterday = (now.replace(hour=12, minute=0) - dt.timedelta(days=1)).astimezone(dt.timezone.utc)
    tdir = _transcripts(tmp_path, [
        _line("old", 5_000_000, yesterday.strftime("%Y-%m-%dT%H:%M:%S.000Z")),
        _line("new", 1_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ("daily",))
    assert v["results"][0]["cost_usd"] == 1.0


def test_regola_non_valida_scartata_con_nota(tmp_path):
    rules = _rules(("session", 2.0, "warn"), ("yearly", 2.0, "warn"), ("daily", -1, "warn"))
    root = _factory(tmp_path, rules=rules)
    tdir = _transcripts(tmp_path, [_line("m1", 1_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ca.PERIODS)
    assert [r["period"] for r in v["results"]] == ["session"]
    assert any("yearly" in n for n in v["notes"])
    assert any("threshold_usd" in n for n in v["notes"])


def test_valuta_diversa_da_usd_nessun_confronto(tmp_path):
    root = _factory(tmp_path, pricing=PRICING.replace("USD", "EUR"))
    tdir = _transcripts(tmp_path, [_line("m1", 5_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ca.PERIODS)
    assert v["results"] == [] and any("valuta non omogenea" in n for n in v["notes"])


def test_capability_spenta_nessun_controllo(tmp_path):
    root = _factory(tmp_path, config=_config(enabled=False))
    tdir = _transcripts(tmp_path, [_line("m1", 5_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ca.PERIODS)
    assert v["enabled"] is False and v["results"] == []


def test_escalate_scrive_record_e_conserva_ack(tmp_path):
    root = _factory(tmp_path, rules=_rules(("session", 1.0, "escalate")))
    tdir = _transcripts(tmp_path, [_line("m1", 2_000_000, _now_ts())])
    ctx = _ctx(root, tdir)
    v = ca.evaluate(ctx, ca.PERIODS)
    assert len(v["escalations"]) == 1
    [path] = ca.write_records(ctx, v, "nota")
    op = v["operator"]
    assert len(ca.pending(root, op)) == 1

    rec = json.loads((root / path).read_text(encoding="utf-8"))
    rec["acknowledged_at"] = "2026-10-09T10:00:00+02:00"
    (root / path).write_text(json.dumps(rec), encoding="utf-8")
    ca.write_records(ctx, ca.evaluate(ctx, ca.PERIODS), "")
    rec2 = json.loads((root / path).read_text(encoding="utf-8"))
    assert rec2["acknowledged_at"] == rec["acknowledged_at"] and rec2["note"] == "nota"
    assert ca.pending(root, op) == []


def test_escalate_senza_agente_vale_come_warn(tmp_path):
    root = _factory(tmp_path, config=_config(agent=False),
                    rules=_rules(("session", 1.0, "escalate")))
    tdir = _transcripts(tmp_path, [_line("m1", 2_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ca.PERIODS)
    assert v["agent_enabled"] is False
    assert any("escalation non disponibile" in n for n in v["notes"])


def test_suffisso_status_line(tmp_path):
    root = _factory(tmp_path, rules=_rules(("session", 10.0, "warn")))
    assert ca.status_line_suffix(5.0, root) == ""
    assert "85%" in ca.status_line_suffix(8.5, root)
    assert "superata" in ca.status_line_suffix(12.0, root)
    off = _factory(tmp_path / "off", config=_config(enabled=False))
    assert ca.status_line_suffix(99.0, off) == ""


def test_gate_tace_senza_soglie_superate(tmp_path, capsys):
    root = _factory(tmp_path, rules=_rules(("session", 10.0, "warn")))
    tdir = _transcripts(tmp_path, [_line("m1", 1_000_000, _now_ts())])
    args = ["--root", str(root), "--transcripts-dir", str(tdir), "check", "--session-id", SID]
    ca.main(args + ["--gate"])
    assert capsys.readouterr().out == ""
    ca.main(args + ["--compact"])
    assert "◉ COSTI" in capsys.readouterr().out


def test_gate_parla_con_soglia_superata(tmp_path, capsys):
    root = _factory(tmp_path, rules=_rules(("session", 0.5, "warn")))
    tdir = _transcripts(tmp_path, [_line("m1", 1_000_000, _now_ts())])
    ca.main(["--root", str(root), "--transcripts-dir", str(tdir), "check",
             "--session-id", SID, "--gate"])
    out = capsys.readouterr().out
    assert "⚠" in out and "1.00/0.5 USD" in out


def test_ledger_conta_una_risposta_per_id_e_i_subagenti(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "show_session_tokens", _REPO_ROOT / "tools" / "analytics" / "show-session-tokens.py")
    ledger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ledger)
    ts = _now_ts()
    tdir = _transcripts(tmp_path, [_line("m1", 1_000_000, ts), _line("m1", 1_000_000, ts)],
                        [_line("s1", 2_000_000, ts)])
    totals, models = ledger.parse_tokens(str(tdir / f"{SID}.jsonl"))
    assert totals == {"input": 3_000_000, "output": 0, "cache_read": 0, "cache_write": 0,
                      "cache_write_1h": 0}
    assert models == {"test-model"}
    _, _, per_model = ledger.parse_session(str(tdir / f"{SID}.jsonl"))
    pricing = {"test-model": {"in": 1.0, "out": 0.0, "cr": 0.0, "cw": 0.0}}
    assert ledger.calc_cost(totals, models, pricing, per_model) == 3.0


def _write_line(mid, ts, total, one_hour):
    return json.dumps({"type": "assistant", "timestamp": ts, "message": {
        "id": mid, "model": "test-model",
        "usage": {"input_tokens": 0, "output_tokens": 0,
                  "cache_creation_input_tokens": total,
                  "cache_creation": {"ephemeral_5m_input_tokens": total - one_hour,
                                     "ephemeral_1h_input_tokens": one_hour}}}})


def test_scritture_in_cache_a_1h_prezzate_a_parte(tmp_path):
    # 3M scritti in cache, di cui 1M a TTL 1h: 2M a 1 USD + 1M a 2 USD = 4 USD
    pricing = PRICING.replace("cache_write_per_1m_tokens: 0.0",
                              "cache_write_per_1m_tokens: 1.0\n"
                              "        cache_write_1h_per_1m_tokens: 2.0")
    root = _factory(tmp_path, pricing=pricing)
    tdir = _transcripts(tmp_path, [_write_line("m1", _now_ts(), 3_000_000, 1_000_000)])
    v = ca.evaluate(_ctx(root, tdir), ("session",))
    assert v["results"][0]["cost_usd"] == 4.0


def test_senza_prezzo_1h_vale_quello_a_5m(tmp_path):
    pricing = PRICING.replace("cache_write_per_1m_tokens: 0.0", "cache_write_per_1m_tokens: 1.0")
    root = _factory(tmp_path, pricing=pricing)
    tdir = _transcripts(tmp_path, [_write_line("m1", _now_ts(), 3_000_000, 1_000_000)])
    v = ca.evaluate(_ctx(root, tdir), ("session",))
    assert v["results"][0]["cost_usd"] == 3.0


def test_regola_personale_sostituisce_la_generale_dello_stesso_periodo(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "operator", lambda root: "alice")
    rules = _rules(("session", 10.0, "warn"), ("session", 2.0, "escalate", "alice"),
                   ("session", 1.0, "escalate", "bob"))
    root = _factory(tmp_path, rules=rules)
    tdir = _transcripts(tmp_path, [_line("m1", 3_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ("session",))
    [r] = v["results"]
    assert r["operator"] == "alice" and r["threshold_usd"] == 2.0 and r["breached"]
    assert len(v["escalations"]) == 1
    assert "regola personale di alice" in ca.fmt_verdict(v)


def test_regola_personale_di_altri_non_si_applica(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "operator", lambda root: "carol")
    rules = _rules(("session", 10.0, "warn"), ("session", 2.0, "escalate", "alice"))
    root = _factory(tmp_path, rules=rules)
    tdir = _transcripts(tmp_path, [_line("m1", 3_000_000, _now_ts())])
    [r] = ca.evaluate(_ctx(root, tdir), ("session",))["results"]
    assert r["operator"] == "" and r["threshold_usd"] == 10.0 and not r["breached"]


PLANS = """
plans:
  premium:
    label: "Piano A"
    license_usd_month: 100
    central_funding_usd_month: 20
    included_usd: 2
    included_period: weekly
  general:
    label: "Piano B"
    license_usd_month: 0
    central_funding_usd_month: 20
    included_usd: 5
    included_period: monthly
subscriptions:
  - operator: alice
    plan: premium
  - operator: bob
    plan: general
"""


def test_piano_genera_la_soglia_inclusa_e_la_stima_di_addebito(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "operator", lambda root: "alice")
    root = _factory(tmp_path, rules=_rules(("weekly", 100.0, "warn")) + PLANS)
    tdir = _transcripts(tmp_path, [_line("m1", 3_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ("weekly",))
    [r] = v["results"]
    assert r["plan"] == "premium" and r["threshold_usd"] == 2.0 and r["breached"]
    assert r["action"] == "escalate" and r["excess_usd"] == 1.0
    assert v["plan"]["fixed_usd_month"] == 80.0
    assert "80.00 USD/mese fissi" in ca.fmt_verdict(v)


def test_regola_personale_prevale_sul_piano(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "operator", lambda root: "alice")
    root = _factory(tmp_path, rules=_rules(("weekly", 10.0, "warn", "alice")) + PLANS)
    tdir = _transcripts(tmp_path, [_line("m1", 3_000_000, _now_ts())])
    [r] = ca.evaluate(_ctx(root, tdir), ("weekly",))["results"]
    assert r["threshold_usd"] == 10.0 and "plan" not in r and not r["breached"]


def test_operatore_senza_abbonamento_resta_sulle_regole_generali(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "operator", lambda root: "carol")
    root = _factory(tmp_path, rules=_rules(("weekly", 100.0, "warn")) + PLANS)
    tdir = _transcripts(tmp_path, [_line("m1", 3_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ("weekly", "monthly"))
    assert v["plan"] is None
    assert [(r["period"], r["threshold_usd"]) for r in v["results"]] == [("weekly", 100.0)]


def test_piano_mensile_esclude_i_mesi_precedenti(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "operator", lambda root: "bob")
    root = _factory(tmp_path, rules=_rules(("session", 100.0, "warn")) + PLANS)
    tdir = _transcripts(tmp_path, [_line("old", 9_000_000, _now_ts(delta_hours=24 * 32)),
                                   _line("new", 6_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ("monthly",))
    [r] = v["results"]
    assert r["plan"] == "general" and r["cost_usd"] == 6.0 and r["excess_usd"] == 1.0
    assert v["plan"]["fixed_usd_month"] == 0.0


def test_piano_non_valido_scartato_con_nota(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "operator", lambda root: "alice")
    bad = PLANS.replace("included_period: weekly", "included_period: daily")
    root = _factory(tmp_path, rules=_rules(("weekly", 100.0, "warn")) + bad)
    tdir = _transcripts(tmp_path, [_line("m1", 3_000_000, _now_ts())])
    v = ca.evaluate(_ctx(root, tdir), ("weekly",))
    assert v["plan"] is None and v["results"][0]["threshold_usd"] == 100.0
    assert any("piano premium" in n for n in v["notes"])
    assert any("abbonamento 1" in n for n in v["notes"])


# ---------------------------------------------------------------------------
# Lancio da un worktree della factory: i transcript della sessione stanno nella
# cartella del checkout principale (o di un altro worktree), non in quella del cwd.
# ---------------------------------------------------------------------------

def _home_with_projects(tmp_path, monkeypatch, main_dir, wt_dir):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(ca, "factory_checkouts", lambda root: [str(main_dir), str(wt_dir)])


def test_check_da_worktree_legge_i_transcript_del_checkout_principale(tmp_path, monkeypatch,
                                                                     capsys):
    root = _factory(tmp_path, rules=_rules(("session", 10.0, "warn"), ("daily", 10.0, "warn")))
    main_dir = tmp_path / "factory"
    wt_dir = main_dir / ".claude" / "worktrees" / "a1"
    _home_with_projects(tmp_path, monkeypatch, main_dir, wt_dir)
    tdir = ca.transcripts_dir(str(main_dir))
    tdir.mkdir(parents=True)
    (tdir / f"{SID}.jsonl").write_text(_line("m1", 2_000_000, _now_ts()) + "\n",
                                       encoding="utf-8")
    ca.main(["--root", str(root), "--project-dir", str(wt_dir), "check",
             "--session-id", SID, "--json"])
    v = json.loads(capsys.readouterr().out)
    costs = {r["period"]: r["cost_usd"] for r in v["results"]}
    assert costs == {"session": 2.0, "daily": 2.0}
    assert tdir.name in v["source"]


def test_transcript_dirs_include_worktree_rimossi_e_deduplica_per_sessione(tmp_path,
                                                                          monkeypatch):
    main_dir = tmp_path / "factory"
    _home_with_projects(tmp_path, monkeypatch, main_dir, tmp_path / "wt-esterno")
    main_t = ca.transcripts_dir(str(main_dir))
    removed = main_t.parent / (main_t.name + "--claude-worktrees-agent-x")
    other = main_t.parent / (main_t.name + "-altro-progetto")  # stesso prefisso, altro repo
    for d in (main_t, removed, other):
        d.mkdir(parents=True)
    ts = _now_ts()
    # stessa sessione in due cartelle: conta una volta sola, il file più completo
    (main_t / f"{SID}.jsonl").write_text(_line("m1", 1_000_000, ts) + "\n", encoding="utf-8")
    (removed / f"{SID}.jsonl").write_text(
        _line("m1", 1_000_000, ts) + "\n" + _line("m2", 1_000_000, ts) + "\n", encoding="utf-8")
    (other / "altra.jsonl").write_text(_line("o1", 9_000_000, ts) + "\n", encoding="utf-8")
    dirs = ca.transcript_dirs(str(main_dir), main_dir)
    assert dirs == [main_t, removed]
    root = _factory(tmp_path, rules=_rules(("daily", 10.0, "warn")))
    [r] = ca.evaluate({**_ctx(root, dirs[0]), "tdirs": dirs}, ("daily",))["results"]
    assert r["cost_usd"] == 2.0


def test_transcript_dirs_senza_git_resta_la_cartella_del_progetto(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(ca, "factory_checkouts", lambda root: [])
    dirs = ca.transcript_dirs(str(tmp_path / "progetto"), tmp_path)
    assert dirs == [ca.transcripts_dir(str(tmp_path / "progetto"))]
