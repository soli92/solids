#!/usr/bin/env python3
"""Rende la documentazione funzionale di un servizio (markdown) in HTML e Word.

Uso:
    python3 tools/docs/build_functional_docs.py <servizio> [--root DIR] [--out DIR]
    python3 tools/docs/build_functional_docs.py --tutti
    python3 tools/docs/build_functional_docs.py --file <documento.md> [--out DIR] [--template modello.docx]

Legge deliverables/doc-funzionale/<servizio>/*.md (cartella configurabile in
documentation.functional_docs.output_dir) e scrive accanto a ogni .md un .html
autocontenuto e, se python-docx e' installato, un .docx.

- Stato `bozza` nel frontmatter: banner "BOZZA - da revisionare prima della consegna"
  in testa all'HTML e nell'intestazione del Word.
- Le fonti (path `wiki/...md` nelle righe "Fonti:" e nella sezione "Fonti") diventano
  link al sito tecnico (ultima build in documentation.tech_site.output_dir) se la
  pagina HTML esiste, altrimenti restano testo.
- Prima di scrivere ogni file il testo passa dal controllo di redazione (redact.py):
  se ci sono finding non scrive nulla e termina con exit 2.

Con --file rende un markdown qualsiasi (anche fuori da deliverables/) in <nome>.html e <nome>.docx,
accanto al file oppure in --out. Il Word richiede python-docx: se manca, exit 1 con messaggio.
--template <docx> usa gli stili (Heading, List Bullet, Table Grid...) di un documento esistente come modello.
Formato Word di --file: titolo H1 in grassetto 22pt; ## -> Heading 1, ### -> Heading 2, #### -> Heading 3;
tabelle "Table Grid" con riga d'intestazione in grassetto; **grassetto** e `codice` inline (codice in Consolas
9,5pt); elenchi puntati con secondo livello; righe di continuazione unite alla voce.
Larghezze di colonna: un commento HTML su una riga propria, subito prima della tabella,
    <!-- col-widths: 8.5,8.5 -->
elenca le larghezze in cm (una per colonna). Senza commento le colonne restano di larghezza automatica;
se il numero di valori non coincide con le colonne il commento e' ignorato con un avviso.

Codici di uscita: 0 ok, 1 errore (servizio, file o python-docx mancanti), 2 redazione fallita.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import md_render  # noqa: E402
import redact  # noqa: E402

DEFAULT_OUTPUT_DIR = "deliverables/doc-funzionale"
DEFAULT_TECH_DIR = "deliverables/doc-tecnica"
BANNER_TEXT = "BOZZA — da revisionare prima della consegna"

_FALLBACK_CSS = """
:root{--bg:#fff;--fg:#1c1f23;--mut:#5b6470;--bd:#d9dde3;--bg2:#f4f6f8;--ac:#0b57d0;--code:#eef1f4;--warn:#9a5b00}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--fg:#e4e7eb;--mut:#9aa4b0;--bd:#2c323a;--bg2:#1c2025;--ac:#7fb0ff;--code:#22272d;--warn:#e0a54a}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,sans-serif}
main{max-width:62rem;margin:0 auto;padding:1.5rem 2rem 4rem}
table{border-collapse:collapse;width:100%}th,td{border:1px solid var(--bd);padding:.35rem .6rem;text-align:left}
"""

EXTRA_CSS = """
.layout{display:block}
.banner{border:2px solid var(--warn);color:var(--warn);background:var(--bg2);border-radius:6px;padding:.6rem .9rem;margin-bottom:1.2rem;font-weight:700}
.docmeta{color:var(--mut);font-size:.88rem;margin-bottom:1.2rem}
.docmeta div{margin:.1rem 0}
"""


# --------------------------------------------------------------------------- configurazione


def find_root(start: Optional[Path] = None) -> Path:
    p = (start or Path(__file__)).resolve()
    for cand in [p] + list(p.parents):
        if (cand / "factory.config.yaml").is_file():
            return cand
    raise SystemExit("factory.config.yaml non trovato risalendo da %s" % p)


def load_config(root: Path) -> dict:
    cfg = {"output_dir": DEFAULT_OUTPUT_DIR, "services": {}, "tech_dir": DEFAULT_TECH_DIR, "redaction": True,
           "enabled": True}
    path = root / "factory.config.yaml"
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return cfg
    doc = data.get("documentation") if isinstance(data, dict) else None
    if not isinstance(doc, dict):
        return cfg
    if doc.get("enabled") is False:
        cfg["enabled"] = False
    fd = doc.get("functional_docs")
    if isinstance(fd, dict):
        if fd.get("output_dir"):
            cfg["output_dir"] = str(fd["output_dir"])
        if isinstance(fd.get("services"), dict):
            cfg["services"] = fd["services"]
    ts = doc.get("tech_site")
    if isinstance(ts, dict) and ts.get("output_dir"):
        cfg["tech_dir"] = str(ts["output_dir"])
    red = doc.get("redaction")
    if isinstance(red, dict) and red.get("enabled") is False:
        cfg["redaction"] = False
    return cfg


def _css() -> str:
    try:
        import build_tech_site  # type: ignore

        return build_tech_site.CSS + EXTRA_CSS
    except Exception:
        return _FALLBACK_CSS + EXTRA_CSS


# --------------------------------------------------------------------------- fonti -> sito tecnico


def latest_tech_site(root: Path, tech_dir: str) -> Optional[Path]:
    base = root / tech_dir
    if not base.is_dir():
        return None
    dated = sorted(d for d in base.iterdir() if d.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", d.name))
    return dated[-1] if dated else None


_WIKI_REF = re.compile(r"`(wiki/[^`\s]+?\.md)`")


def link_sources(md: str, site: Optional[Path], from_dir: Path) -> str:
    """Nelle righe di fonti trasforma `wiki/x/y.md` in link al sito tecnico, se la pagina esiste."""
    if site is None:
        return md
    out: List[str] = []
    in_src_section = False
    in_fence = False
    for line in md.split("\n"):
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
        h = re.match(r"^#{1,6}\s+(.*)$", line)
        if h and not in_fence:
            in_src_section = bool(re.match(r"Font[ei]\b", h.group(1).strip(), re.I))
        if not in_fence and (in_src_section or re.match(r"^\s*(\*\*|_|\*)?Font[ei]\b", line)):
            def sub(m: "re.Match[str]") -> str:
                ref = m.group(1)
                target = site / (ref[len("wiki/"):-3] + ".html")
                if not target.is_file():
                    return m.group(0)
                href = os.path.relpath(str(target), str(from_dir)).replace(os.sep, "/")
                return "[`%s`](%s)" % (ref, href)

            line = _WIKI_REF.sub(sub, line)
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------- HTML


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def doc_title(fm: dict, body: str, fallback: str) -> str:
    return str(fm.get("title") or md_render.extract_title(body) or fallback)


def is_draft(fm: dict) -> bool:
    return str(fm.get("stato") or fm.get("status") or "").strip().lower() == "bozza"


def strip_sources(body: str) -> str:
    """Toglie le righe «Fonti:» / «Fonte:» e le sezioni «## Fonti…» / «### Fonte…»: le guide approvate per gli utenti
    finali non mostrano i path della wiki, che restano nel markdown per la revisione."""
    out, skip, skip_level = [], False, 0
    for line in body.splitlines():
        hs = re.match(r"^(#{2,3})\s+Font[ei]\b", line)
        if hs:
            skip, skip_level = True, len(hs.group(1))
            continue
        hh = re.match(r"^(#{1,6})\s", line)
        if skip and hh and len(hh.group(1)) <= skip_level:
            skip = False
        if skip or re.match(r"^\s*(\*\*|_|\*)?Font[ei]\b.*:", line):
            continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def for_audience(fm: dict, body: str) -> str:
    if str(fm.get("pubblico") or "").strip().lower() == "utente" and not is_draft(fm):
        return strip_sources(body)
    return body


def render_html(fm: dict, body: str, name: str, site: Optional[Path], from_dir: Path, today: str) -> str:
    title = doc_title(fm, body, name)
    body_html = md_render.render(link_sources(body, site, from_dir), lambda t: None)
    stato = str(fm.get("stato") or fm.get("status") or "")
    meta = []
    if stato:
        meta.append("<div>Stato: <strong>%s</strong></div>" % esc(stato))
    if fm.get("servizio"):
        meta.append("<div>Servizio: %s</div>" % esc(fm["servizio"]))
    if fm.get("pubblico"):
        meta.append("<div>Pubblico: %s</div>" % esc(fm["pubblico"]))
    meta.append("<div>Data: %s</div>" % esc(fm.get("aggiornata") or fm.get("data") or today))
    if fm.get("approvata_da"):
        meta.append("<div>Approvata da %s il %s</div>" % (esc(fm["approvata_da"]), esc(fm.get("approvata_il", ""))))
    banner = '<div class="banner" role="note">%s</div>\n' % esc(BANNER_TEXT) if is_draft(fm) else ""
    has_h1 = body_html.lstrip().startswith("<h1")
    h1 = "" if has_h1 else "<h1>%s</h1>\n" % esc(title)
    return (
        '<!DOCTYPE html>\n<html lang="it">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<div class=\"layout\">\n<main>\n"
        "%s%s<div class=\"docmeta\">%s</div>\n%s\n</main>\n</div>\n</body>\n</html>\n"
        % (esc(title), _css(), banner, h1, "".join(meta), body_html)
    )


# --------------------------------------------------------------------------- Word

_INLINE_STRIP = [
    (re.compile(r"\[\^[^\]]*\]"), ""),
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\(([^)]*)\)"), r"\1"),
    (re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]"), lambda m: m.group(2) or m.group(1)),
    (re.compile(r"(\*\*|__)(.+?)\1"), r"\2"),
    (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])"), r"\1"),
    (re.compile(r"`([^`]*)`"), r"\1"),
]


def _plain(s: str) -> str:
    for rx, rep in _INLINE_STRIP:
        s = rx.sub(rep, s)
    return s.strip()


def _split_row(line: str) -> List[str]:
    # stesso parser di celle del render HTML: «\|» escapato, pipe dentro il codice, riga senza «|» iniziale
    return [_plain(c) for c in md_render._split_row(line)]


def write_docx(fm: dict, body: str, name: str, dest: Path, today: str) -> bool:
    try:
        import docx  # type: ignore
    except ImportError:
        print("python-docx non installato: Word saltato per %s" % name, file=sys.stderr)
        return False
    title = doc_title(fm, body, name)
    d = docx.Document()
    stato = str(fm.get("stato") or fm.get("status") or "")
    head = "Stato: %s — %s" % (stato or "n/d", fm.get("aggiornata") or fm.get("data") or today)
    if is_draft(fm):
        head += " — " + BANNER_TEXT
    section = d.sections[0]
    section.header.paragraphs[0].text = head
    lines = body.replace("\r\n", "\n").split("\n")
    i = 0
    in_fence = False
    para: List[str] = []
    seen_h1 = False

    def flush() -> None:
        if para:
            d.add_paragraph(_plain(" ".join(para)))
            para.clear()

    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*(```|~~~)", line):
            flush()
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            d.add_paragraph(line)
            i += 1
            continue
        h = re.match(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if h:
            flush()
            lvl = len(h.group(1))
            if lvl == 1:
                seen_h1 = True
            d.add_heading(_plain(h.group(2)), level=min(lvl, 4))
            i += 1
            continue
        if "|" in line and i + 1 < len(lines) and md_render._TABLE_SEP.match(lines[i + 1]) and "-" in lines[i + 1]:
            flush()
            rows = [_split_row(line)]
            i += 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                rows.append(_split_row(lines[i]))
                i += 1
            ncol = max(len(r) for r in rows)
            t = d.add_table(rows=len(rows), cols=ncol)
            try:
                t.style = "Table Grid"
            except Exception:
                pass
            for ri, r in enumerate(rows):
                for ci in range(ncol):
                    t.cell(ri, ci).text = r[ci] if ci < len(r) else ""
            continue
        it = re.match(r"^( *)([-*+]|\d{1,9}[.)])\s+(.*)$", line)
        if it:
            flush()
            style = "List Number" if it.group(2)[0].isdigit() else "List Bullet"
            d.add_paragraph(_plain(it.group(3)), style=style)
            i += 1
            continue
        if not line.strip():
            flush()
        elif re.match(r"^ {0,3}>", line):
            flush()
            d.add_paragraph(_plain(re.sub(r"^ {0,3}>\s?", "", line)))
        else:
            para.append(line.strip())
        i += 1
    flush()
    d.core_properties.title = title
    d.save(str(dest))
    return True


# --------------------------------------------------------------------------- Word da file (--file)

_RUNS = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|(?<![*\w])\*[^*\s](?:[^*]*[^*\s])?\*(?![*\w]))")
_WIDTHS = re.compile(r"^\s*<!--\s*col-widths:\s*([0-9.,\s]+?)\s*-->\s*$")
_COMMENT = re.compile(r"^\s*<!--.*-->\s*$")


def _add_runs(par, text: str, bold: bool = False) -> None:
    from docx.shared import Pt  # type: ignore

    text = re.sub(r"\[\^[^\]]*\]", "", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]*)\)", r"\1", text)
    for part in _RUNS.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            _add_runs(par, part[2:-2], bold=True)
        elif part.startswith("*") and part.endswith("*") and not part.startswith("**") and len(part) > 2:
            # corsivo *testo*
            r = par.add_run(part[1:-1])
            r.italic = True
            r.bold = True if bold else None
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            r = par.add_run(part[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9.5)
            r.bold = True if bold else None
        else:
            r = par.add_run(part)
            r.bold = True if bold else None


def _parse_blocks(lines: List[str]) -> list:
    """Raggruppa le righe in blocchi: ('h', livello, testo), ('table', righe, larghezze), ('bullet', livello, testo),
    ('num', n, testo), ('p', testo)."""
    blocks: list = []
    i = 0
    widths: Optional[List[float]] = None

    def is_start(ln: str) -> bool:
        return bool(ln.startswith("#") or ln.lstrip().startswith("|") or re.match(r"^\s*[-*+] ", ln)
                    or re.match(r"^\d+[.)] ", ln) or ln.strip() in ("", "---") or _COMMENT.match(ln)
                    or re.match(r"^\s*(```|~~~)", ln))

    while i < len(lines):
        ln = lines[i]
        w = _WIDTHS.match(ln)
        if w:
            widths = [float(x) for x in re.findall(r"[0-9]+(?:\.[0-9]+)?", w.group(1).replace(",", " "))]
            i += 1
            continue
        if ln.strip() in ("", "---") or _COMMENT.match(ln):
            i += 1
            continue
        if re.match(r"^\s*(```|~~~)", ln):
            i += 1
            code = []
            while i < len(lines) and not re.match(r"^\s*(```|~~~)", lines[i]):
                code.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", code))
            continue
        if ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i])
                i += 1
            blocks.append(("table", rows, widths))
            widths = None
            continue
        m = re.match(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$", ln)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2)))
            i += 1
            continue
        b = re.match(r"^(\s*)[-*+] (.*)", ln)
        n = re.match(r"^(\d+)[.)] (.*)", ln)
        if b:
            kind: tuple = ("bullet", len(b.group(1)) // 2)
            text = b.group(2)
        elif n:
            kind = ("num", n.group(1))
            text = n.group(2)
        else:
            kind = ("p",)
            text = ln.strip()
        i += 1
        while i < len(lines) and not is_start(lines[i]):
            text += " " + lines[i].strip()
            i += 1
        blocks.append(kind + (text,))
    return blocks


def _apply_widths(t, widths: List[float], ncol: int, name: str) -> None:
    from docx.shared import Cm  # type: ignore

    if len(widths) != ncol:
        print("%s: col-widths ha %d valori ma la tabella ha %d colonne: larghezze ignorate"
              % (name, len(widths), ncol), file=sys.stderr)
        return
    t.autofit = False
    for ci, wcm in enumerate(widths):
        t.columns[ci].width = Cm(wcm)
        for cell in t.columns[ci].cells:
            cell.width = Cm(wcm)


def write_docx_file(fm: dict, body: str, name: str, dest: Path, template: Optional[Path] = None) -> None:
    """Word di un markdown qualsiasi (modalita' --file). Richiede python-docx (ImportError se manca)."""
    import docx  # type: ignore
    from docx.shared import Pt, Cm  # type: ignore

    d = docx.Document(str(template)) if template else docx.Document()
    if template:
        bodyel = d.element.body
        for el in list(bodyel):
            if not el.tag.endswith("sectPr"):
                bodyel.remove(el)
    title = doc_title(fm, body, name)
    title_done = False
    for blk in _parse_blocks(body.replace("\r\n", "\n").split("\n")):
        kind = blk[0]
        if kind == "h":
            lvl, text = blk[1], blk[2]
            if lvl == 1 and not title_done:
                p = d.add_paragraph()
                r = p.add_run(_plain(text))
                r.bold = True
                r.font.size = Pt(22)
                title_done = True
            else:
                p = d.add_paragraph(style={2: "Heading 1", 3: "Heading 2"}.get(lvl, "Heading 3"))
                _add_runs(p, text.replace("`", ""))
        elif kind == "table":
            rows = [md_render._split_row(r) for r in blk[1]]
            rows = [r for r in rows if not (r and all(re.match(r"^:?-{1,}:?$", c.strip()) for c in r if c.strip()) and any(c.strip() for c in r))]
            ncol = max(len(r) for r in rows)
            t = d.add_table(rows=len(rows), cols=ncol)
            try:
                t.style = "Table Grid"
            except Exception:
                pass
            for ri, row in enumerate(rows):
                for ci in range(ncol):
                    _add_runs(t.cell(ri, ci).paragraphs[0], row[ci] if ci < len(row) else "", bold=(ri == 0))
            if blk[2]:
                _apply_widths(t, blk[2], ncol, name)
        elif kind == "bullet":
            p = d.add_paragraph(style="List Bullet 2" if blk[1] >= 1 else "List Bullet")
            _add_runs(p, blk[2])
        elif kind == "num":
            p = d.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.63)
            p.paragraph_format.first_line_indent = Cm(-0.63)
            _add_runs(p, blk[1] + ". " + blk[2])
        elif kind == "code":
            for cl in blk[1]:
                d.add_paragraph(cl)
        else:
            p = d.add_paragraph()
            _add_runs(p, blk[1])
    d.core_properties.title = title
    d.save(str(dest))


def build_file(root: Path, cfg: dict, src: Path, out_dir: Optional[Path] = None,
               template: Optional[Path] = None, today: Optional[str] = None) -> int:
    today = today or dt.date.today().isoformat()
    if not src.is_file():
        print("File non trovato: %s" % src, file=sys.stderr)
        return 1
    if template is not None and not template.is_file():
        print("Template non trovato: %s" % template, file=sys.stderr)
        return 1
    try:
        import docx  # type: ignore  # noqa: F401
    except ImportError:
        print("python-docx non installato: impossibile produrre il Word di %s "
              "(pip install python-docx)" % src.name, file=sys.stderr)
        return 1
    text = src.read_text(encoding="utf-8")
    fm, body = md_render.parse_frontmatter(text)
    h = render_html(fm, body, src.stem, None, src.parent, today)
    if cfg.get("redaction", True):
        problems = []
        for label, content in (("%s (md)" % src.name, text), ("%s (html)" % src.name, h)):
            try:
                redact.assert_clean(content, label)
            except redact.RedactionError as e:
                problems.append(str(e))
        if problems:
            print("Redazione fallita, nessun file scritto:", file=sys.stderr)
            for p in problems:
                print("  " + p, file=sys.stderr)
            return 2
    dest_dir = out_dir if out_dir is not None else src.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / (src.stem + ".html")).write_text(h, encoding="utf-8")
    write_docx_file(fm, body, src.stem, dest_dir / (src.stem + ".docx"), template)
    print("%s: html + docx in %s" % (src.name, dest_dir))
    return 0


# --------------------------------------------------------------------------- build


def build_service(root: Path, cfg: dict, service: str, out_dir: Optional[Path] = None,
                  today: Optional[str] = None) -> int:
    today = today or dt.date.today().isoformat()
    base = out_dir if out_dir is not None else root / cfg["output_dir"]
    sdir = base / service
    if not sdir.is_dir():
        print("Cartella non trovata: %s" % sdir, file=sys.stderr)
        return 1
    mds = sorted(sdir.glob("*.md"))
    if not mds:
        print("Nessun .md in %s" % sdir, file=sys.stderr)
        return 1
    site = latest_tech_site(root, cfg["tech_dir"])
    staged: List[Tuple[Path, str, dict, str]] = []
    problems = []
    for md in mds:
        text = md.read_text(encoding="utf-8")
        fm, body = md_render.parse_frontmatter(text)
        body = for_audience(fm, body)
        h = render_html(fm, body, md.stem, site, sdir, today)
        if cfg.get("redaction", True):
            for label, content in (("%s (md)" % md.name, text), ("%s (html)" % md.name, h)):
                try:
                    redact.assert_clean(content, label)
                except redact.RedactionError as e:
                    problems.append(str(e))
        staged.append((md, h, fm, body))
    if problems:
        print("Redazione fallita, nessun file scritto:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 2
    for md, h, fm, body in staged:
        md.with_suffix(".html").write_text(h, encoding="utf-8")
        ok = write_docx(fm, body, md.stem, md.with_suffix(".docx"), today)
        print("%s: html%s" % (md.relative_to(root) if root in md.parents else md, " + docx" if ok else ""))
    return 0


def list_services(root: Path, cfg: dict) -> List[str]:
    base = root / cfg["output_dir"]
    if not base.is_dir():
        return []
    return sorted(d.name for d in base.iterdir() if d.is_dir() and any(d.glob("*.md")))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Rende la documentazione funzionale (HTML e Word).")
    ap.add_argument("servizio", nargs="?", help="chiave del servizio (cartella in output_dir)")
    ap.add_argument("--tutti", action="store_true", help="rende tutti i servizi presenti")
    ap.add_argument("--root", help="radice factory (default: ricavata da factory.config.yaml)")
    ap.add_argument("--out", help="cartella base dei documenti (default da configurazione); con --file, "
                                  "cartella di destinazione (default: accanto al file)")
    ap.add_argument("--file", help="rende un markdown qualsiasi in .html e .docx (vedi larghezze colonne in testa al file)")
    ap.add_argument("--template", help="solo con --file: docx da cui prendere gli stili")
    args = ap.parse_args(argv)
    if args.template and not args.file:
        ap.error("--template si usa solo con --file")
    root = Path(args.root).resolve() if args.root else find_root()
    cfg = load_config(root)
    if args.file:
        return build_file(root, cfg, Path(args.file).resolve(), Path(args.out).resolve() if args.out else None,
                          Path(args.template).resolve() if args.template else None)
    if not cfg["enabled"]:
        print("documentazione disattivata (documentation.enabled: false in factory.config.yaml): "
              "nessun file generato")
        return 0
    out = Path(args.out).resolve() if args.out else None
    if args.tutti:
        services = list_services(root, cfg) if out is None else sorted(
            d.name for d in out.iterdir() if d.is_dir() and any(d.glob("*.md")))
    elif args.servizio:
        services = [args.servizio]
    else:
        ap.error("indicare un servizio oppure --tutti")
        return 1
    if not services:
        print("Nessun servizio da rendere.", file=sys.stderr)
        return 1
    rc = 0
    for s in services:
        r = build_service(root, cfg, s, out)
        rc = max(rc, r)
    return rc


if __name__ == "__main__":
    sys.exit(main())
