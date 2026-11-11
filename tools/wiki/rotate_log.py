#!/usr/bin/env python3
"""
rotate_log.py — rotazione a soglia di wiki/log.md, byte-preserving.

Quando wiki/log.md raggiunge la soglia (default 180.000 byte), sposta in
wiki/log-AAAA-MM-GG.md (data della rotazione) il prefisso di entry, in ordine di file, datate
fino a quel giorno, e lascia in wiki/log.md tutto il resto. Sotto soglia non fa nulla (salvo
--forza). Nessuna riga viene riscritta, riordinata o rimossa (R.5): la ricomposizione
archivio + log ha lo sha256 dell'originale, verificato prima di scrivere. Il path canonico di
scrittura resta wiki/log.md.

Un archivio per rotazione, con la data del giorno nel nome: le rotazioni a soglia cadono a
metà mese e possono ripetersi nello stesso mese (al ritmo di ottobre 2026, ogni 4-6 giorni),
cosa che archivi per mese non permettevano. Due rotazioni nello stesso giorno: rifiuto.

Entry riconosciute: intestazioni `## ...` e blocchi `---` seguiti da `date:`. La data è quella
dell'intestazione (`## [AAAA-MM-GG` o `## AAAA-MM-GG`) o del campo `date:`; un'entry senza data
eredita quella della precedente. Entry datate dopo il giorno di rotazione, e quelle scritte dopo
di esse, restano in wiki/log.md nell'ordine di scrittura.

Il wiki-keeper non ha Bash: lo script lo esegue il coordinatore, con un claim su wiki/log.md
se la factory usa i claim (memory/active-sessions.yaml).

Uso:
  python3 tools/wiki/rotate_log.py                     # dry-run: dimensione, soglia, cosa sposterebbe
  python3 tools/wiki/rotate_log.py --apply             # esegue, se il log è alla soglia
  python3 tools/wiki/rotate_log.py --apply --forza     # esegue anche sotto soglia
  python3 tools/wiki/rotate_log.py --soglia 160000     # soglia diversa (byte)
Exit: 0 eseguito, sotto soglia o niente da ruotare; 1 rifiuto (archivio esistente, log cambiato
durante l'esecuzione, struttura inattesa).
"""
import argparse
import hashlib
import re
import sys
from datetime import date
from pathlib import Path

FACTORY_ROOT = Path(__file__).resolve().parent.parent.parent
HEADER_DATE = re.compile(rb"^## \[?(\d{4}-\d{2}-\d{2})")
YAML_DATE = re.compile(rb"^date: *(\d{4}-\d{2}-\d{2})")
ARCHIVE_LINE = b"> **Archivi:**"
ARCHIVE_LINE_LEGACY = b"> **Archivi mensili:**"
SOGLIA_DEFAULT = 180_000


def find_entries(lines: list) -> list:
    """[(indice_riga_inizio, 'AAAA-MM-GG' | None)] in ordine di file, frontmatter escluso."""
    start = 0
    if lines and lines[0].rstrip(b"\r\n") == b"---":
        for i in range(1, len(lines)):
            if lines[i].rstrip(b"\r\n") == b"---":
                start = i + 1
                break
    entries = []
    for i in range(start, len(lines)):
        line = lines[i]
        if line.startswith(b"## "):
            m = HEADER_DATE.match(line)
            entries.append((i, m.group(1).decode() if m else None))
        elif line.rstrip(b"\r\n") == b"---" and i + 1 < len(lines):
            m = YAML_DATE.match(lines[i + 1])
            if m:
                entries.append((i, m.group(1).decode()))
    filled, last = [], None
    for i, day in entries:
        last = day or last
        filled.append((i, last))
    return filled


def plan(raw: bytes, day: str):
    lines = raw.splitlines(keepends=True)
    entries = find_entries(lines)
    if not entries:
        return None, "nessuna entry riconosciuta"
    head_end = entries[0][0]
    cut_idx = next((k for k, (_, d) in enumerate(entries) if d is None or d > day), len(entries))
    if cut_idx == 0:
        return None, (f"la prima entry ({entries[0][1]}) è successiva a {day}: niente da ruotare")
    cut_line = entries[cut_idx][0] if cut_idx < len(entries) else len(lines)
    late = [(i + 1, d) for i, d in entries[cut_idx:] if d is not None and d <= day]
    return {
        "head": b"".join(lines[:head_end]),
        "block": b"".join(lines[head_end:cut_line]),
        "rest": b"".join(lines[cut_line:]),
        "moved": cut_idx,
        "kept": len(entries) - cut_idx,
        "late": late,
        "first_line": head_end + 1,
        "last_line": cut_line,
    }, None


def with_archive_pointer(head: bytes, day: str) -> bytes:
    link = f"[`log-{day}.md`](log-{day}.md)".encode()
    lines = head.splitlines(keepends=True)
    for k, line in enumerate(lines):
        if line.startswith(ARCHIVE_LINE) or line.startswith(ARCHIVE_LINE_LEGACY):
            lines[k] = line.rstrip(b"\r\n") + b" \xc2\xb7 " + link + b"\n"
            return b"".join(lines)
    anchor = max((k for k, line in enumerate(lines) if line.startswith(b">")), default=None)
    new = ARCHIVE_LINE + b" " + link + b"\n"
    if anchor is None:
        return head.rstrip(b"\n") + b"\n\n" + new + b"\n"
    lines.insert(anchor + 1, b"\n" + new)
    return b"".join(lines)


def project_name(root: Path) -> str:
    """`project.name` di factory.config.yaml, altrimenti il nome della cartella della factory."""
    cfg = root / "factory.config.yaml"
    if cfg.is_file():
        m = re.search(r"^project:[ \t]*\n(?:[ \t]+.*\n|[ \t]*\n)*?[ \t]+name:\s*[\"']?([^\"'#\n]+?)[\"']?\s*(?:#.*)?$",
                      cfg.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip()
    return root.resolve().name


def archive_preamble(day: str, first: str, size: int, soglia: int, project: str = "factory") -> bytes:
    return (
        "---\n"
        "type: wiki-log-archive\n"
        f"project: {project}\n"
        "append_only: true\n"
        'governed_by: "R.5 (append-only) — archivio di rotazione a soglia"\n'
        "rotated_from: wiki/log.md\n"
        f"rotated_at: {day}\n"
        f'range: "dal {first} al {day}"\n'
        f"log_bytes_at_rotation: {size}\n"
        f"soglia_bytes: {soglia}\n"
        "---\n\n"
        f"# Wiki Log — archivio fino al {day}\n\n"
    ).encode()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--soglia", type=int, default=SOGLIA_DEFAULT,
                    help=f"byte oltre i quali si ruota (default {SOGLIA_DEFAULT})")
    ap.add_argument("--forza", action="store_true", help="ruota anche sotto soglia")
    ap.add_argument("--apply", action="store_true", help="scrive i file (default: dry-run)")
    ap.add_argument("--oggi", help="data di rotazione AAAA-MM-GG (default: oggi; per i test)")
    ap.add_argument("--root", default=str(FACTORY_ROOT), help="root della factory (test)")
    a = ap.parse_args(argv)

    day = a.oggi or date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        print(f"--oggi non valido: {day}")
        return 1
    root = Path(a.root)
    log_path = root / "wiki" / "log.md"
    arc_path = root / "wiki" / f"log-{day}.md"

    raw = log_path.read_bytes()
    sha0 = hashlib.sha256(raw).hexdigest()
    if len(raw) < a.soglia and not a.forza:
        print(f"[rotate_log] wiki/log.md {len(raw)} byte, sotto la soglia di {a.soglia}: niente da fare")
        return 0
    p, why = plan(raw, day)
    if p is None:
        print(f"[rotate_log] {why}")
        return 0
    if arc_path.exists():
        print(f"[rotate_log] RIFIUTO: {arc_path.relative_to(root)} esiste già")
        return 1
    if hashlib.sha256(p["head"] + p["block"] + p["rest"]).hexdigest() != sha0:
        print("[rotate_log] RIFIUTO: lo split non ricompone l'originale")
        return 1

    first = find_entries(raw.splitlines(keepends=True))[0][1] or day
    new_log = with_archive_pointer(p["head"], day) + p["rest"]
    new_arc = archive_preamble(day, first, len(raw), a.soglia, project_name(root)) + p["block"]
    mode = "APPLY" if a.apply else "DRY-RUN"
    print(f"[rotate_log] {mode} rotazione {day} (log {len(raw)} byte, soglia {a.soglia}): righe "
          f"{p['first_line']}-{p['last_line']} ({len(p['block'])} byte, {p['moved']} entry) -> "
          f"wiki/log-{day}.md; wiki/log.md {len(raw)} -> {len(new_log)} byte, {p['kept']} entry restano")
    for line_no, d in p["late"]:
        print(f"  entry datata {d} a riga {line_no}, dopo un'entry successiva: resta in wiki/log.md")
    if not a.apply:
        return 0

    if hashlib.sha256(log_path.read_bytes()).hexdigest() != sha0:
        print("[rotate_log] RIFIUTO: wiki/log.md è cambiato durante l'esecuzione, rilancia")
        return 1
    arc_path.write_bytes(new_arc)
    log_path.write_bytes(new_log)
    ok = arc_path.read_bytes().endswith(p["block"]) and log_path.read_bytes().endswith(p["rest"])
    print(f"[rotate_log] sha256 originale {sha0[:16]}: ricomposizione verificata; scrittura {'OK' if ok else 'DA VERIFICARE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
