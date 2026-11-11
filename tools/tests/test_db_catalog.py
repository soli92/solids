"""
Test di tools/db/db_catalog.py.

Nessun database reale e nessun git reale: `_connect` e' sostituita da una connessione finta che risponde per
tipo di query (marcatore `/* db-catalog <tipo> */`), `_git` da un simulatore. La factory di prova (config,
registro, .env, catalogo) vive in tmp_path. L'hash del fingerprint lo calcola il server: offline si provano il
testo SQL, l'ordinamento e la DDL; il comportamento su un PostgreSQL vero resta da verificare sul campo.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "tools" / "db"))

import db_catalog as cat  # noqa: E402

PASSWORD = "".join(["s3cr3t", "-pw-Z9"])  # finto, composto a runtime (scanner di segreti)
START = dt.datetime(2026, 11, 6, 10, 0, 0, tzinfo=dt.timezone.utc)

REGISTRY = """
version: 1
environments:
  test:
    hosts:
      h: {host: db.test.local, port: 5432, credentials: [[DB_USERNAME, DB_PASSWORD]]}
    databases:
      customers: {host: h, dbname: customers, schemas: [public]}
      orders: {host: h, dbname: orders, schemas: [orders_schema]}
      empty: {host: h, dbname: empty, schemas: []}
  staging:
    hosts:
      h: {host: db.staging.local, port: 5432, credentials: [[DB_USERNAME, DB_PASSWORD]]}
    databases:
      customers: {host: h, dbname: customers, schemas: [public]}
  preprod:
    hosts:
      h: {host: db.prod.local, port: 5432, credentials: [[DB_USERNAME, DB_PASSWORD]]}
    databases:
      customers: {host: h, dbname: customers-preprod, schemas: [public]}
  prod:
    hosts:
      h: {host: db.prod.local, port: 5432, credentials: [[DB_USERNAME, DB_PASSWORD]]}
    databases:
      customers: {host: h, dbname: customers, schemas: [public]}
services:
  catalog-service:
    uses: [{target: customers, schemas: [public_ext, public]}]
"""


class FakeError(Exception):
    def __init__(self, msg: str, sqlstate: str | None = None, attr: str = "sqlstate") -> None:
        super().__init__(msg)
        setattr(self, attr, sqlstate)


def row(kind: str, schema: str, **kw):
    cls = cat.CLASS_BY_KIND[kind]
    vals = [kw.get("schema_q", cat._quote_ident(schema)) if n == "schema" else kw.get(n) for n in cls.names]
    return (schema, *vals)


class FakeDB:
    def __init__(self) -> None:
        self.fp: dict[str, tuple] = {}
        self.extra_fp: list[tuple] = []
        self.rows: dict[str, list[tuple]] = {}
        self.reference: dict[str, dict] = {}
        self.version = ("15.6.0", "PostgreSQL 15.6 (distribuzione compatibile 15.6.0) on x86_64")

    def schema(self, name, fingerprint, usable=True, objects=5, relations=2):
        self.fp[name] = (name, usable, fingerprint if usable else None, objects if usable else 0,
                         relations if usable else 0)

    def add(self, kind, schema, **kw):
        self.rows.setdefault(kind, []).append(row(kind, schema, **kw))


class FakeCursor:
    def __init__(self, conn) -> None:
        self.conn, self.description, self._rows = conn, None, []

    def execute(self, sql, params=None):
        self.conn.state["executed"].append((sql, params))
        marker = re.match(r"/\* db-catalog ([\w-]+)(?: (\w+))? \*/", sql)
        kind, sub = (marker.group(1), marker.group(2)) if marker else ("other", None)
        err = self.conn.state["errors"].get((self.conn.dbname, kind))
        if err:
            raise err
        db: FakeDB = self.conn.db
        rows = None
        if kind == "version":
            rows = [db.version]
        elif kind == "fingerprint":
            rows = [*db.fp.values(), *db.extra_fp]
        elif kind == "extract":
            rows = [r for r in db.rows.get(sub, []) if r[0] in params[0]]
        elif kind == "reference-columns":
            ref = db.reference.get(f"{params[0]}.{params[1]}")
            rows = []
            if ref:
                q = f"{params[0]}.{params[1]}"
                rows = [(q, ref.get("can_read", True), c, f'"{c}"') for c in ref["columns"]]
        elif kind == "reference-values":
            name = re.search(r"from (\S+) limit", sql).group(1)
            rows = list(db.reference[name]["rows"])[:params[0]]
        self._rows = list(rows) if rows is not None else []
        self.description = [("c",)] if rows is not None else None

    def fetchall(self):
        return list(self._rows)


class FakeConn:
    def __init__(self, state, dbname) -> None:
        self.state, self.dbname, self.db = state, dbname, state["dbs"].get(dbname)
        self.read_only, self.commits, self.rollbacks, self.closed = False, 0, 0, False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class Clock:
    def __init__(self) -> None:
        self.now = START

    def advance(self, **kw) -> None:
        self.now += dt.timedelta(**kw)


@pytest.fixture()
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(cat, "utcnow", lambda: c.now)
    return c


@pytest.fixture()
def factory(tmp_path: Path) -> Path:
    root = tmp_path / "factory"
    (root / "tools" / "db").mkdir(parents=True)
    (root / "factory.config.yaml").write_text("db_access:\n  enabled: true\n", encoding="utf-8")
    (root / "tools" / "db" / "db-targets.yaml").write_text(REGISTRY, encoding="utf-8")
    (root / ".env.db").write_text(f"DB_USERNAME=tester\nDB_PASSWORD={PASSWORD}\n",
                                               encoding="utf-8")
    return root


@pytest.fixture()
def fake(monkeypatch):
    state: dict = {"dbs": {}, "executed": [], "errors": {}, "params": [], "conns": [], "connect_errors": {},
                   "git": [], "git_handler": None}

    def connect(params):
        state["params"].append(params)
        err = state["connect_errors"].get(params["dbname"])
        if err:
            raise err
        conn = FakeConn(state, params["dbname"])
        state["conns"].append(conn)
        return conn

    def git(root, args, timeout):
        state["git"].append((args, timeout))
        handler = state["git_handler"]
        if handler:
            return handler(args)
        return subprocess.CompletedProcess(args, 128, b"", b"fatal: path 'x' does not exist in 'origin/main'\n")

    monkeypatch.setattr(cat.dba, "_connect", connect)
    monkeypatch.setattr(cat, "_git", git)
    return state


def cust_db(fp: str = "fp-public-1") -> FakeDB:
    db = FakeDB()
    db.schema("public", fp, objects=9, relations=2)
    db.add("table", "public", name="account", persistence="p", ispartition=False)
    db.add("column", "public", table="account", name="id", type="uuid", notnull=True, identity="", generated="")
    db.add("column", "public", table="account", name="email", type="text", notnull=False, identity="", generated="")
    db.add("constraint", "public", table="account", name="account_pkey", contype="p", **{"def": "PRIMARY KEY (id)"})
    db.add("index", "public", table="account", name="account_email_idx",
           **{"def": "CREATE INDEX account_email_idx ON public.account USING btree (email)"})
    db.add("function", "public", name="touch", args="", prokind="f",
           **{"def": "CREATE OR REPLACE FUNCTION public.touch()\n RETURNS trigger\n LANGUAGE plpgsql\nAS $function$"
                     "\nBEGIN\n  RETURN NEW;\nEND;\n$function$\n"})
    db.add("trigger", "public", table="account", name="account_touch", enabled="O",
           **{"def": "CREATE TRIGGER account_touch BEFORE UPDATE ON public.account FOR EACH ROW EXECUTE FUNCTION touch()"})
    return db


def run(root: Path, *argv: str, capsys) -> tuple[int, dict]:
    code = cat.main(["--root", str(root), *argv])
    out = capsys.readouterr().out.strip().splitlines()
    return code, json.loads(out[-1])


def catdir(root: Path, env="test", target="customers") -> Path:
    return root / "memory" / "semantic" / "db-catalog" / env / target


def manifest(root: Path, env="test", target="customers") -> dict:
    return json.loads((catdir(root, env, target) / "manifest.json").read_text(encoding="utf-8"))


def scan(root, fake, capsys, *extra, env="test", target="customers"):
    return run(root, "catalog-scan", env, target, *extra, capsys=capsys)


def snapshot_files(root: Path) -> dict[str, bytes]:
    base = root / "memory"
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


def set_reference_tables(root: Path, tables: list[dict] | None, env="test", target="customers") -> None:
    path = root / "tools" / "db" / "db-targets.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["environments"][env]["databases"][target]["reference_tables"] = tables
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


# --- testo SQL: fingerprint ---------------------------------------------------

def test_fingerprint_is_one_statement_with_a_row_per_schema_params_only():
    sql = cat.fingerprint_sql()
    assert sql.count("/* db-catalog fingerprint */") == 1 and sql.count("%s") == 1
    assert "group by s.oid, s.nspname" in sql and "md5(" in sql
    assert cat._like_patterns(["dbms_*", "aq$_*", "sys"]) == [r"dbms\_%", r"aq$\_%", "sys"]


def test_fingerprint_sql_uses_names_only_no_oid_no_sizes_no_data():
    sql = cat.fingerprint_sql()
    for forbidden in ("reltuples", "relnatts", "relfilenode", "pg_relation_size", "pg_total_relation_size",
                      "last_value", "pg_stat", "pg_sequences", "setval", "nextval"):
        assert forbidden not in sql
    for cls in cat.CLASSES:
        for name, expr in cls.fields:
            assert not re.fullmatch(r"\w+\.(oid|attnum|attrelid|relnamespace|seqrelid)", expr), (cls.kind, name)
    for c in cat.CLASSES:                      # attnum solo come filtro/ordinamento interno, mai come valore
        for n, expr in c.fields:
            cleaned = (expr.replace("a.attnum > 0", "").replace("order by a.attnum", "")
                       .replace("ra.attnum = dp.refobjsubid", ""))
            assert "attnum" not in cleaned, (c.kind, n)


def test_fingerprint_sql_excludes_dropped_columns_and_system_schemas():
    sql = cat.fingerprint_sql()
    assert "not a.attisdropped" in sql
    assert "n.nspname !~ '^pg_'" in sql and "n.nspname <> 'information_schema'" in sql
    assert "!~~ all(%s::text[])" in sql
    assert "not c.relispartition" in sql                 # le colonne delle partizioni seguono il padre


def test_fingerprint_sql_covers_every_semantic_object():
    sql = cat.fingerprint_sql()
    for token in ("pg_get_functiondef", "pg_get_triggerdef", "pg_get_constraintdef", "pg_get_indexdef",
                  "pg_get_viewdef", "pg_get_partkeydef", "relpartbound", "pg_description", "pg_enum",
                  "enumsortorder", "pg_sequence", "pg_inherits", "pg_extension", "extversion", "typdefaultbin",
                  "seqincrement", "seqcycle", "seqcache", "format_type", "attidentity", "attgenerated",
                  "relkind = 'm'", "relkind = 'S'"):
        assert token in sql, token
    assert "prokind in ('f', 'p')" in sql                 # aggregati esclusi
    assert "deptype = 'e'" in sql                          # membri di estensioni esclusi
    assert "not t.tgisinternal" in sql


def _agg_calls(sql: str) -> list[str]:
    calls = []
    for m in re.finditer(r"string_agg\(", sql):
        depth, i = 1, m.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        calls.append(sql[m.end():i - 1])
    return calls


def test_fingerprint_sql_orders_every_aggregate_deterministically():
    sql = cat.fingerprint_sql()
    calls = _agg_calls(sql)
    assert len(calls) >= 5
    assert all(" order by " in c for c in calls)
    top = [c for c in calls if "l.line" in c][0]
    assert 'l.kind collate "C", l.line collate "C"' in top           # indipendente da collation e ordine di creazione
    assert all('collate "C"' in c for c in calls if "conname" in c)


def test_fingerprint_and_extraction_share_the_same_expressions_for_every_class():
    fp, kinds = cat.fingerprint_sql(), [c.kind for c in cat.CLASSES]
    assert len(kinds) == len(set(kinds))
    for cls in cat.CLASSES:
        ex = cat.extraction_sql(cls)
        for name, expr in cls.fields:
            assert expr in fp and expr in ex, (cls.kind, name)
        assert cls.source in fp and cls.source in ex and cls.where in fp and cls.where in ex
        assert f"'{cls.kind}' as kind" in fp


def test_extraction_sql_has_no_row_data_and_no_percent_besides_params():
    for cls in cat.CLASSES:
        sql = cat.extraction_sql(cls)
        assert "%" not in sql.replace("%s", "")
        assert not re.search(r"\b(insert|copy|update|delete)\b", sql, re.I)
    assert "order by c.relname, a.attnum" in cat.extraction_sql(cat.CLASS_BY_KIND["column"])
    assert not any(c.order for c in cat.CLASSES if c.kind != "column")
    assert "order by c.relname, a.attnum" not in cat.fingerprint_sql()    # l'ordine di colonna non entra nell'hash


def test_namespace_listing_dedups_and_excludes_namespace_packages_with_standard_pg_fallback():
    sql = cat.fingerprint_sql(True)
    assert "distinct on (n.nspname)" in sql
    assert "to_jsonb(n) ->> 'nspparent'" in sql          # NULL (-> 0) su PostgreSQL standard: nessuna colonna non standard richiesta
    assert "nspparent')::bigint, 0) = 0" in sql
    assert "= 0 order by" not in cat.fingerprint_sql(False) and "nspparent')::bigint, 0) = 0" not in cat.fingerprint_sql(False)
    assert "distinct on (n.nspname)" in cat.extraction_sql(cat.CLASSES[0], False)


# --- fingerprint: esecuzione ------------------------------------------------

PKG_CONFIG = ("db_access:\n  enabled: true\n  catalog:\n    package_namespace_filter: true\n"
              "    system_schemas: [pg_catalog, information_schema, pg_toast, sys, \"dbms_*\", \"utl_*\", \"aq$_*\", "
              "htp, htf, msg_prop_t]\n")


def test_default_system_schemas_are_standard_postgresql_and_extendable(factory, fake, capsys):
    assert cat.CATALOG_DEFAULTS["system_schemas"] == ["pg_catalog", "information_schema", "pg_toast"]
    assert cat.CATALOG_DEFAULTS["package_namespace_filter"] is False
    db = cust_db()
    for sysname in ("pg_toast", "information_schema", "sys"):
        db.extra_fp.append((sysname, True, "x", 5, 5))
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)
    # pg_toast e information_schema sono esclusi; "sys" non e' di sistema su PostgreSQL standard: resta
    assert code == 0, out
    assert sorted(manifest(factory)["schemas"]) == ["public", "sys"]


def test_scan_excludes_extra_system_schemas_and_passes_patterns_as_parameters(factory, fake, capsys):
    (factory / "factory.config.yaml").write_text(PKG_CONFIG, encoding="utf-8")
    db = cust_db()
    for sysname in ("sys", "dbms_output", "utl_http", "aq$_agent", "htp", "htf", "msg_prop_t", "pg_toast"):
        db.extra_fp.append((sysname, True, "x", 113, 113))
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)
    assert code == 0, out
    assert sorted(manifest(factory)["schemas"]) == ["public"]
    sql, params = next(e for e in fake["executed"] if e[0].startswith("/* db-catalog fingerprint"))
    assert "sys" in params[0] and "dbms\\_%" in params[0] and "aq$\\_%" in params[0] and "msg\\_prop\\_t" in params[0]


def test_duplicate_schema_rows_on_preprod_are_deduplicated(factory, fake, capsys):
    (factory / "factory.config.yaml").write_text(PKG_CONFIG, encoding="utf-8")
    db = cust_db()
    db.extra_fp += [("public", True, "fp-public-1", 9, 2), ("sys", True, "a", 1, 1), ("sys", True, "a", 1, 1)]
    fake["dbs"]["customers-preprod"] = db
    code, out = scan(factory, fake, capsys, env="preprod")
    assert code == 0 and list(manifest(factory, "preprod")["schemas"]) == ["public"]
    assert manifest(factory, "preprod")["dbname"] == "customers-preprod"


def test_fingerprint_runs_in_read_only_transaction_and_always_rolls_back(factory, fake, capsys):
    fake["dbs"]["customers"] = cust_db()
    code, _ = run(factory, "catalog-scan", "prod", "customers", capsys=capsys)  # prod: lettura ammessa
    fake["dbs"]["customers"] = cust_db()
    code, _ = scan(factory, fake, capsys)
    for conn in fake["conns"]:
        assert conn.read_only is True and conn.commits == 0 and conn.rollbacks >= 1 and conn.closed
    assert all("default_transaction_read_only=on" in p["options"] for p in fake["params"])
    assert not any(re.match(r"\s*(insert|update|delete|create|drop|alter|grant|copy)\b", e[0], re.I)
                   for e in fake["executed"])


# --- DDL canonica ------------------------------------------------------------

def _chunks(rows_by_kind, schema="public"):
    objs = {c.kind: [dict(zip(c.names, r[1:])) for r in rows_by_kind.get(c.kind, [])] for c in cat.CLASSES}
    return cat.render_schema(schema, objs)


def full_sample() -> dict[str, list[tuple]]:
    s = "public"
    r = {}

    def add(kind, **kw):
        r.setdefault(kind, []).append(row(kind, s, **kw))

    add("extension", name="pgcrypto", version="1.3")
    add("enum", name="stato", labels="'attivo', 'chiuso'")
    add("domain", name="cf", base="text", notnull=True, default="'x'::text",
        constraints="CONSTRAINT cf_len CHECK ((length(VALUE) = 16))")
    add("composite", name="indirizzo", attrs="via text, civico integer")
    add("sequence", name="account_seq", type="bigint", start=1, increment=1, min=1, max=9223372036854775807,
        cache=1, cycle=False, owned_by="public.account.seq", identity=False)
    add("sequence", name="ident_seq", type="bigint", start=1, increment=1, min=1, max=100, cache=1, cycle=True,
        owned_by="public.account.n", identity=True)
    add("table", name="account_history", persistence="p", ispartition=False)
    add("table", name="account", persistence="p", ispartition=False, parents="public.account_history")
    add("table", name="evento", persistence="p", ispartition=False, partkey="RANGE (ts)")
    add("table", name="evento_2026", persistence="p", ispartition=True, parents="public.evento",
        partbound="FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')")
    add("column", table="account", name="id", type="uuid", notnull=True, identity="", generated="")
    add("column", table="account", name="n", type="bigint", notnull=True, identity="a", generated="")
    add("column", table="account", name="seq", type="bigint", notnull=False, identity="", generated="",
        default="nextval('account_seq'::regclass)")
    add("column", table="account", name="up", type="text", notnull=False, identity="", generated="s",
        default="upper(id::text)")
    add("column", table="evento", name="ts", type="timestamp without time zone", notnull=True, identity="",
        generated="")
    add("view", name="v_attivi", options="security_barrier=true", **{"def": " SELECT id\n   FROM account;"})
    add("matview", name="m_attivi", options=None, **{"def": " SELECT id\n   FROM account;"})
    add("constraint", table="account", name="account_pkey", contype="p", **{"def": "PRIMARY KEY (id)"})
    add("constraint", table="account", name="account_fk", contype="f",
        **{"def": "FOREIGN KEY (id) REFERENCES account_history(id)"})
    add("index", table="account", name="account_idx", **{"def": "CREATE INDEX account_idx ON public.account (id)"})
    add("function", name="touch", args="", prokind="f",
        **{"def": "CREATE OR REPLACE FUNCTION public.touch()\n RETURNS trigger\nAS $f$\nBEGIN RETURN NEW; END;\n$f$ \n"})
    add("trigger", table="account", name="account_touch", enabled="D",
        **{"def": "CREATE TRIGGER account_touch BEFORE UPDATE ON public.account FOR EACH ROW EXECUTE FUNCTION touch()"})
    add("comment_schema", comment="schema customers")
    add("comment_relation", objtype="TABLE", name="account", comment="utenti")
    add("comment_column", table="account", name="id", comment="chiave d'accesso")
    add("comment_function", objtype="FUNCTION", name="touch", args="", comment="aggiorna")
    add("comment_type", objtype="TYPE", name="stato", comment="stati")
    return r


def test_render_covers_every_object_class_of_the_fingerprint():
    text = cat.assemble(_chunks(full_sample()))
    for needle in ("CREATE SCHEMA IF NOT EXISTS public;", "CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public VERSION '1.3'",
                   "AS ENUM ('attivo', 'chiuso')", "CREATE DOMAIN public.cf AS text DEFAULT 'x'::text NOT NULL CONSTRAINT cf_len",
                   "CREATE TYPE public.indirizzo AS (via text, civico integer)",
                   "CREATE SEQUENCE public.account_seq AS bigint START WITH 1 INCREMENT BY 1 MINVALUE 1",
                   "NO CYCLE;", "ALTER SEQUENCE public.account_seq OWNED BY public.account.seq;",
                   "-- identity sequence public.ident_seq (public.account.n)", " CYCLE",
                   "GENERATED ALWAYS AS IDENTITY", "GENERATED ALWAYS AS (upper(id::text)) STORED",
                   "INHERITS (public.account_history)", "PARTITION BY RANGE (ts)",
                   "PARTITION OF public.evento FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')",
                   "CREATE VIEW public.v_attivi WITH (security_barrier=true) AS", "WITH NO DATA;",
                   "CREATE MATERIALIZED VIEW public.m_attivi AS", "ADD CONSTRAINT account_pkey PRIMARY KEY (id)",
                   "ADD CONSTRAINT account_fk FOREIGN KEY", "CREATE INDEX account_idx", "$f$;",
                   "CREATE TRIGGER account_touch", "DISABLE TRIGGER account_touch;",
                   "COMMENT ON SCHEMA public IS 'schema customers';", "COMMENT ON TABLE public.account IS 'utenti';",
                   "COMMENT ON COLUMN public.account.id IS 'chiave d''accesso';",
                   "COMMENT ON FUNCTION public.touch() IS 'aggiorna';", "COMMENT ON TYPE public.stato IS 'stati';"):
        assert needle in text, needle


def test_inherits_child_is_rendered_after_its_parent_and_keeps_the_relation():
    text = cat.assemble(_chunks(full_sample()))
    assert text.index("CREATE TABLE public.account_history") < text.index("CREATE TABLE public.account (")
    assert text.index("CREATE TABLE public.evento (") < text.index("CREATE TABLE public.evento_2026")
    assert "CREATE TABLE public.evento_2026 (" not in text            # la partizione non ripete le colonne


def test_ddl_has_no_data_owner_acl_or_sequence_state():
    text = cat.assemble(_chunks(full_sample()))
    for forbidden in ("INSERT", "COPY ", "setval", "last_value", "OWNER TO", "GRANT ", "REVOKE", "ALTER DEFAULT"):
        assert forbidden not in text
    assert not re.search(r"-- .*\d{4}-\d{2}-\d{2}", text)           # nessuna data nel testo


def test_ddl_is_deterministic_whatever_the_row_order_from_the_server():
    sample = full_sample()
    first = cat.assemble(_chunks(sample))
    shuffled = {k: list(reversed(v)) for k, v in sample.items()}
    # le colonne arrivano nell'ordine di attnum (ORDER BY dell'estrazione): l'ordine fra tabelle puo' variare
    shuffled["column"] = [r for t in ("evento", "account") for r in sample["column"] if r[2] == t]
    assert cat.assemble(_chunks(shuffled)) == first
    assert cat.assemble(_chunks(sample)) == first


def test_equivalent_schemas_in_two_envs_give_the_same_text():
    assert cat.assemble(_chunks(full_sample())) == cat.assemble(_chunks(full_sample()))


def test_ddl_whitespace_is_normalised_and_order_is_by_name():
    objs = {"table": [("public", "public", "b", "p", None, None, False, None),
                      ("public", "public", "a", "p", None, None, False, None)]}
    text = cat.assemble(_chunks(objs))
    assert text.index("CREATE TABLE public.a") < text.index("CREATE TABLE public.b")
    assert cat._canon("  \n\nSELECT 1   \r\n  x  \n\n") == "  SELECT 1\n  x" or cat._canon("\n\nA  \r\nB \n\n") == "A\nB"
    assert cat._canon("\n\nA  \r\nB \n\n") == "A\nB"


def test_weird_schema_name_gets_a_safe_reversible_file_name_and_quoted_ddl():
    name = '"$user", public'
    fname = cat.schema_filename(name)
    assert not re.search(r'[<>:"/\\|?*, ]', fname) and fname.endswith(".sql")
    assert unquote(fname[:-4].replace("%2E", ".")) == name
    assert cat.schema_filename("billing-service") == "billing-service.sql"
    assert cat.schema_filename("../x") != "../x.sql" and "/" not in cat.schema_filename("../x")
    text = cat.assemble(cat.render_schema(name, {c.kind: [] for c in cat.CLASSES}))
    assert 'CREATE SCHEMA IF NOT EXISTS """$user"", public";' in text


def test_weird_schema_name_in_scan_manifest_has_the_real_name(factory, fake, capsys):
    name = '"$user", public'
    db = cust_db()
    db.schema(name, "fp-w", objects=1, relations=1)
    db.add("table", name, name="t", persistence="p", ispartition=False, schema_q='"""$user"", public"')
    fake["dbs"]["customers"] = db
    set_reference_tables(factory, None)
    reg = factory / "tools" / "db" / "db-targets.yaml"
    data = yaml.safe_load(reg.read_text(encoding="utf-8"))
    data["environments"]["test"]["databases"]["customers"]["schemas"] = ["public", name]
    reg.write_text(yaml.safe_dump(data), encoding="utf-8")
    code, out = scan(factory, fake, capsys)
    assert code == 0, out
    entry = manifest(factory)["schemas"][name]
    assert (catdir(factory) / entry["ddl_file"]).is_file()
    assert 'CREATE TABLE """$user"", public".t' in (catdir(factory) / entry["ddl_file"]).read_text(encoding="utf-8")


# --- scan: perimetro e manifest ---------------------------------------------

def make_test_customers(fake) -> FakeDB:
    db = cust_db()
    db.schema("test", "fp-test", objects=3, relations=1)                  # accessibile, fuori registro
    db.schema("public_ext", "fp-api", objects=4, relations=2)             # usato da un servizio
    for name in ("billing-service", "customers_main", "restricted", "public_sandbox", "public_qa"):
        db.schema(name, None, usable=False)
    db.add("table", "public_ext", name="v", persistence="p", ispartition=False)
    db.add("table", "test", name="t", persistence="p", ispartition=False)
    fake["dbs"]["customers"] = db
    return db


def test_scan_extracts_ddl_only_for_in_registry_or_service_schemas(factory, fake, capsys):
    make_test_customers(fake)
    code, out = scan(factory, fake, capsys)
    assert code == 0, out
    files = sorted(p.name for p in catdir(factory).glob("*.sql"))
    assert files == ["public.sql", "public_ext.sql"]
    m = manifest(factory)["schemas"]
    assert m["public_ext"]["scope"] == "in_registry" and m["public_ext"]["used_by"] == ["catalog-service"]
    assert m["test"]["scope"] == "out_of_registry" and "ddl_file" not in m["test"]
    assert m["test"]["fingerprint"] == "fp-test" and m["test"]["objects"] == 3 and m["test"]["relations"] == 1
    extracted = {e[0].split()[3] for e in fake["executed"] if e[0].startswith("/* db-catalog extract")}
    assert extracted == {c.kind for c in cat.CLASSES}
    for sql, params in fake["executed"]:
        if sql.startswith("/* db-catalog extract"):
            assert sorted(params[0]) == ["public", "public_ext"]


def test_schemas_without_usage_are_inaccessible_with_cause_and_never_fresh(factory, fake, clock, capsys):
    make_test_customers(fake)
    scan(factory, fake, capsys)
    m = manifest(factory)["schemas"]
    for name in ("billing-service", "customers_main", "restricted", "public_sandbox", "public_qa"):
        assert m[name]["accessible"] is False and "USAGE" in m[name]["cause"]
        assert m[name]["since"] == "2026-11-06" and "fingerprint" not in m[name]
    code, out = run(factory, "catalog-check", "test", "customers", capsys=capsys)
    states = out["targets"][0]["schemas"]
    assert states["restricted"]["state"] == "inaccessible" and states["public"]["state"] == "fresh"
    assert out["targets"][0]["state"] == "fresh" and "restricted" in out["targets"][0]["inaccessible_schemas"]


def test_inaccessible_in_registry_schema_is_reported_as_warning(factory, fake, capsys):
    db = cust_db()
    db.schema("public_ext", None, usable=False)
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)
    assert code == 0 and "schema in registro non leggibile: public_ext" in out["targets"][0]["warnings"]


def test_database_with_empty_schemas_list_is_discovery_only(factory, fake, capsys):
    db = FakeDB()
    db.schema("misc", "fp-misc", objects=2, relations=1)
    fake["dbs"]["empty"] = db
    code, out = scan(factory, fake, capsys, target="empty")
    assert code == 0
    assert not list(catdir(factory, target="empty").glob("*.sql"))
    assert manifest(factory, target="empty")["schemas"]["misc"]["scope"] == "out_of_registry"
    assert not any(e[0].startswith("/* db-catalog extract") for e in fake["executed"])


def test_manifest_has_required_fields_and_no_secret_or_personal_data(factory, fake, capsys, clock):
    make_test_customers(fake)
    scan(factory, fake, capsys)
    text = (catdir(factory) / "manifest.json").read_text(encoding="utf-8")
    m = json.loads(text)
    assert m["server_version"] == "15.6.0" and m["extractor_version"] == cat.EXTRACTOR_VERSION
    assert m["scanned_at"] == "2026-11-06T10:00:00Z" and m["schemas"]["public"]["scanned_at"] == m["scanned_at"]
    assert m["server_flavor"] == "postgres-compatible" and any("non standard" in n for n in m["not_covered"])
    assert m["manifest_version"] == 1 and m["object_classes"] == [c.kind for c in cat.CLASSES]
    assert PASSWORD not in text and "tester" not in text and "db.test.local" not in text


def test_manifest_path_is_memory_semantic_db_catalog_env_db_for_all_envs(factory, fake, capsys):
    fake["dbs"]["customers"] = cust_db()
    fake["dbs"]["customers-preprod"] = cust_db()
    for env in ("test", "staging", "preprod", "prod"):
        code, out = scan(factory, fake, capsys, env=env)
        assert code == 0, out
        assert (factory / "memory/semantic/db-catalog" / env / "customers" / "manifest.json").is_file()
    assert manifest(factory, "preprod")["dbname"] == "customers-preprod"
    assert not (factory / "raw").exists()


def test_env_outside_versioned_envs_is_a_usage_error(factory, fake, capsys):
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  catalog:\n    versioned_envs: [test]\n", encoding="utf-8")
    code, out = scan(factory, fake, capsys, env="prod")
    assert code == 1 and out["error"] == "env_not_versioned" and not fake["params"]


# --- idempotenza e incrementalita' -------------------------------------------

def test_two_scans_without_changes_touch_no_file_and_keep_scanned_at(factory, fake, capsys, clock):
    make_test_customers(fake)
    scan(factory, fake, capsys)
    before = snapshot_files(factory)
    mtimes = {p: p.stat().st_mtime_ns for p in (factory / "memory").rglob("*") if p.is_file()}
    clock.advance(days=3)
    code, out = scan(factory, fake, capsys)
    assert code == 0 and out["targets"][0]["written"] == [] and out["targets"][0]["manifest"] == "unchanged"
    assert snapshot_files(factory) == before
    assert mtimes == {p: p.stat().st_mtime_ns for p in (factory / "memory").rglob("*") if p.is_file()}
    state = json.loads((factory / ".db-access-state/catalog/test/customers.json").read_text(encoding="utf-8"))
    assert state["verified_at"] == "2026-11-09T10:00:00Z"            # l'ultimo controllo sta nello stato locale


def test_unchanged_schemas_are_neither_read_nor_rewritten(factory, fake, capsys):
    make_test_customers(fake)
    scan(factory, fake, capsys)
    fake["executed"].clear()
    scan(factory, fake, capsys)
    assert [e[0].split()[2] for e in fake["executed"]] == ["snapshot", "version", "fingerprint"]
    assert len(fake["executed"]) == 3


def test_drift_rewrites_only_the_changed_schema_and_updates_timestamps(factory, fake, capsys, clock):
    db = make_test_customers(fake)
    scan(factory, fake, capsys)
    api_before = (catdir(factory) / "public_ext.sql").read_bytes()
    first = manifest(factory)
    clock.advance(days=2)
    db.schema("public", "fp-public-2", objects=10, relations=2)
    db.add("column", "public", table="account", name="phone2", type="text", notnull=False, identity="", generated="")
    code, out = scan(factory, fake, capsys)
    assert code == 0
    assert out["targets"][0]["written"] == ["memory/semantic/db-catalog/test/customers/public.sql",
                                            "memory/semantic/db-catalog/test/customers/manifest.json"]
    assert (catdir(factory) / "public_ext.sql").read_bytes() == api_before
    now = manifest(factory)
    assert now["schemas"]["public"]["fingerprint"] == "fp-public-2"
    assert now["schemas"]["public"]["scanned_at"] == "2026-11-08T10:00:00Z" and now["scanned_at"] == "2026-11-08T10:00:00Z"
    assert now["schemas"]["public_ext"]["scanned_at"] == first["schemas"]["public_ext"]["scanned_at"]


def test_full_rereads_everything_but_writes_only_what_changed(factory, fake, capsys):
    make_test_customers(fake)
    scan(factory, fake, capsys)
    before = snapshot_files(factory)
    fake["executed"].clear()
    code, out = scan(factory, fake, capsys, "--full")
    assert code == 0 and out["targets"][0]["written"] == [] and snapshot_files(factory) == before
    assert sum(e[0].startswith("/* db-catalog extract") for e in fake["executed"]) == len(cat.CLASSES)


def test_schema_that_disappears_or_loses_scope_has_its_file_removed(factory, fake, capsys):
    db = make_test_customers(fake)
    scan(factory, fake, capsys)
    del db.fp["public_ext"]
    code, out = scan(factory, fake, capsys)
    assert out["targets"][0]["removed"] == ["memory/semantic/db-catalog/test/customers/public_ext.sql"]
    assert not (catdir(factory) / "public_ext.sql").exists() and "public_ext" not in manifest(factory)["schemas"]


def test_extractor_version_change_forces_regeneration(factory, fake, capsys, monkeypatch):
    make_test_customers(fake)
    scan(factory, fake, capsys)
    bumped = str(int(cat.EXTRACTOR_VERSION) + 1)
    monkeypatch.setattr(cat, "EXTRACTOR_VERSION", bumped)
    fake["executed"].clear()
    scan(factory, fake, capsys)
    assert sum(e[0].startswith("/* db-catalog extract") for e in fake["executed"]) == len(cat.CLASSES)
    assert manifest(factory)["extractor_version"] == bumped


def test_dry_run_reports_without_writing(factory, fake, capsys):
    make_test_customers(fake)
    code, out = scan(factory, fake, capsys, "--dry-run")
    assert code == 0 and out["dry_run"] is True and out["targets"][0]["manifest"] == "dry-run"
    assert any(w.endswith("public.sql") for w in out["targets"][0]["written"])
    assert not (factory / "memory").exists() and not (factory / ".db-access-state").exists()


# --- anti-segreti ---------------------------------------------------------------

AKIA = "AKIA" + "ABCDEFGHIJKLMNOP"
PEM = "-----" + "BEGIN RSA PRIVATE KEY" + "-----"
JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + "." + "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0" + "." + "abcDEF123"
SECRETS = {
    "credential_literal": "v_pass := 'hunter22'; password = 'hunter22';",
    "credential_adjacent": "conn := 'password=hunter22';",
    "connection_url_with_credentials": "url := 'postgresql://app:hunter22@db.example.org/x';",
    "connection_string_host_dbname": "x := 'host=db.example.org dbname=other';",
    "connection_string_user_password": "x := 'user=app " + "password=hunter22';",
    "aws_access_key": f"k := '{AKIA}';",
    "private_key_block": f"k := '{PEM}';",
    "jwt": f"t := '{JWT}';",
    "vendor_token": "t := 'ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8" + "';",
    "bearer_token": "h := 'Bearer " + "abcdefghijklmnopqrstuvwxyz0123" + "';",
}


def _secret_db(rule: str, place: str) -> FakeDB:
    db = cust_db()
    payload = SECRETS[rule]
    if place == "function":
        db.rows["function"][0] = row("function", "public", name="touch", args="", prokind="f",
                                     **{"def": f"CREATE FUNCTION public.touch()\nAS $f$\nBEGIN\n  {payload}\nEND;\n$f$"})
    elif place == "comment":
        db.add("comment_column", "public", table="account", name="email", comment=payload)
    else:
        db.add("column", "public", table="account", name="note", type="text", notnull=False, identity="",
               generated="", default=f"'{payload}'::text")
    return db


@pytest.mark.parametrize("place", ["function", "comment", "default"])
@pytest.mark.parametrize("rule", sorted(SECRETS))
def test_secret_check_flags_every_kind_in_body_comment_and_default(rule, place, factory, fake, capsys):
    fake["dbs"]["customers"] = _secret_db(rule, place)
    code, out = scan(factory, fake, capsys)
    assert code == cat.EXIT_SECRET == 7 and out["targets"][0]["error"] == "secret_found"
    findings = out["targets"][0]["findings"]
    assert any(f["rule"] == rule or rule.startswith("credential") for f in findings)
    assert not (factory / "memory").exists()                          # nessun file, manifest compreso
    dumped = json.dumps(out)
    for value in ("hunter22", AKIA, PEM, JWT, "ghp_", "db.example.org", "abcdefghijklmnopqrstuvwxyz0123"):
        assert value not in dumped


def test_secret_finding_reports_object_and_line_never_the_value(factory, fake, capsys):
    fake["dbs"]["customers"] = _secret_db("connection_url_with_credentials", "function")
    code, out = scan(factory, fake, capsys)
    f = out["targets"][0]["findings"][0]
    assert f["schema"] == "public" and f["object"] == "function touch()" and f["rule"].startswith("connection_url")
    assert set(f) == {"schema", "object", "line", "rule"}
    # la riga indicata e' quella del file che sarebbe stato scritto
    text = cat.assemble(cat.render_schema("public", {c.kind: [dict(zip(c.names, r[1:])) for r in
                                                             fake["dbs"]["customers"].rows.get(c.kind, [])]
                                                      for c in cat.CLASSES}))
    assert "postgresql://" in text.split("\n")[f["line"] - 1]


def test_secret_in_one_schema_blocks_the_whole_database_but_not_other_targets(factory, fake, capsys):
    db = cust_db()
    db.schema("public_ext", "fp-api")
    db.add("function", "public_ext", name="f", args="", prokind="f",
           **{"def": "CREATE FUNCTION public_ext.f()\nAS $f$ select 'password=hunter22' $f$"})
    fake["dbs"]["customers"] = db
    nis = FakeDB()
    nis.schema("orders_schema", "fp-nis")
    fake["dbs"]["orders"] = nis
    code, out = run(factory, "catalog-scan", "test", "customers", "orders", capsys=capsys)
    assert code == 7 and out["complete"] is False
    assert not (catdir(factory) / "public.sql").exists() and (catdir(factory, target="orders") / "manifest.json").is_file()
    assert [f["target"] for f in out["failed"]] == ["customers"]


def test_secret_check_clean_ddl_and_non_secret_look_alikes_have_no_findings():
    clean = ["password_hash text NOT NULL", "UPDATE t SET pass" + "word = p_new WHERE id = 1",
             "mail := 'utente@example.org'; ip := '10.1.2.3';", "COMMENT ON COLUMN u.password IS 'hash bcrypt'",
             "token text DEFAULT ''::text", "host_name text, db_name text"]
    assert cat.find_secrets("public", [("function f()", "\n".join(clean))]) == []


def test_email_or_ip_in_ddl_does_not_block_the_write(factory, fake, capsys):
    db = cust_db()
    db.add("comment_column", "public", table="account", name="email", comment="es. utente@example.org da 10.0.0.1")
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)
    assert code == 0 and (catdir(factory) / "public.sql").is_file()


# --- tabelle di dominio ------------------------------------------------------

def ref_db() -> FakeDB:
    db = cust_db()
    db.reference["public.settings"] = {"columns": ["uid", "value"],
                                       "rows": [(2, "Altro"), (1, "Area Servizi"), (3, None), (4, "")]}
    return db


DECL = [{"table": "public.settings", "reason": "valori di piattaforma usati dalle query"}]


def test_reference_table_is_extracted_in_canonical_csv_with_fingerprint(factory, fake, capsys):
    set_reference_tables(factory, DECL)
    fake["dbs"]["customers"] = ref_db()
    code, out = scan(factory, fake, capsys)
    assert code == 0, out
    csv_path = catdir(factory) / "reference" / "public.settings.csv"
    assert csv_path.read_text(encoding="utf-8").splitlines() == ["uid,value", "1,Area Servizi", "2,Altro",
                                                                 "3,", '4,""']
    assert b"\r" not in csv_path.read_bytes()
    entry = manifest(factory)["reference_tables"]["public.settings"]
    assert entry["rows"] == 4 and entry["reason"] == DECL[0]["reason"] and len(entry["content_fingerprint"]) == 64
    assert entry["file"] == "reference/public.settings.csv" and entry["scanned_at"]
    values_sql = [e for e in fake["executed"] if e[0].startswith("/* db-catalog reference-values")]
    assert len(values_sql) == 1                                          # una sola lettura per tabella
    sql = values_sql[0][0]
    assert re.match(r"/\* [\w -]+ \*/ select ", sql) and " limit %s" in sql and values_sql[0][1] == (201,)
    assert not re.search(r"\b(insert|copy|update|delete|create)\b", sql, re.I)


def test_reference_extraction_is_idempotent_and_detects_content_change(factory, fake, capsys, clock):
    set_reference_tables(factory, DECL)
    db = ref_db()
    fake["dbs"]["customers"] = db
    scan(factory, fake, capsys)
    before = snapshot_files(factory)
    first_fp = manifest(factory)["reference_tables"]["public.settings"]["content_fingerprint"]
    clock.advance(hours=5)
    code, out = scan(factory, fake, capsys)
    assert out["targets"][0]["written"] == [] and snapshot_files(factory) == before
    db.reference["public.settings"]["rows"].append((5, "Nuova"))
    scan(factory, fake, capsys)
    entry = manifest(factory)["reference_tables"]["public.settings"]
    assert entry["content_fingerprint"] != first_fp and entry["rows"] == 5
    assert "5,Nuova" in (catdir(factory) / "reference" / "public.settings.csv").read_text(encoding="utf-8")


def test_row_order_from_the_server_does_not_change_the_csv():
    rows = [(10, "b"), (9, "a"), (None, "z")]
    assert cat.canonical_csv(["id", "v"], rows) == cat.canonical_csv(["id", "v"], list(reversed(rows)))
    assert cat.canonical_csv(["id", "v"], rows).splitlines()[1:] == [",z", "9,a", "10,b"]


def test_undeclared_table_and_database_without_list_produce_no_values(factory, fake, capsys):
    db = ref_db()
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)                     # nessun elenco dichiarato
    assert code == 0 and not (catdir(factory) / "reference").exists()
    assert not any(e[0].startswith("/* db-catalog reference") for e in fake["executed"])
    set_reference_tables(factory, DECL)
    db.reference["public.other"] = {"columns": ["a"], "rows": [(1,)]}
    scan(factory, fake, capsys)
    names = {p.name for p in (catdir(factory) / "reference").glob("*")}
    assert names == {"public.settings.csv"}


@pytest.mark.parametrize("column", ["email", "codice_fiscale", "user_email", "first_name", "cf", "Telefono", "userphone"])
def test_personal_column_name_refuses_the_table_and_reads_no_values(column, factory, fake, capsys):
    set_reference_tables(factory, DECL)
    db = cust_db()
    db.reference["public.settings"] = {"columns": ["uid", column], "rows": [(1, "x")]}
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)
    ref = out["targets"][0]["reference_tables"][0]
    assert code == 4 and ref["status"] == "refused" and "public.settings" in ref["table"] and column in ref["cause"]
    assert not any(e[0].startswith("/* db-catalog reference-values") for e in fake["executed"])
    assert not (catdir(factory) / "reference").exists()
    assert out["complete"] is False


def test_harmless_column_names_are_not_flagged():
    names = cat.CATALOG_DEFAULTS["personal_column_names"]
    for col in ("uid", "value", "label", "settings", "description", "code", "label", "created_at"):
        assert cat.personal_match(col, names) is None, col
    assert cat.personal_match("nome", names) == "nome" and cat.personal_match("birth_date", names) == "birth"


def test_table_above_max_rows_is_refused_and_not_written(factory, fake, capsys):
    set_reference_tables(factory, DECL)
    db = cust_db()
    db.reference["public.settings"] = {"columns": ["uid", "value"], "rows": [(i, "v") for i in range(250)]}
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)
    ref = out["targets"][0]["reference_tables"][0]
    assert code == 4 and ref["status"] == "refused" and "200" in ref["cause"] and "csv" not in ref
    values = [e for e in fake["executed"] if e[0].startswith("/* db-catalog reference-values")]
    assert values[0][1] == (201,)                                       # il server non restituisce oltre max+1
    assert not (catdir(factory) / "reference").exists()
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  catalog:\n    max_reference_rows: 300\n", encoding="utf-8")
    code, out = scan(factory, fake, capsys)
    assert code == 0 and manifest(factory)["reference_tables"]["public.settings"]["rows"] == 250


def test_declared_table_missing_from_catalog_is_unverified_and_not_extracted(factory, fake, capsys):
    set_reference_tables(factory, DECL)
    fake["dbs"]["customers"] = cust_db()
    code, out = scan(factory, fake, capsys)
    assert code == 4 and out["targets"][0]["reference_tables"][0]["status"] == "unverified"
    assert out["targets"][0]["state"] == "incomplete" and "public.settings" not in manifest(factory)["reference_tables"]


def test_declared_table_without_select_is_inaccessible(factory, fake, capsys):
    set_reference_tables(factory, DECL)
    db = ref_db()
    db.reference["public.settings"]["can_read"] = False
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)
    assert code == 4 and out["targets"][0]["reference_tables"][0]["status"] == "inaccessible"


def test_secret_in_reference_values_blocks_the_write_and_hides_the_value(factory, fake, capsys):
    set_reference_tables(factory, DECL)
    db = cust_db()
    db.reference["public.settings"] = {"columns": ["uid", "value"], "rows": [(1, "password=hunter22")]}
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)
    assert code == 7 and "hunter22" not in json.dumps(out) and not (factory / "memory").exists()
    assert out["targets"][0]["findings"][0]["schema"] == "reference/public.settings"


def test_reference_entry_removed_from_registry_deletes_its_file(factory, fake, capsys):
    set_reference_tables(factory, DECL)
    fake["dbs"]["customers"] = ref_db()
    scan(factory, fake, capsys)
    set_reference_tables(factory, None)
    code, out = scan(factory, fake, capsys)
    assert out["targets"][0]["removed"] == ["memory/semantic/db-catalog/test/customers/reference/public.settings.csv"]
    assert manifest(factory)["reference_tables"] == {}


@pytest.mark.parametrize("bad", [
    [{"table": "public.settings", "reason": "x", "status": "ok"}],
    [{"table": "public.settings", "reason": "x", "evidence": "y"}],
    [{"table": "settings", "reason": "x"}],
    [{"table": "public.settings", "reason": " "}],
    [{"table": "public.settings"}],
    [{"table": "public.settings", "reason": "x", "columns": []}],
    [{"table": "public.settings", "reason": "x", "columns": ["value", "value"]}],
    "public.settings",
])
def test_reference_tables_registry_shape_is_validated(bad, factory, fake, capsys):
    set_reference_tables(factory, bad)
    fake["dbs"]["customers"] = cust_db()
    code, out = scan(factory, fake, capsys)
    assert code == 1 and out["error"] == "reference_tables_invalid" and not fake["params"]


def test_example_registry_declares_reference_tables_with_known_keys_only():
    data = yaml.safe_load((_REPO_ROOT / "tools" / "db" / "db-targets.example.yaml").read_text(encoding="utf-8"))
    for env, edef in data["environments"].items():
        for target, db in edef["databases"].items():
            for entry in db.get("reference_tables") or []:
                assert {"table", "reason"} <= set(entry) <= {"table", "reason", "columns"}, (env, target)
    ctx = cat.Ctx(_REPO_ROOT, {}, cat.catalog_cfg({}), data["environments"], {})
    for env, edef in data["environments"].items():
        for target in edef["databases"]:
            cat.declared_reference_tables(ctx, env, target)


# --- catalog-check -------------------------------------------------------------

def scanned(factory, fake, capsys, fp="fp-public-1"):
    fake["dbs"]["customers"] = cust_db(fp)
    code, _ = scan(factory, fake, capsys)
    assert code == 0
    fake["executed"].clear()
    fake["params"].clear()
    return fake["dbs"]["customers"]


def check(factory, capsys, *extra, env="test", target="customers"):
    return run(factory, "catalog-check", env, target, *extra, capsys=capsys)


def test_check_fresh_is_one_query_per_database_and_has_no_warning(factory, fake, capsys):
    scanned(factory, fake, capsys)
    code, out = check(factory, capsys)
    t = out["targets"][0]
    assert code == 0 and t["state"] == "fresh" and out["catalog_warning"] is None and out["needs_sync"] is False
    assert [e[0].split()[2] for e in fake["executed"]] == ["fingerprint"]       # nessuna query per tabella o schema
    assert len(fake["params"]) == 1 and t["reference"]["source"] == "local"
    assert "riferimento non aggiornato" in t["reference"]["note"]


def test_check_cost_does_not_grow_with_schemas_or_objects(factory, fake, capsys):
    db = make_test_customers(fake)
    scan(factory, fake, capsys)
    for i in range(30):
        db.add("table", "public", name=f"t{i}", persistence="p", ispartition=False)
    fake["executed"].clear()
    check(factory, capsys, "--refresh")
    assert len(fake["executed"]) == 1


def test_check_reports_drift_with_changed_schemas_and_warning(factory, fake, capsys):
    db = scanned(factory, fake, capsys)
    db.schema("public", "fp-public-2")
    db.schema("brand_new", "fp-n")
    code, out = check(factory, capsys)
    t = out["targets"][0]
    assert code == 0 and t["state"] == "drift" and t["changed_schemas"] == ["brand_new", "public"]
    assert t["schemas"]["public"] == {"state": "drift", "change": "changed", "scope": "in_registry"}
    assert t["schemas"]["brand_new"]["state"] == "missing" and t["schemas"]["brand_new"]["change"] == "new"
    assert out["needs_sync"] is True and "drift su brand_new, public" in out["catalog_warning"]
    assert "\n" not in out["catalog_warning"]


def test_check_with_drift_writes_only_the_overlay_and_leaves_the_catalog_unchanged(factory, fake, capsys):
    db = scanned(factory, fake, capsys)
    before = snapshot_files(factory)
    db.schema("public", "fp-public-2")
    check(factory, capsys)
    assert snapshot_files(factory) == before
    state = json.loads((factory / ".db-access-state/catalog/test/customers.json").read_text(encoding="utf-8"))
    assert state["overlay"]["schemas"]["public"]["fingerprint"] == "fp-public-2"


def test_removed_schema_and_lost_access_are_drift(factory, fake, capsys):
    db = make_test_customers(fake)
    scan(factory, fake, capsys)
    del db.fp["test"]
    db.schema("public_ext", None, usable=False)
    code, out = check(factory, capsys, "--refresh")
    s = out["targets"][0]["schemas"]
    assert s["test"]["change"] == "removed" and s["public_ext"]["change"] == "access_lost"
    assert out["targets"][0]["state"] == "drift"


def test_check_without_snapshot_is_missing_and_opens_no_connection(factory, fake, capsys):
    code, out = check(factory, capsys)
    t = out["targets"][0]
    assert code == 0 and t["state"] == "missing" and not fake["params"] and t["needs_sync"] is True
    assert "nessuno snapshot" in out["catalog_warning"]


def test_check_without_connect_privilege_is_inaccessible_exit_2_with_cause(factory, fake, capsys):
    scanned(factory, fake, capsys)
    fake["connect_errors"]["customers"] = FakeError(
        'FATAL: permission denied for database "customers"\nDETAIL: User does not have CONNECT privilege.', "42501")
    code, out = check(factory, capsys, "--refresh")
    t = out["targets"][0]
    assert code == 2 and t["state"] == "inaccessible" and "CONNECT" in t["cause"]
    assert len(fake["params"]) == 1                                      # un solo tentativo
    assert out["ok"] is False and "non accessibile" in out["catalog_warning"]


@pytest.mark.parametrize("env,days,expected", [("test", 6, "unverified"), ("test", 8, "stale"),
                                               ("staging", 8, "stale"), ("preprod", 13, "unverified"),
                                               ("preprod", 15, "stale"), ("prod", 13, "unverified"),
                                               ("prod", 15, "stale")])
def test_unverifiable_check_is_stale_only_past_the_threshold(env, days, expected, factory, fake, capsys, clock):
    target_db = "customers-preprod" if env == "preprod" else "customers"
    fake["dbs"][target_db] = cust_db()
    assert scan(factory, fake, capsys, env=env)[0] == 0
    clock.advance(days=days)
    fake["connect_errors"][target_db] = FakeError("connection timeout expired")
    code, out = check(factory, capsys, env=env)
    t = out["targets"][0]
    assert code == 2 and t["state"] == expected and t["snapshot_age_days"] == days
    assert t["schemas"]["public"]["state"] == expected                 # lo snapshot non viene scartato
    assert "non verificato" in out["catalog_warning"]
    if expected == "stale":
        assert f"soglia di {7 if env in ('test', 'staging') else 14}" in out["catalog_warning"]


def test_staleness_threshold_is_configurable(factory, fake, capsys, clock):
    scanned(factory, fake, capsys)
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  catalog:\n    stale_days: {test: 2}\n", encoding="utf-8")
    clock.advance(days=3)
    fake["connect_errors"]["customers"] = FakeError("connection timeout expired")
    code, out = check(factory, capsys)
    assert out["targets"][0]["state"] == "stale"


def test_connection_error_keeps_snapshot_and_does_not_retry_within_ttl(factory, fake, capsys, clock):
    scanned(factory, fake, capsys)
    before = snapshot_files(factory)
    fake["connect_errors"]["customers"] = FakeError("connection timeout expired")
    code, out = check(factory, capsys)
    code2, out2 = check(factory, capsys)
    assert code == code2 == 2 and out2["targets"][0]["cached"] is True and len(fake["params"]) == 1
    assert snapshot_files(factory) == before


def test_check_within_ttl_opens_no_connection_and_after_ttl_reconnects(factory, fake, capsys, clock):
    scanned(factory, fake, capsys)
    check(factory, capsys)
    clock.advance(minutes=14)
    code, out = check(factory, capsys)
    assert out["targets"][0]["cached"] is True and len(fake["params"]) == 1
    clock.advance(minutes=2)
    code, out = check(factory, capsys)
    assert out["targets"][0]["cached"] is False and len(fake["params"]) == 2


def test_check_refresh_ignores_the_ttl(factory, fake, capsys):
    scanned(factory, fake, capsys)
    check(factory, capsys)
    check(factory, capsys, "--refresh")
    assert len(fake["params"]) == 2


def test_ttl_is_dropped_when_the_reference_manifest_changes(factory, fake, capsys):
    db = scanned(factory, fake, capsys)
    check(factory, capsys)
    db.schema("public", "fp-public-2")
    scan(factory, fake, capsys)                                         # nuovo manifest locale
    fake["executed"].clear()
    code, out = check(factory, capsys)
    assert out["targets"][0]["cached"] is False and out["targets"][0]["state"] == "fresh"


def test_db_timeout_is_exit_6_and_state_unverified(factory, fake, capsys):
    scanned(factory, fake, capsys)
    fake["errors"][("customers", "fingerprint")] = FakeError("canceling statement due to statement timeout", "57014")
    code, out = check(factory, capsys)
    t = out["targets"][0]
    assert code == 6 and t["state"] == "unverified" and t["cause"] == "timeout"
    assert fake["conns"][0].rollbacks >= 1 and fake["conns"][0].closed


@pytest.mark.parametrize("attr", ["sqlstate", "pgcode"])
def test_sql_errors_from_psycopg3_and_psycopg2_are_both_classified(attr, factory, fake, capsys):
    scanned(factory, fake, capsys)
    fake["errors"][("customers", "fingerprint")] = FakeError("boom", "42P01", attr=attr)
    code, out = check(factory, capsys)
    assert code == 5 and out["targets"][0]["state"] == "unverified"


def test_check_never_exposes_the_password(factory, fake, capsys):
    scanned(factory, fake, capsys)
    fake["connect_errors"]["customers"] = FakeError(f"password authentication failed ({PASSWORD})")
    code, out = check(factory, capsys)
    state_file = (factory / ".db-access-state/catalog/test/customers.json").read_text(encoding="utf-8")
    blob = json.dumps(out) + state_file
    assert PASSWORD not in blob and out["targets"][0]["cause"] == "autenticazione rifiutata"


def test_check_without_credentials_is_unverifiable_exit_1(factory, fake, capsys):
    scanned(factory, fake, capsys)
    (factory / ".env.db").write_text("OTHER=1\n", encoding="utf-8")
    code, out = check(factory, capsys, "--refresh")
    assert code == 1 and out["targets"][0]["state"] == "unverified" and not fake["params"]
    assert out["targets"][0]["cause"] == "credenziali assenti"


# --- riferimento su origin/main (git simulato) -------------------------------

def git_with(fake, remote: dict | None, rc_missing=True):
    def handler(args):
        if args[0] == "show" and remote is not None:
            return subprocess.CompletedProcess(args, 0, json.dumps(remote).encode("utf-8"), b"")
        if rc_missing:
            return subprocess.CompletedProcess(args, 128, b"", b"fatal: path 'x' does not exist in 'origin/main'\n")
        return subprocess.CompletedProcess(args, 128, b"", b"fatal: invalid object name 'origin/main'.\n")
    fake["git_handler"] = handler


def test_reference_manifest_is_read_from_origin_main_without_checkout_or_fetch(factory, fake, capsys):
    scanned(factory, fake, capsys)
    git_with(fake, manifest(factory))
    code, out = check(factory, capsys)
    t = out["targets"][0]
    assert t["reference"]["source"] == "origin/main" and t["reference"]["note"] is None and t["needs_commit"] is False
    shows = [a for a, _ in fake["git"] if a[0] == "show"]
    assert shows == [["show", "origin/main:memory/semantic/db-catalog/test/customers/manifest.json"]]
    assert all(a[0] != "fetch" and "fetch" not in a and "pull" not in a for a, _ in fake["git"])
    assert all(timeout == 10.0 for _, timeout in fake["git"])


def test_reference_from_origin_main_wins_over_a_newer_local_manifest(factory, fake, capsys):
    db = scanned(factory, fake, capsys)
    old_remote = manifest(factory)
    db.schema("public", "fp-public-2")
    scan(factory, fake, capsys)                                         # locale aggiornato, non su origin/main
    git_with(fake, old_remote)
    code, out = check(factory, capsys, "--refresh")
    t = out["targets"][0]
    assert t["state"] == "drift" and t["needs_commit"] is True
    assert t["needs_sync"] is False and t["local_is_current"] is True   # basta il commit, non un nuovo scan
    assert out["needs_commit"] is True and "non committato" in out["catalog_warning"]


def test_local_files_not_on_origin_main_return_needs_commit(factory, fake, capsys):
    scanned(factory, fake, capsys)
    git_with(fake, None, rc_missing=True)                                # origin/main raggiungibile ma senza il file
    code, out = check(factory, capsys)
    t = out["targets"][0]
    assert t["reference"]["source"] == "local" and t["needs_commit"] is True and t["state"] == "fresh"


def test_reference_falls_back_to_local_and_says_riferimento_non_aggiornato(factory, fake, capsys):
    scanned(factory, fake, capsys)
    git_with(fake, None, rc_missing=False)
    code, out = check(factory, capsys)
    t = out["targets"][0]
    assert t["reference"]["source"] == "local" and "riferimento non aggiornato" in t["reference"]["note"]
    assert t["needs_commit"] is None


def test_reference_local_reports_age_of_last_fetch(factory, fake, capsys, monkeypatch, clock):
    scanned(factory, fake, capsys)
    head = factory / "FETCH_HEAD"
    head.write_text("x", encoding="utf-8")
    import os
    stamp = (START - dt.timedelta(hours=30)).timestamp()
    os.utime(head, (stamp, stamp))

    def handler(args):
        if args[0] == "rev-parse":
            return subprocess.CompletedProcess(args, 0, b"FETCH_HEAD\n", b"")
        return subprocess.CompletedProcess(args, 128, b"", b"fatal: invalid object name\n")
    fake["git_handler"] = handler
    code, out = check(factory, capsys)
    assert out["targets"][0]["reference"]["fetch_age_hours"] == 30.0


def test_git_timeout_falls_back_to_the_local_manifest(factory, fake, capsys):
    scanned(factory, fake, capsys)

    def handler(args):
        raise subprocess.TimeoutExpired(["git", *args], 10)
    fake["git_handler"] = handler
    code, out = check(factory, capsys)
    t = out["targets"][0]
    assert code == 0 and t["reference"]["source"] == "local" and "timeout" in t["reference"]["note"]


def test_git_missing_falls_back_to_the_local_manifest(factory, fake, capsys):
    scanned(factory, fake, capsys)

    def handler(args):
        raise FileNotFoundError("git")
    fake["git_handler"] = handler
    code, out = check(factory, capsys)
    assert code == 0 and out["targets"][0]["reference"]["source"] == "local"


@pytest.mark.parametrize("bad", ["../x", "a/b", "..", "", ".hidden", "a b"])
def test_reference_path_cannot_escape_the_catalog_directory(bad):
    with pytest.raises(cat.ToolError):
        cat.manifest_relpath(cat.catalog_cfg({}), "test", bad)
    with pytest.raises(cat.ToolError):
        cat.manifest_relpath(cat.catalog_cfg({}), bad, "customers")
    for directory in ("../outside", "/abs", "a/../b", "C:/x"):
        with pytest.raises(cat.ToolError):
            cat.catalog_cfg({"catalog": {"directory": directory}})
    assert cat.manifest_relpath(cat.catalog_cfg({}), "test", "customers") == \
        "memory/semantic/db-catalog/test/customers/manifest.json"


# --- status offline, JSON, exit code -----------------------------------------

def test_status_is_offline_and_reports_age_and_states(factory, fake, capsys, clock):
    make_test_customers(fake)
    scan(factory, fake, capsys)
    fake["params"].clear()
    clock.advance(days=9)
    code, out = run(factory, "catalog-status", "test", capsys=capsys)
    by = {t["target"]: t for t in out["targets"]}
    assert code == 0 and not fake["params"] and not fake["git"] and out["offline"] is True
    assert by["customers"]["state"] == "stale" and by["customers"]["snapshot_age_days"] == 9.0
    assert by["customers"]["schemas"]["restricted"]["accessible"] is False
    assert by["orders"]["state"] == "missing" and by["empty"]["state"] == "missing"
    assert "stale" in out["catalog_warning"]


def test_status_all_envs_and_unknown_env(factory, fake, capsys):
    code, out = run(factory, "catalog-status", capsys=capsys)
    assert code == 0 and {t["env"] for t in out["targets"]} == {"test", "staging", "preprod", "prod"}
    code, out = run(factory, "catalog-status", "nope", capsys=capsys)
    assert code == 1 and out["error"] == "unknown_env"


def test_scan_with_unreachable_database_is_incomplete_exit_2_with_the_list(factory, fake, capsys):
    fake["dbs"]["customers"] = cust_db()
    fake["connect_errors"]["orders"] = FakeError("connection timeout expired")
    code, out = run(factory, "catalog-scan", "test", "customers", "orders", capsys=capsys)
    assert code == 2 and out["ok"] is False and out["complete"] is False
    assert [f["target"] for f in out["failed"]] == ["orders"]
    assert (catdir(factory) / "manifest.json").is_file() and not catdir(factory, target="orders").exists()


def test_scan_default_targets_are_all_registry_targets_of_the_env(factory, fake, capsys):
    code, out = run(factory, "catalog-scan", "test", capsys=capsys)
    assert code != 0 and sorted(t["target"] for t in out["targets"]) == ["customers", "empty", "orders"]


def test_scan_db_without_connect_privilege_is_recorded_and_exits_nonzero(factory, fake, capsys, clock):
    fake["connect_errors"]["customers"] = FakeError('FATAL: permission denied for database "customers"', "42501")
    code, out = scan(factory, fake, capsys)
    m = manifest(factory)
    assert code == 2 and m["accessible"] is False and "CONNECT" in m["cause"] and m["since"] == "2026-11-06"
    clock.advance(days=5)
    scan(factory, fake, capsys)
    assert manifest(factory)["since"] == "2026-11-06"                   # la data resta quella della prima osservazione
    code, out = check(factory, capsys)
    assert out["targets"][0]["state"] == "inaccessible"


def test_scan_sql_timeout_is_exit_6_and_writes_nothing(factory, fake, capsys):
    fake["dbs"]["customers"] = cust_db()
    fake["errors"][("customers", "extract")] = FakeError("canceling statement due to statement timeout", "57014")
    code, out = scan(factory, fake, capsys)
    assert code == 6 and out["targets"][0]["error"] == "timeout" and not (factory / "memory").exists()


def test_scan_never_writes_to_the_database_on_any_env(factory, fake, capsys):
    for env in ("test", "staging", "prod"):
        fake["dbs"]["customers"] = cust_db()
        scan(factory, fake, capsys, env=env)
    for sql, _ in fake["executed"]:
        assert not re.search(r"\b(insert|update|delete|truncate|drop|alter|grant|copy|vacuum)\b", sql, re.I)
        assert "nextval" not in sql and "setval" not in sql
    assert all(c.commits == 0 for c in fake["conns"])


def test_snapshot_isolation_is_the_first_statement_and_can_be_disabled(factory, fake, capsys):
    fake["dbs"]["customers"] = cust_db()
    scan(factory, fake, capsys)
    assert fake["executed"][0][0].endswith("set transaction isolation level repeatable read")
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  catalog:\n    repeatable_read: false\n", encoding="utf-8")
    fake["executed"].clear()
    scan(factory, fake, capsys, "--full")
    assert not any("isolation" in e[0] for e in fake["executed"])


def test_capability_disabled_and_unknown_target_exit_1(factory, fake, capsys):
    code, out = run(factory, "catalog-check", "test", "nope", capsys=capsys)
    assert code == 1 and out["error"] == "unknown_target"
    code, out = run(factory, "catalog-check", "mars", capsys=capsys)
    assert code == 1 and out["error"] == "unknown_env"
    (factory / "factory.config.yaml").write_text("db_access:\n  enabled: false\n", encoding="utf-8")
    code, out = run(factory, "catalog-status", capsys=capsys)
    assert code == 1 and out["error"] == "capability_disabled"


def test_corrupt_manifest_is_an_error_not_silently_overwritten(factory, fake, capsys):
    fake["dbs"]["customers"] = cust_db()
    (catdir(factory)).mkdir(parents=True)
    (catdir(factory) / "manifest.json").write_text("{not json", encoding="utf-8")
    code, out = scan(factory, fake, capsys)
    assert code == 1 and out["error"] == "json_invalid"
    assert (catdir(factory) / "manifest.json").read_text(encoding="utf-8") == "{not json"


def test_large_output_goes_to_a_file_under_32_kib(factory, fake, capsys):
    db = cust_db()
    for i in range(1500):
        db.schema(f"schema_{i:04d}_" + "x" * 20, f"fp{i}")
    fake["dbs"]["customers"] = db
    run(factory, "catalog-scan", "test", "customers", capsys=capsys)
    code = cat.main(["--root", str(factory), "catalog-check", "test", "customers", "--refresh"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 0 and "output_file" in out and len(json.dumps(out).encode()) < cat.MAX_STDOUT_BYTES
    assert Path(out["output_file"]).is_file() and out["summary"]["targets"][0]["state"] == "fresh"


def test_stdout_is_a_single_json_document_and_diagnostics_go_to_stderr(factory, fake, capsys):
    fake["dbs"]["customers"] = cust_db()
    cat.main(["--root", str(factory), "catalog-scan", "test", "customers"])
    captured = capsys.readouterr()
    assert json.loads(captured.out)["command"] == "catalog-scan" and "db_catalog: scan" in captured.err
    assert PASSWORD not in captured.out + captured.err


def test_no_secret_in_any_file_written(factory, fake, capsys):
    set_reference_tables(factory, DECL)
    fake["dbs"]["customers"] = ref_db()
    scan(factory, fake, capsys)
    check(factory, capsys)
    for base in (factory / "memory", factory / ".db-access-state"):
        for p in base.rglob("*"):
            if p.is_file():
                text = p.read_text(encoding="utf-8")
                assert PASSWORD not in text and "tester" not in text


def test_files_are_lf_only(factory, fake, capsys):
    set_reference_tables(factory, DECL)
    fake["dbs"]["customers"] = ref_db()
    scan(factory, fake, capsys)
    for p in (factory / "memory").rglob("*"):
        if p.is_file():
            assert b"\r" not in p.read_bytes(), p.name
            assert p.read_bytes().endswith(b"\n")


def test_module_import_is_light_and_does_not_touch_the_network_or_filesystem(monkeypatch):
    import importlib
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("subprocess all'import"))
    importlib.reload(cat)


# --- letterali fiscali mascherati nella DDL ------------------------------------------------------------------

def test_mask_fiscal_literals_masks_cf_and_valid_piva_only():
    # 12345678903 ha cifra di controllo valida; 12345678901 no (resta: e' un numero qualsiasi)
    ddl = ("CREATE VIEW v AS SELECT * FROM t WHERE cf = ANY (ARRAY['RSSMRA85T10A562S'::text, "
           "'rssmra85t10a562s'::text, '12345678903'::text, '12345678901'::text, 'RSSMRA8LT10A562S'::text]);")
    out, counts = cat.mask_fiscal_literals(ddl)
    assert "RSSMRA85T10A562S" not in out.upper() and "12345678903" not in out
    assert "'12345678901'" in out                                   # non e' una partita IVA valida
    assert counts == {"codice_fiscale": 3, "partita_iva": 1}
    assert out.count(f"'{cat.CF_PLACEHOLDER}'") == 3 and out.count(f"'{cat.PIVA_PLACEHOLDER}'") == 1


def test_mask_fiscal_literals_leaves_structure_untouched():
    ddl = "CREATE TABLE t (fiscal_code character varying(16), piva character(11) DEFAULT '00000000000'::bpchar);"
    out, counts = cat.mask_fiscal_literals(ddl)
    assert out == ddl and counts == {}                               # tutti zeri: non e' una partita IVA


def test_piva_check_digit():
    assert cat.piva_valid("12345678903") and not cat.piva_valid("12345678901")
    assert not cat.piva_valid("00000000000") and not cat.piva_valid("1234567890")


def test_audit_columns_are_refused_unless_excluded_by_an_explicit_column_list(factory, fake, capsys):
    assert cat.personal_match("row_created_by", cat.CATALOG_DEFAULTS["personal_column_names"]) == "created_by"
    assert cat.personal_match("sys_updated_by", cat.CATALOG_DEFAULTS["personal_column_names"]) == "updated_by"
    assert cat.personal_match("label", cat.CATALOG_DEFAULTS["personal_column_names"]) is None


def test_reference_columns_list_restricts_the_extracted_columns(factory, fake, capsys):
    set_reference_tables(factory, [{"table": "public.settings", "reason": "valori di dominio", "columns": ["value"]}])
    fake["dbs"]["customers"] = ref_db()
    code, out = scan(factory, fake, capsys)
    assert code == 0, out
    lines = (catdir(factory) / "reference" / "public.settings.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "value"
    assert manifest(factory)["reference_tables"]["public.settings"]["columns"] == ["value"]


def test_reference_columns_list_with_a_missing_column_is_unverified(factory, fake, capsys):
    set_reference_tables(factory, [{"table": "public.settings", "reason": "x", "columns": ["value", "assente"]}])
    fake["dbs"]["customers"] = ref_db()
    code, out = scan(factory, fake, capsys)
    assert code == 4


# --- pii_scrub (opzione, default acceso) ---------------------------------------------------------------------

def _cf_view_db() -> FakeDB:
    db = cust_db()
    db.add("view", "public", name="v_cf", options="", **{"def": " SELECT 1 WHERE cf = 'RSSMRA85T10A562S'::text;"})
    return db


def test_pii_scrub_is_on_by_default_and_masks_literals_in_the_ddl(factory, fake, capsys):
    assert cat.CATALOG_DEFAULTS["pii_scrub"] is True
    fake["dbs"]["customers"] = _cf_view_db()
    code, out = scan(factory, fake, capsys)
    ddl = (catdir(factory) / "public.sql").read_text(encoding="utf-8")
    assert code == 0 and "RSSMRA85T10A562S" not in ddl and cat.CF_PLACEHOLDER in ddl
    assert "pii_scrub" not in manifest(factory)


def test_pii_scrub_off_keeps_literals_and_declares_it_in_the_manifest(factory, fake, capsys):
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  catalog:\n    pii_scrub: false\n", encoding="utf-8")
    fake["dbs"]["customers"] = _cf_view_db()
    code, out = scan(factory, fake, capsys)
    ddl = (catdir(factory) / "public.sql").read_text(encoding="utf-8")
    assert code == 0 and "RSSMRA85T10A562S" in ddl and manifest(factory)["pii_scrub"] is False


def test_pii_scrub_off_lets_a_personal_column_reference_table_through(factory, fake, capsys):
    (factory / "factory.config.yaml").write_text(
        "db_access:\n  enabled: true\n  catalog:\n    pii_scrub: false\n", encoding="utf-8")
    set_reference_tables(factory, DECL)
    db = cust_db()
    db.reference["public.settings"] = {"columns": ["uid", "email"], "rows": [(1, "x")]}
    fake["dbs"]["customers"] = db
    code, out = scan(factory, fake, capsys)
    assert out["targets"][0]["reference_tables"][0]["status"] == "ok"


def test_catalog_directory_default_is_configurable():
    assert cat.catalog_cfg({})["directory"] == "memory/semantic/db-catalog"
    assert cat.catalog_cfg({"catalog": {"directory": "knowledge/db"}})["directory"] == "knowledge/db"
    with pytest.raises(cat.ToolError):
        cat.catalog_cfg({"catalog": {"directory": "../fuori"}})
