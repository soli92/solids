#!/usr/bin/env python3
"""Convertitore markdown -> HTML, solo libreria standard.

Pensato per le pagine della wiki: titoli con id, paragrafi, liste annidate e task list,
tabelle GFM con allineamento, blocchi di codice, citazioni, link, immagini, enfasi,
wikilink `[[pagina]]`, `[[pagina|testo]]`, `[[pagina#sezione]]`.

Tutto il testo viene passato da html.escape: l'HTML grezzo presente nel markdown non viene
mai emesso (i commenti HTML vengono scartati).

API:
    render(md, link_resolver=None) -> str
    parse_frontmatter(text) -> (dict, body)
    slugify(text) -> str
    extract_title(body) -> str | None
    plain_text(md) -> str       # testo senza markup, per l'indice di ricerca
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
from typing import Callable, Dict, List, Optional, Tuple

__all__ = ["render", "parse_frontmatter", "slugify", "extract_title", "plain_text"]

LinkResolver = Optional[Callable[[str], Optional[str]]]

# --------------------------------------------------------------------------- frontmatter


def _scalar(v: str):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in _split_flow(inner)] if inner else []
    if v in ("null", "~", ""):
        return None if v else ""
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    return v


def _split_flow(s: str) -> List[str]:
    out, cur, q = [], "", None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur += ch
        elif ch == ",":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _simple_yaml(block: str) -> Dict[str, object]:
    """Parser minimo: `chiave: valore`, liste `- voce` sotto la chiave, liste inline [a, b]."""
    data: Dict[str, object] = {}
    key = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s+-\s+(.*)$", raw) or re.match(r"^-\s+(.*)$", raw)
        if m and key is not None:
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(_scalar(m.group(1)))  # type: ignore[union-attr]
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", raw)
        if m and not raw.startswith(" "):
            key = m.group(1)
            val = m.group(2)
            data[key] = _scalar(val) if val.strip() else None
    return data


def _normalize(v):
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {str(k): _normalize(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_normalize(x) for x in v]
    return v


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    """Separa il frontmatter YAML dal corpo. Senza frontmatter: ({}, text)."""
    if text.startswith("﻿"):
        text = text[1:]
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.DOTALL)
    if not m:
        return {}, text
    block, body = m.group(1), text[m.end():]
    data = None
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(block)
        if isinstance(loaded, dict):
            data = _normalize(loaded)
    except Exception:
        data = None
    if data is None:
        data = _simple_yaml(block)
    return data, body


# --------------------------------------------------------------------------- inline

_SLUG_STRIP = re.compile(r"[^\w\s-]", re.UNICODE)


def slugify(text: str) -> str:
    s = _plain_inline(text).strip().lower()
    s = _SLUG_STRIP.sub("", s)
    s = re.sub(r"[\s]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "sezione"


def _plain_inline(text: str) -> str:
    t = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    t = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\[\^[^\]]*\]", "", t)
    t = t.replace("`", "")
    t = re.sub(r"(\*\*|__|~~)", "", t)
    t = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"\1", t)
    return t


_SAFE_SCHEME = re.compile(r"^(https?:|mailto:|#|/|\.{1,2}/|[^:]*$)", re.IGNORECASE)


def _safe_url(url: str) -> str:
    url = url.strip()
    if not _SAFE_SCHEME.match(url):
        return "#"
    return url


def _esc(s: str) -> str:
    return _html.escape(s, quote=True)


_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
_URL_END = r"[^\s<>\]\)\"'`\x00]*[^\s<>\]\)\"'`\x00.,;:!?*]"


class _Inline:
    def __init__(self, resolver: LinkResolver):
        self.resolver = resolver
        self.stash: List[str] = []

    def put(self, html_: str) -> str:
        self.stash.append(html_)
        return "\x00%d\x00" % (len(self.stash) - 1)

    def restore(self, s: str) -> str:
        while "\x00" in s:
            new = re.sub(r"\x00(\d+)\x00", lambda m: self.stash[int(m.group(1))], s)
            if new == s:
                break
            s = new
        return s

    # -- elementi
    def _code(self, m):
        code = m.group(2).replace("\n", " ")
        if code.startswith(" ") and code.endswith(" ") and code.strip():
            code = code[1:-1]
        return self.put("<code>%s</code>" % _esc(code))

    def _wikilink(self, m):
        inner = m.group(1)
        target, _, alias = inner.partition("|")
        target = target.strip()
        page, _, section = target.partition("#")
        text = alias.strip() or target
        href = self.resolver(page.strip()) if (self.resolver and page.strip()) else None
        if page.strip() == "" and section:  # [[#sezione]] -> ancora nella stessa pagina
            href = ""
        if href is None:
            return self.put('<span class="wl-missing" title="non pubblicata">%s</span>' % _esc(text))
        if section:
            href = href + "#" + slugify(section)
        return self.put('<a class="wikilink" href="%s">%s</a>' % (_esc(href), _esc(text)))

    def _image(self, m):
        alt, url = m.group(1), m.group(2).split()[0] if m.group(2).split() else ""
        return self.put('<img src="%s" alt="%s">' % (_esc(_safe_url(url)), _esc(alt)))

    def _link(self, m):
        text, rest = m.group(1), m.group(2).strip()
        url, title = rest, ""
        tm = re.match(r'^(\S+)\s+"([^"]*)"$', rest)
        if tm:
            url, title = tm.group(1), tm.group(2)
        url = url.strip("<>")
        inner = self.inline(text)
        if self.resolver and re.search(r"\.md(#.*)?$", url) and not re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I):
            path, _, frag = url.partition("#")
            href = self.resolver(path)
            if href is None:
                return self.put('<span class="wl-missing" title="non pubblicata">%s</span>' % inner)
            if frag:
                href = href + "#" + frag
            return self.put('<a href="%s">%s</a>' % (_esc(href), inner))
        ext = re.match(r"^https?:", url, re.I) is not None
        attrs = ' rel="noopener noreferrer"' if ext else ""
        t = ' title="%s"' % _esc(title) if title else ""
        return self.put('<a href="%s"%s%s>%s</a>' % (_esc(_safe_url(url)), t, attrs, inner))

    def _autolink(self, m):
        u = m.group(1)
        return self.put('<a href="%s" rel="noopener noreferrer">%s</a>' % (_esc(u), _esc(u)))

    def _cite(self, m):
        return self.put('<span class="cite">%s</span>' % _esc(m.group(1).strip()))

    def inline(self, text: str) -> str:
        text = re.sub(r"<!--.*?-->", "", text)
        text = _CODE_SPAN.sub(self._code, text)
        text = re.sub(r"\[\[([^\]\n]+)\]\]", self._wikilink, text)
        text = re.sub(r"!\[([^\]]*)\]\(([^()\s]*(?:\([^()]*\)[^()\s]*)*(?:\s+\"[^\"]*\")?)\)", self._image, text)
        text = re.sub(r"\[([^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*)\]\(([^()\s]*(?:\([^()]*\)[^()\s]*)*(?:\s+\"[^\"]*\")?)\)", self._link, text)
        text = re.sub(r"\[\^([^\]\n]*)\]", self._cite, text)
        text = re.sub(r"<(https?://[^>\s]+)>", self._autolink, text)
        text = re.sub(r"(?<![\w/=\"'(])(https?://" + _URL_END + ")", self._autolink, text)
        text = _esc(text)
        text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text, flags=re.DOTALL)
        text = re.sub(r"(?<![\w])__(?=\S)(.+?)(?<=\S)__(?![\w])", r"<strong>\1</strong>", text, flags=re.DOTALL)
        text = re.sub(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])", r"<em>\1</em>", text, flags=re.DOTALL)
        text = re.sub(r"(?<![\w])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w])", r"<em>\1</em>", text, flags=re.DOTALL)
        text = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", text, flags=re.DOTALL)
        text = re.sub(r"(?: {2,}|\\)\n", "<br>\n", text)
        return self.restore(text)


# --------------------------------------------------------------------------- blocchi

_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})\s*([^\s`]*)[^`]*$")
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_HR = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_ITEM = re.compile(r"^( *)([-*+]|\d{1,9}[.)])(?: +(.*)|$)")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _split_row(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, in_code = [], "", False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    cells.append(cur.strip())
    return cells


class _Renderer:
    def __init__(self, resolver: LinkResolver):
        self.inl = _Inline(resolver)
        self.resolver = resolver
        self.ids: Dict[str, int] = {}

    def inline(self, t: str) -> str:
        self.inl = _Inline(self.resolver)
        return self.inl.inline(t)

    def heading_id(self, text: str) -> str:
        base = slugify(text)
        n = self.ids.get(base, 0)
        self.ids[base] = n + 1
        return base if n == 0 else "%s-%d" % (base, n)

    def is_block_start(self, line: str) -> bool:
        return bool(
            _FENCE.match(line)
            or _HEADING.match(line)
            or _HR.match(line)
            or line.lstrip().startswith(">")
            or _ITEM.match(line)
        )

    def blocks(self, lines: List[str], tight: bool = False) -> str:
        out: List[str] = []
        i, n = 0, len(lines)
        while i < n:
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            # commento HTML su più righe
            if line.lstrip().startswith("<!--"):
                while i < n and "-->" not in lines[i]:
                    i += 1
                i += 1
                continue
            m = _FENCE.match(line)
            if m:
                ind, fence, lang = len(m.group(1)), m.group(2), m.group(3)
                i += 1
                body = []
                while i < n:
                    cl = lines[i]
                    if re.match(r"^ {0,3}" + re.escape(fence[0]) + "{%d,}\\s*$" % len(fence), cl):
                        i += 1
                        break
                    body.append(cl[ind:] if cl[:ind].strip() == "" else cl)
                    i += 1
                cls = ' class="language-%s"' % _esc(lang) if lang else ""
                out.append("<pre><code%s>%s</code></pre>" % (cls, _esc("\n".join(body))))
                continue
            m = _HEADING.match(line)
            if m:
                lvl, txt = len(m.group(1)), m.group(2)
                out.append('<h%d id="%s">%s</h%d>' % (lvl, _esc(self.heading_id(txt)), self.inline(txt), lvl))
                i += 1
                continue
            if _HR.match(line):
                out.append("<hr>")
                i += 1
                continue
            if line.lstrip().startswith(">"):
                q = []
                while i < n and (lines[i].lstrip().startswith(">") or (lines[i].strip() and q and not self.is_block_start(lines[i]))):
                    l = lines[i].lstrip()
                    if l.startswith(">"):
                        l = l[1:]
                        if l.startswith(" "):
                            l = l[1:]
                    q.append(l)
                    i += 1
                out.append("<blockquote>%s</blockquote>" % self.blocks(q))
                continue
            if "|" in line and i + 1 < n and _TABLE_SEP.match(lines[i + 1]) and "-" in lines[i + 1]:
                head = _split_row(line)
                seps = _split_row(lines[i + 1])
                if len(seps) == len(head) or len(seps) >= 1:
                    aligns = []
                    for s in seps:
                        s = s.strip()
                        l_, r_ = s.startswith(":"), s.endswith(":")
                        aligns.append("center" if l_ and r_ else "right" if r_ else "left" if l_ else "")
                    i += 2
                    rows = []
                    while i < n and lines[i].strip() and "|" in lines[i]:
                        rows.append(_split_row(lines[i]))
                        i += 1

                    def cell(tag, txt, k):
                        a = aligns[k] if k < len(aligns) else ""
                        st = ' style="text-align:%s"' % a if a else ""
                        return "<%s%s>%s</%s>" % (tag, st, self.inline(txt), tag)

                    t = ["<div class=\"table-wrap\"><table>", "<thead><tr>"]
                    t += [cell("th", c, k) for k, c in enumerate(head)]
                    t.append("</tr></thead><tbody>")
                    for r in rows:
                        r = (r + [""] * len(head))[: max(len(head), len(r))]
                        t.append("<tr>" + "".join(cell("td", c, k) for k, c in enumerate(r)) + "</tr>")
                    t.append("</tbody></table></div>")
                    out.append("".join(t))
                    continue
            if _ITEM.match(line):
                html_, i = self.list(lines, i)
                out.append(html_)
                continue
            # paragrafo
            para = [line.lstrip()]
            i += 1
            while i < n and lines[i].strip() and not self.is_block_start(lines[i]) and not lines[i].lstrip().startswith("<!--"):
                if "|" in lines[i] and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
                    break
                para.append(lines[i].lstrip())  # i due spazi finali (a capo) restano
                i += 1
            para[-1] = para[-1].rstrip()
            html_ = self.inline("\n".join(para))
            out.append(html_ if tight else "<p>%s</p>" % html_)
        return "\n".join(out)

    def list(self, lines: List[str], i: int) -> Tuple[str, int]:
        n = len(lines)
        m0 = _ITEM.match(lines[i])
        base = len(m0.group(1))
        ordered = m0.group(2)[0].isdigit()
        start = int(re.match(r"\d+", m0.group(2)).group(0)) if ordered else 1
        items: List[Tuple[List[str], bool]] = []
        loose = False
        while i < n:
            if not lines[i].strip():  # riga vuota tra voci dello stesso elenco: elenco "largo"
                j = i
                while j < n and not lines[j].strip():
                    j += 1
                mj = _ITEM.match(lines[j]) if j < n else None
                if mj and len(mj.group(1)) == base and mj.group(2)[0].isdigit() == ordered:
                    loose = True
                    i = j
                else:
                    break
            m = _ITEM.match(lines[i])
            if not m or len(m.group(1)) != base or m.group(2)[0].isdigit() != ordered:
                break
            first = m.group(3) or ""
            body = [first]
            raw_cont: List[str] = []
            i += 1
            while i < n:
                l = lines[i]
                if not l.strip():
                    j = i
                    while j < n and not lines[j].strip():
                        j += 1
                    if j < n and _indent(lines[j]) > base:
                        raw_cont.extend([""] * (j - i))
                        i = j
                        continue
                    break
                if _indent(l) > base:
                    raw_cont.append(l)
                    i += 1
                    continue
                prev_blank = bool(raw_cont and not raw_cont[-1].strip()) or False
                if (not prev_blank and not self.is_block_start(l) and not _ITEM.match(l)
                        and not (body and not body[-1].strip() and not raw_cont)):
                    raw_cont.append("  " * 0 + " " * (base + 1) + l.strip())  # continuazione pigra
                    i += 1
                    continue
                break
            nz = [_indent(x) for x in raw_cont if x.strip()]
            cut = min(nz) if nz else 0
            body += [x[cut:] if x.strip() else "" for x in raw_cont]
            has_blank = any(not x.strip() for x in body[1:]) and any(x.strip() for x in body[1:])
            # lista "larga" solo se la riga vuota separa blocchi di primo livello
            items.append((body, has_blank))
        tag = "ol" if ordered else "ul"
        attrs = ' start="%d"' % start if ordered and start != 1 else ""
        has_task = False
        li = []
        for body, has_blank in items:
            task = ""
            if body and re.match(r"^\[[ xX]\]\s", body[0] + " "):
                checked = body[0][1] in "xX"
                body[0] = body[0][3:].lstrip()
                task = '<input type="checkbox" disabled%s> ' % (" checked" if checked else "")
                has_task = True
            inner = self.blocks(body, tight=not (has_blank or loose))
            cls = ' class="task"' if task else ""
            li.append("<li%s>%s%s</li>" % (cls, task, inner))
        cls = ' class="task-list"' if has_task else ""
        return "<%s%s%s>\n%s\n</%s>" % (tag, attrs, cls, "\n".join(li), tag), i


def render(md: str, link_resolver: LinkResolver = None) -> str:
    """Converte markdown in HTML (frammento, senza <html>/<body>)."""
    md = md.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    return _Renderer(link_resolver).blocks(md.split("\n"))


def extract_title(body: str) -> Optional[str]:
    in_fence = False
    for line in body.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
        if in_fence:
            continue
        m = re.match(r"^#\s+(.*?)\s*#*\s*$", line)
        if m:
            return _plain_inline(m.group(1)).strip()
    return None


def plain_text(md: str) -> str:
    """Testo senza markup (per l'indice di ricerca): niente codice, tabelle appiattite."""
    out = []
    in_fence = False
    for line in md.replace("\r\n", "\n").split("\n"):
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _TABLE_SEP.match(line) and "-" in line:
            continue
        s = re.sub(r"<!--.*?-->", "", line)
        s = re.sub(r"^\s*(#{1,6}\s+|>+\s*|[-*+]\s+(\[[ xX]\]\s+)?|\d+[.)]\s+)", "", s)
        s = s.replace("|", " ")
        s = _plain_inline(s)
        s = re.sub(r"\s+", " ", s).strip()
        if s and not _HR.match(line):
            out.append(s)
    return " ".join(out)
