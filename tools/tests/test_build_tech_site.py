"""Test di tools/docs/build_tech_site.py su una wiki finta in tmp_path."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docs"))
import build_tech_site as b  # noqa: E402

PAT = "a2" * 26  # 52 caratteri base32: sembra un PAT


def _w(wiki: Path, rel: str, text: str) -> None:
    p = wiki / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def factory(tmp_path):
    root = tmp_path / "factory"
    wiki = root / "wiki"
    (root / "factory.config.yaml").parent.mkdir(parents=True)
    (root / "factory.config.yaml").write_text("project: t\n", encoding="utf-8")
    _w(wiki, "decisions/d1.md",
       "---\ntitle: Decisione uno\nstatus: approved\nsource: raw/x.md\n---\n# Decisione uno\n\n"
       "Vedi [[runbook-a]], [[sessions/s1]], [[inesistente]] e [[runbooks/runbook-a#Passi]].\n")
    _w(wiki, "runbooks/runbook-a.md", "---\nstatus: draft\n---\n# Runbook A\n\n## Passi\n\n- uno\n")
    _w(wiki, "be-services/api/svc.md", "# Servizio\n\nTesto del servizio con ricerca.\n")
    _w(wiki, "sessions/s1.md", "# Sessione\n")
    _w(wiki, "sources/src.md", "# Sorgente grezza\n")
    _w(wiki, "gaps.md", "# Gaps\n")
    _w(wiki, "log.md", "# Log\n")
    return root


def run(factory, out, *extra):
    return b.main(["--root", str(factory), "--out", str(out)] + list(extra))


def test_build_sezioni_incluse_ed_escluse(factory, tmp_path):
    out = tmp_path / "site"
    assert run(factory, out) == 0
    assert (out / "index.html").is_file()
    assert (out / "decisions" / "d1.html").is_file()
    assert (out / "runbooks" / "runbook-a.html").is_file()
    assert (out / "be-services" / "api" / "svc.html").is_file()  # path speculare
    assert not (out / "sessions").exists()
    assert not (out / "sources").exists()
    assert not (out / "gaps.html").exists() and not (out / "log.html").exists()
    assert (out / "search-index.js").is_file()


def test_pagina_ha_badge_fonte_breadcrumb_e_ritorno(factory, tmp_path):
    out = tmp_path / "site"
    run(factory, out)
    h = (out / "decisions" / "d1.html").read_text(encoding="utf-8")
    assert "st-approved" in h and "approved" in h
    assert "raw/x.md" in h  # fonte in testa
    assert 'class="crumbs"' in h and "../index.html" in h
    assert "Torna all'indice" in h
    assert 'lang="it"' in h and "http://" not in h.split("<main>")[0] and "https://" not in h.split("<main>")[0]


def test_wikilink_risolti_e_non_pubblicati(factory, tmp_path):
    out = tmp_path / "site"
    run(factory, out)
    h = (out / "decisions" / "d1.html").read_text(encoding="utf-8")
    assert 'href="../runbooks/runbook-a.html"' in h  # per nome file
    assert 'href="../runbooks/runbook-a.html#passi"' in h  # per path + sezione
    assert h.count('class="wl-missing"') == 2  # sezione esclusa + pagina inesistente
    assert "sessions/s1" in h.split('class="wl-missing"')[1]


def test_index_conteggi_commit_e_ricerca(factory, tmp_path):
    out = tmp_path / "site"
    run(factory, out)
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert "Generata il" in idx and "3 pagine" in idx
    assert '<script src="search-index.js">' in idx and 'id="q"' in idx
    js = (out / "search-index.js").read_text(encoding="utf-8")
    assert js.startswith("window.SEARCH_INDEX=")
    assert "Decisione uno" in js and "Testo del servizio" in js
    assert "Sorgente grezza" not in js


def test_sections_flag(factory, tmp_path):
    out = tmp_path / "site"
    assert run(factory, out, "--sections", "runbooks") == 0
    assert (out / "runbooks" / "runbook-a.html").is_file()
    assert not (out / "decisions").exists()
    h = (out / "runbooks" / "runbook-a.html").read_text(encoding="utf-8")
    assert "Passi" in h


def test_dry_run_non_scrive(factory, tmp_path, capsys):
    out = tmp_path / "site"
    assert run(factory, out, "--dry-run") == 0
    assert not out.exists()
    assert "3 pagine" in capsys.readouterr().out


def test_redazione_blocca_e_non_lascia_output(factory, tmp_path, capsys):
    _w(factory / "wiki", "runbooks/cattivo.md", "# Cattivo\n\nriga\nuso token=" + PAT[:20] + "abcdefgh\n")
    out = tmp_path / "site"
    assert run(factory, out) == 2
    err = capsys.readouterr().err
    assert "wiki/runbooks/cattivo.md:4" in err
    assert PAT[:20] + "abcdefgh" not in err  # excerpt mascherato
    assert not out.exists()
    assert [p for p in tmp_path.iterdir() if "site" in p.name] == []  # niente cartelle temporanee


def test_redazione_non_sovrascrive_output_esistente(factory, tmp_path):
    out = tmp_path / "site"
    assert run(factory, out) == 0
    before = (out / "index.html").read_text(encoding="utf-8")
    _w(factory / "wiki", "decisions/cattivo.md", "password: SuperSegreto1\n")
    assert run(factory, out) == 2
    assert (out / "index.html").read_text(encoding="utf-8") == before
    assert not (out / "decisions" / "cattivo.html").exists()


def test_redazione_dry_run(factory, tmp_path):
    # stringa composta a runtime: nel sorgente non compare un token letterale
    _w(factory / "wiki", "decisions/cattivo.md", "Authorization: " + "Bearer " + "x1y2" * 6 + "\n")
    assert run(factory, tmp_path / "site", "--dry-run") == 2


def test_variabili_ambiente_senza_valore_non_bloccano(factory, tmp_path):
    _w(factory / "wiki", "runbooks/env.md",
       "Usa `ACME_TOKEN` e `Authorization: Basic <base64>` e password: ${PWD}\n")
    assert run(factory, tmp_path / "site") == 0


def test_rebuild_sostituisce_output(factory, tmp_path):
    out = tmp_path / "site"
    run(factory, out)
    (factory / "wiki" / "decisions" / "d1.md").unlink()
    run(factory, out)
    assert not (out / "decisions" / "d1.html").exists()


def test_scambio_fallito_ripristina_la_versione_precedente(factory, tmp_path, monkeypatch):
    out = tmp_path / "site"
    out.mkdir()
    (out / "precedente.txt").write_text("vecchio", encoding="utf-8")
    orig = Path.rename

    def rename(self, target):
        if ".tmp-" in self.name:
            raise OSError("rename fallita")
        return orig(self, target)

    monkeypatch.setattr(Path, "rename", rename)
    with pytest.raises(OSError):
        run(factory, out)
    monkeypatch.undo()
    assert (out / "precedente.txt").read_text(encoding="utf-8") == "vecchio"
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("site")) == ["site"]


def test_documentazione_disattivata(factory, tmp_path, capsys):
    pytest.importorskip("yaml")
    (factory / "factory.config.yaml").write_text("documentation:\n  enabled: false\n", encoding="utf-8")
    out = tmp_path / "site"
    assert run(factory, out) == 0
    assert "disattivata" in capsys.readouterr().out
    assert not out.exists()


def test_redazione_spenta_solo_se_false(factory):
    pytest.importorskip("yaml")
    for body, atteso in (("documentation:\n  redaction:\n    enabled: false\n", False),
                         ("documentation:\n  redaction:\n    enabled:\n", True),
                         ("documentation:\n  redaction:\n", True),
                         ("documentation:\n  enabled: true\n", True)):
        (factory / "factory.config.yaml").write_text(body, encoding="utf-8")
        assert b.load_tech_config(factory)["redaction"] is atteso, body
    assert b.load_tech_config(factory)["enabled"] is True


def test_etichetta_sezione_di_ripiego():
    assert b.section_label("decisions") == "Decisioni"
    assert b.section_label("area-nuova") == "Area Nuova"
