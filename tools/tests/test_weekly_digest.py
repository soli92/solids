"""
Test di tools/docs/weekly_digest.py.

Livelli:
- fixture finta in tmp_path (kanban, log, gap, incidenti, event store, deliverables) con valori
  attesi scritti a mano;
- config con documentation.weekly_digest.release_kinds e forma di wiki/log.md di questa factory.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "tools" / "docs" / "weekly_digest.py"
_spec = importlib.util.spec_from_file_location("weekly_digest", _SCRIPT)
wd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wd)

WEEK = "2026-W41"  # lun 2026-10-05 .. dom 2026-10-11


# ---------------------------------------------------------------------------
# Fixture finta
# ---------------------------------------------------------------------------

def _tsk(root: Path, epic: str, us: str, tid: str, **fm) -> None:
    d = root / "management" / "kanban" / epic / us
    d.mkdir(parents=True, exist_ok=True)
    lines = [f"id: {tid}", f'title: "Titolo {tid}"', f"epic: {epic}"]
    lines += [f"{k}: {v}" for k, v in fm.items()]
    (d / f"{tid}.md").write_text("---\n" + "\n".join(lines) + "\n---\n\n# corpo\n", encoding="utf-8")


@pytest.fixture()
def fake(tmp_path: Path) -> Path:
    r = tmp_path
    (r / "factory.config.yaml").write_text("project: test\n", encoding="utf-8")
    ep = r / "management" / "kanban" / "AA-EP-001"
    ep.mkdir(parents=True)
    (ep / "AA-EP-001.md").write_text('---\nid: AA-EP-001\ntitle: "Epica uno"\n---\n', encoding="utf-8")
    # chiusi nella settimana
    _tsk(r, "AA-EP-001", "AA-US-1", "AA-TSK-1", status="done", closed_at="2026-10-05", done_by='"Mario Rossi"', estimate="M")
    _tsk(r, "AA-EP-001", "AA-US-1", "AA-TSK-2", status="done", closed_at='"2026-10-11"', done_by="Mario Rossi", estimate="S")
    # lista di autori: contato per ciascuno, una volta nel totale
    _tsk(r, "AA-EP-001", "AA-US-1", "AA-TSK-3", status="done", closed_at="2026-10-07", done_by='["Mario Rossi", "Anna Bianchi"]', estimate="XS")
    # alias del campo data e alias di done_by
    _tsk(r, "AA-EP-001", "AA-US-1", "AA-TSK-4", status="done", completed="2026-10-08", closed_by='"Anna Bianchi"', estimate="L")
    # senza done_by e senza taglia
    _tsk(r, "BB-EP-002", "BB-US-1", "BB-TSK-5", status="done", closed_at="2026-10-09")
    # fuso: 2026-10-04 23:30Z = 05/10 01:30 a Roma (dentro); 2026-10-11 22:30Z = 12/10 00:30 (fuori)
    _tsk(r, "AA-EP-001", "AA-US-2", "AA-TSK-6", status="done", closed_at="2026-10-04T23:30:00Z", done_by="Anna Bianchi", estimate="S")
    _tsk(r, "AA-EP-001", "AA-US-2", "AA-TSK-7", status="done", closed_at="2026-10-11T22:30:00Z", done_by="Anna Bianchi", estimate="S")
    # fuori settimana, senza data, altri stati
    _tsk(r, "AA-EP-001", "AA-US-2", "AA-TSK-8", status="done", closed_at="2026-10-12", done_by="Anna Bianchi", estimate="S")
    _tsk(r, "AA-EP-001", "AA-US-2", "AA-TSK-9", status="done", done_by="Anna Bianchi", estimate="S")
    _tsk(r, "AA-EP-001", "AA-US-2", "AA-TSK-10", status="superseded", closed_at="2026-10-06", estimate="S")
    _tsk(r, "AA-EP-001", "AA-US-2", "AA-TSK-11", status="in-progress", owner="utente-esempio", started_at="2026-10-06")
    _tsk(r, "AA-EP-001", "AA-US-2", "AA-TSK-12", status="blocked", owner="utente-esempio", blocked_by="[AA-TSK-11]")
    _tsk(r, "AA-EP-001", "AA-US-2", "AA-TSK-13", status="todo")

    wiki = r / "wiki"
    (wiki / "incidents").mkdir(parents=True)
    (wiki / "log.md").write_text(
        "# Log\n\n"
        "## 2026-10-12 09:00 — release DS @example/design-system 4.0.12 — DONE\n\n"
        "## 2026-10-07 09:40 — release DS @example/design-system 4.0.7 — DONE\n\ntesto\n\n"
        "## 2026-10-08 14:44 — release BE servizio-esempio-be → preprod — DONE\n\n"
        "## 2026-10-06 16:45 — release app-esempio → test — FAILED (build)\n\n"
        "## 2026-10-09T08:16Z — tavola-rotonda — non e' un rilascio — DONE\n", encoding="utf-8")
    (wiki / "log-2026-Q3.md").write_text(
        "## 2026-10-10T22:30Z — release BE altro-servizio-be → test — DONE\n"  # 11/10 00:30 a Roma: dentro
        "## 2026-09-30 10:00 — release DS @example/design-system 4.0.3 — DONE\n", encoding="utf-8")
    (wiki / "gaps.md").write_text(
        "# Gaps\n\n"
        "## 2026-10-06 — Gap uno\n\n"
        "- [ ] **G-AA-001** (HIGH) — primo\n"
        "  **Risolto:** 2026-10-09 — fatto\n"
        "- [ ] **G-AA-002** — secondo, resta aperto\n\n"
        "## 2026-10-12 — Fuori settimana\n\n"
        "- [ ] **G-AA-003** — troppo tardi\n\n"
        "## 2026-09-20 — Vecchio\n\n"
        "- [ ] **G-AA-000** — vecchio gap\n"
        "  **Risolto:** 2026-10-08 — chiuso in settimana\n\n"
        "## 2026-10-07 — Chiusura\n\n"
        "**Risolto:** 2026-10-07 — G-AA-004 chiuso.\n", encoding="utf-8")
    (wiki / "incidents" / "inc-uno.md").write_text(
        "---\ntype: wiki-incident\nstatus: resolved\nincident_date: 2026-10-08\ndate_resolved: 2026-10-10\n---\n",
        encoding="utf-8")
    (wiki / "incidents" / "inc-vecchio.md").write_text(
        "---\ntype: wiki-incident\nstatus: resolved\nincident_date: 2026-09-01\n---\n", encoding="utf-8")

    an = r / "analytics"
    (an / "events").mkdir(parents=True)
    (an / "pricing.yaml").write_text(
        "currency: USD\nmodels:\n  - id: test-model\n    pricing:\n      - valid_from: 2026-01-01\n"
        "        input_per_1m_tokens: 1.0\n        output_per_1m_tokens: 2.0\n"
        "        cache_read_per_1m_tokens: 0\n        cache_write_per_1m_tokens: 0\n", encoding="utf-8")
    ev = [
        {"ts": "2026-10-07T10:00:00Z", "model": "test-model", "hash": "a", "tokens": {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_write": 0}},
        {"ts": "2026-10-07T10:00:00Z", "model": "test-model", "hash": "a", "tokens": {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_write": 0}},  # duplicato
        {"ts": "2026-10-09T10:00:00Z", "model": "test-model", "hash": "b", "tokens": {"input": 0, "output": 1_000_000, "cache_read": 0, "cache_write": 0}},
        {"ts": "2026-10-13T10:00:00Z", "model": "test-model", "hash": "c", "tokens": {"input": 5_000_000, "output": 0, "cache_read": 0, "cache_write": 0}},
    ]
    (an / "events" / "2026-10.jsonl").write_text("\n".join(json.dumps(e) for e in ev) + "\n", encoding="utf-8")

    dl = r / "deliverables"
    (dl / "sub").mkdir(parents=True)
    (dl / "2026-10-06-report.md").write_text("x", encoding="utf-8")
    (dl / "2026-10-12-fuori.md").write_text("x", encoding="utf-8")
    (dl / "2026-10-08-cartella").mkdir()
    (dl / "2026-10-08-cartella" / "2026-10-08-interno.md").write_text("x", encoding="utf-8")
    (dl / "sub" / "nota-2026-10-10.md").write_text("x", encoding="utf-8")
    (dl / "digest").mkdir()
    (dl / "digest" / "2026-10-07-escluso.md").write_text("x", encoding="utf-8")
    (r / "factory.config.yaml").write_text(
        "documentation:\n  weekly_digest:\n    release_kinds:\n"
        "      - {prefix: \"ds \", label: \"design system\"}\n"
        "      - {prefix: \"be \", label: \"back-end\"}\n"
        "      - {prefix: \"app\", label: \"front-end\"}\n", encoding="utf-8")
    return r


def test_settimana_iso():
    assert wd.parse_week("2026-W41") == (dt.date(2026, 10, 5), dt.date(2026, 10, 11))
    assert wd.parse_week("2026-W01") == (dt.date(2025, 12, 29), dt.date(2026, 1, 4))
    with pytest.raises(ValueError):
        wd.parse_week("2026-41")
    assert wd.current_week(dt.date(2026, 10, 13)) == "2026-W42"


def test_fuso_roma():
    assert wd.utc_to_rome_date("2026-10-04T23:30:00Z") == dt.date(2026, 10, 5)   # CEST (+2)
    assert wd.utc_to_rome_date("2026-12-31T23:30:00Z") == dt.date(2027, 1, 1)    # CET (+1)
    assert wd.utc_to_rome_date("2026-03-29T00:30:00Z") == dt.date(2026, 3, 29)   # prima del cambio ora
    assert wd.utc_to_rome_date("2026-10-24T22:30:00Z") == dt.date(2026, 10, 25)  # ancora CEST
    assert wd.utc_to_rome_date("2026-10-25T23:30:00Z") == dt.date(2026, 10, 26)  # dopo il cambio: CET
    assert wd.utc_to_rome_date("2026-10-06") == dt.date(2026, 10, 6)
    assert wd.utc_to_rome_date("non una data") is None


def test_tsk_chiusi_fixture(fake):
    d = wd.collect(WEEK, fake)
    c = d["tsk_chiusi"]
    ids = [t["id"] for t in c["elenco"]]
    # TSK-7 fuori per il fuso, TSK-8 dopo, TSK-9 senza data, TSK-10 superseded
    assert ids == ["AA-TSK-1", "AA-TSK-6", "AA-TSK-3", "AA-TSK-4", "BB-TSK-5", "AA-TSK-2"]
    assert c["totale"] == 6
    assert c["punti"] == 2 + 3 + 1 + 5 + 0 + 2          # S + M + XS + L + senza taglia + S
    assert c["senza_taglia"] == 1
    assert c["senza_done_by"] == 1
    per_epic = {e["epica"]: (e["tsk"], e["punti"], e["titolo"]) for e in c["per_epica"]}
    assert per_epic == {"AA-EP-001": (5, 13, "Epica uno"), "BB-EP-002": (1, 0, "")}
    per_person = {p["persona"]: (p["tsk"], p["punti"]) for p in c["per_persona"]}
    assert per_person == {"Mario Rossi": (3, 6), "Anna Bianchi": (3, 8), "senza done_by": (1, 0)}
    assert d["qualita_dati"]["tsk_chiusi_senza_data"] == 1


def test_in_corso_e_bloccati_fixture(fake):
    s = wd.collect(WEEK, fake)["tsk_stato_attuale"]
    assert [t["id"] for t in s["in_corso"]] == ["AA-TSK-11"]
    assert [t["id"] for t in s["bloccati"]] == ["AA-TSK-12"]
    assert "stato" in s["nota"].lower() and "generazione" in s["nota"]


def test_rilasci_forma_log_factory_e_tipi_di_default(tmp_path):
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "log.md").write_text(
        "## [2026-10-07] release | v2.44.0 — titolo — DONE\n"
        "## [2026-10-08] migration | non e' un rilascio\n", encoding="utf-8")
    r = wd.collect_releases(tmp_path, *wd.parse_week(WEEK))
    assert [(x["data"], x["tipo"]) for x in r["elenco"]] == [("2026-10-07", "altro")]


def test_rilasci_fixture(fake):
    pytest.importorskip("yaml")
    r = wd.collect(WEEK, fake)["rilasci"]
    assert [(x["data"], x["oggetto"], x["esito"], x["tipo"]) for x in r["elenco"]] == [
        ("2026-10-06", "app-esempio → test", "fallito", "front-end"),
        ("2026-10-07", "DS @example/design-system 4.0.7", "completato", "design system"),
        ("2026-10-08", "BE servizio-esempio-be → preprod", "completato", "back-end"),
        ("2026-10-11", "BE altro-servizio-be → test", "completato", "back-end"),   # 22:30Z del 10 = 00:30 dell'11
    ]
    assert r["totale"] == 4 and r["completati"] == 3


def test_gap_e_incidenti_fixture(fake):
    d = wd.collect(WEEK, fake)
    g = d["gap"]
    assert g["registrati"] == ["G-AA-001", "G-AA-002"]
    assert g["chiusi"] == ["G-AA-000", "G-AA-001", "G-AA-004"]
    assert g["ancora_aperti_fra_i_registrati"] == ["G-AA-002"]
    i = d["incidenti"]
    assert [x["file"] for x in i["aperti"]] == ["inc-uno.md"]
    assert [x["file"] for x in i["chiusi"]] == ["inc-uno.md"]


def test_costo_fixture(fake):
    k = wd.collect(WEEK, fake)["costo_token"]
    assert k["disponibile"] is True
    assert k["usd"] == 3.0                      # 1M input a 1 USD + 1M output a 2 USD; duplicato e 13/10 esclusi
    assert k["eventi"] == 2
    assert k["giorni_con_eventi"] == ["2026-10-07", "2026-10-09"]
    assert k["parziale"] is True and "2 giorni su 7" in k["nota"]


def test_costo_non_disponibile(fake):
    for f in (fake / "analytics" / "events").glob("*.jsonl"):
        f.unlink()
    k = wd.collect(WEEK, fake)["costo_token"]
    assert k["disponibile"] is False and "event store" in k["motivo"]
    # settimana senza eventi con event store presente
    (fake / "analytics" / "events" / "2026-10.jsonl").write_text(
        '{"ts":"2026-10-13T10:00:00Z","model":"test-model","tokens":{"input":1}}\n', encoding="utf-8")
    k = wd.collect(WEEK, fake)["costo_token"]
    assert k["disponibile"] is False and "non contiene eventi nella settimana" in k["motivo"]


def test_deliverable_fixture(fake):
    dl = wd.collect(WEEK, fake)["deliverable"]
    assert [x["nome"] for x in dl["elenco"]] == [
        "2026-10-06-report.md", "2026-10-08-cartella/", "sub/nota-2026-10-10.md"]


def test_collect_deterministico(fake):
    assert json.dumps(wd.collect(WEEK, fake), sort_keys=True) == json.dumps(wd.collect(WEEK, fake), sort_keys=True)


def test_render_html_e_commento(fake):
    d = wd.collect(WEEK, fake)
    page = wd.render_html(d)
    assert page.startswith("<!DOCTYPE html>") and '<html lang="it">' in page
    assert "prefers-color-scheme" in page and "http://" not in page and "https://" not in page
    assert "Commento dell'autore" not in page
    d["commento"] = "Una settimana buona.\n\n- punto uno\n- punto <b>due</b>"
    page = wd.render_html(d)
    assert "Commento dell'autore" in page and "Una settimana buona." in page
    assert "&lt;b&gt;due" in page                       # testo del commento sempre escapato
    assert "Fonte:" in page and "Limiti dei dati" in page
    assert "Costo token (USD)" in page


def test_render_docx(fake, tmp_path):
    pytest.importorskip("docx")
    d = wd.collect(WEEK, fake)
    d["commento"] = "Commento di prova."
    out = tmp_path / "out" / "w.docx"
    assert wd.render_docx(d, out) is True
    import docx
    text = "\n".join(p.text for p in docx.Document(str(out)).paragraphs)
    assert "Digest settimanale 2026-W41" in text and "Commento di prova." in text


def test_cli_scrive_html_e_json(fake, tmp_path, capsys):
    sys_path = _REPO_ROOT / "tools" / "docs"
    if not (sys_path / "redact.py").is_file():
        pytest.skip("redact.py non ancora presente")
    (fake / "tools" / "docs").mkdir(parents=True)
    (fake / "tools" / "docs" / "redact.py").write_text(
        (sys_path / "redact.py").read_text(encoding="utf-8"), encoding="utf-8")
    comm = tmp_path / "c.md"
    comm.write_text("Commento.", encoding="utf-8")
    out = tmp_path / "o"
    assert wd.main(["--root", str(fake), "--settimana", WEEK, "--out", str(out), "--commento", str(comm)]) == 0
    assert (out / f"{WEEK}.html").is_file()
    assert "Commento dell'autore" in (out / f"{WEEK}.html").read_text(encoding="utf-8")
    capsys.readouterr()
    assert wd.main(["--root", str(fake), "--settimana", WEEK, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["tsk_chiusi"]["totale"] == 6
    # un segreto nel commento blocca la scrittura
    comm.write_text("password: SuperSegreta123", encoding="utf-8")
    out2 = tmp_path / "o2"
    assert wd.main(["--root", str(fake), "--settimana", WEEK, "--out", str(out2), "--commento", str(comm)]) == 3
    assert not (out2 / f"{WEEK}.html").exists()


def test_cli_settimana_non_valida(fake):
    assert wd.main(["--root", str(fake), "--settimana", "boh"]) == 2


# ---------------------------------------------------------------------------
# Correzioni della revisione
# ---------------------------------------------------------------------------

def _snap(ts, task, out, inp=0, h=None):
    return {"ts": ts, "task_id": task, "task_type": "session-aggregate", "model": "test-model",
            "hash": h or f"{task}-{ts}", "tokens": {"input": inp, "output": out, "cache_read": 0, "cache_write": 0}}


def test_costo_istantanee_cumulative(fake):
    """Le istantanee session-aggregate sono cumulative: per sessione ultima della settimana meno ultima
    precedente alla settimana, non la somma."""
    ev = [
        _snap("2026-10-02T10:00:00Z", "session:aaa:main:test-model", 1_000_000, 1_000_000),   # prima della settimana
        _snap("2026-10-06T10:00:00Z", "session:aaa:main:test-model", 1_500_000, 1_000_000),
        _snap("2026-10-08T10:00:00Z", "session:aaa:main:test-model", 3_000_000, 1_000_000),
        _snap("2026-10-07T10:00:00Z", "session:bbb:main:test-model", 500_000),                 # sessione nata nella settimana
        _snap("2026-10-07T12:00:00Z", "session:bbb:main:test-model", 700_000),
    ]
    (fake / "analytics" / "events" / "2026-10.jsonl").write_text(
        "\n".join(json.dumps(e) for e in ev) + "\n", encoding="utf-8")
    k = wd.collect(WEEK, fake)["costo_token"]
    assert k["token"]["output"] == (3_000_000 - 1_000_000) + 700_000
    assert k["token"]["input"] == 0                       # 1M - 1M, il contatore non cresce
    assert k["usd"] == 2 * 2.7
    assert k["sessioni"] == 2
    assert any("istantanee cumulative" in x for x in wd.collect(WEEK, fake)["riuso"])


def test_costo_istantanea_calo_non_negativo(fake):
    ev = [_snap("2026-10-02T10:00:00Z", "session:ccc:main:test-model", 900),
          _snap("2026-10-06T10:00:00Z", "session:ccc:main:test-model", 100)]
    (fake / "analytics" / "events" / "2026-10.jsonl").write_text(
        "\n".join(json.dumps(e) for e in ev) + "\n", encoding="utf-8")
    assert wd.collect(WEEK, fake)["costo_token"]["token"]["output"] == 0


def _with_redact(fake):
    (fake / "tools" / "docs").mkdir(parents=True, exist_ok=True)
    (fake / "tools" / "docs" / "redact.py").write_text(
        (_REPO_ROOT / "tools" / "docs" / "redact.py").read_text(encoding="utf-8"), encoding="utf-8")


def test_redazione_su_dati_sorgente_commento(fake, tmp_path):
    """L'escape HTML trasforma le virgolette in &quot; e nasconde il segreto al controllo: va controllato il
    testo sorgente, prima del render, cosi' copre anche il Word."""
    _with_redact(fake)
    comm = tmp_path / "c.md"
    comm.write_text('Config: token="ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"', encoding="utf-8")
    out = tmp_path / "o"
    assert wd.main(["--root", str(fake), "--settimana", WEEK, "--out", str(out), "--commento", str(comm)]) == 3
    assert not list(out.glob("*")) if out.exists() else True


def test_redazione_su_dati_sorgente_kanban(fake, tmp_path):
    _with_redact(fake)
    _tsk(fake, "AA-EP-001", "AA-US-3", "AA-TSK-20", status="done", closed_at="2026-10-06",
         done_by="Mario Rossi", estimate="S")
    f = next((fake / "management" / "kanban").rglob("AA-TSK-20.md"))
    f.write_text(f.read_text(encoding="utf-8").replace('title: "Titolo AA-TSK-20"',
                                                       'title: "usa password: Abc12345xyz"'), encoding="utf-8")
    out = tmp_path / "o"
    assert wd.main(["--root", str(fake), "--settimana", WEEK, "--out", str(out)]) == 3
    assert not out.exists() or not list(out.glob("*"))


def test_deliverable_data_non_valida(fake):
    dl = fake / "deliverables"
    (dl / "2026-13-01-rotto.md").write_text("x", encoding="utf-8")
    (dl / "0000-00-00-zero.md").write_text("x", encoding="utf-8")
    (dl / "zz-2026-10-09-dopo.md").write_text("x", encoding="utf-8")
    nomi = [x["nome"] for x in wd.collect(WEEK, fake)["deliverable"]["elenco"]]
    assert "zz-2026-10-09-dopo.md" in nomi            # la scansione prosegue dopo il nome non valido
    assert "sub/nota-2026-10-10.md" in nomi and "2026-10-06-report.md" in nomi


def test_documentazione_disattivata(fake, tmp_path, capsys):
    pytest.importorskip("yaml")
    (fake / "factory.config.yaml").write_text("documentation:\n  enabled: false\n", encoding="utf-8")
    out = tmp_path / "o"
    assert wd.main(["--root", str(fake), "--settimana", WEEK, "--out", str(out)]) == 0
    assert "disattivata" in capsys.readouterr().out
    assert not out.exists()


def test_redazione_spenta_solo_se_false(fake):
    pytest.importorskip("yaml")
    for body, atteso in (("documentation:\n  redaction:\n    enabled: false\n", False),
                         ("documentation:\n  redaction:\n    enabled:\n", True),
                         ("documentation:\n  redaction:\n    enabled: 0\n", True),
                         ("documentation:\n  redaction: {}\n", True),
                         ("documentation:\n  redaction:\n", True)):
        (fake / "factory.config.yaml").write_text(body, encoding="utf-8")
        assert wd.load_doc_config(fake)["redaction"] is atteso, body


def test_persone_dal_team_della_config_di_velocity(fake):
    """Il team si legge con load_config di team-velocity.py e resolve_persona ha tre argomenti.

    Prima la funzione cercava una chiave `team_config` che load_config non conosce (team mai letto)
    e chiamava resolve_persona con quattro argomenti (TypeError appena il team c'era)."""
    cfg = fake / "analytics" / "velocity" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({
        "punti": {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8},
        "team": [{"id": "mrossi", "nome": "Mario Rossi", "alias": ["mario"]}],
        "agenti": ["docs-dev"],
    }), encoding="utf-8")
    _tsk(fake, "AA-EP-001", "AA-US-3", "AA-TSK-20", status="done", closed_at="2026-10-06", done_by="mario", estimate="S")
    _tsk(fake, "AA-EP-001", "AA-US-3", "AA-TSK-21", status="done", closed_at="2026-10-06", done_by="docs-dev", estimate="S")
    per_person = {p["persona"]: p["tsk"] for p in wd.collect(WEEK, fake)["tsk_chiusi"]["per_persona"]}
    assert per_person["Mario Rossi"] == 4      # 3 della fixture + l'alias «mario»
    assert per_person["agente"] == 1
    assert per_person["Anna Bianchi"] == 3     # fuori dal team: il nome resta com'e'
