#!/usr/bin/env python3
"""Genera il sito statico di documentazione tecnica a partire dalla wiki.

Uso:
    python3 tools/docs/build_tech_site.py [--out DIR] [--sections a,b] [--dry-run]
                                          [--wiki DIR] [--root DIR]

Output: <output_dir>/<YYYY-MM-DD>/index.html, una pagina HTML per pagina wiki (stesso
percorso, estensione .html), search-index.js. Le pagine sono autocontenute (CSS inline,
nessuna risorsa esterna) e si aprono da disco.

Prima di scrivere ogni pagina passa dal controllo di redazione (redact.py). Se anche una
sola pagina ha finding il build si ferma con exit 2 e non scrive nulla: l'output viene
costruito in una cartella temporanea e rinominato solo a fine lavoro.

Codici di uscita: 0 ok, 1 errore generico, 2 redazione fallita.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import posixpath
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import md_render  # noqa: E402
import redact  # noqa: E402

# Cartelle inesistenti si ignorano: l'elenco copre sia la wiki del meta-framework sia quella delle derivate.
DEFAULT_INCLUDE = [
    "getting-started", "guides", "onboarding", "tech", "be-services", "design-system",
    "decisions", "runbooks", "user-flows", "concepts", "entities", "incidents",
    "syntheses", "synthesis",
]
DEFAULT_EXCLUDE = ["sources", "sessions", "lint", "gaps"]
DEFAULT_OUTPUT_DIR = "deliverables/doc-tecnica"

SECTION_LABELS = {
    "onboarding": "Onboarding", "getting-started": "Per iniziare", "guides": "Guide",
    "tech": "Tecnologie", "be-services": "Servizi backend",
    "design-system": "Design system", "decisions": "Decisioni", "runbooks": "Runbook",
    "user-flows": "Flussi utente", "concepts": "Concetti", "entities": "Entità",
    "incidents": "Incidenti", "syntheses": "Sintesi", "synthesis": "Sintesi (archivio)",
}


def section_label(sec: str) -> str:
    """Etichetta di una sezione: dizionario, altrimenti il nome cartella (trattini -> spazi, maiuscola iniziale)."""
    return SECTION_LABELS.get(sec) or sec.replace("-", " ").title()


# --------------------------------------------------------------------------- configurazione


def find_root(start: Optional[Path] = None) -> Path:
    p = (start or Path(__file__)).resolve()
    for cand in [p] + list(p.parents):
        if (cand / "factory.config.yaml").is_file():
            return cand
    raise SystemExit("factory.config.yaml non trovato risalendo da %s" % p)


def load_tech_config(root: Path) -> dict:
    cfg = {
        "output_dir": DEFAULT_OUTPUT_DIR,
        "include_sections": list(DEFAULT_INCLUDE),
        "exclude_sections": list(DEFAULT_EXCLUDE),
        "redaction": True,
        "enabled": True,
    }
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
    ts = doc.get("tech_site") or {}
    for k in ("output_dir", "include_sections", "exclude_sections"):
        if ts.get(k):
            cfg[k] = ts[k]
    red = doc.get("redaction")
    if isinstance(red, dict) and red.get("enabled") is False:
        cfg["redaction"] = False
    return cfg


# --------------------------------------------------------------------------- modello


class Page:
    def __init__(self, section: str, rel: str, path: Path, text: str):
        self.section = section
        self.rel = rel  # path relativo alla wiki, senza estensione, posix (es. decisions/x)
        self.path = path
        self.text = text
        self.fm, self.body = md_render.parse_frontmatter(text)
        self.title = str(self.fm.get("title") or self.fm.get("topic") or md_render.extract_title(self.body) or Path(rel).name)
        self.status = str(self.fm.get("status") or self.fm.get("stato") or "")

    @property
    def out_rel(self) -> str:
        return self.rel + ".html"

    @property
    def sources(self) -> List[str]:
        out: List[str] = []
        for key in ("source", "source_file", "sources"):
            v = self.fm.get(key)
            if v is None or v == "":
                continue
            if isinstance(v, (list, tuple)):
                out.extend(str(x) for x in v if x)
            else:
                out.append(str(v))
        return out


def collect_pages(wiki: Path, sections: List[str]) -> List[Page]:
    pages: List[Page] = []
    for sec in sections:
        base = wiki / sec
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(wiki).with_suffix("").as_posix()
            pages.append(Page(sec, rel, p, p.read_text(encoding="utf-8")))
    return pages


class Resolver:
    """Risolve wikilink e link .md verso le sole pagine pubblicate."""

    def __init__(self, pages: List[Page]):
        self.by_rel = {p.rel: p for p in pages}
        self.by_name: Dict[str, List[Page]] = {}
        self.by_id: Dict[str, List[Page]] = {}
        for p in pages:
            self.by_name.setdefault(posixpath.basename(p.rel), []).append(p)
            pid = p.fm.get("id")
            if pid:
                self.by_id.setdefault(str(pid), []).append(p)

    def find(self, target: str, cur: Page) -> Optional[Page]:
        t = target.strip().replace("\\", "/")
        if t.endswith(".md"):
            t = t[:-3]
        while t.startswith("./"):
            t = t[2:]
        if t.startswith("wiki/"):
            t = t[5:]
        if not t:
            return None
        for cand in (t, posixpath.normpath(posixpath.join(posixpath.dirname(cur.rel), t))):
            if cand in self.by_rel:
                return self.by_rel[cand]
        name = posixpath.basename(t)
        pool = self.by_name.get(name, [])
        if "/" in t:
            pool = [p for p in pool if p.rel.endswith("/" + t) or p.rel == t]
        if not pool and "/" not in t:
            pool = self.by_id.get(t, [])
        if not pool:
            return None
        same = [p for p in pool if p.section == cur.section]
        return (same or sorted(pool, key=lambda p: p.rel))[0]

    def href(self, target: str, cur: Page) -> Optional[str]:
        page = self.find(target, cur)
        if page is None:
            return None
        return rel_href(cur.out_rel, page.out_rel)


def rel_href(from_file: str, to_file: str) -> str:
    return posixpath.relpath(to_file, posixpath.dirname(from_file) or ".")


# --------------------------------------------------------------------------- HTML

CSS = """
:root{--bg:#fff;--fg:#1c1f23;--mut:#5b6470;--bd:#d9dde3;--bg2:#f4f6f8;--ac:#0b57d0;--code:#eef1f4;--warn:#9a5b00}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--fg:#e4e7eb;--mut:#9aa4b0;--bd:#2c323a;--bg2:#1c2025;--ac:#7fb0ff;--code:#22272d;--warn:#e0a54a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--ac)}
.layout{display:flex;min-height:100vh}
nav.side{width:290px;flex:none;background:var(--bg2);border-right:1px solid var(--bd);padding:1rem;font-size:.9rem;overflow-y:auto;max-height:100vh;position:sticky;top:0}
nav.side h2{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin:1rem 0 .3rem}
nav.side ul{list-style:none;margin:0;padding:0}
nav.side li{margin:.1rem 0}
nav.side li.cur>a{font-weight:700;color:var(--fg)}
nav.side ul ul{padding-left:.9rem}
nav.side .grp{color:var(--mut);margin-top:.4rem}
main{flex:1;min-width:0;max-width:62rem;padding:1.5rem 2rem 4rem}
.crumbs{font-size:.85rem;color:var(--mut);margin-bottom:1rem}
.meta{border:1px solid var(--bd);background:var(--bg2);border-radius:6px;padding:.6rem .9rem;margin-bottom:1.5rem;font-size:.88rem}
.meta div{margin:.15rem 0}
.badge{display:inline-block;padding:.05rem .55rem;border-radius:99px;font-size:.78rem;font-weight:600;border:1px solid var(--bd)}
.st-draft{color:var(--warn);border-color:var(--warn)}
.st-review{color:var(--ac);border-color:var(--ac)}
.st-approved{color:#1a7f37;border-color:#1a7f37}
h1,h2,h3,h4{line-height:1.25}
h2{border-bottom:1px solid var(--bd);padding-bottom:.2rem;margin-top:2rem}
code{background:var(--code);padding:.1rem .3rem;border-radius:3px;font:.88em ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:var(--code);padding:.8rem 1rem;border-radius:6px;overflow-x:auto}
pre code{background:none;padding:0}
blockquote{margin:1rem 0;padding:.1rem 1rem;border-left:4px solid var(--bd);color:var(--mut)}
.table-wrap{overflow-x:auto;margin:1rem 0}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid var(--bd);padding:.35rem .6rem;vertical-align:top;text-align:left}
th{background:var(--bg2)}
img{max-width:100%}
.wl-missing{border-bottom:1px dotted var(--mut);color:var(--mut);cursor:help}
.cite{display:block;font-size:.78rem;color:var(--mut)}
ul.task-list,li.task{list-style:none}
ul.task-list{padding-left:1.2rem}
.back{margin-top:3rem;font-size:.9rem}
#q{width:100%;padding:.55rem .8rem;font-size:1rem;border:1px solid var(--bd);border-radius:6px;background:var(--bg);color:var(--fg)}
#results{list-style:none;padding:0}
#results li{padding:.5rem 0;border-bottom:1px solid var(--bd)}
#results .sec{color:var(--mut);font-size:.8rem}
#results .ex{color:var(--mut);font-size:.88rem}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:.8rem;padding:0;list-style:none}
.cards li{border:1px solid var(--bd);border-radius:6px;padding:.6rem .8rem;background:var(--bg2)}
.cards .n{font-size:1.5rem;font-weight:700}
details{margin:.6rem 0}
summary{cursor:pointer;font-weight:600}
@media print{nav.side,#q,.back{display:none}main{max-width:none;padding:0}.layout{display:block}}
@media (max-width:760px){.layout{display:block}nav.side{width:auto;position:static;max-height:none}}
"""


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def badge(status: str) -> str:
    if not status:
        return ""
    cls = "st-" + "".join(c for c in status.lower() if c.isalnum())
    return '<span class="badge %s">%s</span>' % (cls, esc(status))


def shell(title: str, body: str, sidebar: str, here: str, extra_head: str = "", extra_end: str = "") -> str:
    return (
        '<!DOCTYPE html>\n<html lang="it">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>%s</title>\n<style>%s</style>\n%s</head>\n<body>\n"
        '<div class="layout">\n%s\n<main>\n%s\n</main>\n</div>\n%s</body>\n</html>\n'
        % (esc(title), CSS, extra_head, sidebar, body, extra_end)
    )


def sidebar_html(cur: Optional[Page], pages_by_section: Dict[str, List[Page]], sections: List[str], here: str) -> str:
    home = rel_href(here, "index.html")
    out = ['<nav class="side">', '<a href="%s"><strong>Indice</strong></a>' % esc(home), "<h2>Sezioni</h2>", "<ul>"]
    for sec in sections:
        if sec not in pages_by_section:
            continue
        n = len(pages_by_section[sec])
        cls = ' class="cur"' if cur is not None and cur.section == sec else ""
        out.append('<li%s><a href="%s#sec-%s">%s</a> <span class="badge">%d</span></li>'
                   % (cls, esc(home), esc(sec), esc(section_label(sec)), n))
    out.append("</ul>")
    if cur is not None:
        out.append("<h2>%s</h2>" % esc(section_label(cur.section)))
        out.append(tree_html(pages_by_section[cur.section], cur, here))
    out.append("</nav>")
    return "\n".join(out)


def tree_html(pages: List[Page], cur: Page, here: str) -> str:
    """Albero di cartelle -> pagine della sezione corrente."""
    tree: dict = {}
    for p in pages:
        parts = p.rel.split("/")[1:]
        node = tree
        for d in parts[:-1]:
            node = node.setdefault(d + "/", {})
        node.setdefault("", []).append(p)

    def walk(node: dict) -> str:
        items = []
        for p in sorted(node.get("", []), key=lambda x: x.rel):
            cls = ' class="cur"' if p is cur else ""
            items.append('<li%s><a href="%s">%s</a></li>' % (cls, esc(rel_href(here, p.out_rel)), esc(p.title)))
        for k in sorted(x for x in node if x):
            items.append('<li><div class="grp">%s</div>%s</li>' % (esc(k.rstrip("/")), walk(node[k])))
        return "<ul>%s</ul>" % "".join(items)

    return walk(tree)


def render_page(page: Page, resolver: Resolver, pages_by_section, sections, root_note: str) -> str:
    here = page.out_rel
    html_body = md_render.render(page.body, lambda t: resolver.href(t, page))
    home = rel_href(here, "index.html")
    parts = page.rel.split("/")
    crumbs = ['<a href="%s">Indice</a>' % esc(home),
              '<a href="%s#sec-%s">%s</a>' % (esc(home), esc(page.section), esc(section_label(page.section)))]
    crumbs += [esc(d) for d in parts[1:-1]]
    crumbs.append(esc(page.title))
    meta = []
    if page.status:
        meta.append("<div>Stato: %s</div>" % badge(page.status))
    srcs = page.sources
    if srcs:
        meta.append("<div>Fonte: %s</div>" % "; ".join("<code>%s</code>" % esc(s) for s in srcs))
    for key, label in (("updated", "Aggiornata"), ("type", "Tipo")):
        if page.fm.get(key):
            meta.append("<div>%s: %s</div>" % (label, esc(page.fm[key])))
    meta.append("<div>Pagina wiki: <code>wiki/%s.md</code></div>" % esc(page.rel))
    has_h1 = html_body.lstrip().startswith("<h1")
    h1 = "" if has_h1 else "<h1>%s</h1>\n" % esc(page.title)
    body = ('<div class="crumbs">%s</div>\n<div class="meta">%s</div>\n%s%s\n'
            '<p class="back"><a href="%s">&larr; Torna all\'indice</a></p>'
            % (" &rsaquo; ".join(crumbs), "".join(meta), h1, html_body, esc(home)))
    return shell(page.title + " - Documentazione tecnica", body,
                 sidebar_html(page, pages_by_section, sections, here), here)


SEARCH_JS = """
(function(){
  var data=window.SEARCH_INDEX||[],q=document.getElementById('q'),res=document.getElementById('results');
  function norm(s){return (s||'').toLowerCase();}
  function run(){
    var terms=norm(q.value).split(/\\s+/).filter(Boolean);res.innerHTML='';
    if(!terms.length){return;}
    var hits=[];
    data.forEach(function(d){
      var t=norm(d.t),b=norm(d.t+' '+d.p+' '+d.x),score=0;
      for(var i=0;i<terms.length;i++){
        if(b.indexOf(terms[i])<0){return;}
        score+=t.indexOf(terms[i])>=0?10:1;
      }
      hits.push([score,d]);
    });
    hits.sort(function(a,b){return b[0]-a[0];});
    hits.slice(0,50).forEach(function(h){
      var d=h[1],li=document.createElement('li'),a=document.createElement('a');
      a.href=d.p.replace(/\\.md$/,'')+'.html';a.textContent=d.t;
      var s=document.createElement('div');s.className='sec';s.textContent=d.s+' \\u00b7 '+d.p;
      var e=document.createElement('div');e.className='ex';e.textContent=d.x;
      li.appendChild(a);li.appendChild(s);li.appendChild(e);res.appendChild(li);
    });
    if(!hits.length){res.innerHTML='<li>Nessun risultato.</li>';}
  }
  q.addEventListener('input',run);
})();
"""


def render_index(pages_by_section, sections, stats: dict) -> str:
    here = "index.html"
    cards = []
    for sec in sections:
        if sec in pages_by_section:
            cards.append('<li><a href="#sec-%s">%s</a><div class="n">%d</div></li>'
                         % (esc(sec), esc(section_label(sec)), len(pages_by_section[sec])))
    info = ["Generata il %s" % esc(stats["date"])]
    if stats.get("commit"):
        info.append("commit factory <code>%s</code>" % esc(stats["commit"]))
    info.append("%d pagine in %d sezioni" % (stats["pages"], len(cards)))
    status_counts = stats["status"]
    sts = " ".join("%s %d" % (badge(k or "senza stato"), v) for k, v in sorted(status_counts.items()))
    lists = []
    for sec in sections:
        if sec not in pages_by_section:
            continue
        lis = "".join('<li><a href="%s">%s</a> %s</li>' % (esc(p.out_rel), esc(p.title), badge(p.status))
                      for p in sorted(pages_by_section[sec], key=lambda p: p.rel))
        lists.append('<details id="sec-%s"><summary>%s (%d)</summary><ul>%s</ul></details>'
                     % (esc(sec), esc(section_label(sec)), len(pages_by_section[sec]), lis))
    body = (
        "<h1>Documentazione tecnica</h1>\n"
        '<div class="meta"><div>%s</div><div>Stati: %s</div>'
        "<div>Contenuto interno: la condivisione fuori dal team è manuale e va decisa caso per caso.</div></div>\n"
        '<input id="q" type="search" placeholder="Cerca per titolo o testo..." autocomplete="off" aria-label="Cerca">\n'
        '<ul id="results"></ul>\n<h2>Sezioni</h2>\n<ul class="cards">%s</ul>\n<h2>Tutte le pagine</h2>\n%s\n'
        % (" &middot; ".join(info), sts, "".join(cards), "\n".join(lists))
    )
    end = '<script src="search-index.js"></script>\n<script>%s</script>\n' % SEARCH_JS
    return shell("Documentazione tecnica", body, sidebar_html(None, pages_by_section, sections, here), here, extra_end=end)


# --------------------------------------------------------------------------- build


def git_commit(root: Path) -> Optional[str]:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(root), capture_output=True,
                           text=True, timeout=10)
        v = r.stdout.strip()
        return v if r.returncode == 0 and v else None
    except Exception:
        return None


def build(root: Path, wiki: Path, out: Path, sections: List[str], exclude: List[str],
          dry_run: bool, redaction: bool, today: Optional[str] = None) -> int:
    t0 = time.time()
    sections = [s for s in sections if s not in exclude]
    pages = collect_pages(wiki, sections)
    pages_by_section: Dict[str, List[Page]] = {}
    for p in pages:
        pages_by_section.setdefault(p.section, []).append(p)

    # redazione: su tutto il file sorgente, prima di scrivere qualsiasi cosa
    problems = []
    if redaction:
        for p in pages:
            for f in redact.scan(p.text):
                problems.append((p, f))
    else:
        print("ATTENZIONE: redazione disattivata da configurazione", file=sys.stderr)
    if problems:
        print("Redazione: %d finding in %d pagine. Build fermato, nessun file scritto."
              % (len(problems), len({id(p) for p, _ in problems})), file=sys.stderr)
        for p, f in problems:
            print("  wiki/%s.md:%d [%s] %s" % (p.rel, f.line, f.kind, f.excerpt), file=sys.stderr)
        return 2

    resolver = Resolver(pages)
    unresolved = 0
    counts = {s: len(v) for s, v in pages_by_section.items()}
    status: Dict[str, int] = {}
    for p in pages:
        status[p.status] = status.get(p.status, 0) + 1

    def summary(prefix: str) -> None:
        print("%s: %d pagine in %d sezioni (%.1fs)" % (prefix, len(pages), len(counts), time.time() - t0))
        for s in sections:
            if s in counts:
                print("  %-14s %d" % (s, counts[s]))

    if dry_run:
        summary("dry-run, redazione pulita")
        return 0

    tmp = out.parent / (out.name + ".tmp-%d" % os.getpid())
    if tmp.exists():
        shutil.rmtree(str(tmp))
    try:
        tmp.mkdir(parents=True)
        index = []
        for p in pages:
            doc = render_page(p, resolver, pages_by_section, sections, "")
            dest = tmp / p.out_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(doc, encoding="utf-8")
            index.append({"t": p.title, "s": section_label(p.section),
                          "p": p.rel + ".md", "x": md_render.plain_text(p.body)[:300]})
        stats = {"date": today or dt.date.today().isoformat(), "commit": git_commit(root),
                 "pages": len(pages), "status": status}
        (tmp / "index.html").write_text(render_index(pages_by_section, sections, stats), encoding="utf-8")
        (tmp / "search-index.js").write_text(
            "window.SEARCH_INDEX=" + json.dumps(index, ensure_ascii=True, separators=(",", ":")) + ";\n",
            encoding="utf-8")
        old = None
        if out.exists():
            old = out.parent / (out.name + ".old-%d" % os.getpid())
            out.rename(old)
        try:
            tmp.rename(out)
        except BaseException:
            # lo scambio e' fallito: rimette la versione precedente al suo posto prima di propagare l'errore
            if old is not None and old.exists() and not out.exists():
                old.rename(out)
            raise
        if old is not None:
            shutil.rmtree(str(old))
    except BaseException:
        if tmp.exists():
            shutil.rmtree(str(tmp), ignore_errors=True)
        raise
    # conteggio wikilink non risolti (informativo)
    import re
    for p in pages:
        body = re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", p.body, flags=re.S))  # fuori dal codice
        for m in re.finditer(r"\[\[([^\]|#\n]+)", body):
            if resolver.find(m.group(1), p) is None:
                unresolved += 1
    summary("generato in %s" % out)
    print("wikilink non pubblicati: %d" % unresolved)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Genera il sito di documentazione tecnica dalla wiki.")
    ap.add_argument("--out", help="cartella di output (default: <output_dir>/<data>)")
    ap.add_argument("--sections", help="sezioni da includere, separate da virgola (default: da configurazione)")
    ap.add_argument("--dry-run", action="store_true", help="conta le pagine e controlla la redazione, senza scrivere")
    ap.add_argument("--wiki", help="cartella wiki (default: <root>/wiki)")
    ap.add_argument("--root", help="radice della factory (default: risalendo da questo file)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else find_root()
    cfg = load_tech_config(root)
    if not cfg["enabled"]:
        print("documentazione disattivata (documentation.enabled: false in factory.config.yaml): "
              "nessun file generato")
        return 0
    wiki = Path(args.wiki).resolve() if args.wiki else root / "wiki"
    if not wiki.is_dir():
        print("wiki non trovata: %s" % wiki, file=sys.stderr)
        return 1
    sections = [s.strip() for s in args.sections.split(",") if s.strip()] if args.sections else list(cfg["include_sections"])
    out = Path(args.out).resolve() if args.out else root / cfg["output_dir"] / dt.date.today().isoformat()
    return build(root, wiki, out, sections, list(cfg["exclude_sections"]), args.dry_run, cfg["redaction"])


if __name__ == "__main__":
    sys.exit(main())
