"""Test del backend SQLite FTS5 su una wiki finta."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import fts_index  # noqa: E402

pytestmark = pytest.mark.skipif(not fts_index.fts5_available(), reason="SQLite senza FTS5")


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / "wiki" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "factory.config.yaml").write_text("wiki_search:\n  enabled: true\n", encoding="utf-8")
    _write(tmp_path, "decisions/adr-uno.md",
           "---\ntitle: Scelta del flusso di rilascio\nstatus: approved\n---\n"
           "Introduzione generale.\n\n## Contesto\nIl rilascio in preprod richiede la promozione.\n\n"
           "## Decisione\nUsiamo Unleash per i flag.\n")
    _write(tmp_path, "runbooks/attivita.md",
           "---\ntitle: Elenco delle attività\nstatus: draft\n---\n"
           "## Passi\nLa dichiarazione ACME42 si compila dal modulo.\n")
    _write(tmp_path, "concepts/codice.md",
           "---\ntitle: Esempio\nstatus: approved\n---\n"
           "## Reale\nTesto reale zanzibar.\n\n```\n## finto heading\nnon una sezione\n```\n")
    _write(tmp_path, "index.md", "# Indice\nPagina radice con keyword radicepage.\n")
    return tmp_path


def test_build_e_ricerca_base(root: Path):
    info = fts_index.build(root)
    assert info["pages"] == 4
    assert info["chunks"] >= 6
    assert (root / ".wiki-search" / "fts.sqlite").is_file()
    out = fts_index.search(root, "Unleash flag")
    assert out["results"][0]["path"] == "wiki/decisions/adr-uno.md"
    assert out["results"][0]["section"] == "Decisione"
    assert "[Unleash]" in out["results"][0]["snippet"]


def test_prefisso_e_diacritici(root: Path):
    fts_index.build(root)
    assert fts_index.search(root, "attivita")["results"][0]["path"] == "wiki/runbooks/attivita.md"
    assert fts_index.search(root, "attività")["results"][0]["path"] == "wiki/runbooks/attivita.md"
    assert fts_index.search(root, "promoz")["results"]  # prefisso


def test_query_con_caratteri_speciali(root: Path):
    fts_index.build(root)
    for q in ['"ACME42" OR (', 'ACME42 AND', '*', '"', 'a:b NEAR(', "x' OR 1=1 --", ""]:
        out = fts_index.search(root, q)  # non deve sollevare
        assert "results" in out
    assert fts_index.search(root, '"ACME42" OR (')["results"][0]["path"] == "wiki/runbooks/attivita.md"


def test_fallback_or(root: Path):
    fts_index.build(root)
    out = fts_index.search(root, "Unleash zanzibar")  # nessuna sezione contiene entrambi
    assert out["mode"] == "or"
    paths = {r["path"] for r in out["results"]}
    assert {"wiki/decisions/adr-uno.md", "wiki/concepts/codice.md"} <= paths


def test_heading_in_code_fence_non_divide(root: Path):
    fts_index.build(root)
    out = fts_index.search(root, "finto")
    assert out["results"] and out["results"][0]["section"] == "Reale"


def test_filtri(root: Path):
    fts_index.build(root)
    assert fts_index.search(root, "rilascio", section="runbooks")["results"] == []
    assert fts_index.search(root, "rilascio", section="decisions")["results"]
    assert fts_index.search(root, "dichiarazione", status="approved")["results"] == []
    assert fts_index.search(root, "dichiarazione", status="draft")["results"]


def test_ranking_titolo_pesa_piu_del_corpo(root: Path):
    _write(root, "tech/solo-corpo.md", "---\ntitle: Altro\n---\n## X\nrilascio rilascio rilascio\n")
    fts_index.build(root)
    out = fts_index.search(root, "rilascio")
    assert out["results"][0]["path"] == "wiki/decisions/adr-uno.md"  # "rilascio" nel titolo


def test_incrementale_una_sola_pagina(root: Path):
    first = fts_index.build(root)
    assert first["reindexed"] == 4
    again = fts_index.build(root)
    assert again["reindexed"] == 0 and again["unchanged"] == 4
    _write(root, "runbooks/attivita.md",
           "---\ntitle: Elenco delle attività\nstatus: draft\n---\n## Passi\nContenuto nuovo kiwi.\n")
    upd = fts_index.build(root)
    assert upd["reindexed"] == 1 and upd["changed"] == 1 and upd["unchanged"] == 3
    assert fts_index.search(root, "kiwi")["results"]
    assert fts_index.search(root, "ACME42")["results"] == []  # il vecchio contenuto è sparito


def test_pagine_aggiunte_e_rimosse(root: Path):
    fts_index.build(root)
    _write(root, "tech/nuova.md", "## A\nparola quokka\n")
    (root / "wiki" / "index.md").unlink()
    upd = fts_index.build(root)
    assert upd["added"] == 1 and upd["removed"] == 1
    assert fts_index.search(root, "quokka")["results"]
    assert fts_index.search(root, "radicepage")["results"] == []


def test_full_ricostruisce(root: Path):
    fts_index.build(root)
    info = fts_index.build(root, full=True)
    assert info["full"] and info["reindexed"] == 4


def test_ricerca_senza_indice_lo_costruisce(root: Path):
    assert not (root / ".wiki-search" / "fts.sqlite").exists()
    out = fts_index.search(root, "Unleash")
    assert out["built"] is not None and out["results"]
    assert fts_index.status(root)["exists"]


def test_status_senza_indice(root: Path):
    assert fts_index.status(root)["exists"] is False


def test_cli_json(root: Path, capsys):
    rc = fts_index._main(["--root", str(root), "search", "Unleash", "--json"])
    assert rc == 0
    assert "adr-uno.md" in capsys.readouterr().out


def test_searcher_backend_fts5(root: Path, monkeypatch):
    import searcher

    assert searcher.resolve_backend("fts5") == "fts5"
    assert searcher.resolve_backend("hybrid") == "hybrid"
    monkeypatch.setattr(searcher, "_hybrid_deps_importable", lambda: False)
    assert searcher.resolve_backend("auto") == "fts5"
    monkeypatch.setattr(searcher, "_hybrid_deps_importable", lambda: True)
    assert searcher.resolve_backend("auto") == "hybrid"

    (root / "factory.config.yaml").write_text(
        "wiki_search:\n  enabled: true\n  backend: fts5\n", encoding="utf-8")
    s = searcher.HybridSearcher(config_path=str(root))
    res = s.search("Unleash flag", top_k=3)
    assert res["fallback"] is False
    assert res["results"][0]["path"] == "wiki/decisions/adr-uno.md"


def test_sezioni_secondarie_pesano_meno(root: Path):
    _write(root, "sessions/s1.md", "---\ntitle: Sessione\n---\n## Note\nkappaterm kappaterm kappaterm kappaterm\n")
    _write(root, "entities/e1.md", "---\ntitle: Entita\n---\n## Note\nkappaterm\n")
    fts_index.build(root)
    out = fts_index.search(root, "kappaterm")
    assert out["results"][0]["path"] == "wiki/entities/e1.md"
    assert fts_index.search(root, "kappaterm", section="sessions")["results"][0]["path"] == "wiki/sessions/s1.md"


def test_una_riga_per_pagina(root: Path):
    _write(root, "entities/multi.md",
           "---\ntitle: Multi\n---\n## Uno\nomegaterm\n\n## Due\nomegaterm\n\n## Tre\nomegaterm\n")
    fts_index.build(root)
    paths = [r["path"] for r in fts_index.search(root, "omegaterm", top=5)["results"]]
    assert paths == ["wiki/entities/multi.md"]


def test_aggiornamento_automatico_senza_refresh(root: Path):
    import os
    fts_index.build(root)
    assert fts_index.search(root, "novitaunica")["results"] == []
    p = _write(root, "runbooks/nuova.md", "---\ntitle: Nuova\nstatus: draft\n---\n## Corpo\nNel testo c'e novitaunica.\n")
    # mtime sicuramente piu' recente dell'ultima costruzione
    future = p.stat().st_mtime + 10
    os.utime(p, (future, future))
    out = fts_index.search(root, "novitaunica")          # niente refresh=True
    assert [r["path"] for r in out["results"]] == ["wiki/runbooks/nuova.md"]
    assert out["built"] is not None
    # indice aggiornato: una seconda ricerca non ricostruisce
    assert fts_index.search(root, "novitaunica")["built"] is None


def test_nessun_aggiornamento_se_wiki_invariata(root: Path):
    fts_index.build(root)
    assert fts_index.search(root, "Unleash")["built"] is None
