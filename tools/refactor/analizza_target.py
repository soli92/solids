#!/usr/bin/env python3
"""analizza_target.py — Fase 0: inventario e outline di un target di refactoring.

Il target puo' essere: un singolo file .md (skill o agente), una dir-skill
(contiene SKILL.md), o una flotta (dir con piu' unita' .md con frontmatter).

Uso: analizza_target.py <path>
Solo lettura. Exit 0 = analisi prodotta; exit 1 = precondizioni violate.

Singola passata in-process: scala a flotte di centinaia di file (a differenza di
un ciclo bash che forka per-file). Robusto a CRLF e byte non-UTF8.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

SOGLIA_REFACTOR = 500
SOGLIA_VALUTARE = 300
SOGLIA_SEZIONE = 80
FENCE = re.compile(r"^```")
HEAD = re.compile(r"^(#{2,})[ \t]+(.+?)\s*$")


_EXT = chr(92) * 2 + "?" + chr(92)   # prefisso Windows extended-length: \\?\


def _rt(path: Path) -> str:
    """Legge un file; su Windows ritenta con prefisso extended-length oltre MAX_PATH."""
    try:
        with open(str(path), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        if os.name == "nt":
            try:
                with open(_EXT + os.path.abspath(str(path)), encoding="utf-8", errors="replace") as f:
                    return f.read()
            except OSError:
                pass
        print(f"[AVVISO] impossibile leggere (path troppo lungo?): {path}", file=sys.stderr)
        return ""


def read_lines(p: Path) -> list[str]:
    return _rt(p).replace("\r\n", "\n").split("\n")


def fm_end(lines: list[str]) -> int:
    """Riga (1-based) del '---' di chiusura del frontmatter, 0 se assente."""
    if not lines or lines[0].strip() != "---":
        return 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i + 1
    return 0


def metriche(lines: list[str]) -> tuple[int, int, int]:
    tot = len(lines)
    fe = fm_end(lines)
    inizio = fe + 1 if fe else 1
    return tot, tot - inizio + 1, fe


def verdetto(corpo: int) -> str:
    if corpo > SOGLIA_REFACTOR:
        return f"REFACTOR (>{SOGLIA_REFACTOR})"
    if corpo > SOGLIA_VALUTARE:
        return "VALUTARE"
    return "ok"


def outline(lines: list[str], fe: int) -> list[str]:
    tot = len(lines)
    secs = []  # (livello, riga1based, titolo)
    fence = False
    for i in range(fe, tot):
        ln = lines[i]
        if FENCE.match(ln):
            fence = not fence
            continue
        if not fence:
            m = HEAD.match(ln)
            if m:
                secs.append((len(m.group(1)), i + 1, m.group(2)))
    out = []
    if not secs:
        return ["    (nessuna sezione ##)"]
    for k, (lvl, riga, tit) in enumerate(secs):
        fine = secs[k + 1][1] - 1 if k + 1 < len(secs) else tot
        span = fine - riga + 1
        mark = "  <-- candidata foglia" if span > SOGLIA_SEZIONE else ""
        out.append(f"    {'#'*lvl:<4} r.{riga:>4}-{fine:<4} ({span:>3} righe)  {tit}{mark}")
    return out


def is_unit(p: Path) -> bool:
    if {"evals", "node_modules", "__pycache__"} & set(p.parts):
        return False
    if p.name in ("SKILL.md", "AGENTS.md"):
        return True
    try:
        first = _rt(p).lstrip("﻿").splitlines()[:1]
    except Exception:
        return False
    return bool(first) and first[0].strip() == "---"


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: analizza_target.py <path>", file=sys.stderr)
        return 1
    target = Path(sys.argv[1])
    if not target.exists():
        print(f"[ERRORE] path non trovato: {target}", file=sys.stderr)
        return 1

    print("=" * 64)
    print(f"ANALISI TARGET: {target}")
    print("=" * 64)

    # --- singolo file
    if target.is_file():
        lines = read_lines(target)
        tot, corpo, fe = metriche(lines)
        print(f"File singolo — righe {tot}, corpo {corpo} — {verdetto(corpo)}\n")
        print("OUTLINE:")
        print("\n".join(outline(lines, fe)))
        return 0

    units = sorted(p for p in target.rglob("*.md") if is_unit(p))
    if not units:
        print(f"[ERRORE] nessuna unita' (SKILL.md/AGENTS.md/.md con frontmatter) in {target}",
              file=sys.stderr)
        return 1
    is_skill = (target / "SKILL.md").is_file()

    print(f"Unita' trovate: {len(units)}  (layout skill: {'si' if is_skill else 'no'})\n")
    print("TABELLA UNITA' (corpo = righe dopo il frontmatter)")
    print("-" * 64)
    print(f"  {'file':<45} {'corpo':>6}  verdetto")
    sopra = []
    cache = {}
    for u in units:
        lines = read_lines(u)
        tot, corpo, fe = metriche(lines)
        cache[u] = (lines, fe)
        v = verdetto(corpo)
        print(f"  {str(u.relative_to(target)):<45} {corpo:>6}  {v}")
        if v.startswith(("REFACTOR", "VALUTARE")):
            sopra.append(u)
    print()

    if sopra:
        print(f"OUTLINE DELLE UNITA' SOPRA SOGLIA (candidate foglia se > {SOGLIA_SEZIONE} righe)")
        print("-" * 64)
        for u in sopra:
            lines, fe = cache[u]
            print(f"  {u.relative_to(target)}:")
            print("\n".join(outline(lines, fe)))
            print()
    else:
        print("Nessuna unita' sopra soglia: nessun refactor strutturale necessario.\n")

    # --- inventario risorse (layout skill)
    if is_skill:
        print("RISORSE (layout skill)")
        print("-" * 64)
        corpus_parts = [_rt(target / "SKILL.md")]
        for d in ("references", "scripts"):
            dd = target / d
            if dd.is_dir():
                for f in dd.rglob("*"):
                    if f.is_file():
                        corpus_parts.append(_rt(f))
        corpus = "\n".join(corpus_parts)
        trovate = False
        for d in ("references", "scripts", "assets"):
            dd = target / d
            if dd.is_dir():
                for f in sorted(x for x in dd.rglob("*") if x.is_file()):
                    trovate = True
                    righe = len(read_lines(f))
                    st = "CITATA" if f.name in corpus else "ORFANA"
                    print(f"  {st:<8} {righe:>5} righe  {f.relative_to(target)}")
        if not trovate:
            print("  (nessuna: skill a file singolo)")
        print()

    print("NOTA: per il grafo dei riferimenti tra file (orfani, collisioni, path")
    print(f"assenti, mismatch nome/filename) esegui: scripts/mappa_riferimenti.py {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
