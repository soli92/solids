#!/usr/bin/env python3
"""Mappa funzionalita' -> microservizio -> database/schema -> tabella e relazioni logiche tra database.

Lavora solo sui file: il catalogo DDL (memory/semantic/db-catalog/<env>/<db>/<schema>.sql), il registro
(tools/db/db-targets.yaml) e la mappa (memory/semantic/db-catalog/feature-map.yaml). Nessuna connessione a
database, nessuna lettura di righe: una relazione logica non si prova sui dati.

Sottocomandi (JSON su stdout, diagnostica su stderr):

  map-check [--env ENV]
        Valida feature-map.yaml: schema, id unici, servizi presenti nel registro, ogni tabella e colonna citata
        presente nel catalogo dell'ambiente (default prod; poi riporta in quali altri ambienti manca), fonti
        esistenti su disco, regole di confidenza (verified e derived richiedono fonte e catalogo; unverified con
        estremo assente dal catalogo finisce tra i `gap_candidates`, da portare in gaps.md).
  map-suggest-relations [--env ENV] [--scope cross_db|cross_schema|intra_schema ...] [--write-candidates]
        Legge le DDL di tutti i DB dell'ambiente e propone relazioni logiche senza chiave esterna dichiarata:
        colonne `<entita>_id`, `<entita>_uid`, `uid_<entita>` (anche con prefissi: `parent_organization_id`,
        alias `org`) il cui nome corrisponde a una tabella con chiave primaria `uid` o `id`. Ogni candidato e'
        `derived`, mai `verified`. `--write-candidates` riscrive la sezione `relation_candidates` della mappa
        (idempotente: stesso input, stesso file).
  map-locate TERMINE [--env ENV]
        Dato un termine (funzionalita', servizio, tabella, colonna) restituisce funzionalita', servizi, tabelle e
        relazioni collegate, con fonti e confidenza, e per ogni tabella se esiste nel catalogo dell'ambiente.

Exit code: 0 ok | 1 mappa non valida o incompleta | 2 uso o configurazione (file mancanti, ambiente sconosciuto).
Un risultato incompleto non esce mai con 0.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2

ENVS = ("dev", "test", "staging", "preprod", "prod")
CONFIDENCE = ("verified", "derived", "unverified")
MAX_STDOUT_BYTES = 32 * 1024
MAP_VERSION = 1

DEFAULT_MAP = "memory/semantic/db-catalog/feature-map.yaml"
DEFAULT_CATALOG = "memory/semantic/db-catalog"
DEFAULT_REGISTRY = "tools/db/db-targets.yaml"
DEFAULT_OUT_DIR = ".db-access-state/map"

SCOPES = ("cross_db", "cross_schema", "intra_schema")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

TOP_KEYS = {"version", "meta", "features", "services", "relations", "relation_candidates"}
FEATURE_KEYS = {"id", "name", "area", "description", "services", "tables", "sources", "confidence", "note"}
SERVICE_ITEM_KEYS = {"name", "role", "confidence", "sources", "code_refs", "registry", "note"}
TABLE_ITEM_KEYS = {"ref", "columns", "confidence", "sources", "used_by", "envs", "code_refs", "note"}
SERVICE_ATTR_KEYS = {"description", "repo", "area", "sources", "note"}
RELATION_KEYS = {"id", "from", "to", "kind", "evidence", "confidence", "sources", "features", "note"}
CANDIDATE_KEYS = {"from", "to", "kind", "scope", "reason", "confidence", "env"}
SOURCE_KEYS = {"path", "note", "line"}
CODE_REF_KEYS = {"repo", "entity", "table", "note"}

# Tabelle che non rappresentano un'entita' di dominio: storiche, backup, di servizio. Non sono ne' sorgente ne'
# destinazione dei candidati (la storia di una tabella eredita il nome della colonna, non e' una relazione).
SKIP_TABLE = re.compile(
    r"(_history|_bk|_bck|_bak|_aud|_legacy|_backup|_\d{8})$"
    r"|^(flyway_schema_history|shedlock|transactional_outbox|batch_.+|temp_.+)$")
ALIASES = {"org": "organization", "orgs": "organization"}


class ToolError(Exception):
    def __init__(self, code: int, error: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.payload: dict[str, Any] = {"ok": False, "error": error, "message": message, **extra}


# ---------------------------------------------------------------------------
# Contesto e caricamento file
# ---------------------------------------------------------------------------

@dataclass
class Ctx:
    root: Path
    map_path: Path
    catalog_dir: Path
    registry_path: Path
    out_dir: Path

    def rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()


_FILE_MEMO: dict[tuple[str, int, int], Any] = {}


def _stat_key(path: Path, tag: str) -> tuple[str, int, int]:
    st = path.stat()
    return (f"{tag}:{path.resolve()}", st.st_mtime_ns, st.st_size)


def load_yaml(path: Path) -> Any:
    import yaml  # import pigro: il modulo resta leggero all'import

    key = _stat_key(path, "yaml")
    if key not in _FILE_MEMO:
        _FILE_MEMO[key] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _FILE_MEMO[key]


def load_registry(ctx: Ctx) -> dict[str, Any]:
    if not ctx.registry_path.is_file():
        raise ToolError(EXIT_USAGE, "registry_missing", f"registro non trovato: {ctx.rel(ctx.registry_path)}")
    data = load_yaml(ctx.registry_path) or {}
    return {"environments": data.get("environments") or {}, "services": data.get("services") or {}}


def load_map(ctx: Ctx) -> Any:
    import yaml

    if not ctx.map_path.is_file():
        raise ToolError(EXIT_USAGE, "map_missing", f"mappa non trovata: {ctx.rel(ctx.map_path)}")
    try:
        return load_yaml(ctx.map_path)
    except yaml.YAMLError as err:
        raise ToolError(EXIT_INVALID, "yaml_invalid", f"{ctx.rel(ctx.map_path)}: {err}") from err


# ---------------------------------------------------------------------------
# Catalogo DDL
# ---------------------------------------------------------------------------

@dataclass
class Table:
    target: str
    schema: str
    name: str
    columns: dict[str, str]
    file: str
    line: int
    pk: list[str] = field(default_factory=list)
    fks: list[tuple[list[str], str, str, list[str]]] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.target, self.schema, self.name)


@dataclass
class Catalog:
    env: str
    targets: set[str] = field(default_factory=set)
    schemas: dict[str, set[str]] = field(default_factory=dict)
    tables: dict[tuple[str, str, str], Table] = field(default_factory=dict)


_IDENT = r'(?:"(?:[^"]|"")+"|[\w$]+)'
_QNAME = rf"{_IDENT}(?:\.{_IDENT})?"
_CREATE_TABLE = re.compile(rf"^CREATE TABLE (?P<name>{_QNAME}) \($")
_CREATE_SCHEMA = re.compile(rf"^CREATE SCHEMA IF NOT EXISTS (?P<name>{_IDENT});$")
_COLUMN = re.compile(rf"^ {{4}}(?P<name>{_IDENT}) (?P<rest>.+?),?$")
_ALTER_PK = re.compile(rf"^ALTER TABLE (?:ONLY )?(?P<t>{_QNAME}) ADD CONSTRAINT {_IDENT} PRIMARY KEY \((?P<cols>[^)]*)\)")
_ALTER_FK = re.compile(
    rf"^ALTER TABLE (?:ONLY )?(?P<t>{_QNAME}) ADD CONSTRAINT {_IDENT} FOREIGN KEY \((?P<cols>[^)]*)\) "
    rf"REFERENCES (?P<rt>{_QNAME})\((?P<rcols>[^)]*)\)")
_NOT_COLUMN = ("CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "LIKE", "EXCLUDE")
_TYPE_END = re.compile(r"\s+(DEFAULT|NOT NULL|NULL|GENERATED|CONSTRAINT|REFERENCES|CHECK|PRIMARY|UNIQUE|COLLATE)\b")


def _unquote(ident: str) -> str:
    ident = ident.strip()
    if ident.startswith('"') and ident.endswith('"') and len(ident) >= 2:
        return ident[1:-1].replace('""', '"')
    return ident


def _split_qname(name: str, default_schema: str) -> tuple[str, str]:
    parts = re.findall(_IDENT, name)
    if len(parts) >= 2:
        return _unquote(parts[0]), _unquote(parts[1])
    return default_schema, _unquote(parts[0])


def _split_cols(text: str) -> list[str]:
    return [_unquote(c) for c in re.findall(_IDENT, text)]


def parse_ddl(text: str, target: str, file_rel: str, stem: str) -> tuple[str, list[Table]]:
    """Tabelle, chiavi primarie ed esterne di un file `<schema>.sql` del catalogo."""
    schema = stem
    tables: dict[tuple[str, str], Table] = {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _CREATE_SCHEMA.match(line)
        if m:
            schema = _unquote(m.group("name"))
        m = _CREATE_TABLE.match(line)
        if m:
            sch, name = _split_qname(m.group("name"), schema)
            columns: dict[str, str] = {}
            start = i + 1
            i += 1
            while i < len(lines) and not lines[i].startswith(")"):
                cm = _COLUMN.match(lines[i])
                if cm and not cm.group("name").upper().startswith(_NOT_COLUMN):
                    rest = cm.group("rest")
                    end = _TYPE_END.search(rest)
                    columns[_unquote(cm.group("name"))] = (rest[:end.start()] if end else rest).strip().lower()
                i += 1
            tables[(sch, name)] = Table(target, sch, name, columns, file_rel, start)
        i += 1
    for line in lines:
        if not line.startswith("ALTER TABLE"):
            continue
        m = _ALTER_PK.match(line)
        if m:
            sch, name = _split_qname(m.group("t"), schema)
            if (sch, name) in tables:
                tables[(sch, name)].pk = _split_cols(m.group("cols"))
            continue
        m = _ALTER_FK.match(line)
        if m:
            sch, name = _split_qname(m.group("t"), schema)
            rsch, rname = _split_qname(m.group("rt"), sch)
            if (sch, name) in tables:
                tables[(sch, name)].fks.append((_split_cols(m.group("cols")), rsch, rname, _split_cols(m.group("rcols"))))
    return schema, list(tables.values())


def load_catalog(ctx: Ctx, env: str) -> Catalog:
    key = (f"catalog:{ctx.catalog_dir.resolve()}:{env}", 0, 0)
    files: list[tuple[str, Path]] = []
    env_dir = ctx.catalog_dir / env
    if env_dir.is_dir():
        for db_dir in sorted(p for p in env_dir.iterdir() if p.is_dir()):
            for sql in sorted(db_dir.glob("*.sql")):
                files.append((db_dir.name, sql))
    sig = tuple((t, str(p), p.stat().st_mtime_ns, p.stat().st_size) for t, p in files)
    memo_key = (key[0], hash(sig), len(sig))
    if memo_key in _FILE_MEMO:
        return _FILE_MEMO[memo_key]
    cat = Catalog(env)
    if env_dir.is_dir():
        cat.targets = {p.name for p in env_dir.iterdir() if p.is_dir()}
    for target, sql in files:
        schema, tables = parse_ddl(sql.read_text(encoding="utf-8"), target, ctx.rel(sql), sql.stem)
        cat.schemas.setdefault(target, set()).add(schema)
        for table in tables:
            cat.schemas[target].add(table.schema)
            cat.tables[table.key] = table
    _FILE_MEMO[memo_key] = cat
    return cat


# ---------------------------------------------------------------------------
# Riferimenti e stato di presenza nel catalogo
# ---------------------------------------------------------------------------

def parse_table_ref(ref: str) -> tuple[str, str, str] | None:
    parts = ref.split(".", 2)
    if len(parts) != 3 or not all(p.strip() for p in parts):
        return None
    return parts[0], parts[1], parts[2]


def parse_column_ref(ref: str) -> tuple[str, str, str, str] | None:
    head, _, col = ref.rpartition(".")
    table = parse_table_ref(head) if head else None
    if table is None or not col.strip():
        return None
    return table[0], table[1], table[2], col


def registry_targets(registry: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for env in registry["environments"].values():
        out.update((env.get("databases") or {}).keys())
    return out


def presence(cat: Catalog, targets_in_registry: set[str], target: str, schema: str, table: str,
             columns: list[str]) -> dict[str, Any]:
    """Stato di (target, schema, tabella, colonne) nel catalogo dell'ambiente."""
    if target not in targets_in_registry:
        return {"status": "target_not_in_registry"}
    if target not in cat.targets or target not in cat.schemas:
        return {"status": "catalog_unavailable", "detail": "nessuna DDL per il database in questo ambiente"}
    if schema not in cat.schemas[target]:
        return {"status": "catalog_unavailable", "detail": "nessuna DDL per lo schema in questo ambiente"}
    tab = cat.tables.get((target, schema, table))
    if tab is None:
        return {"status": "table_missing"}
    missing = [c for c in columns if c not in tab.columns]
    if missing:
        return {"status": "column_missing", "missing_columns": missing, "catalog_ref": f"{tab.file}:{tab.line}"}
    return {"status": "ok", "catalog_ref": f"{tab.file}:{tab.line}"}


# ---------------------------------------------------------------------------
# map-check
# ---------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []
        self.gap_candidates: list[dict[str, Any]] = []
        self.env_gaps: list[dict[str, Any]] = []
        self.skipped: list[dict[str, Any]] = []

    def error(self, code: str, where: str, message: str, **extra: Any) -> None:
        self.errors.append({"code": code, "where": where, "message": message, **extra})

    def warn(self, code: str, where: str, message: str, **extra: Any) -> None:
        self.warnings.append({"code": code, "where": where, "message": message, **extra})


def _is_list(value: Any) -> bool:
    return isinstance(value, list)


def _check_keys(rep: Report, where: str, item: dict[str, Any], allowed: set[str]) -> None:
    for key in sorted(set(item) - allowed):
        rep.error("unknown_key", where, f"chiave non prevista: {key}")


def _check_confidence(rep: Report, where: str, item: dict[str, Any], required: bool = True) -> str | None:
    conf = item.get("confidence")
    if conf is None:
        if required:
            rep.error("confidence_missing", where, "marcatore di confidenza assente (verified, derived, unverified)")
        return None
    if conf not in CONFIDENCE:
        rep.error("confidence_invalid", where, f"confidenza non ammessa: {conf!r}", allowed=list(CONFIDENCE))
        return None
    return conf


def _check_sources(ctx: Ctx, rep: Report, where: str, item: dict[str, Any], conf: str | None) -> None:
    sources = item.get("sources")
    if sources is None:
        sources = []
    if not _is_list(sources):
        rep.error("sources_invalid", where, "`sources` deve essere una lista di {path, note}")
        return
    if conf in ("verified", "derived") and not sources:
        rep.error("source_missing", where, f"confidenza {conf} senza fonte: serve almeno un {{path, note}}")
    for n, src in enumerate(sources):
        w = f"{where}.sources[{n}]"
        if not isinstance(src, dict) or not isinstance(src.get("path"), str) or not src["path"].strip():
            rep.error("source_invalid", w, "la fonte deve avere `path` (stringa)")
            continue
        _check_keys(rep, w, src, SOURCE_KEYS)
        path = src["path"].strip()
        norm = path.replace("\\", "/")
        if norm.startswith("/") or ".." in norm.split("/") or re.match(r"^[A-Za-z]:", norm):
            rep.error("source_path_invalid", w, "la fonte e' un path relativo alla radice del repo", path=path)
            continue
        if norm.startswith("code_repos/"):
            rep.error("source_code_repos_path", w,
                      "i riferimenti al codice si scrivono in `code_refs` (repo e nome di entity o tabella), "
                      "non come path di file", path=path)
            continue
        if not (ctx.root / norm).exists():
            rep.error("source_not_found", w, "la fonte non esiste su disco", path=path)


def _check_code_refs(rep: Report, where: str, item: dict[str, Any]) -> None:
    refs = item.get("code_refs")
    if refs is None:
        return
    if not _is_list(refs):
        rep.error("code_refs_invalid", where, "`code_refs` deve essere una lista di {repo, entity|table}")
        return
    for n, ref in enumerate(refs):
        w = f"{where}.code_refs[{n}]"
        if not isinstance(ref, dict) or not ref.get("repo") or not (ref.get("entity") or ref.get("table")):
            rep.error("code_ref_invalid", w, "il riferimento al codice ha `repo` e `entity` o `table`")
            continue
        _check_keys(rep, w, ref, CODE_REF_KEYS)
        for key in ("repo", "entity", "table"):
            value = ref.get(key)
            if isinstance(value, str) and ("/" in value or "\\" in value or re.search(r"\.\w+$", value)):
                rep.error("code_ref_is_path", w, f"`{key}` e' un nome, non un path di file", value=value)


def _judge(rep: Report, where: str, conf: str | None, state: dict[str, Any], what: str) -> None:
    """verified e derived esigono l'estremo nel catalogo; unverified con estremo assente e' un gap."""
    status = state["status"]
    if status == "ok":
        return
    if conf in ("verified", "derived"):
        rep.error(f"{conf}_not_in_catalog", where,
                  f"{what}: {status}, ma la confidenza e' {conf} (richiede la presenza nel catalogo)", **state)
    else:
        rep.gap_candidates.append({"where": where, "what": what, **state})


def _env_coverage(rep: Report, where: str, what: str, primary: str, states: dict[str, dict[str, Any]],
                  expected: list[str]) -> None:
    for env in expected:
        if env == primary:
            continue
        st = states.get(env)
        if st and st["status"] != "ok":
            rep.env_gaps.append({"where": where, "what": what, "env": env, **st})


def check_map(ctx: Ctx, env: str) -> dict[str, Any]:
    registry = load_registry(ctx)
    data = load_map(ctx)
    rep = Report()
    reg_services: dict[str, Any] = registry["services"]
    reg_targets = registry_targets(registry)
    catalogs = {e: load_catalog(ctx, e) for e in ENVS}
    primary = catalogs[env]
    if not primary.tables:
        raise ToolError(EXIT_USAGE, "catalog_missing",
                        f"nessuna DDL nel catalogo dell'ambiente {env}: {ctx.rel(ctx.catalog_dir / env)}")

    counts = {"features": 0, "service_links": 0, "table_links": 0, "relations": 0, "relation_candidates": 0}
    by_conf: dict[str, dict[str, int]] = {k: {c: 0 for c in CONFIDENCE} for k in ("service_links", "table_links", "relations")}

    if not isinstance(data, dict):
        rep.error("map_invalid", "<root>", "la mappa deve essere un dizionario YAML")
        return _finish(ctx, env, rep, counts, by_conf)
    _check_keys(rep, "<root>", data, TOP_KEYS)
    if data.get("version") != MAP_VERSION:
        rep.error("version_invalid", "version", f"versione attesa: {MAP_VERSION}")
    features = data.get("features")
    if not _is_list(features) or not features:
        rep.error("features_missing", "features", "`features` deve essere una lista non vuota")
        features = []

    def check_table_item(w: str, tab: dict[str, Any], fsvc: dict[str, str]) -> None:
        _check_keys(rep, w, tab, TABLE_ITEM_KEYS)
        conf = _check_confidence(rep, w, tab)
        _check_sources(ctx, rep, w, tab, conf)
        _check_code_refs(rep, w, tab)
        ref = parse_table_ref(tab["ref"]) if isinstance(tab.get("ref"), str) else None
        if ref is None:
            rep.error("table_ref_invalid", w, "`ref` deve essere target.schema.tabella", ref=tab.get("ref"))
            return
        cols = tab.get("columns") or []
        if not _is_list(cols) or not all(isinstance(c, str) for c in cols):
            rep.error("columns_invalid", w, "`columns` deve essere una lista di nomi di colonna")
            cols = []
        envs = tab.get("envs")
        if envs is not None and (not _is_list(envs) or not set(envs) <= set(ENVS)):
            rep.error("envs_invalid", w, f"`envs` ammette solo {list(ENVS)}")
            envs = None
        expected = list(envs) if envs else list(ENVS)
        counts["table_links"] += 1
        if conf:
            by_conf["table_links"][conf] += 1
        for svc in tab.get("used_by") or []:
            if svc not in fsvc:
                rep.error("used_by_not_in_feature_services", w, f"{svc}: non e' tra i servizi della funzionalita'")
                continue
            reg = reg_services.get(svc)
            if reg is None:
                continue
            uses = [u for u in (reg.get("uses") or []) if u.get("target") == ref[0]]
            if not uses or (ref[1] and all(u.get("schemas") and ref[1] not in u["schemas"] for u in uses)):
                msg = f"{svc} non risulta usare {ref[0]}.{ref[1]} nel registro"
                if conf == "verified":
                    rep.error("verified_not_in_registry", w, msg)
                else:
                    rep.warn("service_table_not_in_registry", w, msg)
            if reg.get("unverified") and conf == "verified":
                rep.error("verified_on_unverified_service", w,
                          f"{svc} e' `unverified` nel registro: il legame servizio-tabella non puo' essere verified")
        states = {e: presence(catalogs[e], reg_targets, ref[0], ref[1], ref[2], cols) for e in ENVS}
        if env not in expected:
            rep.skipped.append({"where": w, "what": tab["ref"], "reason": f"ambiente {env} fuori da `envs`"})
            return
        _judge(rep, w, conf, states[env], tab["ref"])
        if states[env]["status"] == "ok":
            _env_coverage(rep, w, tab["ref"], env, states, expected)

    seen_ids: set[str] = set()
    for fi, feat in enumerate(features):
        w = f"features[{fi}]"
        if not isinstance(feat, dict):
            rep.error("feature_invalid", w, "la funzionalita' deve essere un dizionario")
            continue
        fid = feat.get("id")
        w = f"features[{fid}]" if isinstance(fid, str) else w
        _check_keys(rep, w, feat, FEATURE_KEYS)
        if not isinstance(fid, str) or not SLUG.match(fid):
            rep.error("feature_id_invalid", w, "`id` deve essere uno slug (minuscole, cifre, trattini)")
        elif fid in seen_ids:
            rep.error("feature_id_duplicate", w, f"id duplicato: {fid}")
        else:
            seen_ids.add(fid)
        for key in ("name", "area", "description"):
            if not isinstance(feat.get(key), str) or not feat[key].strip():
                rep.error("field_missing", w, f"`{key}` assente o vuoto")
        counts["features"] += 1
        fconf = _check_confidence(rep, w, feat)
        _check_sources(ctx, rep, w, feat, fconf)

        fsvc: dict[str, str] = {}
        for si, svc in enumerate(feat.get("services") or []):
            sw = f"{w}.services[{si}]"
            if not isinstance(svc, dict) or not isinstance(svc.get("name"), str):
                rep.error("service_item_invalid", sw, "il servizio ha `name` (stringa)")
                continue
            sw = f"{w}.services[{svc['name']}]"
            _check_keys(rep, sw, svc, SERVICE_ITEM_KEYS)
            if not isinstance(svc.get("role"), str) or not svc["role"].strip():
                rep.error("field_missing", sw, "`role` assente o vuoto")
            conf = _check_confidence(rep, sw, svc)
            _check_sources(ctx, rep, sw, svc, conf)
            _check_code_refs(rep, sw, svc)
            fsvc[svc["name"]] = conf or ""
            counts["service_links"] += 1
            if conf:
                by_conf["service_links"][conf] += 1
            in_registry = svc["name"] in reg_services
            if not in_registry:
                if svc.get("registry") is False and conf == "unverified":
                    rep.gap_candidates.append({"where": sw, "what": svc["name"], "status": "service_not_in_registry"})
                else:
                    rep.error("service_not_in_registry", sw,
                              f"{svc['name']}: assente da `services:` del registro (ammesso solo con "
                              "`registry: false` e confidenza unverified)")
            elif svc.get("registry") is False:
                rep.error("registry_flag_wrong", sw, f"{svc['name']} e' nel registro: togliere `registry: false`")

        tables = feat.get("tables") or []
        if not _is_list(tables):
            rep.error("tables_invalid", w, "`tables` deve essere una lista")
            tables = []
        for ti, tab in enumerate(tables):
            tw = f"{w}.tables[{ti}]"
            if not isinstance(tab, dict):
                rep.error("table_item_invalid", tw, "la tabella deve essere un dizionario")
                continue
            check_table_item(f"{w}.tables[{tab.get('ref')}]", tab, fsvc)

    # servizi: solo attributi non presenti nel registro
    svc_attrs = data.get("services") or {}
    if not isinstance(svc_attrs, dict):
        rep.error("services_invalid", "services", "`services` deve essere un dizionario nome -> attributi")
        svc_attrs = {}
    for name, attrs in svc_attrs.items():
        w = f"services[{name}]"
        if name not in reg_services:
            rep.error("service_not_in_registry", w, f"{name}: assente da `services:` del registro")
        if not isinstance(attrs, dict):
            rep.error("service_attrs_invalid", w, "gli attributi devono essere un dizionario")
            continue
        _check_keys(rep, w, attrs, SERVICE_ATTR_KEYS)
        _check_sources(ctx, rep, w, attrs, None)

    # relazioni logiche
    rel_ids: set[str] = set()
    relations = data.get("relations") or []
    if not _is_list(relations):
        rep.error("relations_invalid", "relations", "`relations` deve essere una lista")
        relations = []
    for ri, rel in enumerate(relations):
        w = f"relations[{ri}]"
        if not isinstance(rel, dict):
            rep.error("relation_invalid", w, "la relazione deve essere un dizionario")
            continue
        rid = rel.get("id")
        w = f"relations[{rid}]" if isinstance(rid, str) else w
        _check_keys(rep, w, rel, RELATION_KEYS)
        if not isinstance(rid, str) or not SLUG.match(rid):
            rep.error("relation_id_invalid", w, "`id` deve essere uno slug")
        elif rid in rel_ids:
            rep.error("relation_id_duplicate", w, f"id duplicato: {rid}")
        else:
            rel_ids.add(rid)
        if rel.get("kind") != "logical":
            rep.error("relation_kind_invalid", w, "`kind` deve essere `logical`")
        if not isinstance(rel.get("evidence"), str) or not rel["evidence"].strip():
            rep.error("evidence_missing", w, "`evidence` assente o vuoto: dire perche' le due colonne sono collegate")
        conf = _check_confidence(rep, w, rel)
        _check_sources(ctx, rep, w, rel, conf)
        for fid in rel.get("features") or []:
            if fid not in seen_ids:
                rep.error("relation_feature_unknown", w, f"funzionalita' sconosciuta: {fid}")
        ends = {k: parse_column_ref(rel[k]) if isinstance(rel.get(k), str) else None for k in ("from", "to")}
        for k, v in ends.items():
            if v is None:
                rep.error("relation_end_invalid", w, f"`{k}` deve essere target.schema.tabella.colonna", value=rel.get(k))
        counts["relations"] += 1
        if conf:
            by_conf["relations"][conf] += 1
        if None in ends.values():
            continue
        if ends["from"] == ends["to"]:
            rep.error("relation_self", w, "i due estremi coincidono")
            continue
        for k, v in ends.items():
            assert v is not None
            states = {e: presence(catalogs[e], reg_targets, v[0], v[1], v[2], [v[3]]) for e in ENVS}
            _judge(rep, f"{w}.{k}", conf, states[env], rel[k])
            if states[env]["status"] == "ok":
                _env_coverage(rep, f"{w}.{k}", rel[k], env, states, list(ENVS))

    # candidati: derived o unverified, mai verified; estremi non piu' nel catalogo = candidato obsoleto
    cands = data.get("relation_candidates") or []
    if not _is_list(cands):
        rep.error("candidates_invalid", "relation_candidates", "`relation_candidates` deve essere una lista")
        cands = []
    for ci, cand in enumerate(cands):
        w = f"relation_candidates[{ci}]"
        if not isinstance(cand, dict):
            rep.error("candidate_invalid", w, "il candidato deve essere un dizionario")
            continue
        _check_keys(rep, w, cand, CANDIDATE_KEYS)
        counts["relation_candidates"] += 1
        if cand.get("confidence") not in ("derived", "unverified"):
            rep.error("candidate_confidence_invalid", w, "un candidato e' `derived` o `unverified`, mai `verified`")
        for k in ("from", "to"):
            v = parse_column_ref(cand[k]) if isinstance(cand.get(k), str) else None
            if v is None:
                rep.error("relation_end_invalid", w, f"`{k}` deve essere target.schema.tabella.colonna")
                continue
            st = presence(primary, reg_targets, v[0], v[1], v[2], [v[3]])
            if st["status"] != "ok":
                rep.warn("candidate_stale", w, f"{cand[k]}: {st['status']} in {env}; rigenerare i candidati")

    return _finish(ctx, env, rep, counts, by_conf)


def _finish(ctx: Ctx, env: str, rep: Report, counts: dict[str, int],
            by_conf: dict[str, dict[str, int]]) -> dict[str, Any]:
    return {
        "ok": not rep.errors,
        "command": "map-check",
        "env": env,
        "map": ctx.rel(ctx.map_path),
        "counts": counts,
        "by_confidence": by_conf,
        "errors": rep.errors,
        "warnings": rep.warnings,
        "gap_candidates": rep.gap_candidates,
        "env_gaps": rep.env_gaps,
        "skipped": rep.skipped,
    }


# ---------------------------------------------------------------------------
# map-suggest-relations
# ---------------------------------------------------------------------------

def _type_group(sql_type: str) -> str:
    t = sql_type.strip().lower()
    if t.startswith("uuid"):
        return "uuid"
    if re.match(r"^(smallint|integer|int|bigint|serial|bigserial|smallserial)\b", t):
        return "int"
    if re.match(r"^(character|varchar|text|char|citext|bpchar)\b", t):
        return "text"
    return "other"


def _compatible(a: str, b: str) -> bool:
    ga, gb = _type_group(a), _type_group(b)
    if "other" in (ga, gb):
        return False
    return ga == gb or {ga, gb} == {"uuid", "text"}


def _entity_names(column: str) -> list[str]:
    """Nomi di entita' candidati per una colonna di collegamento, dal piu' specifico al meno specifico."""
    m = (re.match(r"^(?P<e>.+)_uid$", column) or re.match(r"^uid_(?P<e>.+)$", column)
         or re.match(r"^(?P<e>.+)_id$", column))
    if not m:
        return []
    tokens = m.group("e").split("_")
    names = []
    for i in range(len(tokens)):
        name = "_".join(tokens[i:])
        names.append(ALIASES.get(name, name))
    return names


def _is_domain(table: Table) -> bool:
    return not SKIP_TABLE.search(table.name)


def _entity_index(tables: list[Table]) -> dict[str, list[Table]]:
    index: dict[str, list[Table]] = {}
    for tab in tables:
        if not _is_domain(tab) or len(tab.pk) != 1 or tab.pk[0] not in ("uid", "id"):
            continue
        names = {tab.name}
        if tab.name.endswith("_entity"):
            names.add(tab.name[: -len("_entity")])
        for name in names:
            index.setdefault(name, []).append(tab)
    return index


def suggest_relations(ctx: Ctx, env: str) -> dict[str, Any]:
    cat = load_catalog(ctx, env)
    if not cat.tables:
        raise ToolError(EXIT_USAGE, "catalog_missing",
                        f"nessuna DDL nel catalogo dell'ambiente {env}: {ctx.rel(ctx.catalog_dir / env)}")
    tables = [t for t in cat.tables.values()]
    index = _entity_index(tables)
    declared: set[tuple[tuple[str, str, str], str]] = set()
    for tab in tables:
        for cols, rsch, rname, _ in tab.fks:
            for col in cols:
                declared.add((tab.key, col))
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    skipped_ambiguous = 0
    for tab in sorted(tables, key=lambda t: t.key):
        if not _is_domain(tab):
            continue
        for col, ctype in tab.columns.items():
            if col in tab.pk or (tab.key, col) in declared:
                continue
            for ent in _entity_names(col):
                if any(m.key == tab.key for m in index.get(ent, [])):
                    break  # auto-riferimento (es. uid_parent_service nella tabella service): non e' una relazione tra tabelle
                matches = [m for m in index.get(ent, [])
                           if m.key != tab.key and _compatible(ctype, m.columns[m.pk[0]])]
                if not matches:
                    continue
                same_schema = [m for m in matches if (m.target, m.schema) == (tab.target, tab.schema)]
                same_db = [m for m in matches if m.target == tab.target]
                chosen, scope = (same_schema, "intra_schema") if same_schema else (
                    (same_db, "cross_schema") if same_db else (matches, "cross_db"))
                if len(chosen) > 3:
                    skipped_ambiguous += 1
                    break
                for m in chosen:
                    pkcol = m.pk[0]
                    frm = f"{tab.target}.{tab.schema}.{tab.name}.{col}"
                    to = f"{m.target}.{m.schema}.{m.name}.{pkcol}"
                    why = (f"la colonna `{col}` ({_type_group(ctype)}) porta il nome dell'entita' `{ent}` e "
                           f"`{m.target}.{m.schema}.{m.name}` ha chiave primaria `{pkcol}`; "
                           + ("stesso schema" if scope == "intra_schema" else
                              "stesso database, schema diverso" if scope == "cross_schema" else
                              "database diverso (le chiavi esterne non attraversano i database)")
                           + "; nessuna chiave esterna dichiarata; dedotta dal nome, non da una fonte")
                    if len(chosen) > 1:
                        why += f"; ambigua: {len(chosen)} tabelle chiamate `{ent}`"
                    if _type_group(ctype) != _type_group(m.columns[pkcol]):
                        why += "; tipi uuid e testo: corrispondenza da verificare"
                    candidates[(frm, to)] = {"from": frm, "to": to, "kind": "logical", "scope": scope,
                                             "reason": why, "confidence": "derived", "env": env}
                break  # il nome piu' specifico che corrisponde a una tabella vince
    ordered = sorted(candidates.values(), key=lambda c: (SCOPES.index(c["scope"]), c["from"], c["to"]))
    return {"candidates": ordered, "skipped_ambiguous": skipped_ambiguous}


def _candidate_block(candidates: list[dict[str, Any]]) -> str:
    import yaml

    return yaml.safe_dump({"relation_candidates": candidates}, sort_keys=False, allow_unicode=True,
                          width=100000, default_flow_style=False)


_TOP_KEY = re.compile(r"^[A-Za-z_][\w-]*:")


def write_candidates(ctx: Ctx, candidates: list[dict[str, Any]]) -> bool:
    """Riscrive la sezione `relation_candidates` della mappa; idempotente. Ritorna True se il file e' cambiato."""
    if not ctx.map_path.is_file():
        raise ToolError(EXIT_USAGE, "map_missing", f"mappa non trovata: {ctx.rel(ctx.map_path)}")
    text = ctx.map_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    lines = text.split("\n")
    block = _candidate_block(candidates)
    start = next((i for i, ln in enumerate(lines) if ln.startswith("relation_candidates:")), None)
    if start is None:
        new_text = text.rstrip("\n") + "\n\n" + block
    else:
        end = next((i for i in range(start + 1, len(lines)) if _TOP_KEY.match(lines[i])), len(lines))
        tail = "\n".join(lines[end:])
        new_text = "\n".join(lines[:start]) + ("\n" if start else "") + block + (("\n" + tail) if tail.strip() else "")
        if not new_text.endswith("\n"):
            new_text += "\n"
    if new_text == text:
        return False
    ctx.map_path.write_bytes(new_text.encode("utf-8"))
    _FILE_MEMO.clear()
    return True


# ---------------------------------------------------------------------------
# map-locate
# ---------------------------------------------------------------------------

def _hay(*parts: Any) -> str:
    return " ".join(str(p) for p in parts if p).lower()


def locate(ctx: Ctx, env: str, term: str) -> dict[str, Any]:
    registry = load_registry(ctx)
    data = load_map(ctx) or {}
    if not isinstance(data, dict):
        raise ToolError(EXIT_INVALID, "map_invalid", "la mappa deve essere un dizionario YAML")
    cat = load_catalog(ctx, env)
    reg_targets = registry_targets(registry)
    needle = term.strip().lower()
    if not needle:
        raise ToolError(EXIT_USAGE, "term_empty", "il termine di ricerca e' vuoto")
    reg_services: dict[str, Any] = registry["services"]

    def table_state(ref: str, cols: list[str]) -> dict[str, Any]:
        parsed = parse_table_ref(ref)
        if parsed is None:
            return {"status": "ref_invalid"}
        return presence(cat, reg_targets, parsed[0], parsed[1], parsed[2], cols)

    features_out: list[dict[str, Any]] = []
    services: dict[str, dict[str, Any]] = {}
    tables: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}

    def svc_entry(name: str) -> dict[str, Any]:
        reg = reg_services.get(name) or {}
        return services.setdefault(name, {
            "name": name, "aliases": reg.get("aliases") or [], "in_registry": name in reg_services,
            "registry_unverified": bool(reg.get("unverified")), "registry_source": reg.get("source"),
            "registry_uses": reg.get("uses") or [], "features": []})

    def tab_entry(tab: dict[str, Any], fid: str | None) -> None:
        ref = tab["ref"]
        entry = tables.setdefault(ref, {
            "ref": ref, "columns": tab.get("columns") or [], "confidence": tab.get("confidence"),
            "sources": tab.get("sources") or [], "used_by": tab.get("used_by") or [],
            "in_catalog": {"env": env, **table_state(ref, tab.get("columns") or [])}, "features": []})
        if fid and fid not in entry["features"]:
            entry["features"].append(fid)

    feats = data.get("features") or []
    feat_tables: dict[str, set[str]] = {}
    for feat in feats:
        fid = feat.get("id")
        feat_tables[fid] = {t.get("ref") for t in feat.get("tables") or [] if isinstance(t, dict)}

    def feature_matches(feat: dict[str, Any]) -> bool:
        if needle in _hay(feat.get("id"), feat.get("name"), feat.get("area"), feat.get("description")):
            return True
        for svc in feat.get("services") or []:
            reg = reg_services.get(svc.get("name")) or {}
            if needle in _hay(svc.get("name"), *(reg.get("aliases") or [])):
                return True
        for tab in feat.get("tables") or []:
            if needle in _hay(tab.get("ref"), *(tab.get("columns") or [])):
                return True
        return False

    matched_feats = [f for f in feats if isinstance(f, dict) and feature_matches(f)]
    matched_ids = {f.get("id") for f in matched_feats}
    for rel in data.get("relations") or []:
        ends = [parse_column_ref(rel.get(k, "")) for k in ("from", "to")]
        touches = needle in _hay(rel.get("id"), rel.get("from"), rel.get("to"))
        in_feat = bool(matched_ids & set(rel.get("features") or []))
        if touches or in_feat:
            relations[rel["id"]] = {
                "id": rel["id"], "from": rel.get("from"), "to": rel.get("to"), "kind": rel.get("kind"),
                "evidence": rel.get("evidence"), "confidence": rel.get("confidence"),
                "sources": rel.get("sources") or [], "features": rel.get("features") or [],
                "endpoints_in_catalog": {
                    k: (table_state(f"{e[0]}.{e[1]}.{e[2]}", [e[3]])["status"] == "ok") if e else False
                    for k, e in zip(("from", "to"), ends)}}

    for feat in matched_feats:
        fid = feat["id"]
        features_out.append({
            "id": fid, "name": feat.get("name"), "area": feat.get("area"),
            "description": feat.get("description"), "confidence": feat.get("confidence"),
            "sources": feat.get("sources") or [],
            "services": [{"name": s["name"], "role": s.get("role"), "confidence": s.get("confidence"),
                          "sources": s.get("sources") or []} for s in feat.get("services") or []],
            "tables": [t["ref"] for t in feat.get("tables") or []]})
        for svc in feat.get("services") or []:
            e = svc_entry(svc["name"])
            if fid not in e["features"]:
                e["features"].append(fid)
        for tab in feat.get("tables") or []:
            tab_entry(tab, fid)

    # un servizio cercato per nome compare anche se nessuna funzionalita' lo cita
    for name, reg in reg_services.items():
        if needle in _hay(name, *(reg.get("aliases") or [])):
            svc_entry(name)
    # una tabella cercata per nome compare con le funzionalita' che la citano (gia' sopra) e col catalogo
    catalog_matches = []
    for tab in sorted(cat.tables.values(), key=lambda t: t.key):
        ref = f"{tab.target}.{tab.schema}.{tab.name}"
        hit_cols = [c for c in tab.columns if needle == c.lower()]
        if (needle in ref.lower() or hit_cols) and ref not in tables:
            catalog_matches.append({"ref": ref, "catalog_ref": f"{tab.file}:{tab.line}",
                                    "matched_columns": hit_cols})
    cand_out = [c for c in data.get("relation_candidates") or []
                if isinstance(c, dict) and needle in _hay(c.get("from"), c.get("to"))]
    found = bool(features_out or services or tables or relations or catalog_matches or cand_out)
    return {
        "ok": True, "command": "map-locate", "env": env, "term": term, "found": found,
        "features": features_out, "services": list(services.values()), "tables": list(tables.values()),
        "relations": list(relations.values()), "relation_candidates": cand_out[:50],
        "catalog_matches": catalog_matches[:50],
        "catalog_matches_total": len(catalog_matches),
        "notes": ["catalog_matches: tabelle o colonne del catalogo che corrispondono al termine ma non sono "
                  "in nessuna funzionalita' della mappa (nessun legame a una funzionalita' dichiarato)"]
        if catalog_matches else [],
    }


# ---------------------------------------------------------------------------
# Output e CLI
# ---------------------------------------------------------------------------

def emit(ctx: Ctx, payload: dict[str, Any], name: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text.encode("utf-8")) <= MAX_STDOUT_BYTES:
        print(text)
        return
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    path = ctx.out_dir / f"{name}.json"
    path.write_text(text, encoding="utf-8")
    summary = {k: v for k, v in payload.items()
               if k in ("ok", "command", "env", "term", "found", "counts", "by_confidence", "scopes", "total")}
    summary["errors_total"] = len(payload.get("errors") or [])
    print(json.dumps({**summary, "output_file": ctx.rel(path),
                      "message": "output oltre 32 KiB: il JSON completo e' nel file"}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Mappa funzionalita' -> servizio -> tabella e relazioni logiche.")
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[2]),
                   help="radice della factory (default: dedotta dal path dello script)")
    p.add_argument("--map", default=DEFAULT_MAP, help="percorso della mappa, relativo alla radice")
    p.add_argument("--catalog-dir", default=DEFAULT_CATALOG, help="directory del catalogo, relativa alla radice")
    p.add_argument("--registry", default=DEFAULT_REGISTRY, help="registro dei target, relativo alla radice")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("map-check", help="valida la mappa contro registro, catalogo e fonti")
    c.add_argument("--env", default="prod", choices=ENVS)
    s = sub.add_parser("map-suggest-relations", help="propone relazioni logiche dalle DDL del catalogo")
    s.add_argument("--env", default="prod", choices=ENVS)
    s.add_argument("--scope", action="append", choices=SCOPES,
                   help="limita ai tipi indicati (ripetibile); default: tutti")
    s.add_argument("--write-candidates", action="store_true",
                   help="riscrive la sezione relation_candidates della mappa (idempotente; non con --scope)")
    s.add_argument("--limit", type=int, default=0, help="mostra al massimo N candidati (0 = tutti)")
    loc = sub.add_parser("map-locate", help="dal termine alla funzionalita', al servizio, alla tabella")
    loc.add_argument("term")
    loc.add_argument("--env", default="prod", choices=ENVS)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    ctx = Ctx(root=root, map_path=root / args.map, catalog_dir=root / args.catalog_dir,
              registry_path=root / args.registry, out_dir=root / DEFAULT_OUT_DIR)
    try:
        if args.cmd == "map-check":
            payload = check_map(ctx, args.env)
            emit(ctx, payload, f"map-check-{args.env}")
            for err in payload["errors"][:20]:
                print(f"db_map: {err['code']}: {err['where']}: {err['message']}", file=sys.stderr)
            return EXIT_OK if payload["ok"] else EXIT_INVALID
        if args.cmd == "map-suggest-relations":
            if args.write_candidates and args.scope and set(args.scope) != set(SCOPES):
                # la sezione relation_candidates si riscrive per intero: con un filtro sparirebbero
                # i candidati degli altri tipi gia' presenti nella mappa
                raise ToolError(EXIT_USAGE, "scope_with_write",
                                "--write-candidates riscrive tutta la sezione: non si combina con --scope")
            res = suggest_relations(ctx, args.env)
            data = load_map(ctx) if ctx.map_path.is_file() else {}
            known = set()
            for rel in (data or {}).get("relations") or []:
                if isinstance(rel, dict):
                    known.add((rel.get("from"), rel.get("to")))
                    known.add((rel.get("to"), rel.get("from")))
            wanted = set(args.scope or SCOPES)
            cands = [c for c in res["candidates"] if c["scope"] in wanted and (c["from"], c["to"]) not in known]
            written = None
            if args.write_candidates:
                written = write_candidates(ctx, cands)
            shown = cands[: args.limit] if args.limit else cands
            payload = {
                "ok": True, "command": "map-suggest-relations", "env": args.env,
                "total": len(cands),
                "scopes": {s: sum(1 for c in cands if c["scope"] == s) for s in SCOPES},
                "skipped_ambiguous": res["skipped_ambiguous"],
                "already_in_relations": len(res["candidates"]) - len(cands) if wanted == set(SCOPES) else None,
                "written": written, "candidates": shown}
            emit(ctx, payload, f"map-suggest-relations-{args.env}")
            return EXIT_OK
        payload = locate(ctx, args.env, args.term)
        emit(ctx, payload, "map-locate")
        return EXIT_OK
    except ToolError as err:
        print(json.dumps(err.payload, ensure_ascii=False, default=str))
        print(f"db_map: {err.payload['error']}: {err.payload['message']}", file=sys.stderr)
        return err.code


if __name__ == "__main__":
    sys.exit(main())
