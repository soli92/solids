"""
Test di tools/db/db_access.py.

Nessun database reale: `_connect` e' sostituita da una connessione finta che registra le
istruzioni, risponde con rowcount configurabili e puo' sollevare errori con SQLSTATE.
La factory di prova (config, registro, .env) vive in tmp_path.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "tools" / "db" / "db_access.py"

_spec = importlib.util.spec_from_file_location("db_access", _SCRIPT)
dba = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dba)

REGISTRY = """
version: 1
environments:
  test:
    label: TEST
    hosts:
      h:
        host: db.test.local
        port: 5432
        credentials:
          - [T_USER, T_PWD]
          - [FALLBACK_USER, FALLBACK_PWD]
      v:
        host_var: VAR_HOST
        default_host: default.local
        port_var: VAR_PORT
        default_port: 9999
        credentials:
          - [NOPE_USER, NOPE_PWD]
    databases:
      app: {host: h, dbname: app, schemas: [appschema]}
      dyn: {host: v, dbname: dyn, schemas: [public]}
  prod:
    hosts:
      h:
        host: db.prod.local
        port: 5432
        credentials:
          - [P_USER, P_PWD]
    databases:
      app: {host: h, dbname: app, schemas: [public]}
"""

# Valore finto, composto a runtime: nessun segreto nel sorgente (scanner di segreti).
_FAKE_PWD = "".join(["s3cr", "#et^<>"])

ENV = f"""# commento
T_USER=tester
T_PWD='{_FAKE_PWD}'
P_USER=prodder
export P_PWD="pp"
"""


class FakeError(Exception):
    def __init__(self, msg: str, sqlstate: str | None = None) -> None:
        super().__init__(msg)
        self.sqlstate = sqlstate


class FakeCursor:
    def __init__(self, conn: "FakeConn") -> None:
        self.conn = conn
        self.description = None
        self.rowcount = -1
        self.statusmessage = None
        self._rows: list = []

    def execute(self, sql: str, params=None) -> None:
        self.conn.executed.append(sql)
        self.conn.params.append(params)
        behaviour = self.conn.behaviour(sql)
        if isinstance(behaviour, Exception):
            raise behaviour
        rows, rowcount = behaviour
        self._rows = list(rows or [])
        self.description = [("c1",), ("c2",)] if rows is not None else None
        self.rowcount = rowcount
        self.statusmessage = "OK"

    def fetchmany(self, n: int):
        return self._rows[:n]


class FakeConn:
    def __init__(self, behaviour) -> None:
        self.behaviour = behaviour
        self.executed: list[str] = []
        self.params: list = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.read_only = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


@pytest.fixture()
def factory(tmp_path: Path) -> Path:
    root = tmp_path / "factory"
    (root / "tools" / "db").mkdir(parents=True)
    (root / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  protected_envs: [prod]\n  pending_ttl_minutes: 30\n  write:\n    enabled: true\n",
        encoding="utf-8")
    (root / "tools" / "db" / "db-targets.yaml").write_text(REGISTRY, encoding="utf-8")
    (root / ".env.db").write_text(ENV, encoding="utf-8")
    return root


@pytest.fixture()
def fake(monkeypatch):
    state: dict = {"behaviour": lambda sql: (None, 3), "params": []}

    def connect(params):
        state["params"].append(params)
        conn = FakeConn(lambda sql: state["behaviour"](sql))
        state["conn"] = conn
        return conn

    monkeypatch.setattr(dba, "_connect", connect)
    return state


def plan(total_cost: float = 10.0, plan_rows: float = 5.0, as_text: bool = False):
    """Risposta di `EXPLAIN (FORMAT JSON)`: una riga con una colonna che contiene il piano."""
    doc = [{"Plan": {"Node Type": "Seq Scan", "Total Cost": total_cost, "Plan Rows": plan_rows}}]
    return ([(json.dumps(doc) if as_text else doc,)], -1)


def _with_plan(inner, total_cost: float = 10.0, plan_rows: float = 5.0):
    """Comportamento del DB finto: EXPLAIN risponde con il piano, il resto con `inner`."""
    return lambda sql: plan(total_cost, plan_rows) if sql.startswith("EXPLAIN") else inner(sql)


def run(root: Path, *argv: str, capsys) -> tuple[int, dict]:
    code = dba.main(["--root", str(root), *argv])
    out = capsys.readouterr().out.strip().splitlines()
    return code, json.loads(out[-1])


# --- parsing -----------------------------------------------------------------

def test_env_parsing_keeps_special_chars_and_strips_quotes(tmp_path):
    p = tmp_path / ".env"
    p.write_text(ENV, encoding="utf-8")
    values = dba.parse_env_file(p)
    assert values["T_PWD"] == "s3cr#et^<>"
    assert values["P_PWD"] == "pp"
    assert "# commento" not in values


def test_split_sql_respects_quotes_comments_and_dollar_quotes():
    sql = ("select ';' as a; -- commento ; finto\n"
           "update t set x = $$a;b$$ where y = 'it''s;';"
           "/* blocco ; /* annidato ; */ */ delete from t;  ;")
    parts = dba.split_sql(sql)
    assert [dba.first_keyword(p["code"]) for p in parts] == ["SELECT", "UPDATE", "DELETE"]
    assert "$$a;b$$" in parts[1]["text"]


def test_split_sql_e_string_backslash_escape():
    parts = dba.split_sql(r"select E'a\';b'; select 1")
    assert len(parts) == 2


@pytest.mark.parametrize("sql", [
    "commit", "BEGIN", "rollback", "start transaction", "end", "savepoint s",
    "SET TRANSACTION READ WRITE", "set session characteristics as transaction read write",
    "set default_transaction_read_only = off", "copy t to '/tmp/x'", "reset all",
    "prepare transaction 'x'", "select 1; commit; delete from t",
])
def test_transaction_control_is_blocked(sql):
    with pytest.raises(dba.ToolError) as exc:
        dba.check_statements(dba.split_sql(sql))
    assert exc.value.payload["error"] == "blocked_statement"


def test_ordinary_set_and_prepare_are_allowed():
    dba.check_statements(dba.split_sql("set search_path = x; prepare p as select 1"))


# --- risoluzione -------------------------------------------------------------

def test_resolve_picks_first_complete_credentials_and_never_exposes_secret(factory):
    reg = dba.load_registry(factory, dba.load_config(factory))
    res = dba.resolve_target(reg, dba.parse_env_file(factory / ".env.db"), "test", "app")
    assert res["public"]["credential_vars"] == ["T_USER", "T_PWD"]
    assert "s3cr#et" not in json.dumps(res["public"])
    assert res["secret"]["password"] == _FAKE_PWD


def test_resolve_host_var_falls_back_to_default(factory):
    reg = dba.load_registry(factory, dba.load_config(factory))
    pub = dba.resolve_target(reg, {"VAR_HOST": "override.local"}, "test", "dyn")["public"]
    assert pub["host"] == "override.local" and pub["port"] == 9999
    pub = dba.resolve_target(reg, {}, "test", "dyn")["public"]
    assert pub["host"] == "default.local" and pub["credential_vars"] is None


def test_targets_lists_without_connecting(factory, fake, capsys):
    code, out = run(factory, "targets", capsys=capsys)
    assert code == 0 and not fake["params"]
    ready = {(t["env"], t["target"]): t["credentials_ready"] for t in out["targets"]}
    assert ready == {("test", "app"): True, ("test", "dyn"): False, ("prod", "app"): True}
    assert "s3cr#et" not in json.dumps(out)


def test_unknown_target_exit_1(factory, fake, capsys):
    code, out = run(factory, "query", "test", "nope", "--sql", "select 1", capsys=capsys)
    assert code == 1 and out["error"] == "unknown_target"


def test_missing_credentials_exit_1(factory, fake, capsys):
    code, out = run(factory, "query", "test", "dyn", "--sql", "select 1", capsys=capsys)
    assert code == 1 and out["error"] == "credentials_missing"
    assert out["expected_vars"] == [["NOPE_USER", "NOPE_PWD"]]


def test_disabled_capability_exit_1(factory, fake, capsys):
    (factory / "factory.config.yaml").write_text("db_access:\n  enabled: false\n", encoding="utf-8")
    code, out = run(factory, "targets", capsys=capsys)
    assert code == 1 and out["error"] == "capability_disabled"


# --- lettura -----------------------------------------------------------------

def test_query_is_read_only_and_always_rolled_back(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([(1, "a"), (2, "b"), (3, "c")], 3)
    code, out = run(factory, "query", "test", "app", "--sql", "select * from t", "--limit", "2",
                    capsys=capsys)
    assert code == 0
    params = fake["params"][0]
    assert "default_transaction_read_only=on" in params["options"]
    assert "search_path=appschema" in params["options"]
    assert fake["conn"].read_only is True
    assert fake["conn"].commits == 0 and fake["conn"].rollbacks >= 1 and fake["conn"].closed
    res = out["results"][0]
    assert res["rows"] == [[1, "a"], [2, "b"]] and res["truncated"] is True


def test_query_write_rejected_by_server_exit_3(factory, fake, capsys):
    fake["behaviour"] = lambda sql: FakeError("cannot execute UPDATE in a read-only transaction",
                                              "25006")
    code, out = run(factory, "query", "test", "app", "--sql", "update t set x=1", capsys=capsys)
    assert code == 3 and out["error"] == "read_only_violation" and "write" in out["hint"]


def test_query_timeout_exit_6(factory, fake, capsys):
    fake["behaviour"] = lambda sql: FakeError("canceling statement due to statement timeout", "57014")
    code, out = run(factory, "query", "test", "app", "--sql", "select count(*) from big", capsys=capsys)
    assert code == 6 and out["error"] == "timeout"


def test_connection_error_is_scrubbed_exit_2(factory, monkeypatch, capsys):
    class OperationalError(Exception):
        pass

    def boom(params):
        raise OperationalError(f"password authentication failed ({params['password']})")

    monkeypatch.setattr(dba, "_connect", boom)
    code, out = run(factory, "check", "test", "app", capsys=capsys)
    assert code == 2 and "s3cr#et" not in json.dumps(out) and "***" in out["message"]


def test_protected_env_forbids_out_file(factory, fake, capsys, tmp_path):
    code, out = run(factory, "query", "prod", "app", "--sql", "select 1",
                    "--out", str(tmp_path / "x.json"), capsys=capsys)
    assert code == 1 and out["error"] == "out_forbidden" and not fake["params"]


def test_protected_env_caps_limit_and_trims_large_output_in_place(factory, fake, capsys):
    big = [(i, "x" * 500) for i in range(400)]
    fake["behaviour"] = _with_plan(lambda sql: (big, 400))
    code, out = run(factory, "query", "prod", "app", "--sql", "select 1", "--limit", "10000",
                    capsys=capsys)
    assert code == 0 and out["limit"] == 500
    res = out["results"][0]
    assert res["truncated_for_size"] is True and "output_file" not in out
    assert len(json.dumps(out).encode()) <= dba.MAX_STDOUT_BYTES


def test_large_output_non_protected_goes_to_file(factory, fake, capsys, tmp_path):
    fake["behaviour"] = lambda sql: ([(i, "x" * 500) for i in range(200)], 200)
    target = tmp_path / "out" / "r.json"
    code, out = run(factory, "query", "test", "app", "--sql", "select 1", "--out", str(target),
                    capsys=capsys)
    assert code == 0 and out["output_file"] == str(target)
    assert len(json.loads(target.read_text(encoding="utf-8"))["results"][0]["rows"]) == 200


# --- scrittura ---------------------------------------------------------------

SQL_W = "update t set x = 1 where id = 7"


def _dry_run(factory, capsys, env="test"):
    code, out = run(factory, "write", env, "app", "--sql", SQL_W, "--dry-run", capsys=capsys)
    assert code == 0, out
    return out


def test_dry_run_rolls_back_and_records_pending(factory, fake, capsys):
    out = _dry_run(factory, capsys)
    assert out["rolled_back"] is True and fake["conn"].commits == 0
    assert "default_transaction_read_only" not in fake["params"][0]["options"]
    assert (factory / ".db-access-state" / "pending" / f"{out['token']}.json").is_file()


def test_commit_requires_matching_token(factory, fake, capsys):
    _dry_run(factory, capsys)
    code, out = run(factory, "write", "test", "app", "--sql", SQL_W + " and 1=1", "--commit",
                    "--token", "deadbeefdeadbeef", capsys=capsys)
    assert code == 4 and out["error"] == "token_mismatch"


def test_commit_without_dry_run_exit_4(factory, fake, capsys):
    token, _ = dba.sql_token("test", "app", "", dba.split_sql(SQL_W))
    code, out = run(factory, "write", "test", "app", "--sql", SQL_W, "--commit", "--token", token,
                    capsys=capsys)
    assert code == 4 and out["error"] == "no_pending_dry_run" and not fake["params"]


def test_commit_happy_path_writes_audit_and_is_not_repeatable(factory, fake, capsys):
    token = _dry_run(factory, capsys)["token"]
    code, out = run(factory, "write", "test", "app", "--sql", SQL_W, "--commit", "--token", token,
                    capsys=capsys)
    assert code == 0 and out["committed"] is True and fake["conn"].commits == 1
    lines = (factory / "deliverables" / "db-access" / "audit-scritture.jsonl").read_text(
        encoding="utf-8").splitlines()
    entry = json.loads(lines[-1])
    assert entry["statements"] == [{"keyword": "UPDATE", "rowcount": 3}] and entry["sql"] == SQL_W
    # idempotenza: lo stesso token non si riusa
    code, out = run(factory, "write", "test", "app", "--sql", SQL_W, "--commit", "--token", token,
                    capsys=capsys)
    assert code == 4 and out["error"] == "no_pending_dry_run"
    assert len((factory / "deliverables" / "db-access" / "audit-scritture.jsonl").read_text(
        encoding="utf-8").splitlines()) == 1


def test_commit_aborts_on_rowcount_drift(factory, fake, capsys):
    token = _dry_run(factory, capsys)["token"]
    fake["behaviour"] = lambda sql: (None, 5)
    code, out = run(factory, "write", "test", "app", "--sql", SQL_W, "--commit", "--token", token,
                    capsys=capsys)
    assert code == 4 and out["error"] == "rowcount_drift"
    assert out["dry_run_rowcounts"] == [3] and out["actual_rowcounts"] == [5]
    assert fake["conn"].commits == 0


def test_commit_expired_dry_run(factory, fake, capsys):
    token = _dry_run(factory, capsys)["token"]
    pf = factory / ".db-access-state" / "pending" / f"{token}.json"
    data = json.loads(pf.read_text(encoding="utf-8"))
    data["created_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat()
    pf.write_text(json.dumps(data), encoding="utf-8")
    code, out = run(factory, "write", "test", "app", "--sql", SQL_W, "--commit", "--token", token,
                    capsys=capsys)
    assert code == 4 and out["error"] == "dry_run_expired"


def test_protected_commit_needs_confirm_env_and_audit_omits_sql(factory, fake, capsys):
    # ambiente protetto ma scrivibile (prod e' in sola lettura di default: qui lo si toglie apposta)
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  protected_envs: [prod]\n  read_only_envs: []\n  write:\n    enabled: true\n", encoding="utf-8")
    token = _dry_run(factory, capsys, env="prod")["token"]
    code, out = run(factory, "write", "prod", "app", "--sql", SQL_W, "--commit", "--token", token,
                    capsys=capsys)
    assert code == 4 and out["error"] == "confirm_env_required"
    code, out = run(factory, "write", "prod", "app", "--sql", SQL_W, "--commit", "--token", token,
                    "--confirm-env", "prod", capsys=capsys)
    assert code == 0
    entry = json.loads((factory / "deliverables" / "db-access" / "audit-scritture.jsonl")
                       .read_text(encoding="utf-8").splitlines()[-1])
    assert "sql" not in entry and entry["sql_sha256"]


def test_write_blocks_embedded_commit_before_connecting(factory, fake, capsys):
    code, out = run(factory, "write", "test", "app", "--sql", "delete from t; commit",
                    "--dry-run", capsys=capsys)
    assert code == 1 and out["error"] == "blocked_statement" and not fake["params"]


def test_write_sql_error_exit_5_rolls_back(factory, fake, capsys):
    fake["behaviour"] = lambda sql: FakeError("permission denied for table t", "42501")
    code, out = run(factory, "write", "test", "app", "--sql", SQL_W, "--dry-run", capsys=capsys)
    assert code == 5 and out["sqlstate"] == "42501"
    assert fake["conn"].commits == 0 and fake["conn"].rollbacks >= 1


# --- prod in sola lettura -----------------------------------------------------

@pytest.mark.parametrize("mode", ["--dry-run", "--commit"])
def test_read_only_env_refuses_any_write_before_connecting(factory, fake, capsys, mode):
    code, out = run(factory, "write", "prod", "app", "--sql", SQL_W, mode, "--token", "x", "--confirm-env", "prod",
                    capsys=capsys)
    assert code == 4 and out["error"] == "read_only_env" and not fake["params"]
    assert "DBA" in out["hint"]


def test_read_only_env_query_suggests_dba_file_not_write(factory, fake, capsys):
    code, out = run(factory, "query", "prod", "app", "--sql", "update t set x = 1", capsys=capsys)
    assert code == 3 and out["error"] == "read_only_violation" and "file .sql" in out["hint"] and not fake["params"]


def test_targets_reports_read_only_envs(factory, fake, capsys):
    code, out = run(factory, "targets", capsys=capsys)
    flags = {(t["env"], t["target"]): t["read_only"] for t in out["targets"]}
    assert flags[("prod", "app")] is True and flags[("test", "app")] is False


# --- validazione della lettura --------------------------------------------------

@pytest.mark.parametrize("sql,error", [
    ("select dblink('host=x', 'delete from t')", "denied_function"),
    ("select pg_sleep(10)", "denied_function"),
    ("select set_config('default_transaction_read_only', 'off', false)", "denied_function"),
    ("select lo_import('/etc/passwd')", "denied_function"),
    ("select nextval('seq')", "denied_function"),
    ("select pg_terminate_backend(123)", "denied_function"),
    ('select "pg_sleep"(1)', "denied_function"),
    ("select utl_http.request('x')", "denied_function"),
    ("with d as (delete from t returning *) select * from d", "read_only_violation"),
    ("select * from t for update", "read_only_violation"),
    ("insert into t values (1)", "read_only_violation"),
    ("show all", "not_a_read"),
    ("explain analyze delete from t", "not_a_read"),
])
def test_read_path_rejects_side_effects_and_writes_before_connecting(factory, fake, capsys, sql, error):
    code, out = run(factory, "query", "test", "app", "--sql", sql, capsys=capsys)
    assert out["error"] == error and not fake["params"]
    assert code == (3 if error == "read_only_violation" else 1)


def test_read_path_ignores_keywords_inside_strings_and_comments(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([("update",)], 1)
    code, out = run(factory, "query", "test", "app", "--sql",
                    "select 'update; delete' as x -- drop table t\n, $$pg_sleep(1)$$ as y", capsys=capsys)
    assert code == 0


def test_read_query_is_wrapped_with_limit_on_the_server(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([(1, "a")], 1)
    code, out = run(factory, "query", "test", "app", "--sql", "select * from t -- commento finale",
                    "--limit", "7", capsys=capsys)
    executed = fake["conn"].executed[0]
    assert code == 0 and executed.startswith("SELECT * FROM (\nselect * from t -- commento finale\n) AS q")
    assert executed.endswith("LIMIT 8")


def test_explain_runs_only_the_plan(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([("Seq Scan on t",)], 1)
    code, out = run(factory, "query", "test", "app", "--sql", "select * from t", "--explain", capsys=capsys)
    assert code == 0 and out["mode"] == "explain"
    assert fake["conn"].executed[0].startswith("EXPLAIN SELECT * FROM (")


def test_write_path_blocks_dblink_but_allows_nextval(factory, fake, capsys):
    code, out = run(factory, "write", "test", "app", "--sql", "select dblink_exec('x', 'delete from t')",
                    "--dry-run", capsys=capsys)
    assert code == 1 and out["error"] == "denied_function" and not fake["params"]
    code, out = run(factory, "write", "test", "app", "--sql", "insert into t (id) values (nextval('s'))",
                    "--dry-run", capsys=capsys)
    assert code == 0


# --- credenziali solo dal .env, registro a piu' host e driver psycopg2 ----------

REGISTRY_MULTI = """
version: 1
environments:
  prod:
    hosts:
      h:
        host: 10.0.0.1
        port: 5432
        credentials:
          - [P_USER, P_PWD]
      other:
        host: 10.0.0.2
        port: 5432
        credentials:
          - [P_USER, P_PWD]
    databases:
      warehouse: {host: h, dbname: warehouse, schemas: [warehouse_core, warehouse_etl], aliases: [magazzino]}
      customers: {host: other, dbname: customers, schemas: [public]}
      lontano: {host: h, dbname: lontano, schemas: []}
services:
  warehouse-admin:
    aliases: [magazzino]
    source: wiki/x.md
    uses: [{target: warehouse, schemas: [warehouse_core, warehouse_etl]}]
  inventory-service:
    source: wiki/y.md
    uses: [{target: customers, schemas: [public]}]
"""


@pytest.fixture()
def factory_multi(factory):
    (factory / "tools" / "db" / "db-targets.yaml").write_text(REGISTRY_MULTI, encoding="utf-8")
    return factory


def test_credentials_come_only_from_the_env_file(factory_multi, fake, capsys):
    # Nessun ripiego fuori dal .env (niente credenziale generica di Windows o altro).
    assert not hasattr(dba, "read_windows_credential")
    reg = dba.load_registry(factory_multi, dba.load_config(factory_multi))
    res = dba.resolve_target(reg, {}, "prod", "warehouse")
    assert res["public"]["credential_source"] is None and res["secret"] is None
    assert "windows_credential" not in res["public"]
    res = dba.resolve_target(reg, {"P_USER": "u", "P_PWD": "segreta"}, "prod", "warehouse")
    assert res["public"]["credential_source"] == "env-file:P_USER" and res["secret"]["user"] == "u"
    code, out = run(factory_multi, "targets", capsys=capsys)
    assert code == 0 and '"pp"' not in json.dumps(out)


def test_example_registry_uses_one_pair_and_fictitious_hosts():
    import yaml as _yaml
    reg = _yaml.safe_load((_REPO_ROOT / "tools" / "db" / "db-targets.example.yaml").read_text(encoding="utf-8"))
    for env, env_def in reg["environments"].items():
        for host_id, host in env_def["hosts"].items():
            assert "windows_credential" not in host, (env, host_id)
            assert [tuple(p) for p in host["credentials"]] == [("DB_USERNAME", "DB_PASSWORD")], (env, host_id)
            assert str(host["default_host"]).endswith(".example.internal"), (env, host_id)
            assert not re.search(r"\d+\.\d+\.\d+\.\d+", str(host["default_host"]))


def test_psycopg2_connection_gets_readonly_session_and_pgcode_is_understood(factory, monkeypatch, capsys):
    class Psycopg2Conn(FakeConn):
        def __setattr__(self, name, value):
            if name == "read_only":
                raise AttributeError(name)
            object.__setattr__(self, name, value)

        def set_session(self, readonly=False):
            object.__setattr__(self, "session_readonly", readonly)

    class Pg2Error(Exception):
        pgcode = "57014"

    holder = {}

    def connect(params):
        conn = Psycopg2Conn.__new__(Psycopg2Conn)
        for key, value in {"behaviour": lambda sql: Pg2Error("timeout"), "executed": [], "params": [],
                           "commits": 0, "rollbacks": 0, "closed": False}.items():
            object.__setattr__(conn, key, value)
        holder["conn"] = conn
        return conn

    monkeypatch.setattr(dba, "_connect", connect)
    code, out = run(factory, "query", "test", "app", "--sql", "select 1", capsys=capsys)
    assert holder["conn"].session_readonly is True and code == 6 and out["error"] == "timeout"


# --- navigazione: locate, databases, tables, describe -------------------------

def test_locate_static_from_service_alias_and_schema(factory_multi, fake, capsys):
    code, out = run(factory_multi, "locate", "prod", "warehouse-admin", capsys=capsys)
    assert code == 0 and not fake["params"]
    assert out["matches"][0] == {"via": "servizio", "service": "warehouse-admin", "target": "warehouse",
                                 "schemas": ["warehouse_core", "warehouse_etl"], "in_env": True,
                                 "source": "wiki/x.md", "unverified": False}
    _, out = run(factory_multi, "locate", "prod", "magazzino", capsys=capsys)
    assert {m["via"] for m in out["matches"]} == {"servizio", "database"}
    _, out = run(factory_multi, "locate", "prod", "warehouse_etl", capsys=capsys)
    assert out["matches"] == [{"via": "schema", "target": "warehouse", "schemas": ["warehouse_etl"]}]


def test_locate_live_searches_catalogs_and_reports_incomplete(factory_multi, fake, capsys):
    fake["behaviour"] = lambda sql: ([("warehouse_core", "ticket_history", "tabella/vista")], 1)
    code, out = run(factory_multi, "locate", "prod", "timeline", "--live", capsys=capsys)
    assert out["live"][0]["objects"][0]["name"] == "ticket_history"
    assert fake["conn"].params[-1] == ("%timeline%", "%timeline%")        # valore passato come parametro
    assert out["complete"] is True and code == 0
    (factory_multi / ".env.db").write_text("", encoding="utf-8")
    code, out = run(factory_multi, "locate", "prod", "timeline", "--live", capsys=capsys)
    assert {"customers", "warehouse"} <= set(out["skipped_no_credentials"])
    assert out["complete"] is False and code == 1


def test_databases_lists_server_databases_and_marks_registered(factory_multi, fake, capsys):
    fake["behaviour"] = lambda sql: ([("warehouse",), ("flags",)], 2)
    code, out = run(factory_multi, "databases", "prod", capsys=capsys)
    host = next(h for h in out["hosts"] if h["host"] == "h")
    assert {d["dbname"]: d["target"] for d in host["databases"]} == {"warehouse": "warehouse", "flags": None}
    assert host["registered_missing"] == ["lontano"] and code == 0


def test_tables_passes_pattern_as_parameter(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([("appschema", "ticket_history", "tabella", 10, "8 kB", "")], 1)
    code, out = run(factory, "tables", "test", "app", "timeline", capsys=capsys)
    assert code == 0 and out["rows"][0][1] == "ticket_history"
    assert fake["conn"].params[0] == ("%timeline%", "", "")
    assert fake["conn"].read_only is True and fake["conn"].commits == 0


def test_describe_collects_columns_constraints_indexes(factory, fake, capsys):
    def behaviour(sql):
        if "from pg_class c join pg_namespace" in sql:
            return [(42, "appschema", "r")], 1
        if "from pg_attribute" in sql:
            return [("uid", "uuid", True, "", "")], 1
        if "from pg_constraint" in sql:
            return [("pk", "PRIMARY KEY (uid)")], 1
        if "from pg_index" in sql:
            return [("pk_idx", "CREATE UNIQUE INDEX pk_idx ON t USING btree (uid)")], 1
        return [], 0
    fake["behaviour"] = behaviour
    code, out = run(factory, "describe", "test", "app", "appschema.t", capsys=capsys)
    obj = out["objects"][0]
    assert code == 0 and obj["columns"][0]["name"] == "uid" and obj["indexes"][0]["definition"] == "btree (uid)"
    fake["behaviour"] = lambda sql: ([], 0)
    code, out = run(factory, "describe", "test", "app", "nope", capsys=capsys)
    assert code == 1 and out["error"] == "not_found"


def test_example_registry_is_consistent():
    import yaml

    data = yaml.safe_load((_REPO_ROOT / "tools" / "db" / "db-targets.example.yaml").read_text(encoding="utf-8"))
    envs = data["environments"]
    assert set(envs) == {"test", "staging", "prod"}
    for env, env_def in envs.items():
        for name, db in env_def["databases"].items():
            assert db["host"] in env_def["hosts"], (env, name)
    for service, entry in data["services"].items():
        assert entry.get("source"), service
        for use in entry["uses"]:
            assert use["target"] in envs["test"]["databases"], (service, use)


def test_application_name_default_has_no_factory_or_ai_term():
    # Il nome della sessione lo vede il server (pg_stat_activity): deve restare neutro.
    import re as _re
    name = dba.DEFAULTS["application_name"]
    assert not _re.search(r"factory|claude|anthropic|\bai\b|agent|llm", name, _re.I), name


# --- timeout per ambiente ------------------------------------------------------

def _config(factory: Path, extra: str = "") -> None:
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  protected_envs: [prod]\n" + extra, encoding="utf-8")


def _options(fake) -> str:
    return fake["params"][-1]["options"]


def test_timeouts_default_values_for_unlisted_env(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([(1, "a")], 1)
    code, out = run(factory, "query", "test", "app", "--sql", "select 1", capsys=capsys)
    assert code == 0
    assert "-c statement_timeout=30000" in _options(fake) and "-c lock_timeout=5000" in _options(fake)
    assert out["timeouts"] == {"statement_timeout_ms": 30000, "lock_timeout_ms": 5000}


def test_prod_gets_stricter_timeouts_and_test_keeps_global(factory, fake, capsys):
    fake["behaviour"] = _with_plan(lambda sql: ([(1, "a")], 1))
    code, out = run(factory, "query", "prod", "app", "--sql", "select 1", capsys=capsys)
    assert code == 0
    assert "-c statement_timeout=15000" in _options(fake) and "-c lock_timeout=3000" in _options(fake)
    assert out["timeouts"] == {"statement_timeout_ms": 15000, "lock_timeout_ms": 3000}
    run(factory, "query", "test", "app", "--sql", "select 1", capsys=capsys)
    assert "-c statement_timeout=30000" in _options(fake) and "-c lock_timeout=5000" in _options(fake)


def test_config_env_override_merges_with_defaults(factory, fake, capsys):
    _config(factory, "  statement_timeout_ms: 20000\n  env_overrides:\n    test: {statement_timeout_ms: 8000}\n"
                     "    prod: {lock_timeout_ms: 1000}\n")
    cfg = dba.load_config(factory)
    assert dba.effective_timeouts(cfg, "test") == {"statement_timeout_ms": 8000, "lock_timeout_ms": 5000}
    assert dba.effective_timeouts(cfg, "prod") == {"statement_timeout_ms": 15000, "lock_timeout_ms": 1000}
    assert dba.effective_timeouts(cfg, "staging") == {"statement_timeout_ms": 20000, "lock_timeout_ms": 5000}
    fake["behaviour"] = lambda sql: ([(1, "a")], 1)
    run(factory, "query", "test", "app", "--sql", "select 1", capsys=capsys)
    assert "-c statement_timeout=8000" in _options(fake) and "-c lock_timeout=5000" in _options(fake)


def test_defaults_are_not_mutated_by_config_loading(factory):
    _config(factory, "  env_overrides:\n    prod: {statement_timeout_ms: 1}\n  cost_gate: {max_total_cost: 5}\n")
    dba.load_config(factory)
    assert dba.DEFAULTS["env_overrides"]["prod"]["statement_timeout_ms"] == 15000
    assert dba.DEFAULTS["cost_gate"]["max_total_cost"] == 1000000


def test_catalog_commands_use_the_env_timeouts(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([], 0)
    code, _ = run(factory, "tables", "prod", "app", capsys=capsys)
    assert code == 0
    assert "-c statement_timeout=15000" in _options(fake) and "-c lock_timeout=3000" in _options(fake)
    run(factory, "tables", "test", "app", capsys=capsys)
    assert "-c statement_timeout=30000" in _options(fake)


def test_statement_timeout_message_names_limit_and_env(factory, fake, capsys):
    fake["behaviour"] = lambda sql: FakeError("canceling statement due to statement timeout", "57014")
    code, out = run(factory, "query", "test", "app", "--sql", "select count(*) from big", capsys=capsys)
    assert code == 6 and out["ok"] is False
    assert out["timeout"] == {"limit": "statement_timeout", "limit_ms": 30000, "env": "test"}
    assert "statement_timeout" in out["message"] and "30000" in out["message"] and "test" in out["message"]


def test_lock_timeout_on_prod_uses_prod_value(factory, fake, capsys):
    fake["behaviour"] = _with_plan(lambda sql: FakeError("canceling statement due to lock timeout", "55P03"))
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from t", capsys=capsys)
    assert code == 6
    assert out["timeout"] == {"limit": "lock_timeout", "limit_ms": 3000, "env": "prod"}


def test_catalog_timeout_names_limit_and_env(factory, fake, capsys):
    fake["behaviour"] = lambda sql: FakeError("canceling statement due to statement timeout", "57014")
    code, out = run(factory, "tables", "prod", "app", capsys=capsys)
    assert code == 6 and out["timeout"] == {"limit": "statement_timeout", "limit_ms": 15000, "env": "prod"}


# --- controllo di costo --------------------------------------------------------

def _non_explain(conn) -> list[str]:
    return [s for s in conn.executed if not s.startswith("EXPLAIN")]


def test_cost_gate_below_threshold_runs_after_explain(factory, fake, capsys):
    fake["behaviour"] = _with_plan(lambda sql: ([(1, "a")], 1), total_cost=1200.5, plan_rows=300)
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from t", capsys=capsys)
    assert code == 0
    executed = fake["conn"].executed
    assert executed[0].startswith("EXPLAIN (FORMAT JSON) SELECT * FROM (\nselect * from t\n) AS q LIMIT 201")
    assert len(executed) == 2 and executed[1].startswith("SELECT * FROM (")
    assert out["cost_gate"]["status"] == "passed"
    assert out["cost_gate"]["estimates"] == [{"index": 1, "total_cost": 1200.5, "plan_rows": 300.0, "exceeded": []}]
    assert fake["conn"].commits == 0 and fake["conn"].rollbacks >= 1 and fake["conn"].closed


def test_cost_gate_never_sends_analyze(factory, fake, capsys):
    fake["behaviour"] = _with_plan(lambda sql: ([(1, "a")], 1))
    run(factory, "query", "prod", "app", "--sql", "select * from t; select 2", capsys=capsys)
    explains = [s for s in fake["conn"].executed if s.startswith("EXPLAIN")]
    assert len(explains) == 2
    assert all(s.startswith("EXPLAIN (FORMAT JSON) ") and "ANALYZE" not in s.upper() for s in explains)


def test_cost_gate_above_cost_blocks_without_running(factory, fake, capsys):
    fake["behaviour"] = _with_plan(lambda sql: ([(1, "a")], 1), total_cost=5_000_000, plan_rows=10)
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from big", capsys=capsys)
    assert code == 4 and out["ok"] is False and out["error"] == "cost_gate"
    assert out["total_cost"] == 5_000_000 and out["plan_rows"] == 10 and out["exceeded"] == ["max_total_cost"]
    assert out["max_total_cost"] == 1000000 and out["max_plan_rows"] == 1000000
    assert "conferma" in out["message"] and "utente" in out["message"] and out["confirm_with"] == "--accept-cost"
    assert _non_explain(fake["conn"]) == [] and fake["conn"].rollbacks >= 1 and fake["conn"].closed


def test_cost_gate_above_rows_blocks_even_with_low_cost(factory, fake, capsys):
    fake["behaviour"] = _with_plan(lambda sql: ([(1, "a")], 1), total_cost=50, plan_rows=2_000_000)
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from big", capsys=capsys)
    assert code == 4 and out["error"] == "cost_gate" and out["exceeded"] == ["max_plan_rows"]
    assert _non_explain(fake["conn"]) == []


def test_cost_gate_reads_plan_returned_as_text(factory, fake, capsys):
    fake["behaviour"] = lambda sql: (plan(9e9, 1, as_text=True) if sql.startswith("EXPLAIN")
                                     else ([(1, "a")], 1))
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from big", capsys=capsys)
    assert code == 4 and out["error"] == "cost_gate"


def test_cost_gate_blocks_when_any_statement_is_over(factory, fake, capsys):
    def behaviour(sql):
        if sql.startswith("EXPLAIN"):
            return plan(9e9, 1) if "from big" in sql else plan(1, 1)
        return ([(1, "a")], 1)

    fake["behaviour"] = behaviour
    code, out = run(factory, "query", "prod", "app", "--sql", "select 1; select * from big", capsys=capsys)
    assert code == 4 and out["estimates"][1]["exceeded"] == ["max_total_cost"] and out["estimates"][0]["exceeded"] == []
    assert _non_explain(fake["conn"]) == []


def test_accept_cost_runs_once_and_is_audited_without_secrets(factory, fake, capsys):
    fake["behaviour"] = _with_plan(lambda sql: ([(1, "a")], 1), total_cost=5_000_000, plan_rows=7)
    argv = ("query", "prod", "app", "--sql", "select * from big")
    code, out = run(factory, *argv, "--accept-cost", capsys=capsys)
    assert code == 0 and len(_non_explain(fake["conn"])) == 1
    assert out["cost_gate"]["status"] == "accepted"
    assert out["cost_gate"]["estimates"][0]["total_cost"] == 5_000_000
    assert out["cost_gate"]["estimates"][0]["plan_rows"] == 7
    audit = factory / "deliverables" / "db-access" / "audit-scritture.jsonl"
    entry = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["event"] == "cost_gate_accepted" and entry["env"] == "prod" and entry["sql_sha256"]
    assert "sql" not in entry and "select * from big" not in json.dumps(entry)
    assert "password" not in json.dumps(entry) and '"pp"' not in json.dumps(entry)
    # la conferma non resta valida: una nuova esecuzione senza l'opzione e' di nuovo bloccata
    code, out = run(factory, *argv, capsys=capsys)
    assert code == 4 and out["error"] == "cost_gate"
    assert len(audit.read_text(encoding="utf-8").splitlines()) == 1


def test_accept_cost_below_threshold_is_not_audited(factory, fake, capsys):
    fake["behaviour"] = _with_plan(lambda sql: ([(1, "a")], 1))
    code, out = run(factory, "query", "prod", "app", "--sql", "select 1", "--accept-cost", capsys=capsys)
    assert code == 0 and out["cost_gate"]["status"] == "passed"
    assert not (factory / "deliverables" / "db-access" / "audit-scritture.jsonl").exists()


def test_accept_cost_audit_failure_blocks_the_query(factory, fake, capsys):
    (factory / "deliverables").write_text("file al posto della cartella", encoding="utf-8")
    fake["behaviour"] = _with_plan(lambda sql: ([(1, "a")], 1), total_cost=5_000_000)
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from big", "--accept-cost", capsys=capsys)
    assert code == 4 and out["error"] == "audit_unwritable" and _non_explain(fake["conn"]) == []


def test_cost_gate_skips_envs_outside_cost_gate_envs(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([(1, "a")], 1)
    code, out = run(factory, "query", "test", "app", "--sql", "select 1", capsys=capsys)
    assert code == 0 and "cost_gate" not in out
    assert not any(s.startswith("EXPLAIN") for s in fake["conn"].executed)


def test_cost_gate_envs_and_thresholds_are_configurable(factory, fake, capsys):
    _config(factory, "  cost_gate:\n    envs: [prod, test]\n    max_total_cost: 100\n")
    fake["behaviour"] = _with_plan(lambda sql: ([(1, "a")], 1), total_cost=500, plan_rows=5)
    code, out = run(factory, "query", "test", "app", "--sql", "select 1", capsys=capsys)
    assert code == 4 and out["error"] == "cost_gate" and out["max_total_cost"] == 100
    assert out["max_plan_rows"] == 1000000                      # chiave non indicata: default
    _config(factory, "  cost_gate:\n    envs: []\n")
    code, _ = run(factory, "query", "prod", "app", "--sql", "select 1", capsys=capsys)
    assert code == 0 and not any(s.startswith("EXPLAIN") for s in fake["conn"].executed)


def test_explain_option_shows_plan_without_cost_gate(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([("Seq Scan on t",)], 1)
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from t", "--explain", capsys=capsys)
    assert code == 0 and out["mode"] == "explain" and "cost_gate" not in out
    assert fake["conn"].executed == ["EXPLAIN SELECT * FROM (\nselect * from t\n) AS q LIMIT 201"]


def test_cost_gate_explain_failure_blocks_the_query(factory, fake, capsys):
    fake["behaviour"] = lambda sql: (FakeError("permission denied for table t", "42501")
                                     if sql.startswith("EXPLAIN") else ([(1, "a")], 1))
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from t", capsys=capsys)
    assert code == 5 and out["ok"] is False and out["error"] == "cost_gate_explain_failed"
    assert "non e' stata eseguita" in out["message"] and out["sqlstate"] == "42501"
    assert _non_explain(fake["conn"]) == [] and fake["conn"].closed


def test_cost_gate_explain_failure_blocks_even_with_accept_cost(factory, fake, capsys):
    fake["behaviour"] = lambda sql: (FakeError("boom", "42501") if sql.startswith("EXPLAIN") else ([(1, "a")], 1))
    code, out = run(factory, "query", "prod", "app", "--sql", "select 1", "--accept-cost", capsys=capsys)
    assert code == 5 and out["error"] == "cost_gate_explain_failed" and _non_explain(fake["conn"]) == []


def test_cost_gate_explain_timeout_blocks_with_timeout_exit(factory, fake, capsys):
    fake["behaviour"] = lambda sql: (FakeError("canceling statement due to statement timeout", "57014")
                                     if sql.startswith("EXPLAIN") else ([(1, "a")], 1))
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from t", capsys=capsys)
    assert code == 6 and out["error"] == "cost_gate_explain_failed"
    assert out["timeout"] == {"limit": "statement_timeout", "limit_ms": 15000, "env": "prod"}
    assert _non_explain(fake["conn"]) == []


def test_cost_gate_unreadable_plan_blocks_the_query(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([("non json",)], -1) if sql.startswith("EXPLAIN") else ([(1, "a")], 1)
    code, out = run(factory, "query", "prod", "app", "--sql", "select * from t", capsys=capsys)
    assert code == 5 and out["error"] == "cost_gate_explain_failed" and _non_explain(fake["conn"]) == []


def test_read_validation_still_runs_before_any_connection_on_prod(factory, fake, capsys):
    code, out = run(factory, "query", "prod", "app", "--sql", "update t set x = 1", capsys=capsys)
    assert code == 3 and not fake["params"]


# --- scrittura spenta per default, sslmode verify-full -------------------------------------------------------

def test_write_is_disabled_by_default(factory, fake, capsys):
    (factory / "factory.config.yaml").write_text("db_access:\n  enabled: true\n", encoding="utf-8")
    assert dba.DEFAULTS["write"] == {"enabled": False}
    for mode in ("--dry-run", "--commit"):
        code, out = run(factory, "write", "test", "app", "--sql", SQL_W, mode, capsys=capsys)
        assert code == 4 and out["error"] == "write_disabled" and not fake["params"]


def test_write_disabled_explicitly_refuses_even_with_a_valid_token(factory, fake, capsys):
    token = _dry_run(factory, capsys)["token"]            # fixture con write.enabled: true
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  write:\n    enabled: false\n", encoding="utf-8")
    fake["params"].clear()
    code, out = run(factory, "write", "test", "app", "--sql", SQL_W, "--commit", "--token", token, capsys=capsys)
    assert code == 4 and out["error"] == "write_disabled" and not fake["params"]


def test_write_enabled_never_writes_on_read_only_envs(factory, fake, capsys):
    code, out = run(factory, "write", "prod", "app", "--sql", SQL_W, "--dry-run", capsys=capsys)
    assert code == 4 and out["error"] == "read_only_env" and not fake["params"]


def test_write_enabled_must_be_boolean_true(factory, fake, capsys):
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  write:\n    enabled: \"yes\"\n", encoding="utf-8")
    code, out = run(factory, "write", "test", "app", "--sql", SQL_W, "--dry-run", capsys=capsys)
    assert code == 4 and out["error"] == "write_disabled"


def test_sslmode_defaults_to_verify_full_without_warning(factory, fake, capsys):
    fake["behaviour"] = lambda sql: ([(1,)], 1)
    code, out = run(factory, "query", "test", "app", "--sql", "select 1", capsys=capsys)
    assert code == 0 and dba.DEFAULTS["sslmode"] == "verify-full"
    assert fake["params"][-1]["sslmode"] == "verify-full"
    assert out["target"]["sslmode"] == "verify-full" and out["target"]["ssl_warning"] is None


def test_weak_sslmode_is_accepted_only_when_declared_and_warns(factory, fake, capsys):
    (factory / "tools" / "db" / "db-targets.yaml").write_text(
        REGISTRY.replace("host: db.test.local", "host: db.test.local\n        sslmode: prefer", 1), encoding="utf-8")
    fake["behaviour"] = lambda sql: ([(1,)], 1)
    code = dba.main(["--root", str(factory), "query", "test", "app", "--sql", "select 1"])
    captured = capsys.readouterr()
    out = json.loads(captured.out.strip().splitlines()[-1])
    assert code == 0 and fake["params"][-1]["sslmode"] == "prefer"
    assert "prefer" in out["target"]["ssl_warning"]
    assert "avviso" in captured.err and "prefer" in captured.err


def test_global_weak_sslmode_in_config_warns_and_unknown_value_is_refused(factory, fake, capsys):
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  sslmode: require\n", encoding="utf-8")
    fake["behaviour"] = lambda sql: ([(1,)], 1)
    code, out = run(factory, "query", "test", "app", "--sql", "select 1", capsys=capsys)
    assert code == 0 and out["target"]["ssl_warning"] and fake["params"][-1]["sslmode"] == "require"
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  sslmode: banana\n", encoding="utf-8")
    code, out = run(factory, "query", "test", "app", "--sql", "select 1", capsys=capsys)
    assert code == 1 and out["error"] == "bad_sslmode"


def test_default_env_file_and_registry_are_neutral():
    assert dba.DEFAULTS["env_file"] == ".env.db" and dba.DEFAULTS["registry"] == "tools/db/db-targets.yaml"
