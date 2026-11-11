#!/usr/bin/env python3
"""Catalogo DDL dei database PostgreSQL: fingerprint per schema, scan e stato.

Sottocomandi (JSON su stdout, diagnostica su stderr; solo lettura verso i DB):

  catalog-check  ENV [TARGET...] [--refresh]
        Una query per database restituisce un fingerprint per schema; il confronto e' col manifest di
        riferimento (`git show origin/main:<manifest>` senza fetch, altrimenti il manifest locale).
        Stati per schema e per db: fresh | drift | missing | inaccessible | stale | unverified.
        TTL per (env, target) in <state_dir>/catalog/; su drift l'overlay resta in <state_dir>, mai nel catalogo.
  catalog-scan   ENV [TARGET...] [--full] [--dry-run]
        Per ogni db del registro enumera tutti gli schemi non di sistema, calcola il fingerprint, estrae la DDL
        canonica dei soli schemi in registro (o usati da un servizio) e le tabelle di dominio dichiarate.
        Scrive <directory>/<env>/<db>/<schema>.sql, manifest.json, reference/*.csv. Non committa mai.
  catalog-status [ENV]
        Offline: legge i manifest locali e riporta eta', stati e schemi, senza connettersi.

Exit code (come db_access.py): 0 ok | 1 uso/config | 2 connessione | 4 guardia (tabella di dominio rifiutata)
| 5 errore SQL | 6 timeout | 7 controllo anti-segreti. Un risultato incompleto non esce mai con 0.
`catalog-check` e' advisory sull'obsolescenza (nessun blocco): drift, missing e stale escono 0 con lo stato nel
JSON; una verifica impossibile per connessione o SQL esce col codice dell'errore.

Chiavi di configurazione: blocco `db_access.catalog` di factory.config.yaml, ognuna con un default nel codice
(vedi CATALOG_DEFAULTS).
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import db_access as dba  # noqa: E402  (funzioni del tool esistente: config, registro, connessione)

ToolError = dba.ToolError
EXIT_OK = dba.EXIT_OK
EXIT_USAGE = dba.EXIT_USAGE
EXIT_CONNECT = dba.EXIT_CONNECT
EXIT_GATE = dba.EXIT_GATE
EXIT_SQL = dba.EXIT_SQL
EXIT_TIMEOUT = dba.EXIT_TIMEOUT
EXIT_SECRET = 7
MAX_STDOUT_BYTES = dba.MAX_STDOUT_BYTES

EXTRACTOR_VERSION = "2"   # 2: codici fiscali e partite IVA mascherati nei letterali
MANIFEST_VERSION = 1

CATALOG_DEFAULTS: dict[str, Any] = {
    "directory": "memory/semantic/db-catalog",
    "versioned_envs": ["dev", "test", "staging", "preprod", "prod"],
    "reference_ref": "origin/main",
    "git_timeout_s": 10,
    "check_ttl_minutes": 15,
    "stale_days": {"dev": 7, "test": 7, "staging": 7, "preprod": 14, "prod": 14},
    # schemi di sistema esclusi dal catalogo; glob, * = qualunque. Default: PostgreSQL standard; estendibile
    # (distribuzioni compatibili con PostgreSQL possono aggiungere schemi propri). Il filtro ^pg_ e
    # information_schema vale comunque.
    "system_schemas": ["pg_catalog", "information_schema", "pg_toast"],
    "max_reference_rows": 200,
    "personal_column_names": [
        "email", "mail", "codice_fiscale", "fiscal_code", "cf", "telefono", "phone", "mobile", "nome",
        "cognome", "first_name", "last_name", "surname", "indirizzo", "address", "data_nascita", "birth",
        "iban", "password", "token", "username", "user_name",
        # colonne di audit: contengono l'utenza di chi ha creato o modificato la riga (es. DEFAULT CURRENT_USER)
        "created_by", "updated_by", "modified_by", "deleted_by", "owner", "author", "operator"],
    "repeatable_read": True,        # fingerprint e DDL dello scan dallo stesso snapshot del server
    "package_namespace_filter": False,  # true se la distribuzione registra package in pg_namespace (nspparent != 0)
    # Scrub dei dati personali nell'analisi (letterali tipo codice fiscale / partita IVA / email nella DDL; guardia
    # sulle colonne personali delle tabelle di dominio). Default ACCESO: spegnerlo e' una scelta esplicita.
    "pii_scrub": True,
}

# Cosa il catalogo non copre (dichiarato nel manifest: nessun dato dato per coperto senza prova).
NOT_COVERED = [
    "policy RLS, regole (rules), publication, statistiche estese, tablespace, reloptions delle tabelle",
    "tipi base e range, collation, FDW e tabelle esterne, event trigger",
    "commenti su indici, vincoli e trigger",
]


# ---------------------------------------------------------------------------
# Classi di oggetti: UNA definizione per ciascuna, usata da fingerprint E da estrazione DDL
# ---------------------------------------------------------------------------

def _ext_free(classid: str, objid: str) -> str:
    """Esclude i membri di estensioni (pg_depend deptype 'e'): l'estensione e' registrata per nome e versione."""
    return (f"not exists (select 1 from pg_depend dx where dx.classid = '{classid}'::regclass "
            f"and dx.objid = {objid} and dx.deptype = 'e')")


@dataclass(frozen=True)
class ObjClass:
    kind: str
    source: str                      # clausola FROM; deve unire `u` (oid, nspname) dello schema
    where: str
    fields: tuple[tuple[str, str], ...]   # (nome, espressione SQL); sempre solo NOMI, mai OID
    order: str = ""                  # ORDER BY della sola estrazione (leggibilita' della DDL); mai nel fingerprint

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(n for n, _ in self.fields)


_S = ("schema", "quote_ident(u.nspname)")
_OWNED_BY = ("(select quote_ident(rn.nspname) || '.' || quote_ident(rc.relname) || '.' || quote_ident(ra.attname) "
             "from pg_depend dp join pg_class rc on rc.oid = dp.refobjid "
             "join pg_namespace rn on rn.oid = rc.relnamespace "
             "join pg_attribute ra on ra.attrelid = rc.oid and ra.attnum = dp.refobjsubid "
             "where dp.classid = 'pg_class'::regclass and dp.objid = c.oid "
             "and dp.refclassid = 'pg_class'::regclass and dp.deptype in ('a', 'i') limit 1)")
_IS_IDENTITY = ("exists (select 1 from pg_depend di where di.classid = 'pg_class'::regclass "
                "and di.objid = c.oid and di.deptype = 'i')")

CLASSES: tuple[ObjClass, ...] = (
    ObjClass("extension", "pg_extension x join u on u.oid = x.extnamespace", "true",
             (_S, ("name", "quote_ident(x.extname)"), ("version", "x.extversion"))),
    ObjClass("enum", "pg_type t join u on u.oid = t.typnamespace",
             "t.typtype = 'e' and " + _ext_free("pg_type", "t.oid"),
             (_S, ("name", "quote_ident(t.typname)"),
              ("labels", "(select string_agg(quote_literal(e.enumlabel), ', ' order by e.enumsortorder) "
                         "from pg_enum e where e.enumtypid = t.oid)"))),
    ObjClass("domain", "pg_type t join u on u.oid = t.typnamespace",
             "t.typtype = 'd' and " + _ext_free("pg_type", "t.oid"),
             (_S, ("name", "quote_ident(t.typname)"),
              ("base", "format_type(t.typbasetype, t.typtypmod)"),
              ("notnull", "t.typnotnull"),
              ("default", "pg_get_expr(t.typdefaultbin, 0)"),
              ("constraints", "(select string_agg('CONSTRAINT ' || quote_ident(k.conname) || ' ' || "
                              "pg_get_constraintdef(k.oid), ' ' order by k.conname collate \"C\") "
                              "from pg_constraint k where k.contypid = t.oid)"))),
    ObjClass("composite", "pg_type t join pg_class c on c.oid = t.typrelid join u on u.oid = t.typnamespace",
             "t.typtype = 'c' and c.relkind = 'c' and " + _ext_free("pg_type", "t.oid"),
             (_S, ("name", "quote_ident(t.typname)"),
              ("attrs", "(select string_agg(quote_ident(a.attname) || ' ' || format_type(a.atttypid, a.atttypmod), "
                        "', ' order by a.attnum) from pg_attribute a "
                        "where a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped)"))),
    ObjClass("sequence", "pg_class c join pg_sequence sq on sq.seqrelid = c.oid join u on u.oid = c.relnamespace",
             "c.relkind = 'S' and " + _ext_free("pg_class", "c.oid"),
             (_S, ("name", "quote_ident(c.relname)"), ("type", "format_type(sq.seqtypid, null)"),
              ("start", "sq.seqstart"), ("increment", "sq.seqincrement"), ("min", "sq.seqmin"),
              ("max", "sq.seqmax"), ("cache", "sq.seqcache"), ("cycle", "sq.seqcycle"),
              ("owned_by", _OWNED_BY), ("identity", _IS_IDENTITY))),
    ObjClass("table", "pg_class c join u on u.oid = c.relnamespace",
             "c.relkind in ('r', 'p') and " + _ext_free("pg_class", "c.oid"),
             (_S, ("name", "quote_ident(c.relname)"), ("persistence", "c.relpersistence"),
              ("partkey", "case when c.relkind = 'p' then pg_get_partkeydef(c.oid) end"),
              ("partbound", "case when c.relispartition then pg_get_expr(c.relpartbound, c.oid) end"),
              ("ispartition", "c.relispartition"),
              ("parents", "(select string_agg(quote_ident(pn.nspname) || '.' || quote_ident(pc.relname), ', ' "
                          "order by i.inhseqno) from pg_inherits i join pg_class pc on pc.oid = i.inhparent "
                          "join pg_namespace pn on pn.oid = pc.relnamespace where i.inhrelid = c.oid)"))),
    ObjClass("column", "pg_attribute a join pg_class c on c.oid = a.attrelid join u on u.oid = c.relnamespace "
                       "left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum",
             "c.relkind in ('r', 'p') and not c.relispartition and a.attnum > 0 and not a.attisdropped and "
             + _ext_free("pg_class", "c.oid"),
             (_S, ("table", "quote_ident(c.relname)"), ("name", "quote_ident(a.attname)"),
              ("type", "format_type(a.atttypid, a.atttypmod)"), ("notnull", "a.attnotnull"),
              ("default", "pg_get_expr(d.adbin, d.adrelid)"), ("identity", "a.attidentity::text"),
              ("generated", "a.attgenerated::text")),
             order="c.relname, a.attnum"),
    ObjClass("view", "pg_class c join u on u.oid = c.relnamespace",
             "c.relkind = 'v' and " + _ext_free("pg_class", "c.oid"),
             (_S, ("name", "quote_ident(c.relname)"), ("options", "array_to_string(c.reloptions, ',')"),
              ("def", "pg_get_viewdef(c.oid, true)"))),
    ObjClass("matview", "pg_class c join u on u.oid = c.relnamespace",
             "c.relkind = 'm' and " + _ext_free("pg_class", "c.oid"),
             (_S, ("name", "quote_ident(c.relname)"), ("options", "array_to_string(c.reloptions, ',')"),
              ("def", "pg_get_viewdef(c.oid, true)"))),
    ObjClass("constraint", "pg_constraint k join pg_class c on c.oid = k.conrelid join u on u.oid = c.relnamespace",
             "k.conislocal and k.conparentid = 0 and k.contype <> 't' and c.relkind in ('r', 'p') and "
             + _ext_free("pg_class", "c.oid"),
             (_S, ("table", "quote_ident(c.relname)"), ("name", "quote_ident(k.conname)"),
              ("contype", "k.contype::text"), ("def", "pg_get_constraintdef(k.oid)"))),
    ObjClass("index", "pg_index i join pg_class ic on ic.oid = i.indexrelid join pg_class c on c.oid = i.indrelid "
                      "join u on u.oid = c.relnamespace",
             "c.relkind in ('r', 'p', 'm') and not ic.relispartition and not exists (select 1 from pg_constraint kk "
             "where kk.conindid = i.indexrelid and kk.conrelid = i.indrelid and kk.contype in ('p', 'u', 'x')) "
             "and " + _ext_free("pg_class", "c.oid"),
             (_S, ("table", "quote_ident(c.relname)"), ("name", "quote_ident(ic.relname)"),
              ("def", "pg_get_indexdef(i.indexrelid)"))),
    ObjClass("function", "pg_proc p join u on u.oid = p.pronamespace",
             "p.prokind in ('f', 'p') and " + _ext_free("pg_proc", "p.oid"),
             (_S, ("name", "quote_ident(p.proname)"), ("args", "pg_get_function_identity_arguments(p.oid)"),
              ("prokind", "p.prokind::text"), ("def", "pg_get_functiondef(p.oid)"))),
    ObjClass("trigger", "pg_trigger t join pg_class c on c.oid = t.tgrelid join u on u.oid = c.relnamespace",
             "not t.tgisinternal and t.tgparentid = 0 and " + _ext_free("pg_class", "c.oid"),
             (_S, ("table", "quote_ident(c.relname)"), ("name", "quote_ident(t.tgname)"),
              ("enabled", "t.tgenabled::text"), ("def", "pg_get_triggerdef(t.oid, true)"))),
    ObjClass("comment_schema", "pg_description d join u on u.oid = d.objoid",
             "d.classoid = 'pg_namespace'::regclass and d.objsubid = 0",
             (_S, ("comment", "d.description"))),
    ObjClass("comment_relation", "pg_description d join pg_class c on c.oid = d.objoid "
                                 "join u on u.oid = c.relnamespace",
             "d.classoid = 'pg_class'::regclass and d.objsubid = 0 and c.relkind in ('r', 'p', 'v', 'm', 'S') and "
             + _ext_free("pg_class", "c.oid"),
             (_S, ("objtype", "case c.relkind when 'v' then 'VIEW' when 'm' then 'MATERIALIZED VIEW' "
                              "when 'S' then 'SEQUENCE' else 'TABLE' end"),
              ("name", "quote_ident(c.relname)"), ("comment", "d.description"))),
    ObjClass("comment_column", "pg_description d join pg_class c on c.oid = d.objoid "
                               "join pg_attribute a on a.attrelid = c.oid and a.attnum = d.objsubid "
                               "join u on u.oid = c.relnamespace",
             "d.classoid = 'pg_class'::regclass and d.objsubid > 0 and c.relkind in ('r', 'p', 'v', 'm') and "
             "not a.attisdropped and " + _ext_free("pg_class", "c.oid"),
             (_S, ("table", "quote_ident(c.relname)"), ("name", "quote_ident(a.attname)"),
              ("comment", "d.description"))),
    ObjClass("comment_function", "pg_description d join pg_proc p on p.oid = d.objoid "
                                 "join u on u.oid = p.pronamespace",
             "d.classoid = 'pg_proc'::regclass and d.objsubid = 0 and p.prokind in ('f', 'p') and "
             + _ext_free("pg_proc", "p.oid"),
             (_S, ("objtype", "case p.prokind when 'p' then 'PROCEDURE' else 'FUNCTION' end"),
              ("name", "quote_ident(p.proname)"), ("args", "pg_get_function_identity_arguments(p.oid)"),
              ("comment", "d.description"))),
    ObjClass("comment_type", "pg_description d join pg_type t on t.oid = d.objoid join u on u.oid = t.typnamespace",
             "d.classoid = 'pg_type'::regclass and d.objsubid = 0 and t.typtype in ('e', 'd', 'c') and "
             + _ext_free("pg_type", "t.oid"),
             (_S, ("objtype", "case t.typtype when 'd' then 'DOMAIN' else 'TYPE' end"),
              ("name", "quote_ident(t.typname)"), ("comment", "d.description"))),
)
CLASS_BY_KIND = {c.kind: c for c in CLASSES}
RELATION_KINDS = ("table", "view", "matview")

_NS_PARENT = "coalesce((to_jsonb(n) ->> 'nspparent')::bigint, 0)"
_NS_TYPE = "coalesce((to_jsonb(n) ->> 'nspobjecttype')::bigint, 0)"


def _distinct_namespaces(where: str, package_filter: bool) -> str:
    """Elenco schemi senza duplicati. Alcune distribuzioni compatibili registrano package in pg_namespace
    accanto agli schemi (gli schemi di sistema possono comparire due volte); le colonne aggiuntive si leggono
    via to_jsonb, che da' NULL (-> 0) su PostgreSQL standard dove non esistono. A parita' di nome vince la riga che non e' un package."""
    extra = f" and {_NS_PARENT} = 0" if package_filter else ""
    return (f"select distinct on (n.nspname) n.oid, n.nspname from pg_namespace n where {where}{extra} "
            f"order by n.nspname, {_NS_PARENT}, {_NS_TYPE}, n.oid")


def fingerprint_sql(package_filter: bool = True) -> str:
    """UNA query per database: una riga per schema non di sistema. Solo nomi (nessun OID, attnum, relnatts,
    reltuples, dimensioni, last_value); colonne eliminate escluse; ogni aggregato ordinato per nome in collation C."""
    members = []
    for cls in CLASSES:
        parts = ", ".join(f"quote_nullable(({expr})::text)" for _, expr in cls.fields)
        members.append(f"select u.nspname as nspname, '{cls.kind}' as kind, concat_ws(chr(31), {parts}) as line "
                       f"from {cls.source} where {cls.where}")
    relations = ", ".join(f"'{k}'" for k in RELATION_KINDS)
    ns = _distinct_namespaces("n.nspname !~ '^pg_' and n.nspname <> 'information_schema' "
                              "and n.nspname !~~ all(%s::text[])", package_filter)
    return ("/* db-catalog fingerprint */ "
            f"with s as ({ns}), "
            "u as (select oid, nspname from s where has_schema_privilege(oid, 'USAGE')) "
            "select s.nspname, has_schema_privilege(s.oid, 'USAGE') as usable, "
            "case when has_schema_privilege(s.oid, 'USAGE') then "
            "md5(coalesce(string_agg(l.line, chr(10) order by l.kind collate \"C\", l.line collate \"C\"), '')) "
            "end as fingerprint, "
            "count(l.line) as objects, "
            f"count(l.line) filter (where l.kind in ({relations})) as relations "
            f"from s left join ({' union all '.join(members)}) l on l.nspname = s.nspname "
            "group by s.oid, s.nspname order by s.nspname collate \"C\"")


def extraction_sql(cls: ObjClass, package_filter: bool = True) -> str:
    """Una query per classe di oggetti e per database, sugli schemi dati (parametro): stesse espressioni del
    fingerprint, quindi nessun oggetto e' contato da una parte sola."""
    ns = _distinct_namespaces("n.nspname = any(%s::text[]) and has_schema_privilege(n.oid, 'USAGE')", package_filter)
    cols = ", ".join(expr for _, expr in cls.fields)
    tail = f" order by {cls.order}" if cls.order else ""
    return (f"/* db-catalog extract {cls.kind} */ with u as ({ns}) "
            f"select u.nspname, {cols} from {cls.source} where {cls.where}{tail}")


VERSION_SQL = "/* db-catalog version */ select current_setting('server_version'), version()"
SNAPSHOT_SQL = "/* db-catalog snapshot */ set transaction isolation level repeatable read"
REFERENCE_COLUMNS_SQL = (
    "/* db-catalog reference-columns */ "
    "select quote_ident(n.nspname) || '.' || quote_ident(c.relname), "
    "has_schema_privilege(n.oid, 'USAGE') and has_table_privilege(c.oid, 'SELECT'), a.attname, quote_ident(a.attname) "
    "from pg_class c join pg_namespace n on n.oid = c.relnamespace join pg_attribute a on a.attrelid = c.oid "
    "where n.nspname = %s and c.relname = %s and c.relkind in ('r', 'p') and a.attnum > 0 and not a.attisdropped "
    "order by a.attnum")
REFERENCE_VALUES_TEMPLATE = "/* db-catalog reference-values */ select {cols} from {table} limit %s"


# ---------------------------------------------------------------------------
# Utilita'
# ---------------------------------------------------------------------------

def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> dt.datetime:
    return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def catalog_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    user = cfg.get("catalog") or {}
    out = dict(CATALOG_DEFAULTS)
    out.update(user)
    out["stale_days"] = {**CATALOG_DEFAULTS["stale_days"], **(user.get("stale_days") or {})}
    raw_dir = str(out["directory"]).replace("\\", "/")
    directory = raw_dir.strip("/")
    if (not directory or raw_dir.startswith("/") or ".." in directory.split("/")
            or re.match(r"^[A-Za-z]:", directory)):
        raise ToolError(EXIT_USAGE, "bad_catalog_directory", f"directory del catalogo non valida: {directory!r}")
    out["directory"] = directory
    return out


def _segment(value: str, what: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value or "") or ".." in value:
        raise ToolError(EXIT_USAGE, "bad_path_segment", f"{what} non valido per un percorso: {value!r}")
    return value


def manifest_relpath(ccfg: dict[str, Any], env: str, target: str) -> str:
    return f"{ccfg['directory']}/{_segment(env, 'ambiente')}/{_segment(target, 'target')}/manifest.json"


def schema_filename(schema: str) -> str:
    """Nome file sicuro e reversibile: i nomi di schema possono avere virgolette, virgole, spazi, punti
    (es. `"$user", public`). Escape percentuale; il nome reale sta nel manifest."""
    if re.fullmatch(r"[A-Za-z0-9_$][A-Za-z0-9_$-]*", schema):
        return f"{schema}.sql"
    return quote(schema, safe="").replace(".", "%2E") + ".sql"


def _quote_ident(name: str) -> str:
    if re.fullmatch(r"[a-z_][a-z0-9_$]*", name):
        return name
    return '"' + name.replace('"', '""') + '"'


def _lit(text: str) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def _canon(text: Any) -> str:
    """Forma canonica del testo: LF, niente spazi a fine riga, niente righe vuote in testa e in coda."""
    lines = [ln.rstrip() for ln in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _write_if_changed(path: Path, data: bytes) -> bool:
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return True


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ToolError(EXIT_USAGE, "json_invalid", f"file non leggibile come JSON: {path.name}") from exc
    return data if isinstance(data, dict) else None


def _strip_ts(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_ts(v) for k, v in value.items() if k != "scanned_at"}
    if isinstance(value, list):
        return [_strip_ts(v) for v in value]
    return value


def _canon_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


# ---------------------------------------------------------------------------
# Contesto, registro, scope
# ---------------------------------------------------------------------------

@dataclass
class Ctx:
    root: Path
    cfg: dict[str, Any]
    ccfg: dict[str, Any]
    registry: dict[str, Any]
    services: dict[str, Any]
    _env_values: dict[str, str] | None = None

    def env_values(self) -> dict[str, str]:
        if self._env_values is None:
            path = self.root / self.cfg["env_file"]
            if not path.is_file():
                raise ToolError(EXIT_USAGE, "env_file_missing", f"file credenziali assente: {self.cfg['env_file']}")
            self._env_values = dba.parse_env_file(path)
        return self._env_values

    def catalog_dir(self, env: str, target: str) -> Path:
        return self.root / self.ccfg["directory"] / _segment(env, "ambiente") / _segment(target, "target")

    def state_file(self, env: str, target: str) -> Path:
        return (self.root / self.cfg["state_dir"] / "catalog" / _segment(env, "ambiente")
                / f"{_segment(target, 'target')}.json")


def build_ctx(root: Path) -> Ctx:
    cfg = dba.load_config(root)
    if not cfg.get("enabled"):
        raise ToolError(EXIT_USAGE, "capability_disabled", "db_access disabilitata: imposta db_access.enabled: true")
    return Ctx(root, cfg, catalog_cfg(cfg), dba.load_registry(root, cfg), dba.load_services(root, cfg))


def pick_targets(ctx: Ctx, env: str, requested: list[str]) -> list[str]:
    if env not in ctx.registry:
        raise ToolError(EXIT_USAGE, "unknown_env", f"ambiente sconosciuto: {env}", available=sorted(ctx.registry))
    if env not in ctx.ccfg["versioned_envs"]:
        raise ToolError(EXIT_USAGE, "env_not_versioned", f"{env} non e' fra gli ambienti del catalogo",
                        versioned_envs=ctx.ccfg["versioned_envs"])
    dbs = ctx.registry[env].get("databases") or {}
    if not requested:
        return sorted(dbs)
    unknown = [t for t in requested if t not in dbs]
    if unknown:
        raise ToolError(EXIT_USAGE, "unknown_target", f"target non definiti per {env}: {', '.join(unknown)}",
                        available=sorted(dbs))
    return list(dict.fromkeys(requested))


def service_use(ctx: Ctx, target: str) -> dict[str, list[str]]:
    """schema -> servizi che lo usano su questo target (services.*.uses[].schemas del registro)."""
    used: dict[str, set[str]] = {}
    for service, entry in (ctx.services or {}).items():
        for use in (entry or {}).get("uses") or []:
            if use.get("target") == target:
                for schema in use.get("schemas") or []:
                    used.setdefault(schema, set()).add(service)
    return {s: sorted(v) for s, v in used.items()}


def scope_of(ctx: Ctx, env: str, target: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    registered = set((ctx.registry[env]["databases"][target].get("schemas")) or [])
    used = service_use(ctx, target)

    class _Scope(dict):
        def __missing__(self, schema: str) -> str:
            return "in_registry" if schema in registered or schema in used else "out_of_registry"

    return _Scope(), used


def declared_reference_tables(ctx: Ctx, env: str, target: str) -> list[dict[str, Any]]:
    """`reference_tables: [{table: <schema>.<tabella>, reason: <testo>, columns: [..]}]` per target. `columns` e'
    facoltativo: se c'e', si estraggono solo quelle colonne (le guardie valgono su di esse)."""
    raw = (ctx.registry[env]["databases"][target]).get("reference_tables")
    if raw in (None, []):
        return []
    if not isinstance(raw, list):
        raise ToolError(EXIT_USAGE, "reference_tables_invalid", f"{env}/{target}: reference_tables deve essere una lista")
    out = []
    for entry in raw:
        if not isinstance(entry, dict) or not {"table", "reason"} <= set(entry) <= {"table", "reason", "columns"}:
            raise ToolError(EXIT_USAGE, "reference_tables_invalid",
                            f"{env}/{target}: ogni voce ha `table`, `reason` e, facoltativo, `columns`")
        table, reason = entry["table"], entry["reason"]
        if not isinstance(table, str) or not re.fullmatch(r"[^.\s]+\.[^.\s]+", table) \
                or not isinstance(reason, str) or not reason.strip():
            raise ToolError(EXIT_USAGE, "reference_tables_invalid",
                            f"{env}/{target}: `table` come <schema>.<tabella> e `reason` non vuoto")
        columns = entry.get("columns")
        if columns is not None and (not isinstance(columns, list) or not columns
                                    or not all(isinstance(c, str) and c.strip() for c in columns)
                                    or len(set(columns)) != len(columns)):
            raise ToolError(EXIT_USAGE, "reference_tables_invalid",
                            f"{env}/{target}: `columns` e' una lista non vuota di nomi di colonna distinti")
        item: dict[str, Any] = {"table": table, "reason": reason.strip()}
        if columns is not None:
            item["columns"] = [c.strip() for c in columns]
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _open(ctx: Ctx, resolved: dict[str, Any]):
    """Unico punto di apertura: transazione READ ONLY (sempre chiusa con ROLLBACK da chi la usa)."""
    return dba.open_connection(ctx.cfg, resolved, None, True)


def _query(conn, sql: str, params: tuple, secret: dict[str, str] | None) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
    except Exception as exc:  # noqa: BLE001 - classificato e riportato come ToolError
        code, kind = dba._error_class(exc)
        raise ToolError(code, kind, dba._scrub(str(exc).strip(), secret), sqlstate=dba._sqlstate(exc)) from exc
    if cur.description is None:
        return []
    return [tuple(r) for r in cur.fetchall()]


def _like_patterns(globs: list[str]) -> list[str]:
    out = []
    for glob in globs:
        out.append("".join("%" if ch == "*" else ("\\" + ch if ch in "_%\\" else ch) for ch in glob))
    return out


def is_system_schema(name: str, globs: list[str]) -> bool:
    return (name.startswith("pg_") or name == "information_schema"
            or any(fnmatch.fnmatchcase(name, g) for g in globs))


def _no_connect(err: ToolError) -> bool:
    message = str(err.payload.get("message") or "").lower()
    return (err.payload.get("sqlstate") == "42501" or "connect privilege" in message
            or "permission denied for database" in message)


def _cause(err: ToolError) -> str:
    """Causa breve e senza segreti (niente host, utenti o testo del server)."""
    if _no_connect(err):
        return "nessun privilegio CONNECT sul database"
    message = str(err.payload.get("message") or "").lower()
    if err.code == EXIT_TIMEOUT:
        return "timeout"
    if "timeout" in message or "timed out" in message:
        return "timeout di connessione"
    if "authentication" in message or "password" in message:
        return "autenticazione rifiutata"
    if err.payload.get("error") == "credentials_missing":
        return "credenziali assenti"
    if err.code == EXIT_CONNECT:
        return "connessione non riuscita"
    return f"errore {err.payload.get('error')}"


def read_fingerprints(ctx: Ctx, conn, secret) -> dict[str, dict[str, Any]]:
    """name -> {usable, fingerprint, objects, relations}; schemi di sistema esclusi, nomi senza duplicati."""
    globs = list(ctx.ccfg["system_schemas"])
    rows = _query(conn, fingerprint_sql(bool(ctx.ccfg["package_namespace_filter"])), (_like_patterns(globs),), secret)
    out: dict[str, dict[str, Any]] = {}
    for name, usable, fingerprint, objects, relations in rows:
        if is_system_schema(name, globs):
            continue
        entry = {"usable": bool(usable), "fingerprint": fingerprint if usable else None,
                 "objects": int(objects or 0), "relations": int(relations or 0)}
        if name not in out or (entry["usable"] and not out[name]["usable"]):
            out[name] = entry
    return out


# ---------------------------------------------------------------------------
# Rendering della DDL canonica
# ---------------------------------------------------------------------------

def _sorted(rows: list[dict[str, Any]], *keys: str) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: tuple(str(r.get(k) or "") for k in keys))


def render_schema(schema: str, objs: dict[str, list[dict[str, Any]]]) -> list[tuple[str, str]]:
    """Chunk (etichetta, testo) in ordine deterministico per tipo di oggetto e nome. Niente OWNER, GRANT, ACL,
    nessun dato (nessun INSERT/COPY, nessun setval/last_value). Le etichette sono solo nomi di oggetti."""
    def rows(kind: str) -> list[dict[str, Any]]:
        return objs.get(kind) or []

    any_row = next((r for c in CLASSES for r in rows(c.kind)), None)
    qs = any_row["schema"] if any_row else _quote_ident(schema)
    chunks: list[tuple[str, str]] = []

    def add(label: str, text: str) -> None:
        chunks.append((label, _canon(text)))

    header = " ".join(schema.split())
    add("schema", f"-- schema {header}: struttura canonica (solo definizioni: nessun dato, owner o ACL)\n"
                  f"CREATE SCHEMA IF NOT EXISTS {qs};")
    for r in _sorted(rows("extension"), "name"):
        add(f"extension {r['name']}",
            f"CREATE EXTENSION IF NOT EXISTS {r['name']} WITH SCHEMA {qs} VERSION {_lit(r['version'])};")
    for r in _sorted(rows("enum"), "name"):
        add(f"enum {r['name']}", f"CREATE TYPE {qs}.{r['name']} AS ENUM ({r['labels'] or ''});")
    for r in _sorted(rows("domain"), "name"):
        parts = [f"CREATE DOMAIN {qs}.{r['name']} AS {r['base']}"]
        if r["default"] is not None:
            parts.append(f"DEFAULT {r['default']}")
        if r["notnull"] is True or r["notnull"] == "true":
            parts.append("NOT NULL")
        if r["constraints"]:
            parts.append(r["constraints"])
        add(f"domain {r['name']}", " ".join(parts) + ";")
    for r in _sorted(rows("composite"), "name"):
        add(f"composite {r['name']}", f"CREATE TYPE {qs}.{r['name']} AS ({r['attrs'] or ''});")

    for r in _sorted(rows("sequence"), "name"):
        spec = (f"AS {r['type']} START WITH {r['start']} INCREMENT BY {r['increment']} MINVALUE {r['min']} "
                f"MAXVALUE {r['max']} CACHE {r['cache']} {'' if r['cycle'] in (True, 'true') else 'NO '}CYCLE")
        if r["identity"] in (True, "true"):
            owner = f" ({r['owned_by']})" if r["owned_by"] else ""
            add(f"sequence {r['name']}", f"-- identity sequence {qs}.{r['name']}{owner}: {spec}")
        else:
            add(f"sequence {r['name']}", f"CREATE SEQUENCE {qs}.{r['name']} {spec};")

    columns: dict[str, list[dict[str, Any]]] = {}
    for c in rows("column"):
        columns.setdefault(c["table"], []).append(c)
    pending = _sorted(rows("table"), "name")
    emitted: set[str] = set()
    local_tables = {t["name"] for t in pending}
    ordered: list[dict[str, Any]] = []
    while pending:
        progress = False
        for t in list(pending):
            deps = [p.split(".", 1)[1] for p in (t["parents"] or "").split(", ")
                    if p and p.split(".", 1)[0] == qs and p.split(".", 1)[1] in local_tables]
            if all(d in emitted for d in deps):
                ordered.append(t)
                emitted.add(t["name"])
                pending.remove(t)
                progress = True
        if not progress:        # dipendenze cicliche: impossibile, ma l'ordine resta deterministico
            ordered.extend(pending)
            break
    for t in ordered:
        kw = "CREATE UNLOGGED TABLE" if t["persistence"] == "u" else "CREATE TABLE"
        name = f"{qs}.{t['name']}"
        if t["ispartition"] in (True, "true") and t["parents"]:
            text = f"{kw} {name} PARTITION OF {t['parents']} {t['partbound']}"
            if t["partkey"]:
                text += f" PARTITION BY {t['partkey']}"
        else:
            defs = []
            for c in columns.get(t["name"], []):    # ordine di colonna: ORDER BY attnum dell'estrazione
                piece = f"{c['name']} {c['type']}"
                if c["generated"] == "s":
                    piece += f" GENERATED ALWAYS AS ({c['default']}) STORED"
                elif c["identity"] in ("a", "d"):
                    piece += f" GENERATED {'ALWAYS' if c['identity'] == 'a' else 'BY DEFAULT'} AS IDENTITY"
                elif c["default"] is not None:
                    piece += f" DEFAULT {c['default']}"
                if c["notnull"] in (True, "true"):
                    piece += " NOT NULL"
                defs.append(piece)
            body = "(\n    " + ",\n    ".join(defs) + "\n)" if defs else "()"
            text = f"{kw} {name} {body}"
            if t["parents"]:
                text += f" INHERITS ({t['parents']})"
            if t["partkey"]:
                text += f" PARTITION BY {t['partkey']}"
        add(f"table {t['name']}", text + ";")
    for r in _sorted(rows("sequence"), "name"):
        if r["owned_by"] and r["identity"] not in (True, "true"):
            add(f"sequence {r['name']} owned by",
                f"ALTER SEQUENCE {qs}.{r['name']} OWNED BY {r['owned_by']};")

    for kind, prefix in (("view", "CREATE VIEW"), ("matview", "CREATE MATERIALIZED VIEW")):
        for r in _sorted(rows(kind), "name"):
            opts = f" WITH ({r['options']})" if r["options"] and kind == "view" else ""
            definition = str(r["def"] or "").strip().rstrip(";").strip()
            tail = " WITH NO DATA" if kind == "matview" else ""
            add(f"{kind} {r['name']}", f"{prefix} {qs}.{r['name']}{opts} AS\n{definition}{tail};")

    rank = {"p": 0, "u": 1, "c": 2, "x": 3}
    for r in sorted(rows("constraint"), key=lambda r: (rank.get(r["contype"], 4), r["table"], r["name"])):
        add(f"constraint {r['table']}.{r['name']}",
            f"ALTER TABLE {qs}.{r['table']} ADD CONSTRAINT {r['name']} {r['def']};")
    for r in _sorted(rows("index"), "table", "name"):
        add(f"index {r['table']}.{r['name']}", f"{_canon(r['def']).rstrip(';')};")
    for r in _sorted(rows("function"), "name", "args"):
        add(f"{'procedure' if r['prokind'] == 'p' else 'function'} {r['name']}({r['args']})",
            _canon(r["def"]).rstrip(";") + ";")
    alter = {"D": "DISABLE TRIGGER", "R": "ENABLE REPLICA TRIGGER", "A": "ENABLE ALWAYS TRIGGER"}
    for r in _sorted(rows("trigger"), "table", "name"):
        text = f"{_canon(r['def']).rstrip(';')};"
        if r["enabled"] in alter:
            text += f"\nALTER TABLE {qs}.{r['table']} {alter[r['enabled']]} {r['name']};"
        add(f"trigger {r['table']}.{r['name']}", text)

    for r in _sorted(rows("comment_schema"), "schema"):
        add("comment schema", f"COMMENT ON SCHEMA {qs} IS {_lit(r['comment'])};")
    for r in _sorted(rows("comment_relation"), "objtype", "name"):
        add(f"comment {r['objtype'].lower()} {r['name']}",
            f"COMMENT ON {r['objtype']} {qs}.{r['name']} IS {_lit(r['comment'])};")
    for r in _sorted(rows("comment_column"), "table", "name"):
        add(f"comment column {r['table']}.{r['name']}",
            f"COMMENT ON COLUMN {qs}.{r['table']}.{r['name']} IS {_lit(r['comment'])};")
    for r in _sorted(rows("comment_function"), "name", "args"):
        add(f"comment {r['objtype'].lower()} {r['name']}({r['args']})",
            f"COMMENT ON {r['objtype']} {qs}.{r['name']}({r['args']}) IS {_lit(r['comment'])};")
    for r in _sorted(rows("comment_type"), "name"):
        add(f"comment type {r['name']}",
            f"COMMENT ON {r['objtype']} {qs}.{r['name']} IS {_lit(r['comment'])};")
    return chunks


def assemble(chunks: list[tuple[str, str]]) -> str:
    return "\n\n".join(text for _, text in chunks) + "\n"


def extract_schemas(ctx: Ctx, conn, secret, schemas: list[str]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    out: dict[str, dict[str, list[dict[str, Any]]]] = {s: {c.kind: [] for c in CLASSES} for s in schemas}
    pkg = bool(ctx.ccfg["package_namespace_filter"])
    for cls in CLASSES:
        seen: set[tuple] = set()
        for row in _query(conn, extraction_sql(cls, pkg), (list(schemas),), secret):
            if row[0] not in out or tuple(row) in seen:
                continue
            seen.add(tuple(row))
            out[row[0]][cls.kind].append(dict(zip(cls.names, row[1:])))
    return out


# ---------------------------------------------------------------------------
# Controllo anti-segreti (sempre attivo, non dipende da pii_scrub): credenziali e stringhe di connessione; mai il valore nell'esito
# ---------------------------------------------------------------------------

_KEYS = (r"(?<![a-z0-9])(?:[a-z0-9]+[_-])*(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|private[_-]?key"
         r"|auth[_-]?token|client[_-]?secret|token)(?![a-z0-9_])")
_RE_LITERAL = re.compile(_KEYS + r"[\"']?\s*(?::=|=|:)\s*(?:'{1,2}[^'\s][^']*'{1,2}|\"[^\"]+\")", re.I)
_RE_ADJACENT = re.compile(_KEYS + r"=[^\s'\";,)]+", re.I)
_RE_URL = re.compile(r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqps?|ldaps?|s?ftp|https?)://"
                     r"[^\s/:@'\"]+:[^\s/@'\"]+@", re.I)
_RE_HOST = re.compile(r"\bhost\s*=", re.I)
_RE_DBNAME = re.compile(r"\b(?:dbname|database)\s*=", re.I)
_RE_USER = re.compile(r"\buser(?:name)?\s*=", re.I)
_RE_PWD = re.compile(r"\b(?:password|passwd)\s*=", re.I)
_RE_AWS = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_RE_PEM = re.compile(r"-----BEGIN[ A-Z]*-----")
_RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+")
_RE_VENDOR = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{32,}"
                        r"|AIza[0-9A-Za-z_-]{35})\b")
_RE_BEARER = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/-]{20,}=*", re.I)

SECRET_RULES: list[tuple[str, Any]] = [
    ("credential_literal", lambda ln: bool(_RE_LITERAL.search(ln))),
    ("credential_adjacent", lambda ln: bool(_RE_ADJACENT.search(ln))),
    ("connection_url_with_credentials", lambda ln: bool(_RE_URL.search(ln))),
    ("connection_string_host_dbname", lambda ln: bool(_RE_HOST.search(ln) and _RE_DBNAME.search(ln))),
    ("connection_string_user_password", lambda ln: bool(_RE_USER.search(ln) and _RE_PWD.search(ln))),
    ("aws_access_key", lambda ln: bool(_RE_AWS.search(ln))),
    ("private_key_block", lambda ln: bool(_RE_PEM.search(ln))),
    ("jwt", lambda ln: bool(_RE_JWT.search(ln))),
    ("vendor_token", lambda ln: bool(_RE_VENDOR.search(ln))),
    ("bearer_token", lambda ln: bool(_RE_BEARER.search(ln))),
]


# Codici fiscali e partite IVA scritti come letterali nella DDL (es. una vista che filtra su un elenco fisso di
# organizzazioni): sono dati, non struttura, e non vanno nel repo. Si sostituisce solo il letterale intero, il resto
# della definizione resta 1:1. Codice fiscale di persona: 16 caratteri, con omocodia. Partita IVA (o codice fiscale
# numerico di un'organizzazione): 11 cifre con cifra di controllo valida, per non toccare altri numeri di 11 cifre.
CF_PLACEHOLDER = "CF_MASCHERATO"
PIVA_PLACEHOLDER = "PIVA_MASCHERATA"
_RE_CF_LITERAL = re.compile(
    r"'([A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z])'", re.I)
_RE_ELEVEN_DIGITS_LITERAL = re.compile(r"'([0-9]{11})'")


def piva_valid(digits: str) -> bool:
    """Cifra di controllo della partita IVA (algoritmo dell'Agenzia delle Entrate)."""
    if len(digits) != 11 or not digits.isdigit() or digits == "0" * 11:
        return False
    total = 0
    for i, ch in enumerate(digits[:10]):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10 == int(digits[10])


def mask_fiscal_literals(text: str) -> tuple[str, dict[str, int]]:
    """Sostituisce i letterali che sono codici fiscali o partite IVA; ritorna il testo e i conteggi (mai i valori)."""
    counts = {"codice_fiscale": 0, "partita_iva": 0}

    def cf(match: re.Match) -> str:
        counts["codice_fiscale"] += 1
        return f"'{CF_PLACEHOLDER}'"

    def piva(match: re.Match) -> str:
        if not piva_valid(match.group(1)):
            return match.group(0)
        counts["partita_iva"] += 1
        return f"'{PIVA_PLACEHOLDER}'"

    text = _RE_CF_LITERAL.sub(cf, text)
    text = _RE_ELEVEN_DIGITS_LITERAL.sub(piva, text)
    return text, {k: v for k, v in counts.items() if v}


def find_secrets(scope: str, chunks: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Finding {scope, object, line, rule}: la riga e' quella del file che verrebbe scritto. Mai il valore."""
    findings: list[dict[str, Any]] = []
    line_no = 1
    for label, text in chunks:
        for offset, line in enumerate(text.split("\n")):
            for rule, test in SECRET_RULES:
                if test(line):
                    findings.append({"schema": scope, "object": label, "line": line_no + offset, "rule": rule})
        line_no += text.count("\n") + 2          # il chunk piu' la riga vuota di separazione
    return findings


# ---------------------------------------------------------------------------
# Tabelle di dominio (valori di poche tabelle piccole e non personali, dichiarate nel registro)
# ---------------------------------------------------------------------------

def personal_match(column: str, names: list[str]) -> str | None:
    col = column.lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", col) if t]
    for name in names:
        low = name.lower()
        ntok = [t for t in re.split(r"[^a-z0-9]+", low) if t]
        if not ntok:
            continue
        if any(tokens[i:i + len(ntok)] == ntok for i in range(len(tokens) - len(ntok) + 1)):
            return name
        if len(low) >= 5 and "_" not in low and low in col:
            return name
    return None


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (bytes, bytearray, memoryview)):
        text = "\\x" + bytes(value).hex()
    elif isinstance(value, (dt.datetime, dt.date, dt.time)):
        text = value.isoformat()
    elif isinstance(value, (list, tuple, dict)):
        text = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    else:
        text = str(value)
    if text == "" or any(ch in text for ch in ',"\n\r') or text != text.strip():
        return '"' + text.replace('"', '""') + '"'
    return text


def _sort_key(value: Any) -> tuple:
    if value is None:
        return (0, 0)
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, (int, float)) or type(value).__name__ == "Decimal":
        return (2, float(value))
    return (3, _cell(value))


def canonical_csv(columns: list[str], rows: list[tuple]) -> str:
    """Intestazione + righe ordinate su tutte le colonne (ordinamento qui, indipendente da collation e tipi del
    server), LF, quoting fisso. NULL = campo vuoto senza apici; stringa vuota = \"\"."""
    ordered = sorted(rows, key=lambda r: tuple(_sort_key(v) for v in r))
    lines = [",".join(_cell(c) for c in columns)]
    lines += [",".join(_cell(v) for v in r) for r in ordered]
    return "\n".join(lines) + "\n"


def read_reference(ctx: Ctx, conn, secret, entry: dict[str, str]) -> dict[str, Any]:
    """Esito per una tabella dichiarata: status ok | unverified | inaccessible | refused. Una sola SELECT di
    valori, con LIMIT max+1 (mai lette righe oltre il massimo); le guardie sui nomi di colonna vengono prima."""
    schema, _, table = entry["table"].partition(".")
    base = {"table": entry["table"], "reason": entry["reason"]}
    rows = _query(conn, REFERENCE_COLUMNS_SQL, (schema, table), secret)
    seen, cols = set(), []
    for qualified, can_read, raw, quoted in rows:
        if raw not in seen:
            seen.add(raw)
            cols.append((raw, quoted))
    if not cols:
        return {**base, "status": "unverified", "cause": "tabella assente dal catalogo del database"}
    qualified = rows[0][0]
    if not all(bool(r[1]) for r in rows):
        return {**base, "status": "inaccessible", "cause": "nessun privilegio USAGE sullo schema o SELECT sulla tabella"}
    if entry.get("columns"):
        by_name = dict(cols)
        missing = [c for c in entry["columns"] if c not in by_name]
        if missing:
            return {**base, "status": "unverified", "cause": f"colonne dichiarate assenti dalla tabella: {missing}"}
        cols = [(c, by_name[c]) for c in entry["columns"]]
        base["columns"] = list(entry["columns"])
    for raw, _ in (cols if ctx.ccfg["pii_scrub"] else []):
        hit = personal_match(raw, list(ctx.ccfg["personal_column_names"]))
        if hit:
            return {**base, "status": "refused",
                    "cause": f"la colonna '{raw}' sembra un dato personale (nome simile a '{hit}')"}
    limit = int(ctx.ccfg["max_reference_rows"])
    data = _query(conn, REFERENCE_VALUES_TEMPLATE.format(
                      cols=", ".join(q for _, q in cols).replace("%", "%%"), table=qualified.replace("%", "%%")),
                  (limit + 1,), secret)
    if len(data) > limit:
        return {**base, "status": "refused", "cause": f"piu' di {limit} righe (massimo consentito)"}
    csv_text = canonical_csv([r for r, _ in cols], data)
    return {**base, "status": "ok", "rows": len(data), "csv": csv_text,
            "content_fingerprint": hashlib.sha256(csv_text.encode("utf-8")).hexdigest()}


# ---------------------------------------------------------------------------
# Riferimento (git) e stato locale
# ---------------------------------------------------------------------------

_REF_MEMO: dict[tuple, dict[str, Any]] = {}


def _git(root: Path, args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=timeout, check=False)


def _fetch_age_hours(ctx: Ctx) -> float | None:
    try:
        proc = _git(ctx.root, ["rev-parse", "--git-path", "FETCH_HEAD"], float(ctx.ccfg["git_timeout_s"]))
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    path = ctx.root / proc.stdout.decode("utf-8", "replace").strip()
    if not path.is_file():
        return None
    return round((utcnow().timestamp() - path.stat().st_mtime) / 3600, 1)


def reference_manifest(ctx: Ctx, env: str, target: str) -> dict[str, Any]:
    """Manifest di riferimento: `git show <ref>:<path>` (senza fetch di rete); se assente quello locale."""
    rel = manifest_relpath(ctx.ccfg, env, target)
    ref = str(ctx.ccfg["reference_ref"])
    key = (str(ctx.root), rel, ref)
    if key in _REF_MEMO:
        return _REF_MEMO[key]
    local_path = ctx.root / rel
    local = _read_json(local_path)
    origin_status, reason, remote = "unavailable", None, None
    try:
        proc = _git(ctx.root, ["show", f"{ref}:{rel}"], float(ctx.ccfg["git_timeout_s"]))
        if proc.returncode == 0:
            try:
                remote = json.loads(proc.stdout.decode("utf-8"))
                origin_status = "found"
            except ValueError:
                reason = f"manifest su {ref} non leggibile"
        else:
            err = proc.stderr.decode("utf-8", "replace")
            if "does not exist in" in err or "exists on disk, but not in" in err:
                origin_status = "missing"
            reason = f"git show {ref} exit {proc.returncode}"
    except subprocess.TimeoutExpired:
        reason = f"git show {ref}: timeout"
    except OSError:
        reason = "git non disponibile"
    result: dict[str, Any] = {"path": rel, "origin_status": origin_status, "local": local, "remote": remote}
    if origin_status == "found":
        result.update(manifest=remote, source=ref, note=None)
        result["needs_commit"] = local is not None and _canon_json(local) != _canon_json(remote)
        result["fetch_age_hours"] = None
    elif local is not None:
        result.update(manifest=local, source="local",
                      note=f"riferimento locale ({reason or 'manifest assente su ' + ref}): riferimento non aggiornato")
        result["needs_commit"] = True if origin_status == "missing" else None
        result["fetch_age_hours"] = _fetch_age_hours(ctx)
    else:
        result.update(manifest=None, source=None, note=None, needs_commit=False, fetch_age_hours=None)
    result["sha"] = (hashlib.sha256(_canon_json(result["manifest"]).encode("utf-8")).hexdigest()[:16]
                     if result["manifest"] else None)
    _REF_MEMO[key] = result
    return result


def load_state(ctx: Ctx, env: str, target: str) -> dict[str, Any]:
    return _read_json(ctx.state_file(env, target)) or {}


def save_state(ctx: Ctx, env: str, target: str, state: dict[str, Any]) -> None:
    _write_if_changed(ctx.state_file(env, target), _json_bytes(state))


def snapshot_age_days(manifest: dict[str, Any], state: dict[str, Any], now: dt.datetime) -> float:
    stamps = [manifest.get("scanned_at"), state.get("verified_at")]
    moments = [parse_iso(s) for s in stamps if s]
    if not moments:
        return float("inf")
    return round((now - max(moments)).total_seconds() / 86400, 1)


# ---------------------------------------------------------------------------
# catalog-check
# ---------------------------------------------------------------------------

def compare(manifest: dict[str, Any], live: dict[str, dict[str, Any]], scope: dict[str, str]) -> dict[str, dict[str, Any]]:
    recorded = manifest.get("schemas") or {}
    out: dict[str, dict[str, Any]] = {}
    for name in sorted(set(recorded) | set(live)):
        m, current = recorded.get(name), live.get(name)
        if current is None:
            state, change = "drift", "removed"
        elif not current["usable"]:
            if m is not None and not m.get("accessible", True):
                state, change = "inaccessible", "unchanged"
            elif m is None:
                state, change = "inaccessible", "new"
            else:
                state, change = "inaccessible", "access_lost"
        elif m is None:
            state, change = "missing", "new"
        elif not m.get("accessible", True):
            state, change = "drift", "access_gained"
        elif m.get("fingerprint") != current["fingerprint"]:
            state, change = "drift", "changed"
        elif m.get("scope") != scope[name]:
            state, change = "drift", "scope_changed"
        else:
            state, change = "fresh", "unchanged"
        out[name] = {"state": state, "change": change, "drift": change not in ("unchanged",)}
    return out


def _db_state(manifest: dict[str, Any], per_schema: dict[str, dict[str, Any]]) -> str:
    if manifest.get("accessible") is False:
        return "drift"                                  # il manifest dice inaccessibile ma ora ci si connette
    if manifest.get("extractor_version") != EXTRACTOR_VERSION:
        return "drift"
    if any(s["drift"] for s in per_schema.values()):
        return "drift"
    if per_schema and all(s["state"] == "inaccessible" for s in per_schema.values()):
        return "inaccessible"
    return "fresh"


def _warning(res: dict[str, Any]) -> str | None:
    state, label = res["state"], f"catalogo {res['env']}/{res['target']}"
    if state == "fresh":
        return None
    if state == "drift":
        changed = res.get("changed_schemas") or []
        text = f"{label}: drift su {', '.join(changed[:5])}{' ...' if len(changed) > 5 else ''}"
        if res.get("needs_sync"):
            text += " (serve catalog-scan)"
        elif res.get("needs_commit"):
            text += " (catalogo locale aggiornato ma non committato)"
        return text
    if state == "missing":
        return f"{label}: nessuno snapshot (serve catalog-scan)"
    if state == "inaccessible":
        return f"{label}: non accessibile ({res.get('cause')})"
    age = res.get("snapshot_age_days")
    if state == "stale":
        return (f"{label}: non verificato ({res.get('cause')}), snapshot di {age} giorni, "
                f"oltre la soglia di {res.get('stale_after_days')}")
    return f"{label}: non verificato ({res.get('cause')}), snapshot di {age} giorni"


def _base_result(ctx: Ctx, env: str, target: str, ref: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    return {"env": env, "target": target, "checked_at": iso(now), "cached": False,
            "reference": {"source": ref["source"], "note": ref["note"], "fetch_age_hours": ref["fetch_age_hours"]},
            "needs_commit": ref["needs_commit"], "needs_sync": False}


def _unverifiable(ctx: Ctx, res: dict[str, Any], manifest: dict[str, Any], state: dict[str, Any],
                  cause: str, now: dt.datetime) -> None:
    threshold = int(ctx.ccfg["stale_days"].get(res["env"], 14))
    age = snapshot_age_days(manifest, state, now)
    res.update(state="stale" if age > threshold else "unverified", cause=cause,
               snapshot_age_days=age if age != float("inf") else None, stale_after_days=threshold)
    res["schemas"] = {n: {"state": res["state"], "scope": e.get("scope")}
                      for n, e in sorted((manifest.get("schemas") or {}).items())}


def check_target(ctx: Ctx, env: str, target: str, refresh: bool) -> tuple[dict[str, Any], int]:
    now = utcnow()
    ref = reference_manifest(ctx, env, target)
    res = _base_result(ctx, env, target, ref, now)
    manifest = ref["manifest"]
    if manifest is None:
        res.update(state="missing", cause="nessuno snapshot", schemas={}, needs_sync=True)
        res["catalog_warning"] = _warning(res)
        return res, EXIT_OK
    state = load_state(ctx, env, target)
    last = state.get("last_check")
    if last and not refresh and last.get("reference_sha") == ref["sha"]:
        age_min = (now - parse_iso(last["checked_at"])).total_seconds() / 60
        if 0 <= age_min < float(ctx.ccfg["check_ttl_minutes"]):
            cached = dict(last["result"])
            cached["cached"] = True
            return cached, int(last.get("exit_code", 0))
    resolved = dba.resolve_target(ctx.registry, ctx.env_values(), env, target, ctx.cfg)
    res["dbname"] = resolved["public"]["dbname"]
    code = EXIT_OK
    live = None
    if resolved["secret"] is None:
        _unverifiable(ctx, res, manifest, state, "credenziali assenti", now)
        res["catalog_warning"] = _warning(res)
        return res, EXIT_USAGE
    try:
        conn = _open(ctx, resolved)
        try:
            live = read_fingerprints(ctx, conn, resolved["secret"])
        finally:
            conn.rollback()
            conn.close()
    except ToolError as err:
        code = err.code
        if _no_connect(err):
            res.update(state="inaccessible", cause=_cause(err), schemas={})
        else:
            _unverifiable(ctx, res, manifest, state, _cause(err), now)
    if live is not None:
        scope, _ = scope_of(ctx, env, target)
        per = compare(manifest, live, scope)
        db_state = _db_state(manifest, per)
        res.update(state=db_state, schemas={n: {"state": s["state"], "change": s["change"], "scope": scope[n]}
                                            for n, s in per.items()})
        res["changed_schemas"] = [n for n, s in per.items() if s["drift"]]
        res["inaccessible_schemas"] = [n for n, s in per.items() if s["state"] == "inaccessible"]
        res["needs_sync"] = db_state == "drift"
        if db_state == "drift" and ref["source"] not in (None, "local") and ref["needs_commit"]:
            # il riferimento e' origin/main: se il catalogo locale coincide col DB, serve solo il commit
            local_per = compare(ref["local"], live, scope)
            if _db_state(ref["local"], local_per) == "fresh":
                res["needs_sync"] = False
                res["local_is_current"] = True
        if db_state == "drift":
            state["overlay"] = {"checked_at": iso(now), "schemas": {
                n: {"fingerprint": v["fingerprint"], "objects": v["objects"]} for n, v in sorted(live.items())}}
        if db_state == "fresh":
            state["verified_at"] = iso(now)
    res["catalog_warning"] = _warning(res)
    state["last_check"] = {"checked_at": iso(now), "reference_sha": ref["sha"], "result": res, "exit_code": code}
    save_state(ctx, env, target, state)
    return res, code


def cmd_check(ctx: Ctx, args) -> int:
    targets = pick_targets(ctx, args.env, args.targets)
    results, code = [], EXIT_OK
    for target in targets:
        print(f"db_catalog: check {args.env}/{target}", file=sys.stderr)
        res, c = check_target(ctx, args.env, target, args.refresh)
        results.append(res)
        code = max(code, c)
    warnings = [r["catalog_warning"] for r in results if r.get("catalog_warning")]
    emit({"ok": code == EXIT_OK, "command": "catalog-check", "env": args.env, "targets": results,
          "needs_sync": any(r.get("needs_sync") for r in results),
          "needs_commit": any(r.get("needs_commit") for r in results),
          "catalog_warning": "; ".join(warnings) if warnings else None}, ctx, f"check-{args.env}")
    return code


# ---------------------------------------------------------------------------
# catalog-scan
# ---------------------------------------------------------------------------

def _carry_timestamps(new: dict[str, Any], old: dict[str, Any] | None, now: dt.datetime) -> None:
    for section in ("schemas", "reference_tables"):
        previous = (old or {}).get(section) or {}
        for name, entry in (new.get(section) or {}).items():
            before = previous.get(name)
            if before and _canon_json(_strip_ts(before)) == _canon_json(_strip_ts(entry)) and before.get("scanned_at"):
                entry["scanned_at"] = before["scanned_at"]
            else:
                entry["scanned_at"] = iso(now)


def _manifest_bytes(core: dict[str, Any], old: dict[str, Any] | None, now: dt.datetime) -> tuple[bytes | None, dict]:
    """Il manifest cambia solo a un cambio reale: `scanned_at` e' l'istante dell'ultimo cambio, non dell'ultimo
    scan (quello vive in <state_dir>). Ritorna (bytes da scrivere | None se invariato, manifest finale)."""
    _carry_timestamps(core, old, now)
    if old is not None and _canon_json(_strip_ts(old)) == _canon_json(_strip_ts(core)):
        return None, old
    core["scanned_at"] = iso(now)
    return _json_bytes(core), core


def _scan_failure(res: dict[str, Any], code: int, err: str, message: str, **extra: Any) -> tuple[dict[str, Any], int]:
    res.update(state="error", error=err, message=message, **extra)
    return res, code


def scan_target(ctx: Ctx, env: str, target: str, full: bool, dry_run: bool) -> tuple[dict[str, Any], int]:
    now = utcnow()
    ccfg = ctx.ccfg
    res: dict[str, Any] = {"env": env, "target": target}
    resolved = dba.resolve_target(ctx.registry, ctx.env_values(), env, target, ctx.cfg)
    res["dbname"] = resolved["public"]["dbname"]
    if resolved["secret"] is None:
        return _scan_failure(res, EXIT_USAGE, "credentials_missing", "credenziali assenti per questo target")
    secret = resolved["secret"]
    cdir = ctx.catalog_dir(env, target)
    manifest_path = cdir / "manifest.json"
    old = _read_json(manifest_path)
    declared = declared_reference_tables(ctx, env, target)
    scope, used = scope_of(ctx, env, target)

    try:
        conn = _open(ctx, resolved)
    except ToolError as err:
        if not _no_connect(err):
            return _scan_failure(res, err.code, err.payload.get("error", "connection"), _cause(err))
        base = copy.deepcopy(old) if old else {"manifest_version": MANIFEST_VERSION, "env": env, "target": target,
                                      "dbname": resolved["public"]["dbname"], "schemas": {}, "reference_tables": {}}
        cause = _cause(err)
        since = old.get("since") if old and old.get("accessible") is False and old.get("cause") == cause else None
        base.update(accessible=False, cause=cause, since=since or now.strftime("%Y-%m-%d"))
        payload, _ = _manifest_bytes(base, old, now)
        res.update(state="inaccessible", cause=cause, manifest="unchanged")
        if payload is not None:
            res["manifest"] = "dry-run" if dry_run else "written"
            if not dry_run:
                _write_if_changed(manifest_path, payload)
        return res, EXIT_CONNECT          # db non scansionabile: esito incompleto, mai 0
    try:
        if ccfg["repeatable_read"]:
            _query(conn, SNAPSHOT_SQL, (), secret)
        version_row = _query(conn, VERSION_SQL, (), secret)[0]
        live = read_fingerprints(ctx, conn, secret)
        prev_schemas = (old or {}).get("schemas") or {}
        outdated = bool(old) and old.get("extractor_version") != EXTRACTOR_VERSION
        to_extract = []
        for name, info in live.items():
            if info["usable"] and scope[name] == "in_registry":
                before = prev_schemas.get(name) or {}
                file_ok = (cdir / schema_filename(name)).is_file()
                if full or outdated or not file_ok or before.get("fingerprint") != info["fingerprint"]:
                    to_extract.append(name)
        extracted = extract_schemas(ctx, conn, secret, sorted(to_extract)) if to_extract else {}
        references = [read_reference(ctx, conn, secret, entry) for entry in declared]
    except ToolError as err:
        return _scan_failure(res, err.code, err.payload.get("error", "sql"), _cause(err))
    finally:
        conn.rollback()
        conn.close()

    # --- tutto in memoria: controlli prima di scrivere qualsiasi file -----------------------------------
    texts: dict[str, str] = {}
    masked: dict[str, dict[str, int]] = {}
    findings: list[dict[str, Any]] = []
    for name in sorted(extracted):
        chunks = render_schema(name, extracted[name])
        findings += find_secrets(name, chunks)
        texts[name], counts = (mask_fiscal_literals(assemble(chunks)) if ccfg["pii_scrub"]
                               else (assemble(chunks), {}))
        if counts:
            masked[name] = counts
    csvs: dict[str, str] = {}
    for ref in references:
        if ref["status"] == "ok":
            lines = [("reference " + ref["table"], ref["csv"].rstrip("\n"))]
            findings += find_secrets("reference/" + ref["table"], lines)
            csvs[ref["table"]] = ref["csv"]
    if findings:
        return _scan_failure(res, EXIT_SECRET, "secret_found",
                             "controllo anti-segreti scattato: nessun file scritto per questo database",
                             findings=findings)

    flavor = "postgresql" if str(version_row[1]).lower().startswith("postgresql") and "(" not in str(version_row[1]) else "postgres-compatible"
    entries: dict[str, Any] = {}
    for name, info in sorted(live.items()):
        entry: dict[str, Any] = {"scope": scope[name], "accessible": info["usable"]}
        if used.get(name):
            entry["used_by"] = used[name]
        if info["usable"]:
            entry.update(fingerprint=info["fingerprint"], objects=info["objects"], relations=info["relations"])
            if scope[name] == "in_registry":
                entry["ddl_file"] = schema_filename(name)
                if name in masked:
                    entry["masked_literals"] = masked[name]
                elif name not in extracted and (prev_schemas.get(name) or {}).get("masked_literals"):
                    entry["masked_literals"] = prev_schemas[name]["masked_literals"]   # file invariato
        else:
            cause = "nessun privilegio USAGE sullo schema"
            before = prev_schemas.get(name) or {}
            entry["cause"] = cause
            entry["since"] = (before.get("since") if before.get("accessible") is False
                              and before.get("cause") == cause else None) or now.strftime("%Y-%m-%d")
        entries[name] = entry
    ref_entries: dict[str, Any] = {}
    prev_refs = (old or {}).get("reference_tables") or {}
    for ref in references:
        if ref["status"] == "ok":
            ref_entries[ref["table"]] = {
                "rows": ref["rows"], "content_fingerprint": ref["content_fingerprint"], "reason": ref["reason"],
                "file": f"reference/{ref['table']}.csv"}
            if ref.get("columns"):
                ref_entries[ref["table"]]["columns"] = ref["columns"]
        elif ref["table"] in prev_refs:
            ref_entries[ref["table"]] = prev_refs[ref["table"]]      # non estraibile ora: resta l'ultimo noto
    not_covered = list(NOT_COVERED)
    if flavor != "postgresql":
        not_covered.append("oggetti non standard della distribuzione (package, sinonimi): non coperti, probe non eseguito")
    core = {"manifest_version": MANIFEST_VERSION, "env": env, "target": target, "dbname": res["dbname"],
            "accessible": True, "server_version": str(version_row[0]), "server_flavor": flavor,
            "extractor_version": EXTRACTOR_VERSION, "object_classes": [c.kind for c in CLASSES],
            "not_covered": not_covered, "schemas": entries, "reference_tables": ref_entries}
    if not ccfg["pii_scrub"]:
        core["pii_scrub"] = False          # catalogo non mascherato: dichiarato nel manifest
    payload, _final = _manifest_bytes(core, old, now)

    written, removed = [], []
    wanted = {e["ddl_file"] for e in entries.values() if e.get("ddl_file")}
    wanted |= {e["file"] for e in ref_entries.values()}
    for name, text in texts.items():
        path = cdir / schema_filename(name)
        if dry_run:
            if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
                written.append(_rel(ctx.root, path))
        elif _write_if_changed(path, text.encode("utf-8")):
            written.append(_rel(ctx.root, path))
    for table, text in csvs.items():
        path = cdir / "reference" / f"{table}.csv"
        if dry_run:
            if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
                written.append(_rel(ctx.root, path))
        elif _write_if_changed(path, text.encode("utf-8")):
            written.append(_rel(ctx.root, path))
    for stale in sorted({e.get("ddl_file") for e in prev_schemas.values() if e.get("ddl_file")}
                        | {e.get("file") for e in prev_refs.values() if e.get("file")}):
        if stale not in wanted and (cdir / stale).is_file():
            removed.append(_rel(ctx.root, cdir / stale))
            if not dry_run:
                (cdir / stale).unlink()
    res["manifest"] = "unchanged"
    if payload is not None:
        res["manifest"] = "dry-run" if dry_run else "written"
        if not dry_run:
            _write_if_changed(manifest_path, payload)
            written.append(_rel(ctx.root, manifest_path))

    problems = [r for r in references if r["status"] != "ok"]
    res.update(state="ok" if not problems else "incomplete", server_version=str(version_row[0]),
               server_flavor=flavor, extracted=sorted(texts), written=written, removed=removed,
               schemas={n: {"scope": e["scope"], "accessible": e["accessible"],
                            "action": ("inaccessible" if not e["accessible"] else
                                       "extracted" if n in texts else
                                       "no_ddl" if e["scope"] != "in_registry" else "unchanged")}
                        for n, e in entries.items()},
               reference_tables=[{k: v for k, v in r.items() if k not in ("csv",)} for r in references],
               warnings=[f"schema in registro non leggibile: {n}" for n, e in entries.items()
                         if not e["accessible"] and e["scope"] == "in_registry"])
    if not dry_run:
        state = load_state(ctx, env, target)
        state.pop("last_check", None)
        state.pop("overlay", None)
        state["verified_at"] = iso(now)
        state["last_scan_at"] = iso(now)
        save_state(ctx, env, target, state)
    return res, (EXIT_GATE if problems else EXIT_OK)


def cmd_scan(ctx: Ctx, args) -> int:
    targets = pick_targets(ctx, args.env, args.targets)
    results, code = [], EXIT_OK
    for target in targets:
        print(f"db_catalog: scan {args.env}/{target}", file=sys.stderr)
        res, c = scan_target(ctx, args.env, target, args.full, args.dry_run)
        results.append(res)
        code = max(code, c)
    failed = [{"target": r["target"], "state": r["state"], "error": r.get("error"),
               "message": r.get("message") or r.get("cause")}
              for r in results if r["state"] in ("error", "inaccessible")]
    emit({"ok": code == EXIT_OK, "command": "catalog-scan", "env": args.env, "dry_run": bool(args.dry_run),
          "complete": not failed and all(r["state"] != "incomplete" for r in results),
          "failed": failed, "targets": results}, ctx, f"scan-{args.env}")
    return code


# ---------------------------------------------------------------------------
# catalog-status (offline)
# ---------------------------------------------------------------------------

def cmd_status(ctx: Ctx, args) -> int:
    envs = [args.env] if args.env else [e for e in ctx.ccfg["versioned_envs"] if e in ctx.registry]
    now, rows = utcnow(), []
    for env in envs:
        if env not in ctx.registry:
            raise ToolError(EXIT_USAGE, "unknown_env", f"ambiente sconosciuto: {env}", available=sorted(ctx.registry))
        threshold = int(ctx.ccfg["stale_days"].get(env, 14))
        for target in sorted(ctx.registry[env].get("databases") or {}):
            manifest = _read_json(ctx.catalog_dir(env, target) / "manifest.json")
            if manifest is None:
                rows.append({"env": env, "target": target, "state": "missing"})
                continue
            age = snapshot_age_days(manifest, load_state(ctx, env, target), now)
            schemas = manifest.get("schemas") or {}
            state = ("inaccessible" if manifest.get("accessible") is False
                     else "stale" if age > threshold else "unverified")
            rows.append({
                "env": env, "target": target, "dbname": manifest.get("dbname"), "state": state,
                "cause": manifest.get("cause"), "scanned_at": manifest.get("scanned_at"),
                "snapshot_age_days": age if age != float("inf") else None, "stale_after_days": threshold,
                "server_version": manifest.get("server_version"),
                "extractor_outdated": manifest.get("extractor_version") != EXTRACTOR_VERSION,
                "schemas": {n: {"scope": e.get("scope"), "accessible": e.get("accessible"),
                                "objects": e.get("objects")} for n, e in sorted(schemas.items())},
                "reference_tables": sorted((manifest.get("reference_tables") or {}))})
    warnings = [f"catalogo {r['env']}/{r['target']}: {r['state']}" for r in rows if r["state"] in ("stale", "missing")]
    emit({"ok": True, "command": "catalog-status", "offline": True, "targets": rows,
          "catalog_warning": "; ".join(warnings) if warnings else None}, ctx, "status")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Output e CLI
# ---------------------------------------------------------------------------

def emit(payload: dict[str, Any], ctx: Ctx, name: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text.encode("utf-8")) <= MAX_STDOUT_BYTES:
        print(text)
        return
    path = ctx.root / ctx.cfg["state_dir"] / "catalog" / "output" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    targets = payload.get("targets") or []
    print(json.dumps({"ok": payload.get("ok"), "output_file": str(path),
                      "summary": {"command": payload.get("command"), "env": payload.get("env"),
                                  "targets": [{"target": t.get("target"), "state": t.get("state")} for t in targets],
                                  "catalog_warning": payload.get("catalog_warning")}}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Catalogo DDL dei database (sola lettura verso i DB).")
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[2]),
                   help="root della factory (default: dedotta dal path dello script)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("catalog-check")
    c.add_argument("env")
    c.add_argument("targets", nargs="*")
    c.add_argument("--refresh", action="store_true", help="ignora il TTL e verifica ora")
    s = sub.add_parser("catalog-scan")
    s.add_argument("env")
    s.add_argument("targets", nargs="*")
    s.add_argument("--full", action="store_true", help="rilegge e rigenera la DDL di tutti gli schemi in scope")
    s.add_argument("--dry-run", action="store_true", help="calcola e riporta senza scrivere file")
    st = sub.add_parser("catalog-status")
    st.add_argument("env", nargs="?")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _REF_MEMO.clear()
    try:
        ctx = build_ctx(Path(args.root))
        handler = {"catalog-check": cmd_check, "catalog-scan": cmd_scan, "catalog-status": cmd_status}[args.cmd]
        return handler(ctx, args)
    except ToolError as err:
        print(json.dumps(err.payload, ensure_ascii=False, default=str))
        print(f"db_catalog: {err.payload['error']}: {err.payload['message']}", file=sys.stderr)
        return err.code


if __name__ == "__main__":
    sys.exit(main())
