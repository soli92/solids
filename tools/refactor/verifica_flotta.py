#!/usr/bin/env python3
"""verifica_flotta.py — Fase 3: gate strutturali fail-closed per unita'.

Target: singolo file .md, dir-skill (SKILL.md), o flotta (dir di unita').
Uso: verifica_flotta.py <path> [--snapshot DIR] [--consenti-modifica-triggering]
Exit 0 = PASS (gli avvisi non bloccano); exit 1 = FAIL (>=1 errore).

I gate di grafo G9-G11 stanno in mappa_riferimenti.py --gate: eseguilo dopo.
Singola passata in-process (scala a flotte grandi). Robusto a CRLF e non-UTF8.
Nota G8: slug ancore stile GitHub (minuscole, punteggiatura via, spazi->trattini).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

SOGLIA_ERRORE = 500
SOGLIA_AVVISO = 250

PATH_RE = re.compile(r"(?<![\w./-])((?:references|scripts|assets)/[A-Za-z0-9._/-]*\.[A-Za-z0-9]{1,5}(?:#[A-Za-z0-9._-]+)?)")
HEAD_RE = re.compile(r"^#{1,6}[ \t]+(.+?)\s*$")
FENCE_RE = re.compile(r"^```")

ERRORI = 0
AVVISI = 0


def ok(m): print(f"[OK]      {m}")
def avv(m):
    global AVVISI; AVVISI += 1; print(f"[AVVISO]  {m}")
def err(m):
    global ERRORI; ERRORI += 1; print(f"[ERRORE]  {m}")


_EXT = chr(92) * 2 + "?" + chr(92)   # prefisso Windows extended-length: \\?\


def lines_of(p: Path) -> list[str]:
    """Legge un file; su Windows ritenta con prefisso extended-length oltre MAX_PATH."""
    try:
        with open(str(p), encoding="utf-8", errors="replace") as f:
            return f.read().replace("\r\n", "\n").split("\n")
    except OSError:
        if os.name == "nt":
            try:
                with open(_EXT + os.path.abspath(str(p)), encoding="utf-8", errors="replace") as f:
                    return f.read().replace("\r\n", "\n").split("\n")
            except OSError:
                pass
        print(f"[AVVISO] impossibile leggere (path troppo lungo?): {p}", file=sys.stderr)
        return []


_YAML_BLOCK_SCALAR = re.compile(r"^[>|][-+]?\s*$")


def split_fm(lines: list[str]) -> tuple[dict, int]:
    """(frontmatter_dict, riga_fine_1based). fine=0 se assente.

    Gestisce YAML block scalars (`description: >-`, `description: |`): l'indicatore
    (`>-`, `|`, `>+`, ...) è metadata di parsing, non parte del valore. Bug fix
    EP-060 pilot: senza questo, il parser cattura `>-` come contenuto e G2 fallisce
    con "description con parentesi angolari" su tutti i frontmatter multi-line YAML.
    """
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fm: dict[str, str] = {}
    key = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return fm, i + 1
        m = re.match(r"^([A-Za-z][\w-]*):\s?(.*)$", lines[i])
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            # YAML block scalar indicator (>-, |-, >, |, >+, |+) → non è contenuto
            fm[key] = "" if _YAML_BLOCK_SCALAR.match(val) else val
        elif key and lines[i].strip():
            fm[key] = (fm[key] + " " + lines[i].strip()).strip()
    return {}, 0


def unquote(v: str) -> str:
    v = v.strip()
    return v[1:-1] if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0] else v


def anchors(lines: list[str]) -> set[str]:
    out, fence = set(), False
    for ln in lines:
        if FENCE_RE.match(ln):
            fence = not fence; continue
        if fence:
            continue
        m = HEAD_RE.match(ln)
        if m:
            t = re.sub(r"[^a-z0-9 -]", "", m.group(1).lower())
            out.add(re.sub(r" +", "-", t.strip()))
    return out


def cited_paths(lines: list[str]) -> set[str]:
    """Estrae path citati, ignorando blockquote e code fence (ospitano esempi
    illustrativi / placeholder). Bug fix EP-060 pilot: senza code fence guard,
    esempi foo/bar/baz dentro triple-backtick vengono catturati come veri path."""
    out = set()
    fence = False
    for ln in lines:
        if FENCE_RE.match(ln):
            fence = not fence
            continue
        if fence or ln.lstrip().startswith(">"):
            continue
        for m in PATH_RE.finditer(ln):
            out.add(m.group(1).rstrip(".,;:)\"'`"))
    return out


def verify_unit(file: Path, root: Path, snap: Path | None) -> None:
    lines = lines_of(file)
    rel = file.relative_to(root) if root in file.parents or root == file.parent else file.name
    rel = str(rel)
    fm, fe = split_fm(lines)

    # G2 frontmatter
    if fe == 0:
        if file.name == "AGENTS.md":
            avv(f"G2 {rel}: nessun frontmatter (indice di flotta: ammesso).")
        else:
            err(f"G2 {rel}: frontmatter YAML assente o non delimitato.")
    else:
        g2 = True
        name = unquote(fm.get("name", ""))
        desc = unquote(fm.get("description", ""))
        if name and not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?", name.lower().replace(" ", "-")):
            err(f"G2 {rel}: name '{name}' non normalizzabile a kebab-case."); g2 = False
        if desc:
            if len(desc) > 1024:
                err(f"G2 {rel}: description {len(desc)} char (>1024)."); g2 = False
            if "<" in desc or ">" in desc:
                err(f"G2 {rel}: description con parentesi angolari."); g2 = False
        if g2:
            ok(f"G2 {rel}: frontmatter valido.")

    # G4 path interni citati esistono
    g4 = True
    for p in cited_paths(lines):
        pf = p.split("#")[0]
        if not ((file.parent / pf).exists() or (root / pf).exists()):
            err(f"G4 {rel}: path citato assente: {pf}"); g4 = False
    if g4:
        ok(f"G4 {rel}: path interni citati esistono.")

    # G7 righe corpo
    tot = len(lines)
    corpo = tot - (fe + 1) + 1 if fe else tot
    if corpo > SOGLIA_ERRORE:
        err(f"G7 {rel}: corpo {corpo} righe (>{SOGLIA_ERRORE}): refactor non riuscito.")
    elif corpo > SOGLIA_AVVISO:
        avv(f"G7 {rel}: corpo {corpo} righe (obiettivo <={SOGLIA_AVVISO}).")
    else:
        ok(f"G7 {rel}: corpo {corpo} righe.")

    # G8 ancore citate (file.md#ancora)
    g8n = g8bad = 0
    for p in cited_paths(lines):
        if "#" not in p:
            continue
        pf, anc = p.split("#", 1)
        if not pf.endswith(".md"):
            continue
        tgt = file.parent / pf
        if not tgt.exists():
            tgt = root / pf
        if not tgt.exists():
            continue
        g8n += 1
        if anc not in anchors(lines_of(tgt)):
            err(f"G8 {rel}: ancora inesistente: {pf}#{anc}"); g8bad += 1
    if g8n and not g8bad:
        ok(f"G8 {rel}: {g8n} ancore citate valide.")

    # G3 frontmatter invariato vs snapshot
    if snap and snap.is_file():
        cur = lines[1:fe - 1] if fe else []
        snl = lines_of(snap)
        _, sfe = split_fm(snl)
        old = snl[1:sfe - 1] if sfe else []
        if cur == old:
            ok(f"G3 {rel}: frontmatter invariato vs snapshot.")
        elif ARGS.consenti_modifica_triggering:
            avv(f"G3 {rel}: frontmatter modificato (consentito da flag).")
        else:
            err(f"G3 {rel}: frontmatter diverso dallo snapshot (V-3 triggering/dispatch).")


def is_unit(p: Path) -> bool:
    if {"evals", "node_modules", "__pycache__"} & set(p.parts):
        return False
    if p.name in ("SKILL.md", "AGENTS.md"):
        return True
    try:
        head = p.read_text(encoding="utf-8", errors="replace").lstrip("﻿").splitlines()[:1]
    except Exception:
        return False
    return bool(head) and head[0].strip() == "---"


def skill_extra_gates(target: Path) -> None:
    n = len([f for f in target.rglob("SKILL.md")
             if "evals" not in f.parts and "node_modules" not in f.parts])
    ok("G1 una sola SKILL.md.") if n == 1 else err(
        f"G1 trovate {n} SKILL.md: la piattaforma ne accetta una sola.")
    corpus = (target / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    for d in ("references", "scripts"):
        dd = target / d
        if dd.is_dir():
            for f in dd.rglob("*"):
                if f.is_file():
                    corpus += "\n" + f.read_text(encoding="utf-8", errors="replace")
    refs = target / "references"
    if refs.is_dir():
        g5 = True
        for f in sorted(x for x in refs.rglob("*") if x.is_file()):
            if f.name not in corpus:
                err(f"G5 foglia orfana: references/{f.name}"); g5 = False
        if g5:
            ok("G5 nessuna foglia orfana.")
    scr = target / "scripts"
    if scr.is_dir():
        for f in sorted(x for x in scr.rglob("*") if x.is_file()):
            if f.name not in corpus:
                avv(f"G6 script mai citato: scripts/{f.name}")
        ok("G6 script citati (bit eseguibile non verificato su questo OS).")


def main() -> int:
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--snapshot", default="")
    ap.add_argument("--consenti-modifica-triggering", dest="consenti_modifica_triggering",
                    action="store_true")
    ARGS = ap.parse_args()

    target = Path(ARGS.target)
    if not target.exists():
        print(f"[ERRORE] path inesistente: {target}", file=sys.stderr)
        return 1
    snapdir = Path(ARGS.snapshot) if ARGS.snapshot else None

    print("=" * 64)
    print(f"VERIFICA STRUTTURALE: {target}")
    print("=" * 64)

    if target.is_file():
        snap = (snapdir / target.name) if snapdir else None
        verify_unit(target, target.parent, snap)
    elif (target / "SKILL.md").is_file():
        skill_extra_gates(target)
        snap = (snapdir / "SKILL.md") if snapdir else None
        verify_unit(target / "SKILL.md", target, snap)
    else:
        units = sorted(p for p in target.rglob("*.md") if is_unit(p))
        if not units:
            err(f"Nessuna unita' verificabile in {target}.")
        for u in units:
            snap = None
            if snapdir:
                cand = snapdir / u.relative_to(target)
                snap = cand if cand.is_file() else None
            verify_unit(u, target, snap)
        print(f"  ({len(units)} unita' verificate)")

    print("-" * 64)
    if ERRORI:
        print(f"ESITO: FAIL ({ERRORI} errori, {AVVISI} avvisi) — correggere e rilanciare.")
        print(f"Ricorda i gate di grafo: scripts/mappa_riferimenti.py {target} --gate")
        return 1
    print(f"ESITO: PASS ({AVVISI} avvisi).")
    print(f"Prossimo: gate di grafo -> scripts/mappa_riferimenti.py {target} --gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
