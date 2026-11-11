#!/usr/bin/env python3
"""Verifica di un documento destinato a lettori esterni.

Tre controlli, tutti con la sola libreria standard:

  citazioni  i rimandi `path:riga`, `path:riga-riga`, `[^src: path ...]` e i path
             `wiki/...md` puntano a file esistenti e a righe esistenti.
  verbatim   i blocchi (per intestazione o marcati) e le stringhe indicate
             compaiono identici nel file di origine.
  codici     nel documento non compaiono identificativi interni (kanban, ADR,
             regole, piu' i pattern del progetto) ne' termini vietati.

Limite dichiarato: il controllo verifica che il rimando esista e che il testo
coincida. NON verifica che il contenuto citato sostenga l'affermazione.

Exit code: 0 tutto verificato, 1 problemi trovati, 2 errore d'uso o file non leggibile.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

DISCLAIMER = (
    "Nota: il controllo verifica il rimando e l'identita' del testo; "
    "NON verifica che il contenuto sostenga l'affermazione."
)

# Codici interni della factory. Quelli di un progetto (identificativi di gap, domande, regole
# proprie) si aggiungono da riga di comando con --pattern ETICHETTA=REGEX o --pattern-file.
INTERNAL_CODE_PATTERNS = [
    ("id-kanban", r"\b(?:[A-Z]{2,4}-)?(?:TSK|US|EP)-\d+\b"),
    ("adr", r"\bADR-\d{3}\b"),
    ("regola", r"(?<![\w.])R\.\d+\b"),
]

EXT = r"(?:md|py|yaml|yml|json|js|mjs|cjs|ts|svelte|astro|sh|html|css|sql|toml|txt)"
PATH = r"[\w@~.\-/]+\." + EXT
RE_LINEREF = re.compile(r"(?<![\w/:.\-])(" + PATH + r"):(\d+)(?:-(\d+))?\b")
RE_SRC = re.compile(r"\[\^src:\s*([^\s,;:\]]+)(?::(\d+)(?:-(\d+))?)?")
RE_WIKI = re.compile(r"(?<![\w/.\-])(wiki/[\w@~.\-/]+\.md)\b")


WARNINGS = []


class UsageError(Exception):
    pass


def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise UsageError("file non leggibile: %s (%s)" % (path, exc))


def strip_frontmatter(text):
    """Restituisce (testo, righe_rimosse): il frontmatter viene sostituito da righe vuote."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join([""] * (i + 1) + lines[i + 1:])
    return text


# ---------------------------------------------------------------- citazioni

def load_source_lines(path, root, ref):
    """Righe del file citato, o None se non esiste. Con ref legge da git (submodule)."""
    rel = path.lstrip("./") if path.startswith("./") else path
    if ref and rel.startswith("code_repos/"):
        parts = rel.split("/", 2)
        if len(parts) < 3:
            return None
        repo = os.path.join(root, parts[0], parts[1])
        try:
            out = subprocess.run(
                ["git", "-C", repo, "show", "%s:%s" % (ref, parts[2])],
                capture_output=True, text=True, check=False)
        except OSError as exc:
            raise UsageError("git non eseguibile: %s" % exc)
        if out.returncode != 0:
            return None
        return out.stdout.split("\n")
    full = os.path.join(root, rel)
    if not os.path.isfile(full):
        return None
    return read_text(full).split("\n")


def count_lines(lines):
    return len(lines) - 1 if lines and lines[-1] == "" else len(lines)


def find_citations(text):
    """Yield (riga, colonna, path, da, a) per ogni rimando trovato."""
    for n, line in enumerate(text.split("\n"), 1):
        seen = set()
        for rx in (RE_SRC, RE_LINEREF):
            for m in rx.finditer(line):
                a = int(m.group(2)) if m.group(2) else None
                b = int(m.group(3)) if m.group(3) else a
                key = (m.group(1), a, b)
                if key in seen or "://" in line[max(0, m.start(1) - 3):m.start(1)]:
                    continue
                seen.add(key)
                yield n, m.start(1) + 1, m.group(1), a, b
        for m in RE_WIKI.finditer(line):
            if any(c[0] == m.group(1) for c in seen):
                continue
            yield n, m.start(1) + 1, m.group(1), None, None


def check_citations(text, root, ref):
    problems, total, cache = [], 0, {}
    for n, col, path, a, b in find_citations(text):
        total += 1
        if path not in cache:
            cache[path] = load_source_lines(path, root, ref)
        lines = cache[path]
        where = "%d:%d" % (n, col)
        if lines is None:
            problems.append("%s file non trovato: %s" % (where, path))
            continue
        if a is None:
            continue
        size = count_lines(lines)
        if a < 1 or b < a or b > size:
            problems.append("%s riga fuori intervallo: %s:%d%s (il file ha %d righe)" % (
                where, path, a, "-%d" % b if b != a else "", size))
    return problems, total


# ----------------------------------------------------------------- verbatim

RE_TITLE = re.compile(r"^(?:(#+)\s+|\*\*)(.*?)(?:\*\*)?\s*$")
RE_BOLD_TITLE = re.compile(r"^\*\*[^*].*\*\*\s*$")


def title_key(line):
    """Testo di un titolo senza i marcatori `#` o `**`."""
    m = RE_TITLE.match(line.strip())
    return m.group(2).strip() if m else line.strip()


def extract_heading_blocks(text, heading):
    """Tutti i blocchi che partono da un titolo che inizia con `heading` (i marcatori
    `#`/`**` non contano: `### T2 —` trova sia `### T2 — ...` sia `**T2 — ...**`).
    Un blocco arriva al prossimo titolo (intestazione `#` dello stesso livello o
    superiore, o riga tutta in grassetto), a un separatore `---` o a fine file.
    Restituisce una lista di (titolo, corpo)."""
    key = title_key(heading)
    lines = text.split("\n")
    found = []
    in_fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if in_fence or not (line.startswith("#") or line.startswith("**")):
            continue
        if not title_key(line).startswith(key):
            continue
        level = len(line) - len(line.lstrip("#")) or 99
        end, fence = len(lines), False
        for j in range(i + 1, len(lines)):
            if lines[j].lstrip().startswith("```"):
                fence = not fence
            if fence:
                continue
            m = re.match(r"^(#+)\s", lines[j])
            if (m and len(m.group(1)) <= level) or RE_BOLD_TITLE.match(lines[j]) \
                    or lines[j].strip() == "---":
                end = j
                break
        body = [l.rstrip() for l in lines[i + 1:end]]
        while body and not body[-1].strip():
            body.pop()
        found.append((title_key(line), "\n".join(body)))
    return found


def normalize(text):
    return "\n".join(l.rstrip() for l in text.split("\n"))


def extract_marked_blocks(text):
    return re.findall(r"<!--\s*verbatim\s*-->\n?(.*?)\n?<!--\s*/verbatim\s*-->", text, re.S)


def squash(text, exact):
    """Di default le righe vuote non contano (in markdown separano soltanto)."""
    if exact:
        return text
    return "\n".join(l for l in text.split("\n") if l.strip())


def check_blocks(doc, src, headings, marked, exact=False, warnings=None):
    warnings = warnings if warnings is not None else []
    problems, total = [], 0
    nsrc = squash(normalize(src), exact)
    for h in headings:
        total += 1
        dc = extract_heading_blocks(doc, h)
        sc = extract_heading_blocks(src, h)
        if not dc:
            problems.append("blocco assente nel documento: %s" % h)
            continue
        if not sc:
            problems.append("blocco assente nella fonte: %s" % h)
            continue
        d = dc[0]
        same = [c for c in sc if c[0] == d[0]]
        if not same:
            problems.append("blocco diverso dalla fonte: %s (titolo diverso: documento %r; "
                            "titoli nella fonte: %s)" % (
                                h, d[0][:70], "; ".join(repr(c[0][:70]) for c in sc)))
            continue
        if len(same) > 1:
            warnings.append("piu' titoli identici nella fonte per %s: confrontato il primo" % h)
        s = same[0]
        if squash(d[1], exact) != squash(s[1], exact):
            problems.append("blocco diverso dalla fonte: %s (%s)" % (
                h, first_diff(squash(d[1], exact), squash(s[1], exact))))
    if marked:
        for i, blk in enumerate(extract_marked_blocks(doc), 1):
            total += 1
            if squash(normalize(blk), exact).strip("\n") not in nsrc:
                problems.append("blocco marcato n.%d non presente identico nella fonte: %r" % (
                    i, blk.strip().split("\n")[0][:70]))
    return problems, total


def first_diff(d, s):
    dl, sl = d.split("\n"), s.split("\n")
    for i in range(max(len(dl), len(sl))):
        a = dl[i] if i < len(dl) else "<fine>"
        b = sl[i] if i < len(sl) else "<fine>"
        if a != b:
            k = 0
            while k < min(len(a), len(b)) and a[k] == b[k]:
                k += 1
            k = max(0, k - 15)
            return "prima differenza alla riga %d, colonna %d: documento %r, fonte %r" % (
                i + 1, k + 1, a[k:k + 60], b[k:k + 60])
    return "differenza non localizzata"


def check_strings(doc, src, strings):
    problems = []
    for s in strings:
        if s not in src:
            problems.append("stringa assente nella fonte: %r" % s)
        elif s not in doc:
            problems.append("stringa assente nel documento: %r" % s)
    return problems, len(strings)


# -------------------------------------------------------------------- codici

def parse_patterns(specs, path=None):
    """Coppie (etichetta, regex compilata) da `ETICHETTA=REGEX` (e da un file, uno per riga)."""
    specs = list(specs or [])
    if path:
        specs += [l.strip() for l in read_text(path).split("\n") if l.strip() and not l.startswith("#")]
    out = []
    for spec in specs:
        label, sep, rx = spec.partition("=")
        if not sep or not label.strip() or not rx:
            raise UsageError("pattern non valido (atteso ETICHETTA=REGEX): %s" % spec)
        try:
            out.append((label.strip(), re.compile(rx)))
        except re.error as exc:
            raise UsageError("espressione regolare non valida in %s: %s" % (spec, exc))
    return out


def check_codes(text, forbidden, extra=()):
    problems = []
    pats = [(lab, re.compile(rx)) for lab, rx in INTERNAL_CODE_PATTERNS] + list(extra)
    for w in forbidden:
        pats.append(("vietato", re.compile(r"(?<!\w)" + re.escape(w) + r"(?!\w)", re.I)))
    for n, line in enumerate(text.split("\n"), 1):
        for lab, rx in pats:
            for m in rx.finditer(line):
                problems.append("%d:%d %s: %s" % (n, m.start() + 1, lab, m.group(0)))
    return sorted(problems, key=lambda p: tuple(int(x) for x in p.split(" ")[0].split(":"))), 0


# ----------------------------------------------------------------------- cli

def split_list(values, sep):
    out = []
    for v in values or []:
        out.extend(x.strip() for x in v.split(sep) if x.strip())
    return out


def build_parser():
    p = argparse.ArgumentParser(
        prog="verify_verbatim.py",
        description=("Verifica un documento per lettori esterni: citazioni che risolvono, "
                     "testo copiato alla lettera, assenza di codici interni. " + DISCLAIMER),
        epilog="Exit code: 0 tutto verificato, 1 problemi trovati, 2 errore d'uso o file non leggibile.")
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("documento", help="file markdown da verificare")
        sp.add_argument("--con-frontmatter", action="store_true",
                        help="include il frontmatter YAML (di default e' escluso)")

    c = sub.add_parser("citazioni", help="verifica che path e righe citati esistano. " + DISCLAIMER,
                       description="Trova `path:riga`, `path:riga-riga`, `[^src: path ...]` e path "
                                   "`wiki/...md`. " + DISCLAIMER)
    common(c)
    c.add_argument("--root", default=None, help="radice per i path relativi (default: radice del repository)")
    c.add_argument("--ref", default=None,
                   help="SHA o ref: i path in code_repos/<repo>/ si leggono con `git show <ref>:<path>` nel submodule")

    v = sub.add_parser("verbatim", help="verifica blocchi e stringhe contro la fonte. " + DISCLAIMER,
                       description="Confronta blocchi (per intestazione o marcati con "
                                   "<!-- verbatim --> ... <!-- /verbatim -->) e stringhe con la fonte. "
                                   "Un blocco per intestazione va dalla riga che inizia con il testo "
                                   "indicato fino alla prossima intestazione dello stesso livello o superiore. "
                                   + DISCLAIMER)
    common(v)
    v.add_argument("--fonte", required=True, help="file di origine del testo copiato")
    v.add_argument("--blocchi", default=None,
                   help="titoli separati da virgola, es. \"### T2 —,### BE-4 —\"")
    v.add_argument("--esatto", action="store_true",
                   help="conta anche le righe vuote (di default non contano; gli spazi a fine riga mai)")
    v.add_argument("--marcati", action="store_true",
                   help="verifica anche i blocchi marcati <!-- verbatim --> ... <!-- /verbatim -->")
    v.add_argument("--stringhe", action="append", default=[],
                   help="stringhe (nomi, orari, scadenze) separate da '|'; ripetibile. Devono comparire "
                        "identiche nella fonte e nel documento")
    v.add_argument("--stringhe-file", default=None, help="file con una stringa per riga")

    k = sub.add_parser("codici", help="segnala ID interni e termini vietati. " + DISCLAIMER,
                       description="Segnala con riga e colonna gli identificativi interni "
                                   "(elenco in INTERNAL_CODE_PATTERNS, piu' --pattern) e i termini vietati. " + DISCLAIMER)
    common(k)
    k.add_argument("--vietati", default="", help="termini vietati separati da virgola, es. alfa,beta")
    k.add_argument("--pattern", action="append", default=[], metavar="ETICHETTA=REGEX",
                   help="codice interno aggiuntivo del progetto (ripetibile)")
    k.add_argument("--pattern-file", default=None,
                   help="file con un ETICHETTA=REGEX per riga (le righe # sono commenti)")
    return p


def default_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))


def run(args):
    raw = read_text(args.documento)
    doc = raw if args.con_frontmatter else strip_frontmatter(raw)
    if args.cmd == "citazioni":
        root = os.path.abspath(args.root) if args.root else default_root()
        if not os.path.isdir(root):
            raise UsageError("root non valida: %s" % root)
        return check_citations(doc, root, args.ref)
    if args.cmd == "verbatim":
        src = read_text(args.fonte)
        problems, total = [], 0
        heads = split_list([args.blocchi], ",") if args.blocchi else []
        strings = split_list(args.stringhe, "|")
        if args.stringhe_file:
            strings += [l.strip() for l in read_text(args.stringhe_file).split("\n") if l.strip()]
        if not (heads or args.marcati or strings):
            raise UsageError("verbatim richiede --blocchi, --marcati o --stringhe/--stringhe-file")
        if heads or args.marcati:
            p, t = check_blocks(doc, src, heads, args.marcati, args.esatto, WARNINGS)
            problems += p
            total += t
        if strings:
            p, t = check_strings(doc, src, strings)
            problems += p
            total += t
        return problems, total
    if args.cmd == "codici":
        extra = parse_patterns(args.pattern, args.pattern_file)
        return check_codes(doc, [w.strip() for w in args.vietati.split(",") if w.strip()], extra)
    raise UsageError("sotto-comando mancante")


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if not args.cmd:
        parser.print_usage(sys.stderr)
        return 2
    del WARNINGS[:]
    try:
        problems, total = run(args)
    except UsageError as exc:
        print("errore: %s" % exc, file=sys.stderr)
        return 2
    for w in WARNINGS:
        print("%s: avviso: %s" % (args.documento, w))
    for p in problems:
        print("%s: %s" % (args.documento, p))
    if args.cmd == "codici":
        print("%s: %d codici interni trovati" % (args.cmd, len(problems)))
    else:
        print("%s: %d controlli, %d problemi" % (args.cmd, total, len(problems)))
    print(DISCLAIMER)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
