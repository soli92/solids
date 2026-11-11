"""Test per tools/docs/verify_verbatim.py."""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "docs"))

import verify_verbatim as vv  # noqa: E402


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = vv.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = self._t.name
        self.addCleanup(self._t.cleanup)

    def w(self, name, text):
        p = os.path.join(self.d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p


class Citazioni(Base):
    def test_ok(self):
        self.w("a/f.py", "1\n2\n3\n")
        self.w("wiki/x.md", "x\n")
        doc = self.w("d.md", "vedi a/f.py:2-3 e [^src: a/f.py:1] e wiki/x.md\n")
        code, out, _ = run("citazioni", doc, "--root", self.d)
        self.assertEqual(code, 0, out)

    def test_riga_fuori(self):
        self.w("a/f.py", "1\n2\n3\n")
        doc = self.w("d.md", "vedi a/f.py:9\n")
        code, out, _ = run("citazioni", doc, "--root", self.d)
        self.assertEqual(code, 1)
        self.assertIn("fuori intervallo", out)
        self.assertIn("1:6", out)

    def test_file_mancante_e_wiki(self):
        doc = self.w("d.md", "[^src: nope.md, sezione] e wiki/manca.md\n")
        code, out, _ = run("citazioni", doc, "--root", self.d)
        self.assertEqual(code, 1)
        self.assertEqual(out.count("file non trovato"), 2)

    def test_frontmatter_escluso(self):
        doc = self.w("d.md", "---\nsrc: wiki/manca.md\n---\ntesto\n")
        self.assertEqual(run("citazioni", doc, "--root", self.d)[0], 0)
        self.assertEqual(run("citazioni", doc, "--root", self.d, "--con-frontmatter")[0], 1)

    def test_ref_git(self):
        import subprocess
        repo = os.path.join(self.d, "code_repos", "r")
        os.makedirs(repo)
        git = ["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
        with open(os.path.join(repo, "f.js"), "w") as fh:
            fh.write("a\nb\n")
        subprocess.run(git + ["add", "f.js"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "m"], check=True)
        doc = self.w("d.md", "code_repos/r/f.js:2 e code_repos/r/f.js:3\n")
        code, out, _ = run("citazioni", doc, "--root", self.d, "--ref", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual(out.count("fuori intervallo"), 1)


class Verbatim(Base):
    SRC = "# T\n\n### A — uno\nriga a\n\n### B — due\nriga b\n\n## Fine\nx\n"

    def test_blocchi_identici(self):
        src = self.w("s.md", self.SRC)
        doc = self.w("d.md", "intro\n\n### B — due\nriga b\n\n### A — uno\nriga a\n")
        code, out, _ = run("verbatim", doc, "--fonte", src, "--blocchi", "### A —,### B —")
        self.assertEqual(code, 0, out)

    def test_blocco_diverso(self):
        src = self.w("s.md", self.SRC)
        doc = self.w("d.md", "### A — uno\nriga A\n")
        code, out, _ = run("verbatim", doc, "--fonte", src, "--blocchi", "### A —")
        self.assertEqual(code, 1)
        self.assertIn("diverso", out)

    def test_righe_vuote(self):
        src = self.w("s.md", self.SRC)
        doc = self.w("d.md", "### A — uno\n\n\nriga a\n")
        self.assertEqual(run("verbatim", doc, "--fonte", src, "--blocchi", "### A —")[0], 0)
        self.assertEqual(run("verbatim", doc, "--fonte", src, "--blocchi", "### A —", "--esatto")[0], 1)

    def test_titolo_in_grassetto_nella_fonte(self):
        src = self.w("s.md", "**A — uno**\nriga a\n\n**B — due**\nriga b\n")
        doc = self.w("d.md", "### A — uno\nriga a\n\n### B — due\nriga X\n")
        code, out, _ = run("verbatim", doc, "--fonte", src, "--blocchi", "A —,B —")
        self.assertEqual(code, 1)
        self.assertEqual(out.count("blocco diverso"), 1)
        self.assertIn("B —", out)

    def test_stesso_codice_in_piu_titoli(self):
        src = self.w("s.md", "**C-1 — Breve · In parte**\nuno\n\n**C-1 — Esteso · Da definire**\ndue\n")
        doc = self.w("d.md", "### C-1 — Esteso · Da definire\ndue\n")
        self.assertEqual(run("verbatim", doc, "--fonte", src, "--blocchi", "C-1 —")[0], 0)
        bad = self.w("b.md", "### C-1 — Altro\ndue\n")
        code, out, _ = run("verbatim", bad, "--fonte", src, "--blocchi", "C-1 —")
        self.assertEqual(code, 1)
        self.assertIn("titolo diverso", out)
        self.assertIn("Breve", out)
        self.assertIn("Esteso", out)
        dup = self.w("s2.md", "**C-1 — X**\ndue\n\n**C-1 — X**\ndue\n")
        same = self.w("d2.md", "### C-1 — X\ndue\n")
        code, out, _ = run("verbatim", same, "--fonte", dup, "--blocchi", "C-1 —")
        self.assertEqual(code, 0)
        self.assertIn("avviso", out)

    def test_separatore_finale(self):
        src = self.w("s.md", "### A — uno\nriga a\n")
        doc = self.w("d.md", "### A — uno\nriga a\n\n---\n\nnota finale\n")
        self.assertEqual(run("verbatim", doc, "--fonte", src, "--blocchi", "A —")[0], 0)

    def test_blocco_assente(self):
        src = self.w("s.md", self.SRC)
        doc = self.w("d.md", "### A — uno\nriga a\n")
        code, out, _ = run("verbatim", doc, "--fonte", src, "--blocchi", "### Z —")
        self.assertEqual(code, 1)

    def test_marcati(self):
        src = self.w("s.md", "uno\ndue\ntre\n")
        ok = self.w("ok.md", "<!-- verbatim -->\ndue\ntre\n<!-- /verbatim -->\n")
        ko = self.w("ko.md", "<!-- verbatim -->\ndue\nQUATTRO\n<!-- /verbatim -->\n")
        self.assertEqual(run("verbatim", ok, "--fonte", src, "--marcati")[0], 0)
        self.assertEqual(run("verbatim", ko, "--fonte", src, "--marcati")[0], 1)

    def test_stringhe(self):
        src = self.w("s.md", "Mario Rossi entro le 18:30\n")
        doc = self.w("d.md", "Mario Rossi, 18:30\n")
        self.assertEqual(run("verbatim", doc, "--fonte", src, "--stringhe", "Mario Rossi|18:30")[0], 0)
        code, out, _ = run("verbatim", doc, "--fonte", src, "--stringhe", "Mario Rossi|18:45")
        self.assertEqual(code, 1)
        self.assertIn("18:45", out)

    def test_stringhe_file(self):
        src = self.w("s.md", "alfa beta\n")
        doc = self.w("d.md", "alfa\n")
        sf = self.w("l.txt", "alfa\nbeta\n")
        code, out, _ = run("verbatim", doc, "--fonte", src, "--stringhe-file", sf)
        self.assertEqual(code, 1)
        self.assertIn("beta", out)

    def test_senza_criteri_e_fonte_illeggibile(self):
        doc = self.w("d.md", "x\n")
        src = self.w("s.md", "x\n")
        self.assertEqual(run("verbatim", doc, "--fonte", src)[0], 2)
        self.assertEqual(run("verbatim", doc, "--fonte", os.path.join(self.d, "no.md"), "--stringhe", "x")[0], 2)


class Codici(Base):
    def test_pulito(self):
        doc = self.w("d.md", "---\nsrc: XX-TSK-1\n---\nTesto normale, Dr.2 e task 249 non sono codici.\n")
        self.assertEqual(run("codici", doc)[0], 0)

    def test_pattern(self):
        doc = self.w("d.md", "ok\nvedi XX-TSK-12, TSK-7, ADR-007, R.12 e G-AB-033\n")
        code, out, _ = run("codici", doc)
        self.assertEqual(code, 1)
        for kind in ("id-kanban", "adr", "regola"):
            self.assertIn(kind, out)
        self.assertEqual(out.count("id-kanban"), 2)
        self.assertNotIn("G-AB-033", out)
        self.assertIn("2:6", out)

    def test_pattern_del_progetto(self):
        doc = self.w("d.md", "vedi G-AB-033 e Q-CD-001\n")
        code, out, _ = run("codici", doc, "--pattern", r"gap=\bG-[A-Z]+-\d{3}\b")
        self.assertEqual(code, 1)
        self.assertIn("gap: G-AB-033", out)
        self.assertNotIn("Q-CD-001", out)
        pf = self.w("p.txt", "# codici del progetto\ndomanda=\\bQ-[A-Z]+-\\d{3}\\b\n")
        code, out, _ = run("codici", doc, "--pattern-file", pf)
        self.assertIn("domanda: Q-CD-001", out)
        self.assertEqual(run("codici", doc, "--pattern", "senza-uguale")[0], 2)
        self.assertEqual(run("codici", doc, "--pattern", "x=(")[0], 2)

    def test_frontmatter_e_vietati(self):
        doc = self.w("d.md", "---\nsrc: XX-TSK-1\n---\nla alfa e il beta\n")
        self.assertEqual(run("codici", doc)[0], 0)
        code, out, _ = run("codici", doc, "--vietati", "alfa,beta")
        self.assertEqual(code, 1)
        self.assertEqual(out.count("vietato"), 2)
        self.assertEqual(run("codici", doc, "--con-frontmatter")[0], 1)


class Uso(Base):
    def test_errori_e_disclaimer(self):
        self.assertEqual(run()[0], 2)
        self.assertEqual(run("codici", os.path.join(self.d, "no.md"))[0], 2)
        doc = self.w("d.md", "x\n")
        code, out, _ = run("codici", doc)
        self.assertEqual(code, 0)
        self.assertIn("NON verifica che il contenuto sostenga", out)
        self.assertIn("NON verifica che il contenuto sostenga", vv.build_parser().format_help())


if __name__ == "__main__":
    unittest.main()
