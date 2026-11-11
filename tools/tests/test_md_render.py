"""Test di tools/docs/md_render.py: un caso per costrutto, escape, wikilink, frontmatter."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docs"))
import md_render as r  # noqa: E402


def test_heading_con_id_e_dedupe():
    h = r.render("# Titolo uno\n\n## Sezione\n\n## Sezione\n")
    assert '<h1 id="titolo-uno">Titolo uno</h1>' in h
    assert '<h2 id="sezione">' in h and '<h2 id="sezione-1">' in h


def test_paragrafi_e_a_capo():
    h = r.render("uno\ndue\n\ntre  \nquattro")
    assert h.count("<p>") == 2
    assert "<br>" in h


def test_liste_annidate_e_numerate():
    h = r.render("- a\n  - b\n    1. x\n    2. y\n- c\n")
    assert h.count("<ul>") == 2 and "<ol>" in h
    assert "<li>x</li>" in h and "<li>c</li>" in h


def test_lista_numerata_con_start():
    assert '<ol start="3">' in r.render("3. tre\n4. quattro\n")


def test_task_list():
    h = r.render("- [x] fatto\n- [ ] da fare\n")
    assert 'class="task-list"' in h
    assert '<input type="checkbox" disabled checked>' in h
    assert '<input type="checkbox" disabled>' in h


def test_tabella_con_allineamento():
    h = r.render("| A | B | C |\n|:--|:-:|--:|\n| 1 | 2 | 3 |\n")
    assert 'text-align:left">A' in h
    assert 'text-align:center">B' in h
    assert 'text-align:right">C' in h
    assert "<td" in h and "<thead>" in h


def test_tabella_pipe_dentro_codice():
    h = r.render("| a | b |\n|---|---|\n| `x|y` | 2 |\n")
    assert "<code>x|y</code>" in h


def test_code_fence_con_linguaggio_ed_escape():
    h = r.render('```bash\necho "<x>" && a > b\n```\n')
    assert '<pre><code class="language-bash">' in h
    assert "&lt;x&gt;" in h and "<x>" not in h


def test_code_fence_senza_interpretare_markdown():
    h = r.render("```\n# non titolo\n**no**\n```\n")
    assert "<h1" not in h and "<strong>" not in h


def test_codice_inline():
    assert "<code>a&lt;b&gt;</code>" in r.render("usa `a<b>` qui")


def test_blockquote_annidato():
    h = r.render("> uno\n> > due\n")
    assert h.count("<blockquote>") == 2


def test_hr():
    assert "<hr>" in r.render("a\n\n---\n\nb")


def test_link_e_immagine():
    h = r.render('[sito](https://example.org/x "t") ![alt](img/a.png)')
    assert '<a href="https://example.org/x" title="t"' in h
    assert '<img src="img/a.png" alt="alt">' in h


def test_link_pericolosi_neutralizzati():
    h = r.render("[x](javascript:alert(1))")
    assert "javascript:" not in h


def test_enfasi():
    h = r.render("**g** *c* ~~b~~ _u_ __g2__")
    assert "<strong>g</strong>" in h and "<em>c</em>" in h and "<del>b</del>" in h
    assert "<em>u</em>" in h and "<strong>g2</strong>" in h


def test_enfasi_su_piu_righe():
    assert "<strong>a\nb</strong>" in r.render("**a\nb**")


def test_autolink():
    h = r.render("vedi <https://a.it/x> e https://b.it/y.")
    assert '<a href="https://a.it/x"' in h
    assert '<a href="https://b.it/y"' in h and "y</a>." in h


def test_escape_html_grezzo():
    h = r.render("<script>alert(1)</script> & <b>x</b>")
    assert "<script>" not in h and "&lt;script&gt;" in h and "&amp;" in h


def test_commenti_html_scartati():
    h = r.render("prima\n\n<!-- nota\nsu due righe -->\n\ndopo <!-- inline --> fine")
    assert "nota" not in h and "inline" not in h
    assert "prima" in h and "fine" in h


def test_citazione_src_come_span():
    h = r.render("[^src: raw/x.md §1]")
    assert '<span class="cite">src: raw/x.md §1</span>' in h


def test_wikilink_semplice_con_testo_e_sezione():
    seen = []

    def res(t):
        seen.append(t)
        return "../a/" + t + ".html"

    h = r.render("[[pagina]] [[pagina|testo]] [[pagina#Una Sezione]]", res)
    assert '<a class="wikilink" href="../a/pagina.html">pagina</a>' in h
    assert '>testo</a>' in h
    assert 'href="../a/pagina.html#una-sezione"' in h
    assert seen == ["pagina", "pagina", "pagina"]


def test_wikilink_non_risolto():
    h = r.render("[[assente]] [[x|etichetta]]", lambda t: None)
    assert '<span class="wl-missing" title="non pubblicata">assente</span>' in h
    assert ">etichetta</span>" in h


def test_wikilink_senza_resolver_e_escape():
    h = r.render("[[<b>]]")
    assert "wl-missing" in h and "<b>" not in h


def test_link_md_relativo_passa_dal_resolver():
    h = r.render("[x](../a/b.md#sez) [y](https://e.org/z.md)", lambda t: "OK/" + t)
    assert 'href="OK/../a/b.md#sez"' in h
    assert 'href="https://e.org/z.md"' in h


def test_frontmatter_yaml():
    fm, body = r.parse_frontmatter("---\ntitle: T\nstatus: draft\ncreated: 2026-10-13\ntags: [a, b]\n---\n# Corpo\n")
    assert fm["title"] == "T" and fm["status"] == "draft"
    assert fm["created"] == "2026-10-13"  # data normalizzata a stringa
    assert fm["tags"] == ["a", "b"]
    assert body.startswith("# Corpo")


def test_frontmatter_assente():
    assert r.parse_frontmatter("# solo corpo") == ({}, "# solo corpo")


def test_frontmatter_parser_semplice(monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", None)  # import yaml -> ImportError
    fm, _ = r.parse_frontmatter("---\nstatus: review\nsources:\n  - \"a.md\"\n  - b.md\nrelated: [x, y]\n---\nc")
    assert fm["status"] == "review"
    assert fm["sources"] == ["a.md", "b.md"]
    assert fm["related"] == ["x", "y"]


def test_extract_title_e_plain_text():
    assert r.extract_title("testo\n# Il **titolo**\n") == "Il titolo"
    pt = r.plain_text("# T\n\n- voce `x`\n\n```\ncodice\n```\n| a | b |\n|---|---|\n| 1 | 2 |")
    assert "codice" not in pt and "voce x" in pt and "---" not in pt


def test_lista_con_righe_vuote_resta_un_solo_elenco():
    h = r.render("- uno\n\n- due\n\n- tre\n")
    assert h.count("<ul") == 1 and h.count("<li>") == 3 and "<p>uno</p>" in h


def test_autolink_non_ingloba_segnaposto():
    """Un URL nudo seguito da wikilink o code span non deve finire nell'href con l'HTML dei segnaposto."""
    for src in ("vedi https://example.com[[pagina]]", "https://example.com`code`"):
        h = r.render(src)
        assert 'href="https://example.com"' in h, h
        assert "\x00" not in h
        import re as _re
        for href in _re.findall(r'href="([^"]*)"', h):
            assert "<" not in href and ">" not in href, h
