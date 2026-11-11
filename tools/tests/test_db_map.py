"""
Test di tools/db/db_map.py.

Nessun database, nessuna rete: catalogo, registro e mappa finti vivono in tmp_path. Il tool non apre connessioni e
non esegue subprocess (non c'e' un timeout da simulare): un test ne verifica gli import. Un test finale controlla
che la mappa reale del repo passi `map-check`.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "tools" / "db"))

import db_map as dm  # noqa: E402

REGISTRY = """
version: 1
environments:
  test:
    hosts: {h: {host: db.test.local, port: 5432}}
    databases:
      cust: {host: h, dbname: cust, schemas: [public]}
      reg: {host: h, dbname: reg, schemas: [public]}
      cloud: {host: h, dbname: cloud, schemas: [main, extra]}
  prod:
    hosts: {h: {host: db.prod.local, port: 5432}}
    databases:
      cust: {host: h, dbname: cust, schemas: [public]}
      reg: {host: h, dbname: reg, schemas: [public]}
      cloud: {host: h, dbname: cloud, schemas: [main, extra]}
services:
  cust-svc:
    aliases: [customers]
    source: wiki/cust.md
    uses: [{target: cust, schemas: [public]}]
  reg-svc:
    source: wiki/reg.md
    uses: [{target: reg}]
  shaky-svc:
    unverified: true
    source: "dedotto"
    uses: [{target: reg}]
  cloud-svc:
    source: wiki/cloud.md
    uses: [{target: cloud, schemas: [main, extra]}]
"""

DDL_ANAG = """-- schema public: struttura canonica
CREATE SCHEMA IF NOT EXISTS public;

CREATE TABLE public.organization (
    uid uuid DEFAULT uuid_generate_v4() NOT NULL,
    name character varying(255),
    fiscal_code character varying,
    parent_organization_id uuid
);

CREATE TABLE public.organization_history (
    uid uuid NOT NULL,
    name character varying(255)
);

CREATE TABLE public."group" (
    uid uuid NOT NULL,
    name text
);

CREATE TABLE public.account (
    uid uuid NOT NULL,
    organization_id uuid,
    group_id uuid,
    "order" integer
);

ALTER TABLE public.organization ADD CONSTRAINT organization_pk PRIMARY KEY (uid);

ALTER TABLE public."group" ADD CONSTRAINT group_pk PRIMARY KEY (uid);

ALTER TABLE public.account ADD CONSTRAINT account_pk PRIMARY KEY (uid);

ALTER TABLE public.account ADD CONSTRAINT account_group_fk FOREIGN KEY (group_id) REFERENCES "group"(uid);
"""

DDL_REG = """CREATE SCHEMA IF NOT EXISTS public;

CREATE TABLE public.invitation (
    uid uuid NOT NULL,
    organization_id uuid NOT NULL,
    org_uid uuid,
    other_id bigint
);

CREATE TABLE public.invitation_history (
    uid uuid NOT NULL,
    organization_id uuid NOT NULL
);

ALTER TABLE public.invitation ADD CONSTRAINT invitation_pk PRIMARY KEY (uid);
"""

DDL_CLOUD_MAIN = """CREATE SCHEMA IF NOT EXISTS main;

CREATE TABLE main.supplier (
    uid uuid NOT NULL,
    name text,
    uid_parent_supplier uuid
);

ALTER TABLE main.supplier ADD CONSTRAINT supplier_pk PRIMARY KEY (uid);
"""

DDL_CLOUD_EXTRA = """CREATE SCHEMA IF NOT EXISTS extra;

CREATE TABLE extra.assignment (
    uid uuid NOT NULL,
    uid_supplier uuid
);

ALTER TABLE extra.assignment ADD CONSTRAINT assignment_pk PRIMARY KEY (uid);
"""

SRC = {"path": "wiki/cust.md", "note": "pagina del servizio"}

MAP_OK: dict[str, Any] = {
    "version": 1,
    "features": [
        {
            "id": "org-list",
            "name": "Elenco organizzazioni",
            "area": "Area Test",
            "description": "Elenco delle organizzazioni.",
            "confidence": "verified",
            "sources": [SRC],
            "services": [
                {"name": "cust-svc", "role": "possiede i dati", "confidence": "verified", "sources": [SRC]},
            ],
            "tables": [
                {"ref": "cust.public.organization", "columns": ["uid", "name"], "used_by": ["cust-svc"],
                 "confidence": "verified", "sources": [SRC]},
            ],
        },
    ],
    "services": {},
    "relations": [
        {"id": "inv-org", "from": "reg.public.invitation.organization_id",
         "to": "cust.public.organization.uid", "kind": "logical",
         "evidence": "l'invito e' per organizzazione", "confidence": "derived", "sources": [SRC]},
    ],
    "relation_candidates": [],
}


def _write_lf(path: Path, text: str) -> None:
    # Path.write_text(newline=...) esiste solo da Python 3.10
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _write_catalog(root: Path, env: str, layout: dict[str, dict[str, str]]) -> None:
    for target, files in layout.items():
        d = root / "memory" / "semantic" / "db-catalog" / env / target
        d.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            _write_lf(d / name, text)


@pytest.fixture()
def factory(tmp_path: Path) -> Path:
    root = tmp_path
    (root / "tools" / "db").mkdir(parents=True)
    (root / "tools" / "db" / "db-targets.yaml").write_text(REGISTRY, encoding="utf-8")
    (root / "wiki").mkdir()
    for name in ("cust", "reg", "cloud"):
        (root / "wiki" / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
    full = {"cust": {"public.sql": DDL_ANAG}, "reg": {"public.sql": DDL_REG},
            "cloud": {"main.sql": DDL_CLOUD_MAIN, "extra.sql": DDL_CLOUD_EXTRA}}
    _write_catalog(root, "prod", full)
    # in test manca il database reg e lo schema extra di cloud
    _write_catalog(root, "test", {"cust": {"public.sql": DDL_ANAG}, "cloud": {"main.sql": DDL_CLOUD_MAIN}})
    write_map(root, MAP_OK)
    return root


def write_map(root: Path, data: dict[str, Any]) -> None:
    path = root / "memory" / "semantic" / "db-catalog" / "feature-map.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_lf(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def map_text(root: Path) -> str:
    return (root / "memory" / "semantic" / "db-catalog" / "feature-map.yaml").read_text(encoding="utf-8")


def run(root: Path, capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    dm._FILE_MEMO.clear()
    code = dm.main(["--root", str(root), *argv])
    out = capsys.readouterr().out.strip().splitlines()
    return code, json.loads(out[0]) if out else {}


def mutated(**changes: Any) -> dict[str, Any]:
    """Copia di MAP_OK con la prima funzionalita' modificata (chiavi di `changes`)."""
    data = json.loads(json.dumps(MAP_OK))
    data["features"][0].update(changes)
    return data


def error_codes(payload: dict[str, Any]) -> list[str]:
    return [e["code"] for e in payload["errors"]]


# ---------------------------------------------------------------------------
# map-check: percorso felice e forma dell'output
# ---------------------------------------------------------------------------

def test_check_passes_on_valid_map_and_reports_counts(factory, capsys):
    code, out = run(factory, capsys, "map-check")
    assert code == 0, out
    assert out["ok"] is True and out["command"] == "map-check" and out["env"] == "prod"
    assert out["counts"]["features"] == 1 and out["counts"]["relations"] == 1
    assert out["by_confidence"]["table_links"]["verified"] == 1
    assert out["errors"] == []


def test_check_reports_envs_where_a_cited_table_is_missing(factory, capsys):
    data = mutated()
    data["features"][0]["tables"].append(
        {"ref": "reg.public.invitation", "columns": ["uid"], "confidence": "derived", "sources": [SRC]})
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check", "--env", "prod")
    assert code == 0, out
    gaps = [g for g in out["env_gaps"] if g["what"] == "reg.public.invitation"]
    assert "test" in [g["env"] for g in gaps] and all(g["status"] == "catalog_unavailable" for g in gaps)


def test_check_env_option_changes_the_reference_catalog(factory, capsys):
    data = mutated()
    data["features"][0]["tables"][0]["ref"] = "cloud.extra.assignment"
    data["features"][0]["tables"][0]["columns"] = ["uid_supplier"]
    data["features"][0]["tables"][0].pop("used_by")
    write_map(factory, data)
    assert run(factory, capsys, "map-check", "--env", "prod")[0] == 0
    code, out = run(factory, capsys, "map-check", "--env", "test")
    assert code == 1 and "verified_not_in_catalog" in error_codes(out)


# ---------------------------------------------------------------------------
# map-check: schema, confidenza, fonti
# ---------------------------------------------------------------------------

def test_row_without_source_is_rejected_unless_unverified(factory, capsys):
    data = mutated()
    data["features"][0]["services"][0]["sources"] = []
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "source_missing" in error_codes(out)

    data["features"][0]["services"][0]["confidence"] = "unverified"
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 0 and out["errors"] == []


def test_confidence_outside_the_three_values_is_rejected(factory, capsys):
    data = mutated()
    data["features"][0]["tables"][0]["confidence"] = "probabile"
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "confidence_invalid" in error_codes(out)


def test_row_without_confidence_marker_is_rejected(factory, capsys):
    data = mutated()
    del data["features"][0]["services"][0]["confidence"]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "confidence_missing" in error_codes(out)


def test_source_that_does_not_exist_is_rejected(factory, capsys):
    data = mutated()
    data["features"][0]["sources"] = [{"path": "wiki/non-esiste.md", "note": "x"}]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "source_not_found" in error_codes(out)


def test_source_cannot_be_a_code_repos_path_or_escape_the_repo(factory, capsys):
    data = mutated()
    data["features"][0]["sources"] = [{"path": "code_repos/servizi/Foo.java", "note": "x"},
                                      {"path": "../fuori.md", "note": "x"}]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1
    assert {"source_code_repos_path", "source_path_invalid"} <= set(error_codes(out))


def test_code_refs_are_repo_and_entity_not_file_paths(factory, capsys):
    data = mutated()
    data["features"][0]["services"][0]["code_refs"] = [{"repo": "cust-repo", "entity": "OrganizationEntity"}]
    write_map(factory, data)
    assert run(factory, capsys, "map-check")[0] == 0

    data["features"][0]["services"][0]["code_refs"] = [{"repo": "cust-repo", "entity": "src/Org.java"}]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "code_ref_is_path" in error_codes(out)

    data["features"][0]["services"][0]["code_refs"] = [{"repo": "cust-repo"}]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "code_ref_invalid" in error_codes(out)


def test_duplicate_feature_id_and_bad_slug_are_rejected(factory, capsys):
    data = mutated()
    data["features"].append(json.loads(json.dumps(data["features"][0])))
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "feature_id_duplicate" in error_codes(out)

    data = mutated(id="Org List")
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "feature_id_invalid" in error_codes(out)


def test_unknown_keys_are_rejected(factory, capsys):
    data = mutated(colore="blu")
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "unknown_key" in error_codes(out)


# ---------------------------------------------------------------------------
# map-check: servizi e registro
# ---------------------------------------------------------------------------

def test_service_missing_from_registry_is_rejected_unless_flagged_unverified(factory, capsys):
    data = mutated()
    data["features"][0]["services"].append(
        {"name": "ghost-svc", "role": "x", "confidence": "verified", "sources": [SRC]})
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "service_not_in_registry" in error_codes(out)

    data["features"][0]["services"][1].update({"registry": False, "confidence": "unverified"})
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 0
    assert any(g["what"] == "ghost-svc" for g in out["gap_candidates"])


def test_verified_table_link_through_unverified_registry_service_is_rejected(factory, capsys):
    data = mutated()
    data["features"][0]["services"].append(
        {"name": "shaky-svc", "role": "x", "confidence": "derived", "sources": [SRC]})
    data["features"][0]["tables"] = [
        {"ref": "reg.public.invitation", "columns": ["uid"], "used_by": ["shaky-svc"],
         "confidence": "verified", "sources": [SRC]}]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "verified_on_unverified_service" in error_codes(out)

    data["features"][0]["tables"][0]["confidence"] = "derived"
    write_map(factory, data)
    assert run(factory, capsys, "map-check")[0] == 0


def test_verified_table_not_used_by_the_service_in_registry_is_rejected(factory, capsys):
    data = mutated()
    data["features"][0]["tables"] = [
        {"ref": "reg.public.invitation", "columns": ["uid"], "used_by": ["cust-svc"],
         "confidence": "verified", "sources": [SRC]}]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "verified_not_in_registry" in error_codes(out)


def test_used_by_must_be_a_service_of_the_feature(factory, capsys):
    data = mutated()
    data["features"][0]["tables"][0]["used_by"] = ["reg-svc"]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "used_by_not_in_feature_services" in error_codes(out)


# ---------------------------------------------------------------------------
# map-check: tabelle e colonne contro il catalogo
# ---------------------------------------------------------------------------

def test_verified_table_missing_from_catalog_is_rejected(factory, capsys):
    data = mutated()
    data["features"][0]["tables"][0]["ref"] = "cust.public.nonexistent"
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and out["ok"] is False
    assert "verified_not_in_catalog" in error_codes(out)


def test_unverified_table_missing_from_catalog_becomes_a_gap_candidate(factory, capsys):
    data = mutated()
    data["features"][0]["tables"][0].update({"ref": "cust.public.nonexistent", "confidence": "unverified"})
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 0
    gap = out["gap_candidates"][0]
    assert gap["what"] == "cust.public.nonexistent" and gap["status"] == "table_missing"


def test_missing_column_is_reported_with_its_name(factory, capsys):
    data = mutated()
    data["features"][0]["tables"][0]["columns"] = ["uid", "colonna_fantasma"]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1
    err = next(e for e in out["errors"] if e["code"] == "verified_not_in_catalog")
    assert err["status"] == "column_missing" and err["missing_columns"] == ["colonna_fantasma"]


def test_derived_row_also_requires_the_catalog(factory, capsys):
    data = mutated()
    data["features"][0]["tables"][0].update({"ref": "reg.public.nonexistent", "confidence": "derived"})
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "derived_not_in_catalog" in error_codes(out)


def test_target_not_in_registry_is_allowed_only_as_unverified(factory, capsys):
    data = mutated()
    data["features"][0]["tables"].append(
        {"ref": "elsewhere.logging.events", "confidence": "unverified", "sources": [SRC]})
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 0
    assert any(g["status"] == "target_not_in_registry" for g in out["gap_candidates"])

    data["features"][0]["tables"][1]["confidence"] = "derived"
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "derived_not_in_catalog" in error_codes(out)


def test_envs_restricts_where_a_table_is_expected(factory, capsys):
    data = mutated()
    data["features"][0]["tables"] = [
        {"ref": "cloud.extra.assignment", "columns": ["uid"], "envs": ["prod"],
         "confidence": "verified", "sources": [SRC]}]
    data["relations"] = []
    write_map(factory, data)
    assert run(factory, capsys, "map-check", "--env", "prod")[0] == 0
    code, out = run(factory, capsys, "map-check", "--env", "test")
    assert code == 0 and out["skipped"] and "fuori da `envs`" in out["skipped"][0]["reason"]


def test_quoted_identifiers_and_inherited_style_columns_are_parsed(factory, capsys):
    data = mutated()
    data["features"][0]["tables"] = [
        {"ref": "cust.public.group", "columns": ["uid", "name"], "confidence": "derived", "sources": [SRC]},
        {"ref": "cust.public.account", "columns": ["order"], "confidence": "derived", "sources": [SRC]}]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 0, out


# ---------------------------------------------------------------------------
# map-check: relazioni logiche
# ---------------------------------------------------------------------------

def test_relation_without_evidence_or_marker_is_rejected(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    del data["relations"][0]["evidence"]
    del data["relations"][0]["confidence"]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and {"evidence_missing", "confidence_missing"} <= set(error_codes(out))


def test_relation_without_source_is_valid_only_as_unverified(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    data["relations"][0]["sources"] = []
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "source_missing" in error_codes(out)

    data["relations"][0]["confidence"] = "unverified"
    write_map(factory, data)
    assert run(factory, capsys, "map-check")[0] == 0


def test_verified_relation_with_missing_endpoint_is_rejected_and_unverified_becomes_a_gap(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    data["relations"][0]["to"] = "cust.public.organization.colonna_fantasma"
    data["relations"][0]["confidence"] = "verified"
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1
    err = next(e for e in out["errors"] if e["code"] == "verified_not_in_catalog")
    assert err["where"].endswith(".to") and err["status"] == "column_missing"

    data["relations"][0]["confidence"] = "unverified"
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 0
    assert any(g["where"].endswith(".to") for g in out["gap_candidates"])


def test_relation_endpoint_in_database_without_catalog_is_a_gap_when_unverified(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    data["relations"].append(
        {"id": "ext-org", "from": "audit.logging.events.organization_uid",
         "to": "cust.public.organization.uid", "kind": "logical", "evidence": "ipotesi",
         "confidence": "unverified", "sources": [SRC]})
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 0
    assert any(g["status"] == "target_not_in_registry" and "events" in g["what"] for g in out["gap_candidates"])


@pytest.mark.parametrize("change,code_expected", [
    ({"kind": "foreign"}, "relation_kind_invalid"),
    ({"from": "cust.public.organization"}, "relation_end_invalid"),
    ({"to": "reg.public.invitation.organization_id"}, "relation_self"),
    ({"features": ["nessuna"]}, "relation_feature_unknown"),
    ({"id": "Non Slug"}, "relation_id_invalid"),
])
def test_relation_schema_violations(factory, capsys, change, code_expected):
    data = json.loads(json.dumps(MAP_OK))
    data["relations"][0].update(change)
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and code_expected in error_codes(out)


def test_duplicate_relation_id_is_rejected(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    data["relations"].append(json.loads(json.dumps(data["relations"][0])))
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "relation_id_duplicate" in error_codes(out)


def test_candidate_cannot_be_verified(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    data["relation_candidates"] = [
        {"from": "reg.public.invitation.organization_id", "to": "cust.public.organization.uid",
         "kind": "logical", "scope": "cross_db", "reason": "x", "confidence": "verified", "env": "prod"}]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and "candidate_confidence_invalid" in error_codes(out)


def test_stale_candidate_is_a_warning(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    data["relation_candidates"] = [
        {"from": "reg.public.invitation.organization_id", "to": "cust.public.organization.vecchia_colonna",
         "kind": "logical", "scope": "cross_db", "reason": "x", "confidence": "derived", "env": "prod"}]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-check")
    assert code == 0 and out["warnings"][0]["code"] == "candidate_stale"


# ---------------------------------------------------------------------------
# map-check: uso e configurazione
# ---------------------------------------------------------------------------

def test_missing_map_exits_with_usage_error(factory, capsys):
    (factory / "memory" / "semantic" / "db-catalog" / "feature-map.yaml").unlink()
    code, out = run(factory, capsys, "map-check")
    assert code == 2 and out["error"] == "map_missing" and out["ok"] is False


def test_invalid_yaml_is_an_invalid_map(factory, capsys):
    (factory / "memory" / "semantic" / "db-catalog" / "feature-map.yaml").write_text("features: [\n", encoding="utf-8")
    code, out = run(factory, capsys, "map-check")
    assert code == 1 and out["error"] == "yaml_invalid"


def test_missing_catalog_for_the_environment_is_incomplete_not_success(factory, capsys):
    code, out = run(factory, capsys, "map-check", "--env", "preprod")
    assert code == 2 and out["error"] == "catalog_missing"


def test_missing_registry_exits_with_usage_error(factory, capsys):
    (factory / "tools" / "db" / "db-targets.yaml").unlink()
    code, out = run(factory, capsys, "map-check")
    assert code == 2 and out["error"] == "registry_missing"


def test_unknown_environment_is_refused_by_the_parser(factory):
    with pytest.raises(SystemExit) as exc:
        dm.main(["--root", str(factory), "map-check", "--env", "sandbox"])
    assert exc.value.code == 2


def test_catalog_is_parsed_once_per_process(factory, monkeypatch):
    calls = {"n": 0}
    real = dm.parse_ddl

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(dm, "parse_ddl", counting)
    dm._FILE_MEMO.clear()
    ctx = dm.Ctx(factory, factory / dm.DEFAULT_MAP, factory / dm.DEFAULT_CATALOG,
                 factory / dm.DEFAULT_REGISTRY, factory / dm.DEFAULT_OUT_DIR)
    dm.load_catalog(ctx, "prod")
    first = calls["n"]
    dm.load_catalog(ctx, "prod")
    assert first == 4 and calls["n"] == first


# ---------------------------------------------------------------------------
# map-suggest-relations
# ---------------------------------------------------------------------------

def _suggest(factory, capsys, *extra: str) -> dict[str, Any]:
    code, out = run(factory, capsys, "map-suggest-relations", "--env", "prod", *extra)
    assert code == 0, out
    return out


def _pairs(out: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(c["from"], c["to"]): c for c in out["candidates"]}


def test_suggest_finds_cross_db_relations_by_column_name_and_pk(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    data["relations"] = []
    write_map(factory, data)
    out = _suggest(factory, capsys)
    pairs = _pairs(out)
    key = ("reg.public.invitation.organization_id", "cust.public.organization.uid")
    assert key in pairs
    cand = pairs[key]
    assert cand["scope"] == "cross_db" and cand["confidence"] == "derived" and cand["kind"] == "logical"
    assert "dedotta dal nome" in cand["reason"]
    # alias org -> organization
    assert ("reg.public.invitation.org_uid", "cust.public.organization.uid") in pairs


def test_suggest_never_proposes_verified(factory, capsys):
    out = _suggest(factory, capsys)
    assert out["candidates"] and {c["confidence"] for c in out["candidates"]} == {"derived"}


def test_suggest_skips_history_tables_declared_fks_and_self_references(factory, capsys):
    pairs = _pairs(_suggest(factory, capsys))
    assert not any(".invitation_history." in frm for frm, _ in pairs)
    assert not any(frm.endswith("organization_history.uid") for frm, _ in pairs)
    # FK dichiarata account.group_id -> group
    assert not any(frm == "cust.public.account.group_id" for frm, _ in pairs)
    # parent_organization_id sta nella tabella organization stessa: auto-riferimento, non una relazione
    assert not any(frm == "cust.public.organization.parent_organization_id" for frm, _ in pairs)
    # la chiave primaria non e' un riferimento
    assert not any(frm.endswith(".uid") for frm, _ in pairs)


def test_suggest_same_db_across_schemas_and_type_mismatch(factory, capsys):
    out = _suggest(factory, capsys)
    pairs = _pairs(out)
    key = ("cloud.extra.assignment.uid_supplier", "cloud.main.supplier.uid")
    assert pairs[key]["scope"] == "cross_schema"
    # other_id e' bigint e non ha un'entita' `other`: nessun candidato
    assert not any(frm.endswith(".other_id") for frm, _ in pairs)
    # uid_parent_supplier e' un auto-riferimento di supplier
    assert not any(frm.endswith("uid_parent_supplier") for frm, _ in pairs)


def test_suggest_scope_filter_and_counts(factory, capsys):
    out = _suggest(factory, capsys, "--scope", "cross_db")
    assert {c["scope"] for c in out["candidates"]} == {"cross_db"}
    assert out["total"] == len(out["candidates"]) and out["scopes"]["cross_db"] == out["total"]


def test_suggest_excludes_pairs_already_in_relations(factory, capsys):
    pairs = _pairs(_suggest(factory, capsys))
    assert ("reg.public.invitation.organization_id", "cust.public.organization.uid") not in pairs


def test_suggest_reads_no_rows_and_opens_no_connection():
    tree = ast.parse((_REPO_ROOT / "tools" / "db" / "db_map.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"psycopg", "psycopg2", "pg8000", "sqlalchemy", "socket", "subprocess", "db_access", "db_catalog",
                 "urllib", "requests"}
    assert not (imported & forbidden), imported & forbidden


def test_write_candidates_with_a_scope_filter_is_refused_and_leaves_the_map_untouched(factory, capsys):
    path = factory / "memory" / "semantic" / "db-catalog" / "feature-map.yaml"
    _suggest(factory, capsys, "--write-candidates")
    before = path.read_bytes()
    code, out = run(factory, capsys, "map-suggest-relations", "--env", "prod", "--scope", "cross_db",
                    "--write-candidates")
    assert code == 2 and out["error"] == "scope_with_write"
    assert path.read_bytes() == before


def test_write_candidates_is_idempotent_and_preserves_the_rest_of_the_map(factory, capsys):
    path = factory / "memory" / "semantic" / "db-catalog" / "feature-map.yaml"
    _write_lf(path, map_text(factory) + "\nextra_tail: 1\n")
    # `relation_candidates: []` non e' l'ultima sezione: il resto deve restare
    before = yaml.safe_load(path.read_text(encoding="utf-8"))
    out1 = _suggest(factory, capsys, "--write-candidates")
    after1 = path.read_text(encoding="utf-8")
    out2 = _suggest(factory, capsys, "--write-candidates")
    after2 = path.read_text(encoding="utf-8")
    assert out1["written"] is True and out2["written"] is False
    assert after1 == after2
    data = yaml.safe_load(after2)
    assert data["features"] == before["features"] and data["relations"] == before["relations"]
    assert len(data["relation_candidates"]) == out1["total"] > 0
    assert data["extra_tail"] == 1
    assert "\r" not in after2


def test_write_candidates_appends_the_section_when_absent_and_map_still_checks(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    del data["relation_candidates"]
    write_map(factory, data)
    out = _suggest(factory, capsys, "--write-candidates")
    assert out["written"] is True
    assert "relation_candidates:" in map_text(factory)
    code, chk = run(factory, capsys, "map-check")
    assert code == 0 and chk["counts"]["relation_candidates"] == out["total"]


def test_write_candidates_shrinks_the_section_when_a_candidate_is_promoted(factory, capsys):
    _suggest(factory, capsys, "--write-candidates")
    before = len(yaml.safe_load(map_text(factory))["relation_candidates"])
    data = yaml.safe_load(map_text(factory))
    data["relations"].append(
        {"id": "inv-org-sys", "from": "reg.public.invitation.org_uid", "to": "cust.public.organization.uid",
         "kind": "logical", "evidence": "x", "confidence": "unverified", "sources": []})
    write_map(factory, data)
    out = _suggest(factory, capsys, "--write-candidates")
    assert out["written"] is True
    assert len(yaml.safe_load(map_text(factory))["relation_candidates"]) == before - 1


def test_suggest_large_output_goes_to_a_file(factory, capsys, monkeypatch):
    monkeypatch.setattr(dm, "MAX_STDOUT_BYTES", 200)
    code, out = run(factory, capsys, "map-suggest-relations", "--env", "prod")
    assert code == 0 and "output_file" in out and "candidates" not in out
    saved = json.loads((factory / out["output_file"]).read_text(encoding="utf-8"))
    assert saved["candidates"]


def test_suggest_without_catalog_for_env_exits_with_usage_error(factory, capsys):
    code, out = run(factory, capsys, "map-suggest-relations", "--env", "staging")
    assert code == 2 and out["error"] == "catalog_missing"


# ---------------------------------------------------------------------------
# map-locate
# ---------------------------------------------------------------------------

def test_locate_by_feature_returns_services_tables_and_relations(factory, capsys):
    data = json.loads(json.dumps(MAP_OK))
    data["relations"][0]["features"] = ["org-list"]
    write_map(factory, data)
    code, out = run(factory, capsys, "map-locate", "elenco")
    assert code == 0 and out["found"] is True
    feat = out["features"][0]
    assert feat["id"] == "org-list" and feat["confidence"] == "verified"
    assert feat["services"][0]["name"] == "cust-svc" and feat["services"][0]["sources"]
    table = out["tables"][0]
    assert table["ref"] == "cust.public.organization" and table["in_catalog"]["status"] == "ok"
    assert table["in_catalog"]["catalog_ref"].endswith("cust/public.sql:" + table["in_catalog"]["catalog_ref"].split(":")[-1])
    assert out["relations"][0]["id"] == "inv-org"
    assert out["relations"][0]["endpoints_in_catalog"] == {"from": True, "to": True}


def test_locate_catalog_ref_points_to_the_create_table_line(factory, capsys):
    code, out = run(factory, capsys, "map-locate", "organization")
    assert code == 0
    ref = out["tables"][0]["in_catalog"]["catalog_ref"]
    path, line = ref.rsplit(":", 1)
    lines = (factory / path).read_text(encoding="utf-8").split("\n")
    assert lines[int(line) - 1].startswith("CREATE TABLE public.organization (")


def test_locate_by_service_alias_includes_registry_info(factory, capsys):
    code, out = run(factory, capsys, "map-locate", "customers")
    assert code == 0
    svc = next(s for s in out["services"] if s["name"] == "cust-svc")
    assert svc["in_registry"] is True and svc["registry_uses"][0]["target"] == "cust"
    assert svc["features"] == ["org-list"]


def test_locate_by_column_and_table_names(factory, capsys):
    code, out = run(factory, capsys, "map-locate", "fiscal_code")
    assert code == 0 and out["found"] is True
    assert any(m["ref"] == "cust.public.organization" and "fiscal_code" in m["matched_columns"]
               for m in out["catalog_matches"])
    code, out = run(factory, capsys, "map-locate", "invitation")
    assert any(r["id"] == "inv-org" for r in out["relations"])


def test_locate_unknown_term_is_found_false_and_exit_zero(factory, capsys):
    code, out = run(factory, capsys, "map-locate", "zzz-niente")
    assert code == 0 and out["found"] is False and out["features"] == [] and out["tables"] == []


def test_locate_flags_tables_missing_from_the_environment_catalog(factory, capsys):
    data = mutated()
    data["features"][0]["tables"][0]["confidence"] = "unverified"
    data["features"][0]["tables"][0]["ref"] = "cust.public.nonexistent"
    data["features"][0]["tables"][0]["columns"] = []
    write_map(factory, data)
    code, out = run(factory, capsys, "map-locate", "elenco")
    assert code == 0 and out["tables"][0]["in_catalog"]["status"] == "table_missing"


def test_locate_lists_candidates_separately_from_relations(factory, capsys):
    _suggest(factory, capsys, "--write-candidates")
    code, out = run(factory, capsys, "map-locate", "org_uid")
    assert code == 0 and out["relation_candidates"]
    assert all(c["confidence"] == "derived" for c in out["relation_candidates"])
    assert out["relations"] == []


def test_locate_empty_term_is_a_usage_error(factory, capsys):
    code, out = run(factory, capsys, "map-locate", "  ")
    assert code == 2 and out["error"] == "term_empty"


# ---------------------------------------------------------------------------
# Registro di esempio del repo
# ---------------------------------------------------------------------------

def test_example_registry_services_are_unchanged_in_shape():
    reg = yaml.safe_load((_REPO_ROOT / "tools" / "db" / "db-targets.example.yaml").read_text(encoding="utf-8"))
    for name, svc in reg["services"].items():
        assert not ({"evidence", "status"} & set(svc)), name


def test_default_paths_are_configurable_and_neutral():
    assert dm.DEFAULT_CATALOG == "memory/semantic/db-catalog"
    assert dm.DEFAULT_MAP.startswith(dm.DEFAULT_CATALOG)
    assert "area" in dm.FEATURE_KEYS and "portal" not in dm.FEATURE_KEYS
